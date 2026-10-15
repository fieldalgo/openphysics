# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Actual independent thermal adapter acceptance; fixed pre-candidate gates."""
import copy
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import numpy as np
import pytest
from simcase import Document,DocumentError,ThermalRunResult,run
import thermal_simcase_independent_oracle as answer


def actual(**kw):
    return run(Document.from_dict(answer.document(**kw)),verbose=False)


@pytest.mark.parametrize('source',[0.,answer.SOURCE,-answer.SOURCE])
def test_independent_original_matrix_reactions_and_closed_form(source):
    result=actual(source=source);assert isinstance(result,ThermalRunResult)
    raw=answer.result_arrays(result);answer.validate_actual_raw(raw,source)
    expected,_=answer.closed_form(raw['nodes_m'],source)
    np.testing.assert_allclose((raw['temperature_k']-expected)/35,0,atol=1e-10)
    assert result.summary()['physics_name']=='independent_heat'
    assert not {'neff','wavelength','group_index','normalization'}&result.summary().keys()


def test_independent_actual_original_mesh_convergence():
    errors=[]
    for n in (8,16,32,64):
        result=actual(n=n);raw=answer.result_arrays(result)
        answer.validate_actual_raw(raw)
        errors.append(answer.errors_from_actual(raw))
        np.testing.assert_allclose(errors[-1],answer.errors_from_actual(raw,8),rtol=1e-8)
    rates=np.log2(np.array(errors[:-1])/np.array(errors[1:]))
    print('ACTUAL independent n8/16/32/64 errors',np.array(errors),'rates',rates)
    assert np.all(rates[-2:]>=np.array([1.8,.9]))


def test_independent_document_units_and_normalized_arrays(tmp_path):
    reference=answer.result_arrays(actual(unit='m'))
    for unit in ('mm','um'):
        data=answer.document(unit=unit);doc=Document.from_dict(data)
        assert list(doc['physics'])==['independent_heat'] and set(doc['geometry'])=={'domain'}
        path=tmp_path/(unit+'.json');doc.save(path);loaded=Document.load(path)
        assert loaded.data==doc.data and loaded['geometry']['domain']==data['geometry']['domain']
        raw=answer.result_arrays(run(loaded,False));answer.validate_actual_raw(raw)
        for key in reference:
            if raw[key].dtype.kind in 'iu':np.testing.assert_array_equal(raw[key],reference[key]);continue
            scale=answer.L if key=='nodes_m' else 35. if key in ('temperature_k','dirichlet_temperature_k') else answer.K*35/answer.L if key=='heat_flux_w_m2' else 2*answer.K*35*answer.H/answer.L+60
            np.testing.assert_allclose((raw[key]-reference[key])/scale,0,atol=1e-9)


def test_independent_saved_numeric_raw_and_metadata(tmp_path):
    result=actual();out=result.save(tmp_path/'fresh')
    summary=json.loads((out/'summary.json').read_text(),parse_constant=lambda s: (_ for _ in ()).throw(ValueError(s)))
    assert summary['result_format']==answer.FORMAT and summary['field_layout']==answer.LAYOUT
    assert summary['mesh_length_unit']=='m' and summary['units']=={'length':'mm','temperature':'K'}
    assert summary['source_heat_w_per_m']==pytest.approx(60.,rel=1e-10)
    assert summary['outward_heat_w_per_m']==pytest.approx(60.,rel=1e-10)
    with np.load(out/'fields.npz',allow_pickle=False) as z:
        arrays={key:z[key] for key in z.files}
    assert all(v.dtype.kind in 'iufUS' for v in arrays.values())
    assert arrays['result_format'].shape==() and arrays['result_format'].item()==answer.FORMAT
    assert arrays['field_layout'].item()==answer.LAYOUT and arrays['mesh_length_unit'].item()=='m'
    assert json.loads(arrays['metadata_json'].item())==summary
    raw={key:arrays[key] for key in answer.UNITS};answer.validate_actual_raw(raw)
    for key,value in answer.result_arrays(result).items():np.testing.assert_array_equal(raw[key],value)
    for key in answer.UNITS:
        assert summary['field_units'][key]==answer.UNITS[key]
        assert summary['field_shapes'][key]==list(raw[key].shape)
        location = 'triangle_centroids' if key=='heat_flux_w_m2' else 'triangle_connectivity' if key=='triangles' else 'dirichlet_nodes' if key.startswith('dirichlet_') else 'nodes'
        assert summary['field_locations'][key]==location
    assert set(p.name for p in out.iterdir())=={'fields.npz','model.json','summary.json','log.txt'}
    assert json.loads((out/'model.json').read_text())==result.doc.data
    corrupt={key:value.copy() for key,value in raw.items()};corrupt['residual_w_per_m'][0]+=1
    with pytest.raises(AssertionError):answer.validate_actual_raw(corrupt)


def test_independent_fields_false(tmp_path):
    out=actual(fields=False).save(tmp_path/'no-fields');summary=json.loads((out/'summary.json').read_text())
    assert set(p.name for p in out.iterdir())=={'model.json','summary.json','log.txt'}
    assert summary['result_format']==answer.FORMAT
    assert not (set(answer.UNITS)-{'dirichlet_temperature_k'})&summary.keys()
    assert summary['dirichlet_temperature_k']=={'left':280.,'right':315.}


@pytest.mark.parametrize('kind',['file','empty','nonempty','dangling'])
@pytest.mark.parametrize('fields',[True,False])
def test_independent_existing_targets_unchanged(tmp_path,kind,fields):
    target=tmp_path/'existing'
    if kind=='file':target.write_bytes(b'preserve-file')
    elif kind=='dangling':target.symlink_to(tmp_path/'absent')
    else:
        target.mkdir()
        if kind=='nonempty':(target/'foreign').write_bytes(b'preserve-child')
    before=target.lstat()
    with pytest.raises(FileExistsError):actual(fields=fields).save(target)
    after=target.lstat();assert (before.st_dev,before.st_ino,before.st_mode)==(after.st_dev,after.st_ino,after.st_mode)
    if kind=='file':assert target.read_bytes()==b'preserve-file'
    elif kind=='dangling':assert os.readlink(target)==str(tmp_path/'absent')
    elif kind=='empty':assert not any(target.iterdir())
    else:assert sorted(p.name for p in target.iterdir())==['foreign'] and (target/'foreign').read_bytes()==b'preserve-child'


@pytest.mark.parametrize('tags',[{'left':300.,'top':300.},{'left':300.,'right':300.,'top':300.,'bottom':300.}])
def test_independent_equal_corners_deduplicate(tags):
    data=answer.document(source=0);data['physics']['independent_heat']['dirichlet_temperature_k']=tags
    result=run(Document.from_dict(data),False)
    _,_,sets=answer.rectangle(8)
    expected=answer.prescribed_nodes(sets,tags)[0]
    np.testing.assert_array_equal(result.dirichlet_node_ids,expected)
    np.testing.assert_allclose((result.temperature_k-300)/35,0,atol=1e-10)


@pytest.mark.parametrize('tags',[{'left':280.,'top':315.},{'top':315.,'left':280.}])
def test_independent_corner_conflict(tags):
    data=answer.document();data['physics']['independent_heat']['dirichlet_temperature_k']=tags
    with pytest.raises(DocumentError,match='corner'):Document.from_dict(data)


def _set(data,path,value):
    node=data
    for key in path[:-1]:node=node[key]
    node[path[-1]]=value
    return data


BAD=[(('physics','independent_heat','conductivity_w_mk'),x) for x in [0,-1,True,float('nan'),float('inf'),'12.5',[],None]]
BAD += [(('physics','independent_heat','heat_source_w_m3'),x) for x in [False,float('nan'),float('inf'),'Q',[],None]]
BAD += [(('physics','independent_heat','dirichlet_temperature_k','left'),x) for x in [-1,False,float('nan'),float('inf'),'280',None]]
BAD += [(('mesh','subdivisions'),x) for x in [[True,8],[0,8],[1.5,8],[8,8,8],[],None]]
BAD += [(('units','temperature'),x) for x in ['C','F',{'in_K':1}]]
BAD += [(('study',),{'type':'sweep'}),(('geometry','domain','xmax'),.0),(('geometry','domain','xmin'),True),(('geometry','domain','xmax'),float('inf'))]
BAD += [(('physics','independent_heat',key),1.) for key in ['wavelength','neff','formulation','n_cladding','num_modes','flux','robin']]
BAD += [(('materials',),{'glass':{'n':1.5}}),(('geometry','shapes'),[]),(('mesh','size'),.01),(('units','mass'),'kg'),(('results','plots'),True),(('physics','independent_heat','dirichlet_temperature_k'),{})]


@pytest.mark.parametrize('path,value',BAD,ids=lambda x:str(x))
def test_independent_strict_rejection(path,value):
    data=_set(answer.document(),path,value)
    with pytest.raises(DocumentError):Document.from_dict(data)


@pytest.mark.parametrize('section',['geometry','mesh','results','study','physics'])
@pytest.mark.parametrize('value',[[],None,False,1])
def test_independent_malformed_sections_are_document_errors(section,value):
    data=answer.document();data[section]=value
    with pytest.raises(DocumentError):Document.from_dict(data)


@pytest.mark.parametrize('stage',['after_npz','unexpected','replaced'])
def test_independent_actual_failure_cleanup(tmp_path,monkeypatch,stage):
    import simcase.thermal as thermal
    target=tmp_path/'fresh';moved=tmp_path/'moved';original=thermal._OwnedOutput.write
    def injected(owner,name,writer):
        if name=='summary.json':
            assert (target/'fields.npz').is_file()
            if stage=='unexpected':(target/'foreign').write_bytes(b'preserve-external')
            if stage=='replaced':
                target.rename(moved);target.mkdir();(target/'foreign').write_bytes(b'replacement-owner')
            raise OSError('independent injected pre-summary write failure')
        return original(owner,name,writer)
    monkeypatch.setattr(thermal._OwnedOutput,'write',injected)
    with pytest.raises(OSError,match='independent injected'):actual().save(target)
    if stage=='after_npz':assert not target.exists()
    elif stage=='unexpected':
        assert sorted(p.name for p in target.iterdir())==['.incomplete','foreign']
        assert (target/'foreign').read_bytes()==b'preserve-external'
    else:
        assert sorted(p.name for p in target.iterdir())==['foreign']
        assert (target/'foreign').read_bytes()==b'replacement-owner'
        assert (moved/'.incomplete').is_file() and not (moved/'summary.json').exists()


def test_independent_actual_two_writers(tmp_path):
    results=[actual(source=q) for q in (0.,answer.SOURCE)]
    for i,result in enumerate(results):result.doc.data['name']=f'independent writer {i}'
    target=tmp_path/'race';barrier=threading.Barrier(2)
    def writer(i):
        barrier.wait()
        try:results[i].save(target);return ('won',i)
        except FileExistsError:return ('lost',i)
    with ThreadPoolExecutor(max_workers=2) as executor:outcomes=list(executor.map(writer,(0,1)))
    assert sorted(v[0] for v in outcomes)==['lost','won']
    winner=[v[1] for v in outcomes if v[0]=='won'][0]
    assert set(p.name for p in target.iterdir())=={'model.json','log.txt','fields.npz','summary.json'}
    meta=json.loads((target/'summary.json').read_text());model=json.loads((target/'model.json').read_text())
    assert meta['name']==model['name']==f'independent writer {winner}'
    with np.load(target/'fields.npz',allow_pickle=False) as data:
        np.testing.assert_array_equal(data['temperature_k'],results[winner].temperature_k)
        assert json.loads(data['metadata_json'].item())==meta


@pytest.mark.parametrize('field',['heat_flux','load','reaction','residual'])
def test_independent_save_refuses_nonfinite_result_arrays(tmp_path,field):
    result=actual();getattr(result.solution,field).flat[0]=np.nan
    with pytest.raises(ValueError):result.save(tmp_path/'invalid')
    assert not (tmp_path/'invalid'/'summary.json').exists()


def test_independent_save_refuses_wrong_cell_flux_shape(tmp_path):
    result=actual();result.solution.heat_flux=np.ones(len(result.mesh_triangles))
    with pytest.raises(ValueError):result.save(tmp_path/'invalid-shape')
    assert not (tmp_path/'invalid-shape'/'summary.json').exists()


def test_independent_cli_actual_process(tmp_path):
    model=tmp_path/'thermal.json';model.write_text(json.dumps(answer.document(n=4)))
    env=os.environ.copy();env.pop('PYTHONPATH',None)
    valid=subprocess.run([sys.executable,'-I','-m','simcase','validate',str(model)],capture_output=True,text=True,env=env)
    assert valid.returncode==0 and 'thermal.steady2d' in valid.stdout and 'neff' not in valid.stdout
    out=tmp_path/'cli-result'
    done=subprocess.run([sys.executable,'-I','-m','simcase','run',str(model),'-o',str(out),'-q'],capture_output=True,text=True,env=env)
    assert done.returncode==0,done.stderr
    with np.load(out/'fields.npz',allow_pickle=False) as z:answer.validate_actual_raw({k:z[k] for k in answer.UNITS})
    assert 'results written' in done.stdout
    existing=subprocess.run([sys.executable,'-I','-m','simcase','run',str(model),'-o',str(out),'-q'],capture_output=True,text=True,env=env)
    assert existing.returncode==1 and 'Traceback' not in existing.stderr and 'results written' not in existing.stdout
    bad=answer.document();bad['results']['plots']=True;model.write_text(json.dumps(bad))
    invalid=subprocess.run([sys.executable,'-I','-m','simcase','run',str(model),'-o',str(tmp_path/'bad')],capture_output=True,text=True,env=env)
    assert invalid.returncode==2 and not (tmp_path/'bad').exists() and 'Traceback' not in invalid.stderr
    missing=subprocess.run([sys.executable,'-I','-m','simcase','validate',str(tmp_path/'missing')],capture_output=True,text=True,env=env)
    assert missing.returncode==2 and 'Traceback' not in missing.stderr
    print('ACTUAL subprocess executable',sys.executable)


def test_independent_studio_capability_no_jobs(monkeypatch):
    from fastapi.testclient import TestClient
    import simcase.studio.server as server
    jobs=copy.deepcopy(server._jobs)
    def forbidden(*args,**kwargs):raise AssertionError('thermal reached optical worker/mesh')
    monkeypatch.setattr(server,'build_mesh',forbidden);monkeypatch.setattr(server,'run',forbidden)
    with TestClient(server.app) as client:
        validation=client.post('/api/validate',json={'doc':answer.document()})
        assert validation.status_code==200 and validation.json()['ok'] is False and 'headless' in validation.json()['error']
        for path in ('/api/mesh','/api/run'):
            reply=client.post(path,json={'doc':answer.document()})
            assert reply.status_code==400 and 'headless' in reply.text
        listed=client.get('/api/examples').json()['examples']
        assert not any('thermal' in name for name in listed)
        for name in ('thermal_slab','thermal_mixed'):
            reply=client.get('/api/examples/'+name)
            assert reply.status_code==400 and 'headless' in reply.text
    assert server._jobs==jobs


def test_independent_all_fixed_source_reactions():
    result=actual(n=1)
    assert len(result.dirichlet_node_ids)==len(result.temperature_k)
    answer.validate_actual_raw(answer.result_arrays(result))


@pytest.mark.parametrize('kind',['unknown','empty','unanchored'])
def test_independent_boundary_and_component_failures(monkeypatch,kind):
    import galerkin
    from galerkin.mesh import Mesh
    data=answer.document(n=2)
    if kind=='unknown':
        data['physics']['independent_heat']['dirichlet_temperature_k']={'outside':280.}
        with pytest.raises(DocumentError):Document.from_dict(data)
        return
    nodes,tri,tags=answer.rectangle(2,origin=(0.,0.))
    if kind=='empty':tags['left']=np.array([],dtype=int)
    else:
        nodes=np.concatenate([nodes,nodes+[1.,0.]])
        tri=np.concatenate([tri,tri+9])
    monkeypatch.setattr(galerkin,'rectangle_mesh',lambda *args:Mesh(nodes.copy(),tri.copy(),tags))
    with pytest.raises((DocumentError,ValueError),match='empty|component|Dirichlet|anchor'):
        run(Document.from_dict(data),False)


@pytest.mark.parametrize('kind',['file','empty','nonempty','dangling'])
def test_independent_cli_existing_target_unchanged(tmp_path,kind):
    model=tmp_path/'model.json';model.write_text(json.dumps(answer.document(fields=False)))
    target=tmp_path/'keep'
    if kind=='file':target.write_bytes(b'original')
    elif kind=='dangling':target.symlink_to(tmp_path/'missing')
    else:
        target.mkdir()
        if kind=='nonempty':(target/'foreign').write_bytes(b'original')
    before=target.lstat()
    done=subprocess.run([sys.executable,'-I','-m','simcase','run',str(model),'-o',str(target),'-q'],capture_output=True,text=True)
    assert done.returncode==1 and 'Traceback' not in done.stderr and 'results written' not in done.stdout
    after=target.lstat();assert (before.st_dev,before.st_ino,before.st_mode)==(after.st_dev,after.st_ino,after.st_mode)
    if kind=='file':assert target.read_bytes()==b'original'
    elif kind=='dangling':assert os.readlink(target)==str(tmp_path/'missing')
    elif kind=='empty':assert not any(target.iterdir())
    else:assert sorted(p.name for p in target.iterdir())==['foreign'] and (target/'foreign').read_bytes()==b'original'


@pytest.mark.parametrize('stage',['solve','save'])
def test_independent_cli_expected_runtime_exit_one(tmp_path,stage):
    model=tmp_path/'model.json';model.write_text(json.dumps(answer.document(n=2)))
    target=tmp_path/'failed'
    injection="cli.run=lambda *a,**k: (_ for _ in ()).throw(ValueError('independent solve injection'))" if stage=='solve' else "np.savez_compressed=lambda *a,**k: (_ for _ in ()).throw(OSError('independent save injection'))"
    script="import sys,numpy as np;from simcase import cli;"+injection+";sys.exit(cli.main(sys.argv[1:]))"
    done=subprocess.run([sys.executable,'-I','-c',script,'run',str(model),'-o',str(target),'-q'],capture_output=True,text=True)
    assert done.returncode==1 and 'independent '+stage+' injection' in done.stderr
    assert 'Traceback' not in done.stderr and 'results written' not in done.stdout and not target.exists()


@pytest.mark.parametrize('mode',['empty','foreign','replaced'])
def test_independent_constructor_failure_does_not_leave_unmarked_target(tmp_path,monkeypatch,mode):
    import simcase.thermal as thermal
    target=tmp_path/'constructor-failed';original=thermal.os.open
    def failed(path,*args,**kwargs):
        if Path(path)==target:
            if mode=='foreign':(target/'foreign').write_bytes(b'preserved external file')
            elif mode=='replaced':
                target.rename(tmp_path/'moved-owner');target.mkdir();(target/'foreign').write_bytes(b'preserved replacement')
            raise OSError('independent constructor handle injection')
        return original(path,*args,**kwargs)
    result=actual();monkeypatch.setattr(thermal.os,'open',failed)
    with pytest.raises(OSError,match='constructor handle injection'):result.save(target)
    if mode=='empty':assert not target.exists(),'empty exclusively created target must be cleaned after constructor failure'
    else:
        expected=b'preserved external file' if mode=='foreign' else b'preserved replacement'
        assert (target/'foreign').read_bytes()==expected and not (target/'summary.json').exists()


@pytest.mark.parametrize('missing',['model.json','log.txt','fields.npz','summary.json','.incomplete'])
def test_independent_missing_required_owned_file_cannot_complete(tmp_path,monkeypatch,missing):
    import simcase.thermal as thermal
    original=thermal._OwnedOutput.write;target=tmp_path/'missing-required'
    def remove_required(owner,name,writer):
        value=original(owner,name,writer)
        if name=='summary.json':(target/missing).unlink()
        return value
    monkeypatch.setattr(thermal._OwnedOutput,'write',remove_required)
    with pytest.raises(OSError):actual().save(target)
    assert not (target/'summary.json').exists() or (target/'.incomplete').exists()


def test_independent_replaced_owned_file_is_preserved(tmp_path,monkeypatch):
    import simcase.thermal as thermal
    original=thermal._OwnedOutput.write;target=tmp_path/'replaced-file'
    def replace_owned(owner,name,writer):
        value=original(owner,name,writer)
        if name=='fields.npz':
            (target/'model.json').unlink();(target/'model.json').write_bytes(b'external replacement')
            raise OSError('independent owned file replaced')
        return value
    monkeypatch.setattr(thermal._OwnedOutput,'write',replace_owned)
    with pytest.raises(OSError,match='owned file replaced'):actual().save(target)
    assert (target/'model.json').read_bytes()==b'external replacement'
    assert (target/'.incomplete').exists() and not (target/'summary.json').exists()


@pytest.mark.parametrize('key',list(answer.UNITS))
@pytest.mark.parametrize('fields',[True,False])
def test_independent_all_raw_nonfinite_refused(key,fields,tmp_path):
    result=actual(fields=fields)
    owners={'nodes_m':(result.mesh,'nodes'),'triangles':(result.mesh,'triangles'),
            'dirichlet_node_ids':(result,'dirichlet_node_ids'),
            'dirichlet_temperature_k':(result,'dirichlet_temperature_k')}
    properties={'temperature_k':'temperature','heat_flux_w_m2':'heat_flux','load_w_per_m':'load','reaction_w_per_m':'reaction','residual_w_per_m':'residual'}
    owner,name=owners[key] if key in owners else (result.solution,properties[key])
    changed=np.asarray(getattr(owner,name),dtype=float).copy();changed.flat[-1]=np.inf;setattr(owner,name,changed)
    with pytest.raises(ValueError):result.save(tmp_path/'nonfinite')
    assert not (tmp_path/'nonfinite'/'summary.json').exists()


@pytest.mark.parametrize('damage',['clockwise','out_of_range','duplicate_fixed','fixed_value_shape','bool_flux','float_subdivisions'])
def test_independent_additional_raw_and_input_refusals(tmp_path,damage):
    if damage=='float_subdivisions':
        data=answer.document();data['mesh']['subdivisions']=[4.,4]
        with pytest.raises(DocumentError):Document.from_dict(data)
        return
    result=actual()
    if damage=='clockwise':result.mesh.triangles[0]=result.mesh.triangles[0,::-1]
    elif damage=='out_of_range':result.mesh.triangles[0,0]=len(result.mesh_nodes_m)
    elif damage=='duplicate_fixed':result.dirichlet_node_ids[-1]=result.dirichlet_node_ids[-2]
    elif damage=='fixed_value_shape':result.dirichlet_temperature_k=result.dirichlet_temperature_k[:,None]
    else:result.solution.heat_flux=np.ones(result.heat_flux_w_m2.shape,dtype=bool)
    with pytest.raises(ValueError):result.save(tmp_path/'invalid-structure')
    assert not (tmp_path/'invalid-structure'/'summary.json').exists()
