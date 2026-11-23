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
 assert.equal(P.persistenceTitle({saved,runsUnsaved:false},when),'optical-waveguide-session-2026-11-21-1305.json · saved 13:05 (download)');
 // the browser copy does not change what the indicator says about the file
 assert.equal(P.persistenceTitle({saved,recovery:'kept'},when),P.persistenceTitle({saved},when));
 const recovered={kind:'recovered',name:null,current:true};
 assert.equal(P.persistenceTitle({saved,loaded:recovered},when),'Recovered from this browser · same as file optical-waveguide-session-2026-11-21-1305.json');
 assert.equal(P.persistenceTitle({saved:{...saved,current:false},runsUnsaved:true,loaded:recovered},when),'Recovered from this browser (last sent to a file: optical-waveguide-session-2026-11-21-1305.json at 13:05; changed since)');
 assert.equal(P.persistenceTitle({loaded:recovered},when),'Recovered from this browser');
 // a recovered notebook never saved to a file still says its results are not in one
 assert.equal(P.persistenceTitle({runsUnsaved:true,loaded:recovered},when),'Recovered from this browser · not saved to a file');
 // round 13 (O1): a download names the file and says it was a download, not that the browser kept it
 for(const title of [P.persistenceTitle({saved},when),P.persistenceTitle({saved,recovery:'kept'},when)])assert.match(title,/ \(download\)$/,'a download says so');
 assert.doesNotMatch(P.persistenceTitle({saved,loaded:recovered},when),/saved/i);
 assert.equal(P.persistenceTitle({saved:{...saved,current:false},clean:false},when),'Unsaved inputs');
 assert.equal(P.persistenceTitle({saved:{...saved,current:false},runsUnsaved:true,recovery:'kept'},when),'Changed since session file optical-waveguide-session-2026-11-21-1305.json (13:05) · kept for recovery in this browser');
 // before a file save the indicator says which copy exists: none in a file, and the browser copy's state
 assert.equal(P.persistenceTitle({runsUnsaved:true,recovery:'kept'},when),'Not saved to a file · kept for recovery in this browser');
 assert.equal(P.persistenceTitle({runsUnsaved:true,recovery:'updating'},when),'Not saved to a file · updating browser recovery');
 assert.equal(P.persistenceTitle({runsUnsaved:true,recovery:'unavailable'},when),'Not saved to a file · browser recovery unavailable');
 assert.equal(P.persistenceTitle({runsUnsaved:true,recovery:'conflict'},when),'Not saved to a file · browser recovery changed in another tab');
 assert.equal(P.persistenceTitle({runsUnsaved:true},when),'Not saved to a file · not in browser recovery yet');
 // a failing or conflicting browser copy is said after a file save, an open or a recovery too
 assert.equal(P.persistenceTitle({saved,recovery:'conflict'},when),'optical-waveguide-session-2026-11-21-1305.json · saved 13:05 (download) · browser recovery changed in another tab');
 assert.equal(P.persistenceTitle({loaded:recovered,recovery:'unavailable'},when),'Recovered from this browser · browser recovery unavailable');
 assert.equal(P.persistenceTitle({recovery:'unavailable'},when),'No unsaved input changes');
 assert.equal(P.persistenceTitle({}),'No unsaved input changes');
 // an invalid draft outranks a saved state
 assert.equal(P.persistenceTitle({invalid:true,clean:true,saved},when),'Invalid input draft · last valid inputs unchanged');
});

test('after an open the title names the file opened; after the next change it says what changed',()=>{
 const opened={kind:'opened',name:'design-a.json',current:true};
 assert.equal(P.persistenceTitle({loaded:opened}),'Opened design-a.json');
 assert.equal(P.persistenceTitle({loaded:{...opened,current:false,file:'design-a.json',fileCurrent:true},runsUnsaved:true,recovery:'kept'}),'Changed since session file design-a.json · kept for recovery in this browser');
 assert.equal(P.persistenceTitle({loaded:{...opened,current:false},runsUnsaved:true,recovery:'kept'}),'Not saved to a file · kept for recovery in this browser');
 assert.equal(P.persistenceTitle({loaded:{...opened,current:false},clean:false}),'Unsaved inputs');
 // a save after the open names the new file, not the one opened
 assert.equal(P.persistenceTitle({saved:{name:'b.json',savedAt:'2026-11-21T04:05:00Z',current:true},loaded:null},()=>'13:05'),'b.json · saved 13:05 (download)');
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

test('Compare formats: n_eff to 8 decimals, the difference as a percentage of A, run headings',()=>{
 assert.equal(C.formatIndex(2.65-2.6),'0.05000000');
 assert.equal(C.formatPercent(0.05/2.6*100),'1.9231 %');assert.equal(C.formatPercent(-0.1/2.1*100),'-4.7619 %');
 assert.equal(C.formatPercent(null),'—');
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
test('browser recovery of a multiphysics session over 16 MiB says which maps it left out, or that it wrote nothing',()=>{
 assert.equal(P.persistenceTitle({runsUnsaved:true,recovery:'kept:2'}),'Not saved to a file · kept for recovery in this browser without the maps of 2 runs · Save session to keep them');
 assert.equal(P.persistenceTitle({runsUnsaved:true,recovery:'kept:1'}),'Not saved to a file · kept for recovery in this browser without the maps of 1 run · Save session to keep them');
 assert.equal(P.persistenceTitle({runsUnsaved:true,recovery:'overLimit'}),'Not saved to a file · browser recovery unavailable: session over 16 MiB');
 assert.equal(P.persistenceTitle({runsUnsaved:true,recovery:'kept'}),'Not saved to a file · kept for recovery in this browser');
});
test('the title names the session file a download went to and says it was a download',()=>{
 const title=P.persistenceTitle({saved:{name:'s.json',savedAt:'2026-11-21T04:05:00Z',current:true}},()=>'13:05');
 assert.match(title,/^s\.json · saved 13:05 \(download\)$/);assert.doesNotMatch(title,/disk/i);
 assert.equal(P.sentToDownloads('Model','m.json'),"Model file m.json sent to your browser's Downloads");
});
test('leaving a model whose runs only this tab holds asks first, names what is lost and offers the save that fits',()=>{
 // multiphysics runs no session file holds: leaving discards them from the tab; Save session is offered
 assert.deepEqual(P.leaveConfirmText({from:'multiphysics',runs:3,target:'Optical waveguide'}),{title:'Leave this model?',description:'3 runs are only in this tab and in browser recovery. Save session first to keep them in a file.',
  save:{kind:'session',label:'Save session'},leave:'Leave',stay:'Cancel'});
 assert.equal(P.leaveConfirmText({from:'multiphysics',runs:1}).description,'1 run is only in this tab and in browser recovery. Save session first to keep it in a file.');
 assert.equal(P.leaveConfirmText({from:'multiphysics',runs:0}),null,'every run in a session file, or none: nothing to lose, no question');
 // optical runs not in a session file stay in the tab but no file holds them: Save session is offered
 const optical=P.leaveConfirmText({from:'optical',runs:1,saved:false,target:'Heated silicon waveguide'});
 assert.equal(optical.title,'Open Heated silicon waveguide?');
 assert.equal(optical.description,'1 optical run is in no file. It stays in this tab while Heated silicon waveguide is open and comes back with the optical model, but closing the tab can lose it. Save session keeps it in a file.');
 assert.deepEqual(optical.save,{kind:'session',label:'Save session, then continue'});
 assert.match(P.leaveConfirmText({from:'optical',runs:2,target:'x.json'}).description,/^2 optical runs are in no file\. They stay/);
 assert.equal(P.leaveConfirmText({from:'optical',runs:2,saved:true}),null,'runs in a session file: no question');
 assert.equal(P.leaveConfirmText({from:'optical',runs:0}),null);
});
test('a model just chosen reads as new until its first edit, save or open',async()=>{
 const P=await import('../../packages/simcase/src/simcase/studio/static/workspace-persistence.mjs');
 assert.equal(P.persistenceTitle({fresh:true,clean:false}),'New model · not saved');
 assert.equal(P.persistenceTitle({fresh:false,clean:false}),'Unsaved inputs');
 // runs not in a file and invalid drafts outrank it
 assert.equal(P.persistenceTitle({fresh:true,clean:false,runsUnsaved:true,recovery:'kept'}),'Not saved to a file · kept for recovery in this browser');
 assert.match(P.persistenceTitle({fresh:true,invalid:true,clean:false}),/^Invalid input draft/);
});
test('switching models says where the optical runs stay: one short line, the rest behind More',()=>{
 assert.deepEqual(P.opticalRunsStayText({runs:0}),{text:'',more:''});
 const one='Optical waveguide run stays in this tab · Library › Optical waveguide returns to it',two='Optical waveguide runs stay in this tab · Library › Optical waveguide returns to them';
 // the tab holds them until it is closed or reloaded; after that, only what still holds them is named
 assert.deepEqual(P.opticalRunsStayText({runs:1}),{text:one,more:'This tab holds 1 run until it is closed or reloaded. After that, no file or browser recovery holds it.'});
 assert.deepEqual(P.opticalRunsStayText({runs:2,file:'optical-waveguide-session-2026-11-22-0922.json',recovery:true}),
  {text:two,more:'This tab holds 2 runs until it is closed or reloaded. After that, Library › Optical waveguide › Restore from this browser (browser recovery, which keeps the four newest sessions) or Open session with optical-waveguide-session-2026-11-22-0922.json brings them back.'});
 assert.deepEqual(P.opticalRunsStayText({runs:2,recovery:true}),
  {text:two,more:'This tab holds 2 runs until it is closed or reloaded. After that, Library › Optical waveguide › Restore from this browser (browser recovery, which keeps the four newest sessions) brings them back.'});
 assert.deepEqual(P.opticalRunsStayText({runs:1,file:'a.json'}),
  {text:one,more:'This tab holds 1 run until it is closed or reloaded. After that, Open session with a.json brings it back.'});
});
test('round 9 (J5), round 11: the title says in a few words that the viewed run used other inputs, and that they are not unsaved edits',()=>{
 const when=()=>'15:50',viewed={run:1,name:'Design A'};
 assert.equal(P.persistenceTitle({viewed},when),'No unsaved input changes · viewing Run 1 · Design A (other inputs)');
 assert.equal(P.persistenceTitle({viewed:{run:2,name:''}},when),'No unsaved input changes · viewing Run 2 (other inputs)');
 assert.equal(P.persistenceTitle({loaded:{kind:'recovered',current:true},viewed},when),'Recovered from this browser · viewing Run 1 · Design A (other inputs)');
 // without a viewed run of other inputs, or with an invalid draft, the title is as before
 assert.equal(P.persistenceTitle({},when),'No unsaved input changes');
 assert.equal(P.persistenceTitle({invalid:true,viewed},when),'Invalid input draft · last valid inputs unchanged');
});
test('round 9 (J5): Compare headings name a run by its number with its name',()=>{
 assert.equal(C.runHeading(run('aaaaaaaa',600,'design A'),1),'Run 1 · design A · 600 × 300 nm · Silicon · λ 1550 nm');
 assert.equal(C.runHeading(run('aaaaaaaa',700),2),'Run 2 · 700 × 300 nm · Silicon · λ 1550 nm');
 assert.equal(C.fieldHeading('A',run('aaaaaaaa',600,'A'),1),'A · Run 1 · 600 × 300 nm · Silicon · λ 1550 nm');
 assert.equal(C.fieldHeading('B',run('aaaaaaaa',700,'design B'),2),'B · Run 2 · design B · 700 × 300 nm · Silicon · λ 1550 nm');
});

test('round 10: a recovered notebook whose record still matched its file says "same as file", not "not saved to a file"',()=>{
 const when=()=>'13:05',name='optical-waveguide-session-2026-11-22-2010.json';
 // the record names the file it was opened from and says the inputs and runs were still that file's
 const recovered={kind:'recovered',name:null,current:true,file:name,fileCurrent:true};
 assert.equal(P.persistenceTitle({loaded:recovered,recovery:'kept'},when),'Recovered from this browser · same as file '+name);
 // the record's file link no longer matched when it was written
 assert.equal(P.persistenceTitle({loaded:{...recovered,fileCurrent:false},runsUnsaved:true,recovery:'kept'},when),`Recovered from this browser (opened from ${name}; changed since)`);
 // after a change of the model or a run: what changed, and the file it changed from
 assert.equal(P.persistenceTitle({loaded:{...recovered,current:false},runsUnsaved:true,recovery:'kept'},when),`Changed since session file ${name} · kept for recovery in this browser`);
 // a record with no file link reads as before
 assert.equal(P.persistenceTitle({loaded:{kind:'recovered',name:null,current:true},runsUnsaved:true,recovery:'kept'},when),'Recovered from this browser · not saved to a file');
 // a file sent to Downloads that still matches outranks an opened one
 const saved={name:'later.json',savedAt:'2026-11-22T20:15:00Z',current:true};
 assert.equal(P.persistenceTitle({saved,loaded:recovered},when),'Recovered from this browser · same as file later.json');
 for(const t of [P.persistenceTitle({loaded:recovered},when),P.persistenceTitle({saved,loaded:recovered},when)])assert.doesNotMatch(t,/not saved to a file/i);
});
test('round 11: Compare opens with the two newest runs, A the older; the two run cards say their side',()=>{
 const run=(job,label='')=>({job,label});
 assert.deepEqual(C.defaultComparison([]),[null,null]);
 assert.deepEqual(C.defaultComparison([run('a1')]),['a1','a1']);
 assert.deepEqual(C.defaultComparison([run('a1','design A'),run('a2','design B')]),['a1','a2']);
 // the run just computed is B, the run before it A, named or not
 assert.deepEqual(C.defaultComparison([run('a1','design A'),run('a2','design B'),run('a3')]),['a2','a3']);
 assert.equal(C.compareSide('a2',['a2','a3']),'A');assert.equal(C.compareSide('a3',['a2','a3']),'B');
 assert.equal(C.compareSide('a1',['a2','a3']),'');assert.equal(C.compareSide('a1',['a1','a1']),'A and B');
});
test('round 11: a fresh multiphysics template reads as new; a recovered record that matched its opened file says "same as file"',()=>{
 // the multiphysics indicator's inputs (workspace-multiphysics-view.mjs indicator)
 assert.equal(P.persistenceTitle({clean:false,fresh:true}),'New model · not saved');
 assert.equal(P.persistenceTitle({clean:true,runsUnsaved:false,saved:null,loaded:{kind:'recovered',current:true,file:'heated-silicon-waveguide-session-2026-11-22-2124.json',fileCurrent:true}}),
  'Recovered from this browser · same as file heated-silicon-waveguide-session-2026-11-22-2124.json');
 assert.equal(P.persistenceTitle({clean:true,saved:{name:'h.json',savedAt:'2026-11-22T21:24:00Z',current:true},loaded:{kind:'recovered',current:true}},()=>'21:24'),
  'Recovered from this browser · same as file h.json');
});
