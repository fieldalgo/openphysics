// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// The Studio browser checks' launch (tools/studio_browser/browser_launch.mjs) with a fake browser:
// one relaunch when the DevTools endpoint does not answer, every failed attempt recorded with its
// command line, exit code and stderr tail, and a second failure still failing.
const test=require('node:test');const assert=require('node:assert/strict');
const path=require('node:path');const {spawn}=require('node:child_process');const net=require('node:net');const {pathToFileURL}=require('node:url');
const HELPER=pathToFileURL(path.join(__dirname,'..','..','tools','studio_browser','browser_launch.mjs')).href;
// A fake browser: "exit" writes to stderr and exits 3; "answer-on-2" serves /json/list with one
// page only on attempt 2 and exits 3 on attempt 1; "silent" runs and never answers.
const FAKE=`const [mode,port,attempt]=process.argv.slice(1);
if(mode==='silent'){setInterval(()=>{},1000);}
else if(mode==='answer-on-2'&&attempt==='2'){require('node:http').createServer((q,r)=>{r.setHeader('content-type','application/json');r.end(JSON.stringify([{type:'page',webSocketDebuggerUrl:'ws://127.0.0.1:'+port+'/devtools/page/1'}]));}).listen(+port,'127.0.0.1');}
else{process.stderr.write('fake browser failed to start on '+port+'\\n');process.exit(3);}`;
const freePort=()=>new Promise(r=>{const s=net.createServer();s.listen(0,'127.0.0.1',()=>{const p=s.address().port;s.close(()=>r(p));});});
function harness(mode){
 const owned=[];
 const launch=(command,argv)=>{const child=spawn(command,argv,{stdio:['ignore','pipe','pipe']});owned.push(child);return child;};
 return {owned,options:{launch,command:process.execPath,freePort,argv:(port,attempt)=>['-e',FAKE,mode,String(port),String(attempt)],waitMs:1500}};
}
test('a browser that exits at once is launched twice, both recorded, and the launch fails',async()=>{
 const {launchBrowser,LAUNCH_WAIT_MS,LAUNCH_ATTEMPTS}=await import(HELPER);
 assert.equal(LAUNCH_WAIT_MS,60000);assert.equal(LAUNCH_ATTEMPTS,2);
 const {owned,options}=harness('exit'),report={};
 await assert.rejects(launchBrowser({...options,report}),/^Error: Browser DevTools endpoint unavailable after 2 launches/);
 assert.equal(owned.length,2,'one relaunch, no more');
 assert.equal(report.browserLaunch.length,2);
 for(const [i,a] of report.browserLaunch.entries()){
  assert.equal(a.attempt,i+1);assert.equal(a.ok,false);assert.equal(a.command,process.execPath);
  assert.equal(a.args.at(-1),String(i+1));assert.equal(a.exit,3);assert.match(a.stderrTail,/^fake browser failed to start on \d+\n$/);
 }
 assert.notEqual(report.browserLaunch[0].args.at(-2),report.browserLaunch[1].args.at(-2),'a new port for the relaunch');
});
test('a browser that answers on the relaunch is used, and the first attempt is recorded',async()=>{
 const {launchBrowser}=await import(HELPER);
 const {owned,options}=harness('answer-on-2'),report={};
 try{
  const got=await launchBrowser({...options,report});
  assert.equal(got.attempt,2);assert.equal(got.target.type,'page');assert.notEqual(got.port,+report.browserLaunch[0].args.at(-2),'the relaunch has its own port');
  assert.deepEqual(report.browserLaunch.map(a=>[a.attempt,a.ok]),[[1,false],[2,true]]);
  assert.equal(report.browserLaunch[0].exit,3);
 }finally{for(const c of owned)c.kill();}
});
test('a browser that never answers is stopped before the relaunch, and its signal recorded',async()=>{
 const {launchBrowser}=await import(HELPER);
 const {owned,options}=harness('silent'),report={};
 try{
  await assert.rejects(launchBrowser({...options,report}),/Browser DevTools endpoint unavailable/);
  assert.equal(owned.length,2);
  for(const a of report.browserLaunch){assert.equal(a.ok,false);assert.ok(a.signal==='SIGTERM'||a.exit!==null,JSON.stringify(a));assert.ok(a.ms>=1500);}
  assert.ok(owned.every(c=>c.exitCode!==null||c.signalCode!==null),'each attempt was stopped');
 }finally{for(const c of owned)c.kill();}
});
// endScript: a browser script ends even when a process it started ignores SIGTERM, or a process it
// did not start itself (a browser's helper) keeps its stdout pipe open. On 2026-11-24 the project
// script passed on macOS and then ran until the CI job's limit with a Chrome process left.
// The "script" is a child Node process, since endScript exits the process it runs in.
// stubborn: ignores SIGTERM. holder: starts a grandchild that inherits the stub's stdout, prints
// the grandchild's pid and exits, so the stub's stdout pipe stays open after the stub is gone.
const STUB=`const mode=process.argv[1];
if(mode==='stubborn'){process.on('SIGTERM',()=>{});setInterval(()=>{},1000);}
else{const g=require('node:child_process').spawn(process.execPath,['-e','setInterval(()=>{},1000)'],{stdio:['ignore','inherit','inherit'],detached:true});g.unref();process.stderr.write('grandchild '+g.pid+'\\n');setTimeout(()=>process.exit(0),200);}`;
function script(mode,exitCode){
 const body=`import {spawn} from 'node:child_process';import {endScript} from ${JSON.stringify(HELPER)};
const owned=[];const c=spawn(process.execPath,['-e',${JSON.stringify(STUB)},${JSON.stringify(mode)}],{stdio:['ignore','pipe','pipe']});owned.push(c);
let err='';c.stderr.on('data',x=>{err+=x;process.stderr.write(x);});c.stdout.on('data',()=>{});
await new Promise(r=>setTimeout(r,800));
${exitCode===null?'':`process.exitCode=${exitCode};`}
await endScript(owned,'[fake browser] '+(${JSON.stringify(mode)})+' done',500);`;
 const started=Date.now();
 const p=spawn(process.execPath,['--input-type=module','-e',body],{stdio:['ignore','pipe','pipe']});
 let out='',err='';p.stdout.on('data',x=>{out+=x;});p.stderr.on('data',x=>{err+=x;});
 return new Promise((resolve,reject)=>{
  const timer=setTimeout(()=>{p.kill('SIGKILL');reject(new Error('script did not exit within 20 s: '+err));},20000);
  p.on('exit',(code,signal)=>{clearTimeout(timer);resolve({code,signal,out,err,ms:Date.now()-started});});
 });
}
test('endScript stops a child that ignores SIGTERM and exits with process.exitCode',async()=>{
 const {END_WAIT_MS}=await import(HELPER);
 assert.equal(END_WAIT_MS,10000);
 const r=await script('stubborn',null);
 assert.equal(r.code,0,r.err);assert.equal(r.signal,null);
 assert.equal(r.out,'[fake browser] stubborn done\n');
 const failed=await script('stubborn',1);
 assert.equal(failed.code,1,failed.err);assert.equal(failed.out,'[fake browser] stubborn done\n');
});
test('endScript exits while a process it did not start still holds its stdout pipe',async()=>{
 const r=await script('holder',null);
 const found=r.err.split('\n').find(l=>l.startsWith('grandchild '));
 try{
  assert.equal(r.code,0,r.err);assert.equal(r.out,'[fake browser] holder done\n');
  assert.ok(found,'the stub reported its grandchild: '+r.err);
 }finally{
  const pid=found?Number(found.slice('grandchild '.length)):NaN;
  if(Number.isInteger(pid)){try{process.kill(pid,'SIGKILL');}catch{}}
 }
});
