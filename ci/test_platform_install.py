# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""External -I consumer: installed bytes/origins and portable public API smoke."""
__test__ = False  # Standalone installed consumer, explicitly executed by the driver.

import hashlib
import importlib
import json
import os
from pathlib import Path
import platform
import sys

import numpy as np
from meshine import Domain, box_sides, generate, rectangle


def test_installed_origins_all_package_bytes_and_bundled_assets():
    assert sys.flags.isolated
    manifest = json.loads(Path(os.environ["OPENPHYSICS_INSTALL_MANIFEST"]).read_text(encoding="utf-8"))
    prefix = Path(sys.prefix).resolve()
    report = {"platform": platform.platform(), "python": sys.version,
              "external_gmsh": "not executed; parser/import coverage only",
              "modules": {}, "files": {}}
    roots = {}
    for name in (*manifest["packages"], "numpy", "scipy", "shapely", "yaml", "matplotlib",
                 "galerkin.thermal", "simcase.schema", "simcase.thermal", "simcase.cli"):
        module = importlib.import_module(name)
        origin = Path(module.__file__).resolve()
        assert origin.is_relative_to(prefix), (name, str(origin))
        report["modules"][name] = {"origin": str(origin),
                                  "sha256": hashlib.sha256(origin.read_bytes()).hexdigest()}
        if name in manifest["packages"]:
            roots[name] = origin.parent
    for relative, expected in manifest["files"].items():
        root, *parts = relative.split("/")
        path = roots[root].joinpath(*parts)
        assert path.resolve().is_relative_to(prefix)
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == expected, relative
        report["files"][relative] = actual
    Path(os.environ["OPENPHYSICS_INSTALL_REPORT"]).write_text(
        json.dumps(report, indent=2)+"\n", encoding="utf-8")


def test_public_mesh_generation_has_ccw_unit_area():
    domain = Domain(size=0.3)
    domain.add_region("domain", rectangle(0, 0, 1, 1))
    mesh = generate(domain, box_sides(0, 1, 0, 1), min_angle=28)
    nodes = mesh.nodes[mesh.triangles]
    a, b = nodes[:, 1]-nodes[:, 0], nodes[:, 2]-nodes[:, 0]
    area = (a[:, 0]*b[:, 1]-a[:, 1]*b[:, 0])/2
    assert np.all(area > 0)
    np.testing.assert_allclose(area.sum(), 1.0, rtol=0, atol=1e-12)


if __name__ == "__main__":
    test_installed_origins_all_package_bytes_and_bundled_assets()
    test_public_mesh_generation_has_ccw_unit_area()
    print("Installed byte/origin and public mesh smoke completed")
