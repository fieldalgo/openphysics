# Tutorial: analyse your own waveguide

**English** | [한국어](../../locales/ko/pages/packages/simcase/waveguide_tutorial.md)

This tutorial takes you from the supplied silicon strip to your own waveguide
cross-section. You get the effective index n_eff, the mode fields and the group
index over a wavelength sweep, and you learn the checks that tell you whether to
trust them. Every Python block and `python -m simcase` command below is run by
`tests/simcase/test_waveguide_tutorial.py` against the installed packages, and
the printed numbers must match the outputs shown here to within one unit in the
last printed digit (your machine may differ by that much).

You need the runtime packages installed; see the
[package overview](overview.md) for the install command. Studio (the browser
editor, step 8) needs the `studio` extra. Run everything from a working folder
outside the repository's `packages/` and `tests/` folders.

## 1. Run the example

```bash
python -m simcase example soi_strip > strip.json
python -m simcase run strip.json -o strip_results
```

`strip.json` describes a 500 × 220 nm silicon core in silica, solved as full
vector modes at seven wavelengths from 1.40 to 1.70 µm. The run prints n_eff for
two modes at each wavelength, for example
`physics.em1.wavelength = 1.55 um: n_eff = 2.444060, 1.771237`, and writes
`strip_results/` (step 7). The first mode is the TE-like mode (electric field
mostly along x), the second the TM-like mode.

## 2. Load the document in Python and change it

The JSON file and `simcase.examples.SOI_STRIP` are the same document. Edit it as
a dictionary, then run it. A single wavelength is quicker while you edit:

```python
import copy
from simcase import Document, examples, run

def solve(doc):
    result = run(Document.from_dict(doc), verbose=False)
    return result.neff[0]

strip = copy.deepcopy(examples.SOI_STRIP)
strip["study"] = {"type": "single"}
print(" ".join(f"{n:.4f}" for n in solve(strip)))
```

```text
2.4441 1.7712
```

Lengths are in the declared unit, here `"units": {"length": "um"}`. Make the core
450 nm wide by changing the rectangle (`x` is its left edge, `y` its bottom):

```python
narrow = copy.deepcopy(strip)
narrow["geometry"]["shapes"][0].update(x=-0.225, w=0.45)
print(" ".join(f"{n:.4f}" for n in solve(narrow)))
```

```text
2.3520 1.7341
```

## 3. Shapes: strip, rib and polygon

Shapes are `rect`, `circle` or `polygon`. A later shape cuts the shapes before it,
and the background material fills the rest of the domain. A rib is a thin slab
across the whole window with the rib on top:

```python
rib = copy.deepcopy(strip)
rib["geometry"]["shapes"] = [
    {"name": "slab", "type": "rect", "x": -1.5, "y": 0.0, "w": 3.0, "h": 0.09,
     "material": "Si", "mesh_size": 0.02},
    {"name": "rib", "type": "rect", "x": -0.25, "y": 0.0, "w": 0.5, "h": 0.22,
     "material": "Si", "mesh_size": 0.02},
]
rib["physics"]["em1"]["num_modes"] = 1
print(f"{solve(rib)[0]:.4f}")
```

```text
2.5669
```

Step 6 explains why this asks for one mode only. A polygon takes its corners in
order; here a strip with sloped side walls, 500 nm wide at the bottom and 440 nm
at the top:

```python
sloped = copy.deepcopy(strip)
sloped["geometry"]["shapes"][0] = {
    "name": "core", "type": "polygon", "material": "Si", "mesh_size": 0.02,
    "points": [[-0.25, 0.0], [0.25, 0.0], [0.22, 0.22], [-0.22, 0.22]],
}
print(" ".join(f"{n:.4f}" for n in solve(sloped)))
```

```text
2.3922 1.7495
```

## 4. Materials

A material name is looked up first in the document's own `materials` table, then
in the 18 built-in materials, which include `Si`, `SiO2`, `Si3N4`, `LiNbO3` and
`vacuum`. Built-in materials carry their dispersion, so each wavelength of a
sweep uses its own index. For your own material give a constant index or
Sellmeier coefficients. Sellmeier `C` values are in the document's length unit
squared:

```python
import physmat

print(len(physmat.names()), "built-in materials")
nitride = copy.deepcopy(strip)
nitride["materials"] = {
    "my_sin": {"n": 2.0},
    "my_glass": {"sellmeier": {"B": [0.6961663, 0.4079426, 0.8974794],
                               "C": [0.0684043**2, 0.1162414**2, 9.896161**2]}},
}
nitride["geometry"]["background"]["material"] = "my_glass"
nitride["geometry"]["shapes"][0].update(material="my_sin", x=-0.6, w=1.2, h=0.4)
nitride["physics"]["em1"].update(n_cladding=1.45, num_modes=1)
print(f"{solve(nitride)[0]:.4f}")
```

```text
18 built-in materials
1.6658
```

The mode solver is lossless. A material with absorption, such as the built-in
metals `Au`, `Ag`, `Cu` and `Al`, is refused with an error instead of being
solved without its loss. The refractiveindex.info database that `physmat` can read
is not available from a document.

## 5. Check the window and the mesh

The domain edge is a perfect electric conductor (`"pec"`), not open space, and
the mesh is finite. Neither is checked for you. Change each one and see how far
n_eff moves:

```python
def changed(edit):
    doc = copy.deepcopy(strip)
    edit(doc)
    return f"{solve(doc)[0]:.5f}"

def wider_window(doc):
    doc["geometry"]["domain"] = {"xmin": -3.0, "xmax": 3.0, "ymin": -2.4, "ymax": 2.4}

def finer_core(doc):
    doc["geometry"]["shapes"][0]["mesh_size"] = 0.01

def finer_outside(doc):
    doc["mesh"]["size"] = 0.125
    doc["mesh"]["grading"].update(near=0.01, far=0.08)

def finer_both(doc):
    finer_core(doc)
    finer_outside(doc)

print("as supplied  ", changed(lambda doc: None))
print("window x2    ", changed(wider_window))
print("core mesh /2 ", changed(finer_core))
print("outside /2   ", changed(finer_outside))
print("both /2      ", changed(finer_both))
```

```text
as supplied   2.44406
window x2     2.44377
core mesh /2  2.44459
outside /2    2.44614
both /2       2.44634
```

For this strip the window is large enough (3e-4), but the supplied mesh is at
least 2e-3 low (n_eff is still rising when both are refined), and most of that
error is outside the core: `mesh_size` on a shape sets the element size inside
that shape, while `mesh.size` and `mesh.grading` set it around the shape, where
the field still varies quickly near the corners. Refine both
together until n_eff stops changing at the precision you need. A field that
reaches the window edge needs a larger window. These two checks are your
responsibility for every new geometry.

## 6. The rib trap: slab modes

The slab of a rib guides modes of its own, and with electric walls at the window
edges they appear as extra solutions. `n_cladding` is the lower bound of the
n_eff search, and the strip example's 1.45 lets them in. Ask the rib for four
modes and widen its window:

```python
def rib_modes(half_width, n_cladding=1.45, modes=4):
    doc = copy.deepcopy(rib)
    doc["geometry"]["domain"].update(xmin=-half_width, xmax=half_width)
    doc["geometry"]["shapes"][0].update(x=-half_width, w=2 * half_width)
    doc["physics"]["em1"].update(num_modes=modes, n_cladding=n_cladding)
    return " ".join(f"{n:.4f}" for n in solve(doc))

print("half width 1.5:", rib_modes(1.5))
print("half width 3.0:", rib_modes(3.0))
print("n_cladding 2.2:", rib_modes(1.5, n_cladding=2.2))
```

```text
half width 1.5: 2.5669 2.1157 2.0798 2.0422
half width 3.0: 2.5668 2.1124 2.0952 2.0904
n_cladding 2.2: 2.5669
```

The rib mode, 2.5669, hardly moves with the window. The others sit near the
TE mode of a bare 90 nm slab (n_eff 2.104) and change with the window width:
they are slab modes bounced between the walls, not modes of your rib. Set
`n_cladding` above the slab's own n_eff to exclude them: with 2.2 the same request
for four modes returns only the rib mode, and the log says fewer were found.
For a rib, also look at the field: a slab mode spreads across the whole slab.

## 7. Sweep the wavelength and read the group index

A wavelength sweep tracks each mode from point to point and also gives the
group index, `n_g = n_eff - λ dn_eff/dλ`, from a finite difference across the
sweep:

```python
result = run(Document.from_dict(examples.SOI_STRIP), verbose=False)
i = result.values.index(1.55)
print(f"n_eff {result.neff[i, 0]:.4f}  n_g {result.group_index()[i, 0]:.4f}")
```

```text
n_eff 2.4441  n_g 4.1923
```

The group index needs the same mesh check as n_eff, and also a wavelength step
fine enough for the finite difference.

`result.save("strip_results")` (or `python -m simcase run`) writes the folder
from step 1:

| File | Contents |
|---|---|
| `summary.json` | n_eff per study point and mode, group index, declared units, mesh statistics, timings, mode tracking |
| `fields.npz` | mesh nodes and triangles, the raw vector field coefficients and the electric field (Ex, Ey, Ez) at triangle centroids; load with `numpy.load(..., allow_pickle=False)` |
| `results.png` | mesh, the first mode's \|E\| and the sweep |
| `log.txt`, `model.json` | the run log and the exact document that was run |

Field amplitudes are relative (the largest centroid \|E\| is 1), not watts or
volts per metre. The [package overview](overview.md#vector-fields-and-single-point-studies)
describes the arrays.

## 8. The same model in Studio

Install the `studio` extra as the [package overview](overview.md#the-browser-ui)
describes, then start it:

```bash
simcase-studio
```

Studio opens on this strip example. Open your own JSON file, edit shapes,
materials and the mesh, run, and view n_eff, the sweep and the \|E\|, \|Ex\|,
\|Ey\| and \|Ez\| fields. It runs the same engine as the commands above.

## Limits

- Lossless dielectrics only: no metals, absorbing materials, gain or leaky modes.
- The window edge is a wall (PEC or PMC), not an open boundary; there are no
  perfectly matched layers, so bend and leakage losses are not computed.
- Straight waveguides only: no bends, no propagation along the guide.
- No automatic window or mesh convergence check: do step 5 yourself.
- `n_cladding` is a search bound you choose; the solver does not prove that it
  found every guided mode.
- The scalar formulation (`"formulation": "scalar"`) is an approximation for
  high-contrast cores: 2.611 instead of 2.444 for this strip.
