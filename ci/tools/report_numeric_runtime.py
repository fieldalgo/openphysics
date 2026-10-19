# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Record the CPU model and the BLAS kernel numpy actually uses.

Hosted runners are fresh virtual machines whose CPU model can change between
runs, and numpy's bundled OpenBLAS selects its kernel from that CPU at import
time. Last-bit floating-point results can therefore differ between two runs of
the same commit. This report puts the evidence in the log and artifacts.

With ``--expect-core NAME`` the script fails unless OpenBLAS reports that core,
so a forced ``OPENBLAS_CORETYPE`` cannot silently fall back to another kernel.
"""
import argparse
import ctypes
import glob
import io
import json
import os
import platform
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path


def cpu_model() -> str:
    system = platform.system()
    try:
        if system == "Linux":
            for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
                if line.lower().startswith("model name"):
                    return line.split(":", 1)[1].strip()
        if system == "Darwin":
            return subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True,
                                  text=True, check=True).stdout.strip()
        if system == "Windows":
            return os.environ.get("PROCESSOR_IDENTIFIER", "") or platform.processor()
    except (OSError, subprocess.SubprocessError):
        pass
    return platform.processor() or "unknown"


def openblas_core():
    """Kernel name reported by numpy's bundled OpenBLAS, or None (e.g. Accelerate)."""
    import numpy as np
    base = Path(np.__file__).resolve().parent
    patterns = [base.parent / "numpy.libs" / "*openblas*", base / ".dylibs" / "*openblas*"]
    for pattern in patterns:
        for path in sorted(glob.glob(str(pattern))):
            try:
                if hasattr(os, "add_dll_directory"):
                    os.add_dll_directory(str(Path(path).parent))
                library = ctypes.CDLL(path)
            except OSError:
                continue
            for symbol in ("scipy_openblas_get_corename64_", "scipy_openblas_get_corename",
                           "openblas_get_corename64_", "openblas_get_corename"):
                function = getattr(library, symbol, None)
                if function is not None:
                    function.restype = ctypes.c_char_p
                    return function().decode()
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, help="also write the report to this file")
    parser.add_argument("--expect-core", help="fail unless OpenBLAS reports this kernel")
    args = parser.parse_args()
    import numpy as np
    runtime = io.StringIO()
    with redirect_stdout(runtime):
        np.show_runtime()
    report = {
        "platform": platform.platform(), "machine": platform.machine(), "cpu_model": cpu_model(),
        "python": sys.version.split()[0], "numpy": np.__version__, "openblas_core": openblas_core(),
        "OPENBLAS_CORETYPE": os.environ.get("OPENBLAS_CORETYPE"),
        "threads": {name: os.environ.get(name) for name in
                    ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")},
    }
    print(json.dumps(report, indent=2))
    print(runtime.getvalue())
    if args.json:
        report["numpy_show_runtime"] = runtime.getvalue()
        args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.expect_core and (report["openblas_core"] or "").lower() != args.expect_core.lower():
        print(f"error: expected OpenBLAS core {args.expect_core}, got {report['openblas_core']}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
