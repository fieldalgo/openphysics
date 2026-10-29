# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The shared layer under galerkin's physics modules.

Input checks (``checks``), P1 triangle mesh checks and element data
(``triangles``), P1 tetrahedron element data (``tets``), edge numbering and
orientation for the Nédélec spaces (``spaces``), scalar or region-table materials (``materials``, public as
``galerkin.materials``), boundary sampling and loads (``boundary``), source loads
(``loads``), Dirichlet constraints (``constraints``) and triangle quadrature
(``quadrature``). The array layer dispatches on NumPy, JAX and PyTorch in one
place (``backend``), builds element matrices and vectors (``kernels``) and
places them (``forms``), holds assembled matrices (``sparse``) and solves them
with a hand-written adjoint so JAX and PyTorch can differentiate (``solve``).
Checks, boundary sampling and loads keep JAX and PyTorch values live only when
asked (``live=True``, ``real_value``); otherwise they refuse them.
Physics modules import these public names rather than each other's private
helpers. This layer imports only the mesh types (``mesh``, ``mesh3d``), never
the public assembly modules (they sit on core), physics or coupling. Import the
submodules explicitly: ``galerkin`` re-exports only ``EdgeSpace`` and ``EdgeSpace3D``
(through ``edge`` and ``edge3d``) and ``tet_gradients`` (through ``assembly3d``).
"""
