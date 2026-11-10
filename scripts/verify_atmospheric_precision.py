"""Bounded physical-viscosity precision/collision experiment for HAWA-003 (#13).

Declared before the recorded run (November 10, 2026); not atmospheric validation.

Setup: periodic N x 4 x 4 D3Q19 lattice, production shifted-regularized-sgs-v1
collision and shifted storage, air at Uref=5 m/s, nu=1.5e-5 m^2/s, Ma_ref=0.05.
A transverse shear wave u_y=A Uref sin(2 pi x/(N dx)) rides on a uniform
u_z=Uref, so stored populations carry a realistic mean-flow magnitude. The
initial non-equilibrium is the Chapman-Enskog stress of the analytic strain.

Metric: effective relaxation increment delta_eff=-3 slope/k^2, from a least-
squares fit of log|A| against lattice steps over the last 90% of the run.
FP64 references always run on CPU; FP32 runs on each requested device for the
same steps, hence equal physical time.

Criteria:
1. Collision: CPU FP64 delta_eff within 5% of the molecular increment at
   dx=0.1, 1 and 10 m (Cs=0, A=0.01).
2. FP32 storage represents a case when delta_eff(FP32) is within 5% of the FP64
   reference. Physical-air FP32 outcomes are recorded evidence, not exit criteria.
3. Diagnostic: the production storage_resolution status ('resolved') must agree
   with criterion 2 for every FP32 case. Its ratio 10 was calibrated on the
   'calibration' group; the 'validation' group was declared before measuring it.

Exit 0 only when criteria 1 and 3 hold. MPS and CUDA need their own devices.
"""
import argparse
import json
import math
from pathlib import Path
import platform

import numpy as np
import torch
import lettuce as lt

from hawa.atmosphere import scaling_report
from hawa.neutral import ShiftedEquilibrium, ShiftedRegularizedSGS

SPEED, VISCOSITY, MACH = 5., 1.5e-5, .05
TOLERANCE = .05


class ShearWave(lt.Flow):
    """Periodic transverse shear wave with a uniform perpendicular mean flow."""

    def __init__(self, context, n, amplitude, margin):
        self.n, self.amplitude, self.margin = n, amplitude, margin
        super().__init__(context, [n, 4, 4], lt.UnitConversion(1., mach_number=MACH),
                         lt.D3Q19(), ShiftedEquilibrium())

    def rho(self, f=None):
        return 1+(self.f if f is None else f).sum(0, keepdim=True)

    def initial_pu(self):
        raise NotImplementedError('ShearWave initializes populations directly')

    def initialize(self):
        scale = MACH/math.sqrt(3)
        k = 2*math.pi/self.n
        x = torch.arange(self.n, dtype=torch.float64)
        u = torch.zeros(3, *self.resolution, dtype=torch.float64)
        u[1] = (self.amplitude*scale*torch.sin(k*x))[:, None, None]
        u[2] = scale
        strain = torch.zeros(3, 3, *self.resolution, dtype=torch.float64)
        strain[0, 1] = strain[1, 0] = (.5*self.amplitude*scale*k*torch.cos(k*x))[:, None, None]
        e = torch.tensor(np.asarray(self.stencil.e), dtype=torch.float64)
        w = torch.tensor(np.asarray(self.stencil.w), dtype=torch.float64)
        # The stress is pure xy (traceless), so Q = ee - I/3 reduces exactly to ee.
        q = torch.einsum('qa,qb->qab', e, e)
        eu = torch.einsum('qd,d...->q...', e, u)
        equilibrium = w[:, None, None, None]*(3*eu+4.5*eu*eu-1.5*(u*u).sum(0))
        stress = -(2/3)*(.5+self.margin)*strain
        self.f = self.context.convert_to_tensor(equilibrium+4.5*torch.einsum('q,qab,ab...->q...', w, q, stress))

    @property
    def post_boundaries(self):
        return []


def amplitude(flow):
    """Lattice amplitude of the sin(kx) mode of u_y."""
    u = flow.u().cpu().double()[1].mean((1, 2))
    x = torch.arange(flow.n, dtype=torch.float64)
    return float((u*torch.sin(2*math.pi*x/flow.n)).sum()*2/flow.n)


def measure(dx, cs, wave, device='cpu', dtype=torch.float32, n=32, steps=4000, sample=100, margin=None):
    """Run one shear-wave decay and return delta_eff plus the storage diagnostic."""
    if steps < 10*sample or steps % sample:
        raise ValueError('Steps must be a multiple of sample and contain at least ten samples')
    scaling = scaling_report(dx, SPEED, VISCOSITY, MACH)
    margin = scaling['tau_minus_half'] if margin is None else margin
    flow = ShearWave(lt.Context(device, dtype, use_native=False), n, wave, margin)
    collision = ShiftedRegularizedSGS(margin, cs)
    simulation = lt.Simulation(flow, collision, [])
    count = steps//sample
    values = [amplitude(flow)]
    for _ in range(count):
        simulation(sample)
        values.append(amplitude(flow))
    if not all(math.isfinite(v) and v != 0 for v in values):
        raise RuntimeError('Shear-wave amplitude became nonfinite or vanished')
    times = sample*np.arange(count+1)
    keep = times >= .1*steps
    slope = np.polyfit(times[keep], np.log(np.abs(values))[keep], 1)[0]
    delta = float(-3*slope/(2*math.pi/n)**2)
    return dict(dx_m=dx, cs=cs, wave_fraction=wave, device=device,
                dtype=str(dtype).replace('torch.', ''), n=n, steps=steps, samples=len(values),
                physical_time_s=steps*scaling['time_step_seconds'], margin=margin,
                delta_effective=delta, delta_ratio=delta/margin,
                storage=collision.storage_resolution(flow))


CASES = {
    'physical': [dict(dx=dx, cs=0., wave=.01) for dx in (.1, 1., 10.)]
    + [dict(dx=dx, cs=.17, wave=a) for dx in (.1, 1., 10.) for a in (.1, .01)],
    'calibration': [dict(dx=1., cs=0., wave=.01, margin=m) for m in (1e-5, 1e-4, 1e-3, 1e-2)],
    'validation': [dict(dx=1., cs=.17, wave=.03), dict(dx=10., cs=.17, wave=.1, n=16),
                   dict(dx=1., cs=.17, wave=.1, n=64, steps=8000), dict(dx=1., cs=0., wave=.01, margin=3e-4),
                   dict(dx=1., cs=0., wave=.01, margin=3e-3), dict(dx=1., cs=.3, wave=.01),
                   dict(dx=1., cs=.17, wave=.3)],
}


def compare(reference, candidate):
    """Criterion 2 and 3 for one FP32 case against its FP64 reference."""
    error = candidate['delta_effective']/reference['delta_effective']-1
    represented = bool(abs(error) <= TOLERANCE)
    predicted = candidate['storage']['model_status'] == 'resolved'
    return dict(relative_error_vs_fp64=error, represented=represented,
                diagnostic_predicted_resolved=predicted, diagnostic_agrees=predicted == represented)


def run(devices, cases=None):
    """Measure every declared case; return rows and the acceptance summary."""
    rows = []
    for group, entries in (CASES if cases is None else cases).items():
        for entry in entries:
            entry = dict(entry)
            dx, cs, wave = entry.pop('dx'), entry.pop('cs'), entry.pop('wave')
            reference = measure(dx, cs, wave, 'cpu', torch.float64, **entry)
            row = dict(group=group, reference_fp64=reference, fp32={})
            for device in devices:
                candidate = measure(dx, cs, wave, device, torch.float32, **entry)
                row['fp32'][device] = dict(candidate, **compare(reference, candidate))
            rows.append(row)
    collision = [r for r in rows if r['group'] == 'physical' and r['reference_fp64']['cs'] == 0]
    collision_pass = bool(collision) and all(abs(r['reference_fp64']['delta_ratio']-1) <= TOLERANCE for r in collision)
    fp32 = [c for r in rows for c in r['fp32'].values()]
    agreement = all(c['diagnostic_agrees'] for c in fp32)
    molecular = {'{}:{}'.format(device, r['reference_fp64']['dx_m']): r['fp32'][device]['represented']
                 for r in collision for device in devices}
    return rows, dict(collision_fp64_represents_molecular=collision_pass,
                      diagnostic_agrees_on_all_fp32_cases=agreement,
                      fp32_molecular_represented=molecular,
                      false_resolved_cases=sum(c['diagnostic_predicted_resolved'] and not c['represented'] for c in fp32),
                      conservative_misses=sum(c['represented'] and not c['diagnostic_predicted_resolved'] for c in fp32),
                      passed=collision_pass and agreement)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--device', action='append', help='FP32 device; repeat for several (default cpu)')
    args = parser.parse_args(argv)
    devices = args.device or ['cpu']
    rows, summary = run(devices)
    report = dict(schema=1, issue='HAWA-003 / range-et/hawa-cfd#13',
                  claim='storage/collision representation of declared dissipation; not atmospheric validation',
                  environment=dict(python=platform.python_version(), torch=torch.__version__,
                                   numpy=np.__version__, os=platform.platform(), devices=devices),
                  air=dict(speed_m_s=SPEED, viscosity_m2_s=VISCOSITY, mach=MACH), tolerance=TOLERANCE,
                  cases=rows, **summary)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(summary, indent=2))
    return 0 if report['passed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
