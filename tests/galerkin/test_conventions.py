# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Check P3-4 of the galerkin step: one complex convention at the public surface, converted in one place.

galerkin's and refsol's public complex values follow exp(-i omega t); a kernel that computes in
exp(+i omega t) is reached through ``to_kernel`` and left through ``to_public`` of the package's
private ``_conventions`` module. This test is the subset of the design's T8 that the galerkin step
adopts (spec D3): sipi keeps its own convention until its own step, and tests/ is not scanned
(a test may conjugate once to compare a kernel with a public value, D8).

- **Where conjugation may appear.** An AST scan of the package code of galerkin, refsol and
  simcase. Conjugation is a name or attribute ``conj`` or ``conjugate`` (also as a word of an
  identifier: ``resolve_conj``, ``conj_physical``) or a sign flip of an imaginary part written
  ``0.0 - <x>.imag`` or ``-<x>.imag``. It may appear only in a ``_conventions`` module, in
  simcase's P2-15 boundary functions (``BOUNDARY`` of tests/simcase/test_units_em.py) and on the
  closed list ``conventions_allowlist.json``: mathematical conjugations (Hermitian products,
  phase fixes, adjoints), each with its file, function, source line, count and reason, written in
  L3 commit 10 from map M2 2.3. An entry is matched by package, file, function and its normalized
  source line (comment and spacing removed) with the count of sites on it, never by line number,
  so unrelated edits keep it; an entry that no longer matches fails, and so does any other site.
- **Passivity** of each public complex output on a passive lossy input, from the commit that
  converts it: electrostatics (L3 commit 10) and the modes (L3 commit 11b: Im(effective_index) >= 0);
  the cavity clause comes with L3 commit 12, which converts its outputs.
- **Live arrays.** A JAX and a PyTorch gradient pass through ``to_public`` and ``to_kernel``, on a
  synthetic product (L3 commit 10) and through a mode solve (L3 commit 11b).
"""
from __future__ import annotations

import ast
import dataclasses
import functools
import io
import json
import tokenize
from collections import Counter
from pathlib import Path

import numpy as np
import pytest

import galerkin
import refsol
import simcase
from galerkin._conventions import to_kernel, to_public

HERE = Path(__file__).resolve().parent
ALLOWLIST = HERE / "conventions_allowlist.json"
SCHEMA = "openphysics.conventions-allowlist/1"
PACKAGES = {name: Path(module.__file__).resolve().parent
            for name, module in (("galerkin", galerkin), ("refsol", refsol), ("simcase", simcase))}
#: the module of each package that converts between conventions (refsol's comes with its first conversion)
CONVENTIONS = "_conventions.py"
SIMCASE_P2_15 = HERE.parent / "simcase" / "test_units_em.py"


@dataclasses.dataclass(frozen=True)
class Site:
    """One conjugation in package code."""

    package: str
    file: str            # path inside the package, with "/"
    function: str        # qualified name of the enclosing function or class ("<module>" at module level)
    line: str            # the normalized source line
    lineno: int
    form: str            # the name, attribute or sign flip that matched


def _is_conj_word(name: str) -> bool:
    return any(word in ("conj", "conjugate") for word in name.lower().split("_"))


def _is_imag(node) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == "imag"


def _normalized_lines(text: str) -> dict[int, str]:
    """Each source line without its comment, with runs of spacing collapsed."""
    lines = text.splitlines()
    comments = {}
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type == tokenize.COMMENT:
            comments[tok.start[0]] = tok.start[1]
    out = {}
    for number, line in enumerate(lines, start=1):
        if number in comments:
            line = line[:comments[number]]
        out[number] = " ".join(line.split())
    return out


def conjugation_sites(package: str, file: str, text: str) -> list[Site]:
    """Every conjugation in one module's source, with its enclosing function."""
    tree = ast.parse(text)
    lines = _normalized_lines(text)
    found = []

    def visit(node, scope):
        for child in ast.iter_child_nodes(node):
            inner = scope + [child.name] if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                                                ast.ClassDef)) else scope
            form = None
            if isinstance(child, ast.Attribute) and _is_conj_word(child.attr):
                form = f".{child.attr}"
            elif isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load) and _is_conj_word(child.id):
                form = child.id
            elif (isinstance(child, ast.BinOp) and isinstance(child.op, ast.Sub) and _is_imag(child.right)
                  and isinstance(child.left, ast.Constant) and not isinstance(child.left.value, bool)
                  and child.left.value == 0):
                form = "0.0 - .imag"
            elif isinstance(child, ast.UnaryOp) and isinstance(child.op, ast.USub) and _is_imag(child.operand):
                form = "-.imag"
            if form:
                function = ".".join(scope) or "<module>"
                found.append(Site(package, file, function, lines[child.lineno], child.lineno, form))
            visit(child, inner)

    visit(tree, [])
    return found


def package_sites() -> list[Site]:
    return list(_package_sites())


@functools.lru_cache(maxsize=1)
def _package_sites() -> tuple[Site, ...]:
    out = []
    for package, root in PACKAGES.items():
        for path in sorted(root.rglob("*.py")):
            out += conjugation_sites(package, path.relative_to(root).as_posix(), path.read_text(encoding="utf-8"))
    return tuple(out)


def simcase_boundary() -> dict[str, set[str]]:
    """``BOUNDARY`` of simcase's P2-15 test: the functions that convert at simcase's surface."""
    tree = ast.parse(SIMCASE_P2_15.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "BOUNDARY" for t in node.targets):
            return {k: set(v) for k, v in ast.literal_eval(node.value).items()}
    raise AssertionError("tests/simcase/test_units_em.py defines no BOUNDARY")


def allowed_place(site: Site, boundary: dict[str, set[str]]) -> bool:
    if site.file == CONVENTIONS:
        return True
    return site.package == "simcase" and bool(set(site.function.split(".")) & boundary.get(site.file, set()))


def load_allowlist(path: Path = ALLOWLIST) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema"] == SCHEMA, data["schema"]
    for e in data["entries"]:
        assert set(e) == {"package", "file", "function", "line", "count", "source", "reason"}, e
        assert e["reason"].strip() and e["source"].strip() and e["count"] >= 1, e
    return data["entries"]


def problems(sites: list[Site], allowlist: list[dict], boundary: dict[str, set[str]]) -> list[str]:
    """Conjugations outside the allowed places, and allowlist entries that no longer match."""
    listed = Counter()
    for e in allowlist:
        key = (e["package"], e["file"], e["function"], e["line"])
        if key in listed:
            return [f"allowlist entry {key} is listed twice"]
        listed[key] = e["count"]
    found = Counter((s.package, s.file, s.function, s.line) for s in sites if not allowed_place(s, boundary))
    out = []
    for key, count in sorted(found.items()):
        if key not in listed:
            site = next(s for s in sites if (s.package, s.file, s.function, s.line) == key)
            out.append(f"conjugation outside the conversion places: {key[0]}/{key[1]}:{site.lineno} in {key[2]}: "
                       f"{key[3]} ({count} site(s); convert in _conventions, or list a mathematical one with "
                       "its reason)")
        elif listed[key] != count:
            out.append(f"allowlist entry {key} lists {listed[key]} site(s); the code has {count}")
    for key in sorted(set(listed) - set(found)):
        out.append(f"stale allowlist entry {key}: it matches no conjugation any more; remove it")
    return out


# ---- where conjugation may appear --------------------------------------------------------------------------

def test_conjugation_appears_only_in_the_conversion_places_and_the_allowlist():
    sites = package_sites()
    assert {s.package for s in sites} == set(PACKAGES)              # the scan reads all three packages
    found = problems(sites, load_allowlist(), simcase_boundary())
    assert not found, "\n".join(found)


def test_the_allowlist_is_closed_and_complete():
    entries = load_allowlist()
    sites = Counter(e["package"] for e in entries for _ in range(e["count"]))
    # map M2 2.3 on f693ae3a: 29 galerkin code lines (31 sites: two lines hold two), 17 simcase code lines (20
    # sites) and refsol's fiber.py:365; plus the two complex-step lines of galerkin.temperature_joule_heating that
    # the map's search missed (the same text in one function: one entry with count 2). Entries only ever leave.
    assert sites == {"galerkin": 33, "simcase": 20, "refsol": 1}, sites
    assert len(entries) == 48
    boundary = simcase_boundary()
    listed = {(s.package, s.file, s.lineno) for s in package_sites() if not allowed_place(s, boundary)}
    assert Counter(package for package, _, _ in listed) == {"galerkin": 31, "simcase": 17, "refsol": 1}
    conventions = [s for s in package_sites() if s.file == CONVENTIONS]
    assert {s.package for s in conventions} == {"galerkin"} and {s.function for s in conventions} == {
        "to_kernel", "to_public"}
    assert boundary == {"runner.py": {"_to_kernel", "_to_public", "_public_open_boundary", "_public_candidate",
                                      "_shown"}, "cavity.py": {"_to_kernel", "_to_public"}}


PLANTED = '''
import numpy as np


def kernel(x, xp):
    a = np.conj(x)
    b = x.conjugate()
    c = xp.conj(x) + x.conj()
    d = complex(x.real, 0.0 - x.imag)
    e = -x.imag
    f = 0 - x.imag
    g = x.detach().resolve_conj()
    return x.imag, x.real - x.imag, -2 * x.imag      # none of these is a sign flip of .imag
'''


def test_every_form_is_found_and_an_added_conjugation_fails():
    sites = conjugation_sites("galerkin", "planted.py", PLANTED)
    forms = Counter(s.form for s in sites)
    assert forms == {".conj": 3, ".conjugate": 1, "0.0 - .imag": 2, "-.imag": 1, ".resolve_conj": 1}, forms
    assert {s.function for s in sites} == {"kernel"}
    allowlist, boundary = load_allowlist(), simcase_boundary()
    found = problems(package_sites() + sites, allowlist, boundary)
    assert len(found) == 7 and all("outside the conversion places: galerkin/planted.py" in p for p in found), found
    # the same code in a _conventions module, or in a simcase P2-15 function, is allowed
    assert not problems(package_sites() + [dataclasses.replace(s, file=CONVENTIONS) for s in sites],
                        allowlist, boundary)
    moved = [dataclasses.replace(s, package="simcase", file="runner.py", function="_to_public.inner") for s in sites]
    assert not problems(package_sites() + moved, allowlist, boundary)


def test_a_stale_or_miscounted_allowlist_entry_fails():
    sites, allowlist, boundary = package_sites(), load_allowlist(), simcase_boundary()
    stale = dict(allowlist[0], line=allowlist[0]["line"] + " + 0")
    found = problems(sites, allowlist + [stale], boundary)
    assert found == [f"stale allowlist entry {(stale['package'], stale['file'], stale['function'], stale['line'])}: "
                     "it matches no conjugation any more; remove it"]
    counted = [dict(e, count=e["count"] + 1) if i == 0 else e for i, e in enumerate(allowlist)]
    assert len(problems(sites, counted, boundary)) == 1
    # an entry is matched by its function too: the same line in another function is another site
    elsewhere = [dict(e, function="elsewhere") if i == 0 else e for i, e in enumerate(allowlist)]
    assert len(problems(sites, elsewhere, boundary)) == 2


# ---- passivity: electrostatics (L3 commit 10) ---------------------------------------------------------------

def _three_conductors():
    from galerkin.mesh import rectangle_mesh
    mesh = rectangle_mesh(4.0, 2.0, 16, 8)
    x, y = mesh.nodes[:, 0], mesh.nodes[:, 1]
    row = np.isclose(y, 1.0)
    left = np.flatnonzero(row & (x >= 0.75 - 1e-12) & (x <= 1.5 + 1e-12))
    right = np.flatnonzero(row & (x >= 2.5 - 1e-12) & (x <= 3.25 + 1e-12))
    return mesh, {"left": left, "right": right}, mesh.boundary["bottom"]


@pytest.mark.parametrize("permittivity", [2.2 * (1 + 0.02j), complex(4.0, 0.3)])
def test_electrostatics_capacitance_and_energy_have_the_passive_signs(permittivity):
    """A passive lossy dielectric (Im eps_r >= 0 under exp(-i omega t)): the capacitance matrix's real
    part is positive definite and its loss matrix Im C positive semidefinite with a positive diagonal
    (design 3.9: one convention, loss is a positive imaginary part); the stored energy of real conductor
    potentials has Re W > 0 (design 4.8: stored_energy >= 0) and Im W >= 0, and equals V^T C V / 2."""
    from galerkin.electrostatics import capacitance_matrix, solve_electrostatics
    mesh, conductors, ground = _three_conductors()
    C = capacitance_matrix(mesh, relative_permittivity=permittivity, conductors=conductors, ground=ground)
    assert C.dtype == complex
    assert np.all(np.linalg.eigvalsh(C.real) > 0)
    assert np.all(np.linalg.eigvalsh(C.imag) >= 0) and np.all(np.diag(C.imag) > 0)
    volts = {"left": 1.0, "right": -0.5}
    r = solve_electrostatics(mesh, relative_permittivity=permittivity, ground=ground,
                             conductors={name: (nodes, volts[name]) for name, nodes in conductors.items()})
    W = r.stored_energy_per_depth
    assert W.real > 0 and W.imag >= 0
    V = np.array([volts["left"], volts["right"]])
    assert abs(W - 0.5 * V @ C @ V) <= 1e-10 * abs(W)
    assert np.all(np.imag(r.relative_permittivity) >= 0)            # the public permittivity is echoed back


def test_electrostatics_lossless_is_real_and_a_gain_is_refused():
    from galerkin.electrostatics import capacitance_matrix
    mesh, conductors, ground = _three_conductors()
    C = capacitance_matrix(mesh, relative_permittivity=2.2, conductors=conductors, ground=ground)
    assert C.dtype == float and np.all(np.linalg.eigvalsh(C) > 0)
    with pytest.raises(ValueError, match="Im >= 0"):
        capacitance_matrix(mesh, relative_permittivity=2.2 * (1 - 0.02j), conductors=conductors, ground=ground)


def test_refsol_electrostatics_has_the_passive_sign():
    from refsol.electrostatics import coax_capacitance, two_layer_plate_capacitance
    assert coax_capacitance(position=(1.0, 3.0), relative_permittivity=2.2 * (1 + 0.02j)).imag > 0
    assert two_layer_plate_capacitance(thickness=(3e-4, 7e-4), relative_permittivity=(2.0 * (1 + 0.01j), 5.0),
                                       length=2e-3).imag > 0


# ---- passivity: modes (L3 commit 11b) -------------------------------------------------------------------------

_WAVELENGTH = 1.55e-6


def _lossy_guide():
    from galerkin.mesh import rectangle_mesh
    mesh = rectangle_mesh(2e-6, 1e-6, 16, 8)
    centre = mesh.nodes[mesh.triangles].mean(axis=1)
    core = (np.abs(centre[:, 0] - 1e-6) < 0.4e-6) & (np.abs(centre[:, 1] - 0.5e-6) < 0.2e-6)
    return mesh, core


@pytest.mark.parametrize("core_loss,cladding_loss", [(0.05, 0.0), (0.0, 0.01), (0.2, 0.02)])
def test_modes_of_a_passive_lossy_guide_have_im_effective_index_at_least_zero(core_loss, cladding_loss):
    """A passive lossy permittivity (Im eps_r >= 0 under exp(-i omega t)) gives forward modes that decay
    along +z: Im(effective_index) >= 0 for every returned mode, > 0 for the core-guided ones, and the
    public values are the conjugates of the kernel's (exp(+i omega t): Im n_eff <= 0)."""
    from galerkin import kernels
    from galerkin.waveguide import mode_power, solve_waveguide_modes
    mesh, core = _lossy_guide()
    permittivity = np.where(core, complex(12.0, core_loss), complex(2.1, cladding_loss))
    modes = solve_waveguide_modes(mesh, relative_permittivity=permittivity, vacuum_wavelength=_WAVELENGTH,
                                  target_effective_index=3.4, search_mode_count=4)
    n = modes.effective_index
    assert n.dtype == complex and len(n) >= 2
    assert np.all(n.imag >= 0)
    assert np.all(n.imag[n.real > np.sqrt(2.1)] > 0)
    assert mode_power(modes, 0).real > 0                                # it carries power in +z
    n_kernel = kernels.solve_modes(mesh, np.conj(permittivity), 2 * np.pi / _WAVELENGTH, 3.4, 4)[0]
    assert np.all(n_kernel.imag <= 0) and np.array_equal(n, np.conj(n_kernel))


def test_a_lossless_guide_has_real_effective_indices():
    from galerkin.waveguide import solve_waveguide_modes
    mesh, core = _lossy_guide()
    modes = solve_waveguide_modes(mesh, relative_permittivity=np.where(core, 12.0, 2.1),
                                  vacuum_wavelength=_WAVELENGTH, target_effective_index=3.4, search_mode_count=4)
    assert modes.effective_index.dtype == float and np.all(modes.effective_index > 0)


def _live_mode_loss(xp, solve, scale, permittivity):
    """Im(n_eff) of the fundamental mode for a core permittivity ``permittivity(scale)``, as a live value."""
    mesh, core = _lossy_guide()
    eps = xp.where(xp.asarray(core), permittivity(scale), xp.asarray(2.1 + 0.0j, dtype=xp.complex128))
    return xp.imag(solve(mesh, eps)[0])


def _public_solve(mesh, eps):
    from galerkin.waveguide import solve_waveguide_modes
    return solve_waveguide_modes(mesh, relative_permittivity=eps, vacuum_wavelength=_WAVELENGTH,
                                 target_effective_index=3.4, search_mode_count=2).effective_index


def _kernel_solve(mesh, eps):
    from galerkin import kernels
    return kernels.solve_modes(mesh, eps, 2 * np.pi / _WAVELENGTH, 3.4, 2)[0]


def test_a_jax_gradient_passes_through_a_mode_solve():
    """The derivative of the public Im(effective_index) with respect to the core's loss passes through
    ``to_kernel`` and ``to_public``: it is the negated derivative of the kernel's Im(n_eff) with respect to
    the kernel's loss (Im eps_r = -loss), the same doubles, and positive (more loss, more decay)."""
    jax = pytest.importorskip("jax")
    jax.config.update("jax_enable_x64", True)
    jnp = jax.numpy
    public = jax.grad(lambda x: _live_mode_loss(jnp, _public_solve, x, lambda t: 12.0 + 1j * t))(0.05)
    kernel = jax.grad(lambda x: _live_mode_loss(jnp, _kernel_solve, x, lambda t: 12.0 - 1j * t))(0.05)
    assert float(public) > 0
    assert float(public) == -float(kernel)


def test_a_torch_gradient_passes_through_a_mode_solve():
    torch = pytest.importorskip("torch")
    values = []
    for solve, sign in ((_public_solve, 1.0), (_kernel_solve, -1.0)):
        x = torch.tensor(0.05, dtype=torch.float64, requires_grad=True)
        loss = _live_mode_loss(torch, solve, x, lambda t, s=sign: 12.0 + s * 1j * t)
        loss.backward()
        values.append(float(x.grad))
    assert values[0] > 0
    assert values[0] == -values[1]


# ---- the conversions -----------------------------------------------------------------------------------------

def test_the_conversions_on_numpy_values_and_scalars():
    z = np.array([1.5 + 0.25j, -0.0 + 0.0j, 2.0 - 0.0j, -3.0 - 1.0j])
    k = to_kernel(z)
    assert k.dtype == complex and np.array_equal(k, np.conj(z))
    assert np.array_equal(np.signbit(k.real), np.signbit(z.real))             # a -0.0 real part is kept
    assert not np.any(np.signbit(k.imag[1:3]))                                 # a zero imaginary part becomes +0.0
    assert np.array_equal(to_public(k), z) and to_public(k).dtype == complex
    assert to_kernel(2.2 + 0.044j) == 2.2 - 0.044j and type(to_kernel(2.2 + 0.044j)) is complex
    assert to_public(2.2 - 0.044j) == 2.2 + 0.044j and type(to_public(2.2 - 0.044j)) is complex
    real = np.array([1.0, -0.0])
    for value in (2.2, 3, None, real, "text", {"a": 1 + 1j}):
        assert to_kernel(value) is value and to_public(value) is value     # nothing real is touched


def test_a_jax_gradient_passes_through_the_conversions():
    jax = pytest.importorskip("jax")
    jax.config.update("jax_enable_x64", True)
    jnp = jax.numpy
    kernel = jnp.asarray(3.0 + 4.0j)
    assert float(jax.grad(lambda x: jnp.imag(to_public(x * kernel)))(2.0)) == -4.0
    assert float(jax.grad(lambda x: jnp.real(to_public(x * kernel)))(2.0)) == 3.0
    assert float(jax.grad(lambda x: jnp.imag(to_kernel(x * kernel)))(2.0)) == -4.0
    real = jnp.asarray([1.0, 2.0])
    assert to_public(real) is real and to_kernel(real) is real


def test_a_torch_gradient_passes_through_the_conversions():
    torch = pytest.importorskip("torch")
    for convert in (to_public, to_kernel):
        x = torch.tensor(2.0, dtype=torch.float64, requires_grad=True)
        torch.imag(convert(x * torch.tensor(3.0 + 4.0j, dtype=torch.complex128))).backward()
        assert float(x.grad) == -4.0
    real = torch.tensor([1.0, 2.0], dtype=torch.float64)
    assert to_public(real) is real and to_kernel(real) is real
