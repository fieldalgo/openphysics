# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""The example gallery script (docs/gallery.md) still runs and draws what it claims."""

import importlib.util
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
import pytest
from PIL import Image

from simcase import Document

EXAMPLES = Path(__file__).resolve().parents[2] / "examples" / "simcase"


def _gallery():
    spec = importlib.util.spec_from_file_location("openphysics_gallery", EXAMPLES / "gallery.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("name", ["gallery_heated_plate.json", "gallery_box_cavity.json"])
def test_gallery_documents_validate(name):
    Document.load(EXAMPLES / name).validate()


def test_quick_gallery_renders_every_item(tmp_path):
    out = tmp_path / "gallery"
    values = _gallery().main([str(out), "--quick"])
    assert json.loads((out / "gallery.json").read_text(encoding="utf-8")) == values

    times = Document.load(EXAMPLES / "gallery_heated_plate.json")["study"]["time_s"][::8]
    plate = values["heated_plate"]
    assert plate["frames"] == len(times) and plate["end_time_s"] == times[-1]
    assert plate["max_rise_k"] > 0
    with Image.open(out / "heated_plate.webp") as animation:
        assert animation.is_animated and animation.n_frames == len(times)
    with Image.open(out / "heated_plate.png") as poster:
        assert poster.size == animation.size
    if plate["paraview"] is not None:
        steps = [float(d.get("timestep")) for d in ET.parse(out / plate["paraview"]).getroot().iter("DataSet")]
        assert steps == times

    coax = values["coax"]
    assert np.all(np.diff(coax["l2_errors"]) < 0)
    assert coax["final_rate"] > 1.8

    cavity = values["box_cavity"]
    assert cavity["indices"] == [[1, 1, 0], [2, 1, 0], [1, 0, 1], [0, 1, 1]]
    assert max(abs(e) for e in cavity["relative_error"]) < 0.01
    for name in ("coax.png", "box_cavity.png"):
        with Image.open(out / name) as image:
            assert image.format == "PNG"


def test_gallery_refuses_a_non_empty_output(tmp_path):
    (tmp_path / "keep.txt").write_text("x", encoding="utf-8")
    with pytest.raises(SystemExit):
        _gallery().main([str(tmp_path), "--quick"])
    assert [p.name for p in tmp_path.iterdir()] == ["keep.txt"]
