// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Round 24: usability fixes of the optical model (B2 to B6, pre-registered P1 to P5).
// Plain text comparison only: no RegExp is built from a dynamic string.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const read=name=>fs.readFileSync(path.join(__dirname,STATIC,name),'utf8');
const body=(text,from,to)=>{const a=text.indexOf(from),b=text.indexOf(to,a+from.length);assert.ok(a>=0&&b>a,from);return text.slice(a,b);};

test('P1 (B2): after a change, a project that came from a file says "changed since <file>, not saved" in every recovery state',async()=>{
 const PS=await import(STATIC+'workspace-persistence.mjs'),when=()=>'10:15';
 const changed=recovery=>PS.projectTitle({name:'both-models',models:2,recovery,fromFile:'both-models.json'},when);
 assert.equal(changed('updating'),'both-models · changed since both-models.json, not saved · updating browser recovery');
 assert.equal(changed('kept'),'both-models · changed since both-models.json, not saved · kept for recovery in this browser');
 assert.equal(changed('keptFields:6'),'both-models · changed since both-models.json, not saved · kept for recovery in this browser without the fields of Run 6');
 assert.equal(changed(null),'both-models · changed since both-models.json, not saved · not in browser recovery yet');
 // right after the restore (the recovered words lead, as before: E5 and Q4)
 assert.equal(PS.projectTitle({name:'both-models',models:2,recovery:'kept',recovered:{opened:null,changed:'both-models.json'},fromFile:'both-models.json'},when),'both-models · recovered from this browser · changed since both-models.json, not saved · kept for recovery in this browser');
 assert.equal(PS.projectTitle({name:'both-models',models:2,recovery:'kept',recovered:{opened:'both-models.json',changed:null},fromFile:'both-models.json'},when),'both-models · recovered from this browser · as opened from both-models.json · kept for recovery in this browser');
 // a project no file held keeps "not saved to a file"
 assert.equal(PS.projectTitle({name:'both-models',models:2,recovery:'updating'},when),'both-models · not saved to a file · updating browser recovery');
 assert.equal(PS.projectTitle({models:1,recovery:'kept'},when),'Untitled project · not saved to a file · kept for recovery in this browser');
 // a project file of its own: its words, as before (opened, then changed)
 assert.equal(PS.projectTitle({name:'both-models',models:2,file:{name:'both-models.json',how:'opened'},current:false,recovery:'updating',fromFile:'other.json'},when),'both-models · both-models.json · changed since opened · updating browser recovery');
 assert.equal(PS.projectTitle({name:'both-models',models:2,file:{name:'both-models.json',how:'opened'},current:true,recovery:'kept'},when),'both-models · both-models.json · opened');
});

test('P1 (B2): the page keeps the file a recovered record came from until a new project',()=>{
 const app=read('workspace-app.mjs');
 assert.ok(app.includes('const project={name:null,nameFrom:null,ids:{},next:1,file:null,stamp:null,scope:0,copyOf:null,recovered:null,fromFile:null,openedFrom:null,openedStamp:null};'));
 assert.ok(body(app,'function resetProject(','\n}').includes('openedFrom:null,openedStamp:null,file:null,fromFile:null,stamp:null,scope:project.scope+1,copyOf:null,recovered:null});'));
 assert.ok(body(app,'function restoreProjectName(','\n}').includes('project.fromFile=next.recovered.opened||next.recovered.changed||null;'));
 assert.ok(body(app,'function projectLine(){','\n}').includes('return projectTitle({name:project.name,fromFile:project.fromFile,models:'));
});

test('P1 (B2, follow-up): an untitled project whose content came from File › Open of a session or model file says "changed since <file>, not saved" once changed',async()=>{
 const PS=await import(STATIC+'workspace-persistence.mjs'),when=()=>'10:15';
 const t=(opened,extra={})=>PS.projectTitle({models:1,recovery:'updating',opened,...extra},when);
 assert.equal(t({file:'run-a.json',changed:true}),'Untitled project · changed since run-a.json, not saved · updating browser recovery');
 assert.equal(PS.projectTitle({models:1,recovery:'keptFields:6',opened:{file:'run-a.json',changed:true}},when),'Untitled project · changed since run-a.json, not saved · kept for recovery in this browser without the fields of Run 6');
 // just opened, not changed: as before
 assert.equal(t({file:'run-a.json',changed:false}),'Untitled project · not saved to a file · updating browser recovery');
 // renamed after the open: the name, the same words
 assert.equal(t({file:'run-a.json',changed:true},{name:'Study'}),'Study · changed since run-a.json, not saved · updating browser recovery');
 // a nameless recovered record of a copy (Y3): its words until a change, then the same words
 assert.equal(t({file:'both-models.json',changed:false},{copyOf:'both-models.json'}),'Untitled project · recovered from a copy of both-models.json · not saved to a file · updating browser recovery');
 assert.equal(t({file:'both-models.json',changed:true},{copyOf:'both-models.json'}),'Untitled project · changed since both-models.json, not saved · updating browser recovery');
 // never any file; a project file of its own
 assert.equal(t(null),'Untitled project · not saved to a file · updating browser recovery');
 assert.equal(PS.projectTitle({name:'p',models:1,file:{name:'p.json',how:'opened'},current:false,recovery:'updating',opened:{file:'run-a.json',changed:true}},when),'p · p.json · changed since opened · updating browser recovery');
 // the page: File › Open of a session or model file, a multiphysics session file, and a copy's restore
 const app=read('workspace-app.mjs');
 assert.ok(app.includes("function markOpenedFrom(name){project.openedFrom=name;project.openedStamp=projectStamp();}"));
 assert.ok(app.includes("  if(pending.source==='file'&&pending.newProject)markOpenedFrom(pending.label);"));
 assert.ok(app.includes("{if(source==='file'){multiphysicsProject();markOpenedFrom(label);rememberOpened(label);}"));
 assert.equal(app.split('if(project.copyOf)markOpenedFrom(project.copyOf);').length,3);
 assert.ok(app.includes('opened:project.openedFrom?{file:project.openedFrom,changed:project.openedStamp!==projectStamp()}:null,'));
});

test('P2 (B3): the size message in one unit (MB, one decimal), what browser recovery left out first, then what Save offers',async()=>{
 const N=await import(STATIC+'workspace-notebook.mjs');
 const out={ok:false,bytes:17.04e6,reduced:{bytes:9e6,notKept:[6],kept:[1,2,9]},refusal:null};
 const text=N.sessionSizeText(out,[6]);
 assert.equal(text,"Session is now 17.0 MB, over the 16.8 MB limit. Browser recovery keeps every run's values; the field plots of Run 6 are not kept. File › Save will ask whether to keep the field plots of the selected and pinned runs only (Runs 1, 2 and 9).");
 assert.ok(!text.includes('MiB'));
 assert.equal(N.sessionSizeText({...out,bytes:24.31e6},[1,2]),"Session is now 24.3 MB, over the 16.8 MB limit. Browser recovery keeps every run's values; the field plots of Run 1 and Run 2 are not kept. File › Save will ask whether to keep the field plots of the selected and pinned runs only (Runs 1, 2 and 9).");
 assert.equal(N.sessionSizeText(out,[]),"Session is now 17.0 MB, over the 16.8 MB limit. Browser recovery keeps every run's values and field plots. File › Save will ask whether to keep the field plots of the selected and pinned runs only (Runs 1, 2 and 9).");
 // the refusal branch: the same unit in Save's words
 const refusal=N.keptOverText([{name:'Run 6',selected:true,pinned:false}],18.94e6),off=N.sessionSizeText({ok:false,bytes:48.8e6,reduced:null,refusal});
 assert.equal(off,'Session is now 48.8 MB, over the 16.8 MB limit, and File › Save will refuse: The selected run (Run 6) is 18.9 MB with its fields, over the 16.8 MB session limit. Select a different run before saving, so this one is saved without its fields, or run it again with fewer modes. Browser recovery is off.');
 assert.ok(!off.includes('MiB'));
 // MB to one decimal; a size just over the limit never reads as the limit itself
 assert.equal(N.megabytes(17e6),'17.0 MB');assert.equal(N.megabytes(9.94e6),'9.9 MB');
 assert.equal(N.megabytes(16*1024*1024+1),'16.78 MB');assert.equal(N.megabytes(16.7e6),'16.7 MB');
 // the header keeps its words (fields), as the coordinator allowed
 const PS=await import(STATIC+'workspace-persistence.mjs');
 assert.equal(PS.projectTitle({models:1,recovery:'keptFields:6'}),'Untitled project · not saved to a file · kept for recovery in this browser without the fields of Run 6');
});

test('P3 (B4): runs newer than a named pair: Compare offers the two newest; a pair picked by hand is kept and keeps its swap',async()=>{
 const C=await import(STATIC+'workspace-compare.mjs');
 const runs=[1,2,3,4,5,6,7].map(n=>({job:'j'+n,number:n,...(n<3?{label:'Design '+'AB'[n-1]}:{})}));
 // T18-like: Run 1 and Run 2 named, so new runs keep them (round 16); five more runs came
 const named=['j1','j2'];
 assert.deepEqual(C.comparisonAfterRun(runs,named,false),named);
 assert.equal(C.newerThanPair(runs,named).job,'j7');
 assert.deepEqual(C.newestPairOffer(runs,named,false),['j6','j7']);
 // picked by hand: no offer, the pair stays after a run
 assert.equal(C.newestPairOffer(runs,named,true),null);
 assert.deepEqual(C.comparisonAfterRun(runs,named,true),named);
 // the newest pair shown, or nothing newer: no offer
 assert.equal(C.newestPairOffer(runs,['j6','j7'],false),null);
 assert.equal(C.newestPairOffer(runs,['j5','j7'],false),null);
 assert.equal(C.newestPairOffer(runs.slice(0,1),['j1','j1'],false),null);
 // a named pair read from a file is kept because it is named, not as picked (round 25, A3: pairChosen)
 assert.equal(C.pairChosen(runs,named),false);
 // the page: one action for an unpicked pair, which shows the two newest and leaves the pair unpicked
 const app=read('workspace-app.mjs'),line=body(app,'const newer=newerThanPair(runs,compareIds);','line.append(swap);host.append(line);}');
 assert.ok(line.includes('const offer=newestPairOffer(runs,compareIds,comparePicked);'));
 assert.ok(line.includes('swap.textContent=`Compare the two newest: Run ${na} and Run ${nb}`;swap.onclick=()=>{compareIds=[...offer];comparePicked=false;'));
 assert.ok(line.includes('else{swap.textContent=`Compare Run ${n} with B`;swap.onclick=()=>{compareIds=[compareIds[1],newer.job];comparePicked=true;'));
});

test('P4 (B5): runs read from a file or browser recovery carry no wall time; the estimate skips them and uses an older measured run, or none',async()=>{
 const N=await import(STATIC+'workspace-notebook.mjs'),W=await import(STATIC+'workspace-workflow.mjs');
 const fixture=name=>fs.readFileSync(path.join(__dirname,'studio_session_fixtures',name),'utf8');
 // a session file (an open run of version 10) read: no duration on its runs
 const opened=N.parseSession(fixture('optical-v10-open-full-083e151.json'));
 assert.ok(opened.runs.length>0&&opened.runs.every(r=>!('duration' in r)));
 // a run measured in this tab, written and read back as File › Save and browser recovery do: its
 // wall time is not in the session (no format change; the session stores completedAt only)
 const timed={...opened.runs[0],duration:68000},out=N.writeOpticalSession(opened.input,[timed],timed.job,[timed.job,timed.job],opened.view);
 assert.equal(out.ok,true);assert.ok(!out.text.includes('"duration"'));
 assert.equal('duration' in N.parseSession(out.text).runs[0],false);
 // the estimate before an open n_g run: the comparable run from a file is skipped
 const kinds={isOpen:r=>r.open===true,hasGroup:r=>r.ng===true};
 const fromFile={job:'f',open:true,ng:false},older={job:'o',open:true,ng:false,duration:60000},closed={job:'c',open:false,ng:false,duration:5000};
 assert.equal(W.groupIndexEstimate([fromFile],{open:true},kinds),null);
 assert.equal(W.groupIndexEstimate([closed,fromFile],{open:true},kinds),null);
 assert.equal(W.groupIndexEstimate([older,closed,fromFile],{open:true},kinds),180000);
 assert.equal(W.runPlanText({open:true,searches:2,groupIndex:true,estimate:W.groupIndexEstimate([older,fromFile],{open:true},kinds)}),'Open boundary · 2 searches · group index on (3 solves) · about 3 min');
 assert.equal(W.runPlanText({open:true,searches:2,groupIndex:true,estimate:W.groupIndexEstimate([closed,fromFile],{open:true},kinds)}),'Open boundary · 2 searches · group index on (3 solves)');
 // and the "last such run" time of a run without group index likewise
 assert.equal(W.lastComparableRun([older,fromFile],{open:true,groupIndex:false},kinds),older);
 assert.equal(W.lastComparableRun([fromFile],{open:true,groupIndex:false},kinds),null);
 // the duration is set only when a run completes in this tab
 const app=read('workspace-app.mjs');
 assert.ok(app.includes('{const started=Date.parse(pending.startedAt);if(Number.isFinite(started))completed.duration=Date.now()-started;}'));
 assert.equal(app.split('.duration=').length,2);
});

test('P5 (B6): one loss column name, "Loss (dB/cm)", with what it counts on the header\'s second line, in Results, Compare and the heated model',async()=>{
 const M=await import(STATIC+'workspace-modes.mjs');
 assert.deepEqual({...M.lossColumn({open:false}),note:undefined},{header:'Loss (dB/cm)',qualifier:'absorption only (closed window)',help:M.ABSORPTION_HELP,note:undefined});
 assert.deepEqual({...M.lossColumn({open:true}),note:undefined},{header:'Loss (dB/cm)',qualifier:'absorption + leakage into the PML',help:M.PML_LOSS_HELP,note:undefined});
 // the notes stay
 assert.equal(M.lossColumn({open:false}).note,M.ABSORPTION_NOTE);assert.equal(M.lossColumn({open:false,lossless:true}).note,M.LOSSLESS_NOTE);assert.equal(M.lossColumn({open:true}).note,M.PML_LOSS_NOTE);
 // the header cell: the name, a space and the qualifier (textContent "Loss (dB/cm) absorption only (closed window)")
 const el=tag=>({tag,className:'',textContent:''}),doc={createElement:el,createTextNode:t=>({text:t})};
 const nodes=M.lossHeaderNodes(doc,'Loss (dB/cm)','absorption only (closed window)');
 assert.deepEqual(nodes.map(n=>[n.className,n.textContent]),[['loss-name','Loss (dB/cm)'],['pol-sep',' '],['loss-qualifier','absorption only (closed window)']]);
 assert.deepEqual(M.lossHeaderNodes(doc,'Loss (dB/cm)',null),[{text:'Loss (dB/cm)'}]);
 const app=read('workspace-app.mjs');
 // Results
 assert.ok(body(app,'function modesTable(run){','\n}').includes("lossHead(cell('th','',{scope:'col',title:loss.help}),loss.header,loss.qualifier)"));
 // Compare: the group "Loss (dB/cm)", its qualifier when both sides count the same, the sides "Loss A/B (dB/cm)"
 const compare=body(app,'// [short header, full label','// one column group per header');
 assert.ok(compare.includes("['Loss (dB/cm)','Loss',"));assert.ok(!compare.includes('Absorption loss'));
 assert.ok(compare.includes("if(full==='Loss')lossHead(group,short,isOpenRun(a)===isOpenRun(b)?(isOpenRun(a)?PML_LOSS_QUALIFIER:LOSS_QUALIFIER):null);"));
 assert.ok(compare.includes("h=full==='Loss'?(isOpenRun(run)?OPEN_LOSS_HELP:ABSORPTION_HELP):help;"));
 // Compare's note for a closed and an open run stays
 const OR=await import(STATIC+'workspace-open-run.mjs');
 assert.equal(OR.COMPARE_LOSS_NOTE,'A counts material absorption only; B also counts leakage. Their difference is not a leakage loss.');
 // the heated model's table
 assert.ok(read('workspace-multiphysics-view.mjs').includes('<span class="loss-name">${esc(table.loss.header)}</span><span class="pol-sep"> </span><span class="loss-qualifier">${esc(table.loss.qualifier)}</span>'));
 // the qualifier is a line of its own that wraps
 assert.ok(read('workspace.css').includes('.loss-name,.loss-qualifier{display:block}.loss-qualifier{white-space:normal;max-width:11em;font-size:10px;font-weight:400;color:#586c87}.compare-table thead th[scope=colgroup] .loss-qualifier{margin:0 auto}'));
});
