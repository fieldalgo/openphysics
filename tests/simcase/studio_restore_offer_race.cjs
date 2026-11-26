// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// The restore box after a reload shows its first offer only once the stored records have been read:
// the latest record and the earlier ones (renderEarlierSessions). Before this, #resume-newest was
// shown and clickable while the earlier records were still being read; it restored one model of a
// pair, then became the pair a moment later (macos-15, run 45891974567, the project browser check's
// R20). Plain text comparison only: no RegExp is built from a dynamic string.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const read=name=>fs.readFileSync(path.join(__dirname,STATIC,name),'utf8');

// A small DOM, enough for renderApplications: elements with children, attributes and text.
function fakeDocument(){
 class El{constructor(tag){this.tagName=tag.toUpperCase();this.children=[];this.attrs={};this.dataset={};this.style={};this._text='';this.id='';this.className='';this.listeners={};}
  append(...c){for(const x of c){if(typeof x==='string'){const t=new El('#text');t._text=x;this.children.push(t);}else{x.parentElement=this;this.children.push(x);}}}
  replaceChildren(...c){this.children=[];this.append(...c);}
  setAttribute(k,v){this.attrs[k]=String(v);if(k==='id')this.id=String(v);}
  getAttribute(k){return this.attrs[k]??null;}
  addEventListener(type,f){(this.listeners[type]||=[]).push(f);}
  set textContent(v){this.children=[];this._text=String(v);}
  get textContent(){return this._text+this.children.map(c=>c.textContent).join('');}
  all(){return [this,...this.children.flatMap(c=>c.all())];}
  querySelectorAll(sel){return this.all().slice(1).filter(e=>match(e,sel));}
  querySelector(sel){return this.querySelectorAll(sel)[0]||null;}
 }
 const match=(e,sel)=>sel.startsWith('#')?e.id===sel.slice(1):sel.startsWith('.')?(' '+e.className+' ').includes(' '+sel.slice(1)+' '):e.tagName===sel.toUpperCase();
 const doc={createElement:tag=>new El(tag),getElementById:id=>doc.root.all().find(e=>e.id===id)||null,activeElement:null};
 doc.root=new El('div');doc.root.ownerDocument=doc;return doc;
}

test('the gate opens only once the latest and the earlier records have both been read',async()=>{
 const A=await import(STATIC+'workspace-applications.mjs');
 for(const order of [['latestRead','earlierRead'],['earlierRead','latestRead']]){
  const gate=A.recoveryReadGate();assert.equal(gate.ready,false);
  gate[order[0]]();assert.equal(gate.ready,false,order[0]);
  gate[order[1]]();assert.equal(gate.ready,true);
  gate[order[0]]();gate[order[1]]();assert.equal(gate.ready,true,'stays open');
 }
});

test('a delayed earlier-records read: no #resume-newest before it resolves; the first one is the pair',async()=>{
 const A=await import(STATIC+'workspace-applications.mjs');
 const doc=fakeDocument(),host=doc.root,prev=globalThis.document;globalThis.document=doc;
 // the app's order (loadNotebookRecovery): the latest record, then renderEarlierSessions; any
 // render in between (the save indicator, a server reply) draws the Library with what is known
 const gate=A.recoveryReadGate();
 const latest={runs:2,model:'Optical waveguide',names:['Run 1','Run 2'],savedAt:'2026-11-26T21:17:19Z',file:'r20-both.json',fileCurrent:false,fileSavedAt:'2026-11-26T21:17:00Z'};
 let earlier=null;
 const offer=()=>({latest:earlier?{...latest,pair:{model:'Heated silicon waveguide',runs:1,savedAt:'2026-11-26T21:17:08Z',fileCurrent:true}}:latest,earlier:[],onLatest(){},onEarlier(){},onPair(){},onStartNew(){},onToggle(){}});
 const seen=[];
 const render=()=>{A.renderApplications(host,gate.ready?offer():null,null,{onOpenFile(){},kept:{optical:2}});const b=host.querySelector('#resume-newest');seen.push(b?{pair:b.dataset.resumePair??null,text:b.textContent}:null);};
 let release;const loadEarlier=new Promise(r=>{release=r;});
 try{
  render();                                   // the first page, nothing read
  gate.latestRead();render();                 // the latest record read
  const reading=(async()=>{await loadEarlier;earlier=[{model:'Heated silicon waveguide'}];gate.earlierRead();render();})();
  render();                                   // a render while the earlier records are read
  assert.deepEqual(seen,[null,null,null],JSON.stringify(seen));
  release();await reading;
  assert.equal(seen.length,4);
  assert.deepEqual(seen[3],{pair:'true',text:'Restore newest from this browser: Optical waveguide (2 runs) and Heated silicon waveguide (1 run)'});
  assert.ok(host.querySelector('#resume-newest-detail'));
  // the Library itself is drawn throughout: Open file… and the cards, without the box
  assert.ok(host.querySelector('#library-open-file'));
 }finally{globalThis.document=prev;}
});

test('the app reads both before it offers: resumeOffer waits on the gate; the reads open it',()=>{
 const app=read('workspace-app.mjs');
 assert.ok(app.includes('const recoveryRead=recoveryReadGate();'));
 assert.ok(app.includes('function resumeOffer(){\n if(!recoveryRead.ready)return null;\n if(runs.length)return null;\n'));
 // renderEarlierSessions opens its half once a read completes (or fails), not when superseded
 assert.ok(app.includes("let list=[];try{list=await notebookStore.loadEarlier();}catch{if(generation===earlierGeneration){recoveryRead.earlierRead();if(ui.page==='Applications')render();}return;}\n if(generation!==earlierGeneration)return;\n recoveryRead.earlierRead();"));
 // loadNotebookRecovery opens its half on every way out: read (before the check for this tab's own
 // save, which supersedes it) or failed; latestOffer is set in the same task, before any render
 const load=app.slice(app.indexOf('async function loadNotebookRecovery(){'),app.indexOf('// The model a recovered multiphysics session names'));
 assert.ok(load.includes('const recovered=readNotebookRecovery(record);recoveryRead.latestRead();if(version!==notebookLoadVersion)return;'),load);
 assert.ok(load.includes('}catch(error){recoveryRead.latestRead();if(version!==notebookLoadVersion)return;'),load);
 assert.equal(load.split('recoveryRead.latestRead();').length-1,2,load);
 // the read and latestOffer are in one task: no await between latestRead() and latestOffer=
 const between=load.slice(load.indexOf('recoveryRead.latestRead();'),load.indexOf('latestOffer=recovered?'));
 assert.ok(!between.includes('await'),between);
});
