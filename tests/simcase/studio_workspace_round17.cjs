// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Round 17: run numbers that never change within a tab, and the message naming a run the limit
// dropped. Plain text comparison only: no RegExp is built from a dynamic string.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const read=name=>fs.readFileSync(path.join(__dirname,STATIC,name),'utf8');
let W,N,P,S;
test.before(async()=>{W=await import(STATIC+'workspace-workflow.mjs');N=await import(STATIC+'workspace-notebook.mjs');P=await import(STATIC+'workspace-project.mjs');S=await import(STATIC+'workspace-shapes.mjs');});

const input=()=>P.snapshot({width:700,voltage:1,electric:false,heat:false,structure:false,optics:true},{materials:{Core:'Silicon',Oxide:'Silica',Heater:''},temperature:293.15,cooling:'',fixed:'',terminal:''});
const run=(job,extra={})=>({job,completedAt:'2026-11-23T00:00:00.000Z',settings:N.opticalSettings(),input:input(),effective_index:[2.4,1.7],
 field:{node_coordinates:[[0,0],[1e-6,0],[0,1e-6]],triangles:[[0,1,2]],real:[[[1,0,0]],[[0,1,0]]],imag:[[[0,0,0]],[[0,0,0]]]},origin:'local',...extra});
const job=i=>i.toString(16).padStart(8,'0');
// a field of 200 triangles, so that a run written without it is smaller
const bigField=()=>{const n=200,X=[],T=[];for(let i=0;i<n;i++){X.push([i*1e-8,0],[i*1e-8,1e-8]);}for(let i=0;i<n-1;i++)T.push([2*i,2*i+2,2*i+1]);T.push([0,2,3]);
 const mode=k=>T.map((_,i)=>[k?0:1+i*1e-3,k?1+i*1e-3:0,0]);return {node_coordinates:X,triangles:T,real:[mode(0),mode(1)],imag:[T.map(()=>[0,0,0]),T.map(()=>[0,0,0])]};};

test('U2: the limit drops the oldest unpinned run and renumbers nothing; the next number is the largest used + 1',()=>{
 let runs=[],used=0;const dropped=[];
 for(let i=0;i<8;i++){const r=run(job(i));used=W.numberRuns([r],used);const next=N.appendRun(runs,r);dropped.push(...runs.filter(x=>!next.includes(x)));runs=next;}
 assert.deepEqual(runs.map(r=>r.number),[3,4,5,6,7,8]);
 assert.deepEqual(dropped.map(r=>r.number),[1,2]);
 assert.equal(used,8);
 // the same job again keeps its number (appendRun replaces it in place of the old record)
 const again=run(job(5));again.number=runs.find(r=>r.job===job(5)).number;used=W.numberRuns([again],used);runs=N.appendRun(runs,again);
 assert.deepEqual(runs.map(r=>r.number),[3,4,5,7,8,6]);assert.equal(used,8);
 // a run added after a pinned one keeps counting from the largest
 runs[0].pinned=true;const ninth=run(job(9));used=W.numberRuns([ninth],used);const next=N.appendRun(runs,ninth);
 assert.equal(ninth.number,9);assert.deepEqual(runs.filter(x=>!next.includes(x)).map(r=>r.number),[4]);
});
test('U2: a file opened numbers its runs from 1; runs added from a file continue from the largest',()=>{
 const opened=[run(job(1)),run(job(2)),run(job(3))];assert.equal(W.numberRuns(opened),3);assert.deepEqual(opened.map(r=>r.number),[1,2,3]);
 const added=[run(job(7)),run(job(8))];assert.equal(W.numberRuns([...opened.slice(1),...added],5),7);assert.deepEqual(added.map(r=>r.number),[6,7]);
});
test('U2: the message of a dropped run names its number, name, geometry and modes',()=>{
 const r=run(job(3),{number:3});
 assert.equal(W.droppedRunText(r),'Run 3 (700 × 220 nm · 2 modes) was dropped: up to six runs are kept; pin a run to keep it.');
 assert.equal(W.droppedRunText({...r,label:'Design A'}),'Run 3 · Design A (700 × 220 nm · 2 modes) was dropped: up to six runs are kept; pin a run to keep it.');
});
test('U2: the number is not written to files; the save names a run by its number',()=>{
 const a=run(job(1),{number:4,field:bigField()}),b=run(job(2),{number:7,field:bigField()}),view={mode:0,component:'magnitude',window:'Core region'};
 const full=N.writeOpticalSession(input(),[a,b],a.job,[a.job,b.job],view);
 assert.equal(full.ok,true);assert.equal(JSON.parse(full.text).runs.some(r=>Object.hasOwn(r,'number')),false);
 // over the limit: the fields of the selected run only; the run left without them is named by its number
 const limit=full.bytes-1,out=N.writeOpticalSession(input(),[a,b],a.job,[a.job,b.job],view,{keepSelected:true,limit});
 assert.equal(out.ok,true);assert.deepEqual(out.notKept,[7]);
 const plain=N.writeOpticalSession(input(),[{...a,number:undefined},{...b,number:undefined}],a.job,[a.job,b.job],view,{keepSelected:true,limit});
 assert.equal(plain.text,out.text);assert.deepEqual(plain.notKept,[2]);
 const refused=N.writeOpticalSession(input(),[{...a,pinned:true},b],a.job,[a.job,b.job],view,{keepSelected:true,limit:100});
 assert.equal(refused.ok,false);assert.ok(refused.refusal.startsWith('The pinned run (Run 4 selected) is '),refused.refusal);
});
test('U2: the status line and the freshness words use the run number, not the list place',()=>{
 const runs=[run(job(4),{number:4}),run(job(5),{number:5})];
 runs.forEach(r=>{r.signature='x'+r.job;});
 const f=W.opticalFreshness(input(),runs,runs[1],2);assert.equal(f.run,5);
 assert.equal(W.opticalFreshness(input(),runs,null,2).run,5);
 const app=read('workspace-app.mjs');
 assert.ok(app.includes("function runNumber(run){return runs.includes(run)&&Number.isInteger(run.number)?run.number:null;}"));
});
test('U14: the status line names several shapes as the run list does (round 16 S8), without materials',()=>{
 const core={name:'Core',type:'rect',material:'Silicon',x:-250,y:0,w:500,h:220},sub={name:'Substrate',type:'rect',material:'Silicon',x:-1500,y:-1200,w:3000,h:700};
 assert.equal(S.geometryWords({shapes:[core,sub]}),'Core 500 × 220 + Substrate 3000 × 700 nm');
 assert.equal(S.designSummary({shapes:[core,sub]}),'Core 500 × 220 + Substrate 3000 × 700 nm · Silicon');
 const tooth={name:'Tooth',type:'polygon',material:'Silica',points:[[0,300],[100,300],[50,400]]};
 assert.equal(S.geometryWords({shapes:[core,tooth]}),'Core 500 × 220 nm + Tooth 3-vertex polygon');
 const many=[core,sub,{...core,name:'A',x:600},{...core,name:'B',x:-900}];
 assert.equal(S.geometryWords({shapes:many}),'Core 500 × 220 + Substrate 3000 × 700 + A 500 × 220 nm +1 more');
 assert.equal(S.geometryWords({shapes:[core]}),'500 × 220 nm');
 // the viewed-run status line: "Run 6 · Core 500 × 220 + Substrate 3000 × 700 nm" (was "Run 6 · 2 shapes")
 const r=run(job(6),{number:6});r.input.model.shapes=[core,sub];r.signature='other';
 const f=W.opticalFreshness(input(),[r],r,2);assert.equal(f.geometry,'Core 500 × 220 + Substrate 3000 × 700 nm');
});

// A 100 nm grid over the closed window (two triangles per cell, metres), and one mode per
// intensity function of the centroid in nm (|E|² = f, all in E_x).
function gridRun(shapes,intensities){
 const X=[],T=[],nx=30,ny=24;for(let j=0;j<=ny;j++)for(let i=0;i<=nx;i++)X.push([(-1500+100*i)*1e-9,(-1200+100*j)*1e-9]);
 const id=(i,j)=>j*(nx+1)+i;for(let j=0;j<ny;j++)for(let i=0;i<nx;i++){T.push([id(i,j),id(i+1,j),id(i+1,j+1)]);T.push([id(i,j),id(i+1,j+1),id(i,j+1)]);}
 const c=t=>[(X[t[0]][0]+X[t[1]][0]+X[t[2]][0])/3*1e9,(X[t[0]][1]+X[t[1]][1]+X[t[2]][1])/3*1e9];
 const real=intensities.map(f=>T.map(t=>[Math.sqrt(f(...c(t))),0,0])),imag=intensities.map(()=>T.map(()=>[0,0,0]));
 return {effective_index:intensities.map((_,k)=>3-k*0.1),field:{node_coordinates:X,triangles:T,real,imag},input:{model:{shapes}},settings:{adapter:'simcase-optical-waveguide-v1'}};
}
const core={name:'Core',type:'rect',material:'Silicon',x:-250,y:0,w:500,h:220};
const substrate={name:'Substrate',type:'rect',material:'Silicon',x:-1500,y:-1200,w:3000,h:700};
test('U1: a mode mostly in a shape touching the window edge, with |E|² near those edges, is named',async()=>{
 const M=await import(STATIC+'workspace-modes.mjs');
 // mode 1 fills the substrate; mode 2 the core; mode 3 the substrate's middle only (|x| < 600 nm)
 const run=gridRun([core,substrate],[(x,y)=>y<-500?1:0,(x,y)=>x>-250&&x<250&&y>0&&y<220?1:0,(x,y)=>y<-500&&Math.abs(x)<600?1:0]);
 const p=M.edgePlacement(run);
 // 210 substrate cells; within 300 nm of its left, right or bottom edge: 3 columns each side (7 rows) and
 // 3 rows of 30, the corners once: 21 + 21 + 90 - 18 = 114
 assert.equal(p[0].shape,'Substrate');assert.ok(Math.abs(p[0].share-1)<1e-12);assert.ok(Math.abs(p[0].near-114/210)<1e-12,String(p[0].near));assert.equal(p[0].named,true);
 assert.equal(p[1].share,0);assert.equal(p[1].named,false);
 assert.ok(Math.abs(p[2].share-1)<1e-12);assert.ok(Math.abs(p[2].near-3/7)<1e-12,String(p[2].near));assert.equal(p[2].named,true);
 assert.deepEqual(M.edgeNotes(run).map(n=>n.mode),[0,2]);
 assert.equal(M.edgeNotes(run)[0].text,'Mode 1 is mostly in Substrate (100 % of |E|²), which touches the window edge; its n_eff depends on the closed window. Use Open boundary, or ask for more modes to reach the core mode.');
 assert.equal(M.edgeNoteText(0,{shape:'Substrate',share:0.934}),'Mode 1 is mostly in Substrate (93 % of |E|²), which touches the window edge; its n_eff depends on the closed window. Use Open boundary, or ask for more modes to reach the core mode.');
});
test('U1: the bounds: more than half in the shape, and at least 1 % of |E|² within 300 nm of its touched edges',async()=>{
 const M=await import(STATIC+'workspace-modes.mjs');
 assert.deepEqual([M.EDGE_SHARE,M.EDGE_NEAR,M.EDGE_BAND_NM],[0.5,0.01,300]);
 // half in the substrate (not more): not named; a slab mode of a rib whose field stays 400 nm from the walls: not named
 const slab={name:'Slab',type:'rect',material:'Silicon',x:-1500,y:0,w:3000,h:200},rib={name:'Rib',type:'rect',material:'Silicon',x:-200,y:200,w:400,h:100};
 // a core on the grid: 4 cells in the substrate's top row and 4 in the core
 const box={name:'Box',type:'rect',material:'Silicon',x:-200,y:0,w:400,h:200};
 const half=gridRun([box,substrate],[(x,y)=>Math.abs(x)<200&&((y<-500&&y>-600)||(y>0&&y<100))?1:0]);
 const h=M.edgePlacement(half)[0];assert.ok(Math.abs(h.share-0.5)<1e-12,String(h.share));assert.equal(h.named,false);
 const ribRun=gridRun([slab,rib],[(x,y)=>y>0&&y<200&&Math.abs(x)<1100?1:0,(x,y)=>y>0&&y<200?1:0]);
 const r=M.edgePlacement(ribRun);assert.equal(r[0].shape,'Slab');assert.ok(Math.abs(r[0].share-1)<1e-12);assert.equal(r[0].near,0);assert.equal(r[0].named,false);
 // 3 columns on each side of 30
 assert.ok(Math.abs(r[1].near-0.2)<1e-12,String(r[1].near));assert.equal(r[1].named,true);
 // the template (one core, touching nothing): every mode null, no note
 assert.deepEqual(M.edgePlacement(gridRun([core],[(x,y)=>1])),[null]);assert.deepEqual(M.edgeNotes(gridRun([core],[(x,y)=>1])),[]);
});
test('U1: shapes layer as the geometry contract does; circles, polygons and edges; open runs and runs without fields',async()=>{
 const M=await import(STATIC+'workspace-modes.mjs');
 // the core drawn after a substrate that covers it wins there
 const big={name:'Big',type:'rect',material:'Silicon',x:-1500,y:-1200,w:3000,h:1500};
 const run=gridRun([big,{...core,y:-300}],[(x,y)=>x>-250&&x<250&&y>-300&&y<-80?1:0]);
 assert.equal(M.edgePlacement(run)[0].share,0);
 assert.deepEqual(M.touchedEdges(substrate),['left','right','bottom']);assert.deepEqual(M.touchedEdges(core),[]);
 assert.deepEqual(M.touchedEdges({name:'Top',type:'circle',cx:0,cy:1100,r:100}),['top']);
 assert.deepEqual(M.touchedEdges({name:'P',type:'polygon',points:[[1400,0],[1500,0],[1450,100]]}),['right']);
 assert.equal(M.insideShape({type:'circle',cx:0,cy:0,r:100},60,79),true);assert.equal(M.insideShape({type:'circle',cx:0,cy:0,r:100},60,81),false);
 const tri={type:'polygon',points:[[0,0],[100,0],[0,100]]};assert.equal(M.insideShape(tri,20,20),true);assert.equal(M.insideShape(tri,70,70),false);
 const noField={...gridRun([substrate],[()=>1]),field:undefined};assert.deepEqual(M.edgePlacement(noField),[]);
 const open={...gridRun([substrate],[()=>1]),settings:{boundary:'PML'}};
 const OR=await import(STATIC+'workspace-open-run.mjs');assert.equal(OR.isOpenRun(open),true,'the open fixture is an open run');assert.deepEqual(M.edgePlacement(open),[]);
 // the Results note row and the Compare note are drawn from edgeNotes
 const app=read('workspace-app.mjs');assert.ok(app.includes("id:'edge-note-'+m"));assert.ok(app.includes("id:'compare-edge-note'"));
});
test('U4: an unmatched row shows its best overlap below the threshold; the matching rule is unchanged',async()=>{
 const M=await import(STATIC+'workspace-match.mjs');
 assert.deepEqual([M.MATCH_THRESHOLD,M.MATCH_MARGIN],[0.8,0.1]);
 assert.equal(M.bestOverlapText({eta:0.0512,unit:[1]}),'best 0.05 (< 0.8, not matched)');
 // never printed as 0.80 below the threshold
 assert.equal(M.bestOverlapText({eta:0.7996,unit:[0]}),'best 0.799 (< 0.8, not matched)');
 // at or above the threshold an unmatched best was not clear of the next best
 assert.equal(M.bestOverlapText({eta:0.86,unit:[0]}),'best 0.86 (margin < 0.1, not matched)');
 assert.equal(M.bestOverlapText(null),'—');
 const app=read('workspace-app.mjs');assert.ok(app.includes("bestCell(r.best,r.kind==='a'?'B':'A')"));
});
test('U3: the slow options of the next run, beside Run study',async()=>{
 // round 18 (X2): the line names the whole run; the slow options carry their solve count after the last
 assert.equal(W.runPlanText({groupIndex:true,modeCount:2}),'Closed window · group index on (3 solves) · no timed run in this tab yet');
 assert.equal(W.runPlanText({open:true,pmlCheck:true,modeCount:2}),'Open boundary · 1 search · PML check on (3 solves) · no timed run in this tab yet');
 assert.equal(W.runPlanText({open:true,groupIndex:true,pmlCheck:true,modeCount:2}),'Open boundary · 1 search · group index on · PML check on (5 solves) · no timed run in this tab yet');
 assert.equal(W.runPlanText({modeCount:2}),'Closed window · no timed run in this tab yet');
 // the words of the Study line
 assert.ok(W.nextRunText(input(),2,true).includes(' · group index on'));
 assert.ok(read('workspace.html').includes('<button id="run-optical" disabled>Run study</button><div id="run-options" class="run-options" hidden><span id="run-plan" class="run-plan"></span><span id="run-drop" class="run-drop" hidden><span id="run-drop-text" class="run-drop-text"></span><button type="button" id="run-drop-pin" class="message-action"></button></span></div>'));
});
test('U5: the outer boundary is a choice: the workspace note and the closed Study panel say where',()=>{
 const app=read('workspace-app.mjs');
 assert.ok(app.includes('Shapes, materials, wavelength and core mesh editable; window fixed; outer boundary chosen in Physics › Optical modes.'));
 assert.ok(!app.includes('window/PEC fixed'));assert.ok(!app.includes('Window and boundaries are fixed.'));
 assert.equal(app.split('<p>The window is fixed; the outer boundary is chosen in Physics › Optical modes.').length,3);
});
test('U9: the Compare pickers are named Run A and Run B, with the full run label as their title',()=>{
 const app=read('workspace-app.mjs');
 assert.ok(app.includes("select.setAttribute('aria-label',side?'Run B':'Run A')"));
 assert.ok(app.includes("select.title=select.selectedOptions[0]?.textContent||''"));
});
test('U10: the toolbar Open… button is named by its visible text',()=>{
 const html=read('workspace.html');
 assert.ok(html.includes('title="Open a project, session or model file (Ctrl+O)" aria-label="Open…"'));
 assert.ok(!html.includes('aria-label="Open"'));
});
test('U11: a completed result loads in user words, the job id in the title',async()=>{
 const {OpticalJobMonitor}=await import(STATIC+'workspace-job.mjs');
 const states=[];const m=new OpticalJobMonitor({api:async path=>path.includes('/result?')?{}:{status:'done'},onState:s=>states.push(s),onResult:()=>{}});
 const pending={version:1,job:'65eb796b',serverInstance:'a'.repeat(32),serverVersion:'0.1.0',revision:3,startedAt:'2026-11-23T12:00:00Z',input:input()};await m.follow(pending,pending.serverInstance);
 const loading=states.find(s=>s.phase==='loading');
 assert.equal(loading.message,'Loading the result of this run…');assert.equal(loading.title,'Job 65eb796b');
});
test('U7: a model of the tab with runs lands on Results, else Model, at the top of the page',()=>{
 const app=read('workspace-app.mjs'),mp=read('workspace-multiphysics-view.mjs');
 assert.ok(app.includes("if(runs.length){if(!solverRun)solverRun=runs.at(-1);ui.page='Results';"));
 assert.ok(!app.includes("back.page==='Compare'&&runs.length>1"));
 assert.ok(mp.includes("function returnPage(){return lastRun&&resultPage?'Results':'Model';}"));
 assert.ok(app.includes("function topOfPage(){for(const id of ['canvas','inspector'])"));
});
test('U8: on the download path Save asks (Save As, prefilled) when the project models changed',()=>{
 const app=read('workspace-app.mjs');
 assert.ok(app.includes("if(result.status==='known'&&modelsChanged(target)){"));
 assert.ok(app.includes("const name=await askFileName(result.name,{saveAs:true,why:modelsChangedText(target,result.name)});"));
 // the file's models are recorded where it is written, opened or recovered
 assert.equal(app.split('project.file.models=models').length,2);assert.ok(app.includes("if(project.file)project.file.models=modelList();"));assert.ok(app.includes('savedAt:file.savedAt,models:modelList()'));
 // the picker path is unchanged: saveToFile writes a kept handle before any of this
 const files=read('workspace-files.mjs');assert.ok(files.includes("if (!saveAs && file?.handle) return 'write';"));
});
test('U6: browser recovery that cannot be kept says why and what to do',async()=>{
 const P=await import(STATIC+'workspace-persistence.mjs'),R=await import(STATIC+'workspace-notebook-recovery.mjs');
 assert.equal(P.persistenceTitle({runsUnsaved:true,recovery:'quota'}),'Not saved to a file · browser recovery unavailable: this browser’s storage is full · File › Save keeps your work');
 assert.equal(P.persistenceTitle({runsUnsaved:true,recovery:'overLimit'}),'Not saved to a file · browser recovery unavailable: session over 16 MiB · File › Save keeps your work');
 // a store whose write is refused for space, and an autosave whose snapshot is over the limit
 const states=[];const quota=new R.NotebookAutosave({save:async()=>{throw Object.assign(new Error('The quota has been exceeded.'),{name:'QuotaExceededError'});}},{onState:s=>states.push(s),setTimer:()=>0,clearTimer:()=>{}});
 quota.schedule('s1',()=>'{}');await quota.flush();
 const failed=states.find(s=>s.phase==='error');assert.equal(failed.code,'recovery-quota');assert.ok(failed.message.startsWith('This browser’s storage is full'));
 const over=[];const limit=new R.NotebookAutosave({save:async r=>r},{onState:s=>over.push(s),setTimer:()=>0,clearTimer:()=>{}});
 limit.schedule('s2',()=>{throw Object.assign(new Error('Recovery snapshot exceeds 16 MiB: x'),{code:'recovery-over-limit'});});await limit.flush();
 assert.equal(over.find(s=>s.phase==='error').code,'recovery-over-limit');
 // the optical snapshot over 16 MiB (the selected and pinned runs with their fields) carries its code
 const notebook=read('workspace-notebook.mjs');assert.ok(notebook.includes("{code:'recovery-over-limit'});return out.text;};"));
 const app=read('workspace-app.mjs');assert.ok(app.includes("state.code==='recovery-quota'?'quota':'unavailable'"));
});
