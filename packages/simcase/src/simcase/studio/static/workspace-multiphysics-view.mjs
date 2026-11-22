// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

// The multiphysics model's views (contract D2): the model tree, Settings, the Connections view
// drawn from the document's couplings, Messages from the live check, the run with progress per
// physics and loop, and Results per physics with the coupling check. The model is its document
// (workspace-multiphysics.mjs); the server checks and runs it (/api/multiphysics/*).
import {ENVELOPE,SIDES,PHYSMAT_THERMO_OPTIC,kindCatalog,physicsLabel,physicsNames,couplingNames,couplingTitle,splitSpec,portLabel,quantityWords,unitText,locationWords,
 normalizeEnvelope,isMultiphysics,addPhysics,removePhysics,sourceChoices,targetChoices,transferNote,addCoupling,removeCoupling,suggestedCouplings,suggestionText,
 acceptLoop,removeLoop,loopText,loopIndexOf,materialUses,materialLabel,modesTemperatureCoupled,anyTemperatureCoupled,physmatFor,fillThermoOptic,usePhysmat,fillText,geometryOf,
 mapDiagnostics,problemCounts,runBlockText,connectionLayout,renderMultiphysicsGraph,progressRows,failureText,formatValue,couplingCheckRows,effectiveIndexRows,indexChange,resultPages,uncoupledDocument} from './workspace-multiphysics.mjs';
import {curvePath,loopPath} from './workspace-graph.mjs';

const clone=x=>JSON.parse(JSON.stringify(x));
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const FILLS={'physmat:Si':'#6d9fe0','physmat:SiO2':'#dde7f1'};const OTHER_FILLS=['#a66a28','#7c9a5a','#9a6a9e','#c9a64a'];
const HEAT_TYPES={insulated:'Insulated',temperature:'Fixed temperature',flux:'Inward heat flux',convection:'Convection'};
const MARK={model:'◇',geometry:'◇',materials:'▱',mesh:'▦',physics:'∿',coupling:'⇄',study:'▷',order:'≡',loop:'↻',results:'▤'};
// a quantity string "1550 nm" -> {number, unit}; a bare number has unit ''
function parseQuantity(value){if(typeof value==='number')return {number:value,unit:''};const m=/^\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)\s*(.*)$/.exec(String(value??''));return m?{number:Number(m[1]),unit:m[2].trim()}:null;}

// ctx: {$, notice(text), announceResult(text), request(method, url, body), render(), ui,
// applications(host), onHistory()}
export function createMultiphysicsView(ctx){
 const {$,notice}=ctx;
 let active=false,doc=null,caps=null,catalog={types:new Map(),providers:[]},capsError=null;
 let check={pending:false,diagnostics:[],solve_order:[],run_refusal:null,error:null},messages=[],checkSeq=0,checkTimer=null;
 let selection='model',undoStack=[],redoStack=[],savedSignature=null,savedFile=null,announcedMultiphysics=false;
 let job=null,lastRun=null,runFailure=null,uncoupled={},resultPage=null,indexView='n',resize=null;
 const signature=()=>JSON.stringify(doc);
 // ---- model lifecycle ----
 async function loadCapabilities(){try{caps=await ctx.request('GET','/api/multiphysics/capabilities');catalog=kindCatalog(caps);capsError=null;}catch(e){capsError=e.message;}}
 async function open(tree,label,{fromFile=false}={}){
  if(!caps)await loadCapabilities();
  active=true;doc=normalizeEnvelope(tree);undoStack=[];redoStack=[];savedSignature=fromFile?signature():null;savedFile=fromFile?{name:label,kind:'Opened from',at:null}:null;selection='model';lastRun=null;runFailure=null;uncoupled={};resultPage=null;announcedMultiphysics=isMultiphysics(doc);
  ctx.onHistory();validate(true);ctx.ui.page='Model';ctx.render();notice(`${label||doc.name||'Model'} ready. Edit settings and couplings, then press Run.`);
 }
 async function openTemplate(){try{const tree=await ctx.request('GET','/api/multiphysics/template');await open(tree,'Heated silicon waveguide');}catch(e){notice('The multiphysics template could not be loaded: '+e.message);}}
 function close(){active=false;stopPolling();}
 function commit(next,message,select){
  undoStack.push(doc);if(undoStack.length>100)undoStack.shift();redoStack=[];
  const before=isMultiphysics(doc);doc=normalizeEnvelope(next);if(select)selection=select;
  validate();ctx.onHistory();ctx.render();
  let text=message+' Press Run to compute the new model.';
  if(!before&&isMultiphysics(doc)&&!announcedMultiphysics){announcedMultiphysics=true;text+=' This model is now saved as a multiphysics model (format 0.3/multiphysics.1).';}
  notice(text);
 }
 function undo(){if(!undoStack.length)return;redoStack.push(doc);doc=undoStack.pop();validate();ctx.onHistory();ctx.render();notice('Undo · model edit undone; nothing was computed.');}
 function redo(){if(!redoStack.length)return;undoStack.push(doc);doc=redoStack.pop();validate();ctx.onHistory();ctx.render();notice('Redo · model edit redone; nothing was computed.');}
 // ---- the live check ----
 function validate(now=false){
  clearTimeout(checkTimer);check.pending=true;refreshRun();
  const go=async()=>{const seq=++checkSeq,sent=clone(doc);
   try{const reply=await ctx.request('POST','/api/multiphysics/validate',{doc:sent});if(seq!==checkSeq)return;check={pending:false,error:null,...reply};}
   catch(e){if(seq!==checkSeq)return;check={pending:false,diagnostics:[],solve_order:check.solve_order,run_refusal:null,error:e.message};}
   messages=mapDiagnostics(doc,catalog,check.diagnostics);if(active)ctx.render();};
  if(now)go();else checkTimer=setTimeout(go,250);
 }
 const errors=()=>messages.filter(m=>m.severity==='error');
 function runBlock(){
  if(capsError)return 'Studio cannot list the installed physics: '+capsError;
  if(job)return 'Running… (stop it under Study)';
  if(check.error)return 'The model could not be checked: '+check.error;
  if(check.pending)return 'Checking the model…';
  return runBlockText(errors().length,check.run_refusal);
 }
 function refreshRun(){
  const button=$('run-multiphysics'),reason=$('run-multiphysics-reason');if(!button)return;
  button.hidden=!active;reason.hidden=!active;if(!active)return;
  const block=runBlock();button.disabled=!!block;button.textContent=job?'Running… (stop it under Study)':'Run';reason.textContent=job?'':block;
  $('status').textContent=job?'Multiphysics run in progress':block?'Model not ready · '+block:'Model checked · press Run';
 }
 // ---- running ----
 let pollTimer=null;function stopPolling(){clearTimeout(pollTimer);pollTimer=null;}
 async function run(source=doc,{alone=null}={}){
  if(job||(!alone&&runBlock()))return;
  const sent=clone(source),order=alone?[[alone]]:check.solve_order;
  try{const reply=await ctx.request('POST','/api/multiphysics/run',{doc:sent});
   job={id:reply.job,doc:sent,order:reply.solve_order||order,events:[],status:'running',error:null,alone,source:clone(doc)};runFailure=null;
   refreshRun();ctx.render();notice(alone?`Running ${physicsLabel(alone)} alone, without its coupled input…`:'Running every physics in solve order…');poll();
  }catch(e){notice('Run refused: '+e.message);}
 }
 async function poll(){
  if(!job)return;
  try{const s=await ctx.request('GET',`/api/multiphysics/jobs/${job.id}?after=${job.events.length}`);
   job.events.push(...s.events);job.status=s.status;job.error=s.error;
   if(s.status==='running'){renderDock();pollTimer=setTimeout(poll,300);return;}
   if(s.status==='done'){const result=await ctx.request('GET',`/api/multiphysics/jobs/${job.id}/result`);finish(result);return;}
   runFailure={events:job.events,order:job.order,status:s.status,error:s.error,doc:job.doc};const failed=job;job=null;refreshRun();ctx.render();
   notice(s.status==='stopped'?'Run stopped. No result was kept'+(lastRun?'; the previous complete run stays under Results.':'.'):failureText(s.error,failed.doc)+(lastRun?' The previous complete run stays under Results.':''));
  }catch(e){runFailure={events:job.events,order:job.order,status:'error',error:{message:e.message},doc:job.doc};job=null;refreshRun();ctx.render();notice('The run could not be followed: '+e.message);}
 }
 function finish(result){
  const done=job;job=null;
  if(done.alone){uncoupled[done.alone]={rows:effectiveIndexRows(result.physics[done.alone]),source:JSON.stringify(done.source),completedAt:new Date().toISOString()};refreshRun();ctx.render();ctx.announceResult(`${physicsLabel(done.alone)} alone finished; its n_eff is shown beside the coupled one.`);return;}
  lastRun={id:(lastRun?.id||0)+1,doc:done.doc,events:done.events,order:result.solve_order,result,completedAt:new Date().toISOString()};runFailure=null;
  resultPage=resultPages(result).find(p=>p.id.startsWith('results:')&&result.physics[p.id.slice(8)]?.coupled)?.id||resultPages(result)[0].id;
  selection=resultPage;ctx.ui.page='Results';refreshRun();ctx.render();ctx.announceResult(`Run ${lastRun.id} complete. Its results belong to that run; editing the model does not change them.`);
 }
 async function stop(){if(!job)return;try{await ctx.request('POST',`/api/multiphysics/jobs/${job.id}/stop`);notice('Stopping after the physics being solved finishes; no result will be kept.');}catch(e){notice('Stop failed: '+e.message);}}
 // ---- fixes ----
 function applyFix(fix){
  if(!fix)return;
  if(fix.action==='remove-coupling')commit(removeCoupling(doc,fix.coupling),`Coupling ${fix.coupling} removed.`,'model');
  else if(fix.action==='use-same-mesh'){const next=clone(doc);next.couplings[fix.coupling].transfer='same_mesh';commit(next,'Transfer set to Same mesh.');}
  else if(fix.action==='remove-mesh-key'){const next=clone(doc);delete next.mesh[fix.key];commit(next,`Mesh ${quantityWords(fix.key)} removed; both physics use the same mesh.`,'mesh');}
  else if(fix.action==='accept-loop'){const {doc:next,index}=acceptLoop(doc,fix.proposal);commit(next,`Iteration step ${index+1} accepted with the default settings; Undo reverts it.`,'loop:'+index);}
  else if(fix.action==='fill-physmat')commit(fillThermoOptic(doc,fix.material,fix.ref),`Thermo-optic data of ${fix.ref} copied into ${materialLabel(fix.material)}; the source notes it.`);
 }
 const messageHtml=(m,i,show=true)=>`<div class="mp-message ${m.severity}" data-mp-message="${i}"><p>${esc(m.text)}</p><div class="mp-message-actions">${show?`<button type="button" data-mp-show="${i}">Show</button>`:''}${m.fix?`<button type="button" data-mp-fix="${i}">${esc(m.fix.label)}</button>`:''}<details><summary>Details</summary><code>${esc(m.code)}</code> at <code>${esc(m.path||'document')}</code>: ${esc(m.detail)}</details></div></div>`;
 function bindMessages(host){
  host.querySelectorAll('[data-mp-fix]').forEach(b=>b.onclick=()=>applyFix(messages[+b.dataset.mpFix].fix));
  host.querySelectorAll('[data-mp-show]').forEach(b=>b.onclick=()=>{selection=messages[+b.dataset.mpShow].node;if(ctx.ui.page!=='Connections')ctx.ui.page='Model';ctx.render();$('inspector').querySelector('.mp-message')?.scrollIntoView({block:'nearest'});});
 }
 // ---- the tree ----
 function tree(){
  const counts=problemCounts(messages),order=check.solve_order||[],badge=name=>{const i=order.findIndex(g=>g.includes(name));return i<0?'':`<span class="order-badge${order[i].length>1?' cycle':''}" aria-label="solve order ${i+1}">${i+1}</span>`;};
  const count=id=>counts[id]?`<span class="problem-badge" aria-label="${counts[id]} problem${counts[id]===1?'':'s'}">${counts[id]}</span>`:'';
  const item=(id,label,mark,extra='',indent=false)=>`<button data-mp-node="${esc(id)}" aria-pressed="${selection===id}" class="${indent?'tree-child':''}"><span class="tree-node-mark" aria-hidden="true">${mark}</span>${extra}${esc(label)}${count(id)}</button>`;
  const multi=isMultiphysics(doc)||couplingNames(doc).length>0;
  const physics=physicsNames(doc).map(n=>item('physics:'+n,`${physicsLabel(n)} · ${catalog.types.get(doc.physics[n].type)?.label||doc.physics[n].type}`,MARK.physics,multi?badge(n):'')).join('');
  const couplings=couplingNames(doc).map(c=>item('coupling:'+c,couplingTitle(doc,c),MARK.coupling)).join('')||'<p class="muted tree-empty">No couplings</p>';
  const loops=(Array.isArray(doc.study?.loops)?doc.study.loops:[]).map((l,i)=>item('loop:'+i,`Iteration step ${i+1} · ${(l.physics||[]).map(physicsLabel).join(' ⇄ ')}`,MARK.loop,'',true)).join('');
  const materials=materialUses(doc).map(u=>item('material:'+u.ref,u.label,'·','',true)).join('');
  const results=lastRun?resultPages(lastRun.result).map(p=>item(p.id,p.label,MARK.results,'',true)).join(''):'';
  return `<div class="pane-title"><span>Model builder</span><span class="pane-detail">${multi?'Multiphysics model':'Model 1'}</span></div><div class="model-root"><button data-mp-node="model" aria-pressed="${selection==='model'}"><span aria-hidden="true">▾ ◇</span><strong>${esc(doc.name||'Untitled model')}</strong></button></div>`+
   `<section class="tree-group"><h3><span aria-hidden="true">▾</span>Component 1</h3>${item('geometry','Geometry 1',MARK.geometry,'',false)}${item('materials','Materials',MARK.materials)}${materials}${item('mesh',multi?'Mesh 1 · shared':'Mesh 1',MARK.mesh)}</section>`+
   `<section class="tree-group"><h3><span aria-hidden="true">▾</span>Physics</h3>${physics}</section>`+
   (multi?`<section class="tree-group"><h3><span aria-hidden="true">▾</span>Couplings</h3>${couplings}</section>`:'')+
   `<section class="tree-group"><h3><span aria-hidden="true">▾</span>Study 1</h3>${item('study','Study 1',MARK.study)}${multi?item('order','Solve order (from couplings)',MARK.order,'',true):''}${loops}</section>`+
   (results?`<section class="tree-group"><h3><span aria-hidden="true">▾</span>Results · run ${lastRun.id}</h3>${results}</section>`:'')+
   `<div class="capability-card"><span class="capability-dot" aria-hidden="true"></span><strong>Solver available</strong><p>${multi?'Multiphysics model · one Run solves every physics in order':'One physics · format 0.3'}</p></div>`;
 }
 // ---- fields ----
 const getPath=path=>path.reduce((o,k)=>o?.[k],doc);
 function setPath(path,value,message){const next=clone(doc);let o=next;for(const k of path.slice(0,-1)){if(o[k]===undefined||o[k]===null)o[k]={};o=o[k];}if(value===undefined)delete o[path.at(-1)];else o[path.at(-1)]=value;commit(next,message);}
 // a quantity field: a number in the expected unit, or the text as written when another unit
 function qfield(path,label,unit,{required=false,invalid=false,attrs=''}={}){
  const value=getPath(path),q=value===undefined?null:parseQuantity(value),id='mp-f-'+path.join('-');
  if(value!==undefined&&(!q||q.unit!==unit))return `<label for="${id}">${esc(label)}<input id="${id}" type="text" data-mp-text="${esc(JSON.stringify(path))}" value="${esc(value)}" aria-invalid="${invalid}"></label>`;
  return `<label for="${id}">${esc(label)} [${esc(unitText(unit))}]<input id="${id}" type="number" step="any" ${attrs} data-mp-quantity="${esc(JSON.stringify(path))}" data-unit="${esc(unit)}" value="${q?q.number:''}" ${required&&value===undefined?'placeholder="needed"':''} aria-invalid="${invalid}"></label>`;
 }
 function nfield(path,label,attrs=''){const id='mp-f-'+path.join('-');return `<label for="${id}">${esc(label)}<input id="${id}" type="number" step="any" ${attrs} data-mp-number="${esc(JSON.stringify(path))}" value="${esc(getPath(path)??'')}"></label>`;}
 function sfield(path,label,options,current){return `<label>${esc(label)}<select data-mp-select-field="${esc(JSON.stringify(path))}">${Object.entries(options).map(([k,v])=>`<option value="${esc(k)}" ${k===current?'selected':''}>${esc(v)}</option>`).join('')}</select></label>`;}
 const pair=(a,b)=>`<div class="pair"><span>${esc(a)}</span><strong>${esc(b)}</strong></div>`;
 const link=(id,text)=>`<button type="button" class="link-button" data-mp-node="${esc(id)}">${esc(text)}</button>`;
 function bindFields(host){
  host.querySelectorAll('[data-mp-quantity]').forEach(el=>el.onchange=()=>{const path=JSON.parse(el.dataset.mpQuantity),raw=el.value.trim();
   if(raw===''){setPath(path,undefined,'Value cleared.');return;}const n=Number(raw);if(!Number.isFinite(n)){notice('Enter a number.');el.value='';return;}setPath(path,`${raw} ${el.dataset.unit}`,'Value updated.');});
  host.querySelectorAll('[data-mp-text]').forEach(el=>el.onchange=()=>{const path=JSON.parse(el.dataset.mpText),raw=el.value.trim();setPath(path,raw===''?undefined:raw,'Value updated.');});
  host.querySelectorAll('[data-mp-number]').forEach(el=>el.onchange=()=>{const path=JSON.parse(el.dataset.mpNumber),raw=el.value.trim(),n=Number(raw);if(raw===''||!Number.isFinite(n)){notice('Enter a number; the last value is kept.');el.value=getPath(path)??'';return;}setPath(path,n,'Value updated.');});
  host.querySelectorAll('[data-mp-select-field]').forEach(el=>el.onchange=()=>setPath(JSON.parse(el.dataset.mpSelectField),el.value,'Setting changed.'));
  host.querySelectorAll('[data-mp-node]').forEach(b=>b.onclick=()=>choose(b.dataset.mpNode));
  bindMessages(host);
 }
 // ---- Settings ----
 const nodeMessages=id=>messages.map((m,i)=>[m,i]).filter(([m])=>m.node===id||(id==='materials'&&m.node.startsWith('material:'))||(id==='study'&&m.node.startsWith('loop:')));
 function heatSide(name,side){
  const p=doc.physics[name],type=p.prescribed_temperature?.[side]!==undefined?'temperature':p.inward_heat_flux?.[side]!==undefined?'flux':p.convection?.[side]!==undefined?'convection':'insulated';
  const base=['physics',name];let fields='';
  if(type==='temperature')fields=qfield([...base,'prescribed_temperature',side],'Temperature','K');
  else if(type==='flux')fields=qfield([...base,'inward_heat_flux',side],'Inward heat flux','W/m^2');
  else if(type==='convection')fields=qfield([...base,'convection',side,'heat_transfer_coefficient'],'Heat transfer coefficient','W/(m^2 K)')+qfield([...base,'convection',side,'ambient_temperature'],'Ambient temperature','K');
  return `<fieldset class="heat-side"><legend>${side[0].toUpperCase()+side.slice(1)} side</legend><label>Condition<select data-mp-heat-side="${esc(name)}" data-side="${side}">${Object.entries(HEAT_TYPES).map(([k,v])=>`<option value="${k}" ${k===type?'selected':''}>${v}</option>`).join('')}</select></label>${fields}</fieldset>`;
 }
 function regions(){const block=geometryOf(doc);return [...(block?.features||[]).map(f=>f.name),'background'];}
 function physicsPanel(name){
  const p=doc.physics[name],info=catalog.types.get(p.type),order=check.solve_order||[],place=order.findIndex(g=>g.includes(name));
  let html=pair('Physics',info?.label||p.type)+pair('Type',p.type)+pair('Name in file',name)+(place>=0&&couplingNames(doc).length?pair('Solve order',`${place+1} of ${order.length} (from the couplings)`):'');
  if(p.type==='thermal.steady2d'){
   html+='<h3>Sides</h3>'+SIDES.map(s=>heatSide(name,s)).join('')+'<h3>Heat source per region</h3>';
   const source=p.heat_source_density;
   if(typeof source==='string')html+=qfield(['physics',name,'heat_source_density'],'Heat source density (every region)','W/m^3');
   else html+=regions().map(r=>qfield(['physics',name,'heat_source_density',r],`${r}`,'W/m^3')).join('')+'<p class="muted">Leave a region empty for no source there.</p>';
   html+='<p>Conductivity comes from each material (Materials). One fixed temperature or convection sets the temperature level.</p>';
  }else if(p.type==='em.modes2d'){
   html+=qfield(['physics',name,'vacuum_wavelength'],'Vacuum wavelength','nm',{attrs:'min="0"'})+nfield(['physics',name,'mode_count'],'Modes to find','min="1" step="1"')+sfield(['physics',name,'formulation'],'Formulation',{scalar:'Scalar',vector:'Vector'},p.formulation||'scalar');
   html+='<h3>Window sides</h3>'+SIDES.map(s=>sfield(['physics',name,'boundary',s],`${s[0].toUpperCase()+s.slice(1)} side`,{pec:'PEC (electric wall)',pmc:'PMC (magnetic wall)'},p.boundary?.[s]||'pec')).join('');
   const coupling=couplingNames(doc).find(c=>doc.couplings[c]?.to===`${name}.temperature`);
   html+='<h3>Temperature input</h3>';
   if(coupling)html+=`<p>Comes from the coupling ${link('coupling:'+coupling,couplingTitle(doc,coupling))}. Each triangle takes the mean of its 3 node temperatures, and n = n₀ + (dn/dT)(T − T_ref) in each triangle.</p>`;
   else{html+='<p>Not coupled: every material keeps its index n₀.</p>';for(const s of suggestedCouplings(doc,catalog).filter(s=>s.to===`${name}.temperature`))html+=`<p class="mp-suggestion">${esc(suggestionText(s))}</p><button type="button" data-mp-add-coupling="${esc(s.from)}|${esc(s.to)}">Add coupling…</button>`;}
  }else html+='<p>Studio has no settings for this physics; its entry is kept as written in the file.</p>';
  return html+`<p><button type="button" data-mp-remove-physics="${esc(name)}">Remove physics</button></p>`;
 }
 function materialPanel(ref){
  const use=materialUses(doc).find(u=>u.ref===ref),needed=anyTemperatureCoupled(doc);let html=pair('Used by',use?use.regions.join(', '):'no region');
  if(ref.startsWith('physmat:')){const t=PHYSMAT_THERMO_OPTIC[ref];
   html+=pair('Library material',ref)+pair('Refractive index','physmat dispersion at the wavelength')+pair('Thermal conductivity',ref==='physmat:Si'?'148 W/(m K) (constant 300 K handbook value)':ref==='physmat:SiO2'?'1.38 W/(m K) (constant 300 K handbook value)':'from physmat')+(t?pair('Thermo-optic coefficient',`${t.coefficient.toExponential(1)} 1/K`)+pair('Reference temperature',`${t.reference} K`):pair('Thermo-optic data','none in physmat'));
   return html+'<p>Library values are read by the engine; they are not edited here.</p>';}
  const record=doc.materials?.[ref];if(!record||typeof record!=='object')return html+'<p>This material is not in the document’s materials.</p>';
  const base=['materials',ref];html+=nfield([...base,'refractive_index'],'Refractive index n₀')+qfield([...base,'thermal_conductivity'],'Thermal conductivity','W/(m K)');
  const missing=needed&&(record.thermo_optic_coefficient===undefined||record.reference_temperature===undefined);
  html+=`<fieldset class="heat-side${missing?' needed':''}"><legend>Thermo-optic data${missing?' · needed':''}</legend>${qfield([...base,'thermo_optic_coefficient'],'Thermo-optic coefficient dn/dT','1/K',{required:true,invalid:missing&&record.thermo_optic_coefficient===undefined})}${qfield([...base,'reference_temperature'],'Reference temperature T_ref','K',{required:true,invalid:missing&&record.reference_temperature===undefined})}<p>n = n₀ + (dn/dT)(T − T_ref) in each triangle.</p>`;
  if(missing){const r=physmatFor(record);html+=`<button type="button" data-mp-fill="${esc(ref)}" data-ref="${r}">${esc(fillText(r))}</button> <button type="button" data-mp-use-physmat="${esc(ref)}" data-ref="${r}">Use ${r} instead</button>`;}
  html+='</fieldset>';
  if(ref==='heater')html+='<p class="muted">The heater is a lossless placeholder index; metal loss is later work.</p>';
  if(record.source)html+=pair('Source',record.source);
  return html;
 }
 function loopPanel(i){
  const l=doc.study.loops[i],base=['study','loops',i];if(!l)return '<p>No such iteration step.</p>';
  const tol=parseQuantity(l.tolerance?.value);
  let html=pair('Physics',(l.physics||[]).map(physicsLabel).join(' ⇄ '))+pair('Method','Fixed point')+pair('Measured on',portLabel(l.tolerance?.port));
  html+=tol&&tol.unit?qfield([...base,'tolerance','value'],'Stop when the change is at most',tol.unit):`<label>Stop when the change is at most<input type="text" data-mp-text="${esc(JSON.stringify([...base,'tolerance','value']))}" value="${esc(l.tolerance?.value)}"></label>`;
  html+=nfield([...base,'max_iterations'],'Iteration limit','min="2" step="1"')+nfield([...base,'relaxation'],'Relaxation (0, 1]','min="0" max="1"');
  html+='<p>x ← (1 − w) x + w G(x) on the coupled fields, until the change of the measured field is at most the tolerance.</p>';
  const history=lastRun?.result.loops?.find(h=>[...h.physics].sort().join()===[...l.physics].sort().join())?.residuals||(runFailure?.error?.code==='E-LOOP-DIVERGED'?runFailure.error.residuals.map(v=>({value:v,unit:runFailure.error.unit})):null);
  if(history)html+=`<h3>Change per iteration · ${lastRun&&!runFailure?'run '+lastRun.id:'last run'}</h3>`+residualChart(history,tol?.number);
  return html+`<p><button type="button" data-mp-remove-loop="${i}">Remove iteration step</button></p>`;
 }
 function residualChart(points,tolerance){
  const vals=points.map(p=>typeof p==='number'?p:p.value).filter(v=>v>0);if(!vals.length)return '<p class="muted">No change measured yet.</p>';
  const all=[...vals,...(tolerance>0?[tolerance]:[])],lo=Math.log10(Math.min(...all))-0.3,hi=Math.log10(Math.max(...all))+0.3,W=300,H=140,x=i=>30+i*(W-40)/Math.max(1,vals.length-1),y=v=>10+(hi-Math.log10(v))*(H-30)/(hi-lo||1);
  const line=vals.map((v,i)=>`${i?'L':'M'}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(' ');
  return `<svg class="mp-residuals" viewBox="0 0 ${W} ${H}" role="img" aria-label="Change per iteration on a log scale, last ${formatValue(vals.at(-1))}"><path d="M30 10 V${H-20} H${W-10}" stroke="#7a939f" fill="none"/>${tolerance>0?`<path d="M30 ${y(tolerance).toFixed(1)} H${W-10}" stroke="#285db1" stroke-dasharray="4 3"/><text x="${W-12}" y="${(y(tolerance)-4).toFixed(1)}" text-anchor="end" font-size="9" fill="#285db1">stop at ${formatValue(tolerance)}</text>`:''}<path d="${line}" stroke="#b9772c" fill="none" stroke-width="1.5"/>${vals.map((v,i)=>`<circle cx="${x(i).toFixed(1)}" cy="${y(v).toFixed(1)}" r="2" fill="#b9772c"/>`).join('')}<text x="4" y="14" font-size="9" fill="#5b6d82">${formatValue(10**hi)}</text><text x="4" y="${H-20}" font-size="9" fill="#5b6d82">${formatValue(10**lo)}</text><text x="${W/2}" y="${H-4}" text-anchor="middle" font-size="9" fill="#5b6d82">iteration</text></svg>`;
 }
 function settings(){
  const [kind,...rest]=selection.split(':'),id=rest.join(':');let title,html='';
  if(kind==='model'){title='Model';html=`<label>Name<input type="text" data-mp-text="${esc(JSON.stringify(['name']))}" value="${esc(doc.name||'')}"></label>`+pair('Format',isMultiphysics(doc)?`Multiphysics model · ${ENVELOPE}`:'One physics · 0.3')+pair('Physics',physicsNames(doc).map(physicsLabel).join(', ')||'none')+pair('Couplings',String(couplingNames(doc).length))+'<p><button type="button" data-mp-dialog="physics">Add physics…</button> <button type="button" data-mp-dialog="coupling">Add coupling…</button></p><p>Save model file keeps this document; runs stay in this tab.</p>';}
  else if(kind==='geometry'){title='Geometry 1';const g=geometryOf(doc),u=g?.length_unit||'';const gpath=doc.geometry?.version===1?['geometry','components',Object.keys(doc.geometry.components)[0]]:['geometry'];
   html=pair('Length unit',u)+['xmin','xmax','ymin','ymax'].map(k=>nfield([...gpath,'domain',k],`Domain ${k} [${u}]`)).join('')+'<h3>Shapes (later shapes win where they overlap)</h3>'+(g?.features||[]).map((f,i)=>`<fieldset class="heat-side"><legend>${esc(f.name)} · ${esc(f.type)} · ${esc(materialLabel(f.material))}</legend>${f.type==='rect'?['x','y','w','h'].map(k=>nfield([...gpath,'features',i,k],`${k} [${u}]`)).join(''):'<p class="muted">Edited in the file.</p>'}</fieldset>`).join('')+'<p>Every physics uses this geometry and one shared mesh.</p>';}
  else if(kind==='materials'){title='Materials';html=materialUses(doc).map(u=>`<p>${link('material:'+u.ref,u.label)} · ${esc(u.local?'document record':u.ref)}</p>`).join('')+(anyTemperatureCoupled(doc)?'<p>A coupled temperature needs a thermo-optic coefficient and a reference temperature for every optical material.</p>':'');}
  else if(kind==='material'){title=materialLabel(id,materialUses(doc).find(u=>u.ref===id)?.regions||[]);html=materialPanel(id);}
  else if(kind==='mesh'){title=isMultiphysics(doc)?'Mesh 1 · shared':'Mesh 1';const modes=physicsNames(doc).find(n=>doc.physics[n].type==='em.modes2d'),heat=physicsNames(doc).find(n=>doc.physics[n].type==='thermal.steady2d');
   html=qfield(['mesh','element_size'],'Element size','um',{attrs:'min="0"'})+pair('Refinement',(doc.mesh?.controls||[]).map(c=>`${c.select}: ${c.near??c.element_size} near, ${c.far??''} far within ${c.refinement_distance??''}`).join('; ')||'none');
   if(modes&&heat&&doc.mesh?.grading===undefined)html+=pair('Grading toward the core',`not available: ${physicsLabel(heat)} does not read it`);
   html+='<p>Every physics solves on this one mesh, so coupled values move without interpolation.</p>';}
  else if(kind==='physics'){title=doc.physics[id]?physicsLabel(id):id;html=doc.physics[id]?physicsPanel(id):'<p>This physics is not in the model.</p>';}
  else if(kind==='coupling'){const c=doc.couplings?.[id];title=c?couplingTitle(doc,id):id;if(c){const inp=catalog.types.get(doc.physics[splitSpec(c.to)[0]]?.type)?.ports.find(p=>p.name===splitSpec(c.to)[1]);
   html=pair('From',portLabel(c.from))+pair('To',portLabel(c.to))+pair('Transfer',c.transfer==='same_mesh'?'Same mesh (both use Mesh 1)':String(c.transfer))+pair('Values',transferNote(doc,catalog,c.from,c.to).split(' · ').slice(1).join(' · ')||'—')+(inp?pair('Input takes',(inp.combine||'single')==='single'?'one source':'sources add'):'')+pair('Name in file',id)+`<p><button type="button" data-mp-remove-coupling="${esc(id)}">Remove coupling</button></p>`;}}
  else if(kind==='study'){title='Study 1';const sweep=doc.study?.type==='sweep';html=pair('Study',sweep?'Sweep':'Single run')+(sweep?`<p class="validation-warning">${esc(check.run_refusal||'')}</p><button type="button" data-mp-single>Use single run</button>`:'')+'<h3>Solve order (from the couplings)</h3>'+orderList()+((doc.study?.loops||[]).length?'<h3>Iteration steps</h3>'+doc.study.loops.map((l,i)=>`<p>${link('loop:'+i,`Iteration step ${i+1} · ${(l.physics||[]).map(physicsLabel).join(' ⇄ ')}`)} · ${esc(loopText(l))}</p>`).join(''):'');}
  else if(kind==='order'){title='Solve order';html=orderList()+'<p>The order is derived from the couplings, not stored. To change it, change the couplings.</p>';}
  else if(kind==='loop'){title=`Iteration step ${+id+1}`;html=loopPanel(+id);}
  else if(kind==='results'){title='Results';html=lastRun?pair('Run',String(lastRun.id))+pair('Completed',new Date(lastRun.completedAt).toLocaleTimeString())+pair('Inputs',JSON.stringify(lastRun.doc)===signature()?'Same as the current model':'The model changed since this run')+'<p>A result belongs to its run; editing the model does not change it.</p>':'<p>No run yet.</p>';}
  const own=nodeMessages(selection).map(([m,i])=>messageHtml(m,i,false)).join('');
  return `<span class="muted">SELECTION</span><h2>${esc(title)}</h2>${own}${html}`;
 }
 function orderList(){const order=check.solve_order||[];return `<ol class="mp-order">${order.map(g=>`<li>${g.length>1?`Together: ${esc(g.map(physicsLabel).join(' ⇄ '))}`:esc(physicsLabel(g[0]))}</li>`).join('')}</ol>`;}
 function bindSettings(host){
  bindFields(host);
  host.querySelectorAll('[data-mp-heat-side]').forEach(el=>el.onchange=()=>{const name=el.dataset.mpHeatSide,side=el.dataset.side,next=clone(doc),p=next.physics[name];
   for(const k of ['prescribed_temperature','inward_heat_flux','convection'])if(p[k]&&typeof p[k]==='object'){delete p[k][side];if(!Object.keys(p[k]).length)delete p[k];}
   if(el.value==='temperature')(p.prescribed_temperature??={})[side]='300 K';else if(el.value==='flux')(p.inward_heat_flux??={})[side]='0 W/m^2';else if(el.value==='convection')(p.convection??={})[side]={heat_transfer_coefficient:'10 W/(m^2 K)',ambient_temperature:'300 K'};
   commit(next,`${physicsLabel(name)} ${side} side: ${HEAT_TYPES[el.value].toLowerCase()}.`);});
  host.querySelectorAll('[data-mp-remove-physics]').forEach(b=>b.onclick=()=>{const n=b.dataset.mpRemovePhysics;commit(removePhysics(doc,n),`${physicsLabel(n)} removed; couplings that named it are listed in Messages.`,'model');});
  host.querySelectorAll('[data-mp-remove-coupling]').forEach(b=>b.onclick=()=>{const n=b.dataset.mpRemoveCoupling;commit(removeCoupling(doc,n),`Coupling ${couplingTitle(doc,n)} removed.`,'model');});
  host.querySelectorAll('[data-mp-remove-loop]').forEach(b=>b.onclick=()=>commit(removeLoop(doc,+b.dataset.mpRemoveLoop),'Iteration step removed.','study'));
  host.querySelectorAll('[data-mp-fill]').forEach(b=>b.onclick=()=>applyFix({action:'fill-physmat',material:b.dataset.mpFill,ref:b.dataset.ref}));
  host.querySelectorAll('[data-mp-use-physmat]').forEach(b=>b.onclick=()=>commit(usePhysmat(doc,b.dataset.mpUsePhysmat,b.dataset.ref),`${materialLabel(b.dataset.mpUsePhysmat)} replaced by ${b.dataset.ref} in every region; its thermo-optic data come from physmat.`,'material:'+b.dataset.ref));
  host.querySelectorAll('[data-mp-add-coupling]').forEach(b=>b.onclick=()=>{const [from,to]=b.dataset.mpAddCoupling.split('|');couplingDialog(from,to);});
  host.querySelectorAll('[data-mp-dialog]').forEach(b=>b.onclick=()=>b.dataset.mpDialog==='physics'?physicsDialog():couplingDialog());
  host.querySelectorAll('[data-mp-single]').forEach(b=>b.onclick=()=>{const next=clone(doc);next.study={type:'single',...(next.study.loops?{loops:next.study.loops}:{})};commit(next,'Study set to a single run.');});
 }
 function choose(id){selection=id;if(id.startsWith('results:')){resultPage=id;ctx.ui.page='Results';}else if(id.startsWith('coupling:')&&ctx.ui.page!=='Connections')ctx.ui.page='Model';else if(ctx.ui.page==='Results'||ctx.ui.page==='Applications'||ctx.ui.page==='Compare')ctx.ui.page='Model';ctx.render();}
 // ---- dialogs ----
 function dialog(title,body,actions){
  const d=document.createElement('dialog');d.className='mp-dialog';d.innerHTML=`<form method="dialog"><h2>${esc(title)}</h2>${body}<div class="mp-dialog-actions">${actions}<button value="cancel" type="submit">Cancel</button></div></form>`;
  document.body.append(d);d.addEventListener('close',()=>d.remove());d.showModal();return d;
 }
 function physicsDialog(){
  if(capsError){notice('Studio cannot list the installed physics: '+capsError);return;}
  const willBecome=!isMultiphysics(doc)&&physicsNames(doc).length===1;
  const body=(willBecome?'<p class="mp-note">Adding a second physics saves this model as a multiphysics model (format 0.3/multiphysics.1).</p>':'')+catalog.providers.map(p=>`<section class="mp-provider"><h3>${esc(p.name)}${p.version?` · ${esc(p.version)}`:''}</h3>${p.status!=='available'?`<p class="muted">Unavailable: ${esc(p.error||'it did not load')}. Other physics stay usable.</p>`:p.types.map(t=>catalog.types.get(t)).filter(Boolean).map(t=>`<div class="mp-kind${t.addable?'':' unavailable'}"><div><strong>${esc(t.label)}</strong> <code>${esc(t.type)}</code> · ${esc(t.field)}<ul>${t.ports.map(port=>`<li>${port.direction==='input'?'in':'out'}: ${esc(quantityWords(port.name))} · ${esc(unitText(port.unit))} · ${esc(locationWords(port.location))}${port.direction==='input'?' · '+((port.combine||'single')==='single'?'one source':'sources add'):''}</li>`).join('')}</ul>${t.addable?'':`<p class="muted">Not offered: ${esc(t.type)} ${esc(t.reason)}.</p>`}</div>${t.addable?`<button type="button" data-add-type="${esc(t.type)}">Add physics</button>`:''}</div>`).join('')}</section>`).join('');
  const d=dialog('Add physics',body,'');
  d.querySelectorAll('[data-add-type]').forEach(b=>b.onclick=()=>{try{const {doc:next,name,becameMultiphysics}=addPhysics(doc,catalog.types.get(b.dataset.addType));d.close();
   commit(next,`${physicsLabel(name)} added.`+(becameMultiphysics?'':''),'physics:'+name);
   const s=suggestedCouplings(doc,catalog)[0];if(s)notice(`${physicsLabel(name)} added. ${suggestionText(s)} Use Add coupling… to connect them.`);}catch(e){notice(e.message);}});
 }
 function couplingDialog(from=null,to=null){
  const sources=sourceChoices(doc,catalog);from=from||sources.find(s=>s.ok)?.spec;
  if(!from){notice('No physics of this model sends a field to couplings yet. Add physics first.');return;}
  const d=dialog('Add coupling','<div id="mp-coupling-body"></div>','<button type="button" id="mp-coupling-add" class="primary">Add coupling</button>');
  const draw=()=>{const targets=targetChoices(doc,catalog,from);if(!to||!targets.find(t=>t.spec===to&&t.ok))to=targets.find(t=>t.ok)?.spec||null;
   d.querySelector('#mp-coupling-body').innerHTML=`<label>From (outputs)<select id="mp-from">${sources.map(s=>`<option value="${esc(s.spec)}" ${s.spec===from?'selected':''} ${s.ok?'':'disabled'}>${esc(s.label)} · ${esc(unitText(s.port.unit))}${s.ok?'':' — '+esc(s.reason)}</option>`).join('')}</select></label>
    <label>To (inputs)<select id="mp-to">${targets.map(t=>`<option value="${esc(t.spec)}" ${t.spec===to?'selected':''} ${t.ok?'':'disabled'}>${esc(t.label)} · ${esc(unitText(t.port.unit))}${t.ok?'':' — '+esc(t.reason)}</option>`).join('')}</select></label>
    <ul class="mp-choice-reasons">${targets.filter(t=>!t.ok).map(t=>`<li>${esc(t.label)}: ${esc(t.reason)}</li>`).join('')}</ul>
    ${pair('Transfer',transferNote(doc,catalog,from,to||from).split(' · ')[0])}${to?`<p>${esc(transferNote(doc,catalog,from,to).split(' · ').slice(1).join(' · '))}.</p>`:'<p class="muted">No input can take this output.</p>'}`;
   d.querySelector('#mp-from').onchange=e=>{from=e.target.value;to=null;draw();};d.querySelector('#mp-to').onchange=e=>{to=e.target.value;draw();};d.querySelector('#mp-coupling-add').disabled=!to;};
  draw();
  d.querySelector('#mp-coupling-add').onclick=()=>{try{const {doc:next,name}=addCoupling(doc,catalog,from,to);d.close();commit(next,`Coupling ${portLabel(from)} → ${portLabel(to)} added.`,'coupling:'+name);}catch(e){notice(e.message);}};
 }
 // ---- graphics ----
 function geometrySvg(){
  const g=geometryOf(doc);if(!g?.domain)return '<p>No geometry.</p>';const D=g.domain,w=D.xmax-D.xmin,h=D.ymax-D.ymin,s=Math.min(540/w,300/h),X=x=>300+(x-(D.xmin+D.xmax)/2)*s,Y=y=>175-(y-(D.ymin+D.ymax)/2)*s;
  const refs=materialUses(doc).map(u=>u.ref),fill=ref=>FILLS[ref]||OTHER_FILLS[Math.max(0,refs.indexOf(ref))%OTHER_FILLS.length];
  const shapes=(g.features||[]).map(f=>{const sel=selection==='material:'+f.material,attrs=`fill="${fill(f.material)}" stroke="${sel?'#285db1':'#ffffff'}" stroke-width="${sel?2:1}" data-mp-pick="${esc(f.material)}" role="button" tabindex="0" aria-label="${esc(f.name)}: ${esc(materialLabel(f.material))}"`;
   if(f.type==='rect')return `<rect x="${X(f.x)}" y="${Y(f.y+f.h)}" width="${f.w*s}" height="${f.h*s}" ${attrs}/>`;
   if(f.type==='circle')return `<circle cx="${X(f.cx)}" cy="${Y(f.cy)}" r="${f.r*s}" ${attrs}/>`;
   if(f.type==='polygon')return `<polygon points="${f.points.map(([x,y])=>X(x)+','+Y(y)).join(' ')}" ${attrs}/>`;return '';}).join('');
  const labels=(g.features||[]).filter(f=>f.type==='rect').map(f=>`<text x="${X(f.x+f.w)+4}" y="${Y(f.y+f.h/2)+3}" font-size="10" fill="#34445b">${esc(f.name)}</text>`).join('');
  return `<svg data-geometry-view="multiphysics" viewBox="0 0 600 350" role="group" aria-label="Geometry 1: ${esc(doc.name||'model')}"><rect x="${X(D.xmin)}" y="${Y(D.ymax)}" width="${w*s}" height="${h*s}" fill="${fill(g.background?.material)}" stroke="#7a939f" data-mp-pick="${esc(g.background?.material)}" role="button" tabindex="0" aria-label="background: ${esc(materialLabel(g.background?.material||''))}"/>${shapes}${labels}<text x="300" y="16" text-anchor="middle" font-size="11" fill="#34445b">${esc(w)} × ${esc(h)} ${esc(g.length_unit)} · shared by ${esc(physicsNames(doc).map(physicsLabel).join(' and '))}</text></svg>`;
 }
 function connections(){
  const layout=connectionLayout(doc,catalog,check.solve_order,messages),states={};
  if(job||runFailure||lastRun){const src=job||runFailure||lastRun,rows=progressRows(src.order||[],src.doc,src.events||[],job?'running':runFailure?runFailure.status:'done',runFailure?.error);for(const r of rows)for(const n of r.group)states[n]={state:r.state,text:r.text};}
  const relevant=messages.map((m,i)=>[m,i]).filter(([m])=>m.node.startsWith('coupling:')||m.code==='E-COUPLING-CYCLE'||m.node.startsWith('physics:'));
  const loopRow=job?progressRows(job.order,job.doc,job.events,'running').find(r=>r.residuals.length):null;
  return `<div class="graph-heading"><h2>Physics connections</h2><span class="setup-badge solved">${couplingNames(doc).length?'Drawn from the couplings':'No couplings yet'}</span></div><p class="graph-intro">Badges give the solve order. Select a node or wire to open it in Settings. <button type="button" data-mp-action="add-coupling">Add coupling…</button></p>${renderMultiphysicsGraph(layout,selection,states)}${relevant.length?`<section class="mp-graph-messages" aria-label="Coupling problems">${relevant.map(([m,i])=>messageHtml(m,i)).join('')}</section>`:''}${loopRow?`<h3>${esc(loopRow.label)} · change per iteration</h3>`+residualChart(loopRow.residuals,parseQuantity(job.doc.study.loops[loopRow.loop]?.tolerance?.value)?.number):''}`;
 }
 function installGraph(host){
  const stage=host.querySelector('.mp-stage');if(!stage)return;
  const svg=stage.querySelector('.graph-wires'),edges=JSON.parse(stage.dataset.edges);
  const draw=()=>{if(!stage.isConnected)return;const b=stage.getBoundingClientRect();svg.setAttribute('viewBox',`0 0 ${b.width} ${b.height}`);
   const point=id=>{const el=stage.querySelector(`[data-port="${CSS.escape(id)}"] .port-dot`);if(!el)return null;const r=el.getBoundingClientRect();return {x:r.x+r.width/2-b.x,y:r.y+r.height/2-b.y};};
   const channel=Math.max(0,...[...stage.querySelectorAll('.graph-node')].map(n=>n.getBoundingClientRect().bottom-b.y))+18;
   svg.replaceChildren(...edges.map(([from,to,color,label,route,coupling])=>{const a=point(from),c=point(to);const g=document.createElementNS('http://www.w3.org/2000/svg','g');if(!a||!c)return g;
    const path=document.createElementNS('http://www.w3.org/2000/svg','path');path.setAttribute('d',route==='below'?loopPath(a,c,channel):curvePath(a,c));path.setAttribute('class',color+(selection==='coupling:'+coupling?' selected':''));path.dataset.coupling=coupling;
    const hit=path.cloneNode();hit.setAttribute('class','wire-hit');hit.addEventListener('click',()=>choose('coupling:'+coupling));
    const title=document.createElementNS('http://www.w3.org/2000/svg','title');title.textContent=label;path.append(title);g.append(path,hit);
    const mark=stage.querySelector(`[data-mark-for="${CSS.escape(coupling)}"]`);if(mark){const m=route==='below'?{x:(a.x+c.x)/2,y:channel}:{x:(a.x+c.x)/2,y:(a.y+c.y)/2};mark.style.left=m.x+'px';mark.style.top=m.y+'px';}
    return g;}));};
  resize=new ResizeObserver(draw);resize.observe(stage);draw();
 }
 // ---- results ----
 const RAMP=[[48,18,59],[64,98,215],[34,180,180],[150,215,80],[250,200,40],[180,30,20]];
 function colour(t){t=Math.min(1,Math.max(0,t))*(RAMP.length-1);const i=Math.min(RAMP.length-2,Math.floor(t)),f=t-i,a=RAMP[i],b=RAMP[i+1];return `rgb(${a.map((v,k)=>Math.round(v+(b[k]-v)*f)).join(',')})`;}
 function drawMap(canvas,result,values,{nodal=false,region=null,label}){
  const mesh=result.mesh,P=mesh.node_coordinates,T=mesh.triangles,keep=region===null?null:mesh.region_names.indexOf(region);
  const tris=T.map((t,i)=>i).filter(i=>keep===null||keep<0||mesh.regions[i]===keep),tv=i=>nodal?(values[T[i][0]]+values[T[i][1]]+values[T[i][2]])/3:values[i];
  let x0=Infinity,x1=-Infinity,y0=Infinity,y1=-Infinity,lo=Infinity,hi=-Infinity;for(const i of tris){for(const n of T[i]){x0=Math.min(x0,P[n][0]);x1=Math.max(x1,P[n][0]);y0=Math.min(y0,P[n][1]);y1=Math.max(y1,P[n][1]);}const v=tv(i);lo=Math.min(lo,v);hi=Math.max(hi,v);}
  const r=canvas.getBoundingClientRect(),W=Math.max(200,Math.round(r.width)),H=Math.max(120,Math.round(r.height)),dpr=globalThis.devicePixelRatio||1;canvas.width=W*dpr;canvas.height=H*dpr;
  const c=canvas.getContext('2d');c.setTransform(dpr,0,0,dpr,0,0);c.clearRect(0,0,W,H);const pad=16,bar=46,s=Math.min((W-2*pad-bar)/(x1-x0||1),(H-2*pad)/(y1-y0||1)),X=x=>pad+(x-x0)*s,Y=y=>H-pad-(y-y0)*s;
  for(const i of tris){const [a,b,d]=T[i];c.beginPath();c.moveTo(X(P[a][0]),Y(P[a][1]));c.lineTo(X(P[b][0]),Y(P[b][1]));c.lineTo(X(P[d][0]),Y(P[d][1]));c.closePath();const col=colour(hi>lo?(tv(i)-lo)/(hi-lo):.5);c.fillStyle=col;c.strokeStyle=col;c.lineWidth=.6;c.fill();c.stroke();}
  const bx=W-bar+6;for(let k=0;k<64;k++){c.fillStyle=colour(k/63);c.fillRect(bx,H-pad-(k+1)*(H-2*pad)/64,10,(H-2*pad)/64+1);}
  c.fillStyle='#34445b';c.font='10px system-ui,sans-serif';const fmt=v=>Math.abs(hi-lo)<1e-3*Math.max(Math.abs(hi),1e-30)?v.toPrecision(7):v.toPrecision(Math.max(3,Math.ceil(Math.log10(Math.max(Math.abs(hi),Math.abs(lo))/Math.max(hi-lo,1e-300)))+2));c.fillText(fmt(hi),bx-12,pad-4>8?pad-4:10);c.fillText(fmt(lo),bx-12,H-4);
  canvas.setAttribute('aria-label',`${label}: ${formatValue(lo)} to ${formatValue(hi)}`);return {lo,hi};
 }
 const wavelengthText=w=>{const v=Number(w?.values?.[0]??w?.value);return w?.unit==='m'&&Number.isFinite(v)?`${Number((v*1e9).toPrecision(9))} nm`:`${w?.values?.[0]??w?.value??''} ${w?.unit||''}`;};
 function results(host){
  if(!lastRun){host.innerHTML=`<h2>No result in this tab</h2><p>Press Run to solve every physics in solve order. Results are kept in this tab; Save model file keeps the model.</p>${runFailure?`<p class="validation-warning">${esc(runFailure.status==='stopped'?'The last run was stopped; no result was kept.':failureText(runFailure.error,runFailure.doc))}</p>`:''}`;return [];}
  const r=lastRun.result,pages=resultPages(r);if(!pages.find(p=>p.id===resultPage))resultPage=pages[0].id;
  const same=JSON.stringify(lastRun.doc)===signature();
  host.innerHTML=`<div class="toolbar mp-result-tabs" role="tablist">${pages.map(p=>`<button role="tab" data-mp-node="${p.id}" aria-selected="${p.id===resultPage}">${esc(p.label)}</button>`).join('')}</div><p class="muted">Run ${lastRun.id} · ${new Date(lastRun.completedAt).toLocaleTimeString()} · ${same?'the current model':'the model changed since this run; this result is unchanged'}.${runFailure?' The last run failed; this is the previous complete run.':''}</p>`;
  const id=resultPage.slice(8),maps=[];
  if(id==='check'){
   const rows=couplingCheckRows(r,lastRun.doc);
   host.insertAdjacentHTML('beforeend',`<h2>Coupling check</h2>${pair('Solve order used',r.solve_order.map(g=>g.map(physicsLabel).join(' ⇄ ')).join(' → '))}<div class="table-scroll"><table class="mp-check"><thead><tr><th>Coupling</th><th>Sent</th><th>Received</th><th>Check</th></tr></thead><tbody>${rows.map(row=>`<tr><td>${esc(row.title)}<br><small>${esc(row.name)}</small></td><td>${esc(row.sent)}</td><td>${esc(row.received)}</td><td class="${row.passed?'passed':'failed'}">${esc(row.check)}</td></tr>`).join('')}</tbody></table></div>`);
   for(const loop of r.loops||[])host.insertAdjacentHTML('beforeend',`<h3>${esc(loop.physics.map(physicsLabel).join(' ⇄ '))} · settled in ${loop.iterations} iterations</h3>`+residualChart(loop.residuals,parseQuantity(loop.tolerance?.value)?.number));
   return maps;
  }
  const p=r.physics[id];
  if(p.type==='thermal.steady2d'){
   host.insertAdjacentHTML('beforeend',`<h2>${esc(physicsLabel(id))} · temperature</h2><div class="mp-plot"><canvas data-mp-map="temperature" role="img"></canvas></div>${pair('Minimum T',p.range.min.toFixed(3)+' K')}${pair('Maximum T',p.range.max.toFixed(3)+' K')}${pair('Nodes',r.mesh.node_coordinates.length.toLocaleString('en-US'))}${pair('Triangles',r.mesh.triangles.length.toLocaleString('en-US'))}<p class="muted">Each triangle is coloured by the mean of its node temperatures.</p>`);
   maps.push(['temperature',()=>drawMap(host.querySelector('[data-mp-map=temperature]'),r,p.temperature.values,{nodal:true,label:'Temperature in K'})]);
  }else{
   const rows=effectiveIndexRows(p),alone=uncoupled[id],coupled=p.coupled;
   host.insertAdjacentHTML('beforeend',`<h2>${esc(physicsLabel(id))} · optical modes</h2>`);
   if(coupled){const region=r.mesh.region_names.includes('core')?'core':null,dn=indexChange(r,lastRun.doc,id);
    host.insertAdjacentHTML('beforeend',`<div class="mp-maps"><figure><figcaption>Temperature per triangle [K]${region?' · core':''}</figcaption><div class="mp-plot"><canvas data-mp-map="T" role="img"></canvas></div></figure><figure><figcaption><label>Show <select id="mp-index-view"><option value="n" ${indexView==='n'?'selected':''}>refractive index n</option><option value="dn" ${indexView==='dn'?'selected':''}>change n − n₀</option></select></label>${region?' · core':''}</figcaption><div class="mp-plot"><canvas data-mp-map="n" role="img"></canvas></div></figure></div><p class="muted">The coupled input as the optical solve used it: the mean of each triangle's 3 node temperatures, and n = n₀ + (dn/dT)(T − T_ref). The change is computed here from the material data.</p>`);
    maps.push(['T',()=>drawMap(host.querySelector('[data-mp-map=T]'),r,coupled.temperature.values,{region,label:'Temperature in K'})]);
    maps.push(['n',()=>drawMap(host.querySelector('[data-mp-map=n]'),r,indexView==='n'?coupled.refractive_index.n:dn,{region,label:indexView==='n'?'Refractive index':'Index change n − n₀'})]);}
   else host.insertAdjacentHTML('beforeend','<p>This physics had no coupled input in this run.</p>');
   const sameSource=alone&&alone.source===JSON.stringify(lastRun.doc);
   host.insertAdjacentHTML('beforeend',`<div class="table-scroll"><table class="mp-neff"><thead><tr><th>Mode</th><th>n_eff${coupled?' (coupled)':''}</th>${alone?'<th>n_eff without heater</th><th>Shift</th>':''}</tr></thead><tbody>${rows.map((row,k)=>`<tr><td>${row.mode}</td><td data-neff="${row.mode}" data-neff-value="${row.value}">${row.value.toFixed(8)}</td>${alone?`<td data-neff-alone="${row.mode}" data-neff-value="${alone.rows[k]?.value??''}">${alone.rows[k]?alone.rows[k].value.toFixed(8):'—'}</td><td>${alone.rows[k]?(row.value-alone.rows[k].value).toExponential(3):'—'}</td>`:''}</tr>`).join('')}</tbody></table></div>${pair('Vacuum wavelength',wavelengthText(p.vacuum_wavelength))}`+
    (coupled?`<p>${alone?(sameSource?'The uncoupled column is the optical model run alone, from the same model.':'The uncoupled column was run from an earlier model.'):'An uncoupled comparison appears here only if you run the optical model alone.'} <button type="button" id="mp-run-alone" ${job?'disabled':''}>Run ${esc(physicsLabel(id))} alone</button></p>`:''));
   const alone_=host.querySelector('#mp-run-alone');if(alone_)alone_.onclick=()=>run(uncoupledDocument(lastRun.doc,id),{alone:id});
   const sel=host.querySelector('#mp-index-view');if(sel)sel.onchange=()=>{indexView=sel.value;maps.find(m=>m[0]==='n')?.[1]();};
  }
  return maps;
 }
 // ---- the dock ----
 function renderDock(){
  const host=$('sequence');if(!host)return;const src=job||runFailure||lastRun;
  const order=src?.order||check.solve_order||[];const rows=src?progressRows(order,src.doc,src.events||[],job?'running':runFailure?runFailure.status:'done',runFailure?.error):order.map(g=>({group:g,label:g.length>1?g.map(physicsLabel).join(' ⇄ '):physicsLabel(g[0]),state:'ready',text:'Ready'}));
  host.innerHTML=rows.map((r,i)=>`<span class="mp-row ${esc(r.state)}"><b>${i+1}</b>${esc(r.label)} · ${esc(r.text)}</span>`).join('')+(job?'<button type="button" id="mp-stop">Stop run</button>':'');
  const stopButton=$('mp-stop');if(stopButton)stopButton.onclick=stop;
  const box=$('mp-messages');if(!box)return;box.hidden=!active;
  const list=messages.map((m,i)=>messageHtml(m,i)).join(''),fail=runFailure&&runFailure.status!=='stopped'?`<div class="mp-message error"><p>${esc(failureText(runFailure.error,runFailure.doc))}</p></div>`:'';
  const suggest=suggestedCouplings(doc,catalog).map(s=>`<div class="mp-message info"><p>${esc(suggestionText(s))}</p><div class="mp-message-actions"><button type="button" data-mp-add-coupling="${esc(s.from)}|${esc(s.to)}">Add coupling…</button></div></div>`).join('');
  box.innerHTML=fail+list+suggest||'<p class="muted">No problems: the model passes the check.</p>';bindMessages(box);
  box.querySelectorAll('[data-mp-add-coupling]').forEach(b=>b.onclick=()=>{const [f,t]=b.dataset.mpAddCoupling.split('|');couplingDialog(f,t);});
 }
 // ---- the page ----
 function renderPage(){
  resize?.disconnect();resize=null;const page=ctx.ui.page,main=document.querySelector('main');
  main.dataset.page=page;main.classList.toggle('connecting',page==='Connections');main.classList.toggle('choosing',page==='Applications');main.classList.remove('comparing');
  $('view-title').textContent=({Model:'Graphics',Connections:'Physics connections',Results:'Results',Compare:'Comparison',Applications:'Model library'})[page];
  $('view-detail').textContent=page==='Connections'?(couplingNames(doc).length?'Drawn from the couplings':'One physics'):page==='Model'?'Interactive model view':page==='Applications'?'Choose an application':'';
  document.querySelectorAll('[data-page]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.page===page));
  document.querySelectorAll('[data-command-node]').forEach(b=>{b.disabled=page==='Applications';b.onclick=()=>choose(({Geometry:'geometry',Materials:'materials',Mesh:'mesh',Study:'study'})[b.dataset.commandNode]);});
  document.querySelectorAll('[data-view]').forEach(b=>b.hidden=true);
  const toolbar=document.querySelector('.workspace > .toolbar');if(toolbar)toolbar.style.display=page==='Model'?'flex':'none';
  $('breadcrumb').textContent=page+' / '+(selection.startsWith('physics:')?physicsLabel(selection.slice(8)):selection.startsWith('coupling:')?couplingTitle(doc,selection.slice(9)):selection.startsWith('material:')?materialLabel(selection.slice(9)):selection.startsWith('results:')?'Results':selection[0].toUpperCase()+selection.slice(1));
  document.querySelector('.workspace > .note').textContent=page==='Results'?'A result belongs to its run; editing the model does not change it.':'Lengths in the geometry’s unit; other values carry their units. Run solves every physics in solve order.';
  $('solver-log').hidden=true;$('workflow').hidden=true;
  $('tree').innerHTML=tree();$('tree').querySelectorAll('[data-mp-node]').forEach(b=>b.onclick=()=>choose(b.dataset.mpNode));
  const inspector=$('inspector');inspector.innerHTML=settings();bindSettings(inspector);
  const canvas=$('canvas');let maps=[];
  if(page==='Applications')ctx.applications(canvas);
  else if(page==='Connections'){canvas.innerHTML=connections();bindFields(canvas);canvas.querySelectorAll('[data-mp-select]').forEach(b=>b.onclick=()=>choose(b.dataset.mpSelect));canvas.querySelector('[data-mp-action=add-coupling]').onclick=()=>couplingDialog();installGraph(canvas);}
  else if(page==='Results'){maps=results(canvas);canvas.querySelectorAll('[data-mp-node]').forEach(b=>b.onclick=()=>choose(b.dataset.mpNode));}
  else if(page==='Compare')canvas.innerHTML='<h2>Compare</h2><p>Comparison is for optical runs. A multiphysics run shows its physics side by side under Results, and Run Modes 1 alone adds the uncoupled n_eff.</p>';
  else{canvas.innerHTML=`<h2>${esc(doc.name||'Model')}</h2>`+geometrySvg();canvas.querySelectorAll('[data-mp-pick]').forEach(el=>{const pick=()=>choose('material:'+el.dataset.mpPick);el.onclick=pick;el.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();pick();}};});}
  if(maps.length){const draw=()=>maps.forEach(([,f])=>{try{f();}catch(e){}});resize=new ResizeObserver(draw);canvas.querySelectorAll('canvas').forEach(c=>resize.observe(c));draw();}
  for(const id of ['add-physics','add-coupling'])if($(id))$(id).hidden=false;
  for(const id of ['save-session','open-session']){const b=$(id);b.disabled=true;b.title='A multiphysics model is saved as its document: More › Save model file. Runs stay in this tab.';}
  $('save-project').textContent='Save model file';$('open-project').textContent='Open model file';
  renderDock();refreshRun();
 }
 function leave(){
  resize?.disconnect();resize=null;for(const id of ['add-physics','add-coupling','run-multiphysics','run-multiphysics-reason'])if($(id))$(id).hidden=true;
  const box=$('mp-messages');if(box){box.hidden=true;box.replaceChildren();}
  for(const id of ['save-session','open-session'])$(id).title=id==='save-session'?'Save inputs, completed runs and comparison to one file':'Open a saved session with its runs and comparison';
  $('save-project').textContent='Save inputs only';$('open-project').textContent='Open inputs file';
 }
 function saveFile(){
  const text=JSON.stringify(doc,null,2)+'\n',name=(String(doc.name||'model').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'')||'model')+'.json';
  const url=URL.createObjectURL(new Blob([text],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  savedSignature=signature();savedFile={name,kind:'Sent to model file',at:new Date()};ctx.onHistory();notice(`Model file ${name} sent to the browser's downloads. It holds the model; runs stay in this tab.`);
 }
 return {active:()=>active,open,openTemplate,close,leave,renderPage,undo,redo,canUndo:()=>active&&undoStack.length>0,canRedo:()=>active&&redoStack.length>0,
  addPhysics:()=>physicsDialog(),addCoupling:()=>couplingDialog(),run:()=>run(),stop,saveFile,busy:()=>!!job,
  title:()=>`${isMultiphysics(doc)?'Multiphysics model':'Model'} / ${!savedFile?'Not saved to a file · runs stay in this tab':savedSignature===signature()?`${savedFile.kind} ${savedFile.name}${savedFile.at?' · '+savedFile.at.toLocaleTimeString():''}`:`Changed since ${savedFile.kind.toLowerCase()} ${savedFile.name}`}`,
  // for checks: the current document and the last result
  document:()=>clone(doc),lastResult:()=>lastRun?.result||null};
}
