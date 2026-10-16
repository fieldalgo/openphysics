# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Standalone installed-wheel consumer; run with python -I, without pytest."""
from dataclasses import fields
import importlib.util
from pathlib import Path
import unittest
import numpy as np
from galerkin.mesh import Mesh
import galerkin.thermoelasticity as production

spec=importlib.util.spec_from_file_location('independent_math',Path(__file__).with_name('thermoelastic_traction_independent_oracle.py'))
oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)


class InstalledConsumer(unittest.TestCase):
    def setUp(self):
        self.assertIn('site-packages',Path(production.__file__).resolve().parts)

    def example(self,plane):
        p,t=oracle.square_geometry()
        mesh=Mesh(p,t,{'all':np.arange(4)}, {'left':np.array([[0,3]]),'right':np.array([[1,2]]),'top':np.array([[2,3]]),'bottom':np.array([[0,1]])})
        exact=oracle.patch(p,plane);snapshot=production.freeze_temperature(mesh,oracle.TREF+exact['theta'])
        cfg=dict(reference_temperature_k=oracle.TREF,thermal_expansion_per_k=oracle.ALPHA,young_modulus=oracle.E,poisson_ratio=oracle.NU,plane=plane,dirichlet={(i,c):exact['u'][i,c] for i in (0,3) for c in (0,1)},traction={tag:(lambda p,n:n@oracle.TARGET.T) for tag in ('right','top','bottom')})
        r=production.solve_thermoelasticity(mesh,snapshot,**cfg)
        np.testing.assert_allclose(r.displacement,exact['u'],rtol=0,atol=1e-14)
        np.testing.assert_allclose(r.stress,np.broadcast_to([8e6,-2e6,3e6],r.stress.shape),rtol=0,atol=.001)
        self.assertAlmostEqual(r.physical_elastic_energy,float(exact['state']['energy'][0]),delta=1e-6)
        return mesh,snapshot,r,cfg

    def test_patch_plane_stress(self):self.example('stress')
    def test_patch_plane_strain(self):self.example('strain')

    def test_legacy18_and_snapshot_lifetime(self):
        mesh,snapshot,r,cfg=self.example('strain')
        legacy=production.ThermoelasticResult(*(getattr(r,f.name) for f in fields(r)[:18]))
        self.assertIsNone(legacy.load_body);self.assertIsNone(legacy.load_traction)
        original=np.full(len(mesh.nodes),300.);copied=production.freeze_temperature(mesh,original);original[:]=0
        self.assertTrue(np.all(copied.temperature_k==300.))
        with self.assertRaises(ValueError):copied.temperature_k.setflags(write=True)
        self.assertEqual(len(fields(r)),20)
        np.testing.assert_allclose(r.load_external,r.load_body+r.load_traction,rtol=0,atol=1e-8)

    def test_consistent_linear_segment(self):
        p=np.array([[0.,0.],[1.,0.],[0.,1.]])
        mesh=Mesh(p,np.array([[0,1,2]]),{'all':np.arange(3)},{'edge':np.array([[0,1]])})
        snapshot=production.freeze_temperature(mesh,np.full(3,oracle.TREF+20))
        r=production.solve_thermoelasticity(mesh,snapshot,reference_temperature_k=oracle.TREF,thermal_expansion_per_k=oracle.ALPHA,young_modulus=oracle.E,poisson_ratio=oracle.NU,plane='strain',dirichlet={(i,c):0. for i in range(3) for c in (0,1)},traction={'edge':lambda p,n:p[:,0,None]*[3e6,-2e6]})
        expected=np.array([[3e6,-2e6],[6e6,-4e6],[0.,0.]])/6
        np.testing.assert_allclose(r.load_traction,expected,rtol=0,atol=1e-8)


if __name__=='__main__':unittest.main(verbosity=2)
