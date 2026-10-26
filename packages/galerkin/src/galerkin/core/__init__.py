# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The shared layer under galerkin's physics modules.

Input checks (``checks``), P1 triangle mesh checks and element data
(``triangles``), boundary sampling and loads (``boundary``), source loads
(``loads``), Dirichlet constraints (``constraints``) and triangle quadrature
(``quadrature``). Physics modules import these public names rather than each
other's private helpers. Import the submodules explicitly; nothing here is
re-exported from ``galerkin``.
"""
