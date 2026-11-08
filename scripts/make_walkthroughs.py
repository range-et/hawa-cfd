"""Create captioned, screenshot-based launch videos from verified UI captures.

No simulated motion or fabricated solver results. Requires Pillow and ffmpeg.
Video files and intermediate frames go into ignored dist/.
"""
from pathlib import Path
import json, subprocess, textwrap
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'dist/videos'
OUT.mkdir(parents=True, exist_ok=True)
CAP = ROOT / 'docs/captures'
FONTS = Path('/System/Library/Fonts/Supplemental')
REG = str(FONTS / 'Arial.ttf')
BOLD = str(FONTS / 'Arial Bold.ttf')
BG = '#102d37'
WHITE = '#f5f4ec'
TEAL = '#84dcd6'
MUTED = '#b5cccd'

VIDEOS = [
    dict(slug='hawa-first-look', title='Hawa: GPU CFD inside Rhino and Grasshopper | First Look',
         scenes=[
            ('Flow, inside Rhino.', 'Hawa / an embedded GPU lattice Boltzmann prototype', None, None, 5),
            ('A Grasshopper workflow you can open.', '15 Hawa components, distinct icons, and eight editable definition files.', '01-hawa-toolbar.jpg', None, 9),
            ('Choose a case. Choose a backend.', 'Start with the supplied Taylor–Green vortex. Auto selects an available device.', '02-vortex-ready.jpg', None, 9),
            ('200 iterations on the Apple GPU.', 'This run used PyTorch MPS inside Rhino’s Python 3.9 runtime.', '03-vortex-mps-completed.jpg', (1190,750,1980,1660), 9),
            ('See the field directly in Rhino.', 'This is the computed vortex speed slice. Colors use the displayed auto range.', '04-vortex-rhino-preview.jpg', (260,400,1550,1450), 9),
            ('One engine. Three device choices.', 'CPU and MPS tested here. CUDA selection is implemented; NVIDIA verification is pending.', None, None, 8),
            ('Open it. Run it. Tweak it.', 'Source, installation notes, and editable examples: range-et.github.io/hawa-cfd', None, None, 7),
         ]),
    dict(slug='hawa-block-workflow', title='Hawa: 3D Block Flow in Grasshopper | Embedded MPS Workflow',
         scenes=[
            ('Geometry to flow, in one definition.', 'Hawa / 3D block workflow in Rhino 8 + Grasshopper', None, None, 5),
            ('Build the physical case.', 'Domain → voxelized geometry + physics + face boundaries → case → solver.', '05-block-ready.jpg', None, 10),
            ('Set units and resolution explicitly.', 'The self-contained block example uses meters and a 0.5-meter lattice spacing.', '05-block-ready.jpg', (210,715,1270,1200), 9),
            ('Run the embedded solver on MPS.', 'The visible graph completed 300 iterations on a 33 × 17 × 17 grid.', '06-block-mps-completed.jpg', (1510,760,2250,1680), 9),
            ('Inspect the obstacle and its wake.', 'The speed slice excludes solid cells. Curves are instantaneous snapshot streamlines.', '07-block-rhino-preview.jpg', (260,450,1550,1300), 10),
            ('Edit the definition and experiment.', 'Run false pauses. Reset clears state. A false-to-true Run toggle resumes.', '06-block-mps-completed.jpg', (1510,760,2250,1680), 9),
            ('A working prototype, with stated limits.', 'Viscosity is 0.1 m²/s for this demonstration. This is not validated atmospheric CFD.', None, None, 8),
            ('Try the editable block example.', 'Download, documentation, and source: range-et.github.io/hawa-cfd', None, None, 7),
         ]),
]

def font(n, bold=False): return ImageFont.truetype(BOLD if bold else REG, n)
def lines(draw, text, at, f, width, fill, spacing=12):
    words=text.split(); parts=[]; line=''
    for word in words:
        new=(line+' '+word).strip()
        if draw.textlength(new,font=f)>width and line: parts.append(line);line=word
        else:line=new
    if line:parts.append(line)
    x,y=at
    for line in parts:draw.text((x,y),line,font=f,fill=fill);y+=f.size+spacing
    return y

def frame(scene, number, total):
    title, caption, source, crop, duration=scene
    im=Image.new('RGB',(1920,1080),BG);d=ImageDraw.Draw(im)
    d.text((70,32),'HAWA',font=font(29,True),fill=TEAL)
    d.text((1530,38),f'WALKTHROUGH  /  {number:02}—{total:02}',font=font(18),fill=MUTED)
    d.line((70,88,1850,88),fill='#35525b',width=1)
    if source:
        shot=Image.open(CAP/source).convert('RGB')
        if crop:shot=shot.crop(crop)
        shot.thumbnail((1780,720),Image.Resampling.LANCZOS)
        x=(1920-shot.width)//2;y=116+(720-shot.height)//2
        im.paste(shot,(x,y));d.rectangle((x-1,y-1,x+shot.width,y+shot.height),outline='#52767d',width=1)
        y=lines(d,title,(70,862),font(42,True),1780,WHITE)
        lines(d,caption,(70,y+8),font(27),1780,MUTED,8)
    else:
        d.line((70,290,200,290),fill=TEAL,width=5)
        y=lines(d,title,(70,340),font(88,True),1740,WHITE,14)
        lines(d,caption,(75,y+48),font(35),1580,MUTED,15)
    d.text((70,1030),'Screenshot-based walkthrough • actual Rhino 8 / Apple MPS runs • v0.2.0 prototype',font=font(19),fill=MUTED)
    d.text((1475,1030),'Hawa + Lettuce / MIT',font=font(19),fill=TEAL)
    return im

metadata=[]
for video in VIDEOS:
    folder=OUT/video['slug'];folder.mkdir(exist_ok=True)
    concat=[];t=0;chapters=[]
    for i,scene in enumerate(video['scenes'],1):
        p=folder/f'{i:02}.png';frame(scene,i,len(video['scenes'])).save(p)
        concat.extend([f"file '{p}'",f'duration {scene[4]}'])
        chapters.append({'seconds':t,'title':scene[0]});t+=scene[4]
    concat.append(f"file '{p}'")
    listing=folder/'frames.txt';listing.write_text('\n'.join(concat)+'\n')
    output=OUT/(video['slug']+'.mp4')
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(listing),'-vf','fps=30,format=yuv420p','-c:v','libx264','-preset','fast','-crf','20','-movflags','+faststart','-an',str(output)],check=True)
    record={k:v for k,v in video.items() if k!='scenes'};record.update(duration_seconds=t,chapters=chapters,file=output.name,format='1920x1080, captioned screenshot walkthrough, no audio')
    metadata.append(record)
    print(output,flush=True)
(OUT/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
