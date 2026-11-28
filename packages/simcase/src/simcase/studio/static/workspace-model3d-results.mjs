// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// The 3D model's result view (slice D, UI): the temperature of a run on the mesh's exterior and
// interface triangles (the run's /surface answer, or the surface map a kept record holds), coloured
// from blue (minimum) to red (maximum), with a cut plane drawn from the run's exact P1 slice
// (/cut). It is the 3D view (model3d-view.mjs) with the run's triangles: the same camera, controls,
// hidden regions and face picking; a pick also keeps the point hit, for a probe.
import * as THREE from '/vendor/three-0.186.1/three.module.js';
import {View3D} from '/model3d-assets/model3d-view.mjs';
import {SHADE,decode,pick,rayAt,viewCamera} from '/model3d-assets/model3d-model.mjs';
import {temperatureColor,cutColor,srgbToLinear,UNITS} from './workspace-model3d.mjs';

export class TemperatureView3D extends View3D{
 constructor(canvas,options){super(canvas,options);this.cut=null;this.lastHit=null;}

 /** Show a surface answer (positions in metres from origin_m, one temperature per position). */
 load(surface,{keep=false}={}){
  this.positions=decode(surface.positions,Float32Array);
  // the camera's radius: the half extents of the triangles about origin_m (the run's answer has no display box)
  const half=[0,0,0];for(let i=0;i<this.positions.length;i++){const a=i%3;half[a]=Math.max(half[a],Math.abs(this.positions[i]));}
  this.view={...surface,metres_per_unit:surface.metres_per_unit??UNITS[surface.unit],half_extent_m:surface.half_extent_m??half};
  this.indices=decode(surface.indices,Uint32Array);
  this.owner=decode(surface.triangle_faces,Uint32Array);
  this.temperature=decode(surface.temperature,Float32Array);
  this.edgePositions=new Float32Array(0);this.edgeFaces=new Uint32Array(0);
  this.tmin=surface.temperature_min.value;this.tmax=surface.temperature_max.value;
  this.regionsByName=Object.fromEntries(surface.regions.map(r=>[r.name,r]));
  this.hidden=new Set([...this.hidden].filter(n=>n in this.regionsByName));
  if(this.selected!==null&&!surface.faces[this.selected])this.selected=null;
  if(!keep||!this.cam)this.cam=viewCamera(this.view,'iso');
  this.rebuild();
 }

 rebuild(){
  for(const o of [this.mesh,this.edges])if(o){this.scene.remove(o);o.geometry.dispose();}
  const v=this.view,shown=this.shownFaces(),n=this.indices.length/3;
  let m=0;for(let t=0;t<n;t++)if(shown.has(this.owner[t]))m++;
  const pos=new Float32Array(9*m),col=new Float32Array(9*m);let k=0;
  for(let t=0;t<n;t++){
   const f=this.owner[t];if(!shown.has(f))continue;
   const s=f===this.selected?1:SHADE[v.faces[f].axis];
   for(let j=0;j<3;j++){
    const i=this.indices[3*t+j],c=f===this.selected?[0.82,0.14,0.18]:temperatureColor(this.temperature[i],this.tmin,this.tmax);
    pos.set(this.positions.subarray(3*i,3*i+3),k);col[k]=srgbToLinear(c[0]*s);col[k+1]=srgbToLinear(c[1]*s);col[k+2]=srgbToLinear(c[2]*s);k+=3;   // V8: sRGB colours as linear
   }
  }
  const g=new THREE.BufferGeometry();
  g.setAttribute('position',new THREE.BufferAttribute(pos,3));g.setAttribute('color',new THREE.BufferAttribute(col,3));
  this.mesh=new THREE.Mesh(g,this.material);
  this.edges=new THREE.LineSegments(new THREE.BufferGeometry(),this.edgeMaterial);
  this.scene.add(this.mesh,this.edges);
  this.applySection();this.render();
 }

 /** Show a cut answer (positions from its origin_m) coloured over the cut's own range, the part beyond it clipped; null removes it. */
 setCut(cut){
  if(this.cutMesh){this.scene.remove(this.cutMesh);this.cutMesh.geometry.dispose();this.cutMesh=null;}
  this.cut=cut;
  if(!cut){this.setSection(null);return;}
  const p=decode(cut.positions,Float32Array),ix=decode(cut.indices,Uint32Array),T=decode(cut.temperature,Float32Array);
  const shift=cut.origin_m.map((o,a)=>o-this.view.origin_m[a]);
  const pos=new Float32Array(3*ix.length),col=new Float32Array(3*ix.length);
  // the cut's own colour range (its own legend under the view), not the surface's
  const lo=cut.temperature_min.value,hi=cut.temperature_max.value;
  for(let q=0;q<ix.length;q++){const i=ix[q],c=cutColor(T[i],lo,hi);       // V8: the cut's saturated map, sRGB as linear
   for(let a=0;a<3;a++){pos[3*q+a]=p[3*i+a]+shift[a];col[3*q+a]=srgbToLinear(c[a]);}}
  const g=new THREE.BufferGeometry();
  g.setAttribute('position',new THREE.BufferAttribute(pos,3));g.setAttribute('color',new THREE.BufferAttribute(col,3));
  this.cutMesh=new THREE.Mesh(g,new THREE.MeshBasicMaterial({vertexColors:true,side:THREE.DoubleSide}));
  this.scene.add(this.cutMesh);
  this.setSection({axis:cut.axis,at:cut.at});
 }

 /** The face at a canvas point; the hit point is kept (document units) for a probe. */
 pickAt(px,py){
  if(!this.view)return null;
  const hit=pick(rayAt(this.frame(),px,py),this.positions,this.indices,this.owner,this.shownFaces(),this.section);
  this.lastHit=hit?{face:hit.face,point:hit.point.map((x,a)=>(x+this.view.origin_m[a])/this.view.metres_per_unit)}:null;
  return hit?hit.face:null;
 }
}
