// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

// Session file version 8: a multiphysics model with its runs (docs/packages/simcase/workspace.md,
// "Session files"). One JSON object {format, version: 8, application: "multiphysics", document,
// runs, baselines, selected, view}. Optical sessions stay version 7 (workspace-notebook.mjs).
// Version 15 (run retention, design "Keeping more runs" section 7): version 8 with 0 to 20 runs,
// written only when the session has more than six runs; a session of six or fewer is version 8, byte
// for byte. The maps of the runs are kept within the field budget (workspace-budget.mjs) when a map
// arrives: a new result, a recompute, or an opened or restored session.
//
// Every number is written in its shortest round-trip form, as JSON.stringify writes it, except
// negative zero, which is written -0.0 so that it reads back as negative zero; NaN and the
// infinities are refused. Each run and each without-heater result carries a SHA-256 digest of
// itself without the digest, as sorted-key JSON with the same number rules. The digest detects a
// damaged or hand-edited file; it is not an authentication: whoever edits a file can recompute it.
import {ENVELOPE,uncoupledDocument,canonicalJson,physicsLabel,materialUses} from './workspace-multiphysics.mjs';
import {FIELD_BUDGET_BYTES,budgetOrder,budgetChoose} from './workspace-budget.mjs';
import {validateRunLabel} from './workspace-notebook.mjs';

export const SESSION_FORMAT='openphysics-studio-session';
export const MULTIPHYSICS_VERSION=8;
export const RUNS_MULTIPHYSICS_VERSION=15;
export const MULTIPHYSICS_RUN_LIMIT=20;
/** The most runs a version 8 file holds. */
export const PREVIOUS_MULTIPHYSICS_RUN_LIMIT=6;
/** The version a session of these runs is written as: 15 above six runs, else 8. */
export const multiphysicsVersion=runs=>runs.length>PREVIOUS_MULTIPHYSICS_RUN_LIMIT?RUNS_MULTIPHYSICS_VERSION:MULTIPHYSICS_VERSION;
/** The session versions of a multiphysics model. */
export const MULTIPHYSICS_VERSIONS=Object.freeze([MULTIPHYSICS_VERSION,RUNS_MULTIPHYSICS_VERSION]);
export const MAX_SESSION_BYTES=16*1024*1024;
export const MAX_DOCUMENT_BYTES=1024*1024;
export const RESULT_FORMAT='multiphysics-run-v1';
// The replies of a one-physics ("0.3") model run in the multiphysics view, by type: the layouts
// Studio reads for the two types it runs there.
export const SINGLE_RESULT_FORMATS=Object.freeze({'em.modes2d':['em-modes2d-p1-node-centroid-v2'],
 'thermal.steady2d':['thermal.steady2d-result-v3','thermal.steady2d-result-v4','thermal.steady2d-regions-result-v2']});
export const VIEW_PAGES=Object.freeze(['Model','Connections','Results']);
export const INDEX_MAPS=Object.freeze(['index','change']);
export const MAPS_NOT_KEPT='Maps not kept in this file: n_eff, the coupling check and the iteration history are.';
const isObject=x=>x!==null&&typeof x==='object'&&!Array.isArray(x);
// an own entry of a record: "__proto__" or "toString" name nothing in a document
const own=(o,k)=>isObject(o)&&Object.hasOwn(o,k)&&isObject(o[k]);
const plural=(n,word)=>`${n} ${word}${n===1?'':'s'}`;
const utf8=text=>new TextEncoder().encode(text);

// ---- numbers and text --------------------------------------------------------------------------
function numberText(n){
 if(!Number.isFinite(n))throw new Error('A session cannot hold NaN or an infinite value.');
 return Object.is(n,-0)?'-0.0':JSON.stringify(n);
}
function write(value,sorted){
 if(typeof value==='number')return numberText(value);
 if(value===null||typeof value==='boolean'||typeof value==='string')return JSON.stringify(value);
 if(Array.isArray(value))return '['+value.map(v=>write(v,sorted)).join(',')+']';
 if(ArrayBuffer.isView(value))return '['+Array.from(value,numberText).join(',')+']';
 if(typeof value==='object'){const keys=Object.keys(value).filter(k=>value[k]!==undefined);if(sorted)keys.sort();
  return '{'+keys.map(k=>JSON.stringify(k)+':'+write(value[k],sorted)).join(',')+'}';}
 throw new Error('A session holds only JSON values.');
}
/** The file text of a value: its keys in their order, the §2 number rules. */
export const sessionJson=value=>write(value,false);
/** The digest text of a value: sorted keys (UTF-16 order, as Array.prototype.sort), the same numbers. */
export const digestJson=value=>write(value,true);

// ---- SHA-256 (FIPS 180-4) over the UTF-8 bytes of a text; synchronous, so a page served over
// plain http and the module tests compute the same value as node:crypto ----------------------------
const K=new Uint32Array([0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
 0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
 0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
 0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2]);
export function sha256Hex(input){
 const bytes=typeof input==='string'?utf8(input):input,length=bytes.length,blocks=Math.ceil((length+9)/64),data=new Uint8Array(blocks*64);
 data.set(bytes);data[length]=0x80;const view=new DataView(data.buffer),bits=length*8;
 view.setUint32(data.length-8,Math.floor(bits/2**32));view.setUint32(data.length-4,bits>>>0);
 const h=new Uint32Array([0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19]),w=new Uint32Array(64);
 for(let b=0;b<blocks;b++){
  for(let i=0;i<16;i++)w[i]=view.getUint32(b*64+i*4);
  for(let i=16;i<64;i++){const x=w[i-15],y=w[i-2];w[i]=(((x>>>7|x<<25)^(x>>>18|x<<14)^(x>>>3))+w[i-7]+((y>>>17|y<<15)^(y>>>19|y<<13)^(y>>>10))+w[i-16])>>>0;}
  let [a,c,d,e,f,g,k,m]=h;
  for(let i=0;i<64;i++){
   const t1=(m+((f>>>6|f<<26)^(f>>>11|f<<21)^(f>>>25|f<<7))+((f&g)^(~f&k))+K[i]+w[i])>>>0;
   const t2=(((a>>>2|a<<30)^(a>>>13|a<<19)^(a>>>22|a<<10))+((a&c)^(a&d)^(c&d)))>>>0;
   m=k;k=g;g=f;f=(e+t1)>>>0;e=d;d=c;c=a;a=(t1+t2)>>>0;
  }
  h[0]+=a;h[1]+=c;h[2]+=d;h[3]+=e;h[4]+=f;h[5]+=g;h[6]+=k;h[7]+=m;
 }
 return Array.from(h,x=>x.toString(16).padStart(8,'0')).join('');
}
/** "sha256:<hex>" of a record without its digest. */
export function recordDigest(record){const {digest,...rest}=record;return 'sha256:'+sha256Hex(digestJson(rest));}

// ---- sizes ------------------------------------------------------------------------------------
export const byteLength=text=>utf8(text).length;
export function sizeText(bytes){const mb=bytes/1e6;return `${mb<10?Number(mb.toFixed(1)):Math.round(mb)} MB`;}

// ---- runs -------------------------------------------------------------------------------------
/** The run list: a run of the same job replaces itself (keeping its name and pin); a new run
 * replaces the oldest unpinned one once 20 are kept. Throws when all 20 are pinned. */
export function appendMultiphysicsRun(runs,run){
 const previous=runs.find(r=>r.job===run.job);
 const next=[...runs.filter(r=>r.job!==run.job),previous?{...run,label:previous.label||run.label,pinned:previous.pinned||run.pinned}:run];
 while(next.length>MULTIPHYSICS_RUN_LIMIT){const oldest=next.findIndex(r=>!r.pinned&&r.job!==run.job);if(oldest<0)throw new Error(`All ${MULTIPHYSICS_RUN_LIMIT} runs are pinned. Unpin a run before running again.`);next.splice(oldest,1);}
 return next;
}
export const nextRunNumber=runs=>runs.reduce((n,r)=>Math.max(n,r.number),0)+1;
export function multiphysicsRunName(run){return `Run ${run.number}${run.label?' '+run.label:''}${run.pinned?' (pinned)':''}`;}

// The reply of a run without its arrays: what a run keeps when its maps are not kept.
export function valuesOnly(result){
 const {mesh,...rest}=result,physics={};
 for(const [name,p] of Object.entries(result.physics||{})){
  if(p.type==='thermal.steady2d'){const {temperature,...kept}=p;physics[name]={...kept,temperature:{unit:temperature?.unit,location:temperature?.location}};}
  else if(p.type==='em.modes2d'&&p.coupled){const c=p.coupled;physics[name]={...p,coupled:{temperature:{unit:c.temperature?.unit,location:c.temperature?.location},refractive_index:{location:c.refractive_index?.location}}};}
  else physics[name]=p;
 }
 return {...rest,physics};
}
export function meshCounts(result){return {nodes:result.mesh.node_coordinates.length,triangles:result.mesh.triangles.length};}
/** A run as the file stores it. keepMaps false stores its values only (§2), with the node and
 * triangle counts the Coupling check names. */
export function sessionRun(run,keepMaps=true){
 const kept=keepMaps&&run.maps!=='not kept';
 const record={job:run.job,number:run.number,label:run.label||'',pinned:run.pinned===true,completedAt:run.completedAt,serverVersion:run.serverVersion??null,
  document:run.doc,events:run.events||[],maps:kept?'kept':'not kept',...(kept?{}:{counts:run.counts||meshCounts(run.result)}),result:kept?run.result:run.maps==='not kept'?run.result:valuesOnly(run.result)};
 return {...record,digest:recordDigest(record)};
}
function sessionBaseline(b){const record={job:b.job,completedAt:b.completedAt,document:b.document,result:b.result};return {...record,digest:recordDigest(record)};}
// a baseline is written only for a run in the file or the current document (§1)
function baselineTied(name,b,documents){const key=canonicalJson(b.document);return documents.some(d=>isObject(d?.physics?.[name])&&canonicalJson(uncoupledDocument(d,name))===key);}
// The text of each run record, kept while the run is unchanged: a run's document, events and
// result never change once it is completed, so only its number, name, pin and maps make a new
// text. Browser recovery writes the session after every change; this keeps that write from
// serialising and hashing every map again.
const runTexts=new WeakMap();
function runPiece(run,keep){
 const kept=keep&&run.maps!=='not kept',key=JSON.stringify([run.job,run.number,run.label||'',run.pinned===true,run.completedAt,run.serverVersion??null,kept,run.maps]);
 let byKey=runTexts.get(run.result);if(!byKey){byKey=new Map();runTexts.set(run.result,byKey);}
 let piece=byKey.get(key);
 if(!piece||piece.doc!==run.doc||piece.events!==run.events){const record=sessionRun(run,kept),text=sessionJson(record);piece={record,text,bytes:byteLength(text),doc:run.doc,events:run.events};byKey.set(key,piece);if(byKey.size>8)byKey.delete(byKey.keys().next().value);}
 return piece;
}
function sessionBaselines(state){
 const documents=[state.document,...state.runs.map(r=>r.doc)],baselines={};
 for(const [name,b] of Object.entries(state.baselines||{}))if(b&&b.document&&b.job&&baselineTied(name,b,documents))baselines[name]=sessionBaseline(b);
 return baselines;
}
/** The session object. state: {document, runs, baselines: {name: {job, completedAt, document,
 * result}}, selected: job or null, view}; keep: the jobs whose maps are kept (default all). */
export function createMultiphysicsSession(state,keep=null){
 return {format:SESSION_FORMAT,version:multiphysicsVersion(state.runs),application:'multiphysics',document:state.document,runs:state.runs.map(r=>runPiece(r,keep?keep.has(r.job):true).record),
  baselines:sessionBaselines(state),selected:state.selected??null,view:state.view};
}
// The file as parts: sessionJson(createMultiphysicsSession(state, keep)) is head + the run texts
// joined by commas + tail; its size is counted without building the text.
function fileParts(state,keep,baselines=sessionBaselines(state)){
 const head=`{"format":${sessionJson(SESSION_FORMAT)},"version":${multiphysicsVersion(state.runs)},"application":"multiphysics","document":${sessionJson(state.document)},"runs":[`;
 const pieces=state.runs.map(r=>runPiece(r,keep?keep.has(r.job):true));
 const tail=`],"baselines":${sessionJson(baselines)},"selected":${sessionJson(state.selected??null)},"view":${sessionJson(state.view)}}`;
 const bytes=byteLength(head)+byteLength(tail)+pieces.reduce((n,p)=>n+p.bytes,0)+Math.max(0,pieces.length-1);
 return {bytes,baselines:Object.keys(baselines).length,text:()=>head+pieces.map(p=>p.text).join(',')+tail};
}
// the runs that keep their maps when the file would exceed the limit: the selected and pinned
const priority=state=>new Set(state.runs.filter(r=>r.pinned||r.job===state.selected).map(r=>r.job));
/** Save session (§2): {ok, text, bytes, notKept, baselines} when it fits; else {ok: false,
 * bytes, reduced} where reduced is the file with the maps of the selected and pinned runs only
 * (null when even that is over the limit, with refusal naming why). keepSelected writes the
 * reduced file. name: false leaves out the per-run refusal (browser recovery has no use for it). */
export function writeMultiphysicsSession(state,{keepSelected=false,limit=MAX_SESSION_BYTES,name=true}={}){
 const baselines=sessionBaselines(state),full=fileParts(state,null,baselines),valuesOnlyRuns=state.runs.filter(r=>r.maps==='not kept').map(r=>r.number);
 if(full.bytes<=limit)return {ok:true,text:full.text(),bytes:full.bytes,notKept:valuesOnlyRuns,baselines:full.baselines};
 const keep=priority(state),reduced=fileParts(state,keep,baselines);
 const notKept=state.runs.filter(r=>!keep.has(r.job)||r.maps==='not kept').map(r=>r.number);
 if(reduced.bytes<=limit)return keepSelected?{ok:true,text:reduced.text(),bytes:reduced.bytes,notKept,baselines:reduced.baselines}:{ok:false,bytes:full.bytes,reduced:{bytes:reduced.bytes,notKept},refusal:null};
 if(!name)return {ok:false,bytes:full.bytes,reduced:null,refusal:null};
 // over the limit with only the selected and pinned maps: name the run that alone exceeds it
 const kept=state.runs.filter(r=>keep.has(r.job)&&r.maps!=='not kept');
 for(const run of kept){const alone=fileParts({...state,runs:[run],selected:run.job,baselines:{}},null,{}).bytes;
  if(alone>limit)return {ok:false,bytes:full.bytes,reduced:null,refusal:`Run ${run.number} alone is ${sizeText(alone)}, over the 16 MiB session limit. Unpin it or keep it in a smaller-mesh model.`};}
 return {ok:false,bytes:full.bytes,reduced:null,refusal:`The selected and pinned runs (${kept.map(r=>'Run '+r.number).join(', ')}) are ${sizeText(reduced.bytes)} with their maps, over the 16 MiB session limit. Unpin some of them.`};
}
export function overflowQuestion(bytes){return `Session is ${sizeText(bytes)}; the limit is 16 MiB. Keep the maps of the selected and pinned runs only? The other runs keep n_eff, the coupling check and the iteration history, but not their maps.`;}
/** Browser recovery (§4): the file, or, over the limit, the maps in the order of run retention
 * (the selected run's, then pinned newest first, then the others newest first) within the limit,
 * without a dialog (HK13). Throws when even the selected run's maps alone are over it. */
export function recoveryText(state,limit=MAX_SESSION_BYTES){
 const baselines=sessionBaselines(state),full=fileParts(state,null,baselines);
 if(full.bytes<=limit)return {ok:true,text:full.text(),bytes:full.bytes,notKept:state.runs.filter(r=>r.maps==='not kept').map(r=>r.number),baselines:full.baselines};
 const withMaps=state.runs.filter(r=>r.maps!=='not kept'),base=fileParts(state,new Set(),baselines).bytes;
 const {kept}=budgetChoose(budgetOrder(withMaps,state.selected??null),{base,bytes:mapBytes,selected:state.selected??null,budget:limit});
 const keep=new Set(kept.map(r=>r.job)),out=fileParts(state,keep,baselines);
 if(out.bytes>limit)throw Object.assign(new Error('browser recovery unavailable: session over 16 MiB'),{code:'recovery-over-limit'});
 return {ok:true,text:out.text(),bytes:out.bytes,notKept:state.runs.filter(r=>!keep.has(r.job)).map(r=>r.number),baselines:out.baselines};
}

// ---- run retention: the maps within the budget (design "Keeping more runs", section 7) -----------
/** The bytes a run's maps add to a session file: its record with its maps less its record without
 * them (both texts cached while the run is unchanged); 0 for a run without maps. */
export function mapBytes(run){return run.maps==='not kept'?0:runPiece(run,true).bytes-runPiece(run,false).bytes;}
/** The session file's bytes with no run's maps (the base of the budget). */
export const sessionBytesWithoutMaps=state=>fileParts(state,new Set()).bytes;
/** The session text with the maps of the runs in keep only (for checks; null: every run's). */
export const sessionText=(state,keep=null)=>fileParts(state,keep).text();
/** The maps the budget keeps (state: the session state, its selected run): {kept, letGo, total,
 * base, fits}. kept and letGo: runs with maps; total: the file bytes with the kept maps (null when no
 * run has maps); fits: every map is kept. first: the jobs whose maps arrived (a recompute, a swap). */
export function chooseMaps(state,{first=[],budget=FIELD_BUDGET_BYTES,bytes=mapBytes}={}){
 const withMaps=state.runs.filter(r=>r.maps!=='not kept');
 if(!withMaps.length)return {kept:[],letGo:[],total:null,base:null,fits:true};
 const base=sessionBytesWithoutMaps(state),sum=withMaps.reduce((t,r)=>t+bytes(r),base),selected=state.selected??null;
 if(sum<=budget)return {kept:withMaps,letGo:[],total:sum,base,fits:true};
 const {kept,letGo,total}=budgetChoose(budgetOrder(withMaps,selected,first),{base,bytes,selected,budget});
 return {kept,letGo,total,base,fits:false};
}
/** chooseMaps, with the maps of letGo let go (in place): what the tab does when a map arrives. */
export function keepMapsAtArrival(state,options={}){
 const out=chooseMaps(state,options);for(const r of out.letGo)letGoMaps(r);return out;
}
/** The bytes of the session with the maps of the selected and pinned runs only (the words when a
 * pinned run's maps go). */
export const selectedAndPinnedMapBytes=(state,base)=>state.runs.filter(r=>r.maps!=='not kept'&&(r.pinned||r.job===state.selected)).reduce((t,r)=>t+mapBytes(r),base);
const HELD=Symbol('held maps'),LET_GO=Symbol('maps let go in this tab');
/** A run's maps let go in the tab (in place: the run keeps its job, number, name and pin): the run
 * becomes what a file writes of it without its maps, "not kept" with its counts and its values. */
export function letGoMaps(run){
 if(run.maps==='not kept')return run;
 Object.defineProperty(run,HELD,{value:{result:run.result,bytes:mapBytes(run)},enumerable:false,configurable:true,writable:true});
 Object.defineProperty(run,LET_GO,{value:true,enumerable:false,configurable:true,writable:true});
 run.counts=meshCounts(run.result);run.result=valuesOnly(run.result);run.maps='not kept';
 return run;
}
/** Whether this tab let the run's maps go (else the run came without maps from a file or record). */
export const mapsLetGoHere=run=>run.maps==='not kept'&&run[LET_GO]===true;
/** Whether a run's let-go maps are still held for Keep Run N's maps. */
export const heldMaps=run=>run.maps==='not kept'&&!!run[HELD];
/** The run's let-go maps back, as they were (Keep Run N's maps). */
export function takeBackMaps(run){
 const held=run[HELD];if(!held||run.maps!=='not kept')return false;
 run.result=held.result;run.maps='kept';delete run.counts;delete run[HELD];delete run[LET_GO];return true;
}
/** The held maps are dropped (at the next arrival the swap is stale, and memory is freed). */
export function forgetHeldMaps(runs){for(const r of runs)if(r[HELD])delete r[HELD];}
/** The run Keep Run N's maps lets go instead (letGo: one unpinned run): the oldest unpinned,
 * unselected run with maps at least as large, or null. */
export function mapSwapCandidate(runs,letGo,selected){
 if(letGo.length!==1||letGo[0].pinned||!heldMaps(letGo[0]))return null;
 const need=letGo[0][HELD].bytes;
 return runs.find(r=>r!==letGo[0]&&r.maps!=='not kept'&&!r.pinned&&r.job!==selected&&mapBytes(r)>=need)||null;
}

// ---- reading (§3) -----------------------------------------------------------------------------
const fail=text=>{throw new Error(text);};
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const runName=(r,i)=>`Run ${Number.isInteger(r?.number)&&r.number>0?r.number:i+1}`;
function documentSize(doc,what){if(!isObject(doc))fail(`${what} has no model.`);if(byteLength(sessionJson(doc))>MAX_DOCUMENT_BYTES)fail(`${what} is over 1 MiB, the size Studio reads a model file up to.`);}
function checkArrays(r,result,run){
 const where=`${r}'s stored maps are not well formed`,mesh=result.mesh;
 if(!isObject(mesh))fail(`${where}: the mesh is missing.`);
 const P=mesh.node_coordinates,T=mesh.triangles,R=mesh.regions,names=mesh.region_names;
 if(!Array.isArray(P)||!P.length||!P.every(p=>Array.isArray(p)&&p.length===2&&finite(p[0])&&finite(p[1])))fail(`${where}: node_coordinates must be N × 2 finite numbers.`);
 if(mesh.field_units?.node_coordinates!=='m')fail(`${where}: node_coordinates must be in m.`);
 const N=P.length;
 if(!Array.isArray(T)||!T.length||!T.every(t=>Array.isArray(t)&&t.length===3))fail(`${where}: triangles must be M × 3.`);
 T.forEach((t,i)=>{for(const n of t)if(!Number.isInteger(n)||n<0||n>=N)fail(`${where}: triangle ${i} names node ${n}, outside 0–${N-1}.`);});
 const M=T.length;
 if(!Array.isArray(names)||!names.length||!names.every(n=>typeof n==='string'))fail(`${where}: region_names must be texts.`);
 if(!Array.isArray(R)||R.length!==M||!R.every(x=>Number.isInteger(x)&&x>=0&&x<names.length))fail(`${where}: regions must hold ${M} integers in 0–${names.length-1}.`);
 const values=(a,n,what,nullable=false)=>{if(nullable&&a===null)return;if(!Array.isArray(a)||a.length!==n)fail(`${where}: ${what} has ${Array.isArray(a)?a.length:'no'} values for ${n} ${what.includes('node')?'nodes':'triangles'}.`);
  if(!a.every(finite))fail(`${where}: ${what} holds a value that is not a finite number.`);};
 for(const [name,p] of Object.entries(result.physics)){
  if(p.type==='thermal.steady2d'){
   if(p.temperature?.unit!=='K'||p.temperature?.location!=='node')fail(`${where}: ${physicsLabel(name)} temperature must be node values in K.`);
   values(p.temperature.values,N,`${physicsLabel(name)} node temperature`);
   let lo=Infinity,hi=-Infinity;for(const v of p.temperature.values){if(v<lo)lo=v;if(v>hi)hi=v;}
   if(p.range?.min!==lo||p.range?.max!==hi)fail(`${r}'s heat range does not equal the minimum and maximum of its stored temperatures.`);
  }else if(p.type==='em.modes2d'&&p.coupled){
   const c=p.coupled;
   if(c.temperature?.unit!=='K'||c.temperature?.location!=='element')fail(`${where}: the coupled temperature must be triangle values in K.`);
   values(c.temperature.values,M,'coupled triangle temperature');values(c.refractive_index?.n,M,'refractive_index.n');values(c.refractive_index?.k,M,'refractive_index.k',true);values(c.index_change,M,'index_change',true);
   // §3.4.5: the coupled temperature is the mean of the stored node temperatures (relative 1e-12)
   const source=Object.values(run.document.couplings||{}).find(k=>k?.to===`${name}.temperature`),[from]=String(source?.from||'').split('.'),nodal=result.physics[from]?.temperature?.values;
   if(nodal)T.forEach((t,i)=>{const mean=(nodal[t[0]]+nodal[t[1]]+nodal[t[2]])/3,v=c.temperature.values[i];if(!(Math.abs(v-mean)<=1e-12*Math.abs(mean)))fail(`${r}'s coupled temperature is not the triangle mean of its node temperatures (triangle ${i}).`);});
  }
 }
}
// An effective-index series of unit 1: real {values} (points × modes), or complex {re, im} of the
// same shape under exp(-i omega t), as the engine writes a lossy result.
const indexRows=v=>Array.isArray(v)&&v.length>0&&v.every(row=>Array.isArray(row)&&row.length&&row.every(finite));
function indexSeries(s){
 if(!isObject(s)||s.unit!=='1')return false;
 if('values' in s)return !('re' in s)&&!('im' in s)&&indexRows(s.values);
 return indexRows(s.re)&&indexRows(s.im)&&s.re.length===s.im.length&&s.re.every((row,i)=>row.length===s.im[i].length)&&s.time_convention==='exp(-i omega t)';
}
function checkValues(r,result,run){
 for(const [name,p] of Object.entries(result.physics)){
  if(p.type==='thermal.steady2d'&&!(finite(p.range?.min)&&finite(p.range?.max)&&p.range.min<=p.range.max&&p.range.unit==='K'))fail(`${r}'s heat range is not well formed.`);
  if(p.type==='em.modes2d'&&!indexSeries(p.effective_index))fail(`${r}'s ${physicsLabel(name)} effective index is not well formed.`);
 }
 if(run.maps==='not kept'){const c=run.counts;if(!isObject(c)||!Number.isInteger(c.nodes)||c.nodes<1||!Number.isInteger(c.triangles)||c.triangles<1)fail(`${r} keeps no maps and no node and triangle counts.`);
  if('mesh' in result)fail(`${r} says its maps are not kept but holds a mesh.`);}
 else{if('counts' in run)fail(`${r} keeps its maps and also counts.`);checkArrays(r,result,run);}
}
// a quantity "1e-6 K" in K, for the loop tolerance
const KELVIN={K:1,mK:1e-3,uK:1e-6,'µK':1e-6};
function tolerance(value,unit){const m=/^\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)\s*(\S*)\s*$/.exec(String(value??''));if(!m)return NaN;const u=m[2]||unit;return u===unit?Number(m[1]):unit==='K'&&KELVIN[u]?Number(m[1])*KELVIN[u]:NaN;}
function checkStructure(r,result,doc){
 const physics=isObject(doc.physics)?doc.physics:{},names=Object.keys(physics);
 if(!isObject(result.physics)||Object.keys(result.physics).sort().join()!==[...names].sort().join()||names.some(n=>!isObject(result.physics[n])||result.physics[n].type!==physics[n]?.type))fail(`${r}'s result does not hold the physics of its model.`);
 const couplings=isObject(doc.couplings)?doc.couplings:{},records=isObject(result.couplings)?result.couplings:null;
 if(!records||Object.keys(records).sort().join()!==Object.keys(couplings).sort().join())fail(`${r}'s coupling records do not match its model's couplings.`);
 for(const [name,c] of Object.entries(couplings)){const k=records[name];
  if(!isObject(c)||!isObject(k))fail(`${r}'s coupling record ${name} does not match its model.`);
  if(k.from!==c.from||k.to!==c.to||k.transfer!==(c.transfer??'same_mesh'))fail(`${r}'s coupling record ${name} does not match its model.`);
  if(k.transfer==='same_mesh'&&(k.mesh_signature!=='match'||k.max_abs_difference?.value!==0))fail(`${r}'s coupling ${name} did not pass its same-mesh check.`);}
 const loops=Array.isArray(doc.study?.loops)?doc.study.loops:[],stored=result.loops;
 const set=l=>[...(l?.physics||[])].sort().join();
 if(!Array.isArray(stored)||!loops.every(isObject)||!stored.every(isObject)||stored.length!==loops.length||loops.some(l=>!stored.some(s=>set(s)===set(l))))fail(`${r}'s iteration steps do not match its model.`);
 for(const s of stored){
  // the tolerance is the model's (study.loops), not a value the result repeats
  const step=loops.find(l=>set(l)===set(s));const what=`${r}'s iteration step ${(s.physics||[]).map(physicsLabel).join(' ⇄ ')}`;
  if(s.converged!==true||!Number.isInteger(s.iterations)||s.iterations<1)fail(`${what} did not converge; a run that did not succeed cannot be in a session.`);
  if(!Array.isArray(s.residuals)||s.residuals.length!==s.iterations-1||!s.residuals.every(x=>finite(x?.value)))fail(`${what} has ${Array.isArray(s.residuals)?s.residuals.length:'no'} residuals for ${s.iterations} iterations.`);
  const last=s.residuals.at(-1),limit=tolerance(step.tolerance?.value,last?.unit);
  if(last&&!(last.value<=limit))fail(`${what} did not converge: its last change ${last.value} ${last.unit} is above the tolerance.`);}
 if(!Array.isArray(result.solve_order)||!result.solve_order.every(g=>Array.isArray(g)&&g.every(n=>names.includes(n))))fail(`${r}'s solve order is not well formed.`);
}
/** The local reading of a version 8 session object (§3.4 checks 1-7 that need no server): throws
 * a named message on the first failure. The documents still to check on the server are listed
 * in `documents` ({what, doc, run}). */
export function readMultiphysicsSession(doc,{recovered=false}={}){
 if(doc.application!=='multiphysics')fail(`This session file holds a “${typeof doc.application==='string'?doc.application:'unnamed'}” model, which this Studio does not read.`);
 documentSize(doc.document,'The session');
 if(typeof doc.document.openphysics!=='string')fail('The session model has no "openphysics" version.');
 // version 8 holds up to six runs, version 15 up to 20
 const limit=doc.version===RUNS_MULTIPHYSICS_VERSION?MULTIPHYSICS_RUN_LIMIT:PREVIOUS_MULTIPHYSICS_RUN_LIMIT;
 if(!Array.isArray(doc.runs)||doc.runs.length>limit)fail('Unsupported session format or run count.');
 const jobs=new Set(),numbers=new Set(),runs=[],documents=[{what:'The session model',doc:doc.document,current:true}];
 doc.runs.forEach((raw,i)=>{
  const r=runName(raw,i);
  if(!isObject(raw))fail(`${r} is not a run record.`);
  if(typeof raw.job!=='string'||!/^mp-[0-9a-f]{12}$/.test(raw.job))fail(`${r} has an invalid job identifier.`);
  if(jobs.has(raw.job))fail(`Two runs have the same job identifier ${raw.job}.`);jobs.add(raw.job);
  if(!Number.isInteger(raw.number)||raw.number<1)fail(`${r} has an invalid run number.`);
  if(numbers.has(raw.number))fail(`Two runs have the same number ${raw.number}.`);numbers.add(raw.number);
  if(typeof raw.label!=='string')fail(`${r} has an invalid name.`);let label;try{label=validateRunLabel(raw.label);}catch(e){fail(`${r}: ${e.message}`);}
  if(typeof raw.pinned!=='boolean')fail(`${r} has an invalid pin state.`);
  if(typeof raw.completedAt!=='string'||!Number.isFinite(Date.parse(raw.completedAt)))fail(`${r} has an invalid completion time.`);
  if(raw.serverVersion!==null&&(typeof raw.serverVersion!=='string'||!/^\d[0-9A-Za-z.+-]{0,63}$/.test(raw.serverVersion)))fail(`${r} has an invalid server version.`);
  documentSize(raw.document,r);
  if(!Array.isArray(raw.events)||!raw.events.every(e=>isObject(e)&&typeof e.event==='string'))fail(`${r}'s progress events are not well formed.`);
  if(!['kept','not kept'].includes(raw.maps))fail(`${r} does not say whether its maps are kept.`);
  if(!isObject(raw.result))fail(`${r} has no result.`);
  const multi=raw.document.openphysics===ENVELOPE,types=Object.values(isObject(raw.document.physics)?raw.document.physics:{}).map(p=>p?.type);
  // a document of another envelope is refused by the server's reader, named in the run (§3.3)
  const known=multi||raw.document.openphysics==='0.3',accepted=multi?[RESULT_FORMAT]:types.length===1?SINGLE_RESULT_FORMATS[types[0]]||[]:[];
  if(known&&!accepted.includes(raw.result.result))fail(`${r} was saved as result “${typeof raw.result.result==='string'?raw.result.result:'unnamed'}”, which this Studio does not read.`);
  // a record of an unexpected shape is refused by name, not with the engine's TypeError
  try{checkStructure(r,raw.result,raw.document);checkValues(r,raw.result,raw);}catch(e){if(e instanceof TypeError)fail(`${r} is not well formed.`);throw e;}
  if(typeof raw.digest!=='string'||raw.digest!==recordDigest(raw))fail(`${r} changed after it was saved (its check value does not match).`);
  documents.push({what:r,doc:raw.document,run:raw.job,order:raw.result.solve_order});
  runs.push({job:raw.job,number:raw.number,label,pinned:raw.pinned,completedAt:new Date(raw.completedAt).toISOString(),serverVersion:raw.serverVersion,doc:raw.document,events:raw.events,
   order:raw.result.solve_order,result:raw.result,maps:raw.maps,...(raw.maps==='not kept'?{counts:{nodes:raw.counts.nodes,triangles:raw.counts.triangles}}:{}),origin:recovered?'recovered':'imported'});
 });
 const baselines={};
 if(!isObject(doc.baselines))fail('The without-heater results are not well formed.');
 const tied=[doc.document,...runs.map(r=>r.doc)];
 for(const [name,raw] of Object.entries(doc.baselines)){
  const what=`The without-heater result of ${physicsLabel(name)}`;
  if(!isObject(raw)||typeof raw.job!=='string'||!/^mp-[0-9a-f]{12}$/.test(raw.job)||typeof raw.completedAt!=='string'||!Number.isFinite(Date.parse(raw.completedAt)))fail(`${what} is not well formed.`);
  documentSize(raw.document,what);
  if(raw.result?.type!=='em.modes2d'||!indexSeries(raw.result?.effective_index))fail(`${what} is not well formed.`);
  if(typeof raw.digest!=='string'||raw.digest!==recordDigest(raw))fail(`${what} changed after it was saved (its check value does not match).`);
  if(!baselineTied(name,raw,tied))fail(`${what} belongs to no run in this file and not to its model.`);
  baselines[name]={job:raw.job,completedAt:new Date(raw.completedAt).toISOString(),document:raw.document,result:raw.result};
  documents.push({what,doc:raw.document,baseline:name});
 }
 if(doc.selected!==null&&!jobs.has(doc.selected))fail('The selected run is not in the file.');
 const view=readMultiphysicsView(doc.view,doc.document,runs.find(r=>r.job===doc.selected)||null);
 return {application:'multiphysics',document:doc.document,runs,baselines,selected:doc.selected,view,documents};
}
/** §3.4.7: the view values the multiphysics view offers; selection names an item of the stored
 * document or of the selected run's result. */
export function readMultiphysicsView(view,document,run){
 const bad=()=>fail('The saved view is not one this Studio offers.');
 if(!isObject(view)||!VIEW_PAGES.includes(view.page)||!INDEX_MAPS.includes(view.index_map)||typeof view.baseline_option!=='boolean'||typeof view.selection!=='string')bad();
 const [kind,...rest]=view.selection.split(':'),id=rest.join(':');
 const plain=['model','geometry','materials','mesh','study','order','results'];
 const ok=plain.includes(view.selection)||(kind==='physics'&&own(document.physics,id))||(kind==='coupling'&&own(document.couplings,id))
  ||(kind==='material'&&materialUses(document).some(u=>u.ref===id))||(kind==='loop'&&/^\d+$/.test(id)&&Array.isArray(document.study?.loops)&&+id<document.study.loops.length)
  ||(kind==='results'&&!!run&&(id==='check'?Object.keys(run.result.couplings||{}).length>0:id==='runs'||own(run.result.physics,id)));
 if(!ok)bad();
 return {page:view.page,selection:view.selection,index_map:view.index_map,baseline_option:view.baseline_option};
}
/** The server checks of an opened session (§3.2): every run and baseline document passes the
 * check of simcase validate, runs a document Studio runs, and its result's solve order is the
 * server's for it; the current model is refused only when it is not readable. validate(doc)
 * resolves to the /api/multiphysics/validate reply. */
export async function checkSessionModels(session,validate){
 for(const item of session.documents){
  let reply;try{reply=await validate(item.doc);}catch(e){fail(`Studio's server must check the model before a session opens: ${e.message}`);}
  const errors=(reply.diagnostics||[]).filter(d=>d.severity==='error'||!d.severity);
  const first=errors[0],problem=first?`${first.path?first.path+': ':''}${first.message}`:'';
  if(item.current){const unreadable=errors.filter(d=>['E-JSON','E-KEY-DUPLICATE','E-FORMAT'].includes(d.code));
   if(unreadable.length)fail(`The session model is not readable: ${unreadable.map(d=>`${d.path?d.path+': ':''}${d.message}`).join('; ')}`);continue;}
  if(reply.ok!==true)fail(`${item.what}'s model does not pass today's check: ${problem||'it is not valid'}`);
  if(reply.run_refusal)fail(`${item.what}'s model is not one Studio runs: ${reply.run_refusal}`);
  if(item.order&&JSON.stringify(item.order)!==JSON.stringify(reply.solve_order))fail(`${item.what}'s solve order ${JSON.stringify(item.order)} is not the order of its model (${JSON.stringify(reply.solve_order)}).`);
 }
 return session;
}
/** A bare model file given to Open session: the model with no runs. */
export const isModelDocument=doc=>isObject(doc)&&typeof doc.openphysics==='string';

// ---- what the screens say ---------------------------------------------------------------------
/** The Open session question (§6), in the words of the optical one. */
export function multiphysicsLoadText(session,{runs=0,unsaved=false,model='the current model'}={},source='file'){
 const back=session.runs;
 return {title:source==='file'?'Open saved session?':'Recover saved session?',
  description:`Brings back ${back.length?`${plural(back.length,'run')} with ${back.length===1?'its name and pin':'their names and pins'}`:'no completed runs'}. Replaces ${model}${runs?` and ${plural(runs,'run')} in this tab`:''}; input undo starts at the opened session.`+(runs&&unsaved?' Save session first to keep the current runs.':''),
  button:source==='file'?'Open session':'Recover session',runs:back.length?back.map(multiphysicsRunName).join('; '):'None'};
}
/** The Save session notice (§6). */
// opticalRuns: the Optical waveguide runs this tab also holds; they are not in a multiphysics
// session file (File › Export › Model with runs), and the message says where they are kept: the
// project file of File › Save (P3).
// via: 'picker' (written to the file chosen in the browser's save dialog) or 'download'.
// known: Save downloaded under the model's current file name without asking (again: that name
// was downloaded before); after: the sentence that follows (a download cannot replace a file).
export function savedNotice(name,{runs,notKept=[],baseline=false,opticalRuns=0,via='download',known=false,again=false,after=''}){
 const one=opticalRuns===1;
 return `${via==='picker'?`Saved to ${name}`:known&&again?`Downloaded ${name} again`:`Session file ${name} sent to your browser's Downloads`}: the model, ${plural(runs,'run')}${baseline?' and the without-heater result':''}.`+(notKept.length?` ${plural(notKept.length,'run')} (${notKept.map(n=>'Run '+n).join(', ')}) ${notKept.length===1?'keeps':'keep'} values only, without maps.`:'')
  +(opticalRuns>0?` The ${one?'Optical waveguide run':opticalRuns+' Optical waveguide runs'} of this tab ${one?'is':'are'} not in this file; File › Save keeps ${one?'it':'them'} with this model in one project file.`:'')+after;
}
/** The session file name's prefix: the model name lowercased, every run of other characters
 * (digits too: the file names of sessions have letters and hyphens) one hyphen, at most 40
 * characters, else "multiphysics". */
export function modelSlug(name){const s=String(name||'').toLowerCase().replace(/[^a-z]+/g,'-').replace(/^-+|-+$/g,'').slice(0,40).replace(/-+$/,'');return /^[a-z][a-z-]*$/.test(s)?s:'multiphysics';}
