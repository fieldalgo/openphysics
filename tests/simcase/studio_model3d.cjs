// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// The 3D view's pure helpers (model3d-model.mjs): the camera contract, controls, CPU picking.
const {test,before}=require('node:test');const assert=require('node:assert/strict');
let M;
before(async()=>{M=await import('../../packages/simcase/src/simcase/studio/static/model3d-model.mjs');});
const close=(a,b,eps=1e-12)=>a.forEach((x,i)=>assert.ok(Math.abs(x-b[i])<=eps,`${a} vs ${b}`));
// the card: 10 x 10 x 4 um
const card={half_extent_m:[5e-6,5e-6,2e-6],metres_per_unit:1e-6,origin_m:[5e-6,5e-6,2e-6],
 domain:{xmin:0,xmax:10,ymin:0,ymax:10,zmin:0,zmax:4},unit:'um',
 regions:[{name:'a',void:false},{name:'gap',void:true},{name:'b',void:false}]};

test('decode reads little-endian base64 arrays',()=>{
 const f=new Float32Array([1.5,-2,3e-6]);
 const text=Buffer.from(f.buffer).toString('base64');
 assert.deepEqual([...M.decode(text,Float32Array)],[...f]);
 assert.deepEqual([...M.decode(Buffer.from(new Uint32Array([7,0,4294967295]).buffer).toString('base64'),Uint32Array)],[7,0,4294967295]);
});

test('the isometric camera follows the contract (W3 oracle words)',()=>{
 const cam=M.viewCamera(card,'iso'),R=Math.hypot(5e-6,5e-6,2e-6);
 assert.equal(cam.r,R);
 const f=M.frameOf(cam,720,504),s=1/Math.sqrt(3),h=1/Math.sqrt(2);
 close(f.z,[s,s,s]);close(f.x,[-h,h,0]);close(f.y,M.cross(f.z,f.x));
 assert.equal(f.halfHeight,1.1*R);assert.equal(f.halfWidth,1.1*R*720/504);
 close(f.position,[4*R*s,4*R*s,4*R*s],1e-18);
 const tall=M.frameOf(cam,390,600);assert.equal(tall.halfWidth,1.1*R);assert.equal(tall.halfHeight,1.1*R*600/390);
 const r=M.rayAt(f,360,252);close(r.origin,f.position,1e-18);close(r.direction,[-s,-s,-s]);
 const corner=M.rayAt(f,0,0);
 close(corner.origin,[f.position[0]-f.x[0]*f.halfWidth+f.y[0]*f.halfHeight,f.position[1]-f.x[1]*f.halfWidth+f.y[1]*f.halfHeight,
  f.position[2]-f.x[2]*f.halfWidth+f.y[2]*f.halfHeight],1e-18);
});

test('every named view is orthonormal and looks at the target',()=>{
 for(const name of Object.keys(M.VIEWS)){
  const f=M.frameOf(M.viewCamera(card,name),720,504);
  for(const [a,b] of [[f.x,f.y],[f.y,f.z],[f.x,f.z]])assert.ok(Math.abs(M.dot(a,b))<1e-12,name);
  for(const v of [f.x,f.y,f.z])assert.ok(Math.abs(Math.hypot(...v)-1)<1e-12,name);
 }
 close(M.frameOf(M.viewCamera(card,'+z'),720,504).z,[0,0,1]);
 close(M.frameOf(M.viewCamera(card,'-x'),720,504).z,[-1,0,0]);
});

test('orbit, pan, zoom and fit',()=>{
 let cam=M.viewCamera(card,'iso');
 const turned=M.orbit(cam,Math.PI/12,Math.PI/12);
 assert.ok(Math.abs(Math.hypot(...turned.eye)-1)<1e-12);
 const tf=M.frameOf(turned,720,504);
 for(const [a,b] of [[tf.x,tf.y],[tf.y,tf.z],[tf.x,tf.z]])assert.ok(Math.abs(M.dot(a,b))<1e-12);
 assert.notDeepEqual(turned.eye,cam.eye);
 const back=M.orbit(M.orbit(turned,0,-Math.PI/12),-Math.PI/12,0);close(back.eye,cam.eye,1e-12);
 const f=M.frameOf(cam,720,504),moved=M.pan(cam,f,0.5,0);close(moved.target,f.x.map(c=>c*0.5*f.halfWidth),1e-18);
 assert.equal(M.zoomBy(cam,2).zoom,2);assert.equal(M.zoomBy(cam,1e6).zoom,200);
 const reset=M.fit({...moved,zoom:3});assert.deepEqual(reset.target,[0,0,0]);assert.equal(reset.zoom,1);
});

test('CPU pick: nearest shown triangle, on the kept side of a section',()=>{
 // two squares at z = 0 (face 0) and z = 1 (face 1), each two triangles, looked at from +z
 const positions=Float32Array.from([0,0,0,1,0,0,1,1,0,0,1,0, 0,0,1,1,0,1,1,1,1,0,1,1]);
 const indices=Uint32Array.from([0,1,2,0,2,3,4,5,6,4,6,7]),owner=Uint32Array.from([0,0,1,1]);
 const ray={origin:[0.3,0.6,5],direction:[0,0,-1]};
 assert.equal(M.pick(ray,positions,indices,owner,new Set([0,1])).face,1);
 assert.equal(M.pick(ray,positions,indices,owner,new Set([0])).face,0);
 assert.equal(M.pick(ray,positions,indices,owner,new Set([0,1]),{axis:2,at:0.5}).face,0);
 assert.equal(M.pick({origin:[2,2,5],direction:[0,0,-1]},positions,indices,owner,new Set([0,1])),null);
 assert.equal(M.pick({origin:[0.5,0.5,-5],direction:[0,0,-1]},positions,indices,owner,new Set([0,1])),null);
});

test('faces are shown by their non-void, unhidden sides',()=>{
 const by=Object.fromEntries(card.regions.map(r=>[r.name,r]));
 const f={minus:['a'],plus:['gap']},g={minus:['a'],plus:['b']};
 assert.equal(M.faceShown(f,by,new Set()),true);assert.equal(M.faceShown(f,by,new Set(['a'])),false);
 assert.equal(M.faceRegion(g,by,new Set()),'b');assert.equal(M.faceRegion(g,by,new Set(['b'])),'a');
 assert.equal(M.faceRegion(f,by,new Set()),'a');
 const view={faces:[{id:0,first_triangle:0,triangle_count:1},{id:1,first_triangle:1,triangle_count:2}]};
 const d=M.drawn(view,Uint32Array.from([0,1,2,3,4,5,6,7,8]),new Set([1]));
 assert.deepEqual([...d.indices],[3,4,5,6,7,8]);assert.deepEqual(d.faces,[1,1]);
 assert.equal(M.regionColor(card,'b'),M.regionColor({regions:[{name:'a'},{name:'b'}]},'b'));
});

test('section helpers: the slider range and document units to the frame',()=>{
 assert.deepEqual(M.sectionRange(card,'z'),{min:0,max:4,step:0.02,start:2});
 assert.ok(Math.abs(M.toFrame(card,'x',4)-(-1e-6))<1e-18);
 assert.equal(M.kept(null,[9,9,9]),true);
 assert.equal(M.kept({axis:0,at:0},[1e-9,0,0]),false);assert.equal(M.kept({axis:0,at:0},[0,5,5]),true);
});

test('the names panel lines',()=>{
 const lines=M.faceLines(card,{id:4,axis:'z',at:3,area:4,exterior:false,tag:null,minus:['via'],plus:['silicon'],
  names:['stack.oxide.top','stack.top.bottom','via.z1']});
 assert.equal(lines.title,'Face 4 · z = 3 um');assert.equal(lines.sides,'via | silicon');
 assert.deepEqual(lines.names,['stack.oxide.top','stack.top.bottom','via.z1']);
});

test('a curved face (axis null) is named by its shape, with the display note, and shaded',()=>{
 const note='Shape drawn for display; the mesh follows it to within its size';
 const view={...card,unit:'m',display_note:note};
 const lines=M.faceLines(view,{id:8,shape:'cylinder',axis:null,at:null,area:1.88496,exterior:false,tag:null,
  minus:['background'],plus:['via'],names:['via.side']});
 assert.equal(lines.title,'Face 8 · cylinder');assert.equal(lines.sides,'background | via');
 assert.equal(lines.detail,`area 1.88496 m² · interior · ${note}`);
 const plane=M.faceLines(view,{id:5,shape:'plane',axis:'z',at:0,area:0.282743,exterior:true,tag:'z0',minus:[],plus:['via'],
  names:['domain.z0','via.bottom']});
 assert.equal(plane.title,'Face 5 · z = 0 m');assert.equal(plane.detail,'area 0.282743 m² · exterior · tag z0');
 assert.equal(M.shapeOf({axis:'x'}),'plane');assert.equal(M.SHADE[null],0.85);
 // a curved face is coloured by its non-void side as a plane is: plus (inside) first, else minus
 const regions={via:{void:false},background:{void:false},hole:{void:true}};
 const side={minus:['background'],plus:['via']};
 assert.equal(M.faceRegion(side,regions,new Set()),'via');
 assert.equal(M.faceRegion(side,regions,new Set(['via'])),'background');
 assert.equal(M.faceRegion({minus:['sb'],plus:['hole']},{...regions,sb:{void:false}},new Set()),'sb');
 const s=1/Math.sqrt(3);assert.ok(Math.abs(M.curvedShade([s,s,s])-1)<1e-15);assert.equal(M.curvedShade([s,-s,0]),0.55);
});
