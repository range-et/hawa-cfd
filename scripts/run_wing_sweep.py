"""CPU/headless example driver; internal results, not the shared export format.

Run from the checkout with ``.venv/bin/python -m scripts.run_wing_sweep``.
This blocking command-line driver must not run on a Rhino/GH solution thread.
"""
import argparse
from copy import deepcopy
import json
import math
import time

from hawa.atmosphere import scaling_report
from hawa.measurements import validate_request
from hawa.sweeps import SweepController, plot_segments


def prepare_entries(recipe, settling_steps, sample_steps, tolerance, case_id='wing-demo',
                    generation=0, probes=None):
    """Bind final voxelized cases to explicit step-aligned SI measurement windows."""
    if (type(settling_steps) is not int or settling_steps < 0 or
            type(sample_steps) is not int or sample_steps < 4 or
            settling_steps + sample_steps > 100000):
        raise ValueError('Require nonnegative settling, >=4 samples and <=100000 total steps')
    entries = {}
    for candidate in recipe['candidates']:
        raw = recipe['prepared'][candidate['candidate_id']]
        spec = raw['case']
        dt = scaling_report(spec['dx'], spec['speed'], spec['viscosity'],
                            spec['mach'])['time_step_seconds']
        request = dict(schema='hawa-measurement-1', identity=dict(
            case_id=case_id, candidate_id=candidate['candidate_id'], revision=0,
            generation=generation, case_hash=candidate['case_hash'],
            geometry_hash=candidate['geometry_hash']), references=raw['references'],
            bodies=raw['bodies'], window=dict(start_s=settling_steps*dt,
            end_s=(settling_steps+sample_steps-1)*dt, minimum_samples=sample_steps,
            stationarity_absolute_coefficient_tolerance=tolerance))
        validate_request(request)
        entries[candidate['candidate_id']] = deepcopy(dict(candidate=candidate, spec=spec,
            body_indices=raw['body_indices'], request=request,
            probes=[] if probes is None else probes, origin_world_m=raw['origin_world_m'],
            basis=raw['basis'], steps=settling_steps+sample_steps,
            selected_body_id='wing', dtype='float32', geometry=raw['geometry']))
    return entries


def run_prepared(prepared, timeout_s=120.):
    """Run sequential CPU cases and cooperatively drain before returning evidence.

    Timeout stops further work and requests cancellation; it is not a deadline
    for killing a running numerical step. Cleanup finishes before return.
    """
    from hawa.sweep_executor import CpuSweepExecutor
    if type(timeout_s) not in (int, float) or not math.isfinite(timeout_s) or timeout_s <= 0:
        raise ValueError('timeout_s must be positive finite seconds')
    candidates = [entry['candidate'] for entry in prepared.values()]
    generations = {entry['request']['identity']['generation'] for entry in prepared.values()}
    if len(generations) != 1:
        raise ValueError('All entries require one generation')
    generation = generations.pop()
    executor = CpuSweepExecutor(prepared)
    controller = SweepController(candidates, executor, generation=generation)
    started = time.monotonic()
    timed_out = False
    try:
        controller.run()
        while controller.state not in ('completed', 'cancelled', 'disposed'):
            if not timed_out and time.monotonic()-started >= timeout_s:
                timed_out = True
                controller.cancel()
            controller.tick()
            time.sleep(.001)
    finally:
        controller.dispose()
        while controller.state == 'draining':
            controller.tick()
            time.sleep(.001)
    records = controller.records
    details = {candidate['candidate_id']: executor.results(candidate['candidate_id'], generation)
               for candidate in candidates}
    return dict(schema='hawa-headless-sweep-demo-1', device='cpu', dtype='float32',
                timed_out=timed_out, records=records, details=details,
                plots={name: plot_segments(records, kind=name)
                       for name in ('cl_alpha', 'cd_alpha', 'cl_cd')}, cleanup=executor.audit(),
                claim='Experimental workflow demonstration; no aerodynamic accuracy qualification')


def main(argv=None):
    """Print the bounded demo's internal report; no CSV/export service integration."""
    from scripts.wing_solver_recipe import demo_sweep
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settling-steps', type=int, default=1000)
    parser.add_argument('--sample-steps', type=int, default=64)
    parser.add_argument('--stationarity-tolerance', type=float, default=.05)
    parser.add_argument('--timeout', type=float, default=120.)
    args = parser.parse_args(argv)
    recipe = demo_sweep()
    entries = prepare_entries(recipe, args.settling_steps, args.sample_steps,
                              args.stationarity_tolerance,
                              probes=[dict(probe_id='upstream', position_world_m=[-.1, 0., .1])])
    report = run_prepared(entries, args.timeout)
    # Full array/history data remain available through run_prepared in Python.
    # The console summary is deliberately small and is not an interchange writer.
    print(json.dumps({key: value for key, value in report.items() if key != 'details'},
                     allow_nan=False))
    return 0 if not report['timed_out'] and all(
        record['state'] == 'completed' for record in report['records']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
