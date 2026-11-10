// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Typed saved-time views only. No solver, interpolation or frame cache.
(function(root, factory) {
  if(typeof module==='object'&&module.exports)module.exports=factory(require('./thermal.js'));
  else root.TransientThermalStudio=factory(root.ThermalStudio);
})(typeof globalThis!=='undefined'?globalThis:this,function(T) {
  'use strict';
  const TYPE='thermal.transient2d',RESULT='thermal.transient2d-result-v3',LAYOUT='thermal2d-transient-p1-node-cell-v2';
  // Region documents: their own pair and manifest format; frames and pages keep their
  // format IDs and carry the region pair. Region documents are still format 0.2 until their
  // commit of the units batch, so their manifests keep the 0.2 names (LEGACY below).
  const RESULT_R='thermal.transient2d-regions-result-v1',LAYOUT_R='thermal2d-transient-p1-node-cell-regions-v1';
  const MANIFEST='studio-thermal-transient-v2',MANIFEST_R='studio-thermal-transient-regions-v1';
  const REGION_CAPABILITY={result_formats:[RESULT_R],field_layouts:[LAYOUT_R],
    payload_formats:[MANIFEST_R,'studio-thermal-transient-frame-v1','studio-thermal-transient-history-v1']};
  const REGION_FIELD={shape:null,unit:'1',location:'triangles',axis:'static',available_views:[],
    initial_available:true,ui_supported:false};
  // Rectangle documents are format 0.3: registry names, SI values; a structural array has no unit.
  const UI=['temperature','heat_flux','stored_heat_per_depth','thermal_energy_functional_per_depth'];
  const SPEC={
    node_coordinates:['m','nodes','static'],triangles:[null,'triangle_connectivity','static'],
    time:['s','requested_times','time'],temperature:['K','nodes','time'],
    heat_flux:['W/m^2','triangle_centroids','time'],generated_heat_rate_per_depth:['W/m','nodes','time'],
    reaction_heat_rate_per_depth:['W/m','nodes','time[1:]'],residual_heat_rate_per_depth:['W/m','nodes','time[1:]'],
    heat_storage_rate_per_depth:['W/m','nodes','time[1:]'],stored_heat_per_depth:['J/m','domain','time'],
    thermal_energy_functional_per_depth:['J K/m','domain','time'],prescribed_node_ids:[null,'prescribed_nodes','static'],
    prescribed_temperature:['K','prescribed_nodes','time']
  };
  const RECTANGLE={format:'0.3',result:RESULT,layout:LAYOUT,manifest:MANIFEST,
    frame:'studio-thermal-transient-frame-v2',history:'studio-thermal-transient-history-v2',spec:SPEC,ui:UI,
    nodes:'node_coordinates',fixed:'prescribed_node_ids',time:'time',rate:'time[1:]',
    temperature:'temperature',flux:'heat_flux',histories:['stored_heat_per_depth','thermal_energy_functional_per_depth']};
  const LEGACY={format:'0.2',result:'thermal.transient2d-result-v1',layout:'thermal2d-transient-p1-node-cell-v1',
    manifest:'studio-thermal-transient-v1',frame:'studio-thermal-transient-frame-v1',
    history:'studio-thermal-transient-history-v1',
    spec:{nodes_m:['m','nodes','static'],triangles:['1','triangle_connectivity','static'],
      time_s:['s','requested_times','time_s'],temperature_k:['K','nodes','time_s'],
      heat_flux_w_m2:['W/m^2','triangle_centroids','time_s'],source_load_w_per_m:['W/m','nodes','time_s'],
      reaction_w_per_m:['W/m','nodes','time_s[1:]'],residual_w_per_m:['W/m','nodes','time_s[1:]'],
      storage_rate_w_per_m:['W/m','nodes','time_s[1:]'],heat_content_j_per_m:['J/m','domain','time_s'],
      quadratic_functional_jk_per_m:['J K/m','domain','time_s'],dirichlet_node_ids:['1','dirichlet_nodes','static'],
      dirichlet_temperatures_k:['K','dirichlet_nodes','time_s']},
    ui:['temperature_k','heat_flux_w_m2','heat_content_j_per_m','quadratic_functional_jk_per_m'],
    nodes:'nodes_m',fixed:'dirichlet_node_ids',time:'time_s',rate:'time_s[1:]',
    temperature:'temperature_k',flux:'heat_flux_w_m2',histories:['heat_content_j_per_m','quadratic_functional_jk_per_m']};
  // View fields: 'temperature' (nodal) or the heat flux 'qx', 'qy', 'magnitude' (per cell).
  const VIEWS=['temperature','qx','qy','magnitude'];
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
  function typed(x,format,pair){if(!identity(x)||x.payload_format!==format||x.result_format!==pair[0]||x.field_layout!==pair[1]
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
  function manifest(raw,expected,limits) { return checkManifest(raw,expected,limits,RECTANGLE); }
  function checkManifest(raw,expected,limits,L) {
    const x=copy(raw);typed(x,L.manifest,[L.result,L.layout]);matches(x,expected);
    if(!keys(x,['kind','job','result_id','client_revision','request_seq','result_format','field_layout',
      'display_length_in_m','payload_format','default_frame_index',L.time,'arrays','summary','fields','frame_url','history_url',
      ...(L.format==='0.3'?['length_unit']:[])]))fail('manifest fields');
    if(!keys(x.arrays,[L.nodes,'triangles',L.fixed])||!Array.isArray(x[L.time]))fail('static arrays/time catalog');
    const times=x[L.time],nt=times.length,n=x.arrays[L.nodes]?.length,m=x.arrays.triangles?.length,d=x.arrays[L.fixed]?.length;
    if(!integer(n)||n<3||n>limits.max_nodes||!integer(m)||m<1||m>limits.max_triangles||!integer(d)||d>n
        ||nt<2||nt>limits.max_times||times.some((v,i)=>!finite(v)||v<0||(i>0&&(!(v>times[i-1])||!finite(v-times[i-1]))))
        ||x.default_frame_index!==nt-1)fail('mesh/time counts or default final index');
    numeric(x.arrays[L.nodes],[n,2],'nodes');
    for(const tri of x.arrays.triangles){if(!Array.isArray(tri)||tri.length!==3||tri.some(v=>!integer(v)||v>=n)||new Set(tri).size!==3)fail('triangle index');
      const [a,b,c]=tri.map(i=>x.arrays[L.nodes][i]),det=(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
      if(!finite(det)||det<=0)fail('CCW finite geometry');}
    if(x.arrays[L.fixed].some((v,i,a)=>!integer(v)||v>=n||(i&&v<=a[i-1])))fail('unique sorted fixed nodes');
    const shapes={};
    for(const [field,[,location,axis]]of Object.entries(L.spec)){
      const rows=location==='triangle_connectivity'||location==='triangle_centroids'?m:location.endsWith('_nodes')?d
        :location==='domain'||location==='requested_times'?null:n;
      const cols=field===L.nodes?[2]:field==='triangles'?[3]:field===L.flux?[2]:[];
      const shape=rows===null?[]:[rows,...cols];
      shapes[field]=axis==='static'?shape:[axis===L.rate?nt-1:nt,...shape];
    }
    const s=x.summary;
    if(!object(s)||s.physics_type!==TYPE||s.result_format!==L.result||s.field_layout!==L.layout
        ||s.mesh?.nodes!==n||s.mesh?.triangles!==m)fail('complete summary/catalog mismatch');
    let label;
    if(L.format==='0.3'){
      // The geometry's length_unit names the display unit; the summary's inputs agree with it.
      label=x.length_unit;
      if(s.study?.time?.unit!=='s'||!same(s.study?.time?.values,times)
          ||typeof label!=='string'||!label.length
          ||s.resolved_inputs?.['geometry.domain.xmin']?.length_unit!==label)fail('complete summary/catalog mismatch');
    } else {
      if(s.mesh_length_unit!=='m'||s.units?.temperature!=='K'||s.units?.time!=='s'||!same(s.study?.time_s,times))
        fail('complete summary/catalog mismatch');
      label=s.units.length;
      if(object(label)&&keys(label,['in_m'])&&finite(label.in_m)&&label.in_m>0)label=String(label.in_m)+' m';
      if(typeof label!=='string'||!label.length)fail('display length unit');
    }
    const fields=Object.keys(L.spec);
    if(!keys(x.fields,fields))fail('13 field descriptors required');
    const unitKeys=fields.filter(f=>L.spec[f][0]!==null),axisKeys=L.format==='0.3'?fields.filter(f=>L.spec[f][2]!=='static'):fields;
    for(const [meta,expect] of [['field_units',unitKeys],['field_locations',fields],['field_shapes',fields],['field_time_axes',axisKeys]])
      if(!keys(s[meta],expect))fail('summary field set');
    for(const [field,[unit,location,axis]]of Object.entries(L.spec)){
      const f=x.fields[field],staticField=axis==='static'||field===L.time;
      if(!keys(f,['shape','unit','location','axis','available_views','initial_available','ui_supported'])
          ||!same(f.shape,shapes[field])||f.unit!==unit||f.location!==location||f.axis!==axis
          ||!same(f.available_views,staticField?[]:['frame','history'])
          ||f.initial_available!==(axis!==L.rate)||f.ui_supported!==L.ui.includes(field)
          ||(unit===null?Object.hasOwn(s.field_units,field):s.field_units[field]!==unit)
          ||s.field_locations[field]!==location
          ||(axis==='static'&&L.format==='0.3'?Object.hasOwn(s.field_time_axes,field):s.field_time_axes[field]!==axis)
          ||!same(s.field_shapes[field],shapes[field]))fail('descriptor/summary '+field);
    }
    template(x.frame_url,x,'frame');template(x.history_url,x,'history');
    x.lengthLabel=label;
    // the layout and time catalog of this manifest, for frames, pages and views
    Object.defineProperty(x,'layout',{value:L});Object.defineProperty(x,'times',{value:times});
    return x;
  }
  function regionManifest(raw,expected,limits,regionLimits=null) {
    const x=copy(raw),s=x?.summary,metadata=['field_units','field_locations','field_shapes','field_time_axes'];
    if(!object(x)||x.payload_format!==MANIFEST_R||x.result_format!==RESULT_R||x.field_layout!==LAYOUT_R
        ||!object(s)||s.result_format!==RESULT_R||s.field_layout!==LAYOUT_R)fail('unsupported region manifest or pair');
    if(!object(x.arrays)||!Object.hasOwn(x.arrays,'triangle_regions')||!object(x.fields)||!Object.hasOwn(x.fields,'triangle_regions')
        ||metadata.some(m=>!object(s[m])||!Object.hasOwn(s[m],'triangle_regions')))fail('missing triangle_regions');
    // Relabel a copy as a 0.2 rectangle manifest, summary pair included, and reuse every
    // unchanged rectangle check.
    const rect=copy(x);rect.payload_format=LEGACY.manifest;rect.result_format=rect.summary.result_format=LEGACY.result;
    rect.field_layout=rect.summary.field_layout=LEGACY.layout;
    delete rect.arrays.triangle_regions;delete rect.fields.triangle_regions;
    for(const m of metadata)delete rect.summary[m].triangle_regions;
    const accepted=checkManifest(rect,expected,limits,LEGACY),m=accepted.arrays.triangles.length;
    if(!same(x.fields.triangle_regions,{...REGION_FIELD,shape:[m]})||s.field_units.triangle_regions!=='1'
        ||s.field_locations.triangle_regions!=='triangles'||s.field_time_axes.triangle_regions!=='static'
        ||!same(s.field_shapes.triangle_regions,[m]))fail('triangle_regions descriptor');
    const table=T.regionTable(s,x.arrays.triangle_regions,m,true,regionLimits);
    const edges=T.regionEdges(accepted.arrays.triangles,table.ids,accepted.arrays.nodes_m.length);
    const out={...accepted,payload_format:MANIFEST_R,result_format:RESULT_R,field_layout:LAYOUT_R,
      fields:x.fields,summary:s,regions:Object.freeze({...table,edges})};
    Object.defineProperty(out,'layout',{value:LEGACY});Object.defineProperty(out,'times',{value:accepted.times});
    return out;
  }
  function queryURL(man,kind,query) {
    const path=template(kind==='frame'?man.frame_url:man.history_url,man,kind);
    const p=new URLSearchParams({result_id:man.result_id,...query});return path+'?'+p.toString();
  }
  function frame(raw,man,q) {
    const L=man.layout,x=copy(raw);typed(x,L.frame,[man.result_format,man.field_layout]);matches(x,man);
    if(!keys(x,['kind','job','result_id','client_revision','request_seq','result_format','field_layout',
      'display_length_in_m','payload_format','frame_seq','field','time_index',L.time,'unit','location','shape','arrays']))fail('frame fields');
    const desc=man.fields[q.field];
    if(![L.temperature,L.flux].includes(q.field)||!integer(q.time_index)||q.time_index>=man.times.length
        ||!integer(q.frame_seq)||x.frame_seq!==q.frame_seq||x.field!==q.field||x.time_index!==q.time_index
        ||x[L.time]!==man.times[q.time_index]||x.display_length_in_m!==man.display_length_in_m
        ||x.unit!==desc.unit||x.location!==desc.location||!same(x.shape,desc.shape.slice(1))
        ||!keys(x.arrays,[q.field]))fail('frame query/axis/field mismatch');
    numeric(x.arrays[q.field],x.shape,'frame');return x;
  }
  function history(raw,man,q) {
    const L=man.layout,x=copy(raw);typed(x,L.history,[man.result_format,man.field_layout]);matches(x,man);
    if(!keys(x,['kind','job','result_id','client_revision','request_seq','result_format','field_layout',
      'display_length_in_m','payload_format','frame_seq','field','start','stop','time_indices',L.time,'unit','location','shape','arrays']))fail('history fields');
    if(!L.histories.includes(q.field)
        ||!integer(q.start)||!integer(q.stop)||q.stop<=q.start||q.stop>man.times.length||q.stop-q.start>16
        ||!integer(q.frame_seq))fail('history query');
    const desc=man.fields[q.field],indices=Array.from({length:q.stop-q.start},(_,i)=>i+q.start);
    if(x.field!==q.field||x.start!==q.start||x.stop!==q.stop||x.frame_seq!==q.frame_seq
        ||x.display_length_in_m!==man.display_length_in_m||!same(x.time_indices,indices)
        ||!same(x[L.time],man.times.slice(q.start,q.stop))||!same(x.shape,[indices.length])
        ||x.unit!==desc.unit||x.location!==desc.location||!keys(x.arrays,[q.field]))fail('history response identity/axis');
    numeric(x.arrays[q.field],x.shape,'history');return x;
  }
  function model(man,f,view) {
    const L=man.layout,flux=view!=='temperature';
    if((flux?L.flux:L.temperature)!==f.field)fail('view field mismatch');
    const payload={arrays:{...man.arrays,...f.arrays},display_length_in_m:man.display_length_in_m,lengthLabel:man.lengthLabel};
    if(man.regions)payload.regions=man.regions;
    return T.viewModel(payload,view);
  }
  function meshModel(man) {
    const p=T.named(man.arrays).nodes.map(v=>v.map(x=>x/man.display_length_in_m));
    if(p.some(v=>v.some(x=>!finite(x))))fail('display coordinates overflow');
    let xmin=Infinity,xmax=-Infinity,ymin=Infinity,ymax=-Infinity;
    for(const [x,y]of p){xmin=Math.min(xmin,x);xmax=Math.max(xmax,x);ymin=Math.min(ymin,y);ymax=Math.max(ymax,y);}
    if(!finite(xmax-xmin)||!finite(ymax-ymin)||xmax<=xmin||ymax<=ymin)fail('display range overflow');
    const mesh={nodes:p,triangles:man.arrays.triangles,domain:{xmin,xmax,ymin,ymax},lengthLabel:man.lengthLabel,
      field:'Result mesh',unit:'m',min:0,max:0,nodal:true,values:[],flux:[]};
    if(man.regions)mesh.regions=man.regions;
    return mesh;
  }
  function createController({request,wait=ms=>new Promise(r=>setTimeout(r,ms)),onState=()=>{},onManifest=()=>{},onFrame=()=>{},onHistory=()=>{}}) {
    let cap=null,revision=0,op=0,capSeq=0,viewSeq=0,frameSeq=0,renderSeq=0;
    let validated=null,busy=false,dirty=true,man=null,accepted=null,error=null,index=null,view='temperature';
    let readActive=false,pending=null,readKind=null,family=null;const panes={};
    const regionCap=()=>cap?T.regionCapability(cap.regions,REGION_CAPABILITY):null;
    const familyRuns=()=>family!=='regions'||regionCap()?.run_enabled===true;
    const state=()=>({cap,revision,op,busy,dirty,validated:!!validated,
      canRun:!!cap&&cap.run_enabled===true&&!dirty&&!!validated&&!busy&&familyRuns(),
      manifest:man,frame:accepted,index,view,error,readActive,readKind,pages:{...panes}});
    const emit=()=>onState(state());
    const token=()=>({revision,op,man,viewSeq});
    const current=t=>t.revision===revision&&t.op===op&&t.man===man&&t.viewSeq===viewSeq;
    function clearView(){accepted=null;error=null;renderSeq++;onFrame(null); }
    function invalidate() {
      revision++;op++;viewSeq++;renderSeq++;dirty=true;validated=null;busy=false;man=null;accepted=null;
      pending=null;index=null;error=null;family=null;for(const k of Object.keys(panes))delete panes[k];onFrame(null);emit();
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
      op++;viewSeq++;dirty=true;validated=null;man=null;pending=null;family=null;for(const k of Object.keys(panes))delete panes[k];
      clearView();busy=true;const r=revision,o=op;emit();
      try {const parsed=T.strictParse(rawText===undefined?JSON.stringify(doc):rawText);
        if(T.soleType(parsed)!==TYPE)fail('raw document type');
        // The document family is pinned here, before any request; its manifest must match.
        const kind=T.hasRegionGeometry(parsed,TYPE)?'regions':'rectangle';
        if(kind==='regions'&&!regionCap())fail('this Studio server does not advertise region documents');
        family=kind;
        const reply=await request('POST',cap.validate,{doc:parsed,client_revision:r,request_seq:o},rawText===undefined?JSON.stringify(doc):rawText);
        if(r!==revision||o!==op)return false;
        if(reply?.ok!==true)fail(reply?.error?.message||'invalid document');
        if(reply.client_revision!==r||reply.request_seq!==o||T.soleType(reply.doc)!==TYPE
            ||(T.hasRegionGeometry(reply.doc,TYPE)?'regions':'rectangle')!==kind)fail('validation ownership');
        validated=copy(reply.doc);dirty=false;return true;
      }catch(e){if(r===revision&&o===op){error=String(e.message||e);validated=null;dirty=true;}return false;}
      finally{if(r===revision&&o===op){busy=false;emit();}}
    }
    async function run() {
      if(!cap||cap.run_enabled!==true||dirty||!validated||busy||!familyRuns())return false;
      const kind=family;
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
            if(!own())return false;
            // A manifest of the other family is refused by the other parser.
            man=kind==='regions'?regionManifest(raw,reply,cap.limits,regionCap()?.limits):manifest(raw,reply,cap.limits);
            index=man.default_frame_index;view='temperature';
            onManifest(man);select(index,view);return true;
          }
          if(!['reserved','running'].includes(status.status))fail('unknown job status');
        }return false;
      }catch(e){if(own()){error=String(e.message||e);man=null;accepted=null;}return false;}
      finally{if(own()){busy=false;emit();}}
    }
    function select(i,field=view) {
      if(!man||!integer(i)||i>=man.times.length||!VIEWS.includes(field))fail('saved index/field');
      index=i;view=field;viewSeq++;clearView();pending={kind:'frame',i,field,owner:token()};emit();void drain();return true;
    }
    function loadHistory(field,start,stop) {
      if(!man||!man.layout.histories.includes(field)||!integer(start)||!integer(stop)
          ||stop<=start||stop>man.times.length||stop-start>Math.min(16,cap.limits.page_rows))fail('history page');
      if(readActive||pending)return false; // Explicit action only: no automatic page fetching/queue.
      error=null;pending={kind:'history',field,start,stop,owner:token()};emit();void drain();return true;
    }
    async function drain() {
      if(readActive||!pending)return;
      const task=pending;pending=null;if(!current(task.owner))return;
      readActive=true;readKind=task.kind;const seq=++frameSeq,owner=task.owner;
      const L=owner.man.layout;
      const q=task.kind==='frame'?{field:task.field==='temperature'?L.temperature:L.flux,time_index:task.i,frame_seq:seq}:
        {field:task.field,start:task.start,stop:task.stop,frame_seq:seq};
      emit();
      try {const raw=await request('GET',queryURL(owner.man,task.kind==='frame'?'frame':'history',q));
        if(!current(owner))return;
        if(task.kind==='frame'){
          const candidate=frame(raw,owner.man,q);
          model(owner.man,candidate,task.field); // A derived view is not accepted merely because its raw row is finite.
          accepted=candidate;onFrame(accepted);
        }
        else {const page=history(raw,owner.man,q);panes[task.field]=page;onHistory(page);}
      }catch(e){if(current(owner)){error=String(e.message||e);if(task.kind==='frame'){accepted=null;onFrame(null);}}}
      finally {readActive=false;readKind=null;if(current(owner))emit();if(pending){emit();void drain();}}
    }
    function renderToken(){return {...token(),renderSeq:++renderSeq,frame:accepted};}
    function renderCurrent(t){return current(t)&&t.renderSeq===renderSeq&&t.frame===accepted;}
    function rejectView(t,message){
      if(!renderCurrent(t)||!accepted)return false;
      accepted=null;error=String(message);renderSeq++;onFrame(null);emit();return true;
    }
    return {loadCapability,validate,run,select,loadHistory,invalidate,state,result:()=>man,
      snapshot:()=>validated?copy(validated):null,supports:doc=>!!cap&&T.soleType(doc)===TYPE,
      renderToken,renderCurrent,rejectView};
  }
  return {TYPE,RESULT,LAYOUT,UI,SPEC,VIEWS,RECTANGLE,LEGACY,copy,capability,template,queryURL,manifest,frame,history,model,
    meshModel,createController,RESULT_R,LAYOUT_R,MANIFEST_R,regionManifest};
});
