# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Session files of version 8 read by an independent reader: the digests and the number text.

The fixture ``studio_session_fixtures/multiphysics-v8.json`` is what Studio's writer
(``workspace-multiphysics-session.mjs``) writes for a fixed state; the JavaScript module test
checks that it still does. Here Python reads it with ``json`` and writes it again with its own
writer: ECMAScript's Number::toString for every number, except negative zero as ``-0.0``, and
the keys in their order (the file) or sorted (the digest). Every run and every without-heater
result must carry ``sha256:`` of its sorted-key text without the digest, computed with hashlib.
The digest detects a damaged or hand-edited file; it is not an authentication.
"""

from __future__ import annotations

import hashlib
import json
import math
from decimal import Decimal
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "studio_session_fixtures" / "multiphysics-v8.json"


def ecmascript_number(x) -> str:
    """Number::toString (ECMA-262, 6.1.6.1.20) of a double, with negative zero as -0.0."""
    if isinstance(x, bool):
        raise TypeError("not a number")
    if isinstance(x, int):
        if abs(x) >= 10**21:
            return ecmascript_number(float(x))
        return str(x)
    if not math.isfinite(x):
        raise ValueError("a session holds no NaN or infinity")
    if x == 0:
        return "-0.0" if math.copysign(1.0, x) < 0 else "0"
    sign = "-" if x < 0 else ""
    # repr gives the shortest round-trip digits: |x| = int(digits) × 10^exponent
    parts = Decimal(repr(abs(x))).as_tuple()
    digits = "".join(map(str, parts.digits))
    stripped = digits.rstrip("0")
    exponent = parts.exponent + len(digits) - len(stripped)
    digits, k = stripped, len(stripped)
    n = exponent + k                                     # |x| = 0.digits × 10^n
    if k <= n <= 21:
        return sign + digits + "0" * (n - k)
    if 0 < n <= 21:
        return sign + digits[:n] + "." + digits[n:]
    if -6 < n <= 0:
        return sign + "0." + "0" * (-n) + digits
    e = n - 1
    mantissa = digits if k == 1 else digits[0] + "." + digits[1:]
    return f"{sign}{mantissa}e{'+' if e >= 0 else '-'}{abs(e)}"


def write(value, *, sort: bool) -> str:
    if value is None or isinstance(value, bool):
        return json.dumps(value)
    if isinstance(value, (int, float)):
        return ecmascript_number(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ",".join(write(v, sort=sort) for v in value) + "]"
    keys = sorted(value) if sort else list(value)
    return "{" + ",".join(json.dumps(k, ensure_ascii=False) + ":" + write(value[k], sort=sort) for k in keys) + "}"


def digest(record: dict) -> str:
    rest = {k: v for k, v in record.items() if k != "digest"}
    return "sha256:" + hashlib.sha256(write(rest, sort=True).encode("utf-8")).hexdigest()


@pytest.mark.parametrize("x, text", [
    (0.0, "0"), (-0.0, "-0.0"), (300.0, "300"), (0.1, "0.1"), (1e21, "1e+21"), (1e20, "100000000000000000000"),
    (1e-7, "1e-7"), (1.5e-6, "0.0000015"), (5e-324, "5e-324"), (1.7976931348623157e308, "1.7976931348623157e+308"),
    (-1.5e-310, "-1.5e-310"), (2.4456501286415855, "2.4456501286415855"), (123456789012345680000.0, "123456789012345680000"),
    (2**53 - 1, "9007199254740991"), (1.8e-5, "0.000018"), (-2.5e-7, "-2.5e-7"),
])
def test_ecmascript_number_text(x, text):
    """The reference writer itself, against values whose ECMAScript text is known."""
    assert ecmascript_number(x) == text


def test_every_digest_recomputes_with_hashlib():
    session = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert (session["format"], session["version"], session["application"]) == ("openphysics-studio-session", 8, "multiphysics")
    records = [*session["runs"], *session["baselines"].values()]
    assert len(records) == 3
    for record in records:
        assert record["digest"] == digest(record)
    # a changed value no longer matches
    changed = json.loads(json.dumps(session["runs"][0]))
    changed["result"]["physics"]["modes1"]["effective_index"]["values"][0][0] += 1e-15
    assert changed["digest"] != digest(changed)


def test_the_file_text_is_the_number_rules_written_in_key_order():
    """Python reads the file and writes the same bytes: negative zero, a subnormal, 1e21 and
    integers above 2^31 keep their value and their text."""
    text = FIXTURE.read_text(encoding="utf-8")
    session = json.loads(text)
    assert write(session, sort=False) == text
    timing = session["runs"][0]["result"]["timing"]
    assert math.copysign(1.0, timing["heat1"]) < 0 and timing["heat1"] == 0
    assert timing["modes1"] == 5e-324 and timing["total"] == 1e21 and timing["big"] == 2**53 - 1
    assert session["runs"][1]["maps"] == "not kept" and "mesh" not in session["runs"][1]["result"]
    assert session["runs"][1]["counts"] == {"nodes": 4, "triangles": 2}
