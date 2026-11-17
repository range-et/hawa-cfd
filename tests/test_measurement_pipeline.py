"""Cross-lane contract checks. Manufactured loads are NOT wing CFD predictions."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from hawa.measurements import summarize
from hawa.sweeps import SweepController, plot_segments
from scripts.wing_measurement_recipe import sweep_recipe


FIXTURE = Path(__file__).parent / 'fixtures/measurements/measurement-v1.json'


class ManufacturedExecutor:
    """Translate the real measurement reducer into the frozen sweep envelope."""
    def __init__(self, fixture, references, reject_middle=False):
        self.fixture = fixture
        self.references = references
        self.reject_middle = reject_middle
        self.open_handles = []
        self.closed = []
        self.started = []

    def start(self, candidate, generation):
        assert not self.open_handles
        handle = dict(candidate=deepcopy(candidate), generation=generation)
        self.open_handles.append(handle)
        self.started.append(candidate['candidate_id'])
        return handle

    def poll(self, handle):
        candidate = handle['candidate']
        request = deepcopy(self.fixture['request'])
        request['identity'].update(candidate_id=candidate['candidate_id'],
                                   generation=handle['generation'],
                                   case_hash=candidate['case_hash'],
                                   geometry_hash=candidate['geometry_hash'])
        request['references'].update(speed_m_s=candidate['speed_m_s'],
                                     area_m2=self.references['area_m2'],
                                     chord_m=self.references['chord_m'])
        samples = deepcopy(self.fixture['samples'])
        for sample in samples:
            sample['identity'] = deepcopy(request['identity'])
        if self.reject_middle and candidate['candidate_id'] == 'wing-001':
            for sample in samples[2:]:
                sample['force_world_n'][2] *= 2
        summary = summarize(request, samples)
        body = summary['bodies'][0]
        result = dict(identity=summary['identity'], quality=body['quality'], window_valid=True,
                      stationarity_passed=body['stationarity']['passed'],
                      coefficients={name: body['mean'][name] for name in ('CL', 'CD')})
        return dict(state='completed', candidate_id=candidate['candidate_id'],
                    generation=handle['generation'], result=result)

    def pause(self, handle):
        assert handle in self.open_handles

    def resume(self, handle):
        assert handle in self.open_handles

    def cancel(self, handle):
        assert handle in self.open_handles

    def close(self, handle):
        self.open_handles.remove(handle)
        self.closed.append(handle['candidate']['candidate_id'])
        return True


def test_manufactured_recipe_measurements_and_sweep_keep_identity_and_gap():
    recipe = sweep_recipe({}, [dict(angle_deg=a, speed_m_s=3.) for a in (-2., 0., 2.)],
                          dict(collision='bgk', viscosity=.1, density=2.))
    fixture = json.loads(FIXTURE.read_text())
    executor = ManufacturedExecutor(fixture, recipe['references'], reject_middle=True)
    controller = SweepController(recipe['candidates'], executor, generation=7)
    controller.tick()
    assert not executor.started
    controller.run()
    for _ in range(9):  # exactly start, poll, cleanup for each of three candidates
        controller.tick()
    assert controller.state == 'completed'
    assert [r['state'] for r in controller.records] == ['completed', 'rejected', 'completed']
    assert executor.started == executor.closed == ['wing-000', 'wing-001', 'wing-002']
    assert executor.open_handles == []
    segments = plot_segments(controller.records)
    assert [len(s) for s in segments] == [1, 1]
    assert [s[0]['x'] for s in segments] == [-2., 2.]
    expected_cl = 72. / (9. * recipe['references']['area_m2'])
    assert [s[0]['y'] for s in segments] == pytest.approx([expected_cl, expected_cl])
    for segment, candidate in zip(segments, (recipe['candidates'][0], recipe['candidates'][2])):
        assert segment[0]['identity']['geometry_hash'] == candidate['geometry_hash']
        assert segment[0]['identity']['case_hash'] == candidate['case_hash']
        assert segment[0]['identity']['generation'] == 7
    assert len({c['geometry_hash'] for c in recipe['candidates']}) == 3
    # Same static lift data at each angle is intentional: this test is not a polar.


def test_speed_changes_reference_coefficients_without_changing_geometry():
    recipe = sweep_recipe({}, [dict(angle_deg=0., speed_m_s=s) for s in (3., 6.)],
                          dict(collision='bgk', viscosity=.1, density=2.))
    fixture = json.loads(FIXTURE.read_text())
    executor = ManufacturedExecutor(fixture, recipe['references'])
    controller = SweepController(recipe['candidates'], executor)
    controller.run()
    for _ in range(6):
        controller.tick()
    a, b = controller.records
    assert a['result']['coefficients']['CL'] == pytest.approx(4*b['result']['coefficients']['CL'])
    assert a['candidate']['geometry_hash'] == b['candidate']['geometry_hash']
    assert a['candidate']['case_hash'] != b['candidate']['case_hash']
    saved = controller.save()
    reopened = SweepController(saved, executor)
    reopened.tick()
    assert reopened.state == 'idle'
    assert executor.open_handles == []
    assert executor.started == ['wing-000', 'wing-001']
