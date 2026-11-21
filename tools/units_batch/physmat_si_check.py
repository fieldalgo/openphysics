# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""P3-7: physmat's SI library API against the micrometre API it replaced (unshipped landing script).

Check P3-7 of the galerkin step (phase-3 units spec, landing L1). The baseline API
(``physmat.get``, ``Material.index``/``.eps``/``.get``, ``standard_air``) no longer exists
on the head, so this is not a committed test: it runs twice, in two processes.

1. ``baseline``: run with the baseline B's packages on ``PYTHONPATH`` (a separate worktree
   at the landing's merge base) and write its values to a ``.npz`` file;
2. ``check``: run with the head's packages and compare with that file. It prints the
   counts and exits 1 on any difference.

What it compares, on decimal-text grids of vacuum wavelengths (200-2000 nm by 1 nm and
1500-1600 nm by 0.01 nm), each intersected with a model's validity range:

- conversion: physmat's metre-to-micrometre rule on ``float(text_m)`` equals
  ``float(Fraction(text_nm) / 1000)`` at every point (and how often ``x * 1e6`` would not);
- library materials: ``refractive_index`` and ``relative_permittivity`` at
  ``float(text_m)`` against the baseline's ``Material.index`` and ``.eps`` at the micrometre
  double, bit for bit; every point outside the range raises ``OutOfRange`` on the head;
  ``valid_vacuum_wavelength`` against ``range_um`` by the decimal rule; every property at a
  temperature grid against ``Material.get``, and ``metal_thermal_conductivity`` against
  ``thermal.thermal_conductivity``, bit for bit;
- local models: every local ``refractive_index`` of the em documents of the P3-1 corpus
  (examples/simcase and the v03 fixtures), as simcase builds it, through ``physmat.kernels``
  against the baseline's ``physmat.Constant``/``Sellmeier`` model, bit for bit;
- public constructors: ``constant_model`` and ``sellmeier_model`` built from the same
  records' SI values against the kernel model simcase builds, within rel 1e-14 (margin
  reported; the four local Sellmeier fixtures are not bit-identical this way, decision D30);
- signed zero: ``constant_model`` with k = -0.0 keeps it, and evaluates as the baseline's
  ``physmat.constant(n, -0.0)``;
- air: ``ciddor_air(temperature=T, ...)`` against ``standard_air(temperature_c=T_c, ...)``,
  T and T_c both from decimal text, at the conditions the package ships (library record,
  docs, tests) and on a 1 K grid from 233.15 to 333.15 K (dry and 50 % RH): refractive index
  and permittivity on the grid, the density property, the datum and the kernel's Celsius
  and ppm, bit for bit.

Run from the repository root (``B`` is a worktree at the merge base):

    PYTHONPATH=<B's packages/*/src> python tools/units_batch/physmat_si_check.py baseline OUT.npz
    PYTHONPATH=<this tree's packages/*/src> python tools/units_batch/physmat_si_check.py check OUT.npz
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ("examples/simcase/*.json", "tools/units_batch/fixtures/v03/*.json")
SLACK_UM = 1e-12                    # the kernels' range check (physmat.dispersion.Dispersion.check_range)
CONSTRUCTOR_RTOL = 1e-14
SELLMEIER_FIXTURES = ("em_sellmeier_range", "em_sellmeier_open_lower_bound", "em_length_nm_sellmeier_rib",
                      "em_length_m_sellmeier_rib")


# ---- grids from decimal text ---------------------------------------------------------------------------------

def grids() -> dict[str, list[str]]:
    """The nanometre texts of the two grids."""
    coarse = [str(i) for i in range(200, 2001)]
    fine = [f"{i // 100}.{i % 100:02d}" for i in range(150000, 160001)]
    return {"1nm": coarse, "0.01nm": fine}


def micrometres(texts) -> np.ndarray:
    return np.array([float(Fraction(t) / 1000) for t in texts])


def metres(texts) -> np.ndarray:
    return np.array([float(f"{t}e-9") for t in texts])


def metres_of(micrometre: float) -> float:
    """A micrometre bound in metres by the decimal rule (an infinite bound stays infinite)."""
    return micrometre if np.isinf(micrometre) else float(Fraction(repr(micrometre)) / 10 ** 6)


def in_range(um: np.ndarray, bounds) -> np.ndarray:
    lo, hi = bounds
    return (um >= lo - SLACK_UM) & (um <= hi + SLACK_UM)


# ---- air conditions from decimal text ------------------------------------------------------------------------

def air_conditions() -> list[tuple[str, str, str, str, str]]:
    """(label, T in K, absolute pressure in Pa, relative humidity, CO2 in ppm), all as decimal text."""
    shipped = [
        ("library standard_air (15 C)", "288.15", "101325", "0", "450"),
        ("docs: 20 C, RH 50 %", "293.15", "101325", "0.5", "450"),
        ("docs: .at(25 C)", "298.15", "101325", "0.5", "450"),
        ("tests: 20 C, RH 50 %, 400 ppm", "293.15", "101325", "0.5", "400"),
        ("tests: 20 C dry, 400 ppm", "293.15", "101325", "0", "400"),
        ("docs: 90 kPa, -40 C", "233.15", "90000", "0", "450"),
        ("docs: 90 kPa, -5 C", "268.15", "90000", "0", "450"),
        ("docs: 90 kPa, 30 C", "303.15", "90000", "0", "450"),
        ("docs: 90 kPa, 65 C", "338.15", "90000", "0", "450"),
        ("docs: 90 kPa, 100 C", "373.15", "90000", "0", "450"),
        ("NIST table: 50 C, RH 100 %, 120 kPa", "323.15", "120000", "1", "450"),
        ("NIST table: 5 C, 100 kPa", "278.15", "100000", "0", "450"),
    ]
    grid = []
    for k in range(101):                                   # 233.15 K to 333.15 K by 1 K
        t = f"{233 + k}.15"
        grid.append((f"1 K grid {t} K dry", t, "101325", "0", "450"))
        grid.append((f"1 K grid {t} K RH 50 %", t, "101325", "0.5", "450"))
    return shipped + grid


def celsius_text(kelvin_text: str) -> str:
    return str(Fraction(kelvin_text) - Fraction("273.15"))


def float_of(fraction_text: str) -> float:
    return float(Fraction(fraction_text))


def mole_fraction_text(ppm_text: str) -> str:
    return f"{ppm_text}e-6"


# ---- the corpus documents --------------------------------------------------------------------------------------

def local_materials():
    """(document id, local name, document) of every local refractive_index of the corpus's em documents."""
    from simcase.schema import Document
    out = []
    for pattern in CORPUS:
        for path in sorted(ROOT.glob(pattern)):
            data = json.loads(path.read_text(encoding="utf-8"))
            physics = data.get("physics") or {}
            if not any(isinstance(p, dict) and p.get("type") == "em.modes2d" for p in physics.values()):
                continue
            doc = Document.load(path)
            for name, record in sorted((doc.si.get("materials") or {}).items()):
                if "refractive_index" in record:
                    out.append((f"{path.parent.name}/{path.stem}", name, doc))
    return out


def digest(values) -> str:
    a = np.ascontiguousarray(np.asarray(values))
    return hashlib.sha256(str(a.dtype).encode() + str(a.shape).encode() + a.tobytes()).hexdigest()


TEMPERATURES = np.array([4.0, 20.0, 77.0, 150.0, 293.15, 300.0, 400.0, 900.0])
METAL_RRR = {"Cu": (30.0, 100.0, 300.0), "Al": (30.0, 100.0, 300.0), "W": (30.0, 100.0)}
METAL_T = np.array([1.0, 2.0, 4.0, 10.0, 20.0, 50.0, 77.0, 100.0, 200.0, 293.15, 300.0, 500.0, 900.0])


# ---- baseline (B's API) ----------------------------------------------------------------------------------------

def baseline(out: Path) -> int:
    import physmat
    from physmat import thermal
    from simcase.modes_document import optical_material
    assert hasattr(physmat, "get") and not hasattr(physmat, "ciddor_air"), "baseline mode needs B's physmat"
    store: dict[str, np.ndarray] = {}
    meta: dict = {"materials": {}, "local": [], "air": [], "properties": {}, "metals": {}}
    g = grids()
    for name in physmat.names():
        m = physmat.get(name)
        meta["materials"][name] = {"range_um": [float(v) for v in m.range_um]}
        for key, texts in g.items():
            um = micrometres(texts)
            mask = in_range(um, m.range_um)
            store[f"mat/{name}/{key}/mask"] = mask
            store[f"mat/{name}/{key}/index"] = m.index(um[mask])
            store[f"mat/{name}/{key}/eps"] = m.eps(um[mask])
        for prop in sorted(m.properties):
            store[f"prop/{name}/{prop}/grid"] = np.asarray(m.get(prop, TEMPERATURES))
            store[f"prop/{name}/{prop}/default"] = np.asarray(m.get(prop))
    for metal, rrrs in METAL_RRR.items():
        for rrr in rrrs:
            store[f"metal/{metal}/{rrr:g}"] = np.asarray(thermal.thermal_conductivity(metal, METAL_T, rrr))
    for doc_id, ref, doc in local_materials():
        m = optical_material(doc, ref)
        entry = {"doc": doc_id, "ref": ref, "range_um": [float(v) for v in m.range_um], "model": repr(m.optical)}
        meta["local"].append(entry)
        for key, texts in g.items():
            um = micrometres(texts)
            mask = in_range(um, m.range_um)
            store[f"local/{doc_id}/{ref}/{key}/index"] = m.index(um[mask])
            store[f"local/{doc_id}/{ref}/{key}/eps"] = m.eps(um[mask])
    for n, k in ((1.5, -0.0), (1.444, -0.0), (3.48, 0.01)):
        store[f"constant/{n!r}/{k!r}"] = physmat.constant(n, k).index(micrometres(g["1nm"]))
    for label, t, p, h, ppm in air_conditions():
        m = physmat.standard_air(temperature_c=float_of(celsius_text(t)), pressure_pa=float(p),
                                 humidity=float(h), co2_ppm=float(ppm))
        entry = {"label": label, "datum": m.datum_temperature, "temperature_c": m.optical.temperature_c,
                 "co2_ppm": m.optical.co2_ppm, "density": float(m.get("density", float(t))), "grids": {}}
        for key, texts in g.items():
            um = micrometres(texts)
            mask = in_range(um, m.range_um)
            entry["grids"][key] = {"points": int(mask.sum()), "index": digest(m.index(um[mask])),
                                   "eps": digest(m.eps(um[mask]))}
        meta["air"].append(entry)
    store["meta"] = np.frombuffer(json.dumps(meta).encode("utf-8"), dtype=np.uint8)
    np.savez(out, **store)
    print(f"baseline: {len(meta['materials'])} library materials, {len(meta['local'])} local models, "
          f"{len(meta['air'])} air conditions -> {out}")
    return 0


# ---- check (the head's API) -----------------------------------------------------------------------------------

class Tally:
    def __init__(self):
        self.counts: dict[str, list[int]] = {}
        self.problems: list[str] = []

    def add(self, what: str, ok: bool, problem: str = "", n: int = 1):
        c = self.counts.setdefault(what, [0, 0])
        c[0] += n if ok else 0
        c[1] += n
        if not ok:
            self.problems.append(f"{what}: {problem}")


def same_bits(a, b) -> bool:
    a, b = np.asarray(a), np.asarray(b)
    return a.dtype == b.dtype and a.shape == b.shape and a.tobytes() == b.tobytes()


def check(path: Path) -> int:
    import physmat
    from physmat import _si, kernels
    from simcase.modes_document import optical_material
    assert hasattr(physmat, "ciddor_air") and not hasattr(physmat, "get"), "check mode needs the head's physmat"
    with np.load(path, allow_pickle=False) as data:
        base = {k: data[k] for k in data.files}
    meta = json.loads(base.pop("meta").tobytes().decode("utf-8"))
    tally = Tally()
    g = grids()

    # conversion
    for key, texts in g.items():
        exact_um = micrometres(texts)
        m = metres(texts)
        converted = _si.micrometres("vacuum_wavelength", m)
        misses = int(np.sum(converted != exact_um))
        tally.add(f"conversion {key}", misses == 0, f"{misses} misses", len(texts))
        tally.counts.setdefault(f"(x * 1e6 would miss, {key})", [int(np.sum(m * 1e6 != exact_um)), len(texts)])

    # library materials
    oor = [0, 0]
    for name, info in meta["materials"].items():
        mat = physmat.material(name)
        lo_um, hi_um = info["range_um"]
        tally.add("valid_vacuum_wavelength", mat.valid_vacuum_wavelength == (metres_of(lo_um), metres_of(hi_um)),
                  f"{name}: {mat.valid_vacuum_wavelength} vs {info['range_um']} um")
        for key, texts in g.items():
            m, um = metres(texts), micrometres(texts)
            mask = base[f"mat/{name}/{key}/mask"]
            tally.add("library range masks", np.array_equal(mask, in_range(um, mat.optical.range_um)), name)
            n = int(mask.sum())
            if n:
                tally.add("library refractive_index", same_bits(mat.refractive_index(vacuum_wavelength=m[mask]),
                                                                base[f"mat/{name}/{key}/index"]), f"{name} {key}", n)
                tally.add("library relative_permittivity",
                          same_bits(mat.relative_permittivity(vacuum_wavelength=m[mask]), base[f"mat/{name}/{key}/eps"]),
                          f"{name} {key}", n)
            for x in m[~mask]:
                for method in (mat.refractive_index, mat.relative_permittivity):
                    oor[1] += 1
                    try:
                        method(vacuum_wavelength=float(x))
                    except physmat.OutOfRange:
                        oor[0] += 1
                    else:
                        tally.problems.append(f"{name}: no OutOfRange at {x!r} m")
        for prop in sorted(mat.properties):
            tally.add("library properties", same_bits(np.asarray(mat.property(prop, temperature=TEMPERATURES)),
                                                      base[f"prop/{name}/{prop}/grid"]), f"{name} {prop}",
                      len(TEMPERATURES))
            tally.add("library properties at 293.15 K (the removed default)",
                      same_bits(np.asarray(mat.property(prop, temperature=293.15)), base[f"prop/{name}/{prop}/default"]),
                      f"{name} {prop}")
    tally.counts["library points outside the range raising OutOfRange"] = oor
    for metal, rrrs in METAL_RRR.items():
        for rrr in rrrs:
            got = physmat.metal_thermal_conductivity(metal, temperature=METAL_T, residual_resistivity_ratio=rrr)
            tally.add("metal_thermal_conductivity", same_bits(np.asarray(got), base[f"metal/{metal}/{rrr:g}"]),
                      f"{metal} RRR {rrr:g}", len(METAL_T))

    # local models through physmat.kernels, and the public constructors beside them
    worst = {}
    for entry, (doc_id, ref, doc) in zip(meta["local"], local_materials(), strict=True):
        assert (entry["doc"], entry["ref"]) == (doc_id, ref)
        mat = optical_material(doc, ref)
        tally.add("local models: same kernel model", repr(mat.optical) == entry["model"] and
                  isinstance(mat.optical, (kernels.Constant, kernels.Sellmeier)), f"{doc_id} {ref}")
        public = physmat.Material(ref, constructor(physmat, doc, ref))
        for key, texts in g.items():
            um, m = micrometres(texts), metres(texts)
            mask = in_range(um, mat.optical.range_um)
            tally.add("local range masks", np.array_equal(mask, in_range(um, public.optical.range_um)),
                      f"{doc_id} {ref} {key}")
            n = int(mask.sum())
            if not n:
                continue
            index, eps = mat.optical.index(um[mask], True), mat.optical.eps(um[mask], True)
            tally.add("local models refractive_index (kernels)", same_bits(index, base[f"local/{doc_id}/{ref}/{key}/index"]),
                      f"{doc_id} {ref} {key}", n)
            tally.add("local models relative_permittivity (kernels)",
                      same_bits(eps, base[f"local/{doc_id}/{ref}/{key}/eps"]), f"{doc_id} {ref} {key}", n)
            got = public.refractive_index(vacuum_wavelength=m[mask])
            rel = float(np.max(np.abs(got - index) / np.abs(index)))
            bitwise = same_bits(got, index)
            w = worst.setdefault((doc_id, ref), [0.0, True, type(mat.optical).__name__])
            w[0], w[1] = max(w[0], rel), w[1] and bitwise
            tally.add("public constructors within rel 1e-14", rel <= CONSTRUCTOR_RTOL,
                      f"{doc_id} {ref} {key}: rel {rel:.3e}", n)
    # signed zero
    for n, k in ((1.5, -0.0), (1.444, -0.0), (3.48, 0.01)):
        model = physmat.constant_model(refractive_index=complex(n, k))
        keeps = model.k0 == k and np.signbit(model.k0) == np.signbit(k)
        got = physmat.Material("c", model).refractive_index(vacuum_wavelength=metres(g["1nm"]))
        tally.add("constant_model signed zero", keeps and same_bits(got, base[f"constant/{n!r}/{k!r}"]),
                  f"n={n} k={k!r}")

    # air
    for entry, (label, t, p, h, ppm) in zip(meta["air"], air_conditions(), strict=True):
        assert entry["label"] == label
        m = physmat.ciddor_air(temperature=float(t), absolute_pressure=float(p), relative_humidity=float(h),
                               co2_mole_fraction=float(mole_fraction_text(ppm)))
        tally.add("air kernel conditions (Celsius, ppm) and datum",
                  m.optical.temperature_c == entry["temperature_c"] and m.optical.co2_ppm == entry["co2_ppm"]
                  and m.datum_temperature == entry["datum"], label)
        tally.add("air density property", float(m.property("density", temperature=float(t))) == entry["density"], label)
        for key, texts in g.items():
            mm, um = metres(texts), micrometres(texts)
            mask = in_range(um, m.optical.range_um)
            info = entry["grids"][key]
            tally.add("air grid sizes", int(mask.sum()) == info["points"], f"{label} {key}")
            tally.add("air refractive_index", digest(m.refractive_index(vacuum_wavelength=mm[mask])) == info["index"],
                      f"{label} {key}", int(mask.sum()))
            tally.add("air relative_permittivity",
                      digest(m.relative_permittivity(vacuum_wavelength=mm[mask])) == info["eps"], f"{label} {key}",
                      int(mask.sum()))

    print("P3-7 physmat SI API against the baseline")
    for what, (ok, total) in tally.counts.items():
        print(f"  {what}: {ok}/{total}")
    print("  public constructors against the kernel model simcase builds (max rel; bitwise?):")
    for (doc_id, ref), (rel, bitwise, kind) in sorted(worst.items()):
        margin = "inf" if rel == 0 else f"{CONSTRUCTOR_RTOL / rel:.1f}x"
        mark = " (a listed Sellmeier fixture)" if doc_id.split("/")[-1] in SELLMEIER_FIXTURES else ""
        print(f"    {doc_id} {ref} [{kind}]: max rel {rel:.3e}, margin {margin}, bitwise {bitwise}{mark}")
    if tally.problems:
        print(f"FAILED: {len(tally.problems)} problems")
        for line in tally.problems[:50]:
            print("  " + line)
        return 1
    print("all equal")
    return 0


def constructor(physmat, doc, ref):
    """The public SI constructor of a document's local refractive_index, from the reader's SI values."""
    index = doc.si["materials"][ref]["refractive_index"]
    if not isinstance(index, dict):
        return physmat.constant_model(refractive_index=index)
    terms = index["terms"]
    squared = ["resonance_wavelength_squared" in t for t in terms]
    if all(squared):
        resonance = {"resonance_wavelength_squared": [t["resonance_wavelength_squared"] for t in terms]}
    elif not any(squared):
        resonance = {"resonance_wavelength": [t["resonance_wavelength"] for t in terms]}
    else:
        raise ValueError(f"{ref}: terms mix the two resonance forms")
    valid = (index.get("valid") or {}).get("vacuum_wavelength")
    return physmat.sellmeier_model(strength=[t["strength"] for t in terms], constant=index.get("constant", 1.0),
                                   valid_vacuum_wavelength=None if valid is None else tuple(valid), **resonance)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", choices=("baseline", "check"))
    parser.add_argument("file", type=Path, help="the baseline's .npz (written by baseline, read by check)")
    args = parser.parse_args(argv)
    return baseline(args.file) if args.mode == "baseline" else check(args.file)


if __name__ == "__main__":
    sys.exit(main())
