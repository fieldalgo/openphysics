// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Project files, version 1 (workspace-project-file.mjs): every model of a Studio tab in one file.
// V-P1 the round trip bit for bit, V-P2 each entry unchanged (its bytes and digest as node:crypto
// computes them), V-P3 one mutation per reading check, refused by name, V-P6 the sizes. The
// committed fixture project-v1.json is checked with Python's hashlib in test_studio_project_file.py.
const test=require('node:test');const assert=require('node:assert/strict');
const {createHash}=require('node:crypto');const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const FIXTURES=path.join(__dirname,'studio_session_fixtures');
const fixture=name=>fs.readFileSync(path.join(FIXTURES,name),'utf8');
let PF,N,P,S;
test.before(async()=>{
 PF=await import(STATIC+'workspace-project-file.mjs');N=await import(STATIC+'workspace-notebook.mjs');
 P=await import(STATIC+'workspace-project.mjs');S=await import(STATIC+'workspace-multiphysics-session.mjs');
});
const setup=()=>({materials:{Core:'Silicon',Oxide:'Silica',Heater:''},temperature:293.15,cooling:'',fixed:'',terminal:''});
const input=(width=500)=>P.snapshot({width,voltage:1,electric:false,heat:false,structure:false,optics:true,wavelength:1550,coreMesh:30},setup());
// a field of k modes whose samples hold the numbers a file must keep bit for bit: negative zero,
// a subnormal, 1e308 and integers above 2^31
const SPECIAL=[-0,5e-324,1e308,2**31+7,2**53-1];
const field=k=>({node_coordinates:[[0,0],[1e-6,0],[0,1e-6],[1e-6,1e-6]],triangles:[[0,1,2],[1,3,2]],
 real:Array.from({length:k},(_,m)=>[[1,0.25*m,-0],[SPECIAL[1],SPECIAL[2],SPECIAL[3]+m]]),imag:Array.from({length:k},(_,m)=>[[0,1e-9*m,SPECIAL[4]],[-2e-3,0,-0]])});
const neff=k=>Array.from({length:k},(_,m)=>2.9-0.17*m);
const run=(job,k=4,extra={})=>({job,completedAt:'2026-11-23T01:00:00.000Z',settings:N.opticalSettings(1550,30,k),input:input(),
 effective_index:neff(k),field:field(k),origin:'local',serverVersion:'0.0.0',...extra});
const view={mode:0,component:'magnitude',window:'Core region'};
// the optical entry: two runs, one of 4 modes (a version 9 session)
const opticalText=()=>N.sessionText(P.withStudy(input(),{modeCount:4}),[run('00000001',2),run('00000002',4,{label:'four modes',pinned:true})],'00000002',['00000001','00000002'],view);
const multiText=()=>fixture('multiphysics-v8.json');
const entries=()=>[PF.projectEntry({id:'m1',kind:'workspace',title:'Optical waveguide',card:'optical',text:opticalText()}),
 PF.projectEntry({id:'m2',kind:'multiphysics',title:'Heated silicon waveguide',card:'heated-waveguide',text:multiText()})];
const project=(over={})=>({name:'Heater study',savedAt:'2026-11-23T13:15:00.000Z',studio:'0.0.2',active:'m2',entries:entries(),...over});
const write=(over)=>{const out=PF.writeProject(project(over));assert.equal(out.ok,true);return out.text;};
// a project read and written again from what it read, as a second Save writes it
const rewrite=(read,over={})=>PF.writeProject({name:read.name,savedAt:read.savedAt,studio:read.studio,active:read.active,
 entries:read.models.map(m=>PF.projectEntry({id:m.id,kind:m.kind,title:m.title,card:m.card,text:PF.sessionWriterText(JSON.parse(m.text))})),...over});
const sha=text=>'sha256:'+createHash('sha256').update(text,'utf8').digest('hex');
// the raw text of each entry's session as it stands in the file (the bytes between "session": and
// the entry's closing brace), found by the JSON grammar rather than by searching for a pattern
function rawSessions(text){
 const doc=JSON.parse(text),out=[];let at=0;
 for(const m of doc.models){const key='"session":';at=text.indexOf(key,text.indexOf(JSON.stringify(m.digest),at))+key.length;
  const start=at;let depth=0,end=start,inString=false;
  for(let i=start;i<text.length;i++){const c=text[i];
   if(inString){if(c==='\\')i++;else if(c==='"')inString=false;continue;}
   if(c==='"')inString=true;else if(c==='{'||c==='[')depth++;else if(c==='}'||c===']'){depth--;if(depth===0){end=i+1;break;}}}
  out.push(text.slice(start,end));at=end;}
 return out;
}
// written back with the session number rules, so a version 9 entry's −0.0 stays as it was
const mutate=(text,f)=>{const doc=JSON.parse(text);f(doc);return S.sessionJson(doc);};

test('V-P1 the envelope: compact, keys in the contract order, each session its writer’s text',()=>{
 const text=write();
 assert.ok(text.startsWith('{"format":"openphysics-studio-project","version":1,"name":"Heater study","savedAt":"2026-11-23T13:15:00.000Z","studio":"0.0.2","active":"m2","models":[{"id":"m1","kind":"workspace","title":"Optical waveguide","card":"optical","bytes":'));
 const doc=JSON.parse(text);assert.deepEqual(Object.keys(doc),[...PF.PROJECT_KEYS]);
 for(const m of doc.models)assert.deepEqual(Object.keys(m),[...PF.ENTRY_KEYS]);
 assert.equal(doc.models[0].session.version,9,'a run of 4 modes needs version 9');assert.equal(doc.models[1].session.version,8);
 const raw=rawSessions(text);assert.equal(raw[0],opticalText());assert.equal(raw[1],multiText());
 assert.ok(!text.includes('\n'),'compact, like a session file');
});
test('V-P1 save, open, save: the second file is byte-identical; −0.0, a subnormal, 1e308 and integers above 2^31 come back bit for bit',()=>{
 const first=write(),read=PF.readProject(first),second=rewrite(read);
 assert.equal(second.ok,true);assert.ok(Buffer.from(second.text,'utf8').equals(Buffer.from(first,'utf8')),'byte-identical');
 assert.ok(first.includes('-0.0'),'negative zero is written -0.0 in the version 9 entry');
 const r=read.models[0].session.runs.find(x=>x.job==='00000002');
 assert.ok(Object.is(r.field.real[0][0][2],-0));assert.equal(r.field.real[0][1][0],5e-324);assert.equal(r.field.real[0][1][1],1e308);
 assert.equal(r.field.real[0][1][2],2**31+7);assert.equal(r.field.imag[0][0][2],2**53-1);
 assert.equal(read.models[0].session.input.model.modeCount,4);assert.equal(read.models[1].session.application,'multiphysics');
 assert.deepEqual(read.models.map(m=>[m.id,m.kind,m.title,m.card]),[['m1','workspace','Optical waveguide','optical'],['m2','multiphysics','Heated silicon waveguide','heated-waveguide']]);
 assert.equal(read.name,'Heater study');assert.equal(read.active,'m2');
 // a version 7 entry (JSON.stringify) and a byte order mark
 const v7=fixture('optical-v7-one.json'),text=PF.writeProject(project({active:'m1',entries:[PF.projectEntry({id:'m1',kind:'workspace',title:'Optical waveguide',card:'optical',text:v7})]})).text;
 const back=PF.readProject('﻿'+text);assert.equal(back.models[0].text,v7);assert.equal(rewrite(back).text,text);
});
test('V-P2 each entry is its session file unchanged; bytes and digest equal node:crypto',()=>{
 const text=write(),doc=JSON.parse(text),raw=rawSessions(text);
 doc.models.forEach((m,i)=>{assert.equal(m.bytes,Buffer.byteLength(raw[i],'utf8'));assert.equal(m.digest,sha(raw[i]));});
 // each entry exported alone is the file today's writers give (the session's own text)
 assert.equal(raw[0],N.sessionText(P.withStudy(input(),{modeCount:4}),[run('00000001',2),run('00000002',4,{label:'four modes',pinned:true})],'00000002',['00000001','00000002'],view));
 const mp=N.parseSession(multiText());
 assert.equal(raw[1],S.writeMultiphysicsSession({document:mp.document,runs:mp.runs,baselines:mp.baselines,selected:mp.selected,view:mp.view}).text);
});
test('V-P2 the committed fixture project-v1.json is what writeProject writes today',()=>{
 assert.equal(write(),fixture('project-v1.json'));
});
test('V-P3 one mutation per reading check, each refused by name',()=>{
 const text=write(),refused=(t,message)=>assert.throws(()=>PF.readProject(t),{message});
 // a value changed in each entry
 refused(mutate(text,d=>{d.models[0].session.runs[0].effective_index[0]=2.8;}),'Optical waveguide changed after it was saved (its check value does not match).');
 refused(mutate(text,d=>{d.models[1].session.runs[0].result.physics.modes1.effective_index.values[0][0]=2.4456501286415877;}),'Heated silicon waveguide changed after it was saved (its check value does not match).');
 // an entry shortened (a run removed)
 refused(mutate(text,d=>{d.models[0].session.runs.pop();}),'Optical waveguide changed after it was saved (its size does not match).');
 // the kind swapped
 refused(mutate(text,d=>{d.models[1].kind='workspace';d.models[0].kind='multiphysics';}),'Optical waveguide is a multiphysics model, but its session is of version 9 (an optical session).');
 refused(mutate(text,d=>{d.models[1].kind='workspace';}),'A project file holds at most one workspace model.');
 // a duplicate id; two workspace entries; active missing or naming no model; an unknown key
 refused(mutate(text,d=>{d.models[1].id='m1';}),'Two models have the same id m1.');
 refused(mutate(text,d=>{d.models.push({...d.models[0],id:'m3'});}),'A project file holds at most one workspace model.');
 refused(mutate(text,d=>{delete d.active;}),'The project file has no "active".');
 refused(mutate(text,d=>{d.active='m9';}),'The model to show (active) is not in the project file.');
 refused(mutate(text,d=>{d.comparisons=[];}),'Unknown key "comparisons" in the project file.');
 refused(mutate(text,d=>{d.models[0].note='x';}),'Optical waveguide: unknown key "note".');
 refused(mutate(text,d=>{delete d.models[0].digest;}),'Optical waveguide: missing digest.');
 // the envelope's other checks
 refused(mutate(text,d=>{d.models=[];}),'A project file holds 1 to 8 models.');
 refused(mutate(text,d=>{d.models=Array.from({length:9},(_,i)=>({...d.models[1],id:'m'+(i+1)}));}),'A project file holds 1 to 8 models.');
 refused(mutate(text,d=>{d.models=Array.from({length:8},(_,i)=>({...d.models[1],id:'m'+(i+1)}));d.active='m1';}),'A project file holds at most 7 multiphysics models.');
 refused(mutate(text,d=>{d.models[0].id='model1';}),'Optical waveguide has an invalid id (m followed by 1 to 3 digits).');
 refused(mutate(text,d=>{d.models[0].id='m1000';}),'Optical waveguide has an invalid id (m followed by 1 to 3 digits).');
 refused(mutate(text,d=>{d.name='x'.repeat(81);}),'The project name is not one Studio writes: A project name has at most 80 characters.');
 refused(mutate(text,d=>{d.name='Heater\u0007study';}),'The project name is not one Studio writes: A project name cannot hold control characters.');
 refused(mutate(text,d=>{d.name='  ';}),'The project name is not one Studio writes: A project name needs 1 to 80 characters.');
 refused(mutate(text,d=>{d.models[0].bytes+=0.5;}),'Optical waveguide has an invalid size.');
 refused(mutate(text,d=>{d.models[0].card='thermal';}),'Optical waveguide names an unknown Library card.');
 refused(mutate(text,d=>{d.models[0].digest='sha256:abc';}),'Optical waveguide has an invalid check value.');
 refused(mutate(text,d=>{d.savedAt='yesterday';}),'The project file has an invalid save time.');
 refused(mutate(text,d=>{d.version=2;}),'This project file is version 2, newer than this Studio reads (version 1). Open it in a newer Studio.');
 refused(mutate(text,d=>{d.version=0;}),'Unsupported project file version.');
 refused(text.slice(0,-1),'This project file is not valid JSON.');
 refused('{"format":"openphysics-studio-session","version":7}','This is not a project file.');
});
test('V-P3 an entry whose check values were computed again still meets parseSession’s own checks, named by the model',()=>{
 const text=write();
 // a run changed and the entry's bytes and digest recomputed: the per-run digest of version 9 refuses it
 const doc=JSON.parse(text);doc.models[0].session.runs[1].effective_index[0]=2.8;
 const changed=PF.sessionWriterText(doc.models[0].session);doc.models[0].bytes=Buffer.byteLength(changed);doc.models[0].digest=sha(changed);
 assert.throws(()=>PF.readProject(S.sessionJson(doc)),{message:'Optical waveguide: Run 2 changed after it was saved (its check value does not match).'});
 // a newer session version inside an entry is refused by its own words (12 since the closed-window search's 11)
 const newer=JSON.parse(text);newer.models[0].session.version=12;const t10=PF.sessionWriterText(newer.models[0].session);newer.models[0].bytes=Buffer.byteLength(t10);newer.models[0].digest=sha(t10);
 assert.throws(()=>PF.readProject(S.sessionJson(newer)),{message:'Optical waveguide: This session file is version 12, newer than this Studio reads (versions 6–11). Open it in a newer Studio.'});
});
test('the workspace entry takes the versions parseSession reads, from its own list',()=>{
 assert.deepEqual([...PF.KIND_VERSIONS.workspace],[...N.OPTICAL_SESSION_VERSIONS]);assert.deepEqual([...N.OPTICAL_SESSION_VERSIONS],[6,7,9,10,11]);  // 10: the optical open boundary (slice P2); 11: the closed-window search (slice C2)
 assert.deepEqual([...PF.KIND_VERSIONS.multiphysics],[8]);
 for(const name of ['optical-v6-one.json','optical-v7-three.json']){const t=fixture(name);
  const text=PF.writeProject(project({active:'m1',entries:[PF.projectEntry({id:'m1',kind:'workspace',title:'Optical waveguide',card:'optical',text:t})]})).text;
  assert.deepEqual(PF.readProject(text).models[0].session,N.parseSession(t),name);}
});
test('V-P6 sizes: 64 MiB ± 1 byte refused before parsing; 16 MiB per entry; the over-limit messages name models',()=>{
 const MiB=1024*1024,text=write();
 let parsed=0;const parse=t=>{parsed++;return JSON.parse(t);};
 // the whole file, at the limit and one byte over (a lowered limit, then the real 64 MiB)
 const limit=Buffer.byteLength(text);assert.doesNotThrow(()=>PF.readProject(text,{limit,parse}));assert.equal(parsed,1);
 assert.throws(()=>PF.readProject(text,{limit:limit-1,parse}),{message:/^This project file is [\d.]+ MB, over the 64 MiB limit\.$/});assert.equal(parsed,1,'not parsed');
 const pad=n=>text.slice(0,-2)+']'+' '.repeat(n-Buffer.byteLength(text))+'}';
 assert.equal(Buffer.byteLength(pad(64*MiB)),64*MiB);assert.doesNotThrow(()=>PF.readProject(pad(64*MiB)));
 parsed=0;assert.throws(()=>PF.readProject(pad(64*MiB+1),{parse}),{message:'This project file is 67 MB, over the 64 MiB limit.'});assert.equal(parsed,0,'refused before parsing');
 assert.equal(PF.MAX_PROJECT_BYTES,64*MiB);assert.equal(PF.MAX_ENTRY_BYTES,16*MiB);
 // an entry at 16 MiB and one byte over: the reader's limit (the writers' own 16 MiB question is
 // checked in studio_mode_count.cjs and studio_workspace_multiphysics_session.cjs)
 const padded=n=>{const t=opticalText();return t.slice(0,-1)+' '.repeat(n-Buffer.byteLength(t))+'}';};
 const at=padded(16*MiB),over=padded(16*MiB+1);assert.equal(Buffer.byteLength(at),16*MiB);
 assert.doesNotThrow(()=>PF.projectEntry({id:'m1',kind:'workspace',title:'Optical waveguide',text:at}));
 assert.equal(PF.writeProject(project({active:'m1',entries:[PF.projectEntry({id:'m1',kind:'workspace',title:'Optical waveguide',text:at})]})).ok,true);
 assert.throws(()=>PF.writeProject(project({active:'m1',entries:[PF.projectEntry({id:'m1',kind:'workspace',title:'Optical waveguide',text:over})]})),{message:'Optical waveguide is 17 MB, over the 16 MiB session limit.'});
 const huge=JSON.parse(write());huge.models[0].session.runs[0].label='x'.repeat(16*MiB);
 assert.throws(()=>PF.readProject(S.sessionJson(huge)),{message:'Optical waveguide is 17 MB, over the 16 MiB session limit.'});
 // a Save over the limit names the largest models to export
 const e=entries(),bytes=e[0].bytes+e[1].bytes;
 const refused=PF.writeProject(project({entries:e}),{limit:bytes});assert.equal(refused.ok,false);
 assert.equal(refused.refusal,`The project is ${S.sizeText(refused.bytes)}, over the 64 MiB limit. Export ${e[0].bytes>e[1].bytes?'Optical waveguide':'Heated silicon waveguide'} (${S.sizeText(Math.max(e[0].bytes,e[1].bytes))}) to its own file, or remove runs.`);
 assert.equal(PF.overLimitText(71e6,[{title:'Optical waveguide',bytes:15e6},{title:'Heated silicon waveguide',bytes:22e6}],64*MiB),'The project is 71 MB, over the 64 MiB limit. Export Heated silicon waveguide (22 MB) to its own file, or remove runs.');
 assert.equal(PF.overLimitText(90e6,[{title:'A',bytes:16e6},{title:'B',bytes:15e6},{title:'C',bytes:14e6}],64*MiB),'The project is 90 MB, over the 64 MiB limit. Export A (16 MB) and B (15 MB) to their own files, or remove runs.');
});
test('project names and file names',()=>{
 assert.equal(PF.validateProjectName('  Heater study '),'Heater study');
 assert.equal(PF.validateProjectName('é'.repeat(80)),'é'.repeat(80));
 assert.throws(()=>PF.validateProjectName('é'.repeat(81)),{message:'A project name has at most 80 characters.'});
 assert.throws(()=>PF.validateProjectName(''),{message:'A project name needs 1 to 80 characters.'});
 assert.throws(()=>PF.validateProjectName('a\nb'),{message:'A project name cannot hold control characters.'});
 assert.equal(PF.projectFileName('Heater study'),'heater-study.json');assert.equal(PF.projectFileName(null),'untitled-project.json');
 assert.equal(PF.projectFileName('Untitled project'),'untitled-project.json');assert.equal(PF.projectFileName('Δn'),'n.json');
 assert.equal(PF.nameFromFile('design-a-ng.json'),'design-a-ng');assert.equal(PF.nameFromFile('Heater study.JSON'),'Heater study');
 assert.equal(PF.nameFromFile('.json'),'Untitled project');assert.equal(PF.nameFromFile('a'.repeat(120)+'.json'),'a'.repeat(80));
 assert.throws(()=>PF.writeProject(project({name:''})),{message:'A project name needs 1 to 80 characters.'});
 assert.throws(()=>PF.writeProject(project({active:'m7'})),{message:'The model shown is not in the project.'});
});
test('the save notice names every model, and the maps or fields left out',()=>{
 const models=[{title:'Optical waveguide',parts:PF.modelParts({runs:2,comparison:true})},{title:'Heated silicon waveguide',parts:PF.modelParts({runs:1,baseline:true})}];
 assert.equal(PF.projectSavedNotice({name:'Heater study',file:'heater-study.json',via:'picker',models}),'Saved Heater study to heater-study.json: Optical waveguide (2 runs, the comparison) and Heated silicon waveguide (1 run, the without-heater result).');
 assert.equal(PF.projectSavedNotice({name:'Heater study',file:'heater-study.json',models}),"Project file heater-study.json sent to your browser's Downloads: Optical waveguide (2 runs, the comparison) and Heated silicon waveguide (1 run, the without-heater result).");
 assert.equal(PF.projectSavedNotice({name:'x',file:'x.json',known:true,again:true,models:[{title:'Steady heat conduction',parts:PF.modelParts({inputsOnly:true})}],notKept:[{title:'Heated silicon waveguide',kind:'multiphysics',runs:[1,3]}],after:' Then.'}),'Downloaded x.json again: Steady heat conduction (inputs). Heated silicon waveguide keeps values only for Run 1 and Run 3, without maps. Then.');
 assert.ok(!PF.projectSavedNotice({name:'x',file:'x.json',models}).includes('not in this file'));
});
test('the title bar’s project line and the leave question, in the round-14 words',async()=>{
 const W=await import(STATIC+'workspace-persistence.mjs'),when=()=>'13:15';
 const file=how=>({name:'heater-study.json',how,savedAt:'2026-11-23T13:15:00.000Z'});
 assert.equal(W.UNTITLED_PROJECT,PF.UNTITLED_PROJECT);
 assert.equal(W.projectTitle({name:'Heater study',models:2,file:file('picker'),current:true,recovery:'kept'},when),'Heater study · heater-study.json · saved 13:15');
 assert.equal(W.projectTitle({name:'Heater study',models:2,file:file('download'),current:true,recovery:'kept'},when),'Heater study · heater-study.json · downloaded 13:15');
 assert.equal(W.projectTitle({name:'Heater study',models:2,file:file('opened'),current:true},when),'Heater study · heater-study.json · opened');
 assert.equal(W.projectTitle({name:'Heater study',models:2,file:file('picker'),current:false,recovery:'kept'},when),'Heater study · heater-study.json · changed since saved 13:15 · kept for recovery in this browser');
 assert.equal(W.projectTitle({name:null,models:1,file:null,recovery:'kept'},when),'Untitled project · not saved to a file · kept for recovery in this browser');
 assert.equal(W.projectTitle({name:null,models:1,file:null,recovery:null},when),'Untitled project · not saved to a file · not in browser recovery yet');
 assert.equal(W.projectTitle({name:null,models:0},when),'Untitled project · no model chosen');
 assert.equal(W.projectTitle({name:'H',models:1,file:file('picker'),current:true,recovery:'conflict'},when),'H · heater-study.json · saved 13:15 · browser recovery changed in another tab');
 assert.equal(W.projectHint(file('download')),'Your browser may have added “ (1)” to the file name.');assert.equal(W.projectHint(file('picker')),'');assert.equal(W.projectHint(null),'');
 assert.equal(W.projectLeaveText({name:'Heater study',models:[]}),null);assert.equal(W.projectLeaveText({models:[{title:'Optical waveguide',runs:0}]}),null);
 assert.deepEqual(W.projectLeaveText({name:'Heater study',models:[{title:'Optical waveguide',runs:2},{title:'Heated silicon waveguide',runs:1}]}),{title:'Replace Heater study?',
  description:'Optical waveguide (2 runs) and Heated silicon waveguide (1 run) have runs in no file. Save project first to keep them.',save:{kind:'project',label:'Save project, then open'},leave:'Open without saving',stay:'Cancel'});
 assert.equal(W.projectLeaveText({models:[{title:'Optical waveguide',runs:1}]}).description,'Optical waveguide (1 run) has a run in no file. Save project first to keep it.');
 assert.equal(W.projectLeaveText({models:[{title:'Optical waveguide',runs:1}]}).title,'Replace Untitled project?');
});
