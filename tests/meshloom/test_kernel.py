# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""meshloom's compiled kernel on this platform (V30 of the pre-registered 3D plan):
the extension loads, was built as the package's version, and computes IEEE double
products with plain multiply and add. The exact predicates of the mesher rely on the
error-free product, which a fused multiply-add or a non-default rounding mode would
break; the probe compares the kernel's (product, error) pairs with exact rationals.
"""

import random
from fractions import Fraction

import pytest

meshloom = pytest.importorskip("meshloom")
if not meshloom.kernel_available():
    pytest.skip("meshloom's compiled kernel is not built in this environment", allow_module_level=True)


def test_kernel_version_is_the_package_version():
    assert meshloom.kernel_version() == meshloom.__version__


def test_kernel_is_an_abi3_extension_module():
    from meshloom import _kernel
    name = _kernel.__file__.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    assert name in ("_kernel.abi3.so", "_kernel.pyd"), name


def test_two_product_is_exact():
    from meshloom import _kernel
    rng = random.Random(20261030)
    # Dekker's split is exact for |x| < 2**996 and products whose error stays normal; the
    # kernel scales its input to unit size, far inside that range.
    cases = [(1.0 + 2.0 ** -52, 1.0 + 2.0 ** -52), (0.1, 0.1), (1e300, 1e-300), (3.0, 1.0 / 3.0),
             (2.0 ** 995 * (1 + 2.0 ** -40), 0.75), (-0.0, 5.0)]
    cases += [(rng.uniform(-1, 1) * 2.0 ** rng.randint(-200, 200), rng.uniform(-1, 1) * 2.0 ** rng.randint(-200, 200))
              for _ in range(20000)]
    for a, b in cases:
        p, e = _kernel.two_product_probe(a, b)
        assert p == a * b, (a, b)
        assert Fraction(p) + Fraction(e) == Fraction(a) * Fraction(b), (a, b, p, e)


def test_generate3d_is_not_implemented_yet():
    with pytest.raises(NotImplementedError, match="not implemented yet"):
        meshloom.generate3d()
