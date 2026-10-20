#!/usr/bin/env python3
"""Bounded public-HTTP observation; never a RAM or physical-accuracy gate.

No runtime package imports, private store access, retries of solves, or server
instrumentation. Pair the report with server-side counters and memory records.
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import platform
import sys
import time
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

MIB = 1024 * 1024


def raw_bytes(n: int, nt: int, d: int) -> int:
    """Conservative eight-byte estimate for the thirteen public arrays."""
    if any(type(v) is not int for v in (n, nt, d)):
        raise ValueError("n, nt and d must be integers, excluding bool")
    nodes, cells = (n + 1) ** 2, 2 * n * n
    if not 1 <= n <= 100 or not 2 <= nt <= 128 or not 0 <= d <= nodes:
        raise ValueError("outside candidate spatial/time/Dirichlet bounds")
    scalars = 2 * nodes + 3 * cells + d
    scalars += nt * (2 * nodes + 2 * cells + d + 3)
    scalars += 3 * (nt - 1) * nodes
    return 8 * scalars


def workload_plan() -> dict:
    choices = [(raw_bytes(n, nt, (n + 1) ** 2), n, nt)
               for n in range(2, 101) for nt in range(2, 129)]
    near = max(x for x in choices if x[0] <= 16 * MIB)
    over = min(x for x in choices if x[0] > 16 * MIB)
    cases = [("small", 2, 3), ("medium", 16, 8),
             ("near_raw_candidate", near[1], near[2]),
             ("over_raw_candidate", over[1], over[2])]
    return {"scope": "integer shape arithmetic only; no allocation or solve",
            "raw_candidate_bytes": 16 * MIB,
            "cases": [{"stage": name, "n": n, "nt": nt,
                       "nodes": (n + 1) ** 2, "cells": 2 * n * n,
                       "d0_bytes": raw_bytes(n, nt, 0),
                       "d_upper": (n + 1) ** 2,
                       "d_upper_bytes": raw_bytes(n, nt, (n + 1) ** 2)}
                      for name, n, nt in cases],
            "limitations": ["eight-byte dtype assumption, not actual nbytes",
                            "D=N conservative until complete BC validation",
                            "metadata, reservations, lists, native memory and RSS excluded",
                            "near-budget inputs require separate physical fixture validation"]}


def finite_json(data: bytes):
    def unique(pairs):
        out = {}
        for k, v in pairs:
            if k in out:
                raise ValueError("duplicate JSON key")
            out[k] = v
        return out
    def nonfinite(value):
        raise ValueError("non-finite JSON constant: " + value)
    value = json.loads(data.decode("utf-8"), object_pairs_hook=unique,
                       parse_constant=nonfinite)
    # JSON exponents such as 1e999 do not use parse_constant.
    json.dumps(value, allow_nan=False)
    return value


def loopback_url(value: str) -> str:
    parts = urllib.parse.urlsplit(value)
    if parts.scheme != "http" or parts.username or parts.password:
        raise ValueError("use credential-free HTTP on a literal loopback address")
    if parts.path not in ("", "/") or parts.query or parts.fragment:
        raise ValueError("base URL must have no path, query or fragment")
    if not parts.hostname or not ipaddress.ip_address(parts.hostname).is_loopback:
        raise ValueError("base URL must use a literal loopback IP")
    if parts.port is None:
        raise ValueError("base URL requires an explicit port")
    return value.rstrip("/")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("redirects are outside the observation contract")


class Observer:
    def __init__(self, base: str, out: Path, report: dict, timeout: float):
        self.base, self.out, self.report, self.timeout = base, out, report, timeout
        self.record_lock = threading.Lock()
        # Ignore ambient proxy settings for the explicitly local server.
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def request(self, path: str, payload=None, cap=4 * MIB, save=False):
        if not path.startswith("/api/") or "#" in path:
            raise ValueError("only explicit API paths are permitted")
        if len(self.report["requests"]) >= 160:
            raise ValueError("observation request-count bound reached")
        data = None if payload is None else json.dumps(
            payload, allow_nan=False, separators=(",", ":")).encode()
        if data is not None and len(data) > MIB:
            raise ValueError("input envelope exceeds candidate request cap")
        req = urllib.request.Request(self.base + path, data=data,
                                     headers={"Content-Type": "application/json"})
        started = time.perf_counter()
        entry = {"path": path, "method": "GET" if data is None else "POST",
                 "request_bytes": len(data or b"")}
        with self.record_lock:
            if len(self.report["requests"]) >= 160:
                raise ValueError("observation request-count bound reached")
            self.report["requests"].append(entry)
            sequence = len(self.report["requests"])
        try:
            try:
                response = self.opener.open(req, timeout=self.timeout)
            except urllib.error.HTTPError as exc:
                response = exc
            with response:
                body = response.read(cap + 1)
                entry.update(status=response.code, response_bytes=len(body),
                             sha256=hashlib.sha256(body).hexdigest())
                if save or response.code >= 400:
                    name = f"response-{sequence:03d}.bin"
                    (self.out / name).write_bytes(body)
                    entry["raw_file"] = name
                if len(body) > cap:
                    raise ValueError("response exceeds observation byte cap")
            return entry, finite_json(body)
        except Exception as exc:
            entry["error"] = {"type": type(exc).__name__, "message": str(exc)}
            raise
        finally:
            entry["elapsed_s"] = time.perf_counter() - started


def observe(args, out: Path, report: dict):
    with Path(args.document).open("rb") as source:
        original = source.read(MIB + 1)
    if len(original) > MIB:
        raise ValueError("document exceeds candidate request cap")
    doc = finite_json(original)
    if not isinstance(doc, dict):
        raise ValueError("document must be a JSON object")
    (out / "input-document.json").write_bytes(original)
    report["input_sha256"] = hashlib.sha256(original).hexdigest()
    observer = Observer(loopback_url(args.base_url), out, report, args.http_timeout)
    entry, capabilities = observer.request("/api/capabilities", save=True)
    report["capabilities"] = capabilities
    if entry["status"] != 200 or not capabilities.get("thermal.transient2d", {}).get("run_enabled"):
        raise ValueError("transient run unavailable; no solve submitted")
    envelope = {"doc": doc, "client_revision": 1, "request_seq": 1}
    entry, validation = observer.request("/api/thermal/transient/validate", envelope, save=True)
    if entry["status"] != 200 or validation.get("ok") is not True:
        raise ValueError("validation refused; no solve submitted")
    entry, submitted = observer.request("/api/thermal/transient/run", envelope, save=True)
    if entry["status"] != 200:
        raise ValueError("run refused; no retry")
    job = submitted.get("job")
    if not isinstance(job, str) or not job or any(c not in
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in job):
        raise ValueError("invalid submitted job identifier")
    endpoint = "/api/jobs/" + job
    deadline = time.monotonic() + args.job_timeout
    for _ in range(100):
        entry, state = observer.request(endpoint, cap=131072)
        if entry["status"] != 200:
            raise ValueError("job status refused")
        if state.get("status") in ("done", "error"):
            (out / "terminal-state.json").write_text(
                json.dumps(state, indent=2, allow_nan=False) + "\n", encoding="utf-8")
            break
        if time.monotonic() >= deadline:
            raise TimeoutError("observation deadline; server solve is NOT cancelled")
        time.sleep(min(1.0, max(0.0, deadline - time.monotonic())))
    else:
        raise TimeoutError("poll-count bound; server solve is NOT cancelled")
    if state.get("status") != "done":
        raise ValueError("server terminal error; original responses preserved")
    entry, manifest = observer.request(endpoint + "/result", save=True)
    if entry["status"] != 200 or manifest.get("payload_format") != "studio-thermal-transient-v1":
        raise ValueError("unexpected transient manifest")
    result_id = manifest.get("result_id")
    times = manifest.get("time_s")
    if not isinstance(result_id, str) or not isinstance(times, list) or not 2 <= len(times) <= 128:
        raise ValueError("manifest identity/time count unavailable")
    query = urllib.parse.urlencode({"result_id": result_id, "field": "temperature_k",
                                   "time_index": len(times) - 1, "frame_seq": 1})
    path = endpoint + "/frame?" + query
    first, frame = observer.request(path, save=True)
    if first["status"] != 200 or frame.get("result_id") != result_id:
        raise ValueError("frame refused or identity mismatch")
    for _ in range(10):
        current, _ = observer.request(path)
        if any(current[k] != first[k] for k in ("status", "response_bytes", "sha256")):
            raise ValueError("same complete frame query changed bytes/status")
    query = urllib.parse.urlencode({"result_id": result_id, "field": "heat_content_j_per_m",
                                   "start": 0, "stop": min(16, len(times)), "frame_seq": 2})
    entry, page = observer.request(endpoint + "/history?" + query, save=True)
    if entry["status"] != 200 or page.get("result_id") != result_id:
        raise ValueError("history refused or identity mismatch")
    report["observation_ok"] = True
    report["server_internal_measurements"] = {
        "status": "unavailable: pair with instrumented server/platform records",
        "required": ["getter/capture/solve/encode counts", "raw/manifest/reserved/pinned/workspace bytes",
                     "read permit through send-finally", "ingress/solver admission and release",
                     "current RSS/cumulative highwater/traced live and peak/native coverage"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", action="store_true", help="shape arithmetic only")
    parser.add_argument("--base-url")
    parser.add_argument("--document", type=Path)
    parser.add_argument("--output", required=True, type=Path, help="new evidence directory")
    parser.add_argument("--source-commit", help="operator-supplied server commit, not byte verification")
    parser.add_argument("--http-timeout", type=float, default=30)
    parser.add_argument("--job-timeout", type=float, default=90)
    args = parser.parse_args(argv)
    if not args.plan and not (args.base_url and args.document and args.source_commit):
        parser.error("HTTP mode requires --base-url, --document and --source-commit")
    if not 0 < args.http_timeout <= 60 or not 0 < args.job_timeout <= 90:
        parser.error("timeouts must be positive; HTTP<=60s, job<=90s")
    args.output.mkdir(parents=True, exist_ok=False)
    report = {"format": "transient-resource-observation-v1", "observation_ok": False,
              "scope": "shape arithmetic" if args.plan else "public HTTP client only",
              "operator_source_commit": args.source_commit, "requests": [],
              "environment": {"python": sys.version, "platform": platform.platform()},
              "limitations": ["not numerical acceptance, server instrumentation or capacity certification",
                              "client timings include transport; no server RSS measurement",
                              "on-demand transient encode allowed; HTTP hashes cannot prove zero getters/solves",
                              "slow readers, pins, budget races and cleanup need separate instrumented evidence"]}
    code = 0
    try:
        if args.plan:
            report["plan"] = workload_plan()
            report["observation_ok"] = True
        else:
            observe(args, args.output, report)
    except Exception as exc:
        code = 1
        report["failure"] = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        report["exit_code"] = code
        (args.output / "report.json").write_text(
            json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return code


if __name__ == "__main__":
    sys.exit(main())
