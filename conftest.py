# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Make one pytest run test the packages in *this* checkout.

The eight implementation packages are installed editable, and an editable install points at the
directory it was installed from. In a git worktree that directory is the other
checkout, so without this the suite imports the main checkout's library while
collecting this one's tests, and reports on code that is not the code under test:
green for a change that is not there, red for one that is.

Putting each package's src/ folder at the front of sys.path makes the import
follow the tests. In the main checkout it resolves to the same files the editable
install already points at, so nothing changes there.
"""

import pathlib
import sys

PACKAGES = pathlib.Path(__file__).resolve().parent / "packages"

for _root in sorted(PACKAGES.iterdir()):
    if (_root / "src").is_dir():
        sys.path.insert(0, str(_root / "src"))
