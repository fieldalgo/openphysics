// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Library recovery after a restart (after rounds 26–30): one box with one button per piece of
// work, a detail line saying how the browser copy compares with its file, older copies folded
// under "Earlier copies in this browser (N)", and model cards with a plain line instead of their
// own restore buttons. Plain text comparison only: no RegExp is built from a dynamic string.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const read=name=>fs.readFileSync(path.join(__dirname,STATIC,name),'utf8');
const when=t=>t;
const file='heater-study.json';

test('5.1: the detail line under the newest button, strings 1–6',async()=>{
 const A=await import(STATIC+'workspace-applications.mjs');
 const base={runs:1,model:'Optical waveguide',names:['Run 1'],savedAt:'T'};
 // 1 no file
 assert.equal(A.resumeDetail({...base,file:null},when),'Kept in this browser T · not saved to a file');
 // 2 same as a file saved here
 assert.equal(A.resumeDetail({...base,file,fileCurrent:true,fileSavedAt:'F'},when),'Kept in this browser T · same as heater-study.json, saved F · Open file… gives the same runs');
 // 3 same as an opened file (no save time)
 assert.equal(A.resumeDetail({...base,file,fileCurrent:true},when),'Kept in this browser T · same as heater-study.json as opened · Open file… gives the same runs');
 // 4 changed since a file saved here
 assert.equal(A.resumeDetail({...base,file,fileCurrent:false,fileSavedAt:'F'},when),'Kept in this browser T · newer than heater-study.json, saved here F');
 // 5 changed since an opened file
 assert.equal(A.resumeDetail({...base,file,fileCurrent:false},when),'Kept in this browser T · newer than heater-study.json as opened');
 // 6 a file named, its match unknown
 assert.equal(A.resumeDetail({...base,file,fileCurrent:null},when),'Kept in this browser T · last linked to heater-study.json');
 // the other model's runs already in this tab (no pair): the tab's run names
 assert.equal(A.resumeDetail({...base,file:null,also:[{model:'Heated silicon waveguide',names:['Run 1','Run 2'],runs:2,inTab:true}]},when),
  'Kept in this browser T · not saved to a file · Heated silicon waveguide · Run 1, Run 2 already in this tab');
 // a record of the other model not in the tab adds nothing (it is offered on its own, or as the pair)
 assert.equal(A.resumeDetail({...base,file:null,also:[{model:'Heated silicon waveguide',names:['Run 1'],runs:1,inTab:false}]},when),'Kept in this browser T · not saved to a file');
 // the default time words are offerTime's
 const now=new Date();assert.equal(A.resumeDetail({...base,savedAt:now.toISOString()}),'Kept in this browser '+A.offerTime(now.toISOString())+' · not saved to a file');
});

test('5.2: a pair is the same as its file only when both records are; T is the newer time',async()=>{
 const A=await import(STATIC+'workspace-applications.mjs');
 const optical={runs:4,model:'Optical waveguide',names:[],savedAt:'2026-11-26T11:40:00Z',file,fileSavedAt:'F'};
 const pair=(fileCurrent,savedAt='2026-11-26T11:12:00Z')=>({model:'Heated silicon waveguide',runs:1,savedAt,fileCurrent});
 // one same, the other changed: string 4
 assert.equal(A.resumeDetail({...optical,fileCurrent:true,pair:pair(false)},when),'Kept in this browser 2026-11-26T11:40:00Z · newer than heater-study.json, saved here F');
 assert.equal(A.resumeDetail({...optical,fileCurrent:false,pair:pair(true)},when),'Kept in this browser 2026-11-26T11:40:00Z · newer than heater-study.json, saved here F');
 // both same: string 2
 assert.equal(A.resumeDetail({...optical,fileCurrent:true,pair:pair(true)},when),'Kept in this browser 2026-11-26T11:40:00Z · same as heater-study.json, saved F · Open file… gives the same runs');
 // T is the newer of the two records' times, whichever comes first
 assert.equal(A.resumeDetail({...optical,fileCurrent:true,pair:pair(true,'2026-11-26T11:50:00Z')},when),'Kept in this browser 2026-11-26T11:50:00Z · same as heater-study.json, saved F · Open file… gives the same runs');
 // an opened file: strings 3 and 5
 const {fileSavedAt,...opened}=optical;
 assert.equal(A.resumeDetail({...opened,fileCurrent:true,pair:pair(true)},when),'Kept in this browser 2026-11-26T11:40:00Z · same as heater-study.json as opened · Open file… gives the same runs');
 assert.equal(A.resumeDetail({...opened,fileCurrent:true,pair:pair(false)},when),'Kept in this browser 2026-11-26T11:40:00Z · newer than heater-study.json as opened');
 // the newest choice of a pair: label without time or file words, the detail beside it
 const choices=A.resumeChoices({...optical,fileCurrent:false,pair:pair(true)},[],when);
 assert.equal(choices.newest.label,'Restore newest from this browser: Optical waveguide (4 runs) and Heated silicon waveguide (1 run)');
 assert.equal(choices.newest.pair,true);
 assert.equal(choices.newest.detail,'Kept in this browser 2026-11-26T11:40:00Z · newer than heater-study.json, saved here F');
});

test('5.3: newest, at most one other piece of work, and every remaining record as an earlier copy',async()=>{
 const A=await import(STATIC+'workspace-applications.mjs');
 assert.deepEqual(A.resumeChoices(null,[],when),{newest:null,other:null,earlier:[]});
 // Y1 order: the newest record with runs leads whatever its kind
 const o3={runs:3,model:'Optical waveguide',names:['Run 1','Run 2','Run 3'],savedAt:'2026-11-26T11:40:00Z',file:null};
 const h1={runs:1,model:'Heated silicon waveguide',names:['Run 1'],savedAt:'2026-11-26T11:30:00Z',file:null,index:0};
 const o2={runs:2,model:'Optical waveguide',names:['Run 1','Run 2'],savedAt:'2026-11-26T11:20:00Z',file:null,index:1};
 const h0={runs:1,model:'Heated silicon waveguide',names:['Run 1'],savedAt:'2026-11-26T11:10:00Z',file:'old.json',fileCurrent:true,fileSavedAt:'F0',index:2};
 const c=A.resumeChoices(o3,[o2,h0,h1],when);
 assert.deepEqual({kind:c.newest.kind,newest:c.newest.newest,label:c.newest.label,detail:c.newest.detail},
  {kind:'latest',newest:true,label:'Restore newest from this browser: Optical waveguide · 3 runs · Run 1, Run 2, Run 3',detail:'Kept in this browser 2026-11-26T11:40:00Z · not saved to a file'});
 // the other model's newest record, not paired and not in the tab
 assert.deepEqual(c.other,{kind:'earlier',index:0,label:'Restore from this browser: Heated silicon waveguide · 1 run · Run 1',detail:'Older · kept in this browser 2026-11-26T11:30:00Z · not saved to a file'});
 // the rest, newest first, as older copies
 assert.deepEqual(c.earlier,[
  {kind:'earlier',index:1,label:'Restore Optical waveguide · 2 runs · Run 1, Run 2',detail:'Older copy · kept in this browser 2026-11-26T11:20:00Z · not saved to a file'},
  {kind:'earlier',index:2,label:'Restore Heated silicon waveguide · 1 run · Run 1',detail:'Older copy · kept in this browser 2026-11-26T11:10:00Z · matched old.json as saved F0'}]);
 // a newer record without runs does not lead; it is listed as an earlier copy
 const empty={runs:0,model:'Optical waveguide',names:[],savedAt:'2026-11-26T11:50:00Z',file:null};
 const e=A.resumeChoices(empty,[{...o2,index:0}],when);
 assert.equal(e.newest.index,0);assert.equal(e.newest.kind,'earlier');assert.deepEqual(e.earlier.map(x=>x.kind),['latest']);
 // other is null when the other model's runs are in the tab
 const tab=A.resumeChoices(o3,[o2,h0,h1],when,{inTab:['Heated silicon waveguide']});
 assert.equal(tab.other,null);assert.deepEqual(tab.earlier.map(x=>x.index),[0,1,2]);
 // other is null when paired, and the pair's second record is listed nowhere (W4)
 const pairOf=h=>({model:h.model,runs:h.runs,savedAt:h.savedAt,fileCurrent:false});
 const both={...o3,file:'p.json',fileCurrent:false,pair:pairOf({...h1})},h1p={...h1,file:'p.json',fileCurrent:false};
 const p=A.resumeChoices(both,[o2,h0,h1p],when);
 assert.equal(p.other,null);assert.equal(p.newest.pair,true);assert.deepEqual(p.earlier.map(x=>x.index),[1,2]);
 // the count: newest + other + earlier = every record, minus the pair's second record
 for(const [r,n] of [[c,4],[tab,4],[p,3]])assert.equal(1+(r.other?1:0)+r.earlier.length,n);
 // the storage index is kept when an unreadable record is skipped
 const skipped=A.resumeChoices(null,[{runs:1,savedAt:'T0',index:0},{runs:2,savedAt:'T2',index:2}],when);
 assert.deepEqual([skipped.newest,...skipped.earlier].map(x=>x.index),[0,2]);
 // an earlier copy whose record was changed after its file, or whose match is unknown, does not say "matched"
 const later=A.resumeChoices(o3,[{...o2,file:'x.json',fileCurrent:false,fileSavedAt:'F'},{...o2,index:3,file:'x.json',fileCurrent:true}],when,{inTab:['Heated silicon waveguide']});
 assert.deepEqual(later.earlier.map(x=>x.detail),['Older copy · kept in this browser 2026-11-26T11:20:00Z · last linked to x.json','Older copy · kept in this browser 2026-11-26T11:20:00Z · matched x.json as opened']);
});

test('5.4: no label or detail says "restored separately", "saved" before a browser time, or "older ·" outside older entries',async()=>{
 const A=await import(STATIC+'workspace-applications.mjs');
 const also=[{model:'Heated silicon waveguide',names:['Run 1'],runs:1,inTab:false}];
 const cases=[];
 for(const fileCurrent of [true,false,null])for(const fileSavedAt of ['F',undefined])for(const f of [file,null]){
  const latest={runs:2,model:'Optical waveguide',names:['Run 1','Run 2'],savedAt:'T1',file:f,fileCurrent,...(fileSavedAt?{fileSavedAt}:{}),also};
  const heated={runs:1,model:'Heated silicon waveguide',names:['Run 1'],savedAt:'T0',file:f,fileCurrent,index:0,also:[{model:'Optical waveguide',names:['Run 1','Run 2'],runs:2,inTab:false}]};
  cases.push(A.resumeChoices(latest,[heated,{...latest,savedAt:'T-1',index:1}],when));
  cases.push(A.resumeChoices({...latest,pair:{model:'Heated silicon waveguide',runs:1,savedAt:'T0',fileCurrent}},[heated],when));
 }
 for(const c of cases){
  const all=[c.newest,c.other,...c.earlier].filter(Boolean);
  for(const x of all){
   for(const text of [x.label,x.detail]){
    assert.ok(!text.includes('restored separately'),text);
    assert.ok(!text.includes('also in this project'),text);
    assert.ok(!text.includes(' · saved T'),text);
    assert.ok(!text.includes('older ·'),text);
   }
   assert.ok(!x.label.includes('Kept')&&!x.label.includes('file'),x.label);
   // round 10: never "(this browser)", Resume or Recover in a recovery offer
   for(const text of [x.label,x.detail])assert.doesNotMatch(text,/\(this browser|Resume|Recover/);
  }
  assert.ok(c.newest.detail.startsWith('Kept in this browser '));
  if(c.other)assert.ok(c.other.detail.startsWith('Older · kept in this browser '));
  for(const x of c.earlier)assert.ok(x.detail.startsWith('Older copy · kept in this browser '));
 }
 // coordinator ruling 2026-11-26: an older copy whose record changed after its file (fileCurrent
 // false) or whose match is unknown (null) is only "last linked to" its file: never a match or "newer"
 for(const fileCurrent of [false,null])for(const fileSavedAt of ['F',undefined]){
  const c=A.resumeChoices({runs:3,model:'Optical waveguide',names:[],savedAt:'2026-11-26T12:00:00Z',file:null},
   [{runs:2,model:'Optical waveguide',names:[],savedAt:'2026-11-26T11:00:00Z',file,fileCurrent,...(fileSavedAt?{fileSavedAt}:{}),index:0}],when);
  assert.equal(c.earlier[0].detail,'Older copy · kept in this browser 2026-11-26T11:00:00Z · last linked to heater-study.json');
 }
 // the Workspace tools list (sessionLine) names the other model without "(restored separately)"
 assert.equal(A.sessionLine({model:'Optical waveguide',runs:1,names:['Run 1'],file,also:[{model:'Heated silicon waveguide',names:['Run 1'],runs:1,inTab:false}]}),
  'Optical waveguide · 1 run · Run 1 · file heater-study.json · also in this project: Heated silicon waveguide · Run 1');
 assert.ok(A.alsoWords({also:[{model:'Heated silicon waveguide',names:['Run 1'],runs:1,inTab:true}]}).endsWith(' (already in this tab)'));
 // the words are gone from the module and the app
 for(const name of ['workspace-applications.mjs','workspace-app.mjs'])assert.ok(!read(name).includes('restored separately'),name);
});

test('5.5: a model card with a kept record says where to restore it, without a button',async()=>{
 const A=await import(STATIC+'workspace-applications.mjs');
 assert.equal(A.cardKeptText(4),'Kept in this browser · 4 runs · Restore at the top of the page');
 assert.equal(A.cardKeptText(1),'Kept in this browser · 1 run · Restore at the top of the page');
 // the card buttons are gone with their functions
 assert.equal(A.cardResumeChoice,undefined);assert.equal(A.opticalResumeChoice,undefined);
 const lib=read('workspace-applications.mjs'),css=read('workspace.css');
 for(const word of ['card-resume',"'resume-'+key","'-start-new'",'CARD_START_NEW_TEXT'])assert.ok(!lib.includes(word),word);
 assert.ok(!css.includes('.card-resume'));
 // the newest button has a style of its own, and the box keeps its heading and Not now
 assert.ok(css.includes('.resume-actions .primary'));
 assert.equal(A.RESUME_NOT_NOW_TEXT,'Not now (choose a model below)');
 assert.equal(A.RESUME_NOTE,'Restore brings back completed runs kept in this browser, without recomputing. Open file… at the top opens a project file instead.');
 assert.equal(A.earlierCopiesText(2),'Earlier copies in this browser (2)');
});

// A small DOM, enough for renderApplications: elements with children, attributes and text.
function fakeDocument(){
 class El{constructor(tag){this.tagName=tag.toUpperCase();this.children=[];this.attrs={};this.dataset={};this.style={};this._text='';this.id='';this.className='';this.listeners={};}
  append(...c){for(const x of c){if(typeof x==='string'){const t=new El('#text');t._text=x;this.children.push(t);}else{x.parentElement=this;this.children.push(x);}}}
  after(x){const p=this.parentElement,i=p.children.indexOf(this);x.parentElement=p;p.children.splice(i+1,0,x);}
  replaceChildren(...c){this.children=[];this.append(...c);}
  setAttribute(k,v){this.attrs[k]=String(v);if(k==='id')this.id=String(v);}
  getAttribute(k){return this.attrs[k]??null;}
  addEventListener(type,f){(this.listeners[type]||=[]).push(f);}
  set textContent(v){this.children=[];this._text=String(v);}
  get textContent(){return this._text+this.children.map(c=>c.textContent).join('');}
  all(){return [this,...this.children.flatMap(c=>c.all())];}
  querySelectorAll(sel){return this.all().slice(1).filter(e=>match(e,sel));}
  querySelector(sel){return this.querySelectorAll(sel)[0]||null;}
  closest(sel){let e=this;while(e){if(match(e,sel))return e;e=e.parentElement;}return null;}
 }
 const match=(e,sel)=>sel.startsWith('#')?e.id===sel.slice(1):sel.startsWith('.')?(' '+e.className+' ').includes(' '+sel.slice(1)+' '):sel.startsWith('[data-')?e.dataset[sel.slice(6,-1).replace(/-([a-z])/g,(_,c)=>c.toUpperCase())]!==undefined:e.tagName===sel.toUpperCase();
 const doc={createElement:tag=>new El(tag),getElementById:id=>doc.root.all().find(e=>e.id===id)||null,activeElement:null};
 doc.root=new El('div');doc.root.ownerDocument=doc;return doc;
}

test('the Library page: one box (a disclosure), the detail line, earlier copies closed, card lines',async()=>{
 const A=await import(STATIC+'workspace-applications.mjs');
 const doc=fakeDocument(),host=doc.root;
 const latest={runs:4,model:'Optical waveguide',names:['Run 1','Run 2','Run 3','Run 4'],savedAt:'2026-11-26T11:40:00Z',file,fileCurrent:false,fileSavedAt:'2026-11-26T11:12:00Z'};
 const older={runs:2,model:'Optical waveguide',names:['Run 1','Run 2'],savedAt:'2026-11-26T11:12:00Z',file,fileCurrent:true,fileSavedAt:'2026-11-26T11:12:00Z',index:0};
 const calls=[];
 const resume={latest,earlier:[older],onLatest:()=>calls.push('latest'),onEarlier:i=>calls.push('earlier '+i),onStartNew:()=>calls.push('not now'),onToggle:open=>calls.push('toggle '+open)};
 const prev=globalThis.document;globalThis.document=doc;
 try{
  A.renderApplications(host,resume,{},{kept:{optical:4}});
  const box=host.querySelector('#resume-box');
  assert.equal(box.tagName,'DETAILS');assert.equal(box.open,true);
  assert.equal(box.querySelector('summary').textContent,'Continue where you left off');
  const newest=host.querySelector('#resume-newest');
  assert.equal(newest.className,'primary');assert.equal(newest.getAttribute('aria-describedby'),'resume-newest-detail');
  assert.equal(newest.textContent,'Restore newest from this browser: Optical waveguide · 4 runs · Run 1, Run 2, Run 3, Run 4');
  const detail=host.querySelector('#resume-newest-detail');assert.equal(detail.tagName,'P');assert.equal(detail.className,'resume-detail');
  assert.ok(detail.textContent.startsWith('Kept in this browser ')&&detail.textContent.includes(' · newer than heater-study.json, saved here '));
  assert.equal(host.querySelector('#resume-other'),null);
  const copies=host.querySelector('#earlier-copies');assert.equal(copies.tagName,'DETAILS');assert.equal(copies.open,false);
  assert.equal(copies.querySelector('summary').textContent,'Earlier copies in this browser (1)');
  assert.equal(copies.querySelector('button').textContent,'Restore Optical waveguide · 2 runs · Run 1, Run 2');
  assert.equal(copies.querySelector('button').dataset.resumeRecord,'0');
  assert.ok(copies.querySelector('p').textContent.startsWith('Older copy · kept in this browser '));
  assert.ok(!box.textContent.includes('restored separately'));
  // Not now closes the box (A1), it does not remove it
  const notNow=host.querySelector('#resume-start-new');assert.equal(notNow.textContent,'Not now (choose a model below)');
  notNow.onclick();assert.deepEqual(calls,['not now']);
  // the card line: non-interactive, inside the card; no card restore buttons
  const card=host.querySelectorAll('[data-template]').find(b=>b.dataset.template==='optical');
  assert.equal(card.querySelector('.card-kept').textContent,'Kept in this browser · 4 runs · Restore at the top of the page');
  assert.equal(card.querySelector('.card-kept').tagName,'SPAN');
  for(const id of ['resume-optical','resume-heated-waveguide','optical-start-new','heated-waveguide-start-new'])assert.equal(host.querySelector('#'+id),null,id);
  assert.equal(host.querySelectorAll('.card-kept').length,1);
  // collapsed: the box renders closed, with the same buttons inside
  A.renderApplications(host,{...resume,collapsed:true},{},{kept:{optical:4}});
  assert.equal(host.querySelector('#resume-box').open,false);assert.ok(host.querySelector('#resume-newest'));
  // the earlier copies keep their open state across a re-render
  host.querySelector('#earlier-copies').open=true;
  A.renderApplications(host,resume,{},{kept:{optical:4}});
  assert.equal(host.querySelector('#earlier-copies').open,true);
  // two pieces of work: a second button with its "Older ·" detail
  const heated={runs:1,model:'Heated silicon waveguide',names:['Run 1'],savedAt:'2026-11-26T11:30:00Z',file:null,index:1};
  A.renderApplications(host,{...resume,earlier:[older,heated]},{},{kept:{optical:4,'heated-waveguide':1}});
  const other=host.querySelector('#resume-other');
  assert.equal(other.textContent,'Restore from this browser: Heated silicon waveguide · 1 run · Run 1');
  assert.equal(other.getAttribute('aria-describedby'),'resume-other-detail');
  assert.ok(host.querySelector('#resume-other-detail').textContent.startsWith('Older · kept in this browser '));
  other.onclick();assert.equal(calls.at(-1),'earlier 1');
  assert.equal(host.querySelectorAll('.card-kept').length,2);
  // no earlier copies: no disclosure
  A.renderApplications(host,{...resume,earlier:[]},{},{});
  assert.equal(host.querySelector('#earlier-copies'),null);
 }finally{globalThis.document=prev;}
});

test('the app passes the card lines, the tab models and the pair record\'s file match; Not now collapses',()=>{
 const app=read('workspace-app.mjs');
 assert.ok(!app.includes('cardResumeChoice')&&!app.includes('cardResumeOffers'));
 assert.ok(app.includes('fileCurrent:o.record.fileCurrent'));
 assert.ok(app.includes('resumeCollapsed=true'));
 assert.ok(!app.includes('resumeDismissed'));
});
