# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Slice S1 of the guided / leaky notes of open-boundary modes (decision D1): Studio's index table
at the run's wavelength. INDEX_TABLE in workspace-open-boundary.mjs holds the real index of the ten
Studio materials from 1400 to 1700 nm every 10 nm (physmat, five decimals), and indexAt(material,
wavelength in nm) interpolates it linearly. Pre-registered: indexAt is within 1e-4 of physmat at the
301 wavelengths 1400, 1401, ..., 1700 nm for every material (measured on main 2318e5f: at most
7.5e-6, indium phosphide). The 1550 nm table INDEX_1550 is unchanged; the order of the ten materials
over the same range is test_studio_round22.py."""
import json
import subprocess

import physmat
from open_boundary_fixtures import STATIC, node

WAVELENGTHS_NM = tuple(range(1400, 1701))
TOLERANCE = 1e-4


def _node(script):
    done = subprocess.run([node(), "--input-type=module", "-e", script, (STATIC / "workspace-open-boundary.mjs").as_uri(),
                           (STATIC / "workspace-shapes.mjs").as_uri()], capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def _physmat(name, nm):
    return complex(physmat.material(name.removeprefix("physmat:")).refractive_index(vacuum_wavelength=nm * 1e-9)).real


def test_the_index_table_covers_the_ten_materials_from_1400_to_1700_nm_every_10_nm():
    out = _node("const B = await import(process.argv[1]), S = await import(process.argv[2]);"
                "process.stdout.write(JSON.stringify({table: B.INDEX_TABLE, materials: S.SHAPE_MATERIALS}));")
    table, materials = out["table"], out["materials"]
    assert (table["from_nm"], table["to_nm"], table["step_nm"]) == (1400, 1700, 10)
    assert set(table["index"]) == set(materials)
    for display, name in materials.items():
        values = table["index"][display]
        assert len(values) == 31, display
        # each entry is physmat at its wavelength to five decimals
        assert values == [round(_physmat(name, 1400 + 10 * k), 5) for k in range(31)], display


def test_index_at_matches_physmat_within_1e_4_at_301_wavelengths():
    out = _node("const B = await import(process.argv[1]), S = await import(process.argv[2]);"
                f"const nm = {list(WAVELENGTHS_NM)};"
                "process.stdout.write(JSON.stringify({materials: S.SHAPE_MATERIALS, at: Object.fromEntries(Object.keys(S.SHAPE_MATERIALS).map(m => [m, nm.map(x => B.indexAt(m, x))]))}));")
    worst = 0.0
    for display, name in out["materials"].items():
        for nm, value in zip(WAVELENGTHS_NM, out["at"][display]):
            error = abs(value - _physmat(name, nm))
            worst = max(worst, error)
            assert error <= TOLERANCE, (display, nm, value)
    print(f"\nS1 largest |indexAt - physmat| over 301 wavelengths: {worst:.2e}")


def test_index_at_outside_the_table_or_for_another_material_is_null():
    out = _node("const B = await import(process.argv[1]);"
                "process.stdout.write(JSON.stringify([B.indexAt('Silicon', 1399), B.indexAt('Silicon', 1701), B.indexAt('Gold', 1550),"
                " B.indexAt('Silicon', Number.NaN), B.indexAt('Silicon', 1550), B.INDEX_1550.Silicon]));")
    assert out[:4] == [None, None, None, None]
    # at 1550 nm the table and the 1550 nm table agree to the latter's four decimals
    assert abs(out[4] - out[5]) <= 5e-5
