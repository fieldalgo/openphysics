// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// The experimental 3D view: three.js WebGLRenderer, Studio's own controls (rotate, pan, zoom,
// fit, six axis views and the isometric one, all from the keyboard too), CPU picking against
// the server's display triangles, a section plane and hidden regions. three.js 0.186.1 is
// vendored unmodified and served by Studio (docs/third-party.md, browser-served files).
import * as THREE from '/vendor/three-0.186.1/three.module.js';
import {SHADE,VIEWS,decode,drawn,faceRegion,faceShown,fit,frameOf,orbit,pan,pick,rayAt,regionColor,
 toFrame,viewCamera,zoomBy} from '/model3d-assets/model3d-model.mjs';

const STEP=Math.PI/12;                       // 15 degrees per arrow key
const SELECTED=new THREE.Color('#d1242f');

export class View3D{
 /** canvas: the drawing surface; onPick(faceId|null) is called on a pick or a keyboard select. */
 constructor(canvas,{onPick=()=>{},onCamera=()=>{}}={}){
  this.canvas=canvas;this.onPick=onPick;this.onCamera=onCamera;
  this.renderer=new THREE.WebGLRenderer({canvas,antialias:true,preserveDrawingBuffer:true});
  this.renderer.setPixelRatio(globalThis.devicePixelRatio||1);
  this.renderer.localClippingEnabled=true;
  this.renderer.setClearColor(0xfbfcfd,1);
  this.scene=new THREE.Scene();
  this.camera=new THREE.OrthographicCamera(-1,1,1,-1,0,10);
  this.clip=new THREE.Plane(new THREE.Vector3(0,0,-1),0);
  this.material=new THREE.MeshBasicMaterial({vertexColors:true,side:THREE.DoubleSide,polygonOffset:true,
   polygonOffsetFactor:1,polygonOffsetUnits:1});
  this.edgeMaterial=new THREE.LineBasicMaterial({color:0x374151});
  this.outlineMaterial=new THREE.LineBasicMaterial({color:0xd1242f});
  this.view=null;this.hidden=new Set();this.section=null;this.selected=null;this.cam=null;
  this.mesh=null;this.edges=null;this.outline=null;
  this._controls();
  new ResizeObserver(()=>this.render()).observe(canvas);
 }

 /** Show a display answer (from /api/model3d/display); keeps the camera if `keep`. */
 load(view,{keep=false}={}){
  this.view=view;
  this.positions=decode(view.positions,Float32Array);
  this.indices=decode(view.indices,Uint32Array);
  this.owner=decode(view.triangle_faces,Uint32Array);
  this.edgePositions=decode(view.edges,Float32Array);
  this.edgeFaces=decode(view.edge_faces,Uint32Array);
  this.regionsByName=Object.fromEntries(view.regions.map(r=>[r.name,r]));
  this.hidden=new Set([...this.hidden].filter(n=>n in this.regionsByName));
  if(this.selected!==null&&!view.faces[this.selected])this.selected=null;
  if(!keep||!this.cam)this.cam=viewCamera(view,'iso');
  else this.cam={...this.cam,r:viewCamera(view).r};
  this.rebuild();
 }

 shownFaces(){
  return new Set(this.view.faces.filter(f=>faceShown(f,this.regionsByName,this.hidden)).map(f=>f.id));
 }

 rebuild(){
  for(const o of [this.mesh,this.edges])if(o){this.scene.remove(o);o.geometry.dispose();}
  const v=this.view,shown=this.shownFaces();
  const colors=new Float32Array(this.positions.length);
  const c=new THREE.Color();
  for(const f of v.faces){
   const region=faceRegion(f,this.regionsByName,this.hidden);
   c.set(f.id===this.selected?SELECTED:regionColor(v,region));
   if(f.id!==this.selected)c.multiplyScalar(SHADE[f.axis]);
   for(let t=f.first_triangle;t<f.first_triangle+f.triangle_count;t++)
    for(let k=0;k<3;k++){const i=this.indices[3*t+k];colors[3*i]=c.r;colors[3*i+1]=c.g;colors[3*i+2]=c.b;}
  }
  const g=new THREE.BufferGeometry();
  g.setAttribute('position',new THREE.BufferAttribute(this.positions,3));
  g.setAttribute('color',new THREE.BufferAttribute(colors,3));
  g.setIndex(new THREE.BufferAttribute(drawn(v,this.indices,shown).indices,1));
  this.mesh=new THREE.Mesh(g,this.material);
  const seg=[];
  for(let e=0;e<this.edgeFaces.length;e++)if(shown.has(this.edgeFaces[e]))
   for(let k=0;k<6;k++)seg.push(this.edgePositions[6*e+k]);
  const eg=new THREE.BufferGeometry();eg.setAttribute('position',new THREE.BufferAttribute(Float32Array.from(seg),3));
  this.edges=new THREE.LineSegments(eg,this.edgeMaterial);
  this.scene.add(this.mesh,this.edges);
  this.applySection();
  this.render();
 }

 /** Section: {axis:'x'|'y'|'z', at (document units)} keeps coordinate <= at; null removes it. */
 setSection(section,outline=null){
  this.section=section&&{axis:'xyz'.indexOf(section.axis),at:toFrame(this.view,section.axis,section.at)};
  if(this.outline){this.scene.remove(this.outline);this.outline.geometry.dispose();this.outline=null;}
  if(outline&&section){
   const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.BufferAttribute(decode(outline.segments,Float32Array),3));
   this.outline=new THREE.LineSegments(g,this.outlineMaterial);this.scene.add(this.outline);
  }
  this.applySection();this.render();
 }

 applySection(){
  const planes=[];
  if(this.section){
   const n=[0,0,0];n[this.section.axis]=-1;
   this.clip.set(new THREE.Vector3(...n),this.section.at);planes.push(this.clip);
  }
  this.material.clippingPlanes=planes;this.edgeMaterial.clippingPlanes=planes;
  this.material.needsUpdate=true;this.edgeMaterial.needsUpdate=true;
 }

 setHidden(names){
  this.hidden=new Set(names);if(!this.view)return;
  if(this.selected!==null&&!this.shownFaces().has(this.selected))this.selected=null;
  this.rebuild();
 }
 select(face){this.selected=face;if(this.view)this.rebuild();}

 size(){const r=this.canvas.getBoundingClientRect();return [Math.max(1,r.width),Math.max(1,r.height)];}

 frame(){const [w,h]=this.size();return frameOf(this.cam,w,h);}

 render(){
  if(!this.view)return;
  const [w,h]=this.size();
  this.renderer.setSize(w,h,false);
  const f=frameOf(this.cam,w,h),cam=this.camera;
  cam.left=-f.halfWidth;cam.right=f.halfWidth;cam.top=f.halfHeight;cam.bottom=-f.halfHeight;
  cam.near=f.near;cam.far=f.far;
  cam.position.set(...f.position);cam.up.set(...this.cam.up);cam.lookAt(...this.cam.target);
  cam.updateProjectionMatrix();
  this.renderer.render(this.scene,cam);
 }

 /** The face at a canvas point (CSS pixels), or null. */
 pickAt(px,py){
  if(!this.view)return null;
  const hit=pick(rayAt(this.frame(),px,py),this.positions,this.indices,this.owner,this.shownFaces(),this.section);
  return hit?hit.face:null;
 }

 setView(name){this.cam={...viewCamera(this.view,name),zoom:this.cam.zoom,target:this.cam.target};this.changed(name);}
 fit(){this.cam=fit(this.cam);this.changed('fit');}
 orbit(yaw,pitch){this.cam=orbit(this.cam,yaw,pitch);this.changed('rotate');}
 pan(fx,fy){this.cam=pan(this.cam,this.frame(),fx,fy);this.changed('pan');}
 zoom(factor){this.cam=zoomBy(this.cam,factor);this.changed('zoom');}
 changed(what){this.render();this.onCamera(what,this.cam);}

 _controls(){
  const c=this.canvas;let drag=null;
  c.addEventListener('pointerdown',e=>{drag={x:e.clientX,y:e.clientY,moved:false,pan:e.shiftKey||e.button===2};c.setPointerCapture(e.pointerId);});
  c.addEventListener('pointermove',e=>{
   if(!drag)return;const dx=e.clientX-drag.x,dy=e.clientY-drag.y;
   if(Math.abs(dx)+Math.abs(dy)<3&&!drag.moved)return;
   drag.moved=true;drag.x=e.clientX;drag.y=e.clientY;
   const [w,h]=this.size();
   if(drag.pan)this.pan(-2*dx/w,2*dy/h);else this.orbit(-dx*0.01,-dy*0.01);
  });
  c.addEventListener('pointerup',e=>{
   if(drag&&!drag.moved){const r=c.getBoundingClientRect();const face=this.pickAt(e.clientX-r.left,e.clientY-r.top);this.select(face);this.onPick(face);}
   drag=null;
  });
  c.addEventListener('contextmenu',e=>e.preventDefault());
  c.addEventListener('wheel',e=>{e.preventDefault();this.zoom(e.deltaY<0?1.15:1/1.15);},{passive:false});
  c.addEventListener('keydown',e=>{
   const keys={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]};
   let done=true;
   if(e.key in keys){const [a,b]=keys[e.key];if(e.shiftKey)this.pan(-0.1*a,0.1*b);else this.orbit(a*STEP,b*STEP);}
   else if(e.key==='+'||e.key==='=')this.zoom(1.25);
   else if(e.key==='-'||e.key==='_')this.zoom(1/1.25);
   else if(e.key==='f'||e.key==='F')this.fit();
   else if(e.key==='0'||e.key==='i'||e.key==='I')this.setView('iso');
   else if(KEY_VIEWS[e.key])this.setView(KEY_VIEWS[e.key]);
   else done=false;
   if(done)e.preventDefault();
  });
 }
}

/** Keys 1-6 choose +X, -X, +Y, -Y, +Z, -Z; 0 or I the isometric view. */
export const KEY_VIEWS={'1':'+x','2':'-x','3':'+y','4':'-y','5':'+z','6':'-z'};
export {VIEWS};
