# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Documents and test-local kinds of the multiphysics document tests (D2)."""
import copy
from types import SimpleNamespace

import numpy as np

from simcase import multiphysics, registry

#: the validation geometry: a 1.0 x 2.4 um window, a 0.22 um core at y in [0, 0.22] across its
#: whole width, cladding below and above
CORE = {"refractive_index": 3.48, "thermal_conductivity": "148 W/(m K)",
        "thermo_optic_coefficient": "1.8e-4 1/K", "reference_temperature": "300 K"}
CLAD = {"refractive_index": 1.444, "thermal_conductivity": "1.38 W/(m K)",
        "thermo_optic_coefficient": "1.0e-5 1/K", "reference_temperature": "300 K"}
WINDOW = {"xmin": -0.5, "xmax": 0.5, "ymin": -1.2, "ymax": 1.2}


def geometry(background="clad", core="core"):
    return {"version": 1, "components": {"xs": {
        "dimension": "2d", "length_unit": "um", "depth": None, "domain": dict(WINDOW),
        "background": {"material": background},
        "features": [{"name": "core", "type": "rect", "x": -0.5, "y": 0.0, "w": 1.0, "h": 0.22, "material": core}]}}}


def modes_entry(formulation="scalar"):
    entry = {"type": "em.modes2d", "formulation": formulation, "vacuum_wavelength": "1.55 um", "mode_count": 1,
             "boundary": {"left": "pmc", "right": "pmc", "top": "pec", "bottom": "pec"}}
    if formulation == "vector":
        entry["effective_index_threshold"] = 1.5
    return entry


def heated_slab(h=0.04, *, bottom="310 K", top="310 K", formulation="scalar", core=None, clad=None, sides=None):
    """heat1 (thermal.steady2d) -> modes1 (em.modes2d) on the validation geometry, mesh size h um."""
    prescribed = {"bottom": bottom, "top": top}
    if sides is not None:
        prescribed.update(left=sides, right=sides)
    return {
        "openphysics": multiphysics.ENVELOPE, "name": "heated slab",
        "geometry": geometry(),
        "materials": {"core": copy.deepcopy(CORE if core is None else core),
                      "clad": copy.deepcopy(CLAD if clad is None else clad)},
        "physics": {"heat1": {"type": "thermal.steady2d", "prescribed_temperature": prescribed},
                    "modes1": modes_entry(formulation)},
        "couplings": {"heat_to_optics": {"from": "heat1.temperature", "to": "modes1.temperature",
                                         "transfer": "same_mesh"}},
        "mesh": {"element_size": f"{h} um"}}


def uncoupled_modes(h=0.04, *, formulation="scalar", core=None, clad=None):
    """The modes entry of ``heated_slab`` alone, as a single-physics format 0.3 document."""
    doc = heated_slab(h, formulation=formulation, core=core, clad=clad)
    del doc["physics"]["heat1"], doc["couplings"]
    doc["openphysics"] = "0.3"
    for record in doc["materials"].values():
        for key in ("thermal_conductivity", "thermo_optic_coefficient", "reference_temperature"):
            record.pop(key, None)
    return doc


# -- test-local kinds: a relay y = gain * (sum of inputs x) + offset on a fixed mesh -----------------

def _mesh():
    from galerkin import rectangle_mesh
    return rectangle_mesh(1.0, 1.0, 2, 2)


MESH = _mesh()


def _relay_slots(kind_type):
    return (
        {"pattern": f"physics.*{{{kind_type}}}.type", "kind": "enum", "values": [kind_type], "required": True},
        {"pattern": f"physics.*{{{kind_type}}}.gain", "kind": "quantity", "quantity": "constant", "forms": ["BD"],
         "required": True},
        {"pattern": f"physics.*{{{kind_type}}}.offset", "kind": "quantity", "quantity": "temperature",
         "forms": ["QS"], "required": True},
        {"pattern": "study", "kind": "override", "default": {"type": "single"},
         "default_reason": "structural default of the relay"},
        {"pattern": "materials.*", "kind": "override", "library": "any", "reads": {kind_type: []}},
    )


class RelayResult:
    def __init__(self, doc, y):
        self.doc, self.y, self.log = doc, y, []

    def summary(self):
        return {"result_format": "test-relay-v1"}

    def save(self, outdir):
        outdir.mkdir(parents=True, exist_ok=True)
        np.save(outdir / "y.npy", self.y)


def relay_kind(name="test.relay", unit="K", calls=None, quantity="temperature"):
    """A kind with input ``x`` (temperature, ``unit``, node, sum) and output ``y`` on ``MESH``."""
    from galerkin.coupling import Field

    def prepare(doc, pname):
        return SimpleNamespace(view=doc.views[pname], name=pname, mesh=MESH, triangle_regions=None)

    def solve(state, inputs, verbose):
        p = state.view.si["physics"][state.name]
        x = np.asarray(inputs["x"].values) if "x" in inputs else np.zeros(MESH.num_nodes)
        y = float(p["gain"]) * x + float(p["offset"])
        if calls is not None:
            calls.append((state.name, x.copy()))
        return RelayResult(state.view, y), {"y": Field(MESH, y, location="node", unit=unit)}

    ports = ({"name": "x", "direction": "input", "quantity": quantity, "unit": unit, "location": "node",
              "combine": "sum"},
             {"name": "y", "direction": "output", "quantity": quantity, "unit": unit, "location": "node"})
    return registry.PhysicsKind(
        name=name, types=frozenset({name}), precedence=60, validate=lambda doc: None,
        run=lambda doc, verbose=True: None, summary=lambda doc: f"{name} relay",
        result_types=(RelayResult,), slots=_relay_slots(name),
        coupling=multiphysics.CouplingHook(prepare=prepare, solve=solve, ports=ports))


def relay_document(relays, couplings, loops=None):
    """``relays``: {name: (type, gain, offset K)}; ``couplings``: {name: (from, to)}."""
    doc = {"openphysics": multiphysics.ENVELOPE,
           "geometry": {"version": 1, "components": {"c": {
               "dimension": "2d", "length_unit": "m", "depth": None,
               "domain": {"xmin": 0, "xmax": 1, "ymin": 0, "ymax": 1}}}},
           "physics": {n: {"type": t, "gain": g, "offset": f"{o} K"} for n, (t, g, o) in relays.items()},
           "couplings": {n: {"from": a, "to": b, "transfer": "same_mesh"} for n, (a, b) in couplings.items()}}
    if loops is not None:
        doc["study"] = {"type": "single", "loops": loops}
    return doc
