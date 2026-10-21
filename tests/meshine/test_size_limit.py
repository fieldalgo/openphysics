# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""``max_points`` raises a typed error, and holds for the input domain as built.

``generate`` refused an insertion that would pass ``max_points`` with a plain
``RuntimeError``, so a caller could tell the cap from any other failure only by the
message. It now raises ``meshine.MeshSizeLimitError``, a ``RuntimeError`` subclass with
the same message. The cap is also checked right after ``Domain.build``: an input with
more points was refused only at its first insertion, after the corner analysis, the
lattice splits and a Delaunay round, and one that needed no insertion came back over
the cap.

The pass criteria were fixed before the change. Nothing is stored: the mesh each cap is
compared with is computed here, uncapped, and the node count it gives is not written
down (it is a property of this platform's Qhull, not of the cap).
"""

import math

import numpy as np
import pytest
from scipy.spatial import cKDTree

import meshine
from meshine import Domain, MeshSizeLimitError, box_sides, generate, rectangle
from meshine import refine


def polygon(n, radius=1.0):
    return [(radius * math.cos(2 * math.pi * k / n), radius * math.sin(2 * math.pi * k / n)) for k in range(n)]


def sixty_four_gon():
    d = Domain(size=0.5)
    d.add_region("disc", polygon(64))
    return d


def built_points(domain, boundary_names="outer"):
    """The number of points ``Domain.build`` gives, which ``generate`` starts from."""
    return len(domain.build(boundary_names)[0])


class Calls:
    """What ``generate`` called before it raised."""

    def __init__(self):
        self.delaunay = 0
        self.sharp_corners = 0
        self.trees = 0


def spy(monkeypatch) -> Calls:
    """Count the first triangulation, the corner analysis and every tree ``generate`` builds.
    ``cKDTree`` is an extension type whose methods cannot be patched, so ``meshine.refine``
    gets a counting subclass instead."""
    calls = Calls()
    delaunay, sharp_corners = refine.Delaunay, refine._sharp_corners

    def counting_delaunay(*args, **kwargs):
        calls.delaunay += 1
        return delaunay(*args, **kwargs)

    def counting_sharp_corners(*args, **kwargs):
        calls.sharp_corners += 1
        return sharp_corners(*args, **kwargs)

    class CountingTree(cKDTree):
        def __init__(self, *args, **kwargs):
            calls.trees += 1
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(refine, "Delaunay", counting_delaunay)
    monkeypatch.setattr(refine, "_sharp_corners", counting_sharp_corners)
    monkeypatch.setattr(refine, "cKDTree", CountingTree)
    return calls


def assert_same_mesh(new, old):
    for field in ("nodes", "triangles", "regions"):
        assert np.array_equal(getattr(new, field), getattr(old, field)), field
        assert getattr(new, field).dtype == getattr(old, field).dtype, field
    assert new.region_names == old.region_names
    for field in ("boundary_edges", "boundary_nodes", "interfaces"):
        a, b = getattr(new, field), getattr(old, field)
        assert list(a) == list(b), field
        assert all(np.array_equal(a[k], b[k]) for k in a), field


# ---- B1a: the type -----------------------------------------------------------------------

def test_b1a_the_cap_error_is_a_public_runtime_error_with_the_old_message():
    assert issubclass(MeshSizeLimitError, RuntimeError)
    assert "MeshSizeLimitError" in meshine.__all__
    assert meshine.MeshSizeLimitError is refine.MeshSizeLimitError
    # the insertion cap: a unit square of size 0.1 needs far more than 20 points
    d = Domain(size=0.1)
    d.add_region("sq", rectangle(0, 0, 1, 1))
    with pytest.raises(MeshSizeLimitError) as insertion:
        generate(d, box_sides(0, 1, 0, 1), min_angle=28, max_points=20)
    assert str(insertion.value) == "more than 20 points; check sizes / min_angle"
    # the input cap: the 64-gon is built from 64 points
    with pytest.raises(MeshSizeLimitError) as built:
        generate(sixty_four_gon(), max_points=40)
    assert str(built.value).startswith("more than 40 points")
    # callers that catch RuntimeError keep working
    with pytest.raises(RuntimeError, match="more than 40 points"):
        generate(sixty_four_gon(), max_points=40)


# ---- B1b: the input domain is checked before any refinement work ---------------------------

def test_b1b_an_input_over_the_cap_is_refused_before_the_corners_and_the_first_triangulation(monkeypatch):
    n = built_points(sixty_four_gon())
    assert n > 40
    calls = spy(monkeypatch)
    with pytest.raises(MeshSizeLimitError) as refused:
        generate(sixty_four_gon(), max_points=40)
    assert str(refused.value) == f"more than 40 points; the input domain has {n}"
    assert (calls.delaunay, calls.sharp_corners, calls.trees) == (0, 0, 0)


def test_b1b_the_input_check_is_exactly_at_the_cap(monkeypatch):
    """One point over the cap is refused as input; exactly at the cap the input passes, and
    this input then needs insertions, which the per-insertion cap refuses after a Delaunay
    round."""
    n = built_points(sixty_four_gon())
    calls = spy(monkeypatch)
    with pytest.raises(MeshSizeLimitError, match=f"the input domain has {n}$"):
        generate(sixty_four_gon(), max_points=n - 1)
    assert calls.delaunay == 0
    with pytest.raises(MeshSizeLimitError, match="check sizes / min_angle$"):
        generate(sixty_four_gon(), max_points=n)
    assert calls.delaunay >= 1 and calls.sharp_corners == 1


def test_b1b_an_input_that_needs_no_insertion_no_longer_comes_back_over_the_cap():
    """A square at a size far above its own needs no insertion. Before, ``max_points=3``
    returned its 4-node mesh, over the cap, because only insertions were checked."""
    def square():
        d = Domain(size=100.0)
        d.add_region("sq", rectangle(0, 0, 1, 1))
        return d
    mesh = generate(square(), box_sides(0, 1, 0, 1), min_angle=28, max_points=4)
    assert mesh.num_nodes == 4
    with pytest.raises(MeshSizeLimitError, match="the input domain has 4$"):
        generate(square(), box_sides(0, 1, 0, 1), min_angle=28, max_points=3)


# ---- B1c: a cap at the node count changes nothing ------------------------------------------

def plate_and_background():
    """The loops simcase builds for its shipped transient region example (a 10 x 5 mm steel
    plate beside a 20 x 5 mm background, mesh size 0.7 mm), in micrometres as simcase meshes
    region documents, in the vertex order shapely gives."""
    d = Domain(size=700.0)
    d.add_region("steel_plate", [(10000.0, 0.0), (0.0, 0.0), (0.0, 5000.0), (10000.0, 5000.0)])
    d.add_region("background", [(30000.0, 5000.0), (30000.0, 0.0), (10000.0, 0.0), (10000.0, 5000.0)])
    return d


def test_b1c_a_cap_at_the_node_count_gives_the_same_mesh_and_one_less_raises():
    sides = box_sides(0, 30000, 0, 5000)
    uncapped = generate(plate_and_background(), sides, min_angle=28)
    n = uncapped.num_nodes
    assert n > built_points(plate_and_background(), sides)          # refinement inserted points
    capped = generate(plate_and_background(), sides, min_angle=28, max_points=n)
    assert_same_mesh(capped, uncapped)
    with pytest.raises(MeshSizeLimitError, match=f"more than {n - 1} points; check sizes / min_angle"):
        generate(plate_and_background(), sides, min_angle=28, max_points=n - 1)
