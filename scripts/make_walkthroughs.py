"""Render captioned videos with the pinned Monad palette.

The videos use actual Rhino screenshots. Titles have no added bars or rules.
Requires macOS Helvetica Neue and Menlo, Pillow, ffmpeg, and ffprobe.
"""
from pathlib import Path
import json
import subprocess
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'dist/videos-monad'
OUT.mkdir(parents=True, exist_ok=True)
CAP = ROOT / 'docs/captures'
PALETTE = json.loads((ROOT / 'vendor/monad_system/colors.json').read_text())
UI = PALETTE['Default_Colors']['General_UI_Colors']
BG = UI['Background']['hex']
PRIMARY = UI['Primary_Text']['hex']
SECONDARY = UI['Secondary_Text']['hex']
DISABLED = UI['Disabled_Text']['hex']
HELVETICA = '/System/Library/Fonts/HelveticaNeue.ttc'
MENLO = '/System/Library/Fonts/Menlo.ttc'
REVISION = json.loads((ROOT / 'vendor/monad_system/upstream.json').read_text())['commit']

VIDEOS = [
    dict(slug='hawa-first-look', title='Hawa: GPU flow simulation in Rhino and Grasshopper',
         scenes=[
            ('Hawa', 'GPU flow simulation in Rhino 8 and Grasshopper.', None, None, 5),
            ('Open the example', 'Open the supplied Grasshopper definition. Select a backend.', '01-hawa-toolbar.jpg', (210,670,2850,1680), 9),
            ('Select the backend', 'Auto checks the available devices. This Mac selected MPS.', '02-vortex-ready.jpg', (1080,715,1980,1660), 9),
            ('Run the solver', 'The vortex completed 200 iterations inside Rhino.', '03-vortex-mps-completed.jpg', (1190,750,1980,1660), 9),
            ('View the speed field', 'The slice shows the computed velocity magnitude. Blue marks low values. Red marks high values.', '04-vortex-rhino-preview.jpg', (260,400,1550,1450), 10),
            ('Check device support', 'CPU and MPS checks passed. CUDA hardware checks remain open.', None, None, 8),
            ('Hawa', 'Download the plugin. Open an example. Change the inputs.', None, None, 7),
         ]),
    dict(slug='hawa-block-workflow', title='Hawa: 3D block flow in Grasshopper with MPS',
         scenes=[
            ('Hawa', 'Three-dimensional flow around a block.', None, None, 5),
            ('Define the case', 'Connect the domain, geometry, physics, and boundaries to Case.', '05-block-ready.jpg', (210,670,2850,1680), 10),
            ('Set the length units', 'Use meters. Set the cell size to 0.5 meters.', '05-block-ready.jpg', (210,715,1270,1200), 9),
            ('Run 300 iterations', 'The case completed 300 iterations on MPS. The grid contains 33 × 17 × 17 sites.', '06-block-mps-completed.jpg', (1510,760,2250,1680), 10),
            ('View the flow field', 'The slice excludes solid cells. Each streamline follows one field snapshot.', '07-block-rhino-preview.jpg', (260,450,1550,1300), 10),
            ('Pause or reset', 'Set Run to false to pause. Toggle Reset to clear the state.', '06-block-mps-completed.jpg', (1580,990,1880,1200), 9),
            ('Check the physical case', 'The demonstration viscosity is 0.1 m²/s. Atmospheric validation remains open.', None, None, 8),
            ('Hawa', 'Open the block example. Change its controls. Inspect the results.', None, None, 7),
         ]),
]

def font(size, medium=False, mono=False):
    return ImageFont.truetype(MENLO if mono else HELVETICA, size, index=0 if mono else 10 if medium else 0)

def draw_text(draw, text, xy, face, width, color, spacing=12):
    words = text.split()
    wrapped, line = [], ''
    for word in words:
        candidate = (line + ' ' + word).strip()
        if draw.textlength(candidate, font=face) > width and line:
            wrapped.append(line)
            line = word
        else:
            line = candidate
    if line:
        wrapped.append(line)
    x, y = xy
    for line in wrapped:
        draw.text((x, y), line, font=face, fill=color)
        y += face.size + spacing
    return y

def frame(scene):
    title, caption, source, crop, _ = scene
    result = Image.new('RGB', (1920, 1080), BG)
    draw = ImageDraw.Draw(result)
    if source:
        shot = Image.open(CAP / source).convert('RGB')
        if crop:
            shot = shot.crop(crop)
        shot = ImageOps.contain(shot, (1256, 820), Image.Resampling.LANCZOS)
        x, y = 64 + (1256 - shot.width) // 2, 64 + (820 - shot.height) // 2
        result.paste(shot, (x, y))
        bottom = draw_text(draw, title, (1384, 252), font(48, medium=True), 472, PRIMARY, 8)
        draw_text(draw, caption, (1384, bottom + 32), font(30), 472, SECONDARY, 13)
        draw.text((64, 984), 'Hawa', font=font(28, medium=True), fill=PRIMARY)
        draw.text((1384, 984), 'Rhino 8 / MPS', font=font(20), fill=SECONDARY)
    else:
        size = 224 if title == 'Hawa' else 108
        bottom = draw_text(draw, title, (64, 216), font(size, medium=True), 1760, PRIMARY, 8)
        draw_text(draw, caption, (72, bottom + 56), font(48), 1500, SECONDARY, 16)
        draw.text((72, 972), 'range-et.github.io/hawa-cfd', font=font(25, mono=True), fill=SECONDARY)
    draw.text((64, 1040), 'Screenshot walkthrough', font=font(18), fill=DISABLED)
    draw.text((1720, 1040), 'v0.2.0', font=font(18, mono=True), fill=DISABLED)
    return result

metadata = []
for video in VIDEOS:
    folder = OUT / video['slug']
    folder.mkdir(exist_ok=True)
    concat, chapters, elapsed = [], [], 0
    for number, scene in enumerate(video['scenes'], 1):
        path = folder / f'{number:02}.png'
        frame(scene).save(path)
        concat.extend([f"file '{path}'", f'duration {scene[4]}'])
        chapters.append({'seconds': elapsed, 'title': scene[0]})
        elapsed += scene[4]
    concat.append(f"file '{path}'")
    listing = folder / 'frames.txt'
    listing.write_text('\n'.join(concat) + '\n')
    output = OUT / (video['slug'] + '.mp4')
    subprocess.run([
        'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
        '-f', 'concat', '-safe', '0', '-i', str(listing),
        '-t', str(elapsed), '-vf', 'fps=30,format=yuv420p',
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '20',
        '-movflags', '+faststart', '-an', str(output)
    ], check=True)
    actual = float(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=nw=1:nk=1', str(output)
    ]))
    assert abs(actual - elapsed) < .1
    metadata.append({
        'slug': video['slug'], 'title': video['title'],
        'duration_seconds': actual, 'chapters': chapters,
        'file': output.name, 'theme': 'Monad System', 'theme_commit': REVISION,
        'format': '1920x1080 H.264, captioned screenshots, no audio',
        'captions': [{'title': s[0], 'text': s[1]} for s in video['scenes']]
    })
    print(output, flush=True)
(OUT / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')

# Export the web posters and the files for the YouTube upload.
import zipfile
for video in VIDEOS:
    slug = video['slug']
    with Image.open(OUT / slug / '01.png') as thumbnail:
        thumbnail.resize((1280, 720), Image.Resampling.LANCZOS).save(
            OUT / (slug + '-thumbnail.jpg'), quality=95)
    scene = '04.png' if slug == 'hawa-first-look' else '05.png'
    name = 'first-look-poster.jpg' if slug == 'hawa-first-look' else 'block-workflow-poster.jpg'
    with Image.open(OUT / slug / scene) as poster:
        poster.resize((1280, 720), Image.Resampling.LANCZOS).save(
            ROOT / 'site/assets' / name, quality=92)
with zipfile.ZipFile(ROOT / 'dist/Hawa-YouTube-upload-kit.zip', 'w', zipfile.ZIP_DEFLATED) as kit:
    for path in sorted(OUT.glob('*.mp4')):
        kit.write(path, path.name)
    for path in sorted(OUT.glob('*-thumbnail.jpg')):
        kit.write(path, path.name)
    for path in sorted((ROOT / 'docs/media').glob('*.txt')):
        kit.write(path, path.name)
    kit.write(ROOT / 'docs/media/README.md', 'README.md')
    kit.write(ROOT / 'LICENSE', 'licenses/Hawa-LICENSE')
    kit.write(ROOT / 'vendor/lettuce/LICENSE', 'licenses/Lettuce-LICENSE')
    kit.write(ROOT / 'vendor/monad_system/LICENSE', 'licenses/Monad-LICENSE')
