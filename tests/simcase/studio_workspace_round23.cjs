// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Round 23: usability fixes of the optical model (E1 to E6, pre-registered P1 to P6).
// Plain text comparison only: no RegExp is built from a dynamic string.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const read=name=>fs.readFileSync(path.join(__dirname,STATIC,name),'utf8');
const body=(text,from,to)=>{const a=text.indexOf(from),b=text.indexOf(to,a+from.length);assert.ok(a>=0&&b>a,from);return text.slice(a,b);};

const CORE={name:'Core',type:'rect',material:'Silicon',x:-250,y:0,w:500,h:220};
const SUBSTRATE={name:'Substrate',type:'rect',material:'Silicon',x:-1500,y:-1200,w:3000,h:700};
test('P1 (E1): the plan line row says the short form; Optical modes keeps the full sentence',async()=>{
 const M=await import(STATIC+'workspace-modes.mjs');
 const t18=M.edgeSlabRisk([CORE,SUBSTRATE]);
 assert.equal(M.edgeSlabShortText(t18),'Substrate touches the window edge: in a closed window its slab modes come first.');
 assert.equal(M.edgeSlabShortText({edge:'Wafer',core:'Rib'}),'Wafer touches the window edge: in a closed window its slab modes come first.');
 assert.equal(M.edgeSlabWarningText(t18),"Substrate touches the window edge and its index is as high as Core's: in a closed window its slab modes come first.");
 const app=read('workspace-app.mjs'),row=body(app,'function refreshEdgeWarning(){','\n}');
 // the row: the short words, the full sentence as its title, both buttons
 assert.ok(row.includes("const text=edgeSlabShortText(risk),key=text+'\\n'+defaultTarget(state.shapes);"));
 assert.ok(row.includes("$('run-edge-text').textContent=text;$('run-edge-text').title=edgeSlabWarningText(risk);"));
 assert.ok(row.includes("host.append(...edgeWarningButtons('run-edge'));"));
 // the panel: the full sentence
 assert.ok(app.includes('<p class="validation-warning" id="closed-edge-warning-text">${escapeHtml(edgeSlabWarningText(risk))}</p>'));
});

test('P1 (E1): the row wraps and is never cut: no line clamp, no ellipsis, the box grows',()=>{
 const css=read('workspace.css'),rule=sel=>{const a=css.indexOf(sel+'{');assert.ok(a>=0,sel);return css.slice(a,css.indexOf('}',a));};
 assert.equal(rule('.run-edge'),'.run-edge{display:flex;flex-wrap:wrap;align-items:center;gap:2px 4px;min-width:0;color:#8a4b00');
 const text=rule('.run-edge-text');
 for(const cut of ['line-clamp','overflow:hidden','text-overflow','nowrap'])assert.ok(!text.includes(cut),cut);
 assert.equal(rule('.run-options.edge-warning'),'.run-options.edge-warning{height:auto;min-height:50px;overflow:visible');
 // on a phone the box fits the screen beside Run study (it was 460 px wide in a 390 px window)
 assert.ok(css.includes('@media(max-width:600px){.run-options{width:280px}}'));
 // nothing else clamps or cuts the row's words
 assert.ok(!css.includes('.run-edge-text{-webkit-line-clamp')&&!css.includes('.dropping .run-edge-text'));
});

// E2: a session over the limit; browser recovery keeps the fields of the selected and pinned runs only
const FIXTURES=path.join(__dirname,'studio_session_fixtures');
const OPEN_FULL='optical-v10-open-full-083e151.json';
test('P2 (E2): recovery over the limit leaves fields out, and the header and Messages now say so',async()=>{
 const N=await import(STATIC+'workspace-notebook.mjs'),R=await import(STATIC+'workspace-notebook-recovery.mjs'),PS=await import(STATIC+'workspace-persistence.mjs');
 const full=N.parseSession(fs.readFileSync(path.join(FIXTURES,OPEN_FULL),'utf8')),base=full.runs[0];
 const runs=[1,2,3].map(n=>({...base,job:'0000000'+n,number:n,pinned:false}));
 // a limit between one run with its field and three: the stand-in for 16 MiB of the measured 22 MB session
 const one=N.writeOpticalSession(full.input,runs.slice(0,1),'00000003',[null,null],full.view).bytes,three=N.writeOpticalSession(full.input,runs,'00000003',[null,null],full.view).bytes;
 const limit=Math.floor((one+three)/2),all=N.writeOpticalSession(full.input,runs,'00000003',[null,null],full.view,{limit});
 assert.equal(all.ok,false);assert.deepEqual(all.reduced.kept,[3]);assert.deepEqual(all.reduced.notKept,[1,2]);
 // the record recovery writes: every run, the field of the selected run only, with no question
 const make=N.captureSession(full.input,runs,'00000003',[null,null],full.view,{limit});
 const record=JSON.parse(make());assert.deepEqual(record.runs.map(r=>!!r.field),[false,false,true]);
 // before round 23 nothing said so: the snapshot reported no dropped fields and the header read "kept"
 assert.equal(make.dropped,2);
 const states=[];const store={save:async r=>r};
 const saver=new R.NotebookAutosave(store,{onState:s=>states.push(s),delay:0,setTimer:fn=>{fn();return 1;},clearTimer:()=>{}});
 saver.schedule('over',make);await saver.settle();
 assert.equal(states.find(s=>s.phase==='saved').dropped,2);
 // within the limit: none dropped
 const fits=N.captureSession(full.input,runs.slice(0,1),'00000001',[null,null],full.view,{limit});fits();assert.equal(fits.dropped,0);
 // the header and the save indicator words
 assert.equal(PS.projectTitle({models:1,recovery:'keptFields:5'}),'Untitled project · not saved to a file · kept for recovery in this browser without the fields of 5 runs');
 assert.equal(PS.projectTitle({models:1,recovery:'keptFields:1'}),'Untitled project · not saved to a file · kept for recovery in this browser without the fields of 1 run');
 assert.equal(PS.projectTitle({models:1,recovery:'kept'}),'Untitled project · not saved to a file · kept for recovery in this browser');
 // the Messages line: what Save will offer, what the other runs keep, what recovery keeps
 assert.equal(N.sessionSizeText({ok:false,bytes:22.0e6,reduced:{bytes:4e6,notKept:[1,2,3,4,5],kept:[6]},refusal:null}),
  'Session is now 22 MB, over the 16 MiB (16.8 MB) limit. File › Save will ask whether to keep the fields of the selected and pinned runs only (Run 6); the other runs keep n_eff, the TE fractions and the effective areas. Browser recovery already keeps only those fields.');
 assert.equal(N.sessionSizeText({ok:false,bytes:18.0e6,reduced:{bytes:8e6,notKept:[1,2,3],kept:[4,5,6]},refusal:null}),
  'Session is now 18 MB, over the 16 MiB (16.8 MB) limit. File › Save will ask whether to keep the fields of the selected and pinned runs only (Runs 4, 5 and 6); the other runs keep n_eff, the TE fractions and the effective areas. Browser recovery already keeps only those fields.');
 // the page: the optical snapshot's count, shown while recovery is kept, in the header and the indicator
 const app=read('workspace-app.mjs');
 assert.ok(app.includes("const opticalRecoveryShown=()=>recoveryState==='kept'&&!multiView.active()&&opticalRecoveryDropped>0?'keptFields:'+opticalRecoveryDropped:recoveryState;"));
 assert.ok(app.includes("opticalRecoveryDropped=recoveryKind==='optical'&&Number.isInteger(state.dropped)?state.dropped:0;"));
 assert.ok(app.includes('recovery:opticalRecoveryShown(),copyOf:project.copyOf,recovered});'));
 assert.ok(app.includes('persistenceTitle({...saveIndicator,recovery:opticalRecoveryShown()})'));
 // the message wraps
 assert.ok(read('workspace.css').includes('#file-status{color:#7b8798;min-width:0;overflow-wrap:anywhere}'));
});
