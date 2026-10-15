# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Measure PEC cavity solves in fresh processes; no solver or timing gate changes."""

import argparse
import contextlib
from datetime import datetime, timezone
import hashlib
import io
import json
import math
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
CASES = {"cube": (1.0, 1.0, 1.0), "rectangle": (1.0, 0.8, 0.6)}
THREADS = ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
           "BLIS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "OMP_THREAD_LIMIT")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_identity():
    def git(*args):
        return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()

    files = sorted((ROOT / "packages/galerkin/galerkin").rglob("*.py"))
    return dict(revision=git("rev-parse", "HEAD"),
                checkout_dirty=bool(git("status", "--porcelain")),
                benchmark_sha256=digest(Path(__file__).resolve()),
                galerkin_sources_sha256={str(p.relative_to(ROOT)): digest(p) for p in files},
                pins_sha256=digest(ROOT / "ci/requirements-py312-linux.txt"))


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
    # Only the measuring worker calls this. Never query the parent or RUSAGE_CHILDREN.
    if sys.platform not in ("linux", "darwin"):
        return dict(peak_rss_mib=None, rss_method="unsupported platform")
    import resource

    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    unit = "bytes" if sys.platform == "darwin" else "KiB"
    return dict(peak_rss_mib=raw / (1024**2 if unit == "bytes" else 1024),
                peak_rss_raw=raw, peak_rss_raw_unit=unit,
                rss_method="worker resource.getrusage(RUSAGE_SELF).ru_maxrss")


def profiling_state():
    # CPython 3.12 cProfile uses monitoring instead of the legacy profile hook.
    legacy_hook = sys.getprofile() is not None
    monitoring = getattr(sys, "monitoring", None)
    tool = None
    events = 0
    if monitoring is not None:
        tool = monitoring.get_tool(monitoring.PROFILER_ID)
        events = monitoring.get_events(monitoring.PROFILER_ID)
    return dict(profiled=legacy_hook or bool(events),
                profiling=dict(legacy_hook_active=legacy_hook,
                               monitoring_profiler_tool=tool,
                               monitoring_profiler_events=events))


def worker(case, subdivision, modes, target):
    inputs = dict(lengths_m=CASES[case], subdivisions=[subdivision] * 3,
                  num_modes=modes, target_frequency_hz=target)
    sample = dict(case=case, subdivision=subdivision, inputs=inputs,
                  input_sha256=hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest(),
                  pid=os.getpid(), parent_pid=os.getppid(),
                  thread_environment={key: os.environ.get(key) for key in THREADS})
    sample.update(profiling_state())
    start = None
    try:
        # This source benchmark must not silently use an editable install elsewhere.
        sys.path.insert(0, str(ROOT / "packages/galerkin"))
        import galerkin
        import numpy as np
        import scipy

        if not Path(galerkin.__file__).resolve().is_relative_to(ROOT / "packages/galerkin"):
            raise RuntimeError("galerkin was not imported from the benchmark checkout")
        sample["galerkin_path"] = str(Path(galerkin.__file__).resolve())
        sample["versions"] = dict(numpy=np.__version__, scipy=scipy.__version__)
        for name, module in (("numpy", np), ("scipy", scipy)):
            build = io.StringIO()
            with contextlib.redirect_stdout(build):
                module.show_config()
            sample[name + "_build_config"] = build.getvalue()
        start = time.perf_counter()
        result = galerkin.solve_cavity_box(**inputs)
        seconds = time.perf_counter() - start
        sample.update(peak_rss())  # Before reporting/profiling postprocessing allocates memory.
        if (len(result.frequencies_hz) != modes
                or not np.isfinite(result.relative_residuals).all()
                or np.max(result.relative_residuals) > 1e-8):
            raise RuntimeError("returned count/residual does not satisfy the solver contract")
        sample.update(status="ok", solve_wall_seconds=seconds,
                      nodes=result.mesh.num_nodes, tets=len(result.mesh.tets),
                      edge_dofs=result.space.num_edges, pec_dofs=len(result.pec_edge_ids),
                      free_dofs=result.space.num_edges - len(result.pec_edge_ids),
                      returned_modes=len(result.frequencies_hz),
                      frequencies_hz=result.frequencies_hz.tolist(),
                      eigenvalues_m2=result.eigenvalues_m2.tolist(),
                      relative_residuals=result.relative_residuals.tolist(),
                      max_relative_residual=float(np.max(result.relative_residuals)),
                      edge_coefficients_bytes=result.edge_coefficients.nbytes,
                      centroid_electric_field_bytes=result.electric_field.nbytes,
                      search=result.search, cluster_completeness=result.cluster_completeness,
                      mode_count_policy=result.mode_count_policy)
    except Exception as exc:
        sample.update(peak_rss())
        sample.update(status="error", error_type=type(exc).__name__, error=str(exc),
                      traceback=traceback.format_exc(),
                      failed_solve_wall_seconds=None if start is None else time.perf_counter() - start)
    return sample


def run_sample(case, subdivision, modes, target, timeout, env):
    command = [sys.executable, str(Path(__file__).resolve()), "--worker", case,
               "--subdivisions", str(subdivision), "--num-modes", str(modes),
               "--target-frequency-hz", str(target)]
    started = time.perf_counter()
    try:
        completed = subprocess.run(command, cwd=ROOT, env=env, capture_output=True,
                                   text=True, timeout=timeout)
        elapsed = time.perf_counter() - started
        try:
            sample = json.loads(completed.stdout)
            if not isinstance(sample, dict) or sample.get("status") not in ("ok", "error"):
                raise ValueError("invalid worker result")
        except (ValueError, TypeError):
            sample = dict(status="error", error_type="WorkerProtocolError",
                          error="worker did not return a valid JSON result", stdout=completed.stdout)
        if completed.returncode and sample["status"] == "ok":
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
    sample.update(case=case, subdivision=subdivision, subprocess_wall_seconds=elapsed)
    return sample


def summarize(runs):
    summaries = []
    for case, subdivision in sorted({(r["case"], r["subdivision"]) for r in runs}):
        selected = [r for r in runs if (r["case"], r["subdivision"]) == (case, subdivision)]
        successful = [r for r in selected if r["status"] == "ok"]
        good = [r for r in successful if not r.get("profiled", False)]
        summary = dict(case=case, subdivision=subdivision, attempted=len(selected),
                       succeeded=len(successful), failed=len(selected) - len(successful),
                       unprofiled_succeeded=len(good),
                       profiled_succeeded=len(successful) - len(good))
        for metric in ("solve_wall_seconds", "subprocess_wall_seconds", "peak_rss_mib"):
            values = [r[metric] for r in good if r.get(metric) is not None]
            summary[metric] = (dict(median=statistics.median(values), min=min(values), max=max(values))
                               if values else None)
        summaries.append(summary)
    return summaries


def save_report(path, report):
    # Reserve the requested output once in main; replace only our own checkpoint.
    data = json.dumps(report, indent=2, allow_nan=False) + "\n"
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(data)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", choices=CASES, help="default: both boxes")
    parser.add_argument("--subdivisions", type=int, nargs="+", default=[4, 8, 12, 16])
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--num-modes", type=int, default=6)
    parser.add_argument("--target-frequency-hz", type=float, default=210e6)
    parser.add_argument("--timeout-seconds", type=float, default=300)
    parser.add_argument("--output", type=Path, help="new JSON file; checkpoints after each worker")
    parser.add_argument("--worker", choices=CASES, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if min([args.repeats, args.num_modes, *args.subdivisions]) < 1:
        parser.error("subdivisions, repeats and num-modes must be positive")
    if any(not math.isfinite(x) or x <= 0 for x in (args.target_frequency_hz, args.timeout_seconds)):
        parser.error("target-frequency-hz and timeout-seconds must be finite and positive")
    if args.worker:
        if len(args.subdivisions) != 1:
            parser.error("worker requires exactly one subdivision count")
        sample = worker(args.worker, args.subdivisions[0], args.num_modes, args.target_frequency_hz)
        print(json.dumps(sample, allow_nan=False))
        return 0 if sample["status"] == "ok" else 1
    cases = args.case or list(CASES)
    if len(set(cases)) != len(cases) or len(set(args.subdivisions)) != len(args.subdivisions):
        parser.error("duplicate cases/subdivisions: use --repeats for repetitions")
    if args.output is None:
        parser.error("--output is required so interrupted/failed runs retain checkpoints")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        args.output.open("x").close()
    except FileExistsError:
        parser.error("--output must not exist")
    env = os.environ.copy()
    env.update({key: "1" for key in THREADS})
    report = dict(schema_version=1, started_utc=datetime.now(timezone.utc).isoformat(),
                  source=source_identity(), machine=machine_info(),
                  settings=dict(cases={case: CASES[case] for case in cases},
                                subdivisions=args.subdivisions, repeats=args.repeats,
                                num_modes=args.num_modes, target_frequency_hz=args.target_frequency_hz,
                                search="near_target", timeout_seconds=args.timeout_seconds,
                                thread_environment={key: env[key] for key in THREADS},
                                execution_order="repetition, subdivision, case; sequential"),
                  expected_runs=len(cases) * len(args.subdivisions) * args.repeats,
                  completed=False, runs=[], summary=[])
    save_report(args.output, report)
    # Interleave geometries/sizes between repetitions to expose drift; no discarded warm-up.
    for repetition in range(1, args.repeats + 1):
        for subdivision in args.subdivisions:
            for case in cases:
                sample = run_sample(case, subdivision, args.num_modes, args.target_frequency_hz,
                                    args.timeout_seconds, env)
                sample["repetition"] = repetition
                report["runs"].append(sample)
                report["summary"] = summarize(report["runs"])
                save_report(args.output, report)
                print(f"{case} n={subdivision} repeat={repetition}: {sample['status']} "
                      f"process={sample['subprocess_wall_seconds']:.3f}s", file=sys.stderr, flush=True)
    report.update(completed=True, ended_utc=datetime.now(timezone.utc).isoformat(),
                  source_at_end=source_identity())
    report["source_unchanged"] = report["source"] == report["source_at_end"]
    save_report(args.output, report)
    return 0 if report["source_unchanged"] and all(r["status"] == "ok" for r in report["runs"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
