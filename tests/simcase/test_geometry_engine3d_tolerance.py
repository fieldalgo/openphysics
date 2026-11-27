# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Stage 5: pieces of a 3d component's arrangement below the mesher tolerance are refused before the
hand-off to meshloom.

The contract (geometry_document.md, "What the grid does not fix") refuses, before the hand-off,
any feature whose size relative to its component's bounding-box diagonal is below the mesher
tolerance, ``MESHER_RELATIVE_TOLERANCE`` = 3e-8. Whole features are refused at parse time; this
check covers the pieces the arrangement creates: the distance from a 2D vertex to a fine curve
that does not end there (a short curve, or a thin neck between two curves), the height of a slab
between two z levels, and the width (2 area / perimeter) of a horizontal face. It names the
later feature whose part bounds the piece, with code ``E-CONTRACT`` and the 2D route's sentence.

Pre-registered (fixed before measuring):
- R1: two large boxes whose faces are offset by 1.5e-8 of the diagonal, as a strip (one face
  shifted along a shared plane) and as a gap (a thin sheet of background between them), are
  refused with ``E-CONTRACT`` at ``geometry.components.c`` and the existing sentence, naming box B.
- R2 (re-registered after the result; coordinator decision
  2026-11-27-openphysics-geometry-stage5-thin-piece-hang): the same documents at 6e-8 pass the
  check; the exact complex builds and the meshloom input (points, facets, tags, region points) is
  formed. Meshing them is not asserted: meshloom.generate3d does not return on them (meshloom
  backlog, finding 4; reproducers ``thin_strip_6e-8`` and ``thin_gap_6e-8``).
- R3: a box whose top lies 1.5e-8 of the diagonal above a slab-layer level (a thin slab) is
  refused, naming the box.
- R4: none of slice 1's 200 G1 sets nor E1 hits the check (they keep meshing as before; G1 and
  its S1 digests are unchanged).
"""

import math

import pytest

meshloom = pytest.importorskip("meshloom")
if not meshloom.kernel_available():
    pytest.skip("meshloom's compiled kernel is not built in this environment", allow_module_level=True)

import test_geometry_engine3d as s1  # noqa: E402
from simcase.geometry_document import GeometryError  # noqa: E402
from simcase.geometry_engine3d import _prepare, build_mesh3d  # noqa: E402

E = 10 ** 9                                     # 1 mm in pm
DIAG = math.sqrt(2 * (10 * E) ** 2 + (2.5 * E) ** 2)     # the 10 x 10 x 2.5 mm domain's diagonal, pm


def two_boxes(mode: str, ratio: float):
    delta = round(ratio * DIAG)
    a = {"name": "A", "type": "box", "xmin": 2 * E, "xmax": 5 * E, "ymin": 2 * E, "ymax": 8 * E, "zmin": 0,
         "zmax": 2 * E, "material": "Cu"}
    if mode == "strip":     # B touches A at x = 5 mm; B's y0 face is delta above A's y0 face
        b = {"xmin": 5 * E, "ymin": 2 * E + delta, "ymax": 7 * E}
    else:                   # B's x0 face is delta beyond A's x1 face: a thin sheet of background between
        b = {"xmin": 5 * E + delta, "ymin": 3 * E, "ymax": 7 * E}
    b.update({"name": "B", "type": "box", "xmax": 8 * E, "zmin": 0, "zmax": 2 * E, "material": "Al"})
    return s1.doc([a, b], unit="pm", domain=(0, 10 * E, 0, 10 * E, 0, 25 * E // 10), size="0.8 mm"), delta


def _sentence(name, size, ratio):
    return (f"geometry.components.c: feature {name!r} is {size} pm across, {ratio:.2e} of the component's diagonal, "
            "below the mesher tolerance 3e-08; it would vanish in the mesh. Meshing such multi-scale geometry is not "
            "supported yet.")


@pytest.mark.parametrize("mode", ["strip", "gap"])
def test_r1_a_piece_at_1_5e_8_of_the_diagonal_is_refused_by_name(mode):
    d, delta = two_boxes(mode, 1.5e-8)
    with pytest.raises(GeometryError) as err:
        build_mesh3d(d)
    assert err.value.code == "E-CONTRACT"
    assert err.value.path == "geometry.components.c"
    assert str(err.value) == _sentence("B", delta, delta / DIAG)


@pytest.mark.parametrize("mode", ["strip", "gap"])
def test_r2_a_piece_at_6e_8_passes_and_its_meshloom_input_is_formed(mode):
    d, _ = two_boxes(mode, 6e-8)
    cx, comp, ho, info = _prepare(d)
    assert ho.points and ho.facets and ho.region_points
    assert len(ho.face_of_facet) == len(ho.facets)
    assert {r for _, r in ho.region_points} == {"A", "B", "background"}
    assert info.code == "I-MESH-ESTIMATE"


def test_r3_a_thin_slab_is_refused_naming_the_box():
    delta = round(1.5e-8 * DIAG)
    feats = [{"name": "stack", "type": "layers", "z0": 0, "layers": [
                 {"name": "a", "thickness": E, "material": "FR4"}, {"name": "b", "thickness": 15 * E // 10,
                                                                    "material": "mold"}]},
             {"name": "pad", "type": "box", "xmin": 2 * E, "xmax": 5 * E, "ymin": 2 * E, "ymax": 5 * E, "zmin": 0,
              "zmax": E + delta, "material": "Cu"}]
    d = s1.doc(feats, unit="pm", domain=(0, 10 * E, 0, 10 * E, 0, 25 * E // 10), size="0.8 mm")
    with pytest.raises(GeometryError) as err:
        build_mesh3d(d)
    assert err.value.code == "E-CONTRACT"
    assert str(err.value) == _sentence("pad", delta, delta / DIAG)


def test_r4_slice1_sets_and_e1_do_not_hit_the_check():
    hit = []
    for seed in range(200):
        d, _, _ = s1.g1_doc(seed)
        try:
            _prepare(d)
        except GeometryError as err:
            if "below the mesher tolerance" in str(err):
                hit.append(seed)
            elif "has nothing to mesh" not in str(err):
                raise
    assert hit == []
    _prepare(s1.e1(), through_meshloom=True)
