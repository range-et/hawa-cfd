"""Render real recorded fields with Monad captions; no generated flow footage."""
from pathlib import Path
import json
import subprocess
import hashlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap,Normalize
from PIL import Image,ImageDraw,ImageFont,ImageOps

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'dist/videos-v04'
CAP=ROOT/'docs/captures/v04'
SOURCE=ROOT/'results/v04/vortex-recording-v2'
UI=json.loads((ROOT/'vendor/monad_system/colors.json').read_text())['Default_Colors']['General_UI_Colors']
BG=UI['Background']['hex'];FG=UI['Primary_Text']['hex'];SUB=UI['Secondary_Text']['hex']
FONT='/System/Library/Fonts/HelveticaNeue.ttc'
CMAP=LinearSegmentedColormap.from_list('hawa',['#08306b','#00a0b4','#96eb8c'])

def card(title,caption,picture,footer='Hawa 0.4 / development preview'):
    TITLE=ImageFont.truetype(FONT,54,index=10);BODY=ImageFont.truetype(FONT,28);SMALL=ImageFont.truetype(FONT,22)
    im=Image.new('RGB',(1920,1080),BG);d=ImageDraw.Draw(im)
    d.text((90,50),title,font=TITLE,fill=FG)
    d.text((90,125),caption,font=BODY,fill=SUB)
    if picture is not None:
        fitted=ImageOps.contain(picture.convert('RGB'),(1740,770),Image.Resampling.LANCZOS)
        im.paste(fitted,((1920-fitted.width)//2,200+(770-fitted.height)//2))
    d.text((90,1015),footer,font=SMALL,fill=SUB)
    return im

def evolving(entry):
    with np.load(SOURCE/entry['file'],allow_pickle=False) as data:
        u=data['velocity'];speed=np.linalg.norm(u,axis=0)
    n=speed.shape[0];x,y=np.meshgrid(np.arange(n),np.arange(n),indexing='ij');k=n//2
    fig=plt.figure(figsize=(16,7),dpi=110,facecolor=BG)
    ax=fig.add_subplot(121,projection='3d',facecolor=BG);ax.set_axis_off();ax.view_init(27,-52)
    for a in range(3):
        for b in (0,n-1):
            for c in (0,n-1):
                p=np.zeros((2,3));p[1,a]=n-1;p[:,(a+1)%3]=b;p[:,(a+2)%3]=c
                ax.plot(*p.T,color=SUB,linewidth=.7,alpha=.6)
    ax.plot_surface(x,y,np.full_like(x,k),facecolors=CMAP(speed[:,:,k]),shade=False,rstride=1,cstride=1,alpha=.8)
    gx,gy,gz=np.meshgrid(np.arange(2,n-2,4),np.arange(2,n-2,4),np.arange(2,n-2,5),indexing='ij')
    v=u[:,gx,gy,gz];ax.quiver(gx,gy,gz,*v,length=3,normalize=False,color='#65dfb1',linewidth=.8)
    ax.set_box_aspect((1,1,1));ax.set_title('3D velocity and speed plane',color=FG,pad=0,fontsize=17)
    bx=fig.add_subplot(122,facecolor=BG)
    picture=bx.imshow(speed[:,:,k].T,origin='lower',cmap=CMAP,vmin=0,vmax=1)
    bx.contour(speed[:,:,k].T,levels=[.2,.4,.6,.8],colors=SUB,linewidths=.55)
    bx.set_title('Speed contours / fixed range',color=FG,fontsize=17)
    bx.set_xlabel('Lattice X',color=SUB);bx.set_ylabel('Lattice Y',color=SUB);bx.tick_params(colors=SUB)
    cb=fig.colorbar(picture,ax=bx,shrink=.78);cb.ax.tick_params(colors=SUB);cb.set_label('Speed / reference units',color=SUB)
    fig.subplots_adjust(left=.01,right=.95,bottom=.1,top=.92,wspace=.03)
    fig.canvas.draw();im=Image.fromarray(np.asarray(fig.canvas.buffer_rgba())[:,:,:3]);plt.close(fig)
    return card('Record the evolving flow',f"Taylor–Green vortex / MPS / iteration {entry['iteration']:03d} / simulation time {entry['time']:.3f}",im,'31 saved fields / 24 × 24 × 24 sites / frames held at fixed playback intervals')

def write_video(path,frames):
    command=['ffmpeg','-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s','1920x1080','-r','30','-i','-','-an','-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p','-movflags','+faststart',str(path)]
    proc=subprocess.Popen(command,stdin=subprocess.PIPE)
    try:
        for im,count in frames:
            raw=im.tobytes()
            for _ in range(count):proc.stdin.write(raw)
    finally:proc.stdin.close()
    if proc.wait():raise RuntimeError('ffmpeg failed')

def airfoil_picture():
    path=ROOT/'examples/grasshopper/data/naca0012.dat'
    xy=np.loadtxt(path,skiprows=1)
    fig,ax=plt.subplots(figsize=(16,6),dpi=110,facecolor=BG)
    ax.set_facecolor(BG)
    ax.fill(xy[:,0],xy[:,1],color='#00a0b4',alpha=.25)
    ax.plot(xy[:,0],xy[:,1],color='#96eb8c',linewidth=3)
    ax.set_aspect('equal');ax.set_xlim(-.05,1.05);ax.set_ylim(-.18,.18)
    ax.set_xlabel('x / chord',color=SUB,fontsize=17);ax.set_ylabel('y / chord',color=SUB,fontsize=17)
    ax.tick_params(colors=SUB);ax.grid(alpha=.15,color=SUB)
    for spine in ax.spines.values():spine.set_color(SUB)
    ax.set_title('NACA 0012 / supplied local coordinate file',color=FG,fontsize=22,pad=20)
    fig.tight_layout(pad=2);fig.canvas.draw()
    result=Image.fromarray(np.asarray(fig.canvas.buffer_rgba())[:,:,:3]);plt.close(fig)
    return result

def frames():
    DATA=json.loads((SOURCE/'manifest.json').read_text())
    yield card('Hawa / flow tools','Open the definition. Run the case. Inspect the fields.',Image.open(CAP/'block-flow.png')),90
    yield card('Inspect the domain in Rhino','3D flow tubes, a domain wireframe, and a blue-green speed plane.',Image.open(CAP/'block-flow.png')),180
    for i,entry in enumerate(DATA['frames']):
        im=evolving(entry)
        if i in (0,15,30):im.save(CAP/f'vortex-frame-{i:02d}.png')
        print('render frame',i,flush=True)
        yield im,12
    yield card('Search after each completed result','Five hull candidates completed after a pause and resume.',Image.open(CAP/'search-completed.png')),180
    yield card('Inspect pressure around a sphere','Offset Cp samples and 3D flow tubes.',Image.open(CAP/'sphere-pressure.png')),150
    yield card('Inspect a fixed refinement patch','Two coupled grids return separate field frames.',Image.open(CAP/'refinement.png')),150
    yield card('Use local airfoil files','Import coordinates and polars. Keep the source and operating conditions.',airfoil_picture()),120
    yield card('Check the model limits','Experimental refinement. Single-phase flow. Validate each case.',Image.open(CAP/'refinement.png')),120

if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True);CAP.mkdir(parents=True,exist_ok=True)
    output=OUT/'hawa-flow-tools.mp4';write_video(output,frames())
    (OUT/'provenance.json').write_text(json.dumps({'video':output.name,'source_manifest':str(SOURCE/'manifest.json'),'source_sha256':hashlib.sha256((SOURCE/'manifest.json').read_bytes()).hexdigest(),'frames':31,'device':'mps','rhino_captures':['block-flow.png','search-completed.png','sphere-pressure.png','refinement.png'],'render':'scripts/make_v04_demo.py','audio':False,'airfoil_coordinates':'examples/grasshopper/data/naca0012.dat','revision':'visuals-on-all-cards'},indent=2))
    print(output)
