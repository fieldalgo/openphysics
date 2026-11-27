// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// The 3D model's page in the workspace (slice B of the Studio 3D view; docs/packages/simcase/
// workspace.md, "3D models"): its tree, its property tables, the 3D view with picking, the faces
// list and Use for → New selection, and its Messages. Every edit sends the whole document to
// /api/model3d/check; the tree's coverage words and every refusal come from the server's exact
// complex. One Undo history holds the documents (no view state). No mesh, run or result here.
import {View3D} from '/model3d-assets/model3d-view.mjs';
import {faceLines,regionColor} from '/model3d-assets/model3d-model.mjs';
import {treeOpen,groupHeading,itemAttributes,treeState,bindTree,treeFocus,restoreTreeFocus} from './workspace-tree.mjs';
import {markPageTabs} from './workspace-tabs.mjs';
import {CARD3D,FEATURE_TYPES,Model3dHistory,addFeature,addLayer,addParameter,blockReason,componentName,deleteFeature,deleteParameter,deletedText,
 duplicateFeature,editField,featureLabel,fieldNote,fieldsOf,getField,moveFeature,refusalMessage,removeLayer,setParameter,shownUnit,treeRows} from './workspace-model3d.mjs';
import {writeModel3dSession,documentDigest} from './workspace-model3d-session.mjs';

const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]);

/**
 * ctx: {$, ui, notice(text), render(), request(url, body) → reply JSON (POST), applications(host),
 * onHistory(), projectLine()}. Returns the model's interface for workspace-app.mjs.
 */
export function createModel3dView(ctx){
 const {$}=ctx;
 let doc=null,title=CARD3D.title,history=null,shown=false,inProject=false;
 let check=null,refused=null,lastGood=null,request=0,checking=false;
 let selection='geometry',face=null,hidden=new Set();
 const drafts=new Map();          // field key → {raw, problem}
 const treeView=treeState();
 let viewer=null,canvas3d=null;
 let lastNotice=null;            // {text, undo}: a deletion's notice with its Undo

 // ---- the document and the check ----
 async function runCheck(){
  const id=++request;checking=true;renderDock();
  let reply;
  try{reply=await ctx.request('/api/model3d/check',{doc,component:componentName(doc)});}
  catch(e){reply={ok:false,refused:'The Studio server could not check the model: '+e.message,code:null,path:null,feature_index:null};}
  if(id!==request)return;
  checking=false;
  if(reply.ok){check=reply;refused=null;lastGood=reply.display;}else refused=reply;
  if(shown)ctx.render();
 }
 function commit(next,{record=true}={}){
  doc=next;if(record&&history.record(doc))ctx.onHistory();
  drafts.clear();runCheck();if(shown)ctx.render();
 }
 function open(document,{asTitle=CARD3D.title}={}){
  doc=JSON.parse(JSON.stringify(document));title=asTitle;history=new Model3dHistory(doc);
  check=null;refused=null;lastGood=null;selection='geometry';face=null;hidden=new Set();drafts.clear();lastNotice=null;
  inProject=true;shown=true;ctx.ui.page='Model';runCheck();ctx.render();
 }
 // ---- the tree ----
 function rows(){return treeRows(doc,check,refused);}
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
   `<span class="tree-node-mark" aria-hidden="true">${r.key.startsWith('feature:')?'▣':r.key==='form'?'◆':'·'}</span>${esc(r.label)}`+
   (r.problem?`<span class="problem-badge" role="img" aria-label="problem: ${esc(refusalMessage(refused).text)}" title="${esc(refusalMessage(refused).text)}">!</span>`:'')+
   (r.note?`<span class="m3-note">${esc(r.note)}</span>`:'')+`</button>`;
  // Component 1 · 3D · <unit> is the group heading; Parameters, Geometry 1 and Materials sit in it
  const head=all.find(r=>r.key==='component'),name='Component 1';
  return `<div class="pane-title"><span>Model builder</span><span class="pane-detail">3D model</span></div>${treeOpen()}`+
   `<section class="tree-group" role="none">${groupHeading(name,!treeView.collapsed.has(name),head.label)}${all.filter(r=>r.key!=='component').map(item).join('')}</section></div>`+
   `<div class="capability-card"><span class="capability-dot" aria-hidden="true"></span><strong>3D geometry (experimental)</strong><p>Boxes and slab layers, checked by the exact engine. Meshing and heat come in a later step.</p></div>`;
 }
 function choose(key){selection=key;ctx.ui.page='Model';ctx.render();}

 // ---- edits ----
 function move(i,delta){try{commit(moveFeature(doc,i,delta));selection=`feature:${i+delta}`;ctx.render();focusRow(selection);}catch(e){ctx.notice(e.message);}}
 function focusRow(key){const b=$('tree')?.querySelector(`[data-m3-node="${CSS.escape(key)}"]`);if(b){b.tabIndex=0;b.focus();}}
 function remove(i){
  const f=doc.geometry.components[componentName(doc)].features[i];
  const text=deletedText(doc,i);commit(deleteFeature(doc,i));selection='geometry';lastNotice={text,undo:true};ctx.render();
 }
 function fieldInput(field){
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
  if(selection==='materials')return `<h3>Materials</h3><ul>${Object.entries(doc.materials||{}).map(([n,p])=>`<li><code>${esc(n)}</code> k = ${esc(p.thermal_conductivity??'—')}</li>`).join('')}</ul>`;
  return '';
 }
 function parametersTable(){
  const params=doc.geometry.parameters||{},info=new Map((check?.parameters||[]).map(p=>[p.name,p]));
  // a refusal about a parameter (E-DOMAIN, E-EXPRESSION-KIND, a cycle) is shown on its row
  const rowProblem=n=>refused&&new RegExp(`^geometry\\.parameters\\.${n}\\b`).test(refused.path||'')?refused.refused:'';
  const rowsHtml=Object.entries(params).map(([n,p])=>{const i=info.get(n),used=i?.used_by||[],problem=rowProblem(n);
   return `<tr${problem?' class="has-problem"':''}><th scope="row"><code>${esc(n)}</code></th><td><input data-m3-param="${esc(n)}" value="${esc(p.value)}" aria-label="value of ${esc(n)}"${problem?' aria-invalid="true"':''}>${problem?`<small class="m3-si">${esc(problem)}</small>`:''}</td>`+
    `<td>${esc(i?.kind||'')}</td><td>${esc(p.range?JSON.stringify(p.range):'')}</td><td>${i?esc(`= ${Number(i.value.toPrecision(6))} ${i.unit}`):''}</td><td>${used.length?esc(`used by ${used.length}`):'unused'}</td>`+
    `<td><button type="button" data-m3-unparam="${esc(n)}">Delete</button></td></tr>`;}).join('');
  return `<h3>Parameters</h3><table class="m3-params"><thead><tr><th>Name</th><th>Value</th><th>Kind</th><th>Range</th><th>SI value</th><th>Use</th><th></th></tr></thead><tbody>${rowsHtml||'<tr><td colspan="7" class="muted">No parameters.</td></tr>'}</tbody></table>`+
   `<form class="m3-param-add"><label>Name <input name="name" spellcheck="false"></label><label>Value <input name="value" spellcheck="false" placeholder="20 um"></label><button type="submit">Add parameter</button></form>`;
 }
 function bindSettings(host){
  host.querySelectorAll('[data-m3-field]').forEach(input=>input.addEventListener('change',()=>{
   const field=fieldsOf(doc,selection).find(f=>f.key===input.dataset.m3Field)||fieldsOf(doc,'domain').find(f=>f.key===input.dataset.m3Field);
   const out=editField(doc,field,input.value);
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
  host.querySelectorAll('[data-m3-add]').forEach(b=>b.onclick=()=>{commit(addFeature(doc,b.dataset.m3Add));selection=`feature:${doc.geometry.components[componentName(doc)].features.length-1}`;ctx.render();});
  host.querySelectorAll('[data-m3-param]').forEach(input=>input.addEventListener('change',()=>{try{commit(setParameter(doc,input.dataset.m3Param,input.value));}catch(e){ctx.notice(e.message);}}));
  host.querySelectorAll('[data-m3-unparam]').forEach(b=>b.onclick=()=>{
   const name=b.dataset.m3Unparam,used=(check?.parameters||[]).find(p=>p.name===name)?.used_by||[];
   try{commit(deleteParameter(doc,name,used));}catch(e){ctx.notice(e.message);lastNotice={text:e.message,undo:false};renderDock();}
  });
  const form=host.querySelector('.m3-param-add');
  if(form)form.onsubmit=e=>{e.preventDefault();try{commit(addParameter(doc,form.elements.name.value.trim(),form.elements.value.value));}catch(err){ctx.notice(err.message);}};
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
  const block=blockReason({refused,drafts:drafts.size});
  host.innerHTML=`<div class="m3-head"><h2>${esc(title)}</h2><div class="m3-run"><button type="button" disabled aria-describedby="m3-block">Mesh</button><button type="button" disabled aria-describedby="m3-block">Run</button><small id="m3-block">${esc(block)}</small></div></div>`+
   `<div class="m3-views" role="toolbar" aria-label="3D view">${['iso','+x','-x','+y','-y','+z','-z'].map(v=>`<button type="button" data-m3-view="${v}">${v==='iso'?'Iso':v.toUpperCase().replace('-','−')}</button>`).join('')}<button type="button" data-m3-fit>Fit</button></div>`+
   `<div class="m3-stage${refused?' stale':''}"><div id="m3-canvas-slot"></div>${refused&&lastGood?'<p class="m3-last">Last shape that could be formed</p>':''}</div>`+
   `<section class="m3-faces"><h3 id="m3-faces-heading">Faces</h3><ul id="m3-faces" aria-labelledby="m3-faces-heading"></ul></section>`+
   `<section class="m3-names" id="m3-names" aria-live="polite"></section>`+
   `<p class="muted">Lengths in ${esc(shownUnit(comp.length_unit))}. A face's names say which surface of which feature it lies on.</p>`;
  const v=ensureViewer();
  host.querySelector('#m3-canvas-slot').append(canvas3d);
  if(lastGood){
   if(v.view!==lastGood){v.setHidden([...hidden]);v.load(lastGood,{keep:!!v.view});}
   v.select(face);
  }
  host.querySelectorAll('[data-m3-view]').forEach(b=>b.onclick=()=>v.setView(b.dataset.m3View));
  host.querySelector('[data-m3-fit]').onclick=()=>v.fit();
  renderFaces();renderNames();
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
  const lines=faceLines(lastGood,f),can=f.alone.length>0&&!refused;
  box.innerHTML=`<h3>Names</h3><p>${esc(lines.title)}</p><p class="muted">${esc(lines.detail)} · sides ${esc(lines.sides)}</p><ul>${lines.names.map(n=>`<li><code>${esc(n)}</code></li>`).join('')}</ul>`+
   `<div class="m3-use"><label>Use for <select id="m3-use"><option value="new">New selection</option></select></label><input id="m3-use-name" aria-label="new selection name" value="${esc(suggestName(f))}" spellcheck="false"><button type="button" id="m3-use-go"${can?'':' disabled aria-describedby="m3-use-why"'}>Apply</button>`+
   (can?'':`<small id="m3-use-why">${esc(refused?'The geometry cannot be formed; fix the problem in Messages first.':'No single name selects this face alone.')}</small>`)+`</div>`;
  const go=box.querySelector('#m3-use-go');
  go.onclick=()=>newSelection(f.id,box.querySelector('#m3-use-name').value.trim());
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
   parts.push(`<div class="mp-message error" data-m3-refusal><p>${esc(m.text)}</p><div class="mp-message-actions">${m.feature!==null?`<button type="button" data-m3-show="feature:${m.feature}">Show</button>`:''}</div>`+
    (m.details?`<details><summary>Details</summary><code>${esc(refused.code||'')}</code>${refused.path?` at <code>${esc(refused.path)}</code>`:''}</details>`:'')+`</div>`);}
  if(lastNotice)parts.push(`<div class="mp-message info"><p>${esc(lastNotice.text)}</p><div class="mp-message-actions">${lastNotice.undo?'<button type="button" data-m3-undo>Undo</button>':''}</div>${lastNotice.details?`<details><summary>Details</summary><code>${esc(lastNotice.details)}</code></details>`:''}</div>`);
  if(drafts.size)parts.push(`<div class="mp-message warning"><p>${esc(blockReason({drafts:drafts.size}))}</p></div>`);
  box.innerHTML=parts.join('')||(checking?'<p class="muted">Checking the geometry…</p>':'<p class="muted">No problems: the geometry passes the check.</p>');
  box.querySelectorAll('[data-m3-show]').forEach(b=>b.onclick=()=>choose(b.dataset.m3Show));
  box.querySelector('[data-m3-undo]')?.addEventListener('click',()=>{undo();lastNotice=null;renderDock();});
 }

 // ---- the page ----
 function renderPage(){
  const page=ctx.ui.page,main=document.querySelector('main');
  main.dataset.page=page;main.classList.toggle('connecting',false);main.classList.toggle('choosing',page==='Applications');main.classList.remove('comparing');
  $('view-title').textContent=page==='Applications'?'Model library':'Graphics';
  $('view-detail').textContent=page==='Applications'?(ctx.projectLine?.()||'Choose a model'):'Interactive 3D view';
  markPageTabs(document.querySelector('.page-tabs'),page==='Applications'?'Applications':'Model');
  document.querySelectorAll('[data-command-node]').forEach(b=>{b.disabled=page==='Applications';b.onclick=()=>choose(({Geometry:'geometry',Materials:'materials',Mesh:'form',Study:'form'})[b.dataset.commandNode]);});
  document.querySelectorAll('[data-view]').forEach(b=>b.hidden=true);
  const toolbar=document.querySelector('.workspace > .toolbar');if(toolbar)toolbar.style.display=page==='Model'?'flex':'none';
  $('breadcrumb').textContent='Model / '+(rows().find(r=>r.key===selection)?.label||'Geometry 1');
  document.querySelector('.workspace > .note').textContent='A 3D model of boxes and slab layers. Meshing and heat come in a later step.';
  $('solver-log').hidden=true;$('workflow').hidden=true;
  for(const id of ['run-optical','run-heat','run-joule','run-multiphysics','run-multiphysics-reason','add-physics','add-coupling','run-options','run-baseline-option'])if($(id))$(id).hidden=true;
  const steps=$('sequence');if(steps)steps.innerHTML='<span class="sequence-empty">No study steps yet: meshing and heat come in a later step of the 3D model.</span>';
  drawTree();
  const inspector=$('inspector');inspector.innerHTML=settings();bindSettings(inspector);
  const host=$('canvas');
  if(page==='Applications')ctx.applications(host);
  else graphics(host);
  renderDock();
 }

 return {
  card:()=>CARD3D.id,kind:'model3d',
  active:()=>shown,inProject:()=>inProject,
  open,
  /** A model3d session read by parseSession: its document (and the title the project gives it). */
  openSession:(session,{asTitle}={})=>open(session.document,{asTitle}),
  show(){if(!inProject)return;shown=true;ctx.ui.page='Model';ctx.render();},
  leave(){shown=false;const box=$('mp-messages');if(box){box.hidden=true;box.replaceChildren();delete box.dataset.m3State;}},
  close(){shown=false;inProject=false;doc=null;history=null;check=null;refused=null;lastGood=null;},
  renderPage,
  canUndo:()=>!!history?.canUndo,canRedo:()=>!!history?.canRedo,
  undo(){if(!history?.canUndo)return;doc=history.undo();drafts.clear();runCheck();ctx.render();ctx.onHistory();},
  redo(){if(!history?.canRedo)return;doc=history.redo();drafts.clear();runCheck();ctx.render();ctx.onHistory();},
  drafts:()=>drafts.size,
  blockText:()=>drafts.size?blockReason({drafts:drafts.size}):null,
  projectTitle:()=>title,
  /** What "changed" counts for the project: the document only (no view state). */
  contentStamp:()=>doc?documentDigest(doc):null,
  sessionText:()=>writeModel3dSession(doc),
  document:()=>doc,
  state:()=>({check,refused,selection,face}),
 };
}
