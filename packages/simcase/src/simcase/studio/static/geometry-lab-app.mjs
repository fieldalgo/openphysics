// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// The experimental geometry lab page: holds one version 1 document, sends it whole to the
// exact engine on every edit, and draws what the engine answers.
import {areaLabel,cellPath,copyDocument,curvePath,highlightOf,isVersion1,newDocument,refusalText,
 quantityOf,regionColor,saveName,serializeDocument,setParameter,sliderOf,sliderValue,viewTransform} from './geometry-lab-model.mjs';
import {STARTERS} from './geometry-lab-starters.mjs';
import {View3D} from '/model3d-assets/model3d-view.mjs';
import {faceLines,regionColor as regionColor3d,sectionRange} from '/model3d-assets/model3d-model.mjs';
import {MeshView3D} from '/model3d-assets/model3d-mesh-view.mjs';
import {CANCELLED,estimateText,longer,meshBlocked,progressText,statsRows,stepList} from '/model3d-assets/model3d-mesh-model.mjs';

const $=id=>document.getElementById(id);
const SVG='http://www.w3.org/2000/svg';
const state={doc:null,component:null,view:null,highlight:null,request:0,mode:'2d',view3d:null,face:null,hidden:new Set(),section:0};
let viewer=null;
// the mesh job (experimental): its estimate, the running job and the mesh view
const mesh={estimate:null,refused:null,key:null,job:null,timer:null,view:null,viewer:null,request:0,shownFace:null,shownHidden:''};

function el(tag,attrs={},text){
 const e=tag.startsWith('svg:')?document.createElementNS(SVG,tag.slice(4)):document.createElement(tag);
 for(const [k,v] of Object.entries(attrs))e.setAttribute(k,v);
 if(text!==undefined)e.textContent=text;
 return e;
}
function status(text){$('status').textContent=text;}

/** Whether the shown component is a 3d one: the named one, or the document has no 2D component. */
function is3d(){
 const comps=state.doc?.geometry?.components||{};
 if(state.component&&comps[state.component])return comps[state.component].dimension==='3d';
 const names=Object.keys(comps);
 return names.length>0&&names.every(n=>comps[n]?.dimension==='3d');
}

function setMode(mode){
 state.mode=mode;
 $('view').toggleAttribute('hidden',mode!=='2d');$('view3d').hidden=mode!=='3d';
 $('faces').hidden=$('faces-heading').hidden=mode!=='3d';
}

async function evaluate(){
 if(is3d())return evaluate3d();
 const id=++state.request;
 status('Evaluating…');
 let response,body;
 try{
  response=await fetch('/api/geometry-lab/evaluate',{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({doc:state.doc,component:state.component})});
  body=await response.json().catch(()=>null);
 }catch(error){if(id===state.request)refuse('The Studio server could not be reached: '+error.message);return;}
 if(id!==state.request)return;            // a later edit is already on its way
 if(!response.ok||!body||body.ok!==true){refuse(refusalText(response.status,body));return;}
 state.view=body;state.component=body.component;
 $('refusal').hidden=true;$('view').classList.remove('stale');
 setMode('2d');
 render();
 status(`Evaluated ${body.component}: ${body.regions.length} regions, ${body.cells.length} cells, ${body.curves.length} curves.`);
}

function refuse(text){
 ++state.request;                         // an answer already on its way must not hide this
 $('refusal').textContent='Refused: '+text;$('refusal').hidden=false;
 $('view').classList.add('stale');$('canvas3d').classList.add('stale');
 status(state.view||state.view3d?'Not evaluated: the drawing shows the last accepted document.':'Not evaluated.');
}

function load(doc){
 if(!isVersion1(doc)){refuse('the document has no version 1 geometry block; this lab reads only version 1 documents.');return;}
 state.doc=copyDocument(doc);state.component=null;state.view=null;state.highlight=null;
 state.view3d=null;state.face=null;state.hidden=new Set();
 $('section-axis').value='';sectionControls();
 $('save-file').disabled=false;
 renderParameters();evaluate();
}

function renderParameters(){
 const rows=$('parameter-rows');rows.replaceChildren();
 const params=Object.entries(state.doc.geometry.parameters||{});
 $('no-parameters').hidden=params.length>0;
 for(const [name,entry] of params){
  const box=el('div',{class:'param'});
  const text=el('input',{type:'text',id:'param-'+name,'aria-label':name,spellcheck:'false'});
  text.value=String(entry.value);
  box.append(el('label',{for:'param-'+name},name),text);
  const slider=sliderOf({written:entry.value,range:entry.range});
  let range=null;
  if(slider){
   range=el('input',{type:'range',min:slider.min,max:slider.max,step:slider.step,'aria-label':name+' slider'});
   const unit=slider.unit?' '+slider.unit:'';
   range.value=String(slider.unit?quantityOf(entry.value).number:entry.value);
   range.addEventListener('input',()=>{const v=sliderValue(slider,range.value);text.value=String(v)+unit;edit(name,String(v)+unit);});
   box.append(range,el('small',{},`range ${slider.min} … ${slider.max}${unit}`));
  }
  text.addEventListener('change',()=>{
   const ok=edit(name,text.value),held=state.doc.geometry.parameters[name].value;
   if(!ok)text.value=String(held);        // the field shows what the document holds; the refusal says why
   else if(range)range.value=String(typeof held==='number'?held:quantityOf(held)?.number??range.value);
  });
  box.append(el('small',{class:'evaluated',id:'value-'+name}));
  rows.append(box);
 }
}

function edit(name,value){
 try{state.doc=setParameter(state.doc,name,value);}catch(error){refuse(error.message);return false;}
 evaluate();return true;
}

function render(){
 const v=state.view,svg=$('view');
 const view=viewTransform(v.domain,800,560);
 const lit=highlightOf(v,state.highlight);   // looked up by key in this answer
 svg.replaceChildren();
 for(const cell of v.cells){
  const cls='cell'+(cell.void?' void':'')+(lit.cells.has(cell.index)?' lit':'');
  const p=el('svg:path',{class:cls,d:cellPath(cell,v.curves,view),'data-cell':cell.index});
  if(!cell.void)p.setAttribute('fill',regionColor(v,cell.region));
  p.append(el('svg:title',{},`${cell.region} (cell ${cell.index}, ${cell.material===null?'void':cell.material})`));
  svg.append(p);
 }
 for(const curve of v.curves){
  const p=el('svg:path',{class:'curve'+(lit.curves.has(curve.index)?' lit':''),d:curvePath(curve.points,view),'data-curve':curve.index});
  p.append(el('svg:title',{},`curve ${curve.index}: ${curve.provenance.join(' ')}${curve.tag?' · tag '+curve.tag:''}`));
  svg.append(p);
 }
 $('unit').textContent=`${v.component} (${v.dimension}) · lengths in ${v.unit}`;
 // format 0.3 parameters are evaluated in SI (p.unit "m"); format 0.2 ones in the component unit
 for(const p of v.parameters){const e=$('value-'+p.name);if(e)e.textContent=`= ${p.value} ${p.kind==='length'?p.unit??v.unit:''}`;}
 const select=$('component');select.replaceChildren(...v.components.map(n=>{const o=el('option',{value:n},n);o.selected=n===v.component;return o;}));
 select.disabled=v.components.length<2;
 list('regions',v.regions.map(r=>({key:'region:'+r.name,swatch:r.void?null:regionColor(v,r.name),
  label:r.name,detail:`${r.void?'void':r.material} · ${areaLabel(r.area,v.unit)}`})));
 list('selections',v.selections.map(s=>({key:'selection:'+s.name,label:s.name,detail:`${s.kind} · ${s.entries.length}`})),'No named selections.');
 list('tags',v.tags.map(t=>({key:'tag:'+t.tag,label:t.tag,detail:`${t.curves.length} curves`})));
 $('summary').textContent=v.summary;
}

function list(id,rows,empty='None.'){
 const ul=$(id);ul.replaceChildren();
 if(!rows.length){ul.append(el('li',{class:'muted'},empty));return;}
 for(const row of rows){
  const li=el('li',{'data-key':row.key,tabindex:'0'});
  if(state.highlight===row.key)li.classList.add('active');
  if(row.swatch!==undefined){const s=el('span',{class:'swatch'+(row.swatch?'':' void')});if(row.swatch)s.style.background=row.swatch;li.append(s);}
  li.append(el('code',{},row.label),el('small',{},row.detail));
  const pick=()=>{state.highlight=state.highlight===row.key?null:row.key;render();};
  li.addEventListener('click',pick);
  li.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();pick();}});
  ul.append(li);
 }
}

$('starter').addEventListener('change',async()=>{
 const key=$('starter').value;if(!key)return;
 if(key==='model3d_via_stack'){
  try{load(await (await fetch('/model3d-assets/model3d-via-stack.json')).json());}
  catch(error){refuse('The 3D example could not be loaded: '+error.message);}
  return;
 }
 load(key==='new'?newDocument():STARTERS[key]);
});
$('open-file').addEventListener('click',()=>$('file').click());
$('file').addEventListener('change',async()=>{
 const file=$('file').files[0];if(!file)return;
 try{load(JSON.parse(await file.text()));}catch(error){refuse(`${file.name} is not JSON: ${error.message}`);}
 $('file').value='';
});
$('component').addEventListener('change',()=>{state.component=$('component').value;state.highlight=null;state.face=null;evaluate();});
$('save-file').addEventListener('click',()=>{
 const blob=new Blob([serializeDocument(state.doc)],{type:'application/json'});
 const url=URL.createObjectURL(blob),a=el('a',{href:url,download:saveName(state.doc)});
 document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
 status('Saved '+saveName(state.doc)+' (the document as edited, version 1 geometry).');
});

// ---- the 3D view (experimental): /api/model3d/display and /api/model3d/section ------------

async function evaluate3d(){
 const id=++state.request;
 status('Evaluating…');
 let response,body;
 try{
  response=await fetch('/api/model3d/display',{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({doc:state.doc,component:state.component})});
  body=await response.json().catch(()=>null);
 }catch(error){if(id===state.request)refuse('The Studio server could not be reached: '+error.message);return;}
 if(id!==state.request)return;
 if(!response.ok||!body||body.ok!==true){refuse(refusalText(response.status,body));return;}
 const same=state.view3d&&state.view3d.component===body.component;
 state.view3d=body;state.component=body.component;
 if(!same){state.face=null;state.hidden=new Set();$('section-axis').value='';}
 $('refusal').hidden=true;$('canvas3d').classList.remove('stale');
 setMode('3d');
 if(!viewer)viewer=new View3D($('canvas3d'),{onPick:face=>{state.face=face;render3d();},
  onCamera:what=>{$('canvas3d').dataset.camera=what;}});
 viewer.setHidden([...state.hidden]);
 viewer.load(body,{keep:same});
 viewer.select(state.face);
 sectionControls(same);
 render3d();
 estimate3d();
 status(`Shown ${body.component} (3d): ${body.regions.length} regions, ${body.faces.length} faces, ${body.counts.triangles} triangles.`);
}

// ---- the mesh job (experimental): /api/model3d/mesh/estimate, /api/model3d/mesh, /api/model3d/jobs/…

async function estimate3d(){
 const id=++mesh.request;
 let response,body;
 try{
  response=await fetch('/api/model3d/mesh/estimate',{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({doc:state.doc,component:state.component})});
  body=await response.json().catch(()=>null);
 }catch(error){if(id===mesh.request){mesh.estimate=null;mesh.refused='The Studio server could not be reached: '+error.message;renderMesh();}return;}
 if(id!==mesh.request)return;
 if(response.ok&&body?.ok===true){mesh.estimate=body.estimate;mesh.refused=null;mesh.key=body.key;}
 else{mesh.estimate=null;mesh.refused=refusalText(response.status,body);mesh.key=null;}
 renderMesh();
}

function renderMesh(){
 const blocked=meshBlocked({estimate:mesh.estimate,refused:mesh.refused,running:!!mesh.job});
 const start=$('mesh-start');start.disabled=!!blocked;start.title=blocked||'Mesh this component in a separate process';
 $('mesh-estimate').textContent=mesh.refused?'Mesh is not available: '+mesh.refused:mesh.estimate?estimateText(mesh.estimate):'Show a 3d component first.';
 $('mesh-cancel').hidden=!mesh.job;
 const stale=!!(mesh.view&&mesh.key!==mesh.view.key);
 $('canvas-mesh').classList.toggle('stale',stale);
 const note=$('mesh-note');note.hidden=!stale;
 note.textContent=stale?'The mesh view shows an earlier geometry or mesh block; mesh again to update it.':'';
}

function renderSteps(s){
 const ol=$('mesh-steps');ol.hidden=false;
 ol.replaceChildren(...stepList(s).map(step=>{const li=el('li',{class:step.state},step.label);if(step.state==='current')li.setAttribute('aria-current','step');return li;}));
 const p=$('mesh-progress');p.textContent=progressText(s);p.classList.toggle('longer',longer(s));
}

async function startMesh(){
 let response,body;
 $('mesh-start').disabled=true;
 try{
  response=await fetch('/api/model3d/mesh',{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({doc:state.doc,component:state.component})});
  body=await response.json().catch(()=>null);
 }catch(error){$('mesh-progress').textContent='The Studio server could not be reached: '+error.message;renderMesh();return;}
 if(!response.ok||!body?.job){$('mesh-progress').textContent=body?.detail||refusalText(response.status,body);renderMesh();return;}
 mesh.job=body.job;
 if(body.status==='done'){await meshDone(body.job,{status:'done',step:'ready',reused:true,expected_s:body.estimate.seconds,elapsed_s:0});return;}
 renderSteps({status:'running',step:'forming',expected_s:body.estimate.seconds,elapsed_s:0});
 renderMesh();
 poll(body.job);
}

function poll(job){
 clearTimeout(mesh.timer);
 mesh.timer=setTimeout(async()=>{
  if(mesh.job!==job)return;
  let s;
  try{const r=await fetch(`/api/model3d/jobs/${encodeURIComponent(job)}`);s=await r.json();if(!r.ok)throw new Error(s?.detail||r.status);}
  catch(error){if(mesh.job===job){$('mesh-progress').textContent='Lost the mesh job: '+error.message;mesh.job=null;renderMesh();}return;}
  if(mesh.job!==job)return;
  if(s.status==='running'){renderSteps(s);poll(job);return;}
  if(s.status==='done'){await meshDone(job,s);return;}
  renderSteps(s);mesh.job=null;renderMesh();
 },400);
}

async function meshDone(job,s){
 let view;
 try{const r=await fetch(`/api/model3d/jobs/${encodeURIComponent(job)}/result`);view=await r.json();if(!r.ok)throw new Error(view?.detail||r.status);}
 catch(error){$('mesh-progress').textContent='The mesh could not be read: '+error.message;mesh.job=null;renderMesh();return;}
 if(mesh.job!==job)return;
 mesh.job=null;
 renderSteps(s);
 showMesh(view);
 renderMesh();
}

function showMesh(view){
 mesh.view=view;
 const canvas=$('canvas-mesh');canvas.hidden=false;
 if(!mesh.viewer)mesh.viewer=new MeshView3D(canvas,{onPick:face=>{if(mesh.view?.component!==state.view3d?.component)return;state.face=face;viewer?.select(face);render3d();},
  onCamera:what=>{canvas.dataset.camera=what;}});
 mesh.viewer.setHidden([...state.hidden]);
 mesh.viewer.load(view);
 mesh.viewer.select(state.face);mesh.shownFace=state.face;mesh.shownHidden=[...state.hidden].sort().join('\n');
 const dl=$('mesh-stats');dl.hidden=false;
 dl.replaceChildren(...statsRows(view).flatMap(([k,v])=>[el('dt',{},k),el('dd',{},v)]));
 status(`Meshed ${view.component}: ${view.stats.nodes} nodes, ${view.stats.tetrahedra} tetrahedra, ${view.stats.regions} regions.`);
}

/** Keep the mesh view's selection and hidden regions with the 3D view's. */
function syncMesh(){
 if(!mesh.viewer||!mesh.view||mesh.view.component!==state.view3d?.component)return;
 const hidden=[...state.hidden].sort().join('\n');
 if(hidden!==mesh.shownHidden){mesh.shownHidden=hidden;mesh.viewer.setHidden([...state.hidden]);}
 if(state.face!==mesh.shownFace||mesh.viewer.selected!==state.face){mesh.shownFace=state.face;mesh.viewer.select(state.face);}
}

async function cancelMesh(){
 const job=mesh.job;if(!job)return;
 clearTimeout(mesh.timer);
 let response,body=null;
 try{
  response=await fetch(`/api/model3d/jobs/${encodeURIComponent(job)}/cancel`,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
  body=await response.json().catch(()=>null);
 }catch(error){$('mesh-progress').textContent='Cancel did not reach the server: '+error.message;poll(job);return;}
 if(mesh.job!==job)return;
 if(!response.ok||!body){$('mesh-progress').textContent='Cancel was refused: '+refusalText(response.status,body);poll(job);return;}
 if(body.cancelled===false&&body.status==='done'){await meshDone(job,{status:'done',step:'ready',expected_s:0,elapsed_s:0});return;}
 if(body.cancelled===false){poll(job);return;}            // it had already ended: its status says how
 mesh.job=null;
 $('mesh-steps').hidden=true;
 const p=$('mesh-progress');p.textContent=CANCELLED;p.classList.remove('longer');
 renderMesh();
}

$('mesh-start').addEventListener('click',()=>startMesh());
$('mesh-cancel').addEventListener('click',()=>cancelMesh());

function render3d(){
 const v=state.view3d;
 $('unit').textContent=`${v.component} (3d) · lengths in ${v.unit} · read-only view`;
 for(const p of state.view?.parameters??[]){const e=$('value-'+p.name);if(e)e.textContent='';}
 const select=$('component');select.replaceChildren(...v.components.map(c=>{const o=el('option',{value:c.name},c.name);o.selected=c.name===v.component;return o;}));
 select.disabled=v.components.length<2;
 // regions, each with a show/hide box
 const ul=$('regions');ul.replaceChildren();
 for(const r of v.regions){
  const li=el('li',{'data-key':'region:'+r.name});
  const sw=el('span',{class:'swatch'+(r.void?' void':'')});if(!r.void)sw.style.background=regionColor3d(v,r.name);
  li.append(sw,el('code',{},r.name),el('small',{},`${r.void?'void':r.material} · ${Number(r.volume.toPrecision(6))} ${v.unit}³`));
  if(!r.void){
   const box=el('input',{type:'checkbox','aria-label':'show region '+r.name});box.checked=!state.hidden.has(r.name);
   box.addEventListener('change',()=>{if(box.checked)state.hidden.delete(r.name);else state.hidden.add(r.name);
    viewer.setHidden([...state.hidden]);if(viewer.selected===null&&state.face!==null)state.face=null;render3d();});
   li.append(box);
  }
  ul.append(li);
 }
 // faces: the keyboard way to every face and its names
 const faces=$('faces');faces.replaceChildren();
 for(const f of v.faces){
  const li=el('li',{'data-key':'face:'+f.id,'data-face':String(f.id),tabindex:'0','aria-label':`face ${f.id}: ${f.names.join(', ')}`});
  if(state.face===f.id){li.classList.add('active');li.setAttribute('aria-current','true');}
  li.append(el('code',{},'face '+f.id),el('small',{},f.names.join(' ')));
  const pick=()=>{state.face=state.face===f.id?null:f.id;viewer.select(state.face);render3d();const again=$('faces').querySelector(`[data-face="${f.id}"]`);if(again)again.focus();};
  li.addEventListener('click',pick);
  li.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();pick();}});
  faces.append(li);
 }
 plain('selections',v.selections.map(s=>({label:s.name,detail:`${s.kind} · ${s.entries.length}`})),'No named selections.');
 plain('tags',v.tags.map(t=>({label:t.tag,detail:`${t.faces.length} face${t.faces.length===1?'':'s'}`})));
 $('summary').textContent=v.summary;
 names();
 syncMesh();
}

function plain(id,rows,empty='None.'){
 const ul=$(id);ul.replaceChildren();
 if(!rows.length){ul.append(el('li',{class:'muted'},empty));return;}
 ul.replaceChildren(...rows.map(row=>{const li=el('li');li.append(el('code',{},row.label),el('small',{},row.detail));return li;}));
}

/** The names panel: the selected face's names, or a prompt. */
function names(){
 const v=state.view3d,face=state.face===null?null:v.faces[state.face];
 const panel=$('names'),list=$('face-names');list.replaceChildren();
 panel.dataset.face=face?String(face.id):'';
 if(!face){$('names-title').textContent='No face selected. Pick a face in the view or in the faces list.';$('names-detail').textContent='';return;}
 const lines=faceLines(v,face);
 $('names-title').textContent=lines.title;
 $('names-detail').textContent=`${lines.detail} · sides ${lines.sides}`;
 for(const n of lines.names){const li=el('li');li.append(el('code',{},n));list.append(li);}
}

function sectionControls(keep=false){
 const axis=$('section-axis').value,range=$('section-at');
 if(!axis||!state.view3d){range.disabled=true;$('section-value').textContent='';if(viewer&&state.view3d)viewer.setSection(null);if(mesh.viewer&&mesh.view)mesh.viewer.setSection(null);return;}
 const r=sectionRange(state.view3d,axis);
 if(!keep||range.disabled||range.dataset.axis!==axis){
  range.min=String(r.min);range.max=String(r.max);range.step=String(r.step);range.value=String(r.start);range.dataset.axis=axis;
 }
 range.disabled=false;
 applySection();
}

async function applySection(){
 const axis=$('section-axis').value,at=Number($('section-at').value),id=++state.section;
 if(!axis||!state.view3d||!viewer)return;
 $('section-value').textContent=`${axis} = ${Number(at.toPrecision(6))} ${state.view3d.unit}`;
 viewer.setSection({axis,at});
 if(mesh.viewer&&mesh.view)mesh.viewer.setSection({axis,at});
 try{
  const response=await fetch('/api/model3d/section',{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({doc:state.doc,component:state.component,axis,at})});
  const body=await response.json().catch(()=>null);
  if(id!==state.section)return;
  if(!response.ok||!body||body.ok!==true){status('Section refused: '+refusalText(response.status,body));return;}
  viewer.setSection({axis,at},body);
  if(mesh.viewer&&mesh.view)mesh.viewer.setSection({axis,at},body);
  status(`Section ${axis} = ${Number(at.toPrecision(6))} ${state.view3d.unit}: cuts ${body.faces.length} faces of ${body.regions.join(', ')||'no region'}.`);
 }catch(error){if(id===state.section)status('Section not shown: '+error.message);}
}

$('section-axis').addEventListener('change',()=>sectionControls());
$('section-at').addEventListener('input',()=>applySection());
for(const b of document.querySelectorAll('#view3d [data-view]'))b.addEventListener('click',()=>viewer?.setView(b.dataset.view));
$('fit3d').addEventListener('click',()=>viewer?.fit());
