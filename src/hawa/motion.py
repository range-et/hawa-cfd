"""Prescribed rigid motion in domain-local physical metres and seconds.

The motion, moving-body and motion-evaluation payloads are declared below as
pydantic models: an unversioned v0, exactly the shape Grasshopper sends today.
The models only validate. Callers keep the original dicts, so case hashes and
checkpoint specs stay byte-identical. Every model follows the #68 rules that keep
the known pydantic 2.13 advisories unreachable: BaseModel only, extra='forbid',
Python-mode model_validate, and no Fraction or URL types. Annotations are
evaluated at runtime on Rhino's Python 3.9, so use Optional/Union, never X | Y.
"""
import math
from typing import Annotated, Any, Dict, List, Literal, Optional, Union
import numpy as np
import pydantic
import pydantic_core


def require_pinned_pydantic():
    """Rhino shares one interpreter across script venvs, so the first pydantic loaded wins.

    The advisory analysis covers only the pinned release; refuse any other.
    """
    found=(pydantic.VERSION,pydantic_core.__version__)
    if found!=('2.13.5','2.46.5'):
        raise RuntimeError('pydantic {} with pydantic-core {} was already loaded, probably by another plugin or script. '
                           'Hawa requires pydantic 2.13.5 with pydantic-core 2.46.5; restart Rhino before using moving bodies.'.format(*found))


require_pinned_pydantic()
from pydantic import BaseModel, ConfigDict, Discriminator, Field, StrictFloat, StrictInt, StrictStr, Tag, ValidationError, model_validator


class Payload(BaseModel):
    # StrictFloat still accepts int (Grasshopper serializes 0d as the JSON integer 0)
    # but rejects numeric strings and booleans; allow_inf_nan=False keeps it finite.
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)


Vector=Annotated[List[StrictFloat],Field(min_length=3,max_length=3)]
NonNegative=Annotated[StrictFloat,Field(ge=0)]
Positive=Annotated[StrictFloat,Field(gt=0)]


class Motion(Payload):
    """Prescribed rigid motion. Unused parameters for the chosen type are ignored."""
    kind:Literal['Motion']=Field('Motion',description='Grasshopper object tag')
    type:Literal['fixed','translation','rotation','oscillation']='fixed'
    axis:Vector=Field([1.,0.,0.],description='Nonzero direction or rotation axis, domain-local')
    ramp:NonNegative=Field(0.,description='Startup ramp, s')
    speed:StrictFloat=Field(0.,description='Translation speed, m/s')
    rpm:StrictFloat=Field(0.,description='Rotation rate, revolutions per minute')
    amplitude:StrictFloat=Field(0.,description='Oscillation amplitude, m (translation) or rad (rotation)')
    frequency:NonNegative=Field(0.,description='Oscillation frequency, Hz')
    phase:StrictFloat=Field(0.,description='Oscillation phase, rad')
    mode:Literal['translation','rotation']=Field('translation',description='Oscillation mode')

    @model_validator(mode='after')
    def nonzero_axis(self):
        if np.linalg.norm(self.axis)<1e-12:raise ValueError('Motion axis cannot be zero')
        return self


class Sphere(Payload):
    type:Literal['sphere']
    center:Vector=Field(description='Centre, m')
    radius:Positive=Field(description='Radius, m')


class Cylinder(Payload):
    """Cylinder along the body's local z axis."""
    type:Literal['cylinder']
    center:Vector=Field(description='Centre, m')
    radius:Positive=Field(description='Radius, m')
    length:Positive=Field(description='Length, m')


class Sdf(Payload):
    """Signed distances (negative inside) on a regular grid, C order (z fastest)."""
    type:Literal['sdf']
    origin:Vector=Field(description='First sample position, m')
    shape:Annotated[List[Annotated[StrictInt,Field(ge=3)]],Field(min_length=3,max_length=3)]
    spacing:Positive=Field(description='Sample spacing, m')
    values:Annotated[List[StrictFloat],Field(max_length=200000)]=Field(description='Signed distances, m')

    @model_validator(mode='after')
    def sample_count(self):
        if math.prod(self.shape)>200000:raise ValueError('SDF shape exceeds 200000 samples')
        if len(self.values)!=math.prod(self.shape):raise ValueError('SDF values must match its shape')
        return self


def geometry_type(value):
    return value.get('type') if isinstance(value,dict) else None


class Body(Payload):
    """One prescribed-motion body; Motion Case removes Grasshopper's domain_key."""
    kind:Literal['Body']=Field('Body',description='Grasshopper object tag')
    id:Annotated[StrictStr,Field(min_length=1)]
    pivot:Vector=Field(description='Rotation pivot at time zero, m')
    motion:Motion=Field(default_factory=Motion)
    geometry:Annotated[Union[Annotated[Sphere,Tag('sphere')],Annotated[Cylinder,Tag('cylinder')],Annotated[Sdf,Tag('sdf')]],
                       Discriminator(geometry_type,custom_error_type='geometry_type',
                                     custom_error_message='use type sphere, cylinder or sdf')]


class MotionEvaluation(Payload):
    """Motion Evaluate job request; the job envelope keys are declared too."""
    kind:Literal['motion_evaluate']='motion_evaluate'
    case:Dict[str,Any]=Field(default_factory=dict,description='Case spec, validated by the session')
    device:StrictStr='auto'
    period:Positive=Field(1.,description='Common motion period, s')
    settle_cycles:Annotated[StrictInt,Field(ge=0,le=20)]=1
    cycles:Annotated[StrictInt,Field(ge=1,le=20)]=1
    metric:Literal['force','torque','power','input_power']='input_power'
    axis:Annotated[StrictInt,Field(ge=0,le=2)]=Field(0,description='Domain axis for force and torque')
    body_id:Optional[Annotated[StrictStr,Field(min_length=1)]]=Field(None,description='Default: the first moving body')


def check(model, payload, label):
    """Validate a Python payload; report the first problem as one short ValueError."""
    try:return model.model_validate(payload)
    except ValidationError as error:
        first=error.errors()[0];where='.'.join(str(part) for part in first['loc'])
        reason=str(first['ctx']['error']) if first['type']=='value_error' else first['msg']
        raise ValueError(label+(' '+where if where else '')+': '+reason) from error


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
    for index,body in enumerate(bodies):
        check(Body,body,'Moving body {}'.format(index+1));g=body['geometry']
        if g['type']=='sdf':
            grid=np.asarray(g['values']).reshape(g['shape'])
            if not np.any(grid<0):raise ValueError('SDF requires a resolved interior')
            if any(np.any(np.take(grid,side,axis=axis)<=0) for axis in range(3) for side in (0,-1)):raise ValueError('SDF needs a positive exterior padding layer')
        if (spec['speed']+speed_bound(body))*spec.get('mach',.05)/spec['speed']>.15:
            raise ValueError('Inlet plus maximum wall speed exceeds lattice Mach 0.15; reduce lattice Mach or motion speed')
    ids=[body['id'] for body in bodies]
    if len(set(ids))!=len(ids):raise ValueError('Body IDs must be unique')


def evaluate_motion(session, request, checkpoint):
    """Complete whole prescribed cycles before publishing a search objective."""
    r=check(MotionEvaluation,request,'Motion evaluation')
    if not hasattr(session.solver,'moving'):raise ValueError('Motion evaluation requires moving bodies')
    period=r.period;settle=r.settle_cycles;cycles=r.cycles
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
    body_id=session.spec['moving_bodies'][0]['id'] if r.body_id is None else r.body_id;metric=r.metric;axis=r.axis
    values=[]
    for h in history:
        load=next((v for v in h['loads'] if v['id']==body_id),None)
        if load is None:raise ValueError('Unknown evaluation body ID')
        values.append(-load['power'] if metric=='input_power' else load[metric] if metric=='power' else load[metric][axis])
    return dict(fitness=float(np.mean(values)),std=float(np.std(values)),samples=len(values),steps=steps,
                metric=metric,body_id=body_id,period=period,settle_cycles=settle,cycles=cycles,
                limits='Prescribed motion; minimize signed mean load. Check cycle and grid convergence.')
