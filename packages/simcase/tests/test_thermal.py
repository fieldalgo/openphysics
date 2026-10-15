# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Headless thermal document consumers: SI fields, physical signs and refusals."""
import copy
import json
import numpy as np
import pytest
from simcase import Document, DocumentError, ThermalRunResult, examples, run


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
