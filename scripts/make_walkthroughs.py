"""Render captioned videos with the pinned Monad palette.

The videos use actual Rhino screenshots. Titles have no added bars or rules.
Requires macOS Helvetica Neue and Menlo, Pillow, ffmpeg, and ffprobe.
"""
from pathlib import Path
import json
import argparse
import subprocess
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'dist/videos-monad'
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
            ('Select the device', 'Choose a backend in the Grasshopper definition.', None, None, 8),
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

VIDEOS.append(dict(slug='hawa-hull-galapagos', version='v0.3.0',
    title='Hawa: parametric hull search with Galapagos and MPS', scenes=[
        ('Hawa', 'Parametric hull search in Grasshopper.', None, None, 5),
        ('Open the assembly', 'Open example 09. All geometry, controls, solver nodes, and Galapagos links are in the definition.', '12-hull-assembly.jpg', (160,480,2940,1600), 9),
        ('Change the hull', 'Bow: 0.8. Stern: 0.8. Beam / draft: 2. The closed mesh volume stays at 6 m³.', 'hull-variant-1.jpg', (360,220,1540,780), 7),
        ('Make the ends fuller', 'Bow: 0.4. Stern: 0.4. Beam / draft: 3.', 'hull-variant-2.jpg', (360,220,1540,780), 6),
        ('Make the ends finer', 'Bow: 1.6. Stern: 1.6. Beam / draft: 1.', 'hull-variant-3.jpg', (360,220,1540,780), 6),
        ('Keep the test fixed', 'Use the same tank, fluid, grid, and iteration count for every candidate. Enable evaluation.', '12-hull-assembly.jpg', (1100,480,2500,1480), 9),
        ('Minimize the fitness', 'Galapagos controls the three shape sliders. Fitness comes from the completed CFD run.', '08-hull-galapagos-options.jpg', None, 9),
        ('Run the search', 'This two-minute MPS search completed one population of ten genomes.', '09-hull-galapagos-search.jpg', None, 10),
        ('Restore a candidate', 'Select a genome. Press Reinstate. Hawa runs the selected hull again.', '09-hull-galapagos-search.jpg', (880,630,1380,1150), 8),
        ('Inspect the selected hull', 'Bow: 0.896. Stern: 1.461. Beam / draft: 2.586. Mesh volume: 6 m³.', 'hull-variant-4.jpg', (360,220,1540,780), 8),
        ('View the completed run', 'MPS completed 200 iterations. The force average uses the final 20 iterations.', '13-hull-mps-completed.jpg', (900,400,2610,1660), 9),
        ('Inspect the flow', 'The speed slice and streamlines show the completed field around the submerged hull.', '10-hull-best-flow.jpg', (260,260,1800,1020), 10),
        ('Read the result', 'Starting fitness: 3.964145. Selected fitness: 3.895586. Reinstating the selected hull reproduced its score.', None, None, 9),
        ('Check the limits', 'The coarse grid changes the voxel volume. This short search verifies the assembly. It does not establish a real-boat resistance improvement.', None, None, 10),
        ('Single phase flow', 'The hull is fully submerged in a viscous demonstration fluid. The model excludes waves, buoyancy, and boat motion.', None, None, 9),
        ('Hawa', 'Open example 09. Change the shape. Evaluate. Search with Galapagos.', None, None, 7),
    ]))

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

def frame(scene, version="v0.2.0"):
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
    draw.text((1720, 1040), version, font=font(18, mono=True), fill=DISABLED)
    return result

if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    parser = argparse.ArgumentParser()
    parser.add_argument('--only', choices=[v['slug'] for v in VIDEOS])
    args = parser.parse_args()
    if args.only:
        VIDEOS = [v for v in VIDEOS if v['slug'] == args.only]
    metadata_path = OUT / "metadata.json"
    selected = {v["slug"] for v in VIDEOS}
    metadata = [m for m in json.loads(metadata_path.read_text()) if m["slug"] not in selected] if metadata_path.exists() else []
    for video in VIDEOS:
        folder = OUT / video['slug']
        folder.mkdir(exist_ok=True)
        concat, chapters, elapsed = [], [], 0
        for number, scene in enumerate(video['scenes'], 1):
            path = folder / f'{number:02}.png'
            frame(scene, video.get("version", "v0.2.0")).save(path)
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
        name = {'hawa-first-look':'first-look-poster.jpg','hawa-block-workflow':'block-workflow-poster.jpg','hawa-hull-galapagos':'hull-workflow-poster.jpg'}[slug]
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
