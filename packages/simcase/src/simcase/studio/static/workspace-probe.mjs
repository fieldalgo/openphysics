// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// The displayed field is constant on each triangle, sampled at its centroid.
// At shared edges, prefer the last drawn triangle, matching canvas paint order.
export function triangleAt(field,x,y){
 if(!Number.isFinite(x)||!Number.isFinite(y))throw new Error('Probe coordinates must be finite.');
 for(let i=field.triangles.length-1;i>=0;i--){
  const [a,b,c]=field.triangles[i].map(n=>field.nodes[n]);
  const det=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1]);
  if(!Number.isFinite(det)||det===0)continue;
  const u=((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/det;
  const v=((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/det,w=1-u-v;
  if([u,v,w].every(n=>Number.isFinite(n)&&n>=-1e-12&&n<=1+1e-12))return {index:i,centroid:[(a[0]+b[0]+c[0])/3,(a[1]+b[1]+c[1])/3]};
 }
 return null;
}
export function probeField(field,values,x,y){
 if(!Array.isArray(values)||values.length!==field.triangles.length)throw new Error('Probe values must match triangles.');
 const triangle=triangleAt(field,x,y);if(!triangle)return null;
 const value=values[triangle.index];if(!Number.isFinite(value))throw new Error('Invalid probe sample.');
 return {...triangle,value,x,y};
}
