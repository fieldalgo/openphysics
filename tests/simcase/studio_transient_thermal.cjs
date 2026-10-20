// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Synthetic indexing fixtures; not PDE or browser acceptance.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const X=require('../../packages/simcase/simcase/studio/static/transient_thermal.js');
const copy=x=>JSON.parse(JSON.stringify(x));
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function cap(){return {capability_format:'studio-capabilities-v1',[X.TYPE]:{supported:true,run_enabled:true,
  input:'json',mesh_preview:false,mesh_from_result:true,time_navigation:true,
  validate:'/api/thermal/transient/validate',run:'/api/thermal/transient/run',
  result_formats:[X.RESULT],field_layouts:[X.LAYOUT],fields:X.UI,
  limits:{request_bytes:1048576,max_nodes:10201,max_triangles:20000,max_times:128,raw_bytes:16777216,
    manifest_bytes:4194304,frame_page_bytes:4194304,page_rows:16,terminal_bytes:33554432,
    terminal_jobs:2,active_jobs:1,read_encoding_slots:1}}};}
function doc(){return {openphysics:'0.2',units:{length:'m',temperature:'K',time:'s'},
  physics:{heat:{type:X.TYPE}},study:{type:'transient',time_s:[2,2.03,2.1,2.4,3]}};}
function manifest(Nt=5){const time_s=Nt===5?[2,2.03,2.1,2.4,3]:Array.from({length:Nt},(_,i)=>2+i/10);
  const n=4,m=2,d=0,shapes={nodes_m:[n,2],triangles:[m,3],time_s:[Nt],temperature_k:[Nt,n],heat_flux_w_m2:[Nt,m,2],
    source_load_w_per_m:[Nt,n],reaction_w_per_m:[Nt-1,n],residual_w_per_m:[Nt-1,n],storage_rate_w_per_m:[Nt-1,n],
    heat_content_j_per_m:[Nt],quadratic_functional_jk_per_m:[Nt],dirichlet_node_ids:[d],dirichlet_temperatures_k:[Nt,d]};
  const fields={},summary={physics_type:X.TYPE,result_format:X.RESULT,field_layout:X.LAYOUT,
    units:{length:'m',temperature:'K',time:'s'},mesh_length_unit:'m',mesh:{nodes:n,triangles:m},
    study:{type:'transient',time_s},field_units:{},field_shapes:{},field_locations:{},field_time_axes:{}};
  for(const [name,[unit,location,axis]]of Object.entries(X.SPEC)){
    fields[name]={shape:shapes[name],unit,location,axis,available_views:axis==='static'||name==='time_s'?[]:['frame','history'],
      initial_available:axis!=='time_s[1:]',ui_supported:X.UI.includes(name)};
    summary.field_units[name]=unit;summary.field_locations[name]=location;summary.field_shapes[name]=shapes[name];summary.field_time_axes[name]=axis;
  }
  const value={payload_format:'studio-thermal-transient-v1',kind:X.TYPE,job:'thermal-transient-test',result_id:'result-test',
    client_revision:1,request_seq:2,result_format:X.RESULT,field_layout:X.LAYOUT,display_length_in_m:1,
    default_frame_index:Nt-1,time_s,arrays:{nodes_m:[[0,0],[1,0],[1,1],[0,1]],triangles:[[0,1,2],[0,2,3]],dirichlet_node_ids:[]},summary,fields};
  value.frame_url='/api/jobs/'+value.job+'/frame?result_id='+value.result_id+'&field={field}&time_index={time_index}&frame_seq={frame_seq}';
  value.history_url='/api/jobs/'+value.job+'/history?result_id='+value.result_id+'&field={field}&start={start}&stop={stop}&frame_seq={frame_seq}';
  return value;
}
function frame(m,q){const vector=q.field==='heat_flux_w_m2';return {...identity(m),payload_format:'studio-thermal-transient-frame-v1',
  frame_seq:q.frame_seq,field:q.field,time_index:q.time_index,time_s:m.time_s[q.time_index],
  unit:vector?'W/m^2':'K',location:vector?'triangle_centroids':'nodes',shape:vector?[2,2]:[4],
  arrays:{[q.field]:vector?[[1000*q.time_index+1,-1000*q.time_index-2],[1000*q.time_index+11,-1000*q.time_index-12]]:
    Array.from({length:4},(_,n)=>100*q.time_index+n)}};}
function identity(m){const keys=['kind','job','result_id','client_revision','request_seq','result_format','field_layout','display_length_in_m'];
  return Object.fromEntries(keys.map(k=>[k,m[k]]));}
function history(m,q){return {...identity(m),payload_format:'studio-thermal-transient-history-v1',field:q.field,
  frame_seq:q.frame_seq,start:q.start,stop:q.stop,time_indices:Array.from({length:q.stop-q.start},(_,i)=>q.start+i),
  time_s:m.time_s.slice(q.start,q.stop),shape:[q.stop-q.start],unit:m.fields[q.field].unit,location:'domain',
  arrays:{[q.field]:Array.from({length:q.stop-q.start},(_,i)=>q.start+i+10)}};}
function boot({deferReads=false}={}) {
  const reads=[],states=[];let current,runs=0,active=0,maxActive=0;
  const c=X.createController({wait:async()=>{},onState:s=>states.push(s),request:async(method,url,body)=>{
    if(url==='/api/capabilities')return cap();
    if(url.endsWith('/validate'))return {ok:true,doc:body.doc,client_revision:body.client_revision,request_seq:body.request_seq};
    if(url.endsWith('/run')){runs++;current=manifest();current.client_revision=body.client_revision;current.request_seq=body.request_seq;return identity(current);}
    if(url.endsWith('/result'))return copy(current);
    if(!url.includes('?'))return {...identity(current),status:'done'};
    const parsed=new URL(url,'http://test'),q=Object.fromEntries(parsed.searchParams);for(const k of ['time_index','frame_seq','start','stop'])if(k in q)q[k]=Number(q[k]);
    active++;maxActive=Math.max(maxActive,active);
    const result=parsed.pathname.endsWith('/frame')?frame(current,q):history(current,q);
    if(!deferReads){active--;return result;}
    return new Promise((resolve,reject)=>reads.push({q,resolve:v=>{active--;resolve(v===undefined?result:v);},reject:e=>{active--;reject(e);}}));
  }});
  return {c,reads,states,runs:()=>runs,maxActive:()=>maxActive};
}
test('typed manifest preserves nonzero/nonuniform exact catalog and final default',()=>{
  const m=manifest(),accepted=X.manifest(m,m,cap()[X.TYPE].limits);
  assert.equal(accepted.default_frame_index,4);assert.deepEqual(accepted.time_s,[2,2.03,2.1,2.4,3]);
  assert.deepEqual(accepted.fields.reaction_w_per_m.shape,[4,4]);assert.equal(accepted.fields.reaction_w_per_m.initial_available,false);
});
for(const actor of ['times','default','descriptor','summary','ccw','bool','D','scale','nonfinite'])
test('manifest refuses '+actor,()=>{const m=manifest();if(actor==='times')m.time_s[1]=2;if(actor==='default')m.default_frame_index=0;
  if(actor==='descriptor')m.fields.heat_flux_w_m2.location='nodes';if(actor==='summary')m.summary.field_units.temperature_k='C';
  if(actor==='ccw')m.arrays.triangles[0]=[0,2,1];if(actor==='bool')m.arrays.nodes_m[0][0]=true;
  if(actor==='D')m.arrays.dirichlet_node_ids=[1,1];if(actor==='scale')m.display_length_in_m=0;
  if(actor==='nonfinite')m.summary.temperature_min_k=[Infinity];assert.throws(()=>X.manifest(m,m,cap()[X.TYPE].limits));});
test('same-origin templates bind job/result and exact placeholders',()=>{
  const m=manifest();assert.match(X.queryURL(m,'frame',{field:'temperature_k',time_index:4,frame_seq:2}),/result_id=result-test/);
  for(const bad of ['https://evil.test/a','//evil.test/a','/api/jobs/thermal-transient-test/../frame?x=1',
    m.frame_url+'&frame_seq={frame_seq}',m.frame_url.replace('result-test','other'),m.frame_url+'#x',
    m.frame_url.replace('{time_index}','0')])assert.throws(()=>X.template(bad,m,'frame'));
});
test('frame exact index/axis/row, signed K and distinct cell vectors',()=>{
  const m=manifest(),q={field:'temperature_k',time_index:4,frame_seq:3},f=X.frame(frame(m,q),m,q);
  assert.equal(f.arrays.temperature_k[3],403);assert.equal(f.time_s,3);
  const fq={field:'heat_flux_w_m2',time_index:2,frame_seq:4},v=X.frame(frame(m,fq),m,fq);
  assert.deepEqual(v.arrays.heat_flux_w_m2[1],[2011,-2012]);
  const man=X.manifest(m,m,cap()[X.TYPE].limits);assert.equal(X.model(man,v,'qy').values[1],-2012);
  f.arrays.temperature_k.fill(-10);assert.equal(X.model(man,f,'temperature_k').min,-10);
  const wrong=frame(m,q);wrong.time_s=2.4;assert.throws(()=>X.frame(wrong,m,q));
});
test('H/V half-open pages, Nt17 final partial and wrong indices',()=>{
  const m=manifest(17),q={field:'heat_content_j_per_m',start:16,stop:17,frame_seq:3};
  assert.deepEqual(X.history(history(m,q),m,q).time_indices,[16]);
  assert.throws(()=>X.history(history(m,{...q,start:0}),m,{...q,start:0}));
  const v=history(m,q);v.time_indices=[15];assert.throws(()=>X.history(v,m,q));
  assert.equal(history(m,{...q,field:'quadratic_functional_jk_per_m'}).unit,'J K/m');
});
test('capability refuses absent/false/invalid configuration',()=>{
  assert.ok(X.capability(cap()));const c=cap();c[X.TYPE].supported=false;assert.equal(X.capability(c),null);
  c[X.TYPE].supported=true;c[X.TYPE].limits.page_rows=17;assert.equal(X.capability(c),null);
});
test('default last frame only, no automatic H/V page or additional solve',async()=>{
  const {c,reads,runs}=boot({deferReads:true});await c.loadCapability();await c.validate(doc());await c.run();
  assert.equal(reads.length,1);assert.equal(reads[0].q.time_index,4);reads[0].resolve();await tick();
  assert.equal(c.state().frame.arrays.temperature_k[3],403);assert.deepEqual(c.state().pages,{});assert.equal(runs(),1);
});
test('one read active, coalesced explicit index and stale success/finally cannot install',async()=>{
  const {c,reads,maxActive}=boot({deferReads:true});await c.loadCapability();await c.validate(doc());await c.run();
  c.select(1,'qx');c.select(2,'qy');assert.equal(reads.length,1);assert.equal(c.state().frame,null);
  reads[0].resolve();await tick();assert.equal(reads.length,2);assert.equal(reads[1].q.time_index,2);
  assert.equal(c.state().frame,null);reads[1].resolve();await tick();
  assert.equal(c.state().frame.time_index,2);assert.equal(c.state().view,'qy');assert.equal(maxActive(),1);
});
test('stale error cannot replace newer view; current429 has no retry or solve',async()=>{
  const {c,reads,runs}=boot({deferReads:true});await c.loadCapability();await c.validate(doc());await c.run();
  c.select(0);reads[0].reject(Error('old429'));await tick();assert.equal(c.state().error,null);
  reads[1].reject(Error('HTTP429 read busy'));await tick();assert.match(c.state().error,/429/);
  assert.ok(c.result());assert.equal(reads.length,2);assert.equal(runs(),1);
});
test('dirty invalidation ignores pending reads and prevents prior snapshot run',async()=>{
  const {c,reads,runs}=boot({deferReads:true});await c.loadCapability();await c.validate(doc());await c.run();
  c.invalidate();reads[0].resolve();await tick();assert.equal(c.result(),null);assert.equal(c.state().frame,null);
  assert.equal(c.snapshot(),null);assert.equal(await c.run(),false);assert.equal(runs(),1);
});
test('history explicit only and globally serialized with frame, no automatic next page',async()=>{
  const {c,reads,maxActive}=boot({deferReads:true});await c.loadCapability();await c.validate(doc());await c.run();
  assert.equal(c.loadHistory('heat_content_j_per_m',0,5),false);reads[0].resolve();await tick();
  assert.equal(c.loadHistory('heat_content_j_per_m',0,5),true);
  assert.equal(c.loadHistory('quadratic_functional_jk_per_m',0,5),false);
  reads[1].resolve();await tick();assert.ok(c.state().pages.heat_content_j_per_m);
  assert.equal(reads.length,2);assert.equal(maxActive(),1);
});
test('duplicates and validation200 okfalse never approve, run400 never installs',async()=>{
  let mode='duplicate',runs=0;const c=X.createController({request:async(method,url,body)=>{
    if(url==='/api/capabilities')return cap();if(url.endsWith('/validate'))return mode==='invalid'?{ok:false,error:{message:'invalid'}}:
      {ok:true,doc:body.doc,client_revision:body.client_revision,request_seq:body.request_seq};
    runs++;throw Error('HTTP400 run refused');
  }});
  await c.loadCapability();assert.equal(await c.validate(doc(),'{"physics":{"a":1,"a":2}}'),false);
  mode='invalid';assert.equal(await c.validate(doc()),false);assert.equal(await c.run(),false);assert.equal(runs,0);
  mode='valid';await c.validate(doc());assert.equal(await c.run(),false);assert.equal(c.result(),null);assert.equal(c.state().busy,false);
});
test('same revision old validation error/finally and reversed capability replies are ignored',async()=>{
  const pending=[];let capabilityCalls=0;const c=X.createController({request:(method,url,body)=>{
    if(url==='/api/capabilities'){capabilityCalls++;return Promise.resolve(cap());}
    return new Promise((resolve,reject)=>pending.push({body,resolve,reject}));}});
  await c.loadCapability();const old=c.validate(doc()),newer=c.validate(doc());
  pending[1].resolve({ok:true,doc:doc(),client_revision:pending[1].body.client_revision,request_seq:pending[1].body.request_seq});await newer;
  pending[0].reject(Error('old'));await old;assert.equal(c.state().error,null);assert.ok(c.snapshot());assert.equal(c.state().busy,false);
  const caps=[];const d=X.createController({request:()=>new Promise(resolve=>caps.push(resolve))});
  const a=d.loadCapability(),b=d.loadCapability();caps[1]({});await b;caps[0](cap());await a;assert.equal(d.supports(doc()),false);
});

const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const staticRoot=path.join(__dirname,'../../packages/simcase/simcase/studio/static');
const html=fs.readFileSync(path.join(staticRoot,'index.html'),'utf8');
function page(){
  const elements=new Map(),requests=[];let activeTab='geometry';
  const names=['geometry','mesh','results','json'];
  const tabs=names.map(tab=>({dataset:{tab},classList:{toggle(){}},onclick:null}));
  const panels=names.map(name=>({id:'tab-'+name,classList:{toggle(cls,on){if(on)activeTab=name;}}}));
  function element(id){
    if(!elements.has(id)){
      const calls=[],ctx=new Proxy({createImageData:(w,h)=>({data:new Uint8ClampedArray(w*h*4)}),
        clearRect:()=>calls.push('clear'),putImageData:()=>calls.push('pixels'),
        moveTo:()=>calls.push('path'),fillText:text=>calls.push(['text',text])},{get:(o,k)=>o[k]||(()=>{})});
      elements.set(id,{width:320,height:240,calls,value:'',hidden:false,textContent:'',innerHTML:'',children:[],
        appendChild(x){this.children.push(x);},getContext:()=>ctx,click(){return this.onclick?.();},
        getBoundingClientRect(){
          const tab=id==='meshCanvas'?'mesh':id==='geoCanvas'?'geometry':'results';
          const on=!id.endsWith('Canvas')||activeTab===tab;return {width:on?320:0,height:on?240:0,left:0,top:0};
        }});
    }return elements.get(id);
  }
  const child=()=>({textContent:'',children:[],appendChild(x){this.children.push(x);},click(){return this.onclick?.();}});
  const context=vm.createContext({document:{getElementById:element,createElement:child,
    querySelectorAll:s=>s==='.view > div'?panels:s==='.tabs button'?tabs:[]},window:{devicePixelRatio:1,addEventListener(){}},
    console,URL,URLSearchParams,Blob,Uint8ClampedArray,setTimeout:cb=>cb(),
    fetch:(...args)=>{requests.push(args);return new Promise(()=>{});}});
  for(const script of ['thermal.js','transient_thermal.js'])vm.runInContext(fs.readFileSync(path.join(staticRoot,script),'utf8'),context);
  vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1],context);
  return {element,requests,context,run:code=>vm.runInContext(code,context),tab:name=>tabs.find(b=>b.dataset.tab===name).onclick()};
}
function installAPI(p,{rejectValidation=false,rejectRun=false,held=false}={}) {
  // All generated source is parsed by the same VM before invoking handlers.
  p.run('globalThis.fixtureManifest='+JSON.stringify(manifest())+';globalThis.fixtureCap='+JSON.stringify(cap())+
    ';globalThis.apiCalls=[];globalThis.held=[];'+
    'globalThis.fetch=async(url,options)=>{apiCalls.push(url);'+
    'if(url==="/api/capabilities")return {ok:true,json:async()=>fixtureCap};'+
    'if(url.endsWith("/validate")){const e=JSON.parse(options.body);return {ok:true,status:200,json:async()=>('+
      (rejectValidation?'{ok:false,error:{message:"invalid fixture"}}':'{ok:true,doc:e.doc,client_revision:e.client_revision,request_seq:e.request_seq}')+')};}'+
    'if(url.endsWith("/run")){const e=JSON.parse(options.body);fixtureManifest.client_revision=e.client_revision;fixtureManifest.request_seq=e.request_seq;'+
      (rejectRun?'return {ok:false,status:400,json:async()=>({error:{message:"run rejected fixture"}})};':
        'return {ok:true,json:async()=>({kind:fixtureManifest.kind,job:fixtureManifest.job,result_id:fixtureManifest.result_id,client_revision:e.client_revision,request_seq:e.request_seq})};')+'}'+
    'if(url.endsWith("/result"))return {ok:true,json:async()=>fixtureManifest};'+
    'if(!url.includes("?"))return {ok:true,json:async()=>({...fixtureManifest,status:"done"})};'+
    'const u=new URL(url,"http://test"),q=Object.fromEntries(u.searchParams);'+
    'const i=Number(q.time_index),start=Number(q.start),stop=Number(q.stop),f=q.field;'+
    'const vector=f==="heat_flux_w_m2";const result={kind:fixtureManifest.kind,job:fixtureManifest.job,result_id:fixtureManifest.result_id,'+
      'client_revision:fixtureManifest.client_revision,request_seq:fixtureManifest.request_seq,result_format:fixtureManifest.result_format,'+
      'field_layout:fixtureManifest.field_layout,display_length_in_m:1,frame_seq:Number(q.frame_seq),field:f,unit:fixtureManifest.fields[f].unit,location:fixtureManifest.fields[f].location};'+
    'if(u.pathname.endsWith("/frame"))Object.assign(result,{payload_format:"studio-thermal-transient-frame-v1",time_index:i,time_s:fixtureManifest.time_s[i],'+
      'shape:vector?[2,2]:[4],arrays:{[f]:vector?[[1000*i+1,-1000*i-2],[1000*i+11,-1000*i-12]]:[100*i,100*i+1,100*i+2,100*i+3]}});'+
    'else Object.assign(result,{payload_format:"studio-thermal-transient-history-v1",start,stop,time_indices:Array.from({length:stop-start},(_,j)=>start+j),'+
      'time_s:fixtureManifest.time_s.slice(start,stop),shape:[stop-start],arrays:{[f]:Array.from({length:stop-start},(_,j)=>10+start+j)}});'+
    (held?'return new Promise((resolve,reject)=>held.push(error=>error?reject(Error(error)):resolve({ok:true,json:async()=>result})));':
      'return {ok:true,json:async()=>result};')+'};');
}
async function readyPage(options){
  const p=page();installAPI(p,options);await p.run('transientController.loadCapability()');
  p.element('json').value=JSON.stringify(doc());p.element('json').oninput();await p.element('applyJson').onclick();return p;
}
test('shipped transient page runs default exact last frame, explicit H/V pages and actual tabs',async()=>{
  const p=await readyPage();assert.equal(p.element('runBtn').disabled,false);
  await p.element('runBtn').onclick();await tick();
  assert.equal(p.element('transientTime').value,4);assert.match(p.element('resInfo').textContent,/index 4; t = 3 s/);
  assert.match(p.element('resInfo').textContent,/raw 400 … 403/);assert.ok(p.element('fieldCanvas').calls.includes('pixels'));
  assert.equal(p.element('meshCanvas').getBoundingClientRect().width,0);
  assert.equal(p.run('apiCalls.some(u=>u.includes("/history?"))'),false);
  p.element('thermalField').value='qy';p.element('thermalField').onchange();await tick();
  assert.match(p.element('resInfo').textContent,/qy.*-4012 … -4002/);
  p.tab('mesh');await tick();assert.equal(p.element('fieldCanvas').getBoundingClientRect().width,0);
  assert.match(p.element('meshInfo').textContent,/Actual transient result mesh/);
  p.tab('results');await tick();assert.match(p.element('resInfo').textContent,/qy/);
  p.element('transientPageStart').value='1';p.element('transientReadH').onclick();await tick();
  assert.ok(p.element('transientH').children.some(x=>/H heat content.*J\/m/.test(x.textContent)));
  p.element('transientReadV').onclick();await tick();
  assert.ok(p.element('transientV').children.some(x=>/not stored heat.*J K\/m/.test(x.textContent)));
});
test('shipped dirty transient JSON clears controller/hover/labels and pending render cannot restore',async()=>{
  const p=await readyPage();await p.element('runBtn').onclick();await tick();
  p.element('thermalField').value='magnitude';p.element('thermalField').onchange();
  p.element('json').value='{';p.element('json').oninput();await tick();
  assert.equal(p.run('transientController.result()'),null);assert.equal(p.element('fieldCanvas').onmousemove,null);
  assert.equal(p.element('runBtn').disabled,true);assert.equal(p.element('transientControls').hidden,true);
  assert.equal(p.element('meshInfo').textContent,'');assert.equal(p.element('meshLegend').textContent,'');
  p.tab('results');await tick();assert.equal(p.run('transientController.state().frame'),null);
});
test('shipped transient original duplicate raw keys never approve or run',async()=>{
  const p=await readyPage();p.element('json').value=JSON.stringify(doc()).replace('"openphysics":"0.2"','"openphysics":"0.2","openphysics":"0.2"');
  p.element('json').oninput();await p.element('applyJson').onclick();
  assert.equal(p.element('runBtn').disabled,true);assert.match(p.element('status').textContent,/duplicate/);
  await p.element('runBtn').onclick();assert.equal(p.run('apiCalls.filter(u=>u.endsWith("/run")).length'),0);
});
test('shipped transient validation200 false and run400 remain distinct failures',async()=>{
  const invalid=await readyPage({rejectValidation:true});assert.equal(invalid.element('runBtn').disabled,true);
  assert.match(invalid.element('status').textContent,/invalid fixture/);
  const badRun=await readyPage({rejectRun:true});await badRun.element('runBtn').onclick();
  assert.equal(badRun.run('transientController.result()'),null);assert.match(badRun.element('status').textContent,/run rejected/);
});
test('shipped serialized latest selection, hidden tabs, stale callbacks and dirty during held fetch',async()=>{
  const p=await readyPage({held:true});await p.element('runBtn').onclick();await tick();
  assert.equal(p.run('held.length'),1);
  p.element('transientTime').value='1';p.element('transientTime').onchange();
  p.element('transientTime').value='2';p.element('transientTime').onchange();
  p.run('held[0]()');await tick();assert.equal(p.run('held.length'),2);
  assert.equal(p.run('transientController.state().frame'),null);
  p.run('held[1]()');await tick();assert.match(p.element('resInfo').textContent,/index 2; t = 2.1 s/);
  p.tab('mesh');p.element('thermalField').value='qx';p.element('thermalField').onchange();
  p.element('json').value='{';p.element('json').oninput();p.run('held[2]()');await tick();
  p.tab('results');await tick();assert.equal(p.run('transientController.result()'),null);
  assert.equal(p.element('fieldCanvas').onmousemove,null);assert.equal(p.element('runBtn').disabled,true);
});



test('manifest rejects illustrative comments and abbreviated public summaries',()=>{
  const m=manifest();m.fixture_summary_note='not production';assert.throws(()=>X.manifest(m,m,cap()[X.TYPE].limits));
  delete m.fixture_summary_note;m.summary={physics_type:X.TYPE,result_format:X.RESULT,field_layout:X.LAYOUT};
  assert.throws(()=>X.manifest(m,m,cap()[X.TYPE].limits));
});
test('nearby saved times never select by rounded text or accept bool/string/fractional indices',async()=>{
  const m=manifest();m.time_s=[2,2+1e-12,2.1,2.4,3];m.summary.study.time_s=m.time_s;
  const valid=X.manifest(m,m,cap()[X.TYPE].limits),q={field:'temperature_k',time_index:1,frame_seq:1};
  assert.equal(X.frame(frame(valid,q),valid,q).time_s,2+1e-12);
  const b=boot();await b.c.loadCapability();await b.c.validate(doc());await b.c.run();await tick();
  for(const i of [true,'1',.5,-1,5])assert.throws(()=>b.c.select(i));
});
test('shipped current magnitude overflow clears field only and newer temperature restores exact label/hover',async()=>{
  const p=await readyPage();
  p.run('const normalFetch=fetch;globalThis.fetch=async(...args)=>{const response=await normalFetch(...args);return {...response,json:async()=>{const value=await response.json();'
    +'if(value.payload_format==="studio-thermal-transient-frame-v1"&&value.field==="heat_flux_w_m2")value.arrays.heat_flux_w_m2=[[Number.MAX_VALUE,Number.MAX_VALUE],[1,0]];return value;}};};');
  await p.element('runBtn').onclick();await tick();
  p.element('transientReadH').onclick();await tick();
  const marker=()=>p.element('transientH').children.at(-1).children.some(row=>row.children[0].children[0].textContent.includes('(current frame)'));
  assert.equal(marker(),true);
  p.element('thermalField').value='magnitude';p.element('thermalField').onchange();await tick();
  assert.match(p.element('resInfo').textContent,/derived field magnitude overflow/);assert.equal(p.element('fieldCanvas').onmousemove,null);
  assert.equal(p.run('transientController.state().frame'),null);
  assert.doesNotMatch(p.element('status').textContent,/frame ready/);
  assert.equal(marker(),false);
  assert.ok(p.run('transientController.result()'));p.tab('mesh');await tick();assert.match(p.element('meshInfo').textContent,/Actual transient result mesh/);
  p.element('thermalField').value='temperature_k';p.element('thermalField').onchange();p.tab('results');await tick();
  assert.match(p.element('resInfo').textContent,/index 4.*raw 400 … 403/);
  assert.equal(typeof p.element('fieldCanvas').onmousemove,'function');
  assert.equal(marker(),true);
});
test('refresh preserves an accepted transient view rather than clearing panels through steady fallback',async()=>{
  const p=await readyPage();await p.element('runBtn').onclick();await tick();p.run('refresh()');await tick();
  assert.equal(p.element('transientControls').hidden,false);assert.equal(p.element('transientHistory').hidden,false);
  assert.match(p.element('resInfo').textContent,/index 4/);
});

test('controller rejects only current render frame and stale render error cannot clear newer frame',async()=>{
  const {c}=boot();await c.loadCapability();await c.validate(doc());await c.run();await tick();
  const old=c.renderToken();c.select(2);await tick();const current=c.renderToken(),before=c.state().frame;
  assert.equal(c.rejectView(old,'old render error'),false);assert.equal(c.state().frame,before);
  assert.equal(c.rejectView(current,'current canvas failure'),true);
  assert.equal(c.state().frame,null);assert.ok(c.result());assert.match(c.state().error,/current canvas failure/);
});
test('shipped canvas failure rejects accepted frame and clears history current markers',async()=>{
  const p=await readyPage();await p.element('runBtn').onclick();await tick();
  p.element('transientReadH').onclick();await tick();
  p.run('const drawBeforeFailure=ThermalStudio.draw;ThermalStudio.draw=(canvas,model,options)=>{'
    +'if(canvas===document.getElementById("fieldCanvas"))throw Error("injected current canvas failure");'
    +'return drawBeforeFailure(canvas,model,options);};drawTransientViews();');
  await tick();assert.equal(p.run('transientController.state().frame'),null);
  assert.ok(p.run('transientController.result()'));assert.equal(p.element('fieldCanvas').onmousemove,null);
  const table=p.element('transientH').children.at(-1);
  assert.equal(table.children.some(row=>row.children[0].children[0].textContent.includes('(current frame)')),false);
  assert.match(p.element('status').textContent,/canvas failure/);
});
test('shipped mesh display overflow clears stale field and mesh rather than falling outside rejection',async()=>{
  const p=await readyPage();p.run('fixtureManifest.display_length_in_m=Number.MIN_VALUE;'
    +'const fetchBeforeScale=fetch;globalThis.fetch=async(...args)=>{const response=await fetchBeforeScale(...args);'
    +'return {...response,json:async()=>{const value=await response.json();if(value.payload_format==="studio-thermal-transient-frame-v1")value.display_length_in_m=Number.MIN_VALUE;return value;}};};');
  await p.element('runBtn').onclick();await tick();
  const fieldClears=p.element('fieldCanvas').calls.filter(x=>x==='clear').length;
  const meshClears=p.element('meshCanvas').calls.filter(x=>x==='clear').length;
  p.tab('mesh');await tick();
  assert.equal(p.run('transientController.state().frame'),null);assert.ok(p.run('transientController.result()'));
  assert.ok(p.element('fieldCanvas').calls.filter(x=>x==='clear').length>fieldClears);
  assert.ok(p.element('meshCanvas').calls.filter(x=>x==='clear').length>meshClears);
  assert.match(p.element('meshInfo').textContent,/Mesh view error.*overflow/);
  assert.equal(p.element('fieldCanvas').onmousemove,null);
});

for(const outcome of ['success','error'])test('shipped dirty status overrides obsolete physical read '+outcome,async()=>{
  const p=await readyPage({held:true});await p.element('runBtn').onclick();await tick();
  assert.equal(p.run('transientController.state().readActive'),true);
  assert.match(p.element('status').textContent,/reading saved transient data/);
  p.element('json').value='{';p.element('json').oninput();
  const dirtyStatus=p.element('status').textContent;
  assert.equal(dirtyStatus,'validate current transient JSON');
  assert.equal(p.run('transientController.state().readActive'),true);
  p.run(outcome==='success'?'held[0]()':'held[0]("obsolete read error")');await tick();
  assert.equal(p.run('transientController.state().readActive'),false);
  assert.equal(p.element('status').textContent,dirtyStatus);
  assert.equal(p.run('transientController.result()'),null);
  assert.equal(p.element('fieldCanvas').onmousemove,null);
  assert.equal(p.element('transientControls').hidden,true);
  assert.equal(p.element('runBtn').disabled,true);
});
