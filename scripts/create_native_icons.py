"""Original Hawa native UI glyphs, rasterized from simple vector primitives."""
from pathlib import Path
from PIL import Image, ImageDraw
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'plugin/Hawa.Rhino/Assets'
OUT.mkdir(exist_ok=True)
glyphs = {
 'hawa': [[(5,6),(5,18)],[(19,6),(19,18)],[(5,12),(8,8),(12,12),(16,16),(19,12)]],
 'run': [[(8,5),(19,12),(8,19),(8,5)]],
 'pause': [[(8,5),(8,19)],[(16,5),(16,19)]],
 'cancel': [[(6,6),(18,6),(18,18),(6,18),(6,6)]],
 'reset': [[(19,9),(16,5),(8,5),(4,10),(5,17),(11,20),(18,17)],[(19,4),(19,10),(13,10)]],
 'geometry': [[(5,8),(12,4),(20,8),(20,17),(12,21),(5,17),(5,8),(12,12),(20,8)],[(12,12),(12,21)]],
 'domain': [[(4,6),(20,6),(20,19),(4,19),(4,6)],[(9,6),(9,19)],[(15,6),(15,19)],[(4,12),(20,12)]],
 'field': [[(4,7),(9,5),(15,9),(20,7)],[(4,12),(9,10),(15,14),(20,12)],[(4,17),(9,15),(15,19),(20,17)]],
 'apply': [[(4,12),(10,18),(20,5)]],
 'fit': [[(4,9),(4,4),(9,4)],[(15,4),(20,4),(20,9)],[(20,15),(20,20),(15,20)],[(9,20),(4,20),(4,15)]],
 'link': [[(10,5),(6,5),(3,9),(3,12),(7,16),(11,16)],[(14,8),(18,8),(21,12),(21,15),(17,19),(13,19)],[(8,12),(16,12)]],
}
for name, paths in glyphs.items():
 im=Image.new('RGBA',(192,192)); d=ImageDraw.Draw(im)
 d.rounded_rectangle((1,1,191,191),radius=40,fill='#163142')
 for path in paths:
  pts=[(x*8,y*8) for x,y in path];d.line(pts,fill='#9aeeea',width=14,joint='curve')
  for x,y in pts:d.ellipse((x-7,y-7,x+7,y+7),fill='#9aeeea')
 im.resize((24,24),Image.Resampling.LANCZOS).save(OUT/(name+'.png'))
 svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><rect width="24" height="24" rx="5" fill="#163142"/>'
 for path in paths:svg+='<polyline points="'+' '.join(f'{x},{y}' for x,y in path)+'" fill="none" stroke="#9aeeea" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"/>'
 (OUT/(name+'.svg')).write_text(svg+'</svg>\n')
 if name=='hawa':im.resize((64,64),Image.Resampling.LANCZOS).save(OUT/'hawa.ico',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64)])
print(f'Created {len(glyphs)} native glyphs plus panel icon')
