"""Native checkpoint products: direct Session arrays are the independent oracle."""
import copy
import itertools
import json
import os

import numpy as np

SOURCES = ('voxel', 'curved')
MODES = ('valid-resume', 'expected-mismatch', 'save-cancel', 'import-cancel',
         'truncated', 'unsupported-schema', 'corrupt-populations')


def native_data_cases():
    for source, mode in itertools.product(SOURCES, MODES):
        yield dict(id='native-data/'+source+'/'+mode, source=source, mode=mode,
                   expected=mode == 'valid-resume')


def native_case(source):
    from .exports import source_case
    import lettuce as lt
    spec = source_case('physical3D')
    spec['basis'] = np.eye(3).tolist()
    if source == 'curved':
        shape = spec['shape']
        solid = set(spec['solid'])
        links = []
        for site in solid:
            location = np.asarray(np.unravel_index(site, shape))
            for q, direction in enumerate(lt.D3Q19().e[1:], 1):
                fluid = location-direction
                index = int(np.ravel_multi_index(fluid, shape))
                if index not in solid:
                    links.append([q, index, .25 if q % 2 else .75])
        spec['wall_links'] = links
    return spec


def assert_state(session, populations, fields, quality, iteration, local_time):
    assert session.flow.i == iteration
    assert float(session.flow.units.convert_time_to_pu(session.flow.i)) == local_time
    np.testing.assert_array_equal(session.flow.f.detach().cpu().numpy(), populations)
    actual = session.fields()
    assert set(actual) == set(fields)
    for key in fields:
        np.testing.assert_array_equal(actual[key], fields[key])
    assert session.quality == quality


def exercise_native_data(row, directory, device):
    from hawa.plugin import Session, SESSIONS, dispatch
    from hawa.jobs import Job, JOBS, Cancelled, dispatch_job
    before_sessions, before_jobs = set(SESSIONS), set(JOBS)
    session = Session(native_case(row['source']), device)
    owned = []
    SESSIONS[session.id] = session
    path = directory/row['id']/device.replace(':', '-')/'native.npz'
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = b'previous complete native destination\n'
    path.write_bytes(previous)
    mode = row['mode']
    context = dict(case_id='matrix-import', revision=9, generation=4, version=2)
    settings = dict(block_width=.5, target_steps=10, view=dict(field='speed', axis=2))

    class ControlledJob(Job):
        def checkpoint(self, steps, state='running'):
            if ((mode == 'save-cancel' and steps == 1)
                    or (mode == 'import-cancel' and self.session is not None)):
                raise Cancelled('matrix native-data cancellation')
            super().checkpoint(steps, state)

    def execute(request):
        job = ControlledJob(request)
        JOBS[job.id] = job
        owned.append(job)
        job.work()
        return job

    try:
        session.advance(6)
        populations = session.flow.f.detach().cpu().numpy().copy()
        fields = session.fields()
        quality = copy.deepcopy(session.quality)
        local_time = float(session.flow.units.convert_time_to_pu(6))
        means = {name: getattr(session, name).detach().cpu().numpy().copy()
                 for name in ('mean_u', 'mean_p', 'mean_rho')}
        samples = session.samples
        assert samples == 1
        initial_mass = session.initial_mass
        expected = dict(case_hash=session.key, iteration=6, state=session.state)
        if mode == 'expected-mismatch':
            expected['iteration'] += 1
        request = dict(op='data', action='save', session=session.id, path=str(path),
                       expected=expected, native_settings=settings, attribution=context)
        saved = execute(dict(kind='query', request=request))
        if mode in ('expected-mismatch', 'save-cancel'):
            assert saved.state == ('failed' if mode == 'expected-mismatch' else 'cancelled')
            if mode == 'expected-mismatch':
                assert 'exact stopped source' in saved.error
            assert saved.result is None and path.read_bytes() == previous
            assert list(path.parent.iterdir()) == [path]
            return False
        assert saved.state == 'completed', saved.error
        result = saved.result
        # The request may be relative; the public result preserves its lexical
        # absolute identity (without resolving symlinks).
        assert result['path'] == os.path.abspath(path) and result['format'] == 'npz'
        assert result['schema'] == 'hawa-native-data-1'
        with np.load(path, allow_pickle=False) as archive:
            assert set(archive.files) == {'populations', 'metadata', 'mean_u', 'mean_p', 'mean_rho'}
            for name, values in means.items():
                np.testing.assert_array_equal(archive[name], values)
            stored = archive['populations'].copy()
            metadata = json.loads(str(archive['metadata']))
        np.testing.assert_array_equal(stored, populations)
        assert stored.dtype == np.float32
        assert metadata == result['metadata']
        for key, value in dict(schema='hawa-native-data-1', case=session.spec,
                case_hash=session.key, iteration=6, local_time=local_time,
                time_origin=2., absolute_time=local_time+2., source_state=session.state,
                source_session=session.id, quality=quality, native_settings=settings,
                attribution=context, population_storage='f', samples=samples,
                initial_mass=initial_mass).items():
            assert metadata[key] == value
        if mode == 'truncated':
            path.write_bytes(path.read_bytes()[:32])
        elif mode == 'unsupported-schema':
            metadata['schema'] = 'hawa-native-data-999'
            np.savez_compressed(path, populations=stored, metadata=np.array(json.dumps(metadata)), **means)
        elif mode == 'corrupt-populations':
            stored.flat[0] = np.nan
            np.savez_compressed(path, populations=stored, metadata=np.array(json.dumps(metadata)), **means)
        import_bytes = path.read_bytes()
        imported = execute(dict(kind='native_data_import', path=str(path), device=device, context=context))
        assert path.read_bytes() == import_bytes
        assert list(path.parent.iterdir()) == [path]
        if mode != 'valid-resume':
            assert imported.state == ('cancelled' if mode == 'import-cancel' else 'failed')
            assert imported.result is None and imported.session is None
            if mode != 'import-cancel':
                reason = {'truncated': 'File is not a zip file',
                          'unsupported-schema': 'Unsupported native data metadata schema',
                          'corrupt-populations': 'finite float32 D3Q19 data and positive density'}[mode]
                assert reason in imported.error
            assert set(SESSIONS) == before_sessions | {session.id}
            return False
        assert imported.state == 'completed', imported.error
        value = imported.result
        restored = SESSIONS[value['status']['session']]
        assert restored is imported.session and restored.id != session.id
        assert value['status']['state'] == restored.state == 'paused'
        assert restored.thread is None
        assert value['case'] == session.spec and value['metadata'] == metadata
        assert value['context'] == context
        assert_state(restored, populations, fields, quality, 6, local_time)
        assert restored.samples == samples and restored.initial_mass == initial_mass
        for name, values in means.items():
            np.testing.assert_array_equal(getattr(restored, name).cpu().numpy(), values)
        for key, values in session.fields(mean=True).items():
            np.testing.assert_array_equal(restored.fields(mean=True)[key], values)
        # Repeated public views must not advance a paused imported session.
        for _ in range(2):
            assert dispatch(dict(op='status', session=restored.id))['steps'] == 6
            dispatch(dict(op='slice', session=restored.id, axis=2, index=2))
        assert_state(restored, populations, fields, quality, 6, local_time)
        session.advance(6)
        restored.advance(6)
        assert_state(restored, session.flow.f.detach().cpu().numpy(), session.fields(),
                     session.quality, 12, float(session.flow.units.convert_time_to_pu(12)))
        assert restored.samples == session.samples
        for name in ('mean_u', 'mean_p', 'mean_rho'):
            np.testing.assert_array_equal(getattr(restored, name).cpu().numpy(), getattr(session, name).cpu().numpy())
        return True
    finally:
        for job in owned:
            dispatch_job(dict(op='evaluate_control', job=job.id, action='close'))
        session.pause()
        SESSIONS.pop(session.id, None)
        assert set(SESSIONS) == before_sessions and set(JOBS) == before_jobs
