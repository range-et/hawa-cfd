"""Render the recorded cylinder fields. Captions use the Monad palette."""
import json,hashlib
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
from make_v04_demo import ROOT,OUT,CAP,BG,FG,SUB,CMAP,card,write_video
SOURCE=ROOT/'results/v04/cylinder-recording-outflow'
data=json.loads((SOURCE/'manifest.json').read_text())

def picture(entry,closing=False):
    with np.load(SOURCE/entry['file']) as a:
        u=a['velocity'][:,:,:,1];solid=a['solid'][:,:,1]
    speed=np.linalg.norm(u,axis=0);vort=np.gradient(u[1],.15,axis=0)-np.gradient(u[0],.15,axis=1)
    # Exclude derivative stencils touching the solid.
    invalid=solid.copy()
    for axis in (0,1):invalid|=np.roll(solid,1,axis)|np.roll(solid,-1,axis)
    vort=np.ma.array(vort,mask=invalid);speed=np.ma.array(speed,mask=solid)
    fig,axs=plt.subplots(2,1,figsize=(16,7),dpi=110,facecolor=BG)
    for ax,value,cmap,lo,hi,label in zip(axs,(speed,vort),(CMAP,'turbo'),(0,-2),(1.6,2),('Speed / m/s','Spanwise vorticity / 1/s')):
        ax.set_facecolor(BG);im=ax.imshow(value.T,origin='lower',extent=[0,24,0,12],cmap=cmap,vmin=lo,vmax=hi,aspect='equal');ax.set_xlim(2,22);ax.set_ylim(2,10)
        ax.add_patch(plt.Circle((6,6.045),1,color=SUB));ax.tick_params(colors=SUB);ax.set_ylabel('Y / m',color=SUB);ax.set_xlabel('X / m',color=SUB)
        cb=fig.colorbar(im,ax=ax,fraction=.025,pad=.02);cb.ax.tick_params(colors=SUB);cb.set_label(label,color=SUB);ax.set_anchor('C')
    fig.subplots_adjust(left=.04,right=.93,bottom=.08,top=.98,hspace=.27);fig.canvas.draw();result=Image.fromarray(np.asarray(fig.canvas.buffer_rgba())[:,:,:3]);plt.close(fig)
    if closing:
        return card('Inspect the saved fields','Open the Grasshopper example. Record a run. Move the frame slider.',result,footer='Demonstration case / compare finer grids and larger domains before using engineering results')
    return card('Follow the cylinder wake',f"MPS / iteration {entry['iteration']:04d} / simulation time {entry['time']:.2f} s",result,'Re = 100 / 161 × 81 × 4 lattice / periodic transverse faces / fixed color limits')

def frames():
    yield picture(data['frames'][0]),90
    for i,e in enumerate(data['frames']):
        im=picture(e)
        if i in (0,40,80):im.save(CAP/f'wake-{i:02d}.png')
        print(i,flush=True);yield im,10
    yield picture(data['frames'][-1],closing=True),150

if __name__=='__main__':
    path=OUT/'hawa-cylinder-wake.mp4';write_video(path,frames())
    (OUT/'wake-provenance.json').write_text(json.dumps({'video':path.name,'manifest':str(SOURCE/'manifest.json'),'sha256':hashlib.sha256((SOURCE/'manifest.json').read_bytes()).hexdigest(),'iterations':8000,'frames':81,'render':'scripts/make_wake_demo.py','audio':False,'revision':'visuals-on-all-cards'},indent=2))
