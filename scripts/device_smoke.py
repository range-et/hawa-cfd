"""Device smoke gate: short fixed cases compared with a CPU FP64 reference.

    python scripts/device_smoke.py --device cpu|cuda|mps --output NEW_DIR --overlapping-jobs TEXT

Each case in scripts/device_smoke_policy.json runs twice in this process: on the
CPU in FP64 (the reference) and on the requested device with Hawa's FP32
production storage (the candidate). Devices are never compared with each other.
The committed policy declares every check's class and tolerance before any device
run. A declared runtime guard that refuses a device is recorded as
unsupported-guarded, not as a pass. The machine-generated manifest records source
provenance, environment, seeds, timings and every comparison. This is a smoke
gate, not a convergence, accuracy or long-window qualification.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time

import numpy as np
import torch

from verification_evidence import snapshot

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / 'scripts/device_smoke_policy.json'
DEVICES = {'cpu': 'cpu', 'cuda': 'cuda:0', 'mps': 'mps'}
CLASSES = ('bitwise', 'bounded')
STATUSES = ('pass', 'fail', 'unsupported-guarded')
SEED = 0


def engine(device, reference, params, directory):
    """Run only the declared compatibility cases through parity_worker."""
    import parity_worker
    metadata = parity_worker.run('backport', 'cpu64' if reference else device, directory, params['cases'])
    arrays, config = {}, {}
    for name in params['cases']:
        with np.load(Path(directory) / (name + '.npz')) as fields:
            for key in fields.files:
                arrays[name + '/' + key] = fields[key]
                config[name + '/' + key] = metadata['cases'][name]
    return arrays, config


def kbc(device, reference, params, directory):
    """One KBC collision of the stored PorousMedium cell, as in test_kbc_precision."""
    import lettuce as lt
    dtype = torch.float64 if reference else torch.float32
    arrays = {}
    for size in params['sizes']:
        flow = lt.TaylorGreenVortex(lt.Context(device, dtype, use_native=False), [size, size], 10, .05)
        flow.units = lt.UnitConversion(reynolds_number=lt.D2Q9.cs*.05*512/(1/6),
                                       mach_number=.05, characteristic_length_lu=1)
        # Both paths start from the same representable FP32 populations.
        stored = torch.tensor(params['populations'], device=device, dtype=torch.float32)
        flow.f = stored.to(dtype)[:, None, None].expand(-1, size, size).clone()
        arrays['size-{}/populations'.format(size)] = lt.KBCCollision()(flow).cpu().numpy()
    return arrays, {}


def neutral(device, reference, params, directory):
    """Neutral precursor: production Session candidate, FP64 make() reference."""
    import lettuce as lt
    from hawa.neutral import make
    from hawa.plugin import Session
    if not reference:
        session = Session(params['spec'], device)
        session.advance(params['steps'])
        return dict(velocity=session.fields()['velocity'],
                    relative_mass_change=np.float64(session.relative_mass_change)), {}
    flow, simulation = make(params['spec'], lt.Context(device, torch.float64, use_native=False))
    mass = float(flow.rho().sum())
    simulation(params['steps'])
    return dict(velocity=flow.u_pu.cpu().numpy(),
                relative_mass_change=np.float64((float(flow.rho().sum()) - mass) / mass)), {}


def moving(device, reference, params, directory):
    """Moving sphere: production Session candidate, FP64 reference of the same assembly."""
    from hawa.plugin import Session
    if reference:
        import lettuce as lt
        from hawa.moving_boundaries import MovingBoundaries
        from hawa.plugin import WindFlow
        # make_solver's BGK moving-body assembly, with an FP64 context.
        flow = WindFlow(lt.Context(device, torch.float64, use_native=False), params['spec'])
        simulation = lt.Simulation(flow, lt.BGKCollision(flow.units.relaxation_parameter_lu), [])
        simulation.moving = MovingBoundaries(simulation, params['spec'])
        simulation(params['steps'])
    else:
        session = Session(params['spec'], device)
        session.advance(params['steps'])
        flow = session.flow
    return dict(populations=flow.f.cpu().numpy(), solid=flow.solid.cpu().numpy()), {}


def wall(device, reference, params, directory):
    """Fractional-wall channel benchmark maximum speed for each declared q."""
    from benchmark_curved_walls import run
    dtype = torch.float64 if reference else torch.float32
    return {'q-{}/max_speed'.format(q): np.float64(run(params['n'], q, device, dtype)['max_speed'])
            for q in params['q']}, {}


BUILDERS = dict(engine=engine, kbc=kbc, neutral=neutral, moving=moving, wall=wall)


def load_policy(path):
    """Reject a policy whose cases, classes, tolerances or guards are incomplete."""
    policy = json.loads(Path(path).read_text(encoding='utf-8'))
    if policy.get('schema') != 1 or not policy.get('cases'):
        raise ValueError('Policy requires schema 1 and at least one case')
    for name, case in policy['cases'].items():
        if case.get('builder') not in BUILDERS or not case.get('checks') or not case.get('criterion_source'):
            raise ValueError(name + ': requires a known builder, checks and a criterion source')
        for check in case['checks']:
            if check.get('class') not in CLASSES:
                raise ValueError(name + ': comparison class must be one of ' + ', '.join(CLASSES))
            re.compile(check['pattern'])
            tolerances = [check.get('rtol'), check.get('atol')]
            if check['class'] == 'bounded' and not all(
                    isinstance(t, (int, float)) and np.isfinite(t) and t >= 0 for t in tolerances):
                raise ValueError(name + ': bounded checks require finite nonnegative rtol and atol')
            if check['class'] == 'bitwise' and tolerances != [None, None]:
                raise ValueError(name + ': bitwise checks take no tolerance')
        for device, guard in case.get('unsupported', {}).items():
            if device not in DEVICES or not guard.get('exception') or not guard.get('match'):
                raise ValueError(name + ': an unsupported device needs its guard exception and message')
    return policy


def compare(check, reference, candidate, config):
    """Apply one declared check to each selected array, without changing its tolerance."""
    rows = []
    for name in sorted(reference):
        expected, actual = np.asarray(reference[name]), np.asarray(candidate[name])
        row = dict(array=name, reference_dtype=str(expected.dtype), candidate_dtype=str(actual.dtype),
                   shape=list(actual.shape))
        if expected.shape != actual.shape:
            row.update(passed=False, error='Shape differs from reference {}'.format(list(expected.shape)))
        elif check['class'] == 'bitwise':
            rounded = np.ascontiguousarray(expected.astype(actual.dtype))
            bits = np.ascontiguousarray(actual)
            width = bits.dtype.itemsize
            differs = (rounded.view(np.uint8) != bits.view(np.uint8)).reshape(bits.size, width).any(1)
            row.update(mismatches=int(differs.sum()), passed=not differs.any())
        else:
            atol = check['atol'] * (config[name][check['atol_scale']] if 'atol_scale' in check else 1)
            error = np.abs(actual.astype(np.float64) - expected.astype(np.float64))
            violations = ~(error <= atol + check['rtol'] * np.abs(expected.astype(np.float64)))
            finite = bool(np.isfinite(error).all())
            row.update(rtol=check['rtol'], atol=atol, violations=int(violations.sum()),
                       max_abs_error=float(error.max()) if finite else 'nonfinite',
                       passed=not violations.any())
        rows.append(row)
    return dict(name=check['name'], comparison_class=check['class'], arrays=rows,
                passed=all(row['passed'] for row in rows))


def evaluate(checks, reference, candidate, reference_config, candidate_config):
    """Require identical inventories and exactly one declared check per array."""
    if set(reference) != set(candidate):
        raise ValueError('Reference and candidate arrays differ: {}'.format(
            sorted(set(reference) ^ set(candidate))))
    if reference_config != candidate_config:
        raise ValueError('Reference and candidate case configurations differ')
    owners = {name: [c for c in checks if re.search(c['pattern'], name)] for name in reference}
    unowned = sorted(name for name, matches in owners.items() if len(matches) != 1)
    if unowned:
        raise ValueError('Arrays need exactly one declared check: ' + ', '.join(unowned))
    results = []
    for check in checks:
        names = [name for name in reference if owners[name][0] is check]
        if not names:
            raise ValueError('Check selects no arrays: ' + check['name'])
        results.append(compare(check, {n: reference[n] for n in names},
                               {n: candidate[n] for n in names}, reference_config))
    return results


def seed():
    torch.manual_seed(SEED)
    np.random.seed(SEED)


def run_case(name, case, device, directory):
    """Run the reference, then the candidate; record a guard refusal separately."""
    builder = BUILDERS[case['builder']]
    record = dict(id=name, builder=case['builder'], criterion_source=case['criterion_source'],
                  status='fail', checks=[])
    guard = case.get('unsupported', {}).get(torch.device(device).type)
    try:
        directory.mkdir(parents=True)
        seed()
        start = time.perf_counter()
        reference, reference_config = builder('cpu', True, case['params'], directory / 'reference')
        record['reference_seconds'] = time.perf_counter() - start
        np.savez_compressed(directory / 'reference.npz', **reference)
        seed()
        start = time.perf_counter()
        try:
            candidate, candidate_config = builder(device, False, case['params'], directory / 'candidate')
        except Exception as exc:
            record['candidate_seconds'] = time.perf_counter() - start
            if guard and type(exc).__name__ == guard['exception'] and re.search(guard['match'], str(exc)):
                record.update(status='unsupported-guarded', guard='{}: {}'.format(type(exc).__name__, exc))
                return record
            raise
        record['candidate_seconds'] = time.perf_counter() - start
        np.savez_compressed(directory / 'candidate.npz', **candidate)
        if guard:
            raise RuntimeError('Declared unsupported on this device, but no runtime guard refused it')
        record['checks'] = evaluate(case['checks'], reference, candidate, reference_config, candidate_config)
        record['status'] = 'pass' if all(check['passed'] for check in record['checks']) else 'fail'
    except Exception as exc:
        record['error'] = '{}: {}'.format(type(exc).__name__, exc)
    return record


def command(arguments):
    """Optional host description; an absent tool is recorded as None."""
    try:
        return subprocess.check_output(arguments, text=True, stderr=subprocess.DEVNULL, timeout=30).strip()
    except (OSError, subprocess.SubprocessError):
        return None


def environment(device):
    info = dict(os=platform.platform(), machine=platform.machine(), processor=platform.processor(),
                python=sys.version, executable=sys.executable, torch=torch.__version__,
                numpy=np.__version__, torch_threads=torch.get_num_threads(),
                variables={k: os.environ.get(k) for k in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS',
                                                          'PYTORCH_ENABLE_MPS_FALLBACK', 'CUDA_VISIBLE_DEVICES')})
    if device.startswith('cuda'):
        info.update(cuda_runtime=torch.version.cuda, gpu=torch.cuda.get_device_name(0),
                    capability=list(torch.cuda.get_device_capability(0)),
                    driver=command(['nvidia-smi', '--query-gpu=driver_version', '--format=csv,noheader']))
    if device == 'mps':
        info.update(macos=platform.mac_ver()[0], mac_model=command(['sysctl', '-n', 'hw.model']),
                    chip=command(['sysctl', '-n', 'machdep.cpu.brand_string']))
    return info


def provenance(root=ROOT):
    """Commit, dirty flag and a digest of every tracked/nonignored file (scripts/verification_evidence.py)."""
    state = snapshot(root)
    status = subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True)
    return dict(commit=state['commit'], dirty=bool(status.strip()), status=status.splitlines(),
                index_sha256=state['index_sha256'], files=len(state['files']),
                source_sha256=hashlib.sha256(json.dumps(state['files'], sort_keys=True).encode()).hexdigest())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--device', choices=sorted(DEVICES), required=True)
    parser.add_argument('--output', type=Path, required=True, help='New evidence directory')
    parser.add_argument('--overlapping-jobs', required=True,
                        help='Other work running on this machine during the run, or "none"')
    parser.add_argument('--policy', type=Path, default=POLICY)
    args = parser.parse_args(argv)
    if not args.overlapping_jobs.strip():
        parser.error('State the overlapping jobs, or "none"')
    if args.device == 'mps' and os.environ.get('PYTORCH_ENABLE_MPS_FALLBACK') == '1':
        parser.error('Unset PYTORCH_ENABLE_MPS_FALLBACK; CPU fallback would hide MPS results')
    try:
        policy = load_policy(args.policy)
    except (OSError, ValueError, KeyError, re.error) as exc:
        parser.error('Invalid policy: {}'.format(exc))
    from hawa.backends import select_backend
    device = DEVICES[args.device]
    backend = select_backend(device)  # Executes a real operation; never falls back.
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)  # Refuse stale evidence.
    torch.set_num_threads(1)
    started = time.perf_counter()
    manifest = dict(schema=1, tool='scripts/device_smoke.py', result='incomplete',
                    started_utc=datetime.now(timezone.utc).isoformat(), device=args.device,
                    torch_device=device, backend=backend.info(), reference=dict(device='cpu', dtype='float64'),
                    candidate_dtype='float32', seeds=dict(torch=SEED, numpy=SEED),
                    overlapping_jobs=args.overlapping_jobs,
                    policy=dict(path=str(args.policy), sha256=hashlib.sha256(args.policy.read_bytes()).hexdigest()),
                    source_before=provenance(), environment=environment(device), cases=[])

    def save():
        (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')

    save()
    for name, case in policy['cases'].items():
        print(name + ': running', flush=True)
        record = run_case(name, case, device, output / 'cases' / name)
        manifest['cases'].append(record)
        save()
        print('{}: {} {}'.format(name, record['status'], record.get('error', '')), flush=True)
    manifest['source_after'] = provenance()
    manifest['source_unchanged'] = manifest['source_after'] == manifest['source_before']
    manifest['counts'] = {s: sum(r['status'] == s for r in manifest['cases']) for s in STATUSES}
    manifest['result'] = 'pass' if not manifest['counts']['fail'] and manifest['source_unchanged'] else 'fail'
    manifest['seconds'] = time.perf_counter() - started
    manifest['finished_utc'] = datetime.now(timezone.utc).isoformat()
    save()
    print('Device smoke {}: {} ({})'.format(args.device, manifest['result'], output / 'manifest.json'), flush=True)
    return 0 if manifest['result'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
