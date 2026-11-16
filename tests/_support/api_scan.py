# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Public-API units scan for galerkin, refsol and physmat (unshipped test support).

The scan reads the public API as the ``__all__`` of each public module (the module
lists are in ``api_units_modules.json``; ``physmat.units`` is public but not scanned).
It looks at every parameter of every callable named there: functions, class
constructors and every public method of a public class. ``__call__`` counts as public,
because calling an instance makes it so. The constructors of the result classes listed in
``api_units_result_classes.json`` (records that solvers return and users do not build) are
not scanned; their methods are, and their field names are check P3-11's job. Each
parameter must be one of

- a name from the ``physmat.units`` registry with an ``api`` place, keyword-only and
  without a dimensional default; or
- a structural name from ``api_units_structural.json`` (closed; a category per name),
  which may be positional. A name with a scope there is structural only in callables
  defined in those modules, and a name on both lists is structural.

No parameter name may end in a unit token. The tokens are derived from the unit
symbols of physmat's ``unit_tables.json`` (``temperature_k``, ``wavelength_um``,
``conductivity_w_mk``, ``thermal_expansion_per_k``, ...), never typed by hand. A
structural name may end in one only with a note that says why it is not a unit
(``mode_a``).

A default is dimensional when the parameter is a registry quantity whose canonical
unit is not ``1`` and the default is anything but ``None``, a ``bool`` or a ``str``. A
dimensionless registry quantity may have any default. An ``int`` on a dimensional
quantity is dimensional: a count is a dimensionless quantity.

Each violation is a tuple ``(module, callable, parameter, reason)``: ``module`` is the
module that defines the callable, ``callable`` its qualified name (a class name for
its constructor, ``Class.method`` for a method) and ``reason`` one of ``REASONS``. A
parameter with several problems gives one violation per reason. Each package keeps
today's violations in ``tests/<package>/api_units_allowlist.json``. The allowlist must
equal the violations found: a new violation fails, and so does an entry that no longer
matches one. Entries may only be removed, never added.

Once no allowlist entry belongs to a public module, two more clauses apply to it: every
removed name (``api_units_removed.json``) is absent from it, and a ``str`` passed to each
of its quantity parameters raises ``TypeError``. That second clause needs a valid call
per callable, supplied by the package's test as a string-refusal case.
"""

from __future__ import annotations

import dataclasses
import importlib
import importlib.util
import inspect
import json
import pkgutil
import re
import types
from collections.abc import Callable, Iterable, Mapping
from importlib import resources
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODULES_FILE = HERE / "api_units_modules.json"
STRUCTURAL_FILE = HERE / "api_units_structural.json"
REMOVED_FILE = HERE / "api_units_removed.json"
RESULT_CLASSES_FILE = HERE / "api_units_result_classes.json"

ALLOWLIST_SCHEMA = "openphysics.api-units-allowlist/1"
ALLOWLIST_FIELDS = ["module", "callable", "parameter", "reason"]

REASONS = {
    "unregistered": "neither a registry name nor a structural name",
    "no-api-place": "a registry name without an api place",
    "positional": "a registry quantity that can be passed by position",
    "dimensional-default": "a registry quantity whose unit is not 1, with a dimensional default",
    "unit-suffix": "the name ends in a unit token",
}

CATEGORIES = ("object", "positional data", "index or count", "enum", "mapping of tags", "flag", "path or text",
              "mesher, pending", "deferred to the materials step")
MESHER_SCOPE = ("galerkin.mesh", "galerkin.mesh3d")
#: physmat record arguments the materials step after 0.0.2 replaces (spec 1.2, 13); each names its closing condition
DEFERRED = "deferred to the materials step"

# The phrase every internal module's docstring carries.
INTERNAL_DOCSTRING = "Internal module, consistent units"

# Allowlist counts: refsol on openphysics main f693ae3a, when the scan landed; physmat after L1 commit 3,
# which emptied it (107 on f693ae3a); galerkin after L2 commit 4, which moved its assembly kernels and
# helpers to galerkin.kernels (301 on f693ae3a). They never grow.
BASELINE_COUNTS = {"galerkin": 191, "physmat": 0, "refsol": 549}

_KEYWORD = (inspect.Parameter.KEYWORD_ONLY, inspect.Parameter.VAR_KEYWORD)


@dataclasses.dataclass(frozen=True)
class Structural:
    """One name of the closed structural list."""

    name: str
    category: str
    source: str
    scope: tuple[str, ...] = ()        # module prefixes where the name is structural; empty means everywhere
    unit_token_note: str | None = None  # why a trailing unit token is not a unit here
    reviewer_note: str | None = None    # why the name was added after L1 commit 1b
    closing: str | None = None          # the condition that ends a 'deferred to the materials step' entry


@dataclasses.dataclass(frozen=True)
class Removed:
    """One removed name, asserted absent once its module has no allowlist entries."""

    package: str
    kind: str        # "name" (module attribute), "parameter" or "member" ("Class.attribute")
    name: str
    source: str


@dataclasses.dataclass(frozen=True)
class Rules:
    """Everything the scan compares with: the module lists, the two name lists and the registry."""

    packages: tuple[str, ...]
    public: Mapping[str, tuple[str, ...]]
    internal: Mapping[str, tuple[str, ...]]
    excluded: frozenset[str]
    structural: Mapping[str, Structural]
    removed: tuple[Removed, ...]
    registry: Mapping[str, tuple[frozenset[str], str]]   # name -> (places, canonical unit)
    tokens: frozenset[str]
    result_classes: frozenset[tuple[str, str]] = frozenset()   # (module, class) whose constructor is not scanned


@dataclasses.dataclass(frozen=True)
class Item:
    """One scanned callable."""

    module: str
    name: str
    signature: inspect.Signature
    target: object


def _within(module: str, prefixes: Iterable[str]) -> bool:
    return any(module == p or module.startswith(p + ".") for p in prefixes)


def _root(module: str | None) -> str:
    return (module or "").split(".")[0]


# ---- rule data --------------------------------------------------------------------------------------------------

def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_structural(path: Path = STRUCTURAL_FILE) -> dict[str, Structural]:
    """The closed structural list, keyed by name."""
    data = _read(path)
    if tuple(data["categories"]) != CATEGORIES:
        raise ValueError(f"{path.name}: the categories are {CATEGORIES}")
    out: dict[str, Structural] = {}
    for e in data["entries"]:
        name = e["name"]
        if name in out:
            raise ValueError(f"{path.name}: {name!r} is listed twice")
        if e["category"] not in CATEGORIES:
            raise ValueError(f"{path.name}: {name!r} has unknown category {e['category']!r}")
        out[name] = Structural(name, e["category"], e["source"], tuple(e.get("scope", ())), e.get("unit_token_note"),
                               e.get("reviewer_note"), e.get("closing"))
    return out


def load_removed(path: Path = REMOVED_FILE) -> tuple[Removed, ...]:
    data = _read(path)
    out = tuple(Removed(e["package"], e["kind"], e["name"], e["source"]) for e in data["entries"])
    for r in out:
        if r.kind not in ("name", "parameter", "member") or (r.kind == "member") != ("." in r.name):
            raise ValueError(f"{path.name}: bad entry {r}")
    return out


def load_result_classes(path: Path = RESULT_CLASSES_FILE) -> dict[tuple[str, str], str]:
    """The closed list of result classes, ``(module, class) -> reason``."""
    out: dict[tuple[str, str], str] = {}
    for e in _read(path)["entries"]:
        key = (e["module"], e["class"])
        if key in out:
            raise ValueError(f"{path.name}: {key} is listed twice")
        out[key] = e["reason"]
    return out


def result_class_problems(package: str, rules: Rules) -> list[str]:
    """Each listed result class of ``package`` is a class defined in its module, with a reason."""
    problems = []
    for (module, name), reason in sorted(load_result_classes().items()):
        if _root(module) != package:
            continue
        obj = getattr(importlib.import_module(module), name, None)
        if not inspect.isclass(obj) or obj.__module__ != module or obj.__qualname__ != name:
            problems.append(f"result class {module}.{name} is not a class defined in {module}")
        if not reason.strip():
            problems.append(f"result class {module}.{name} has no reason")
    return problems


def registry() -> dict[str, tuple[frozenset[str], str]]:
    """Every legal quantity name of physmat.units with its places and canonical unit."""
    from physmat import units
    return {n: (frozenset(units.quantity(n).places), units.quantity(n).unit) for n in units.names()}


def _token_parts(text: str) -> list[str]:
    text = text.strip()
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1]
    parts = (re.sub(r"[^0-9a-z]", "", p.lower().replace("\u00b5", "u").replace("\u03bc", "u"))
             for p in re.split(r"[ *]+", text))
    return [p for p in parts if p]


def symbol_tokens(symbol: str) -> set[str]:
    """The identifier spellings of one unit symbol: ``W/(m K)`` gives ``wmk``, ``w_mk``, ``w_per_m_k``, ``mk``, ..."""
    if symbol == "1":
        return set()
    if symbol == "%":
        return {"percent"}
    num, slash, den = symbol.partition("/")
    n = [] if num.strip() == "1" else _token_parts(num)
    d = _token_parts(den) if slash else []
    forms = {"".join(n + d), "_".join(n + d)}
    if d:
        for b in ("".join(d), "_".join(d)):
            forms |= {b, "per_" + b}
            for a in ("".join(n), "_".join(n)) if n else ():
                forms |= {f"{a}_{b}", f"{a}_per_{b}"}
    return {f for f in forms if f}


def unit_tokens() -> frozenset[str]:
    """Unit tokens derived from every unit symbol in physmat's unit table."""
    table = json.loads(resources.files("physmat").joinpath("unit_tables.json").read_text(encoding="utf-8"))
    tokens: set[str] = set()
    for symbol in table["units"]:
        tokens |= symbol_tokens(symbol)
    return frozenset(tokens)


def unit_token(name: str, tokens: Iterable[str]) -> str | None:
    """The unit token ``name`` ends in (after at least one other word), or None."""
    tokens = tokens if isinstance(tokens, (set, frozenset)) else set(tokens)
    parts = name.lower().split("_")
    for k in range(1, len(parts)):
        tail = parts[-k:]
        for t in ("_".join(tail), "".join(tail)):
            if t in tokens:
                return t
    return None


def load_rules() -> Rules:
    data = _read(MODULES_FILE)
    return Rules(
        packages=tuple(data["public"]),
        public={p: tuple(m) for p, m in data["public"].items()},
        internal={p: tuple(m) for p, m in data["internal"].items()},
        excluded=frozenset(data["excluded_from_scan"]),
        structural=load_structural(),
        removed=load_removed(),
        registry=registry(),
        tokens=unit_tokens(),
        result_classes=frozenset(load_result_classes()),
    )


# ---- collecting the public callables ----------------------------------------------------------------------------

def public_names(module: types.ModuleType) -> list[str]:
    names = getattr(module, "__all__", None)
    if names is None:
        raise AssertionError(f"public module {module.__name__} has no __all__")
    return list(names)


def _constructor(cls: type, roots: Iterable[str]) -> inspect.Signature | None:
    # The first class in the MRO that defines __init__ or __new__ owns the constructor. One
    # from outside the scanned packages (object, Exception, ...) has no parameters of ours.
    for k in cls.__mro__:
        if "__init__" in vars(k) or "__new__" in vars(k):
            if k is object or _root(k.__module__) not in roots:
                return None
            return inspect.signature(cls)
    return None


def _methods(cls: type, roots: Iterable[str]):
    seen: set[str] = set()
    for k in cls.__mro__:
        own = _root(k.__module__) in roots
        for name, attr in vars(k).items():
            if (name.startswith("_") and name != "__call__") or name in seen:
                continue
            seen.add(name)
            if not own:
                continue
            if isinstance(attr, staticmethod):
                fn, drop = attr.__func__, 0
            elif isinstance(attr, classmethod):
                fn, drop = attr.__func__, 1
            elif inspect.isfunction(attr):
                fn, drop = attr, 1
            else:
                continue
            sig = inspect.signature(fn)
            params = list(sig.parameters.values())
            if drop and params and params[0].kind in (inspect.Parameter.POSITIONAL_ONLY,
                                                      inspect.Parameter.POSITIONAL_OR_KEYWORD):
                params = params[1:]
            yield Item(fn.__module__, fn.__qualname__, sig.replace(parameters=params), fn)


def public_items(module: types.ModuleType, roots: Iterable[str],
                 result_classes: Iterable[tuple[str, str]] = ()) -> tuple[list[Item], list[str]]:
    """The callables reached through ``module.__all__``, and the names that re-export a foreign callable.

    A class in ``result_classes`` contributes its methods but not its constructor.
    """
    roots, result_classes = tuple(roots), frozenset(result_classes)
    items: dict[tuple[str, str], Item] = {}
    foreign: list[str] = []
    for name in public_names(module):
        obj = getattr(module, name)
        if isinstance(obj, types.ModuleType) or not callable(obj):
            continue
        if _root(getattr(obj, "__module__", None)) not in roots:
            foreign.append(f"{module.__name__}.{name} re-exports {getattr(obj, '__module__', '?')}.{name}")
            continue
        if inspect.isclass(obj):
            sig = None if (obj.__module__, obj.__qualname__) in result_classes else _constructor(obj, roots)
            if sig is not None:
                items.setdefault((obj.__module__, obj.__qualname__), Item(obj.__module__, obj.__qualname__, sig, obj))
            for m in _methods(obj, roots):
                items.setdefault((m.module, m.name), m)
        else:
            qualname = getattr(obj, "__qualname__", name)
            items.setdefault((obj.__module__, qualname), Item(obj.__module__, qualname, inspect.signature(obj), obj))
    return list(items.values()), foreign


# ---- the parameter rule -----------------------------------------------------------------------------------------

def structural_entry(name: str, module: str, rules: Rules) -> Structural | None:
    entry = rules.structural.get(name)
    if entry is None or (entry.scope and not _within(module, entry.scope)):
        return None
    return entry


def is_dimensional_default(default: object, unit: str) -> bool:
    if default is None or isinstance(default, (bool, str)):
        return False
    return unit != "1"


def parameter_reasons(module: str, param: inspect.Parameter, rules: Rules) -> list[str]:
    """The reasons one parameter of a callable defined in ``module`` breaks the rule (empty: it complies)."""
    name = param.name
    reasons = []
    entry = structural_entry(name, module, rules)
    if unit_token(name, rules.tokens) and not (entry and entry.unit_token_note):
        reasons.append("unit-suffix")
    if entry is not None:
        return reasons
    quantity = rules.registry.get(name)
    if quantity is None:
        return reasons + ["unregistered"]
    places, unit = quantity
    if "api" not in places:
        reasons.append("no-api-place")
    if param.kind not in _KEYWORD:
        reasons.append("positional")
    if param.default is not inspect.Parameter.empty and is_dimensional_default(param.default, unit):
        reasons.append("dimensional-default")
    return reasons


def quantity_parameters(item: Item, rules: Rules) -> list[str]:
    """The parameters of ``item`` that are registry quantities (not structural)."""
    return [p.name for p in item.signature.parameters.values()
            if structural_entry(p.name, item.module, rules) is None and p.name in rules.registry]


def violations(items: Iterable[Item], rules: Rules) -> set[tuple[str, str, str, str]]:
    found = set()
    for item in items:
        for param in item.signature.parameters.values():
            for reason in parameter_reasons(item.module, param, rules):
                found.add((item.module, item.name, param.name, reason))
    return found


def scanned_modules(package: str, rules: Rules) -> list[types.ModuleType]:
    return [importlib.import_module(m) for m in rules.public[package] if m not in rules.excluded]


def package_items(package: str, rules: Rules) -> tuple[dict[str, list[Item]], list[str]]:
    """Per scanned public module, its callables; and every foreign re-export."""
    per_module, foreign = {}, []
    for module in scanned_modules(package, rules):
        items, bad = public_items(module, rules.packages, rules.result_classes)
        per_module[module.__name__] = items
        foreign += bad
    return per_module, foreign


def package_violations(package: str, rules: Rules) -> set[tuple[str, str, str, str]]:
    per_module, _ = package_items(package, rules)
    unique = {(i.module, i.name): i for items in per_module.values() for i in items}
    return violations(unique.values(), rules)


# ---- the allowlist ----------------------------------------------------------------------------------------------

def load_allowlist(path: Path) -> list[tuple[str, str, str, str]]:
    data = _read(path)
    if data.get("schema") != ALLOWLIST_SCHEMA or data.get("fields") != ALLOWLIST_FIELDS:
        raise ValueError(f"{path}: expected schema {ALLOWLIST_SCHEMA} with fields {ALLOWLIST_FIELDS}")
    return [tuple(e) for e in data["entries"]]


def format_allowlist(package: str, entries: Iterable[tuple[str, str, str, str]]) -> str:
    """The canonical text of an allowlist file: sorted, one entry per line."""
    entries = sorted(set(entries))
    lines = [
        "{",
        f'  "schema": {json.dumps(ALLOWLIST_SCHEMA)},',
        f'  "package": {json.dumps(package)},',
        '  "rule": "Violations of the public-API units scan (tests/_support/api_scan.py) that exist today. '
        'Entries may only be removed; a new violation and an entry that no longer matches one both fail.",',
        f'  "fields": {json.dumps(ALLOWLIST_FIELDS)},',
        '  "entries": [',
    ]
    body = [f"    {json.dumps(list(e), ensure_ascii=False)}" for e in entries]
    lines.append(",\n".join(body))
    lines += ["  ]", "}", ""]
    if not body:
        lines.pop(-4)
    return "\n".join(lines)


def allowlist_problems(package: str, path: Path, rules: Rules) -> list[str]:
    """New violations and stale entries of one package's allowlist."""
    allowed = load_allowlist(path)
    found = package_violations(package, rules)
    problems = []
    for e in sorted(found - set(allowed)):
        problems.append(f"new violation {e}: {REASONS[e[3]]}")
    for e in sorted(set(allowed) - found):
        problems.append(f"stale allowlist entry {e}: it no longer matches a violation; remove it")
    return problems


def allowlist_format_problems(package: str, path: Path, baseline: int | None = None) -> list[str]:
    """The file is canonical, its entries belong to ``package``, and it holds no more than the baseline."""
    baseline = BASELINE_COUNTS[package] if baseline is None else baseline
    entries = load_allowlist(path)
    problems = []
    if path.read_text(encoding="utf-8") != format_allowlist(package, entries):
        problems.append(f"{path.name} is not in canonical form (sorted, unique, one entry per line)")
    for e in entries:
        if len(e) != 4 or e[3] not in REASONS:
            problems.append(f"bad entry {e}")
        elif _root(e[0]) != package:
            problems.append(f"entry {e} does not belong to {package}")
    if len(entries) > baseline:
        problems.append(f"{len(entries)} entries, more than the baseline {baseline}: entries may only be removed")
    return problems


def clean_modules(package: str, path: Path, rules: Rules) -> list[str]:
    """The scanned public modules of ``package`` none of whose callables has an allowlist entry."""
    keys = {(e[0], e[1]) for e in load_allowlist(path)}
    per_module, _ = package_items(package, rules)
    return [m for m, items in per_module.items() if not any((i.module, i.name) in keys for i in items)]


# ---- modules ----------------------------------------------------------------------------------------------------

def walk_modules(package: str) -> set[str]:
    """Every module of ``package`` whose dotted name has no part starting with an underscore."""
    root = importlib.import_module(package)

    def fail(name):
        raise ImportError(f"cannot import {name}")

    names = {package} | {m.name for m in pkgutil.walk_packages(root.__path__, package + ".", onerror=fail)}
    return {n for n in names if not any(part.startswith("_") for part in n.split("."))}


def module_problems(package: str, rules: Rules) -> list[str]:
    """Every non-underscore module is on exactly one list; internal ones say so; public ones define ``__all__``."""
    found = walk_modules(package)
    public, internal = set(rules.public[package]), set(rules.internal[package])
    problems = [f"{m} is on neither the public nor the internal module list" for m in sorted(found - public - internal)]
    problems += [f"{m} is listed but does not exist" for m in sorted((public | internal) - found)]
    problems += [f"{m} is on both module lists" for m in sorted(public & internal)]
    for m in sorted(internal & found):
        doc = importlib.import_module(m).__doc__ or ""
        if INTERNAL_DOCSTRING not in doc:
            problems.append(f"internal module {m}: its docstring does not say {INTERNAL_DOCSTRING!r}")
    for m in sorted(public & found):
        module = importlib.import_module(m)
        names = getattr(module, "__all__", None)
        if names is None:
            problems.append(f"public module {m} has no __all__")
            continue
        if len(set(names)) != len(names):
            problems.append(f"public module {m}: __all__ repeats a name")
        for n in names:
            if not hasattr(module, n):
                problems.append(f"public module {m}: __all__ names {n!r}, which it does not define")
    return problems


def structural_problems(rules: Rules) -> list[str]:
    """The closed structural list is well formed: mesher names are scoped, unit tokens are explained."""
    problems = []
    for e in rules.structural.values():
        if e.category == "mesher, pending" and e.scope != MESHER_SCOPE:
            problems.append(f"{e.name}: 'mesher, pending' applies only to {MESHER_SCOPE}, not {e.scope}")
        if unit_token(e.name, rules.tokens) and not e.unit_token_note:
            problems.append(f"{e.name} ends in unit token {unit_token(e.name, rules.tokens)!r} with no note")
        if e.unit_token_note and not unit_token(e.name, rules.tokens):
            problems.append(f"{e.name} has a unit-token note but ends in no unit token")
        if not e.source:
            problems.append(f"{e.name} has no source")
        if e.category == DEFERRED and not (e.closing and e.reviewer_note):
            problems.append(f"{e.name}: a '{DEFERRED}' entry names its closing condition and has a reviewer note")
        if e.closing and e.category != DEFERRED:
            problems.append(f"{e.name}: only a '{DEFERRED}' entry has a closing condition")
    return problems


# ---- clauses that apply once a module is clean ------------------------------------------------------------------

StringCase = Callable[[], tuple[Callable, dict]]


def string_refusal_problems(package: str, path: Path, rules: Rules, cases: Mapping[str, StringCase]) -> list[str]:
    """For each clean module, a ``str`` given to each quantity parameter raises TypeError.

    ``cases`` maps ``"module:callable"`` to a function returning a callable and keyword
    arguments that make a valid call; the call must succeed as given, and fail with
    TypeError once any one quantity parameter is replaced by a string.
    """
    problems, used = [], set()
    per_module, _ = package_items(package, rules)
    for modname in clean_modules(package, path, rules):
        for item in per_module[modname]:
            quantities = quantity_parameters(item, rules)
            if not quantities:
                continue
            key = f"{item.module}:{item.name}"
            used.add(key)
            if key not in cases:
                problems.append(f"{key} (public through {modname}, which has no allowlist entries) needs a "
                                f"string-refusal case for {quantities}")
                continue
            target, kwargs = cases[key]()
            try:
                target(**kwargs)
            except Exception as exc:        # noqa: BLE001 - the case itself must be a valid call
                problems.append(f"{key}: the string-refusal case is not a valid call ({type(exc).__name__}: {exc})")
                continue
            for name in quantities:
                try:
                    target(**{**kwargs, name: "1"})
                except TypeError:
                    continue
                except Exception as exc:    # noqa: BLE001
                    problems.append(f"{key}: a str for {name} raised {type(exc).__name__}, not TypeError")
                else:
                    problems.append(f"{key}: a str for {name} was accepted")
    problems += [f"string-refusal case {k} matches no quantity callable of a clean module" for k in
                 sorted(set(cases) - used)]
    return problems


def removed_name_problems(package: str, path: Path, rules: Rules) -> list[str]:
    """For each clean module, every removed name of ``package`` is absent from its namespace."""
    entries = [r for r in rules.removed if r.package == package]
    if not entries:
        return []
    per_module, _ = package_items(package, rules)
    problems = []
    for modname in clean_modules(package, path, rules):
        problems += removed_in_module(importlib.import_module(modname), per_module[modname], entries)
    return problems


def removed_in_module(module: types.ModuleType, items: list[Item], entries: Iterable[Removed]) -> list[str]:
    problems = []
    names = set(public_names(module))
    for r in entries:
        if r.kind == "name":
            if r.name in names or hasattr(module, r.name):
                problems.append(f"{module.__name__}.{r.name} still exists ({r.source})")
        elif r.kind == "parameter":
            for item in items:
                if r.name in item.signature.parameters:
                    problems.append(f"{item.module}:{item.name} still takes {r.name} ({r.source})")
        else:
            cls_name, attr = r.name.split(".", 1)
            for n in names:
                obj = getattr(module, n)
                if inspect.isclass(obj) and obj.__name__ == cls_name:
                    fields = {f.name for f in dataclasses.fields(obj)} if dataclasses.is_dataclass(obj) else set()
                    if hasattr(obj, attr) or attr in fields:
                        problems.append(f"{module.__name__}.{n}.{attr} still exists ({r.source})")
    return problems


def kernel_disjointness(package: str, rules: Rules) -> list[str] | None:
    """Public names and objects of ``package`` against ``<package>.kernels``; None while that namespace is absent."""
    name = f"{package}.kernels"
    if importlib.util.find_spec(name) is None:
        return None
    kernels = importlib.import_module(name)
    knames = set(getattr(kernels, "__all__", [n for n in vars(kernels) if not n.startswith("_")]))
    kobjects = {id(getattr(kernels, n)): n for n in knames
                if not isinstance(getattr(kernels, n), types.ModuleType)}
    problems = []
    for module in scanned_modules(package, rules):
        modname = module.__name__
        for n in public_names(module):
            obj = getattr(module, n)
            if obj is kernels:
                problems.append(f"{modname}.__all__ names {name}, an internal namespace")
                continue
            if n in knames:
                problems.append(f"{modname}.{n} has the name of a kernel")
            if not isinstance(obj, types.ModuleType) and id(obj) in kobjects:
                problems.append(f"{modname}.{n} is the kernel {name}.{kobjects[id(obj)]}")
    return problems
