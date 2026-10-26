// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
const {test,before}=require('node:test');const assert=require('node:assert/strict');let draggedWidth,installWidthEditor;
before(async()=>({draggedWidth,installWidthEditor}=await import('../../packages/simcase/src/simcase/studio/static/workspace-width-editor.mjs')));
test('symmetric edge motion converts drawing units to nm and clamps supported widths',()=>{
 assert.equal(draggedWidth(500,5,1),600);assert.equal(draggedWidth(500,-5,-1),600);
 assert.equal(draggedWidth(500,-100,1),300);assert.equal(draggedWidth(500,100,1),900);
 assert.equal(draggedWidth(550.5,.01,1),551);assert.throws(()=>draggedWidth(500,NaN,1));
});

test('drag previews commit once on release; Escape and disposal preserve inputs',()=>{
 const original={document:global.document,window:global.window,DOMPoint:global.DOMPoint};
 class Element{
  constructor(){this.attrs={};this.children=[];this.style={};}
  setAttribute(k,v){this.attrs[k]=String(v);}getAttribute(k){return this.attrs[k];}
  remove(){}
  append(e){this.children.push(e);}focus(){}setPointerCapture(id){this.capture=id;}
  hasPointerCapture(id){return this.capture===id;}releasePointerCapture(){this.capture=null;this.onlostpointercapture?.();}
 }
 const svg=new Element();svg.getScreenCTM=()=>({inverse:()=>({})});
 const host=new Element();host.querySelector=()=>svg;
 global.document={createElementNS:()=>new Element(),createElement:()=>new Element()};
 global.window={addEventListener(){},removeEventListener(){}};
 global.DOMPoint=class{constructor(x){this.x=x;}matrixTransform(){return this;}};
 try{
  const commits=[];const dispose=installWidthEditor(host,{width:500,blocked:()=>false,commit:w=>commits.push(w)});
  const right=svg.children.at(-1);const ev=x=>({button:0,pointerId:1,clientX:x,clientY:0,preventDefault(){},stopPropagation(){}});
  right.onpointerdown(ev(325));right.onpointermove(ev(330));assert.deepEqual(commits,[]);
  right.onkeydown({...ev(330),key:'Escape'});right.onpointerup(ev(330));assert.deepEqual(commits,[]);
  right.onpointerdown(ev(325));right.onpointermove(ev(330));right.onpointerup(ev(330));assert.deepEqual(commits,[600]);
  right.onpointerdown(ev(325));right.onpointermove(ev(340));dispose();assert.deepEqual(commits,[600]);
 }finally{for(const [key,value] of Object.entries(original)){if(value===undefined)delete global[key];else global[key]=value;}}
});
