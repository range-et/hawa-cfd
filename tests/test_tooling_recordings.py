"""Recording recipe contracts and preview ownership against host/encoder doubles."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]


def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


@pytest.mark.parametrize('name,steps,stride', [('record_vortex_demo',300,10),('record_cylinder_demo',8000,100),('record_motion_demo',1000,10)])
def test_recording_recipe_steps_initialization_and_progress(tmp_path,monkeypatch,capsys,name,steps,stride):
    m=load(name);seen=[]
    def record(session,n,every,folder,checkpoint):
        assert n==steps and every==stride and session.backend.device.type=='cpu'
        folder=Path(folder);folder.mkdir(parents=True)
        checkpoint(0);checkpoint(1);checkpoint(500)
        fields=session.fields()
        assert np.isfinite(fields['velocity']).all()
        if name=='record_cylinder_demo':
            assert fields['velocity'].shape==(3,161,81,4)
            assert np.max(np.abs(fields['velocity'][1]))>0
        seen.append((n,every,folder));return dict(manifest=str(folder/'manifest.json'))
    monkeypatch.setattr(m,'record',record);out=tmp_path/'recording'
    m.main(output=out,device='cpu')
    assert seen==[(steps,stride,out)]
    text=capsys.readouterr().out;assert '500' in text
    if name=='record_motion_demo':
        summary=json.loads((tmp_path/'cylinder-summary.json').read_text())
        assert summary['manifest']==str(out/'manifest.json')
        assert json.loads((tmp_path/'cylinder-loads.json').read_text())==[]


def test_boundary_transfer_script_retains_same_time_and_cpu_scope(tmp_path,monkeypatch):
    m=load('verify_boundary_transfer')
    monkeypatch.setattr(m.torch.backends.mps,'is_available',lambda:False)
    out=tmp_path/'transfer';monkeypatch.setattr(sys,'argv',['transfer','--output',str(out)])
    m.main()
    report=json.loads((out/'report.json').read_text())
    assert report['cuda_tested'] is False and set(report['devices'])=={'cpu'}
    record=report['devices']['cpu']
    assert record['max_velocity_difference_from_cpu']==0
    assert abs(record['parent']['time_seconds']-record['child']['time_seconds'])<1e-12


def test_curved_benchmark_grid_property_matches_cartesian_resolution(monkeypatch):
    m=load('benchmark_curved_walls');original=m.lt.Simulation.__init__;seen=[]
    def initialize(self,flow,*args,**kwargs):
        grid=flow.grid
        assert len(grid)==3 and tuple(grid[0].shape)==(4,4,4)
        assert grid[0][:,0,0].tolist()==[0,1,2,3] and grid[1][0,:,0].tolist()==[0,1,2,3]
        seen.append(True);original(self,flow,*args,**kwargs)
    monkeypatch.setattr(m.lt.Simulation,'__init__',initialize)
    result=m.run(4,.5)
    assert seen==[True] and result['expected_max']==pytest.approx(7.5e-6)


def test_rhino_preview_preserves_unowned_geometry_and_validates_document(tmp_path,monkeypatch):
    m=load('rhino_vortex')
    class Attributes:
        def __init__(self,owner=None):self.tags={} if owner is None else {'hawa.demo':owner}
        def GetUserString(self,key):return self.tags.get(key)
        def SetUserString(self,key,value):self.tags[key]=value
    class Collection(list):
        def Add(self,*values):self.append(values)
        def AddFace(self,*values):self.append(values)
    class Mesh:
        def __init__(self):self.Vertices=Collection();self.VertexColors=Collection();self.Faces=Collection();self.Normals=SimpleNamespace(ComputeNormals=lambda:None)
    class Point:
        def __init__(self,*values):self.values=values
        def __add__(self,other):return Point(*(a+b for a,b in zip(self.values,other.values)))
    class Objects(list):
        def __init__(self):super().__init__([SimpleNamespace(Id='user',Attributes=Attributes()),SimpleNamespace(Id='old-demo',Attributes=Attributes('taylor-green'))]);self.deleted=[];self.added=[]
        def Delete(self,id,quiet):self.deleted.append(id)
        def AddMesh(self,mesh,attrs):self.added.append(('mesh',mesh,attrs));return 'new-mesh'
        def AddLine(self,start,end,attrs):self.added.append(('line',start,end,attrs));return 'line-'+str(len(self.added))
    objects=Objects();layers=[];redraw=[]
    doc=SimpleNamespace(Objects=objects,Layers=SimpleNamespace(FindByFullPath=lambda name,unused:-1,Add=lambda layer:layers.append(layer) or 3),Views=SimpleNamespace(Redraw=lambda:redraw.append(True)))
    rhino=SimpleNamespace(RhinoApp=SimpleNamespace(Version='fixture'),RhinoDoc=SimpleNamespace(ActiveDoc=doc),Geometry=SimpleNamespace(Mesh=Mesh,Point3d=Point,Vector3d=Point),DocObjects=SimpleNamespace(Layer=lambda:SimpleNamespace(),ObjectAttributes=Attributes))
    drawing=SimpleNamespace(Color=SimpleNamespace(FromArgb=lambda *rgb:rgb))
    monkeypatch.setitem(sys.modules,'Rhino',rhino);monkeypatch.setitem(sys.modules,'System',SimpleNamespace(Drawing=drawing));monkeypatch.setitem(sys.modules,'System.Drawing',drawing)
    monkeypatch.setattr(m,'ROOT',tmp_path);monkeypatch.setattr(m,'HAWA_DEVICE','cpu',raising=False);monkeypatch.setattr(m,'HAWA_SIZE',16,raising=False);monkeypatch.setattr(m,'HAWA_STEPS',0,raising=False)
    m.main()
    assert objects.deleted==['old-demo'] and objects[0].Id=='user'
    mesh=objects.added[0][1]
    assert len(mesh.Vertices)==256 and len(mesh.Faces)==225 and len(mesh.VertexColors)==256
    assert mesh.Vertices[0]==(100.,0.,0.) and objects.added[0][2].LayerIndex==3
    assert layers[0].Name=='Hawa Feasibility' and redraw==[True]
    report=json.loads((tmp_path/'results/rhino-cpu/report.json').read_text())
    assert report['host']=='rhino-embedded' and report['rhino']=='fixture' and len(report['preview_object_ids'])==65
    rhino.RhinoDoc.ActiveDoc=None
    with pytest.raises(RuntimeError,match='No Rhino document'):m.create_preview()
