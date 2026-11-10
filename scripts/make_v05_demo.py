"""Build the local 0.5 review film. Actual captures; explicitly labelled older footage.

No upload or publication. Inspect decoded frames/contact sheets after encoding.
"""
from pathlib import Path
import json, subprocess, hashlib, shutil
from PIL import Image, ImageDraw, ImageFont, ImageOps
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'dist/videos-v05'
CAP=ROOT/'docs/captures'; W,H=1920,1080; FPS=24
C=json.loads((ROOT/'vendor/monad_system/colors.json').read_text())['Default_Colors']['General_UI_Colors']
BG=C['Background']['hex']; FG=C['Primary_Text']['hex']; SUB=C['Secondary_Text']['hex']; ACC='#71d7cb'
def font(n,bold=False):return ImageFont.truetype('/System/Library/Fonts/HelveticaNeue.ttc',n,index=10 if bold else 0)
def text(d,s,x,y,size,width,color=FG):
 lines=[]; line='';f=font(size)
 for word in s.split():
  test=(line+' '+word).strip()
  if d.textlength(test,font=f)>width and line:lines.append(line);line=word
  else:line=test
 if line:lines.append(line)
 for line in lines:d.text((x,y),line,font=f,fill=color);y+=size+12
 return y
scenes=[]
def scene(title,caption,source=None,crop=None,seconds=9,kind='image',note='Verified Rhino captures / 0.5',**kw):
 scenes.append(dict(title=title,caption=caption,source=source,crop=crop,seconds=seconds,kind=kind,note=note,**kw))
scene('Hawa 0.5','Set up flow in Rhino. Connect Grasshopper controls. Inspect the same result.','v05/gates-curved.png',crop=[260,210,2990,1630],seconds=7)
scene('A native Rhino workspace','Open Hawa. Dock the panel. Setup, Solve and View keep the case controls together.','v05/native-selected-view.png',crop=[2200,210,2990,1630])
scene('Select the bodies','Use closed Rhino meshes or solid Breps. Fit the domain, then edit its origin and size.','v05/native-selected-setup.png',crop=[260,210,2990,1630],seconds=10)
scene('Set the physical case','Enter viscosity, density and speed. Choose each domain-face boundary. Native flow follows the global X axis.','v05/native-selected-setup.png',crop=[2240,660,2990,1630],seconds=10)
scene('Run, pause, cancel, reset','Set cell size, target steps and backend. Run the embedded Python solver. This canopy capture shows 200 MPS steps.','v05/native-selected-solve.png',crop=[260,210,2990,1630],seconds=10)
scene('Choose the field view','Select speed or pressure. Set the slice axis and position. Use blue-green or spectrum colours and fixed limits.','v05/native-selected-view.png',crop=[2240,210,2990,1630],seconds=10)
scene('Share the case with Grasshopper','Hawa Linked Case connects the panel to GH. Direct sliders can update from either interface.','v05/native-selected-grasshopper.png',crop=[500,500,2650,1600],seconds=10)
scene('Keep one owner for each edit','Computed GH inputs stay read-only in the panel. One Linked Case owns the binding. Physical edits invalidate old results.',kind='diagram',diagram='sync',seconds=11,note='Shared-state contract / verified in Rhino')
scene('Save the model and definition','Save the .3dm and its bound .gh together. Reopening restores settings and stays idle. Missing bodies produce an error.','v05/native-docked-live-sync.png',crop=[260,210,2990,1630],seconds=10)
scene('Resolve curved stationary walls','Brep tessellation follows cell size and body scale. Enable interpolated stationary walls to use fractional wall-link distances.','v05/gates-curved.png',crop=[260,210,2990,1630],seconds=11)
scene('Clip the visible boundary','Supported slices now cut mixed cells at stored wall intersections. The old display discarded whole cells around the body.',kind='compare',seconds=11,note='Display correction / captured before and after')
scene('Read the wall colours correctly','Boundary colours are reconstructed for display. Raw probe samples stay unchanged. Plane Field and Grid Preview keep their existing masks.','v05/curved-slice-after.png',crop=[440,490,2140,1500],seconds=11)
scene('Three native starting points','21: linked block case. 22: selected canopy with GH controls. 23: curved sphere, operated from the Rhino panel.',kind='gallery',seconds=11,note='Editable examples / native-prototype folder')
scene('Find tools by their operation','The Hawa tab and icons group setup, solve and display tools. Hull construction stays in the example assembly.','v05/gates-toolbar.png',crop=[0,45,2850,360],seconds=8)
scene('Keep the wider GH toolbox','Use domain wireframes, 3D flow tubes, contours, isosurfaces and surface fields. Share one Field Snapshot across time-matched views.','v04/block-flow.png',seconds=10,note='Existing GH workflow / available in 0.5')
scene('Load airfoils from local files','Example 12 loads coordinates and polars. Generate four-digit NACA sections offline. Inspect the RC wing assembly.','v04/airfoil-card.png',seconds=9,note='Existing GH workflow / local data only')
scene('Search completed candidates','Example 10 varies a parametric hull. Hawa Search advances after each completed result. Pause or cancel at solver checkpoints.','v04/search-completed.png',seconds=10,note='Existing asynchronous GH search / available in 0.5')
scene('Explore prescribed motion','Examples 17–20 cover an oscillating cylinder, pitching foil, rotating paddle and cycle search. Body pose and fields share a capture time.',source='dist/videos-v04/hawa-moving-surfaces.mp4',kind='clip',seconds=11,start=8,note='Recorded 0.4 motion footage / retained in 0.5')
scene('Compare a refinement patch','Example 15 uses one fixed 2:1 patch. Check a uniform fine-grid reference before interpreting a result.','v04/refinement.png',seconds=8,note='Existing experimental GH refinement / available in 0.5')
scene('Record the evolving flow','Examples 13 and 16 save fields for playback. Keep colour limits fixed while you inspect the changing wake.',source='dist/videos-v04/hawa-cylinder-wake.mp4',kind='clip',seconds=11,start=12,note='Recorded 0.4 wake footage / 8,000 MPS steps')
scene('Open, change, repeat','Start with the annotated definitions. Keep the domain, fluid and comparison time controlled when you change geometry.',kind='catalog',seconds=12,note='21 supported GH definitions + native-only example 23')
scene('Recover after a failed close','Detached jobs stay in a shared cleanup queue. Failed close requests retry after GH closes. No native panel is required.',kind='diagram',diagram='cleanup',seconds=11,note='0.5 cleanup fix / commit e8d316e')
scene('Check the work in Rhino','148 Python tests and 33 state contracts passed. Live failure tests covered all six cleanup paths. Final jobs, sessions and workers: zero.',kind='checks',seconds=11,note='Local macOS CPU/MPS verification / November 8, 2026')
scene('Use the documented scope','Native setup covers stationary, single-fluid flow. GH provides the broader workflows. These short examples demonstrate controls and output.','v05/native-selected-view.png',crop=[260,210,2230,1600],seconds=10,note='Experimental solver / compare grids, domains and physical time')
scene('Start with an example','Open 21 for live sync, 22 for selected bodies, or 23 for curved walls. Read the build log and inspect the verification records.','v05/gates-curved.png',crop=[260,210,2230,1600],seconds=8,note='Hawa 0.5 / local review cut / GPL-3.0-only')

def paste_fit(im,source,box,crop=None):
 shot=Image.open(source).convert('RGB')
 if crop:shot=shot.crop(crop)
 x,y,w,h=box;shot=ImageOps.contain(shot,(w,h),Image.Resampling.LANCZOS);im.paste(shot,(x+(w-shot.width)//2,y+(h-shot.height)//2))
def draw_scene(s,i):
 im=Image.new('RGB',(W,H),BG);d=ImageDraw.Draw(im)
 d.text((64,45),'HAWA / BUILD LOG 005',font=font(22),fill=SUB)
 end=text(d,s['title'],64,104,58,1780)
 assert end<220,s['title']
 end=text(d,s['caption'],1380,285,32,470,SUB);assert end<940,s['title']
 d.text((64,1014),s['note'],font=font(21),fill=SUB)
 d.text((1760,1014),f'{i+1:02d} / {len(scenes):02d}',font=font(21),fill=SUB)
 box=(64,230,1252,728)
 if s['kind']=='image':paste_fit(im,CAP/s['source'],box,s['crop'])
 elif s['kind']=='compare':
  for j,(name,label) in enumerate([('curved-slice-before.png','Previous masking'),('curved-slice-after.png','Wall-linked clipping')]):
   paste_fit(im,CAP/'v05'/name,(64+640*j,310,612,560),[440,490,2140,1500]);d.text((64+640*j,260),label,font=font(28),fill=FG)
 elif s['kind']=='gallery':
  for j,(name,label) in enumerate([('native-docked-live-sync.png','21 / Linked block'),('native-selected-view.png','22 / Selected canopy'),('gates-curved.png','23 / Curved solid')]):
   paste_fit(im,CAP/'v05'/name,(64+j*423,330,400,460),[260,210,2230,1600]);text(d,label,64+j*423,825,27,400)
 elif s['kind']=='diagram':
  labels=[('Rhino panel','Direct controls'),('Shared case','Version + run + field time'),('Grasshopper','Sliders + computed inputs')] if s['diagram']=='sync' else [('GH closes','Detach the job IDs'),('Shared queue','Retain failed requests'),('Rhino Idle','Retry until acknowledged')]
  for j,(a,b) in enumerate(labels):
   x=64+j*424;d.rounded_rectangle((x,390,x+385,635),radius=12,outline=SUB,width=2);text(d,a,x+24,425,35,340);text(d,b,x+24,495,26,340,SUB)
   if j<2:d.line((x+388,510,x+420,510),fill=ACC,width=3);d.polygon([(x+420,510),(x+410,503),(x+410,517)],fill=ACC)
  text(d,'Physical edit → invalidate old field → run → publish matching result' if s['diagram']=='sync' else 'Close acknowledged → cancellation requested → verify worker exit',84,730,30,1190,ACC)
 elif s['kind']=='catalog':
  rows=[('01–08','Vortices, cavity, channel and block'),('10–12','Hull search, 3D views and local airfoils'),('13–16','Recording, curved walls, refinement and wake'),('17–20','Prescribed motion and cycle search'),('21–23','Native block, selected geometry and curved solid')]
  for j,(a,b) in enumerate(rows):
   y=300+j*115;d.text((90,y),a,font=font(40),fill=ACC);text(d,b,295,y+4,29,980)
 elif s['kind']=='checks':
  for j,(a,b) in enumerate([('148','Python tests passed'),('33','State contracts passed'),('6','Cleanup ownership paths checked'),('0','Jobs, sessions and workers after teardown')]):
   y=300+j*145;d.text((90,y),a,font=font(68),fill=ACC);text(d,b,310,y+20,30,950)
 return im

def run(args):subprocess.run(args,check=True)
def timestamp(t,sep='.'):
 h=int(t//3600);m=int(t%3600//60);s=t%60;return f'{h:02}:{m:02}:{s:06.3f}'.replace('.',sep)
if __name__ == '__main__':
 OUT.mkdir(parents=True,exist_ok=True)
 chapters=[];vtt=['WEBVTT',''];elapsed=0;parts=[]

 for i,s in enumerate(scenes):
  png=OUT/f'scene-{i+1:02}.png';draw_scene(s,i).save(png);part=OUT/f'part-{i+1:02}.mp4';parts.append(part)
  cmd=['ffmpeg','-y','-hide_banner','-loglevel','error','-loop','1','-framerate',str(FPS),'-i',str(png)]
  if s['kind']=='clip':
   cmd+=['-ss',str(s['start']),'-i',str(ROOT/s['source']),'-filter_complex','[1:v]scale=1252:704[clip];[0:v][clip]overlay=64:242:shortest=1[v]','-map','[v]']
  cmd+=['-t',str(s['seconds']),'-r',str(FPS),'-an','-c:v','libx264','-preset','fast','-threads','2','-crf','20','-pix_fmt','yuv420p',str(part)]
  run(cmd);chapters.append(dict(start_seconds=elapsed,**s));vtt.extend([f'{timestamp(elapsed)} --> {timestamp(elapsed+s["seconds"])}',s['title']+'. '+s['caption'],'']);elapsed+=s['seconds'];print(f'{i+1}/{len(scenes)} {s["title"]}',flush=True)
 listing=OUT/'concat.txt';listing.write_text('\n'.join("file '"+str(p)+"'" for p in parts)+'\n')
 video=OUT/'hawa-0.5-build-log.mp4';run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(listing),'-c','copy','-movflags','+faststart',str(video)])
 (OUT/'hawa-0.5-build-log.vtt').write_text('\n'.join(vtt))
 metadata=dict(title='Hawa 0.5 / Native workspace and live sync',duration_seconds=elapsed,audio=False,style='Pinned Monad tokens; captions; no added title bars',chapters=chapters,video_sha256=hashlib.sha256(video.read_bytes()).hexdigest(),sources={})
 for s in scenes:
  if s['source']:
   p=ROOT/s['source'] if s['kind']=='clip' else CAP/s['source'];metadata['sources'][str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
 (OUT/'provenance.json').write_text(json.dumps(metadata,indent=2)+'\n')
 (ROOT/'docs/media/v05/storyboard.json').write_text(json.dumps(metadata,indent=2)+'\n')
 # Decode the delivered MP4, including each scene's end and the last video frame.
 qa=OUT/'decoded';qa.mkdir(exist_ok=True)
 for i,s in enumerate(chapters):
  for label,t in [('middle',s['start_seconds']+s['seconds']/2),('end',s['start_seconds']+s['seconds']-0.15)]:
   run(['ffmpeg','-y','-v','error','-ss',str(t),'-i',str(video),'-frames:v','1',str(qa/f'{i+1:02}-{label}.jpg')])
 for page in range((len(scenes)+7)//8):
  sheet=Image.new('RGB',(1600,960),BG);d=ImageDraw.Draw(sheet)
  for j in range(8):
   n=page*8+j
   if n>=len(scenes):break
   p=qa/f'{n+1:02}-middle.jpg';paste_fit(sheet,p,((j%2)*800,(j//2)*240,800,220));d.text(((j%2)*800+10,(j//2)*240+220),f'{n+1:02} {scenes[n]["title"]}',font=font(15),fill=FG)
  sheet.save(OUT/f'contact-{page+1}.jpg')
 print(video,elapsed,flush=True)
