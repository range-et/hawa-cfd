"""Measure the experimental coupling before exposing it in Grasshopper."""
import json
from pathlib import Path
import numpy as np
import torch
import lettuce as lt
from hawa.refinement import RefinedStepper


def benchmark(n=16,steps=40,device='cpu'):
    ctx=lt.Context(torch.device(device),torch.float32,use_native=False)
    def simulation(size,tau):
        flow=lt.TaylorGreenVortex(ctx,[size]*2,10,.05)
        return lt.Simulation(flow,lt.BGKCollision(tau),[])
    lo=n//4;hi=3*n//4-1
    coarse=simulation(n,.8);plain=simulation(n,.8);reference=simulation(2*n,1.1);fine=simulation(2*(hi-lo)+1,1.1)
    coupled=RefinedStepper(coarse,fine,[lo]*2,[hi]*2)
    value=coupled.interpolate(coarse.flow.f);eq=coupled.equilibrium(fine.flow,value);fine.flow.f=eq+coupled.scale*(value-eq)
    mass=float(coupled.composite_mass().cpu())
    coupled(steps);plain(steps);reference(2*steps)
    region=(slice(None),slice(2*lo+2,2*hi-1),slice(2*lo+2,2*hi-1))
    truth=reference.flow.u()[region].cpu().numpy()
    actual=fine.flow.u()[:,2:-2,2:-2].cpu().numpy()
    coarse_estimate=coupled.interpolate(plain.flow.f);coarse_u=torch.einsum('qd,q...->d...',fine.flow.torch_stencil.e,coarse_estimate)/coarse_estimate.sum(0,keepdim=True)
    error=lambda u:float(np.linalg.norm(u-truth)/np.linalg.norm(truth))
    return {'n':n,'steps':steps,'device':device,'refined_relative_l2':error(actual),'coarse_relative_l2':error(coarse_u[:,2:-2,2:-2].cpu().numpy()),'relative_mass_drift':float(coupled.composite_mass().cpu())/mass-1}

def main():
    values=[benchmark(n,40) for n in (16,24,32)]
    if torch.backends.mps.is_available():values.append(benchmark(16,40,'mps'))
    print(json.dumps(values,indent=2));(Path(__file__).resolve().parents[1]/'results/v04/refinement-benchmark.json').write_text(json.dumps(values,indent=2))


if __name__ == "__main__":
    main()
