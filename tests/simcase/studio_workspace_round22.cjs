// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Round 22: usability fixes of the optical and heated models (V1 to V6, pre-registered P1 to P6).
// Plain text comparison only: no RegExp is built from a dynamic string.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const FIXTURES=path.join(__dirname,'studio_session_fixtures');
const read=name=>fs.readFileSync(path.join(__dirname,STATIC,name),'utf8');
const body=(text,from,to)=>{const a=text.indexOf(from),b=text.indexOf(to,a+from.length);assert.ok(a>=0&&b>a,from);return text.slice(a,b);};

test('P1 (V1): Modes to return: two radios and the field, each with its own name; the field always enabled',async()=>{
 const C=await import(STATIC+'workspace-closed-target.mjs');
 assert.equal(C.CLOSED_SEARCH_LEGEND,'Modes to return');
 assert.equal(C.HIGHEST_LABEL,'Highest n_eff above 1.45');assert.equal(C.NEAREST_LABEL,'Nearest to n_eff');assert.equal(C.NEAR_FIELD_LABEL,'n_eff to search near');
 assert.equal(new Set([C.HIGHEST_LABEL,C.NEAREST_LABEL,C.NEAR_FIELD_LABEL]).size,3);
 const field=body(read('workspace-app.mjs'),'const closedSearchField=()=>{','const bindClosedSearchField=');
 // each radio is named by its own label; the field, outside both labels, by its aria-label; never disabled
 assert.ok(field.includes('<label class="radio-field"><input type="radio" name="closed-search" id="closed-search-highest" value="highest"${near?\'\':\' checked\'}> ${HIGHEST_LABEL}</label>'));
 assert.ok(field.includes('<label class="radio-field"><input type="radio" name="closed-search" id="closed-search-nearest" value="nearest"${near?\' checked\':\'\'}> ${NEAREST_LABEL}</label><input id="closed-target-number"'));
 assert.ok(field.includes('aria-label="${NEAR_FIELD_LABEL}"'));
 assert.ok(!field.includes('disabled'));assert.ok(!field.includes('checkbox'));
 assert.ok(!read('workspace-app.mjs').includes('closed-search-check'));
});

test('P1 (V1): typing in the field selects Nearest to n_eff; Highest is the target off, Nearest the target on',()=>{
 const bind=body(read('workspace-app.mjs'),'const bindClosedSearchField=()=>{','// The group index box');
 assert.ok(bind.includes('field.oninput=()=>{nearest.checked=true;};'));
 assert.ok(bind.includes('field.onchange=take;'));
 assert.ok(bind.includes('highest.onchange=()=>{if(highest.checked&&state.searchTarget!=null)setClosedSearch(null);};'));
 assert.ok(bind.includes('nearest.onchange=()=>{if(nearest.checked)take();};'));
 assert.ok(bind.includes('ui.closedNear=t;if(state.searchTarget===t)return;setClosedSearch(t);'));
 // the one input the document, the signature and the session read is unchanged
 const app=read('workspace-app.mjs');
 assert.ok(app.includes('function setClosedSearch(t){state.searchTarget=t;render();notice(closedSearchNotice(t));offerMatchingRun();}'));
 assert.ok(app.includes('const opticalDocument=()=>buildOpticalDocument({...state,searchTarget:closedTargetNow()},setup);'));
});

test('P1 (V1): Highest writes the K1 documents byte for byte; Nearest 2.46 the targeted ones',async()=>{
 const O=await import(STATIC+'workspace-optical.mjs'),F=await import('./studio_session_fixtures/closed_documents.mjs');
 const golden=JSON.parse(fs.readFileSync(path.join(FIXTURES,'optical-documents-closed-13f07f4.json'),'utf8'));
 const highest=null,nearest=2.46;
 for(const [label,state] of F.closedStates()){
  assert.equal(JSON.stringify(O.opticalDocument({...state,searchTarget:highest},F.SETUP)),golden[label],label);
  const plain=JSON.parse(golden[label]);plain.physics.em1.target_effective_index=2.46;
  assert.equal(JSON.stringify(O.opticalDocument({...state,searchTarget:nearest},F.SETUP)),JSON.stringify(plain),label);
 }
});

test('P5 (V5): Set search near 2.46 · 4 modes; its message ends "Press Run study to compute."; it runs nothing',async()=>{
 const C=await import(STATIC+'workspace-closed-target.mjs'),W=await import(STATIC+'workspace-workflow.mjs');
 assert.equal(C.shortcutText(2.46),'Set search near 2.46 · 4 modes');assert.equal(C.SHORTCUT_RUN_TEXT,'Press Run study to compute.');
 const use=body(read('workspace-app.mjs'),'function useClosedSearch(t){','\n');
 assert.ok(use.includes('notice(`${closedSearchNotice(t)} Modes to find set to ${SHORTCUT_MODE_COUNT}. ${SHORTCUT_RUN_TEXT}`);offerMatchingRun();}'));
 // nothing is submitted: no job, no run
 for(const call of ['runOptical','submit','jobMonitor','api('])assert.ok(!use.includes(call),call);
 assert.equal(`${C.closedSearchNotice(2.46)} Modes to find set to 4. ${C.SHORTCUT_RUN_TEXT}`,'Modes to return: nearest to n_eff 2.460 in the closed window. The next run returns the modes nearest it. Modes to find set to 4. Press Run study to compute.');
 // when a kept run has these inputs, "No need to run" replaces the request (round 20, Z1)
 assert.equal(W.matchingRunMessage('Modes to find set to 4. Press Run study to compute.'),'Modes to find set to 4.');
});

const CORE={name:'Core',type:'rect',material:'Silicon',x:-250,y:0,w:500,h:220};
const SUBSTRATE={name:'Substrate',type:'rect',material:'Silicon',x:-1500,y:-1200,w:3000,h:700};
test('P2 (V2): the slab warning before a run: T18 warns; the core-only template and a lower-index edge slab do not',async()=>{
 const M=await import(STATIC+'workspace-modes.mjs');
 // T18: 500 × 220 core over a 3000 × 700 silicon substrate spanning the window
 const t18=M.edgeSlabRisk([CORE,SUBSTRATE]);assert.deepEqual(t18,{edge:'Substrate',core:'Core'});
 assert.equal(M.edgeSlabWarningText(t18),"Substrate touches the window edge and its index is as high as Core's: in a closed window its slab modes come first.");
 // the real shape names, in any order
 assert.equal(M.edgeSlabWarningText(M.edgeSlabRisk([{...SUBSTRATE,name:'Wafer'},{...CORE,name:'Rib'}])),"Wafer touches the window edge and its index is as high as Rib's: in a closed window its slab modes come first.");
 // the core-only template: no warning; a silica slab touching the edge: no warning
 assert.equal(M.edgeSlabRisk([CORE]),null);
 assert.equal(M.edgeSlabRisk([CORE,{...SUBSTRATE,name:'Oxide slab',material:'Silica'}]),null);
 // lower than the core (silicon nitride under silicon) no, higher (silicon under silicon nitride) yes
 assert.equal(M.edgeSlabRisk([CORE,{...SUBSTRATE,material:'Silicon nitride'}]),null);
 assert.deepEqual(M.edgeSlabRisk([{...CORE,material:'Silicon nitride'},SUBSTRATE]),{edge:'Substrate',core:'Core'});
 // every shape on the edge (no core away from it): no warning; the highest of each group is compared
 // (the first of equal ones is named), and a higher core away from the edge clears it
 assert.equal(M.edgeSlabRisk([SUBSTRATE]),null);
 assert.deepEqual(M.edgeSlabRisk([{...CORE,material:'Silicon nitride'},{...CORE,name:'Core 2',x:300,w:100,material:'Silicon nitride'},{...SUBSTRATE,material:'Silica'},{...SUBSTRATE,name:'Top',y:1000,h:200,material:'Gallium arsenide'}]),{edge:'Top',core:'Core'});
 assert.equal(M.edgeSlabRisk([{...CORE,material:'Silicon nitride'},{...CORE,name:'Core 2',x:300,w:100},{...SUBSTRATE,name:'Top',y:1000,h:200,material:'Gallium arsenide'}]),null);
 // a shape short of the window edge does not touch it
 assert.equal(M.edgeSlabRisk([CORE,{...SUBSTRATE,x:-1499,w:2998,y:-1199}]),null);
});

test('P2 (V2): shown in the plan line and Optical modes, with both buttons, only for a closed window with Highest',()=>{
 const app=read('workspace-app.mjs');
 assert.ok(app.includes('const edgeWarning=()=>isOptical()&&applicationChosen()&&!state.openBoundary&&state.searchTarget==null?edgeSlabRisk(state.shapes):null;'));
 // the buttons: the edge note's shortcut with the same target estimate (defaultTarget) and Use Open boundary
 const buttons=body(app,'function edgeWarningButtons(prefix){','\n}');
 assert.ok(buttons.includes('const near=defaultTarget(state.shapes)'));
 assert.ok(buttons.includes('search.textContent=shortcutText(near);search.onclick=()=>useClosedSearch(near);'));
 assert.ok(buttons.includes("open.textContent='Use Open boundary';open.onclick=()=>{if(!state.openBoundary)setOuterBoundary(true);};"));
 // the plan line's row and the panel's warning
 assert.ok(app.includes(' refreshDropWarning();refreshEdgeWarning();'));
 assert.ok(app.includes("host.append(...edgeWarningButtons('run-edge'));"));
 assert.ok(app.includes("$('closed-edge-actions')?.append(...edgeWarningButtons('closed-edge'));"));
 assert.ok(app.includes('<p class="validation-warning" id="closed-edge-warning-text">${escapeHtml(edgeSlabWarningText(risk))}</p>'));
 // no solve: the check reads the shapes only; the result-side edge note is unchanged
 assert.ok(!body(app,'const edgeWarning=','\n').includes('runs'));
 assert.ok(app.includes("b.id='edge-search-near';b.textContent=shortcutText(near);b.onclick=()=>useClosedSearch(near);"));
});

test('P3 (V3): Compare without a matched mode says why when a run\'s mode 1 is an edge mode, with a link to that run',async()=>{
 const M=await import(STATIC+'workspace-modes.mjs'),N=await import(STATIC+'workspace-notebook.mjs'),P=await import(STATIC+'workspace-project.mjs');
 const setup={materials:{Core:'Silicon',Oxide:'Silica',Heater:''},temperature:293.15,cooling:'',fixed:'',terminal:''};
 const input=shapes=>P.snapshot({width:500,voltage:1,electric:false,heat:false,structure:false,optics:true,wavelength:1550,coreMesh:30,shapes},setup);
 // one triangle in the core, one in the substrate near its edge; mode 1 in the substrate, mode 2 in the core
 const f={node_coordinates:[[-2e-7,1e-8],[2e-7,1e-8],[0,2e-7],[-1.4e-6,-1.1e-6],[1.4e-6,-1.1e-6],[0,-6e-7]],triangles:[[0,1,2],[3,4,5]],
  real:[[[0,0,0],[1,0,0]],[[1,0,0],[0.1,0,0]]],imag:[[[0,0,0],[0,0,0]],[[0,0,0],[0,0,0]]]};
 const run=(extra={})=>N.validateRun({job:'0000000a',completedAt:'2026-11-24T01:00:00.000Z',settings:N.opticalSettings(1550,30,2),input:input([CORE,SUBSTRATE]),effective_index:[2.6,2.44],field:f,origin:'local',serverVersion:'0.0.0',...extra});
 assert.equal(M.firstModeEdgeShape(run()),'Substrate');
 assert.equal(M.noMatchEdgeText('A','Run 6','Substrate'),'A · Run 6: its modes are mostly in Substrate, which touches the window edge; the core mode was not found.');
 // mode 1 in the core: no reason; the core-only template: none
 const swapped={...f,real:[f.real[1],f.real[0]],imag:f.imag};
 assert.equal(M.firstModeEdgeShape(run({field:swapped})),null);
 assert.equal(M.firstModeEdgeShape(N.validateRun({...run(),input:input([CORE])})),null);
 // the page: only with no matched mode (not disabled, no error); the link opens the run in Results
 const app=read('workspace-app.mjs'),part=body(app,' // round 22 (V3): no matched mode,',' // the plots first, right under the pickers');
 assert.ok(part.includes("if(!chosen&&!match.disabled&&!match.error)[['A',a],['B',b]].forEach("));
 assert.ok(part.includes('reason.textContent=noMatchEdgeText(side,runNumberTitle(run),shape);'));
 assert.ok(part.includes('link.textContent=`Open Run ${runNumber(run)} in Results`;'));
 assert.ok(part.includes("link.onclick=e=>{e.preventDefault();if(!runs.includes(run))return;solverRun=run;ui.page='Results';render();"));
});

const shape700={type:'rect',name:'Core',material:'Silicon',x:-350,y:0,w:700,h:300};
const listRun=(n,extra={})=>({job:String(n).padStart(8,'0'),number:n,label:'',pinned:false,settings:{mode_count:4},input:{model:{shapes:[shape700]}},...extra});
test('P4 (V4): Pin Run N names the run the next result drops instead (optical and heated words)',async()=>{
 const W=await import(STATIC+'workspace-workflow.mjs');
 const six=[1,2,3,4,5,6].map(n=>listRun(n));
 // the line names Run 1; pinning it moves the drop to Run 2
 assert.deepEqual(W.droppedBy(six).map(r=>r.number),[1]);six[0].pinned=true;
 const next=W.droppedBy(six);assert.deepEqual(next.map(r=>r.number),[2]);
 assert.equal(W.pinnedDropText(six[0],next),'Run 1 pinned. If you run: drops Run 2 (closed · 4 modes · 700 × 300 nm) · pin it to keep it');
 assert.equal(W.pinnedDropText({number:4},[listRun(5)]),'Run 4 pinned. If you run: drops Run 5 (closed · 4 modes · 700 × 300 nm) · pin it to keep it');
 // while the run computes, the line's words; the heated model's names
 assert.equal(W.pinnedDropText(six[0],next,true),'Run 1 pinned. When this run finishes, Run 2 (closed · 4 modes · 700 × 300 nm) is dropped');
 const heated=r=>`Run ${r.number} (run at 05:31 AM)`;
 assert.equal(W.pinnedDropText({number:4},[listRun(5)],false,heated),'Run 4 pinned. If you run: drops Run 5 (run at 05:31 AM) · pin it to keep it');
 assert.equal(W.pinnedDropText({number:4},[listRun(5)],true,heated),'Run 4 pinned. When this run finishes, Run 5 (run at 05:31 AM) is dropped');
 // the pages call it after the pin, with droppedBy of the runs as pinned
 assert.ok(read('workspace-app.mjs').includes('const next=droppedBy(runs,RUN_LIMIT);notice(next.length?pinnedDropText(run,next,solverBusy||!!pendingJob):pinNotice(run));};'));
 assert.ok(read('workspace-multiphysics-view.mjs').includes("const next=droppedBy(runs,MULTIPHYSICS_RUN_LIMIT);notice(next.length?pinnedDropText(r,next,!!job&&!job.alone||starting&&!job,dropName):'Run pinned: new runs will not replace it. File › Save keeps it in a file.');};"));
});

test('P4 (V4): a result that drops a run with every other earlier run pinned says why there is no swap',async()=>{
 const W=await import(STATIC+'workspace-workflow.mjs'),N=await import(STATIC+'workspace-notebook.mjs'),M=await import(STATIC+'workspace-multiphysics-session.mjs');
 const six=[listRun(1,{pinned:true}),listRun(2,{pinned:true}),listRun(3),listRun(4,{pinned:true}),listRun(5,{pinned:true}),listRun(6,{pinned:true})],seventh=listRun(7);
 // the optical limit is 20 runs (run retention): its list is twenty runs and a 21st result; the
 // heated model's is the six runs and the seventh, as before
 const twenty=[...Array.from({length:20},(_,i)=>listRun(i+1,{pinned:i+1!==3}))],twentyFirst=listRun(21);
 for(const [append,list,newest] of [[N.appendRun,twenty,twentyFirst],[M.appendMultiphysicsRun,six,seventh]]){
  const next=append(list,newest),dropped=list.filter(r=>!next.includes(r));
  assert.deepEqual(dropped.map(r=>r.number),[3]);assert.equal(W.swapCandidate(next,newest),null);
 }
 assert.equal(W.droppedNoSwapText([listRun(3)]),'Run 3 (closed · 4 modes · 700 × 300 nm) was dropped; every other earlier run is pinned, so no other run can be dropped instead');
 assert.equal(W.droppedNoSwapText([listRun(3)],r=>`Run ${r.number} (run at 05:31 AM)`),'Run 3 (run at 05:31 AM) was dropped; every other earlier run is pinned, so no other run can be dropped instead');
 // the pages: the no-swap words exactly when no swap candidate exists (optical and heated)
 assert.ok(read('workspace-app.mjs').includes("droppedNote=!dropped.length?'':swapCandidate(runs,solverRun)?droppedAfterText(dropped):droppedNoSwapText(dropped);"));
 assert.ok(read('workspace-multiphysics-view.mjs').includes("const droppedWords=!dropped.length?'':swapCandidate(runs,completed)?droppedAfterText(dropped,dropName):droppedNoSwapText(dropped,dropName);"));
 // the heated model says them again when the without-heater solves finish, as it does the swap's
 assert.ok(read('workspace-multiphysics-view.mjs').includes("noSwapNote=dropped.length&&!swapCandidate(runs,completed)?droppedWords:'';"));
 assert.ok(read('workspace-multiphysics-view.mjs').includes("(dropSwap?' '+dropSwap.note:noSwapNote?' '+noSwapNote:''),swapAction());return;}"));
});

test('P6 (V6): Use this run\'s inputs does not say that Undo returns the search target',()=>{
 const app=read('workspace-app.mjs'),use=body(app,'function useRunInputs(run){','const runNumberTitle=');
 assert.ok(app.includes("const TARGET_NOT_UNDONE='Modes to return is set and is not part of Undo.';"));
 assert.ok(use.includes("const undo=!targetChange.length?'The next run uses them; Undo takes them back.':inputs.length?`The next run uses them; Undo takes back the other inputs. ${TARGET_NOT_UNDONE}`:`The next run uses it. ${TARGET_NOT_UNDONE}`;"));
 assert.ok(use.includes("returned=t=>t==null?'highest n_eff':'nearest to '+shortTarget(t)"));
 // the words of the three cases
 const text=(changes,target)=>{const returned=t=>t==null?'highest n_eff':'nearest to '+t,tc=target?[`Modes to return ${returned(target[0])} → ${returned(target[1])}`]:[];
  const undo=!tc.length?'The next run uses them; Undo takes them back.':changes.length?'The next run uses them; Undo takes back the other inputs. Modes to return is set and is not part of Undo.':'The next run uses it. Modes to return is set and is not part of Undo.';
  return `Current inputs set from Run 4: ${[...changes,...tc].join(' · ')}. ${undo}`;};
 assert.equal(text([],[null,'2.46']),'Current inputs set from Run 4: Modes to return highest n_eff → nearest to 2.46. The next run uses it. Modes to return is set and is not part of Undo.');
 assert.equal(text(['Modes to find 2 → 4'],[null,'2.46']),'Current inputs set from Run 4: Modes to find 2 → 4 · Modes to return highest n_eff → nearest to 2.46. The next run uses them; Undo takes back the other inputs. Modes to return is set and is not part of Undo.');
 // no message of the page says that Undo takes back the search target
 for(const name of ['workspace-app.mjs','workspace-closed-target.mjs'])assert.ok(!/Undo (takes|returns)[^.\n]*(search|Search near|target|Modes to return)/.test(read(name)),name);
});
