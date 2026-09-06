# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Drive the Gmsh executable as a separate process.

Gmsh is GPL-licensed. This package never links against it or imports its
Python API; it writes a ``.geo`` script, invokes the ``gmsh`` command-line
program, and reads the resulting ``.msh`` file. That keeps the solver code
that uses this package free to choose its own license.

The executable is found from, in order: the ``GMSH_EXECUTABLE`` environment
variable, ``gmsh`` on PATH, and the binary shipped with the ``gmsh`` PyPI
wheel if it happens to be installed.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .mesh import Mesh
from .msh import read_msh


class GmshNotFound(RuntimeError):
    pass


def find_gmsh() -> str | None:
    """Path to the gmsh executable, or None."""
    env = os.environ.get("GMSH_EXECUTABLE")
    if env and Path(env).exists():
        return env
    on_path = shutil.which("gmsh")
    if on_path:
        return on_path
    # the PyPI wheel installs a launcher script next to the interpreter
    cand = Path(sys.executable).with_name("gmsh")
    if cand.exists():
        return str(cand)
    return None


def gmsh_version() -> str | None:
    exe = find_gmsh()
    if exe is None:
        return None
    out = subprocess.run([exe, "-version"], capture_output=True, text=True)
    return (out.stdout + out.stderr).strip().splitlines()[-1]


def generate(geo: str | Path, dim: int, *, out: str | Path | None = None,
             clmax: float | None = None, clmin: float | None = None,
             order: int = 1, algorithm: int | None = None,
             extra_args: tuple[str, ...] = (), verbosity: int = 1,
             keep_geo: bool = False) -> Mesh:
    """Mesh a ``.geo`` script (path or literal text) with Gmsh and read it back.

    Parameters
    ----------
    geo : path to a .geo file, or the script text itself
    dim : 1, 2 or 3 — highest dimension to mesh
    out : where to write the .msh (default: temporary file, removed afterwards)
    clmax, clmin : global characteristic-length bounds (``-clmax``/``-clmin``)
    order : element order (1 = linear, 2 = quadratic)
    algorithm : Gmsh 2D/3D algorithm id (``-algo``), e.g. 6 = Frontal-Delaunay
    extra_args : any further command-line flags
    verbosity : Gmsh ``-v`` level; 0 silences it
    """
    exe = find_gmsh()
    if exe is None:
        raise GmshNotFound("gmsh executable not found; install Gmsh (https://gmsh.info) "
                           "or `pip install gmsh`, or set GMSH_EXECUTABLE")
    if dim not in (1, 2, 3):
        raise ValueError("dim must be 1, 2 or 3")

    tmpdir = tempfile.mkdtemp(prefix="gmshio_")
    try:
        geo_path = Path(geo) if _looks_like_path(geo) else None
        if geo_path is None:
            geo_path = Path(tmpdir) / "model.geo"
            geo_path.write_text(str(geo))
        msh_path = Path(out) if out is not None else Path(tmpdir) / "model.msh"

        cmd = [exe, f"-{dim}", str(geo_path), "-format", "msh41", "-o", str(msh_path),
               "-order", str(order), "-v", str(verbosity)]
        if clmax is not None:
            cmd += ["-clmax", repr(float(clmax))]
        if clmin is not None:
            cmd += ["-clmin", repr(float(clmin))]
        if algorithm is not None:
            cmd += ["-algo", str(algorithm)]
        cmd += list(extra_args)

        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0 or not msh_path.exists():
            raise RuntimeError("gmsh failed:\n" + proc.stdout + proc.stderr)
        mesh = read_msh(msh_path)
        if keep_geo and out is not None and geo_path.parent == Path(tmpdir):
            shutil.copy(geo_path, Path(out).with_suffix(".geo"))
        return mesh
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _looks_like_path(geo: str | Path) -> bool:
    if isinstance(geo, Path):
        return True
    s = str(geo)
    if "\n" in s or ";" in s:
        return False
    return Path(s).exists()
