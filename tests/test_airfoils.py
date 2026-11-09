import numpy as np
import pytest
from hawa.airfoils import naca,read_airfoil,read_polar,operating_point,wing_analysis


def test_naca_symmetry_and_camber():
    xy=np.array(naca('0012')['coordinates']);np.testing.assert_allclose(xy[:,0],xy[::-1,0],atol=1e-12);np.testing.assert_allclose(xy[:,1],-xy[::-1,1],atol=1e-12)
    assert np.ptp(xy[:,1])==pytest.approx(.12,abs=.001)
    assert np.array(naca('2412')['coordinates'])[:,1].max()>xy[:,1].max()


def test_import_formats(tmp_path):
    p=tmp_path/'foil.dat';p.write_text('foil\n1 0\n.5 .1\n0 0\n.5 -.1\n1 0\n');a=read_airfoil(p)
    p.write_text('foil\n3 3\n0 0\n.5 .1\n1 0\n\n0 0\n.5 -.1\n1 0\n');b=read_airfoil(p)
    np.testing.assert_allclose(a['coordinates'],b['coordinates'])


def test_local_polar_no_extrapolation(tmp_path):
    p=tmp_path/'polar.csv';p.write_text('alpha,cl,cd,cm\n-2,-.2,.02,0\n0,0,.01,0\n2,.2,.02,0\n')
    polar=read_polar(p,100000,0);assert operating_point(polar,1)['cl']==pytest.approx(.1)
    with pytest.raises(ValueError):operating_point(polar,4)


def test_wing_symmetry_and_induced_drag():
    a=wing_analysis(2,.3,.3,4);b=wing_analysis(2,.3,.3,-4);zero=wing_analysis(2,.3,.3,0)
    assert zero['CL']==0 and zero['CDi']==0
    assert a['CL']==pytest.approx(-b['CL']);assert a['CDi']==pytest.approx(b['CDi'])
    assert a['CDi']>=a['CL']**2/(np.pi*a['aspect_ratio'])
    np.testing.assert_allclose(a['section_cl'],a['section_cl'][::-1],atol=1e-12)


def test_moment_coefficient_and_missing_moment(tmp_path):
    p=tmp_path/'polar.csv';p.write_text('alpha,cl,cd,cm\n0,0,.01,-.02\n2,.2,.02,-.04\n')
    assert operating_point(read_polar(p),1)['cm']==pytest.approx(-.03)
    p.write_text('alpha,cl,cd\n0,0,.01\n2,.2,.02\n')
    assert operating_point(read_polar(p),1)['cm'] is None


def test_wing_profile_drag_with_local_polar(tmp_path):
    p=tmp_path/'polar.csv';p.write_text('alpha,cl,cd\n-20,-2,.02\n0,0,.02\n20,2,.02\n')
    r=wing_analysis(2,.3,.15,4,polar=read_polar(p))
    assert r['CD_profile']==pytest.approx(.02,rel=.003)
    assert r['CD_total']==pytest.approx(r['CDi']+r['CD_profile'])
