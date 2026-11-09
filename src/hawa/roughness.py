"""Spatial aerodynamic roughness for a planar ground; no geometric displacement."""
import copy
import numpy as np


def grid(spec):
    default=spec['neutral_precursor']['roughness_length_m'];n=spec['shape'][:2]
    data=spec.get('wall_roughness')
    if data is None:return np.full(n,default,float)
    if not isinstance(data,dict) or data.get('schema')!=1 or data.get('face')!='z-':raise ValueError('Wall roughness requires schema 1 on Z-')
    values=np.asarray(data.get('length_m'),float)
    if values.shape!=(n[0]*n[1],) or not np.isfinite(values).all() or np.any(values<=0) or np.any(values>=spec['dx']/2):raise ValueError('Roughness requires one finite 0 < z0 < dx/2 value per ground column')
    return values.reshape(n)


def apply(spec,regions):
    from .plugin import check_case
    check_case(spec)
    if not spec.get('neutral_precursor'):raise ValueError('Planar wall roughness currently requires Neutral Flow')
    if not isinstance(regions,list) or not 1<=len(regions)<=100:raise ValueError('Provide 1..100 roughness regions')
    result=copy.deepcopy(spec);values=grid(spec);x,y=np.indices(values.shape);covered=[]
    for region in regions:
        points=np.asarray(region.get('polygon'),float);length=region.get('length_m')
        if points.ndim!=2 or points.shape[1]!=2 or not 3<=len(points)<=1000 or not np.isfinite(points).all():raise ValueError('Roughness polygon needs finite lattice XY coordinates')
        if not isinstance(length,(int,float)) or not np.isfinite(length) or not 0<length<spec['dx']/2:raise ValueError('Require roughness 0 < z0 < dx/2 in metres')
        mask=np.zeros(values.shape,bool)
        for a,b in zip(points,np.roll(points,-1,axis=0)):
            if a[1]==b[1]:continue
            mask^=((a[1]>y)!=(b[1]>y))&(x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0])
        if not mask.any():raise ValueError('Roughness region contains no ground column; enlarge it or refine the domain')
        values[mask]=length;covered.append(int(mask.sum()))
    result['wall_roughness']=dict(schema=1,face='z-',length_m=values.ravel().tolist(),region_order='last region wins')
    check_case(result)
    return dict(case=result,report=dict(covered_columns=covered,minimum_z0_m=float(values.min()),maximum_z0_m=float(values.max()),limits='Planar equilibrium wall law; local separation and waves are not modelled'))
