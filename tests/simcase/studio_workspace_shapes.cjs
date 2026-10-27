// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
const {test,before}=require('node:test');const assert=require('node:assert/strict');
let S,opticalDocument,opticalBlock,runTableCsv,opticalSettings,snapshot;
before(async()=>{
 S=await import('../../packages/simcase/src/simcase/studio/static/workspace-shapes.mjs');
 ({opticalDocument,opticalBlock}=await import('../../packages/simcase/src/simcase/studio/static/workspace-optical.mjs'));
 ({runTableCsv,opticalSettings}=await import('../../packages/simcase/src/simcase/studio/static/workspace-notebook.mjs'));
 ({snapshot}=await import('../../packages/simcase/src/simcase/studio/static/workspace-project.mjs'));
});
const rect=(name,x,y,w,h,material='Silicon')=>({name,type:'rect',material,x,y,w,h});
const state=shapes=>({wavelength:1550,coreMesh:30,shapes,electric:false,heat:false,structure:false,optics:true});
const setup={materials:{Core:'Silicon',Oxide:'Silica',Heater:''},temperature:293.15,cooling:'',fixed:'',terminal:''};

test('rectangles, circles and polygons are checked against the window, size and simplicity',()=>{
 assert.deepEqual(S.validateShapes([rect('Core',-250,0,500,220)]),[rect('Core',-250,0,500,220)]);
 const bad=[[],[rect('',0,0,100,100)],[rect('background',0,0,100,100)],[rect(' Core',0,0,100,100)],[rect('Core',0,0,9,100)],[rect('Core',1400,0,200,100)],[rect('Core',0,-1300,100,200)],
  [{name:'C',type:'circle',material:'Silicon',cx:0,cy:1100,r:200}],[{name:'C',type:'circle',material:'Silicon',cx:0,cy:0,r:5}],[{name:'C',type:'ellipse',material:'Silicon'}],
  [{name:'P',type:'polygon',material:'Silicon',points:[[0,0],[100,0]]}],[{name:'P',type:'polygon',material:'Silicon',points:[[0,0],[100,100],[100,0],[0,100]]}],
  [{name:'P',type:'polygon',material:'Silicon',points:[[0,0],[100,0],[100,0.5],[0,100]]}],[{name:'P',type:'polygon',material:'Silicon',points:[[0,0],[100,0],[200,0]]}],
  [rect('Core',0,0,100,100,'Gold')],[rect('A',0,0,100,100),rect('a',200,0,100,100)],Array.from({length:9},(_,i)=>rect('R'+i,-1500+i*300,0,100,100)),
  [{...rect('Core',0,0,100,100),x:'0'}],[{...rect('Core',0,0,100,100),w:Infinity}]];
 for(const shapes of bad)assert.throws(()=>S.validateShapes(shapes),undefined,JSON.stringify(shapes));
 const poly={name:'Trapezoid',type:'polygon',material:'Silicon',points:[[-300,0],[300,0],[200,220],[-200,220]]};
 assert.deepEqual(S.validateShape(poly),poly);assert.equal(S.polygonArea(poly.points),110000);
 assert.deepEqual(S.validateShape(rect('Edge',-1500,-1200,3000,2400)),rect('Edge',-1500,-1200,3000,2400));
});
test('touching rectangles reach the solver with identical shared coordinates',()=>{
 const slot=[rect('Left',-300,0,250,220),rect('Right',50,0,250,220),rect('Slot',-50,0,100,220,'Air')];
 const d=opticalDocument(state(slot),setup),[a,b,c]=d.geometry.shapes;
 assert.equal(a.points[1][0],c.points[0][0]);assert.equal(c.points[1][0],b.points[0][0]);assert.equal(a.points[1][0],-0.05);
 assert.equal(c.material,'vacuum');assert.equal(c.mesh_size,undefined);assert.equal(a.mesh_size,.03);
 assert.deepEqual(d.mesh.grading.center,[0,.11]);
 assert.notEqual(100.1+200.2,300.3);const decimal=opticalDocument(state([rect('A',100.1,0,200.2,100),rect('B',300.3,0,100,100)]),setup).geometry.shapes;
 assert.equal(decimal[0].points[1][0],decimal[1].points[0][0]);
});
test('readiness needs assigned materials, a guiding shape and a silica background',()=>{
 assert.equal(opticalBlock(state([rect('Core',-250,0,500,220)]),setup),'');
 assert.match(opticalBlock(state([rect('Core',-250,0,500,220,'')]),setup),/Assign a material to Core/);
 assert.match(opticalBlock(state([rect('Core',-250,0,500,220,'Air')]),setup),/silicon or silicon nitride/);
 assert.match(opticalBlock(state([rect('Core',-250,0,500,220)]),{...setup,materials:{...setup.materials,Oxide:'Air'}}),/silica/);
 assert.throws(()=>opticalDocument(state([rect('Core',-250,0,500,220,'Air')]),setup));
});
test('summaries, overlaps and new shapes stay unique and inside the window',()=>{
 const shapes=[rect('Slab',-1500,0,3000,90),rect('Rib',-250,0,500,220),{name:'Rod',type:'circle',material:'Air',cx:1000,cy:-800,r:100}];
 assert.equal(S.designSummary({shapes:[shapes[1]]}),'500 × 220 nm · Silicon');assert.equal(S.designSummary({shapes}),'3 shapes · Silicon, Air');
 assert.equal(S.designSummary({shapes:[shapes[2]]}),'r 100 nm circle · Air');
 assert.deepEqual(S.overlappingPairs(shapes),[[0,1]]);
 let list=[...shapes];for(const type of ['rect','circle','polygon','rect']){const shape=S.newShape(type,list);S.validateShape(shape);list=[...list,shape];}
 assert.deepEqual(list.slice(3).map(s=>s.name),['Rectangle 1','Circle 1','Polygon 1','Rectangle 2']);S.validateShapes(list.slice(0,8));
 const copy=S.duplicateShape(shapes[0],shapes);assert.equal(copy.name,'Slab copy 1');assert.equal(copy.x,-1500);
 const moved=S.duplicateShape(shapes[1],shapes);assert.equal(moved.x,-150);assert.equal(S.duplicateShape(moved,[...shapes,moved]).name,'Rib copy 2');
});
test('run tables keep legacy columns for one rectangle and describe every shape',()=>{
 const field={nodes:[[0,0],[1,0],[0,1]],triangles:[[0,1,2]],real:[[[1,0,0]],[[0,1,0]]],imag:[[[0,0,0]],[[0,0,0]]]};
 const single=snapshot({width:500,voltage:1,electric:false,heat:false,structure:false,optics:true},setup);
 const multi=snapshot({width:500,voltage:1,electric:false,heat:false,structure:false,optics:true,shapes:[rect('Slab',-1500,0,3000,90),{name:'Rod',type:'circle',material:'Silicon nitride',cx:0,cy:500,r:150}]},setup);
 const run=(job,input)=>({job,completedAt:'2026-10-27T00:00:00Z',input,settings:opticalSettings(),neff:[2.5,1.8],field,origin:'local'});
 const rows=runTableCsv([run('aaaaaaa1',single),run('aaaaaaa2',multi)]).trim().split('\n');
 assert.ok(rows[0].includes('"core_width_nm","core_height_nm","wavelength_nm","core_mesh_nm","core_material","shapes"'));
 assert.ok(rows[1].includes('"500","220","1550","30","Silicon","Core: rect Silicon x -250…250, y 0…220 nm"'));
 assert.ok(rows[3].includes('"","","1550","30","","Slab: rect Silicon x -1500…1500, y 0…90 nm | Rod: circle Silicon nitride centre (0, 500), r 150 nm"'));
});
test('alignment meets reference edges exactly and refuses leaving the window',()=>{
 const slot=rect('Slot',-50,0,100,220,'Air'),left=rect('Left',300.3,40,250.1,180),right={name:'Right',type:'polygon',material:'Silicon',points:[[0,500],[250,500],[250,720],[0,720]]};
 const placedLeft=S.alignShape(left,'left-of',slot);assert.equal(S.shapeBounds(placedLeft).xmax,-50);assert.equal(placedLeft.y,40);
 const placedRight=S.alignShape(right,'right-of',slot);assert.equal(S.shapeBounds(placedRight).xmin,50);assert.deepEqual(placedRight.points[0],[50,500]);
 const d=opticalDocument(state([placedLeft,S.alignShape(S.alignShape(placedRight,'rest-y'),'right-of',slot),slot]),setup).geometry.shapes;
 assert.equal(d[0].points[1][0],d[2].points[0][0]);assert.equal(d[1].points[0][0],d[2].points[1][0]);
 assert.equal(S.alignShape(left,'centre-x').x,-125.05);assert.equal(S.alignShape(right,'rest-y').points[0][1],0);
 assert.deepEqual(S.shapeBounds(S.alignShape(slot,'on-top',left)),{xmin:-50,xmax:50,ymin:220,ymax:440});
 assert.equal(S.shapeBounds(S.alignShape(slot,'below',left)).ymax,40);
 const rod={name:'Rod',type:'circle',material:'Silicon nitride',cx:900,cy:-300,r:100};assert.equal(S.alignShape(rod,'centre-on',slot).cx,0);
 assert.throws(()=>S.alignShape(rect('Wide',-1500,0,3000,100),'right-of',slot),/outside the window/);
 assert.throws(()=>S.alignShape(slot,'left-of'),/reference/);assert.throws(()=>S.alignShape(slot,'spin',left));
});
test('added materials map to physmat, guide only above silica and keep v4 runs honest',async()=>{
 const {createSession,parseSession}=await import('../../packages/simcase/src/simcase/studio/static/workspace-notebook.mjs');
 const expected={Silicon:'Si','Silicon nitride':'Si3N4',Silica:'SiO2',Air:'vacuum','Sapphire (ordinary)':'Al2O3','Lithium niobate (ordinary)':'LiNbO3','Indium phosphide':'InP','Gallium arsenide':'GaAs','Calcium fluoride':'CaF2','Magnesium fluoride (ordinary)':'MgF2'};
 assert.deepEqual({...S.SHAPE_MATERIALS},expected);
 for(const [name,id] of Object.entries(expected)){
  const shapes=[rect('Core',-250,0,500,220,name)],block=opticalBlock(state(shapes),setup);
  assert.equal(block==='',S.GUIDING_MATERIALS.includes(name),name);
  if(!block){const s=opticalDocument(state(shapes),setup).geometry.shapes[0];assert.equal(s.material,id);assert.equal(s.mesh_size,.03);}
 }
 assert.deepEqual([...S.GUIDING_MATERIALS].sort(),['Gallium arsenide','Indium phosphide','Lithium niobate (ordinary)','Sapphire (ordinary)','Silicon','Silicon nitride']);
 const field={nodes:[[0,0],[1,0],[0,1]],triangles:[[0,1,2]],real:[[[1,0,0]],[[0,1,0]]],imag:[[[0,0,0]],[[0,0,0]]]};
 const make=material=>{const input=snapshot({width:500,voltage:1,electric:false,heat:false,structure:false,optics:true,shapes:[rect('Core',-250,0,500,220,material)]},setup);return {input,run:{job:'abcdef12',completedAt:'2026-10-27T00:00:00Z',input,settings:{...opticalSettings(),adapter:'optical-shapes-v4'},neff:[2,1.8],field,origin:'local'}};};
 const ok=make('Silicon nitride');assert.equal(parseSession(JSON.stringify(createSession(ok.input,[ok.run],'abcdef12',['abcdef12',null]))).runs[0].settings.adapter,'optical-shapes-v4');
 const newer=make('Lithium niobate (ordinary)');assert.throws(()=>createSession(newer.input,[newer.run],'abcdef12',['abcdef12',null]));
 newer.run.settings=opticalSettings();assert.equal(parseSession(JSON.stringify(createSession(newer.input,[newer.run],'abcdef12',['abcdef12',null]))).runs[0].settings.adapter,'optical-shapes-v5');
});
