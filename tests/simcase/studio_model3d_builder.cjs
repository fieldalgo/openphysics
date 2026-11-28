// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// The 3D builder's pure helpers (workspace-model3d.mjs): tree rows, field edits and drafts,
// feature operations, parameters in use, the undo history and the refusal words.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const STATIC_DIR=path.join(__dirname,'..','..','packages','simcase','src','simcase','studio','static');
let M,W;
test.before(async()=>{M=await import(STATIC+'workspace-model3d.mjs');const C=await import(STATIC+'model3d-mesh-model.mjs');W={estimateText:C.estimateText,meshBlocked:C.meshBlocked};});
const card=()=>JSON.parse(fs.readFileSync(path.join(STATIC_DIR,'model3d-layer-stack-3d.json'),'utf8'));
// card 1 written out in numbers: the document before it held its design parameters (t_ox, via_w);
// the editing tests below need numeric via extents and a model without parameters
const numeric=()=>{const d=card(),c=d.geometry.components.stack3d;delete d.geometry.parameters;c.features[0].layers[1].thickness=10;
 Object.assign(c.features[1],{xmin:90,xmax:110,ymin:90,ymax:110,zmin:500,zmax:510});c.domain.zmax=610;return d;};
// the domain the server's check evaluates for card 1 (its top is "500 + t_ox + 100"): the view passes it
const DOMAIN1={xmin:0,xmax:200,ymin:0,ymax:200,zmin:0,zmax:610};
const comp=doc=>doc.geometry.components.stack3d;

test('the card is its own Library group, with the square-via note',()=>{
 assert.equal(M.CARD3D.id,'layer-stack-3d');assert.equal(M.CARD3D.kind,'model3d');
 assert.equal(M.CARD3D.title,'Via in a layer stack (3D heat)');
 assert.equal(M.CARD3D.note,'Square via: a box through the oxide, in a layer stack');
 assert.equal(M.CARD3D.asset,'/model3d-assets/model3d-layer-stack-3d.json');
 assert.deepEqual(M.FEATURE_TYPES.filter(t=>t.available).map(t=>t.label),['Box','Layers','Cylinder','Sphere']);
 // design 5.2, the coordinator's exact reason (Cylinder and Sphere are taken since E2-UI)
 assert.deepEqual(M.FEATURE_TYPES.filter(t=>!t.available).map(t=>[t.label,t.reason]),[['Extrude','Extrude comes with a later geometry step']]);
 assert.throws(()=>M.addFeature(card(),'extrude'),{message:'Extrude comes with a later geometry step'});
});

test('the tree (design 5.2): Component 1 with Parameters, Geometry 1 (Domain, numbered features, Form result) and Materials',()=>{
 const check={features:[{text:'covered in part by 2 (via)'},{text:'',size:[20,20,10]}],regions:[1,2,3,4],display:{faces:new Array(23).fill({})},domain:DOMAIN1,
  mesh:{ok:true,estimate:{tetrahedra:2402,seconds:1.4411},key:'k'}};
 const rows=M.treeRows(card(),check,null,W);
 assert.deepEqual(rows.map(r=>[r.label,r.level,r.note]),[['Component 1 · 3D · µm',1,''],['Parameters',2,'t_ox = 10 um · via_w = 20 um'],['Geometry 1',2,''],
  ['Domain',3,'200 × 200 × 610 µm'],['1 Layers stack',3,'sub · oxide · top (covered in part by 2 (via))'],['2 Box via',3,'20 × 20 × 10 µm'],
  ['Form result',3,'4 regions · 23 faces'],['Materials',2,'Si · Si (top) · SiO2 · Cu'],
  ['Heat transfer (3D)',2,''],['Thermal conductivity',3,'from Materials'],['Fixed temperature 1',3,'z0 · 300 K'],['Heat source 1',3,'Si (top) · 1e12 W/m³'],
  ['Insulated',3,'every other outer face'],['Mesh 1',2,'size 40 µm · Estimate 2,400 tetrahedra · about 1 s'],['Study 1 · Steady',2,''],['Results',2,'no run yet']]);
 // the card's own fields that name a parameter show it with its written value
 assert.equal(M.fieldNote(card(),'features[0].layers[1].thickness'),'= t_ox (10 µm)');
 assert.equal(M.fieldNote(card(),'features[1].xmin'),'','an expression is the server\'s to evaluate');
 let doc=M.addParameter(M.addParameter(numeric(),'t_ox','10 um'),'via_w','20 um');
 const free=JSON.parse(JSON.stringify(doc));delete free.geometry.components.stack3d.domain.zmin;delete free.geometry.components.stack3d.domain.zmax;
 const r2=M.treeRows(free,null);
 assert.equal(r2.find(r=>r.key==='parameters').note,'t_ox = 10 um · via_w = 20 um');
 assert.equal(r2.find(r=>r.key==='domain').note,'200 × 200 µm, z from the features');
 assert.equal(r2.find(r=>r.key==='form').note,'');
 assert.equal(r2.find(r=>r.key==='mesh').note,'size 40 µm');
});

test('a refusal before meshing marks features[i], else the Mesh node; the shape is not refused',()=>{
 const base={features:[{text:''},{text:''}],regions:[1,2,3],display:{faces:[]}};
 const at=mesh=>M.treeRows(card(),{...base,mesh});
 const marked=rows=>rows.filter(r=>r.problem).map(r=>r.key);
 assert.deepEqual(marked(at({ok:false,refused:'about 2402 tetrahedra …',code:'E-MESH-ESTIMATE',path:'mesh.element_count_limit',feature_index:null})),['mesh']);
 assert.deepEqual(marked(at({ok:false,refused:'west.x1 and east.x0 round to the same coordinate',code:'E-3D-COMBINATION',feature_index:1})),['feature:1']);
 const rows=at({ok:false,refused:'r',code:'E-CONTRACT',path:'geometry.components.c',feature_index:null});
 assert.equal(rows.find(r=>r.key==='mesh').note,'refused');assert.equal(rows.find(r=>r.key==='form').note,'3 regions · 0 faces');
 assert.equal(M.meshRefusal({...base,mesh:{ok:false,refused:'r',feature_index:null}}).refused,'r');
 assert.equal(M.meshRefusal({...base,mesh:{ok:true}}),null);assert.equal(M.meshRefusal(null),null);
});

test('the refusal while forming marks the tree as before',()=>{
 const refused=M.treeRows(card(),null,{feature_index:1});
 assert.deepEqual(refused.filter(r=>r.problem).map(r=>r.key),['feature:1']);
 assert.equal(refused.find(r=>r.key==='form').note,'refused');
 assert.deepEqual(M.treeRows(card(),null,{feature_index:null}).filter(r=>r.problem).map(r=>r.key),['form']);
});

test('the mesh size: a quantity in the document mesh block, within the 5.2 range',()=>{
 const f=M.fieldsOf(card(),'mesh');
 assert.deepEqual(f.map(x=>[x.key,x.label]),[['mesh.element_size','Element size']]);
 assert.equal(M.getField(card(),'mesh.element_size'),'40 um');
 assert.equal(M.editField(card(),f[0],'20').doc.mesh.element_size,'20 um','a bare number takes the component unit');
 assert.equal(M.editField(card(),f[0],'0.1 mm').doc.mesh.element_size,'0.1 mm');
 assert.equal(M.editField(card(),f[0],'1',{domain:DOMAIN1}).problem,'Mesh element size must be between 1.68–168 µm.');
 assert.equal(M.editField(card(),f[0],'w').problem,'A mesh size is a number or a quantity such as 20 um.');
 assert.equal(M.fieldNote(card(),'mesh.element_size'),'= 0.00004 m');
 assert.deepEqual(M.editField(card(),f[0],'20').doc.geometry,card().geometry,'the geometry is unchanged');
});

test('field edits: numbers, quantities, names and expressions; a bad one is a draft problem',()=>{
 // a field holding a parameter name shows it with its written value; a number its SI value
 const named=M.setField(M.addParameter(numeric(),'t_ox','10 um'),'features[0].layers[1].thickness','t_ox');
 assert.equal(M.fieldNote(named,'features[0].layers[1].thickness'),'= t_ox (10 µm)');
 assert.equal(M.fieldNote(numeric(),'features[1].xmin'),'= 0.00009 m');
 assert.equal(M.fieldNote(M.setField(numeric(),'features[1].xmin','100 - w / 2'),'features[1].xmin'),'');
 const f=M.fieldsOf(numeric(),'feature:1').find(x=>x.key==='features[1].xmin');
 let r=M.editField(numeric(),f,'95');assert.equal(comp(r.doc).features[1].xmin,95);assert.ok(Math.abs(r.si-9.5e-5)<1e-18);assert.equal(M.siText(r.si),'= 0.000095 m');
 r=M.editField(numeric(),f,'0.1 mm');assert.equal(comp(r.doc).features[1].xmin,'0.1 mm');assert.ok(Math.abs(r.si-1e-4)<1e-18);
 r=M.editField(numeric(),f,'100 - w / 2');assert.equal(comp(r.doc).features[1].xmin,'100 - w / 2');assert.equal(r.si,null);
 assert.equal(M.editField(numeric(),f,'').problem,'Enter a length: a number, a quantity such as 12 um, a parameter name or an expression.');
 assert.equal(M.editField(numeric(),f,'3 ft').problem,'ft is not a length unit (m, mm, um, nm).');
 assert.equal(M.editField(numeric(),f,'2;rm').problem,'2;rm is not a number, a quantity, a parameter name or an expression.');
 const t=M.fieldsOf(numeric(),'feature:0').find(x=>x.key==='features[0].layers[1].thickness');
 assert.deepEqual(t.rule,{positive:true});assert.equal(M.editField(numeric(),t,'0').problem,'Stack oxide thickness must be greater than 0 µm.');
 assert.equal(M.editField(numeric(),t,'-1 um').problem,'Stack oxide thickness must be greater than 0 µm.');
 const mat=M.fieldsOf(numeric(),'feature:1').find(x=>x.kind==='material');
 assert.equal(comp(M.editField(numeric(),mat,'Si').doc).features[1].material,'Si');
 assert.equal(comp(M.editField(numeric(),mat,'').doc).features[1].material,null);
 assert.equal(M.editField(numeric(),mat,'Gold').problem,'Gold is not a material of this model (Si, Si (top), SiO2, Cu).');
 assert.equal(M.siText(9.5e-5),'= 0.000095 m');assert.equal(M.siText(null),'');
 assert.deepEqual(M.fieldsOf(numeric(),'domain').map(x=>x.label),['xmin','xmax','ymin','ymax','zmin','zmax']);
});

test('ranges (design 5.2): the 2D range sentence; Studio guards, not contract rules',()=>{
 const f=key=>M.fieldsOf(numeric(),key.startsWith('domain')?'domain':'feature:'+/features\[(\d+)\]/.exec(key)[1]).find(x=>x.key===key);
 const p=(key,raw,doc=numeric())=>M.editField(doc,f(key),raw).problem;
 // a box: min < max on each axis, inside the domain where the domain is fixed
 assert.equal(p('features[1].xmax','80'),'Via x max must be between 90–200 µm.');
 assert.equal(p('features[1].xmax','210'),'Via x max must be between 90–200 µm.');
 assert.equal(p('features[1].xmax','0.25 mm'),'Via x max must be between 90–200 µm.');
 assert.equal(p('features[1].zmin','-5'),'Via z min must be between 0–510 µm.');
 assert.equal(p('features[1].xmax','150'),undefined);
 assert.equal(p('features[1].xmax','w'),undefined,'a name or an expression is the server\'s to check');
 const free=JSON.parse(JSON.stringify(numeric()));free.geometry.components.stack3d.domain.xmax='2 * w';
 assert.equal(M.editField(free,f('features[1].xmax'),'500').problem,undefined,'no fixed domain bound: only min < max');
 assert.equal(M.editField(free,f('features[1].xmax'),'50').problem,'Via x max must be greater than 90 µm.');
 // the domain: min < max
 assert.equal(p('domain.xmin','200'),'Domain x min must be less than 200 µm.');
 assert.equal(p('domain.zmax','-1'),'Domain z max must be greater than 0 µm.');
 // names: unique in the component; layer names unique in the feature
 assert.equal(p('features[1].name','stack'),'stack is already the name of another feature.');
 assert.equal(p('features[1].name','2via'),'A name starts with a letter or _ and holds letters, digits and _.');
 const lay=M.fieldsOf(numeric(),'feature:0').find(x=>x.key==='features[0].layers[2].name');
 assert.equal(M.editField(numeric(),lay,'sub').problem,'sub is already the name of another layer of stack.');
 // element_size (optional): domain diagonal/400 to diagonal/4 (672.3 µm here)
 const es=M.fieldsOf(numeric(),'feature:1').find(x=>x.key==='features[1].element_size');
 assert.equal(es.optional,true);
 assert.equal(M.editField(numeric(),es,'1').problem,'Via element size must be between 1.68–168 µm.');
 assert.equal(M.editField(numeric(),es,'200').problem,'Via element size must be between 1.68–168 µm.');
 assert.equal(M.getField(M.editField(numeric(),es,'20').doc,'features[1].element_size'),20);
 assert.equal('element_size' in M.editField(M.editField(numeric(),es,'20').doc,es,'').doc.geometry.components.stack3d.features[1],false,'empty clears it');
 // layers: 1 to 32 rows
 let many=numeric();for(let k=0;k<29;k++)many=M.addLayer(many,0);
 assert.equal(M.getField(many,'features[0].layers').length,32);
 assert.throws(()=>M.addLayer(many,0),{message:'A layers feature holds 1 to 32 layers.'});
 let one=numeric();one=M.removeLayer(M.removeLayer(one,0,2),0,1);
 assert.throws(()=>M.removeLayer(one,0,0),{message:'A layers feature holds 1 to 32 layers.'});
 assert.deepEqual(M.getField(M.addLayer(numeric(),0),'features[0].layers').map(l=>l.name),['sub','oxide','top','layer']);
});

test('feature operations: move, duplicate, delete, add',()=>{
 const moved=M.moveFeature(card(),1,-1);assert.deepEqual(comp(moved).features.map(f=>f.name),['via','stack']);
 assert.throws(()=>M.moveFeature(card(),0,-1),{message:'The first feature cannot move up.'});
 assert.throws(()=>M.moveFeature(card(),1,1),{message:'The last feature cannot move down.'});
 const dup=M.duplicateFeature(card(),1);assert.deepEqual(comp(dup).features.map(f=>f.name),['stack','via','via_2']);
 assert.deepEqual(comp(M.duplicateFeature(dup,1)).features.map(f=>f.name),['stack','via','via_3','via_2']);
 assert.deepEqual(comp(M.deleteFeature(card(),0)).features.map(f=>f.name),['via']);
 const box=comp(M.addFeature(card(),'box',{domain:DOMAIN1})).features[2];
 assert.deepEqual([box.name,box.type,box.xmin,box.xmax,box.zmin,box.zmax,box.material],['box','box',50,150,152.5,457.5,'Si']);
 const lay=comp(M.addFeature(card(),'layers',{domain:DOMAIN1})).features[2];
 assert.deepEqual([lay.name,lay.type,lay.z0,lay.layers.length],['layers','layers',152.5,1]);
 assert.deepEqual(comp(card()).features.map(f=>f.name),['stack','via'],'the card itself is unchanged');
});

test('parameters: a used parameter cannot be deleted, and the refusal names its users in feature order',()=>{
 let doc=M.addParameter(numeric(),'w','20 um');
 assert.deepEqual(doc.geometry.parameters,{w:{value:'20 um'}});
 assert.throws(()=>M.addParameter(doc,'w','1'),{message:'A parameter w already exists.'});
 assert.throws(()=>M.addParameter(doc,'2w','1'),{message:/^A parameter name starts with a letter/});
 doc=M.setParameter(doc,'w','25 um');assert.equal(doc.geometry.parameters.w.value,'25 um');
 assert.equal(M.setParameter(doc,'w','3').geometry.parameters.w.value,3);
 assert.throws(()=>M.deleteParameter(doc,'w',['features[0].layers[1].thickness']),{message:'w is used by stack.oxide thickness.'});
 // several: comma-separated in feature order (the server lists them sorted as text)
 assert.throws(()=>M.deleteParameter(doc,'w',['domain.xmax','features[0].layers[1].thickness','features[1].xmax','features[1].xmin']),
  {message:'w is used by domain xmax, stack.oxide thickness, via xmin, via xmax.'});
 assert.equal(M.deleteParameter(doc,'w',[]).geometry.parameters,undefined);
});

test('undo: one history of documents; an equal document records nothing',()=>{
 const h=new M.Model3dHistory(card());assert.equal(h.canUndo,false);
 const a=M.moveFeature(card(),1,-1);assert.equal(h.record(a),true);assert.equal(h.record(a),false);
 const b=M.deleteFeature(a,0);h.record(b);
 assert.deepEqual(h.undo(),a);assert.deepEqual(h.undo(),card());assert.equal(h.canUndo,false);
 assert.deepEqual(h.redo(),a);h.record(M.duplicateFeature(a,0));assert.equal(h.canRedo,false,'a new edit drops the redo branch');
 const small=new M.Model3dHistory(card(),3);for(const n of [1,2,3,4])small.record(M.addParameter(card(),'p'+n,1));
 assert.equal(small.items.length,3);
});

test('refusals: the engine words as written, the code and path under Details; the block reasons',()=>{
 const r={ok:false,refused:"sphere 'ball' is not taken yet in a 3d component; boxes and slab layers are",code:'E-3D-COMBINATION',
  path:'geometry.components.c.features[2]',feature_index:2};
 assert.deepEqual(M.refusalMessage(r),{text:r.refused,details:'E-3D-COMBINATION at geometry.components.c.features[2]',feature:2});
 assert.equal(M.blockReason({drafts:2}),'Correct the highlighted fields or restore their last valid values first.');
 assert.equal(M.blockReason({refused:r}),'Fix 1 problem in Messages to mesh');
 assert.equal(M.blockReason(),'Heat comes in a later step of the 3D model.');
 // Mesh: drafts, then the shape's refusal, then the mesh refusal's own words, then a running job
 assert.equal(M.meshReason({drafts:1},W),'Correct the highlighted field or restore its last valid value first.');
 assert.equal(M.meshReason({refused:r},W),'Fix 1 problem in Messages to mesh');
 assert.equal(M.meshReason({check:{mesh:{ok:false,refused:'about 2402 tetrahedra; over the limit'}}},W),'about 2402 tetrahedra; over the limit');
 assert.equal(M.meshReason({check:{mesh:{ok:true,estimate:{}}},running:true},W),'A mesh job is running; wait for it or cancel it.');
 assert.equal(M.meshReason({check:{mesh:{ok:true,estimate:{}}}},W),null);
 assert.equal(M.meshReason({check:null},W),'Show a 3d component first.');
 assert.equal(M.fieldWords(card(),'parameters.h'),'parameter h');
 assert.equal(M.deletedText(card(),1),'via deleted; Undo restores it.');
});
