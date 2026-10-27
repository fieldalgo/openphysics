# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The coupling layer: fields passed between physics on one mesh.

``Field`` holds node or element values of one 2D P1 triangle mesh with an SI
unit; ``MeshSignature`` decides whether two meshes are the same; ``transfer``
carries a field to the same mesh unchanged. ``OneWayChain`` runs the stages of
a one-way workflow and labels failures by stage. The finite-element engine is
the first kernel behind this contract; see
docs/packages/galerkin/coupling.md. The API may change during 0.x.
Nothing here is re-exported from ``galerkin``.
"""
from .chain import OneWayChain
from .field import LOCATIONS, Field, MeshSignature, transfer

__all__ = ["LOCATIONS", "Field", "MeshSignature", "OneWayChain", "transfer"]
