# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Existing vector consumers must retain both complex polarization directions."""

import copy
import json

import numpy as np

from galerkin import disk_mesh, EdgeSpace, Mesh, eval_edge_field
from galerkin.edge import assemble_edge_mass
from galerkin.assembly import assemble_mass
from simcase import Document, examples
from simcase.fields import VectorField
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
    d['physics']['em1'].update(vacuum_wavelength='1.5 um', mode_count=2)
    d.setdefault('results', {}).update(plots=False, save_fields=True)
    doc = Document.from_dict(d)
    names = [f'region{i}' for i in range(3)]
    materials = dict(zip(names, ['core', 'clad', 'clad']))
    # the public result: SI (metres) under exp(-i omega t), the kernel's answer converted once
    public = VectorField(f.edges, np.conj(f.transverse) * 1e-6, np.conj(f.longitudinal), np.conj(f.electric))
    result = RunResult(doc, mesh.nodes * 1e-6, mesh.triangles, mesh.regions, names, materials, None,
                       np.array([1.5e-6]), np.conj(point['neff'])[None, :], [], vector_fields=[public])
    out = result.save(tmp_path/'complex-pair')
    mesh_m = Mesh(mesh.nodes * 1e-6, mesh.triangles, {})
    space_m = EdgeSpace(mesh_m)
    mass_m, nodal_m = assemble_edge_mass(space_m, 1.), assemble_mass(mesh_m, 1.)
    with np.load(out/'fields.npz', allow_pickle=False) as saved:
        t = saved['unnormalized_electric_field_line_integral'][0]
        z = saved['unnormalized_electric_field_z'][0]
        np.testing.assert_array_equal(t, public.transverse)
        np.testing.assert_array_equal(z, public.longitudinal)
        # the saved span is the kernel's span conjugated: its Gram matrix on the metre mesh is
        # the conjugate of the kernel's times 1e-12, so both polarization directions remain
        gram_m = t.conj().T@(mass_m@t)+z.conj().T@(nodal_m@z)
        np.testing.assert_allclose(gram_m, np.conj(g) * 1e-12, rtol=1e-10, atol=0)
        for j in range(2):
            np.testing.assert_allclose(eval_edge_field(space_m, t[:, j]),
                                       saved['unnormalized_electric_field'][0, :, j, :2], atol=1e-13)
        np.testing.assert_allclose(z[mesh.triangles].mean(axis=1), saved['unnormalized_electric_field'][0, :, :, 2],
                                   atol=1e-13)
    payload = public.to_dict()
    back = np.array(payload['real'])+1j*np.array(payload['imag'])
    np.testing.assert_array_equal(back.transpose(1, 0, 2), public.electric)
    assert json.loads((out/'summary.json').read_text())['field_representation'] == 'vector-edge-nodal-v2'
    assert result.group_index() is None
