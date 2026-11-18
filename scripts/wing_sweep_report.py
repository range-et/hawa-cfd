"""Run the CPU wing example and save a self-contained, clickable HTML report.

Run with .venv/bin/python -m scripts.wing_sweep_report --output /new/report.html.
This is a blocking developer example, never a Rhino/Grasshopper callback.
"""
import argparse
from html import escape
from io import StringIO
import json
import re
from pathlib import Path

import numpy as np
from matplotlib import rc_context
from matplotlib.backends.backend_svg import FigureCanvasSVG
from matplotlib.figure import Figure
from matplotlib.offsetbox import AnnotationBbox, DrawingArea
from matplotlib.patches import Circle

from hawa.fields import validate
from hawa.sweeps import plot_segments
from scripts.run_wing_sweep import prepare_entries, run_prepared
from scripts.wing_solver_recipe import demo_sweep


def theme_css():
    """Embed shared Monad tokens and local font fallbacks; never import a network font."""
    root = Path(__file__).resolve().parents[1]
    palette = json.loads((root / 'vendor/monad_system/colors.json').read_text())
    shared = (root / 'site/assets/monad/monad.css').read_text()
    fonts = '\n'.join(re.findall(r'--font-(?:sans|mono):[^;]+;', shared)[:2])
    rules = []
    for selector, mode in (('body', 'Default_Colors'), ('body:has(#light-theme:checked)', 'Light_Mode')):
        tokens = palette[mode]['General_UI_Colors']
        declarations = ';'.join('--wing-' + key.lower().replace('_', '-') + ':' + item['hex']
                                for key, item in tokens.items())
        rules.append(selector + '{' + declarations + '}')
    signals = palette['Default_Colors']
    colors = [signals['Information_Indicators'][key]['hex'] for key in ('Information_1', 'Information_2', 'Information_3')]
    colors.append(signals['Warnings_and_Alerts']['Warning_1']['hex'])
    return '\n'.join(rules) + ':root{' + fonts + ';' + ';'.join('--wing-signal-' + str(i) + ':' + color for i, color in enumerate(colors)) + '}'+ '''
body{font:16px var(--font-sans);color:var(--wing-primary-text);background:var(--wing-background);max-width:1200px;margin:32px auto;padding:0 20px;color-scheme:dark}
body:has(#light-theme:checked){color-scheme:light}
section{background:var(--wing-layer-01);padding:20px;margin:24px 0;border:1px solid var(--wing-border);scroll-margin-top:20px}
svg{width:100%;height:auto}svg text{font-family:var(--font-sans)!important}
table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:8px;border-bottom:1px solid var(--wing-border)}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font:12px var(--font-mono)}a{color:var(--wing-signal-0)}
a:focus-visible,input:focus-visible{outline:2px solid var(--wing-signal-3);outline-offset:4px}
.limit{background:var(--wing-layer-02);border-left:4px solid var(--wing-signal-3);padding:16px}h1{margin-bottom:8px}
.theme-control{display:block;padding:12px 0}#light-theme{accent-color:var(--wing-signal-0)}
'''


def themed_svg(text):
    """Theme presentation strokes/fills only; keep scientific raster and geometry intact."""
    colors = {'#ffffff': '--wing-layer-01', '#000000': '--wing-primary-text',
              '#b0b0b0': '--wing-border', '#cccccc': '--wing-border',
              '#327c93': '--wing-signal-0', '#cb5a35': '--wing-signal-3',
              '#1f77b4': '--wing-signal-0', '#ff7f0e': '--wing-signal-3', '#2ca02c': '--wing-signal-2'}
    for old, variable in colors.items():
        text = text.replace('fill: ' + old, 'fill: var(' + variable + ')').replace('stroke: ' + old, 'stroke: var(' + variable + ')')
    # Matplotlib inherits black when text has no explicit fill declaration.
    return text.replace('<svg ', '<svg style="fill:var(--wing-primary-text)" ', 1)


def svg(figure):
    """Render a standalone vector figure without a GUI or external resources."""
    stream = StringIO()
    with rc_context({'svg.fonttype': 'none'}):
        FigureCanvasSVG(figure).print_svg(stream, metadata={'Date': None})
    text = stream.getvalue()
    return themed_svg('\n'.join(line.rstrip() for line in text[text.index('<svg'):].splitlines()))


def polar_figure(records):
    """Use the controller's admission rule; every unusable candidate breaks curves."""
    figure = Figure(figsize=(12, 3.6), layout='constrained')
    indices = {r['candidate']['candidate_id']: i for i, r in enumerate(records)}
    for axis, kind, xlabel, ylabel in zip(figure.subplots(1, 3),
            ('cl_alpha', 'cd_alpha', 'cl_cd'), ('Angle (deg)', 'Angle (deg)', 'CD'),
            ('CL', 'CD', 'CL')):
        for segment in plot_segments(records, kind):
            axis.plot([p['x'] for p in segment], [p['y'] for p in segment], color='#327c93')
            for point in segment:
                marker = DrawingArea(14, 14)
                marker.add_artist(Circle((7, 7), 3.5, color='#cb5a35',
                    url='#candidate-' + str(indices[point['candidate']['candidate_id']])))
                axis.add_artist(AnnotationBbox(marker, (point['x'], point['y']),
                                               frameon=False, pad=0, zorder=3))
        axis.set(xlabel=xlabel, ylabel=ylabel)
        axis.grid(alpha=.2)
    return figure


def case_figure(detail, entry):
    """Plot raw retained observations, not reconstructed or qualified loads."""
    figure = Figure(figsize=(11, 8), layout='constrained')
    geometry, forces, pressure, field = figure.subplots(2, 2).flat
    vertices = np.asarray(entry['geometry']['vertices_m'])
    for triangle in entry['geometry']['triangles']:
        loop = vertices[list(triangle) + [triangle[0]]]
        geometry.plot(loop[:, 0], loop[:, 1], color='#327c93', linewidth=.3)
    geometry.set(xlabel='World X (m)', ylabel='World Y (m)', title='Actual candidate mesh — top view', aspect='equal')
    for body in entry['request']['bodies']:
        rows = [r for r in detail['load_samples'] if r['body_id'] == body['body_id']]
        for component, name in enumerate(('Fx', 'Fy', 'Fz')):
            forces.plot([r['time_s'] for r in rows],
                        [r['force_world_n'][component] if r['valid'] else np.nan for r in rows],
                        label=body['body_id'] + ' ' + name)
    forces.set(xlabel='Source time (s)', ylabel='Fluid force, world axes (N)', title='Raw load history (including settling)')
    forces.legend(fontsize=7)
    for probe_id in dict.fromkeys(r['probe_id'] for r in detail['probe_samples']):
        rows = [r for r in detail['probe_samples'] if r['probe_id'] == probe_id]
        pressure.plot([r['time_s'] for r in rows],
                      [r['pressure_pa'] if r['valid'] else np.nan for r in rows], label=probe_id)
    pressure.set(xlabel='Source time (s)', ylabel='Gauge pressure (Pa)', title='Raw probes — invalid samples are gaps')
    pressure.grid(alpha=.2)
    if detail['probe_samples']:
        pressure.legend(fontsize=7)
    arrays = detail['last_field']
    if arrays is not None:
        validate({k: v for k, v in arrays.items() if k != 'snapshot'}, {'case': entry['spec']})
        j = arrays['pressure'].shape[1] // 2
        values = np.ma.array(arrays['pressure'][:, j, :],
                             mask=arrays['solid'][:, j, :] | arrays['boundary_nodes'][:, j, :])
        image = field.imshow(values.T, origin='lower', aspect='equal', cmap='coolwarm')
        figure.colorbar(image, ax=field, label='Gauge pressure (Pa)')
        field.set(title='Retained field: step {} / {:.6g} s; j={}'.format(
            arrays['snapshot']['steps'], arrays['snapshot']['physical_time'], j),
            xlabel='Domain lattice i', ylabel='Domain lattice k')
    else:
        field.text(.5, .5, 'No captured field', ha='center', transform=field.transAxes)
    return figure


def report_html(report, prepared):
    """Bind charts to exact prepared candidate identities and escape all text."""
    if report['schema'] != 'hawa-headless-sweep-demo-1' or report['device'] != 'cpu':
        raise ValueError('Expected a CPU headless sweep report')
    if report['cleanup'] != dict(handles=0, live_workers=0, session_ids=[]):
        raise ValueError('Owned solver resources must be drained before reporting')
    records = report['records']
    ids = [r['candidate']['candidate_id'] for r in records]
    if len(set(ids)) != len(ids) or set(ids) != set(prepared) or set(ids) != set(report['details']):
        raise ValueError('Report and prepared candidate inventory differ')
    sections = []
    table = []
    for index, record in enumerate(records):
        candidate = record['candidate']
        ident = candidate['candidate_id']
        entry, detail = prepared[ident], report['details'][ident]
        if candidate != entry['candidate'] or record['generation'] != entry['request']['identity']['generation']:
            raise ValueError('Prepared candidate identity differs from report')
        table.append('<tr><td><a href="#candidate-{}">{}</a></td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>'.format(
            index, escape(ident), candidate['angle_deg'], candidate['speed_m_s'],
            escape(record['state']), escape(record['reason'])))
        section = '<section id="candidate-{}"><h2>{}</h2><p>{}: {}</p>'.format(
            index, escape(ident), escape(record['state']), escape(record['reason']))
        if detail is None:
            section += '<p>Candidate did not start; no field or measurements exist.</p>'
        else:
            if detail['identity'] != entry['request']['identity'] or detail['candidate'] != candidate:
                raise ValueError('Retained detail identity differs from candidate')
            for row in detail['load_samples'] + detail['probe_samples']:
                if row['identity'] != detail['identity']:
                    raise ValueError('Sample identity differs from retained candidate')
            stamp = None if detail['last_field'] is None else detail['last_field']['snapshot']
            if stamp is not None and (stamp['session'] != detail['session'] or stamp['phase'] != detail['phase']):
                raise ValueError('Retained field source differs from candidate')
            metadata = dict(identity=detail['identity'], session=detail['session'], phase=detail['phase'],
                            field_capture=stamp, references=entry['request']['references'],
                            grid={key: entry['spec'][key] for key in ('shape', 'dx', 'origin', 'basis')},
                            fluid={key: entry['spec'][key] for key in ('density', 'viscosity', 'mach')},
                            measurement_window=entry['request']['window'],
                            summary=detail['summary'], final_quality=detail.get('final_quality'))
            section += svg(case_figure(detail, entry))
            section += '<details><summary>Identity, units, references, quality and measurement window</summary><pre>'
            section += escape(json.dumps(metadata, indent=2, allow_nan=False)) + '</pre></details>'
        sections.append(section + '<p><a href="#overview">Back to all cases</a></p></section>')
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Hawa — experimental wing sweep</title><style>
''' + theme_css() + '''
</style><body><label class="theme-control"><input id="light-theme" type="checkbox"> Light theme</label><main id="overview"><h1>Experimental wing sweep</h1>
<p class="limit">CPU workflow demonstration. Grid/domain sensitivity FAILS; no aerodynamic accuracy or physical qualification.
Synthetic viscosity; full-way staircase walls. These 3D wing coefficients are not section polars.</p>
<p>Click a highlighted point or a case ID for its actual mesh, raw histories, retained field and source identity.
Rejected, failed and cancelled cases remain listed and break coefficient curves. Raw histories include settling and may include rejected quality.</p>
''' + svg(polar_figure(records)) + '<table><thead><tr><th>Case</th><th>Angle (deg)</th><th>Speed (m/s)</th><th>State</th><th>Reason</th></tr></thead><tbody>' + ''.join(table) + '</tbody></table>' + ''.join(sections) + '''
<p>Saved viewing artifact only: this HTML cannot resume a solver and is not numerical CSV interchange.
Stationary pre-reflection measurements cannot be labelled as the existing moving-body step-end CSV contract.</p></main></body></html>'''


def main(argv=None):
    """Run the declared demo; refuse overwrites and retain failed runs for review."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--timeout', type=float, default=3600.)
    parser.add_argument('--coarse', action='store_true', help='Explicit quick 25 mm grid; default is 10 mm')
    args = parser.parse_args(argv)
    if args.output.exists():
        raise FileExistsError('Choose a new report path; existing results are preserved')
    recipe = demo_sweep(refined=not args.coarse)
    settling, samples = (1200, 81) if args.coarse else (3000, 201)
    entries = prepare_entries(recipe, settling, samples, .05,
                              probes=[dict(probe_id='upstream', position_world_m=[-.1, 0., .1])])
    report = run_prepared(entries, args.timeout)
    html = report_html(report, entries)
    with args.output.open('x', encoding='utf-8') as stream:
        stream.write(html)
    print(str(args.output.resolve()))
    return 0 if not report['timed_out'] and all(r['state'] == 'completed' for r in report['records']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
