# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""The quantity registry and unit converter documents use: a re-export of ``physmat.units``.

    from simcase.quantities import q, convert, menu, quantity, names
    q("200 GPa", "youngs_modulus")       # 200000000000.0 (Pa)
    menu("element_size")                 # the units an element size may be written in

The registry, its unit menus, sign sentences and diagnostic codes live in physmat
(docs/packages/physmat/units.md); simcase only maps document paths to its quantities
(``simcase.slots``). This module replaces ``simcase.unit_vocabulary`` when the format 0.2
reader is retired.
"""

from __future__ import annotations

from physmat.units import (DIAGNOSTIC_CODES, LENGTH_UNITS, convert, convert_array, convert_complex, display_groups,
                           menu, q, q_array, quantity)
from physmat.units import format, names  # noqa: A004 - format is left out of __all__, as in physmat.units
from physmat.units import format as format_quantity

#: ``format`` and ``names`` are left out, so a star import hides neither the builtin nor
#: another ``names``; call them as ``quantities.format`` and ``quantities.names``
__all__ = ["q", "q_array", "convert", "convert_array", "convert_complex", "menu", "quantity", "format_quantity",
           "display_groups", "LENGTH_UNITS", "DIAGNOSTIC_CODES"]
