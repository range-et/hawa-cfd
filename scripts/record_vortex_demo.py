"""Record real evolving TGV fields for the editable playback example."""
from pathlib import Path
from hawa.plugin import Session
from hawa.recording import record
root=Path(__file__).resolve().parents[1]
out=root/'results/v04/vortex-recording-v2'
s=Session({'example':'tgv3d-bgk','size':24,'origin':[0,0,0],'spacing':1.},'mps')
print(record(s,300,10,out,lambda n: print('step',n,flush=True) if n%50==0 else None),flush=True)
