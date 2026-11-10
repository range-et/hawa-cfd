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
