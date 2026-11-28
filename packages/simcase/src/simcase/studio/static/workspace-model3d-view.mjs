// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// The 3D model's page in the workspace (slice B of the Studio 3D view; docs/packages/simcase/
// workspace.md, "3D models"): its tree, its property tables, the 3D view with picking, the faces
// list and Use for → New selection, and its Messages. Every edit sends the whole document to
// /api/model3d/check; the tree's coverage words and every refusal come from the server's exact
// complex, and the check also answers the mesh estimate or the refusal that blocks meshing. Mesh 1
// runs slice C's job (/api/model3d/mesh, /api/model3d/jobs/…) and shows its mesh view; the mesh is
// view state, kept neither in Undo nor in files. One Undo history holds the documents.
// Heat transfer (3D) edits the document's thermal.steady3d block; Run solves it with the run routes
// (/api/model3d/run, /api/model3d/runs/…), and each finished run is kept as its record (up to 10, saved
// with the model); Results show a run's surface temperature, a cut plane, a probe and its values.
import {View3D} from '/model3d-assets/model3d-view.mjs';
import {MeshView3D} from '/model3d-assets/model3d-mesh-view.mjs';
import {CANCELLED,longer,meshBlocked,progressText,statsRows,stepList,estimateText} from '/model3d-assets/model3d-mesh-model.mjs';
import {decode,faceLines,regionColor} from '/model3d-assets/model3d-model.mjs';
import {treeOpen,groupHeading,itemAttributes,treeState,bindTree,treeFocus,restoreTreeFocus} from './workspace-tree.mjs';
import {markPageTabs} from './workspace-tabs.mjs';
import {CARD3D,CARDS3D,card3dOf,meshRefusalText,FEATURE_TYPES,Model3dHistory,addFeature,addLayer,addParameter,blockReason,componentName,deleteFeature,deleteParameter,deletedText,
 duplicateFeature,editField,featureLabel,fieldNote,fieldsOf,getField,meshReason,meshRefusal,moveFeature,refusalMessage,removeLayer,setParameter,shownUnit,treeRows,
 heatOf,setFixedTemperature,removeFixedTemperature,setHeatSource,removeHeatSource,setConductivity,editableRegions,runReason,keptRunFor,noNeedText,
 valuesRows,runProgress,boundaryNameFor,temperatureColor,expectedHeatRate,keptRunText,HEAT_RATE_SIGN,colourBarTitle,cutLegend,cutFileName,regionToggles,NAMES_ANY,shownText,runCompleteText,meshDoneText,keptMeshLabel,nameScopes,interiorHint,useTemperatureProblem,fixedNoticeText,crossingAdvice} from './workspace-model3d.mjs';
import {writeModel3dSession,documentDigest,MAX_RUNS} from './workspace-model3d-session.mjs';
import {TemperatureView3D} from './workspace-model3d-results.mjs';
import {NEEDS_TWO,SAME_INPUTS,compareRows,heatRateNote,defaultPair,deltaLegend,encodeF32,inputChanges,meshNotice,surfaceDelta} from './workspace-model3d-compare.mjs';

const WORDS={estimateText,meshBlocked};      // slice C's words, passed to the pure helpers
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]);

/**
 * ctx: {$, ui, notice(text), render(), request(url, body) → reply JSON (POST), get(url) → reply JSON, applications(host),
 * onHistory(), projectLine()}. Returns the model's interface for workspace-app.mjs.
 */
export function createModel3dView(ctx){
 const {$}=ctx;
 let doc=null,title=CARD3D.title,history=null,shown=false,inProject=false;
 let card=null;                 // the Library card the model came from (its id), or null
 let check=null,refused=null,lastGood=null,lastDomain=null,request=0,checking=false;
 let selection='geometry',face=null,hidden=new Set();
 const drafts=new Map();          // field key → {raw, problem}
 const treeView=treeState();
 let viewer=null,canvas3d=null;
 let lastNotice=null;            // {text, undo}: a deletion's notice with its Undo
 // the mesh job of slice C: the running job, its last status, the mesh answer shown, the pane shown
 const mesh={job:null,timer:null,status:null,view:null,viewer:null,canvas:null,pane:'geometry'};
 // the runs: the kept records (saved with the model), the server run of each record when this page
 // ran it (cut, probe and CSV need it), the run going, the refusal the last run ended with, the run shown
 const heat={records:[],live:[],fresh:null,liveValues:new Map(),run:null,timer:null,status:null,failure:null,shown:null,viewer:null,canvas:null,cut:null,probe:null};
 // C3: the Compare page's pair (the two records' run ids, view state; not in the file) and its ΔT view
 const compare={a:null,b:null,canvas:null,viewer:null,source:null};
 let section=null;              // the geometry view's section {axis, at} (document units), view state
 let regionsOpen=false;         // U7: the Regions control is open (view state)
 let pendingFocus=null;         // a Settings field to focus across the renders until the check has answered

 // ---- the document and the check ----
 async function runCheck(){
  const id=++request;checking=true;renderDock();
  let reply;
  try{reply=await ctx.request('/api/model3d/check',{doc,component:componentName(doc)});}
  catch(e){reply={ok:false,refused:'The Studio server could not check the model: '+e.message,code:null,path:null,feature_index:null};}
  if(id!==request)return;
  checking=false;
  if(reply.ok){check=reply;refused=null;lastGood=reply.display;lastDomain=reply.domain||lastDomain;}else refused=reply;
  if(shown)ctx.render();
  pendingFocus=null;
 }
 function commit(next,{record=true}={}){
  heat.fresh=null;                 // an edit: the run just finished is no longer "up to date" news
  doc=next;if(record&&history.record(doc))ctx.onHistory();
  drafts.clear();runCheck();if(shown)ctx.render();
 }
 function open(document,{asTitle=CARD3D.title,runs=[],card:from}={}){
  card=from===undefined?card3dOf(document)?.id??null:from;
  stopJob();stopRun();mesh.status=null;mesh.view=null;mesh.pane='geometry';
  heat.records=runs.slice(-MAX_RUNS);heat.live=heat.records.map(()=>null);heat.liveValues=new Map();heat.status=null;heat.failure=null;heat.shown=null;heat.cut=null;heat.probe=null;section=null;
  doc=JSON.parse(JSON.stringify(document));title=asTitle;history=new Model3dHistory(doc);
  check=null;refused=null;lastGood=null;selection='geometry';face=null;hidden=new Set();drafts.clear();lastNotice=null;
  inProject=true;shown=true;ctx.ui.page='Model';runCheck();ctx.render();
 }
 // ---- the tree ----
 function rows(){return treeRows(doc,check,refused,WORDS,{runs:heat.records});}
 function drawTree(){
  const host=$('tree'),had=treeFocus(host,treeView);host.innerHTML=tree();
  host.querySelectorAll('[data-m3-node]').forEach(b=>{
   b.onclick=()=>choose(b.dataset.m3Node);
   b.addEventListener('keydown',e=>{
    const m=/^feature:(\d+)$/.exec(b.dataset.m3Node);
    if(m&&e.altKey&&(e.key==='ArrowUp'||e.key==='ArrowDown')){e.preventDefault();e.stopPropagation();move(+m[1],e.key==='ArrowUp'?-1:1);}
   },true);
  });
  bindTree(host,treeView,drawTree);restoreTreeFocus(host,treeView,had);
 }
 function tree(){
  const page=ctx.ui.page,all=rows();
  const item=r=>`<button type="button" data-m3-node="${esc(r.key)}" ${itemAttributes(r.level,page==='Model'&&selection===r.key)} class="${r.level>2?'tree-child':''}${r.problem?' has-problem':''}">`+
   `<span class="tree-node-mark" aria-hidden="true">${r.key.startsWith('feature:')?'▣':r.key==='form'?'◆':r.key==='mesh'?'▦':r.key==='heat'?'∿':r.key==='study'?'▷':r.key.startsWith('run:')?'▤':'·'}</span>${esc(r.label)}`+
   (r.problem?`<span class="problem-badge" role="img" aria-label="problem: ${esc(problemText())}" title="${esc(problemText())}">!</span>`:'')+
   (r.note?`<span class="m3-note">${esc(r.note)}</span>`:'')+`</button>`;
  // Component 1 · 3D · <unit> is the group heading; Parameters, Geometry 1 and Materials sit in it
  const head=all.find(r=>r.key==='component'),name='Component 1';
  return `<div class="pane-title"><span>Model builder</span><span class="pane-detail">3D model</span></div>${treeOpen()}`+
   `<section class="tree-group" role="none">${groupHeading(name,!treeView.collapsed.has(name),head.label)}${all.filter(r=>r.key!=='component').map(item).join('')}</section></div>`+
   `<div class="capability-card"><span class="capability-dot" aria-hidden="true"></span><strong>3D steady heat (experimental)</strong><p>Boxes and slab layers, and cylinders and spheres in meshloom's builder shapes, checked by the server, meshed and solved in a separate process.</p></div>`;
 }
 function choose(key){
  selection=key;ctx.ui.page='Model';
  const m=/^run:(\d+)$/.exec(key);if(m)showRun(+m[1]-1);
  ctx.render();
 }
 // the refusal a tree mark stands for: the shape's, else the one that blocks meshing, else the reader's
 function problemText(){return refused?refusalMessage(refused).text:meshRefusal(check)?.refused||(check?.run?.ok===false&&heatOf(doc)?check.run.refused:'');}

 // ---- edits ----
 function move(i,delta){try{commit(moveFeature(doc,i,delta));selection=`feature:${i+delta}`;ctx.render();focusRow(selection);}catch(e){ctx.notice(e.message);}}
 function focusRow(key){const b=$('tree')?.querySelector(`[data-m3-node="${CSS.escape(key)}"]`);if(b){b.tabIndex=0;b.focus();}}
 function remove(i){
  const f=doc.geometry.components[componentName(doc)].features[i];
  const text=deletedText(doc,i);commit(deleteFeature(doc,i));selection='geometry';lastNotice={text,undo:true};ctx.render();
 }
 function fieldInput(field){
  if(field.kind==='fixed'){const id='m3f-'+field.key.replace(/[^A-Za-z0-9]/g,'-');
   return `<label class="m3-field" for="${id}"><span>${esc(field.label)}</span><input id="${id}" value="${esc(field.value)}" readonly aria-readonly="true"></label>`;}
  const key=field.key,draft=drafts.get(key),value=draft?draft.raw:getField(doc,key);
  const shownValue=value===null||value===undefined?'':String(value);
  const si=field.kind==='length'&&!draft?fieldNote(doc,key):'';
  const id='m3f-'+key.replace(/[^A-Za-z0-9]/g,'-');
  return `<label class="m3-field" for="${id}"><span>${esc(field.label)}${field.optional?' (optional)':''}</span><input id="${id}" data-m3-field="${esc(key)}" value="${esc(shownValue)}" spellcheck="false"${draft?' aria-invalid="true" class="invalid"':''}>`+
   `<small class="m3-si">${esc(draft?draft.problem:si)}</small>${draft?`<button type="button" data-m3-restore="${esc(key)}">Restore last valid value</button>`:''}</label>`;
 }
 function settings(){
  const comp=doc.geometry.components[componentName(doc)];
  const m=/^feature:(\d+)$/.exec(selection);
  if(selection==='parameters')return parametersTable();
  if(selection==='domain')return `<h3>Domain</h3><p class="muted">Lengths in ${esc(shownUnit(comp.length_unit))}; a number, a quantity, a parameter or an expression.</p>`+fieldsOf(doc,'domain').map(fieldInput).join('');
  if(selection==='component')return `<h3>Component 1</h3><p>A 3D component in ${esc(shownUnit(comp.length_unit))}. Feature numbers show the order; a later feature wins where features overlap.</p>`;
  if(m){
   const i=+m[1],f=comp.features[i];if(!f)return '';
   const row=check?.features?.[i];
   return `<h3>${esc(featureLabel(f,i))}</h3>${row?.text?`<p class="m3-coverage">${esc(row.text)}</p>`:''}`+
    `<div class="m3-actions"><button type="button" data-m3-act="up"${i===0?' disabled':''}>Move up</button><button type="button" data-m3-act="down"${i===comp.features.length-1?' disabled':''}>Move down</button>`+
    `<button type="button" data-m3-act="duplicate">Duplicate</button><button type="button" data-m3-act="delete">Delete</button></div>`+
    `<p class="muted">Alt+Up and Alt+Down move the feature in the tree. A later feature takes the space it shares with an earlier one.</p>`+
    fieldsOf(doc,selection).map(fieldInput).join('')+
    (f.type==='layers'?`<div class="m3-actions">${f.layers.map((l,j)=>`<button type="button" data-m3-unlayer="${j}"${f.layers.length<=1?' disabled':''}>Remove layer ${esc(l.name)}</button>`).join('')}<button type="button" data-m3-layer${f.layers.length>=32?' disabled':''}>Add layer</button></div>`:'');
  }
  if(selection==='geometry')return `<h3>Geometry 1</h3><p>${comp.features.length} features in ${esc(shownUnit(comp.length_unit))}. Add feature:</p><div class="m3-add">`+
   FEATURE_TYPES.map(t=>t.available?`<button type="button" data-m3-add="${t.type}">${t.label}</button>`:
    `<button type="button" disabled aria-describedby="m3-why-${t.type}">${t.label}</button><small id="m3-why-${t.type}" class="muted">${esc(t.reason)}</small>`).join('')+`</div>`;
  if(selection==='form'){
   if(refused)return `<h3>Form result</h3><p class="m3-refused">${esc(refusalMessage(refused).text)}</p>`;
   const sel=comp.selections||{};
   return `<h3>Form result</h3>`+(check?`<p>${check.regions.length} regions · ${check.display.faces.length} faces: the faces are listed under the view.</p><ul>${check.regions.map(r=>`<li><code>${esc(r.name)}</code> ${esc(r.void?'void':r.material)} · ${Number(r.volume.toPrecision(6))} ${esc(shownUnit(comp.length_unit))}³</li>`).join('')}</ul>`:'<p class="muted">Checking…</p>')+
    `<h4>Selections</h4>`+(Object.keys(sel).length?`<ul>${Object.entries(sel).map(([n,s])=>`<li data-m3-selection="${esc(n)}"><code>${esc(n)}</code> <span class="m3-sel-entry">${esc(JSON.stringify(s))}</span> <button type="button" data-m3-unselect="${esc(n)}">Delete</button></li>`).join('')}</ul>`:'<p class="muted">Pick a face in the view or the faces list, then Use for → New selection.</p>');
  }
  if(selection==='mesh'){
   const off=refused?null:meshRefusal(check),est=!refused&&check?.mesh?.ok?check.mesh.estimate:null;
   return `<h3>Mesh 1</h3><p id="m3-estimate">${esc(off?(meshRefusalText(off,'')!==off.refused?'Mesh is not available: see Messages.':'Mesh is not available: '+off.refused):est?estimateText(est):refused?'The geometry cannot be formed: fix the problem shown in Messages.':'Checking…')}</p>`+
    `<p class="muted">The mesh runs in a separate process on the Studio server; Cancel meshing ends it and keeps nothing. The mesh is not saved in the project file: mesh again after opening it.</p>`+
    fieldsOf(doc,'mesh').map(fieldInput).join('')+
    (mesh.view&&keptMeshLabel(mesh.view,check)?`<h4 id="m3-kept-mesh">${esc(keptMeshLabel(mesh.view,check))}</h4>`:'')+
    (mesh.view?`<dl class="m3-mesh-stats">${statsRows(mesh.view).map(([k,v])=>`<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('')}</dl>`:'');
  }
  if(selection==='materials'||selection==='heat:k')return conductivityTable();
  if(selection.startsWith('heat')||selection==='study'||selection==='results'||selection.startsWith('run:'))return heatSettings();
  return '';
 }
 function heatField(kind,key,label,value){
  const d=drafts.get(`${kind}:${key}`),id=`m3h-${kind}-${key.replace(/[^A-Za-z0-9]/g,'-')}`;
  return `<label class="m3-field" for="${id}"><span>${esc(label)}</span><input id="${id}" data-m3-heat="${kind}" data-m3-key="${esc(key)}" value="${esc(d?d.raw:value)}" spellcheck="false"${d?' aria-invalid="true" class="invalid"':''}>`+
   `<small class="m3-si">${esc(d?d.problem:'')}</small>${d?`<button type="button" data-m3-restore="${esc(kind+':'+key)}">Restore last valid value</button>`:''}</label>`;
 }
 function conductivityTable(){
  return `<h3>${selection==='heat:k'?'Thermal conductivity':'Materials'}</h3><p class="muted">Heat transfer (3D) takes each region's thermal conductivity from its material.</p>`+
   Object.entries(doc.materials||{}).map(([n,p])=>heatField('k',n,`${n}, k`,p.thermal_conductivity??'')).join('');
 }
 function heatSettings(){
  const h=heatOf(doc),reason=runReason({drafts:drafts.size,refused,check,running:!!heat.run,doc,failure:heat.failure},WORDS);
  if(selection==='heat'){
   const regions=editableRegions(check);
   return `<h3>Heat transfer (3D)</h3><p class="muted">Steady heat conduction (thermal.steady3d). Every outer face without a fixed temperature is insulated.</p>`+
    (check?.run?.ok===false?`<p class="m3-refused">${esc(check.run.refused)}</p>`:'')+
    `<form class="m3-heat-add" data-m3-add-fixed><label>Fixed temperature on <input name="name" value="z0" spellcheck="false" aria-label="boundary name"></label><label>at <input name="value" value="300 K" spellcheck="false"></label><button type="submit">Add fixed temperature</button></form>`+
    `<form class="m3-heat-add" data-m3-add-source><label>Heat source in <select name="region" aria-label="region">${regions.map(r=>`<option>${esc(r)}</option>`).join('')}</select></label><label>of <input name="value" value="1e12 W/m^3" spellcheck="false"></label><button type="submit"${regions.length?'':' disabled'}>Add heat source</button></form>`+
    (h?'':'<p>No heat physics yet: add a fixed temperature.</p>');
  }
  let m=/^heat:fixed:(.+)$/.exec(selection);
  if(m&&h?.prescribed_temperature?.[m[1]]!==undefined)return `<h3>Fixed temperature</h3><p>On <code>${esc(m[1])}</code>.</p>`+heatField('fixed',m[1],'Temperature',h.prescribed_temperature[m[1]])+
   `<div class="m3-actions"><button type="button" data-m3-unfixed="${esc(m[1])}">Delete</button></div>`;
  m=/^heat:source:(.+)$/.exec(selection);
  if(m&&h?.heat_source_density!==undefined){const v=typeof h.heat_source_density==='object'?h.heat_source_density[m[1]]:h.heat_source_density;
   return `<h3>Heat source</h3><p>In <code>${esc(m[1])}</code>.</p>`+heatField('source',m[1],'Heat source density',v??'')+`<div class="m3-actions"><button type="button" data-m3-unsource="${esc(m[1])}">Delete</button></div>`;}
  if(selection==='heat:insulated')return `<h3>Insulated</h3><p>Every outer face that no fixed temperature names is insulated (no heat crosses it).</p>`;
  if(selection==='study'){const i=keptRunFor(doc,heat.records);
   return `<h3>Study 1 · Steady</h3><p>Run meshes the component (Mesh 1, reused when unchanged) and solves Heat transfer (3D) in a separate process.</p>`+
    `<p id="m3-study-why">${esc(i>=0?keptRunText(i,heat.fresh):reason||'Ready to run.')}</p>`;}
  if(selection==='results')return `<h3>Results</h3>`+(heat.records.length?`<ul>${heat.records.map((r,i)=>`<li>Run ${i+1}: ${esc(valuesRows(r.values,r.surface?.unit||'um')[0][1])}</li>`).join('')}</ul>`:'<p class="muted">No run yet: press Run.</p>')+
   `<p class="muted">Up to ${MAX_RUNS} runs are kept with the model and saved with it.</p>`;
  m=/^run:(\d+)$/.exec(selection);
  if(m){const i=+m[1]-1,r=heat.records[i];if(!r)return '';
   const unit=r.surface?.unit||'um',live=heat.live[i],u=shownUnit(unit);
   const same=keptRunFor(doc,heat.records)===i;
   return `<h3>Run ${i+1} · Temperature</h3>`+
    `<table class="m3-values" id="m3-values"><tbody>${valuesRows(withExtremes(r.values,live&&heat.liveValues?.get(live)),unit,{expected:expectedHeatRate(r.document)}).map(([k,v])=>`<tr><th scope="row">${esc(k)}</th><td>${esc(v)}</td></tr>`).join('')}</tbody></table>`+
    `<p class="muted" id="m3-sign">${esc(HEAT_RATE_SIGN)}</p>`+
    `<p class="muted">Mesh: ${r.mesh.nodes.toLocaleString('en-US')} nodes, ${r.mesh.tetrahedra.toLocaleString('en-US')} tetrahedra (${esc(r.mesh.route)}).${same?' These are the current inputs.':' The inputs have changed since this run.'}</p>`+
    `<div class="m3-actions">${same?'':'<button type="button" data-m3-run-act="inputs">Use this run\'s inputs</button>'}${live?'':'<button type="button" data-m3-run-act="recompute">Recompute</button>'}</div>`+
    (live?'':`<p class="muted" id="m3-recompute-why">Recompute this run to cut, probe or export CSV.</p>`)+
    `<form class="m3-probe" data-m3-probe><fieldset${live?'':' disabled'}><legend>Probe (${esc(u)})</legend>${['x','y','z'].map((a,k)=>`<label>${a} <input name="${a}" value="${esc(heat.probe?.point?.[k]??'')}" inputmode="decimal" aria-label="probe ${a}"></label>`).join('')}<button type="submit">Probe</button></fieldset></form>`+
    `<p id="m3-probe-result" aria-live="polite">${esc(heat.probe?.text||'')}</p>`+
    `<p class="m3-exports">Export: ${live?`<a href="/api/model3d/runs/${esc(live)}/export/surface.csv" download>Surface (CSV)</a> · ${heat.cut&&heat.cut.run===i?`${cutLink()} · `:''}`:''}<button type="button" data-m3-run-act="json">Run (JSON)</button></p>`;
  }
  return '';
 }
 function parametersTable(){
  const params=doc.geometry.parameters||{},info=new Map((check?.parameters||[]).map(p=>[p.name,p]));
  // a refusal about a parameter (E-DOMAIN, E-EXPRESSION-KIND, a cycle) is shown on its row
  const rowProblem=n=>refused&&new RegExp(`^geometry\\.parameters\\.${n}\\b`).test(refused.path||'')?refused.refused:'';
  // V11: two lines per parameter (name, value, Delete; then kind · range · SI value · use), so nothing is clipped in the pane
  const rowsHtml=Object.entries(params).map(([n,p])=>{const i=info.get(n),used=i?.used_by||[],problem=rowProblem(n);
   const facts=[i?.kind||'',p.range?shownText(JSON.stringify(p.range)):'',i?`= ${Number(i.value.toPrecision(6))} ${i.unit}`:''].filter(Boolean);
   return `<tr${problem?' class="has-problem"':''}><th scope="row"><code>${esc(n)}</code></th><td><input data-m3-param="${esc(n)}" value="${esc(p.value)}" aria-label="value of ${esc(n)}"${problem?' aria-invalid="true"':''}>${problem?`<small class="m3-si">${esc(problem)}</small>`:''}</td>`+
    `<td><button type="button" data-m3-unparam="${esc(n)}">Delete</button></td></tr>`+
    `<tr class="m3-param-facts"><td></td><td colspan="2"><small>${esc(facts.join(' · '))}${facts.length?' · ':''}<span class="m3-param-use">${used.length?esc(`used by ${used.length}`):'unused'}</span></small></td></tr>`;}).join('');
  return `<h3>Parameters</h3><table class="m3-params"><thead><tr><th>Name</th><th>Value</th><th></th></tr></thead><tbody>${rowsHtml||'<tr><td colspan="3" class="muted">No parameters.</td></tr>'}</tbody></table>`+   `<form class="m3-param-add"><label>Name <input name="name" spellcheck="false"></label><label>Value <input name="value" spellcheck="false" placeholder="20 um"></label><button type="submit">Add parameter</button></form>`;
 }
 function bindSettings(host){
  if(pendingFocus){const target=pendingFocus;queueMicrotask(()=>host.querySelector(target)?.focus());}
  host.querySelectorAll('[data-m3-field]').forEach(input=>input.addEventListener('change',()=>{
   const field=[...fieldsOf(doc,selection),...fieldsOf(doc,'domain'),...fieldsOf(doc,'mesh')].find(f=>f.key===input.dataset.m3Field);
   const out=editField(doc,field,input.value,{domain:check?.domain??null});
   if(out.problem){drafts.set(field.key,{raw:input.value,problem:out.problem});ctx.render();ctx.onHistory();return;}
   drafts.delete(field.key);commit(out.doc);
  }));
  host.querySelectorAll('[data-m3-restore]').forEach(b=>b.onclick=()=>{drafts.delete(b.dataset.m3Restore);ctx.render();ctx.onHistory();});
  host.querySelectorAll('[data-m3-act]').forEach(b=>b.onclick=()=>{
   const i=+/^feature:(\d+)$/.exec(selection)[1];
   if(b.dataset.m3Act==='up')move(i,-1);else if(b.dataset.m3Act==='down')move(i,1);
   else if(b.dataset.m3Act==='duplicate'){commit(duplicateFeature(doc,i));selection=`feature:${i+1}`;ctx.render();}
   else remove(i);
  });
  host.querySelector('[data-m3-layer]')?.addEventListener('click',()=>{const i=+/^feature:(\d+)$/.exec(selection)[1];try{commit(addLayer(doc,i));}catch(e){ctx.notice(e.message);}});
  host.querySelectorAll('[data-m3-unlayer]').forEach(b=>b.onclick=()=>{const i=+/^feature:(\d+)$/.exec(selection)[1];try{commit(removeLayer(doc,i,+b.dataset.m3Unlayer));}catch(e){ctx.notice(e.message);}});
  host.querySelectorAll('[data-m3-add]').forEach(b=>b.onclick=()=>{commit(addFeature(doc,b.dataset.m3Add,{domain:check?.domain??null}));selection=`feature:${doc.geometry.components[componentName(doc)].features.length-1}`;ctx.render();});
  host.querySelectorAll('[data-m3-param]').forEach(input=>input.addEventListener('change',()=>{try{commit(setParameter(doc,input.dataset.m3Param,input.value));}catch(e){ctx.notice(e.message);}}));
  host.querySelectorAll('[data-m3-unparam]').forEach(b=>b.onclick=()=>{
   const name=b.dataset.m3Unparam,used=(check?.parameters||[]).find(p=>p.name===name)?.used_by||[];
   try{commit(deleteParameter(doc,name,used));}catch(e){ctx.notice(e.message);lastNotice={text:e.message,undo:false};renderDock();}
  });
  const form=host.querySelector('.m3-param-add');
  if(form)form.onsubmit=e=>{e.preventDefault();try{commit(addParameter(doc,form.elements.name.value.trim(),form.elements.value.value));}catch(err){ctx.notice(err.message);}};
  host.querySelectorAll('[data-m3-heat]').forEach(input=>input.addEventListener('change',()=>{
   const kind=input.dataset.m3Heat,key=input.dataset.m3Key,id=`${kind}:${key}`;
   try{
    const next=kind==='fixed'?setFixedTemperature(doc,key,input.value):kind==='source'?setHeatSource(doc,key,input.value):setConductivity(doc,key,input.value);
    drafts.delete(id);commit(next);
    // Messages follows the value: the notice of a fixed temperature says the one now in the model
    if(kind==='fixed')lastNotice={text:`Fixed temperature ${heatOf(next).prescribed_temperature[key]} on ${key}.`,undo:true};
    else if(lastNotice&&/^Fixed temperature /.test(lastNotice.text))lastNotice=null;
    renderDock();
   }catch(e){drafts.set(id,{raw:input.value,problem:e.message});ctx.render();ctx.onHistory();}
  }));
  host.querySelectorAll('[data-m3-restore]').forEach(b=>{if(/^(fixed|source|k):/.test(b.dataset.m3Restore))b.onclick=()=>{drafts.delete(b.dataset.m3Restore);ctx.render();ctx.onHistory();};});
  host.querySelectorAll('[data-m3-unfixed]').forEach(b=>b.onclick=()=>{commit(removeFixedTemperature(doc,b.dataset.m3Unfixed));selection='heat';lastNotice={text:`Fixed temperature on ${b.dataset.m3Unfixed} deleted; Undo restores it.`,undo:true};ctx.render();});
  host.querySelectorAll('[data-m3-unsource]').forEach(b=>b.onclick=()=>{commit(removeHeatSource(doc,b.dataset.m3Unsource));selection='heat';lastNotice={text:`Heat source in ${b.dataset.m3Unsource} deleted; Undo restores it.`,undo:true};ctx.render();});
  const addFixed=host.querySelector('[data-m3-add-fixed]');
  if(addFixed)addFixed.onsubmit=e=>{e.preventDefault();const name=addFixed.elements.name.value.trim();
   try{commit(setFixedTemperature(doc,name,addFixed.elements.value.value));selection=`heat:fixed:${name}`;ctx.render();}catch(err){ctx.notice(err.message);lastNotice={text:err.message,undo:false};renderDock();}};
  const addSource=host.querySelector('[data-m3-add-source]');
  if(addSource)addSource.onsubmit=e=>{e.preventDefault();const region=addSource.elements.region.value;
   try{commit(setHeatSource(doc,region,addSource.elements.value.value));selection=`heat:source:${region}`;ctx.render();}catch(err){ctx.notice(err.message);lastNotice={text:err.message,undo:false};renderDock();}};
  host.querySelectorAll('[data-m3-run-act]').forEach(b=>b.onclick=()=>runAction(b.dataset.m3RunAct));
  host.querySelectorAll('[data-m3-cut-csv]').forEach(a=>a.onclick=e=>{e.preventDefault();saveCut();});
  const probe=host.querySelector('[data-m3-probe]');
  if(probe)probe.onsubmit=e=>{e.preventDefault();probeAt(['x','y','z'].map(a=>Number(probe.elements[a].value)));};
  host.querySelectorAll('[data-m3-unselect]').forEach(b=>b.onclick=()=>{
   const next=JSON.parse(JSON.stringify(doc));delete next.geometry.components[componentName(doc)].selections[b.dataset.m3Unselect];
   if(!Object.keys(next.geometry.components[componentName(doc)].selections).length)delete next.geometry.components[componentName(doc)].selections;
   commit(next);
  });
 }

 // ---- the 3D view, the faces list and Use for → New selection ----
 function ensureViewer(){
  if(!canvas3d){
   canvas3d=document.createElement('canvas');canvas3d.id='m3-canvas';canvas3d.tabIndex=0;
   canvas3d.setAttribute('aria-label','3D view. Arrow keys rotate, Shift with arrow keys pans, plus and minus zoom, F fits, 1 to 6 choose the axis views, 0 the isometric view.');
   viewer=new View3D(canvas3d,{onPick:f=>{face=f;renderNames();renderFaces();},onCamera:what=>{canvas3d.dataset.camera=what;}});
  }
  return viewer;
 }
 function graphics(host){
  const comp=doc.geometry.components[componentName(doc)];
  const why=meshReason({drafts:drafts.size,refused,check,running:!!mesh.job||!!heat.run},WORDS),block=why||'';
  const kept=keptRunFor(doc,heat.records),runWhy=runReason({drafts:drafts.size,refused,check,running:!!heat.run||!!mesh.job,doc,failure:heat.failure},WORDS);
  const onResult=mesh.pane==='result'&&heat.shown!==null&&!!heat.records[heat.shown]?.surface;
  const onMesh=!onResult&&mesh.pane==='mesh'&&!!mesh.view,stale=!!(mesh.view&&check?.mesh?.ok&&check.mesh.key!==mesh.view.key);
  const resultStale=onResult&&keptRunFor(doc,heat.records)!==heat.shown;
  const cutShown=onResult&&!!heat.cut&&heat.cut.run===heat.shown&&!!heat.live[heat.shown];
  host.innerHTML=`<div class="m3-head"><h2>${esc(title)}</h2><div class="m3-run">`+
   (mesh.job?`<button type="button" id="m3-mesh-cancel">Cancel meshing</button>`:`<button type="button" id="m3-mesh"${why?' disabled aria-describedby="m3-block"':''}>Mesh</button>`)+
   (heat.run?`<button type="button" id="m3-run-cancel">Cancel run</button>`:`<button type="button" id="m3-run"${runWhy&&kept<0?' disabled':''} aria-describedby="m3-run-why">Run</button>`)+
   `<small id="m3-block">${esc(block)}</small>`+
   `<small id="m3-run-why">${kept>=0&&!heat.run?`${esc(keptRunText(kept,heat.fresh))} <button type="button" data-m3-show-run="${kept}">Show Run ${kept+1}</button>`:esc(runWhy||'')}</small></div></div>`+
   meshJob()+runJob()+
   `<div class="m3-views" role="toolbar" aria-label="3D view">${['iso','+x','-x','+y','-y','+z','-z'].map(v=>`<button type="button" data-m3-view="${v}">${v==='iso'?'Iso':v.toUpperCase().replace('-','−')}</button>`).join('')}<button type="button" data-m3-fit>Fit</button>${regionsControl()}`+
   `<span class="m3-section"><label>Section <select id="m3-section-axis" aria-label="section plane"><option value="">none</option>${['x','y','z'].map(a=>`<option value="${a}"${section?.axis===a?' selected':''}>${a} =</option>`).join('')}</select></label>`+
   `<input id="m3-section-at" aria-label="section position" inputmode="decimal" value="${esc(section?.at??'')}"><span class="m3-unit" id="m3-section-unit">${esc(shownUnit(comp.length_unit))}</span><button type="button" id="m3-section-go">Apply</button>${cutShown?cutLink('m3-section-csv'):''}</span>`+
   `<span class="m3-pane" role="group" aria-label="Shown"><button type="button" data-m3-pane="geometry" aria-pressed="${!onMesh&&!onResult}">Geometry</button><button type="button" data-m3-pane="mesh" aria-pressed="${onMesh}"${mesh.view?'':' disabled title="Mesh first"'}>Mesh view</button>`+
   `<button type="button" data-m3-pane="result" aria-pressed="${onResult}"${heat.records.length?'':' disabled title="Run first"'}>Result</button></span></div>`+
   `<div class="m3-stage${refused&&!onMesh&&!onResult?' stale':''}${(onMesh&&stale)||resultStale?' stale':''}"><div id="m3-canvas-slot"></div>${refused&&lastGood&&!onMesh&&!onResult?'<p class="m3-last">Last shape that could be formed</p>':''}`+
   `${onMesh&&stale?'<p class="m3-last">Mesh of an earlier geometry; mesh again to update it</p>':''}${resultStale?`<p class="m3-last">Run ${heat.shown+1}: inputs changed since this run</p>`:''}</div>`+
   (onResult?colourBar(heat.records[heat.shown]):'')+(cutShown?cutBar():'')+
   `<section class="m3-faces"><h3 id="m3-faces-heading">Faces</h3><ul id="m3-faces" aria-labelledby="m3-faces-heading"></ul></section>`+
   `<section class="m3-names" id="m3-names" aria-live="polite"></section>`+
   `<p class="muted">Lengths in ${esc(shownUnit(comp.length_unit))}. A face's names say which surface of which feature it lies on.</p>`;
  host.querySelectorAll('.m3-ramp').forEach(ramp=>{ramp.style.background=ramp.dataset.ramp;});   // CSSOM, not an inline style attribute (CSP)
  const v=ensureViewer(),slot=host.querySelector('#m3-canvas-slot');
  if(onResult){const rv=ensureResultViewer(),rec=heat.records[heat.shown];slot.append(heat.canvas);
   if(rv.source!==rec){rv.source=rec;rv.setHidden([...hidden]);rv.load(rec.surface);rv.setCut(heat.cut&&heat.cut.run===heat.shown?heat.cut.answer:null);}rv.select(face);}
  else if(onMesh){const mv=ensureMeshViewer();slot.append(mesh.canvas);if(mv.view!==mesh.view){mv.setHidden([...hidden]);mv.load(mesh.view);}mv.select(face);}
  else slot.append(canvas3d);
  if(lastGood){
   if(v.view!==lastGood){v.setHidden([...hidden]);v.load(lastGood,{keep:!!v.view});}
   v.select(face);
  }
  if(!onResult&&!onMesh&&lastGood)v.setSection(section,section?.outline||null);
  const active=()=>onResult?heat.viewer:onMesh?mesh.viewer:v;
  host.querySelectorAll('[data-m3-view]').forEach(b=>b.onclick=()=>active().setView(b.dataset.m3View));
  host.querySelector('[data-m3-fit]').onclick=()=>active().fit();
  const regionsBox=host.querySelector('#m3-regions');
  if(regionsBox){regionsBox.ontoggle=()=>{regionsOpen=regionsBox.open;};
   regionsBox.querySelectorAll('[data-m3-region]').forEach(b=>b.onchange=()=>showRegion(b.dataset.m3Region,b.checked));}
  host.querySelectorAll('[data-m3-pane]').forEach(b=>b.onclick=()=>{mesh.pane=b.dataset.m3Pane;ctx.render();document.querySelector(`[data-m3-pane="${mesh.pane}"]`)?.focus();});
  host.querySelector('#m3-mesh')?.addEventListener('click',()=>startMesh());
  host.querySelector('#m3-mesh-cancel')?.addEventListener('click',()=>cancelMesh());
  host.querySelector('#m3-run')?.addEventListener('click',()=>startRun());
  host.querySelector('#m3-run-cancel')?.addEventListener('click',()=>cancelRun());
  host.querySelectorAll('[data-m3-show-run]').forEach(b=>b.onclick=()=>{selection=`run:${+b.dataset.m3ShowRun+1}`;showRun(+b.dataset.m3ShowRun);ctx.render();});
  host.querySelectorAll('[data-m3-cut-csv]').forEach(a=>a.onclick=e=>{e.preventDefault();saveCut();});
  host.querySelector('#m3-section-go').onclick=()=>applySection(host.querySelector('#m3-section-axis').value,host.querySelector('#m3-section-at').value);
  renderFaces();renderNames();
 }
 function ensureMeshViewer(){
  if(!mesh.canvas){
   mesh.canvas=document.createElement('canvas');mesh.canvas.id='m3-mesh-canvas';mesh.canvas.tabIndex=0;
   mesh.canvas.setAttribute('aria-label','Mesh view, coloured by region, with mesh edges. Arrow keys rotate, Shift with arrow keys pans, plus and minus zoom, F fits, 1 to 6 choose the axis views, 0 the isometric view.');
   mesh.viewer=new MeshView3D(mesh.canvas,{onPick:f=>{face=f;viewer?.select(f);renderNames();renderFaces();},onCamera:what=>{mesh.canvas.dataset.camera=what;}});
  }
  return mesh.viewer;
 }
 function ensureResultViewer(){
  if(!heat.canvas){
   heat.canvas=document.createElement('canvas');heat.canvas.id='m3-result-canvas';heat.canvas.tabIndex=0;
   heat.canvas.setAttribute('aria-label','Temperature of the run on the surfaces, blue at the minimum and red at the maximum. Arrow keys rotate, Shift with arrow keys pans, plus and minus zoom, F fits, 1 to 6 choose the axis views, 0 the isometric view. Clicking a surface probes the temperature there.');
   heat.viewer=new TemperatureView3D(heat.canvas,{onPick:f=>{face=f;viewer?.select(f);renderNames();renderFaces();
    const hit=heat.viewer.lastHit;if(hit&&heat.live[heat.shown])probeAt(hit.point);},onCamera:what=>{heat.canvas.dataset.camera=what;}});
  }
  return heat.viewer;
 }
 // a kept record's values with the regions around its extreme nodes, when this server holds the run
 function withExtremes(values,ext){
  if(!ext)return values;
  const out={...values};
  for(const k of ['temperature_min','temperature_max'])if(ext[k]?.node===values[k]?.node)out[k]={...values[k],regions:ext[k].regions};
  return out;
 }
 function ramp(lo,hi){const mid=(lo+hi)/2;
  return [lo,mid,hi].map(t=>`rgb(${temperatureColor(t,lo,hi).map(c=>Math.round(c*255)).join(',')})`).join(',');}
 /** U5: the cut's legend, over its own colour range. */
 function cutBar(){
  const c=heat.cut.answer,lo=c.temperature_min.value,hi=c.temperature_max.value,text=cutLegend({...c,axis:heat.cut.axis,at:heat.cut.at},heat.records[heat.cut.run].surface.unit);
  return `<div class="m3-colourbar m3-cut-bar" id="m3-cut-bar" role="img" aria-label="${esc(text)} (blue to red)"><span class="m3-cb-title">${esc(text.slice(0,text.indexOf(':')))}</span><span>${Number(lo.toPrecision(6))} K</span><span class="m3-ramp" data-ramp="linear-gradient(to right,${ramp(lo,hi)})"></span><span>${Number(hi.toPrecision(6))} K</span></div>`;
 }
 /** U5: the shown cut as CSV (the server's export, columns in metres), saved under the model's and the plane's name. */
 function cutLink(id){const live=heat.live[heat.cut.run];
  return `<a${id?` id="${id}"`:''} data-m3-cut-csv href="/api/model3d/runs/${esc(live)}/export/cut.csv?axis=${heat.cut.axis}&at=${encodeURIComponent(heat.cut.at)}">Cut (CSV)</a>`;}
 async function saveCut(){
  const c=heat.cut;if(!c)return;const rec=heat.records[c.run],live=heat.live[c.run];
  const name=cutFileName(rec.document?.name??doc.name,c.axis,c.at,rec.surface.unit);
  try{const r=await fetch(`/api/model3d/runs/${encodeURIComponent(live)}/export/cut.csv?axis=${c.axis}&at=${encodeURIComponent(c.at)}`);
   if(!r.ok){let t=`Cut (CSV) was not saved (HTTP ${r.status}).`;try{t=(await r.json()).refused||t;}catch{}throw new Error(t);}
   const url=URL.createObjectURL(await r.blob()),a=globalThis.document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
   lastNotice={text:`Cut (CSV) saved as ${name}.`,undo:false};}
  catch(e){lastNotice={text:e.message,undo:false};}
  renderDock();
 }
 /** U7: Regions in the view toolbar: a checkbox per region; unchecked hides it in every view (setHidden). */
 function regionsControl(){
  const rows=regionToggles(lastGood,hidden);if(!rows.length)return '';
  return `<details class="m3-regions" id="m3-regions"${regionsOpen?' open':''}><summary>Regions</summary><fieldset><legend>Shown regions</legend>`+
   rows.map(r=>`<label><input type="checkbox" data-m3-region="${esc(r.name)}"${r.shown?' checked':''}> ${esc(r.name)}</label>`).join('')+`</fieldset></details>`;
 }
 function showRegion(name,shown){
  if(shown)hidden.delete(name);else hidden.add(name);
  for(const v of [viewer,mesh.viewer,heat.viewer])v?.setHidden([...hidden]);
  if(face!==null&&viewer&&viewer.selected===null){face=null;renderFaces();renderNames();}
 }
 function colourBar(rec){
  const s=rec.surface,lo=s.temperature_min.value,hi=s.temperature_max.value,mid=(lo+hi)/2;
  const css=[lo,mid,hi].map(t=>`rgb(${temperatureColor(t,lo,hi).map(c=>Math.round(c*255)).join(',')})`).join(',');
  return `<div class="m3-colourbar" role="img" aria-label="${colourBarTitle} from ${Number(lo.toPrecision(6))} K (blue) to ${Number(hi.toPrecision(6))} K (red)"><span class="m3-cb-title">${colourBarTitle}</span><span>${Number(lo.toPrecision(6))} K</span><span class="m3-ramp" data-ramp="linear-gradient(to right,${css})"></span><span>${Number(hi.toPrecision(6))} K</span></div>`;
 }
 async function applySection(axis,raw){
  const at=Number(raw);
  if(!axis){section=null;heat.cut=null;heat.viewer?.setCut(null);ctx.render();return;}
  if(raw===''||!Number.isFinite(at)){lastNotice={text:'Enter the section position as a number in the component\'s unit.',undo:false};renderDock();return;}
  section={axis,at};
  try{const outline=await ctx.request('/api/model3d/section',{doc,component:componentName(doc),axis,at});if(outline.ok!==false)section.outline=outline;}catch{}
  if(mesh.pane==='result'&&heat.shown!==null&&heat.live[heat.shown]){
   try{const cut=await ctx.request(`/api/model3d/runs/${encodeURIComponent(heat.live[heat.shown])}/cut`,{axis,at});
    heat.cut={run:heat.shown,axis,at,answer:cut};heat.viewer?.setCut(cut);
    lastNotice={text:`Cut ${axis} = ${at} ${shownUnit(heat.records[heat.shown].surface.unit)}: ${Number(cut.temperature_min.value.toPrecision(6))}–${Number(cut.temperature_max.value.toPrecision(6))} K.`,undo:false};}
   catch(e){lastNotice={text:e.message,undo:false};}
  }else if(mesh.pane==='result'&&heat.shown!==null)lastNotice={text:'Recompute this run to cut, probe or export CSV.',undo:false};
  ctx.render();
 }
 // ---- the run: start, poll, cancel, keep the record ----
 const RUN_STEPS=[['mesh','Meshing'],['solve','Solving'],['done','Done']];
 function runJob(){
  const s=heat.status;if(!s)return '';
  const at=RUN_STEPS.findIndex(([k])=>k===(s.status==='done'?'done':s.step));
  return `<div class="m3-mesh-job m3-run-job" aria-live="polite"><p id="m3-run-progress"${s.longer_than_estimate?' class="longer"':''}>${esc(runProgress(s))}</p>`+
   (s.status==='running'||s.status==='done'?`<ol id="m3-run-steps">${RUN_STEPS.map(([k,l],i)=>`<li class="${s.status==='done'||i<at?'done':i===at?'current':'todo'}"${i===at&&s.status==='running'?' aria-current="step"':''}>${l}</li>`).join('')}</ol>`:'')+`</div>`;
 }
 function stopRun(){
  clearTimeout(heat.timer);heat.timer=null;
  const run=heat.run;heat.run=null;
  if(run)ctx.request(`/api/model3d/runs/${encodeURIComponent(run.id)}/cancel`,{}).catch(()=>{});
 }
 function showRun(i){heat.shown=i;mesh.pane='result';if(heat.cut&&heat.cut.run!==i)heat.cut=null;heat.probe=null;}
 async function startRun(document=null,replace=null){
  const target=document||doc;
  if(heat.run)return;
  if(!document){
   const kept=keptRunFor(doc,heat.records);
   if(kept>=0){selection=`run:${kept+1}`;showRun(kept);ctx.render();return;}
   if(runReason({drafts:drafts.size,refused,check,running:!!mesh.job,doc,failure:heat.failure},WORDS))return;
  }
  let body;
  try{body=await ctx.request('/api/model3d/run',{doc:target,component:componentName(target)});}
  catch(e){heat.failure={document:JSON.parse(JSON.stringify(target)),message:e.message};lastNotice={text:'Run not started: '+e.message,undo:false};ctx.render();return;}
  heat.run={id:body.run,document:JSON.parse(JSON.stringify(target)),replace};heat.failure=null;
  heat.status={status:'running',step:body.reused?'solve':'mesh',elapsed_s:0,expected_s:body.estimate.seconds};
  ctx.render();pollRun(body.run);document===null&&globalThis.document.getElementById('m3-run-cancel')?.focus();
 }
 function pollRun(id){
  clearTimeout(heat.timer);
  heat.timer=setTimeout(async()=>{
   if(heat.run?.id!==id)return;
   let s;
   try{s=await ctx.get(`/api/model3d/runs/${encodeURIComponent(id)}`);}
   catch(e){if(heat.run?.id===id){heat.run=null;lastNotice={text:'Lost the run: '+e.message,undo:false};ctx.render();}return;}
   if(heat.run?.id!==id)return;
   heat.status=s;
   if(s.status==='running'){const box=globalThis.document.querySelector('.m3-run-job');if(box)box.outerHTML=runJob();else if(shown)ctx.render();pollRun(id);return;}
   if(s.status==='done'){await runDone(id);return;}
   const run=heat.run;heat.run=null;
   if(s.status==='error'){heat.failure={document:run.document,message:s.error?.message||'unknown error'};lastNotice=null;}
   else lastNotice={text:runProgress(s),undo:false};
   ctx.render();
  },400);
 }
 async function runDone(id){
  let record;
  try{record=await ctx.get(`/api/model3d/runs/${encodeURIComponent(id)}/record?maps=kept`);}
  catch(e){heat.run=null;lastNotice={text:'The run could not be read: '+e.message,undo:false};ctx.render();return;}
  if(heat.run?.id!==id)return;
  const run=heat.run;heat.run=null;
  let i;
  // the regions around Tmax's and Tmin's nodes of this live run (/extremes), beside its stored record
  try{heat.liveValues.set(id,await ctx.get(`/api/model3d/runs/${encodeURIComponent(id)}/extremes`));}catch{}
  if(run.replace!==null&&heat.records[run.replace]){i=run.replace;heat.records[i]=record;heat.live[i]=id;}
  else{heat.records.push(record);heat.live.push(id);
   while(heat.records.length>MAX_RUNS){heat.records.shift();heat.live.shift();}
   i=heat.records.length-1;}
  heat.fresh=i;selection=`run:${i+1}`;showRun(i);
  lastNotice={text:runCompleteText(i,withExtremes(record.values,heat.liveValues.get(id))),undo:false};
  ctx.onHistory();ctx.render();
 }
 async function cancelRun(){
  const run=heat.run;if(!run)return;
  clearTimeout(heat.timer);
  let body;
  try{body=await ctx.request(`/api/model3d/runs/${encodeURIComponent(run.id)}/cancel`,{});}
  catch(e){lastNotice={text:'Cancel was refused: '+e.message,undo:false};renderDock();pollRun(run.id);return;}
  if(heat.run?.id!==run.id)return;
  if(body.cancelled===false&&body.status==='done'){await runDone(run.id);return;}
  if(body.cancelled===false){pollRun(run.id);return;}
  heat.run=null;heat.status={status:'cancelled'};lastNotice={text:body.message||'Run cancelled; nothing kept.',undo:false};
  ctx.render();globalThis.document.getElementById('m3-run')?.focus();
 }
 async function probeAt(point){
  const i=heat.shown,id=heat.live[i];if(i===null||!id)return;
  const u=shownUnit(heat.records[i].surface.unit);
  try{const a=await ctx.request(`/api/model3d/runs/${encodeURIComponent(id)}/probe`,{point});
   heat.probe={point,text:a.ok===false?a.refused:`T = ${Number(a.temperature.value.toPrecision(6))} K at (${point.map(x=>Number(Number(x).toPrecision(4))).join(', ')}) ${u}, in ${a.region}.`};}
  catch(e){heat.probe={point,text:e.message};}
  ctx.render();
 }
 function runAction(act){
  const i=heat.shown,rec=heat.records[i];if(!rec)return;
  if(act==='inputs'){commit(JSON.parse(JSON.stringify(rec.document)));lastNotice={text:`The model now has Run ${i+1}'s inputs; Undo restores the earlier ones.`,undo:true};ctx.render();return;}
  if(act==='recompute'){startRun(rec.document,i);return;}
  if(act==='json'){const url=URL.createObjectURL(new Blob([JSON.stringify(rec,null,1)],{type:'application/json'}));
   const a=globalThis.document.createElement('a');a.href=url;a.download=`run-${i+1}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
 }
 // ---- slice C's mesh job: start, poll, cancel, the result ----
 function meshJob(){
  const s=mesh.status;if(!s)return '';
  const steps=stepList(s);
  return `<div class="m3-mesh-job" aria-live="polite"><p id="m3-mesh-progress"${longer(s)?' class="longer"':''}>${esc(progressText(s))}</p>`+
   (s.status==='cancelled'?'':`<ol id="m3-mesh-steps">${steps.map(t=>`<li class="${t.state}"${t.state==='current'?' aria-current="step"':''}>${esc(t.label)}</li>`).join('')}</ol>`)+`</div>`;
 }
 function stopJob(){
  clearTimeout(mesh.timer);mesh.timer=null;
  const job=mesh.job;mesh.job=null;
  if(job)ctx.request(`/api/model3d/jobs/${encodeURIComponent(job)}/cancel`,{}).catch(()=>{});
 }
 /** V11: the ribbon's Run: as the header's Run when it is allowed (or a kept run answers), else the header's reason in Messages. */
 function runFromRibbon(){
  if(heat.run)return;
  const why=runReason({drafts:drafts.size,refused,check,running:!!mesh.job,doc,failure:heat.failure},WORDS);
  if(why&&keptRunFor(doc,heat.records)<0){lastNotice={text:why,undo:false};renderDock();return;}
  startRun();
 }
 /** U8: the ribbon's Mesh in a 3D model meshes when Mesh is allowed; otherwise Messages gives the header's reason. */
 function meshFromRibbon(){
  const why=meshReason({drafts:drafts.size,refused,check,running:!!mesh.job||!!heat.run},WORDS);
  if(!why){startMesh();return;}
  lastNotice={text:why,undo:false};renderDock();
 }
 async function startMesh(){
  if(mesh.job||meshReason({drafts:drafts.size,refused,check},WORDS))return;
  let body;
  try{body=await ctx.request('/api/model3d/mesh',{doc,component:componentName(doc)});}
  catch(e){lastNotice={text:'Mesh not started: '+e.message,undo:false};ctx.render();return;}
  mesh.job=body.job;
  if(body.status==='done'){await meshDone(body.job,{status:'done',step:'ready',reused:true,expected_s:body.estimate.seconds,elapsed_s:0});return;}
  mesh.status={status:'running',step:'forming',expected_s:body.estimate.seconds,elapsed_s:0};
  ctx.render();poll(body.job);
  document.getElementById('m3-mesh-cancel')?.focus();
 }
 function poll(job){
  clearTimeout(mesh.timer);
  mesh.timer=setTimeout(async()=>{
   if(mesh.job!==job)return;
   let s;
   try{s=await ctx.get(`/api/model3d/jobs/${encodeURIComponent(job)}`);}
   catch(e){if(mesh.job===job){mesh.job=null;lastNotice={text:'Lost the mesh job: '+e.message,undo:false};ctx.render();}return;}
   if(mesh.job!==job)return;
   mesh.status=s;
   if(s.status==='running'){updateJob();poll(job);return;}
   if(s.status==='done'){await meshDone(job,s);return;}
   mesh.job=null;lastNotice={text:progressText(s),undo:false};ctx.render();
  },400);
 }
 // a running job's progress changes in place (focus stays on Cancel meshing)
 function updateJob(){
  const box=document.querySelector('.m3-mesh-job');
  if(!box){if(shown)ctx.render();return;}
  box.outerHTML=meshJob();
 }
 async function meshDone(job,s){
  let view;
  try{view=await ctx.get(`/api/model3d/jobs/${encodeURIComponent(job)}/result`);}
  catch(e){mesh.job=null;lastNotice={text:'The mesh could not be read: '+e.message,undo:false};ctx.render();return;}
  if(mesh.job!==job)return;
  mesh.job=null;mesh.status=s;mesh.view=view;mesh.pane='mesh';
  heat.status=null;      // V7: the last run's status line belongs to the earlier mesh
  lastNotice={text:meshDoneText(view,s),undo:false};
  ctx.render();
 }
 async function cancelMesh(){
  const job=mesh.job;if(!job)return;
  clearTimeout(mesh.timer);
  let body;
  try{body=await ctx.request(`/api/model3d/jobs/${encodeURIComponent(job)}/cancel`,{});}
  catch(e){lastNotice={text:'Cancel was refused: '+e.message,undo:false};renderDock();poll(job);return;}
  if(mesh.job!==job)return;
  if(body.cancelled===false&&body.status==='done'){await meshDone(job,{status:'done',step:'ready',expected_s:0,elapsed_s:0});return;}
  if(body.cancelled===false){poll(job);return;}
  mesh.job=null;mesh.status={status:'cancelled'};lastNotice={text:CANCELLED,undo:false};
  ctx.render();document.getElementById('m3-mesh')?.focus();
 }
 function renderFaces(){
  const list=document.getElementById('m3-faces');if(!list||!lastGood)return;
  const had=document.activeElement?.closest?.('#m3-faces')?document.activeElement.dataset.face:null;
  list.innerHTML=lastGood.faces.map(f=>`<li tabindex="0" data-face="${f.id}" aria-label="face ${f.id}: ${esc(f.names.join(', '))}"${face===f.id?' class="active" aria-current="true"':''}><code>face ${f.id}</code><small>${esc(f.names.join(' '))}</small></li>`).join('');
  list.querySelectorAll('li').forEach(li=>{
   const pick=()=>{face=face===+li.dataset.face?null:+li.dataset.face;viewer?.select(face);renderFaces();renderNames();list.querySelector(`[data-face="${li.dataset.face}"]`)?.focus();};
   li.onclick=pick;li.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();pick();}};
  });
  if(had!==null)list.querySelector(`[data-face="${had}"]`)?.focus();
 }
 function renderNames(){
  const box=document.getElementById('m3-names');if(!box)return;
  const f=face===null||!lastGood?null:lastGood.faces[face];
  box.dataset.face=f?String(f.id):'';
  if(!f){box.innerHTML='<h3>Names</h3><p class="muted">Pick a face in the view or in the faces list.</p>';return;}
  const raw=faceLines(lastGood,f),lines={...raw,title:shownText(raw.title),detail:shownText(raw.detail)},can=f.alone.length>0&&!refused;
  box.innerHTML=`<h3>Names</h3><p>${esc(lines.title)}</p><p class="muted">${esc(lines.detail)} · sides ${esc(lines.sides)}</p><ul>${nameScopes(lastGood,f).map(([n,scope])=>`<li><code>${esc(n)}</code> <small class="m3-name-scope">${esc(scope)}</small></li>`).join('')}</ul><p class="muted" id="m3-names-any">${esc(NAMES_ANY)}</p>`+
   (interiorHint(f)?`<p class="muted" id="m3-names-interior">${esc(interiorHint(f))}</p>`:'')+
   `<div class="m3-use"><label>Use for <select id="m3-use"><option value="new">New selection</option><option value="fixed">Fixed temperature</option></select></label><label for="m3-use-name" id="m3-use-name-label">Selection name</label><input id="m3-use-name" value="${esc(suggestName(f))}" spellcheck="false"><span id="m3-use-temp-box" hidden><label for="m3-use-temp">Temperature (K)</label><input id="m3-use-temp" placeholder="e.g. 330" inputmode="decimal" spellcheck="false" aria-describedby="m3-use-temp-why"></span><button type="button" id="m3-use-go"${can?'':' disabled aria-describedby="m3-use-why"'}>Apply</button>`+
   (can?'':`<small id="m3-use-why">${esc(refused?'The geometry cannot be formed; fix the problem in Messages first.':'No single name selects this face alone.')}</small>`)+`<small id="m3-use-temp-why" hidden></small></div>`;
  const go=box.querySelector('#m3-use-go'),use=box.querySelector('#m3-use'),nameInput=box.querySelector('#m3-use-name');
  // V1: Fixed temperature takes its value here; Apply waits for a valid one and says why
  const tempBox=box.querySelector('#m3-use-temp-box'),temp=box.querySelector('#m3-use-temp'),tempWhy=box.querySelector('#m3-use-temp-why');
  const gate=()=>{const fixed=use.value==='fixed',why=fixed?useTemperatureProblem(temp.value):null;
   tempBox.hidden=!fixed;tempWhy.hidden=!why;tempWhy.textContent=why||'';
   go.disabled=!can||!!why;if(why)go.setAttribute('aria-describedby','m3-use-temp-why');else go.removeAttribute('aria-describedby');};
  use.onchange=()=>{const fixed=use.value==='fixed';
   nameInput.value=fixed?boundaryNameFor(f,doc.geometry.components[componentName(doc)].features.map(x=>x.name))||'':suggestName(f);
   box.querySelector('#m3-use-name-label').textContent=fixed?'Boundary name':'Selection name';gate();};
  temp.oninput=gate;
  temp.onkeydown=e=>{if(e.key==='Enter'&&!go.disabled)go.click();};
  go.onclick=()=>{
   if(use.value==='fixed'){if(!useTemperatureProblem(temp.value))fixedOn(nameInput.value.trim(),temp.value);return;}
   newSelection(f.id,nameInput.value.trim());
  };
 }
 // Use for → Fixed temperature: the edit goes to the server's check first, and a face the heat kind
 // refuses (an inner face) is not written; Messages shows the kind's words, the document is unchanged
 async function fixedOn(name,raw){
  let next;
  try{next=setFixedTemperature(doc,name,raw);}catch(e){lastNotice={text:e.message,undo:false};renderDock();return;}
  let a;
  try{a=await ctx.request('/api/model3d/check',{doc:next,component:componentName(next)});}catch(e){lastNotice={text:e.message,undo:false};renderDock();return;}
  if(a.ok&&a.run?.ok===false&&a.run.refused!==check?.run?.refused){
   lastNotice={text:a.run.refused,undo:false,error:true,details:a.run.code||null};renderDock();
   globalThis.document.querySelector('[data-m3-use-refusal] > p')?.focus();return;}
  // the new node opens in Settings with its Temperature focused
  pendingFocus=`[data-m3-heat="fixed"][data-m3-key="${CSS.escape(name)}"]`;
  commit(next);selection=`heat:fixed:${name}`;lastNotice={text:fixedNoticeText(name,next),undo:true};ctx.render();
 }
 function suggestName(f){
  const taken=new Set(Object.keys(doc.geometry.components[componentName(doc)].selections||{}));
  const base=(f.alone[0]||'face').replace(/[^A-Za-z0-9_]/g,'_');let name=base,k=2;while(taken.has(name))name=`${base}_${k++}`;return name;
 }
 async function newSelection(id,name){
  let reply;
  try{reply=await ctx.request('/api/model3d/selection',{doc,component:componentName(doc),face:id,name});}
  catch(e){ctx.notice('Selection not made: '+e.message);return;}
  if(!reply.ok){lastNotice={text:reply.refused,undo:false,details:refusalMessage(reply).details};renderDock();ctx.notice(reply.refused);return;}
  commit(reply.doc);selection='form';lastNotice={text:`Selection ${name} made from face ${id}.`,undo:true};ctx.render();
 }

 // ---- Messages ----
 function renderDock(){
  const box=$('mp-messages');if(!box)return;box.hidden=!shown;if(!shown)return;
  box.dataset.m3State=checking?'checking':'checked';
  const parts=[];
  if(refused){const m=refusalMessage(refused);
   // V10: a cylinder across a domain side: the plain suggestion first, the engine's sentence and key under Details
   const advice=crossingAdvice(refused,doc,lastDomain);
   parts.push(`<div class="mp-message error" data-m3-refusal><p>${esc(advice||m.text)}</p><div class="mp-message-actions">${m.feature!==null?`<button type="button" data-m3-show="feature:${m.feature}">Show</button>`:''}</div>`+
    (m.details||advice?`<details><summary>Details</summary><code>${esc(refused.code||'')}</code>${refused.path?` at <code>${esc(refused.path)}</code>`:''}${advice?`<p>${esc(refused.refused)}</p>`:''}</details>`:'')+`</div>`);}
  const off=refused?null:meshRefusal(check);
  if(off){const m=refusalMessage(off),at=m.feature!==null?`feature:${m.feature}`:'mesh';
   // an estimate refusal in plain words; the engine's sentence (with its formula) and key under Details
   const plain=meshRefusalText(off,doc.geometry.components[componentName(doc)].length_unit),own=plain!==off.refused;
   parts.push(`<div class="mp-message error" data-m3-refusal data-m3-mesh-refusal><p>${esc(own?plain:m.text)}</p><div class="mp-message-actions"><button type="button" data-m3-show="${at}">Show</button></div>`+
    (m.details||own?`<details><summary>Details</summary><code>${esc(off.code||'')}</code>${off.path?` at <code>${esc(off.path)}</code>`:''}${own?`<p>${esc(off.refused)}</p>`:''}</details>`:'')+`</div>`);}
  if(!refused&&!off&&check?.run?.ok===false&&heatOf(doc))
   parts.push(`<div class="mp-message error" data-m3-refusal data-m3-run-refusal><p>${esc(check.run.refused)}</p><div class="mp-message-actions"><button type="button" data-m3-show="heat">Show</button></div>`+
    (check.run.code?`<details><summary>Details</summary><code>${esc(check.run.code)}</code></details>`:'')+`</div>`);
  if(heat.failure&&runReason({check,doc,failure:heat.failure},WORDS)===heat.failure.message)
   parts.push(`<div class="mp-message error" data-m3-run-failure><p>${esc(heat.failure.message)}</p><div class="mp-message-actions"><button type="button" data-m3-show="heat">Show</button></div></div>`);
  if(lastNotice)parts.push(`<div class="mp-message ${lastNotice.error?'error" data-m3-use-refusal':'info"'}><p>${esc(lastNotice.text)}</p><div class="mp-message-actions">${lastNotice.undo?'<button type="button" data-m3-undo>Undo</button>':''}</div>${lastNotice.details?`<details><summary>Details</summary><code>${esc(lastNotice.details)}</code></details>`:''}</div>`);
  if(drafts.size)parts.push(`<div class="mp-message warning"><p>${esc(blockReason({drafts:drafts.size}))}</p></div>`);
  box.innerHTML=parts.join('')||(checking?'<p class="muted">Checking the geometry…</p>':'<p class="muted">No problems: the geometry passes the check.</p>');
  box.querySelectorAll('.mp-message > p').forEach(p=>p.tabIndex=0);     // each message is reached by Tab
  box.querySelectorAll('[data-m3-show]').forEach(b=>b.onclick=()=>choose(b.dataset.m3Show));
  box.querySelector('[data-m3-undo]')?.addEventListener('click',()=>{undo();lastNotice=null;renderDock();});
 }

 // ---- C3: Compare, two runs of this 3D model ----
 function comparePair(){
  const ids=heat.records.map(r=>r.run),pair=defaultPair(ids.length);if(!pair)return null;
  let a=ids.indexOf(compare.a),b=ids.indexOf(compare.b);
  if(a<0||b<0){[a,b]=pair;compare.a=ids[a];compare.b=ids[b];}
  return [a,b];
 }
 function comparePage(host){
  const pair=comparePair();
  if(!pair){host.innerHTML=`<h2>Compare</h2><p id="m3-compare-none">${esc(NEEDS_TWO)}</p>`;return;}
  const [ia,ib]=pair,A=heat.records[ia],B=heat.records[ib],unit=B.surface?.unit||A.surface?.unit||doc.geometry.components[componentName(doc)].length_unit;
  const pick=(id,label,at)=>`<label>${label} <select id="${id}">${heat.records.map((r,i)=>`<option value="${i}"${i===at?' selected':''}>Run ${i+1}</option>`).join('')}</select></label>`;
  const rows=compareRows(A,B,unit),changes=inputChanges(A.document,B.document),notice=meshNotice(A,B);
  // the surface ΔT: on a shared mesh, from both runs' surface maps (B − A per surface node)
  let d=null,why='';
  if(!notice){const ta=A.surface?.temperature,tb=B.surface?.temperature;
   if(ta&&tb)d=surfaceDelta(decode(ta,Float32Array),decode(tb,Float32Array));
   if(!d)why='Recompute to compare the surface.';}
  host.innerHTML=`<h2>Compare</h2><div class="m3-compare-pick" role="group" aria-label="Runs compared">${pick('m3-compare-a','Run A',ia)}${pick('m3-compare-b','Run B',ib)}</div>`+
   `<table class="m3-values m3-compare" id="m3-compare-values"><thead><tr><th scope="col">Quantity</th><th scope="col">Run ${ia+1} (A)</th><th scope="col">Run ${ib+1} (B)</th><th scope="col">B − A</th></tr></thead>`+
   `<tbody>${rows.map(r=>`<tr><th scope="row">${esc(r[0])}</th><td>${esc(r[1])}</td><td>${esc(r[2])}</td><td>${esc(r[3])}</td></tr>`).join('')}</tbody></table>`+
   (heatRateNote(A.values,B.values)?`<p class="muted" id="m3-compare-sign">${esc(heatRateNote(A.values,B.values))}</p>`:'')+
   `<h3 id="m3-compare-inputs-heading">Inputs that differ</h3>`+(changes.length?`<ul id="m3-compare-inputs" aria-labelledby="m3-compare-inputs-heading">${changes.map(c=>`<li>${esc(c)}</li>`).join('')}</ul>`:`<p id="m3-compare-inputs">${esc(SAME_INPUTS)}</p>`)+
   `<h3>Surface temperature, B − A</h3>`+
   (notice?`<p class="m3-notice" id="m3-compare-mesh" role="note">${esc(notice)}</p>`:why?`<p class="muted" id="m3-compare-recompute">${esc(why)}</p>`:
    `<div class="m3-stage"><div id="m3-compare-slot"></div></div><div class="m3-colourbar" id="m3-compare-legend" role="img" aria-label="${esc(deltaLegend(d))}, blue to red"><span class="m3-cb-title">${esc(deltaLegend(d))}</span><span class="m3-ramp" data-ramp="linear-gradient(to right,${ramp(d.min,d.max)})"></span></div>`);
  host.querySelectorAll('.m3-ramp').forEach(r=>{r.style.background=r.dataset.ramp;});
  const choose2=(which,i)=>{compare[which]=heat.records[i]?.run??null;ctx.render();document.getElementById(`m3-compare-${which}`)?.focus();};
  host.querySelector('#m3-compare-a').onchange=e=>choose2('a',+e.target.value);
  host.querySelector('#m3-compare-b').onchange=e=>choose2('b',+e.target.value);
  if(d){
   if(!compare.canvas){compare.canvas=document.createElement('canvas');compare.canvas.id='m3-compare-canvas';compare.canvas.tabIndex=0;
    compare.canvas.setAttribute('aria-label','Surface temperature difference B − A, blue at its minimum and red at its maximum. Arrow keys rotate, plus and minus zoom, F fits.');
    compare.viewer=new TemperatureView3D(compare.canvas,{onPick:()=>{},onCamera:what=>{compare.canvas.dataset.camera=what;}});}
   host.querySelector('#m3-compare-slot').append(compare.canvas);
   const key=`${A.run}|${B.run}`;
   if(compare.source!==key){compare.source=key;
    compare.viewer.load({...B.surface,temperature:encodeF32(d.delta),temperature_min:{value:d.min,unit:'K'},temperature_max:{value:d.max,unit:'K'}});}
  }
 }

 // ---- the page ----
 function renderPage(){
  const page=ctx.ui.page,main=document.querySelector('main');
  main.dataset.page=page;main.classList.toggle('connecting',false);main.classList.toggle('choosing',page==='Applications');main.classList.remove('comparing');
  $('view-title').textContent=page==='Applications'?'Model library':'Graphics';
  $('view-detail').textContent=page==='Applications'?(ctx.projectLine?.()||'Choose a model'):'Interactive 3D view';
  markPageTabs(document.querySelector('.page-tabs'),page==='Applications'?'Applications':page==='Compare'?'Compare':'Model');
  if(page==='Compare'){$('view-title').textContent='Compare';$('view-detail').textContent='Two runs of this 3D model';}
  document.querySelectorAll('[data-command-node]').forEach(b=>{b.disabled=page==='Applications';b.onclick=()=>{const key=({Geometry:'geometry',Materials:'materials',Mesh:'mesh',Study:'study'})[b.dataset.commandNode];choose(key);if(key==='mesh')meshFromRibbon();};});
  document.querySelectorAll('[data-view]').forEach(b=>b.hidden=true);
  const toolbar=document.querySelector('.workspace > .toolbar');if(toolbar)toolbar.style.display=page==='Model'?'flex':'none';
  $('breadcrumb').textContent='Model / '+(rows().find(r=>r.key===selection)?.label||'Geometry 1');
  document.querySelector('.workspace > .note').textContent='A 3D model of boxes, slab layers, cylinders and spheres: Mesh 1 meshes it, Run solves steady heat.';
  $('solver-log').hidden=true;$('workflow').hidden=true;
  for(const id of ['run-optical','run-heat','run-joule','run-multiphysics','run-multiphysics-reason','add-physics','add-coupling','run-options','run-baseline-option'])if($(id))$(id).hidden=true;
  // V11: the ribbon's Compute has Run for the 3D model (it runs, or Messages gives the header's reason)
  let run3=$('run-model3d');
  if(!run3){run3=document.createElement('button');run3.type='button';run3.id='run-model3d';run3.textContent='Run';
   document.querySelector('.solve-commands .ribbon-commands')?.prepend(run3);}
  run3.hidden=page==='Applications';run3.disabled=!!heat.run;run3.onclick=()=>runFromRibbon();
  const steps=$('sequence');if(steps)steps.innerHTML='<span class="sequence-empty">Study 1 · Steady: Run meshes the component and solves Heat transfer (3D).</span>';
  drawTree();
  const inspector=$('inspector');inspector.innerHTML=settings();bindSettings(inspector);
  const host=$('canvas');
  if(page==='Applications')ctx.applications(host);
  else if(page==='Compare')comparePage(host);
  else graphics(host);
  renderDock();
 }

 return {
  card:()=>card,kind:'model3d',
  /** The session file name Export suggests: the card's, else the card 1 name of before. */
  sessionFile:()=>(CARDS3D.find(c=>c.id===card)||CARD3D).sessionFile,
  active:()=>shown,inProject:()=>inProject,
  open,
  /** A model3d session read by parseSession: its document (and the title the project gives it). */
  openSession:(session,{asTitle,card:from}={})=>open(session.document,{asTitle,runs:session.runs||[],card:from}),
  show(){if(!inProject)return;shown=true;ctx.ui.page='Model';ctx.render();},
  leave(){stopJob();stopRun();shown=false;if($('run-model3d'))$('run-model3d').hidden=true;const box=$('mp-messages');if(box){box.hidden=true;box.replaceChildren();delete box.dataset.m3State;}},
  close(){stopJob();stopRun();card=null;heat.records=[];heat.live=[];heat.liveValues=new Map();mesh.view=null;mesh.status=null;shown=false;inProject=false;doc=null;history=null;check=null;refused=null;lastGood=null;},
  renderPage,
  canUndo:()=>!!history?.canUndo,canRedo:()=>!!history?.canRedo,
  undo(){if(!history?.canUndo)return;doc=history.undo();drafts.clear();runCheck();ctx.render();ctx.onHistory();},
  redo(){if(!history?.canRedo)return;doc=history.redo();drafts.clear();runCheck();ctx.render();ctx.onHistory();},
  drafts:()=>drafts.size,
  blockText:()=>drafts.size?blockReason({drafts:drafts.size}):null,
  projectTitle:()=>title,
  /** What "changed" counts for the project: the document and the kept runs (no view state). */
  contentStamp:()=>doc?documentDigest(doc)+'|'+heat.records.map(r=>r.run).join(','):null,
  sessionText:()=>writeModel3dSession(doc,null,heat.records),
  document:()=>doc,
  state:()=>({check,refused,selection,face,mesh:{job:mesh.job,status:mesh.status?.status||null,view:!!mesh.view,pane:mesh.pane},
   heat:{runs:heat.records.length,live:heat.live.slice(),running:heat.run?.id||null,status:heat.status?.status||null,shown:heat.shown,failure:heat.failure?.message||null}}),
 };
}
