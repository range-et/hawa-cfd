"""Render synthetic developer fixtures; never rewrite captures or claim visual QA."""
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys

import matplotlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import pytest

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def modules(monkeypatch,tmp_path):
    # Legacy deliverables use macOS fonts. Fixture rendering deliberately uses a
    # bundled font on all platforms, without changing the production font choice.
    original=ImageFont.truetype
    font_path=Path(matplotlib.get_data_path())/'fonts/ttf/DejaVuSans.ttf'
    monkeypatch.setattr(ImageFont,'truetype',lambda filename,size,*a,**kw:original(str(font_path),size))
    def load(name):
        spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
        module=importlib.util.module_from_spec(spec);monkeypatch.setitem(sys.modules,name,module);spec.loader.exec_module(module)
        if hasattr(module,'CAP'):monkeypatch.setattr(module,'CAP',tmp_path)
        return module
    return load


def fixture_recording(folder):
    folder.mkdir();grid=np.indices((8,8,8));u=np.stack([grid[0]/8,grid[1]/16,np.zeros((8,8,8))])
    np.savez_compressed(folder/'frame.npz',velocity=u,solid=np.zeros((8,8,8),bool))
    entry=dict(file='frame.npz',iteration=2,time=.5)
    (folder/'manifest.json').write_text(json.dumps(dict(frames=[entry])))
    return entry


def assert_image(image):
    assert image.mode=='RGB' and image.size==(1920,1080)
    pixels=np.asarray(image)
    assert pixels.min()!=pixels.max() and len(np.unique(pixels.reshape(-1,3),axis=0))>10


def test_v04_cards_field_frames_and_airfoil_use_fixture_sources(modules,tmp_path,monkeypatch):
    m=modules('make_v04_demo');source=tmp_path/'recording';entry=fixture_recording(source)
    monkeypatch.setattr(m,'SOURCE',source)
    assert_image(m.card('Title','Caption',Image.new('RGB',(20,10),'red')))
    assert_image(m.card('Title','Caption',None))
    assert_image(m.evolving(entry));assert_image(m.card('Airfoil','Coordinates',m.airfoil_picture()))
    for name in ('block-flow.png','search-completed.png','sphere-pressure.png','refinement.png'):
        Image.new('RGB',(30,20),'red').save(tmp_path/name)
    frames=list(m.frames())
    assert len(frames)==8 and [count for _,count in frames]==[90,180,12,180,150,150,120,120]
    assert (tmp_path/'vortex-frame-00.png').is_file()


@pytest.mark.parametrize('failed',[False,True])
def test_video_writer_preserves_frame_repetitions_and_encoder_failure(modules,tmp_path,monkeypatch,failed):
    m=modules('make_v04_demo');seen=[]
    class Sink(io.BytesIO):
        was_closed=False
        def close(self):self.was_closed=True
    sink=Sink()
    def popen(command,stdin):
        seen.append(command);return type('Process',(),{'stdin':sink,'wait':lambda self:int(failed)})()
    monkeypatch.setattr(m.subprocess,'Popen',popen)
    frame=Image.new('RGB',(1920,1080),'red');target=tmp_path/'out.mp4'
    if failed:
        with pytest.raises(RuntimeError,match='ffmpeg failed'):m.write_video(target,[(frame,2)])
    else:m.write_video(target,[(frame,2)])
    assert sink.was_closed and sink.getvalue()==frame.tobytes()*2
    assert seen[0][0]=='ffmpeg' and seen[0][-1]==str(target)
    assert seen[0][seen[0].index('-pix_fmt')+1]=='rgb24'


def test_wake_frames_read_declared_manifest_and_save_selected_frames(modules,tmp_path,monkeypatch):
    modules('make_v04_demo');m=modules('make_wake_demo');source=tmp_path/'wake';entry=fixture_recording(source)
    monkeypatch.setattr(m,'SOURCE',source)
    assert_image(m.picture(entry));assert_image(m.picture(entry,closing=True))
    frames=list(m.frames());assert [count for _,count in frames]==[90,10,150]
    assert (tmp_path/'wake-00.png').is_file()


def test_v05_layout_helpers_and_timestamps(modules,tmp_path,monkeypatch):
    m=modules('make_v05_demo')
    assert m.timestamp(3661.25)=='01:01:01.250'
    assert m.timestamp(61.25,',')=='00:01:01,250'
    target=Image.new('RGB',(100,100),'blue');source=tmp_path/'red.png';Image.new('RGB',(20,10),'red').save(source)
    m.paste_fit(target,source,(10,20,40,40))
    assert target.getpixel((10,30))==(255,0,0) and target.getpixel((9,30))==(0,0,255)
    draw=ImageDraw.Draw(target);assert m.text(draw,'one two three four',0,0,10,25)>22
    previous=len(m.scenes);m.scene('fixture','caption',kind='catalog',seconds=1)
    assert m.scenes[-1]['seconds']==1 and len(m.scenes)==previous+1
    observed=[];monkeypatch.setattr(m.subprocess,'run',lambda args,check:observed.append((args,check)))
    m.run(['encoder','arg']);assert observed==[(['encoder','arg'],True)]
    def fail(*a,**kw):raise subprocess.CalledProcessError(1,a[0])
    monkeypatch.setattr(m.subprocess,'run',fail)
    with pytest.raises(subprocess.CalledProcessError):m.run(['encoder'])


@pytest.mark.parametrize('kind', ['image','compare','gallery','diagram','catalog','checks','clip'])
def test_v05_each_declared_layout_produces_bounded_frame(modules,tmp_path,kind):
    m=modules('make_v05_demo');(tmp_path/'v05').mkdir()
    for name in ('curved-slice-before.png','curved-slice-after.png','native-docked-live-sync.png','native-selected-view.png','gates-curved.png'):
        Image.new('RGB',(2200,1700),'red').save(tmp_path/'v05'/name)
    scene=dict(title='Fixture',caption='Synthetic layout contract.',note='Not host evidence',kind=kind,source='v05/gates-curved.png',crop=None,diagram='sync')
    assert_image(m.draw_scene(scene,0))
    if kind=='diagram':scene['diagram']='cleanup';assert_image(m.draw_scene(scene,0))


def test_walkthrough_layout_wraps_text_and_preserves_source_bounds(modules,tmp_path):
    m=modules('make_walkthroughs')
    font=m.font(20,medium=True);canvas=Image.new('RGB',(100,100),'black')
    y=m.draw_text(ImageDraw.Draw(canvas),'one two three four five',(0,0),font,50,'white')
    assert y>font.size+12
    assert_image(m.frame(('Title','Caption',None,None,1)))
    Image.new('RGB',(200,100),'red').save(tmp_path/'fixture.png')
    assert_image(m.frame(('Title','Caption','fixture.png',(0,0,100,100),1)))


@pytest.mark.parametrize('failed',[False,True])
def test_motion_media_entrypoint_renders_fixture_and_checks_encoder(modules,tmp_path,monkeypatch,failed):
    # This tests media/provenance mechanics, not MPS or the caption's physics.
    source=tmp_path/'results/motion/cylinder-recording-refill';source.mkdir(parents=True)
    palette=tmp_path/'vendor/monad_system';palette.mkdir(parents=True)
    (palette/'colors.json').write_bytes((ROOT/'vendor/monad_system/colors.json').read_bytes())
    shape=(8,8,12);velocity=np.ones((3,)+shape);solid=np.zeros(shape,bool);solid[3:5,3:5,:]=True
    metadata=dict(motion=dict(poses=[dict(pivot=[1.,1.,1.])]))
    np.savez(source/'frame.npz',velocity=velocity,solid=solid,metadata=json.dumps(metadata))
    (source/'manifest.json').write_text(json.dumps(dict(case=dict(dx=.25),frames=[dict(file='frame.npz',time=1.,iteration=10)])))
    (source.parent/'cylinder-loads.json').write_text(json.dumps([dict(time=t,loads=[dict(force=[t,2*t,0])]) for t in (0.,1.)]))
    class Sink:
        count=0;closed=False
        def write(self,data):
            assert len(data)==1920*1080*3
            self.count+=1
        def close(self):self.closed=True
    sink=Sink();commands=[]
    def popen(command,**kw):
        commands.append(command)
        return type('Encoder',(),dict(stdin=sink,wait=lambda self:int(failed)))()
    monkeypatch.setattr(subprocess,'Popen',popen)
    script=ROOT/'scripts/make_motion_demo.py'
    scope={'__name__':'__main__','__file__':str(script)}
    original_resolve=Path.resolve
    monkeypatch.setattr(Path,'resolve',lambda path,*a,**kw:tmp_path/'scripts'/script.name if path==script else original_resolve(path,*a,**kw))
    if failed:
        with pytest.raises(RuntimeError,match='encoding failed'):exec(compile(script.read_text(),str(script),'exec'),scope)
    else:exec(compile(script.read_text(),str(script),'exec'),scope)
    assert sink.closed and sink.count==60
    assert commands[0][-1]==str(tmp_path/'dist/videos-v04/hawa-moving-surfaces.mp4')
    with Image.open(tmp_path/'docs/captures/motion/moving-cylinder-000.png') as picture:
        assert_image(picture)


def test_v05_entrypoint_builds_chapters_hashes_captions_and_decode_manifest(modules,tmp_path,monkeypatch):
    import hashlib
    from test_tooling_entrypoints import execute_fixture
    m=modules('make_v05_demo')
    palette=tmp_path/'vendor/monad_system';palette.mkdir(parents=True)
    (palette/'colors.json').write_bytes((ROOT/'vendor/monad_system/colors.json').read_bytes())
    (tmp_path/'docs/media/v05').mkdir(parents=True)
    for scene in m.scenes:
        if not scene['source']:continue
        path=tmp_path/scene['source'] if scene['kind']=='clip' else tmp_path/'docs/captures'/scene['source']
        path.parent.mkdir(parents=True,exist_ok=True)
        if scene['kind']=='clip':path.write_bytes(b'fixture-source-video')
        else:Image.new('RGB',(3000,1700),'teal').save(path)
    Image.new('RGB',(3000,1700),'red').save(tmp_path/'docs/captures/v05/curved-slice-before.png')
    commands=[]
    def encode(args,**kwargs):
        assert kwargs==dict(check=True)
        commands.append(args);path=Path(args[-1])
        if path.suffix=='.jpg':Image.new('RGB',(160,90),'teal').save(path)
        else:path.write_bytes(b'fixture-encoded-video')
    monkeypatch.setattr(subprocess,'run',encode)
    execute_fixture('make_v05_demo',tmp_path)
    out=tmp_path/'dist/videos-v05'
    report=json.loads((out/'provenance.json').read_text())
    assert report['duration_seconds']==sum(s['seconds'] for s in m.scenes)
    assert len(report['chapters'])==len(m.scenes)
    assert report['video_sha256']==hashlib.sha256(b'fixture-encoded-video').hexdigest()
    for name,digest in report['sources'].items():assert digest==hashlib.sha256((tmp_path/name).read_bytes()).hexdigest()
    assert (out/'hawa-0.5-build-log.vtt').read_text().startswith('WEBVTT\n')
    assert len(list((out/'decoded').glob('*.jpg')))==2*len(m.scenes)
    assert len(list(out.glob('contact-*.jpg')))==(len(m.scenes)+7)//8
    assert len(commands)==3*len(m.scenes)+1
    assert json.loads((tmp_path/'docs/media/v05/storyboard.json').read_text())==report


def test_walkthrough_entrypoint_preserves_other_metadata_and_packages_licenses(modules,tmp_path,monkeypatch):
    import zipfile
    from test_tooling_entrypoints import execute_fixture
    m=modules('make_walkthroughs');video=m.VIDEOS[0]
    for name in ['vendor/monad_system/colors.json','vendor/monad_system/upstream.json','LICENSE','vendor/lettuce/LICENSE','vendor/monad_system/LICENSE']:
        path=tmp_path/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes((ROOT/name).read_bytes())
    (tmp_path/'site/assets').mkdir(parents=True)
    media=tmp_path/'docs/media';media.mkdir(parents=True)
    (media/'README.md').write_text('Fixture upload notes');(media/'description.txt').write_text('Fixture description')
    cap=tmp_path/'docs/captures';cap.mkdir()
    for scene in video['scenes']:
        if scene[2]:Image.new('RGB',(3000,1700),'teal').save(cap/scene[2])
    out=tmp_path/'dist/videos-monad';out.mkdir(parents=True)
    (out/'metadata.json').write_text(json.dumps([dict(slug='unselected',fixture=True),dict(slug=video['slug'],old=True)]))
    durations=[]
    def encode(args,**kw):
        assert kw==dict(check=True)
        durations.append(float(args[args.index('-t')+1]));Path(args[-1]).write_bytes(b'fixture-video')
    monkeypatch.setattr(subprocess,'run',encode)
    monkeypatch.setattr(subprocess,'check_output',lambda args:str(durations[-1]).encode())
    monkeypatch.setattr(sys,'argv',['walkthrough','--only',video['slug']])
    execute_fixture('make_walkthroughs',tmp_path)
    reports=json.loads((out/'metadata.json').read_text())
    assert reports[0]==dict(slug='unselected',fixture=True)
    assert len(reports)==2 and 'old' not in reports[1]
    assert reports[1]['duration_seconds']==sum(s[4] for s in video['scenes'])
    assert reports[1]['theme_commit']==m.REVISION
    assert len(reports[1]['captions'])==len(video['scenes'])
    assert (tmp_path/'site/assets/first-look-poster.jpg').exists()
    with zipfile.ZipFile(tmp_path/'dist/Hawa-YouTube-upload-kit.zip') as kit:
        assert {'licenses/Hawa-LICENSE','licenses/Lettuce-LICENSE','licenses/Monad-LICENSE','README.md','description.txt',video['slug']+'.mp4'}<=set(kit.namelist())
        assert kit.read('licenses/Hawa-LICENSE')==(ROOT/'LICENSE').read_bytes()


def test_v04_and_wake_entrypoints_hash_fixture_manifests(modules,tmp_path,monkeypatch):
    import hashlib
    from types import SimpleNamespace
    from test_tooling_entrypoints import execute_fixture
    for name in ['vendor/monad_system/colors.json','examples/grasshopper/data/naca0012.dat']:
        path=tmp_path/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes((ROOT/name).read_bytes())
    source=tmp_path/'results/v04';source.mkdir(parents=True)
    fixture_recording(source/'vortex-recording-v2');fixture_recording(source/'cylinder-recording-outflow')
    cap=tmp_path/'docs/captures/v04';cap.mkdir(parents=True)
    for name in ('block-flow.png','search-completed.png','sphere-pressure.png','refinement.png'):
        Image.new('RGB',(40,30),'teal').save(cap/name)
    sinks=[]
    class Sink:
        closed=False;frames=0
        def write(self,data):assert len(data)==1920*1080*3;self.frames+=1
        def close(self):self.closed=True
    def encoder(command,**kwargs):
        sink=Sink();sinks.append(sink);Path(command[-1]).write_bytes(b'fixture-video')
        return SimpleNamespace(stdin=sink,wait=lambda:0)
    monkeypatch.setattr(subprocess,'Popen',encoder)
    scope=execute_fixture('make_v04_demo',tmp_path)
    monkeypatch.setitem(sys.modules,'make_v04_demo',SimpleNamespace(**scope))
    execute_fixture('make_wake_demo',tmp_path)
    out=tmp_path/'dist/videos-v04'
    a=json.loads((out/'provenance.json').read_text());b=json.loads((out/'wake-provenance.json').read_text())
    assert a['source_sha256']==hashlib.sha256((source/'vortex-recording-v2/manifest.json').read_bytes()).hexdigest()
    assert b['sha256']==hashlib.sha256((source/'cylinder-recording-outflow/manifest.json').read_bytes()).hexdigest()
    assert a['audio'] is b['audio'] is False
    assert len(sinks)==2 and all(s.closed and s.frames>0 for s in sinks)
