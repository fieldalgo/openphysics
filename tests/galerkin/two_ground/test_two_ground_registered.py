# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import numpy as np
import pytest
from scipy.constants import epsilon_0
from galerkin.laplace_two_ground import solve_two_ground_rectangle
ROWS=json.loads((Path(__file__).parent/"evidence/registered.json").read_text())

@pytest.mark.parametrize("row",ROWS,ids=[r["case"] for r in ROWS])
def test_registered_geometry_and_stored_independent_reference(row,record_property):
    result=solve_two_ground_rectangle(row["polygons"],width=row["width"],height=row["height"],
        panels_per_edge=256,interpolation_degree=row["degree"])
    c0=epsilon_0*result.capacitance_per_permittivity
    q=np.concatenate((result.current_gram[:-2],result.current_gram[-2:].sum(axis=0)[None]))
    # Not bit for bit: the dense solve's last bits follow the runner's CPU and BLAS kernel
    # (relative 1.1e-15 to 2.5e-15 on an EPYC 7763 runner, Validate run 45466696066).
    np.testing.assert_allclose(c0,row["panel"]["C0"],rtol=1e-13,atol=0)
    np.testing.assert_allclose(q,row["panel"]["Q"],rtol=1e-10,atol=0)
    ref=row["reference"];rq=np.asarray(ref["Q"])
    if rq.ndim==4:rq=rq[0]
    np.testing.assert_allclose(c0,ref["C0"],rtol=5e-4,atol=0)
    np.testing.assert_allclose(q,rq,rtol=.01,atol=0)
    record_property("two_ground_observation",json.dumps(dict(case=row["case"],C0=c0.tolist(),Q=q.tolist(),
        current_integrals=result.current_integrals.tolist(),ground_refinement=result.ground_refinement_error,
        source="stored independent P4 reference; not rerun in this test"),sort_keys=True))
