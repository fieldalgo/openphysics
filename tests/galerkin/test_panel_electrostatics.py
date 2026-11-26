# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""galerkin.panel_electrostatics, the public SI panel API, against the internal panel solvers.

The public functions only read box_size and rename conductor selections, so every result must be
the internal solver's, bit for bit: the six fast solvers are run both ways and compared field by
field (np.array_equal on every array, == on everything else); all nine are checked to hand the
internal solver exactly the caller's numbers (the three harmonic corner solves take about 27 s each,
and test_laplace_corner_harmonic_*.py already run them). Refusals name the public arguments.
"""
import dataclasses
import inspect

import numpy as np
import pytest

from galerkin import panel_electrostatics as pe

SQUARE = [[0.0038, 0.000975], [0.0042, 0.000975], [0.0042, 0.001025], [0.0038, 0.001025]]
SECOND = [[0.0045, 0.000975], [0.0049, 0.000975], [0.0049, 0.001025], [0.0045, 0.001025]]
THREE = [[[0.003425, 0.0006], [0.003775, 0.0006], [0.00375, 0.00065], [0.00345, 0.00065]],
         [[0.00425, 0.0011], [0.00465, 0.0011], [0.004675, 0.00116], [0.004225, 0.00116]],
         [[0.0039, 0.00155], [0.0041, 0.00155], [0.00409, 0.00159], [0.00391, 0.00159]]]
WIDTH, HEIGHT = 0.008, 0.002

#: public name: (internal module, keyword renames public -> internal)
INTERNAL = {
    "solve_grounded_rectangle": ("laplace_boundary", {}),
    "solve_two_ground_rectangle": ("laplace_two_ground", {}),
    "solve_two_ground_rectangle_edges": ("laplace_two_ground", {}),
    "solve_two_ground_corner_rectangle_edges": ("laplace_two_ground", {}),
    "solve_two_ground_linear_corner_rectangle_edges": ("laplace_corner_linear_field", {}),
    "solve_two_ground_harmonic_corner_three_active_edges": ("laplace_corner_harmonic_field", {}),
    "solve_two_ground_harmonic_corner_guard_edges": ("laplace_corner_harmonic_guard_field",
                                                     {"signal_indices": "signals"}),
    "solve_two_ground_harmonic_corner_single_active_edges": ("laplace_corner_harmonic_single_active_field",
                                                             {"signal_index": "signal"}),
    "solve_open_rectangle": ("laplace_open_box", {"ground_indices": "grounds"}),
}

#: public name: (polygons, public keywords besides box_size)
CASES = {
    "solve_grounded_rectangle": ([SQUARE], dict(panels_per_edge=8)),
    "solve_two_ground_rectangle": ([SQUARE], dict(panels_per_edge=8)),
    "solve_two_ground_rectangle_edges": ([SQUARE], dict(panels_per_edge=8)),
    "solve_two_ground_corner_rectangle_edges": ([SQUARE], dict(panels_per_edge=16)),
    "solve_two_ground_linear_corner_rectangle_edges": ([SQUARE], dict(panels_per_edge=16)),
    "solve_two_ground_harmonic_corner_three_active_edges": (THREE, dict(panels_per_edge=16)),
    "solve_two_ground_harmonic_corner_guard_edges": (THREE, dict(panels_per_edge=16, signal_indices=(0, 1))),
    "solve_two_ground_harmonic_corner_single_active_edges": (THREE, dict(panels_per_edge=16, signal_index=2)),
    "solve_open_rectangle": ([SQUARE, SECOND], dict(panels_per_edge=8, ground_indices=(1,))),
}
FAST = [name for name in CASES if "harmonic" not in name]


def _internal(name):
    module, renames = INTERNAL[name]
    return getattr(__import__(f"galerkin.{module}", fromlist=[name]), name), renames


def _internal_kwargs(kwargs, renames):
    return {renames.get(k, k): v for k, v in kwargs.items()}


def _same(a, b, path="result"):
    """Bit-for-bit equality of two result records, recursively."""
    assert type(a) is type(b), path
    if dataclasses.is_dataclass(a):
        for field in dataclasses.fields(a):
            _same(getattr(a, field.name), getattr(b, field.name), f"{path}.{field.name}")
    elif isinstance(a, np.ndarray):
        assert a.dtype == b.dtype and a.shape == b.shape, path
        assert np.array_equal(a, b, equal_nan=a.dtype.kind in "fc"), path
        assert a.tobytes() == b.tobytes(), path
    elif isinstance(a, (tuple, list)):
        assert len(a) == len(b), path
        for i, (x, y) in enumerate(zip(a, b)):
            _same(x, y, f"{path}[{i}]")
    elif isinstance(a, dict):
        assert a.keys() == b.keys(), path
        for k in a:
            _same(a[k], b[k], f"{path}[{k!r}]")
    else:
        assert a == b or (a != a and b != b), path


def test_the_public_names_are_the_nine_solvers_and_their_four_result_classes():
    solvers = [n for n in pe.__all__ if n.startswith("solve_")]
    assert sorted(solvers) == sorted(INTERNAL) and len(pe.__all__) == 13
    for name in ("RectangleBoundaryResult", "TwoGroundRectangleResult", "TwoGroundRectangleEdgesResult",
                 "OpenRectangleResult"):
        assert name in pe.__all__ and getattr(pe, name).__module__ != pe.__name__   # re-exported unchanged


@pytest.mark.parametrize("name", list(INTERNAL))
def test_signatures_take_box_size_and_keep_the_internal_defaults(name):
    public = inspect.signature(getattr(pe, name)).parameters
    internal, renames = _internal(name)
    inner = inspect.signature(internal).parameters
    assert list(public)[0] == "polygons" and public["box_size"].kind is inspect.Parameter.KEYWORD_ONLY
    assert public["box_size"].default is inspect.Parameter.empty
    assert "width" not in public and "height" not in public
    assert {renames.get(n, n) for n in public} - {"box_size"} == set(inner) - {"width", "height"}
    for n, p in public.items():
        if n != "box_size":
            assert p.default == inner[renames.get(n, n)].default, n


@pytest.mark.parametrize("name", list(INTERNAL))
def test_the_internal_solver_receives_the_callers_numbers(name, monkeypatch):
    internal, renames = _internal(name)
    module = inspect.getmodule(internal)
    seen = {}
    sentinel = object()

    def record(polygons, **kwargs):
        seen.update(kwargs, polygons=polygons)
        return sentinel

    monkeypatch.setattr(module, name, record)
    polygons, kwargs = CASES[name]
    width, height = np.float64(WIDTH), np.float64(HEIGHT)
    assert getattr(pe, name)(polygons, box_size=(width, height), **kwargs) is sentinel
    assert seen.pop("polygons") is polygons
    assert seen.pop("width") is width and seen.pop("height") is height
    defaults = {n: p.default for n, p in inspect.signature(internal).parameters.items()
                if p.default is not inspect.Parameter.empty}
    assert seen == {**defaults, **_internal_kwargs(kwargs, renames)}


@pytest.mark.parametrize("name", FAST)
def test_results_equal_the_internal_solver_bit_for_bit(name):
    internal, renames = _internal(name)
    polygons, kwargs = CASES[name]
    public = getattr(pe, name)(polygons, box_size=(WIDTH, HEIGHT), **kwargs)
    direct = internal(polygons, width=WIDTH, height=HEIGHT, **_internal_kwargs(kwargs, renames))
    _same(public, direct)


def test_box_size_may_be_an_array():
    polygons, kwargs = CASES["solve_two_ground_rectangle"]
    a = pe.solve_two_ground_rectangle(polygons, box_size=np.array([WIDTH, HEIGHT]), **kwargs)
    _same(a, pe.solve_two_ground_rectangle(polygons, box_size=[WIDTH, HEIGHT], **kwargs))


@pytest.mark.parametrize("name", list(INTERNAL))
@pytest.mark.parametrize("box_size", ["8 mm, 2 mm", ("8 mm", "2 mm"), (WIDTH, "2 mm")])
def test_text_box_size_raises_type_error(name, box_size):
    polygons, kwargs = CASES[name]
    with pytest.raises(TypeError, match=r"^box_size: SI numbers only"):
        getattr(pe, name)(polygons, box_size=box_size, **kwargs)


@pytest.mark.parametrize("box_size", [(WIDTH,), (WIDTH, HEIGHT, 1.0), np.zeros((2, 1)), WIDTH, None])
def test_box_size_needs_two_side_lengths(box_size):
    with pytest.raises(ValueError, match=r"^box_size must hold two side lengths \(width, height\) in m$"):
        pe.solve_grounded_rectangle([SQUARE], box_size=box_size)


@pytest.mark.parametrize("box_size", [(0.0, HEIGHT), (WIDTH, -1.0), (np.inf, HEIGHT), (True, HEIGHT),
                                      (WIDTH, np.nan), (WIDTH, 1j)])
def test_box_size_needs_finite_positive_lengths(box_size):
    with pytest.raises(ValueError, match=r"^box_size must hold two finite positive side lengths"):
        pe.solve_grounded_rectangle([SQUARE], box_size=box_size)


def test_refusals_name_the_public_arguments():
    with pytest.raises(ValueError, match=r"^box_size: width/height must lie in"):
        pe.solve_two_ground_rectangle([SQUARE], box_size=(WIDTH, 1.0))
    with pytest.raises(ValueError, match=r"^ground_indices must hold distinct conductor indices in \[0, 1\]$"):
        pe.solve_open_rectangle([SQUARE, SECOND], box_size=(WIDTH, HEIGHT), ground_indices=(5,))
    with pytest.raises(ValueError, match=r"^ground_indices must be a sequence"):
        pe.solve_open_rectangle([SQUARE, SECOND], box_size=(WIDTH, HEIGHT), ground_indices=1)
    with pytest.raises(ValueError, match=r"^signal_indices must select exactly two"):
        pe.solve_two_ground_harmonic_corner_guard_edges(THREE, box_size=(WIDTH, HEIGHT), signal_indices=(0,))
    with pytest.raises(ValueError, match=r"^signal_indices entries must be an integer in \[0, 2\]$"):
        pe.solve_two_ground_harmonic_corner_guard_edges(THREE, box_size=(WIDTH, HEIGHT), signal_indices=(0, 3))
    with pytest.raises(ValueError, match=r"^signal_indices must be distinct$"):
        pe.solve_two_ground_harmonic_corner_guard_edges(THREE, box_size=(WIDTH, HEIGHT), signal_indices=(1, 1))
    with pytest.raises(ValueError, match=r"^signal_index must be an integer in \[0, 2\]$"):
        pe.solve_two_ground_harmonic_corner_single_active_edges(THREE, box_size=(WIDTH, HEIGHT), signal_index=3)
    for name in INTERNAL:
        with pytest.raises(TypeError):
            getattr(pe, name)([SQUARE], WIDTH)                       # box_size is keyword-only
