// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Shipped module AND actual page handlers. Node VM is not an actual browser.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {test}=require('node:test');
const script=fs.readFileSync(path.join(__dirname,'../../packages/simcase/src/simcase/studio/static/thermal.js'),'utf8');
const html=fs.readFileSync(path.join(__dirname,'../../packages/simcase/src/simcase/studio/static/index.html'),'utf8');
const T=require('../../packages/simcase/src/simcase/studio/static/thermal.js');
const copy=x=>JSON.parse(JSON.stringify(x));
const tick=()=>new Promise(r=>setImmediate(r));
function cap(){return {capability_format:'studio-capabilities-v1','thermal.steady2d':{
  supported:true,run_enabled:true,resource_policy:'candidate-unmeasured',validate:'/api/thermal/validate',run:'/api/thermal/run',input:'json',mesh_preview:false,
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
    client_revision:revision,request_seq:sequence,result_format,field_layout,summary,arrays,display_length_in_m:1};
}
function canvas(W=200,H=160){
  // Records paths, fills, strokes and globalAlpha assignments.
  const calls=[],ctx=new Proxy({createImageData:(w,h)=>({width:w,height:h,data:new Uint8ClampedArray(w*h*4)}),
    putImageData:image=>calls.push(['pixels',image]),moveTo:(...v)=>calls.push(['move',...v]),
    lineTo:(...v)=>calls.push(['line',...v]),fillText:(...v)=>calls.push(['text',...v]),
    fill:()=>calls.push(['fill',ctx.fillStyle]),stroke:()=>calls.push(['stroke',ctx.lineWidth])},
    {get:(o,k)=>o[k]||(()=>{}),set:(o,k,v)=>{o[k]=v;if(k==='globalAlpha')calls.push(['alpha',v]);return true;}});
  return {width:W,height:H,calls,getContext:()=>ctx,getBoundingClientRect:()=>({width:W,height:H,left:0,top:0})};
}
// Setting textContent or innerHTML replaces an element's children, as in a browser;
// every innerHTML write is recorded so that a test can show names never reach it.
function contentSetters(el,writes){
  let text='',markup='';
  return Object.defineProperties(el,{
    textContent:{get:()=>text,set(v){text=String(v);el.children=[];},enumerable:true,configurable:true},
    innerHTML:{get:()=>markup,set(v){markup=String(v);el.children=[];writes.push(markup);},enumerable:true,configurable:true}});
}
function page({visibility=false}={}){
  const elements=new Map(),requests=[],htmlWrites=[];let activeTab='geometry';
  const panels=['geometry','mesh','results','json'].map(name=>({id:'tab-'+name,classList:{toggle(cls,on){if(on)activeTab=name;}}}));
  function element(id){if(!elements.has(id))elements.set(id,contentSetters(Object.assign(canvas(320,240),{
    value:'',hidden:false,children:[],appendChild(x){this.children.push(x);},
    querySelectorAll:()=>[],click(){if(this.onclick)return this.onclick();}}),htmlWrites));
    const value=elements.get(id);
    if(visibility&&['fieldCanvas','meshCanvas','sweepCanvas','geoCanvas'].includes(id))value.getBoundingClientRect=()=>{
      const tab=id==='meshCanvas'?'mesh':id==='geoCanvas'?'geometry':'results';
      return {width:activeTab===tab?320:0,height:activeTab===tab?240:0,left:0,top:0};};
    return value;}
  const context=vm.createContext({document:{getElementById:element,querySelectorAll:selector=>selector==='.view > div'?panels:[],
    createElement:tag=>contentSetters({tag,style:{},className:'',children:[],appendChild(x){this.children.push(x);},
      setAttribute(){},click(){}},htmlWrites)},window:{addEventListener(){},devicePixelRatio:1},
    Uint8ClampedArray,console,URL:{createObjectURL:()=>''},Blob:function(){},
    setTimeout:cb=>cb(),fetch:(...args)=>{requests.push(args);return new Promise(()=>{});}});
  vm.runInContext(script,context);
  vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1],context);
  return {element,requests,htmlWrites,run:code=>vm.runInContext(code,context)};
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
  if(mutation==='display')p.display_length_in_m=0;
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
  const p=payload();p.arrays.temperature_k.fill(-10);p.display_length_in_m=.001;p.summary.units.length='mm';
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
  const p=page();p.run('thermalController.loadCapability()');p.run('globalThis.fetch=async()=>({ok:true,json:async()=>('+JSON.stringify(cap())+')})');
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
  for(const id of ['resInfo','meshInfo','meshLegend'])p.element(id).textContent='old result '+id;
  p.element('json').value='{';p.element('json').oninput();
  assert.equal(p.element('resInfo').textContent,'no results available');
  for(const id of ['meshInfo','meshLegend'])assert.equal(p.element(id).textContent,'');
  await tick();
  assert.equal(p.element('resInfo').textContent,'no results available');
  for(const id of ['meshInfo','meshLegend'])assert.equal(p.element(id).textContent,'');
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
test('absent run-enabled keeps validated JSON from starting a job',async()=>{
  let runs=0;const c=T.createController({request:async(method,url,body)=>{
    if(url==='/api/capabilities'){const value=cap();delete value[T.TYPE].run_enabled;return value;}
    if(url.endsWith('/validate'))return {ok:true,doc:body.doc,client_revision:body.client_revision,request_seq:body.request_seq};
    runs++;throw Error('must not run');
  }});
  await c.loadCapability();assert.equal(await c.validate(doc()),true);
  assert.equal(await c.run(),false);assert.equal(runs,0);
});

test('settled wire rejects nested coordinates and runs independently of measurement',()=>{const p=payload();assert.equal(T.validatePayload(p).display_length_in_m,1);p.coordinates={raw_unit:'m',display_unit:'m',display_length_in_m:1};assert.throws(()=>T.validatePayload(p));assert.equal(T.capability(cap()).run_enabled,true);assert.equal(T.capability(cap()).resource_policy,'candidate-unmeasured');});

test('shipped result panel shows physical diagnostics and collapsible metadata',()=>{const p=page();p.run("renderThermalSummary({arrays:{temperature_k:[-2,4],nodes_m:[[],[],[]],triangles:[[]]},summary:{diagnostics:{source_heat_w_per_m:60,outward_heat_w_per_m:60,normalized_heat_balance_defect:0}}})");const host=p.element('resTable');assert.equal(host.children[0].children.length,5);assert.equal(host.children[1].children[0].textContent,'Full result metadata');assert.equal(host.children[0].children[0].children[1].textContent,'-2 … 4');});

test('shipped page current derived overflow clears only field; stale render cannot clear newer view',async()=>{
  const p=page(),wire=payload();wire.arrays.heat_flux_w_m2=[[Number.MAX_VALUE,Number.MAX_VALUE],[0,1]];
  p.run('globalThis.wire='+JSON.stringify(wire)+';thermalSupported=()=>true;'
    +'thermalController.result=()=>wire;globalThis.renderSeq=0;'
    +'thermalController.renderToken=field=>({seq:++renderSeq,field});'
    +'thermalController.renderCurrent=t=>t.seq===renderSeq;');
  p.element('thermalField').value='temperature_k';p.run('drawThermalViews()');await tick();
  assert.ok(p.element('fieldCanvas').onmousemove);
  p.element('fieldCanvas').getContext('2d').clearRect=()=>p.element('fieldCanvas').calls.push(['clear']);
  p.element('thermalField').value='magnitude';p.run('drawThermalViews()');await tick();
  assert.ok(p.element('fieldCanvas').calls.some(x=>x[0]==='clear'));
  assert.equal(p.element('fieldCanvas').onmousemove,null);
  assert.match(p.element('resInfo').textContent,/magnitude.*view error.*overflow/);
  assert.equal(p.run('thermalController.result()===wire'),true);
  assert.match(p.element('meshInfo').textContent,/Actual result mesh/);
  const failedLabel=p.element('resInfo').textContent;
  p.run('globalThis.frameTrace=[];'
    +'const fieldContext=document.getElementById("fieldCanvas").getContext("2d");'
    +'const originalPut=fieldContext.putImageData;'
    +'fieldContext.clearRect=()=>frameTrace.push("clear");'
    +'fieldContext.putImageData=image=>{frameTrace.push("pixels");originalPut(image);};');
  p.element('thermalField').value='magnitude';p.run('drawThermalViews()');
  // This checkpoint runs after the obsolete callback and before the current frame.
  p.run('Promise.resolve().then(()=>{globalThis.afterStale={trace:frameTrace.slice(),'
    +'label:document.getElementById("resInfo").textContent,'
    +'hover:document.getElementById("fieldCanvas").onmousemove===null};})');
  p.element('thermalField').value='temperature_k';p.run('drawThermalViews()');await tick();
  assert.equal(p.run('JSON.stringify(afterStale.trace)'),'[]');
  assert.equal(p.run('afterStale.label'),failedLabel);
  assert.equal(p.run('afterStale.hover'),true);
  assert.equal(p.run('JSON.stringify(frameTrace)'),JSON.stringify(['clear','pixels']));
  assert.equal(typeof p.element('fieldCanvas').onmousemove,'function');
  assert.match(p.element('resInfo').textContent,/temperature_k/);
  assert.doesNotMatch(p.element('resInfo').textContent,/view error/);
});

test('shipped HTTP bridge treats validation 200 ok=false and run 400 as errors',async()=>{
  const p=page();
  p.run('globalThis.invalidValidation=true;globalThis.runRequests=0;'
    +'globalThis.fetch=async(url,options)=>{'
    +'if(url==="/api/capabilities")return {ok:true,json:async()=>('+JSON.stringify(cap())+')};'
    +'const e=JSON.parse(options.body);'
    +'if(url==="/api/thermal/validate")return {ok:true,status:200,json:async()=>invalidValidation?'
    +'{ok:false,error:{code:"invalid_document",message:"invalid thermal fixture"},client_revision:e.client_revision,request_seq:e.request_seq}:'
    +'{ok:true,doc:e.doc,client_revision:e.client_revision,request_seq:e.request_seq}};'
    +'runRequests++;return {ok:false,status:400,json:async()=>({ok:false,error:{code:"invalid_document",message:"run rejected fixture"},client_revision:e.client_revision,request_seq:e.request_seq})};};');
  await p.run('thermalController.loadCapability()');
  p.element('json').value=JSON.stringify(doc());await p.element('applyJson').onclick();
  assert.equal(p.element('runBtn').disabled,true);
  assert.equal(p.run('thermalController.gate.validated'),null);
  assert.match(p.element('status').textContent,/invalid thermal fixture/);
  await p.run('doRun()');assert.equal(p.run('runRequests'),0);
  p.run('invalidValidation=false');await p.element('applyJson').onclick();
  assert.equal(p.element('runBtn').disabled,false);
  await p.run('doRun()');
  assert.equal(p.run('runRequests'),1);
  assert.equal(p.run('thermalController.result()'),null);
  assert.equal(p.run('thermalController.gate.busy'),false);
  assert.match(p.element('status').textContent,/run rejected fixture/);
});

// ---- region documents (J1-J6, J8-J10; the transient cases are in studio_transient_thermal.cjs) ----

const REGION_LIMITS={max_shapes:64,max_circles:16,max_polygon_points:512,max_boundary_crossings:1024,max_input_vertices:2048};
function regionBlock(){return {supported:true,run_enabled:true,result_formats:[T.REGION.result_format],
  field_layouts:[T.REGION.field_layout],payload_formats:[T.REGION.payload_format],limits:{...REGION_LIMITS}};}
// regionCap() advertises a valid block; regionCap(undefined) advertises none.
function regionCap(...block){const value=cap(),b=block.length?block[0]:regionBlock();if(b!==undefined)value[T.TYPE].regions=b;return value;}
function regionDoc(){return {openphysics:'0.2',name:'Regions',units:{length:'m',temperature:'K'},
  geometry:{domain:{xmin:0,xmax:1,ymin:0,ymax:1},background:{material:'insulation'},
    shapes:[{name:'heater',type:'rect',x:.5,y:0,w:.5,h:1,material:'copper'}]},
  materials:{copper:{conductivity_w_mk:400},insulation:{conductivity_w_mk:.04}},physics:{heat1:{type:T.TYPE}},
  mesh:{size:.5},study:{type:'single'}};}
// Own properties only: a region may be named __proto__.
const own=entries=>{const o={};for(const [k,v] of entries)Object.defineProperty(o,k,{value:v,enumerable:true,writable:true,configurable:true});return o;};
function regionPayload({names=['heater','background'],ids=[0,1],materials=['copper','insulation'],revision=0,sequence=1}={}){
  const p=payload({v2:true,D:0,revision,sequence});
  p.payload_format=T.REGION.payload_format;
  p.result_format=p.summary.result_format=T.REGION.result_format;
  p.field_layout=p.summary.field_layout=T.REGION.field_layout;
  p.arrays.triangle_regions=ids.slice();
  p.summary.field_units.triangle_regions='1';p.summary.field_locations.triangle_regions='triangles';
  p.summary.field_shapes.triangle_regions=[ids.length];
  p.summary.region_names=names.slice();
  p.summary.regions=own(names.map((n,i)=>[n,{material:materials[i],triangles:ids.filter(v=>v===i).length,area_m2:.5*ids.filter(v=>v===i).length}]));
  p.summary.materials={copper:{conductivity_w_mk:400,source:'document value'},insulation:{conductivity_w_mk:.04}};
  p.summary.heat_source_w_m3=own([[names[0],5e6]]);
  return p;
}
const OWNER={job:'job1',result_id:'res1',client_revision:0,request_seq:1};

test('J1 region capability is nested: rectangle fields unchanged, outer pairs refused, absent block refuses region documents only',async()=>{
  const plain=T.capability(cap()),nested=T.capability(regionCap());
  const {regions,...rest}=nested;assert.deepEqual(rest,plain);assert.deepEqual(regions,regionBlock());
  assert.ok(T.regionCapability(nested.regions));
  const outer=regionCap();outer[T.TYPE].result_formats.push(T.REGION.result_format);outer[T.TYPE].field_layouts.push(T.REGION.field_layout);
  assert.equal(T.capability(outer),null);
  const malformed=[undefined,null,{...regionBlock(),extra:1},{...regionBlock(),supported:false},{...regionBlock(),run_enabled:'yes'},
    {...regionBlock(),payload_formats:['studio-thermal-steady-v1']},{...regionBlock(),limits:{...REGION_LIMITS,max_shapes:0}},
    {...regionBlock(),limits:{...REGION_LIMITS,extra:1}},(()=>{const b=regionBlock();delete b.limits.max_boundary_crossings;return b;})()];
  for(const block of malformed){
    assert.equal(T.regionCapability(block),null);
    let posted=0;const c=T.createController({request:async(method,url,body)=>{
      if(method==='GET')return regionCap(block);posted++;
      return {ok:true,doc:body.doc,client_revision:body.client_revision,request_seq:body.request_seq};}});
    await c.loadCapability();
    assert.equal(await c.validate(regionDoc()),false);assert.equal(posted,0);
    assert.match(c.state().error,/does not advertise region documents/);
    assert.equal(await c.validate(doc()),true);assert.equal(posted,1);
  }
});

test('J2 region payload: D=0, a zero-cell region and literal hostile names are accepted; malformed ones refused',()=>{
  const accepted=T.validateRegionPayload(regionPayload(),OWNER,REGION_LIMITS);
  assert.equal(accepted.arrays.dirichlet_node_ids.length,0);assert.equal(accepted.payload_format,T.REGION.payload_format);
  assert.equal(accepted.result_format,T.REGION.result_format);assert.equal(accepted.summary.result_format,T.REGION.result_format);
  assert.deepEqual(accepted.regions.names,['heater','background']);assert.deepEqual(accepted.regions.ids,[0,1]);
  assert.deepEqual(accepted.regions.rows.map(r=>[r.name,r.material,r.k,r.q,r.cells,r.color]),
    [['heater','copper',400,5e6,1,T.PALETTE[0]],['background','insulation',.04,0,1,T.PALETTE[1]]]);
  assert.deepEqual(accepted.regions.edges,[[0,2]]);
  const empty=T.validateRegionPayload(regionPayload({names:['heater','background','hidden'],materials:['copper','insulation','copper']}),OWNER);
  assert.equal(empty.regions.rows[2].cells,0);
  for(const name of ['__proto__','constructor','toString','<img src=x onerror=1>']){
    const value=T.validateRegionPayload(JSON.parse(JSON.stringify(regionPayload({names:[name,'background']}))),OWNER);
    assert.equal(value.regions.rows[0].name,name);assert.equal(value.regions.rows[0].q,5e6);
    assert.equal(Object.getPrototypeOf(value.summary.regions),Object.prototype);
  }
  const faults={
    missing:p=>{delete p.arrays.triangle_regions;},
    fractional:p=>{p.arrays.triangle_regions[0]=.5;},
    range:p=>{p.arrays.triangle_regions[0]=2;},
    negative:p=>{p.arrays.triangle_regions[0]=-1;},
    length:p=>{p.arrays.triangle_regions.push(0);},
    duplicate_name:p=>{p.summary.region_names=['heater','heater'];},
    empty_name:p=>{p.summary.region_names=['','background'];},
    regions_keys:p=>{delete p.summary.regions.background;},
    entry_keys:p=>{p.summary.regions.heater.extra=1;},
    cell_count:p=>{p.summary.regions.heater.triangles=2;},
    material_not_own:p=>{p.summary.regions.heater.material='toString';},
    metadata:p=>{p.summary.field_locations.triangle_regions='nodes';},
    summary_pair:p=>{p.summary.result_format='thermal.steady2d-result-v2';},
    rectangle_pair:p=>{p.payload_format='studio-thermal-steady-v1';p.result_format=p.summary.result_format='thermal.steady2d-result-v2';
      p.field_layout=p.summary.field_layout=T.PAIRS['thermal.steady2d-result-v2'];},
    too_many:p=>{},
  };
  for(const [name,fault] of Object.entries(faults)){
    const p=regionPayload();fault(p);
    assert.throws(()=>T.validateRegionPayload(p,OWNER,name==='too_many'?{...REGION_LIMITS,max_shapes:0}:REGION_LIMITS),name);
  }
  // A rectangle pair carrying triangle_regions is refused by the unchanged rectangle parser too.
  const rect=payload();rect.arrays.triangle_regions=[0,0];assert.throws(()=>T.validatePayload(rect));
});

test('J3 a rectangle view model keeps its exact keys',()=>{
  assert.deepEqual(Object.keys(T.viewModel(T.validatePayload(payload()))),
    ['nodes','triangles','values','min','max','unit','field','nodal','domain','lengthLabel','flux']);
  assert.deepEqual(Object.keys(T.viewModel(T.validateRegionPayload(regionPayload(),OWNER))),
    ['nodes','triangles','values','min','max','unit','field','nodal','domain','lengthLabel','flux','regions']);
});

// Rectangle draw calls recorded on the commit before region support (thermal.js then).
const RECTANGLE_CALLS={"mesh":[["move",62.5,117.5],["line",137.5,117.5],["line",137.5,42.5],["move",62.5,117.5],["line",137.5,42.5],["line",62.5,42.5],["text","x / y (m); +y upward",100,148],["text","Actual result mesh",12,18]],"temperature":[["text","x / y (m); +y upward",100,148],["text","temperature_k [K] 0 … 3",12,18],["text","0 … 3 K",12,51]],"qx":[["move",112.5,92.5],["line",123.5,92.5],["move",119.11208719054814,94.89712769302102],["line",123.5,92.5],["line",119.11208719054814,90.10287230697898],["move",87.5,67.5],["line",87.5,89.5],["move",85.10287230697898,85.11208719054814],["line",87.5,89.5],["line",89.89712769302102,85.11208719054814],["text","x / y (m); +y upward",100,148],["text","qx [W/m²] 0 … 2",12,18],["text","0 … 2 W/m²",12,51],["text","Cell flux; arrows max 22 px (view only), global +y upward",12,129]]};
const kinds=(cv,...names)=>cv.calls.filter(c=>names.includes(c[0]));
function sameCalls(actual,expected){
  assert.equal(actual.length,expected.length);
  actual.forEach((c,i)=>{assert.equal(c[0],expected[i][0]);
    c.slice(1).forEach((v,j)=>typeof v==='number'?assert.ok(Math.abs(v-expected[i][j+1])<=1e-9):assert.equal(v,expected[i][j+1]));});
}
test('J4 region mesh fills each cell and strokes each region edge; rectangle draws are unchanged',()=>{
  const p=T.validateRegionPayload(regionPayload(),OWNER),m=T.viewModel(p),cv=canvas();
  assert.equal(T.draw(cv,m,{meshOnly:true}),true);
  const fills=kinds(cv,'fill');assert.equal(fills.length,p.arrays.triangles.length);
  assert.deepEqual(fills.map(f=>f[1]),[T.PALETTE[0],T.PALETTE[1]]);
  assert.deepEqual(kinds(cv,'alpha').map(a=>a[1]),[.55,1]);
  const lastFill=cv.calls.lastIndexOf(fills[fills.length-1]),reset=cv.calls.findIndex(c=>c[0]==='alpha'&&c[1]===1);
  assert.ok(reset>lastFill&&reset<cv.calls.findIndex(c=>c[0]==='stroke'));
  const strokes=kinds(cv,'stroke');
  assert.equal(strokes.length,p.arrays.triangles.length+p.regions.edges.length);
  assert.deepEqual(strokes.slice(-p.regions.edges.length).map(s=>s[1]),[1.6]);
  const field=canvas();T.draw(field,T.viewModel(p,'qx'));
  assert.equal(kinds(field,'fill').length,0);assert.ok(kinds(field,'stroke').some(s=>s[1]===1.2));
  for(const [name,model,options] of [['mesh',T.viewModel(T.validatePayload(payload())),{meshOnly:true}],
      ['temperature',T.viewModel(T.validatePayload(payload())),{}],['qx',T.viewModel(T.validatePayload(payload()),'qx'),{}]]){
    const rect=canvas();T.draw(rect,model,options);
    assert.equal(kinds(rect,'fill').length,0);assert.equal(kinds(rect,'alpha').length,0);
    sameCalls(kinds(rect,'move','line','text'),RECTANGLE_CALLS[name]);
  }
  const stale=canvas();assert.equal(T.draw(stale,m,{meshOnly:true,current:()=>false}),false);assert.equal(stale.calls.length,0);
  // An interface edge between two regions of a 4-triangle mesh, and none inside one region.
  assert.deepEqual(T.regionEdges([[0,1,4],[1,2,4],[2,3,4],[3,0,4]],[0,0,1,1],5),[[2,4],[0,4]]);
  assert.deepEqual(T.regionEdges([[0,1,4],[1,2,4],[2,3,4],[3,0,4]],[0,0,0,0],5),[]);
});

function regionPage(wire,{capability=regionCap(),regionDocument=regionDoc()}={}){
  const p=page();
  p.run('globalThis.fetch=async(url,options)=>({ok:true,json:async()=>{'
    +'if(url==="/api/capabilities")return '+JSON.stringify(capability)+';'
    +'if(url==="/api/thermal/validate"){const e=JSON.parse(options.body);return {ok:true,doc:e.doc,client_revision:e.client_revision,request_seq:e.request_seq};}'
    +'if(url==="/api/thermal/run"){globalThis.accepted=JSON.parse(options.body);return {job:"job1",result_id:"res1",client_revision:accepted.client_revision,request_seq:accepted.request_seq};}'
    +'const id={job:"job1",result_id:"res1",client_revision:accepted.client_revision,request_seq:accepted.request_seq};'
    +'return url.endsWith("/result")?{...'+JSON.stringify(wire)+',...id}:{...id,status:"done",log:[]};}})');
  p.document=regionDocument;return p;
}
async function runPage(p){
  await p.run('thermalController.loadCapability()');
  p.element('json').value=JSON.stringify(p.document);await p.element('applyJson').onclick();
  await p.run('doRun()');await tick();
}
function hover(p,x,y){
  const model=p.run('ThermalStudio.viewModel(thermalController.result(),document.getElementById("thermalField").value||"temperature_k")');
  const t=T.transform(model,320,240);p.element('fieldCanvas').onmousemove({clientX:t.X(x),clientY:t.Y(y)});
  return p.element('resInfo').textContent;
}
test('J5 region hover names the region and material; rectangle hover is unchanged',async()=>{
  const p=regionPage(regionPayload());await runPage(p);
  assert.match(p.element('status').textContent,/steady thermal result ready/);
  assert.ok(hover(p,.75,.25).endsWith('; region heater (copper)'));
  assert.ok(hover(p,.25,.75).endsWith('; region background (insulation)'));
  const r=regionPage(payload(),{capability:cap(),regionDocument:doc()});await runPage(r);
  assert.equal(hover(r,.75,.25),'temperature_k = 1 K (raw P1 interpolation)');
});

test('J6 region summary: no region name becomes a quantity row; metadata second, region table third',async()=>{
  const wire=regionPayload({names:['source_block','background']});
  const p=regionPage(wire);await runPage(p);
  const host=p.element('resTable');
  assert.equal(host.children.length,3);
  assert.ok(host.children[0].children.every(row=>!JSON.stringify(row.children.map(c=>c.textContent)).includes('source block')));
  assert.equal(host.children[1].children[0].textContent,'Full result metadata');
  const table=host.children[2],body=table.children[1];
  assert.equal(table.className,'res region-table');assert.equal(body.tag,'tbody');assert.equal(body.children.length,2);
  assert.deepEqual(body.children[0].children.slice(1).map(c=>c.textContent),
    ['source_block','copper','400','5000000','1','0.5','document value']);
});

test('J8 legend, table and literal hostile names; a dirty edit clears legend and table',async()=>{
  const name='<img src=x onerror=1>';
  const p=regionPage(regionPayload({names:[name,'background']}));await runPage(p);
  p.run("showTab('mesh')");await tick();
  assert.equal(p.element('meshInfo').textContent,'Actual result mesh — 4 nodes, 2 cells, 2 regions; axes m');
  const list=p.element('meshLegend').children[0];
  assert.equal(list.className,'region-list');assert.equal(list.children.length,2);
  assert.equal(list.children[0].children[1].textContent,name+' — copper');
  assert.equal(list.children[0].children[0].style.background,T.PALETTE[0]);
  assert.ok(p.htmlWrites.every(markup=>!markup.includes('<img')&&!markup.includes('heater')));
  p.run("showTab('results')");await tick();
  assert.equal(p.element('resTable').children.length,3);
  p.element('json').value='{';p.element('json').oninput();
  for(const id of ['meshLegend','resTable']){
    assert.equal(p.element(id).textContent,'');assert.equal(p.element(id).children.length,0);
  }
});

test('J9 the family is pinned at validation: each family refuses the other payload',async()=>{
  for(const [document,wire] of [[regionDoc(),payload()],[doc(),regionPayload()]]){
    const c=T.createController({wait:async()=>{},request:async(method,url,body)=>{
      if(url==='/api/capabilities')return regionCap();
      if(url.endsWith('/validate'))return {ok:true,doc:body.doc,client_revision:body.client_revision,request_seq:body.request_seq};
      const id={job:'job1',result_id:'res1',client_revision:body?.client_revision??c.gate.revision,request_seq:body?.request_seq??c.gate.sequence};
      if(url.endsWith('/run'))return id;
      return url.endsWith('/result')?{...wire,...id}:{...id,status:'done'};
    }});
    await c.loadCapability();assert.equal(await c.validate(document),true);
    assert.equal(await c.run(),false);assert.equal(c.result(),null);assert.ok(c.state().error);
  }
  // A region document runs only while the region block allows it.
  const block=regionBlock();block.run_enabled=false;
  const c=T.createController({request:async(method,url,body)=>{
    if(url==='/api/capabilities')return regionCap(block);
    if(url.endsWith('/validate'))return {ok:true,doc:body.doc,client_revision:body.client_revision,request_seq:body.request_seq};
    throw Error('must not run');}});
  await c.loadCapability();
  assert.equal(await c.validate(regionDoc()),true);assert.equal(await c.run(),false);
  assert.equal(await c.validate(doc()),true);
});

test('J10 hasRegionGeometry on the server rule fixtures (two physics entries: false here, true on the server)',()=>{
  const region=regionDoc(),rectangle=doc();
  const shapesOnly=copy(region);delete shapesOnly.geometry.background;
  const backgroundOnly=copy(region);delete backgroundOnly.geometry.shapes;
  const geometryList=copy(region);geometryList.geometry=[region.geometry];
  const noGeometry=copy(region);delete noGeometry.geometry;
  const physicsNotDict=copy(region);physicsNotDict.physics=['heat1'];
  const twoPhysics=copy(region);twoPhysics.physics.second={type:T.TYPE};
  const decided=Object.fromEntries(Object.entries({rectangle,region,shapesOnly,backgroundOnly,geometryList,noGeometry,
    physicsNotDict,twoPhysics}).map(([k,v])=>[k,T.hasRegionGeometry(v)]));
  assert.deepEqual(decided,{rectangle:false,region:true,shapesOnly:true,backgroundOnly:true,geometryList:false,
    noGeometry:false,physicsNotDict:false,twoPhysics:false});
});
