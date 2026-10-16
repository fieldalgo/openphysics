// Real installed Studio browser acceptance through the shipped page and public API.
// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
import {spawn, spawnSync} from 'node:child_process';
import {readFile, writeFile, mkdir, mkdtemp, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {createServer} from 'node:net';

const args=process.argv.slice(2);
function arg(name){const i=args.indexOf(name);if(i<0||!args[i+1])throw Error('Missing '+name);return args[i+1];}
const expectedRoot=resolve(arg('--expected-installed-root')), hashes=JSON.parse(await readFile(arg('--expected-module-hashes'),'utf8'));
const out=resolve(arg('--output')), python=arg('--python'), model=JSON.parse(await readFile(arg('--model'),'utf8'));
await mkdir(out,{recursive:false});
const artifactWrites=[];
const report={status:'incomplete',scope:'real installed Studio browser/public API',node:process.version,console:[],stages:[]};
const owned=[]; let profile,cdp;
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function port(){const s=createServer();await new Promise(r=>s.listen(0,'127.0.0.1',r));const p=s.address().port;await new Promise(r=>s.close(r));return p;}
async function wait(fn,label){const end=Date.now()+60000;while(Date.now()<end){try{const x=await fn();if(x)return x;}catch{}await sleep(200);}throw Error('Timeout: '+label);}
function launch(command,argv,name){const p=spawn(command,argv,{stdio:['ignore','pipe','pipe'],env:{...process.env,OPENBLAS_NUM_THREADS:'1',OMP_NUM_THREADS:'1',MKL_NUM_THREADS:'1'}});owned.push(p);let log='';p.stdout.on('data',x=>{log+=x});p.stderr.on('data',x=>{log+=x});p.on('error',e=>{log+=String(e)});p.on('close',(exit,signal)=>{report[name]={pid:p.pid,exit,signal};artifactWrites.push(writeFile(join(out,name+'.log'),log,'utf8'));});return p;}
class CDP{
 constructor(url){this.id=0;this.pending=new Map();this.ws=new WebSocket(url);this.ready=new Promise((r,j)=>{this.ws.addEventListener('open',r,{once:true});this.ws.addEventListener('error',j,{once:true});});this.ws.addEventListener('message',e=>{const x=JSON.parse(e.data);if(x.id){const p=this.pending.get(x.id);if(p){clearTimeout(p.timer);this.pending.delete(x.id);x.error?p.reject(Error(JSON.stringify(x.error))):p.resolve(x.result);}}else if(x.method==='Runtime.exceptionThrown'||(x.method==='Runtime.consoleAPICalled'&&x.params.type==='error'))report.console.push(x);});}
 async call(method,params={}){await this.ready;const id=++this.id;return new Promise((resolve,reject)=>{const timer=setTimeout(()=>{this.pending.delete(id);reject(Error('CDP timeout '+method))},30000);this.pending.set(id,{resolve,reject,timer});this.ws.send(JSON.stringify({id,method,params}));});}
 async eval(expression){const r=await this.call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;}
}
try{
 const found=spawnSync('which',['google-chrome','chromium','chromium-browser','google-chrome-stable'],{encoding:'utf8'});
 const chrome=found.stdout.trim().split('\n').find(Boolean);
 report.browserDiscovery={exit:found.status,stdout:found.stdout,stderr:found.stderr};
 if(!chrome){report.status='browser-unavailable';throw Error('No preinstalled browser; no download attempted');}
 report.browserVersion=spawnSync(chrome,['--version'],{encoding:'utf8',timeout:5000}).stdout.trim();
 const origin=spawnSync(python,['-I','-c',"import hashlib,importlib,json,sys; from pathlib import Path; root=Path(sys.argv[1]).resolve(); expected=json.loads(sys.argv[2]); report={}; assert sys.flags.isolated and Path(sys.prefix).resolve()==root;\nfor name,digest in expected.items():\n p=Path(importlib.import_module(name).__file__).resolve(); assert p.is_relative_to(root); actual=hashlib.sha256(p.read_bytes()).hexdigest(); assert actual==digest; report[name]={'origin':str(p),'sha256':actual}\nprint(json.dumps(report))",expectedRoot,JSON.stringify(hashes)],{encoding:'utf8',timeout:45000});
 report.origin={exit:origin.status,stdout:origin.stdout,stderr:origin.stderr};if(origin.status!==0)throw Error('Installed origin probe failed');
 const apiPort=await port(),debugPort=await port(),base='http://127.0.0.1:'+apiPort;
 launch(python,['-I','-m','uvicorn','simcase.studio.server:app','--host','127.0.0.1','--port',String(apiPort),'--log-level','warning'],'server');
 await wait(async()=>{const r=await fetch(base+'/api/capabilities');return r.ok},'server');
 profile=await mkdtemp(join(tmpdir(),'studio-browser-'));
 launch(chrome,['--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--remote-debugging-address=127.0.0.1','--remote-debugging-port='+debugPort,'--user-data-dir='+profile,'--window-size=1440,1000','about:blank'],'browser');
 const targets=await wait(async()=>{const r=await fetch('http://127.0.0.1:'+debugPort+'/json/list');return r.ok?await r.json():null},'CDP');
 cdp=new CDP(targets.find(x=>x.type==='page').webSocketDebuggerUrl);
 await cdp.call('Runtime.enable');await cdp.call('Page.enable');
 await cdp.call('Page.navigate',{url:base});
 await wait(()=>cdp.eval("document.readyState==='complete' && !!document.querySelector('#applyJson') && thermalController.state().cap?.run_enabled===true"),'page');
 const click=selector=>cdp.eval('(()=>{const e=document.querySelector('+JSON.stringify(selector)+');if(!e||e.disabled)throw Error("Missing/disabled control");e.click();return true})()');
 const snapshot=async(name,canvas)=>{await sleep(300);const state=await cdp.eval('(()=>{const c=document.querySelector('+JSON.stringify(canvas)+'),r=c.getBoundingClientRect();const pixels=c.getContext("2d").getImageData(0,0,c.width,c.height).data;let paintedPixels=0;for(let i=3;i<pixels.length;i+=4)if(pixels[i])paintedPixels++;return {paintedPixels,status:document.querySelector("#status").textContent,canvas:{width:c.width,height:c.height,cssWidth:r.width,cssHeight:r.height},runDisabled:document.querySelector("#runBtn").disabled}})()');report.stages.push({name,...state});if(!(state.canvas.width>0&&state.canvas.height>0&&state.canvas.cssWidth>0&&state.canvas.cssHeight>0&&state.paintedPixels>0))throw Error('Zero-size visible canvas '+name);const png=await cdp.call('Page.captureScreenshot',{format:'png'});await writeFile(join(out,name+'.png'),Buffer.from(png.data,'base64'));};
 await click('[data-tab="json"]');
 await cdp.eval('(()=>{const e=document.querySelector("#json");e.value='+JSON.stringify(JSON.stringify(model,null,2))+';e.dispatchEvent(new Event("input",{bubbles:true}));return true})()');
 await click('#applyJson');
 await wait(()=>cdp.eval('!document.querySelector("#runBtn").disabled'),'applied/validated');
 await click('#validate');
 await wait(()=>cdp.eval('!document.querySelector("#runBtn").disabled'),'explicit validation');
 await click('#runBtn');
 await wait(()=>cdp.eval('document.querySelector("#status").textContent==="steady thermal result ready"'),'real solver result');
 await snapshot('temperature','#fieldCanvas');
 await cdp.eval('(()=>{const e=document.querySelector("#thermalField");e.value="magnitude";e.dispatchEvent(new Event("change",{bubbles:true}));return true})()');
 await snapshot('flux','#fieldCanvas');
 await click('[data-tab="mesh"]');await snapshot('mesh','#meshCanvas');
 await click('[data-tab="results"]');await snapshot('results-return','#fieldCanvas');
 await click('[data-tab="json"]');
 await cdp.eval('(()=>{const e=document.querySelector("#json");e.value+=" ";e.dispatchEvent(new Event("input",{bubbles:true}));return true})()');
 const dirty=await cdp.eval('({disabled:document.querySelector("#runBtn").disabled,status:document.querySelector("#status").textContent})');
 report.dirty=dirty;if(!dirty.disabled)throw Error('Dirty JSON permits stale run');
 const cleared=await cdp.eval('(()=>{const c=document.querySelector("#fieldCanvas"),d=c.getContext("2d").getImageData(0,0,c.width,c.height).data;return !d.some((v,i)=>i%4===3&&v!==0)})()');
 report.dirty.cleared=cleared;if(!cleared)throw Error('Dirty JSON retained stale field pixels');
 await writeFile(join(out,'final-dom.json'),JSON.stringify(await cdp.eval('({status:document.querySelector("#status").textContent,controls:{runDisabled:document.querySelector("#runBtn").disabled,thermalHidden:document.querySelector("#thermalControls").hidden},html:document.documentElement.outerHTML})'),null,2)+'\n','utf8');
 if(report.console.length)throw Error('Browser console exception/error');
 report.model=model; report.fakeApi=false; report.injectedPhysicalResult=false;
 report.status='passed';
}catch(e){if(cdp){try{const png=await cdp.call('Page.captureScreenshot',{format:'png'});await writeFile(join(out,'failure.png'),Buffer.from(png.data,'base64'));}catch{}}
 report.error=String(e.stack||e);if(report.status!=='browser-unavailable')report.status='failed';process.exitCode=1;}
finally{
 if(cdp)cdp.ws.close();
 for(const p of owned.reverse()){if(p.exitCode===null){p.kill('SIGTERM');await Promise.race([new Promise(r=>p.once('close',r)),sleep(5000)]);if(p.exitCode===null&&p.signalCode===null){p.kill('SIGKILL');await new Promise(r=>p.once('close',r));}}}
 if(profile)await rm(profile,{recursive:true,force:true});
 await Promise.all(artifactWrites);
 await writeFile(join(out,'browser-report.json'),JSON.stringify(report,null,2)+'\n','utf8');
}
