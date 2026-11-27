// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Round 38 (agent proxy round 38 on main 6774012): what Compare shows in its first view at 1440 × 900.
// D4: in T18 the agents who pressed "Run as set" saw "No matched modes" and the top of the plots;
// the round-37 D3 button "Set search near 2.46 · 4 modes" sat below the plots, in the description,
// and named neither the run nor what it does there. When Compare has no matched modes and a closed
// run has no core mode (noMatchCoreSearch), one line under the Matched modes toolbar, above the
// plots, now says "A · Run 2 has no core mode: its modes are mostly in Substrate, which touches the
// window edge." with that button, labelled "Use Run 2's inputs with search near 2.46 · 4 modes"; its
// id and action (useRunClosedSearch) are unchanged. The description keeps its edge reason and its
// "Open Run 2 in Results" link. The matching, mode numbers, values, file formats and the dialog are
// unchanged. Plain text comparison only: no RegExp is built from a dynamic string.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const read=name=>fs.readFileSync(path.join(__dirname,STATIC,name),'utf8');
let N,P,M,C,X;
test.before(async()=>{
 N=await import(STATIC+'workspace-notebook.mjs');P=await import(STATIC+'workspace-project.mjs');
 M=await import(STATIC+'workspace-modes.mjs');C=await import(STATIC+'workspace-closed-target.mjs');X=await import(STATIC+'workspace-match.mjs');
});
const setup=()=>({materials:{Core:'Silicon',Oxide:'Silica',Heater:''},temperature:293.15,cooling:'',fixed:'',terminal:''});
const CORE={name:'Core',type:'rect',material:'Silicon',x:-250,y:0,w:500,h:220};
const SUBSTRATE={name:'Substrate',type:'rect',material:'Silicon',x:-1500,y:-1200,w:3000,h:700};
const input=shapes=>P.snapshot({width:500,voltage:1,electric:false,heat:false,structure:false,optics:true,wavelength:1550,coreMesh:30,...(shapes?{shapes}:{})},setup());
// two triangles, one in the core and one in the substrate; inCore: per mode, whether its |E|² is in the core
const twoTriangles=inCore=>({node_coordinates:[[-2e-7,1e-8],[2e-7,1e-8],[0,2e-7],[-1.4e-6,-1.1e-6],[1.4e-6,-1.1e-6],[0,-6e-7]],triangles:[[0,1,2],[3,4,5]],
 real:inCore.map(c=>c?[[1,0,0],[0.1,0,0]]:[[0,0,0],[1,0,0]]),imag:inCore.map(()=>[[0,0,0],[0,0,0]])});
const closedRun=(job,re,inCore,{target=2.46,shapes=[CORE,SUBSTRATE]}={})=>N.validateRun({job,completedAt:'2026-11-27T01:00:00.000Z',
 settings:target===null?N.opticalSettings(1550,30,re.length):N.closedTargetSettings(N.opticalSettings(1550,30,re.length),target),input:input(shapes),
 effective_index:re,field:twoTriangles(inCore),origin:'local',serverVersion:'0.0.0',te_polarization_fraction:re.map(()=>0.99),effective_area:re.map(()=>1e-13)});

test('D4: the line says why the closed run as set has no core mode, in the edge wording',()=>{
 const asSet=closedRun('0000000b',[2.6,2.5],[false,false],{target:null});
 assert.equal(M.noMatchCoreSearch(asSet),2.46);
 assert.equal(M.noCoreModeText('A','Run 2',M.firstModeEdgeShape(asSet)),'A · Run 2 has no core mode: its modes are mostly in Substrate, which touches the window edge.');
 assert.equal(M.noCoreModeText('B','Run 6 · Wide','Substrate'),'B · Run 6 · Wide has no core mode: its modes are mostly in Substrate, which touches the window edge.');
 // the description's reason (round 22, V3) is unchanged
 assert.equal(M.noMatchEdgeText('A','Run 2','Substrate'),'A · Run 2: its modes are mostly in Substrate, which touches the window edge; the core mode was not found.');
});

test('D4: the button names the run and what it does; the shortcut and the dialog keep their words',()=>{
 assert.equal(C.runShortcutText(2,2.46),"Use Run 2's inputs with search near 2.46 · 4 modes");
 assert.equal(C.runShortcutText(6,2.46),"Use Run 6's inputs with search near 2.46 · 4 modes");
 assert.equal(C.shortcutText(2.46),'Set search near 2.46 · 4 modes');
 assert.deepEqual(C.slabQuestionButtons(2.46),['Set search near 2.46 · 4 modes and run','Run as set','Cancel']);
});

test('D4: Compare puts the line and its one button above the plots, with the D3 id and action',()=>{
 const app=read('workspace-app.mjs');
 const body=app.slice(app.indexOf('function renderComparison('),app.indexOf('\nlet pendingRunImport'));
 // one line per side, under the conditions of D3 (no matched mode, the run's mode-1 edge note, noMatchCoreSearch)
 assert.ok(body.includes("if(!chosen&&!match.disabled&&!match.error)[['A',a],['B',b]].forEach(([side,run],i)=>{if(i&&a.job===b.job)return;const shape=firstModeEdgeShape(run);if(!shape)return;"));
 assert.ok(body.includes("const near=noMatchCoreSearch(run);if(near!=null){const line=document.createElement('p');line.className='compare-first-line';line.id='compare-core-search-line-'+side.toLowerCase();line.append(noCoreModeText(side,runNumberTitle(run),shape),' ');"));
 assert.ok(body.includes("search.id='compare-core-search-'+side.toLowerCase();search.textContent=runShortcutText(runNumber(run),near);search.onclick=()=>useRunClosedSearch(run,near);line.append(search);firstLines.push(line);"));
 // one button: none left in the description
 assert.equal(body.split("search.id='compare-core-search-'").length,2);
 assert.ok(!body.includes("description.append(' ',search)"));
 // the description keeps its reason and link
 assert.ok(body.includes("reason.textContent=noMatchEdgeText(side,runNumberTitle(run),shape);"));
 assert.ok(body.includes("description.append(description.textContent.endsWith(' ')?'':' ',reason,' ',link,'.');"));
 // the lines between the toolbar and the plots
 assert.ok(body.includes("host.append(...firstLines,grid,description);"));
 assert.ok(body.indexOf('host.append(opts);')<body.indexOf('host.append(...firstLines,grid,description);'));
 // the action is the round-37 one: Use this run's inputs, the shortcut, the Model page; nothing runs
 assert.ok(app.includes("function useRunClosedSearch(run,t){if(!useRunInputs(run))return;ui.page='Model';render();useClosedSearch(t);}"));
});

test('D4: opening Compare never scrolls the first-view lines out of the pane',()=>{
 const app=read('workspace-app.mjs');
 const body=app.slice(app.indexOf('function frameComparePlots('),app.indexOf('function renderComparison('));
 assert.ok(body.includes("const first=pane.querySelector('.compare-first-line')??grid;"));
 assert.ok(body.includes("room=first.getBoundingClientRect().top-box.top;"));
 assert.ok(body.includes("if(need>0)pane.scrollTop+=Math.min(need,Math.max(0,room));"));
 assert.ok(read('workspace.css').includes('.compare-first-line{'));
});
