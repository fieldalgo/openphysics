"""The meshloom-route 3D estimate with thin features (``geometry_engine3d._thin_excess``).

meshloom takes one size per region, but near faces closer than ``h`` its refinement follows the
local feature size, so a thin layer meshes to about area / t^2 tetrahedra however large ``h`` is.
The estimate T = 6.3 integral(dV / s^3), s = min(h, 1.2 lfs), counts that; it is the number the
limit (``mesh.element_count_limit``) is checked against before meshing.

- G-1: Studio card 1 with t_ox in {2, 5, 10} um and h in {15, 20, 40} um: built / estimate within
  [0.5, 2.0] for every one (the old T = 6.3 sum(V/h^3) was 0.92-45).
- G-2: the stage 5 G1 box sets of seeds 0-9 at their default size (0.25 mm): the same band.
- G-4: card 1 at t_ox 2 um, h 6 um meshes to 637,456 tetrahedra (measured once, not here); the
  estimate refuses it before meshing. Under a limit of 140,000, t_ox 2 um at h 15 um (144,948
  built) is refused too, where the old estimate (44,949) let it through.
- On pull requests G-1 runs its four fastest cases; the rest of G-1 and G-2 are main-only.
- Thick features leave the estimate at 6.3 sum(V/h^3) exactly.
"""

from __future__ import annotations

import json
import os
import sys
from fractions import Fraction
from pathlib import Path

import pytest

meshloom = pytest.importorskip("meshloom")
if not meshloom.kernel_available():
    pytest.skip("meshloom's compiled kernel is not built in this environment", allow_module_level=True)

import simcase  # noqa: E402
from simcase import geometry_engine3d as engine  # noqa: E402
from simcase.geometry_document import GeometryError  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
from test_geometry_engine3d import doc, g1_doc, oracle_volumes  # noqa: E402

CARD1 = (Path(simcase.__file__).parent / "studio" / "static" / "model3d-layer-stack-3d.json")
BAND = (0.5, 2.0)
FULL = os.environ.get("OPENPHYSICS_GEOMETRY3D_FULL") == "1"
#: G-1's (t_ox um, h um) cases on pull requests: the four that mesh fastest (7k-33k tetrahedra)
G1_CASES = [(10, 40), (5, 40), (10, 20), (5, 20)]
#: the other five, main pushes and manual dispatch only (42k-145k tetrahedra)
G1_FULL_CASES = [(2, 40), (2, 20), (2, 15), (5, 15), (10, 15)]


def card1(t_ox_um, h_um):
    d = json.loads(CARD1.read_text())
    d["geometry"]["parameters"]["t_ox"]["value"] = f"{t_ox_um} um"
    d["mesh"]["element_size"] = f"{h_um} um"
    return d


def ratio(d):
    built = len(engine.build_mesh3d(d).mesh.tets)
    estimate = simcase.estimate_mesh3d(d).tetrahedra
    return built, estimate, built / estimate


@pytest.mark.slow
@pytest.mark.parametrize("t_ox,h", G1_CASES)
def test_g1_card1_thin_oxide_built_over_estimate_in_band(t_ox, h):
    built, estimate, r = ratio(card1(t_ox, h))
    print(f"card 1 t_ox {t_ox} um h {h} um: estimate {estimate}, built {built}, x{r:.2f}")
    assert BAND[0] <= r <= BAND[1], f"G-1 t_ox {t_ox} h {h}: built {built} / estimate {estimate} = {r:.2f}"


# G-1's other five cases and G-2 are collected only with OPENPHYSICS_GEOMETRY3D_FULL=1 (the CI job
# geometry3d-full, which checks that they ran): about 2 min of meshing together.
if FULL:
    @pytest.mark.slow
    @pytest.mark.parametrize("t_ox,h", G1_FULL_CASES)
    def test_g1_full_card1_thin_oxide_built_over_estimate_in_band(t_ox, h):
        test_g1_card1_thin_oxide_built_over_estimate_in_band(t_ox, h)

    @pytest.mark.slow
    @pytest.mark.parametrize("seed", range(10))
    def test_g2_g1_box_sets_built_over_estimate_in_band(seed):
        d, boxes, background = g1_doc(seed)
        assert oracle_volumes(boxes, background), f"seed {seed}: every region is void"
        built, estimate, r = ratio(d)
        print(f"G1 seed {seed}: estimate {estimate}, built {built}, x{r:.2f}")
        assert BAND[0] <= r <= BAND[1], f"G-2 seed {seed}: built {built} / estimate {estimate} = {r:.2f}"


def test_g4_a_thin_oxide_over_the_limit_is_refused_before_meshing():
    """Card 1 at t_ox 2 um and h 6 um meshed to 637,456 tetrahedra (measured once, 2026-11-28: 110 s,
    459 MiB peak RSS); the default limit refuses it from the estimate (833,000) alone."""
    with pytest.raises(GeometryError) as refused:
        simcase.estimate_mesh3d(card1(2, 6))
    assert refused.value.code == "E-MESH-ESTIMATE"
    assert "the limit is 600000 (mesh.element_count_limit)" in str(refused.value)


def test_a_thin_oxide_that_meshes_over_its_limit_is_refused_before_meshing():
    """Card 1 at t_ox 2 um and h 15 um meshes to 144,948 tetrahedra (G-1's case); under a limit of
    140,000 the old estimate (44,949) let it through to meshing, the new one refuses it first."""
    d = card1(2, 15)
    d["mesh"]["element_count_limit"] = 140000
    with pytest.raises(GeometryError) as refused:
        simcase.estimate_mesh3d(d)
    assert refused.value.code == "E-MESH-ESTIMATE"
    with pytest.raises(GeometryError) as also:
        engine.build_mesh3d(d)
    assert str(also.value) == str(refused.value)


def test_thick_features_keep_the_volume_estimate():
    """No face pair closer than h / 1.2: the estimate is 6.3 sum(V/h^3), unchanged."""
    d = doc([{"name": "b", "type": "box", "xmin": 2, "xmax": 6, "ymin": 2, "ymax": 6, "zmin": 0, "zmax": 2,
              "material": "m"}], domain=(0, 10, 0, 10, 0, 4), size="0.4 mm")
    found = simcase.estimate_mesh3d(d)
    h = Fraction(4, 10)
    expected = 6.3 * float(Fraction(10 * 10 * 4) / h ** 3)
    assert found.tetrahedra == round(expected)


def test_a_thin_layer_counts_more_than_its_volume():
    """A 10 um layer at h 40 um: the thin excess is positive and grows about as 1 / t^2."""
    est = {t: simcase.estimate_mesh3d(card1(t, 40)).tetrahedra for t in (2, 5)}
    assert est[2] > 4 * est[5] > 4 * 6.3 * 200 * 200 * 612 / 40 ** 3

