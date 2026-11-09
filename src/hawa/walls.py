"""Stationary Bouzidi linear interpolated bounce-back on D3Q19 fluid links.

The post-stream correction uses post-collision populations. Full-way obstacle
sites remain masked. Only adjacent fluid populations receive the correction.
"""
from collections import deque
import numpy as np
import torch


def install_interpolated_walls(simulation, links):
    flow=simulation.flow;ctx=flow.context;shape=tuple(flow.resolution)
    data=np.asarray(links,float)
    if data.ndim!=2 or data.shape[1]!=3 or not np.isfinite(data).all():raise ValueError('Wall links need [direction, fluid flat index, fraction]')
    direction=data[:,0].astype(int);index=data[:,1].astype(int);distance=data[:,2]
    if np.any(data[:,:2]!=data[:,:2].astype(int)) or np.any(direction<1) or np.any(direction>=flow.stencil.q) or np.any(index<0) or np.any(index>=np.prod(shape)) or np.any(distance<=0) or np.any(distance>1):raise ValueError('Invalid interpolated wall link')
    if len(set(zip(direction.tolist(),index.tolist())))!=len(index):raise ValueError('Duplicate wall links')
    coords=np.array(np.unravel_index(index,shape)).T;e=np.asarray(flow.stencil.e)[direction]
    behind=coords-e;ahead=coords+e
    boundaries=getattr(flow,'spec',{}).get('boundaries',['wall']*6)
    for axis,n in enumerate(shape):
        outside=(behind[:,axis]<0)|(behind[:,axis]>=n)|(ahead[:,axis]<0)|(ahead[:,axis]>=n)
        if outside.any() and boundaries[2*axis:2*axis+2]!=['periodic','periodic']:
            raise ValueError('Wall links require one-cell fluid padding')
        behind[:,axis]%=n;ahead[:,axis]%=n
    solid=flow.solid.detach().cpu().numpy()
    if np.any(solid[tuple(coords.T)]) or not np.all(solid[tuple(ahead.T)]):raise ValueError('Wall links must point from fluid into solid')
    # Narrow gaps cannot supply the second fluid site required by q < 0.5.
    if np.any((distance<.5)&solid[tuple(behind.T)]):raise ValueError('Unresolved narrow gap at curved wall. Refine the grid.')
    qi=torch.tensor(direction,device=ctx.device,dtype=torch.long)
    oi=torch.tensor(np.asarray(flow.stencil.opposite)[direction],device=ctx.device,dtype=torch.long)
    ix=torch.tensor(index,device=ctx.device,dtype=torch.long)
    bi=torch.tensor(np.ravel_multi_index(behind.T,shape),device=ctx.device,dtype=torch.long)
    q=ctx.convert_to_tensor(distance);ev=ctx.convert_to_tensor(e)
    simulation.wall_history=deque(maxlen=20)
    pending = {}
    def capture():
        f=flow.f.view(flow.stencil.q,-1)
        incoming=f[qi,ix].clone();opposite=f[oi,ix].clone();back=f[qi,bi].clone()
        reflected=torch.where(q<.5,2*q*incoming+(1-2*q)*back,incoming/(2*q)+(1-1/(2*q))*opposite)
        pending["reflected"] = reflected
        pending["incoming"] = incoming
    def reconstruct():
        reflected = pending.pop("reflected")
        incoming = pending.pop("incoming")
        flow.f.view(flow.stencil.q,-1)[oi,ix]=reflected
        simulation.wall_history.append(torch.sum((incoming+reflected)[:,None]*ev,dim=0).detach().clone())
    from .step import coordinator
    coordinator(simulation).register("interpolated-walls", capture, reconstruct)
    return simulation
