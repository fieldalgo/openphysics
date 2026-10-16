// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Typed saved-time views only. No solver, interpolation or frame cache.
(function(root, factory) {
  if(typeof module==='object'&&module.exports)module.exports=factory(require('./thermal.js'));
  else root.TransientThermalStudio=factory(root.ThermalStudio);
})(typeof globalThis!=='undefined'?globalThis:this,function(T) {
  'use strict';
  const TYPE='thermal.transient2d',RESULT='thermal.transient2d-result-v1',LAYOUT='thermal2d-transient-p1-node-cell-v1';
  const UI=['temperature_k','heat_flux_w_m2','heat_content_j_per_m','quadratic_functional_jk_per_m'];
  const SPEC={
    nodes_m:['m','nodes','static'],triangles:['1','triangle_connectivity','static'],
    time_s:['s','requested_times','time_s'],temperature_k:['K','nodes','time_s'],
    heat_flux_w_m2:['W/m^2','triangle_centroids','time_s'],source_load_w_per_m:['W/m','nodes','time_s'],
    reaction_w_per_m:['W/m','nodes','time_s[1:]'],residual_w_per_m:['W/m','nodes','time_s[1:]'],
    storage_rate_w_per_m:['W/m','nodes','time_s[1:]'],heat_content_j_per_m:['J/m','domain','time_s'],
    quadratic_functional_jk_per_m:['J K/m','domain','time_s'],dirichlet_node_ids:['1','dirichlet_nodes','static'],
    dirichlet_temperatures_k:['K','dirichlet_nodes','time_s']
  };
  const object=x=>x!==null&&typeof x==='object'&&!Array.isArray(x);
  const finite=x=>typeof x==='number'&&Number.isFinite(x);
  const integer=x=>Number.isSafeInteger(x)&&x>=0;
  const id=x=>typeof x==='string'&&/^[a-zA-Z0-9_-]{1,160}$/.test(x);
  const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
  const fail=s=>{throw Error('Transient thermal view: '+s);};
  function copy(value) {
    const seen=new Set();
    function check(x){if(typeof x==='number'){if(!finite(x))fail('nonfinite JSON');return;}
      if(x===null||typeof x==='string'||typeof x==='boolean')return;
      if(!object(x)&&!Array.isArray(x))fail('invalid JSON value');
      if(seen.has(x))fail('cyclic JSON');seen.add(x);
      for(const v of Object.values(x))check(v);seen.delete(x);}
    check(value);return JSON.parse(JSON.stringify(value));
  }
  function keys(x,expected){return object(x)&&same(Object.keys(x).sort(),expected.slice().sort());}
  function identity(x){return object(x)&&x.kind===TYPE&&id(x.job)&&id(x.result_id)&&integer(x.client_revision)&&integer(x.request_seq);}
  function matches(x,e){if(!identity(x)||['job','result_id','client_revision','request_seq'].some(k=>x[k]!==e[k]))fail('response identity');}
  function typed(x,format){if(!identity(x)||x.payload_format!==format||x.result_format!==RESULT||x.field_layout!==LAYOUT
      ||!finite(x.display_length_in_m)||x.display_length_in_m<=0)fail('unsupported type/version/scale');}
  function capability(raw) {
    const c=raw?.[TYPE];
    if(raw?.capability_format!=='studio-capabilities-v1'||!object(c)||c.supported!==true||c.input!=='json'
        ||c.validate!=='/api/thermal/transient/validate'||c.run!=='/api/thermal/transient/run'
        ||c.mesh_preview!==false||c.mesh_from_result!==true||c.time_navigation!==true
        ||!same(c.result_formats,[RESULT])||!same(c.field_layouts,[LAYOUT])
        ||!Array.isArray(c.fields)||!UI.every(f=>c.fields.includes(f))||!object(c.limits))return null;
    const names=['request_bytes','max_nodes','max_triangles','max_times','raw_bytes','manifest_bytes',
      'frame_page_bytes','page_rows','terminal_bytes','terminal_jobs','active_jobs','read_encoding_slots'];
    if(names.some(k=>!integer(c.limits[k])||c.limits[k]<1)||c.limits.max_nodes<3||c.limits.max_times<2
        ||c.limits.page_rows>16||c.limits.read_encoding_slots!==1)return null;
    return copy(c);
  }
  function template(value,manifest,kind) {
    if(typeof value!=='string'||value.includes('#')||value.includes('\\'))fail('unsafe URL template');
    const parts=value.split('?'),path='/api/jobs/'+manifest.job+'/'+kind;
    if(parts.length!==2||parts[0]!==path)fail('URL path must match accepted job');
    const expected=kind==='frame'?['result_id','field','time_index','frame_seq']:['result_id','field','start','stop','frame_seq'];
    const pairs=parts[1].split('&'),seen=new Set();
    for(const pair of pairs){const p=pair.split('=');if(p.length!==2)fail('URL query');
      let key,v;try{key=decodeURIComponent(p[0]);v=decodeURIComponent(p[1]);}catch{fail('URL encoding');}
      if(seen.has(key)||!expected.includes(key))fail('URL duplicate/unknown query');seen.add(key);
      if(v!==(key==='result_id'?manifest.result_id:'{'+key+'}'))fail('URL placeholder or result identity');}
    if(seen.size!==expected.length)fail('incomplete URL template');
    return path;
  }
  function numeric(values,shape,label) {
    if(shape.length===0){if(!finite(values))fail(label+' finite scalar');return values;}
    if(!Array.isArray(values)||values.length!==shape[0])fail(label+' shape');
    return values.map(v=>numeric(v,shape.slice(1),label));
  }
  function manifest(raw,expected,limits) {
    const x=copy(raw);typed(x,'studio-thermal-transient-v1');matches(x,expected);
    if(!keys(x.arrays,['nodes_m','triangles','dirichlet_node_ids'])||!Array.isArray(x.time_s))fail('static arrays/time catalog');
    const times=x.time_s,nt=times.length,n=x.arrays.nodes_m?.length,m=x.arrays.triangles?.length,d=x.arrays.dirichlet_node_ids?.length;
    if(!integer(n)||n<3||n>limits.max_nodes||!integer(m)||m<1||m>limits.max_triangles||!integer(d)||d>n
        ||nt<2||nt>limits.max_times||times.some((v,i)=>!finite(v)||v<0||(i>0&&(!(v>times[i-1])||!finite(v-times[i-1]))))
        ||x.default_frame_index!==nt-1)fail('mesh/time counts or default final index');
    numeric(x.arrays.nodes_m,[n,2],'nodes');
    for(const tri of x.arrays.triangles){if(!Array.isArray(tri)||tri.length!==3||tri.some(v=>!integer(v)||v>=n)||new Set(tri).size!==3)fail('triangle index');
      const [a,b,c]=tri.map(i=>x.arrays.nodes_m[i]),det=(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
      if(!finite(det)||det<=0)fail('CCW finite geometry');}
    if(x.arrays.dirichlet_node_ids.some((v,i,a)=>!integer(v)||v>=n||(i&&v<=a[i-1])))fail('unique sorted fixed nodes');
    const shapes={nodes_m:[n,2],triangles:[m,3],time_s:[nt],temperature_k:[nt,n],heat_flux_w_m2:[nt,m,2],
      source_load_w_per_m:[nt,n],reaction_w_per_m:[nt-1,n],residual_w_per_m:[nt-1,n],storage_rate_w_per_m:[nt-1,n],
      heat_content_j_per_m:[nt],quadratic_functional_jk_per_m:[nt],dirichlet_node_ids:[d],dirichlet_temperatures_k:[nt,d]};
    const s=x.summary;
    if(!object(s)||s.physics_type!==TYPE||s.result_format!==RESULT||s.field_layout!==LAYOUT
        ||s.mesh?.nodes!==n||s.mesh?.triangles!==m||s.mesh_length_unit!=='m'||s.units?.temperature!=='K'
        ||s.units?.time!=='s'||!same(s.study?.time_s,times))fail('complete summary/catalog mismatch');
    let label=s.units.length;
    if(object(label)&&keys(label,['in_m'])&&finite(label.in_m)&&label.in_m>0)label=String(label.in_m)+' m';
    if(typeof label!=='string'||!label.length)fail('display length unit');
    if(!keys(x.fields,Object.keys(SPEC)))fail('13 field descriptors required');
    for(const meta of ['field_units','field_locations','field_shapes','field_time_axes'])if(!keys(s[meta],Object.keys(SPEC)))fail('summary field set');
    for(const [field,[unit,location,axis]]of Object.entries(SPEC)){
      const f=x.fields[field],staticField=axis==='static'||field==='time_s';
      if(!keys(f,['shape','unit','location','axis','available_views','initial_available','ui_supported'])
          ||!same(f.shape,shapes[field])||f.unit!==unit||f.location!==location||f.axis!==axis
          ||!same(f.available_views,staticField?[]:['frame','history'])
          ||f.initial_available!==(axis!=='time_s[1:]')||f.ui_supported!==UI.includes(field)
          ||s.field_units[field]!==unit||s.field_locations[field]!==location||s.field_time_axes[field]!==axis
          ||!same(s.field_shapes[field],shapes[field]))fail('descriptor/summary '+field);
    }
    template(x.frame_url,x,'frame');template(x.history_url,x,'history');
    x.lengthLabel=label;return x;
  }
  function queryURL(man,kind,query) {
    const path=template(kind==='frame'?man.frame_url:man.history_url,man,kind);
    const p=new URLSearchParams({result_id:man.result_id,...query});return path+'?'+p.toString();
  }
  function frame(raw,man,q) {
    const x=copy(raw);typed(x,'studio-thermal-transient-frame-v1');matches(x,man);
    const desc=man.fields[q.field];
    if(!['temperature_k','heat_flux_w_m2'].includes(q.field)||!integer(q.time_index)||q.time_index>=man.time_s.length
        ||!integer(q.frame_seq)||x.frame_seq!==q.frame_seq||x.field!==q.field||x.time_index!==q.time_index
        ||x.time_s!==man.time_s[q.time_index]||x.display_length_in_m!==man.display_length_in_m
        ||x.unit!==desc.unit||x.location!==desc.location||!same(x.shape,desc.shape.slice(1))
        ||!keys(x.arrays,[q.field]))fail('frame query/axis/field mismatch');
    numeric(x.arrays[q.field],x.shape,'frame');return x;
  }
  function history(raw,man,q) {
    const x=copy(raw);typed(x,'studio-thermal-transient-history-v1');matches(x,man);
    if(!['heat_content_j_per_m','quadratic_functional_jk_per_m'].includes(q.field)
        ||!integer(q.start)||!integer(q.stop)||q.stop<=q.start||q.stop>man.time_s.length||q.stop-q.start>16
        ||!integer(q.frame_seq))fail('history query');
    const desc=man.fields[q.field],indices=Array.from({length:q.stop-q.start},(_,i)=>i+q.start);
    if(x.field!==q.field||x.start!==q.start||x.stop!==q.stop||x.frame_seq!==q.frame_seq
        ||x.display_length_in_m!==man.display_length_in_m||!same(x.time_indices,indices)
        ||!same(x.time_s,man.time_s.slice(q.start,q.stop))||!same(x.shape,[indices.length])
        ||x.unit!==desc.unit||x.location!==desc.location||!keys(x.arrays,[q.field]))fail('history response identity/axis');
    numeric(x.arrays[q.field],x.shape,'history');return x;
  }
  function model(man,f,view) {
    const flux=view!=='temperature_k';
    if((flux?'heat_flux_w_m2':'temperature_k')!==f.field)fail('view field mismatch');
    return T.viewModel({arrays:{...man.arrays,...f.arrays},display_length_in_m:man.display_length_in_m,lengthLabel:man.lengthLabel},view);
  }
  function meshModel(man) {
    const p=man.arrays.nodes_m.map(v=>v.map(x=>x/man.display_length_in_m));
    if(p.some(v=>v.some(x=>!finite(x))))fail('display coordinates overflow');
    let xmin=Infinity,xmax=-Infinity,ymin=Infinity,ymax=-Infinity;
    for(const [x,y]of p){xmin=Math.min(xmin,x);xmax=Math.max(xmax,x);ymin=Math.min(ymin,y);ymax=Math.max(ymax,y);}
    if(!finite(xmax-xmin)||!finite(ymax-ymin)||xmax<=xmin||ymax<=ymin)fail('display range overflow');
    return {nodes:p,triangles:man.arrays.triangles,domain:{xmin,xmax,ymin,ymax},lengthLabel:man.lengthLabel,
      field:'Result mesh',unit:'m',min:0,max:0,nodal:true,values:[],flux:[]};
  }
  function createController({request,wait=ms=>new Promise(r=>setTimeout(r,ms)),onState=()=>{},onManifest=()=>{},onFrame=()=>{},onHistory=()=>{}}) {
    let cap=null,revision=0,op=0,capSeq=0,viewSeq=0,frameSeq=0,renderSeq=0;
    let validated=null,busy=false,dirty=true,man=null,accepted=null,error=null,index=null,view='temperature_k';
    let readActive=false,pending=null,readKind=null;const panes={};
    const state=()=>({cap,revision,op,busy,dirty,validated:!!validated,canRun:!!cap&&cap.run_enabled===true&&!dirty&&!!validated&&!busy,
      manifest:man,frame:accepted,index,view,error,readActive,readKind,pages:{...panes}});
    const emit=()=>onState(state());
    const token=()=>({revision,op,man,viewSeq});
    const current=t=>t.revision===revision&&t.op===op&&t.man===man&&t.viewSeq===viewSeq;
    function clearView(){accepted=null;error=null;renderSeq++;onFrame(null); }
    function invalidate() {
      revision++;op++;viewSeq++;renderSeq++;dirty=true;validated=null;busy=false;man=null;accepted=null;
      pending=null;index=null;error=null;for(const k of Object.keys(panes))delete panes[k];onFrame(null);emit();
    }
    async function loadCapability() {
      const seq=++capSeq;
      try { const c=capability(await request('GET','/api/capabilities'));
        if(seq!==capSeq)return;if(!same(c,cap))invalidate();cap=c;
      }catch {if(seq!==capSeq)return;if(cap)invalidate();cap=null;}
      emit();
    }
    async function validate(doc,rawText) {
      if(!cap||T.soleType(doc)!==TYPE){invalidate();return false;}
      op++;viewSeq++;dirty=true;validated=null;man=null;pending=null;for(const k of Object.keys(panes))delete panes[k];
      clearView();busy=true;const r=revision,o=op;emit();
      try {const parsed=T.strictParse(rawText===undefined?JSON.stringify(doc):rawText);
        if(T.soleType(parsed)!==TYPE)fail('raw document type');
        const reply=await request('POST',cap.validate,{doc:parsed,client_revision:r,request_seq:o},rawText===undefined?JSON.stringify(doc):rawText);
        if(r!==revision||o!==op)return false;
        if(reply?.ok!==true)fail(reply?.error?.message||'invalid document');
        if(reply.client_revision!==r||reply.request_seq!==o||T.soleType(reply.doc)!==TYPE)fail('validation ownership');
        validated=copy(reply.doc);dirty=false;return true;
      }catch(e){if(r===revision&&o===op){error=String(e.message||e);validated=null;dirty=true;}return false;}
      finally{if(r===revision&&o===op){busy=false;emit();}}
    }
    async function run() {
      if(!cap||cap.run_enabled!==true||dirty||!validated||busy)return false;
      op++;viewSeq++;man=null;pending=null;for(const k of Object.keys(panes))delete panes[k];clearView();busy=true;
      const r=revision,o=op;emit();const own=()=>r===revision&&o===op;
      try {const reply=await request('POST',cap.run,{doc:copy(validated),client_revision:r,request_seq:o});
        if(!own())return false;if(!identity(reply)||reply.client_revision!==r||reply.request_seq!==o)fail('run identity');
        while(own()){
          await wait(500);if(!own())return false;
          const status=await request('GET','/api/jobs/'+encodeURIComponent(reply.job));
          if(!own())return false;matches(status,reply);
          if(status.status==='error')fail(status.error?.message||'transient job failed');
          if(status.status==='done'){
            const raw=await request('GET','/api/jobs/'+encodeURIComponent(reply.job)+'/result');
            if(!own())return false;man=manifest(raw,reply,cap.limits);index=man.default_frame_index;view='temperature_k';
            onManifest(man);select(index,view);return true;
          }
          if(!['reserved','running'].includes(status.status))fail('unknown job status');
        }return false;
      }catch(e){if(own()){error=String(e.message||e);man=null;accepted=null;}return false;}
      finally{if(own()){busy=false;emit();}}
    }
    function select(i,field=view) {
      if(!man||!integer(i)||i>=man.time_s.length||!['temperature_k','qx','qy','magnitude'].includes(field))fail('saved index/field');
      index=i;view=field;viewSeq++;clearView();pending={kind:'frame',i,field,owner:token()};emit();void drain();return true;
    }
    function loadHistory(field,start,stop) {
      if(!man||!['heat_content_j_per_m','quadratic_functional_jk_per_m'].includes(field)||!integer(start)||!integer(stop)
          ||stop<=start||stop>man.time_s.length||stop-start>Math.min(16,cap.limits.page_rows))fail('history page');
      if(readActive||pending)return false; // Explicit action only: no automatic page fetching/queue.
      error=null;pending={kind:'history',field,start,stop,owner:token()};emit();void drain();return true;
    }
    async function drain() {
      if(readActive||!pending)return;
      const task=pending;pending=null;if(!current(task.owner))return;
      readActive=true;readKind=task.kind;const seq=++frameSeq,owner=task.owner;
      const q=task.kind==='frame'?{field:task.field==='temperature_k'?'temperature_k':'heat_flux_w_m2',time_index:task.i,frame_seq:seq}:
        {field:task.field,start:task.start,stop:task.stop,frame_seq:seq};
      emit();
      try {const raw=await request('GET',queryURL(owner.man,task.kind==='frame'?'frame':'history',q));
        if(!current(owner))return;
        if(task.kind==='frame'){accepted=frame(raw,owner.man,q);onFrame(accepted);}
        else {const page=history(raw,owner.man,q);panes[task.field]=page;onHistory(page);}
      }catch(e){if(current(owner)){error=String(e.message||e);if(task.kind==='frame'){accepted=null;onFrame(null);}}}
      finally {readActive=false;readKind=null;if(current(owner))emit();if(pending){emit();void drain();}}
    }
    function renderToken(){return {...token(),renderSeq:++renderSeq,frame:accepted};}
    function renderCurrent(t){return current(t)&&t.renderSeq===renderSeq&&t.frame===accepted;}
    return {loadCapability,validate,run,select,loadHistory,invalidate,state,result:()=>man,
      snapshot:()=>validated?copy(validated):null,supports:doc=>!!cap&&T.soleType(doc)===TYPE,
      renderToken,renderCurrent};
  }
  return {TYPE,RESULT,LAYOUT,UI,SPEC,copy,capability,template,queryURL,manifest,frame,history,model,meshModel,createController};
});
