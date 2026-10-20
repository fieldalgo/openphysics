#!/usr/bin/env python3
# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Three bounded resource workloads; fresh parent/server processes per document.

Generated documents exercise the existing uniform-source transient contract.
They are resource observations, not independent numerical-oracle fixtures.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from probe_transient_studio_resources import workload_plan


def document(n, nt):
    return {
        'openphysics':'0.2','name':'Transient resource observation',
        'units':{'length':'m','temperature':'K','time':'s'},
        'geometry':{'domain':{'xmin':0.0,'xmax':0.002,'ymin':0.0,'ymax':0.001}},
        'materials':{},
        'physics':{'heat1':{'type':'thermal.transient2d','conductivity_w_mk':2.5,
                           'volumetric_heat_capacity_j_m3k':4.0,
                           'initial_temperature_k':300.0,'dirichlet_temperature_k':{},
                           'heat_source_w_m3':8.0}},
        'mesh':{'subdivisions':[n,n]},
        'study':{'type':'transient','time_s':[2.0+i*0.01 for i in range(nt)]},
        'results':{'save_fields':True,'plots':False}}


def prepare(output):
    plan=workload_plan(); paths={}
    for row in plan['cases']:
        path=output/(row['stage']+'.json')
        path.write_text(json.dumps(document(row['n'],row['nt']),indent=2,allow_nan=False)+'\n',encoding='utf-8')
        paths[row['stage']]=path
        row['document_file']=path.name
        row['document_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        row['actual_requested_dirichlet_nodes']=0
        row['preflight_dirichlet_upper_bound']='N before public boundary validation'
    return plan,paths


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-root',type=Path,default=Path('.'))
    p.add_argument('--expected-commit')
    p.add_argument('--output',required=True,type=Path,help='new retained artifact directory')
    p.add_argument('--prepare-only',action='store_true',help='write inputs/shape plan; no server or solver')
    args=p.parse_args(argv)
    if not args.prepare_only and not args.expected_commit:p.error('runtime requires full --expected-commit')
    args.output.mkdir(parents=True,exist_ok=False)
    summary={'format':'transient-resource-workloads-v1','scope':'arithmetic preparation only' if args.prepare_only else 'three actual resource workloads; not physical/capacity acceptance',
             'ok':False,'runtime_attempted':False,'completed_runtime_stages':0,'stages':[],'expected_commit':args.expected_commit}
    code=1
    try:
        plan,paths=prepare(args.output)
        summary['workload_plan']=plan
        if args.prepare_only:
            summary['ok']=True;code=0
        else:
            script=Path(__file__).with_name('profile_transient_studio_resources.py').resolve()
            for stage in ['small','medium','near_raw_candidate']:
                target=args.output/(stage+'-observation')
                command=[sys.executable,str(script),'--source-root',str(args.source_root.resolve()),
                         '--expected-commit',args.expected_commit,'--document',str(paths[stage].resolve()),
                         '--output',str(target.resolve())]
                if stage=='near_raw_candidate':
                    command+=['--reject-document',str(paths['over_raw_candidate'].resolve())]
                start=time.perf_counter()
                with (args.output/(stage+'.stdout')).open('w',encoding='utf-8') as stdout, (args.output/(stage+'.stderr')).open('w',encoding='utf-8') as stderr:
                    run=subprocess.run(command,stdout=stdout,stderr=stderr,check=False)
                summary['runtime_attempted']=True
                row={'stage':stage,'command':command,'exit_code':run.returncode,'elapsed_s':time.perf_counter()-start,
                     'report':str(target.relative_to(args.output)/'instrumented-report.json')}
                summary['stages'].append(row)
                report=target/'instrumented-report.json'
                if run.returncode or not report.is_file():
                    raise RuntimeError('stage failed; preserved original attempt, no retry or later workload: '+stage)
                actual=json.loads(report.read_text(encoding='utf-8'))
                if actual.get('ok') is not True or actual.get('forced_stop'):
                    raise RuntimeError('instrumented stage did not complete: '+stage)
                row['report_sha256']=hashlib.sha256(report.read_bytes()).hexdigest()
                summary['completed_runtime_stages']+=1
            summary['ok']=True;code=0
    except Exception as exc:
        summary['failure']={'type':type(exc).__name__,'message':str(exc)}
    finally:
        summary['exit_code']=code
        (args.output/'workload-summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    return code

if __name__=='__main__':sys.exit(main())
