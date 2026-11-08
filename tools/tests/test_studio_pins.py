# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The Studio pins of the platform check are the Linux validation versions."""
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]


def pins(name):
    lines = (TOOLS / name).read_text(encoding="utf-8").splitlines()
    return dict(line.split("==", 1) for line in map(str.strip, lines) if line and not line.startswith("#"))


def test_studio_pins_match_the_linux_pins():
    studio, linux = pins("requirements-py312-studio.txt"), pins("requirements-py312-linux.txt")
    assert studio, "no Studio pins"
    assert {name: linux.get(name) for name in studio} == studio
