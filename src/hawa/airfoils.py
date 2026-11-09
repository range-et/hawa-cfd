"""Offline airfoil coordinates, local polars, and a linear lifting-line solver."""
from pathlib import Path
import numpy as np


def naca(code, count=161, closed=True):
    code=str(code).upper().replace('NACA','').strip()
    if len(code)!=4 or not code.isdigit():raise ValueError('Use a four-digit NACA designation')
    if type(count) is not int or not 21<=count<=2001:raise ValueError('Point count must be 21..2001')
    m,p,t=int(code[0])/100,int(code[1])/10,int(code[2:])/100
    if t<=0 or (m>0 and p==0):raise ValueError('Invalid NACA thickness or camber position')
    x=(1-np.cos(np.linspace(0,np.pi,(count+1)//2)))/2
    yt=5*t*(.2969*np.sqrt(x)-.126*x-.3516*x*x+.2843*x**3-(.1036 if closed else .1015)*x**4)
    yc=np.zeros_like(x);slope=yc.copy()
    if m:
        left=x<p
        yc[left]=m/p**2*(2*p*x[left]-x[left]**2)
        yc[~left]=m/(1-p)**2*((1-2*p)+2*p*x[~left]-x[~left]**2)
        slope[left]=2*m/p**2*(p-x[left]);slope[~left]=2*m/(1-p)**2*(p-x[~left])
    angle=np.arctan(slope)
    upper=np.column_stack((x-yt*np.sin(angle),yc+yt*np.cos(angle)))
    lower=np.column_stack((x+yt*np.sin(angle),yc-yt*np.cos(angle)))
    return {'name':'NACA '+code,'coordinates':np.concatenate((upper[::-1],lower[1:])).tolist(),
            'source':'Generated NACA four-digit formula','closed_trailing_edge':closed}


def read_airfoil(path):
    p=Path(path)
    if p.stat().st_size>2_000_000:raise ValueError('Coordinate file exceeds 2 MB')
    text=p.read_text(encoding='utf-8-sig');rows=[]
    for line in text.splitlines():
        tokens=line.replace(',',' ').split()
        if len(tokens)!=2:continue
        try:rows.append([float(t) for t in tokens])
        except ValueError:continue
    xy=np.array(rows,float)
    if xy.ndim!=2 or len(xy)<5 or not np.isfinite(xy).all():raise ValueError('Expected finite two-column airfoil coordinates')
    # Lednicer starts with upper/lower point counts followed by LE-to-TE surfaces.
    if np.all(xy[0]>=2) and np.all(xy[0]==np.floor(xy[0])):
        nu,nl=map(int,xy[0]);xy=xy[1:]
        if len(xy)!=nu+nl:raise ValueError('Lednicer point counts do not match')
        xy=np.concatenate((xy[:nu][::-1],xy[nu:]))
    keep=np.r_[True,np.linalg.norm(np.diff(xy,axis=0),axis=1)>1e-12];xy=xy[keep]
    chord=np.ptp(xy[:,0])
    if chord<=0:raise ValueError('Airfoil chord must be positive')
    xy[:,0]-=xy[:,0].min();xy/=chord
    if len(xy)>10000:raise ValueError('Limit airfoils to 10000 coordinates')
    return {'name':p.stem,'coordinates':xy.tolist(),'source':str(p.resolve()),'original_text':text}


def read_polar(path, reynolds=None, mach=None):
    """Accept CSV alpha,cl,cd[,cm] or an XFOIL text polar. Never download data."""
    p=Path(path)
    if p.stat().st_size>5_000_000:raise ValueError('Polar file exceeds 5 MB')
    text=p.read_text(encoding='utf-8-sig');lines=text.splitlines();rows=[];header=None
    for line in lines:
        tokens=line.strip().lower().replace(',',' ').split()
        if 'alpha' in tokens and 'cl' in tokens and 'cd' in tokens:header=tokens;continue
        if header is None:continue
        try:values=[float(v) for v in tokens]
        except ValueError:continue
        if len(values)!=len(header):continue
        row=dict(zip(header,values))
        rows.append([row['alpha'],row['cl'],row['cd'],row.get('cm',None)])
    if not rows:raise ValueError('Expected headers alpha, cl, cd and optional cm')
    if any(not np.isfinite(r[:3]).all() or r[2]<0 or (r[3] is not None and not np.isfinite(r[3])) for r in rows):raise ValueError('Polar values must be finite with nonnegative drag')
    rows.sort(key=lambda r:r[0])
    if len(set(r[0] for r in rows))!=len(rows):raise ValueError('Select one polar: duplicate angles found')
    if reynolds is not None and (not np.isfinite(reynolds) or reynolds<=0):raise ValueError('Reynolds number must be positive')
    if mach is not None and (not np.isfinite(mach) or mach<0):raise ValueError('Mach must be nonnegative')
    return {'source':str(p.resolve()),'reynolds':reynolds,'mach':mach,'columns':['alpha','cl','cd','cm'],'rows':rows,
            'conditions':'User supplied. Match Reynolds number, Mach and transition before comparing.'}


def operating_point(polar, alpha):
    a=np.array([r[:3] for r in polar['rows']])
    if not np.isfinite(alpha) or alpha<a[0,0] or alpha>a[-1,0]:raise ValueError('Angle outside polar: extrapolation is disabled')
    cl,cd=(float(np.interp(alpha,a[:,0],a[:,i])) for i in (1,2))
    cm = None
    if all(len(r)>3 and r[3] is not None for r in polar['rows']):
        cm = float(np.interp(alpha,a[:,0],[r[3] for r in polar['rows']]))
    return {'alpha':alpha,'cl':cl,'cd':cd,'cm':cm,'lift_drag':cl/cd if cd>0 else None}


def wing_analysis(span, root_chord, tip_chord, alpha, twist=0., alpha_zero=0., stations=21, polar=None):
    """Prandtl linear lifting line. Unswept wing, attached incompressible flow.

    Section lift slope 2*pi/radian. Profile drag requires independent polar data.
    """
    if not all(np.isfinite(v) for v in (span,root_chord,tip_chord,alpha,twist,alpha_zero)) or min(span,root_chord,tip_chord)<=0:raise ValueError('Finite conditions and positive dimensions required')
    if type(stations) is not int or not 5<=stations<=101:raise ValueError('Stations must be 5..101')
    theta=np.arange(1,stations+1)*np.pi/(stations+1)
    y=-.5*span*np.cos(theta);eta=np.abs(2*y/span)
    chord=root_chord+(tip_chord-root_chord)*eta
    modes=np.arange(1,stations+1)
    matrix=np.sin(theta[:,None]*modes)*(2*span/(np.pi*chord[:,None])+modes/np.sin(theta[:,None]))
    rhs=np.deg2rad(alpha+twist*eta-alpha_zero)
    coeff=np.linalg.solve(matrix,rhs)
    area=span*(root_chord+tip_chord)/2;ar=span*span/area
    cl=float(np.pi*ar*coeff[0]);cdi=float(np.pi*ar*np.sum(modes*coeff**2))
    circulation=2*span*(np.sin(theta[:,None]*modes)@coeff)
    result = {'CL':cl,'CDi':cdi,'area':area,'aspect_ratio':ar,'span_positions':y.tolist(),
            'section_cl':(2*circulation/chord).tolist(),'chords':chord.tolist(),
            'limits':'Linear attached flow, unswept wing, section slope 2*pi/radian. CDi excludes profile drag. No stall prediction.'}
    if polar is not None:
        # Linear section lift determines an effective angle after induced downwash.
        # The user must supply one attached-flow polar at matching Re/Mach.
        effective=np.rad2deg(np.asarray(result['section_cl'])/(2*np.pi))+alpha_zero
        positions=np.r_[-span/2,y,span/2]
        chords=np.r_[tip_chord,chord,tip_chord]
        points=[operating_point(polar,float(a)) for a in np.r_[alpha_zero,effective,alpha_zero]]
        cd_profile=float(np.trapezoid(np.array([p['cd'] for p in points])*chords,positions)/area)
        result.update(CD_profile=cd_profile,CD_total=cdi+cd_profile,polar_source=polar['source'],effective_alpha=effective.tolist())
        result['limits']+=' Profile drag integrates the supplied polar; constant section conditions. Match local Reynolds/Mach and attached-flow range.'
    return result


def dispatch_airfoil(request):
    action=request['action']
    if action=='naca':return naca(request['code'],request.get('count',161),request.get('closed',True))
    if action=='import':return read_airfoil(request['path'])
    if action=='polar':return read_polar(request['path'],request.get('reynolds'),request.get('mach'))
    if action=='operating_point':return operating_point(request['polar'],request['alpha'])
    if action=='wing':return wing_analysis(**{k:v for k,v in request.items() if k not in ('op','action')})
    raise ValueError('Unknown airfoil operation')
