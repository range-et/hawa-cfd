"""Additional finite products for refinement and immutable field consumers."""
import itertools
import numpy as np
from .cases import combinations, make_combination

SCALARS = ('speed','pressure','density','ux','uy','uz','cp','vorticity','q')
FIELD_ACTIONS = ('sample','plane','contours','isosurface','trace')


def refinements():
    for row in combinations():
        yield dict(row, id=row['id'].replace('solver/','refinement/'),
                   expected=row['mode']=='legacy' and row['collision']=='bgk' and row['geometry']=='empty' and not row['mapped'])

    yield dict(id='refinement/legacy/bgk/interior-clear/uniform',mode='legacy',collision='bgk',geometry='interior-clear',mapped=False,expected=True)

def make_refinement(row, directory):
    coarse=make_combination(row,directory)
    fine=dict(coarse,shape=[9]*3,dx=.5,spacing=.5,origin=[3.,3.,3.5],refinement_lower=[3]*3,refinement_upper=[7]*3)
    if row['geometry']=='interior-clear':
        coarse.update(shape=[17]*3,solid=[int(np.ravel_multi_index(p,(17,)*3)) for p in itertools.product((8,9),repeat=3)])
        fine.update(shape=[13]*3,origin=[5.,5.,5.5],refinement_lower=[5]*3,refinement_upper=[11]*3,
                    solid=[int(np.ravel_multi_index(p,(13,)*3)) for p in itertools.product(range(6,9),repeat=3)])
    return dict(case=coarse,fine_case=fine,steps=2)


def field_cases():
    for dim,masked,storage,name,action in itertools.product((2,3),(False,True),('memory','reload'),SCALARS,FIELD_ACTIONS):
        yield dict(id='field/%s/%s/%s/%s/%s'%(dim,'solid' if masked else 'fluid',storage,name,action),
                   dim=dim,masked=masked,storage=storage,field=name,action=action,
                   expected=not (dim==2 and action=='isosurface'))


def exercise_field(row,directory):
    from hawa.fields import store,dispatch_field
    dim=row['dim'];grid=np.indices((7,)*dim).astype(float)
    velocity=np.array([.5+.01*grid[0],.02*grid[1]]+([.03*grid[2]] if dim==3 else []))
    arrays=dict(velocity=velocity,pressure=grid.sum(0),density=np.full((7,)*dim,1.225),solid=np.zeros((7,)*dim,bool))
    if row['masked']:arrays['solid'][(2,)*dim]=True
    spec=dict(dx=1.,density=1.225,speed=1.)
    frame=store(arrays,dict(case=spec,iteration=0,time=0.))['frame']
    if row['storage']=='reload':
        path=str(directory/'field.npz')
        dispatch_field(dict(action='save',frame=frame,path=path))
        frame=dispatch_field(dict(action='load',path=path))['frame']
    points=[[x,y]+([3.] if dim==3 else []) for x in (3.,4.) for y in (3.,4.)]
    request=dict(row,frame=frame,points=points,shape=[2,2],levels=[6.5],level=6.5,seeds=[points[0]],steps=4,step=.1)
    result=dispatch_field(request)
    action=row['action'];name=row['field']
    if action in ('sample','plane'):
        assert all(result['valid']) and len(result['values'])==4
        p=np.array(points[0]);u=np.array([.5+.01*p[0],.02*p[1]]+([.03*p[2]] if dim==3 else []))
        expected=dict(speed=np.linalg.norm(u),pressure=sum(p),density=1.225,ux=u[0],uy=u[1],uz=u[2] if dim==3 else 0.,cp=sum(p)/.6125,vorticity=0.,q=-.5*sum(v*v for v in [.01,.02]+([.03] if dim==3 else [])))
        np.testing.assert_allclose(result['values'][0],expected[name],atol=1e-12)
        invalid=dispatch_field(dict(action='sample',frame=frame,field=name,points=[[-1.]*dim]+([[2.]*dim] if row['masked'] else [])))
        assert not any(invalid['valid'])
    elif action=='trace':
        assert len(result['paths'])==1 and len(result['paths'][0])==4
        assert np.isfinite(result['paths']).all() and np.isfinite(result['values']).all()
    elif action=='isosurface':
        assert np.isfinite(result['vertices']).all()
        if name=='pressure':assert len(result['faces'])>0
    elif action=='contours':assert np.isfinite(result['lines']).all()
    return result
