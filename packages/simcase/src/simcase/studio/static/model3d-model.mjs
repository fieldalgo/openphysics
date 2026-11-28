// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Pure helpers of the experimental 3D view: no DOM, no WebGL, no network, so Node tests them.
// The camera contract (docs/packages/simcase/studio_3d.md, "Camera"; the W3 oracle in
// tests/simcase/model3d_pick_oracle.py follows the same words):
//  - the frame is metres from the domain centre; R is half the domain diagonal;
//  - an orthographic camera looks at the target from target + 4 R e (e the unit eye direction);
//    its axes are z = e, x = normalize(up x z), y = z x x, as three.js lookAt makes them;
//  - "fit" frames a sphere of radius 1.1 R: for W >= H half height 1.1 R / zoom and half width
//    that times W / H, else half width 1.1 R / zoom and half height that times H / W;
//  - a canvas point (px, py) in CSS pixels is at ndc (2 px / W - 1, 1 - 2 py / H).

export const MARGIN=1.1, EYE=4;
const S3=1/Math.sqrt(3);

/** The little-endian base64 arrays of a display or section answer. */
export function decode(text,Type){
 const bytes=typeof Buffer!=='undefined'?Uint8Array.from(Buffer.from(text,'base64')):Uint8Array.from(atob(text),c=>c.charCodeAt(0));
 return new Type(bytes.buffer,bytes.byteOffset,bytes.byteLength/Type.BYTES_PER_ELEMENT);
}

export const dot=(a,b)=>a[0]*b[0]+a[1]*b[1]+a[2]*b[2];
export const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
export const norm=a=>{const n=Math.hypot(a[0],a[1],a[2]);return [a[0]/n,a[1]/n,a[2]/n];};
const add=(a,b,s=1)=>[a[0]+s*b[0],a[1]+s*b[1],a[2]+s*b[2]];

/** Half the domain diagonal (m) from the answer's half extents. */
export function radiusOf(view){const h=view.half_extent_m;return Math.hypot(h[0],h[1],h[2]);}

/** The named views: eye direction and up vector. 'iso' is the contract's first camera. */
export const VIEWS={
 iso:{eye:[S3,S3,S3],up:[0,0,1],label:'Isometric'},
 '+x':{eye:[1,0,0],up:[0,0,1],label:'+X'}, '-x':{eye:[-1,0,0],up:[0,0,1],label:'−X'},
 '+y':{eye:[0,1,0],up:[0,0,1],label:'+Y'}, '-y':{eye:[0,-1,0],up:[0,0,1],label:'−Y'},
 '+z':{eye:[0,0,1],up:[0,1,0],label:'+Z'}, '-z':{eye:[0,0,-1],up:[0,1,0],label:'−Z'},
};

/** A camera state of a named view, fitted (target at the domain centre, zoom 1). */
export function viewCamera(view,name='iso'){
 const v=VIEWS[name];
 return {r:radiusOf(view),eye:[...v.eye],up:[...v.up],target:[0,0,0],zoom:1};
}

/** The camera's axes, position and half extents for a W x H canvas. */
export function frameOf(cam,width,height){
 const z=norm(cam.eye),x=norm(cross(cam.up,z)),y=cross(z,x);
 const base=MARGIN*cam.r/cam.zoom;
 const [hw,hh]=width>=height?[base*width/height,base]:[base,base*height/width];
 return {x,y,z,halfWidth:hw,halfHeight:hh,position:add(cam.target,z,EYE*cam.r),near:0,far:2*EYE*cam.r,width,height};
}

/** The pick ray of a canvas point (CSS pixels): {origin, direction} in the frame (m). */
export function rayAt(frame,px,py){
 const nx=2*px/frame.width-1,ny=1-2*py/frame.height;
 let o=add(frame.position,frame.x,nx*frame.halfWidth);o=add(o,frame.y,ny*frame.halfHeight);
 return {origin:o,direction:[-frame.z[0],-frame.z[1],-frame.z[2]]};
}

/** Rotate a vector about a unit axis by angle (radians), Rodrigues. */
export function rotate(v,axis,angle){
 const c=Math.cos(angle),s=Math.sin(angle),k=dot(axis,v),w=cross(axis,v);
 return [v[0]*c+w[0]*s+axis[0]*k*(1-c),v[1]*c+w[1]*s+axis[1]*k*(1-c),v[2]*c+w[2]*s+axis[2]*k*(1-c)];
}

/** Orbit: yaw about world +z, then pitch about the camera's x axis (radians). */
export function orbit(cam,yaw,pitch){
 const z=[0,0,1];
 let eye=rotate(cam.eye,z,yaw),up=rotate(cam.up,z,yaw);
 const x=norm(cross(up,eye));
 eye=rotate(eye,x,pitch);up=rotate(up,x,pitch);
 return {...cam,eye:norm(eye),up:norm(up)};
}

/** Pan by a fraction of the visible half extents along the camera's x and y. */
export function pan(cam,frame,fx,fy){
 let t=add(cam.target,frame.x,fx*frame.halfWidth);t=add(t,frame.y,fy*frame.halfHeight);
 return {...cam,target:t};
}

export function zoomBy(cam,factor){return {...cam,zoom:Math.min(200,Math.max(0.05,cam.zoom*factor))};}
/** Fit: the whole domain again, keeping the direction. */
export function fit(cam){return {...cam,target:[0,0,0],zoom:1};}

/** Whether a face is drawn: a side holds a non-void region that is shown. */
export function faceShown(face,regionsByName,hidden){
 return [...face.minus,...face.plus].some(n=>!regionsByName[n]?.void&&!hidden.has(n));
}

/** The region a face is coloured by: a shown non-void side, the plus side first. */
export function faceRegion(face,regionsByName,hidden){
 return [...face.plus,...face.minus].find(n=>!regionsByName[n]?.void&&!hidden.has(n))??null;
}

/** The section's kept side: coordinate <= at (frame metres); null keeps all. */
export function kept(section,p){return !section||p[section.axis]<=section.at+1e-12*Math.max(1,Math.abs(section.at));}

/**
 * CPU pick: the nearest triangle of a shown face hit by the ray, on the kept side of the section.
 * positions: Float32Array (xyz per vertex, frame m); indices: Uint32Array (3 per triangle);
 * owner: face id per triangle; shown: Set of face ids. Returns {face, t, point} or null.
 */
export function pick(ray,positions,indices,owner,shown,section=null){
 const o=ray.origin,d=ray.direction;let best=null;
 for(let t=0;t<owner.length;t++){
  if(!shown.has(owner[t]))continue;
  const a=3*indices[3*t],b=3*indices[3*t+1],c=3*indices[3*t+2];
  const e1=[positions[b]-positions[a],positions[b+1]-positions[a+1],positions[b+2]-positions[a+2]];
  const e2=[positions[c]-positions[a],positions[c+1]-positions[a+1],positions[c+2]-positions[a+2]];
  const p=cross(d,e2),det=dot(e1,p);
  if(Math.abs(det)<1e-300)continue;
  const s=[o[0]-positions[a],o[1]-positions[a+1],o[2]-positions[a+2]];
  const u=dot(s,p)/det;if(u<0||u>1)continue;
  const q=cross(s,e1),v=dot(d,q)/det;if(v<0||u+v>1)continue;
  const dist=dot(e2,q)/det;if(dist<=0)continue;
  if(best&&dist>=best.t)continue;
  const point=add(o,d,dist);
  if(!kept(section,point))continue;
  best={face:owner[t],t:dist,point};
 }
 return best;
}

/** Display indices of the shown faces, and the face of each drawn triangle. */
export function drawn(view,indices,shown){
 const out=[],faces=[];
 for(const f of view.faces){
  if(!shown.has(f.id))continue;
  for(let t=f.first_triangle;t<f.first_triangle+f.triangle_count;t++){out.push(indices[3*t],indices[3*t+1],indices[3*t+2]);faces.push(f.id);}
 }
 return {indices:Uint32Array.from(out),faces};
}

const PALETTE=['#4c78a8','#f58518','#54a24b','#e45756','#72b7b2','#eeca3b','#b279a2','#ff9da6','#9d755d','#bab0ac'];
/** Region colours in region order (void regions are not drawn). */
export function regionColor(view,name){
 const solid=view.regions.filter(r=>!r.void);const i=solid.findIndex(r=>r.name===name);
 return PALETTE[(i<0?0:i)%PALETTE.length];
}

/** Shading by face orientation, so the three visible sides of a box differ. */
export const SHADE={x:0.78,y:0.62,z:1.0};
/** The shade of a face: by its axis, or for a curved face (a cylinder or a sphere, axis null) one value. */
export const CURVED_SHADE=0.9;
export function shadeOf(face){return face.axis?SHADE[face.axis]:CURVED_SHADE;}

/** The names panel's lines of a face. */
export function faceLines(view,face){
 const unit=view.unit;
 const where=face.axis?`${face.axis} = ${Number(face.at.toPrecision(6))} ${unit}`:(face.shape||'curved');
 return {title:`Face ${face.id} · ${where}`,
  detail:`area ${Number(face.area.toPrecision(6))} ${unit}² · ${face.exterior?'exterior':'interior'}${face.tag?' · tag '+face.tag:''}`
   +(view.display_note?` · ${view.display_note}`:''),
  sides:`${face.minus.length?face.minus.join(', '):'outside'} | ${face.plus.length?face.plus.join(', '):'outside'}`,
  names:face.names};
}

/** The slider of a section along an axis: domain bounds in document units, 200 steps. */
export function sectionRange(view,axis){
 const lo=view.domain[axis+'min'],hi=view.domain[axis+'max'];
 return {min:lo,max:hi,step:(hi-lo)/200,start:(lo+hi)/2};
}

/** Document units -> frame metres along an axis. */
export function toFrame(view,axis,value){
 const i='xyz'.indexOf(axis);return value*view.metres_per_unit-view.origin_m[i];
}
