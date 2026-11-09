"""Render actual recorded flow, body poses and loads in the Monad theme."""
import json,subprocess
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1];source=ROOT/'results/motion/cylinder-recording-refill'
manifest=json.loads((source/'manifest.json').read_text());history=json.loads((ROOT/'results/motion/cylinder-loads.json').read_text())
colors=json.loads((ROOT/'vendor/monad_system/colors.json').read_text())['Default_Colors']['General_UI_Colors']
bg=colors['Background']['hex'];fg=colors['Primary_Text']['hex'];sub=colors['Secondary_Text']['hex']
cmap=LinearSegmentedColormap.from_list('hawa',['#08306b','#00a0b4','#96eb8c'])
font='/System/Library/Fonts/HelveticaNeue.ttc';titlefont=ImageFont.truetype(font,48,index=10);bodyfont=ImageFont.truetype(font,25)
out=ROOT/'dist/videos-v04/hawa-moving-surfaces.mp4';out.parent.mkdir(parents=True,exist_ok=True)
cap=ROOT/'docs/captures/motion';cap.mkdir(parents=True,exist_ok=True)
times=np.array([h['time'] for h in history]);forces=np.array([h['loads'][0]['force'] for h in history]);dx=manifest['case']['dx']
proc=subprocess.Popen(['ffmpeg','-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s','1920x1080','-r','30','-i','-','-an','-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(out)],stdin=subprocess.PIPE)
try:
 for i,entry in enumerate(manifest['frames']):
  with np.load(source/entry['file']) as a:u=a['velocity'];solid=a['solid'];meta=json.loads(str(a['metadata']))
  fig=plt.figure(figsize=(17.4,7.6),dpi=100,facecolor=bg)
  ax=fig.add_subplot(121,projection='3d',facecolor=bg);ax.set_axis_off();ax.view_init(32,-66)
  nx,ny,nz=solid.shape;X,Y=np.meshgrid(np.arange(nx)*dx,np.arange(ny)*dx,indexing='ij');speed=np.linalg.norm(u,axis=0)
  face=cmap(np.clip(speed[:,:,8]/1.8,0,1));face[solid[:,:,8]]=[.12,.14,.16,1]
  ax.plot_surface(X,Y,np.full_like(X,2),facecolors=face,shade=False,rstride=1,cstride=1,alpha=.88)
  for axis in range(3):
   sizes=np.array([nx-1,ny-1,nz-1])*dx
   for a in (0,sizes[(axis+1)%3]):
    for b in (0,sizes[(axis+2)%3]):
     p=np.zeros((2,3));p[1,axis]=sizes[axis];p[:,(axis+1)%3]=a;p[:,(axis+2)%3]=b;ax.plot(*p.T,color=sub,lw=.7,alpha=.7)
  center=np.array(meta['motion']['poses'][0]['pivot']);theta=np.linspace(0,2*np.pi,65)
  for z in (-1,1):ax.plot(center[0]+.5*np.cos(theta),center[1]+.5*np.sin(theta),np.full_like(theta,center[2]+z),color=fg,lw=2)
  for t in np.linspace(0,2*np.pi,9):ax.plot([center[0]+.5*np.cos(t)]*2,[center[1]+.5*np.sin(t)]*2,[center[2]-1,center[2]+1],color=fg,lw=1)
  a,b,c=np.meshgrid(np.arange(2,nx-2,4),np.arange(2,ny-2,4),np.array([5,11]),indexing='ij');valid=~solid[a,b,c];v=u[:,a[valid],b[valid],c[valid]]
  ax.quiver(a[valid]*dx,b[valid]*dx,c[valid]*dx,*v,length=.45,color='#65dfb1',linewidth=.6)
  ax.set_box_aspect((8,6,4));ax.set_title('Prescribed cylinder motion / actual velocity field',color=fg,fontsize=17)
  bx=fig.add_subplot(222,facecolor=bg);bx.imshow(speed[:,:,8].T,origin='lower',extent=[0,8,0,6],cmap=cmap,vmin=0,vmax=1.8,aspect='equal');bx.contour(X,Y,solid[:,:,8].astype(float),levels=[.5],colors=fg,linewidths=1.2);bx.set_title('Speed plane / fixed range 0–1.8 m/s',color=fg,fontsize=15)
  cx=fig.add_subplot(224,facecolor=bg);mask=times<=entry['time']+1e-10
  for axis,label,color in [(0,'Fx','#65dfb1'),(1,'Fy','#00a0b4')]:cx.plot(times[mask],forces[mask,axis],label=label,color=color,lw=1.3)
  cx.set_xlim(0,times[-1]);lo=forces[:,:2].min();hi=forces[:,:2].max();cx.set_yscale('symlog',linthresh=10);cx.set_ylim(lo-2,hi+5);cx.axvline(entry['time'],color=sub,lw=.6);cx.set_xlabel('Simulation time / s',color=sub);cx.set_ylabel('Fluid force / N',color=sub);cx.legend(facecolor=bg,labelcolor=fg,loc='upper right');cx.set_title('Raw forces / startup and cell-transition transients',color=fg,fontsize=15)
  for plot in (bx,cx):
   plot.tick_params(colors=sub)
   for spine in plot.spines.values():spine.set_color(sub)
  fig.subplots_adjust(left=0,right=.97,bottom=.09,top=.93,hspace=.4,wspace=.22);fig.canvas.draw();picture=Image.fromarray(np.asarray(fig.canvas.buffer_rgba())[:,:,:3]);plt.close(fig)
  im=Image.new('RGB',(1920,1080),bg);draw=ImageDraw.Draw(im);draw.text((90,50),'Hawa / moving surfaces',font=titlefont,fill=fg);draw.text((90,125),f"MPS / step {entry['iteration']:04d} / simulation time {entry['time']:.2f} s / prescribed motion",font=bodyfont,fill=sub);im.paste(picture,(90,200));draw.text((90,1010),'Experimental uniform BGK / single phase / compare grids and completed cycles before using loads',font=bodyfont,fill=sub)
  if i in (0,50,100):im.save(cap/f'moving-cylinder-{i:03d}.png')
  count=60 if i in (0,100) else 8
  raw=im.tobytes()
  for _ in range(count):proc.stdin.write(raw)
  if i%10==0:print('rendered',i,flush=True)
finally:proc.stdin.close()
if proc.wait():raise RuntimeError('Video encoding failed')
print(out)
