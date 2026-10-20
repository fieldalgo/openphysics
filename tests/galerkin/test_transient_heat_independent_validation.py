# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Independent transient heat acceptance entry point for source pytest runs."""
from transient_heat_independent_cases import (
    TestTransientHeatIndependentCore,
    TestTransientHeatIndependentPDE,
    TestTransientHeatIndependentContract,
    TestTransientHeatIndependentWrongRuntime,
)
