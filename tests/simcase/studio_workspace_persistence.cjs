// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Session file names, the title's saved state, the open/recover confirmation and the Compare table.
const {test,before}=require('node:test');const assert=require('node:assert/strict');
let P,C,snapshot;
before(async()=>{
 P=await import('../../packages/simcase/src/simcase/studio/static/workspace-persistence.mjs');
 C=await import('../../packages/simcase/src/simcase/studio/static/workspace-compare.mjs');
 ({snapshot}=await import('../../packages/simcase/src/simcase/studio/static/workspace-project.mjs'));
});
const setup={materials:{Core:'Silicon',Oxide:'Silica',Heater:''},cooling:'',temperature:293.15,fixed:'',terminal:''};
const rect=(w,h)=>({name:'Core',type:'rect',material:'Silicon',x:-w/2,y:0,w,h});
const input=(over={})=>snapshot({height:220,width:500,wavelength:1550,coreMesh:30,shapes:[rect(500,220)],voltage:1,heat:true,structure:true,optics:true,...over},setup);
const run=(job,w,label='',pinned=false,index=[2.6,2.1])=>({job,label,pinned,effective_index:index,input:input({shapes:[rect(w,300)],electric:false,heat:false,structure:false})});

test('a session file name holds the application and the local date-time to the minute, and ends in .json',()=>{
 assert.equal(P.sessionFileName('optical-waveguide',new Date(2026,10,21,13,5,59)),'optical-waveguide-session-2026-11-21-1305.json');
 assert.equal(P.sessionFileName('heat-conduction',new Date(2027,0,2,3,4)),'heat-conduction-session-2027-01-02-0304.json');
 assert.throws(()=>P.sessionFileName('../x',new Date()));assert.throws(()=>P.sessionFileName('',new Date()));
});

test('the save indicator shows the file the session was sent to until the next edit, and after recovery what the record kept',()=>{
 const when=()=>'13:05',saved={name:'optical-waveguide-session-2026-11-21-1305.json',savedAt:'2026-11-21T04:05:00Z',current:true};
 assert.equal(P.persistenceTitle({saved,runsUnsaved:false},when),'Sent to session file optical-waveguide-session-2026-11-21-1305.json · 13:05');
 // the browser copy does not change what the indicator says about the file
 assert.equal(P.persistenceTitle({saved,recovery:'kept'},when),P.persistenceTitle({saved},when));
 const recovered={kind:'recovered',name:null,current:true};
 assert.equal(P.persistenceTitle({saved,loaded:recovered},when),'Recovered from this browser · last session file optical-waveguide-session-2026-11-21-1305.json (13:05)');
 assert.equal(P.persistenceTitle({saved:{...saved,current:false},runsUnsaved:true,loaded:recovered},when),'Recovered from this browser · changed since session file optical-waveguide-session-2026-11-21-1305.json (13:05)');
 assert.equal(P.persistenceTitle({loaded:recovered},when),'Recovered from this browser');
 // a recovered notebook never saved to a file still says its results are not in one
 assert.equal(P.persistenceTitle({runsUnsaved:true,loaded:recovered},when),'Recovered from this browser · not saved to a file');
 for(const title of [P.persistenceTitle({saved},when),P.persistenceTitle({saved,loaded:recovered},when),P.persistenceTitle({saved,recovery:'kept'},when)])assert.doesNotMatch(title,/saved/i,'the title never claims the browser kept the file');
 assert.equal(P.persistenceTitle({saved:{...saved,current:false},clean:false},when),'Unsaved inputs');
 assert.equal(P.persistenceTitle({saved:{...saved,current:false},runsUnsaved:true,recovery:'kept'},when),'Changed since session file optical-waveguide-session-2026-11-21-1305.json (13:05) · kept for recovery in this browser');
 // before a file save the indicator says which copy exists: none in a file, and the browser copy's state
 assert.equal(P.persistenceTitle({runsUnsaved:true,recovery:'kept'},when),'Not saved to a file · kept for recovery in this browser');
 assert.equal(P.persistenceTitle({runsUnsaved:true,recovery:'updating'},when),'Not saved to a file · updating browser recovery');
 assert.equal(P.persistenceTitle({runsUnsaved:true,recovery:'unavailable'},when),'Not saved to a file · browser recovery unavailable');
 assert.equal(P.persistenceTitle({runsUnsaved:true,recovery:'conflict'},when),'Not saved to a file · browser recovery changed in another tab');
 assert.equal(P.persistenceTitle({runsUnsaved:true},when),'Not saved to a file · not in browser recovery yet');
 assert.equal(P.persistenceTitle({}),'No unsaved input changes');
 // an invalid draft outranks a saved state
 assert.equal(P.persistenceTitle({invalid:true,clean:true,saved},when),'Invalid input draft · last valid inputs unchanged');
});

test('after an open the title names the file opened; after the next change it says what changed',()=>{
 const opened={kind:'opened',name:'design-a.json',current:true};
 assert.equal(P.persistenceTitle({loaded:opened}),'Opened design-a.json');
 assert.equal(P.persistenceTitle({loaded:{...opened,current:false},runsUnsaved:true,recovery:'kept'}),'Not saved to a file · kept for recovery in this browser');
 assert.equal(P.persistenceTitle({loaded:{...opened,current:false},clean:false}),'Unsaved inputs');
 // a save after the open names the new file, not the one opened
 assert.equal(P.persistenceTitle({saved:{name:'b.json',savedAt:'2026-11-21T04:05:00Z',current:true},loaded:null},()=>'13:05'),'Sent to session file b.json · 13:05');
 // the title carries no revision counter: it would differ after a restore
 for(const title of [P.persistenceTitle({loaded:opened}),P.persistenceTitle({}),P.persistenceTitle({clean:false})])assert.doesNotMatch(title,/revision/i);
});

test('a malformed saved-file entry in a recovery record is ignored, not trusted',()=>{
 const ok={name:'a-session-2026-11-21-1305.json',savedAt:'2026-11-21T04:05:00Z',current:false};
 assert.deepEqual(P.validateSavedFile(ok),ok);assert.equal(P.validateSavedFile(undefined),null);
 for(const bad of [{...ok,name:'x.txt'},{...ok,name:'<b>.json'},{...ok,savedAt:'never'},{...ok,current:'yes'},'name.json',{...ok,name:'a'.repeat(201)+'.json'}])assert.equal(P.validateSavedFile(bad),null,JSON.stringify(bad));
});

test('physics lists only what a model holds; the start state names no multiphysics placeholder',()=>{
 const optical=input({electric:false,heat:false,structure:false}).model;
 assert.equal(P.physicsList(optical),'Optical');assert.equal(P.physicsList(input().model),'Electric + Heat + Mechanics + Optical');
 assert.equal(P.physicsList(input().model,false),'No model chosen');
});

test('only default inputs with no results open without a confirmation; the chosen application does not count',()=>{
 const defaults=input();
 assert.equal(P.untouchedWorkspace(input(),defaults),true);
 assert.equal(P.untouchedWorkspace(input({electric:false,heat:false,structure:false}),defaults),true);
 assert.equal(P.untouchedWorkspace(input(),defaults,{results:1}),false);
 assert.equal(P.untouchedWorkspace(input({shapes:[rect(600,220)]}),defaults),false);
 assert.equal(P.untouchedWorkspace(input({wavelength:1551}),defaults),false);
 assert.equal(P.untouchedWorkspace(snapshot({height:220,width:500,wavelength:1550,coreMesh:30,shapes:[rect(500,220)],voltage:1,heat:true,structure:true,optics:true},{...setup,temperature:300}),defaults),false);
});

test('the session confirmation says what comes back and what is replaced',()=>{
 const a=run('aaaaaaaa',600,'design A',true),b=run('bbbbbbbb',700,'design B');
 const session={runs:[a,b],comparison:['aaaaaaaa','bbbbbbbb']};
 const text=P.sessionLoadText(session,{runs:3,unsaved:true},'file');
 assert.equal(text.title,'Open saved session?');assert.equal(text.button,'Open session');
 assert.equal(text.description,'Brings back 2 runs with their names and pins and the comparison. Replaces the current inputs and 3 runs in this tab; input undo starts at the opened session. Save session first to keep the current runs.');
 assert.equal(text.runs,'design A (pinned); design B');assert.equal(text.comparison,'A design A (pinned) · B design B');
 const browser=P.sessionLoadText({runs:[run('cccccccc',500)],comparison:['cccccccc','cccccccc']},{runs:0},'browser');
 assert.equal(browser.title,'Recover saved session?');assert.equal(browser.button,'Recover session');
 assert.equal(browser.description,'Brings back 1 run with its name and pin. Replaces the current inputs; input undo starts at the opened session.');
 assert.equal(browser.runs,'500 × 300 nm · Silicon');assert.equal(browser.comparison,'None');
 assert.match(P.sessionLoadText({runs:[],comparison:[null,null]}).description,/^Brings back no completed runs\. /);
});

test('the Compare table has one row per candidate rank with both indices, their difference and its percentage of A',()=>{
 const rows=C.compareRows([2.6,2.1],[2.65,2.0]);
 assert.equal(rows.length,2);assert.deepEqual(rows.map(r=>r.rank),[1,2]);
 assert.equal(rows[0].a,2.6);assert.equal(rows[0].b,2.65);assert.equal(C.formatIndex(rows[0].delta),'0.05000000');
 assert.equal(C.formatPercent(rows[0].percent),'1.9231 %');assert.equal(C.formatPercent(rows[1].percent),'-4.7619 %');
 assert.equal(C.formatPercent(C.compareRows([0],[1])[0].percent),'—');
 assert.equal(C.compareRows([1,2,3],[1,2]).length,2);
 assert.equal(C.runHeading(run('aaaaaaaa',600,'design A')),'design A · 600 × 300 nm · Silicon · λ 1550 nm');
 assert.equal(C.runHeading(run('aaaaaaaa',700)),'700 × 300 nm · Silicon · λ 1550 nm');
 // a Compare field heading never repeats the side as the run's name (round 3, N6)
 assert.equal(C.fieldHeading('A',run('aaaaaaaa',600,'A')),'A · 600 × 300 nm · Silicon · λ 1550 nm');
 assert.equal(C.fieldHeading('B',run('aaaaaaaa',700,' b ')),'B · 700 × 300 nm · Silicon · λ 1550 nm');
 assert.equal(C.fieldHeading('A',run('aaaaaaaa',600,'design A')),'A · design A · 600 × 300 nm · Silicon · λ 1550 nm');
 assert.equal(C.fieldHeading('B',run('aaaaaaaa',700)),'B · 700 × 300 nm · Silicon · λ 1550 nm');
 // one n_eff precision everywhere: 8 decimals
 assert.equal(C.formatIndex(2.785604861),'2.78560486');
});
