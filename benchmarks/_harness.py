# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Shared provenance, worker launching and reporting of the solver benchmarks.

The benchmark scripts next to this file import it from their own directory. It
is not a package API: the scripts are run by hand from the repository root and
required CI does not run them.

Each sample runs in a fresh Python process with BLAS/OpenMP thread limits set
to one before NumPy and SciPy import. A worker prints one JSON object with
``status`` "ok", "error" or "skipped" and exits 0 unless it reports an error.
The parent records the checkout, the pinned requirements, the machine and every
sample, and checkpoints the report after each worker.
"""

import contextlib
from datetime import datetime, timezone
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
THREADS = ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
           "BLIS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "OMP_THREAD_LIMIT")
PACKAGES = ("galerkin", "simcase", "meshine", "physmat")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_identity(script):
    def git(*args):
        return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()

    files = sorted((ROOT / "packages/galerkin/src/galerkin").rglob("*.py"))
    return dict(revision=git("rev-parse", "HEAD"),
                checkout_dirty=bool(git("status", "--porcelain")),
                benchmark_sha256=digest(script),
                harness_sha256=digest(__file__),
                galerkin_sources_sha256={str(p.relative_to(ROOT)): digest(p) for p in files},
                pins_sha256=digest(ROOT / "tools/requirements-py312-linux.txt"))


def machine_info():
    def read(path):
        try:
            return Path(path).read_text().strip()
        except OSError:
            return None

    cpu = read("/proc/cpuinfo") or ""
    model = next((line.split(":", 1)[1].strip() for line in cpu.splitlines()
                  if line.startswith("model name")), platform.processor())
    return dict(python=sys.version, executable=sys.executable, platform=platform.platform(),
                cpu_model=model, logical_cpus=os.cpu_count(),
                affinity_cpus=len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
                cgroup_v2_cpu_max=read("/sys/fs/cgroup/cpu.max"),
                cgroup_v2_memory_max=read("/sys/fs/cgroup/memory.max"))


def peak_rss():
    """The calling worker's own lifetime peak RSS; never the parent's or RUSAGE_CHILDREN."""
    if sys.platform not in ("linux", "darwin"):
        return dict(peak_rss_mib=None, rss_method="unsupported platform")
    import resource

    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    unit = "bytes" if sys.platform == "darwin" else "KiB"
    return dict(peak_rss_mib=raw / (1024**2 if unit == "bytes" else 1024),
                peak_rss_raw=raw, peak_rss_raw_unit=unit,
                rss_method="worker resource.getrusage(RUSAGE_SELF).ru_maxrss")


def profiling_state():
    # CPython 3.12 cProfile uses sys.monitoring instead of the legacy profile hook.
    legacy_hook = sys.getprofile() is not None
    monitoring = getattr(sys, "monitoring", None)
    tool, events = None, 0
    if monitoring is not None:
        tool = monitoring.get_tool(monitoring.PROFILER_ID)
        events = monitoring.get_events(monitoring.PROFILER_ID)
    return dict(profiled=legacy_hook or bool(events),
                profiling=dict(legacy_hook_active=legacy_hook,
                               monitoring_profiler_tool=tool,
                               monitoring_profiler_events=events))


def checkout_imports(*names):
    """Import the packages and refuse an editable install from another checkout."""
    paths = {}
    for name in names:
        module = importlib.import_module(name)
        path = Path(module.__file__).resolve()
        if not path.is_relative_to(ROOT / "packages"):
            raise RuntimeError(f"{name} must be imported from this checkout, not {path}")
        paths[name] = str(path)
    return paths


def library_versions():
    import numpy as np
    import scipy

    versions = dict(numpy=np.__version__, scipy=scipy.__version__)
    builds = {}
    for name, module in (("numpy", np), ("scipy", scipy)):
        build = io.StringIO()
        with contextlib.redirect_stdout(build):
            module.show_config()
        builds[name + "_build_config"] = build.getvalue()
    return versions, builds


def timed(function, *args, **kwargs):
    """(result, wall seconds) of one call."""
    start = time.perf_counter()
    result = function(*args, **kwargs)
    return result, time.perf_counter() - start


class Skipped(Exception):
    """Raised by a worker whose optional dependency is absent; recorded, not failed."""


def worker(measure, labels, imports=PACKAGES):
    """Run one measurement in this process and return its JSON-ready sample.

    ``measure`` returns a dict of metrics; it must call ``peak_rss`` itself right
    after the work it measures and merge the result, or the sample gets the peak
    after all postprocessing.
    """
    sample = dict(labels, pid=os.getpid(), parent_pid=os.getppid(),
                  thread_environment={key: os.environ.get(key) for key in THREADS})
    sample.update(profiling_state())
    start = time.perf_counter()
    try:
        sample["import_paths"] = checkout_imports(*imports)
        versions, builds = library_versions()
        sample["versions"] = versions
        sample.update(builds)
        metrics = measure()
        if "peak_rss_mib" not in metrics:
            metrics.update(peak_rss())
        sample.update(metrics)
        sample.update(status="ok", worker_wall_seconds=time.perf_counter() - start)
    except Skipped as exc:
        sample.update(status="skipped", reason=str(exc))
    except Exception as exc:
        sample.update(peak_rss())
        sample.update(status="error", error_type=type(exc).__name__, error=str(exc),
                      traceback=traceback.format_exc(),
                      failed_wall_seconds=time.perf_counter() - start)
    return sample


def print_worker(sample):
    print(json.dumps(sample, allow_nan=False))
    return 0 if sample["status"] in ("ok", "skipped") else 1


def run_worker(script, argv, labels, timeout, env):
    command = [sys.executable, str(Path(script).resolve()), *argv]
    started = time.perf_counter()
    try:
        completed = subprocess.run(command, cwd=ROOT, env=env, capture_output=True,
                                   text=True, timeout=timeout)
        elapsed = time.perf_counter() - started
        try:
            sample = json.loads(completed.stdout)
            if not isinstance(sample, dict) or sample.get("status") not in ("ok", "error", "skipped"):
                raise ValueError("invalid worker result")
        except (ValueError, TypeError):
            sample = dict(status="error", error_type="WorkerProtocolError",
                          error="worker did not return a valid JSON result", stdout=completed.stdout)
        if completed.returncode and sample["status"] != "error":
            sample.update(status="error", error_type="WorkerExitError",
                          error="worker exited unsuccessfully after reporting success")
        sample.update(returncode=completed.returncode, stderr=completed.stderr)
    except subprocess.TimeoutExpired as exc:
        elapsed = time.perf_counter() - started

        def decoded(value):
            return value.decode(errors="replace") if isinstance(value, bytes) else value or ""
        sample = dict(status="timeout", timeout_seconds=timeout, returncode=None,
                      stdout=decoded(exc.stdout), stderr=decoded(exc.stderr),
                      peak_rss_mib=None, rss_method="unavailable: worker timed out")
    except OSError as exc:
        elapsed = time.perf_counter() - started
        sample = dict(status="error", error_type=type(exc).__name__, error=str(exc), returncode=None)
    sample.update(labels, subprocess_wall_seconds=elapsed)
    return sample


def summarize(runs, keys, metrics):
    """Median/min/max of each metric over the successful, unprofiled samples of each group."""
    summaries = []
    groups = sorted({tuple(r.get(k) for k in keys) for r in runs}, key=repr)
    for group in groups:
        selected = [r for r in runs if tuple(r.get(k) for k in keys) == group]
        successful = [r for r in selected if r["status"] == "ok"]
        skipped = [r for r in selected if r["status"] == "skipped"]
        good = [r for r in successful if not r.get("profiled", False)]
        summary = dict(zip(keys, group))
        summary.update(attempted=len(selected), succeeded=len(successful), skipped=len(skipped),
                       failed=len(selected) - len(successful) - len(skipped),
                       unprofiled_succeeded=len(good),
                       profiled_succeeded=len(successful) - len(good))
        if skipped:
            summary["skip_reasons"] = sorted({r.get("reason", "") for r in skipped})
        for metric in (*metrics, "subprocess_wall_seconds", "peak_rss_mib"):
            values = [r[metric] for r in good if r.get(metric) is not None]
            summary[metric] = (dict(median=statistics.median(values), min=min(values), max=max(values))
                               if values else None)
        summaries.append(summary)
    return summaries


def save_report(path, report):
    # The parent reserved the output once; replace only its own checkpoint.
    data = json.dumps(report, indent=2, allow_nan=False) + "\n"
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(data)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def reserve_output(parser, output):
    if output is None:
        parser.error("--output is required so interrupted or failed runs retain checkpoints")
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        output.open("x").close()
    except FileExistsError:
        parser.error("--output must not exist")


def run_parent(script, output, jobs, repeats, timeout, settings, keys, metrics):
    """Run every job ``repeats`` times in fresh processes and write the report.

    ``jobs`` is a list of ``(labels, argv)``; one repetition runs every job before
    the next repetition starts, so drift shows in every group instead of one.
    Returns the process exit status: 0 when the source stayed unchanged and no
    sample failed (skipped samples do not fail the run).
    """
    env = os.environ.copy()
    env.update({key: "1" for key in THREADS})
    report = dict(schema_version=1, benchmark=Path(script).name,
                  started_utc=datetime.now(timezone.utc).isoformat(),
                  source=source_identity(script), machine=machine_info(),
                  settings=dict(settings, repeats=repeats, timeout_seconds=timeout,
                                thread_environment={key: env[key] for key in THREADS},
                                execution_order="repetition, then jobs in the listed order; sequential"),
                  expected_runs=len(jobs) * repeats, completed=False, runs=[], summary=[])
    save_report(output, report)
    for repetition in range(1, repeats + 1):
        for labels, argv in jobs:
            sample = run_worker(script, argv, labels, timeout, env)
            sample["repetition"] = repetition
            report["runs"].append(sample)
            report["summary"] = summarize(report["runs"], keys, metrics)
            save_report(output, report)
            shown = " ".join(f"{k}={v}" for k, v in labels.items())
            detail = "" if sample["status"] != "skipped" else f" ({sample.get('reason', '')})"
            print(f"{shown} repeat={repetition}: {sample['status']}{detail} "
                  f"process={sample['subprocess_wall_seconds']:.3f}s", file=sys.stderr, flush=True)
    report.update(completed=True, ended_utc=datetime.now(timezone.utc).isoformat(),
                  source_at_end=source_identity(script))
    report["source_unchanged"] = report["source"] == report["source_at_end"]
    save_report(output, report)
    return 0 if report["source_unchanged"] and all(
        r["status"] in ("ok", "skipped") for r in report["runs"]) else 1
