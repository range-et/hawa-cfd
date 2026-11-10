"""Fractional-wall Poiseuille benchmark in lattice units, independent of Rhino."""
import json
from pathlib import Path
import numpy as np
import torch
import lettuce as lt
from hawa.walls import install_interpolated_walls


def run(n,q,device='cpu',dtype=torch.float32):
    ctx=lt.Context(torch.device(device),dtype,use_native=False)
    class Channel(lt.Flow):
        def __init__(self):
            self.solid=ctx.zero_tensor([4,n,4],dtype=torch.bool);self.solid[:,0,:]=True;self.solid[:,-1,:]=True
            self.spec={'boundaries':['periodic']*6}
            units=lt.UnitConversion(1,.05,characteristic_length_lu=n-1,characteristic_length_pu=n-1)
            super().__init__(ctx,[4,n,4],units,lt.D3Q19(),lt.QuadraticEquilibrium())
        @property
        def grid(self):return torch.meshgrid(*(torch.arange(k,device=ctx.device) for k in self.resolution),indexing='ij')
        def initial_pu(self):return ctx.zero_tensor([1,*self.resolution]),ctx.zero_tensor([3,*self.resolution])
        @property
        def post_boundaries(self):return [lt.BounceBackBoundary(self.solid)]
    flow=Channel();force=2e-6;nu=.1;tau=.5+3*nu
    sim=lt.Simulation(flow,lt.BGKCollision(tau,lt.Guo(flow,tau,[force,0,0])),[])
    links=[];solid=flow.solid.cpu().numpy();shape=solid.shape
    for p in np.argwhere(~solid):
        for i,e in enumerate(flow.stencil.e[1:],1):
            ahead=(p+e)%np.array(shape)
            if solid[tuple(ahead)]:links.append([i,int(np.ravel_multi_index(p,shape)),q])
    install_interpolated_walls(sim,links)
    for _ in range(int(8*n*n/nu)//100):sim(100)
    y=np.arange(1,n-1);lo=1-q;hi=n-2+q
    expected=force/(2*nu)*(y-lo)*(hi-y)
    # Guo macroscopic velocity includes the half-force correction.
    actual=flow.u()[0,2,1:-1,2].cpu().numpy()+force/2
    error=float(np.linalg.norm(actual-expected)/np.linalg.norm(expected))
    return {'n':n,'q':q,'relative_l2':error,'max_speed':float(actual.max()),'expected_max':float(expected.max())}

def main():
    rows=[run(n,q) for q in (.25,.75) for n in (8,12,16)]
    print(json.dumps(rows,indent=2))
    out=Path(__file__).resolve().parents[1]/'results/v04/wall-benchmark.json';out.write_text(json.dumps(rows,indent=2))


if __name__ == "__main__":
    main()
