// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

// The multiphysics model's views (contract D2): the model tree, Settings, the Connections view
// drawn from the document's couplings, Messages from the live check, the run with progress per
// physics and loop, and Results per physics with the coupling check. The model is its document
// (workspace-multiphysics.mjs); the server checks and runs it (/api/multiphysics/*).
import {markPageTabs} from './workspace-tabs.mjs';
import {POLARIZATION_HELP,SOURCE_TEXT,modeTableRows,physicsModes} from './workspace-modes.mjs';
import {treeOpen,groupHeading,itemAttributes,treeState,bindTree,treeFocus,restoreTreeFocus} from './workspace-tree.mjs';
import {ENVELOPE,SIDES,PHYSMAT_THERMO_OPTIC,kindCatalog,physicsLabel,physicsNames,couplingNames,couplingTitle,splitSpec,portLabel,quantityWords,unitText,locationWords,
 normalizeEnvelope,isMultiphysics,addPhysics,removePhysics,sourceChoicesFor,targetChoices,transferNote,addCoupling,removeCoupling,suggestedCouplings,suggestionText,
 acceptLoop,removeLoop,loopText,loopIndexOf,materialUses,materialLabel,modesTemperatureCoupled,anyTemperatureCoupled,physmatFor,fillThermoOptic,usePhysmat,fillText,geometryOf,lengthsNote,
 mapDiagnostics,problemCounts,runBlockText,connectionLayout,renderMultiphysicsGraph,wireEnds,progressRows,failureText,formatValue,couplingCheckRows,effectiveIndexRows,resultPages,uncoupledDocument,
 runFreshness,freshnessAgain,editNotice,staleRows,originRows,sequenceHeading,readyStatus,RANKING_CAVEAT,modeCountText,baselineReturnText,baselineKey,baselinePhysics,baselineOptionState,shiftText,baselineText,unsourcedInputs,canonicalJson} from './workspace-multiphysics.mjs';
import {curvePath,loopPath} from './workspace-graph.mjs';
import {persistenceTitle,persistenceHint,sessionFileName} from './workspace-persistence.mjs';
import {appendMultiphysicsRun,nextRunNumber,multiphysicsRunName,meshCounts,writeMultiphysicsSession,recoveryText,overflowQuestion,savedNotice,modelSlug,
 MULTIPHYSICS_RUN_LIMIT,MAPS_NOT_KEPT,VIEW_PAGES,readMultiphysicsView} from './workspace-multiphysics-session.mjs';

const clone=x=>JSON.parse(JSON.stringify(x));
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const FILLS={'physmat:Si':'#6d9fe0','physmat:SiO2':'#dde7f1'};const OTHER_FILLS=['#a66a28','#7c9a5a','#9a6a9e','#c9a64a'];
const HEAT_TYPES={insulated:'Insulated',temperature:'Fixed temperature',flux:'Inward heat flux',convection:'Convection'};
const MARK={model:'◇',geometry:'◇',materials:'▱',mesh:'▦',physics:'∿',coupling:'⇄',study:'▷',order:'≡',loop:'↻',results:'▤'};
// the tree marks of the physics types, as the single-physics applications draw them
const TYPE_MARK={'thermal.steady2d':'∿','em.modes2d':'λ','electric.steady2d':'ϟ','mechanics.thermoelastic2d':'↔'};
// a quantity string "1550 nm" -> {number, unit}; a bare number has unit ''
function parseQuantity(value){if(typeof value==='number')return {number:value,unit:''};const m=/^\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)\s*(.*)$/.exec(String(value??''));return m?{number:Number(m[1]),unit:m[2].trim()}:null;}

// ctx: {$, notice(text, more), announceResult(text), request(method, url, body), render(), ui,
// applications(host), onHistory()}
export function createMultiphysicsView(ctx){
 const {$,notice}=ctx;
 let active=false,doc=null,caps=null,catalog={types:new Map(),providers:[]},capsError=null;
 let check={pending:false,diagnostics:[],solve_order:[],run_refusal:null,error:null},messages=[],checkSeq=0,checkTimer=null;
 const treeView=treeState();
 let selection='model',undoStack=[],redoStack=[],announcedMultiphysics=false;
 // runs: up to six completed runs (names, pins); lastRun: the one shown under Results
 let job=null,runs=[],lastRun=null,runFailure=null,uncoupled={},resultPage=null,indexView='n',resize=null;
 // What a session file and the save indicator know (the optical words, persistenceTitle):
 // sessionFile {name, savedAt, stamp, jobs}: the last session file sent or opened; loaded {kind,
 // name, stamp}: the file or recovery opened, until the next change; openedSignature: the model
 // as opened (edited since then means browser recovery keeps it); cleanSignature: the model as
 // last written to a file (Save inputs only or Save session).
 // sourceFile: the session file this model was opened from (or a recovered record names), by name
 let sessionFile=null,loaded=null,openedSignature=null,cleanSignature=null,sourceFile=null;
 // freshSignature: the model a template card gave, until it is edited, saved or run ("New model ·
 // not saved"); openedStamp: the content when it was opened from sourceFile, or recovered from a
 // record that still matched it (whether the recovery record still matches that file)
 let freshSignature=null,openedStamp=null;
 // card: the Library card this model came from ('heated-waveguide' for the template, else null),
 // which a project file names; a model in the project stays while another model is shown (P3)
 let card=null;
 // the heater-off comparison solved after each coupled run (on for a model with a coupled
 // temperature when it opens), the physics still to solve alone, and the last coupling removed
 let baselineOption=false,baselineQueue=[],baselineErrors={},lastRemoval=null,starting=false,stopAsked=false;
 const signature=()=>JSON.stringify(doc);
 // ---- model lifecycle ----
 async function loadCapabilities(){try{caps=await ctx.request('GET','/api/multiphysics/capabilities');catalog=kindCatalog(caps);capsError=null;}catch(e){capsError=e.message;}}
 // note: {text, more} added to the opening notice (where the previous model's runs are): text
 // on the line, more behind More
 async function open(tree,label,{fromFile=false,note=null}={}){
  if(!caps)await loadCapabilities();
  active=true;ctx.onOpen?.();doc=clone(tree);undoStack=[];redoStack=[];selection='model';runs=[];lastRun=null;runFailure=null;uncoupled={};resultPage=null;announcedMultiphysics=isMultiphysics(doc);
  baselineOption=baselinePhysics(doc).length>0;baselineQueue=[];baselineErrors={};lastRemoval=null;indexView='n';
  ctx.ui.page='Model';openedSignature=signature();cleanSignature=fromFile?signature():null;sessionFile=null;sourceFile=fromFile?label:null;loaded=fromFile?{kind:'opened',name:label,stamp:stamp()}:null;freshSignature=fromFile?null:signature();openedStamp=null;
  card=fromFile?null:'heated-waveguide';
  ctx.onHistory();validate(true);ctx.render();notice((fromFile==='session'?`Opened model file ${label}: it holds the model but no runs.`:`${label||doc.name||'Model'} ready. Edit settings and couplings, then press Run.`)+(note?.text?' '+note.text:''),note?.more||'');
 }
 // A session file of version 8 (or browser recovery), already checked (§3): the model, its runs,
 // the without-heater results and the view. Nothing is run, a without-heater run included.
 // source: 'file' | 'browser'; savedFile: the session file a recovered record was saved to.
 // openedFile: the file a recovered record was opened from, which the recovery lists name.
 // openedCurrent: whether the recovered record still matched openedFile (null when it does not say).
 async function openSession(session,{label,source='file',savedFile=null,openedFile=null,openedCurrent=null,card:from=null}){
  if(!caps)await loadCapabilities();
  active=true;ctx.onOpen?.();doc=structuredClone(session.document);undoStack=[];redoStack=[];runFailure=null;lastRemoval=null;baselineQueue=[];baselineErrors={};stopAsked=false;
  card=from;runs=session.runs.map(r=>({...r}));lastRun=runs.find(r=>r.job===session.selected)||null;announcedMultiphysics=isMultiphysics(doc);
  uncoupled={};for(const [name,b] of Object.entries(session.baselines))uncoupled[name]={rows:effectiveIndexRows(b.result),key:canonicalJson(b.document),completedAt:b.completedAt,job:b.job,document:b.document,result:b.result};
  const v=session.view;selection=v.selection;indexView=v.index_map==='change'?'dn':'n';baselineOption=v.baseline_option;resultPage=selection.startsWith('results:')?selection:null;
  // a record that still matched the file it was opened from reads as that file, as an optical one does
  const openedMatch=source!=='file'&&!savedFile&&!!openedFile&&openedCurrent===true;
  openedSignature=signature();const matched=source==='file'||savedFile?.current===true||openedMatch;cleanSignature=matched?signature():null;sourceFile=source==='file'?label:openedFile;freshSignature=null;
  sessionFile=source==='file'||openedMatch?{name:source==='file'?label:openedFile,savedAt:null,stamp:null,jobs:filed(),opened:true}:savedFile?{name:savedFile.name,savedAt:savedFile.savedAt,stamp:null,jobs:matched?filed():new Map(),...(savedFile.projectName?{projectName:savedFile.projectName}:{})}:null;
  ctx.ui.page=v.page==='Results'&&!lastRun?'Model':v.page;validate(true);ctx.onHistory();
  loaded={kind:source==='file'?'opened':'recovered',name:source==='file'?label:null,stamp:stamp(),file:sourceFile,fileCurrent:source==='file'||openedMatch};if(sessionFile&&matched)sessionFile.stamp=loaded.stamp;
  openedStamp=source==='file'||openedMatch?loaded.stamp:null;
  ctx.onHistory();ctx.render();
  notice(source==='file'?`Opened ${label}. Its results were read from the file, not recomputed; input undo starts here.`:`Recovered from this browser (${label}), not recomputed. `+(savedFile?`Last session file ${savedFile.name}${matched?'':'; changed since'}. Input undo starts here.`:'File › Save keeps it in a file; input undo starts here.'));
 }
 // A file is read by the server's reader first: a duplicate key or text that is not JSON is
 // refused with the reader's words, never resolved silently by the browser's JSON.parse.
 async function openText(text,name,{asSession=false}={}){
  const reply=await ctx.requestRaw('/api/multiphysics/validate','{"doc":'+text+'}');
  const unreadable=(reply.diagnostics||[]).filter(d=>d.code==='E-JSON'||d.code==='E-KEY-DUPLICATE');
  if(reply.detail||unreadable.length)throw new Error(reply.detail||unreadable.map(d=>`${d.path?d.path+': ':''}${d.message}`).join('; '));
  await open(JSON.parse(text),name,{fromFile:asSession?'session':true});
 }
 async function openTemplate({note=null}={}){try{const tree=await ctx.request('GET','/api/multiphysics/template');await open(tree,'Heated silicon waveguide',{note});}catch(e){notice('The multiphysics template could not be loaded: '+e.message);}}
 function close(){active=false;stopPolling();}
 // A model of the project shown again (its Library card, P3): its document, runs, without-heater
 // results and its own Undo are as they were left.
 function show(){
  if(!doc)return;active=true;ctx.onOpen?.();ctx.ui.page='Model';validate(true);ctx.onHistory();ctx.render();
  notice(`${doc.name||'Model'} shown with ${runs.length===0?'no runs':runs.length===1?'its run':`its ${runs.length} runs`}; nothing was computed.`);
 }
 // The model leaves the project (a file replaced the project): nothing of it stays in the tab.
 function discard(){
  active=false;stopPolling();doc=null;runs=[];lastRun=null;runFailure=null;uncoupled={};undoStack=[];redoStack=[];resultPage=null;
  sessionFile=null;loaded=null;openedSignature=null;cleanSignature=null;sourceFile=null;freshSignature=null;openedStamp=null;card=null;baselineQueue=[];baselineErrors={};lastRemoval=null;
 }
 function commit(next,message,select){
  undoStack.push(doc);if(undoStack.length>100)undoStack.shift();redoStack=[];
  const before=isMultiphysics(doc),prior=doc;doc=normalizeEnvelope(next);if(select)selection=select;lastRemoval=null;
  validate();ctx.onHistory();ctx.render();
  let text=editNotice(message,freshness(),lastRun?.number,lastRun?.label||'');
  if(!before&&isMultiphysics(doc)&&!announcedMultiphysics){announcedMultiphysics=true;text+=' This model is now saved as a multiphysics model (format 0.3/multiphysics.1).';}
  notice(text+baselineReturnText(prior,doc,baselineOption),'',againAction());
 }
 // The model equals the last run again: Messages offers that run (round 13, O6).
 function againAction(){
  if(freshness()!=='again'||!lastRun)return null;const run=lastRun;
  return {label:`Show Run ${run.number}`,data:{showRun:String(run.number)},run:()=>showRun(run)};
 }
 // A run under Results, as a click in the run list shows it; the model is unchanged.
 function showRun(run){
  if(!runs.includes(run))return;lastRun=run;
  resultPage=resultPages(run.result).find(p=>p.id.startsWith('results:')&&run.result.physics[p.id.slice(8)]?.coupled)?.id||resultPages(run.result)[0].id;
  selection=resultPage;ctx.ui.page='Results';ctx.onHistory();ctx.render();notice(`${runTitle(run)} shown under Results; the model is unchanged.`);
 }
 // Undo and Redo compute nothing; back at the last run's model they say its results are current.
 const historyNotice=(done,prior)=>{const f=freshness();notice((f==='again'?`${done} · ${editNotice('',f,lastRun.number,lastRun.label||'').trim()}`:`${done}; nothing was computed.`)+baselineReturnText(prior,doc,baselineOption),'',againAction());};
 function undo(){if(!undoStack.length)return;lastRemoval=null;const prior=doc;redoStack.push(doc);doc=undoStack.pop();validate();ctx.onHistory();ctx.render();selection=storedSelection();historyNotice('Undo · model edit undone',prior);}
 function redo(){if(!redoStack.length)return;lastRemoval=null;const prior=doc;undoStack.push(doc);doc=redoStack.pop();validate();ctx.onHistory();ctx.render();selection=storedSelection();historyNotice('Redo · model edit redone',prior);}
 // A removed coupling is named in Messages with Undo until the next edit.
 function removeCouplingNamed(name){const title=couplingTitle(doc,name);commit(removeCoupling(doc,name),`Coupling ${title} removed. Undo restores it.`,'model');lastRemoval={title};ctx.render();}
 // ---- the live check ----
 function validate(now=false){
  // the sequence moves now, so a reply for an earlier document is dropped even if it arrives
  // before this check is sent; until the new reply, the fixes of the old messages are disabled
  clearTimeout(checkTimer);check.pending=true;const seq=++checkSeq;refreshRun();
  const go=async()=>{if(seq!==checkSeq)return;const sent=clone(doc),sentSignature=JSON.stringify(sent);
   let next;
   try{const reply=await ctx.request('POST','/api/multiphysics/validate',{doc:sent});next={pending:false,error:null,...reply};}
   catch(e){next={pending:false,diagnostics:[],solve_order:check.solve_order,run_refusal:null,error:e.message};}
   if(seq!==checkSeq||sentSignature!==signature())return;
   check=next;messages=mapDiagnostics(doc,catalog,check.diagnostics);if(active)ctx.render();};
  if(now)go();else checkTimer=setTimeout(go,250);
 }
 const errors=()=>messages.filter(m=>m.severity==='error');
 function runBlock(){
  if(capsError)return 'Studio cannot list the installed physics: '+capsError;
  if(job||starting)return 'Running… (stop it under Study)';
  if(runs.length>=MULTIPHYSICS_RUN_LIMIT&&runs.every(r=>r.pinned))return 'All six runs are pinned. Unpin a run under Results › Runs before running again.';
  if(check.error)return 'The model could not be checked: '+check.error;
  if(check.pending)return 'Checking the model…';
  return runBlockText(errors().length,check.run_refusal);
 }
 // The state of the model against the last run; a run once edited away and back is 'again'.
 function freshness(){const f=runFreshness(lastRun,doc);if(f==='stale')lastRun.diverged=true;return freshnessAgain(f,!!lastRun?.diverged);}
 function refreshRun(){
  const button=$('run-multiphysics'),reason=$('run-multiphysics-reason');if(!button)return;
  button.hidden=!active;reason.hidden=!active;if(!active)return;
  const block=runBlock(),fresh=freshness();button.disabled=!!block;button.textContent=job?'Running… (stop it under Study)':'Run study';reason.textContent=job?'':block;
  $('status').textContent=job?(job.alone?`Solving ${physicsLabel(job.alone)} without heater`:'Multiphysics run in progress'):block?'Model not ready · '+block:readyStatus(fresh,lastRun?.number,lastRun?.origin,lastRun?.label||'');
  const heading=document.querySelector('.dock-title>span');if(heading)heading.textContent=sequenceHeading(fresh,lastRun?.number,lastRun?.origin,lastRun?.label||'');
  const option=$('run-baseline-option'),box=$('run-baseline');
  if(option){const o=baselineOptionState(doc,{on:baselineOption,busy:!!job});option.hidden=false;option.classList.toggle('unavailable',!o.available);box.checked=o.checked;box.disabled=o.disabled;option.title=o.title;}
 }
 // ---- running ----
 let pollTimer=null;function stopPolling(){clearTimeout(pollTimer);pollTimer=null;}
 async function run(source=doc,{alone=null,key=null}={}){
  if(job||starting||(!alone&&runBlock()))return;
  const sent=clone(source),order=alone?[[alone]]:check.solve_order;
  // busy from the request on, so nothing else starts or opens until the job is followed
  // the Run button shows it at once: a without-heater solve starts right after a coupled run, and
  // a Run pressed while its request is out would be ignored
  starting=true;if(!alone)stopAsked=false;refreshRun();
  try{const reply=await ctx.request('POST','/api/multiphysics/run',{doc:sent});starting=false;
   job={id:reply.job,doc:sent,order:reply.solve_order||order,events:[],status:'running',error:null,alone,key};if(!alone)runFailure=null;
   refreshRun();ctx.render();notice(alone?`Solving ${physicsLabel(alone)} without heater: alone, with no temperature input…`:'Running every physics in solve order…');poll();
  }catch(e){starting=false;if(alone){baselineErrors[alone]=e.message;baselineQueue=[];}refreshRun();ctx.render();notice('Run refused: '+e.message);}
 }
 async function poll(){
  if(!job)return;
  try{const s=await ctx.request('GET',`/api/multiphysics/jobs/${job.id}?after=${job.events.length}`);
   const moved=s.events.length>0;job.events.push(...s.events);job.status=s.status;job.error=s.error;job.misses=0;
   if(s.status==='running'){if(moved&&ctx.ui.page==='Connections')ctx.render();else renderDock();pollTimer=setTimeout(poll,300);return;}
   if(s.status==='done'){const result=await ctx.request('GET',`/api/multiphysics/jobs/${job.id}/result`);finish(result);return;}
   if(job.alone){const a=job;job=null;baselineQueue=[];baselineErrors[a.alone]=s.status==='stopped'?'stopped':failureText(s.error,a.doc);refreshRun();ctx.render();
    notice(s.status==='stopped'?`${physicsLabel(a.alone)} without heater stopped; the coupled run stays under Results.`:`${physicsLabel(a.alone)} without heater failed: ${baselineErrors[a.alone]} The coupled run stays under Results.`);return;}
   runFailure={events:job.events,order:job.order,status:s.status,error:s.error,doc:job.doc};const failed=job;job=null;refreshRun();ctx.render();
   notice(s.status==='stopped'?'Run stopped. No result was kept'+(lastRun?'; the previous complete run stays under Results.':'.'):failureText(s.error,failed.doc)+(lastRun?' The previous complete run stays under Results.':''));
  }catch(e){
   // a lost reply is retried with backoff, so Stop stays available; only a job the server no
   // longer has ends the follow-up
   if(job&&!/no such multiphysics job|has no result/.test(e.message)&&(job.misses=(job.misses||0)+1)<=8){notice(`Connection to the run lost (${e.message}); retrying…`);pollTimer=setTimeout(poll,Math.min(8000,500*2**job.misses));return;}
   if(job?.alone){baselineErrors[job.alone]=e.message;baselineQueue=[];job=null;refreshRun();ctx.render();notice('The run without heater could not be followed: '+e.message);return;}
   runFailure={events:job.events,order:job.order,status:'error',error:{message:e.message},doc:job.doc};job=null;refreshRun();ctx.render();notice('The run could not be followed: '+e.message);}
 }
 function finish(result){
  const done=job;job=null;
  if(done.alone){delete baselineErrors[done.alone];const part=result.physics[done.alone];uncoupled[done.alone]={rows:effectiveIndexRows(part),key:done.key,completedAt:new Date().toISOString(),job:done.id,document:done.doc,
    result:{type:part.type,effective_index:part.effective_index,vacuum_wavelength:part.vacuum_wavelength,summary:part.summary}};refreshRun();ctx.render();ctx.onHistory();
   if(!nextBaseline())ctx.announceResult(`${physicsLabel(done.alone)} without heater finished; its n_eff and Δn_eff are shown beside the coupled one.`);return;}
  const completed={job:done.id,number:nextRunNumber(runs),label:'',pinned:false,completedAt:new Date().toISOString(),serverVersion:ctx.serverVersion?.()??null,doc:done.doc,events:done.events,order:result.solve_order,result,maps:'kept',origin:'local'};
  try{runs=appendMultiphysicsRun(runs,completed);}catch(e){notice(e.message);refreshRun();ctx.render();return;}
  lastRun=completed;runFailure=null;
  resultPage=resultPages(result).find(p=>p.id.startsWith('results:')&&result.physics[p.id.slice(8)]?.coupled)?.id||resultPages(result)[0].id;
  selection=resultPage;ctx.ui.page='Results';
  // the heater-off comparison: solved only when no column of the same content is kept
  baselineQueue=baselineOption&&!stopAsked?baselinePhysics(lastRun.doc).filter(n=>uncoupled[n]?.key!==baselineKey(lastRun.doc,n)):[];
  refreshRun();ctx.render();ctx.onHistory();ctx.announceResult(`Run ${lastRun.number} complete. Its results belong to that run; editing the model does not change them.`+(baselineQueue.length?' Solving without heater…':''));
  nextBaseline();
 }
 // Starts the next heater-off solve of the last run; false when none is left.
 function nextBaseline(){const name=baselineQueue.shift();if(!name||!lastRun)return false;runAlone(name);return true;}
 function runAlone(name){return run(uncoupledDocument(lastRun.doc,name),{alone:name,key:baselineKey(lastRun.doc,name)});}
 async function stop(){if(!job)return;baselineQueue=[];stopAsked=true;const alone=job.alone;try{await ctx.request('POST',`/api/multiphysics/jobs/${job.id}/stop`);notice(alone?`Stopping ${physicsLabel(alone)} without heater; the coupled run stays under Results.`:'Stopping after the physics being solved finishes; no result will be kept.');}catch(e){notice('Stop failed: '+e.message);}}
 // ---- fixes ----
 function applyFix(fix){
  if(!fix)return;if(check.pending){notice('The model is being checked; try again when the check finishes.');return;}
  if(fix.action==='remove-coupling')removeCouplingNamed(fix.coupling);
  else if(fix.action==='use-same-mesh'){const next=clone(doc);next.couplings[fix.coupling].transfer='same_mesh';commit(next,'Transfer set to Same mesh.');}
  else if(fix.action==='remove-mesh-key'){const next=clone(doc);delete next.mesh[fix.key];commit(next,`Mesh ${quantityWords(fix.key)} removed; both physics use the same mesh.`,'mesh');}
  else if(fix.action==='accept-loop'){const {doc:next,index,already}=acceptLoop(doc,fix.proposal);if(already){selection='loop:'+index;ctx.render();return;}commit(next,`Iteration step ${index+1} accepted with the default settings; Undo reverts it.`,'loop:'+index);}
  else if(fix.action==='fill-physmat')commit(fillThermoOptic(doc,fix.material,fix.ref),`Thermo-optic data of ${fix.ref} copied into ${materialLabel(fix.material)}; the source notes it.`);
 }
 const messageHtml=(m,i,show=true)=>`<div class="mp-message ${m.severity}" data-mp-message="${i}"><p>${esc(m.text)}</p><div class="mp-message-actions">${show?`<button type="button" data-mp-show="${i}">Show</button>`:''}${m.fix?`<button type="button" data-mp-fix="${i}" ${check.pending?'disabled':''}>${esc(m.fix.label)}</button>`:''}<details><summary>Details</summary><code>${esc(m.code)}</code> at <code>${esc(m.path||'document')}</code>: ${esc(m.detail)}</details></div></div>`;
 function bindMessages(host){
  host.querySelectorAll('[data-mp-fix]').forEach(b=>b.onclick=()=>applyFix(messages[+b.dataset.mpFix].fix));
  host.querySelectorAll('[data-mp-show]').forEach(b=>b.onclick=()=>{selection=messages[+b.dataset.mpShow].node;if(ctx.ui.page!=='Connections')ctx.ui.page='Model';ctx.render();$('inspector').querySelector('.mp-message')?.scrollIntoView({block:'nearest'});});
 }
 // ---- the tree ----
 // drawn again with the focus kept on its item (a group opened or closed, a node chosen)
 function drawTree(){const host=$('tree'),had=treeFocus(host,treeView);host.innerHTML=tree();host.querySelectorAll('[data-mp-node]').forEach(b=>b.onclick=()=>choose(b.dataset.mpNode));bindTree(host,treeView,drawTree);restoreTreeFocus(host,treeView,had);}
 function tree(){
  const counts=problemCounts(messages),order=check.solve_order||[],badge=name=>{const i=order.findIndex(g=>g.includes(name));return i<0?'':`<span class="order-badge${order[i].length>1?' cycle':''}" aria-label="solve order ${i+1}">${i+1}</span>`;};
  const count=id=>counts[id]?`<span class="problem-badge" aria-label="${counts[id]} problem${counts[id]===1?'':'s'}">${counts[id]}</span>`:'';
  // an ARIA tree (workspace-tree.mjs): a node is selected while its page or settings are shown; on
  // Results the results page shown, on Compare none
  const page=ctx.ui.page,shown=id=>page==='Compare'||page==='Applications'?false:page==='Results'?id.startsWith('results:')&&id===resultPage:!id.startsWith('results:')&&selection===id;
  const item=(id,label,mark,extra='',indent=false,level=indent?3:2)=>`<button type="button" data-mp-node="${esc(id)}" ${itemAttributes(level,shown(id))} class="${indent?'tree-child':''}"><span class="tree-node-mark" aria-hidden="true">${mark}</span>${extra}${esc(label)}${count(id)}</button>`;
  const group=name=>groupHeading(name,!treeView.collapsed.has(name));
  const multi=isMultiphysics(doc)||couplingNames(doc).length>0;
  const warned=new Map(unsourcedInputs(doc,catalog).map(w=>[w.physics,w.text]));
  // the badge names the physics and the problem, as Messages does ("Modes 1: Temperature input has no
  // source: …"), as its title and, as an image, its accessible name (a plain span's aria-label is not one)
  const warn=n=>{if(!warned.has(n))return '';const words=esc(`${physicsLabel(n)}: ${warned.get(n)}`);return `<span class="warn-badge" role="img" title="${words}" aria-label="${words}">!</span>`;};
  const physics=physicsNames(doc).map(n=>item('physics:'+n,`${physicsLabel(n)} · ${catalog.types.get(doc.physics[n].type)?.label||doc.physics[n].type}`,TYPE_MARK[doc.physics[n].type]||MARK.physics,multi?badge(n):'').replace(/<\/button>$/,warn(n)+'</button>')).join('');
  const couplings=couplingNames(doc).map(c=>item('coupling:'+c,couplingTitle(doc,c),MARK.coupling)).join('')||`<div role="treeitem" aria-level="2" aria-disabled="true" tabindex="-1" class="muted tree-empty">No couplings</div>`;
  const loops=(Array.isArray(doc.study?.loops)?doc.study.loops:[]).map((l,i)=>item('loop:'+i,`Iteration step ${i+1} · ${(l.physics||[]).map(physicsLabel).join(' ⇄ ')}`,MARK.loop,'',true)).join('');
  const materials=materialUses(doc).map(u=>item('material:'+u.ref,u.label,'·','',true)).join('');
  const results=lastRun?[{id:'results:runs',label:`Runs · ${runs.length} of ${MULTIPHYSICS_RUN_LIMIT}`},...resultPages(lastRun.result)].map(p=>item(p.id,p.label,MARK.results,'',true,2)).join(''):'';
  return `<div class="pane-title"><span>Model builder</span><span class="pane-detail">${multi?'Multiphysics model':'Model 1'}</span></div>${treeOpen()}<div class="model-root" role="none"><button type="button" data-mp-node="model" ${itemAttributes(1,shown('model'))}><span aria-hidden="true">▾ ◇</span><strong>${esc(doc.name||'Untitled model')}</strong></button></div>`+
   `<section class="tree-group" role="none">${group('Component 1')}${item('geometry','Geometry 1',MARK.geometry,'',false)}${item('materials','Materials',MARK.materials)}${materials}${item('mesh',multi?'Mesh 1 · shared':'Mesh 1',MARK.mesh)}</section>`+
   `<section class="tree-group" role="none">${group('Physics')}${physics}</section>`+
   (multi?`<section class="tree-group" role="none">${group('Couplings')}${couplings}</section>`:'')+
   `<section class="tree-group" role="none">${group('Study')}${item('study','Study 1',MARK.study)}${multi?item('order','Solve order (from couplings)',MARK.order,'',true):''}${loops}</section>`+
   (results?`<section class="tree-group" role="none">${groupHeading('Results',!treeView.collapsed.has('Results'),`Results · run ${lastRun.number}`)}${results}</section>`:'')+`</div>`+
   `<div class="capability-card"><span class="capability-dot" aria-hidden="true"></span><strong>Solver available</strong><p>${multi?'Multiphysics model · one Run solves every physics in order':physicsNames(doc).length>1?`${physicsNames(doc).length} physics · no couplings · format 0.3`:'One physics · format 0.3'}</p></div>`;
 }
 // ---- fields ----
 const getPath=path=>path.reduce((o,k)=>o?.[k],doc);
 function setPath(path,value,message){const next=clone(doc);let o=next;for(const k of path.slice(0,-1)){if(o[k]===undefined||o[k]===null)o[k]={};o=o[k];}if(value===undefined)delete o[path.at(-1)];else o[path.at(-1)]=value;commit(next,message);}
 // a quantity field: a number in the expected unit, or the text as written when another unit
 function qfield(path,label,unit,{required=false,invalid=false,attrs=''}={}){
  const value=getPath(path),q=value===undefined?null:parseQuantity(value),id=esc('mp-f-'+path.join('-'));
  if(value!==undefined&&(!q||q.unit!==unit))return `<label for="${id}">${esc(label)}<input id="${id}" type="text" data-mp-text="${esc(JSON.stringify(path))}" value="${esc(value)}" aria-invalid="${invalid}"></label>`;
  return `<label for="${id}">${esc(label)} [${esc(unitText(unit))}]<input id="${id}" type="number" step="any" ${attrs} data-mp-quantity="${esc(JSON.stringify(path))}" data-unit="${esc(unit)}" value="${q?q.number:''}" ${required&&value===undefined?'placeholder="needed"':''} aria-invalid="${invalid}"></label>`;
 }
 function nfield(path,label,attrs=''){const id=esc('mp-f-'+path.join('-'));return `<label for="${id}">${esc(label)}<input id="${id}" type="number" step="any" ${attrs} data-mp-number="${esc(JSON.stringify(path))}" value="${esc(getPath(path)??'')}"></label>`;}
 function sfield(path,label,options,current){return `<label>${esc(label)}<select data-mp-select-field="${esc(JSON.stringify(path))}">${Object.entries(options).map(([k,v])=>`<option value="${esc(k)}" ${k===current?'selected':''}>${esc(v)}</option>`).join('')}</select></label>`;}
 const pair=(a,b)=>`<div class="pair"><span>${esc(a)}</span><strong>${esc(b)}</strong></div>`;
 // The names the model file uses (type, name in file, format, input arity): shown, but closed by default.
 const fileDetails=rows=>`<details class="mp-file-details"><summary>File details</summary>${rows.map(([a,b])=>pair(a,b)).join('')}</details>`;
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
  let html=pair('Physics',info?.label||p.type)+(place>=0&&couplingNames(doc).length?pair('Solve order',`${place+1} of ${order.length} (from the couplings)`):'')+fileDetails([['Type',p.type],['Name in file',name]]);
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
   else{const w=unsourcedInputs(doc,catalog).find(x=>x.physics===name);html+=w?`<p class="validation-warning mp-warn-text" data-mp-warning="${esc(name)}">${esc(w.text)}. The modes are solved with each material's n₀; a coupling from a heat physics gives n(T).</p>`:'<p>Not coupled: every material keeps its index n₀.</p>';for(const s of suggestedCouplings(doc,catalog).filter(s=>s.to===`${name}.temperature`))html+=`<p class="mp-suggestion">${esc(suggestionText(s))}</p><button type="button" data-mp-add-coupling="${esc(s.from)}|${esc(s.to)}">Add coupling…</button>`;}
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
  if(history)html+=`<h3>Change per iteration · ${lastRun&&!runFailure?'run '+lastRun.number:'last run'}</h3>`+residualChart(history,tol?.number);
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
  if(kind==='model'){title='Model';html=`<label>Name<input type="text" data-mp-text="${esc(JSON.stringify(['name']))}" value="${esc(doc.name||'')}"></label>`+pair('Physics',physicsNames(doc).map(physicsLabel).join(', ')||'none')+pair('Couplings',String(couplingNames(doc).length))+fileDetails([['Format',isMultiphysics(doc)?`Multiphysics model · ${ENVELOPE}`:'One physics · 0.3']])+'<p><button type="button" data-mp-dialog="physics">Add physics…</button> <button type="button" data-mp-dialog="coupling">Add coupling…</button></p><p>File › Save keeps this model with its runs in one session file; File › Export › Model file writes the model alone.</p>';}
  else if(kind==='geometry'){title='Geometry 1';const g=geometryOf(doc),u=unitText(g?.length_unit||'');const gpath=doc.geometry?.version===1?['geometry','components',Object.keys(doc.geometry.components)[0]]:['geometry'];
   html=pair('Length unit',u)+['xmin','xmax','ymin','ymax'].map(k=>nfield([...gpath,'domain',k],`Domain ${k} [${u}]`)).join('')+'<h3>Shapes (later shapes win where they overlap)</h3>'+(g?.features||[]).map((f,i)=>`<fieldset class="heat-side"><legend>${esc(f.name)} · ${esc(f.type)} · ${esc(materialLabel(f.material))}</legend>${f.type==='rect'?['x','y','w','h'].map(k=>nfield([...gpath,'features',i,k],`${k} [${u}]`)).join(''):'<p class="muted">Edited in the file.</p>'}</fieldset>`).join('')+'<p>Every physics uses this geometry and one shared mesh.</p>';}
  else if(kind==='materials'){title='Materials';html=materialUses(doc).map(u=>`<p>${link('material:'+u.ref,u.label)} · ${esc(u.local?'document record':u.ref)}</p>`).join('')+(anyTemperatureCoupled(doc)?'<p>A coupled temperature needs a thermo-optic coefficient and a reference temperature for every optical material.</p>':'');}
  else if(kind==='material'){title=materialLabel(id,materialUses(doc).find(u=>u.ref===id)?.regions||[]);html=materialPanel(id);}
  else if(kind==='mesh'){title=isMultiphysics(doc)?'Mesh 1 · shared':'Mesh 1';const modes=physicsNames(doc).find(n=>doc.physics[n].type==='em.modes2d'),heat=physicsNames(doc).find(n=>doc.physics[n].type==='thermal.steady2d');
   html=qfield(['mesh','element_size'],'Element size','um',{attrs:'min="0"'})+pair('Refinement',(doc.mesh?.controls||[]).map(c=>`${c.select}: ${c.near??c.element_size} near, ${c.far??''} far within ${c.refinement_distance??''}`).join('; ')||'none');
   if(modes&&heat&&doc.mesh?.grading===undefined)html+=pair('Grading toward the core',`not available: ${physicsLabel(heat)} does not read it`);
   html+='<p>Every physics solves on this one mesh, so coupled values move without interpolation.</p>';}
  else if(kind==='physics'){title=doc.physics[id]?physicsLabel(id):id;html=doc.physics[id]?physicsPanel(id):'<p>This physics is not in the model.</p>';}
  else if(kind==='coupling'){const c=doc.couplings?.[id];title=c?couplingTitle(doc,id):id;if(c){const inp=catalog.types.get(doc.physics[splitSpec(c.to)[0]]?.type)?.ports.find(p=>p.name===splitSpec(c.to)[1]);
   html=pair('From',portLabel(c.from))+pair('To',portLabel(c.to))+pair('Transfer',c.transfer==='same_mesh'?'Same mesh (both use Mesh 1)':String(c.transfer))+pair('Values',transferNote(doc,catalog,c.from,c.to).split(' · ').slice(1).join(' · ')||'—')+fileDetails([...(inp?[['Input takes',(inp.combine||'single')==='single'?'one source':'sources add']]:[]),['Name in file',id]])+`<p><button type="button" data-mp-remove-coupling="${esc(id)}">Remove coupling</button></p>`;}}
  else if(kind==='study'){title='Study 1';const sweep=doc.study?.type==='sweep';html=pair('Study',sweep?'Sweep':'Single run')+(sweep?`<p class="validation-warning">${esc(check.run_refusal||'')}</p><button type="button" data-mp-single>Use single run</button>`:'')+'<h3>Solve order (from the couplings)</h3>'+orderList()+((doc.study?.loops||[]).length?'<h3>Iteration steps</h3>'+doc.study.loops.map((l,i)=>`<p>${link('loop:'+i,`Iteration step ${i+1} · ${(l.physics||[]).map(physicsLabel).join(' ⇄ ')}`)} · ${esc(loopText(l))}</p>`).join(''):'');}
  else if(kind==='order'){title='Solve order';html=orderList()+'<p>The order is derived from the couplings, not stored. To change it, change the couplings.</p>';}
  else if(kind==='loop'){title=`Iteration step ${+id+1}`;html=loopPanel(+id);}
  else if(kind==='results'){title='Results';html=lastRun?pair('Run',runTitle(lastRun))+pair('Completed',new Date(lastRun.completedAt).toLocaleTimeString())+pair('Inputs',JSON.stringify(lastRun.doc)===signature()?'Same as the current model':'The model changed since this run')+'<p>A result belongs to its run; editing the model does not change it.</p>':'<p>No run yet.</p>';}
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
  host.querySelectorAll('[data-mp-remove-coupling]').forEach(b=>b.onclick=()=>removeCouplingNamed(b.dataset.mpRemoveCoupling));
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
  // opened for one input: its From list holds only the outputs that input can take
  const sources=sourceChoicesFor(doc,catalog,to);if(from&&!sources.some(s=>s.spec===from))from=null;from=from||sources.find(s=>s.ok)?.spec;
  if(!from){notice(to?`No output of this model can feed ${physicsLabel(splitSpec(to)[0])} ${quantityWords(splitSpec(to)[1])}.`:'No physics of this model sends a field to couplings yet. Add physics first.');return;}
  const d=dialog('Add coupling','<div id="mp-coupling-body"></div>','<button type="button" id="mp-coupling-add" class="primary">Add coupling</button>');
  const draw=()=>{const targets=targetChoices(doc,catalog,from);if(!to||!targets.find(t=>t.spec===to&&t.ok))to=targets.find(t=>t.ok)?.spec||null;
   d.querySelector('#mp-coupling-body').innerHTML=`<label>From (outputs)<select id="mp-from">${sources.map(s=>`<option value="${esc(s.spec)}" ${s.spec===from?'selected':''} ${s.ok?'':`disabled title="${esc(s.detail)}"`}>${esc(s.label)}${s.ok?' · '+esc(unitText(s.port.unit)):` (${esc(s.reason)})`}</option>`).join('')}</select></label>
    <label>To (inputs)<select id="mp-to">${targets.map(t=>`<option value="${esc(t.spec)}" ${t.spec===to?'selected':''} ${t.ok?'':'disabled'}>${esc(t.label)} · ${esc(unitText(t.port.unit))}${t.ok?'':' — '+esc(t.reason)}</option>`).join('')}</select></label>
    <ul class="mp-choice-reasons">${targets.filter(t=>!t.ok).map(t=>`<li>${esc(t.label)}: ${esc(t.reason)}</li>`).join('')}</ul>
    ${pair('Transfer',transferNote(doc,catalog,from,to||from).split(' · ')[0])}${to?`<p>${esc(transferNote(doc,catalog,from,to).split(' · ').slice(1).join(' · '))}.</p>`:'<p class="muted">No input can take this output.</p>'}`;
   d.querySelector('#mp-from').onchange=e=>{from=e.target.value;draw();};d.querySelector('#mp-to').onchange=e=>{to=e.target.value;draw();};d.querySelector('#mp-coupling-add').disabled=!to;};
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
  return `<svg data-geometry-view="multiphysics" viewBox="0 0 600 350" role="group" aria-label="Geometry 1: ${esc(doc.name||'model')}"><rect x="${X(D.xmin)}" y="${Y(D.ymax)}" width="${w*s}" height="${h*s}" fill="${fill(g.background?.material)}" stroke="#7a939f" data-mp-pick="${esc(g.background?.material)}" role="button" tabindex="0" aria-label="background: ${esc(materialLabel(g.background?.material||''))}"/>${shapes}${labels}<text x="300" y="16" text-anchor="middle" font-size="11" fill="#34445b">${esc(w)} × ${esc(h)} ${esc(unitText(g.length_unit))} · shared by ${esc(physicsNames(doc).map(physicsLabel).join(' and '))}</text></svg>`;
 }
 function connections(){
  const layout=connectionLayout(doc,catalog,check.solve_order,messages),states={};
  if(job||runFailure||lastRun){for(const r of sequenceRows())if(!/ without heater$/.test(r.label))for(const n of r.group)states[n]={state:r.state,text:r.text};}
  const relevant=messages.map((m,i)=>[m,i]).filter(([m])=>m.node.startsWith('coupling:')||m.code==='E-COUPLING-CYCLE'||m.node.startsWith('physics:'));
  const loopRow=job&&!job.alone?progressRows(job.order,job.doc,job.events,'running').find(r=>r.residuals.length):null;
  return `<div class="graph-heading"><h2>Physics connections</h2><span class="setup-badge solved">${couplingNames(doc).length?'Drawn from the couplings':'No couplings yet'}</span></div><p class="graph-intro">Badges give the solve order. Select a node or wire to open it in Settings. <button type="button" data-mp-action="add-coupling">Add coupling…</button></p>${renderMultiphysicsGraph(layout,selection,states)}${relevant.length?`<section class="mp-graph-messages" aria-label="Coupling problems">${relevant.map(([m,i])=>messageHtml(m,i)).join('')}</section>`:''}${loopRow?`<h3>${esc(loopRow.label)} · change per iteration</h3>`+residualChart(loopRow.residuals,parseQuantity(job.doc.study.loops[loopRow.loop]?.tolerance?.value)?.number):''}`;
 }
 function installGraph(host){
  const stage=host.querySelector('.mp-stage');if(!stage)return;
  const svg=stage.querySelector('.graph-wires'),edges=JSON.parse(stage.dataset.edges);
  const draw=()=>{if(!stage.isConnected)return;const b=stage.getBoundingClientRect();svg.setAttribute('viewBox',`0 0 ${b.width} ${b.height}`);
   const point=id=>{const el=stage.querySelector(`[data-port="${CSS.escape(id)}"] .port-dot`);if(!el)return null;const r=el.getBoundingClientRect();return {x:r.x+r.width/2-b.x,y:r.y+r.height/2-b.y};};
   const channel=Math.max(0,...[...stage.querySelectorAll('.graph-node')].map(n=>n.getBoundingClientRect().bottom-b.y))+18;
   const ends=wireEnds(edges,point);
   svg.replaceChildren(...edges.map(([,,color,label,route,coupling],i)=>{const g=document.createElementNS('http://www.w3.org/2000/svg','g');if(!ends[i])return g;const {from:a,to:c}=ends[i];
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
  if(!lastRun){host.innerHTML=`<h2>No result in this tab</h2><p>Press Run to solve every physics in solve order. File › Save keeps the model and its runs in one file.</p>${runFailure?`<p class="validation-warning">${esc(runFailure.status==='stopped'?'The last run was stopped; no result was kept.':failureText(runFailure.error,runFailure.doc))}</p>`:''}`;return [];}
  const r=lastRun.result,pages=[{id:'results:runs',label:'Runs'},...resultPages(r)];if(!pages.find(p=>p.id===resultPage))resultPage=pages[1].id;
  const same=JSON.stringify(lastRun.doc)===signature(),kept=lastRun.maps!=='not kept',counts=kept?meshCounts(r):lastRun.counts;
  host.innerHTML=`<div class="toolbar mp-result-tabs" role="tablist">${pages.map(p=>`<button role="tab" data-mp-node="${esc(p.id)}" aria-selected="${p.id===resultPage}">${esc(p.label)}</button>`).join('')}</div><p class="muted" data-mp-run-line>${esc(runTitle(lastRun))} · ${new Date(lastRun.completedAt).toLocaleTimeString()} · ${same?'the current model':'the model changed since this run; this result is unchanged'}.${runFailure?' The last run failed; this is the previous complete run.':''}${originNote(lastRun)}</p>`+(kept?'':`<p class="validation-warning" data-mp-values-only>${esc(MAPS_NOT_KEPT)}</p>`);
  const id=resultPage.slice(8),maps=[];
  if(id==='runs'){runList(host);return maps;}
  if(id==='check'){
   const rows=couplingCheckRows(r,lastRun.doc,kept?null:counts);
   host.insertAdjacentHTML('beforeend',`<h2>Coupling check</h2>${pair('Solve order used',r.solve_order.map(g=>g.map(physicsLabel).join(' ⇄ ')).join(' → '))}<div class="table-scroll"><table class="mp-check"><thead><tr><th>Coupling</th><th>Sent</th><th>Received</th><th>Check</th></tr></thead><tbody>${rows.map(row=>`<tr><td>${esc(row.title)}<br><small>${esc(row.name)}</small></td><td>${esc(row.sent)}</td><td>${esc(row.received)}</td><td class="${row.passed?'passed':'failed'}">${esc(row.check)}</td></tr>`).join('')}</tbody></table></div>`);
   for(const loop of r.loops||[])host.insertAdjacentHTML('beforeend',`<h3>${esc(loop.physics.map(physicsLabel).join(' ⇄ '))} · settled in ${loop.iterations} iterations</h3>`+residualChart(loop.residuals,parseQuantity(loop.tolerance?.value)?.number));
   return maps;
  }
  const p=r.physics[id];
  if(p.type==='thermal.steady2d'){
   host.insertAdjacentHTML('beforeend',`<h2>${esc(physicsLabel(id))} · temperature</h2>${kept?'<div class="mp-plot"><canvas data-mp-map="temperature" role="img"></canvas></div>':`<p class="mp-no-maps" data-mp-no-maps>${esc(MAPS_NOT_KEPT)}</p>`}${pair('Minimum T',p.range.min.toFixed(3)+' K')}${pair('Maximum T',p.range.max.toFixed(3)+' K')}${pair('Nodes',counts.nodes.toLocaleString('en-US'))}${pair('Triangles',counts.triangles.toLocaleString('en-US'))}${kept?'<p class="muted">Each triangle is coloured by the mean of its node temperatures.</p>':''}`);
   if(kept)maps.push(['temperature',()=>drawMap(host.querySelector('[data-mp-map=temperature]'),r,p.temperature.values,{nodal:true,label:'Temperature in K'})]);
  }else{
   const rows=effectiveIndexRows(p),alone=uncoupled[id],coupled=p.coupled;
   host.insertAdjacentHTML('beforeend',`<h2>${esc(physicsLabel(id))} · optical modes</h2>`);
   const valid=!!alone&&alone.key===baselineKey(lastRun.doc,id),solving=job?.alone===id||baselineQueue.includes(id),failed=baselineErrors[id];
   const head=alone?`<th>n_eff without heater${valid?'':' (other model)'}</th><th>Δn_eff (coupled − without heater)</th>`:'';
   const cells=(row,k)=>{if(!alone)return '';const a=alone.rows[k];return `<td data-neff-alone="${row.mode}" data-neff-value="${a?.value??''}">${a?a.value.toFixed(8):'—'}</td><td data-neff-shift="${row.mode}">${a&&valid?shiftText(row.value,a.value):'—'}</td>`;};
   const note=!coupled?'':solving?`Solving ${esc(physicsLabel(id))} without heater…`:valid?esc(baselineText(lastRun.doc,id)):alone?`The without-heater column was solved from a different optical model. Run ${esc(physicsLabel(id))} alone to refresh.`:failed?`The run without heater ${failed==='stopped'?'was stopped':'failed: '+esc(failed)}. Run ${esc(physicsLabel(id))} alone to try again.`:`An n_eff without heater appears here when “Also solve without heater” beside Run is on, or run ${esc(physicsLabel(id))} alone.`;
   const identity=physicsModes(p),table=modeTableRows(identity.modes,{missing:identity.missing,areaMissing:identity.areaMissing,areaHelp:identity.areaHelp,open:identity.open});
   // the table holds the first study point's modes; rows of a later point keep their columns
   const cellOf=row=>row.point===0?table.rows[row.mode-1]:undefined;
   const polarization=row=>{const r=cellOf(row);if(!r)return '<td>—</td>';const c=r.polarization;return c?`<td data-polarization="${row.mode}" title="${esc(c.title)}"${c.rowspan>1?` rowspan="${c.rowspan}"`:''}>${esc(c.text)}</td>`:'';};
   const area=row=>{const c=cellOf(row)?.area;return c?`<td data-area="${row.mode}" title="${esc(c.title)}"${c.value===null?'':` data-area-value="${c.value}"`}>${esc(c.text)}</td>`:'<td>—</td>';};
   host.insertAdjacentHTML('beforeend',`<div class="table-scroll"><table class="mp-neff"><thead><tr><th>Mode</th><th>n_eff${coupled?' (coupled)':''}</th><th title="${esc(POLARIZATION_HELP)}">Polarization</th><th title="${esc(table.loss.help)}">${esc(table.loss.header)}</th><th title="${esc(identity.areaHelp)}">A_eff (µm²)</th>${head}</tr></thead><tbody>${rows.map((row,k)=>`<tr><td>Mode ${row.mode}</td><td data-neff="${row.mode}" data-neff-value="${row.value}">${row.value.toFixed(8)}</td>${polarization(row)}<td data-loss="${row.mode}"${cellOf(row)?` title="${esc(cellOf(row).lossTitle)}"`:''}>${esc(cellOf(row)?.loss??'—')}</td>${area(row)}${cells(row,k)}</tr>`).join('')}</tbody></table></div><p class="muted" id="mp-candidate-note">${esc(RANKING_CAVEAT)} ${link('physics:'+id,modeCountText(lastRun.doc,id,{past:freshness()==='stale'}))}</p>`+
    `<p class="muted" data-mp-polarization-note>Polarization: ${esc(POLARIZATION_HELP)}${identity.source?'; '+esc(SOURCE_TEXT[identity.source]):identity.missing?' · '+esc(identity.missing):''}.</p>`+
    `<p class="muted" data-mp-area-note>A_eff: ${esc(identity.areaHelp)}${identity.areaSource?'; '+esc(SOURCE_TEXT[identity.areaSource]):identity.areaMissing?' · '+esc(identity.areaMissing):''}.</p>`+(table.rows.length&&table.rows.every(r=>r.lossless)?`<p class="muted" data-mp-lossless>${esc(table.loss.note)}</p>`:`<p class="muted" data-mp-loss-note>${esc(table.loss.note)}</p>`)+
    (coupled?`<p class="mp-baseline" id="mp-baseline-note">${note}${valid||solving?'':` <button type="button" id="mp-run-alone" ${job||starting?'disabled':''}>Run ${esc(physicsLabel(id))} alone</button>`}</p>`:'')+pair('Vacuum wavelength',wavelengthText(p.vacuum_wavelength)));
   // the answer first, then the coupled input it was solved from
   if(coupled&&!kept)host.insertAdjacentHTML('beforeend',`<p class="mp-no-maps" data-mp-no-maps>${esc(MAPS_NOT_KEPT)}</p>`);
   else if(coupled){const region=r.mesh.region_names.includes('core')?'core':null,dn=coupled.index_change;
    host.insertAdjacentHTML('beforeend',`<div class="mp-maps"><figure><figcaption>Temperature per triangle [K]${region?' · core':''}</figcaption><div class="mp-plot"><canvas data-mp-map="T" role="img"></canvas></div></figure><figure><figcaption><label>Show <select id="mp-index-view"><option value="n" ${indexView==='n'?'selected':''}>refractive index n</option>${dn?`<option value="dn" ${indexView==='dn'?'selected':''}>change n − n₀</option>`:''}</select></label>${region?' · core':''}</figcaption><div class="mp-plot"><canvas data-mp-map="n" role="img"></canvas></div></figure></div><p class="muted">The coupled input as the optical solve used it: the mean of each triangle's 3 node temperatures, and n = n₀ + (dn/dT)(T − T_ref). The change is (dn/dT)(T − T_ref) of each triangle's material.</p>`);
    maps.push(['T',()=>drawMap(host.querySelector('[data-mp-map=T]'),r,coupled.temperature.values,{region,label:'Temperature in K'})]);
    maps.push(['n',()=>drawMap(host.querySelector('[data-mp-map=n]'),r,indexView==='dn'&&dn?dn:coupled.refractive_index.n,{region,label:indexView==='dn'&&dn?'Index change n − n₀':'Refractive index'})]);}
   else host.insertAdjacentHTML('beforeend','<p>This physics had no coupled input in this run.</p>');
   const alone_=host.querySelector('#mp-run-alone');if(alone_)alone_.onclick=()=>runAlone(id);
   const sel=host.querySelector('#mp-index-view');if(sel)sel.onchange=()=>{indexView=sel.value;maps.find(m=>m[0]==='n')?.[1]();};
  }
  return maps;
 }
const runTime=run=>new Date(run.completedAt).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});
 const runTitle=run=>`Run ${run.number}${run.label?' · '+run.label:''}`;
 // round 14 (Q5): the plain words, with what the checksum does not show as the title text
 const CHECKSUM_HELP='The checksum detects a damaged or hand-edited file; it does not show who made the file: whoever edits a file can recompute it.';
 const originNote=run=>run.origin==='local'?'':run.origin==='recovered'?' Recovered from this browser, not recomputed.':' Loaded from file, not recomputed. <span data-mp-checksum title="'+CHECKSUM_HELP+'">Results match the file\'s checksum.</span>';
 const runItem=run=>`${run.pinned?'Pinned · ':''}${runTitle(run)} · ${runTime(run)}${run.origin==='imported'?' · from file':run.origin==='recovered'?' · recovered':''}${run.maps==='not kept'?' · values only':''}`;
 // Results › Runs: the run list, in the optical words; selecting a run shows it, the model stays
 function runList(host){
  const pinned=runs.filter(r=>r.pinned).length;
  host.insertAdjacentHTML('beforeend',`<h2 id="mp-run-list-heading">Runs · ${runs.length} of ${MULTIPHYSICS_RUN_LIMIT} · ${pinned} pinned</h2><div class="mp-run-list">${[...runs].reverse().map(r=>`<button type="button" class="run-item" data-mp-run="${esc(r.job)}" aria-pressed="${r===lastRun}">${esc(runItem(r))}</button>`).join('')}</div>
   <form class="run-name" id="mp-run-name"><label>Run name<input id="mp-run-name-input" type="text" maxlength="80" value="${esc(lastRun.label)}" placeholder="For example: heater 10 mW" aria-describedby="mp-run-name-hint"></label><button id="mp-rename-run" type="submit">Apply name</button><p id="mp-run-name-hint" class="input-hint">Press Enter to apply. Naming a run pins it, so new runs do not replace it; Enter on a named, unpinned run pins it again.</p></form>
   ${lastRun.pinned?'<button type="button" id="mp-unpin-run">Unpin this run</button>':''}
   <p>Up to six runs are kept. Pinned runs stay; when a new run arrives, the oldest unpinned run is replaced. File › Save keeps every run in one file.</p>`);
  host.querySelectorAll('[data-mp-run]').forEach(b=>b.onclick=()=>{const r=runs.find(x=>x.job===b.dataset.mpRun);if(!r)return;lastRun=r;ctx.onHistory();ctx.render();notice(`${runTitle(r)} shown under Results; the model is unchanged.`);});
  const input=host.querySelector('#mp-run-name-input'),form=host.querySelector('#mp-run-name'),target=lastRun;
  const apply=()=>nameRun(target,input.value);
  form.onsubmit=e=>{e.preventDefault();apply();};input.onkeydown=e=>{if(e.key==='Enter'&&!e.isComposing){e.preventDefault();apply();}};
  const unpin=host.querySelector('#mp-unpin-run');if(unpin)unpin.onclick=()=>{target.pinned=false;ctx.onHistory();ctx.render();notice('Run unpinned: once six runs are kept, a new run replaces the oldest unpinned one. Press Enter in Run name to pin it again.');};
 }
 function nameRun(run,value){
  let label;try{label=ctx.validateRunLabel(value);}catch(e){notice(e.message);return;}
  if(label===(run.label||'')&&(!label||run.pinned))return;
  run.label=label;if(label)run.pinned=true;ctx.onHistory();ctx.render();
  notice(label?`Run named “${label}” and pinned: new runs will not replace it. File › Save keeps it in a file.`:'Run name cleared.'+(run.pinned?' The run stays pinned until you unpin it.':''));
 }
 // ---- the session file (§1-§2) and the save indicator ----
 // the selection as a file can hold it: an item an Undo removed (a coupling, an iteration step)
 // is written as the model, so Studio never writes a view it would refuse
 function storedSelection(){try{return readMultiphysicsView({page:'Model',selection,index_map:'index',baseline_option:false},doc,lastRun).selection;}catch{return 'model';}}
 const viewState=()=>({page:VIEW_PAGES.includes(ctx.ui.page)?ctx.ui.page:'Model',selection:storedSelection(),index_map:indexView==='dn'?'change':'index',baseline_option:baselineOption});
 const savedBaselines=()=>Object.fromEntries(Object.entries(uncoupled).filter(([,b])=>b.document&&b.job).map(([n,b])=>[n,{job:b.job,completedAt:b.completedAt,document:b.document,result:b.result}]));
 const sessionState=()=>({document:doc,runs,baselines:savedBaselines(),selected:lastRun?.job||null,view:viewState()});
 // everything a session file holds, as a comparable text, but the page: a tab click (Library,
 // Model, Connections, Results) is not an edit, so an opened or saved file stays current through
 // it. Save session still writes the page shown when it is pressed.
 function stamp(){const {page,...view}=viewState();return JSON.stringify({doc,runs:runs.map(r=>[r.job,r.label,r.pinned,r.maps]),selected:lastRun?.job||null,baselines:Object.entries(uncoupled).map(([n,b])=>[n,b.job||null]),view});}
 const sessionCurrent=()=>!!sessionFile&&sessionFile.stamp===stamp();
 // the runs that no session file holds
 // the runs a session file holds as they are: job -> name and pin
 const filed=()=>new Map(runs.map(r=>[r.job,JSON.stringify([r.label||'',r.pinned===true])]));
 const unsavedRuns=()=>sessionCurrent()?0:runs.filter(r=>sessionFile?.jobs?.get(r.job)!==JSON.stringify([r.label||'',r.pinned===true])).length;
 const editedSinceOpen=()=>signature()!==openedSignature;
 function indicator(){
  return {clean:signature()===cleanSignature||(!cleanSignature&&!editedSinceOpen()),runsUnsaved:(runs.length>0||editedSinceOpen())&&!sessionCurrent(),
   saved:sessionFile&&sessionFile.savedAt?{name:sessionFile.name,savedAt:sessionFile.savedAt,current:sessionCurrent(),written:sessionFile.written===true}:null,file:ctx.currentFileName?.()||null,fileHow:ctx.currentFileHow?.()||null,loaded:loaded?{kind:loaded.kind,name:loaded.name,current:loaded.stamp===stamp(),file:loaded.file||null,fileCurrent:loaded.fileCurrent===true}:null,
   // a template just opened, not yet edited, run, saved or opened
   fresh:freshSignature!==null&&signature()===freshSignature&&!runs.length&&!sessionFile&&!loaded};
 }
 function saveState(){return persistenceTitle({...indicator(),recovery:ctx.recoveryState?.()||null});}
 function saveHint(){return persistenceHint({...indicator(),recovery:ctx.recoveryState?.()||null});}
 // Save session: the file if it fits; else the §2 dialog, or the refusal that names the run
 // saveAs: File › Save As (ask for a file); else Save (the file Save As chose, or ask). The
 // file is written, or downloaded, before anything is marked saved; a cancel marks nothing.
 async function saveSession({keepSelected=false,saveAs=false}={}){
  const out=writeMultiphysicsSession(sessionState(),{keepSelected});
  if(!out.ok){if(out.reduced)return {ok:false,question:overflowQuestion(out.bytes)};notice('Session not saved: '+out.refusal);return {ok:false,refused:out.refusal};}
  const at={stamp:stamp(),jobs:filed(),signature:signature(),runs:runs.length};
  const result=await ctx.deliverSession(out.text,sessionFileName(modelSlug(doc.name)),{saveAs});
  if(!result.written){notice(result.message);return {ok:false,cancelled:true};}
  const name=result.name;
  sessionFile={name,savedAt:new Date().toISOString(),stamp:at.stamp,jobs:at.jobs,written:result.via==='picker'};cleanSignature=at.signature;loaded=null;freshSignature=null;ctx.onHistory();
  notice(savedNotice(name,{runs:at.runs,notKept:out.notKept,baseline:out.baselines>0,opticalRuns:ctx.opticalRunCount?.()||0,via:result.via,known:result.known===true,again:result.again===true,after:result.after}));
  return {ok:true,name};
 }
 // The model's entry of a project file (P3): its session text as Save session writes it, or the
 // 16 MiB question, or the refusal. mark(name, savedAt, written) records the project file as this
 // model's file once it was written, as Save session does.
 function projectEntry({keepSelected=false}={}){
  const out=writeMultiphysicsSession(sessionState(),{keepSelected});
  if(!out.ok)return out.reduced?{ok:false,question:overflowQuestion(out.bytes)}:{ok:false,refusal:out.refusal};
  const at={stamp:stamp(),jobs:filed(),signature:signature(),runs:runs.length};
  return {ok:true,text:out.text,notKept:out.notKept,baselines:out.baselines,runs:at.runs,
   // projectName (round 16): the file is the project file of that name, which a restore names again
   mark:(name,savedAt,written,projectName=null)=>{sessionFile={name,savedAt,stamp:at.stamp,jobs:at.jobs,written,...(projectName?{projectName}:{})};cleanSignature=at.signature;loaded=null;freshSignature=null;ctx.onHistory();}};
 }
 // What the project's "changed" counts of this model: its document, its runs (names, pins, maps)
 // and the without-heater results; not the view or the selected run.
 const contentStamp=()=>doc?JSON.stringify({doc,runs:runs.map(r=>[r.job,r.label,r.pinned,r.maps]),baselines:Object.entries(uncoupled).map(([n,b])=>[n,b.job||null])}):null;
 // browser recovery (§4): written while the model has a run or was edited since it was opened
 function recovery(){
  if(!active||!(runs.length||editedSinceOpen()))return null;
  const savedFile=sessionFile&&sessionFile.savedAt?{name:sessionFile.name,savedAt:sessionFile.savedAt,current:sessionCurrent(),...(sessionFile.projectName?{projectName:sessionFile.projectName}:{})}:null;
  const state={...sessionState(),runs:[...runs],baselines:savedBaselines()};
  // the maps recovery leaves out of a record over 16 MiB: the runs that still have them here
  // openedCurrent: the inputs and runs are still those of the file it was opened from
  const openedCurrent=sourceFile?openedStamp!==null&&openedStamp===stamp():null;
  return {stamp:stamp()+JSON.stringify([savedFile,openedCurrent]),savedFile,openedFile:sourceFile,openedCurrent,makeText:()=>{const out=recoveryText(state);recoveryDropped=out.notKept.filter(n=>state.runs.find(r=>r.number===n)?.maps!=='not kept').length;return out.text;}};
 }
 // the text browser recovery holds for this model as it is now (shown or not), so a project save can
 // relink its record (round 16); null without a model or over 16 MiB
 function recoveryTextNow(){if(!doc)return null;try{return recoveryText({...sessionState(),runs:[...runs],baselines:savedBaselines()}).text;}catch{return null;}}
 let recoveryDropped=0;
 // ---- the dock ----
 // The Study sequence: the coupled run's rows (out of date once the model changed), then the
 // heater-off solve when one is going or kept.
 function sequenceRows(){
  const coupledJob=job&&!job.alone?job:null,src=coupledJob||runFailure||lastRun,order=src?.order||check.solve_order||[];
  if(!src)return order.map(g=>({group:g,label:g.length>1?g.map(physicsLabel).join(' ⇄ '):physicsLabel(g[0]),state:'ready',text:'Ready'}));
  let rows=progressRows(order,src.doc,src.events||[],coupledJob?'running':runFailure?runFailure.status:'done',runFailure?.error);
  if(src===lastRun)rows=originRows(rows,lastRun.origin);
  if(!coupledJob&&src===lastRun&&runFreshness(lastRun,doc)==='stale')rows=staleRows(rows,lastRun.doc,doc);
  if(job?.alone)rows.push(...progressRows([[job.alone]],job.doc,job.events,'running').map(r=>({...r,label:r.label+' without heater'})));
  return rows;
 }
 function renderDock(){
  const host=$('sequence');if(!host)return;const src=job||runFailure||lastRun;
  const rows=sequenceRows();
  host.innerHTML=rows.map((r,i)=>`<span class="mp-row ${esc(r.state)}"><b>${i+1}</b>${esc(r.label)} · ${esc(r.text)}</span>`).join('')+(job?'<button type="button" id="mp-stop">Stop run</button>':'');
  const stopButton=$('mp-stop');if(stopButton)stopButton.onclick=stop;
  const box=$('mp-messages');if(!box)return;box.hidden=!active;
  const removal=lastRemoval?`<div class="mp-message warning" data-mp-removal><p>Coupling ${esc(lastRemoval.title)} removed.</p><div class="mp-message-actions"><button type="button" data-mp-undo>Undo</button></div></div>`:'';
  const warnings=unsourcedInputs(doc,catalog).map(w=>`<div class="mp-message warning" data-mp-warning="${esc(w.physics)}"><p>${esc(physicsLabel(w.physics))}: ${esc(w.text)}.</p><div class="mp-message-actions"><button type="button" data-mp-show-node="physics:${esc(w.physics)}">Show</button></div></div>`).join('');
  const list=messages.map((m,i)=>messageHtml(m,i)).join(''),fail=runFailure&&runFailure.status!=='stopped'?`<div class="mp-message error"><p>${esc(failureText(runFailure.error,runFailure.doc))}</p></div>`:'';
  const suggest=suggestedCouplings(doc,catalog).map(s=>`<div class="mp-message info"><p>${esc(suggestionText(s))}</p><div class="mp-message-actions"><button type="button" data-mp-add-coupling="${esc(s.from)}|${esc(s.to)}">Add coupling…</button></div></div>`).join('');
  box.innerHTML=removal+fail+list+warnings+suggest||'<p class="muted">No problems: the model passes the check.</p>';bindMessages(box);
  box.querySelector('[data-mp-undo]')?.addEventListener('click',()=>undo());
  box.querySelectorAll('[data-mp-show-node]').forEach(b=>b.onclick=()=>choose(b.dataset.mpShowNode));
  box.querySelectorAll('[data-mp-add-coupling]').forEach(b=>b.onclick=()=>{const [f,t]=b.dataset.mpAddCoupling.split('|');couplingDialog(f,t);});
 }
 // ---- the page ----
 function renderPage(){
  resize?.disconnect();resize=null;const page=ctx.ui.page,main=document.querySelector('main');
  main.dataset.page=page;main.classList.toggle('connecting',page==='Connections');main.classList.toggle('choosing',page==='Applications');main.classList.remove('comparing');
  $('view-title').textContent=({Model:'Graphics',Connections:'Physics connections',Results:'Results',Compare:'Comparison',Applications:'Model library'})[page];
  const count=physicsNames(doc).length;
  $('view-detail').textContent=page==='Connections'?(couplingNames(doc).length?'Drawn from the couplings':count===1?'One physics':`${count} physics · no couplings`):page==='Model'?'Interactive model view':page==='Applications'?(ctx.projectLine?.()||'Choose a model'):'';
  markPageTabs(document.querySelector('.page-tabs'),page);
  document.querySelectorAll('[data-command-node]').forEach(b=>{b.disabled=page==='Applications';b.onclick=()=>choose(({Geometry:'geometry',Materials:'materials',Mesh:'mesh',Study:'study'})[b.dataset.commandNode]);});
  document.querySelectorAll('[data-view]').forEach(b=>b.hidden=true);
  const toolbar=document.querySelector('.workspace > .toolbar');if(toolbar)toolbar.style.display=page==='Model'?'flex':'none';
  $('breadcrumb').textContent=page+' / '+(selection.startsWith('physics:')?physicsLabel(selection.slice(8)):selection.startsWith('coupling:')?couplingTitle(doc,selection.slice(9)):selection.startsWith('material:')?materialLabel(selection.slice(9)):selection.startsWith('results:')?'Results':selection[0].toUpperCase()+selection.slice(1));
  document.querySelector('.workspace > .note').textContent=page==='Results'?'A result belongs to its run; editing the model does not change it.':lengthsNote(doc);
  $('solver-log').hidden=true;$('workflow').hidden=true;
  drawTree();
  const inspector=$('inspector');inspector.innerHTML=settings();bindSettings(inspector);
  const canvas=$('canvas');let maps=[];
  if(page==='Applications')ctx.applications(canvas);
  else if(page==='Connections'){canvas.innerHTML=connections();bindFields(canvas);canvas.querySelectorAll('[data-mp-select]').forEach(b=>b.onclick=()=>choose(b.dataset.mpSelect));canvas.querySelector('[data-mp-action=add-coupling]').onclick=()=>couplingDialog();installGraph(canvas);}
  else if(page==='Results'){maps=results(canvas);canvas.querySelectorAll('[data-mp-node]').forEach(b=>b.onclick=()=>choose(b.dataset.mpNode));}
  else if(page==='Compare')canvas.innerHTML='<h2>Compare</h2><p>Comparison is for optical runs. A multiphysics run shows its physics side by side under Results, and Run Modes 1 alone adds the uncoupled n_eff.</p>';
  else{canvas.innerHTML=`<h2>${esc(doc.name||'Model')}</h2>`+geometrySvg();canvas.querySelectorAll('[data-mp-pick]').forEach(el=>{const pick=()=>choose('material:'+el.dataset.mpPick);el.onclick=pick;el.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();pick();}};});}
  if(maps.length){const draw=()=>maps.forEach(([,f])=>{try{f();}catch(e){}});resize=new ResizeObserver(draw);canvas.querySelectorAll('canvas').forEach(c=>resize.observe(c));draw();}
  for(const id of ['add-physics','add-coupling'])if($(id))$(id).hidden=false;
  projectCommands(true);
  renderDock();refreshRun();
  // the page and the selection are part of a session: the save indicator and recovery follow them
  ctx.onHistory();
 }
 // The ribbon's Project group: Open and Save, as in every model (§6), File › Open, Save and
 // Save As; the model file alone is File › Export › Model file. The browser draft holds optical
 // inputs, so File › Browser copy › Save browser draft is hidden here and comes back on leaving.
 const SESSION_WORDS={'open-session':'Opens a project file, a saved session file (a multiphysics model with its runs) or a model file alone.','save-session':'Saves every model of this tab to one project file: this multiphysics model with its runs, their names and pins and the without-heater results, and the optical model.'};
 let describedBefore=null;
 function projectCommands(on){
  if($('save-draft'))$('save-draft').hidden=on;
  if(on&&!describedBefore){describedBefore={};for(const [id,text] of Object.entries(SESSION_WORDS))if($(id)){describedBefore[id]=[$(id).getAttribute('aria-description'),$(id).title];$(id).setAttribute('aria-description',text);$(id).title=text;}}
  else if(!on&&describedBefore){for(const [id,[d,t]] of Object.entries(describedBefore))if($(id)){$(id).setAttribute('aria-description',d);$(id).title=t;}describedBefore=null;}
 }
 function leave(){
  resize?.disconnect();resize=null;for(const id of ['add-physics','add-coupling','run-multiphysics','run-multiphysics-reason','run-baseline-option'])if($(id))$(id).hidden=true;
  const heading=document.querySelector('.dock-title>span');if(heading)heading.textContent='Nothing is computed until you press Run';
  const box=$('mp-messages');if(box){box.hidden=true;box.replaceChildren();}
  projectCommands(false);
 }
 // File › Export › Model file: the document alone
 function saveInputs(){
  const text=JSON.stringify(doc,null,2)+'\n',name=(String(doc.name||'model').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'')||'model')+'.json';
  ctx.download(new Blob([text],{type:'application/json'}),name);
  cleanSignature=signature();ctx.onHistory();notice(`Model file ${name} sent to your browser's Downloads. It has the model but no runs; Save keeps the runs too, in the session file.`);
 }
 return {active:()=>active,open,openText,openTemplate,openSession,close,leave,show,discard,projectEntry,contentStamp,inProject:()=>doc!==null,card:()=>card,projectRuns:()=>doc?runs.length:0,projectUnsavedRuns:()=>doc?unsavedRuns():0,renderPage,undo,redo,canUndo:()=>active&&undoStack.length>0,canRedo:()=>active&&redoStack.length>0,
  addPhysics:()=>physicsDialog(),addCoupling:()=>couplingDialog(),run:()=>run(),stop,saveInputs,saveSession,recovery,recoveryTextNow,recoveryDropped:()=>recoveryDropped,busy:()=>!!job||starting,
  setBaseline:on=>{baselineOption=!!on;refreshRun();ctx.onHistory();notice(on?'The next Run also solves the optical model without heater (about 1 s).':`The next Run solves the coupled model only; Run ${baselinePhysics(doc).map(physicsLabel).join(' or ')||'the optical model'} alone under Results still adds the comparison.`);},
  title:()=>`${isMultiphysics(doc)?'Multiphysics model':'Model'} / ${saveState()}`,saveState,saveHint,
  // what leaving would lose: the runs no session file holds
  unsavedRuns:()=>active?unsavedRuns():0,edited:()=>doc!==null&&editedSinceOpen(),runCount:()=>active?runs.length:0,modelName:()=>doc?.name||'this model',projectTitle:()=>doc?.name||'Multiphysics model',
  // for checks: the current document, the shown result and the run list
  document:()=>clone(doc),lastResult:()=>lastRun?.result||null,runs:()=>runs.map(r=>({job:r.job,number:r.number,label:r.label,pinned:r.pinned,maps:r.maps,origin:r.origin}))};
}
