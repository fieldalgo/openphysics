# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Existing vector consumers must retain both complex polarization directions."""

import copy
import json

import numpy as np

from galerkin import disk_mesh, EdgeSpace, eval_edge_field
from galerkin.edge import assemble_edge_mass
from galerkin.assembly import assemble_mass
from simcase import Document, examples
from simcase.physics_em_modes2d import solve
from simcase.runner import RunResult


def test_vector_eigenspace_reliability_adapter_and_saved_complex_span(tmp_path):
    mesh = disk_mesh((4, 8, 24), (4, 4, 16), 32)
    eps = mesh.by_region([1.45**2, 1.44**2, 1.44**2])
    point = solve(mesh, eps, 1.5, {'outer': 'pec'}, 2, 'vector', 1.44)
    f = point['vector_field']
    space = EdgeSpace(mesh)
    mass = assemble_edge_mass(space, 1.)
    nodal = assemble_mass(mesh, 1.)

    def gram(t, z):
        return t.conj().T@(mass@t)+z.conj().T@(nodal@z)

    g = gram(f.transverse, f.longitudinal)
    norm = np.sqrt(np.outer(g.diagonal().real, g.diagonal().real))
    assert np.linalg.eigvalsh(g/norm)[0] > 1e-8
    d = copy.deepcopy(examples.VECTOR_FIBER)
    d['physics']['em1'].update(wavelength=1.5, num_modes=2)
    d['results'].update(plots=False, save_fields=True)
    doc = Document.from_dict(d)
    names = [f'region{i}' for i in range(3)]
    materials = dict(zip(names, ['core', 'clad', 'clad']))
    result = RunResult(doc, mesh.nodes, mesh.triangles, mesh.regions, names,
                       materials, None, [1.5], point['neff'][None, :], [], vector_fields=[f])
    out = result.save(tmp_path/'complex-pair')
    with np.load(out/'fields.npz', allow_pickle=False) as saved:
        t, z = saved['vector_transverse'][0], saved['vector_longitudinal'][0]
        np.testing.assert_array_equal(t, f.transverse)
        np.testing.assert_array_equal(z, f.longitudinal)
        np.testing.assert_allclose(gram(t, z), g, atol=1e-13)
        for j in range(2):
            np.testing.assert_allclose(eval_edge_field(space, t[:, j]), saved['vector_electric'][0, :, j, :2], atol=1e-13)
        np.testing.assert_allclose(z[mesh.triangles].mean(axis=1), saved['vector_electric'][0, :, :, 2], atol=1e-13)
    payload = f.to_dict()
    back = np.array(payload['real'])+1j*np.array(payload['imag'])
    np.testing.assert_array_equal(back.transpose(1, 0, 2), f.electric)
    assert json.loads((out/'summary.json').read_text())['field_representation'] == 'vector-edge-nodal-v1'
    assert result.group_index() is None
