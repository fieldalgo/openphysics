// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// P2-19 (units and naming batch): the output of every JS document builder, for the Python check.
// The builders are the workspace heat plate (heatDocument), the workspace optical study
// (opticalDocument), and the geometry lab's new document, starters and parameter edits; the classic
// editor and the thermal pages edit documents the server sends and build none. With
// OPENPHYSICS_STUDIO_BUILDER_DUMP set, the documents are written there as one JSON object
// {label: the document's JSON text as the page sends it}; tests/simcase/test_studio_units.py runs
// this file and validates each text. OPENPHYSICS_STUDIO_STATIC names the Studio static folder to
// import the builders from (the Python tests pass the imported simcase package's, which is the
// installed wheel in the installed-package run); without it, the source tree's.
const {test,before}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');
const {pathToFileURL}=require('node:url');
const STATIC=process.env.OPENPHYSICS_STUDIO_STATIC?pathToFileURL(process.env.OPENPHYSICS_STUDIO_STATIC).href+'/'
 :'../../packages/simcase/src/simcase/studio/static/';
let H,O,M,STARTERS,PROJECT,RECOVERY;
before(async()=>{
 H=await import(STATIC+'workspace-heat.mjs');O=await import(STATIC+'workspace-optical.mjs');
 M=await import(STATIC+'geometry-lab-model.mjs');({STARTERS}=await import(STATIC+'geometry-lab-starters.mjs'));
 PROJECT=await import(STATIC+'workspace-project.mjs');RECOVERY=await import(STATIC+'workspace-recovery.mjs');
});
const rect=(name,x,y,w,h,material='Silicon')=>({name,type:'rect',material,x,y,w,h});
const optical={electric:false,heat:false,structure:false,optics:true};
const setup={materials:{Core:'Silicon',Oxide:'Silica'}};
function documents(){
 const docs={};
 const plate=(sides,extra={})=>({...H.DEFAULT_THERMAL,...extra,sides:{...H.DEFAULT_THERMAL.sides,...sides}});
 docs['heat default']=H.heatDocument(H.DEFAULT_THERMAL);
 docs['heat inward flux, convection and source']=H.heatDocument(plate({left:{type:'flux',inward_heat_flux:500},top:{type:'convection',h:10,ambient:290}},{source:1e5}));
 docs['heat fractional plate']=H.heatDocument(plate({right:{type:'flux',inward_heat_flux:-250.5},bottom:{type:'convection',h:0.125,ambient:301.15}},{width:12.5,height:7.25,conductivity:0.03,nx:7,ny:3}));
 docs['optical default core']=O.opticalDocument({width:700,...optical},setup);
 docs['optical study inputs']=O.opticalDocument({width:450,height:300,wavelength:1625,coreMesh:45,...optical},{materials:{Core:'Silicon nitride',Oxide:'Silica'}});
 docs['optical shapes']=O.opticalDocument({width:500,wavelength:1480.5,coreMesh:22.5,...optical,shapes:[rect('Slab',-1500,0,3000,90),{name:'Rod',type:'circle',material:'Silicon nitride',cx:0,cy:500,r:150},{name:'Wedge',type:'polygon',material:'Air',points:[[-900,-600],[-300,-600],[-600,-200]]}]},setup);
 docs['geometry lab new document']=M.newDocument();
 for(const [name,doc] of Object.entries(STARTERS))docs['geometry lab starter '+name]=doc;
 docs['geometry lab edited parameter']=M.setParameter(STARTERS.geometry_v1_imprint_rib,'w','610 nm');
 docs['geometry lab edited number']=M.setParameter(M.newDocument(),'w',0.75);
 return docs;
}
test('every document builder writes format 0.3 documents (dumped for the Python check)',()=>{
 const docs=documents();assert.ok(Object.keys(docs).length>=10);
 for(const [label,doc] of Object.entries(docs))assert.equal(doc.openphysics,'0.3',label);
 const target=process.env.OPENPHYSICS_STUDIO_BUILDER_DUMP;
 if(target)fs.writeFileSync(target,JSON.stringify(Object.fromEntries(Object.entries(docs).map(([label,doc])=>[label,JSON.stringify(doc)]))),'utf8');
});
test('the browser keeps projects under version 2 storage keys (units and naming batch)',()=>{
 assert.equal(PROJECT.PROJECT_VERSION,6);
 assert.equal(PROJECT.DRAFT_KEY,'openphysics.studio.workspace.v2');assert.equal(RECOVERY.RECOVERY_KEY,'openphysics.studio.recovery.v2');
});
