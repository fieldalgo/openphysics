# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""``import simcase`` stays light until a public name is used."""

import subprocess
import sys


def _run(code: str) -> list[str]:
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                          check=True).stdout.split()


HEAVY = "('shapely', 'scipy', 'galerkin', 'meshine', 'matplotlib')"


def test_import_alone_loads_no_solver_chain():
    out = _run(f"import sys, simcase; print(sorted(m for m in {HEAVY} if m in sys.modules))")
    assert out == ["[]"]


def test_the_first_public_name_loads_the_runner_chain():
    out = _run("import sys, simcase; simcase.Document; "
               "print(all(m in sys.modules for m in ('shapely', 'scipy', 'meshine', 'simcase.runner')))")
    assert out == ["True"]


def test_public_names_and_star_import_still_work():
    import simcase
    from simcase import Document, examples, run
    assert simcase.__version__ == "0.0.2"
    assert Document.__name__ == "Document" and callable(run) and "soi_strip" in examples.EXAMPLES
    namespace: dict = {}
    exec("from simcase import *", namespace)
    assert set(simcase.__all__) <= set(namespace)
