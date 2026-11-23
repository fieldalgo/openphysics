// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Round 16: a Width that keeps the left edge where the centred shape would leave the window, and
// refused values tried again; the Compare pair kept over new runs; the project file of a restore
// and of the recovery cards; the project name that follows Save As; multi-shape run labels; the
// page a model returns to; the Library and Save As words. Plain text comparison only: no RegExp is
// built from a dynamic string.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const read=name=>fs.readFileSync(path.join(__dirname,STATIC,name),'utf8');
let S,I;
test.before(async()=>{S=await import(STATIC+'workspace-shapes.mjs');I=await import(STATIC+'workspace-inputs.mjs');});

// The T16 entry: each keystroke is an input event (as typing is), each field a focus and a change.
function typeEntries(shape,entries){
 const drafts=new I.NumericDrafts();let notices=[];
 for(const [key,text] of entries){
  const field=I.INPUT_FIELDS[key];
  if(key==='name'){shape={...S.validateShape({...shape,name:text})};continue;}
  const base={...shape},leftBefore=shape.x;let kept=null,also=[];
  for(let n=1;n<=text.length;n++){
   const parsed=drafts.update(key,text.slice(0,n));if(!parsed.ok)continue;
   let fit;try{fit=S.fitShapeEdit(shape,field.prop,parsed.value,{base:field.prop==='w'?base:shape});}catch(error){drafts.reject(key,text.slice(0,n),error.message);continue;}
   kept=fit.kept;const retried=I.retryShapeDrafts(drafts,fit.shape,key);shape=retried.shape;also=[...also.filter(a=>!retried.applied.some(b=>b.key===a.key)),...retried.applied];
  }
  if(!drafts.get(key)){const leftX=field.prop==='w'&&(shape.x!==leftBefore||kept==='left')?shape.x:null;notices.push(I.editNoticeText(key,shape[field.prop],{leftX,kept:field.prop==='w'?kept:null,also}));}
  else notices.push('refused: '+drafts.get(key).message);
 }
 return {shape,drafts,notices};
}

test('S2: the T16 entry order gives a 3000 × 700 rectangle at (−1500, −1200)',()=>{
 const start=S.newShape('rect',[{name:'Core',type:'rect',material:'Silicon',x:-250,y:0,w:500,h:220}]);
 const {shape,drafts,notices}=typeEntries(start,[['name','Substrate'],['shapeX','-1500'],['shapeY','-1200'],['shapeW','3000'],['shapeH','700']]);
 assert.deepEqual({x:shape.x,y:shape.y,w:shape.w,h:shape.h,name:shape.name},{x:-1500,y:-1200,w:3000,h:700,name:'Substrate'});
 assert.equal(drafts.invalid,false);
 assert.equal(notices[2],'Width set to 3000 nm. Left x kept at −1500 nm: centred, the shape would leave the window. Run explicitly to compute new results.');
});
test('S2: a Width keeps the centre when that fits, else the left edge, else it is refused',()=>{
 const r={name:'R',type:'rect',material:'Silicon',x:-200,y:300,w:400,h:200};
 assert.deepEqual(S.fitShapeEdit(r,'w',600),{shape:{...r,x:-300,w:600},kept:'centre'});
 const left={...r,x:-1500};
 assert.deepEqual(S.fitShapeEdit(left,'w',3000),{shape:{...left,w:3000},kept:'left'});
 // neither fits: the centred shape's reason
 assert.throws(()=>S.fitShapeEdit({...r,x:-1000},'w',3000));
 // the base: the shape at focus, not the shape after the keystroke 300
 const after300=S.fitShapeEdit(left,'w',300).shape;assert.equal(after300.x,-1450);
 assert.deepEqual(S.fitShapeEdit(after300,'w',3000,{base:left}).shape,{...left,w:3000});
 assert.throws(()=>S.fitShapeEdit(after300,'w',3000));
 // other fields as before
 assert.deepEqual(S.fitShapeEdit(r,'h',700),{shape:{...r,h:700},kept:null});
});
test('S2: a refused Width is tried again when Left x changes',()=>{
 const start={name:'Substrate',type:'rect',material:'Silicon',x:-1000,y:-1200,w:400,h:700};
 const first=typeEntries(start,[['shapeW','3000']]);
 assert.equal(first.drafts.get('shapeW').raw,'3000');assert.equal(first.notices[0].startsWith('refused: '),true);
 // retyping Left x applies the refused Width with the left edge kept
 let shape=first.shape;const drafts=first.drafts;
 for(const text of ['-1','-15','-150','-1500']){const parsed=drafts.update('shapeX',text);const fit=S.fitShapeEdit(shape,'x',parsed.value);shape=I.retryShapeDrafts(drafts,fit.shape,'shapeX').shape;}
 assert.deepEqual({x:shape.x,w:shape.w},{x:-1500,w:3000});assert.equal(drafts.invalid,false);
 // a draft that is not a number is not tried
 const d=new I.NumericDrafts();d.update('shapeH','abc');assert.deepEqual(I.retryShapeDrafts(d,start,'shapeX'),{shape:start,applied:[]});assert.equal(d.get('shapeH').raw,'abc');
 assert.equal(I.editNoticeText('shapeX',-1500,{also:[{key:'shapeW',value:3000}]}),'Left x set to −1500 nm. Width set to 3000 nm too. Run explicitly to compute new results.');
});
test('S2: the size hint says where the left edge stays',()=>{
 assert.ok(read('workspace-app.mjs').includes('Width keeps the shape centred (or its left edge, where centred it would leave the window); Height keeps its bottom edge.'));
});

