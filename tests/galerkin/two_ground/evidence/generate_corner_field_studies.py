# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Write corner-field-studies.json: each study's recorded-resolution quantities and outcome.

Run from the repository root, with the study outcomes from the JUnit XML of a run of the
studies (``OPENPHYSICS_PANEL_STUDIES=1``; their ``record_property`` values)::

    python tests/galerkin/two_ground/evidence/generate_corner_field_studies.py \
        --junit studies.xml --source "<where the study run happened>"

The quantities are recomputed here at the resolution each module's ``calculated`` uses by
default (the one its regular tests solve: 32 panels per edge for the harmonic fields, 64 for
the linear field, 8 mm width), which the regular tests compare with. A study outcome missing from the XML is an error. Without
``--junit`` the record keeps each ``study`` null and says so in ``study_source``: the
values are then only those the next study run must confirm.
"""
import argparse
import ast
import datetime
import inspect
import json
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT / "tests" / "_support"), str(ROOT / "tests" / "galerkin")]

import numpy as np  # noqa: E402

MODULES = {
    "test_laplace_corner_harmonic_field": "harmonic_three_active_resolution",
    "test_laplace_corner_harmonic_guard_field": "harmonic_guard_resolution",
    "test_laplace_corner_harmonic_single_active_field": "harmonic_single_active_resolution",
    "test_laplace_corner_linear_field": "linear_corner_resolution",
}
QUANTITIES = ["capacitance_per_permittivity", "edge_current_gram", "grouped_current_gram"]


def outcomes(paths):
    found = {}
    for path in paths:
        for case in ET.parse(path).getroot().iter("testcase"):
            for prop in case.iter("property"):
                if prop.get("name") in MODULES.values():
                    index, panel, changes = ast.literal_eval(prop.get("value"))
                    found[(prop.get("name"), index)] = dict(panel_changes=panel, outer_changes=changes,
                                                           seconds=float(case.get("time", 0) or 0))
    return found


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--junit", nargs="+", default=[])
    parser.add_argument("--source", required=True)
    args = parser.parse_args(argv)
    study = outcomes(args.junit)
    import importlib
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                            check=True).stdout.strip()
    record = dict(
        schema="openphysics.corner-field-studies/1",
        description=("Quantities at the resolution the regular tests solve (panels_per_edge, width_m per case) and "
                     "convergence-study outcomes of the corner field tests; see tests/_support/panel_studies.py."),
        quantities=QUANTITIES, generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        product_commit=commit, study_source=args.source,
        environment=dict(python=platform.python_version(), numpy=np.__version__, os=platform.platform()),
        command="python tests/galerkin/two_ground/evidence/generate_corner_field_studies.py"
                + (" --junit <study JUnit XML>" if args.junit else "") + " --source <study run>",
        modules={})
    for name, prop in MODULES.items():
        module = importlib.import_module(name)
        cases = []
        for index in range(len(module.GEOMETRIES)):
            if args.junit and (prop, index) not in study:
                raise SystemExit(f"{name}[{index}]: no study outcome {prop!r} in the JUnit XML")
            values = module.quantities(module.calculated(index))
            cases.append(dict(case=module.GEOMETRIES[index]["case"], study=study.get((prop, index)),
                              panels_per_edge=inspect.signature(module.calculated).parameters["count"].default,
                              width_m=inspect.signature(module.calculated).parameters["width"].default,
                              **{q: np.asarray(v).tolist() for q, v in zip(QUANTITIES, values)}))
        record["modules"][name] = dict(cases=cases)
    out = Path(__file__).with_name("corner-field-studies.json")
    out.write_text(json.dumps(record, indent=1, allow_nan=False) + "\n", encoding="utf-8")
    print("written", out)


if __name__ == "__main__":
    sys.exit(main())
