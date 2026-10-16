// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Public, JSON-only thermal views. No solver, private API or model mutation.
(function(root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.ThermalStudio = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function() {
  'use strict';
  const TYPE = 'thermal.steady2d';
  const PAIRS = {
    'thermal.steady2d-result-v1': 'thermal2d-p1-node-cell-v1',
    'thermal.steady2d-result-v2': 'thermal2d-p1-node-cell-boundary-v2'
  };
  const BASE = {
    nodes_m: ['m','nodes',2], triangles: ['1','triangle_connectivity',3],
    temperature_k: ['K','nodes',0], heat_flux_w_m2: ['W/m^2','triangle_centroids',2],
    load_w_per_m: ['W/m','nodes',0], reaction_w_per_m: ['W/m','nodes',0],
    residual_w_per_m: ['W/m','nodes',0], dirichlet_node_ids: ['1','dirichlet_nodes',0],
    dirichlet_temperature_k: ['K','dirichlet_nodes',0]
  };
  const ADDED = ['prescribed_outward_load_w_per_m','ambient_load_w_per_m',
    'convective_outward_w_per_m','system_rhs_w_per_m'];
  function fail(message) { throw new Error('Thermal view: '+message); }
  const object = x => x !== null && typeof x === 'object' && !Array.isArray(x);
  const finite = x => typeof x === 'number' && Number.isFinite(x);
  const integer = x => Number.isSafeInteger(x) && x >= 0;
  const clone = x => JSON.parse(JSON.stringify(x));
  function soleType(doc) {
    if (!object(doc?.physics)) return null;
    const values = Object.values(doc.physics);
    return values.length === 1 && object(values[0]) ? values[0].type : null;
  }
  function route(s) { return typeof s === 'string' && /^\/api\/[a-zA-Z0-9_/-]+$/.test(s) && !s.includes('..'); }
  function capability(data) {
    const c = data?.[TYPE];
    if (data?.capability_format !== 'studio-capabilities-v1' || !object(c)
        || c.input !== 'json' || c.mesh_preview !== false || c.mesh_from_result !== true
        || c.time_navigation !== false || !route(c.validate) || !route(c.run)
        || !Array.isArray(c.result_formats) || !Array.isArray(c.field_layouts)
        || !Object.entries(PAIRS).every(([f,l]) => c.result_formats.includes(f) && c.field_layouts.includes(l))
        || !Array.isArray(c.fields) || !['temperature_k','heat_flux_w_m2'].every(f=>c.fields.includes(f)))
      return null;
    return clone(c);
  }
  function strictParse(text) {
    if (typeof text!=='string') fail('raw JSON text required');
    JSON.parse(text);
    let i=0;
    const space=()=>{while(i<text.length&&/\s/.test(text[i]))i++;};
    function string() {
      const start=i++;let escaped=false;
      while(i<text.length){const c=text[i++];if(!escaped&&c==='"')return JSON.parse(text.slice(start,i));
        if(!escaped&&c==='\\')escaped=true;else escaped=false;}
      fail('unterminated string');
    }
    function value() {
      space();const c=text[i];
      if(c==='{'){i++;space();const out={},seen=new Set();if(text[i]==='}'){i++;return out;}
        while(true){space();const k=string();if(seen.has(k))fail('duplicate JSON key '+k);seen.add(k);
          space();i++;const v=value();Object.defineProperty(out,k,{value:v,enumerable:true,writable:true,configurable:true});
          space();if(text[i++]==='}')return out;}}
      if(c==='['){i++;space();const out=[];if(text[i]===']'){i++;return out;}
        while(true){out.push(value());space();if(text[i++]===']')return out;}}
      if(c==='"')return string();
      for(const [word,v]of [['true',true],['false',false],['null',null]])
        if(text.slice(i,i+word.length)===word){i+=word.length;return v;}
      const token=text.slice(i).match(/^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/);
      if(!token)fail('invalid JSON value');i+=token[0].length;const number=Number(token[0]);
      if(!finite(number))fail('nonfinite JSON number');return number;
    }
    const result=value();space();if(i!==text.length)fail('trailing JSON content');return result;
  }
  function identity(x) {
    return object(x) && typeof x.job === 'string' && x.job.length > 0
      && typeof x.result_id === 'string' && x.result_id.length > 0
      && integer(x.client_revision) && integer(x.request_seq);
  }
  function finiteJSON(value, seen=new Set()) {
    if(value===null||typeof value==='string'||typeof value==='boolean')return;
    if(typeof value==='number'){if(!finite(value))fail('nonfinite JSON metadata');return;}
    if(!object(value)&&!Array.isArray(value))fail('unsupported JSON metadata value');
    if(seen.has(value))fail('cyclic JSON metadata');seen.add(value);
    Object.values(value).forEach(v=>finiteJSON(v,seen));seen.delete(value);
  }
  function validatePayload(input, expected) {
    finiteJSON(input);
    const allowed=['payload_format','kind','job','result_id','client_revision','request_seq',
      'result_format','field_layout','arrays','summary','display_length_in_m'];
    if(!object(input)||Object.keys(input).some(k=>!allowed.includes(k)))fail('unknown wire field');
    if(['neff','group_index','wavelength','modes','parameter','time_s'].some(k=>k in (input.summary||{})))
      fail('optical/transient summary keys are unsupported');

    if (!object(input) || input.payload_format !== 'studio-thermal-steady-v1'
        || input.kind !== TYPE || PAIRS[input.result_format] !== input.field_layout || !identity(input))
      fail('unsupported payload, result/layout pair or identity');
    if (expected && ['job','result_id','client_revision','request_seq'].some(k=>input[k]!==expected[k]))
      fail('response ownership mismatch');
    const a = input.arrays, s = input.summary;
    if (!object(a) || !object(s) || s.physics_type !== TYPE
        || s.result_format !== input.result_format || s.field_layout !== input.field_layout)
      fail('summary and arrays do not match the typed result');
    const spec = {...BASE};
    if (input.result_format.endsWith('-v2')) ADDED.forEach(k=>spec[k]=['W/m','nodes',0]);
    if (Object.keys(a).length !== Object.keys(spec).length || Object.keys(a).some(k=>!spec[k]))
      fail('unexpected or missing physical arrays');
    const N = a.nodes_m?.length, M = a.triangles?.length, D = a.dirichlet_node_ids?.length;
    if (!integer(N) || N<3 || !integer(M) || M<1 || !integer(D) || D>N
        || (input.result_format.endsWith('-v1') && D===0)) fail('invalid N/M/D');
    const arrays = {};
    for (const [key,[unit,location,cols]] of Object.entries(spec)) {
      const rows = key==='triangles'||key==='heat_flux_w_m2' ? M : key.startsWith('dirichlet_') ? D : N;
      const shape = cols ? [rows,cols] : [rows];
      const values = a[key];
      if (!Array.isArray(values) || values.length!==rows
          || JSON.stringify(s.field_shapes?.[key])!==JSON.stringify(shape)
          || s.field_units?.[key]!==unit || s.field_locations?.[key]!==location)
        fail('shape/unit/location for '+key);
      arrays[key] = values.map(row=>{
        if (cols) {
          if (!Array.isArray(row) || row.length!==cols || row.some(v=>!finite(v))) fail('numeric row for '+key);
          return row.slice();
        }
        if (!finite(row)) fail('finite number for '+key);
        return row;
      });
    }
    const nodes = arrays.nodes_m, tris = arrays.triangles, ids = arrays.dirichlet_node_ids;
    for (const tri of tris) {
      if (tri.some(i=>!integer(i)||i>=N) || new Set(tri).size!==3) fail('connectivity');
      const [p,q,r]=tri.map(i=>nodes[i]);
      const det=(q[0]-p[0])*(r[1]-p[1])-(q[1]-p[1])*(r[0]-p[0]);
      if (!finite(det)||det<=0) fail('CCW nondegenerate geometry');
    }
    if (ids.some((v,i)=>!integer(v)||v>=N||(i&&v<=ids[i-1]))) fail('unique sorted fixed IDs');
    if (!finite(input.display_length_in_m)||input.display_length_in_m<=0) fail('display length conversion');
    const declared=s.units?.length;
    const label=typeof declared==='string' ? declared
      : object(declared)&&Object.keys(declared).length===1&&finite(declared.in_m)&&declared.in_m>0
        ? String(declared.in_m)+' m' : null;
    if (!label || s.units?.temperature!=='K' || s.mesh_length_unit!=='m') fail('explicit length/K units');
    // Copy the validated finite summary; no backend text is interpreted as HTML.
    const summary = clone(s);
    return Object.freeze({...input, arrays, summary, lengthLabel:label});
  }

  class Ownership {
    constructor() {
      this.revision=0; this.sequence=0; this.renderSeq=0; this.capSeq=0;
      this.job=null; this.resultId=null; this.validated=null; this.dirty=true; this.busy=false;
    }
    invalidate() {
      this.revision++; this.sequence++; this.renderSeq++;
      this.job=this.resultId=null; this.validated=null; this.dirty=true; this.busy=false;
    }
    begin(kind) {
      this.sequence++; this.busy=true;
      if (kind==='run') { this.job=this.resultId=null; this.renderSeq++; }
      return Object.freeze({revision:this.revision, sequence:this.sequence, job:this.job,
        resultId:this.resultId, kind});
    }
    current(t) {
      return !!t && t.revision===this.revision && t.sequence===this.sequence
        && t.job===this.job && t.resultId===this.resultId;
    }
    finish(t) { if (!this.current(t)) return false; this.busy=false; return true; }
    acceptValidation(t, doc) {
      if (!this.current(t)) return false;
      this.validated=clone(doc); this.dirty=false; return true;
    }
    bind(t, reply) {
      if (!this.current(t)) return null;
      if (!identity(reply)||reply.client_revision!==t.revision||reply.request_seq!==t.sequence)
        fail('job response ownership mismatch');
      this.job=reply.job; this.resultId=reply.result_id;
      return Object.freeze({...t,job:this.job,resultId:this.resultId});
    }
    renderToken(field) {
      this.renderSeq++;
      return {revision:this.revision,sequence:this.sequence,job:this.job,
        resultId:this.resultId,renderSeq:this.renderSeq,field};
    }
    renderCurrent(t) { return this.current(t)&&t.renderSeq===this.renderSeq; }
    beginCapability() { return ++this.capSeq; }
    capabilityCurrent(seq) { return seq===this.capSeq; }
  }

  function viewModel(payload, field='temperature_k') {
    const a=payload.arrays, scale=payload.display_length_in_m;
    const nodes=a.nodes_m.map(p=>p.map(x=>x/scale));
    if (nodes.some(p=>p.some(x=>!finite(x)))) fail('display coordinates overflow');
    let values,unit;
    if (field==='temperature_k') { values=a.temperature_k.slice(); unit='K'; }
    else if (['qx','qy','magnitude'].includes(field)) {
      values=a.heat_flux_w_m2.map(q=>field==='qx'?q[0]:field==='qy'?q[1]:Math.hypot(q[0],q[1])); unit='W/m²';
    } else fail('unsupported steady field; no time/history selection');
    if (values.some(v=>!finite(v))) fail('derived field magnitude overflow');
    let min=Infinity,max=-Infinity,xmin=Infinity,xmax=-Infinity,ymin=Infinity,ymax=-Infinity;
    for (const v of values) { min=Math.min(min,v);max=Math.max(max,v); }
    for (const [x,y] of nodes) { xmin=Math.min(xmin,x);xmax=Math.max(xmax,x);ymin=Math.min(ymin,y);ymax=Math.max(ymax,y); }
    if (![max-min,xmax-xmin,ymax-ymin].every(finite)||xmax<=xmin||ymax<=ymin)
      fail('display range overflow or degeneracy');
    return {nodes,triangles:a.triangles,values,min,max,unit,field,
      nodal:field==='temperature_k',domain:{xmin,xmax,ymin,ymax},lengthLabel:payload.lengthLabel,
      flux:a.heat_flux_w_m2};
  }
  function barycentric(p,a,b,c) {
    const det=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1]);
    const u=((b[1]-c[1])*(p[0]-c[0])+(c[0]-b[0])*(p[1]-c[1]))/det;
    const v=((c[1]-a[1])*(p[0]-c[0])+(a[0]-c[0])*(p[1]-c[1]))/det;
    return [u,v,1-u-v];
  }
  function sample(model, point) {
    for (let i=0;i<model.triangles.length;i++) {
      const tri=model.triangles[i], w=barycentric(point,...tri.map(n=>model.nodes[n]));
      if (w.every(v=>v>=-1e-10&&v<=1+1e-10))
        return model.nodal ? w.reduce((s,v,j)=>s+v*model.values[tri[j]],0) : model.values[i];
    }
    return null;
  }
  function transform(model,W,H) {
    const d=model.domain, s=Math.min((W-100)/(d.xmax-d.xmin),(H-85)/(d.ymax-d.ymin));
    if (!finite(s)||s<=0) fail('canvas too small');
    const cx=d.xmin+(d.xmax-d.xmin)/2,cy=d.ymin+(d.ymax-d.ymin)/2;
    return {s,X:x=>W/2+(x-cx)*s,Y:y=>H/2-(y-cy)*s,
      inverse:(x,y)=>[cx+(x-W/2)/s,cy-(y-H/2)/s]};
  }
  function color(v,min,max) {
    const t=max===min?.5:(v-min)/(max-min);
    return [Math.round(35+210*t),Math.round(90+65*(1-Math.abs(2*t-1))),Math.round(235-200*t)];
  }
  function draw(canvas,model,{meshOnly=false,arrows=true,current=()=>true}={}) {
    const rect=canvas.getBoundingClientRect(),W=Math.round(rect.width),H=Math.round(rect.height);
    if (!integer(W)||!integer(H)||W*H>4000000) fail('canvas pixel budget exceeded');
    const T=transform(model,W,H),ctx=canvas.getContext('2d'),image=ctx.createImageData(W,H);
    if (!meshOnly) {
      for (let i=0;i<model.triangles.length;i++) {
        const tri=model.triangles[i],pts=tri.map(n=>model.nodes[n]);
        const px=pts.map(p=>[T.X(p[0]),T.Y(p[1])]);
        const x0=Math.max(0,Math.floor(Math.min(...px.map(p=>p[0])))),x1=Math.min(W-1,Math.ceil(Math.max(...px.map(p=>p[0]))));
        const y0=Math.max(0,Math.floor(Math.min(...px.map(p=>p[1])))),y1=Math.min(H-1,Math.ceil(Math.max(...px.map(p=>p[1]))));
        for (let y=y0;y<=y1;y++) for (let x=x0;x<=x1;x++) {
          const w=barycentric(T.inverse(x+.5,y+.5),...pts);
          if (w.some(v=>v < -1e-10)) continue;
          const value=model.nodal?w.reduce((s,v,j)=>s+v*model.values[tri[j]],0):model.values[i];
          const rgb=color(value,model.min,model.max),k=4*(y*W+x);
          image.data.set([...rgb,255],k);
        }
      }
    }
    let maxQ=0;
    if(!meshOnly&&arrows&&!model.nodal)for(const q of model.flux)maxQ=Math.max(maxQ,Math.hypot(...q));
    if(!finite(maxQ))fail('arrow magnitude overflow');
    if (!current()) return false; // Deferred views must not commit stale pixels or labels.
    canvas.width=W;canvas.height=H;ctx.setTransform(1,0,0,1,0,0);ctx.clearRect(0,0,W,H);
    if (!meshOnly) ctx.putImageData(image,0,0);
    ctx.strokeStyle='rgba(40,45,60,.45)';ctx.lineWidth=.6;
    if (meshOnly) for (const tri of model.triangles) {
      ctx.beginPath();tri.forEach((n,j)=>j?ctx.lineTo(T.X(model.nodes[n][0]),T.Y(model.nodes[n][1])):ctx.moveTo(T.X(model.nodes[n][0]),T.Y(model.nodes[n][1])));
      ctx.closePath();ctx.stroke();
    }
    if (!meshOnly&&arrows&&!model.nodal&&maxQ>0) {
      ctx.strokeStyle='#17212b';ctx.lineWidth=1;
      const stride=Math.max(1,Math.ceil(model.triangles.length/180));
      for(let i=0;i<model.triangles.length;i+=stride) {
        const pts=model.triangles[i].map(n=>model.nodes[n]);
        const x=pts.reduce((s,p)=>s+p[0]/3,0),y=pts.reduce((s,p)=>s+p[1]/3,0);
        const [qx,qy]=model.flux[i],dx=22*qx/maxQ,dy=-22*qy/maxQ;
        const X=T.X(x),Y=T.Y(y),angle=Math.atan2(dy,dx);
        ctx.beginPath();ctx.moveTo(X,Y);ctx.lineTo(X+dx,Y+dy);
        ctx.moveTo(X+dx-5*Math.cos(angle-.5),Y+dy-5*Math.sin(angle-.5));ctx.lineTo(X+dx,Y+dy);
        ctx.lineTo(X+dx-5*Math.cos(angle+.5),Y+dy-5*Math.sin(angle+.5));ctx.stroke();
      }
    }
    ctx.fillStyle='#17212b';ctx.font='12px system-ui';ctx.textAlign='center';
    ctx.fillText('x ('+model.lengthLabel+'); y upward',W/2,H-12);
    ctx.textAlign='left';ctx.fillText(meshOnly?'Actual result mesh':model.field+' ['+model.unit+'] '+model.min+' … '+model.max,12,18);
    if (!meshOnly) {
      for(let i=0;i<100;i++){ctx.fillStyle='rgb('+color(model.min+(model.max-model.min)*i/99,model.min,model.max).join(',')+')';ctx.fillRect(12+i*1.5,27,2,10);}
      ctx.fillStyle='#17212b';ctx.fillText(model.max===model.min?'constant field':model.min+' … '+model.max+' '+model.unit,12,51);
      if(!model.nodal)ctx.fillText('Cell flux; arrows max 22 px (view only), global +y upward',12,H-31);
    }
    return true;
  }

  function createController({request,wait=ms=>new Promise(r=>setTimeout(r,ms)),onState=()=>{},onResult=()=>{}}) {
    const gate=new Ownership();let cap=null,result=null,error=null;
    function emit() { onState({supported:!!cap,busy:gate.busy,dirty:gate.dirty,validated:!!gate.validated,
      canRun:!!cap&&!gate.dirty&&!!gate.validated&&!gate.busy,result,error}); }
    function invalidate() { gate.invalidate();result=null;error=null;emit(); }
    async function loadCapability() {
      const seq=gate.beginCapability();
      try { const value=capability(await request('GET','/api/capabilities'));
        if(!gate.capabilityCurrent(seq))return;if(JSON.stringify(cap)!==JSON.stringify(value))invalidate();cap=value;
      } catch(e) { if(!gate.capabilityCurrent(seq))return;if(cap)invalidate();cap=null; }
      emit();
    }
    async function validate(doc, rawText) {
      if(!cap||soleType(doc)!==TYPE) { invalidate();return false; }
      const token=gate.begin('validate');result=null;error=null;gate.validated=null;gate.dirty=true;emit();
      try {
        const raw=rawText===undefined?JSON.stringify(doc):rawText;
        const parsed=strictParse(raw);if(soleType(parsed)!==TYPE)fail('unsupported raw document type');
        const reply=await request('POST',cap.validate,{doc:parsed,client_revision:token.revision,request_seq:token.sequence},raw);
        if(!gate.current(token))return false;
        if(reply?.ok!==true)fail(reply?.error?.message||'invalid document');
        if(reply.client_revision!==token.revision||reply.request_seq!==token.sequence||soleType(reply.doc)!==TYPE)
          fail('validation response ownership/type');
        gate.acceptValidation(token,reply.doc);return true;
      } catch(e) { if(gate.current(token)){error=String(e.message||e);gate.validated=null;gate.dirty=true;}return false; }
      finally { if(gate.finish(token))emit(); }
    }
    async function run() {
      if(!cap||gate.dirty||!gate.validated||gate.busy)return false;
      let token=gate.begin('run');result=null;error=null;emit();
      try {
        const reply=await request('POST',cap.run,{doc:clone(gate.validated),client_revision:token.revision,request_seq:token.sequence});
        if(!gate.current(token))return false;
        token=gate.bind(token,reply);
        while(gate.current(token)) {
          await wait(500);if(!gate.current(token))return false;
          const state=await request('GET','/api/jobs/'+encodeURIComponent(token.job));
          if(!gate.current(token))return false;
          if(!identity(state)||state.job!==token.job||state.result_id!==token.resultId
              ||state.client_revision!==token.revision||state.request_seq!==token.sequence)fail('status identity');
          if(state.status==='error')fail(state.error?.message||'thermal job failed');
          if(state.status==='done') {
            const raw=await request('GET','/api/jobs/'+encodeURIComponent(token.job)+'/result');
            if(!gate.current(token))return false;
            const accepted=validatePayload(raw,{job:token.job,result_id:token.resultId,
              client_revision:token.revision,request_seq:token.sequence});
            result=accepted;onResult(accepted);return true;
          }
          if(!['running','reserved'].includes(state.status))fail('unknown job status');
        }
        return false;
      } catch(e) { if(gate.current(token)){error=String(e.message||e);result=null;}return false; }
      finally { if(gate.finish(token))emit(); }
    }
    return {gate,invalidate,loadCapability,validate,run,supports:doc=>!!cap&&soleType(doc)===TYPE,
      result:()=>result,state:()=>({cap,result,error}),renderToken:field=>gate.renderToken(field),
      renderCurrent:t=>gate.renderCurrent(t)};
  }
  return {TYPE,PAIRS,BASE,ADDED,soleType,capability,validatePayload,Ownership,
    strictParse,viewModel,barycentric,sample,transform,color,draw,createController};
});
