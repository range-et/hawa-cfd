"""Prescribed rigid motion in domain-local physical metres and seconds."""
import math
import numpy as np


def vector(value, name):
    a=np.asarray(value,float)
    if a.shape!=(3,) or not np.isfinite(a).all():raise ValueError(name+' requires three finite values')
    return a


def validate_motion(m):
    if m.get('type','fixed') not in ('fixed','translation','rotation','oscillation'):raise ValueError('Unknown motion type')
    for key in ('speed','rpm','amplitude','frequency','phase','ramp'):
        if not math.isfinite(float(m.get(key,0))):raise ValueError('Motion parameters must be finite')
    if m.get('ramp',0)<0 or m.get('frequency',0)<0:raise ValueError('Ramp and frequency must be nonnegative')
    axis=vector(m.get('axis',[1,0,0]),'Motion axis')
    if np.linalg.norm(axis)<1e-12:raise ValueError('Motion axis cannot be zero')
    if m.get('mode','translation') not in ('translation','rotation'):raise ValueError('Oscillation mode: translation or rotation')


def pose(body, time):
    """Rotation maps reference vectors to current vectors; phase is radians."""
    m=body.get('motion',{});kind=m.get('type','fixed');axis=np.asarray(m.get('axis',[1,0,0]),float);axis/=np.linalg.norm(axis)
    ramp=float(m.get('ramp',0));t=max(0.,float(time))
    if ramp>0 and t<ramp:
        r=.5*(1-math.cos(math.pi*t/ramp));dr=.5*math.pi/ramp*math.sin(math.pi*t/ramp)
        integral=.5*(t-ramp/math.pi*math.sin(math.pi*t/ramp))
    else:r=1.;dr=0.;integral=t-ramp/2
    displacement=np.zeros(3);velocity=np.zeros(3);angle=0.;omega=0.
    if kind=='translation':displacement=axis*float(m.get('speed',0))*integral;velocity=axis*float(m.get('speed',0))*r
    if kind=='rotation':omega=float(m.get('rpm',0))*2*math.pi/60;angle=omega*integral;omega*=r
    if kind=='oscillation':
        w=2*math.pi*float(m.get('frequency',0));phase=float(m.get('phase',0));a=float(m.get('amplitude',0))
        x=a*(math.sin(w*t+phase)-math.sin(phase));v=a*w*math.cos(w*t+phase)
        if m.get('mode','translation')=='rotation':angle=r*x;omega=dr*x+r*v
        else:displacement=axis*r*x;velocity=axis*(dr*x+r*v)
    x,y,z=axis;K=np.array([[0,-z,y],[z,0,-x],[-y,x,0]])
    rotation=np.eye(3)+math.sin(angle)*K+(1-math.cos(angle))*(K@K)
    return dict(id=body['id'],time=t,pivot=(np.asarray(body['pivot'])+displacement).tolist(),
                rotation=rotation.tolist(),velocity=velocity.tolist(),omega=(axis*omega).tolist())


def speed_bound(body):
    m=body.get('motion',{});kind=m.get('type','fixed');radius=body_radius(body)
    if kind=='translation':return abs(float(m.get('speed',0)))
    if kind=='rotation':return abs(float(m.get('rpm',0)))*2*math.pi/60*radius
    if kind=='oscillation':
        v=abs(float(m.get('amplitude',0)))*(2*math.pi*float(m.get('frequency',0))+(math.pi/float(m['ramp']) if m.get('ramp',0)>0 else 0))
        return v*(radius if m.get('mode','translation')=='rotation' else 1)
    return 0.


def body_radius(body):
    g=body['geometry'];center=np.asarray(g.get('center',body['pivot']))
    if g['type']=='sphere':radius=float(g['radius'])
    elif g['type']=='cylinder':radius=math.hypot(float(g['radius']),float(g['length'])/2)
    else:
        lo=np.asarray(g['origin']);hi=lo+(np.asarray(g['shape'])-1)*g['spacing']
        return float(max(np.linalg.norm(np.array([x,y,z])-body['pivot']) for x in (lo[0],hi[0]) for y in (lo[1],hi[1]) for z in (lo[2],hi[2])))
    return float(np.linalg.norm(center-body['pivot'])+radius)


def validate_bodies(spec):
    bodies=spec.get('moving_bodies',[])
    if not isinstance(bodies,list) or not 1<=len(bodies)<=4:raise ValueError('Use one to four moving bodies')
    if spec.get('collision','regularized')!='bgk' or spec.get('wall_links') or 'refinement_lower' in spec:
        raise ValueError('Moving bodies require uniform BGK without stationary curved links or refinement')
    if np.prod(spec['shape'])>150000:raise ValueError('Experimental moving domains are limited to 150000 cells')
    ids=[]
    for body in bodies:
        if not isinstance(body.get('id'),str) or not body['id']:raise ValueError('Body ID is required')
        ids.append(body['id']);vector(body['pivot'],'Pivot');validate_motion(body.get('motion',{}))
        g=body['geometry'];kind=g['type']
        if kind in ('sphere','cylinder'):
            vector(g['center'],'Center')
            for key in (('radius','length') if kind=='cylinder' else ('radius',)):
                if not math.isfinite(g[key]) or g[key]<=0:raise ValueError('Body dimensions must be positive')
        elif kind=='sdf':
            vector(g['origin'],'SDF origin');shape=g['shape']
            if len(shape)!=3 or any(type(n) is not int or n<3 for n in shape) or np.prod(shape)>200000:raise ValueError('SDF shape invalid or exceeds 200000 samples')
            values=np.asarray(g['values'])
            if values.size!=np.prod(shape) or not np.isfinite(values).all() or not np.any(values<0):raise ValueError('SDF requires finite samples and resolved interior')
            grid=values.reshape(shape)
            if any(np.any(np.take(grid,side,axis=axis)<=0) for axis in range(3) for side in (0,-1)):raise ValueError('SDF needs a positive exterior padding layer')
            if not math.isfinite(g['spacing']) or g['spacing']<=0:raise ValueError('SDF spacing must be positive')
        else:raise ValueError('Moving geometry: sphere, cylinder or sdf')
        if (spec['speed']+speed_bound(body))*spec.get('mach',.05)/spec['speed']>.15:
            raise ValueError('Inlet plus maximum wall speed exceeds lattice Mach 0.15; reduce lattice Mach or motion speed')
    if len(set(ids))!=len(ids):raise ValueError('Body IDs must be unique')


def evaluate_motion(session, request, checkpoint):
    """Complete whole prescribed cycles before publishing a search objective."""
    if not hasattr(session.solver,'moving'):raise ValueError('Motion evaluation requires moving bodies')
    period=float(request.get('period',1));settle=request.get('settle_cycles',1);cycles=request.get('cycles',1)
    if not math.isfinite(period) or period<=0 or type(settle) is not int or not 0<=settle<=20 or type(cycles) is not int or not 1<=cycles<=20:
        raise ValueError('Positive period, 0..20 settling cycles and 1..20 measured cycles required')
    for body in session.spec['moving_bodies']:
        m=body.get('motion',{});kind=m.get('type','fixed')
        rate=abs(m.get('rpm',0))/60 if kind=='rotation' else m.get('frequency',0) if kind=='oscillation' else 0
        if kind=='translation' or (rate and (period*rate<1-1e-7 or abs(period*rate-round(period*rate))>1e-7)):
            raise ValueError('Evaluation period must contain whole cycles of every motion')
        if m.get('ramp',0)>settle*period:raise ValueError('Startup ramp must finish during settling cycles')
    dt=session.solver.moving.dt;steps=int(math.ceil((settle+cycles)*period/dt))
    if steps>10000:raise ValueError('Motion evaluation exceeds 10000 steps; shorten cycles or revise scaling')
    while session.flow.i<steps:
        checkpoint(session.flow.i);session.advance(min(5,steps-session.flow.i))
    checkpoint(steps)
    history=[h for h in session.solver.moving.history if h['time']>settle*period and h['time']<=(settle+cycles)*period+dt*1e-7]
    if len(history)<10:raise ValueError('Use at least ten samples in the measurement window')
    body_id=request.get('body_id',session.spec['moving_bodies'][0]['id']);metric=request.get('metric','input_power');axis=request.get('axis',0)
    if metric not in ('force','torque','power','input_power') or type(axis) is not int or axis not in (0,1,2):raise ValueError('Metric force, torque, power or input_power; axis 0..2')
    values=[]
    for h in history:
        load=next((v for v in h['loads'] if v['id']==body_id),None)
        if load is None:raise ValueError('Unknown evaluation body ID')
        values.append(-load['power'] if metric=='input_power' else load[metric] if metric=='power' else load[metric][axis])
    return dict(fitness=float(np.mean(values)),std=float(np.std(values)),samples=len(values),steps=steps,
                metric=metric,body_id=body_id,period=period,settle_cycles=settle,cycles=cycles,
                limits='Prescribed motion; minimize signed mean load. Check cycle and grid convergence.')
