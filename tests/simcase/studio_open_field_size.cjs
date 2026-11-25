// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Field size of open-boundary runs, slice S1: a new open run keeps its samples on the physical
// window only (crop rule C5'': the triangles that meet the closed physical_bounds grown on each side
// by 1/150 of its longer side, in order, nodes renumbered in first-use order, no value changed); a run read from a file is never cropped (C2);
// a full and a cropped copy of one job merge (C3); no bounds, no crop (C6).
// The fixture optical-v10-open-full-083e151.json is a P3-era file: Studio 083e151 wrote it from the
// T16 structure (a strip over a substrate, open on four edges, both searches, 2 modes) with every
// element length × 8 (776 triangles). Its settings still read core mesh 30 nm: the
// mesh was scaled after the builder so the fixture stays small (tools/studio_open_field_size.mjs
// measures the real T16 and T19). Plain text comparison only: no RegExp is built from a dynamic string.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const fixture=name=>fs.readFileSync(path.join(__dirname,'studio_session_fixtures',name),'utf8');
const FULL='optical-v10-open-full-083e151.json';
// the triangles of the fixture's run that meet its window grown by 20 nm
const COUNT=315;
let F,M,N,R,X;
test.before(async()=>{F=await import(STATIC+'workspace-field.mjs');M=await import(STATIC+'workspace-modes.mjs');N=await import(STATIC+'workspace-notebook.mjs');R=await import(STATIC+'workspace-open-run.mjs');X=await import(STATIC+'workspace-match.mjs');});

const W=[[-1,-1],[1,1]];
const meets=(points)=>F.meetsWindow({node_coordinates:points,triangles:[[0,1,2]]},W)[0];

test('meetsWindow: the separating-axis test against the closed window',()=>{
 assert.equal(meets([[-0.5,-0.5],[0.5,-0.5],[0,0.5]]),true,'inside');
 assert.equal(meets([[0.5,0.5],[3,0.5],[0.5,3]]),true,'crossing an edge');
 // touching only: at a corner, along an edge (closed bounds)
 assert.equal(meets([[1,1],[2,1],[1,2]]),true,'a corner only');
 assert.equal(meets([[1,-0.5],[2,-0.5],[1,0.5]]),true,'along an edge');
 assert.equal(meets([[1,0],[2,-0.5],[2,0.5]]),true,'a vertex on an edge');
 // outside, its bounding box overlapping the window: the edge-normal axis separates it
 assert.equal(meets([[0.5,1.6],[1.6,0.5],[1.6,1.6]]),false,'beyond the corner');
 assert.equal(meets([[0.9,3],[3,0.9],[3,3]]),false,'beyond the corner, overlapping box');
 assert.equal(meets([[1.0000001,0],[2,-1],[2,1]]),false,'just outside an edge');
 // one that contains the whole window
 assert.equal(meets([[-10,-10],[10,-10],[0,10]]),true,'containing the window');
 // each orientation gives the same answer
 for(const p of [[[0.5,1.6],[1.6,0.5],[1.6,1.6]],[[1,1],[2,1],[1,2]],[[-10,-10],[10,-10],[0,10]]])assert.equal(meets([...p].reverse()),meets(p));
});

test('windowField: C5\'\' keeps the triangles in order, renumbers nodes in first use, changes no value',()=>{
 // nodes 0..6; triangle 1 lies outside, the others meet the window
 const field={node_coordinates:[[5,5],[0,0],[0.5,0],[0,0.5],[6,5],[5,6],[1,1]],triangles:[[1,2,3],[0,4,5],[2,6,3],[6,0,2]],
  real:[[[1,2,3],[4,5,6],[7,8,9],[-0,1e-300,5e-324]]],imag:[[[0,0,1],[2,2,2],[3,3,3],[4,4,4]]],regions:[1,2,1,2]};
 const kept=F.windowField(field,W);
 assert.deepEqual(kept.triangles,[[0,1,2],[1,3,2],[3,4,1]]);
 assert.deepEqual(kept.node_coordinates,[[0,0],[0.5,0],[0,0.5],[1,1],[5,5]]);
 assert.deepEqual(kept.real,[[[1,2,3],[7,8,9],[-0,1e-300,5e-324]]]);assert.equal(Object.is(kept.real[0][2][0],-0),true);
 assert.deepEqual(kept.imag,[[[0,0,1],[3,3,3],[4,4,4]]]);assert.deepEqual(kept.regions,[1,1,2]);
 // the same coordinate arrays: no value is recomputed
 assert.equal(kept.node_coordinates[4],field.node_coordinates[0]);
 // cropping again changes nothing
 assert.deepEqual(F.windowField(kept,W),kept);
});

test('C5\'\': the window grown by 1/150 of its longer side; a triangle within the margin is kept',()=>{
 // W is 2 × 2: the margin is 2/150
 const d=F.windowMargin(W);assert.equal(d,2/150);assert.equal(F.windowMargin([[-1.5e-6,-1.2e-6],[1.5e-6,1.2e-6]]),3e-6/150);
 const crop=p=>F.windowField({node_coordinates:p,triangles:[[0,1,2]],real:[[[1,2,3]]],imag:[[[4,5,6]]]},W).triangles.length;
 assert.equal(crop([[1+d/2,0],[2,-0.5],[2,0.5]]),1,'within the margin');
 assert.equal(crop([[1+d,0],[2,-0.5],[2,0.5]]),1,'on the margin');
 assert.equal(crop([[1+2*d,0],[2,-0.5],[2,0.5]]),0,'beyond the margin');
 assert.equal(crop([[0.5,1.6+d],[1.6+d,0.5],[2,2]]),0,'beyond the grown corner, its box overlapping');
 assert.equal(crop([[1+d/2,1+d/2],[2,1+d/2],[1+d/2,2]]),1,'inside the grown corner');
});

// the result the server sends for the fixture's run: its full samples, its record, its indices
function resultOf(run){
 return {node_coordinates:run.field.node_coordinates,field_units:{node_coordinates:'m'},triangles:run.field.triangles,
  vector_fields:[{...F.PML_FIELD_METADATA,real:run.field.real,imag:run.field.imag}],
  summary:{open_boundary:[run.open_boundary]}};
}

test('a new open result keeps the window only; the physical window and its values are unchanged',()=>{
 const session=N.parseSession(fixture(FULL)),run=session.runs[0];
 assert.equal(run.field.triangles.length,776,'C2: a run read from a file keeps its full samples');
 const result=resultOf(run),re=run.effective_index,im=run.effective_index_im;
 const open=R.openResultValues(result,re,im,Number(run.settings.pml.target));
 const bounds=M.physicalBounds(run.open_boundary),window=F.windowField(run.field,bounds);
 assert.equal(open.data.triangles.length,COUNT);
 assert.ok(open.data.triangles.length<776);
 // C3: cropping the cropped samples again changes nothing
 assert.deepEqual(F.windowField(window,bounds),window);
 assert.deepEqual(open.data.triangles,window.triangles);assert.deepEqual(open.data.node_coordinates,window.node_coordinates);
 assert.deepEqual(open.data.vector_fields[0].real,window.real);assert.deepEqual(open.data.vector_fields[0].imag,window.imag);
 const field=F.readOpticalField(open.data,re.length,{open:true});
 // every window triangle (centroid rule) is kept: the window's TE fraction, A_eff and |E| are bit for bit
 const before=M.physicalWindow(run.field,bounds),after=M.physicalWindow(field,bounds);
 assert.equal(after.filter(Boolean).length,before.filter(Boolean).length);
 for(let i=0;i<re.length;i++){
  assert.equal(Object.is(M.teFraction(field,i,after),M.teFraction(run.field,i,before)),true);
  assert.equal(Object.is(M.effectiveArea(field,i,after),M.effectiveArea(run.field,i,before)),true);
  for(const c of ['magnitude','Ex','Ey','Ez']){
   const a=F.fieldScalars(run.field,i,c),b=F.fieldScalars(field,i,c);assert.equal(Object.is(a.maximum,b.maximum),true);
   const inside=a.values.filter((_,k)=>before[k]),kept=b.values.filter((_,k)=>after[k]);assert.deepEqual(kept,inside);
  }
 }
 // C6: without valid bounds the samples are kept whole
 for(const record of [{...run.open_boundary,physical_bounds:undefined},{...run.open_boundary,physical_bounds:{unit:'um',values:run.open_boundary.physical_bounds.values}}]){
  const whole=R.openResultValues({...result,summary:{open_boundary:[record]}},re,im,Number(run.settings.pml.target));
  assert.equal(whole.data.triangles,result.triangles);assert.equal(whole.data.node_coordinates.length,run.field.node_coordinates.length);
 }
});

test('C2/F7: a P3-era file with full samples is read and written again byte for byte',()=>{
 const text=fixture(FULL),s=N.parseSession(text);
 const once=N.sessionText(s.input,s.runs,s.selected,s.comparison,s.view),again=N.parseSession(once);
 assert.equal(JSON.parse(once).runs[0].field.triangles.length,776);
 assert.equal(N.sessionText(again.input,again.runs,again.selected,again.comparison,again.view),once);
 // the file was written by the page (origin local); read, it is imported and the rest is the same
 const strip=t=>{const d=JSON.parse(t);return JSON.stringify({...d,runs:d.runs.map(({origin,digest,...r})=>r)});};
 assert.equal(strip(once),strip(text));
});

test('C3: a full and a cropped copy of one job merge; the copy in the tab is kept',()=>{
 const full=N.parseSession(fixture(FULL)).runs[0],bounds=M.physicalBounds(full.open_boundary),w=F.windowField(full.field,bounds);
 const cropped=N.validateRun({...full,field:F.readOpticalField({node_coordinates:w.node_coordinates,field_units:{node_coordinates:'m'},triangles:w.triangles,vector_fields:[{...F.PML_FIELD_METADATA,real:w.real,imag:w.imag}]},w.real.length,{open:true}),
  effective_index:{re:full.effective_index,im:full.effective_index_im}},true,{format:10});
 assert.equal(cropped.field.triangles.length,COUNT);
 for(const [tab,file] of [[cropped,full],[full,cropped]]){
  const merged=N.mergeRuns([tab],[file]);assert.deepEqual(merged.reused,[full.job]);assert.deepEqual(merged.added,[]);assert.equal(merged.runs[0],tab);
 }
 // a sample that differs inside the window conflicts; one outside it (in the PML) does not
 const d=F.windowMargin(bounds),grown=F.meetsWindow(full.field,[[bounds[0][0]-d,bounds[0][1]-d],[bounds[1][0]+d,bounds[1][1]+d]]);
 const k=M.physicalWindow(full.field,bounds).indexOf(true),out=grown.indexOf(false);
 const changed=index=>({...full,field:{...full.field,real:full.field.real.map((m,j)=>j?m:m.map((v,i)=>i===index?[v[0]+1,v[1],v[2]]:v))}});
 assert.throws(()=>N.mergeRuns([cropped],[changed(k)]),{message:'Conflicting result for job '+full.job+'. Existing notebook kept.'});
 assert.ok(out>=0);assert.deepEqual(N.mergeRuns([cropped],[changed(out)]).reused,[full.job]);
 // closed runs compare their samples whole, as before
 const closed=N.parseSession(fixture('optical-v7-one.json')).runs[0];
 assert.deepEqual(N.mergeRuns([closed],[closed]).reused,[closed.job]);
});

test('matching an open run reads the same window from its cropped copy',()=>{
 const full=N.parseSession(fixture(FULL)).runs[0],bounds=M.physicalBounds(full.open_boundary),w=F.windowField(full.field,bounds);
 const cropped={...full,field:{...full.field,node_coordinates:w.node_coordinates,nodes:w.node_coordinates.map(p=>p.map(v=>v*1e6)),triangles:w.triangles,real:w.real,imag:w.imag}};
 const a=X.matchSide(full),b=X.matchSide(cropped);
 assert.deepEqual(b.field.triangles.map(t=>t.map(n=>b.field.node_coordinates[n])),a.field.triangles.map(t=>t.map(n=>a.field.node_coordinates[n])));
 assert.deepEqual([b.field.real,b.field.imag,b.window],[a.field.real,a.field.imag,a.window]);
});

test('A1: the run file of an open run says its fields cover the physical window only',()=>{
 const app=fs.readFileSync(path.join(__dirname,STATIC,'workspace-app.mjs'),'utf8');
 assert.ok(app.includes("with the run's inputs and fields${isOpenRun(solverRun)?' (on the physical window only, PML excluded)':''}. Add runs from file adds it to a session."));
});

test('A3: the refusal names the selected and the pinned runs apart; Unpin only with a pinned run',()=>{
 const t=kept=>N.keptOverText(kept,18.9e6);
 assert.equal(t([{name:'Run 6',selected:true,pinned:false}]),'The selected run (Run 6) is 18.9 MB with its fields, over the 16.8 MB session limit. Select a different run before saving, so this one is saved without its fields, or run it again with fewer modes.');
 assert.equal(t([{name:'Run 4',pinned:true},{name:'Run 5',pinned:true},{name:'Run 6',selected:true,pinned:false}]),'The selected run (Run 6) and the pinned runs (Run 4, Run 5) are 18.9 MB with their fields, over the 16.8 MB session limit. Unpin some of them.');
 assert.equal(t([{name:'Run 4',pinned:true},{name:'Run 6',selected:true,pinned:true}]),'The pinned runs (Run 4, Run 6 selected) are 18.9 MB with their fields, over the 16.8 MB session limit. Unpin some of them.');
 assert.equal(t([{name:'Run 4',pinned:true}]),'The pinned run (Run 4) is 18.9 MB with its fields, over the 16.8 MB session limit. Unpin it.');
 // Save session and browser recovery: one helper, the same words
 const full=N.parseSession(fixture(FULL)),run={...full.runs[0],pinned:false},view=full.view;
 const out=N.writeOpticalSession(full.input,[run],run.job,[run.job,null],view,{limit:1000,keepSelected:true});
 assert.equal(out.ok,false);assert.equal(out.refusal,N.keptOverText([{name:'Run 1',selected:true,pinned:false}],out.bytes));
 assert.ok(out.refusal.startsWith('The selected run (Run 1) is ')&&out.refusal.endsWith(' Select a different run before saving, so this one is saved without its fields, or run it again with fewer modes.'),out.refusal);
 const src=fs.readFileSync(path.join(__dirname,STATIC,'workspace-notebook.mjs'),'utf8');
 assert.ok(src.includes("new Error('Recovery snapshot exceeds 16 MiB: '+out.refusal[0].toLowerCase()+out.refusal.slice(1))"));
});

test('S2: a run that makes the session go over 16 MiB says the size and what File › Save will do',()=>{
 assert.equal(N.sessionSizeText({ok:true,bytes:1e6}),null);assert.equal(N.sessionSizeText(null),null);
 assert.equal(N.sessionSizeText({ok:false,bytes:18.9e6,reduced:{bytes:9e6,notKept:[1]},refusal:null}),
  'Session is now 18.9 MB, over the 16.8 MB limit. File › Save will ask whether to keep the field plots of the selected and pinned runs only.');
 const refusal=N.keptOverText([{name:'Run 6',selected:true,pinned:false}],18.9e6);
 assert.equal(N.sessionSizeText({ok:false,bytes:48.8e6,reduced:null,refusal}),
  'Session is now 48.8 MB, over the 16.8 MB limit, and File › Save will refuse: The selected run (Run 6) is 18.9 MB with its fields, over the 16.8 MB session limit. Select a different run before saving, so this one is saved without its fields, or run it again with fewer modes. Browser recovery is off.');
 // the same answer Save session gets: a run's session over the limit, its selected run alone fitting
 const full=N.parseSession(fixture(FULL)),run={...full.runs[0],pinned:false},other={...run,job:'0000000f',pinned:false};
 const out=N.writeOpticalSession(full.input,[run,other],run.job,[run.job,null],full.view,{limit:400000});
 assert.equal(out.ok,false);assert.ok(N.sessionSizeText(out).endsWith(', over the 16.8 MB limit. File › Save will ask whether to keep the field plots of the selected and pinned runs only (Run 1).'),N.sessionSizeText(out));
 const app=fs.readFileSync(path.join(__dirname,STATIC,'workspace-app.mjs'),'utf8');
 // posted once after the run's result message, with X4's line not repeated when it says recovery is off
 assert.ok(app.includes("if(state.phase==='done')announceResult(state.message,swapAction());else notice(state.message);if(state.phase==='done'&&sessionSizePending)postSessionSize();"));
 assert.ok(app.includes("compareIds=comparisonAfterRun(runs,compareIds,comparePicked);ui.page='Results';sessionSizePending=true;"));
 assert.ok(app.includes("if(!text)return;if(text.endsWith(' Browser recovery is off.'))recoveryOffPosted='overLimit';"));
 assert.ok(app.includes("const host=$('file-status');if(resultNotice&&host.textContent){host.append(' '+text);}else notice(text);\n}"));
});
