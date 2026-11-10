"""Bounded HAWA-001 diagnostic; never qualifies the original porous trajectory.

The frozen FP32 cell comes from the CPU PorousMedium state before step 50 at
(294, 125), original 512-square case. Repetition tests shape-dependent arithmetic,
not a new flow initial condition or an engineering benchmark. No solver edits.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time

import numpy as np
import torch
import lettuce as lt

ROOT = Path(__file__).resolve().parents[1]
POPULATIONS = (0.43819519877433777, 0.10960162431001663, 0.10923780500888824,
               0.10090156644582748, 0.11824554204940796, 0.027240581810474396,
               0.025348886847496033, 0.027386868372559547, 0.02978522703051567)
RTOL, ATOL = 1e-3, 1e-5  # Original population criteria, unchanged.
EPSILON = torch.finfo(torch.float32).eps


def source_hashes():
    paths = list((ROOT/'vendor/lettuce/lettuce').rglob('*.py'))
    paths += [Path(__file__), ROOT/'pyproject.toml', ROOT/'uv.lock',
              ROOT/'vendor/lettuce/examples/advanced_flows/PorousMedium.ipynb']
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(paths)}



def loaded_module_paths():
    return {name: str(Path(module.__file__).resolve()) if getattr(module, '__file__', None) else None
            for name, module in sorted(tuple(sys.modules.items()))
            if name == 'lettuce' or name.startswith('lettuce.')}


def validate_loaded_modules(paths):
    vendor = (ROOT/'vendor/lettuce/lettuce').resolve()
    if 'lettuce' not in paths:
        raise ValueError('Loaded Lettuce package provenance is missing')
    for name, location in paths.items():
        if location is None or vendor not in Path(location).parents or not Path(location).is_file():
            raise ValueError('Loaded module is outside this checkout vendor source: '+name)

def make_flow(device, size, dtype=torch.float32):
    if type(size) is not int or not 1 <= size <= 512:
        raise ValueError('Diagnostic side length must be an integer in [1, 512]')
    flow = lt.TaylorGreenVortex(lt.Context(device, dtype, use_native=False), [8, 8], 10, .05)
    # Original notebook conversion: domain_length_x=nx and char_length=1.
    flow.units = lt.UnitConversion(reynolds_number=lt.D2Q9.cs*.05*512/(1/6),
                                   mach_number=.05, characteristic_length_lu=1)
    initial = torch.tensor(POPULATIONS, dtype=torch.float32)
    flow.f = initial.to(device=device, dtype=dtype)[:, None, None].expand(-1, size, size).clone()
    return flow


def inspect_collision(flow):
    """Read the existing raw kernel's stages; no replacement collision is used."""
    collision = lt.KBCCollision()
    before = flow.f.clone()
    output = collision._collide(flow, EPSILON)
    equilibrium = flow.equilibrium(flow)
    shear = collision.compute_s_seq_from_m(flow.f, collision.kbc_moment_transform(flow.f))
    shear -= collision.compute_s_seq_from_m(flow.f, collision.kbc_moment_transform(equilibrium))
    higher = flow.f-equilibrium-shear
    numerator = flow.rho(shear*higher/equilibrium)
    denominator = flow.rho(higher*higher/equilibrium)
    near_zero = denominator <= (flow.stencil.q*EPSILON)**2*flow.rho()
    safe = torch.where(near_zero, torch.ones_like(denominator), denominator)
    raw_gamma = 1/collision.beta-(2-1/collision.beta)*numerator/safe
    gamma = torch.where(near_zero | ~torch.isfinite(raw_gamma),
                        torch.full_like(raw_gamma, 2), raw_gamma)
    negative_reset = gamma < 1e-15
    gamma = torch.where(negative_reset, torch.full_like(gamma, 2), gamma)
    reconstructed = flow.f-collision.beta*(2*shear+gamma*higher)
    torch.testing.assert_close(output, reconstructed, rtol=0, atol=0)
    torch.testing.assert_close(flow.f, before, rtol=0, atol=0)
    return dict(rho=flow.rho(), velocity=flow.u(), equilibrium=equilibrium,
                shear=shear, higher=higher, numerator=numerator, denominator=denominator,
                raw_gamma=raw_gamma, applied_gamma=gamma, near_zero=near_zero,
                negative_reset=negative_reset, output=output)


def compare(reference, candidate):
    a = reference.detach().cpu().numpy().astype(np.float64)
    b = candidate.detach().cpu().numpy().astype(np.float64)
    if a.shape != b.shape or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError('Comparison requires matching finite tensors')
    error = np.abs(b-a)
    failed = error > ATOL+RTOL*np.abs(a)
    return dict(max_abs=float(error.max()), rms=float(np.sqrt(np.mean(error**2))),
                failed_values=int(failed.sum()), values=int(a.size),
                passed=bool(not failed.any()), rtol=RTOL, atol=ATOL)


def summarize(stages):
    result = {}
    for name, tensor in stages.items():
        values = tensor.detach().cpu().numpy()
        if not np.isfinite(values).all():
            raise ValueError('Nonfinite diagnostic stage: '+name)
        result[name] = dict(min=float(values.min()), max=float(values.max()),
                            first=float(values.flat[0]))
        if tensor.dtype == torch.bool:
            result[name]['count'] = int(values.sum())
    return result


def study(device, sizes, evidence=None):
    if device not in ('cpu', 'mps', 'cuda:0'):
        raise ValueError('Explicit cpu, mps or cuda:0 device required')
    if not sizes or len(sizes) > 4 or len(set(sizes)) != len(sizes):
        raise ValueError('Require one to four distinct diagnostic sizes')
    # Construct the reference from the exact stored FP32 values, not decimal FP64 values.
    reference = make_flow('cpu', 1, torch.float64)
    reference_stages = inspect_collision(reference)
    evidence = {} if evidence is None else evidence
    evidence.update(reference=summarize(reference_stages), rows=[], completed_sizes=[], failed_size=None, passed=False)
    rows = evidence['rows']
    for size in sizes:
        evidence['failed_size'] = size
        flow = make_flow(device, size)
        original = flow.f.clone()
        stages = inspect_collision(flow)
        public = lt.KBCCollision()(flow)
        target = reference_stages['output'].to(torch.float32).expand_as(public)
        torch.testing.assert_close(flow.f, original, rtol=0, atol=0)
        rows.append(dict(size=size, device=str(public.device), dtype=str(public.dtype),
                         initial_identical=bool(torch.equal(flow.f.cpu(),
                             reference.f.to(torch.float32).expand_as(flow.f.cpu()))),
                         stages=summarize(stages),
                         public_vs_reference=compare(target, public),
                         raw_vs_reference=compare(target, stages['output']),
                         public_vs_raw=compare(stages['output'], public),
                         mass_error=compare(flow.rho(original), flow.rho(public)),
                         momentum_error=compare(flow.j(original), flow.j(public))))
        evidence['completed_sizes'].append(size)
        evidence['failed_size'] = None
    evidence['passed'] = all(row['public_vs_reference']['passed'] for row in rows)
    return evidence


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', choices=['cpu', 'mps', 'cuda:0'], default='mps')
    parser.add_argument('--sizes', nargs='+', type=int, default=[1, 8, 32, 512])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    # Never reuse an earlier result or overwrite unrelated user evidence.
    args.output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    report = dict(passed=False, completed=False, scope='repeated-single-cell KBC diagnostic',
                  original_512x512_50_step_qualified=False, device=args.device,
                  sizes=args.sizes, source_before=source_hashes(),
                  environment=dict(python=sys.version, torch=torch.__version__, numpy=np.__version__,
                                   platform=platform.platform(),
                                   mps_fallback_env=os.environ.get('PYTORCH_ENABLE_MPS_FALLBACK')))
    try:
        report['loaded_modules_before'] = loaded_module_paths()
        validate_loaded_modules(report['loaded_modules_before'])
        report.update(study(args.device, args.sizes, report))
        report['loaded_modules_after'] = loaded_module_paths()
        validate_loaded_modules(report['loaded_modules_after'])
        if any(report['loaded_modules_after'].get(name) != path
               for name, path in report['loaded_modules_before'].items()):
            raise ValueError('Loaded module provenance changed during diagnostic')
        report['source_after'] = source_hashes()
        if report['source_before'] != report['source_after']:
            raise ValueError('Source changed during diagnostic')
        report['completed'] = True
    except (ValueError, RuntimeError, AssertionError, OSError) as exc:
        report.update(passed=False, error=type(exc).__name__+': '+str(exc))
    report['wall_seconds'] = time.monotonic()-started
    (args.output/'result.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(json.dumps({key:report[key] for key in ('completed','passed','scope')}))
    return int(not report['passed'])


if __name__ == '__main__':
    raise SystemExit(main())
