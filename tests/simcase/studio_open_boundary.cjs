// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Open boundary (optical-shapes-v9), the document builder only: a PML outside the 3 x 2.4 um
// window on each open edge, shapes along an open edge continued through it, the fixed PML
// settings and the default search target; with every edge closed, the optical-shapes-v8 document.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const fixture=name=>fs.readFileSync(path.join(__dirname,'studio_session_fixtures',name),'utf8');
let O,B;
test.before(async()=>{O=await import(STATIC+'workspace-optical.mjs');B=await import(STATIC+'workspace-open-boundary.mjs');});
const setup=()=>({materials:{Core:'Silicon',Oxide:'Silica',Heater:''}});
const STRIP={name:'Core',type:'rect',material:'Silicon',x:-250,y:0,w:500,h:220};
const SUBSTRATE={name:'Substrate',type:'rect',material:'Silicon',x:-1500,y:-1200,w:3000,h:700};
const state=(extra={})=>({height:220,width:500,wavelength:1550,coreMesh:30,electric:false,heat:false,structure:false,optics:true,shapes:[STRIP],...extra});
const edges=(...open)=>Object.fromEntries(B.EDGES.map(e=>[e,open.includes(e)?'open':'closed']));

test('V7: every edge closed, or no open boundary, is the optical-shapes-v8 document byte for byte',()=>{
 for(const [n,file] of [[1,'optical-document-template-v8-1.json'],[2,'optical-document-template-v7.json'],[8,'optical-document-template-v8-8.json']]){
  const expected=fixture(file);
  assert.equal(JSON.stringify(O.opticalDocument(state({modeCount:n}),setup())),expected);
  assert.equal(JSON.stringify(O.opticalDocument(state({modeCount:n,openBoundary:{edges:edges()}}),setup())),expected);
  assert.equal(JSON.stringify(O.opticalDocument(state({modeCount:n,openBoundary:{edges:edges(),thickness:2000,target:2.1}}),setup())),expected);
  // closed edges do not read the thickness or the target: values left over from an open design stay harmless
  assert.equal(JSON.stringify(O.opticalDocument(state({modeCount:n,openBoundary:{edges:edges(),thickness:5,target:9}}),setup())),expected);
 }
});

test('the template opened on all four edges: the domain grows by t, the fixed PML settings, target 2.46',()=>{
 const doc=O.opticalDocument(state({openBoundary:{edges:edges('left','right','bottom','top')}}),setup());
 const v8=JSON.parse(fixture('optical-document-template-v7.json'));
 assert.deepEqual(doc.geometry.domain,{xmin:-2500,xmax:2500,ymin:-2200,ymax:2200});
 assert.deepEqual(doc.geometry.shapes,v8.geometry.shapes);         // the strip touches no edge
 assert.deepEqual(doc.physics.em1.boundary,{left:'pec',right:'pec',top:'pec',bottom:'pec'});
 assert.equal(doc.physics.em1.target_effective_index,2.46);
 assert.deepEqual(doc.physics.em1.pml,{pml_thickness:{left:'1000 nm',right:'1000 nm',bottom:'1000 nm',top:'1000 nm'},
  pml_strength:3,pml_order:2,pml_minimum_physical_fraction:0.5,pml_search_mode_count:32});
 // everything else is the v8 document
 const rest=d=>({...d,geometry:{...d.geometry,domain:null},physics:{em1:{...d.physics.em1,target_effective_index:null,pml:null}}});
 assert.deepEqual(rest(doc),rest({...v8,physics:{em1:{...v8.physics.em1,target_effective_index:2.46,pml:{}}}}));
});

test('a substrate along open edges continues through the layer, its open corner filled',()=>{
 const shapes=[STRIP,SUBSTRATE];
 const bottom=O.opticalDocument(state({shapes,openBoundary:{edges:edges('bottom','top'),thickness:1000}}),setup());
 assert.deepEqual(bottom.geometry.domain,{xmin:-1500,xmax:1500,ymin:-2200,ymax:2200});
 assert.deepEqual(bottom.geometry.shapes[1].points,[[-1500,-2200],[1500,-2200],[1500,-500],[-1500,-500]]);
 // the extrusion itself takes any thickness (the builder offers 1 um only)
 const thick=B.applyOpenBoundary(JSON.parse(JSON.stringify(O.opticalDocument(state({shapes}),setup()))),{edges:edges('bottom','top'),thickness:1500,target:2.46});
 assert.deepEqual(thick.geometry.domain,{xmin:-1500,xmax:1500,ymin:-2700,ymax:2700});
 assert.deepEqual(thick.geometry.shapes[1].points,[[-1500,-2700],[1500,-2700],[1500,-500],[-1500,-500]]);
 assert.deepEqual(Object.keys(bottom.physics.em1.pml.pml_thickness),['bottom','top']);
 const all=O.opticalDocument(state({shapes,openBoundary:{edges:edges('left','right','bottom','top')}}),setup());
 assert.deepEqual(all.geometry.shapes[1].points,[[-2500,-2200],[2500,-2200],[2500,-500],[-2500,-500]]);
 const left=O.opticalDocument(state({shapes,openBoundary:{edges:edges('left','bottom')}}),setup());
 assert.deepEqual(left.geometry.domain,{xmin:-2500,xmax:1500,ymin:-2200,ymax:1200});
 assert.deepEqual(left.geometry.shapes[1].points,[[-2500,-2200],[1500,-2200],[1500,-500],[-2500,-500]]);
 // a closed edge is not crossed: only the bottom opens, the substrate keeps its sides at the walls
 const only=O.opticalDocument(state({shapes,openBoundary:{edges:edges('bottom')}}),setup());
 assert.deepEqual(only.geometry.shapes[1].points,[[-1500,-2200],[1500,-2200],[1500,-500],[-1500,-500]]);
});

test('extrusion of polygons: an edge part along the window, a vertex on it, a corner square',()=>{
 const open=edges('left','right','bottom','top');
 // a trapezoid standing on the bottom edge keeps its slanted sides inside and gets a straight foot
 assert.deepEqual(B.extendPolygon([[-400,-1200],[400,-1200],[200,-900],[-200,-900]],open,1000),
  [[-400,-1200],[-400,-2200],[400,-2200],[400,-1200],[200,-900],[-200,-900]]);
 // a triangle touching the bottom edge at one vertex only is unchanged
 const tip=[[0,-1200],[300,-900],[-300,-900]];
 assert.deepEqual(B.extendPolygon(tip,open,1000),tip);
 // a square in the bottom-left corner: both sides pushed and the corner square filled
 assert.deepEqual(B.extendPolygon([[-1500,-1200],[-1000,-1200],[-1000,-700],[-1500,-700]],open,1000),
  [[-2500,-2200],[-1000,-2200],[-1000,-700],[-2500,-700]]);
 // the same square with only the bottom open
 assert.deepEqual(B.extendPolygon([[-1500,-1200],[-1000,-1200],[-1000,-700],[-1500,-700]],edges('bottom'),1000),
  [[-1500,-2200],[-1000,-2200],[-1000,-700],[-1500,-700]]);
 // clockwise order gives the same region
 assert.deepEqual(B.extendPolygon([[-1500,-700],[-1000,-700],[-1000,-1200],[-1500,-1200]],open,1000),
  [[-2500,-700],[-1000,-700],[-1000,-2200],[-2500,-2200]]);
 // a circle touching an edge meets it at a point and is written as before
 const doc=O.opticalDocument(state({shapes:[STRIP,{name:'Ball',type:'circle',material:'Silicon',cx:0,cy:-900,r:300}],
  openBoundary:{edges:open}}),setup());
 assert.deepEqual(doc.geometry.shapes[1],{name:'s2',material:'physmat:Si',element_size:'30 nm',type:'circle',cx:0,cy:-900,r:300});
});

test('the default target and its bounds',()=>{
 assert.equal(B.defaultTarget([STRIP]),2.46);
 assert.equal(B.defaultTarget([{...STRIP,material:'Silicon nitride'}]),1.72);
 const nitride=state({shapes:[{...STRIP,material:'Silicon nitride'}]});
 assert.equal(O.opticalDocument({...nitride,openBoundary:{edges:edges('bottom')}},setup()).physics.em1.target_effective_index,1.72);
 assert.equal(O.opticalDocument(state({openBoundary:{edges:edges('bottom'),target:2.85}}),setup()).physics.em1.target_effective_index,2.85);
 for(const target of [1.45,1.2,3.4777,4,NaN,'2.5'])
  assert.throws(()=>O.opticalDocument(state({openBoundary:{edges:edges('bottom'),target}}),setup()),/Search near n_eff must lie between 1.45 and 3.4777/);
});

test('refusals: thickness, edge words, group index with an open boundary',()=>{
 for(const thickness of [999,1001,1500,2000,1000.5,'1000',NaN])
  assert.throws(()=>O.opticalDocument(state({openBoundary:{edges:edges('top'),thickness}}),setup()),/PML thickness must be 1000 nm \(1 µm\)/);
 assert.throws(()=>O.opticalDocument(state({openBoundary:{edges:{...edges(),top:'pml'}}}),setup()),/top edge must be open or closed/);
 assert.throws(()=>O.opticalDocument(state({openBoundary:'open'}),setup()),/Invalid open boundary/);
 assert.throws(()=>O.opticalDocument(state({groupIndex:true,openBoundary:{edges:edges('top')}}),setup()),/Group index is not computed with an open boundary/);
 // closed edges keep the group index document
 assert.ok(O.opticalDocument(state({groupIndex:true,openBoundary:{edges:edges()}}),setup()).results.group_index);
});

test('1 um on the right only',()=>{
 const doc=O.opticalDocument(state({openBoundary:{edges:edges('right'),thickness:1000}}),setup());
 assert.deepEqual(doc.geometry.domain,{xmin:-1500,xmax:2500,ymin:-1200,ymax:1200});
 assert.deepEqual(doc.physics.em1.pml.pml_thickness,{right:'1000 nm'});
});

test('a vertex within 1e-6 nm of an open edge is on it; the design\'s own collinear vertices stay',()=>{
 const open=edges('bottom');
 assert.deepEqual(B.extendPolygon([[-400,-1199.9999999],[400,-1200],[400,-900],[-400,-900]],open,1000),
  [[-400,-2200],[400,-2200],[400,-900],[-400,-900]]);
 // a vertex of the design in the middle of the top side (collinear, inside the window) is kept
 assert.deepEqual(B.extendPolygon([[-400,-1200],[400,-1200],[400,-900],[0,-900],[-400,-900]],open,1000),
  [[-400,-2200],[400,-2200],[400,-900],[0,-900],[-400,-900]]);
 // a vertex of the design on the open edge itself is part of the pushed side and goes
 assert.deepEqual(B.extendPolygon([[-400,-1200],[0,-1200],[400,-1200],[400,-900],[-400,-900]],open,1000),
  [[-400,-2200],[400,-2200],[400,-900],[-400,-900]]);
});
