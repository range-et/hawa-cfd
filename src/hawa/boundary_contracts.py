"""Solver-independent physical patch schema, SI values and face identities.

No tensor backend, population indexing or numerical method is part of this data
contract. Solver adapters must validate their own supported combinations.
"""
import copy
import numpy as np

FACES = ('x-', 'x+', 'y-', 'y+', 'z-', 'z+')


def conditions(spec):
    data = spec.get('boundary_set')
    if not isinstance(data, dict) or data.get('schema') != 1:
        raise ValueError('Boundary set requires schema 1')
    patches = data.get('patches')
    if not isinstance(patches, list) or len(patches) != 6:
        raise ValueError('Boundary set must cover each of six faces exactly once')
    by_face = {}; names = set()
    for p in patches:
        if not isinstance(p, dict) or p.get('face') not in FACES or not isinstance(p.get('id'), str) or not p['id']:
            raise ValueError('Patch requires a name and an oriented face')
        if p['face'] in by_face or p['id'] in names:
            raise ValueError('Duplicate patch name or face')
        c = copy.deepcopy(p.get('condition', {}))
        if not isinstance(c, dict):
            raise ValueError('Patch condition must be an object')
        if c.get('type') not in ('velocity', 'pressure', 'open', 'wall', 'slip', 'periodic'):
            raise ValueError('Unsupported boundary condition')
        backflow=c.get('backflow_mode','velocity')
        if backflow not in ('velocity','pressure') or (backflow!='velocity' and c['type']!='open'):
            raise ValueError('Backflow mode must be velocity or pressure on an open face')
        if c['type'] in ('velocity', 'wall', 'open'):
            v = np.asarray(c.get('velocity', [0., 0., 0.]), dtype=float)
            if v.shape != (3,) or not np.isfinite(v).all():
                raise ValueError('Boundary velocity requires three finite m/s components')
            axis = FACES.index(p['face'])//2
            outward = 1 if FACES.index(p['face'])%2 else -1
            if c['type']=='wall' and abs(v[axis])>1e-12:
                raise ValueError('A fixed domain wall cannot have normal velocity')
            if c['type']=='open' and v[axis]*outward>1e-12:
                raise ValueError('Open exterior velocity must be incoming or tangential')
            if c['type']=='open' and backflow=='pressure' and abs(v[axis])>1e-12:
                raise ValueError('Pressure backflow derives normal velocity; prescribe only tangential exterior velocity')
            c['velocity'] = v.tolist()
        if c['type'] in ('open', 'pressure'):
            pvalue = c.get('pressure_pa', 0.)
            if not isinstance(pvalue, (int, float)) or not np.isfinite(pvalue):
                raise ValueError('Pressure must be finite gauge Pa')
            c['pressure_pa'] = float(pvalue)
        profile = c.get('profile', 'uniform')
        if profile not in ('uniform', 'parabolic', 'mapped', 'neutral') or (profile != 'uniform' and c['type'] != 'velocity' and not(profile in ('neutral','mapped') and c['type']=='open' and spec.get('neutral_precursor'))):
            raise ValueError('Only velocity supports parabolic or mapped profiles')
        if profile == 'neutral' and not spec.get('neutral_precursor'):
            raise ValueError('Neutral profile requires the neutral model contract')
        if profile == 'parabolic':
            a = c.get('profile_axis')
            if type(a) is not int or a not in (0, 1, 2) or a == FACES.index(p['face'])//2:
                raise ValueError('Parabolic profile requires a tangential profile_axis')
        if profile == 'mapped':
            ref=spec.get('boundary_field',{})
            if ref.get('schema')=='hawa-boundary-series-2':
                if not spec.get('neutral_precursor') or p['face'] not in ref.get('faces',[]):raise ValueError('Mapped v2 face is not present in the attached field')
            elif p['face']!='x-' or not ref:raise ValueError('Mapped v1 data requires an attached X- field')
        by_face[p['face']] = c; names.add(p['id'])
    return [by_face[f] for f in FACES]


