# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Save the wall example with an explicit, local reproducibility record."""
import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import subprocess

from simcase import Document, run


def git_value(root, *args):
    try:
        return subprocess.check_output(['git', '-C', str(root), *args],
                                       text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path, help='new or empty result directory')
    args = parser.parse_args()
    source = Path(__file__).with_name('layered_wall.json')
    root = Path(__file__).resolve().parents[2]
    revision = git_value(root, 'rev-parse', 'HEAD')
    status = git_value(root, 'status', '--porcelain')
    started = datetime.now(timezone.utc).isoformat()
    input_bytes = source.read_bytes()
    document = Document.from_dict(json.loads(input_bytes))
    result = run(document, verbose=False)
    folder = result.save(args.output)
    (folder / 'input.json').write_bytes(input_bytes)
    record = {
        'schema': 'openphysics.example-run-record/1',
        'started_utc': started,
        'finished_utc': datetime.now(timezone.utc).isoformat(),
        'git_commit': revision,
        'git_dirty_before_run': None if status is None else bool(status),
        'python': platform.python_version(),
        'platform': platform.platform(),
        'package_versions': {name: version(name) for name in
                             ('galerkin', 'meshine', 'physmat', 'simcase', 'numpy', 'scipy', 'shapely')},
        'example': 'examples/simcase/record_wall_run.py',
        'materials': document.data['materials'],
        'convergence': 'not_checked',
        'sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in sorted(folder.iterdir()) if p.is_file()},
    }
    (folder / 'run-record.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(f'Saved result and run-record.json: {folder}')
    return folder, record


if __name__ == '__main__':
    main()
