# Physics providers

**English** | [한국어](../../locales/ko/pages/packages/simcase/providers.md)

[simcase overview](overview.md)

A *provider* is an installed distribution that adds physics kinds to simcase's
[physics registry](../../../packages/simcase/src/simcase/registry.py). simcase's own
kinds are the built-in provider `openphysics-fem`. Another distribution can add
kinds without editing simcase, and a user interface can list what is installed from
data alone. The protocol is implemented in
[`simcase.providers`](../../../packages/simcase/src/simcase/providers.py).

**The protocol is unstable in 0.x** (protocol version 1). Its fields, the manifest
layout and the listing may change in any minor release. A provider declares the
version it implements, and simcase refuses another version by name.

## Purpose

Studio and `simcase.run` find every physics they can run, including physics from
separately installed packages, without Studio or the runner testing type strings.

## The contract (D1)

1. **Provider.** A provider is an installed Python distribution that registers one
   entry point in the group `openphysics.providers`. The entry point names a callable
   that returns a provider object with:
   - `name` (for example `"openphysics-fem"`), equal to the entry point's name
     (lowercase letters, digits, `.`, `_` and `-`), and `version` (a non-empty string);
   - `protocol`: the protocol version it implements, `1`;
   - `kinds()`: the `registry.PhysicsKind` objects it adds (the dataclass as it is, no
     new fields);
   - `manifest()`: JSON data describing each kind for Studio and the checker (below).
2. **Built-in provider.** The built-in kinds are the provider `openphysics-fem`,
   registered by simcase's own distribution
   (`openphysics-fem = simcase.providers:builtin_provider`). It wraps the kinds the
   modules of `registry.BUILTIN_MODULES` register (each keeps its kind as `KIND`):
   documents, results and numbers are the same as without it. An error of the built-in
   provider is raised, not listed: without its kinds no document runs.
3. **Discovery.** Providers load on the first registry lookup (`registry.kinds()`,
   `kind_of`, `kind_of_type`, `physics_types`, and everything that uses them), once per
   process: the built-in provider first, then the other entry points in name order. A
   provider is left out, and listed as unavailable with its error, when
   - its entry point fails to import, its callable raises, or its distribution's
     metadata cannot be read,
   - its name differs from its entry point's name or repeats a loaded provider's name
     (including `openphysics-fem`),
   - it declares a protocol version other than 1,
   - `kinds()` returns something that is not a `PhysicsKind`, or `manifest()` is
     invalid (below),
   - one of its kinds claims a type string another kind claims (the `register` rule,
     which names both kinds), or takes the name of another provider's kind, or
   - its modules register kinds that `kinds()` does not return.

   A provider is added whole or not at all: kinds it registered while it loaded are
   removed again, and so are kinds of its `kinds()` that its modules registered before
   the first lookup. Its failure does not stop the other providers or the built-in kinds.
   Two providers claiming one type: the first in name order is loaded, the second is
   unavailable. A kind registered with `registry.register` outside any provider belongs
   to no provider; a provider's kind of the same name takes its place.
4. **Manifest (data only).** `manifest()` returns `{"kinds": {<kind name>: {...}}}`,
   describing exactly the kinds of `kinds()`. For each kind:
   - `types`: the type strings the kind claims;
   - `field`: the group of the "Add physics" list (`electric`, `heat`,
     `electromagnetics`, `structure`, …; lowercase letters, digits and underscores);
   - `engine`: a label for the engine that solves it;
   - `process`: `"in_process"` or `"worker"`. It is a declaration for Studio and the
     checker: simcase starts no worker processes yet (D3), and `run` calls the kind's
     runner in the calling process;
   - `ports`: inputs and outputs, each with `name`, `direction` (`"input"` or
     `"output"`), `quantity` (a name of physmat's
     [quantity registry](../physmat/units.md)), `unit` (that quantity's SI unit
     symbol, compared as a string), `location` (`"node"`, `"element"`, `"grid"` or
     `"scalar"`, which is not on a mesh or grid: one value, or one per mode), and for
     inputs `combine` (`"single"` or `"sum"`);
   - `ui` (optional): hints as data only, such as labels, grouping, units and slider
     ranges. **Studio never loads code (JavaScript or HTML) from a provider.**

   Unknown keys are refused, and the whole manifest must be JSON data (objects with
   string keys, lists, strings, finite numbers, booleans and null) that survives a
   JSON round trip. `providers.check_manifest(manifest, kinds)` applies these rules
   and raises `ProviderError` naming the entry, such as
   `kinds.thermal.steady2d.ports[0].unit`.
5. **Trust.** A provider is ordinary installed Python code and runs with the user's
   rights, like any package. The listing gives each provider's name, version and
   distribution so the user can see what is installed.
6. **Stability.** The protocol is unstable for 0.x (see the
   [changelog](../../../CHANGELOG.md#stability-in-0x)). A provider declares the protocol
   version it implements (`protocol = 1`); simcase refuses a different version by name.

Not in D1: worker processes (D3), saving (D4), adapter distributions (D5) and
multiphysics documents (D2). No built-in kind reads a field another kind computes,
so input ports and `combine` are not used by the built-in kinds yet.

## Listing the providers

```python
from simcase import providers

for p in providers.providers():          # built-in first, then by entry-point name
    print(p.name, p.version, p.distribution, p.status, p.error)

listing = [p.as_dict() for p in providers.providers()]   # JSON data
```

Each entry of `providers.providers()` is a `ProviderInfo` with `name`, `version`,
`distribution`, `protocol`, `status` (`"available"` or `"unavailable"`), `error`
(the exception type and message, or None), `manifest` and `kinds` (the names of its
kinds). `as_dict()` returns `name`, `version`, `distribution`, `protocol`, `status`,
`error` and `kinds`, the manifest's per-kind entries (empty for an unavailable
provider). An unavailable provider is listed under its entry point's name; its
`version` and `protocol` are None when it never returned them.

## The built-in kinds and their ports

Every built-in kind runs in process and is solved by `galerkin`. Its ports are the
outputs every document of the kind saves, under the port's name, in the run's
`fields.npz` ([saved output](overview.md#saved-output)) when it saves fields
(`results.save_fields`, true by default; with false no `fields.npz` is written). A node
port has one entry per mesh node and an element port one per element, after the time
axis of a transient history. The list is minimal: a kind saves more arrays than it
declares. Every shipped example document was checked against it.

| Kind | Types | `field` | Output ports (quantity, unit, location) |
|---|---|---|---|
| `electric_joule` | `electric.steady2d`, `joule.steady2d`, `joule.temperature2d` | `electric` | `electric_potential` (V, node), `electric_field` (V/m, element), `current_density` (A/m^2, element), `joule_power_density` (W/m^3, element) |
| `mechanics` | `mechanics.elasticity2d`, `mechanics.thermoelastic2d` | `structure` | `displacement` (m, node), `strain` (1, element), `stress` (Pa, element) |
| `thermal.transient2d` | `thermal.transient2d` | `heat` | `temperature` (K, node), `heat_flux` (W/m^2, element); one row per output time |
| `thermal.steady2d` | `thermal.steady2d` | `heat` | `temperature` (K, node), `heat_flux` (W/m^2, element) |
| `em.cavity3d` | `em.cavity3d` | `electromagnetics` | `resonant_frequency` (Hz, scalar per mode) |
| `em.modes2d` | `em.modes2d` | `electromagnetics` | `effective_index` (1, scalar per mode) |

No built-in kind has input ports. The Joule temperature workflow and the
thermoelastic workflow couple inside one kind; they do not read another kind's output.

## Writing a provider

```toml
# pyproject.toml of the provider distribution
[project.entry-points."openphysics.providers"]
my-physics = "my_physics.provider:provider"
```

```python
# my_physics/provider.py
from simcase import registry

class Provider:
    name, version, protocol = "my-physics", "0.1.0", 1

    def kinds(self):
        return (MY_KIND,)          # a registry.PhysicsKind claiming "my.type"

    def manifest(self):
        return {"kinds": {MY_KIND.name: {
            "types": ["my.type"], "field": "heat", "engine": "my-solver", "process": "in_process",
            "ports": [{"name": "temperature", "direction": "output", "quantity": "temperature",
                       "unit": "K", "location": "node"}]}}}

def provider():
    return Provider()
```

A kind needs what every kind needs (contract validation, runner, summary, result
types, and slots to read format 0.3 documents); see [adding a physics](../../architecture.md#adding-a-physics).

## Tests

[`tests/simcase/test_providers.py`](../../../tests/simcase/test_providers.py) checks the
built-in provider (same kinds in the same order, its entry point, its manifest, its
ports against physmat's registry and the saved `fields.npz` of twelve examples, and its
errors raised), discovery of a fake provider through injected entry points and through a
test-only distribution on the path, each failure listed above (kinds registered before
the first lookup included), and every manifest rule with a JSON round trip.
