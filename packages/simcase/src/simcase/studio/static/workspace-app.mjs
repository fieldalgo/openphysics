import {NotebookAutosave,indexedNotebookStore,readNotebookRecovery} from './workspace-notebook-recovery.mjs';
import {lineProfile,profileCsv,drawProfile} from './workspace-profile.mjs';
import {OpticalPreflight} from './workspace-preflight.mjs';
import {opticalWorkflow} from './workspace-workflow.mjs';
import {MeshPreview,drawMesh} from './workspace-mesh.mjs';
import {probeField} from './workspace-probe.mjs';
import {OpticalJobMonitor,readPending,storePending,validatePending} from './workspace-job.mjs';
import {readRecovery,writeRecovery} from './workspace-recovery.mjs';
import {installWidthEditor} from './workspace-width-editor.mjs';
import {sectionSvg} from './workspace-section.mjs';
import {SchematicCamera,installViewport} from './workspace-viewport.mjs';
import {checkWorkspaceCapabilities} from './workspace-connection.mjs';
// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

import {INPUT_FIELDS,NumericDrafts} from './workspace-inputs.mjs';
import {installLayout} from './workspace-layout.mjs';
import {MAX_BYTES,DRAFT_KEY,validateProject,parseProject,snapshot} from './workspace-project.mjs';
import {WorkspaceStore} from './workspace-store.mjs';
import {readOpticalField,fieldScalars} from './workspace-field.mjs';
import {MAX_SESSION_BYTES,RUN_LIMIT,opticalSettings,validateRunLabel,runTableCsv,validateRun,appendRun,mergeRuns,createSession,parseSession} from './workspace-notebook.mjs';
import {opticalBlock as opticalSupport,opticalDocument as buildOpticalDocument} from './workspace-optical.mjs';
import {solverApi} from './workspace-api.mjs';
import {renderApplications,templatePhysics} from './workspace-applications.mjs';

(()=>{'use strict';const $=id=>document.getElementById(id);const ui={page:'Applications',selection:'Geometry',view:'Perspective',body:'Core'};const state={height:220,width:500,voltage:1,heat:true,structure:true,optics:true};const setup={materials:{Core:'Silicon',Oxide:'Silica',Heater:''},cooling:'',temperature:293.15,fixed:'',terminal:''};const pick={mode:'Bodies',boundary:null};const names=['Geometry','Materials','Electric currents','Heat transfer','Solid mechanics','Optical modes','Couplings','Mesh','Study'];
const cameras={Perspective:new SchematicCamera(),Section:new SchematicCamera()};
let refreshViewport=null;let disposeWidthEditor=()=>{};
const numericDrafts=new NumericDrafts();
const connection={ready:false,message:'Checking Studio compatibility…',version:null,instance:null};
const pair=(a,b)=>`<div class="pair"><span>${a}</span><strong>${b}</strong></div>`;
function select(name){pick.boundary=null;ui.selection=name;ui.page=name==='Couplings'?'Connections':'Model';render();}

const isOptical=()=>state.electric===false&&!state.heat&&!state.structure&&state.optics;
function bindWidthEditor(){disposeWidthEditor();disposeWidthEditor=()=>{};if(ui.page==='Model'&&ui.selection==='Geometry'&&isOptical()&&pick.mode==='Bodies')disposeWidthEditor=installWidthEditor($('canvas'),{width:state.width,height:state.height,blocked:()=>numericDrafts.invalid,commitHeight:value=>{edits.endGroup();state.height=value;trackEdit();edits.endGroup();render();notice('Core height updated. Run explicitly to compute new results.');},commit:value=>{edits.endGroup();state.width=value;trackEdit();edits.endGroup();render();notice('Core width updated. Run explicitly to compute new results.');}});}
function geom(){
if(isOptical())return sectionSvg(state.width,ui.body,pick.boundary,pick.mode,state.height);
const w=state.width/500;
const attrs=body=>`data-pick-body="${body}" role="button" tabindex="0" aria-label="Select ${body} body" stroke="${ui.body===body?'#fff0a8':'#7a939f'}" stroke-width="${ui.body===body?3:1}"`;
const edge=(id,path,label)=>`<g data-pick-edge="${id}" role="button" tabindex="0" aria-label="Select ${label}">${path==='M65 260 H535'?'<rect x="65" y="250" width="470" height="20" fill="transparent"/>':''}<path d="${path}" fill="none" stroke="transparent" stroke-width="20"/><path d="${path}" fill="none" stroke="${pick.boundary===id?'#fff0a8':'#b5c9d3'}" stroke-width="${pick.boundary===id?5:2}" pointer-events="none"/></g>`;
const section=ui.view==='Section';
const shapes=section?`<rect x="65" y="80" width="470" height="180" fill="#273f4a" ${attrs('Oxide')}/><rect x="${300-65*w}" y="150" width="${130*w}" height="55" fill="#80d7c0" ${attrs('Core')}/><rect x="220" y="100" width="160" height="16" fill="#cfa96f" ${attrs('Heater')}/><text x="300" y="50" text-anchor="middle" fill="#e2e9ed">Cross section · ${pick.mode==='Bodies'?'select a body':'select a boundary'}</text><text x="300" y="300" text-anchor="middle" fill="#a2b2bd">Core width ${state.width} nm · schematic</text>`:`<polygon points="65,160 365,65 550,165 250,275" fill="#2c444f" ${attrs('Oxide')}/><polygon points="65,160 250,275 250,300 65,185" fill="#21323c" ${attrs('Oxide')}/><polygon points="250,275 550,165 550,190 250,300" fill="#263b45" ${attrs('Oxide')}/><path d="M135 163 L421 77 L446 92 L160 180 Z" fill="#80d7c0" ${attrs('Core')}/><path d="M155 143 L410 68 L425 76 L170 152 Z" fill="#cfa96f" ${attrs('Heater')}/><text x="390" y="45" fill="#cfa96f">Heater end</text><text x="65" y="135" fill="#cfa96f">Heater start</text><text x="67" y="325" fill="#a2b2bd">Named boundaries · schematic, not CAD faces</text>`;
let edges='';if(pick.mode==='Boundaries')edges=section?edge('oxide-bottom','M65 260 H535','oxide bottom boundary'):edge('heater-start','M155 143 L170 152','heater start terminal')+edge('heater-end','M410 68 L425 76','heater end ground')+edge('left-end','M65 160 L250 275','left end support')+edge('right-end','M365 65 L550 165','right end support')+edge('oxide-bottom','M65 185 L250 300 L550 190','oxide bottom boundary');
return `<svg viewBox="0 0 600 350" role="group" aria-label="Selectable schematic geometry">${shapes}${edges}</svg>`;
}
function bindPicking(){
const bind=(el,fn)=>{el.onclick=fn;el.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();fn();}};};
$('canvas').querySelectorAll('[data-pick-body]').forEach(el=>{if(pick.mode!=='Bodies'){el.removeAttribute('tabindex');el.setAttribute('role','img');el.onclick=null;return;}bind(el,()=>{ui.body=el.dataset.pickBody;pick.boundary=null;ui.selection='Materials';render();});});
$('canvas').querySelectorAll('[data-pick-edge]').forEach(el=>bind(el,()=>{pick.boundary=el.dataset.pickEdge;ui.selection=pick.boundary.startsWith('optical-')?'Optical modes':pick.boundary.startsWith('heater')?'Electric currents':pick.boundary==='oxide-bottom'?'Heat transfer':'Solid mechanics';render();}));
}
function pickingPanel(){
if(ui.page!=='Model'||!$('canvas').querySelector('svg'))return;
const bar=document.createElement('div');bar.className='toolbar';bar.innerHTML=['Bodies','Boundaries'].map(v=>`<button data-pick-mode="${v}" aria-pressed="${pick.mode===v}">${v}</button>`).join('')+'<span>Click geometry or use Tab + Enter</span>';$('canvas').prepend(bar);
bar.querySelectorAll('[data-pick-mode]').forEach(el=>el.onclick=()=>{pick.mode=el.dataset.pickMode;pick.boundary=null;render();});
const hint=document.createElement('p');hint.className='muted';hint.textContent=pick.mode==='Bodies'?`Selected body: ${ui.body}`:isOptical()?'Optical window: select one of four fixed PEC edges.':ui.view==='Section'?'Cross section: oxide bottom. Switch to Perspective for longitudinal ends.':'Select a highlighted boundary to assign its condition.';$('canvas').append(hint);
bindPicking();
if(pick.mode==='Boundaries'&&pick.boundary){
const info=document.createElement('section');info.className='boundary-selection';
if(pick.boundary.startsWith('optical-')){const heading=document.createElement('h3');heading.textContent='Optical '+pick.boundary.slice(8)+' boundary';const note=document.createElement('p');note.textContent='PEC · fixed by the optical adapter. This edge is not a thermal boundary or a mechanical support.';info.append(heading,note);$('inspector').prepend(info);return;}
const id=pick.boundary;const labels={'heater-start':'Heater start','heater-end':'Heater end','oxide-bottom':'Oxide bottom','left-end':'Left end','right-end':'Right end'};
info.innerHTML=`<h3>Selected boundary: ${labels[id]}</h3>`;
let text,action;
if(id.startsWith('heater')){text='Assign start = terminal / end = ground';action=()=>setup.terminal='Heater start / heater end';}
else if(id==='oxide-bottom'){text='Assign fixed temperature to bottom';action=()=>setup.cooling='Oxide bottom: fixed temperature';}
else if(id==='left-end'){text='Fix left end';action=()=>setup.fixed='Left end fixed';}
else {text='Fix both ends (left + right)';action=()=>setup.fixed='Both ends fixed';}
const button=document.createElement('button');button.textContent=text;button.id='assign-boundary';button.onclick=()=>{action();render();refreshPersistence();notice('Boundary assignment updated. Named regions only; CAD mapping pending.');};info.append(button);$('inspector').prepend(info);
}
}
function active(){return ['Electric currents',...(state.heat?['Heat transfer']:[]),...(state.heat&&state.structure?['Solid mechanics']:[]),...(state.optics?['Optical modes']:[])];}
function render(){const focused=document.activeElement,focusId=focused?.id;const focusData=['node','body','pick-mode','pick-body','pick-edge','run'].map(key=>[key,focused?.getAttribute('data-'+key)]).find(([,value])=>value!==null&&value!==undefined);profileResize?.disconnect();profileRedraw=()=>{};disposeWidthEditor();disposeWidthEditor=()=>{};if(isOptical()){if(ui.page==='Model'&&['Electric currents','Heat transfer','Solid mechanics','Couplings'].includes(ui.selection))ui.selection='Geometry';ui.view='Section';if(ui.body==='Heater')ui.body='Core';if(pick.boundary&&!pick.boundary.startsWith('optical-'))pick.boundary=null;}else if(pick.boundary?.startsWith('optical-'))pick.boundary=null;document.querySelector('[data-view=Perspective]').disabled=isOptical();if(typeof fieldResize!=='undefined'&&fieldResize)fieldResize.disconnect();document.querySelectorAll('[data-page]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.page===ui.page));document.querySelectorAll('[data-view]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.view===ui.view));$('breadcrumb').textContent=ui.page+' / '+ui.selection;$('tree').innerHTML='<small>Model explorer</small><h3>Component 1</h3>'+names.filter(n=>!isOptical()||!['Electric currents','Heat transfer','Solid mechanics','Couplings'].includes(n)).map(n=>`<button data-node="${n}" aria-pressed="${ui.selection===n}">${n}</button>`).join('')+'<small>Capability</small><p>Optical adapter available · coupled solvers pending</p>';$('tree').querySelectorAll('[data-node]').forEach(b=>b.onclick=()=>select(b.dataset.node));
let inspector='<span class="muted">SELECTION</span><h2>'+ui.selection+'</h2>';
if(ui.selection==='Geometry')inspector+=`<label>Core width <output>${state.width} nm</output><input id="width" type="range" min="300" max="900" step="any" value="${state.width}"></label><label>Core width [nm]<input id="width-number" type="number" min="300" max="900" step="any" value="${state.width}"></label>`+(isOptical()?`<label>Core height [nm]<input id="height-number" type="number" min="100" max="500" step="any" value="${state.height}"></label>`:'')+pair('Bodies',isOptical()?'Core / silica background':'Core / oxide / heater')+pair('Representation',isOptical()?'2D optical input · nm':'Concept preview');
else if(ui.selection==='Electric currents')inspector+=`<label>Applied voltage [V]<input id="voltage" type="number" min="0" max="10" step="0.1" value="${state.voltage}"></label>`+pair('Terminal','Heater input')+pair('Ground','Heater output')+pair('Output','Joule heat [W/m³]');
else if(ui.selection==='Materials')inspector+=pair('Core',setup.materials.Core||'Unassigned')+pair('Cladding',setup.materials.Oxide||'Unassigned')+pair('Heater',setup.materials.Heater||'Unassigned')+'<p>Conductivity, thermal expansion, elasticity and optical material laws require validated assignments.</p>';
else if(ui.selection==='Solid mechanics')inspector+=pair('Load','Thermal strain')+pair('Constraints','Not assigned')+pair('Output','Displacement [m]');
else if(ui.selection==='Heat transfer')inspector+=pair('Source','Joule heat')+pair('Heat loss','Not assigned')+pair('Output','Temperature [K]');
else if(ui.selection==='Optical modes')inspector+=pair('Wavelength','1550 nm')+pair('Inputs',isOptical()?'Material at 1550 nm, geometry':'n(T), geometry')+pair('Output','Modes / effective index');
else inspector+=pair('Status','Not executed')+'<p>Settings and validation will be implemented behind package APIs.</p>';
inspector+='<p class="muted">Editing this design does not run a simulation.</p>';$('inspector').innerHTML=inspector;
if(ui.page==='Connections'&&isOptical()){$('canvas').innerHTML='<h2>Optical-only model</h2><p>This model has one optical interface and no coupled physics. Choose the heated-waveguide template to configure a multiphysics preview; coupled computation remains unavailable.</p><button id=choose-multiphysics>Choose another application</button>';$('choose-multiphysics').onclick=()=>{ui.page='Applications';render();};}
else if(ui.page==='Connections')$('canvas').innerHTML='<h2>Physics connections</h2><p>One-way sequence · design configuration</p><div class="flow"><button data-select="Electric currents"><strong>Electric currents</strong>Voltage → current density</button><label><input data-toggle="heat" type="checkbox" '+(state.heat?'checked':'')+'> Joule heating → Heat transfer</label><div class="arrow">Q [W/m³] → T [K]</div><label><input data-toggle="structure" type="checkbox" '+(state.structure?'checked':'')+' '+(!state.heat?'disabled':'')+'> Thermal expansion → Solid mechanics</label><div class="arrow">T [K] → displacement [m]</div><label><input data-toggle="optics" type="checkbox" '+(state.optics?'checked':'')+'> Optical modes · material / geometry update</label></div><p>Field mapping, deformed mesh and material laws are pending. Two-way feedback is not configured.</p>';
else if(ui.page==='Applications')renderApplications($('canvas'));
else if(ui.page==='Results')$('canvas').innerHTML='<h2>Results workspace</h2><p>Temperature · displacement · optical fields</p><div class="empty">No computed results<br>Run adapters are not connected.</div><p>Planned: common coordinates, time playback, probes and explicit deformation magnification.</p>';
else $('canvas').innerHTML='<h2>'+ui.selection+'</h2>'+geom();
$('sequence').innerHTML=active().map((n,i)=>`<span><b>${i+1}</b>${n}</span>`).join('')+'<span>Preflight pending</span>';
const width=$('width');if(width)width.oninput=()=>{state.width=+width.value;numericDrafts.clear('width');if($('width-number'))$('width-number').value=width.value;refreshInputIssues();width.previousElementSibling.textContent=state.width+' nm';if(ui.page==='Model'){const svg=$('canvas').querySelector('svg');if(svg){svg.outerHTML=geom();bindPicking();refreshViewport?.();bindWidthEditor();}}};const v=$('voltage');if(v)v.onchange=()=>{if(!v.checkValidity()||v.value===''){v.value=state.voltage;return;}state.voltage=+v.value;};
document.querySelectorAll('[data-toggle]').forEach(b=>b.onchange=()=>{state[b.dataset.toggle]=b.checked;if(b.dataset.toggle==='heat'&&b.checked)state.electric=true;render();});document.querySelectorAll('[data-select]').forEach(b=>b.onclick=()=>select(b.dataset.select));document.querySelectorAll('[data-template]').forEach(b=>b.onclick=()=>{Object.assign(state,templatePhysics(b.dataset.template));select('Geometry');});decorate();solverPanel();pickingPanel();bindNumericInputs();refreshInputIssues();refreshViewport=ui.page==='Model'?installViewport($('canvas'),cameras[ui.view]):null;bindWidthEditor();if(document.activeElement===document.body){const target=focusId?$(focusId):focusData?document.querySelector('[data-'+focusData[0]+'="'+CSS.escape(focusData[1])+'"]'):null;target?.focus({preventScroll:true});}}

function refreshInputIssues(){
 const host=$('input-problems');host.replaceChildren();host.hidden=!numericDrafts.invalid;
 for(const issue of numericDrafts.issues){
  const row=document.createElement('div'),message=document.createElement('span'),fix=document.createElement('button');
  message.textContent=issue.message+' Last valid value is retained.';fix.textContent='Edit '+INPUT_FIELDS[issue.key].label;fix.dataset.fixInput=issue.key;
  fix.onclick=()=>{select(INPUT_FIELDS[issue.key].node);$(INPUT_FIELDS[issue.key].id)?.focus();};row.append(message,fix);host.append(row);
 }
 if(numericDrafts.invalid){const discard=document.createElement('button');discard.id='discard-invalid';discard.textContent='Restore last valid values';discard.onclick=()=>{numericDrafts.clear();render();notice('Invalid drafts discarded. Last valid model inputs retained.');};host.append(discard);}
 for(const [key,field] of Object.entries(INPUT_FIELDS)){
  const el=$(field.id);if(!el)continue;const issue=numericDrafts.get(key);el.setAttribute('aria-invalid',String(!!issue));
  const hint=$(field.id+'-hint');if(hint)hint.textContent=issue?issue.message:`Allowed: ${field.min}–${field.max} ${field.unit}.`;
 }
 for(const id of ['save-project','save-draft','save-session','open-project','open-session','restore-draft'])$(id).disabled=numericDrafts.invalid;
 $('run-optical').disabled=solverBusy||!!pendingJob||!!opticalBlock()||!!retentionBlock()||numericDrafts.invalid;
 if(numericDrafts.invalid)$('status').textContent='Input errors · correct or restore the last valid values';
 else $('status').textContent=solverBusy?'Optical computation running':pendingJob?'Pending job · resume or detach':retentionBlock()|| (opticalBlock()?'Optical input unsupported · review Study':'Optical adapter ready · explicit Run required');
 refreshPersistence();
}
function bindNumericInputs(){
 for(const [key,field] of Object.entries(INPUT_FIELDS)){
  const el=$(field.id);if(!el)continue;el.step='any';const issue=numericDrafts.get(key);if(issue)el.value=issue.raw;
  const hint=document.createElement('p');hint.id=field.id+'-hint';hint.className='input-hint';el.closest('label').after(hint);el.setAttribute('aria-describedby',hint.id);
  el.oninput=()=>{const parsed=numericDrafts.update(key,el.value);if(parsed.ok){if(key==='temperature')setup.temperature=parsed.value;else state[key]=parsed.value;
   if(key==='width'||key==='height'){const slider=$('width');if(slider&&key==='width'){slider.value=parsed.value;slider.previousElementSibling.textContent=parsed.value+' nm';}const svg=$('canvas').querySelector('svg');if(svg){svg.outerHTML=geom();bindPicking();refreshViewport?.();bindWidthEditor();}}
  }refreshInputIssues();};
  el.onkeydown=e=>{if(e.key==='Escape'){numericDrafts.clear(key);el.value=key==='temperature'?setup.temperature:state[key];refreshInputIssues();}};
 }
}

function options(values,current){return values.map(v=>`<option value="${v}" ${v===current?'selected':''}>${v||'Not assigned'}</option>`).join('');}
function issues(){const out=[];for(const b of ['Core','Oxide',...(state.electric===false?[]:['Heater'])])if(!setup.materials[b])out.push(['Materials',b+' material missing']);if(state.electric!==false&&!setup.terminal)out.push(['Electric currents','Terminal / ground pair missing']);if(state.heat&&!setup.cooling)out.push(['Heat transfer','Thermal boundary missing']);if(state.heat&&state.structure&&!setup.fixed)out.push(['Solid mechanics','Mechanical constraint missing']);return out;}
function decorate(){
if(ui.page==='Model'&&pick.mode==='Bodies'&&['Geometry','Materials'].includes(ui.selection)){
 const controls=document.createElement('div');controls.className='toolbar';controls.innerHTML=(isOptical()?['Core','Oxide']:['Core','Oxide','Heater']).map(b=>`<button data-body="${b}" aria-pressed="${ui.body===b}">${b}</button>`).join('');$('canvas').prepend(controls);
 controls.querySelectorAll('[data-body]').forEach(b=>b.onclick=()=>{ui.body=b.dataset.body;ui.selection='Materials';render();});
}
let form='';
if(ui.selection==='Materials'){
 const allowed=isOptical()?(ui.body==='Core'?['Silicon','Silicon nitride']:['Silica']):['','Silicon','Silica','Silicon nitride','Platinum'];
 const assigned=setup.materials[ui.body];
 const values=allowed.includes(assigned)?allowed:[assigned,...allowed];
 form=`<h2>${ui.body} material</h2><label>Selected body<select id="body-choice">${options(isOptical()?['Core','Oxide']:['Core','Oxide','Heater'],ui.body)}</select></label><label>${isOptical()?'Optical material':'Material label'}<select id="material-choice">${options(values,assigned)}</select></label>`;
 form+=isOptical()?`<p>${allowed.includes(assigned)?'Used by the optical solver at 1550 nm.':'Current assignment is unsupported. Choose a supported material before running.'}</p><p>Core: Silicon (Si) or Silicon nitride (Si3N4). Background: Silica (SiO2). Optical material properties are resolved by the server; thermal and mechanical laws are not assigned here.</p>`:'<p>Setup labels only. Coupled property values, temperature laws and compatibility are not validated.</p>';
}
if(ui.selection==='Electric currents')form=`<h2>Electric currents</h2><label>Applied voltage [V]<input id="setup-voltage" type="number" min="0" max="10" step="0.1" value="${state.voltage}"></label><label>Terminal / ground<select id="terminal">${options(['','Heater start / heater end'],setup.terminal)}</select></label><p>Named end faces are placeholders until CAD selection is connected.</p>`;
if(ui.selection==='Heat transfer')form=`<h2>Heat transfer</h2><label>Thermal boundary<select id="cooling">${options(['','Oxide bottom: fixed temperature'],setup.cooling)}</select></label><label>Boundary temperature [K]<input id="temperature" type="number" min="1" max="2000" step="0.01" value="${setup.temperature}"></label><p>Temperature range is a UI input bound, not material validity.</p>`;
if(ui.selection==='Solid mechanics')form=`<h2>Solid mechanics</h2><label>Fixed support<select id="fixed">${options(['','Left end fixed','Both ends fixed'],setup.fixed)}</select></label><p>Conceptual end selections. Other faces are intended to remain free. Geometry mapping is pending.</p>`;
if(form){$('inspector').innerHTML='<span class="muted">MODEL SETUP</span>'+form+'<p id="input-error" role="alert"></p>';}
const bind=(id,fn)=>{const el=$(id);if(el)el.onchange=()=>{fn(el.value);render();};};bind('body-choice',v=>ui.body=v);bind('material-choice',v=>setup.materials[ui.body]=v);for(const key of ['terminal','cooling','fixed'])bind(key,v=>setup[key]=v);
const missing=issues();$('status').textContent=`Design inputs · ${missing.length} setup items missing · solver not connected`;
if(ui.page==='Model'&&ui.selection==='Study'){
 $('canvas').innerHTML='<h2>Setup review</h2><p>Input completeness only · not a numerical preflight</p>'+ (missing.length?missing.map(([node,msg])=>`<div class="pair"><span>${msg}</span><button data-fix="${node}">Configure →</button></div>`).join(''):'<div class="pair"><strong>Required setup labels assigned</strong></div>')+'<h3>Execution blockers</h3><p>CAD face mapping, material properties, mesh, coupling adapters and numerical validation are not implemented. Run remains disabled.</p>';
 $('canvas').querySelectorAll('[data-fix]').forEach(b=>b.onclick=()=>{if(b.dataset.fix==='Materials')ui.body=Object.keys(setup.materials).find(k=>!setup.materials[k])||'Core';select(b.dataset.fix);});
}
}



let pendingProject = null,pendingSession=null,pendingSessionSource='file',pendingSaved=true;
const notice = text => $('file-status').textContent = text;
const current = () => snapshot(state, setup);
const signature = () => JSON.stringify(current());
const edits=new WorkspaceStore(current());
function refreshPersistence(){
  const clean=!edits.dirty;
  $('project').textContent=(isOptical()?'Optical waveguide':'Multiphysics workspace')+' / '+(numericDrafts.invalid?'Invalid input draft · last valid inputs '+(clean?'saved':'unsaved'):(clean?'Saved inputs':'Unsaved inputs'))+' · Revision '+edits.revision;
  refreshNotebook();refreshWorkflow();
}
function refreshWorkflow(){
 const host=$('workflow');host.hidden=!isOptical()||ui.page==='Applications';if(host.hidden)return;
 const steps=opticalWorkflow({input:current(),invalid:numericDrafts.invalid,block:opticalBlock()||retentionBlock(),busy:solverBusy,pending:!!pendingJob,mesh:meshPreview.record,runs});
 steps.forEach((step,index)=>{
  let button=host.children[index];if(!button){button=document.createElement('button');button.type='button';button.className='workflow-step';button.append(document.createElement('strong'),document.createElement('span'));button.onclick=()=>{if(step.id==='Results'){solverRun=runs.findLast(run=>run.signature===signature())||solverRun;ui.page='Results';render();}else select(step.id);};host.append(button);}button.dataset.state=step.state;
  const selected=step.id==='Results'?['Results','Compare'].includes(ui.page):ui.page==='Model'&&ui.selection===step.id;
  if(selected)button.setAttribute('aria-current','step');else button.removeAttribute('aria-current');
  button.children[0].textContent=`${index+1}. ${step.id}`;button.children[1].textContent=step.detail;
 });
}
function rejectInvalidInput(){
  numericDrafts.assertValid();
}
function applyProject(doc,{saved=true,resetHistory=false}={}){
  doc=edits.replace(doc,{saved,resetHistory});numericDrafts.clear();
  pick.boundary=null;pick.mode='Bodies';Object.assign(state,doc.model);Object.assign(ui,{page:'Model',selection:'Study',view:'Section'});
  Object.assign(setup,doc.setup);ui.body='Core';
  checkpointRecovery();render();updateHistory();refreshPersistence();
  notice('Project inputs restored. Results and CAD geometry are not included.');
}
function requestLoad(doc,{saved=true}={}){
  pendingSaved=saved;
  // Validate completely before changing any current model inputs.
  pendingProject=doc;
  $('load-confirm').querySelector('h2').textContent=pendingSession?'Replace inputs and run history?':'Replace current inputs?';$('load-confirm').querySelector('p').textContent=pendingSession?'Save a session first to retain current results. Session import replaces run history and clears input undo history.':'Save your current design first if you want to keep it.';
  $('load-confirm').showModal();
}
const dialog=document.createElement('dialog');dialog.id='load-confirm';
dialog.innerHTML='<h2>Replace current inputs?</h2><p>Save your current design first if you want to keep it.</p><button id="cancel-load">Keep current</button> <button id="confirm-load">Replace inputs</button>';
document.body.append(dialog);
$('cancel-load').onclick=()=>{pendingProject=null;pendingSession=null;dialog.close();notice('Open cancelled. Current inputs kept.');};
dialog.oncancel=()=>{pendingProject=null;pendingSession=null;};
$('confirm-load').onclick=()=>{const doc=pendingProject;pendingProject=null;dialog.close();if(pendingSession){const session=pendingSession,source=pendingSessionSource;pendingSession=null;pendingSessionSource='file';runs=session.runs;solverRun=runs.find(r=>r.job===session.selected)||runs.at(-1)||null;compareIds=[...session.comparison];restoreView(session.view);applyProject(session.input,{saved:pendingSaved,resetHistory:true});ui.page=runs.length>1?'Compare':runs.length?'Results':'Model';render();savedNotebookState=source==='file'?notebookStamp():null;refreshNotebook();notice(source==='file'?'Session restored. Imported results were loaded from file, not recomputed; input undo history starts here.':'Session recovered from browser storage, not recomputed. Save session for a portable file; input undo history starts here.');}else if(doc)applyProject(doc,{saved:pendingSaved});};
$('save-project').onclick=()=>{try{
  rejectInvalidInput();const doc=current();const blob=new Blob([JSON.stringify(doc,null,2)+'\n'],{type:'application/json'});
  const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='studio-workspace-v2.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  edits.record(doc);edits.markSaved();refreshPersistence();notice('Project file download requested. Inputs only; no computed results.');
}catch(e){notice(e.message);}};
$('open-project').onclick=()=>{try{rejectInvalidInput();$('project-file').click();}catch(e){notice(e.message);}};
$('project-file').onchange=async event=>{const file=event.target.files[0];event.target.value='';if(!file)return;try{
  if(file.size>MAX_BYTES)throw new Error('Project exceeds 64 KiB.');
  requestLoad(parseProject(await file.text()));
}catch(e){notice('Open failed: '+e.message+' Current inputs kept.');}};
$('save-draft').onclick=()=>{try{rejectInvalidInput();const text=signature();localStorage.setItem(DRAFT_KEY,text);edits.record(current());edits.markSaved();refreshPersistence();notice('Draft saved in this browser. Use Restore draft after reloading.');}catch(e){notice('Draft not saved: '+e.message);}};
$('restore-draft').onclick=()=>{try{rejectInvalidInput();const text=localStorage.getItem(DRAFT_KEY);if(!text)throw new Error('No draft saved in this browser.');requestLoad(parseProject(text));}catch(e){notice('Restore failed: '+e.message+' Current inputs kept.');}};


let recoverable=null;
function showRecovery(){
 $('recover-inputs').disabled=!recoverable;
 $('recovery-status').textContent=recoverable?'Recent valid inputs available ('+new Date(recoverable.savedAt).toLocaleString()+'). Results and invalid drafts are not included.':'Valid input changes are saved automatically for recovery in this browser. Save session for a portable result file.';
}
function checkpointRecovery(){
 try{writeRecovery(localStorage,current());recoverable=readRecovery(localStorage);showRecovery();}
 catch(error){$('recovery-status').textContent='Automatic input recovery unavailable: '+error.message+' Use Save file or Save session.';}
}
try{recoverable=readRecovery(localStorage);showRecovery();}catch(error){$('recovery-status').textContent='Recovery could not be read: '+error.message+' Current inputs kept.';}
$('recover-inputs').onclick=()=>{try{rejectInvalidInput();if(recoverable)requestLoad(recoverable.input,{saved:false});}catch(error){notice(error.message);}};

function updateHistory(){ $('undo-edit').disabled=!edits.canUndo;$('redo-edit').disabled=!edits.canRedo; }
function trackEdit(group=null){const before=edits.signature;edits.record(current(),group);if(edits.signature!==before)checkpointRecovery();updateHistory();refreshPersistence();}
function restoreEdit(doc,label){
 numericDrafts.clear();
 Object.assign(state,doc.model);Object.assign(setup,doc.setup);pick.boundary=null;
 checkpointRecovery();render();updateHistory();refreshPersistence();notice(label+' · input changes only; no solver executed.');
}
$('undo-edit').onclick=()=>restoreEdit(edits.undo(),'Undo');
$('redo-edit').onclick=()=>restoreEdit(edits.redo(),'Redo');
document.addEventListener('input',event=>trackEdit(event.target));
document.addEventListener('change',()=>{trackEdit();edits.endGroup();});
document.addEventListener('click',()=>{trackEdit();edits.endGroup();});
document.addEventListener('focusout',()=>edits.endGroup());
document.addEventListener('keydown',event=>{
 if(!(event.ctrlKey||event.metaKey)||event.altKey||document.querySelector('dialog[open]'))return;
 if(event.target.closest('input,textarea,select,[contenteditable="true"]'))return;
 if(event.key.toLowerCase()==='z'){event.preventDefault();if(event.shiftKey){if(edits.canRedo)$('redo-edit').click();}else if(edits.canUndo)$('undo-edit').click();}
 else if(event.key.toLowerCase()==='y'){event.preventDefault();if(edits.canRedo)$('redo-edit').click();}
});

let solverBusy=false,solverRun=null,runs=[],compareIds=[null,null];const fieldView={mode:0,component:'magnitude',window:'Core region'};const fieldProbe={x:0,y:.15,active:false};let savedNotebookState=null;
let notebookRecoveryRecord=null,notebookLoadVersion=0;
const notebookStore=indexedNotebookStore();
const notebookAutosave=new NotebookAutosave(notebookStore,{onState:state=>{
 const message=$('autosave-status');
 if(state.phase==='pending')message.textContent='Browser recovery pending';
 if(state.phase==='saving')message.textContent='Saving browser recovery…';
 if(state.phase==='current')message.textContent='Current notebook already in browser recovery';
 if(state.phase==='saved'){notebookRecoveryRecord=state.record;notebookLoadVersion++;message.textContent='Browser recovery saved · '+new Date(state.record.savedAt).toLocaleTimeString();$('recover-notebook').disabled=false;$('retry-notebook').disabled=true;$('notebook-recovery-detail').textContent='Latest completed session saved in this browser/origin; shared across tabs. Save session for a portable backup.';}
 if(state.phase==='error'){message.textContent='Browser recovery failed · save a session file';$('retry-notebook').disabled=false;$('notebook-recovery-detail').textContent=state.message+' Previous completed snapshot is retained if the database transaction failed.';}
}});
async function loadNotebookRecovery(){
 const version=notebookLoadVersion;
 try{const record=await notebookStore.load();const recovered=readNotebookRecovery(record);if(version!==notebookLoadVersion)return;notebookRecoveryRecord=record||null;$('recover-notebook').disabled=!recovered;$('retry-notebook').disabled=true;
  if(recovered){$('autosave-status').textContent='Previous browser session available · '+recovered.session.runs.length+' runs';$('notebook-recovery-detail').textContent='Saved '+new Date(recovered.savedAt).toLocaleString()+'. Recover last session restores inputs and completed results. Latest snapshot is shared across tabs on this origin.';}
  else $('autosave-status').textContent='Completed sessions will be saved for browser recovery';
 }catch(error){if(version!==notebookLoadVersion)return;$('autosave-status').textContent='Browser recovery unavailable · save a session file';$('notebook-recovery-detail').textContent=error.message;$('retry-notebook').disabled=false;}
}
$('retry-notebook').onclick=()=>runs.length?notebookAutosave.retry():loadNotebookRecovery();
$('recover-notebook').onclick=async()=>{
 if(solverBusy){notice('Wait for the calculation or stop waiting before recovering a session.');return;}
 $('recover-notebook').disabled=true;
 try{rejectInvalidInput();const record=await notebookStore.load(),recovered=readNotebookRecovery(record);if(!recovered)throw new Error('No session is stored for recovery.');if(solverBusy)throw new Error('Calculation started while reading recovery.');rejectInvalidInput();pendingSession=recovered.session;pendingSessionSource='browser';requestLoad(recovered.session.input,{saved:false});}
 catch(error){notice('Session recovery failed: '+error.message+' Current inputs and results kept.');}
 finally{$('recover-notebook').disabled=!notebookRecoveryRecord;}
};

function currentView(){return {...fieldView,probe:{...fieldProbe},profile:{...profileState}};}
function restoreView(view){Object.assign(fieldView,{mode:view.mode,component:view.component,window:view.window});Object.assign(fieldProbe,view.probe||{x:0,y:.15,active:false});Object.assign(profileState,view.profile||{axis:'x',coordinate:.15,open:false});}
function notebookStamp(){return JSON.stringify({input:current(),runs:runs.map(r=>[r.job,r.completedAt,r.label||'',r.pinned===true]),selected:solverRun?.job||null,comparison:compareIds,view:currentView()});}
function refreshNotebook(){const stamp=notebookStamp();if(runs.length&&!numericDrafts.invalid)notebookAutosave.schedule(stamp,()=>JSON.stringify(createSession(current(),runs,solverRun?.job||null,compareIds,currentView())));const changed=savedNotebookState!==stamp;$('notebook-status').textContent=runs.length?(changed?'Session file changed · export a portable copy':'Session file snapshot saved or restored'):'No completed runs in this session';$('save-session').classList.toggle('unsaved-session',runs.length>0&&changed);}
const opticalBlock=()=>connection.ready?opticalSupport(state,setup):connection.message;
const retentionBlock=()=>runs.length===RUN_LIMIT&&runs.every(run=>run.pinned)?'All six runs are pinned. Unpin a run in Results before starting another calculation.':'';
const opticalDocument=()=>buildOpticalDocument(state,setup);
function solverPanel(){document.querySelector('main').classList.toggle('comparing',ui.page==='Compare');document.querySelector('main').classList.toggle('choosing',ui.page==='Applications');
 const block=opticalBlock();if(isOptical())$('sequence').innerHTML='<span>Optical modes</span><span>Run validates a captured input snapshot</span><span>Mesh/window convergence not certified</span>';if(['Results','Compare'].includes(ui.page))$('sequence').innerHTML='<span>Results are attached to captured inputs</span><span>Mode matching / convergence not certified</span>';$('status').textContent=solverBusy?'Optical computation running':block?'Coupled solver unavailable · optical-only template supported':'Optical adapter ready · explicit Run required';$('run-optical').disabled=solverBusy||!!pendingJob||!!block;
 $('run-optical').textContent=solverBusy?'Computing…':'Run optical study';
 if(ui.page==='Model'&&['Study','Optical modes'].includes(ui.selection)){
  const info=document.createElement('section');info.innerHTML='<h3>Optical adapter scope</h3><p>2D rectangular core, height 100–500 nm; silica background; wavelength 1550 nm; 30 nm core mesh; 3 × 2.4 µm window; PEC outer edges; two candidates. Heater, thermal and mechanical settings are excluded. Mesh/window convergence is not certified.</p>';
  const msg=document.createElement('p');msg.textContent=block||'Optical input supported. Solver validation runs before submission.';info.append(msg);
  if(ui.selection==='Study'&&!block)$('canvas').innerHTML='<h2>Optical study</h2><p>Input snapshot is captured when Run is pressed.</p>'+pair('Core dimensions',state.width+' × '+state.height+' nm')+pair('Core material',setup.materials.Core)+pair('Background',setup.materials.Oxide)+'<button id=review-geometry>Edit geometry</button> <button id=review-materials>Edit materials</button>';
   if($('review-geometry'))$('review-geometry').onclick=()=>select('Geometry');if($('review-materials'))$('review-materials').onclick=()=>select('Materials');
  $('canvas').append(info);if(ui.selection==='Study'&&!block)$('inspector').innerHTML='<h2>Optical execution</h2>'+pair('State',solverBusy?'Computing':solverRun?'Completed run available':'Ready for validation')+'<p>Run captures current inputs. Other physics remain unavailable.</p>';
 }
 const controls=document.querySelector('.workspace > .toolbar');controls.style.display=['Applications','Results','Compare'].includes(ui.page)?'none':'flex';document.querySelector('.workspace > .note').textContent=['Results','Compare'].includes(ui.page)?'Field data belongs to a captured run. Imported results are labeled; no automatic computation.':isOptical()?'Optical cross section uses the submitted geometry, in nm. Width/height editable; window/PEC fixed.':'Conceptual geometry only · no CAD kernel or computed deformation';
 if(ui.page==='Compare'){renderComparison();renderRunList();return;}
 if(ui.page==='Results'&&solverRun){
  const same=solverRun.signature===signature();$('inspector').innerHTML='<h2>Run provenance</h2>'+pair('Computation','Optical modes only')+pair('Input',same?'Current snapshot':'Earlier snapshot')+'<p>Selected completed run. Save session includes fields; Save file includes inputs only.</p>'; $('canvas').innerHTML='<h2>Computed optical modes</h2>';
  const desc=document.createElement('p');desc.textContent=`Job ${solverRun.job}${solverRun.serverVersion?' · simcase '+solverRun.serverVersion:''}${Number.isInteger(solverRun.inputRevision)?' · input revision '+solverRun.inputRevision:''} · ${same?'Current input snapshot':'Earlier input snapshot — current edits retained'} · core ${solverRun.input.model.width} × ${solverRun.input.model.height} nm · λ 1550 nm`;$('canvas').append(desc);
  renderField();solverRun.neff.forEach((v,i)=>{const row=document.createElement('div');row.className='pair';const label=document.createElement('span');label.textContent=`Candidate ${i+1} · effective index`;const value=document.createElement('strong');value.textContent=v.toFixed(8);row.append(label,value);$('canvas').append(row);});
  const note=document.createElement('p');note.textContent=(solverRun.origin==='local'?'Actual local solver output. ':solverRun.origin==='recovered'?'Browser recovery result — not recomputed or authenticated. ':'Imported file result — not recomputed or authenticated. ')+' Ranked candidates are not mode-matched between designs. Save session to keep results. No thermal or mechanical solve was performed.';$('canvas').append(note);
 }
 if(ui.page==='Results'){if(!solverRun)$('canvas').innerHTML='<h2>No completed runs</h2><p>Choose Applications → Optical waveguide, edit the model and run an optical study. A session file can also restore prior results.</p>';renderRunList();}
 if(ui.page==='Model'&&ui.selection==='Optical modes'&&isOptical())$('inspector').innerHTML='<h2>Optical interface</h2>'+pair('Equation','Vector optical eigenproblem')+pair('Wavelength','1550 nm')+pair('Candidates','2')+pair('Outer boundary','PEC')+'<p>Run from Study to compute optical fields for the current cross section.</p>';
 if(ui.page==='Connections'&&isOptical()){$('inspector').innerHTML='<h2>Active interfaces</h2>'+pair('Optical modes','Enabled')+pair('Couplings','None')+'<p>This application computes optical modes only.</p>';document.querySelector('.workspace > .note').textContent='One optical interface; no thermal or mechanical field transfer is configured.';}
 if(ui.page==='Model'&&ui.selection==='Mesh'&&isOptical())renderMeshPreview();
 if(ui.page==='Model'&&ui.selection==='Study'&&isOptical())renderOpticalStudy();
}

const preflight=new OpticalPreflight(solverApi,()=>{if(ui.page==='Model'&&ui.selection==='Study')render();});
function renderOpticalStudy(){
 const host=$('canvas'),panel=$('inspector');host.innerHTML='<h2>Optical study</h2><p>Review the current input, optionally check it, then run explicitly.</p>'+pair('Core dimensions',state.width+' × '+state.height+' nm')+pair('Core material',setup.materials.Core)+pair('Background',setup.materials.Oxide);
 const actions=document.createElement('div');actions.className='study-actions';
 for(const name of ['Geometry','Materials']){const edit=document.createElement('button');edit.textContent='Edit '+name.toLowerCase();edit.onclick=()=>select(name);actions.append(edit);}
 const check=document.createElement('button');check.textContent=preflight.busy?'Checking inputs…':'Check inputs';check.disabled=preflight.busy||solverBusy||!!opticalBlock()||numericDrafts.invalid;
 check.onclick=()=>preflight.check(current(),opticalDocument(),connection.instance);actions.append(check);
 const exportDoc=document.createElement('button');exportDoc.textContent='Export solver JSON';exportDoc.disabled=!!opticalSupport(state,setup)||numericDrafts.invalid;
 exportDoc.onclick=()=>{try{rejectInvalidInput();downloadFile(new Blob([JSON.stringify(opticalDocument(),null,2)],{type:'application/json'}),'studio-optical-solver.json');notice('Solver document exported in micrometres. This is a simcase input, not a workspace session.');}catch(error){notice(error.message);}};actions.append(exportDoc);host.append(actions);
 const block=opticalBlock()||retentionBlock();if(block){const message=document.createElement('p');message.textContent=block;message.className='validation-warning';host.append(message);}
 if(preflight.error){const error=document.createElement('p');error.setAttribute('role','alert');error.textContent='Input check failed: '+preflight.error+' Previous check retained.';host.append(error);}
 const record=preflight.record;
 if(record){const report=document.createElement('section');report.className='validation-report';const heading=document.createElement('h3');const same=!numericDrafts.invalid&&record.signature===signature()&&record.serverInstance===connection.instance;
 heading.textContent=(same?'Current inputs':'Earlier inputs or server')+' · '+(record.ok?'document accepted':'document rejected');report.append(heading);
 const captured=document.createElement('p');captured.textContent=record.input.model.width+' × '+record.input.model.height+' nm · '+record.input.setup.materials.Core+' · '+new Date(record.checkedAt).toLocaleTimeString();report.append(captured);
 const summary=document.createElement('pre');summary.textContent=record.ok?record.summary:record.error;report.append(summary);
 for(const note of record.notes){const line=document.createElement('p');line.textContent=note;report.append(line);}host.append(report);
 }else host.insertAdjacentHTML('beforeend','<p>No document check in this tab. Run always validates again before submission.</p>');
 const scope=document.createElement('p');scope.textContent='Document checks validate the schema and settings; they do not generate a mesh, solve fields, verify material accuracy or certify convergence. Run captures current inputs, validates them again, then starts a calculation.';host.append(scope);
 panel.innerHTML='<h2>Execution settings</h2>'+pair('State',opticalWorkflow({input:current(),invalid:numericDrafts.invalid,block,busy:solverBusy,pending:!!pendingJob,runs})[3].detail)+pair('Wavelength','1550 nm')+pair('Candidates','2')+pair('Core mesh','30 nm')+pair('Window','3 × 2.4 µm')+pair('Outer edges','PEC')+'<p>Fixed optical adapter. Electrical, thermal and mechanical solves are unavailable in this workspace.</p>';
 document.querySelector('.workspace > .note').textContent='Checks and runs capture inputs separately. A prior accepted document does not certify the current model.';
 if(!opticalSupport(state,setup)){const details=document.createElement('details');details.className='solver-document';const title=document.createElement('summary');title.textContent=(numericDrafts.invalid?'Last valid solver document':'Solver document')+' · lengths in µm';const body=document.createElement('pre');body.textContent=JSON.stringify(opticalDocument(),null,2);details.append(title,body);host.append(details);}
}

let meshView='Full window';
const meshPreview=new MeshPreview((path,body)=>solverApi(path+'?workspace_instance='+encodeURIComponent(connection.instance),body),()=>{if(ui.page==='Model'&&ui.selection==='Mesh')render();});
function renderMeshPreview(){
 document.querySelector('.workspace > .note').textContent='Actual mesh in µm; preview is attached to captured inputs. Green triangles mark the core.';
 const host=$('canvas'),panel=$('inspector');host.innerHTML='<h2>Optical mesh</h2><p>Generate the actual triangular mesh without solving optical modes.</p>';
 const generate=document.createElement('button');generate.id='generate-mesh';generate.textContent=meshPreview.busy?'Generating mesh…':'Generate mesh';generate.disabled=meshPreview.busy||solverBusy||!!opticalBlock()||numericDrafts.invalid;
 generate.onclick=async()=>{try{rejectInvalidInput();await meshPreview.generate(current(),opticalDocument());}catch(error){notice(error.message);}};host.append(generate);
 panel.innerHTML='<h2>Mesh settings</h2>'+pair('Core target','30 nm')+pair('Far target','160 nm')+pair('Window','3 × 2.4 µm')+'<p>Fixed adapter settings. Mesh generation does not certify convergence. The solve generates its own mesh from the same document.</p>';
 if(meshPreview.error){const error=document.createElement('p');error.setAttribute('role','alert');error.textContent='Mesh generation failed: '+meshPreview.error+' Previous preview retained.';host.append(error);}
 const record=meshPreview.record;if(!record){host.insertAdjacentHTML('beforeend','<p>No mesh generated in this tab.</p>');return;}
 const stale=record.signature!==signature();const note=document.createElement('p');note.textContent=(stale?'Earlier input mesh — regenerate for current inputs. ':'Current input mesh. ')+record.input.model.width+' × '+record.input.model.height+' nm · '+record.input.setup.materials.Core;host.append(note);
 const label=document.createElement('label');label.textContent='Mesh view';const view=document.createElement('select');view.id='mesh-view';view.innerHTML=options(['Full window','Core region'],meshView);label.append(view);host.append(label);
 const canvas=document.createElement('canvas');canvas.id='mesh-preview';canvas.style.cssText='display:block;width:100%;height:360px';canvas.setAttribute('role','img');host.append(canvas);
 panel.insertAdjacentHTML('beforeend',pair('Nodes',record.data.stats.nodes)+pair('Triangles',record.data.stats.triangles)+pair('Minimum angle',record.data.stats.minAngle+'°')+pair('Mean quality',record.data.stats.meanQuality));
 const draw=()=>drawMesh(canvas,record.data,meshView);view.onchange=()=>{meshView=view.value;draw();};fieldResize=new ResizeObserver(draw);fieldResize.observe(canvas);draw();
}

function fieldColor(t){const stops=[[18,38,59],[23,111,139],[69,187,159],[249,235,130]];const z=Math.min(2.999999,Math.max(0,t)*3),i=Math.floor(z),a=z-i;return 'rgb('+stops[i].map((v,k)=>Math.round(v+(stops[i+1][k]-v)*a)).join(',')+')';}
let fieldResize=null,profileResize=null,profileRedraw=()=>{};const profileState={axis:'x',coordinate:.15,open:false};
function addProbeControls(host,redraw){
 const form=document.createElement('form');form.className='probe-controls';
 form.innerHTML='<strong>Inspect displayed sample</strong><label>x [µm]<input id="probe-x" type="number" step="any" min="-1.5" max="1.5" required></label><label>y [µm]<input id="probe-y" type="number" step="any" min="-1.2" max="1.2" required></label><button type="submit">Inspect point</button><button type="button" id="clear-probe">Clear point</button><span>Click a plot or enter coordinates. Values belong to triangle centroids; no interpolation.</span>';
 host.append(form);$('probe-x').value=fieldProbe.x;$('probe-y').value=fieldProbe.y;
 form.onsubmit=event=>{event.preventDefault();if(!form.reportValidity())return;fieldProbe.x=Number($('probe-x').value);fieldProbe.y=Number($('probe-y').value);fieldProbe.active=true;redraw();refreshPersistence();};
 $('clear-probe').onclick=()=>{fieldProbe.active=false;redraw();refreshPersistence();};
}
function probeOutput(host,id){const output=document.createElement('p');output.id=id;output.className='probe-output';output.setAttribute('role','status');host.append(output);return output;}

function renderField(){
 if(fieldResize)fieldResize.disconnect();
 const host=document.createElement('section');host.className='field-result';host.innerHTML=`<div class="toolbar"><label>Candidate <select id="field-mode">${[0,1].map(i=>`<option value="${i}" ${i===fieldView.mode?'selected':''}>${i+1} · n_eff ${solverRun.neff[i].toFixed(6)}</option>`).join('')}</select></label><label>Quantity <select id="field-component">${['magnitude','Ex','Ey','Ez'].map(c=>`<option ${c===fieldView.component?'selected':''} value="${c}">${c==='magnitude'?'|E|':'|'+c+'|'}</option>`).join('')}</select></label><label>View <select id="field-window">${['Core region','Full window'].map(c=>`<option ${c===fieldView.window?'selected':''}>${c}</option>`).join('')}</select></label></div><canvas id="optical-field" role="img" style="display:block;width:100%;height:340px"></canvas><div style="display:flex;align-items:center;gap:10px;padding:10px 0"><span>0</span><div style="flex:1;height:12px;background:linear-gradient(to right,#12263b,#176f8b,#45bb9f,#f9eb82)"></div><span>1</span></div><p id="field-description"></p>`;
 $('canvas').append(host);
 for(const [id,key] of [['field-mode','mode'],['field-component','component'],['field-window','window']])$(id).onchange=()=>{fieldView[key]=key==='mode'?+$(id).value:$(id).value;drawField();profileRedraw();};
 probeOutput(host,'field-probe');addProbeControls(host,()=>drawField());fieldResize=new ResizeObserver(()=>{if($('optical-field'))drawField();});fieldResize.observe(host);drawField();renderLineProfile(host,[solverRun]);
}
function drawField(canvas=$('optical-field'),run=solverRun,descriptionTarget=$('field-description'),sampleTarget=$('field-probe'),redraw=()=>drawField()){
 if(!canvas||!run)return;
 const {values,maximum}=fieldScalars(run.field,fieldView.mode,fieldView.component);
 const box=canvas.getBoundingClientRect(),w=box.width,h=340;if(w<1)return;
 const dpr=Math.min(devicePixelRatio||1,2);canvas.width=Math.round(w*dpr);canvas.height=h*dpr;const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);ctx.fillStyle='#12202a';ctx.fillRect(0,0,w,h);
 const full=fieldView.window==='Full window',xmin=full?-1.5:-.9,xmax=full?1.5:.9,ymin=full?-1.2:-.61,ymax=full?1.2:.83;
 const margin={left:54,right:20,top:20,bottom:45};const scale=Math.min((w-margin.left-margin.right)/(xmax-xmin),(h-margin.top-margin.bottom)/(ymax-ymin));
 const pw=(xmax-xmin)*scale,ph=(ymax-ymin)*scale,left=margin.left+(w-margin.left-margin.right-pw)/2,top=margin.top;
 const X=x=>left+(x-xmin)*scale,Y=y=>top+(ymax-y)*scale;
 ctx.save();ctx.beginPath();ctx.rect(left,top,pw,ph);ctx.clip();
 run.field.triangles.forEach((triangle,i)=>{ctx.beginPath();triangle.forEach((n,j)=>{const p=run.field.nodes[n];if(j)ctx.lineTo(X(p[0]),Y(p[1]));else ctx.moveTo(X(p[0]),Y(p[1]));});ctx.closePath();ctx.fillStyle=fieldColor(values[i]);ctx.fill();});
 ctx.strokeStyle='#f5f1da';ctx.setLineDash([4,3]);ctx.lineWidth=1;const width=run.input.model.width/1000;ctx.strokeRect(X(-width/2),Y(run.input.model.height/1000),width*scale,run.input.model.height/1000*scale);
 if(profileState.open){ctx.strokeStyle='#e7bc73';ctx.setLineDash([8,4]);ctx.lineWidth=1.5;ctx.beginPath();if(profileState.axis==='x'&&profileState.coordinate>=ymin&&profileState.coordinate<=ymax){ctx.moveTo(X(xmin),Y(profileState.coordinate));ctx.lineTo(X(xmax),Y(profileState.coordinate));}else if(profileState.axis==='y'&&profileState.coordinate>=xmin&&profileState.coordinate<=xmax){ctx.moveTo(X(profileState.coordinate),Y(ymin));ctx.lineTo(X(profileState.coordinate),Y(ymax));}ctx.stroke();}ctx.restore();
 ctx.strokeStyle='#91a8b7';ctx.strokeRect(left,top,pw,ph);ctx.fillStyle='#cfdae0';ctx.font='12px Segoe UI';ctx.textAlign='center';
 for(let i=0;i<3;i++){const x=xmin+(xmax-xmin)*i/2;ctx.fillText(x.toFixed(2),X(x),top+ph+18);}
 ctx.fillText('x [µm]',left+pw/2,top+ph+38);ctx.textAlign='right';for(let i=0;i<3;i++){const y=ymin+(ymax-ymin)*i/2;ctx.fillText(y.toFixed(2),left-8,Y(y)+4);}
 ctx.save();ctx.translate(13,top+ph/2);ctx.rotate(-Math.PI/2);ctx.textAlign='center';ctx.fillText('y [µm]',0,0);ctx.restore();
 const q=fieldView.component==='magnitude'?'|E|':'|'+fieldView.component+'|';const description=`Candidate ${fieldView.mode+1}: ${q} / max|E|, relative amplitude (0–1). Each candidate uses its own vector maximum. Triangle-centroid samples, constant color per triangle; dashed outline = core. Not absolute power.${maximum===0?' Zero field returned.':''}`;
 if(descriptionTarget)descriptionTarget.textContent=description;canvas.setAttribute('aria-label',description);
 if(sampleTarget){
  sampleTarget.textContent='No point selected.';
  if(fieldProbe.active){
   const sample=probeField(run.field,values,fieldProbe.x,fieldProbe.y);
   sampleTarget.textContent=sample?`At (${fieldProbe.x.toFixed(4)}, ${fieldProbe.y.toFixed(4)}) µm: ${q} / max|E| = ${sample.value.toPrecision(6)} · triangle ${sample.index+1}, centroid (${sample.centroid[0].toFixed(4)}, ${sample.centroid[1].toFixed(4)}) µm. Stored centroid value, not interpolated.`:'No triangle contains this point in the captured result.';
   if(fieldProbe.x>=xmin&&fieldProbe.x<=xmax&&fieldProbe.y>=ymin&&fieldProbe.y<=ymax){const px=X(fieldProbe.x),py=Y(fieldProbe.y);ctx.strokeStyle='#fff';ctx.lineWidth=1.5;ctx.beginPath();ctx.moveTo(px-6,py);ctx.lineTo(px+6,py);ctx.moveTo(px,py-6);ctx.lineTo(px,py+6);ctx.stroke();}
  }
  canvas.style.cursor='crosshair';canvas.onclick=event=>{
   const rect=canvas.getBoundingClientRect(),px=(event.clientX-rect.left)*w/rect.width,py=(event.clientY-rect.top)*h/rect.height;
   if(px<left||px>left+pw||py<top||py>top+ph)return;
   fieldProbe.x=Math.max(xmin,Math.min(xmax,xmin+(px-left)/scale));fieldProbe.y=Math.max(ymin,Math.min(ymax,ymax-(py-top)/scale));fieldProbe.active=true;
   if($('probe-x'))$('probe-x').value=fieldProbe.x.toFixed(6);if($('probe-y'))$('probe-y').value=fieldProbe.y.toFixed(6);redraw();refreshPersistence();
  };
 }

}


function renderLineProfile(host,profileRuns,updateFields=()=>drawField()){
 const details=document.createElement('details');details.className='line-profile';details.open=profileState.open;
 const summary=document.createElement('summary');summary.textContent='Line profile and CSV';details.append(summary);
 const form=document.createElement('form');form.className='profile-controls';form.innerHTML='<label>Profile direction<select id="profile-axis" aria-label="Profile direction"><option value="x">Horizontal · along x</option><option value="y">Vertical · along y</option></select></label><label>Fixed coordinate [µm]<input id="profile-coordinate" type="number" step="any" required></label><button type="submit">Show profile</button>';details.append(form);
 const description=document.createElement('p');description.setAttribute('role','status');details.append(description);
 const canvas=document.createElement('canvas');canvas.style.cssText='display:block;width:100%;height:260px';canvas.setAttribute('role','img');details.append(canvas);
 const legend=document.createElement('div');legend.className='profile-legend';details.append(legend);
 const note=document.createElement('p');note.textContent='Step segments use the stored value of each intersected triangle. No interpolation, absolute power or mode matching. Each candidate uses its own max|E| normalization.';details.append(note);
 const csv=document.createElement('button');csv.type='button';csv.textContent='Export profile CSV';csv.disabled=true;details.append(csv);const png=document.createElement('button');png.type='button';png.textContent='Export profile PNG';png.style.marginLeft='8px';png.disabled=true;details.append(png);host.append(details);
 $('profile-axis').value=profileState.axis;$('profile-coordinate').value=profileState.coordinate;
 const range=()=>{const extent=$('profile-axis').value==='x'?1.2:1.5;$('profile-coordinate').min=-extent;$('profile-coordinate').max=extent;};range();$('profile-axis').onchange=range;
 let series=[],cacheKey='';
 profileRedraw=()=>{if(!details.isConnected||!details.open)return;try{
  const key=JSON.stringify([profileState.axis,profileState.coordinate,fieldView.mode,fieldView.component]);if(key!==cacheKey){series=profileRuns.map(run=>({run,segments:lineProfile(run.field,fieldScalars(run.field,fieldView.mode,fieldView.component).values,profileState.axis,profileState.coordinate)}));cacheKey=key;}
  const q=fieldView.component==='magnitude'?'|E|':'|'+fieldView.component+'|';description.textContent=`Displayed: ${profileState.axis==='x'?'y':'x'} = ${profileState.coordinate} µm · candidate ${fieldView.mode+1} · ${q} / max|E| (0–1). Full-domain profile; the amber dashed line marks its location in the field view when visible.`;
  legend.replaceChildren();series.forEach((item,i)=>{const line=document.createElement('p');line.style.color=i?'#e7bc73':'#80d7c0';line.textContent=`${i?'B':'A'} · ${item.run.label?item.run.label+' · ':''}${item.run.job} · ${item.run.origin} · ${item.segments.length} intervals`;legend.append(line);});
  drawProfile(canvas,series,profileState.axis,profileState.coordinate);csv.disabled=!series.some(item=>item.segments.length);png.disabled=csv.disabled;
 }catch(error){description.textContent='Profile unavailable: '+error.message;csv.disabled=true;png.disabled=true;}};
 form.onsubmit=event=>{event.preventDefault();if(!form.reportValidity())return;profileState.axis=$('profile-axis').value;profileState.coordinate=Number($('profile-coordinate').value);profileRedraw();updateFields();refreshPersistence();};
 details.ontoggle=()=>{if(!details.isConnected)return;profileState.open=details.open;profileRedraw();updateFields();refreshPersistence();};
 csv.onclick=()=>downloadFile(new Blob([profileCsv(series,profileState.axis,profileState.coordinate,fieldView.mode,fieldView.component)],{type:'text/csv'}),'studio-profile.csv');
 png.onclick=()=>{
  const out=document.createElement('canvas');out.width=canvas.width;out.height=canvas.height+180;const ctx=out.getContext('2d');ctx.fillStyle='#12202a';ctx.fillRect(0,0,out.width,out.height);ctx.drawImage(canvas,0,0);ctx.font='14px Segoe UI';ctx.fillStyle='#cfdae0';
  const q=fieldView.component==='magnitude'?'|E|':'|'+fieldView.component+'|';ctx.fillText(`Line ${profileState.axis==='x'?'y':'x'} = ${profileState.coordinate} um | candidate ${fieldView.mode+1} | ${q} / max|E|`,12,canvas.height+24);
  ctx.fillText('Relative amplitude 0 to 1 per candidate. Stored triangle values; no interpolation.',12,canvas.height+48);
  series.forEach((item,i)=>{ctx.fillStyle=i?'#e7bc73':'#80d7c0';ctx.fillText(`${i?'B':'A'}: ${item.run.job} | ${item.run.input.model.width} x ${item.run.input.model.height} nm | ${item.run.input.setup.materials.Core} | ${item.run.origin}`,12,canvas.height+76+i*24);});
  ctx.fillStyle='#cfdae0';ctx.fillText('Full domain. No absolute-power or cross-design mode matching claim.',12,canvas.height+142);out.toBlob(blob=>{if(blob)downloadFile(blob,'studio-profile.png');},'image/png');
 };
 profileResize=new ResizeObserver(profileRedraw);profileResize.observe(canvas);profileRedraw();
}

function downloadFile(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function renderRunList(){
 const panel=$('inspector');if(ui.page==='Compare')panel.innerHTML='<h2>Run notebook</h2>';
 const importRuns=document.createElement('button');importRuns.id='import-runs';importRuns.textContent='Import runs from file';importRuns.disabled=solverBusy||!!pendingJob;importRuns.onclick=()=>$('run-import-file').click();panel.append(importRuns);
 const title=document.createElement('h3');title.textContent=`History · ${runs.length} / ${RUN_LIMIT} · ${runs.filter(r=>r.pinned).length} pinned`;panel.append(title);
 for(const run of [...runs].reverse()){
  const b=document.createElement('button');b.className='run-item';b.setAttribute('aria-pressed',String(solverRun?.job===run.job));b.dataset.run=run.job;b.textContent=`${run.pinned?'Pinned · ':''}${run.label?run.label+' · ':''}${run.input.model.width} × ${run.input.model.height} nm · ${run.input.setup.materials.Core} · ${run.job}${run.origin!=='local'?' · '+run.origin:''}`;b.onclick=()=>{solverRun=run;ui.page='Results';render();};panel.append(b);
 }
 if(solverRun){
  const pin=document.createElement('button');pin.id='pin-run';pin.textContent=solverRun.pinned?'Unpin selected run':'Pin selected run';pin.disabled=(solverBusy||!!pendingJob)&&!solverRun.pinned;pin.onclick=()=>{solverRun.pinned=!solverRun.pinned;render();$('pin-run')?.focus();notice(solverRun.pinned?'Run pinned against automatic notebook eviction. Save session for a portable backup.':'Run unpinned; it may be replaced when the notebook reaches six runs.');};panel.append(pin);
  const nameForm=document.createElement('form');nameForm.className='run-name';
  const nameLabel=document.createElement('label');nameLabel.textContent='Selected run name';const nameInput=document.createElement('input');nameInput.id='run-name-input';nameInput.type='text';nameInput.maxLength=80;nameInput.value=solverRun.label||'';nameInput.placeholder='Optional name';nameLabel.append(nameInput);
  const rename=document.createElement('button');rename.id='rename-run';rename.type='submit';rename.textContent='Rename run';nameForm.append(nameLabel,rename);panel.append(nameForm);
  nameForm.onsubmit=event=>{event.preventDefault();try{solverRun.label=validateRunLabel(nameInput.value);render();notice('Run name updated. Save session to retain it; captured inputs and fields are unchanged.');}catch(error){notice(error.message);}};
  const exportRun=document.createElement('button');exportRun.textContent='Save selected run';exportRun.style.marginTop='10px';exportRun.onclick=()=>{try{
   const text=JSON.stringify(createSession(solverRun.input,[solverRun],solverRun.job,[solverRun.job,solverRun.job],currentView()));
   if(new TextEncoder().encode(text).length>MAX_SESSION_BYTES)throw new Error('Selected run exceeds the session size limit.');
   downloadFile(new Blob([text],{type:'application/json'}),'studio-run-'+solverRun.job+'.json');notice('Selected run exported with its captured inputs and fields. Current design remains unchanged.');
  }catch(error){notice(error.message);}};panel.append(exportRun);
  const restore=document.createElement('button');restore.id='restore-run-input';restore.textContent='Restore selected run inputs';restore.onclick=()=>requestLoad(validateProject(solverRun.input),{saved:false});panel.append(restore);
  const exportPng=document.createElement('button');exportPng.id='export-field';exportPng.textContent='Export field PNG';exportPng.style.marginTop='10px';exportPng.disabled=ui.page!=='Results';exportPng.onclick=()=>{
   const source=$('optical-field');if(!source)return;const out=document.createElement('canvas');out.width=source.width;out.height=source.height+170;const ctx=out.getContext('2d');ctx.fillStyle='#12202a';ctx.fillRect(0,0,out.width,out.height);ctx.drawImage(source,0,0);ctx.fillStyle='#cfdae0';ctx.font='14px Segoe UI';ctx.fillText(`Job ${solverRun.job} | candidate ${fieldView.mode+1} | ${fieldView.component} / max|E|`,12,source.height+25);ctx.fillText('Relative amplitude 0–1 per candidate; not absolute power.',12,source.height+48);ctx.fillText(`Core ${solverRun.input.model.width} x ${solverRun.input.model.height} nm | wavelength 1550 nm | ${solverRun.origin}`,12,source.height+70);const grad=ctx.createLinearGradient(35,0,out.width-35,0);for(let i=0;i<=3;i++)grad.addColorStop(i/3,fieldColor(i/3));ctx.fillStyle=grad;ctx.fillRect(35,source.height+92,out.width-70,12);ctx.fillStyle='#cfdae0';ctx.fillText('0',12,source.height+104);ctx.fillText('1',out.width-20,source.height+104);ctx.fillText(fieldProbe.active?'Probe ('+fieldProbe.x.toFixed(4)+', '+fieldProbe.y.toFixed(4)+') um; centroid sample, no interpolation.':'No probe point selected.',12,source.height+140);if(profileState.open)ctx.fillText('Profile line: '+(profileState.axis==='x'?'y':'x')+' = '+profileState.coordinate+' um (amber dashed).',12,source.height+162);out.toBlob(blob=>{if(blob)downloadFile(blob,'studio-field.png');},'image/png');
  };panel.append(exportPng);
 }
 const csv=document.createElement('button');csv.id='export-table';csv.textContent='Export run table CSV';csv.disabled=!runs.length;csv.style.marginTop='10px';csv.onclick=()=>downloadFile(new Blob([runTableCsv(runs)],{type:'text/csv'}),'studio-runs.csv');panel.append(csv);
 const limit=document.createElement('p');limit.textContent='Six runs retained. Pinned runs stay; the oldest unpinned run is replaced by a new result. Save session or selected runs for portable backups. No cross-design mode tracking.';panel.append(limit);
}
function renderComparison(){
 const host=$('canvas');host.innerHTML='<h2>Compare two runs</h2>';
 if(runs.length<2){host.insertAdjacentHTML('beforeend','<p>Compute two designs to compare their fields and inputs. Existing results stay attached to their original inputs.</p>');return;}
 if(!runs.some(r=>r.job===compareIds[0]))compareIds[0]=runs.at(-2).job;
 if(!runs.some(r=>r.job===compareIds[1]))compareIds[1]=runs.at(-1).job;
 const bar=document.createElement('div');bar.className='toolbar compare-selection';
 for(let side=0;side<2;side++){const label=document.createElement('label');label.textContent=side?'B':'A';const select=document.createElement('select');select.id=side?'compare-b':'compare-a';for(const r of runs){const o=document.createElement('option');o.value=r.job;o.textContent=`${r.label?r.label+' · ':''}${r.input.model.width} × ${r.input.model.height} nm · ${r.input.setup.materials.Core} · ${r.job}`;o.selected=r.job===compareIds[side];select.append(o);}select.onchange=()=>{compareIds[side]=select.value;render();};label.append(select);bar.append(label);}host.append(bar);
 const opts=document.createElement('div');opts.className='toolbar compare-options';opts.innerHTML=`<label>Candidate rank <select id="compare-mode"><option value="0" ${fieldView.mode===0?'selected':''}>1</option><option value="1" ${fieldView.mode===1?'selected':''}>2</option></select></label><label>Quantity <select id="compare-component">${['magnitude','Ex','Ey','Ez'].map(c=>`<option value="${c}" ${fieldView.component===c?'selected':''}>${c==='magnitude'?'|E|':'|'+c+'|'}</option>`).join('')}</select></label><label>View <select id="compare-window">${['Core region','Full window'].map(v=>`<option ${fieldView.window===v?'selected':''}>${v}</option>`).join('')}</select></label>`;host.append(opts);
 const a=runs.find(r=>r.job===compareIds[0]),b=runs.find(r=>r.job===compareIds[1]);
 const description=document.createElement('p');description.textContent=`Width: ${a.input.model.width} → ${b.input.model.width} nm. Height: ${a.input.model.height} → ${b.input.model.height} nm. Core: ${a.input.setup.materials.Core} → ${b.input.setup.materials.Core}. Δn_eff (B − A), candidate rank ${fieldView.mode+1}: ${(b.neff[fieldView.mode]-a.neff[fieldView.mode]).toFixed(8)}. ${a.job===b.job?'Same run on both sides. ':''}Candidate ranks are not matched modes.`;host.append(description);
 const grid=document.createElement('div');grid.className='compare-grid';[a,b].forEach((run,i)=>{const article=document.createElement('article');const h=document.createElement('h3');h.textContent=`${i?'B':'A'} · ${run.label?run.label+' · ':''}${run.input.model.width} × ${run.input.model.height} nm · ${run.input.setup.materials.Core} · ${run.origin}`;const canvas=document.createElement('canvas');canvas.id=i?'compare-field-b':'compare-field-a';canvas.style.cssText='width:100%;height:340px;display:block';canvas.setAttribute('role','img');article.append(h,canvas);probeOutput(article,i?'compare-probe-b':'compare-probe-a');grid.append(article);});host.append(grid);
 const legend=document.createElement('div');legend.innerHTML='<div style="display:flex;gap:8px;align-items:center"><span>0</span><div style="flex:1;height:12px;background:linear-gradient(to right,#12263b,#176f8b,#45bb9f,#f9eb82)"></div><span>1</span></div><p>Shared coordinates and 0–1 color scale. Each candidate is normalized to its own max|E|; this compares shapes, not absolute amplitudes. Components share their candidate vector denominator. No interpolation or field subtraction across meshes.</p>';host.append(legend);
 const redraw=()=>{if(!grid.isConnected)return;drawField($('compare-field-a'),a,null,$('compare-probe-a'),redraw);drawField($('compare-field-b'),b,null,$('compare-probe-b'),redraw);};addProbeControls(host,redraw);
 for(const [id,key] of [['compare-mode','mode'],['compare-component','component'],['compare-window','window']])$(id).onchange=()=>{fieldView[key]=key==='mode'?+$(id).value:$(id).value;render();};
 fieldResize=new ResizeObserver(redraw);fieldResize.observe(grid);redraw();renderLineProfile(host,[a,b],redraw);
}
let pendingRunImport=null;
const runImportDialog=document.createElement('dialog');runImportDialog.id='run-import-confirm';runImportDialog.innerHTML='<h2>Add saved runs to this notebook?</h2><p id="run-import-summary"></p><p>Current model inputs stay unchanged. Matching existing runs retain their names, pins and provenance. Imported fields are not recomputed.</p><button id="cancel-run-import">Keep notebook</button> <button id="confirm-run-import">Import runs</button>';document.body.append(runImportDialog);
const runListStamp=()=>JSON.stringify(runs.map(run=>[run.job,run.completedAt,run.label,run.pinned]));
$('run-import-file').onchange=async event=>{
 const file=event.target.files[0];event.target.value='';if(!file)return;
 try{if(solverBusy||pendingJob)throw new Error('Finish or detach the pending job before importing runs.');if(file.size>MAX_SESSION_BYTES)throw new Error('Session exceeds 16 MiB.');const session=parseSession(await file.text());if(solverBusy||pendingJob)throw new Error('A job started while reading the file.');const merged=mergeRuns(runs,session.runs);pendingRunImport={session,merged,stamp:runListStamp()};
  $('run-import-summary').textContent=`${file.name}: ${merged.added.length} new, ${merged.reused.length} matching, ${merged.evicted.length} older unpinned runs replaced. ${merged.runs.length} runs will remain. Save a session first if you need all current results.`;runImportDialog.showModal();
 }catch(error){pendingRunImport=null;notice('Run import failed: '+error.message+' Current notebook kept.');}
};
$('cancel-run-import').onclick=()=>{pendingRunImport=null;runImportDialog.close();notice('Run import cancelled. Current notebook kept.');};runImportDialog.oncancel=()=>{pendingRunImport=null;};
$('confirm-run-import').onclick=()=>{
 const pending=pendingRunImport;pendingRunImport=null;runImportDialog.close();if(!pending)return;
 if(solverBusy||pendingJob||runListStamp()!==pending.stamp){notice('Notebook changed while reviewing the import. Open the file again to review current changes.');return;}
 const previous=solverRun;const next=pending.merged.runs;const selected=next.find(run=>run.job===pending.session.selected)||next.findLast(run=>pending.session.runs.some(imported=>imported.job===run.job));
 runs=next;solverRun=selected||runs.at(-1);const other=runs.find(run=>run.job===previous?.job&&run.job!==solverRun.job)||runs.findLast(run=>run.job!==solverRun.job)||solverRun;
 compareIds=[other.job,solverRun.job];ui.page=runs.length>1?'Compare':'Results';render();notice('Saved runs imported. Current model inputs and input undo history kept; imported fields were not recomputed.');
};

$('save-session').onclick=()=>{try{rejectInvalidInput();const text=JSON.stringify(createSession(current(),runs,solverRun?.job||null,compareIds,currentView()));if(new TextEncoder().encode(text).length>MAX_SESSION_BYTES)throw new Error('Session exceeds 16 MiB; export fewer runs.');downloadFile(new Blob([text],{type:'application/json'}),'studio-session-v2.json');edits.record(current());edits.markSaved();savedNotebookState=notebookStamp();refreshPersistence();notice('Session download requested: current inputs, up to six results and comparison choices.');}catch(e){notice('Session not saved: '+e.message);}};
$('open-session').onclick=()=>{if(solverBusy){notice('Wait for the current calculation before opening a session.');return;}try{rejectInvalidInput();$('session-file').click();}catch(e){notice(e.message);}};
$('session-file').onchange=async event=>{const file=event.target.files[0];event.target.value='';if(!file)return;try{if(solverBusy)throw new Error('Calculation is still running.');if(file.size>MAX_SESSION_BYTES)throw new Error('Session exceeds 16 MiB.');const doc=parseSession(await file.text());if(solverBusy)throw new Error('Calculation started while reading the file.');pendingSession=doc;pendingSessionSource='file';requestLoad(doc.input);}catch(e){pendingSession=null;notice('Session open failed: '+e.message+' Current inputs and results kept.');}};

let pendingJob=null;
let jobPhase='idle',jobOperation=0;
const jobMonitor=new OpticalJobMonitor({api:solverApi,onState:state=>{
 const wasBusy=solverBusy;jobPhase=state.phase;solverBusy=['running','loading'].includes(state.phase);
 $('job-message').textContent=state.message;
 if(state.phase==='done')setPending(null);
 notice(state.message);if(state.phase==='done'||wasBusy!==solverBusy)render();refreshJobControls();
},onResult:(result,pending)=>{
 if(!Array.isArray(result.neff?.[0])||result.neff[0].length!==2||!result.neff[0].every(Number.isFinite))throw new Error('Unsupported optical result.');
 const input=pending.input;
 const completed=validateRun({job:pending.job,completedAt:new Date().toISOString(),settings:opticalSettings(input.model.height),input,neff:[...result.neff[0]],field:readOpticalField(result),origin:'local',serverVersion:pending.serverVersion});
 completed.inputRevision=pending.revision;const next=appendRun(runs,completed);runs=next;solverRun=runs.find(run=>run.job===completed.job);compareIds=[runs.length>1?runs.at(-2).job:solverRun.job,solverRun.job];ui.page='Results';
}});
function refreshJobControls(){
 $('job-input').textContent=pendingJob?pendingJob.job+' · '+pendingJob.input.model.width+' × '+pendingJob.input.model.height+' nm · '+pendingJob.input.setup.materials.Core+' · captured inputs':'';
 $('job-panel').hidden=!pendingJob&&!solverBusy&&jobPhase==='idle';
 $('stop-waiting').disabled=!pendingJob||!solverBusy||!jobMonitor.busy;
 $('resume-job').disabled=!pendingJob||solverBusy||!connection.ready;
 $('forget-job').disabled=!pendingJob||solverBusy;
 $('run-optical').disabled=solverBusy||!!pendingJob||!!opticalBlock()||!!retentionBlock()||numericDrafts.invalid;
 if(pendingJob&&!solverBusy)$('status').textContent='Pending job · resume or detach before starting another calculation';else if(!solverBusy&&retentionBlock())$('status').textContent=retentionBlock();
}
function setPending(record){pendingJob=record;try{storePending(sessionStorage,record);$('job-storage').textContent='';}catch(error){$('job-storage').textContent='Job recovery storage unavailable: '+error.message+' Keep this tab open to retrieve the result.';}}
try{pendingJob=readPending(sessionStorage);if(pendingJob){jobPhase='detached';$('job-message').textContent='Saved job '+pendingJob.job+' is available. Resume retrieves its captured result without changing your current inputs.';}}catch(error){$('job-message').textContent='Job recovery record could not be read: '+error.message;jobPhase='error';}
$('stop-waiting').onclick=()=>{if(jobMonitor.busy){jobOperation++;jobMonitor.stop();}};
$('resume-job').onclick=async()=>{
 if(!pendingJob||solverBusy||!connection.ready)return;
 jobOperation++;try{await jobMonitor.follow(pendingJob,connection.instance);}catch(error){$('job-message').textContent=error.message;}
 refreshJobControls();
};
$('forget-job').onclick=()=>{if(solverBusy)return;jobOperation++;setPending(null);jobPhase='idle';$('job-message').textContent='Job detached. Server computation was not cancelled.';notice('Job detached. You may start another calculation; server computation was not cancelled.');render();refreshJobControls();};
$('run-optical').onclick=async()=>{
 if(solverBusy||pendingJob||opticalBlock()||retentionBlock())return;
 try{rejectInvalidInput();}catch(e){notice(e.message);return;}
 const operation=++jobOperation;edits.record(current());const capture=edits.capture(),serverVersion=connection.version,serverInstance=connection.instance,doc=opticalDocument();solverBusy=true;jobPhase='validating';render();refreshJobControls();notice('Validating optical input…');$('job-message').textContent='Validating optical input…';
 try{
  const validation=await solverApi('/api/validate?workspace_instance='+encodeURIComponent(serverInstance),{doc});if(!validation.ok)throw new Error(validation.error||'Solver validation failed.');
  jobPhase='submitting';$('job-message').textContent='Submitting calculation…';
  const started=await solverApi('/api/run?workspace_instance='+encodeURIComponent(serverInstance),{doc});
  const record=validatePending({version:1,job:started.job,input:capture.input,revision:capture.revision,serverVersion,serverInstance,startedAt:new Date().toISOString()});
  setPending(record);await jobMonitor.follow(record,serverInstance);
 }catch(error){jobPhase='error';$('job-message').textContent='Calculation request failed: '+error.message+' If submission reached the server, work may continue.';notice($('job-message').textContent);}
 finally{if(operation===jobOperation){solverBusy=false;render();refreshJobControls();}}
};

async function connectWorkspace(){
 connection.ready=false;connection.message='Checking Studio compatibility…';$('connect-workspace').disabled=true;
 $('connection-status').textContent=connection.message;render();
 try{const caps=checkWorkspaceCapabilities(await solverApi('/api/workspace/capabilities/v2'));connection.ready=true;connection.version=caps.version;connection.instance=caps.instance;connection.message='Connected to simcase '+caps.version+' · optical workspace contract v2';}
 catch(error){connection.message='Studio connection unavailable or incompatible: '+error.message;$('workspace-tools').open=true;}
 finally{$('connection-status').textContent=connection.message;$('connect-workspace').disabled=false;render();refreshJobControls();}
}
$('connect-workspace').onclick=connectWorkspace;
const originalActive=active;active=()=>state.electric===false?originalActive().filter(n=>n!=='Electric currents'):originalActive();document.querySelectorAll('[data-page]').forEach(b=>b.onclick=()=>{ui.page=b.dataset.page;if(ui.page==='Connections')ui.selection='Couplings';render();});document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{ui.view=b.dataset.view;if(ui.view==='Section'&&pick.boundary!=='oxide-bottom')pick.boundary=null;render();});$('reset').onclick=()=>{numericDrafts.clear();pick.mode='Bodies';pick.boundary=null;ui.body='Core';Object.assign(setup,{materials:{Core:'Silicon',Oxide:'Silica',Heater:''},cooling:'',temperature:293.15,fixed:'',terminal:''});Object.assign(ui,{page:'Model',selection:'Geometry',view:'Perspective'});Object.assign(state,{height:220,width:500,voltage:1,heat:true,structure:true,optics:true,electric:true});render();};render();refreshPersistence();connectWorkspace();loadNotebookRecovery();})();

installLayout(document.querySelector('main'),document.getElementById('reset-layout'),document.getElementById('layout-status'));
