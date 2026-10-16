# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Headless thermal document consumers: SI fields, physical signs and refusals."""
import copy
import json
import numpy as np
import pytest
from simcase import Document, DocumentError, ThermalRunResult, examples, run
from simcase.cli import main
from simcase.thermal import _OwnedOutput


@pytest.mark.parametrize('mode',['complete','ordinary','foreign','replaced','known_replaced'])
def test_thermal_partial_failure_safe_cleanup_link_pins(tmp_path,monkeypatch,mode):
    """Exercise the handle-free file pin on every OS, including the Windows gate."""
    import simcase.thermal as thermal
    monkeypatch.setattr(thermal,'_pin_file',lambda path,stream:thermal._pin_file_link(path))
    out=tmp_path/'out';moved=tmp_path/'moved'
    owned=_OwnedOutput(out)
    try:
        owned.write('.incomplete',lambda f:f.write(b'incomplete'))
        owned.write('model.json',lambda f:f.write(b'original'))
        # No original stream is held open here. Both fixture operations must work.
        if mode=='replaced':
            out.rename(moved);out.mkdir();(out/'foreign').write_bytes(b'keep')
        if mode=='known_replaced':
            replacement=tmp_path/'replacement'
            replacement.write_bytes(b'keep')
            replacement.replace(out/'model.json')
        if mode=='foreign':(out/'foreign').write_bytes(b'keep')
        if mode=='complete':owned.finish()
        else:owned.cleanup()
    finally:
        owned.close()
    assert not list(tmp_path.glob('.simcase-pin-*'))
    if mode=='complete':
        assert (out/'model.json').read_bytes()==b'original'
        assert not (out/'.incomplete').exists()
    elif mode=='ordinary':assert not out.exists()
    elif mode=='replaced':
        assert (out/'foreign').read_bytes()==b'keep'
        assert (moved/'.incomplete').exists()
    elif mode=='known_replaced':
        assert (out/'model.json').read_bytes()==b'keep'
        assert (out/'.incomplete').exists()
    else:
        assert (out/'foreign').read_bytes()==b'keep'
        assert (out/'.incomplete').exists()


def test_thermal_partial_failure_safe_cleanup_link_capability(tmp_path,monkeypatch):
    import simcase.thermal as thermal
    path=tmp_path/'out';path.mkdir();file=path/'file';file.write_bytes(b'keep')
    def unsupported(*args,**kwargs):raise OSError('hard links unavailable')
    monkeypatch.setattr(thermal.os,'link',unsupported)
    with pytest.raises(OSError,match='hard-link identity pins') as caught:
        thermal._pin_file_link(file)
    assert str(caught.value.__cause__)=='hard links unavailable'
    assert file.read_bytes()==b'keep'
    assert not list(tmp_path.glob('.simcase-pin-*'))


def test_thermal_partial_failure_safe_cleanup_link_foreign_pin(tmp_path):
    import simcase.thermal as thermal
    out=tmp_path/'out';out.mkdir();file=out/'file';file.write_bytes(b'original')
    close=thermal._pin_file_link(file)
    directory,=tmp_path.glob('.simcase-pin-*')
    # Replacing the private pin is outside caller ownership, but never recurse.
    replacement=tmp_path/'replacement';replacement.write_bytes(b'foreign')
    replacement.replace(directory/'file')
    with pytest.raises(OSError,match='pin was replaced'):close()
    assert (directory/'file').read_bytes()==b'foreign'
    assert file.read_bytes()==b'original'



def model(source=0., n=8, unit='mm'):
    data=copy.deepcopy(examples.THERMAL_SLAB)
    data['mesh']['subdivisions']=[n,n]
    data['physics']['heat1']['heat_source_w_m3']=source
    factor={'m':.001,'mm':1.,'um':1000.}[unit]
    data['geometry']['domain']={k:v*factor for k,v in data['geometry']['domain'].items()}
    data['units']['length']=unit
    return data


def test_thermal_affine_slab_and_no_optical_defaults():
    d=Document.from_dict(model());r=run(d,False)
    assert isinstance(r,ThermalRunResult)
    assert list(d['physics'])==['heat1'] and 'background' not in d['geometry']
    x=r.mesh_nodes_m[:,0]
    np.testing.assert_allclose((r.temperature_k-(280+35*x/.03))/35,0,atol=1e-10)
    np.testing.assert_allclose((r.heat_flux_w_m2-[-12.5*35/.03,0])/14583.3333333333,0,atol=1e-10)
    left=r.mesh.boundary['left'];right=r.mesh.boundary['right'];heat=12.5*35*.02/.03
    np.testing.assert_allclose([r.reaction_w_per_m[left].sum()/heat,r.reaction_w_per_m[right].sum()/heat],[-1,1],atol=1e-10)
    assert not {'neff','wavelength','normalization','group_index'}&r.summary().keys()


def test_thermal_numeric_npz_and_metadata(tmp_path):
    r=run(Document.from_dict(model(1e5)),False);out=r.save(tmp_path/'heat')
    s=json.loads((out/'summary.json').read_text());assert abs(s['outward_heat_w_per_m']-60)/60<1e-10
    assert not (out/'.incomplete').exists()
    with np.load(out/'fields.npz',allow_pickle=False) as z:
        np.testing.assert_array_equal(z['temperature_k'],r.temperature_k)
        assert str(z['field_layout'])=='thermal2d-p1-node-cell-v1'
        assert json.loads(str(z['metadata_json']))==s
    with pytest.raises(FileExistsError):r.save(out)


def test_thermal_corner_conflict_and_equal_dedup():
    d=model();d['physics']['heat1']['dirichlet_temperature_k']={'left':300.,'top':300.}
    r=run(Document.from_dict(d),False)
    assert len(r.dirichlet_node_ids)==17
    np.testing.assert_allclose(r.temperature_k,300.,atol=1e-10)
    d['physics']['heat1']['dirichlet_temperature_k']['top']=301.
    with pytest.raises(DocumentError,match='corner'):Document.from_dict(d)


@pytest.mark.parametrize('unit',['m','mm','um'])
def test_thermal_si_invariance_and_direct_api(unit):
    from galerkin.thermal import solve_steady_heat
    r=run(Document.from_dict(model(1e5,unit=unit)),False)
    base=run(Document.from_dict(model(1e5,unit='m')),False)
    np.testing.assert_allclose(r.mesh_nodes_m,base.mesh_nodes_m,atol=1e-16,rtol=1e-12)
    direct=solve_steady_heat(r.mesh,conductivity=12.5,heat_source=1e5,
        dirichlet=dict(zip(r.dirichlet_node_ids,r.dirichlet_temperature_k)))
    for actual,expected,scale in [(r.temperature_k,base.temperature_k,35.),
        (r.heat_flux_w_m2,base.heat_flux_w_m2,12.5*35/.03),
        (r.load_w_per_m,base.load_w_per_m,12.5*35*.02/.03),
        (r.reaction_w_per_m,base.reaction_w_per_m,12.5*35*.02/.03),
        (r.residual_w_per_m,base.residual_w_per_m,12.5*35*.02/.03)]:
        assert np.max(abs(actual-expected))/scale<=1e-9
    for a,b in [(r.temperature_k,direct.temperature),(r.heat_flux_w_m2,direct.heat_flux),
        (r.load_w_per_m,direct.load),(r.reaction_w_per_m,direct.reaction),(r.residual_w_per_m,direct.residual)]:
        np.testing.assert_array_equal(a,b)


def test_thermal_mixed_convergence_and_refsol_slab():
    from refsol.thermal import slab
    results=[]
    u,w=np.polynomial.legendre.leggauss(8);u,w=(u+1)/2,w/2
    a,b=np.meshgrid(u,u,indexing='ij');bary=np.stack((1-a,a*b,a*(1-b)),axis=-1).reshape(-1,3)
    weights=(w[:,None]*w[None,:]*a).ravel()
    for n in (8,16,32,64):
        r=run(Document.from_dict(model(1e5,n)),False)
        vertices=r.mesh_nodes_m[r.mesh_triangles];p=np.einsum('qi,tic->tqc',bary,vertices)
        x=p[:,:,0];exact=280+35*x/.03+1e5*x*(.03-x)/(2*12.5)
        flux=np.stack((-12.5*35/.03-1e5*.03/2+1e5*x,np.zeros_like(x)),axis=-1)
        T=np.einsum('qi,ti->tq',bary,r.temperature_k[r.mesh_triangles])
        v=vertices[:,1:]-vertices[:,:1];det=abs(v[:,0,0]*v[:,1,1]-v[:,0,1]*v[:,1,0]);measure=det[:,None]*weights
        errors=[np.sqrt(np.sum(measure*(T-exact)**2)),np.sqrt(np.sum(measure[...,None]*(r.heat_flux_w_m2[:,None]-flux)**2))]
        assert r.summary()['normalized_heat_balance_defect']<=1e-10
        assert abs(r.load_w_per_m.sum()-60)/60<=1e-10
        results.append(errors)
    e=np.array(results);rates=np.log(e[:-1]/e[1:])/np.log(2)
    print(json.dumps({'mixed_errors':e.tolist(),'orders':rates.tolist()}))
    assert np.all(np.diff(e,axis=0)<0)
    assert np.all(rates[-2:,0]>=1.8) and np.all(rates[-2:,1]>=.9)
    r=run(Document.from_dict(model()),False)
    exact=slab(r.mesh_nodes_m,length=.03,conductivity=12.5,left_temperature=280,right_temperature=315)
    assert max(abs(r.temperature_k-exact.temperature))/35<=1e-10


@pytest.mark.parametrize('path,value',[
    ('physics.heat1.conductivity_w_mk',0),('physics.heat1.conductivity_w_mk',True),
    ('physics.heat1.heat_source_w_m3',float('nan')),('physics.heat1.wavelength',1.),
    ('physics.heat1.dirichlet_temperature_k',{}),('physics.heat1.dirichlet_temperature_k',{'left':-1}),
    ('physics.heat1.dirichlet_temperature_k',{'unknown':300}),
    ('units.temperature','C'),('units.temperature',{'in_K':1}),('units.mass','g'),
    ('mesh.subdivisions',[2,0]),('mesh.subdivisions',[True,2]),('mesh.size',1),
    ('geometry.shapes',[]),('geometry.background',{'material':'vacuum'}),
    ('materials',{'solid':{'n':1.}}),('study',{'type':'sweep','values':[1,2]}),
    ('results.plots',True),('results.save_fields',1),('geometry.domain.xmax',0),
    ('geometry.domain.xmin',float('inf')),
])
def test_thermal_invalid_document(path,value):
    d=model();node=d
    for key in path.split('.')[:-1]:node=node.setdefault(key,{})
    node[path.split('.')[-1]]=value
    with pytest.raises(DocumentError):Document.from_dict(d)


def test_thermal_schema_boundary_cases():
    for key in ['length','temperature']:
        d=model();del d['units'][key]
        with pytest.raises(DocumentError):Document.from_dict(d)
    d=model();d['physics']['em1']={'type':'em.modes2d'}
    with pytest.raises(DocumentError,match='more than one'):Document.from_dict(d)
    d=model();del d['physics']['heat1']['heat_source_w_m3']
    assert Document.from_dict(d)['physics']['heat1']['heat_source_w_m3']==0
    d=model();d['physics']['heat1']['dirichlet_temperature_k']={'left':0.}
    r=run(Document.from_dict(d),False);np.testing.assert_array_equal(r.temperature_k,0)
    for temperatures in [{'left':280.,'top':315.},{'top':315.,'left':280.}]:
        d=model();d['physics']['heat1']['dirichlet_temperature_k']=temperatures
        with pytest.raises(DocumentError,match='corner'):Document.from_dict(d)


@pytest.mark.parametrize('kind',['file','empty','nonempty','dangling'])
def test_thermal_existing_target_unchanged(tmp_path,kind):
    r=run(Document.from_dict(model()),False);p=tmp_path/'out'
    if kind=='file':p.write_bytes(b'original')
    elif kind=='dangling':p.symlink_to(tmp_path/'absent')
    else:
        p.mkdir()
        if kind=='nonempty':(p/'original.txt').write_bytes(b'original')
    with pytest.raises(FileExistsError):r.save(p)
    if kind=='file':assert p.read_bytes()==b'original'
    elif kind=='dangling':assert p.is_symlink()
    elif kind=='nonempty':assert (p/'original.txt').read_bytes()==b'original'
    else:assert list(p.iterdir())==[]


@pytest.mark.parametrize('mode',['ordinary','foreign','replaced','known_replaced','before_marker'])
def test_thermal_partial_failure_safe_cleanup(tmp_path,monkeypatch,mode):
    r=run(Document.from_dict(model()),False);out=tmp_path/'heat';original=_OwnedOutput.write
    moved=tmp_path/'moved';stages=[];fixture_error=None
    def failing(self,name,writer):
        nonlocal fixture_error
        if mode=='before_marker':
            stages.append('injected before marker');raise OSError('injected before marker')
        answer=original(self,name,writer)
        if name=='fields.npz':
            stages.append('NPZ written; starting fixture')
            try:
                if mode=='foreign':
                    (out/'foreign.txt').write_text('do not remove');stages.append('foreign file written')
                if mode=='known_replaced':
                    replacement=tmp_path/'replacement.json';replacement.write_text('replacement')
                    stages.append('file replace starting')
                    replacement.replace(out/'model.json');stages.append('file replace completed')
                    assert (out/'model.json').read_text()=='replacement'
                if mode=='replaced':
                    stages.append('directory rename starting')
                    out.rename(moved);stages.append('directory rename completed')
                    out.mkdir();stages.append('replacement directory created')
                    (out/'foreign.txt').write_text('replacement directory');stages.append('replacement foreign file written')
                stages.append('injected after NPZ')
                raise OSError('injected after NPZ')
            except OSError as exc:
                fixture_error={'type':type(exc).__name__,'errno':exc.errno,
                               'winerror':getattr(exc,'winerror',None),'message':str(exc),
                               'stage':stages[-1],'stages':list(stages)}
                raise
        return answer
    monkeypatch.setattr(_OwnedOutput,'write',failing)
    with pytest.raises(OSError) as caught:r.save(out)
    expected='injected before marker' if mode=='before_marker' else 'injected after NPZ'
    diagnostic={'mode':mode,'fixture_error':fixture_error,'stages':stages,
                'caught':{'type':type(caught.value).__name__,'errno':caught.value.errno,
                          'winerror':getattr(caught.value,'winerror',None),'message':str(caught.value)}}
    print('THERMAL_CLEANUP_DIAGNOSTIC '+json.dumps(diagnostic,sort_keys=True),flush=True)
    # OS fixture failures are not evidence of the intended post-replacement fault.
    assert str(caught.value)==expected,diagnostic
    assert stages[-1]==expected,diagnostic
    if mode=='known_replaced':assert 'file replace completed' in stages,diagnostic
    if mode=='replaced':assert 'replacement foreign file written' in stages,diagnostic
    if mode in ['ordinary','before_marker']:assert not out.exists()
    elif mode=='replaced':
        assert (out/'foreign.txt').read_text()=='replacement directory'
        assert (moved/'.incomplete').exists()
    else:
        assert (out/'.incomplete').exists() and not (out/'summary.json').exists()
        if mode=='foreign':assert (out/'foreign.txt').read_text()=='do not remove'
        else:assert (out/'model.json').read_text()=='replacement'


def test_thermal_simultaneous_writers_preserve_winner(tmp_path,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    r=run(Document.from_dict(model()),False);out=tmp_path/'heat';barrier=threading.Barrier(2)
    original=_OwnedOutput.__init__
    def together(self,path):barrier.wait();return original(self,path)
    monkeypatch.setattr(_OwnedOutput,'__init__',together)
    def write():
        try:r.save(out);return 'winner'
        except FileExistsError:return 'loser'
    with ThreadPoolExecutor(max_workers=2) as pool:answers=list(pool.map(lambda _:write(),range(2)))
    assert sorted(answers)==['loser','winner'] and (out/'summary.json').exists()
    with np.load(out/'fields.npz',allow_pickle=False) as z:np.testing.assert_array_equal(z['temperature_k'],r.temperature_k)


def test_thermal_fields_disabled_cli_and_expected_errors(tmp_path,capsys,monkeypatch):
    data=model();data['results']['save_fields']=False;doc=Document.from_dict(data);f=tmp_path/'model.json';doc.save(f)
    assert main(['validate',str(f)])==0
    assert main(['run',str(f),'-q','-o',str(tmp_path/'out')])==0
    text=capsys.readouterr().out
    assert 'fields.npz' not in text and 'results.png' not in text and 'n_eff' not in text
    assert not (tmp_path/'out'/'fields.npz').exists()
    assert main(['run',str(f),'-o',str(tmp_path/'out')])==1
    bad=model();bad['results']['plots']=True;f.write_text(json.dumps(bad))
    assert main(['run',str(f),'-o',str(tmp_path/'bad')])==2 and not (tmp_path/'bad').exists()
    f.write_text(json.dumps(data))
    import simcase.cli as cli
    monkeypatch.setattr(cli,'run',lambda *a,**kw:(_ for _ in ()).throw(ValueError('injected solve failure')))
    assert main(['run',str(f),'-o',str(tmp_path/'bad')])==1 and not (tmp_path/'bad').exists()
    assert 'Traceback' not in capsys.readouterr().err


def test_thermal_studio_capability_rejection(monkeypatch):
    from fastapi.testclient import TestClient
    from simcase.studio import server
    client=TestClient(server.app);before=set(server._jobs)
    def forbidden(*a,**kw):raise AssertionError('headless thermal must not enter Studio worker/mesher')
    monkeypatch.setattr(server,'run',forbidden);monkeypatch.setattr(server,'build_mesh',forbidden)
    data=model()
    assert not client.post('/api/validate',json={'doc':data}).json()['ok']
    for route in ['/api/mesh','/api/run']:assert client.post(route,json={'doc':data}).status_code==400
    assert client.get('/api/examples/thermal_slab').status_code==400
    assert 'thermal_slab' not in client.get('/api/examples').json()['examples']
    assert set(server._jobs)==before


def test_thermal_all_raw_metadata(tmp_path):
    r=run(Document.from_dict(model()),False);s=r.summary();arrays=r._raw_arrays()
    assert set(s['field_units'])==set(arrays)==set(s['field_locations'])==set(s['field_shapes'])
    for key,a in arrays.items():assert s['field_shapes'][key]==list(a.shape)
    assert s['field_units']['nodes_m']=='m' and s['field_units']['dirichlet_temperature_k']=='K'
    assert s['field_units']['triangles']==s['field_units']['dirichlet_node_ids']=='1'


@pytest.mark.parametrize('key',['nodes_m','triangles','temperature_k','heat_flux_w_m2','load_w_per_m','reaction_w_per_m','residual_w_per_m','dirichlet_node_ids','dirichlet_temperature_k'])
def test_thermal_all_raw_nonfinite_rejected_even_without_fields(tmp_path,key):
    data=model();data['results']['save_fields']=False
    r=run(Document.from_dict(data),False)
    owners={'nodes_m':(r.mesh,'nodes'),'triangles':(r.mesh,'triangles'),
            'dirichlet_node_ids':(r,'dirichlet_node_ids'),'dirichlet_temperature_k':(r,'dirichlet_temperature_k')}
    owner,attr=owners.get(key,(r.solution,{'temperature_k':'temperature','heat_flux_w_m2':'heat_flux','load_w_per_m':'load','reaction_w_per_m':'reaction','residual_w_per_m':'residual'}.get(key)))
    a=np.asarray(getattr(owner,attr),dtype=float).copy();a.flat[0]=np.nan;setattr(owner,attr,a)
    with pytest.raises(ValueError,match='finite'):r.save(tmp_path/'bad')
    assert not (tmp_path/'bad').exists()


@pytest.mark.parametrize('damage',['nodes_shape','triangles_shape','temperature_shape','flux_shape','load_shape','reaction_shape','residual_shape','fixed_shape','fixed_values_shape','index','duplicate','clockwise'])
def test_thermal_raw_structure_rejected(tmp_path,damage):
    r=run(Document.from_dict(model()),False)
    if damage=='nodes_shape':r.mesh.nodes=r.mesh.nodes[:,0]
    elif damage=='triangles_shape':r.mesh.triangles=r.mesh.triangles[:,:2]
    elif damage=='fixed_shape':r.dirichlet_node_ids=r.dirichlet_node_ids[:,None]
    elif damage=='fixed_values_shape':r.dirichlet_temperature_k=r.dirichlet_temperature_k[:,None]
    elif damage=='index':r.mesh.triangles[0,0]=len(r.mesh.nodes)
    elif damage=='duplicate':r.dirichlet_node_ids[1]=r.dirichlet_node_ids[0]
    elif damage=='clockwise':r.mesh.triangles[0]=r.mesh.triangles[0,::-1]
    else:
        attr={'temperature_shape':'temperature','flux_shape':'heat_flux','load_shape':'load','reaction_shape':'reaction','residual_shape':'residual'}[damage]
        setattr(r.solution,attr,getattr(r.solution,attr)[:-1])
    with pytest.raises(ValueError):r.save(tmp_path/'bad')
    assert not (tmp_path/'bad').exists()


def test_thermal_json_integer_policy():
    for value in [4.0,True,0,-1,'4']:
        d=model();d['mesh']['subdivisions']=[value,4]
        with pytest.raises(DocumentError):Document.from_dict(d)
    Document.from_dict(model(n=4))


def test_thermal_cli_nonfinite_summary_exit1(tmp_path,capsys,monkeypatch):
    import simcase.cli as cli
    data=model();data['results']['save_fields']=False
    r=run(Document.from_dict(data),False)
    r.diagnostics['injected_nonfinite']=float('nan')
    # Put a nonfinite value in a metadata field actually emitted by summary().
    r.timings['solve']=float('nan')
    f=tmp_path/'model.json';r.doc.save(f)
    monkeypatch.setattr(cli,'run',lambda *a,**kw:r)
    assert main(['run',str(f),'-o',str(tmp_path/'bad')])==1
    error=capsys.readouterr().err
    assert not (tmp_path/'bad').exists() and 'Traceback' not in error
    assert 'JSON compliant' in error  # Exercise nonfinite metadata, not snapshot refusal.


@pytest.mark.parametrize('name',['model.json','log.txt','fields.npz','summary.json','.incomplete'])
def test_thermal_missing_owned_artifact_never_commits(tmp_path,monkeypatch,name):
    r=run(Document.from_dict(model()),False);out=tmp_path/'out';original=_OwnedOutput.finish
    def missing(self):
        (self.path/name).unlink()
        original(self)
    monkeypatch.setattr(_OwnedOutput,'finish',missing)
    with pytest.raises(OSError):r.save(out)
    assert not out.exists()  # all remaining known files can safely be cleaned


@pytest.mark.parametrize('mode',['empty','foreign','replaced'])
def test_thermal_directory_pin_failure_safely_cleans_constructor(tmp_path,monkeypatch,mode):
    import simcase.thermal as thermal
    out=tmp_path/'out';moved=tmp_path/'moved'
    def fail(path):
        if mode=='foreign':(path/'foreign').write_text('keep')
        if mode=='replaced':path.rename(moved);path.mkdir();(path/'foreign').write_text('keep')
        raise OSError('original pin acquisition failure')
    monkeypatch.setattr(thermal,'_pin_directory',fail)
    r=run(Document.from_dict(model()),False)
    with pytest.raises(OSError,match='original pin acquisition failure'):r.save(out)
    if mode=='empty':assert not out.exists()
    else:assert (out/'foreign').read_text()=='keep'


@pytest.mark.skipif(__import__('os').name == 'nt', reason='DeleteFile pending-handle semantics differ; replacement is tested portably with replace')
def test_thermal_posix_unlink_recreate_inode_reuse_regression(tmp_path,monkeypatch):
    r=run(Document.from_dict(model()),False);out=tmp_path/'out';original=_OwnedOutput.write
    def failing(self,name,writer):
        original(self,name,writer)
        if name=='fields.npz':
            (out/'model.json').unlink();(out/'model.json').write_text('replacement')
            raise OSError('original immediate unlink/recreate negative control')
    monkeypatch.setattr(_OwnedOutput,'write',failing)
    with pytest.raises(OSError):r.save(out)
    assert (out/'model.json').read_text()=='replacement' and (out/'.incomplete').exists()

