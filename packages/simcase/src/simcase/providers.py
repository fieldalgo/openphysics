# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Physics providers: the installed distributions whose kinds the registry holds.

A provider is an installed distribution that registers one entry point in the group
``openphysics.providers``. The entry point names a callable that returns a provider:
an object with ``name``, ``version``, ``protocol`` (``PROTOCOL``), ``kinds()`` (the
``registry.PhysicsKind`` objects it adds) and ``manifest()`` (JSON data describing each
kind, checked by ``check_manifest``). simcase's own kinds are the built-in provider
``openphysics-fem``, registered by simcase's distribution and always loaded first.

The registry loads providers on its first lookup: the built-in provider, then every other
entry point in name order. A provider that fails to import, raises, declares another
protocol version, returns an invalid manifest or claims a type string or kind name that
another provider holds is listed as unavailable with its error; its kinds are left out and
the other providers and the built-in kinds still load. ``providers()`` lists them all.

The protocol is unstable in 0.x. The contract is docs/packages/simcase/providers.md.
"""

from __future__ import annotations

import importlib
import json
import math
import re
from dataclasses import dataclass, field
from importlib import metadata
from typing import Any, Callable, Iterable

from . import registry

#: the entry-point group a provider distribution registers its provider in
GROUP = "openphysics.providers"
#: the protocol version this simcase reads; a provider declaring another one is unavailable
PROTOCOL = 1
#: the built-in provider: simcase's own kinds, and the entry point simcase registers for them
BUILTIN = "openphysics-fem"
BUILTIN_ENTRY_POINT = "simcase.providers:builtin_provider"

PROCESSES = ("in_process", "worker")
DIRECTIONS = ("input", "output")
LOCATIONS = ("node", "element", "grid", "scalar")
COMBINES = ("single", "sum")

_KIND_KEYS = {"types", "field", "engine", "process", "ports", "ui"}
_KIND_REQUIRED = _KIND_KEYS - {"ui"}
_PORT_KEYS = {"name", "direction", "quantity", "unit", "location", "combine"}
_WORD = re.compile(r"[a-z][a-z0-9_]*\Z")
_PROVIDER_NAME = re.compile(r"[a-z0-9][a-z0-9._-]*\Z")


class ProviderError(ValueError):
    """What is wrong with a provider; ``path`` names the manifest entry when there is one."""

    def __init__(self, message: str, path: str = ""):
        super().__init__(f"{path}: {message}" if path else message)
        self.path = path


@dataclass(frozen=True)
class ProviderInfo:
    """One provider as ``providers()`` lists it.

    ``status`` is ``"available"`` or ``"unavailable"``. An unavailable provider has its
    ``error`` and no kinds; ``name`` is then the entry point's name, and ``version`` and
    ``protocol`` are None when the provider never returned them."""
    name: str
    version: str | None
    distribution: str | None
    protocol: int | None
    status: str
    error: str | None = None
    #: the provider's manifest (``check_manifest``-valid JSON data); None when unavailable
    manifest: dict | None = field(default=None, compare=False)

    @property
    def kinds(self) -> tuple[str, ...]:
        """The names of the kinds this provider adds, in manifest order."""
        return tuple(self.manifest["kinds"]) if self.manifest else ()

    def as_dict(self) -> dict:
        """JSON data: what a user interface lists for this provider."""
        return {"name": self.name, "version": self.version, "distribution": self.distribution,
                "protocol": self.protocol, "status": self.status, "error": self.error,
                "kinds": json.loads(json.dumps(self.manifest["kinds"])) if self.manifest else {}}


# ---------------------------------------------------------------------------------------------
# the manifest

def _check_json(value: Any, path: str) -> None:
    """``value`` is JSON data: dicts with string keys, lists, strings, finite numbers, booleans, None."""
    if value is None or isinstance(value, (str, bool)):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ProviderError("is not a finite number (JSON has no NaN or infinity)", path)
        return
    if isinstance(value, list):
        for i, item in enumerate(value):
            _check_json(item, f"{path}[{i}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ProviderError(f"has the key {key!r}, which is not a string", path)
            _check_json(item, f"{path}.{key}" if path else key)
        return
    raise ProviderError(f"is a {type(value).__name__}, which is not JSON data", path)


def _string(value: Any, path: str, pattern: re.Pattern | None = None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProviderError("must be a non-empty string", path)
    if pattern is not None and not pattern.match(value):
        raise ProviderError(f"{value!r} must be lowercase letters, digits and underscores, "
                            f"starting with a letter", path)
    return value


def _one_of(value: Any, allowed: tuple[str, ...], path: str) -> str:
    if value not in allowed:
        raise ProviderError(f"{value!r} is not one of " + ", ".join(f'"{a}"' for a in allowed), path)
    return value


def _check_port(port: Any, path: str) -> None:
    from physmat import units                       # physmat's quantity registry names the ports

    if not isinstance(port, dict):
        raise ProviderError("must be an object", path)
    unknown = sorted(set(port) - _PORT_KEYS)
    if unknown:
        raise ProviderError(f"has unknown keys {unknown}", path)
    for key in ("name", "direction", "quantity", "unit", "location"):
        if key not in port:
            raise ProviderError(f"is missing {key!r}", path)
    _string(port["name"], f"{path}.name", _WORD)
    direction = _one_of(port["direction"], DIRECTIONS, f"{path}.direction")
    name = _string(port["quantity"], f"{path}.quantity")
    try:
        quantity = units.quantity(name)
    except (units.UnitError, TypeError) as error:
        raise ProviderError(f"{name!r} is not a quantity of physmat's registry ({error})",
                            f"{path}.quantity") from None
    unit = _string(port["unit"], f"{path}.unit")
    if unit != quantity.unit:
        raise ProviderError(f"{unit!r} is not the SI unit of {name}, {quantity.unit!r}", f"{path}.unit")
    _one_of(port["location"], LOCATIONS, f"{path}.location")
    if direction == "input":
        if "combine" not in port:
            raise ProviderError("is an input and is missing 'combine'", path)
        _one_of(port["combine"], COMBINES, f"{path}.combine")
    elif "combine" in port:
        raise ProviderError("is an output; 'combine' belongs to inputs only", f"{path}.combine")


def _check_kind(entry: Any, path: str) -> None:
    if not isinstance(entry, dict):
        raise ProviderError("must be an object", path)
    unknown = sorted(set(entry) - _KIND_KEYS)
    if unknown:
        raise ProviderError(f"has unknown keys {unknown}", path)
    missing = sorted(_KIND_REQUIRED - set(entry))
    if missing:
        raise ProviderError(f"is missing {missing}", path)
    types = entry["types"]
    if not isinstance(types, list) or not types:
        raise ProviderError("must be a non-empty list of type strings", f"{path}.types")
    for i, t in enumerate(types):
        _string(t, f"{path}.types[{i}]")
    if len(set(types)) != len(types):
        raise ProviderError("names a type more than once", f"{path}.types")
    _string(entry["field"], f"{path}.field", _WORD)
    _string(entry["engine"], f"{path}.engine")
    _one_of(entry["process"], PROCESSES, f"{path}.process")
    ports = entry["ports"]
    if not isinstance(ports, list):
        raise ProviderError("must be a list", f"{path}.ports")
    seen = set()
    for i, port in enumerate(ports):
        _check_port(port, f"{path}.ports[{i}]")
        if port["name"] in seen:
            raise ProviderError(f"repeats the port name {port['name']!r}", f"{path}.ports[{i}].name")
        seen.add(port["name"])
    if "ui" in entry and not isinstance(entry["ui"], dict):
        raise ProviderError("must be an object of data (labels, groups, units, ranges)", f"{path}.ui")


def check_manifest(manifest: Any, kinds: Iterable[registry.PhysicsKind] | None = None) -> dict:
    """Check a provider manifest and return it; raise ``ProviderError`` naming the bad entry.

    A manifest is ``{"kinds": {<kind name>: {...}}}``, JSON data only. Each kind has
    ``types``, ``field``, ``engine``, ``process`` (``PROCESSES``), ``ports`` and optionally
    ``ui``; each port has ``name``, ``direction`` (``DIRECTIONS``), ``quantity`` (a name of
    physmat's quantity registry), ``unit`` (that quantity's SI unit, compared as a string),
    ``location`` (``LOCATIONS``) and, for an input, ``combine`` (``COMBINES``). Given the
    provider's ``kinds``, the manifest must describe exactly those kinds and their types."""
    _check_json(manifest, "")
    if not isinstance(manifest, dict):
        raise ProviderError("a manifest must be an object with 'kinds'")
    unknown = sorted(set(manifest) - {"kinds"})
    if unknown:
        raise ProviderError(f"a manifest has only 'kinds'; unknown keys {unknown}")
    entries = manifest.get("kinds")
    if not isinstance(entries, dict):
        raise ProviderError("must be an object keyed by kind name", "kinds")
    for name, entry in entries.items():
        _check_kind(entry, f"kinds.{name}")
    if kinds is not None:
        kinds = tuple(kinds)
        names = [k.name for k in kinds]
        if sorted(names) != sorted(entries):
            raise ProviderError(f"describes the kinds {sorted(entries)}; the provider's kinds() "
                                f"are {sorted(names)}", "kinds")
        for kind in kinds:
            if set(entries[kind.name]["types"]) != set(kind.types):
                raise ProviderError(f"lists {sorted(entries[kind.name]['types'])}; the kind claims "
                                    f"{sorted(kind.types)}", f"kinds.{kind.name}.types")
    if json.loads(json.dumps(manifest)) != manifest:
        raise ProviderError("does not survive a JSON round trip")
    return manifest


# ---------------------------------------------------------------------------------------------
# the built-in provider

def _out(name: str, quantity: str, unit: str, location: str) -> dict:
    return {"name": name, "direction": "output", "quantity": quantity, "unit": unit, "location": location}


def _in(name: str, quantity: str, unit: str, location: str) -> dict:
    return {**_out(name, quantity, unit, location), "direction": "input", "combine": "single"}


#: the outputs every document of a built-in kind saves in its fields.npz under the port's
#: name when it saves fields (``results.save_fields``, true by default; false saves no
#: fields.npz). A "scalar" port is not on the mesh: one value per mode, for example. An input
#: port is read in a multiphysics document (``simcase.multiphysics``) from the coupling into it:
#: em.modes2d takes a node temperature (K) and uses its mean over each triangle.
_THERMAL_PORTS = [_out("temperature", "temperature", "K", "node"),
                  _out("heat_flux", "heat_flux", "W/m^2", "element")]
_BUILTIN_MANIFEST = {
    "electric_joule": {
        "field": "electric", "engine": "galerkin", "process": "in_process",
        "ports": [_out("electric_potential", "electric_potential", "V", "node"),
                  _out("electric_field", "electric_field", "V/m", "element"),
                  _out("current_density", "current_density", "A/m^2", "element"),
                  _out("joule_power_density", "joule_power_density", "W/m^3", "element")]},
    "mechanics": {
        "field": "structure", "engine": "galerkin", "process": "in_process",
        "ports": [_out("displacement", "displacement", "m", "node"),
                  _out("strain", "strain", "1", "element"),
                  _out("stress", "stress", "Pa", "element"),
                  _in("temperature", "temperature", "K", "node")]},
    "thermal.transient2d": {"field": "heat", "engine": "galerkin", "process": "in_process",
                            "ports": _THERMAL_PORTS},
    "thermal.steady2d": {"field": "heat", "engine": "galerkin", "process": "in_process",
                         "ports": [*_THERMAL_PORTS,
                                   _in("heat_source_density", "joule_power_density", "W/m^3", "element")]},
    "thermal.steady3d": {"field": "heat", "engine": "galerkin", "process": "in_process",
                         "ports": [_out("temperature", "temperature", "K", "node")]},
    "em.cavity3d": {"field": "electromagnetics", "engine": "galerkin", "process": "in_process",
                    "ports": [_out("resonant_frequency", "resonant_frequency", "Hz", "scalar")]},
    "em.modes2d": {"field": "electromagnetics", "engine": "galerkin", "process": "in_process",
                   "ports": [_out("effective_index", "effective_index", "1", "scalar"),
                             {"name": "temperature", "direction": "input", "quantity": "temperature", "unit": "K",
                              "location": "element", "combine": "single"}]},
}


class BuiltinProvider:
    """``openphysics-fem``: the kinds of ``registry.BUILTIN_MODULES``, unchanged."""

    name = BUILTIN
    protocol = PROTOCOL

    @property
    def version(self) -> str:
        from . import __version__
        return __version__

    def kinds(self) -> tuple[registry.PhysicsKind, ...]:
        # each module registers its kind when imported and keeps it as ``KIND``: the kind
        # objects come from the modules, not from whatever the registry holds under their names
        modules = [importlib.import_module(f"{registry.__package__}.{m}") for m in registry.BUILTIN_MODULES]
        by_name = {m.KIND.name: m.KIND for m in modules}
        return tuple(by_name[name] for name in _BUILTIN_MANIFEST)

    def manifest(self) -> dict:
        kinds = {k.name: k for k in self.kinds()}
        return {"kinds": {name: {"types": sorted(kinds[name].types), **json.loads(json.dumps(entry))}
                          for name, entry in _BUILTIN_MANIFEST.items()}}


def builtin_provider() -> BuiltinProvider:
    """The entry point of ``openphysics-fem`` in simcase's distribution metadata."""
    return BuiltinProvider()


# ---------------------------------------------------------------------------------------------
# discovery

_PROVIDERS: list[ProviderInfo] = []


def _entry_points() -> list[metadata.EntryPoint]:
    """Every entry point of ``GROUP`` in the installed distributions, in name order."""
    return sorted(metadata.entry_points(group=GROUP), key=lambda ep: (ep.name, ep.value))


def _distribution(ep: metadata.EntryPoint) -> str | None:
    dist = getattr(ep, "dist", None)
    return dist.metadata["Name"] if dist is not None else None


def _is_builtin(ep: metadata.EntryPoint) -> bool:
    return ep.name == BUILTIN and ep.value == BUILTIN_ENTRY_POINT and (_distribution(ep) or "simcase") == "simcase"


def _add(make: Callable[[], Any], name: str, distribution: str | None) -> ProviderInfo:
    """Load one provider (``make()`` returns it) and register its kinds, all or none."""
    version = protocol = None
    kinds: tuple = ()
    before = dict(registry._KINDS)
    owners = dict(registry._OWNERS)
    try:
        provider = make()
        if provider is None:
            raise ProviderError("the entry point returned None, not a provider")
        version = getattr(provider, "version", None)
        protocol = getattr(provider, "protocol", None)
        if getattr(provider, "name", None) != name:
            raise ProviderError(f"the provider calls itself {getattr(provider, 'name', None)!r}; "
                                f"its entry point is named {name!r}")
        if not isinstance(version, str) or not version:
            raise ProviderError(f"version {version!r} is not a non-empty string")
        if protocol != PROTOCOL:
            raise ProviderError(f"declares protocol {protocol!r}; this simcase reads protocol {PROTOCOL}")
        kinds = tuple(provider.kinds())
        for kind in kinds:
            if not isinstance(kind, registry.PhysicsKind):
                raise ProviderError(f"kinds() returned {kind!r}, not a registry.PhysicsKind")
        if len({k.name for k in kinds}) != len(kinds):
            raise ProviderError("kinds() returns two kinds of one name")
        manifest = json.loads(json.dumps(check_manifest(provider.manifest(), kinds)))
        mine = {k.name for k in kinds}
        for kind in kinds:
            owner = owners.get(kind.name)
            if owner is not None and owner != name:
                raise ProviderError(f"kind {kind.name!r} is already provided by {owner!r}")
            # a kind of this name registered outside any provider gives way to the provider's
            if before.get(kind.name) is not None and before[kind.name] is not kind and owner is None:
                del registry._KINDS[kind.name]
            registry.register(kind)
        # a provider's modules may register kinds on import (the built-in ones do): every kind
        # added or replaced while it loaded must be one of its kinds()
        touched = sorted(n for n, k in registry._KINDS.items() if before.get(n) is not k and n not in mine)
        if touched:
            raise ProviderError(f"registered kinds that kinds() does not return: {touched}")
        for kind in kinds:
            registry._OWNERS[kind.name] = name
    except Exception as error:                          # any failure leaves this provider out
        registry._KINDS.clear()
        registry._KINDS.update(before)
        registry._OWNERS.clear()
        registry._OWNERS.update(owners)
        for kind in kinds:                              # its kinds registered before discovery, too
            if registry._KINDS.get(kind.name) is kind and kind.name not in owners:
                del registry._KINDS[kind.name]
        if name == BUILTIN:                             # without the built-in kinds nothing runs
            raise
        return ProviderInfo(name, version if isinstance(version, str) and version else None, distribution,
                            protocol if type(protocol) is int else None, "unavailable",
                            f"{type(error).__name__}: {error}")
    return ProviderInfo(name, version, distribution, protocol, "available", manifest=manifest)


def _unavailable(name: str, distribution: str | None, error: BaseException | str) -> ProviderInfo:
    message = error if isinstance(error, str) else f"{type(error).__name__}: {error}"
    return ProviderInfo(name, None, distribution, None, "unavailable", message)


def _load() -> None:
    """Load the built-in provider, then every other entry point in name order (``registry`` calls it once).

    An error of the built-in provider propagates: without its kinds no document runs. An
    error of any other provider, its metadata included, lists that provider as unavailable."""
    _PROVIDERS.clear()
    _PROVIDERS.append(_add(BuiltinProvider, BUILTIN, "simcase"))
    try:
        points = _entry_points()
    except Exception as error:                          # unreadable metadata: the built-in kinds still load
        _PROVIDERS.append(_unavailable("(entry points)", None, error))
        return
    loaded = {BUILTIN}
    for ep in points:
        name = getattr(ep, "name", "(unnamed entry point)")
        try:
            if _is_builtin(ep):
                continue
            distribution = _distribution(ep)
        except Exception as error:                      # unreadable distribution metadata
            _PROVIDERS.append(_unavailable(name, None, error))
            continue
        if not isinstance(name, str) or not _PROVIDER_NAME.match(name):
            _PROVIDERS.append(_unavailable(str(name), distribution, f"ProviderError: entry point name {name!r} "
                                           "must be lowercase letters, digits, '.', '_' and '-'"))
            continue
        if name in loaded:
            _PROVIDERS.append(_unavailable(name, distribution,
                                           f"ProviderError: provider name {name!r} is already loaded"))
            continue
        loaded.add(name)
        _PROVIDERS.append(_add(lambda ep=ep: ep.load()(), name, distribution))


def providers() -> tuple[ProviderInfo, ...]:
    """Every provider in load order, available or not: built-in first, then by entry-point name."""
    registry.kinds()                                     # the first lookup loads the providers
    return tuple(_PROVIDERS)
