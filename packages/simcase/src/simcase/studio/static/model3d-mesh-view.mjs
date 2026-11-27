// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// The experimental 3D mesh view: the mesh's exterior and interface triangles (from
// /api/model3d/jobs/{job}/result) coloured by region, with mesh edges. It is the 3D view
// (model3d-view.mjs) with the mesh's triangles in place of the display triangles: the same
// camera, controls, sections and hidden regions, and picking on the same face ids, so a pick
// gives the same face names.
import * as THREE from '/vendor/three-0.186.1/three.module.js';
import {View3D} from '/model3d-assets/model3d-view.mjs';
import {SHADE,decode,faceRegion,regionColor,viewCamera} from '/model3d-assets/model3d-model.mjs';
import {triangleColors} from '/model3d-assets/model3d-mesh-model.mjs';

const SELECTED=new THREE.Color('#d1242f');

export class MeshView3D extends View3D{
 constructor(canvas,options){
  super(canvas,options);
  this.edgeMaterial.color.set(0x1f2937);this.edgeMaterial.transparent=true;this.edgeMaterial.opacity=0.45;
 }

 /** Show a mesh answer; keeps the camera if `keep`. */
 load(view,{keep=false}={}){
  this.view=view;
  this.positions=decode(view.positions,Float32Array);
  this.indices=decode(view.indices,Uint32Array);
  this.owner=decode(view.triangle_faces,Uint32Array);
  this.triangleRegions=decode(view.triangle_regions,Int32Array);
  const edges=decode(view.edge_indices,Uint32Array);
  this.edgeFaces=decode(view.edge_faces,Uint32Array);
  this.edgePositions=new Float32Array(6*this.edgeFaces.length);
  for(let e=0;e<this.edgeFaces.length;e++)for(let j=0;j<2;j++){const i=edges[2*e+j];
   for(let k=0;k<3;k++)this.edgePositions[6*e+3*j+k]=this.positions[3*i+k];}
  this.regionsByName=Object.fromEntries(view.regions.map(r=>[r.name,r]));
  this.hidden=new Set([...this.hidden].filter(n=>n in this.regionsByName));
  if(this.selected!==null&&!view.faces[this.selected])this.selected=null;
  if(!keep||!this.cam)this.cam=viewCamera(view,'iso');
  else this.cam={...this.cam,r:viewCamera(view).r};
  this.rebuild();
 }

 rebuild(){
  for(const o of [this.mesh,this.edges])if(o){this.scene.remove(o);o.geometry.dispose();}
  const v=this.view,shown=this.shownFaces(),names=v.region_names;
  const rgb={};const c=new THREE.Color();
  const colorOf=name=>{if(name===SELECTED)return [SELECTED.r,SELECTED.g,SELECTED.b];
   if(!(name in rgb)){c.set(regionColor(v,name));rgb[name]=[c.r,c.g,c.b];}return rgb[name];};
  const regionOf=t=>{
   const f=v.faces[this.owner[t]];
   if(f.id===this.selected)return SELECTED;
   const own=names[this.triangleRegions[t]];
   return own!==undefined&&!this.hidden.has(own)?own:faceRegion(f,this.regionsByName,this.hidden);
  };
  const shadeOf=t=>this.owner[t]===this.selected?1:SHADE[v.faces[this.owner[t]].axis];
  const tri=triangleColors(this.positions,this.indices,regionOf,colorOf,shadeOf,t=>shown.has(this.owner[t]));
  const g=new THREE.BufferGeometry();
  g.setAttribute('position',new THREE.BufferAttribute(tri.positions,3));
  g.setAttribute('color',new THREE.BufferAttribute(tri.colors,3));
  this.mesh=new THREE.Mesh(g,this.material);
  let m=0;for(let e=0;e<this.edgeFaces.length;e++)if(shown.has(this.edgeFaces[e]))m++;
  const seg=new Float32Array(6*m);let k=0;
  for(let e=0;e<this.edgeFaces.length;e++)if(shown.has(this.edgeFaces[e])){seg.set(this.edgePositions.subarray(6*e,6*e+6),k);k+=6;}
  const eg=new THREE.BufferGeometry();eg.setAttribute('position',new THREE.BufferAttribute(seg,3));
  this.edges=new THREE.LineSegments(eg,this.edgeMaterial);
  this.scene.add(this.mesh,this.edges);
  this.applySection();
  this.render();
 }
}
