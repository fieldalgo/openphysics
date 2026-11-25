// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Round 25: usability fixes of the optical model (A1 to A4, pre-registered P1 to P4).
// Plain text comparison only: no RegExp is built from a dynamic string.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const read=name=>fs.readFileSync(path.join(__dirname,STATIC,name),'utf8');

test('P3 (A3): a named pair read from a file is kept because it is named, so the newest-pair offer appears',async()=>{
 const C=await import(STATIC+'workspace-compare.mjs');
 const runs=[1,2,3].map(n=>({job:'j'+n,number:n,...(n<3?{label:'Design '+'AB'[n-1]}:{})}));
 const named=['j1','j2'];
 // read from a file: the named pair is not the default one, yet not picked by hand
 assert.equal(C.pairChosen(runs,named),false);
 // an unnamed pair that is not the default, or a pair with one named run: picked, as before
 const plain=[1,2,3].map(n=>({job:'j'+n,number:n,label:''}));
 assert.equal(C.pairChosen(plain,['j1','j2']),true);
 assert.equal(C.pairChosen([{job:'j1',label:'Design A'},{job:'j2',label:''},{job:'j3',label:''}],['j1','j2']),true);
 // the default pair is never picked; one named run on both sides is not a named pair
 assert.equal(C.pairChosen(runs,['j2','j3']),false);
 assert.equal(C.pairChosen(runs,['j1','j1']),true);
 // one new run after the file: the pair stays (named) and Compare offers the two newest
 const after=[...runs,{job:'j4',number:4,label:''}],picked=C.pairChosen(runs,named);
 assert.deepEqual(C.comparisonAfterRun(after,named,picked),named);
 assert.deepEqual(C.newestPairOffer(after,named,picked),['j3','j4']);
 // the page reads a file's pair through pairChosen, unchanged in shape
 assert.ok(read('workspace-app.mjs').includes('compareIds=[...session.comparison];comparePicked=pairChosen(runs,compareIds);'));
});

// ---- P1 (A1): the words say when fields move; a warning before a run with no size estimate ----
const VIEW={mode:0,component:'magnitude',window:'Core region'};
const setup={materials:{Core:'Silicon',Oxide:'Silica',Heater:''},temperature:293.15,cooling:'',fixed:'',terminal:''};
async function retention(){
 const N=await import(STATIC+'workspace-notebook.mjs'),P=await import(STATIC+'workspace-project.mjs'),X=await import(STATIC+'workspace-retention.mjs');
 const inputs=()=>P.snapshot({width:500,voltage:1,electric:false,heat:false,structure:false,optics:true,wavelength:1550,coreMesh:30},setup);
 const field=(k,t)=>{const X0=[],T=[];for(let i=0;i<=t;i++)X0.push([i*1e-8,0],[i*1e-8,1e-8]);for(let i=0;i<t;i++)T.push([2*i,2*i+2,2*i+1]);
  const mode=m=>T.map((_,i)=>[1+i*1e-3,0.25*m+i*1e-4,1e-3*(m+1)]);return {node_coordinates:X0,triangles:T,real:Array.from({length:k},(_,m)=>mode(m)),imag:Array.from({length:k},(_,m)=>T.map(()=>[0,1e-9*m,0]))};};
 const run=(i,k=2)=>Object.assign(N.validateRun({job:i.toString(16).padStart(8,'0'),completedAt:new Date(Date.UTC(2026,10,25,0,0,i)).toISOString(),settings:N.opticalSettings(1550,30,k),input:inputs(),
  effective_index:Array.from({length:k},(_,m)=>2.9-0.17*m),field:field(k,12),origin:'local',serverVersion:'0.0.0'}),{number:i});
 return {N,X,inputs,run};
}

test('P1 (A1): the run list note and Results say when fields move, exactly',async()=>{
 const {N,X}=await retention();
 assert.equal(N.RUNS_KEPT_TEXT,"Up to 20 runs are kept with their values. Fields are kept up to 16.8 MB. When a result or a recompute arrives, Studio keeps the selected run's fields first, then pinned runs', then the newest. Selecting a run does not bring its fields back; Recompute does.");
 const four={number:4,label:''};
 assert.equal(X.fieldsNotKeptResultsText(four),"Run 4's fields are not kept; its n_eff, TE fractions and effective areas are kept. Fields are kept up to 16.8 MB. When a result or a recompute arrives, Studio keeps the selected run's fields first, then pinned runs', then the newest. Selecting a run does not bring its fields back; Recompute does.");
 // a run read from a file without its fields keeps its words
 assert.equal(X.fieldsNotKeptResultsText(four,true),"Run 4's fields were not kept in the session file. Its n_eff, TE fractions and effective areas are kept.");
 assert.equal(X.FIELDS_MAY_GO_TEXT,"If you run: older runs' fields may not be kept (16.8 MB limit) · pin a run to keep its fields first");
 // the run list keeps the rest of its note
 assert.ok(read('workspace-app.mjs').includes("limit.textContent=RUNS_KEPT_TEXT+' Pinned runs stay; when a 21st run arrives, the oldest unpinned run is replaced. File › Save keeps every run in one file; Export this run writes one run to its own file.';"));
});

test('P1 (A1): with no run of the same key, the line shows only when the room left is less than the smallest kept field',async()=>{
 const {N,X,inputs,run}=await retention();
 const runs=[run(1),run(2),run(3)],sel=runs[2].job,cmp=[runs[1].job,runs[2].job],input=inputs();
 const size=r=>({1:300,2:200,3:500})[r.number];
 const base=N.sessionBytesWithoutFields(input,runs,sel,cmp,VIEW),total=base+1000;
 const other=X.fieldSizeKey({shapes:[{type:'rect',name:'Core',material:'Silicon',x:-100,y:0,w:200,h:300}],coreMesh:30,boundary:null,modeCount:8});
 const risk=budget=>X.unestimatedFieldRisk(input,runs,sel,cmp,VIEW,other,{budget,bytes:size});
 // every field kept: room left = budget - total; the smallest kept field is 200 bytes
 assert.equal(risk(total+199),true);
 assert.equal(risk(total+200),false,'room equal to the smallest field: no line');
 assert.equal(risk(total+5000),false);
 // a field let go: the kept ones count (budget base+800 keeps Run 3 and Run 2, smallest 200; room 100)
 assert.equal(risk(base+800),true);
 // a run of the same key gives an estimate: the named line, not this one
 assert.equal(X.unestimatedFieldRisk(input,runs,sel,cmp,VIEW,X.runFieldSizeKey(runs[0]),{budget:total+1,bytes:size}),false);
 // no field kept: nothing to say
 const bare=[run(5)];X.letGoField(bare[0]);
 assert.equal(X.unestimatedFieldRisk(input,bare,bare[0].job,[bare[0].job,bare[0].job],VIEW,other,{budget:1,bytes:size}),false);
 // the page: shown before a run only, with no Pin button (it names no run)
 const app=read('workspace-app.mjs');
 assert.ok(app.includes("if(!running)risk=unestimatedFieldRisk(inputsFile(),runs,solverRun?.job||null,compareIds,currentView(),next);"));
 assert.ok(app.includes("if(!list.length&&fieldWarning.risk&&!running){$('run-drop').hidden=false;$('run-options').classList.add('dropping');$('run-drop-text').textContent=FIELDS_MAY_GO_TEXT;$('run-drop-text').title=FIELDS_MAY_GO_TEXT;$('run-drop-pin').hidden=true;return;}"));
});

test('P2 (A2): on the download path, Save of a file this tab downloaded asks first, in these words',async()=>{
 const F=await import(STATIC+'workspace-files.mjs');
 assert.equal(F.downloadAgainQuestion('design-a-ng.json'),'Download design-a-ng.json again? This browser cannot replace the earlier file and may name the new one design-a-ng (1).json.');
 assert.deepEqual([...F.DOWNLOAD_AGAIN_BUTTONS],['Download again','Save As…','Cancel']);
 const file=how=>F.rememberFile({name:'design-a-ng.json',how,handle:how==='picker'?{}:null,scope:'s'});
 // downloaded in this tab: Save asks; Save As, a picker, or no file: it does not
 assert.equal(F.asksBeforeDownloadAgain(file('download')),true);
 assert.equal(F.asksBeforeDownloadAgain(file('download'),{saveAs:true}),false);
 assert.equal(F.asksBeforeDownloadAgain(file('download'),{picker:true}),false);
 assert.equal(F.asksBeforeDownloadAgain(null),false);
 // a file opened or recovered: its first Save downloads at once, as before; a picker file is written again
 for(const how of ['opened','recovered','picker'])assert.equal(F.asksBeforeDownloadAgain(file(how)),false,how);
 // the save route itself is unchanged
 assert.equal(F.saveRoute(file('download')),'download');
 // the page asks before both deliveries (the project file and the session export), and Cancel writes nothing
 const app=read('workspace-app.mjs');
 // round 29 (L3, coordinator ruling): the project file's question names the repeat it asks about
 const asks=call=>`if(result.status==='known'&&asksBeforeDownloadAgain(target)){\n   const chosen=await ${call};\n   if(!chosen.name)return {written:false,message:notWrittenNotice({status:'cancelled'},{saveAs:chosen.saveAs})};`;
 assert.equal(app.split(asks('downloadAgainChoice(result.name)')).length-1,1);
 assert.equal(app.split(asks('downloadAgainChoice(result.name,nextDownloadAgain(target,result.name))')).length-1,1);
 assert.ok(app.includes("againDialog.id='download-again';"));
 assert.ok(app.includes("if(answer!=='saveAs')return {name:null,saveAs:false};\n $('save-name-input').defaultValue=name;return {name:await askFileName(name,{saveAs:true}),saveAs:true};"));
 assert.equal(F.notWrittenNotice({status:'cancelled'},{saveAs:false}),'Save cancelled; nothing was written.');
});

// ---- P4 (A4): an open run names its core mode and a mode mostly in an edge shape, PML excluded ----
// a triangle of area 4.5 nm² whose centroid is (x, y) nm, and an open run of these triangles: each
// mode's |E|² per triangle is given by weight (one component, so e = area * weight)
function openRun(modes,{openEdges=['left','right','bottom','top'],boundary='PML'}={}){
 const at={core:[0,110],cladding:[0,800],substrate:[0,-800],substrateEdge:[0,-1100],pml:[0,-1700]},X=[],T=[],keys=Object.keys(at);
 for(const k of keys){const [x,y]=at[k],d=1,n=X.length;X.push([(x-d)*1e-9,(y-d)*1e-9],[(x+2*d)*1e-9,(y-d)*1e-9],[(x-d)*1e-9,(y+2*d)*1e-9]);T.push([n,n+1,n+2]);}
 const value=w=>[Math.sqrt(w),0,0];
 return {settings:{boundary,pml:{thickness:'1000 nm',open_edges:openEdges,target:'2.46'}},
  input:{model:{shapes:[{type:'rect',name:'Core',material:'Silicon',x:-250,y:0,w:500,h:220},{type:'rect',name:'Substrate',material:'Silica',x:-1500,y:-1200,w:3000,h:700}]}},
  effective_index:modes.map((_,i)=>2.4-0.1*i),
  field:{node_coordinates:X,triangles:T,real:modes.map(m=>keys.map(k=>value(m[k]??0))),imag:modes.map(()=>keys.map(()=>[0,0,0]))}};
}
test('P4 (A4): open-boundary region notes, measured over the window without the PML, exactly',async()=>{
 const M=await import(STATIC+'workspace-modes.mjs');
 // the closed note's thresholds, unchanged
 assert.deepEqual([M.EDGE_SHARE,M.EDGE_NEAR,M.EDGE_BAND_NM,M.CORE_SHARE],[0.5,0.01,300,0.5]);
 const modes=[
  {core:0.6,substrate:0.2,cladding:0.2,pml:10},        // the core mode; with the PML counted, 0.6 / 11 would not be
  {substrateEdge:0.7,core:0.1,cladding:0.2,pml:5},      // mostly in Substrate, near its edge
  {substrate:0.4,core:0.3,cladding:0.3},                // neither share above 50 %
  {substrate:0.595,substrateEdge:0.005,core:0.1,cladding:0.3}]; // Substrate 60 %, but only 0.5 % near its edges
 const run=openRun(modes);
 assert.deepEqual(M.openRegionNotes(run).map(n=>[n.mode,n.kind,n.text]),[
  [0,'core','Mode 1 is the core mode: 60 % of |E|² in the window (PML excluded) is in Core, which does not touch the window edge.'],
  [1,'edge','Mode 2 is mostly in Substrate (70 % of |E|² in the window, PML excluded), which continues into the PML at the open window edge.']]);
 const placed=M.openRegionPlacement(run);
 assert.ok(Math.abs(placed[0].core.share-0.6)<1e-12&&Math.abs(placed[3].edge.share-0.6)<1e-12&&Math.abs(placed[3].edge.near-0.005)<1e-12);
 assert.equal(placed[3].edge.named,false);assert.equal(placed[2].edge.named||placed[2].core.named,false);
 // the bottom edge closed: the closed edge is named, with what to do
 assert.equal(M.openRegionNotes(openRun(modes,{openEdges:['left','right','top']}))[1].text,'Mode 2 is mostly in Substrate (70 % of |E|² in the window, PML excluded), which touches the closed bottom edge; its n_eff depends on that closed edge. Open it in Geometry › Boundaries to leave it open.');
 assert.equal(M.openRegionNotes(openRun(modes,{openEdges:['top']}))[1].text,'Mode 2 is mostly in Substrate (70 % of |E|² in the window, PML excluded), which touches the closed left, right and bottom edges; its n_eff depends on those closed edges. Open them in Geometry › Boundaries to leave them open.');
 // a closed run, or an open run without fields: nothing here (the closed notes are edgeNotes and coreNotes)
 assert.deepEqual(M.openRegionNotes(openRun(modes,{boundary:'PEC'})),[]);
 assert.deepEqual(M.openRegionNotes({...run,field:null}),[]);
 // no guided or leaky claim in any of the words
 for(const text of [...M.openRegionNotes(run).map(n=>n.text),M.openEdgeNoteText(0,{shape:'Substrate',share:0.9,closed:['bottom']})])assert.doesNotMatch(text,/\b(?:guided|leaky|bound|radiat\w*)\b/i);
 // the page puts them in the modes table with the closed window's notes
 assert.ok(read('workspace-app.mjs').includes("const regions=openRegionNotes(run),edge=new Map([...edgeNotes(run),...regions.filter(n=>n.kind==='edge')].map(n=>[n.mode,n.text])),core=new Map([...coreNotes(run),...regions.filter(n=>n.kind==='core')].map(n=>[n.mode,n.text]))"));
});

test('P6 (A6): the job panel is not a second live region; Messages carries every job state',()=>{
 const html=read('workspace.html'),app=read('workspace-app.mjs');
 assert.ok(html.includes('<span id="job-message"></span>'));
 assert.ok(!/id="job-message"[^>]*(role|aria-live)=/.test(html));
 for(const id of ['file-status','status','autosave-status'])assert.equal(html.split(`id="${id}" role="status"`).length-1,1,id);
 // every job state still reaches Messages (the one live region) and the panel's text
 assert.ok(app.includes("$('job-message').textContent=state.message;$('job-message').title=state.title||'';"));
  // job progress (round 25 A5): a running state reaches Messages as its live words (without the time),
 // written only when they change; every other state as its message
 assert.ok(app.includes("if(state.phase==='done')announceResult(state.message,swapAction());else if(state.live===undefined)notice(state.message);else if($('file-status').textContent!==state.live)notice(state.live);"));
});

test('a Library re-render keeps a project name being typed, with its focus and selection',async()=>{
 const A=await import(STATIC+'workspace-applications.mjs');
 const input={value:'both-models',dataset:{kept:'Heater study'},selectionStart:3,selectionEnd:11};
 const doc=focused=>({getElementById:id=>id==='project-name-input'?input:null,activeElement:focused?input:null});
 assert.deepEqual(A.projectNameDraft(doc(true)),{value:'both-models',focused:true,start:3,end:11});
 assert.equal(A.projectNameDraft(doc(false)).focused,false);
 // the stored name in the field, or no field: nothing to keep
 assert.equal(A.projectNameDraft({getElementById:()=>({value:'Heater study',dataset:{kept:'Heater study'}})}),null);
 assert.equal(A.projectNameDraft({getElementById:()=>null}),null);
 const src=read('workspace-applications.mjs');
 assert.ok(src.includes("const draft=projectNameDraft(host.ownerDocument);host.replaceChildren();"));
 assert.ok(src.includes("input.dataset.kept=project.name||'';input.value=draft?draft.value:project.name||'';"));
});
