# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""meshine's deliberate refusals carry public classes, with their old bases and messages.

``generate`` and ``Domain.build`` explain why they cannot mesh an input. Those explanations
were a plain ``RuntimeError`` (the refinement did not converge, the triangulation cannot
resolve a boundary point) or a plain ``ValueError`` (the domain's geometry is refused), so a
caller could tell an explanation from any other failure only by its text. They are now
``meshine.MeshingError`` (a ``RuntimeError``; ``MeshSizeLimitError`` is one) and
``meshine.MeshInputError`` (a ``ValueError``), with the same messages, so every caller that
catches ``RuntimeError`` or ``ValueError`` keeps working.

Each raise site has one case here, triggered by an input (the off-edge vertex of
test_small_angles, the film, the single point and the hole of test_meshine_scale, the caps of
test_size_limit) except the all-degenerate empty mesh, which no known input reaches: its
refusal is called directly. A message with numbers that depend on the triangulation is
checked by its fixed words; every other message is compared whole.
"""

import numpy as np
import pytest

import meshine
from meshine import Domain, MeshInputError, MeshingError, MeshSizeLimitError, generate, rectangle
from meshine import geometry, refine


def square(size):
    d = Domain(size=size)
    d.add_region("sq", rectangle(0, 0, 1, 1))
    return d


def raised(call, cls, base):
    """The exception ``call`` raises: of ``cls`` and of the builtin ``base`` it was before."""
    with pytest.raises(cls) as caught:
        call()
    assert isinstance(caught.value, base) and isinstance(caught.value, cls), repr(caught.value)
    return str(caught.value)


def test_the_classes_are_public_and_keep_their_builtin_bases():
    assert {"MeshingError", "MeshInputError", "MeshSizeLimitError"} <= set(meshine.__all__)
    assert meshine.MeshingError is refine.MeshingError and meshine.MeshInputError is geometry.MeshInputError
    assert issubclass(MeshingError, RuntimeError) and not issubclass(MeshingError, ValueError)
    assert issubclass(MeshInputError, ValueError) and not issubclass(MeshInputError, RuntimeError)
    assert issubclass(MeshSizeLimitError, MeshingError)


# ---- MeshingError: meshing could not finish -----------------------------------------------

def test_refinement_that_does_not_finish_in_max_rounds():
    text = raised(lambda: generate(square(0.05), max_rounds=1), MeshingError, RuntimeError)
    assert text == "refinement did not converge in 1 rounds"


def test_a_boundary_point_the_triangulation_drops():
    d = Domain(size=0.2)
    d.add_region("lower", rectangle(0, 0, 2, 1))
    d.add_region("upper", [(0, 1), (2, 1), (2, 2), (1, 2), (1, 1 + 4e-8), (0.9, 2), (0, 2)])
    text = raised(lambda: generate(d), MeshingError, RuntimeError)
    assert text.startswith("meshine.generate: the triangulation cannot resolve 1 boundary point(s); the first is (")
    assert text.endswith("(for example a coarse Circle that touches another boundary; see the Limits in "
                         "meshine's documentation).")


def test_the_point_caps():
    text = raised(lambda: generate(square(0.5), max_points=3), MeshSizeLimitError, RuntimeError)
    assert text == "more than 3 points; the input domain has 4"
    text = raised(lambda: generate(square(0.05), max_points=20), MeshingError, RuntimeError)
    assert text == "more than 20 points; check sizes / min_angle"


# ---- MeshInputError: the domain's geometry is refused ---------------------------------------

def test_a_loop_with_too_few_vertices():
    d = Domain(size=0.2)
    d.add_region("a", [(0, 0), (1, 0)])
    text = raised(lambda: generate(d), MeshInputError, ValueError)
    assert text == "region 'a': a loop needs >= 3 vertices with 2 coordinates"


def test_a_domain_without_regions():
    assert raised(lambda: generate(Domain(size=0.2)), MeshInputError, ValueError) == "no regions added"


def test_a_domain_without_extent():
    d = Domain(size=0.2)
    d.add_region("a", [(1.0, 1.0), (1.0, 1.0), (1.0, 1.0)])
    text = raised(lambda: generate(d), MeshInputError, ValueError)
    assert text == ("Domain.build: the input has no extent: the bounding box of every region vertex has a zero "
                    "diagonal, so every vertex is the same point. A domain needs a finite extent before any "
                    "tolerance here means anything.")


def test_regions_that_overlap():
    d = Domain(size=0.5)
    for name in ("a", "b", "c"):
        d.add_region(name, rectangle(0, 0, 1, 1))
    text = raised(lambda: generate(d), MeshInputError, ValueError)
    assert text == "a segment is shared by more than two regions; regions overlap"


def test_a_zero_length_edge():
    d = Domain(size=0.2)
    d.add_region("film", rectangle(0, 0, 1, 1e-18))
    text = raised(lambda: generate(d), MeshInputError, ValueError)
    assert text == ("Domain.build: region 'film' has a zero-length edge. Two consecutive vertices fell within the "
                    "merge distance 1e-09 (1e-09 of the 1-unit domain diagonal) and became one point. Either the "
                    "loop repeats a vertex, or the feature is finer than 1e-09 of the domain that contains it.")


def test_an_empty_mesh_whose_regions_enclose_nothing():
    d = Domain(size=0.2)
    d.add_region("a", rectangle(0, 0, 1, 1), holes=[rectangle(0, 0, 1, 1)])
    text = raised(lambda: generate(d), MeshInputError, ValueError)
    assert text.startswith("meshine.generate produced 0 triangles and 0 nodes: of ")
    assert text.endswith("none of the remaining 2 has its centroid inside any of the 1 region(s) (a). The regions "
                         "enclose no area the triangulation covers: check that every loop is a simple closed "
                         "polygon and that each hole lies inside its own outer loop.")


def test_an_empty_mesh_of_degenerate_triangles():
    """No known input reaches this refusal (an input whose every triangle is degenerate is
    refused earlier, as a zero-length edge or no extent), so it is called directly."""
    d = square(0.2)
    pts, _segments, regions = d.build()
    text = raised(lambda: refine._refuse_empty_mesh(pts, np.array([[0, 1, 2]]), np.array([True]), d, regions),
                  MeshInputError, ValueError)
    assert text == ("meshine.generate produced 0 triangles and 0 nodes: all 1 triangles of the final triangulation "
                    "are degenerate. The 4 mesh points span 1.41421 units, and at that extent they are collapsed "
                    "onto a line or a single point. This is a geometry problem, not a mesh-size one; check the "
                    "region coordinates and the unit they are written in.")
