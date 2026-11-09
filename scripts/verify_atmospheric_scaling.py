"""Reproduce the coarse-grid air precision gate without bypassing production checks.

This is a feasibility report, not atmospheric-flow validation. Exit 2 means the
requested city-scale grid inventory is not supported; a finite report is not PASS.
"""
import argparse
import json
from pathlib import Path
import platform

import numpy as np
import torch

from hawa.atmosphere import scaling_report
from hawa.plugin import check_case


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rows = []
    for dx in (.1, 1., 10.):
        spec = dict(shape=[9, 9, 9], dx=dx, speed=5., viscosity=1.5e-5,
                    mach=.05, collision='smagorinsky-v1')
        row = dict(dx_m=dx, speed_m_s=5., viscosity_m2_s=1.5e-5,
                   mach=.05, **scaling_report(dx, 5., 1.5e-5))
        try:
            check_case(spec)
            row['preflight'] = 'accepted'
        except ValueError as error:
            row.update(preflight='rejected', reason=str(error))
        row['devices'] = {}
        devices = ['cpu']
        if torch.backends.mps.is_available(): devices.append('mps')
        if torch.cuda.is_available(): devices.append('cuda:0')
        for device in devices:
            represented = float(torch.tensor(row['tau'], dtype=torch.float32, device=device).cpu())
            row['devices'][device] = dict(tau_fp32=represented,
                margin_fp32=represented-.5, rounds_to_half=represented == .5)
        rows.append(row)
    report = dict(schema=1, claim='production molecular-air scaling feasibility only',
                  environment=dict(python=platform.python_version(), torch=torch.__version__,
                                   numpy=np.__version__, os=platform.platform()),
                  acceptance='Every requested grid must pass unchanged production preflight',
                  cases=rows, passed=all(r['preflight']=='accepted' for r in rows),
                  omitted=['atmospheric turbulence', 'rough-wall operator', 'boundary transfer',
                           'physical validation', 'CUDA' if not torch.cuda.is_available() else ''])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))
    return 0 if report['passed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
