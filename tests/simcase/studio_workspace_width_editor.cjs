// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
const {test,before}=require('node:test');const assert=require('node:assert/strict');let draggedWidth,draggedHeight,installWidthEditor;
before(async()=>({draggedWidth,draggedHeight,installWidthEditor}=await import('../../packages/simcase/src/simcase/studio/static/workspace-width-editor.mjs')));
test('symmetric edge motion converts drawing units to nm and clamps supported widths',()=>{
 assert.equal(draggedWidth(500,5,1),600);assert.equal(draggedWidth(500,-5,-1),600);
 assert.equal(draggedWidth(500,-100,1),300);assert.equal(draggedWidth(500,100,1),900);
 assert.equal(draggedHeight(220,-8),300);assert.equal(draggedHeight(220,100),100);assert.equal(draggedHeight(220,-100),500);assert.throws(()=>draggedHeight(220,NaN));
 assert.equal(draggedWidth(550.5,.01,1),551);assert.throws(()=>draggedWidth(500,NaN,1));
});

test('drag previews commit once on release; Escape and disposal preserve inputs',()=>{
 const original={document:global.document,window:global.window,DOMPoint:global.DOMPoint};
 class Element{
  constructor(){this.attrs={};this.children=[];this.style={};}
  setAttribute(k,v){this.attrs[k]=String(v);}getAttribute(k){return this.attrs[k];}
  remove(){}
  append(e){this.children.push(e);}focus(){}setPointerCapture(id){this.capture=id;}
  hasPointerCapture(id){return this.capture===id;}releasePointerCapture(){this.capture=null;this.onlostpointercapture?.({pointerId:1});}
 }
 let scale=1,offset=0;const svg=new Element();svg.getScreenCTM=()=>({inverse:()=>({scale,offset})});
 const host=new Element();host.querySelector=()=>svg;
 global.document={createElementNS:()=>new Element(),createElement:()=>new Element()};
 const listeners={};global.window={addEventListener(k,fn){listeners[k]=fn;},removeEventListener(k){delete listeners[k];}};
 global.DOMPoint=class{constructor(x,y){this.x=x;this.y=y;}matrixTransform(m){return {x:(this.x-m.offset)/m.scale,y:(this.y-m.offset)/m.scale};}};
 try{
  let blocked=false;const commits=[];const dispose=installWidthEditor(host,{width:500,blocked:()=>blocked,commit:w=>commits.push(w)});
  const right=svg.children.at(-1);const ev=x=>({button:0,pointerId:1,clientX:x,clientY:0,preventDefault(){},stopPropagation(){}});
  right.onpointerdown(ev(325));right.onpointermove(ev(330));assert.deepEqual(commits,[]);
  right.onkeydown({...ev(330),key:'Escape'});right.onpointerup(ev(330));assert.deepEqual(commits,[]);
  right.onpointerdown(ev(325));right.onpointermove(ev(330));right.onpointerup(ev(330));assert.deepEqual(commits,[600]);
  right.onpointerdown(ev(325));right.onpointermove(ev(340));right.onpointerup(ev(325));assert.deepEqual(commits,[600]);
  scale=2;offset=100;
  right.onpointerdown(ev(750));right.onpointerup(ev(760));assert.deepEqual(commits,[600,600]);
  right.onpointerdown(ev(750));right.onpointermove(ev(770));listeners.resize();right.onpointerup(ev(770));assert.deepEqual(commits,[600,600]);
  right.onpointerdown(ev(750));right.onpointermove(ev(770));blocked=true;right.onpointerup(ev(770));assert.deepEqual(commits,[600,600]);blocked=false;
  right.onpointerdown(ev(750));right.onpointercancel({...ev(750),pointerId:2});right.onpointerup(ev(760));assert.deepEqual(commits,[600,600,600]);
  right.onpointerdown(ev(750));right.onpointermove(ev(Infinity));right.onpointerup(ev(760));assert.deepEqual(commits,[600,600,600]);
  right.onpointerdown(ev(750));right.onpointermove(ev(770));dispose();assert.deepEqual(commits,[600,600,600]);assert.equal(Object.keys(listeners).length,0);
  scale=2;offset=100;const heights=[];
  const disposeHeight=installWidthEditor(host,{width:500,height:220,blocked:()=>blocked,commit:()=>{},commitHeight:h=>heights.push(h)});
  const top=svg.children.at(-1),vertical=y=>({...ev(300),clientY:y});
  assert.equal(top.getAttribute('aria-orientation'),'vertical');
  top.onpointerdown(vertical(400));top.onpointermove(vertical(384));assert.deepEqual(heights,[]);
  const preview=svg.children.at(-4);assert.equal(preview.getAttribute('height'),'30');assert.equal(preview.getAttribute('y'),'145');
  top.onpointerup(vertical(384));assert.deepEqual(heights,[300]);
  top.onpointerdown(vertical(400));top.onpointerup(vertical(380));assert.deepEqual(heights,[300,320]);
  top.onkeydown({...vertical(0),key:'ArrowUp',shiftKey:true});assert.deepEqual(heights,[300,320,221]);
  top.onkeydown({...vertical(0),key:'Home'});assert.equal(heights.at(-1),100);
  top.onpointerdown(vertical(400));top.onpointermove(vertical(380));top.onkeydown({...vertical(0),key:'Escape'});top.onpointerup(vertical(380));assert.equal(heights.length,4);
  blocked=true;top.onkeydown({...vertical(0),key:'End'});top.onpointerdown(vertical(400));top.onpointerup(vertical(380));assert.equal(heights.length,4);
  disposeHeight();assert.equal(Object.keys(listeners).length,0);

 }finally{for(const [key,value] of Object.entries(original)){if(value===undefined)delete global[key];else global[key]=value;}}
});
