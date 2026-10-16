// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Shipped module AND actual page handlers. Node VM is not an actual browser.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {test}=require('node:test');
const script=fs.readFileSync(path.join(__dirname,'../simcase/studio/static/thermal.js'),'utf8');
const html=fs.readFileSync(path.join(__dirname,'../simcase/studio/static/index.html'),'utf8');
const T=require('../simcase/studio/static/thermal.js');
const copy=x=>JSON.parse(JSON.stringify(x));
const tick=()=>new Promise(r=>setImmediate(r));
function cap(){return {capability_format:'studio-capabilities-v1','thermal.steady2d':{
  supported:true,run_enabled:true,validate:'/api/thermal/validate',run:'/api/thermal/run',input:'json',mesh_preview:false,
  mesh_from_result:true,time_navigation:false,result_formats:Object.keys(T.PAIRS),
  field_layouts:Object.values(T.PAIRS),fields:['temperature_k','heat_flux_w_m2'],
  limits:{request_bytes:1048576,max_nodes:10201,max_triangles:20000,payload_bytes:16777216,active_jobs:1,terminal_jobs:2,terminal_bytes:33554432,ttl_seconds:300,log_bytes:65536,error_bytes:4096,metadata_bytes:65536,status_bytes:131072}}};}
function doc(){return {openphysics:'0.2',name:'Heat',units:{length:'m',temperature:'K'},
  geometry:{domain:{xmin:0,xmax:1,ymin:0,ymax:1}},physics:{heat1:{type:T.TYPE}},
  mesh:{subdivisions:[1,1]},study:{type:'single'}};}
function payload({v2=true,D=0,revision=0,sequence=1}={}){
  const arrays={nodes_m:[[0,0],[1,0],[1,1],[0,1]],triangles:[[0,1,2],[0,2,3]],
    temperature_k:[0,1,2,3],heat_flux_w_m2:[[2,0],[0,-4]],load_w_per_m:[0,0,0,0],
    reaction_w_per_m:[0,0,0,0],residual_w_per_m:[0,0,0,0],
    dirichlet_node_ids:Array.from({length:D},(_,i)=>i),dirichlet_temperature_k:Array(D).fill(300)};
  if(v2)T.ADDED.forEach(k=>arrays[k]=[0,0,0,0]);
  const result_format='thermal.steady2d-result-v'+(v2?2:1),field_layout=T.PAIRS[result_format];
  const spec={...T.BASE};if(v2)T.ADDED.forEach(k=>spec[k]=['W/m','nodes',0]);
  const summary={physics_type:T.TYPE,result_format,field_layout,units:{length:'m',temperature:'K'},
    mesh_length_unit:'m',mesh:{nodes:4,triangles:2},field_units:{},field_locations:{},field_shapes:{}};
  for(const[k,[unit,location,cols]]of Object.entries(spec)){
    summary.field_units[k]=unit;summary.field_locations[k]=location;
    summary.field_shapes[k]=cols?[arrays[k].length,cols]:[arrays[k].length];
  }
  return {payload_format:'studio-thermal-steady-v1',kind:T.TYPE,job:'job1',result_id:'res1',
    client_revision:revision,request_seq:sequence,result_format,field_layout,summary,arrays,coordinates:{raw_unit:'m',display_unit:'m',display_length_in_m:1}};
}
function canvas(W=200,H=160){
  const calls=[],ctx=new Proxy({createImageData:(w,h)=>({width:w,height:h,data:new Uint8ClampedArray(w*h*4)}),
    putImageData:image=>calls.push(['pixels',image]),moveTo:(...v)=>calls.push(['move',...v]),
    lineTo:(...v)=>calls.push(['line',...v]),fillText:(...v)=>calls.push(['text',...v])},
    {get:(o,k)=>o[k]||(()=>{})});
  return {width:W,height:H,calls,getContext:()=>ctx,getBoundingClientRect:()=>({width:W,height:H,left:0,top:0})};
}
function page({visibility=false}={}){
  const elements=new Map(),requests=[];let activeTab='geometry';
  const panels=['geometry','mesh','results','json'].map(name=>({id:'tab-'+name,classList:{toggle(cls,on){if(on)activeTab=name;}}}));
  function element(id){if(!elements.has(id))elements.set(id,Object.assign(canvas(320,240),{
    value:'',hidden:false,innerHTML:'',textContent:'',children:[],appendChild(x){this.children.push(x);},
    querySelectorAll:()=>[],click(){if(this.onclick)return this.onclick();}}));
    const value=elements.get(id);
    if(visibility&&['fieldCanvas','meshCanvas','sweepCanvas','geoCanvas'].includes(id))value.getBoundingClientRect=()=>{
      const tab=id==='meshCanvas'?'mesh':id==='geoCanvas'?'geometry':'results';
      return {width:activeTab===tab?320:0,height:activeTab===tab?240:0,left:0,top:0};};
    return value;}
  const context=vm.createContext({document:{getElementById:element,querySelectorAll:selector=>selector==='.view > div'?panels:[],
    createElement:()=>({click(){}})},window:{addEventListener(){},devicePixelRatio:1},
    Uint8ClampedArray,console,URL:{createObjectURL:()=>''},Blob:function(){},
    setTimeout:cb=>cb(),fetch:(...args)=>{requests.push(args);return new Promise(()=>{});}});
  vm.runInContext(script,context);
  vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1],context);
  return {element,requests,run:code=>vm.runInContext(code,context)};
}
test('strict raw parser rejects nested, escaped duplicate keys and overflow',()=>{
  for(const raw of ['{"a":1,"a":2}','{"a":{"b":1,"b":2}}','{"a":1,"\\u0061":2}','{"a":1e999}'])
    assert.throws(()=>T.strictParse(raw));
  assert.deepEqual(T.strictParse(' \n{"a":[1,true,null,"\\\\"]}'),{a:[1,true,null,'\\']});
});
test('v1/v2 exact physical arrays, paired IDs and Robin-only D0',()=>{
  assert.equal(T.validatePayload(payload()).arrays.dirichlet_node_ids.length,0);
  assert.equal(Object.keys(T.validatePayload(payload({v2:false,D:1})).arrays).length,9);
  assert.throws(()=>T.validatePayload(payload({v2:false,D:0})));
});
for(const mutation of ['pair','units','shape','bool','nonfinite','connectivity','ccw','missing','extra','owner','display'])
test('malformed payload refuses '+mutation,()=>{
  const p=payload();
  if(mutation==='pair')p.field_layout=T.PAIRS['thermal.steady2d-result-v1'];
  if(mutation==='units')p.summary.field_units.temperature_k='relative';
  if(mutation==='shape')p.arrays.temperature_k=[1,2];
  if(mutation==='bool')p.arrays.temperature_k[0]=true;
  if(mutation==='nonfinite')p.arrays.heat_flux_w_m2[0][0]=Infinity;
  if(mutation==='connectivity')p.arrays.triangles[0][0]=.5;
  if(mutation==='ccw')p.arrays.triangles[0].reverse();
  if(mutation==='missing')delete p.arrays.ambient_load_w_per_m;
  if(mutation==='extra')p.arrays.neff=[1];
  if(mutation==='owner')p.job='other';
  if(mutation==='display')p.coordinates.display_length_in_m=0;
  assert.throws(()=>T.validatePayload(p,{job:'job1',result_id:'res1',client_revision:0,request_seq:1}));
});
test('nodal P1 interpolation differs from flat-cell flux, no nodal averaging',()=>{
  const p=T.validatePayload(payload()),m=T.viewModel(p);
  assert.equal(T.sample(m,[.75,.25]),1);assert.equal(T.sample(m,[.25,.75]),2);
  assert.equal(T.sample(T.viewModel(p,'qx'),[.75,.25]),2);
  assert.equal(T.sample(T.viewModel(p,'qx'),[.25,.75]),0);
  assert.equal(T.sample(T.viewModel(p,'qy'),[.25,.75]),-4);
  assert.equal(T.sample(T.viewModel(p,'magnitude'),[.25,.75]),4);
  assert.deepEqual(p.arrays.temperature_k,[0,1,2,3]);
});
test('raw negative constant K and explicit length conversion remain unchanged',()=>{
  const p=payload();p.arrays.temperature_k.fill(-10);p.coordinates.display_length_in_m=.001;p.coordinates.display_unit='mm';p.summary.units.length='mm';
  const accepted=T.validatePayload(p),m=T.viewModel(accepted);
  assert.equal(m.min,-10);assert.equal(m.max,-10);assert.equal(m.nodes[1][0],1000);
  assert.deepEqual(accepted.arrays.nodes_m[1],[1,0]);assert.equal(m.lengthLabel,'mm');
  assert.doesNotThrow(()=>T.draw(canvas(),m));
});
test('pixels commit only for current render; arrows use centroids and screen-y',()=>{
  const p=payload();p.arrays.heat_flux_w_m2=[[0,4],[0,4]];
  const m=T.viewModel(T.validatePayload(p),'qy'),cv=canvas(),X=T.transform(m,200,160);
  assert.equal(T.draw(cv,m,{current:()=>false}),false);assert.equal(cv.calls.length,0);
  assert.equal(T.draw(cv,m),true);
  const move=cv.calls.find(x=>x[0]==='move'),line=cv.calls.find(x=>x[0]==='line');
  assert.ok(Math.abs(move[1]-X.X(2/3))<1e-10);assert.ok(Math.abs(move[2]-X.Y(1/3))<1e-10);
  assert.ok(line[2]<move[2]);assert.ok(cv.calls.some(x=>x[0]==='pixels'));
});
test('ownership ignores same-revision older success, error, finally and render',()=>{
  const g=new T.Ownership(),a=g.begin('validate'),b=g.begin('validate');
  assert.equal(g.acceptValidation(a,doc()),false);assert.equal(g.finish(a),false);assert.equal(g.busy,true);
  assert.equal(g.acceptValidation(b,doc()),true);assert.equal(g.finish(b),true);
  const r1=g.renderToken('qx'),r2=g.renderToken('qy');assert.equal(g.renderCurrent(r1),false);assert.equal(g.renderCurrent(r2),true);
  g.invalidate();assert.equal(g.renderCurrent(r2),false);assert.equal(g.dirty,true);assert.equal(g.validated,null);
});
test('controller retains raw JSON envelope input and rejects duplicate before submission',async()=>{
  const seen=[],c=T.createController({request:async(method,url,body,raw)=>{
    if(method==='GET')return cap();seen.push({body,raw});
    return {ok:true,doc:body.doc,client_revision:body.client_revision,request_seq:body.request_seq};}});
  await c.loadCapability();
  const raw=JSON.stringify(doc(),null,2);
  assert.equal(await c.validate(doc(),raw),true);assert.equal(seen[0].raw,raw);
  const duplicate=raw.replace('"name": "Heat"','"name": "Heat", "name": "Duplicate"');
  assert.equal(await c.validate(doc(),duplicate),false);assert.equal(seen.length,1);
  assert.equal(c.gate.validated,null);assert.equal(await c.run(),false);
});
test('late validation rejection/finally cannot clear newer normalized snapshot',async()=>{
  let rejectOld;const c=T.createController({request:async(method,url,body)=>{
    if(method==='GET')return cap();
    if(body.request_seq===2)return new Promise((_,reject)=>rejectOld=reject);
    return {ok:true,doc:body.doc,client_revision:body.client_revision,request_seq:body.request_seq};}});
  await c.loadCapability();const old=c.validate(doc());await tick();
  const current=c.validate(doc());await current;rejectOld(Error('late'));await old;
  assert.ok(c.gate.validated);assert.equal(c.state().error,null);assert.equal(c.gate.busy,false);
});
test('actual shipped DOM: no capability preserves steady and transient refusal',async()=>{
  for(const type of ['thermal.steady2d','thermal.transient2d']){
    const p=page();p.element('json').value=JSON.stringify({physics:{heat1:{type}}});
    await p.element('applyJson').onclick();assert.equal(p.element('runBtn').disabled,true);
    assert.equal(p.element('meshBtn').disabled,true);assert.match(p.element('status').textContent,/headless thermal/);
  }
});
test('actual shipped DOM: duplicate thermal JSON never validates old doc or runs',async()=>{
  const p=page();p.run('thermalController.loadCapability()');p.run('globalThis.fetch=async()=>({ok:true,json:async()=>'+JSON.stringify(cap())+'})');
  await p.run('thermalController.loadCapability()');
  p.element('json').value=JSON.stringify(doc()).replace('"name":"Heat"','"name":"Heat","name":"other"');
  p.element('json').oninput();await p.element('applyJson').onclick();
  assert.equal(p.element('runBtn').disabled,true);assert.equal(p.run('thermalController.gate.validated'),null);
  assert.match(p.element('status').textContent,/duplicate/);
  await p.run('doRun()');assert.equal(p.run('thermalController.result()'),null);
});
test('actual shipped DOM: strict success enables run, dirty parse failure blocks prior snapshot',async()=>{
  const p=page();
  p.run('globalThis.fetch=async(url,options)=>({ok:true,json:async()=>url==="/api/capabilities"?'
    +JSON.stringify(cap())+':(()=>{const e=JSON.parse(options.body);return {ok:true,doc:e.doc,client_revision:e.client_revision,request_seq:e.request_seq};})()})');
  await p.run('thermalController.loadCapability()');
  p.element('json').value=JSON.stringify(doc());await p.element('applyJson').onclick();
  assert.equal(p.element('runBtn').disabled,false);assert.equal(p.element('meshBtn').disabled,true);
  p.element('json').value='{"physics":';p.element('json').oninput();
  assert.equal(p.element('runBtn').disabled,true);assert.equal(p.run('thermalController.result()'),null);
  await p.element('applyJson').onclick();await p.run('doRun()');
  assert.equal(p.run('thermalController.gate.validated'),null);assert.equal(p.element('runBtn').disabled,true);
});

test('actual shipped DOM: run installs result mesh and typed fields, late render cannot restore after dirty edit',async()=>{
  const p=page(),wire=payload();
  p.run('globalThis.fetch=async(url,options)=>({ok:true,json:async()=>{'
    +'if(url==="/api/capabilities")return '+JSON.stringify(cap())+';'
    +'if(url==="/api/thermal/validate"){const e=JSON.parse(options.body);return {ok:true,doc:e.doc,client_revision:e.client_revision,request_seq:e.request_seq};}'
    +'if(url==="/api/thermal/run"){globalThis.accepted=JSON.parse(options.body);return {job:"job1",result_id:"res1",client_revision:accepted.client_revision,request_seq:accepted.request_seq};}'
    +'const id={job:"job1",result_id:"res1",client_revision:accepted.client_revision,request_seq:accepted.request_seq};'
    +'return url.endsWith("/result")?{...'+JSON.stringify(wire)+',...id}:{...id,status:"done",log:[]};}})');
  await p.run('thermalController.loadCapability()');
  p.element('json').value=JSON.stringify(doc());await p.element('applyJson').onclick();
  await p.run('doRun()');await tick();
  assert.equal(p.element('thermalControls').hidden,false);
  assert.match(p.element('meshInfo').textContent,/Actual result mesh/);
  assert.match(p.element('resInfo').textContent,/temperature_k/);
  p.element('thermalField').value='qy';p.element('thermalField').onchange();
  p.element('json').value='{';p.element('json').oninput();await tick();
  assert.equal(p.run('thermalController.result()'),null);
  assert.equal(p.element('fieldCanvas').onmousemove,null);
  assert.equal(p.element('thermalControls').hidden,true);
});
test('same-revision deferred run/status/result errors and finally do not mutate newer state',async()=>{
  for(const stage of ['submit','status','result']){
    let release;const seen=[];
    const c=T.createController({wait:async()=>{},request:async(method,url,body)=>{
      if(url==='/api/capabilities')return cap();
      if(url.endsWith('/validate'))return {ok:true,doc:body.doc,client_revision:body.client_revision,request_seq:body.request_seq};
      if(url.endsWith('/run')){seen.push(body);
        if(stage==='submit')return new Promise((_,reject)=>release=reject);
        return {job:'job1',result_id:'res1',client_revision:body.client_revision,request_seq:body.request_seq};}
      const e=seen[0],id={job:'job1',result_id:'res1',client_revision:e.client_revision,request_seq:e.request_seq};
      if(stage==='status'&&!url.endsWith('/result'))return new Promise((_,reject)=>release=reject);
      if(url.endsWith('/result'))return new Promise((_,reject)=>release=reject);
      return {...id,status:'done'};
    }});
    await c.loadCapability();await c.validate(doc());const pending=c.run();
    await tick();c.invalidate();await c.validate(doc());
    release(Error('obsolete '+stage));await pending;
    assert.equal(c.state().error,null);assert.ok(c.gate.validated);assert.equal(c.gate.busy,false);
  }
});
test('older capability reply cannot reenable a newer unsupported capability',async()=>{
  const pending=[];const c=T.createController({request:()=>new Promise(resolve=>pending.push(resolve))});
  const old=c.loadCapability(),newer=c.loadCapability();pending[1]({});await newer;
  pending[0](cap());await old;assert.equal(c.supports(doc()),false);
});

test('explicit supported=false disables capability despite complete routes',()=>{
  const value=cap();value[T.TYPE].supported=false;assert.equal(T.capability(value),null);
});
test('finite huge flux arrows and constant high Kelvin stay finite in display',()=>{
  const value=payload();value.arrays.heat_flux_w_m2=[[1e308,0],[0,1e308]];
  value.arrays.temperature_k.fill(Number.MAX_VALUE);
  const p=T.validatePayload(value),m=T.viewModel(p);
  assert.equal(T.sample(m,[.75,.25]),Number.MAX_VALUE);
  const cv=canvas();T.draw(cv,T.viewModel(p,'magnitude'));
  assert.ok(cv.calls.filter(x=>x[0]==='move'||x[0]==='line').every(x=>x.slice(1).every(Number.isFinite)));
});
test('nonfinite metadata is rejected, never converted to JSON null',()=>{
  const value=payload();value.summary.normalized_heat_balance_defect=Infinity;
  assert.throws(()=>T.validatePayload(value),/nonfinite JSON metadata/);
});

test('shipped page zero-size hidden canvases: Results/Mesh switch and stale render ownership',async()=>{
  const p=page({visibility:true}),wire=payload();
  p.run('globalThis.fetch=async(url,options)=>({ok:true,json:async()=>{'
    +'if(url==="/api/capabilities")return '+JSON.stringify(cap())+';'
    +'if(url==="/api/thermal/validate"){const e=JSON.parse(options.body);return {ok:true,doc:e.doc,client_revision:e.client_revision,request_seq:e.request_seq};}'
    +'if(url==="/api/thermal/run"){globalThis.accepted=JSON.parse(options.body);return {job:"job1",result_id:"res1",client_revision:accepted.client_revision,request_seq:accepted.request_seq};}'
    +'const id={job:"job1",result_id:"res1",client_revision:accepted.client_revision,request_seq:accepted.request_seq};'
    +'return url.endsWith("/result")?{...'+JSON.stringify(wire)+',...id}:{...id,status:"done",log:[]};}})');
  await p.run('thermalController.loadCapability()');p.element('json').value=JSON.stringify(doc());
  await p.element('applyJson').onclick();await p.run('doRun()');await tick();
  assert.equal(p.element('meshCanvas').getBoundingClientRect().width,0);
  assert.ok(p.element('fieldCanvas').calls.some(x=>x[0]==='pixels'));
  assert.doesNotMatch(p.element('status').textContent,/canvas too small/);
  p.run("showTab('mesh')");await tick();
  assert.equal(p.element('fieldCanvas').getBoundingClientRect().width,0);
  assert.match(p.element('meshInfo').textContent,/Actual result mesh/);
  assert.ok(p.element('meshCanvas').calls.some(x=>x[0]==='move'));
  assert.equal(p.element('fieldCanvas').onmousemove,null);
  const count=p.element('meshCanvas').calls.length;
  // Schedule an obsolete mesh render, then switch before its microtask commits.
  p.run("drawThermalViews();showTab('results')");await tick();
  assert.equal(p.element('meshCanvas').calls.length,count);
  assert.ok(p.element('fieldCanvas').onmousemove);
  assert.doesNotMatch(p.element('status').textContent,/canvas too small/);
});

test('actual F capability shape: v1-only allowed, bad/unconfigured limits fail closed',()=>{
  const value=cap();value[T.TYPE].result_formats=[Object.keys(T.PAIRS)[0]];
  value[T.TYPE].field_layouts=[Object.values(T.PAIRS)[0]];
  assert.ok(T.capability(value));
  delete value[T.TYPE].limits;assert.equal(T.capability(value),null);
});
test('unmeasured or absent run-enabled keeps validated JSON from starting a job',async()=>{
  let runs=0;const c=T.createController({request:async(method,url,body)=>{
    if(url==='/api/capabilities'){const value=cap();delete value[T.TYPE].run_enabled;return value;}
    if(url.endsWith('/validate'))return {ok:true,doc:body.doc,client_revision:body.client_revision,request_seq:body.request_seq};
    runs++;throw Error('must not run');
  }});
  await c.loadCapability();assert.equal(await c.validate(doc()),true);
  assert.equal(await c.run(),false);assert.equal(runs,0);
});
