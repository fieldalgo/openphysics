// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Slice S3 of the guided / leaky notes of open-boundary modes: the notes of the modes table on
// stored runs (no solve). G9 (pre-registered in the design draft): every closed run of the session
// fixtures gets no category and no channel text, and its edge and core notes, and the run itself,
// are unchanged. Every open run of the fixtures is classified, with or without its field. The T16
// strings of the draft's §4.2 on the stored T16 run (optical-v10-open-f8ece10.json, written by
// Studio f8ece10, no field), and the template's guided strings. Plain text comparison only.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const DIR=path.join(__dirname,'studio_session_fixtures');
let C,M,N;
test.before(async()=>{C=await import(STATIC+'workspace-mode-channel.mjs');M=await import(STATIC+'workspace-modes.mjs');N=await import(STATIC+'workspace-notebook.mjs');});

// every run record in the JSON fixtures (sessions, projects, recovery files), as the file holds it
function fixtureRuns(){
 const runs=[];
 const walk=(o,file)=>{if(Array.isArray(o))o.forEach(x=>walk(x,file));else if(o&&typeof o==='object'){if(o.settings&&o.effective_index&&o.input)runs.push({file,run:o});else Object.values(o).forEach(x=>walk(x,file));}};
 for(const file of fs.readdirSync(DIR).filter(f=>f.endsWith('.json')).sort())walk(JSON.parse(fs.readFileSync(path.join(DIR,file),'utf8')),file);
 return runs;
}
// the runs of every optical session fixture as the page reads them (parseSession)
function pageRuns(){
 const runs=[];
 for(const file of fs.readdirSync(DIR).filter(f=>f.endsWith('.json')).sort()){
  const text=fs.readFileSync(path.join(DIR,file),'utf8'),data=JSON.parse(text);
  if(data.format!=='openphysics-studio-session'||data.application==='multiphysics')continue;
  const session=N.parseSession(text);
  for(const run of session.runs)runs.push({file,run});
 }
 return runs;
}
// the modes table's notes as workspace-app.mjs builds them
function tableNotes(run){
 const regions=M.openRegionNotes(run);
 const edge=new Map([...M.edgeNotes(run),...regions.filter(n=>n.kind==='edge')].map(n=>[n.mode,n.text]));
 const core=new Map([...M.coreNotes(run),...regions.filter(n=>n.kind==='core')].map(n=>[n.mode,n.text]));
 const before={edge:[...edge],core:[...core]};
 const alone=C.placeChannelNotes(run,edge,core);
 return {before,edge:[...edge],core:[...core],alone:[...alone]};
}
const LEAKY=(head,x)=>`${head} is a leaky mode: Re n_eff ${x} is below the index of Substrate (3.478), which reaches the open window edge, so light can leak into Substrate. The loss shown is that leakage; it is part of this structure, not a fault of the solve.`;
const GUIDED=(head,x)=>`${head} is guided: Re n_eff ${x} is above the index of every material at the open window edges (the highest is the silica background, 1.444), so it cannot leak. The loss shown is numerical (mesh and PML), not leakage.`;

test('G9: a closed run of the session fixtures gets no category text; its notes and the run are unchanged',()=>{
 // as the page reads them, and every closed run record of every fixture as its file holds it
 const page=pageRuns(),closed=[...page,...fixtureRuns()].filter(r=>r.run.settings.boundary!=='PML');
 assert.equal(page.filter(r=>r.run.settings.boundary!=='PML').length,38);assert.ok(closed.length>=97,`${closed.length} closed runs`);
 let withNotes=0;
 for(const {file,run} of closed){
  const text=JSON.stringify(run);
  assert.deepEqual(C.modeChannel(run),[],file);assert.deepEqual(C.channelNotes(run),[],file);
  const t=tableNotes(run);
  assert.deepEqual(t.alone,[],file);assert.deepEqual(t.edge,t.before.edge,file);assert.deepEqual(t.core,t.before.core,file);
  if(t.edge.length||t.core.length)withNotes++;
  assert.equal(JSON.stringify(run),text,`${file}: the run is not changed`);
 }
 console.log(`G9: ${closed.length} closed runs, ${withNotes} with edge or core notes, unchanged`);
 // the stored closed runs have no edge note: a closed run with one (round 25's synthetic field, the
 // closed window's thresholds) keeps it exactly
 const at={core:[0,110],substrateEdge:[0,-1100]},X=[],T=[];
 for(const [x,y] of Object.values(at)){const n=X.length;X.push([(x-1)*1e-9,(y-1)*1e-9],[(x+2)*1e-9,(y-1)*1e-9],[(x-1)*1e-9,(y+2)*1e-9]);T.push([n,n+1,n+2]);}
 const synthetic={settings:{adapter:'optical-shapes-v8',boundary:'PEC',vacuum_wavelength:'1550 nm'},input:{model:{wavelength:1550,shapes:[{type:'rect',name:'Core',material:'Silicon',x:-250,y:0,w:500,h:220},{type:'rect',name:'Substrate',material:'Silicon',x:-1500,y:-1200,w:3000,h:700}]}},
  effective_index:[2.9,2.44],field:{node_coordinates:X,triangles:T,real:[[[0.1,0,0],[1,0,0]],[[1,0,0],[0.1,0,0]]],imag:[[[0,0,0],[0,0,0]],[[0,0,0],[0,0,0]]]}};
 const t=tableNotes(synthetic);
 assert.deepEqual(t.edge.map(([m])=>m),[0]);assert.ok(t.edge[0][1].startsWith('Mode 1 is mostly in Substrate ('));
 assert.deepEqual(t.edge,t.before.edge);assert.deepEqual(t.core,t.before.core);assert.deepEqual(t.alone,[]);
});

test('G9: the page adds channel rows only from placeChannelNotes, after the region notes as they were',()=>{
 const app=fs.readFileSync(path.join(__dirname,STATIC,'workspace-app.mjs'),'utf8');
 // round 25's maps are built as before, then the channel text is placed
 assert.ok(app.includes("const regions=openRegionNotes(run),edge=new Map([...edgeNotes(run),...regions.filter(n=>n.kind==='edge')].map(n=>[n.mode,n.text])),core=new Map([...coreNotes(run),...regions.filter(n=>n.kind==='core')].map(n=>[n.mode,n.text])),pending=[];let spanEnd=-1;\n // open-mode notes (slice S3)"));
 assert.ok(app.includes(" const channel=placeChannelNotes(run,edge,core);\n"));
 assert.equal(app.split('placeChannelNotes(').length-1,1);
 assert.ok(app.includes("if(channel.has(m-1)){const note=document.createElement('tr');note.className='edge-note-row channel-note-row';const td=cell('td',channel.get(m-1).text,{colspan:String(head.children.length),id:'channel-note-'+m,'data-channel-note':String(m),'data-channel-kind':channel.get(m-1).kind,class:'edge-note'});"));
});

test('every open run of the fixtures is classified, with or without its field',()=>{
 const open=pageRuns().filter(r=>r.run.settings.boundary==='PML');
 assert.equal(open.length,6);assert.ok(open.some(r=>r.run.field)&&open.some(r=>!r.run.field));
 for(const {file,run} of open){
  const c=C.modeChannel(run);
  assert.equal(c.length,run.effective_index.length,file);
  const substrate=run.input.model.shapes.some(s=>s.name==='Substrate');
  assert.deepEqual(c.map(m=>m.kind),c.map(()=>substrate?'leaky':'guided'),file);
  // the guard agrees with the loss on each (the gain bound of the stored pml_l2_fraction)
  assert.deepEqual(c.map(m=>m.resolved),c.map(()=>substrate),file);
  // the file's form of the same run reads the same
  const raw=fixtureRuns().find(r=>r.file===file&&r.run.job===run.job).run;
  assert.deepEqual(C.modeChannel(raw).map(m=>[m.kind,m.x,m.im,m.bound]),c.map(m=>[m.kind,m.x,m.im,m.bound]),file);
 }
});

test('§4.2 on the stored T16 run (no field): modes 1 and 2 leaky into Substrate, each a note of its own',()=>{
 const runs=N.parseSession(fs.readFileSync(path.join(DIR,'optical-v10-open-f8ece10.json'),'utf8')).runs,t16=runs[2];
 assert.deepEqual(t16.input.model.shapes.map(s=>s.name),['Core','Substrate']);assert.ok(!t16.field);
 assert.deepEqual(C.channelNotes(t16).map(n=>[n.mode,n.kind,n.text]),[[0,'leaky',LEAKY('Mode 1','2.441')],[1,'leaky',LEAKY('Mode 2','1.773')]]);
 const t=tableNotes(t16);
 assert.deepEqual([t.edge,t.core],[[],[]]);
 assert.deepEqual(t.alone,[[0,{kind:'leaky',text:LEAKY('Mode 1','2.441')}],[1,{kind:'leaky',text:LEAKY('Mode 2','1.773')}]]);
 // the template of the same file: guided, its loss within the gain bound
 const template=runs[0];
 assert.deepEqual(C.channelNotes(template).map(n=>n.text),[GUIDED('Mode 1','2.443'),GUIDED('Mode 2','1.770')]);
});

test('a stored open run with its field: a note of its own without a region note, else after it in the same note',()=>{
 // the coarse T16 run of optical-v14-compact.json (776 triangles): Core holds 49 % of mode 1, so no
 // mode is named by its region and each channel text is a note of its own
 const run=N.parseSession(fs.readFileSync(path.join(DIR,'optical-v14-compact.json'),'utf8')).runs[0];
 assert.ok(run.field);
 const t=tableNotes(run),x=C.modeChannel(run).map(c=>c.x.toFixed(3));
 assert.deepEqual([t.before.edge,t.before.core],[[],[]]);
 assert.deepEqual(t.alone,x.map((v,mode)=>[mode,{kind:'leaky',text:LEAKY(`Mode ${mode+1}`,v)}]));
 // with a region note for mode 1 (as G1's real run has), the text follows it and mode 2 stays alone
 const core=new Map([[0,'Mode 1 is the core mode: 64 % of |E|² in the window (PML excluded) is in Core, which does not touch the window edge.']]),edge=new Map();
 const alone=C.placeChannelNotes(run,edge,core);
 assert.deepEqual([...core],[[0,'Mode 1 is the core mode: 64 % of |E|² in the window (PML excluded) is in Core, which does not touch the window edge. '+LEAKY('It',x[0])]]);
 assert.deepEqual([...edge],[]);assert.deepEqual([...alone],[[1,{kind:'leaky',text:LEAKY('Mode 2',x[1])}]]);
 // an edge note takes it the same way
 const e2=new Map([[1,'Mode 2 is mostly in Substrate (93 % of |E|² in the window, PML excluded), which continues into the PML at the open window edge.']]);
 C.placeChannelNotes(run,e2,new Map());
 assert.equal(e2.get(1),'Mode 2 is mostly in Substrate (93 % of |E|² in the window, PML excluded), which continues into the PML at the open window edge. '+LEAKY('It',x[1]));
});
