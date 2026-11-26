// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Round 32 (agent proxy round 32 on main f0c759a): K4, the Library files bar holds "Open file…"
// and the project name only; the note about a portable project file is gone. The restore box keeps
// its own note. Plain text comparison only: no RegExp is built from a dynamic string.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const read=name=>fs.readFileSync(path.join(__dirname,STATIC,name),'utf8');
const OLD_NOTE='A project file is the copy that moves between computers; browser recovery stays in this browser.';

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

test('K4: the Library files bar renders Open file… and no portable-file note',async()=>{
 const A=await import(STATIC+'workspace-applications.mjs');
 const doc=fakeDocument(),host=doc.root;
 const latest={runs:1,model:'Optical waveguide',names:['Run 1'],savedAt:'2026-11-26T11:40:00Z',file:null};
 const resume={latest,earlier:[],onLatest(){},onEarlier(){},onStartNew(){},onToggle(){}};
 const prev=globalThis.document;globalThis.document=doc;
 try{
  for(const project of [null,{name:'Heater study',onRename:()=>true}])for(const r of [null,resume]){
   A.renderApplications(host,r,{},{onOpenFile(){},project});
   const bar=host.querySelector('.library-files');
   assert.equal(host.children[0],bar);
   assert.equal(bar.children[0].id,'library-open-file');assert.equal(bar.children[0].textContent,'Open file…');
   assert.equal(bar.children.length,project?2:1);if(project)assert.equal(bar.children[1].id,'project-name-form');
   assert.equal(host.querySelector('.library-portable'),null);assert.equal(bar.querySelectorAll('p').length,0);
   assert.ok(!host.textContent.includes('moves between computers'),host.textContent);
   assert.ok(!host.textContent.includes('browser recovery stays'),host.textContent);
   // the restore box keeps its own note
   if(r)assert.ok(host.querySelector('#resume-box').textContent.includes(A.RESUME_NOTE));
  }
 }finally{globalThis.document=prev;}
 // the note, its class and the CSS that only served it are gone from the sources
 const lib=read('workspace-applications.mjs'),css=read('workspace.css');
 for(const word of ['PORTABLE_NOTE','library-portable',OLD_NOTE])assert.ok(!lib.includes(word),word);
 assert.ok(!css.includes('.library-portable'));assert.ok(!css.includes('.library-files p'));
 assert.equal(A.RESUME_NOTE,'Restore brings back completed runs kept in this browser, without recomputing.');
});
