"""Run the existing refinement, wall and motion benchmarks on CPU and CUDA.

Numerical acceptance is fixed before measurement: retain the motion invariance
thresholds, require refinement improvement/mass conservation, and compare scalar
observables at the existing accelerator tolerance (3e-4 relative, 2e-6 absolute).
Analytic error and grid trends are reported, not promoted to physical validation.
"""
import argparse
import json
from pathlib import Path
import sys

import numpy as np
import torch
from verification_evidence import snapshot
from hawa.backends import select_backend
from benchmark_motion import comoving
from benchmark_refinement import benchmark as refinement
from benchmark_curved_walls import run as wall
from benchmark_rotating_sphere import benchmark as rotation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Use a fresh output path')
    select_backend('cuda:0')
    torch.set_num_threads(1)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    report = dict(passed=False, rtol=3e-4, atol=2e-6, results=rows,
                  torch=torch.__version__, python=sys.version,
                  gpu=torch.cuda.get_device_name(0))
    root = Path(__file__).resolve().parents[1]
    before = snapshot(root)
    report['source_before'] = before

    def save():
        args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')

    configurations = [('comoving', {}, comoving, ['max_fluid_population_error']),
                      *[('refinement', dict(n=n, steps=40), refinement, []) for n in (16,24,32)],
                      *[('wall', dict(n=n, q=q), wall, ['max_speed']) for q in (.25,.75) for n in (8,12,16)],
                      *[('rotation', dict(dx=dx), rotation, ['torque']) for dx in (.5,1/3,.25)]]
    save()
    for name, options, function, observables in configurations:
        row = dict(benchmark=name, options=options, passed=False, devices={})
        rows.append(row)
        try:
            for device in ('cpu', 'cuda:0'):
                print('{} {} {}'.format(name, options, device), flush=True)
                row['devices'][device] = function(device=device, **options)
                save()
            cpu, gpu = row['devices']['cpu'], row['devices']['cuda:0']
            for observable in observables:
                np.testing.assert_allclose(gpu[observable], cpu[observable], rtol=3e-4, atol=2e-6)
            if name == 'comoving':
                for value in (cpu, gpu):
                    assert value['max_fluid_population_error'] < 3e-6
                    assert value['max_force_newtons'] < .002
            if name == 'refinement':
                for value in (cpu, gpu):
                    assert 0 <= value['refined_relative_l2'] < value['coarse_relative_l2']
                    assert abs(value['relative_mass_drift']) < 3e-6
            if name in ('wall', 'rotation'):
                for value in (cpu, gpu):
                    assert all(np.isfinite(v) for v in value.values() if isinstance(v, (int,float)))
            row['passed'] = True
        except Exception as exc:
            row['error'] = '{}: {}'.format(type(exc).__name__, exc)
        save()
    report['source_after'] = snapshot(root)
    report['source_unchanged'] = report['source_after'] == before
    report['passed'] = bool(rows) and all(row['passed'] for row in rows) and report['source_unchanged']
    save()
    print('Passed {}/{} benchmark configurations'.format(sum(r['passed'] for r in rows), len(rows)), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
