#!/usr/bin/env python3
"""Opt-in fresh-process transient server observation, separate from steady CI.

Imports only public simcase results plus the actual Studio transport adapters.
Runtime hooks observe original calls; no solver/capture replacements or stubs.
"""
from __future__ import annotations
import argparse
import asyncio
import contextlib
import hashlib
import json
import os
from pathlib import Path
import platform
import queue
import subprocess
import sys
import threading
import time
import tracemalloc
import traceback
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

from probe_transient_studio_resources import Observer, finite_json, MIB


def memory():
    result = {"traced_live_bytes": tracemalloc.get_traced_memory()[0],
              "traced_phase_peak_bytes": tracemalloc.get_traced_memory()[1],
              "rss_current_bytes": None, "process_highwater_bytes": None}
    if sys.platform.startswith("linux"):
        try:
            result["rss_current_bytes"] = int(Path('/proc/self/statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
        except (OSError, ValueError, IndexError):
            pass
    try:
        import resource
        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform == 'darwin':
            result['process_highwater_bytes'] = int(value)
        elif sys.platform.startswith('linux'):
            result['process_highwater_bytes'] = int(value*1024)
    except ImportError:
        pass
    return result


def child(args):
    output = sys.stdout
    sys.stdout = sys.stderr  # Keep model/library output out of the RPC protocol.
    def emit(value):
        output.write(json.dumps(value, allow_nan=False)+'\n'); output.flush()
    try:
        # Source imports remain normal packages; no fabricated module namespace.
        root = args.source_root.resolve()
        for package in sorted((root/'packages').iterdir()):
            if (package/'src').is_dir():
                sys.path.insert(0, str(package/'src'))
        import simcase
        import uvicorn
        from simcase.studio import server
        from simcase.studio import thermal_api as common
        from simcase.studio import transient_thermal_api as transient
        counts, events = {}, []
        lock = threading.RLock()
        def hook(owner, name, label):
            original = getattr(owner, name)
            def wrapped(*a, **kw):
                start = time.perf_counter()
                with lock:
                    counts[label] = counts.get(label, 0)+1
                try:
                    return original(*a, **kw)
                except BaseException:
                    with lock:
                        counts["error:"+label] = counts.get("error:"+label,0)+1
                    raise
                finally:
                    with lock:
                        if len(events) < 256:
                            events.append({'hook': label, 'elapsed_s': time.perf_counter()-start})
            setattr(owner, name, wrapped)
        for owner, name, label in [(server,'run','public_run'),
                                  (transient,'capture_result','capture'),
                                  (transient,'encode_view','view_encode'),
                                  (common,'encode_json','strict_encode')]:
            hook(owner, name, label)
        for owner,name,label in [(common.ThermalJobs,'pin','pin'),
                                 (common.ThermalJobs,'reserve','reserve'),
                                 (common.ThermalJobs,'release','solver_release'),
                                 (common.ThermalJobs,'begin_read','read_reserve'),
                                 (common.RecordPin,'release','pin_release'),
                                 (common.ReadAllocation,'publish','read_publish'),
                                 (common.ReadAllocation,'release','read_release')]:
            hook(owner,name,label)
        observed_capture = transient.capture_result
        def capture_once(*a, **kw):
            with lock:
                before_getters = {k:counts.get('getter:'+k,0) for k in transient.SPEC}
            result = observed_capture(*a, **kw)
            with lock:
                actual = {k:counts.get('getter:'+k,0)-before_getters[k] for k in transient.SPEC}
            if any(value!=1 for value in actual.values()):
                raise AssertionError('completed capture must read each13 public getters once: '+json.dumps(actual))
            return result
        transient.capture_result = capture_once
        original_getattr = simcase.TransientThermalRunResult.__getattr__
        def getter(self, name):
            if name in transient.SPEC:
                with lock:
                    key = 'getter:'+name; counts[key] = counts.get(key, 0)+1
            return original_getattr(self, name)
        simcase.TransientThermalRunResult.__getattr__ = getter
        hold_next, held, release = threading.Event(), threading.Event(), threading.Event()
        async def app(scope, receive, send):
            hold = scope['type']=='http' and scope.get('path','').endswith('/frame') and hold_next.is_set()
            if hold:
                hold_next.clear()
            async def observed_send(message):
                if hold and message['type']=='http.response.body':
                    held.set()
                    if not await asyncio.to_thread(release.wait, 30):
                        raise TimeoutError('instrumented send hold expired')
                await send(message)
            await server.app(scope, receive, observed_send)
        import socket
        sock = socket.socket(); sock.bind(('127.0.0.1',0)); sock.listen(128)
        port = sock.getsockname()[1]
        config = uvicorn.Config(app, host='127.0.0.1', port=port, log_level='warning', lifespan='on')
        runtime = uvicorn.Server(config)
        thread = threading.Thread(target=runtime.run, kwargs={'sockets':[sock]}, daemon=True)
        thread.start()
        deadline = time.monotonic()+20
        while not runtime.started:
            if not thread.is_alive() or time.monotonic()>deadline:
                raise RuntimeError('actual ASGI server did not start')
            time.sleep(.01)
        tracemalloc.start()
        def snapshot():
            jobs = server._thermal_jobs
            with jobs._lock:
                records = list(jobs._records.values())+list(jobs._retired.values())
                allocations = {}
                for record in records:
                    allocations.update(jobs._allocations(record))
                allocations.update({k:len(v['payload']) for k,v in jobs._snapshots.items()})
                store = {'active': jobs._active, 'pending': jobs._pending,
                         'reserved_bytes': jobs._reserved_bytes, 'retained_bytes': jobs._retained_bytes(),
                         'read_workspace_bytes': jobs._read_workspace,
                         'live_records': len(jobs._records), 'retired_records': len(jobs._retired),
                         'snapshot_allocations':len(jobs._snapshots),
                         'record_pins':sum(r.get('pins',0) for r in records),
                         'raw_bytes_by_record':[r.get('raw_bytes',0) for r in records],
                         'encoded_result_bytes_by_record':[len(r.get('result') or b'') for r in records],
                         'allocation_bytes':{str(k):v for k,v in allocations.items()}}
            with lock:
                return {'memory':memory(), 'store':store, 'counts':dict(counts),
                        'hook_events':list(events), 'hook_events_truncated':len(events)>=256}
        def origins():
            found={}
            for name, module in list(sys.modules.items()):
                path=getattr(module,'__file__',None)
                if name.split('.')[0] in {'simcase','galerkin','meshine','physmat'} and path and Path(path).is_file():
                    found[name]={'origin':path,'sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest()}
            return found
        emit({'ok':True,'port':port,'pid':os.getpid(),'baseline':snapshot(),
              'python':sys.version,'platform':platform.platform(),'origins_before':origins(),
              'versions':{name:__import__('importlib.metadata',fromlist=['version']).version(name)
                          for name in ['numpy','scipy','fastapi','uvicorn','shapely']}})
        for line in sys.stdin:
            command=json.loads(line)['command']
            if command=='reset_peak':
                tracemalloc.reset_peak()
            elif command=='hold_next_frame':
                held.clear();release.clear();hold_next.set()
            elif command=='wait_held':
                if not held.wait(20):
                    raise TimeoutError('response did not reach observed ASGI send')
            elif command=='release_send':
                release.set()
            elif command=='stop':
                release.set();runtime.should_exit=True;thread.join(10)
                emit({'ok':not thread.is_alive(),'snapshot':snapshot(),'origins_after':origins(),
                      'cleanup_scope':'owned ASGI shutdown only; no TTL/global-cache/leak proof'})
                return 0 if not thread.is_alive() else 1
            elif command!='snapshot':
                raise ValueError('unknown instrumented RPC command')
            emit({'ok':True,'snapshot':snapshot()})
        release.set();runtime.should_exit=True;thread.join(10)
        raise RuntimeError('parent ended without stop')
    except BaseException as exc:
        traceback.print_exc(file=sys.stderr)
        emit({'ok':False,'error':{'type':type(exc).__name__,'message':str(exc)}})
        return 1


def receive(process, timeout=90):
    if not hasattr(process,"observation_queue"):
        process.observation_queue=queue.Queue()
        def reader():
            for line in process.stdout:process.observation_queue.put(line)
            process.observation_queue.put("")
        threading.Thread(target=reader,daemon=True).start()
    return process.observation_queue.get(timeout=timeout)


def rpc(process, command):
    process.stdin.write(json.dumps({'command':command})+'\n');process.stdin.flush()
    line=receive(process)
    if not line:
        raise RuntimeError('instrumented child ended before RPC response')
    result=json.loads(line)
    if not result.get('ok'):
        raise RuntimeError('instrumented child failure: '+json.dumps(result))
    return result


def delta(after, before):
    return {k:after.get(k,0)-before.get(k,0) for k in set(after)|set(before)}


def parent(args):
    args.output.mkdir(parents=True,exist_ok=False)
    root=args.source_root.resolve()
    report={'format':'transient-instrumented-resource-v1','ok':False,'phases':[],
            'requests':[], 'scope':'actual instrumented source ASGI server; separate client process',
            'limitations':['hooks add overhead; nested hook times overlap',
                           'RSS highwater cumulative; traced memory excludes some native allocations',
                           'ASGI send is deliberately held for at most30s, not a network throughput benchmark',
                           'encoded/raw/retained limits are not a process RAM guarantee',
                           'successful workload does not certify every budget/failure/TTL path',
                           'evicted-history retention and transport disconnect/error paths require separate lifecycle evidence',
                           'tracing starts after imports/server startup; hook events bounded256, counters continue']}
    process=None
    code=1
    started=time.perf_counter()
    try:
        head=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
        if head!=args.expected_commit:
            raise ValueError('checkout HEAD differs from expected exact commit')
        subprocess.run(['git','-C',str(root),'diff','--quiet','HEAD','--','packages'],check=True)
        report['source_commit']=head
        env=os.environ.copy()
        for key in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS']:
            env[key]='1'
        with (args.output/'child.stderr').open('w',encoding='utf-8') as stderr:
            process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--child',
                                      '--source-root',str(root)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                     stderr=stderr,text=True,encoding='utf-8',env=env)
            first=json.loads(receive(process))
            report['child_start']=first
            if not first.get('ok'):
                raise RuntimeError('actual child import/start failed; no dependency retry')
            base='http://127.0.0.1:'+str(first['port'])
            observer=Observer(base,args.output,report,60)
            # Use the public observer's actual path, while taking child snapshots.
            import probe_transient_studio_resources as public_probe
            phase_started=time.perf_counter()
            before=rpc(process,'reset_peak')['snapshot']
            public_probe.observe(argparse.Namespace(document=args.document,base_url=base,http_timeout=60,job_timeout=90),args.output,report)
            report['server_internal_measurements']={'status':'instrumented companion snapshots and cumulative hooks',
                'limitations':['not an exhaustive producer allocation inventory',
                               'native coverage and eviction/disconnect lifecycle proof remain separate']}
            after=rpc(process,'snapshot')['snapshot']
            getter_counts={k:after['counts'].get('getter:'+k,0) for k in [
                'nodes_m','triangles','time_s','temperature_k','heat_flux_w_m2',
                'source_load_w_per_m','reaction_w_per_m','residual_w_per_m',
                'storage_rate_w_per_m','heat_content_j_per_m','quadratic_functional_jk_per_m',
                'dirichlet_node_ids','dirichlet_temperatures_k']}
            report['completed_capture_getters']=getter_counts
            if any(v!=1 for v in getter_counts.values()):
                raise ValueError('each13 completed-capture getter must have count1')
            if after['counts'].get('public_run')!=1 or after['counts'].get('capture')!=1:
                raise ValueError('expected exactly one actual public solve and capture')
            report['phases'].append({'name':'single_actual_solve_and_public_reads','elapsed_s':time.perf_counter()-phase_started,'before':before,'after':after})
            manifest=next(finite_json((args.output/r['raw_file']).read_bytes()) for r in report['requests']
                          if r['path'].endswith('/result') and 'raw_file' in r)
            job=manifest['job']; rid=manifest['result_id']
            path='/api/jobs/'+job+'/frame?'+urllib.parse.urlencode({'result_id':rid,'field':'temperature_k',
                         'time_index':len(manifest['time_s'])-1,'frame_seq':77})
            phase_started=time.perf_counter()
            before=rpc(process,'reset_peak')['snapshot']
            first_read,_=observer.request(path,save=True)
            for _ in range(10):
                item,_=observer.request(path)
                if any(item[k]!=first_read[k] for k in ['status','response_bytes','sha256']):
                    raise ValueError('identical repeated frame changed bytes/status')
            after=rpc(process,'snapshot')['snapshot']
            counts=delta(after['counts'],before['counts'])
            if any(v for k,v in counts.items() if k in {'public_run','capture'} or k.startswith('getter:')):
                raise ValueError('repeated reads invoked producer/solver/capture')
            if counts.get('view_encode')!=11:
                raise ValueError('expected exactly11 on-demand view encodes')
            report['phases'].append({'name':'eleven_identical_frames_no_producer_calls','elapsed_s':time.perf_counter()-phase_started,'before':before,'after':after,'counter_delta':counts})
            rpc(process,'hold_next_frame')
            with ThreadPoolExecutor(max_workers=1) as executor:
                pending=executor.submit(observer.request,path,save=True)
                try:
                    held=rpc(process,'wait_held')['snapshot']
                    if held['store']['record_pins']<1 or held['store']['snapshot_allocations']<1:
                        raise ValueError('held send has no observed record/output pin')
                    denied,_=observer.request(path,save=True)
                    if denied['status']!=429:
                        raise ValueError('concurrent read was not refused while send held')
                    report['phases'].append({'name':'actual_response_held_and_second_read429','held':held,
                                            'during':rpc(process,'snapshot')['snapshot']})
                finally:
                    rpc(process,'release_send')
                released,_=pending.result(timeout=65)
                if released['status']!=200:
                    raise ValueError('held original frame did not complete')
            recovered,_=observer.request(path,save=True)
            if recovered['status']!=200:
                raise ValueError('read admission did not recover')
            report['after_reader_release']=rpc(process,'snapshot')['snapshot']
            freed=report['after_reader_release']['store']
            if freed['record_pins'] or freed['snapshot_allocations'] or freed['read_workspace_bytes']:
                raise ValueError('reader accounting did not recover after completed sends')
            if args.reject_document:
                with args.reject_document.open('rb') as source:
                    raw=source.read(MIB+1)
                if len(raw)>MIB:raise ValueError('reject fixture exceeds request observation bound')
                (args.output/'reject-document.json').write_bytes(raw)
                report['reject_input_sha256']=hashlib.sha256(raw).hexdigest()
                doc=finite_json(raw);before=rpc(process,'snapshot')['snapshot']
                entry,_=observer.request('/api/thermal/transient/run',{'doc':doc,'client_revision':2,'request_seq':2},save=True)
                after=rpc(process,'snapshot')['snapshot']
                if entry['status']!=413 or after['counts'].get('public_run',0)!=before['counts'].get('public_run',0):
                    raise ValueError('over-budget actor did not reject before solver')
                report['phases'].append({'name':'supplied_over_budget_document413_no_solve','before':before,'after':after})
            report['cleanup']=rpc(process,'stop');process.wait(timeout=15)
            report['child_exit']=process.returncode
            if process.returncode:raise RuntimeError('child failed cleanup')
            report['ok']=True;code=0
    except BaseException as exc:
        report['failure']={'type':type(exc).__name__,'message':str(exc)}
    finally:
        if process is not None and process.poll() is None:
            with contextlib.suppress(Exception):rpc(process,'release_send')
            with contextlib.suppress(Exception):rpc(process,'stop');process.wait(timeout=15)
            if process.poll() is None:
                process.terminate();process.wait(timeout=15);report['forced_stop']=True
            report['child_exit']=process.returncode
        report['elapsed_s']=time.perf_counter()-started;report['exit_code']=code
        (args.output/'instrumented-report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    return code


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--child',action='store_true',help=argparse.SUPPRESS)
    p.add_argument('--source-root',type=Path,required=True)
    p.add_argument('--expected-commit')
    p.add_argument('--document',type=Path)
    p.add_argument('--reject-document',type=Path)
    p.add_argument('--output',type=Path)
    args=p.parse_args()
    if args.child:return child(args)
    if not(args.expected_commit and args.document and args.output):p.error('require expected commit, document and new output directory')
    return parent(args)

if __name__=='__main__':sys.exit(main())
