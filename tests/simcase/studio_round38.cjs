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

// Round 38 (C2): in T18 the agents who got the core pair said that "first mode" in Compare means
// different things in the two runs: the first view showed "A mode 3 (core) ↔ B mode 1 (core)" and the
// plots, with nothing near the top saying what A's mode 1 is or why it has no match. When the chosen
// pair is a core pair and a run's mode 1 is not a core mode, is an edge-shape mode and is in no
// accepted pair, one line in the same place says so: "Mode 1 of A · Run 3 is a Substrate mode and
// matches no mode of B; the core modes are A mode 3 ↔ B mode 1." The table's "Core modes" line
// (round 36, C1) is unchanged.
// T18 closed, "Set search near 2.46 · 4 modes": modes 1, 2 and 4 in the substrate, mode 3 the core mode
const T18_NEAR=[2.6,2.5,2.43931663,2.40];
// an open run (the round-25 P4 fixture): each mode's |E|² per region of the window and in the PML
function openRun(modes){
 const at={core:[0,110],cladding:[0,800],substrate:[0,-800],substrateEdge:[0,-1100],pml:[0,-1700]},X0=[],T=[],keys=Object.keys(at);
 for(const k of keys){const [x,y]=at[k],d=1,n=X0.length;X0.push([(x-d)*1e-9,(y-d)*1e-9],[(x+2*d)*1e-9,(y-d)*1e-9],[(x-d)*1e-9,(y+2*d)*1e-9]);T.push([n,n+1,n+2]);}
 const value=w=>[Math.sqrt(w),0,0];
 return {settings:{boundary:'PML',pml:{thickness:'1000 nm',open_edges:['left','right','bottom','top'],target:'2.46'}},
  input:{model:{shapes:[CORE,{...SUBSTRATE,material:'Silica'}]}},
  effective_index:modes.map((_,i)=>2.44-0.1*i),te_polarization_fraction:modes.map(()=>0.99),
  field:{node_coordinates:X0,triangles:T,real:modes.map(m=>keys.map(k=>value(m[k]??0))),imag:modes.map(()=>keys.map(()=>[0,0,0]))}};
}
// mode 1 the core mode, mode 2 mostly in the substrate near its edge
const T18_OPEN=[{core:0.6,substrate:0.2,cladding:0.2,pml:10},{substrateEdge:0.7,core:0.1,cladding:0.2,pml:5}];
const pair=(a,b,eta,unitA=[a],unitB=[b])=>({a,b,unitA,unitB,eta,accepted:true,rowNext:0,columnNext:0,delta:-0.005});
const matchOf=pairs=>({pairs,rows:[],unmatchedB:[]});
const TITLES={a:'Run 3',b:'Run 4'};

test('C2: the core pair chosen and A\'s mode 1 a Substrate mode with no match: one line says so',()=>{
 const a=closedRun('0000000a',T18_NEAR,[false,false,true,false]),b=openRun(T18_OPEN);
 assert.equal(M.firstModeEdgeShape(a),'Substrate');assert.deepEqual([...M.coreModes(a)],[2]);assert.deepEqual([...M.coreModes(b)],[0]);
 const m=matchOf([pair(2,0,0.993)]);
 assert.deepEqual(X.firstModeLines(m,{a,b},{a:2,b:0},TITLES),[{side:'A',text:'Mode 1 of A · Run 3 is a Substrate mode and matches no mode of B; the core modes are A mode 3 ↔ B mode 1.'}]);
 // the table's line (round 36, C1) is unchanged
 assert.equal(X.coreMatchText(m,{a,b}),'Core modes: A mode 3 ↔ B mode 1 · overlap 0.99');
 // the sides swapped: the line names B
 assert.deepEqual(X.firstModeLines(matchOf([pair(0,2,0.993)]),{a:b,b:a},{a:0,b:2},{a:'Run 4',b:'Run 3'}),[{side:'B',text:'Mode 1 of B · Run 3 is a Substrate mode and matches no mode of A; the core modes are A mode 1 ↔ B mode 3.'}]);
 // a degenerate core unit is named by unitName
 const pairUnit=pair(2,0,0.95,[2,3],[0]);
 const a2=closedRun('00000011',T18_NEAR,[false,false,true,true]);
 assert.deepEqual(X.firstModeLines(matchOf([pairUnit]),{a:a2,b},{a:2,b:0},TITLES).map(l=>l.text),['Mode 1 of A · Run 3 is a Substrate mode and matches no mode of B; the core modes are A modes 3–4 (pair) ↔ B mode 1.']);
});

test('C2: no line unless every claim holds',()=>{
 const a=closedRun('0000000a',T18_NEAR,[false,false,true,false]),b=openRun(T18_OPEN);
 // no pair chosen (no matched modes), matching off or failed
 assert.deepEqual(X.firstModeLines(matchOf([]),{a,b},null,TITLES),[]);
 assert.deepEqual(X.firstModeLines({...matchOf([pair(2,0,0.993)]),disabled:'Not matched'},{a,b},{a:2,b:0},TITLES),[]);
 assert.deepEqual(X.firstModeLines({error:'The two runs\' windows do not overlap.'},{a,b},{a:2,b:0},TITLES),[]);
 // the chosen pair is not a core pair: A's mode 2 with B's mode 2, though the core pair is also matched
 assert.deepEqual(X.firstModeLines(matchOf([pair(1,1,0.9),pair(2,0,0.993)]),{a,b},{a:1,b:1},TITLES),[]);
 // A's mode 1 is matched (with B's mode 2): it has a match, no line
 assert.deepEqual(X.firstModeLines(matchOf([pair(0,1,0.9),pair(2,0,0.993)]),{a,b},{a:2,b:0},TITLES),[]);
 // A's mode 1 is the core mode: no line
 const first=closedRun('00000010',[2.44,2.40],[true,false]);
 assert.deepEqual(X.firstModeLines(matchOf([pair(0,0,0.99)]),{a:first,b},{a:0,b:0},TITLES),[]);
 // A's mode 1 is not an edge mode (the core-only geometry: no shape touches the window edge, no core mode either)
 const plain=closedRun('0000000d',[2.44,1.77],[true,true],{target:null,shapes:[CORE]});
 assert.equal(M.firstModeEdgeShape(plain),null);
 assert.deepEqual(X.firstModeLines(matchOf([pair(0,0,0.99)]),{a:plain,b},{a:0,b:0},TITLES),[]);
 // a run without a core mode: no core pair, no line (the closed run as set)
 const asSet=closedRun('0000000b',[2.6,2.5],[false,false],{target:null});
 assert.deepEqual(X.firstModeLines(matchOf([pair(1,0,0.85)]),{a:asSet,b},{a:1,b:0},TITLES),[]);
 // the same run on both sides: its mode 1 matches itself
 assert.deepEqual(X.firstModeLines(matchOf([pair(0,0,1),pair(1,1,1),pair(2,2,1),pair(3,3,1)]),{a,b:a},{a:2,b:2},{a:'Run 3',b:'Run 3'}),[]);
});

test('C2: Compare puts the line in the same place as D4; the Core modes line, the pick and the matching unchanged',()=>{
 const app=read('workspace-app.mjs'),match=read('workspace-match.mjs');
 const body=app.slice(app.indexOf('function renderComparison('),app.indexOf('\nlet pendingRunImport'));
 assert.ok(body.includes("for(const l of firstModeLines(match,{a,b},chosen,{a:runNumberTitle(a),b:runNumberTitle(b)})){const line=document.createElement('p');line.className='compare-first-line';line.id='compare-first-mode-'+l.side.toLowerCase();line.textContent=l.text;firstLines.push(line);}"));
 assert.ok(body.includes("host.append(...firstLines,grid,description);"));
 assert.ok(app.includes("box.append(runs,...(coreLine?[cell('p',coreLine,{class:'table-note',id:'compare-core-line'})]:[]),more,frame,note);"));
 assert.ok(app.includes("const chosen=choices.find(c=>compareChoice&&c.a===compareChoice.a&&c.b===compareChoice.b)||choices.find(c=>compareChoice&&c.a===compareChoice.a)||choices[0]||null;"));
 assert.ok(match.includes(" return out.sort((x,y)=>x.a-y.a);\n}"));
 assert.deepEqual([X.MATCH_THRESHOLD,X.MATCH_MARGIN],[0.8,0.1]);
});
