# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Static reference import boundaries. Reads tracked first-party files, never imports them."""
import ast
import fnmatch
import json
from pathlib import Path, PurePosixPath
import subprocess
import time
import tomllib

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from check_licenses import STRONG_COPYLEFT, never_pattern, parse_expression, satisfies

ROOT = Path(__file__).resolve().parents[1]


def tracked_files(root):
    result = subprocess.run(['git', '-C', str(root), 'ls-files', '-z'], check=True,
                            capture_output=True).stdout
    return sorted(set(p.decode('utf-8') for p in result.split(b'\0') if p))


def zone(path):
    p = PurePosixPath(path)
    if p.name == 'conftest.py':
        return 'always'
    if p.parts[0] == 'packages':
        return 'shipped'
    if p.parts[0] == 'examples':
        return 'examples'
    if p.parts[0] in {'studies', 'benchmarks'}:
        return 'study'
    if p.parts[0] == 'tools':
        return 'always'
    if p.parts[0] == 'tests':
        if len(p.parts) > 1 and p.parts[1] == '_support':
            return 'always'
        if len(p.parts) == 5 and p.parts[2] == 'reference_values' and p.name.startswith('generate_'):
            return 'generator'
        if p.name.startswith('test_') or p.name.endswith('_test.py'):
            return 'test'
        return 'always'
    return None


def main_guard(node):
    if not isinstance(node, ast.Compare) or len(node.ops) != 1 or not isinstance(node.ops[0], ast.Eq):
        return False
    left, right = node.left, node.comparators[0]
    return ((isinstance(left, ast.Name) and left.id == '__name__' and
             isinstance(right, ast.Constant) and right.value == '__main__') or
            (isinstance(right, ast.Name) and right.id == '__name__' and
             isinstance(left, ast.Constant) and left.value == '__main__'))


def imports(tree):
    """(name, eagerly evaluated, line, relative level). Resolve literal loader aliases."""
    aliases = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            aliases.update((a.asname or a.name, a.name) for a in n.names)
        elif isinstance(n, ast.ImportFrom):
            aliases.update((a.asname or a.name, f'{n.module}.{a.name}') for a in n.names)
    found = []

    def dotted(n):
        if isinstance(n, ast.Name):
            return aliases.get(n.id, n.id)
        if isinstance(n, ast.Attribute):
            return dotted(n.value) + '.' + n.attr
        return ''

    def visit(n, eager=True):
        if isinstance(n, ast.Import):
            found.extend((a.name, eager, n.lineno, 0) for a in n.names)
        elif isinstance(n, ast.ImportFrom):
            found.append((n.module or '', eager, n.lineno, n.level))
            found.extend((f'{n.module}.{a.name}' if n.module else a.name, eager, n.lineno, n.level)
                         for a in n.names if a.name != '*')
        elif isinstance(n, ast.Call):
            name = dotted(n.func)
            if (name in {'__import__', 'importlib.import_module', 'pytest.importorskip'} or
                    name.split('.')[-1] == 'require_tool'):
                if n.args and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str):
                    found.append((n.args[0].value, eager, n.lineno, 0))
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            # Defaults and decorators run at definition time, unlike function bodies.
            for child in [*getattr(n, 'decorator_list', []), *n.args.defaults,
                          *(x for x in n.args.kw_defaults if x is not None)]:
                visit(child, eager)
            if getattr(n, 'returns', None):
                visit(n.returns, eager)
            for arg in [*n.args.posonlyargs, *n.args.args, *n.args.kwonlyargs]:
                if arg.annotation:
                    visit(arg.annotation, eager)
            body = n.body if isinstance(n.body, list) else [n.body]
            for child in body:
                visit(child, False)
            return
        if isinstance(n, ast.If) and main_guard(n.test):
            for child in n.body:
                visit(child, False)
            for child in n.orelse:
                visit(child, eager)
            return
        for child in ast.iter_child_nodes(n):
            visit(child, eager)
    visit(tree)
    return found


def extra_errors(root, paths, inventory):
    """Walk first-party dependency edges conservatively across all environment markers."""
    projects = {}
    for path in paths:
        if path.startswith('packages/') and path.endswith('/pyproject.toml'):
            project = tomllib.loads((root / path).read_text(encoding='utf-8')).get('project', {})
            if 'name' in project:
                projects[canonicalize_name(project['name'])] = project
    tests = set(inventory['policy'].get('test_extras', ['test']))
    entries = {**inventory.get('external_tools', {}), **inventory['distributions']}
    references = {canonicalize_name(n) for n, e in entries.items() if 'reference' in e}
    nonpermissive = {canonicalize_name(n) for n, e in entries.items()
                     if 'reference' in e and not satisfies(parse_expression(e['spdx']),
                                                           set(inventory['policy']['permissive']))}
    errors = []
    for start, project in projects.items():
        for extra in ['', *project.get('optional-dependencies', {})]:
            strict = extra not in tests
            pending = [(start, extra)]
            seen = set()
            while pending:
                name, active = pending.pop()
                if (name, active) in seen:
                    continue
                seen.add((name, active))
                current = projects[name]
                lines = list(current.get('dependencies', []))
                if active:
                    lines += current.get('optional-dependencies', {}).get(active, [])
                for line in lines:
                    req = Requirement(line)
                    target = canonicalize_name(req.name)
                    requested = {canonicalize_name(e) for e in req.extras}
                    where = f'{start}[{extra}] -> {line}'
                    if target in nonpermissive or (strict and target in references):
                        errors.append(f'{where}: reference tool reachable from published dependency')
                    if strict and target in projects and requested & tests:
                        errors.append(f'{where}: non-test dependency reaches test extra')
                    if start == 'openphysics' and target == 'gmsh':
                        errors.append(f'{where}: meta distribution reaches gmsh')
                    if target in projects:
                        pending.extend((target, e) for e in requested | {''})
    return errors


def check(root=ROOT, inventory=None):
    root = Path(root)
    inventory = inventory or json.loads((root / 'tools/third_party_licenses.json').read_text(encoding='utf-8'))
    paths = tracked_files(root)
    entries = {**inventory.get('external_tools', {}), **inventory['distributions']}
    forbidden = never_pattern(['SSPL', 'EUPL', 'OSL', 'CPAL', 'RPL'])
    tools, errors = {}, []
    for name, entry in entries.items():
        if forbidden.search(entry['spdx']):
            errors.append(f'{name}: forbidden license family {entry["spdx"]}')
        ref = entry.get('reference')
        external = entry.get('external_process')
        if not ref and not external and not STRONG_COPYLEFT.search(entry['spdx']):
            continue
        modules = (ref or {}).get('modules', []) + (external or {}).get('forbidden_imports', [])
        for module in [name, name.replace('-', '_'), *modules]:
            tools[module] = (name, entry)
    trees = {p: imports(ast.parse((root / p).read_text(encoding='utf-8'), filename=p))
             for p in paths if p.endswith('.py')}
    eager_bad = set()
    for path, loads in trees.items():
        kind = zone(path)
        if kind is None:
            errors.append(f'{path}: unclassified Python file')
        for module, eager, line, relative in loads:
            if relative:
                continue
            hit = tools.get(module) or tools.get(module.split('.')[0])
            if hit is None:
                continue
            name, entry = hit
            ref = entry.get('reference', {})
            restricted = not satisfies(parse_expression(entry['spdx']), set(inventory['policy']['permissive']))
            where = f'{path}:{line}: {name}'
            if 'external_process' in entry:
                errors.append(f'{where}: external-process tool must not be imported')
            if restricted:
                if not ref and 'external_process' not in entry:
                    errors.append(f'{where}: restricted tool needs reference importer review')
                if kind == 'test' and entry['spdx'].startswith(('LGPL', 'MPL', 'EPL', 'CDDL', 'CECILL')) and not entry.get('test_only'):
                    errors.append(f'{where}: weak-copyleft test tool needs test_only')
                if 'AGPL' in entry['spdx'].upper() and not ref.get('agpl_review'):
                    errors.append(f'{where}: AGPL needs agpl_review')
                if eager:
                    eager_bad.add(path)
                if kind not in {'test', 'generator', 'study'}:
                    errors.append(f'{where}: non-permissive import in {kind} zone')
                if kind == 'test' and eager:
                    errors.append(f'{where}: test import must be lazy')
            if ref and not any(fnmatch.fnmatchcase(path, p) for p in ref.get('imported_by', [])):
                errors.append(f'{where}: importer not listed')
    # One-level eager import from default-loaded modules into studies/generators.
    for path, loads in trees.items():
        if zone(path) in {'study', 'generator'}:
            continue
        for module, eager, line, relative in loads:
            if not eager:
                continue
            bases = [PurePosixPath('.'), PurePosixPath(path).parent]
            if relative:
                base = PurePosixPath(path).parent
                for _ in range(relative - 1):
                    base = base.parent
                bases = [base]
            for base in bases:
                target = base.joinpath(*module.split('.'))
                for candidate in [str(target) + '.py', str(target / '__init__.py')]:
                    if candidate in eager_bad:
                        errors.append(f'{path}:{line}: eager import reaches non-permissive module {candidate}')
    errors += extra_errors(root, paths, inventory)
    return sorted(set(errors))


if __name__ == '__main__':
    start = time.perf_counter()
    errors = check()
    print('\n'.join(errors) if errors else 'Reference import zones passed')
    print(f'Scan seconds: {time.perf_counter() - start:.3f}')
    raise SystemExit(bool(errors))
