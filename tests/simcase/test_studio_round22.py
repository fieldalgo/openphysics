# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Round 22 (V2): the closed window's slab warning compares Studio's 1550 nm index table
(INDEX_1550 in workspace-open-boundary.mjs, physmat at 1550 nm: test_studio_open_boundary.py). The
comparison must hold at the run's wavelength: this checks against physmat that the ten materials
keep the same order, with no tie between different materials, at every wavelength the workspace
allows (1400 to 1700 nm), so "at least the core's index" decides the same at any of them."""
import itertools
import json
import subprocess

import physmat
from open_boundary_fixtures import STATIC, node

WAVELENGTHS_NM = (1400, 1450, 1500, 1550, 1600, 1650, 1700)


def _module(name, export):
    done = subprocess.run([node(), "--input-type=module", "-e",
                           f"const M = await import(process.argv[1]); process.stdout.write(JSON.stringify(M.{export}));",
                           (STATIC / name).as_uri()], capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def test_the_material_order_of_the_slab_warning_holds_from_1400_to_1700_nm():
    table = _module("workspace-open-boundary.mjs", "INDEX_1550")
    materials = _module("workspace-shapes.mjs", "SHAPE_MATERIALS")
    assert set(table) == set(materials)
    for a, b in itertools.combinations(sorted(materials), 2):
        assert table[a] != table[b], (a, b)
        expected = table[a] > table[b]
        for nm in WAVELENGTHS_NM:
            na = complex(physmat.material(materials[a].removeprefix("physmat:")).refractive_index(vacuum_wavelength=nm * 1e-9)).real
            nb = complex(physmat.material(materials[b].removeprefix("physmat:")).refractive_index(vacuum_wavelength=nm * 1e-9)).real
            assert (na > nb) == expected and na != nb, (a, b, nm, na, nb)
