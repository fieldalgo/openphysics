#!/usr/bin/env python3
# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Observe Studio with heat region documents: fixed workloads, one fresh server each.

Each workload starts the exact source checkout's Studio server in a new loopback
process, requests the capabilities, validates the document and, when validation
accepts it, runs it and polls the job. It records the validation and job wall times,
the outcome code, the result bytes, the server's idle VmRSS after the capability
request and its final VmHWM, and how slowly the server answered a capability request
polled every 100 ms from a second client thread while validation and the run went on.
It also records the document's counts (shapes, circles, polygon points, boundary
crossings and, when those are within Studio's caps, loop vertices), computed with the
checkout's simcase as Studio computes them. The documents come from the tracked
tests/simcase/region_studio_fixtures.py of the same checkout.

This is an observation, not a performance gate: the command fails only when a
workload's outcome code differs from the one fixed below, or a stage fails (the
server does not start, an unexpected HTTP status, a deadline). Linux only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

FORMAT = 'region-resource-workloads-v1'
PACKAGES = ('simcase', 'galerkin', 'meshine', 'physmat', 'galerkin-refsol', 'gmshio')
THREADS = ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS',
           'VECLIB_MAXIMUM_THREADS', 'BLIS_NUM_THREADS')
DEADLINE_S = 300.0
PROBE_S = 0.1   # polling every 20 ms slowed the jobs by up to about 25 % in local runs; 100 ms did not

# Started with the checkout's package sources first on PYTHONPATH; refuses to serve
# when a first-party module comes from anywhere else.
SERVER = r'''
import hashlib, json, socket, sys
from pathlib import Path
root = Path(sys.argv[1]).resolve()
import uvicorn
from simcase.studio import server
origins = {}
for name, module in sorted(sys.modules.items()):
    if name.split('.')[0] in ('simcase', 'galerkin', 'meshine', 'physmat', 'refsol', 'gmshio'):
        filename = getattr(module, '__file__', None)
        if filename and filename.endswith('.py'):
            path = Path(filename).resolve()
            if not path.is_relative_to(root / 'packages'):
                raise SystemExit('server import outside the source checkout: ' + name + ' ' + str(path))
            origins[name] = hashlib.sha256(path.read_bytes()).hexdigest()
sock = socket.socket()
sock.bind(('127.0.0.1', 0))
sock.listen()
print(json.dumps({'port': sock.getsockname()[1], 'origins': origins}), flush=True)
uvicorn.Server(uvicorn.Config(server.app, log_level='error', access_log=False)).run(sockets=[sock])
'''


def workloads(fx, max_boundary_crossings):
    """(name, route, document, expected outcome); the expectations are fixed, not measured."""
    def at_cap(make):
        # The most teeth whose crossings stay within the cap: validates, and the covering
        # rects leave a small mesh.
        teeth = max(t for t in range(1, 127) if fx_complexity(make(teeth=t)) <= max_boundary_crossings)
        return make(teeth=teeth)
    steady, moving = 'steady', 'transient'
    return [
        ('steady_example_size_2', steady, lambda: fx.steady_example(2.0), 'done'),
        ('steady_example_size_0.4', steady, lambda: fx.steady_example(0.4), 'done'),
        ('strip_w0.2_size0.06', steady, lambda: fx.strip(0.2, 0.06), 'done'),
        ('strip_w0.005_size0.01', steady, lambda: fx.strip(0.005, 0.01), 'job:mesh_limit_exceeded'),
        ('thin_film_1e-7', steady, lambda: fx.thin_film(1e-7), 'job:mesh_limit_exceeded'),
        ('circles_rects_512gon', steady, fx.circles_rects_polygon, 'done'),
        ('tiny_global_size_0.025', steady, lambda: fx.tiny_global_size(0.025), 'done'),
        ('crossing_combs_k63', steady, lambda: fx.crossing_combs(63), 'validate:geometry_limit_exceeded'),
        ('covered_crossings_at_cap', steady, lambda: at_cap(fx.covered_crossings), 'done'),
        ('covered_crossings_with_circles_at_cap', steady, lambda: at_cap(fx.covered_crossings_with_circles),
         'done'),
        ('covered_crossings_over_cap', steady, fx.covered_crossings, 'validate:geometry_limit_exceeded'),
        ('collinear_overlaps', steady, fx.collinear_overlaps, 'done'),
        ('crossing_stars_after_circles', steady, fx.crossing_stars, 'validate:geometry_limit_exceeded'),
        # Fixed first as job:mesh_limit_exceeded (meshed in millimetres it reaches the
        # node cap) and changed after the first run on micrometre meshes failed: on the
        # micrometre copy simcase meshes, every length times 1000, meshine refuses this
        # boundary ("cannot resolve" on its teeth, fail-closed) before the node cap.
        # Only that factor does it; the same document scaled by 0.001 to 1e6 otherwise
        # reaches the cap (docs/region_resource_probe.md).
        ('sawtooth_1deg_tips', steady, fx.sawtooth, 'job:solver_failed'),
        ('sawtooth_10deg_jitter_60_rects_angle33', steady,
         lambda: fx.sawtooth(tip_angle_deg=10, jitter=0.1, crossing_rects=60, min_angle=33),
         'job:mesh_limit_exceeded'),
        ('concentric_rings_80_rounds', steady, fx.concentric_rings, 'job:solver_failed'),
        ('transient_9_times_size_0.2', moving, lambda: fx.transient_example(0.2), 'done'),
        ('transient_64_times_size_0.5', moving, lambda: fx.transient_example(0.5, times=64), 'done'),
        ('transient_128_times_size_0.25', moving, lambda: fx.transient_example(0.25, times=128),
         'job:history_limit_exceeded'),
    ]


def fx_complexity(doc):
    from simcase import region_complexity
    return region_complexity(doc).boundary_crossings


def counts(document, limits):
    """The counts Studio checks, as it checks them: the raw counts, the boundary crossings
    only within the shape, circle and point caps, and the loop vertices only within all
    four (in this process, with the checkout's simcase)."""
    from simcase import Document, check_mesh_limits, region_complexity
    raw = region_complexity(document, max_shapes=limits.max_shapes, max_circles=limits.max_circles,
                            max_polygon_points=limits.max_polygon_points)
    result = raw._asdict()
    within = raw.boundary_crossings is not None and raw.boundary_crossings <= limits.max_boundary_crossings
    result['loop_vertices'] = (check_mesh_limits(Document.from_dict(document), max_input_vertices=10**9)
                               if within else None)
    return result


def proc_status(pid, key):
    """A /proc/<pid>/status memory line in bytes."""
    for line in Path(f'/proc/{pid}/status').read_text(encoding='ascii').splitlines():
        if line.startswith(key+':'):
            return int(line.split()[1]) * 1024
    raise RuntimeError(f'{key} missing from /proc/{pid}/status')


def http(port, method, path, data=None, expected=None):
    body = None if data is None else json.dumps(data, allow_nan=False).encode('utf-8')
    request = urllib.request.Request(f'http://127.0.0.1:{port}{path}', data=body, method=method,
                                     headers={'content-type': 'application/json'})
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=DEADLINE_S) as reply:
            status, content = reply.status, reply.read()
    except urllib.error.HTTPError as exc:
        status, content = exc.code, exc.read()
    elapsed = time.perf_counter() - started
    if expected is not None and status not in expected:
        raise RuntimeError(f'{method} {path}: HTTP {status}: {content[:512]!r}')
    return status, content, elapsed


class CapabilityProbe:
    """Requests /api/capabilities every PROBE_S from a second client thread and keeps the
    slowest answer: how long the server took to respond while validation or a job ran."""

    def __init__(self, port):
        self.port, self.polls, self.slowest, self.failure = port, 0, 0., None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._poll, daemon=True)

    def _poll(self):
        try:
            while not self._stop.is_set():
                _, _, elapsed = http(self.port, 'GET', '/api/capabilities', expected=(200,))
                self.polls += 1
                self.slowest = max(self.slowest, elapsed)
                self._stop.wait(PROBE_S)
        except Exception as exc:
            self.failure = exc

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc_info):
        self._stop.set()
        self._thread.join(DEADLINE_S)
        if self._thread.is_alive():
            raise TimeoutError('the capability probe did not stop')
        if self.failure is not None and exc_info[0] is None:
            raise RuntimeError(f'capability probe failed: {self.failure}')

    def record(self):
        return {'capability_polls': self.polls, 'slowest_capability_s': self.slowest}


def observe(name, route, document, root, env, output):
    """One workload in a fresh server process."""
    base = '/api/thermal/transient/' if route == 'transient' else '/api/thermal/'
    record = {'workload': name, 'route': route}
    stderr = (output / (name + '.server.stderr')).open('w', encoding='utf-8')
    server = subprocess.Popen([sys.executable, '-c', SERVER, str(root)], stdout=subprocess.PIPE,
                              stderr=stderr, env=env, text=True, encoding='utf-8')
    try:
        line = server.stdout.readline()
        if not line:
            raise RuntimeError('server did not start (see the .server.stderr file)')
        started = json.loads(line)
        port = started['port']
        record['server'] = {'pid': server.pid, 'first_party_modules': len(started['origins']),
                            'origins_sha256': hashlib.sha256(json.dumps(started['origins'], sort_keys=True)
                                                             .encode('utf-8')).hexdigest()}
        _, content, _ = http(port, 'GET', '/api/capabilities', expected=(200,))
        capability = json.loads(content)
        kind = 'thermal.transient2d' if route == 'transient' else 'thermal.steady2d'
        if capability.get(kind, {}).get('regions', {}).get('run_enabled') is not True:
            raise RuntimeError('the server does not advertise region runs')
        record['idle_vmrss_bytes'] = proc_status(server.pid, 'VmRSS')
        envelope = {'doc': document, 'client_revision': 1, 'request_seq': 1}
        with CapabilityProbe(port) as probe:
            status, content, elapsed = http(port, 'POST', base+'validate', envelope, expected=(200, 413))
        reply = json.loads(content)
        record['validation'] = {'http_status': status, 'wall_s': elapsed, 'ok': reply.get('ok') is True,
                                'code': None if reply.get('ok') is True else reply['error']['code'],
                                'message': None if reply.get('ok') is True else reply['error']['message'],
                                **probe.record()}
        if reply.get('ok') is not True:
            record['outcome'] = 'validate:' + reply['error']['code']
        else:
            with CapabilityProbe(port) as probe:   # the run request validates again, then the job
                started_run = time.perf_counter()
                status, content, run_elapsed = http(port, 'POST', base+'run', envelope, expected=(200,))
                identity = json.loads(content)
                accepted = time.perf_counter()
                slowest_poll = 0.
                while True:
                    _, content, poll = http(port, 'GET', '/api/jobs/'+identity['job'], expected=(200,))
                    slowest_poll = max(slowest_poll, poll)
                    state = json.loads(content)
                    if state['status'] in ('done', 'error'):
                        break
                    if time.perf_counter()-accepted > DEADLINE_S:
                        raise TimeoutError('job did not finish within the deadline')
                    time.sleep(.05)
                finished = time.perf_counter()
            record['job'] = {'run_request_wall_s': run_elapsed, 'job_wall_s': finished-accepted,
                             'run_to_terminal_wall_s': finished-started_run, 'slowest_status_poll_s': slowest_poll,
                             'status': state['status'], 'error': state['error'], **probe.record()}
            if state['status'] == 'done':
                _, content, _ = http(port, 'GET', '/api/jobs/'+identity['job']+'/result', expected=(200,))
                record['job']['result_bytes'] = len(content)
                record['outcome'] = 'done'
            else:
                record['outcome'] = 'job:' + state['error']['code']
        record['final_vmhwm_bytes'] = proc_status(server.pid, 'VmHWM')
        record['peak_over_idle_bytes'] = record['final_vmhwm_bytes'] - record['idle_vmrss_bytes']
    finally:
        server.terminate()
        try:
            server.wait(10)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(10)
            record['server_kill_required'] = True
        record['server_exit'] = server.returncode
        stderr.close()
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--output', type=Path, required=True, help='a new artifact directory')
    parser.add_argument('--workload', action='append', help='run only this workload (repeatable; for local use)')
    args = parser.parse_args(argv)
    if not sys.platform.startswith('linux'):
        parser.error('this resource observation targets Linux only (/proc memory figures)')
    root = args.source_root.resolve()
    head = subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'], check=True, capture_output=True,
                          text=True, encoding='utf-8').stdout.strip()
    if head != args.expected_commit:
        parser.error('the checkout commit differs from --expected-commit')
    fixtures = root / 'tests' / 'simcase' / 'region_studio_fixtures.py'
    subprocess.run(['git', '-C', str(root), 'diff', '--quiet', 'HEAD', '--', 'packages', str(fixtures)], check=True)
    args.output.mkdir(parents=True, exist_ok=False)
    for name in THREADS:
        os.environ[name] = '1'
    sources = [str(root / 'packages' / name / 'src') for name in PACKAGES]
    sys.path[:0] = [str(fixtures.parent), *sources]
    env = {**os.environ, 'PYTHONPATH': os.pathsep.join(sources + [p for p in [os.environ.get('PYTHONPATH')] if p])}
    summary = {'format': FORMAT, 'source_commit': head, 'ok': False, 'python': sys.version,
               'platform': platform.platform(), 'cpu_count': os.cpu_count(),
               'scope': 'fixed region workloads, one fresh loopback server each; an observation, not a gate',
               'fails_on': 'an outcome code other than the expected one, or a stage failure', 'workloads': []}
    code = 1
    try:
        import region_studio_fixtures as fx
        from simcase.studio.thermal_regions_api import RegionLimits
        limits = RegionLimits()
        plan = workloads(fx, limits.max_boundary_crossings)
        if args.workload:
            unknown = set(args.workload) - {row[0] for row in plan}
            if unknown:
                parser.error('unknown workload: ' + ', '.join(sorted(unknown)))
            plan = [row for row in plan if row[0] in args.workload]
        mismatches = []
        for name, route, make, expected in plan:
            document = make()
            path = args.output / (name + '.json')
            path.write_text(json.dumps(document, indent=1, allow_nan=False) + '\n', encoding='utf-8')
            print('Observing region workload ' + name, flush=True)
            row = {'expected': expected, 'document': path.name,
                   'document_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                   'counts': counts(document, limits)}
            try:
                row.update(observe(name, route, document, root, env, args.output))
            except Exception as exc:
                row.update(workload=name, failure={'type': type(exc).__name__, 'message': str(exc)})
            row['matches'] = row.get('outcome') == expected
            if not row['matches']:
                mismatches.append(name)
            summary['workloads'].append(row)
            print(json.dumps({key: row.get(key) for key in ('workload', 'outcome', 'expected', 'matches')}), flush=True)
        summary['mismatches'] = mismatches
        summary['ok'] = not mismatches
        code = 0 if summary['ok'] else 1
    except Exception as exc:
        summary['failure'] = {'type': type(exc).__name__, 'message': str(exc)}
    finally:
        summary['exit_code'] = code
        (args.output / 'region-workloads.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n',
                                                           encoding='utf-8')
    return code


if __name__ == '__main__':
    sys.exit(main())
