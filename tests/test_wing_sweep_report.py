"""Saved reports show real captured data and never promote rejected curves."""
from copy import deepcopy
import xml.etree.ElementTree as ET

import numpy as np
import pytest

from scripts import wing_sweep_report as renderer
from scripts.run_wing_sweep import run_prepared
from test_real_sweep_pipeline import prepared_cube


@pytest.fixture(scope='module')
def control():
    entries = {name: prepared_cube(name, warning=warning) for name, warning in
               [('before', False), ('warning', True), ('after', False)]}
    return run_prepared(entries), entries


def test_real_report_and_clickable_segments(control):
    report, entries = control
    figure = renderer.polar_figure(report['records'])
    assert [len(ax.lines) for ax in figure.axes] == [2, 2, 2]
    assert [artist.offsetbox.get_children()[0].get_url() for artist in figure.axes[0].artists] == ['#candidate-0', '#candidate-2']
    assert [line.get_xdata().tolist() for line in figure.axes[0].lines] == [[0.], [0.]]
    assert figure.axes[0].lines[0].get_ydata()[0] == report['records'][0]['result']['coefficients']['CL']
    text = renderer.report_html(report, entries)
    assert 'Grid/domain sensitivity FAILS' in text
    assert 'href="#candidate-0"' in text and 'href="#candidate-2"' in text
    assert '<td>rejected</td>' in text
    assert report['details']['before']['session'] in text
    assert 'after-collision-before-obstacle-reflection-and-stream' in text
    assert 'cannot resume a solver' in text
    assert '<script' not in text and 'href="https://' not in text and 'src="https://' not in text
    root = ET.fromstring(renderer.svg(figure))
    links = [a.attrib['{http://www.w3.org/1999/xlink}href']
             for a in root.iter('{http://www.w3.org/2000/svg}a')]
    assert links == ['#candidate-0', '#candidate-2'] * 3
    for a in root.iter('{http://www.w3.org/2000/svg}a'):
        assert list(a), 'Every candidate link must wrap a rendered marker'


def test_raw_figures_match_retained_arrays_and_preserve_invalid_gaps(control):
    report, entries = control
    detail = report['details']['before']
    figure = renderer.case_figure(detail, entries['before'])
    forces, probes, field = figure.axes[1:4]
    assert forces.lines[0].get_xdata().tolist() == [r['time_s'] for r in detail['load_samples']]
    assert forces.lines[0].get_ydata().tolist() == [r['force_world_n'][0] for r in detail['load_samples']]
    rows = [r for r in detail['probe_samples'] if r['probe_id'] == 'near-inlet']
    assert probes.lines[0].get_ydata().tolist() == [r['pressure_pa'] for r in rows]
    assert [t.get_text() for t in probes.get_legend().get_texts()] == ['near-inlet', 'solid', 'boundary']
    assert np.isnan(probes.lines[1].get_ydata()).all()  # solid probe is never zero-filled
    arrays = detail['last_field']; j = arrays['pressure'].shape[1] // 2
    rendered = field.images[0].get_array()
    np.testing.assert_array_equal(rendered.mask, (arrays['solid'][:,j,:] | arrays['boundary_nodes'][:,j,:]).T)
    np.testing.assert_array_equal(rendered.data, arrays['pressure'][:,j,:].T)
    changed = deepcopy(detail)
    changed['last_field'] = None
    changed['probe_samples'] = []
    changed['load_samples'][0]['valid'] = False
    figure = renderer.case_figure(changed, entries['before'])
    assert np.isnan(figure.axes[1].lines[0].get_ydata()[0])
    assert figure.axes[3].texts[0].get_text() == 'No captured field'
    assert figure.axes[2].get_legend() is None


@pytest.mark.parametrize('change,match', [
    ('schema', 'Expected'), ('device', 'Expected'), ('cleanup', 'drained'),
    ('duplicate', 'inventory'), ('inventory', 'inventory'), ('detail_inventory', 'inventory'),
    ('candidate', 'Prepared'), ('generation', 'Prepared'), ('detail', 'Retained'),
    ('detail_candidate', 'Retained'), ('sample', 'Sample'), ('session', 'field'), ('phase', 'field')])
def test_identity_mismatches_reject_before_rendering(control, change, match):
    report, entries = deepcopy(control)
    if change == 'schema': report['schema'] = 'different'
    if change == 'device': report['device'] = 'cuda:0'
    if change == 'cleanup': report['cleanup']['live_workers'] = 1
    if change == 'duplicate': report['records'].append(deepcopy(report['records'][0]))
    if change == 'inventory': del entries['after']
    if change == 'detail_inventory': del report['details']['after']
    if change == 'candidate': report['records'][0]['candidate']['angle_deg'] = 5.
    if change == 'generation': report['records'][0]['generation'] += 1
    if change == 'detail': report['details']['before']['identity']['revision'] += 1
    if change == 'detail_candidate': report['details']['before']['candidate']['angle_deg'] = 5.
    if change == 'sample': report['details']['before']['load_samples'][0]['identity']['revision'] += 1
    if change == 'session': report['details']['before']['last_field']['snapshot']['session'] = 'other'
    if change == 'phase': report['details']['before']['last_field']['snapshot']['phase'] = 'other'
    with pytest.raises(ValueError, match=match): renderer.report_html(report, entries)


def test_escaping_unstarted_and_no_capture(control):
    report, entries = deepcopy(control)
    report['records'][0]['reason'] = '<script>alert("x")</script>'
    report['records'][0]['state'] = 'cancelled'
    report['details']['before'] = None
    report['details']['after']['last_field'] = None
    report['details']['after']['final_quality'] = {'reason': '</pre><script>bad</script>'}
    text = renderer.report_html(report, entries)
    assert '&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;' in text
    assert '&lt;/pre&gt;&lt;script&gt;bad&lt;/script&gt;' in text
    assert 'Candidate did not start' in text and '<script>' not in text


@pytest.mark.parametrize('failed,coarse', [(False, False), (True, False), (False, True), (True, True)])
def test_command_preserves_existing_report_and_returns_failure(control, tmp_path, monkeypatch, failed, coarse):
    report, entries = deepcopy(control)
    report['records'] = [report['records'][0]]
    report['details'] = {'before': report['details']['before']}
    entries = {'before': entries['before']}
    report['timed_out'] = failed
    def recipe(refined):
        assert refined is not coarse
        return {'fixture': 'real CPU'}
    monkeypatch.setattr(renderer, 'demo_sweep', recipe)
    def prepare(recipe, settling, sample, tolerance, probes):
        assert recipe == {'fixture': 'real CPU'}
        assert (settling, sample, tolerance) == ((1200, 81, .05) if coarse else (3000, 201, .05))
        assert probes == [dict(probe_id='upstream', position_world_m=[-.1, 0., .1])]
        return entries
    monkeypatch.setattr(renderer, 'prepare_entries', prepare)
    monkeypatch.setattr(renderer, 'run_prepared', lambda prepared, timeout: report)
    path = tmp_path / 'report.html'
    assert renderer.main(['--output', str(path), '--timeout', '5'] + (['--coarse'] if coarse else [])) == int(failed)
    original = path.read_bytes()
    assert b'Grid/domain sensitivity FAILS' in original
    with pytest.raises(FileExistsError): renderer.main(['--output', str(path)])
    assert path.read_bytes() == original


def test_module_entrypoint_help(monkeypatch, capsys):
    import runpy
    import sys
    monkeypatch.setattr(sys, 'argv', ['wing_sweep_report', '--help'])
    with pytest.raises(SystemExit) as stopped:
        runpy.run_module('scripts.wing_sweep_report', run_name='__main__')
    assert stopped.value.code == 0
    assert '--output' in capsys.readouterr().out
