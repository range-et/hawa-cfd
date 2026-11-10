"""Record real evolving TGV fields for the editable playback example."""
from pathlib import Path
from hawa.plugin import Session
from hawa.recording import record

def main(output=None, device="mps"):
    root=Path(__file__).resolve().parents[1]
    out=Path(output) if output is not None else root/'results/v04/vortex-recording-v2'
    s=Session({'example':'tgv3d-bgk','size':24,'origin':[0,0,0],'spacing':1.},device)
    print(record(s,300,10,out,lambda n: print('step',n,flush=True) if n%50==0 else None),flush=True)

if __name__ == "__main__":
    main()
