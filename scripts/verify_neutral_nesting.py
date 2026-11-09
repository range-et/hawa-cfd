"""Same-grid / refined offline nesting against the actual parent solution.

Thresholds: mean U relative L2 <=5%, fluctuation RMS <=10%, Cp RMSE <=0.1.
Small deterministic building experiment, not an atmospheric engineering benchmark.
"""
import argparse, hashlib, json, platform, sys, time
from pathlib import Path
import numpy as np
from hawa.plugin import Session
from hawa.recording import record, read_manifest
from hawa.fields import read_frame
from hawa.boundary_data import capture
from hawa.boundary_series import sample_parent
from hawa.neutral import MODEL


def case(shape, dx, origin, parent=False):
    s=dict(shape=shape,dx=dx,spacing=dx,origin=origin,speed=5.,viscosity=1.5e-5,density=1.225,mach=.05,
        collision=MODEL,boundaries=['periodic']*4+['wall','slip'],neutral_precursor=dict(schema=1,experimental=True,mode='external',reference_height_m=6.,roughness_length_m=.01,perturbation_fraction=.02,wall_sample_index=0,wall_filter_seconds=.1),boundary_method='shifted-links-v1')
    names=('x-','x+','y-','y+','z-','z+');kinds=('velocity','open','periodic','periodic','wall','slip') if parent else ('open','open','open','open','wall','open')
    s['boundary_set']=dict(schema=1,patches=[dict(id=f,face=f,condition=dict(type=k,velocity=[5. if parent and i==0 else 0,0,0],pressure_pa=0.,profile='neutral' if i in (0,1) else 'uniform',**({'backflow_mode':'pressure'} if k=='open' else {}))) for i,(f,k) in enumerate(zip(names,kinds))])
    n=np.array(shape);ix=np.indices(tuple(n+2)).reshape(3,-1).T-1;xyz=origin+ix*dx
    mask=(xyz[:,0]>=8)&(xyz[:,0]<12)&(xyz[:,1]>=8)&(xyz[:,1]<12)&(xyz[:,2]<4)
    halo=mask.reshape(tuple(n+2));s['solid']=np.flatnonzero(halo[1:-1,1:-1,1:-1]).tolist();s['solid_halo']=np.flatnonzero(halo).tolist()
    return s


ROOT = Path(__file__).resolve().parents[1]
POINTS = np.array([[6.5,6.5,2.5],[10.5,6.5,2.5],[14.5,10.5,2.5],
                   [18.5,10.5,2.5],[22.5,10.5,2.5],[14.5,14.5,6.5],[18.5,10.5,8.5]])
THRESHOLDS = dict(mean_relative_l2=.05, rms_relative_l2=.1, cp_rmse=.1,
                  reference_stationarity=.05)


def runtime():
    import torch
    return dict(python=sys.version,torch=torch.__version__,numpy=np.__version__,platform=platform.platform())


def reference_case(ratio):
    dx=1./ratio
    spec=case([32*ratio,24*ratio,16*ratio],dx,np.array([dx/2]*3),True)
    spec['origin']=spec['origin'].tolist()
    return spec


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sources():
    """Bind a frozen reference to the engine, harness and dependency inputs."""
    files = [*ROOT.joinpath('src/hawa').rglob('*.py'),
             *ROOT.joinpath('vendor/lettuce/lettuce').rglob('*.py'),
             Path(__file__), ROOT/'pyproject.toml', ROOT/'uv.lock']
    return {str(p.relative_to(ROOT)): digest(p) for p in sorted(files)}


def recording_identity(path):
    """Require a complete recording and fingerprint its manifest and every frame."""
    manifest, data, _ = read_manifest(path)
    if data.get('complete') is not True:
        raise ValueError('Frozen reference requires a completed recording')
    return dict(manifest_sha256=digest(manifest),
                frames={e['file']: digest(manifest.parent/e['file']) for e in data['frames']})


def series(path, points):
    before = recording_identity(path)
    p, data, _ = read_manifest(path)
    u, pressure, times, qualities = [], [], [], []
    for entry in data['frames']:
        arrays, meta = read_frame(p.parent/entry['file'])
        if (meta['case'] != data['case'] or meta.get('time') != entry['time']
                or meta.get('iteration') != entry.get('iteration')):
            raise ValueError('Recording frame provenance does not match its manifest')
        a, b, _ = sample_parent(arrays, data['case'], points, np.zeros(len(points), bool))
        u.append(a); pressure.append(b)
        times.append(entry['time'] + data['case'].get('time_origin_seconds', 0.))
        qualities.append(meta.get('quality', {}).get('status', 'unchecked'))
    if before != recording_identity(path):
        raise ValueError('Recording changed during analysis')
    return np.asarray(times), np.asarray(u), np.asarray(pressure), qualities


def window_indices(times, start=None, end=None):
    """Default to the historical latter half; explicit bounds use absolute seconds."""
    t = np.asarray(times, float)
    if t.ndim != 1 or len(t) < 4 or not np.isfinite(t).all() or np.any(np.diff(t) <= 0):
        raise ValueError('Comparison needs increasing finite times and at least four samples')
    if start is None and end is None:
        indices = np.arange(len(t)//2, len(t))
    else:
        lo, hi = t[0] if start is None else start, t[-1] if end is None else end
        if not np.isfinite([lo, hi]).all() or lo >= hi or lo < t[0]-1e-10 or hi > t[-1]+1e-10:
            raise ValueError('Analysis window must be finite and inside recorded coverage')
        indices = np.flatnonzero((t >= lo-1e-10) & (t <= hi+1e-10))
    if len(indices) < 4:
        raise ValueError('Analysis window needs at least four samples')
    dt = np.diff(t[indices])
    if not np.allclose(dt, dt.mean(), rtol=1e-5, atol=1e-10):
        raise ValueError('Analysis window must contain uniformly timed samples')
    return indices


def metrics(times, reference_u, reference_p, child_u, child_p, quality, start=None, end=None):
    """Preserve acceptance metrics; expose child stationarity only as a diagnostic."""
    ids = window_indices(times, start, end)
    arrays = [np.asarray(a, float) for a in (reference_u, reference_p, child_u, child_p)]
    ru, rp, cu, cp = arrays
    if (ru.ndim != 3 or ru.shape[-1] != 3 or ru.shape[0] != len(times) or ru.shape[1] < 1
            or cu.shape != ru.shape or rp.shape != ru.shape[:2] or cp.shape != rp.shape
            or any(not np.isfinite(a).all() for a in arrays)):
        raise ValueError('Comparison requires matching finite velocity and pressure arrays')
    u, pr, v, pc = [a[ids] for a in arrays]
    denominator = float(np.linalg.norm(u.mean(0)))
    if denominator <= 1e-12:
        raise ValueError('Reference mean is too small for relative velocity criteria')
    split = len(u)//2
    stationarity = float(np.linalg.norm(u[:split].mean(0)-u[split:].mean(0))/denominator)
    child_stationarity = float(np.linalg.norm(v[:split].mean(0)-v[split:].mean(0)) /
                              max(np.linalg.norm(v.mean(0)), 1e-12))
    mean = float(np.linalg.norm(v.mean(0)-u.mean(0))/denominator)
    reference_rms, child_rms = u.std(0), v.std(0)
    rms = float(np.linalg.norm(child_rms-reference_rms)/max(np.linalg.norm(reference_rms), 1e-12))
    pressure = float(np.sqrt(np.mean((pc.mean(0)-pr.mean(0))**2))/(.5*1.225*25))
    return dict(mean_velocity_relative_l2=mean, fluctuation_rms_relative_l2=rms, cp_rmse=pressure,
                reference_stationarity_change=stationarity, child_stationarity_change=child_stationarity,
                reference_rms_m_s=reference_rms.tolist(), child_rms_m_s=child_rms.tolist(),
                mean_velocity_error_m_s=(v.mean(0)-u.mean(0)).tolist(),
                analysis_start=float(times[ids[0]]), analysis_end=float(times[ids[-1]]), samples=len(ids),
                passed=bool(mean<=.05 and rms<=.1 and pressure<=.1 and stationarity<=.05
                            and quality=='within-tested-envelope'))


def checkpoint(_):
    """Synchronous developer run; recording retains its existing bounded chunks."""
    return None


def create_recording(spec, warmup, steps, interval, directory, device):
    session = Session(spec, device)
    session.advance(warmup)
    result = record(session, warmup+steps, interval, str(directory), checkpoint)
    return result['manifest']


def prepare_reference(output, config, device):
    """Materialize parent and optional full fine-domain sources once for replay."""
    before = sources()
    paths = {}
    for ratio in [1] + ([r for r in config['ratios'] if r != 1] if config['fine_reference'] else []):
        spec = reference_case(ratio)
        name = 'parent' if ratio == 1 else 'reference-%d' % ratio
        manifest = create_recording(spec, config['warmup']*ratio, config['steps']*ratio,
                                    config['interval']*ratio, output/name, device)
        paths[name] = dict(manifest=str(Path(manifest).relative_to(output)), **recording_identity(manifest))
    if before != sources():
        raise ValueError('Source changed during reference preparation')
    bundle = dict(schema=1, config=config, device=device, environment=runtime(), sources=before,
                  points=POINTS.tolist(), recordings=paths)
    target = output/'reference.json'
    target.write_text(json.dumps(bundle, indent=2)+'\n')
    return target


def load_reference(path):
    """Reject stale code, absent frames, changed bytes, schema and clock mismatches."""
    path = Path(path).resolve()
    if path.stat().st_size > 4*1024**2:
        raise ValueError('Reference descriptor exceeds 4 MiB')
    descriptor_before = digest(path)
    bundle = json.loads(path.read_text())
    if (bundle.get('schema') != 1 or bundle.get('sources') != sources()
            or bundle.get('points') != POINTS.tolist()):
        raise ValueError('Stale or incompatible frozen reference source/schema/probes')
    config = bundle['config']
    validate_config(config)
    expected = {'parent'} | ({'reference-%d' % r for r in config['ratios'] if r != 1}
                             if config['fine_reference'] else set())
    if set(bundle['recordings']) != expected:
        raise ValueError('Missing or unexpected reference recordings')
    paths = {}
    for name, item in bundle['recordings'].items():
        manifest = (path.parent/item['manifest']).resolve()
        if path.parent not in manifest.parents:
            raise ValueError('Reference recording must remain inside its bundle directory')
        actual = recording_identity(manifest)
        if actual != {k:item[k] for k in ('manifest_sha256','frames')}:
            raise ValueError('Frozen reference recording changed')
        _, data, _ = read_manifest(manifest)
        ratio = 1 if name == 'parent' else int(name.split('-')[1])
        expected_case=reference_case(ratio)
        recorded_case=dict(data['case'])
        physical_dx=recorded_case.pop('physical_dx',expected_case['dx'])
        if recorded_case!=expected_case or not np.isclose(physical_dx,expected_case['dx'],rtol=0,atol=1e-12):
            raise ValueError('Frozen reference geometry/model differs from the configured experiment')
        expected_iterations = list(range(config['warmup']*ratio, (config['warmup']+config['steps'])*ratio+1, config['interval']*ratio))
        if [e.get('iteration') for e in data['frames']] != expected_iterations:
            raise ValueError('Frozen reference iteration inventory differs from its configuration')
        times, _, _, _ = series(manifest, POINTS)
        dt=expected_case['dx']*expected_case['mach']/(np.sqrt(3)*expected_case['speed'])
        if not np.allclose(times,np.asarray(expected_iterations)*dt,rtol=0,atol=1e-10):
            raise ValueError('Frozen reference absolute clock differs from the configured experiment')
        if name == 'parent':
            parent_times = times
        paths[name] = manifest
    for name, manifest in paths.items():
        times, _, _, _ = series(manifest, POINTS)
        if times.shape != parent_times.shape or not np.allclose(times, parent_times, rtol=0, atol=1e-10):
            raise ValueError('Frozen reference clocks differ')
    if descriptor_before != digest(path):
        raise ValueError('Frozen reference descriptor changed while loading')
    bundle['_descriptor_sha256'] = descriptor_before
    return bundle, paths


def validate_config(config):
    for key in ('warmup', 'steps', 'interval'):
        minimum = 0 if key == 'warmup' else 1
        if type(config.get(key)) is not int or not minimum <= config[key] <= 100000:
            raise ValueError('Invalid reference '+key)
    ratios = config.get('ratios')
    if (not isinstance(ratios, list) or not ratios or len(set(ratios)) != len(ratios)
            or any(type(r) is not int or r not in (1,2) for r in ratios)
            or type(config.get('fine_reference')) is not bool):
        raise ValueError('Use distinct supported reference ratios 1 and/or 2')
    if (config['warmup']+config['steps'])*max(ratios)>100000 or config['warmup']%config['interval'] or config['steps']%config['interval']:
        raise ValueError('Use aligned warmup/steps/interval within the recording step budget')
    if config['steps']//config['interval'] < 7 or config['steps']//config['interval'] > 999:
        raise ValueError('Reference needs 8..1000 uniformly timed frames')


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True); p.add_argument('--device', default='cpu')
    p.add_argument('--warmup', type=int); p.add_argument('--steps', type=int)
    p.add_argument('--ratios'); p.add_argument('--interval', type=int)
    p.add_argument('--fine-reference', action='store_true', default=None)
    p.add_argument('--reference-only', action='store_true')
    p.add_argument('--diagnostic-nonstationary-reference', action='store_true',
                   help='Permit child diagnostics after a failed reference gate; never permits qualification')
    p.add_argument('--reuse-reference', type=Path)
    p.add_argument('--window-start', type=float); p.add_argument('--window-end', type=float)
    a = p.parse_args(argv)
    if any(v is not None and not np.isfinite(v) for v in (a.window_start,a.window_end)):
        p.error('Analysis window bounds must be finite')
    a.output = a.output.resolve(); a.output.mkdir(parents=True, exist_ok=False)
    began = time.monotonic()
    report = dict(passed=False, full_nesting_passed=False, full_scope=False, evaluated_ratios=[], rows=[], thresholds=THRESHOLDS,
                  environment=runtime(),
                  device=a.device, source_before=sources(), requested_window=dict(start=a.window_start,end=a.window_end),
                  scope='Offline nested cropped building; implementation study, not physical validation')
    try:
        if a.reuse_reference:
            bundle, paths = load_reference(a.reuse_reference)
            config = bundle['config']
            for key in ('warmup','steps','interval','fine_reference'):
                supplied = getattr(a,key)
                if supplied is not None and supplied != config[key]:
                    raise ValueError('Requested '+key+' differs from frozen reference')
            ratios = config['ratios'] if a.ratios is None else list(map(int,a.ratios.split(',')))
            if not ratios or len(set(ratios))!=len(ratios) or any(r not in config['ratios'] for r in ratios):
                raise ValueError('Requested ratios are absent from frozen reference')
            reference_path = a.reuse_reference.resolve()
        else:
            config = dict(warmup=5000 if a.warmup is None else a.warmup,
                          steps=1000 if a.steps is None else a.steps,
                          interval=10 if a.interval is None else a.interval,
                          ratios=[1,2] if a.ratios is None else list(map(int,a.ratios.split(','))),
                          fine_reference=bool(a.fine_reference))
            validate_config(config); ratios=config['ratios']
            reference_path = prepare_reference(a.output,config,a.device)
            bundle, paths = load_reference(reference_path)
        report['requested_ratios']=ratios
        report['available_ratios']=config['ratios']
        report['full_scope']=not a.reference_only and set(ratios)==set(config['ratios'])
        report['reference'] = dict(path=str(reference_path),sha256=bundle['_descriptor_sha256'],
                                   config=config,recordings=bundle['recordings'],source_device=bundle['device'],
                                   source_environment=bundle.get('environment'))
        report['reference_checks'] = {}
        for name, path in paths.items():
            t,u,pressure,quality = series(path,POINTS)
            health = 'within-tested-envelope' if all(q=='within-tested-envelope' for q in quality) else 'unchecked'
            report['reference_checks'][name] = metrics(t,u,pressure,u,pressure,health,a.window_start,a.window_end)
        if a.reference_only:
            report['scope'] = 'Frozen reference preparation and stationarity check only; no child or nesting qualification'
            report['passed'] = all(r['passed'] for r in report['reference_checks'].values())
        else:
            if not all(r['passed'] for r in report['reference_checks'].values()) and not a.diagnostic_nonstationary_reference:
                raise ValueError('Reference stationarity/health failed; qualify the reference before child comparison')
            report['diagnostic_nonstationary_reference'] = a.diagnostic_nonstationary_reference
            pt,pu,pp,_ = series(paths['parent'],POINTS)
            for ratio in ratios:
                dx=1./ratio
                child=case([20*ratio,16*ratio,12*ratio],dx,np.array([4+dx/2,4+dx/2,dx/2]))
                child['origin']=child['origin'].tolist()
                mapped=capture(paths['parent'],child,a.output/('boundary-%d.npz'%ratio))
                child_manifest=create_recording(mapped['case'],0,config['steps']*ratio,
                                                config['interval']*ratio,a.output/('child-%d'%ratio),a.device)
                ct,cu,cp,cq=series(child_manifest,POINTS)
                if ct.shape!=pt.shape or not np.allclose(ct,pt,atol=1e-10,rtol=0):
                    raise ValueError('Child and parent absolute clocks differ')
                name='reference-%d'%ratio if config['fine_reference'] and ratio>1 else 'parent'
                _,ru,rp,_=series(paths[name],POINTS)
                health='within-tested-envelope' if all(q=='within-tested-envelope' for q in cq) else 'unchecked'
                row=metrics(ct,ru,rp,cu,cp,health,a.window_start,a.window_end)
                row.update(ratio=ratio,reference=name,child_recording=recording_identity(child_manifest))
                report['rows'].append(row)
                report['evaluated_ratios'].append(ratio)
                np.savez_compressed(a.output/('comparison-%d.npz'%ratio),points=POINTS,times=ct,
                    parent_velocity=pu,child_velocity=cu,parent_pressure=pp,child_pressure=cp,
                    reference_velocity=ru,reference_pressure=rp)
            report['passed']=bool(report['rows']) and all(r['passed'] for r in report['rows']) and all(r['passed'] for r in report['reference_checks'].values())
            report['full_nesting_passed']=report['passed'] and report['full_scope']
        if report['reference']['sha256']!=digest(reference_path):
            raise ValueError('Frozen reference descriptor changed during execution')
        load_reference(reference_path)
        report['source_after']=sources()
        if report['source_before']!=report['source_after']:
            raise ValueError('Source changed during study')
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        report.update(passed=False,full_nesting_passed=False,error=type(exc).__name__+': '+str(exc))
    report['wall_seconds']=time.monotonic()-began
    (a.output/'result.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(passed=report['passed'],full_nesting_passed=report['full_nesting_passed'],
                         error=report.get('error'),output=str(a.output)),indent=2))
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
