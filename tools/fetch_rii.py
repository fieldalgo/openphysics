# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Fetch the pinned CC0 refractiveindex.info dataset into a dedicated directory."""

import argparse
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    dest = args.destination.resolve()
    revision = Path(__file__).with_name("rii-revision.txt").read_text().strip()
    if len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
        raise ValueError("rii-revision.txt must contain a full Git commit ID")
    # Never reset an existing dataset or worktree. A valid cached copy is reusable.
    if dest.exists() and any(dest.iterdir()):
        head = subprocess.check_output(["git", "-C", str(dest), "rev-parse", "HEAD"], text=True).strip()
        dirty = subprocess.check_output(["git", "-C", str(dest), "status", "--porcelain"], text=True)
        if head != revision or dirty:
            raise RuntimeError("destination is not a clean copy of the pinned revision; use a new directory")
    else:
        dest.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init", str(dest)], check=True)
        subprocess.run(["git", "-C", str(dest), "fetch", "--depth", "1",
                        "https://github.com/polyanskiy/refractiveindex.info-database.git", revision], check=True)
        subprocess.run(["git", "-C", str(dest), "checkout", "--detach", revision], check=True)
    if not (dest / "database" / "catalog-nk.yml").is_file():
        raise FileNotFoundError("pinned checkout does not contain catalog-nk.yml")
    print(f"RII {revision}: {dest / 'database'}")


if __name__ == "__main__":
    main()
