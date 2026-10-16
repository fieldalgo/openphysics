// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Synthetic indexing fixtures; not PDE or browser acceptance.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const X=require('../simcase/studio/static/transient_thermal.js');
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
module.exports={cap,doc,manifest,frame,history};
