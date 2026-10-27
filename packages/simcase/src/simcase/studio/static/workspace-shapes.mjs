// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

// Optical cross-section shapes in nanometres. Later shapes win where they overlap,
// as in the simcase geometry contract; the silica background fills the rest.
export const WINDOW_NM=Object.freeze({xmin:-1500,xmax:1500,ymin:-1200,ymax:1200});
export const MAX_SHAPES=8,MAX_POINTS=12,MIN_SIZE_NM=10;
// Lossless physmat data covering 1400–1700 nm. Uniaxial crystals use their ordinary index (isotropic model).
export const SHAPE_MATERIALS=Object.freeze({Silicon:'Si','Silicon nitride':'Si3N4',Silica:'SiO2',Air:'vacuum','Sapphire (ordinary)':'Al2O3','Lithium niobate (ordinary)':'LiNbO3','Indium phosphide':'InP','Gallium arsenide':'GaAs','Calcium fluoride':'CaF2','Magnesium fluoride (ordinary)':'MgF2'});
export const V4_MATERIALS=Object.freeze(['Silicon','Silicon nitride','Silica','Air']);
// Above the silica index across the band, so they can guide light and get the core mesh size.
export const GUIDING_MATERIALS=Object.freeze(['Silicon','Silicon nitride','Sapphire (ordinary)','Lithium niobate (ordinary)','Indium phosphide','Gallium arsenide']);
const NAME=/^[A-Za-z0-9][A-Za-z0-9 _-]{0,39}$/;
const finite=(value,name)=>{if(typeof value!=='number'||!Number.isFinite(value))throw new Error(`Invalid ${name}.`);return value;};
// Shared edges must reach the solver as identical numbers, so corners are rounded once in nm.
const tidy=value=>Math.round(value*1e6)/1e6;

export function legacyCoreShape(width,height,material){
 return {name:'Core',type:'rect',material:GUIDING_MATERIALS.includes(material)?material:'',x:tidy(-width/2),y:0,w:width,h:height};
}
export function shapeCorners(shape){
 if(shape.type==='rect'){const x1=tidy(shape.x+shape.w),y1=tidy(shape.y+shape.h);return [[shape.x,shape.y],[x1,shape.y],[x1,y1],[shape.x,y1]];}
 if(shape.type==='polygon')return shape.points.map(p=>[...p]);
 throw new Error('Circles have no corners.');
}
export function shapeBounds(shape){
 if(shape.type==='circle')return {xmin:shape.cx-shape.r,xmax:shape.cx+shape.r,ymin:shape.cy-shape.r,ymax:shape.cy+shape.r};
 const corners=shapeCorners(shape),xs=corners.map(p=>p[0]),ys=corners.map(p=>p[1]);
 return {xmin:Math.min(...xs),xmax:Math.max(...xs),ymin:Math.min(...ys),ymax:Math.max(...ys)};
}
export function designBounds(shapes){
 const boxes=shapes.map(shapeBounds);
 return {xmin:Math.min(...boxes.map(b=>b.xmin)),xmax:Math.max(...boxes.map(b=>b.xmax)),ymin:Math.min(...boxes.map(b=>b.ymin)),ymax:Math.max(...boxes.map(b=>b.ymax))};
}
const cross=(o,a,b)=>(a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0]);
function segmentsTouch(p,q,r,s){
 const d1=cross(r,s,p),d2=cross(r,s,q),d3=cross(p,q,r),d4=cross(p,q,s);
 if(((d1>0&&d2<0)||(d1<0&&d2>0))&&((d3>0&&d4<0)||(d3<0&&d4>0)))return true;
 const on=(a,b,c)=>Math.min(a[0],b[0])<=c[0]&&c[0]<=Math.max(a[0],b[0])&&Math.min(a[1],b[1])<=c[1]&&c[1]<=Math.max(a[1],b[1]);
 return (d1===0&&on(r,s,p))||(d2===0&&on(r,s,q))||(d3===0&&on(p,q,r))||(d4===0&&on(p,q,s));
}
export function polygonArea(points){let a=0;points.forEach((p,i)=>{const q=points[(i+1)%points.length];a+=p[0]*q[1]-q[0]*p[1];});return Math.abs(a)/2;}
export function validatePolygon(points){
 if(!Array.isArray(points)||points.length<3||points.length>MAX_POINTS)throw new Error(`A polygon needs 3–${MAX_POINTS} vertices.`);
 const copy=points.map((p,i)=>{if(!Array.isArray(p)||p.length!==2)throw new Error(`Vertex ${i+1} needs x and y.`);return [finite(p[0],`vertex ${i+1} x`),finite(p[1],`vertex ${i+1} y`)];});
 const n=copy.length;
 for(let i=0;i<n;i++){const a=copy[i],b=copy[(i+1)%n];if(Math.hypot(b[0]-a[0],b[1]-a[1])<1)throw new Error(`Polygon edge ${i+1} is shorter than 1 nm.`);}
 for(let i=0;i<n;i++)for(let j=i+1;j<n;j++){
  if(j===i+1||(i===0&&j===n-1))continue;
  if(segmentsTouch(copy[i],copy[(i+1)%n],copy[j],copy[(j+1)%n]))throw new Error(`Polygon edges ${i+1} and ${j+1} cross or touch.`);
 }
 if(polygonArea(copy)<MIN_SIZE_NM*MIN_SIZE_NM)throw new Error(`Polygon area must be at least ${MIN_SIZE_NM*MIN_SIZE_NM} nm².`);
 return copy;
}
export function validateShape(raw,index=0){
 const where=`Shape ${index+1}`;
 if(!raw||typeof raw!=='object')throw new Error(`${where} is missing.`);
 if(typeof raw.name!=='string'||!NAME.test(raw.name)||raw.name.trim()!==raw.name||raw.name.toLowerCase()==='background')throw new Error(`${where}: name must be 1–40 letters, digits, spaces, _ or -, and not "background".`);
 if(!['',...Object.keys(SHAPE_MATERIALS)].includes(raw.material))throw new Error(`${where}: unsupported material.`);
 let shape;
 if(raw.type==='rect'){
  shape={name:raw.name,type:'rect',material:raw.material,x:finite(raw.x,'x'),y:finite(raw.y,'y'),w:finite(raw.w,'width'),h:finite(raw.h,'height')};
  if(shape.w<MIN_SIZE_NM||shape.h<MIN_SIZE_NM)throw new Error(`${raw.name}: width and height must be at least ${MIN_SIZE_NM} nm.`);
 }else if(raw.type==='circle'){
  shape={name:raw.name,type:'circle',material:raw.material,cx:finite(raw.cx,'centre x'),cy:finite(raw.cy,'centre y'),r:finite(raw.r,'radius')};
  if(shape.r<MIN_SIZE_NM)throw new Error(`${raw.name}: radius must be at least ${MIN_SIZE_NM} nm.`);
 }else if(raw.type==='polygon'){
  try{shape={name:raw.name,type:'polygon',material:raw.material,points:validatePolygon(raw.points)};}catch(error){throw new Error(`${raw.name}: ${error.message}`);}
 }else throw new Error(`${where}: type must be rect, circle or polygon.`);
 const b=shapeBounds(shape),w=WINDOW_NM;
 if(b.xmin<w.xmin||b.xmax>w.xmax||b.ymin<w.ymin||b.ymax>w.ymax)throw new Error(`${raw.name} must stay inside the window x ${w.xmin}…${w.xmax} nm, y ${w.ymin}…${w.ymax} nm.`);
 return shape;
}
export function validateShapes(list){
 if(!Array.isArray(list)||list.length<1||list.length>MAX_SHAPES)throw new Error(`A design needs 1–${MAX_SHAPES} shapes.`);
 const shapes=list.map(validateShape),names=new Set();
 for(const s of shapes){const key=s.name.toLowerCase();if(names.has(key))throw new Error(`Shape name "${s.name}" is used twice.`);names.add(key);}
 return shapes;
}
// Run readiness, separate from structural validity: drafts may hold unassigned materials.
export function shapesBlock(shapes){
 const missing=shapes.find(s=>!s.material);if(missing)return `Assign a material to ${missing.name}.`;
 if(!shapes.some(s=>GUIDING_MATERIALS.includes(s.material)))return 'Add a shape of a material above the silica index (for example silicon or silicon nitride) to guide light.';
 return '';
}
export function overlappingPairs(shapes){
 const boxes=shapes.map(shapeBounds),pairs=[];
 for(let i=0;i<shapes.length;i++)for(let j=i+1;j<shapes.length;j++){const a=boxes[i],b=boxes[j];if(a.xmin<b.xmax&&b.xmin<a.xmax&&a.ymin<b.ymax&&b.ymin<a.ymax)pairs.push([i,j]);}
 return pairs;
}
export function solverShapes(shapes,coreMeshUm){
 return shapes.map((s,i)=>{
  const base={name:'s'+(i+1),material:SHAPE_MATERIALS[s.material]};
  if(GUIDING_MATERIALS.includes(s.material))base.mesh_size=coreMeshUm;
  if(s.type==='circle')return {...base,type:'circle',cx:s.cx/1000,cy:s.cy/1000,r:s.r/1000};
  return {...base,type:'polygon',points:shapeCorners(s).map(([x,y])=>[x/1000,y/1000])};
 });
}
export function gradingCentre(shapes){
 const guiding=shapes.filter(s=>GUIDING_MATERIALS.includes(s.material)),b=designBounds(guiding.length?guiding:shapes);
 return [(b.xmin+b.xmax)/2000,(b.ymin+b.ymax)/2000];
}
const nm=value=>Number.isInteger(value)?String(value):String(Math.round(value*1000)/1000);
export function shapeText(s){
 const geometry=s.type==='rect'?`x ${nm(s.x)}…${nm(tidy(s.x+s.w))}, y ${nm(s.y)}…${nm(tidy(s.y+s.h))}`:s.type==='circle'?`centre (${nm(s.cx)}, ${nm(s.cy)}), r ${nm(s.r)}`:s.points.map(p=>`(${nm(p[0])}, ${nm(p[1])})`).join(' ');
 return `${s.name}: ${s.type} ${s.material||'unassigned'} ${geometry} nm`;
}
export function designSummary(model){
 const shapes=model.shapes;
 if(shapes.length===1){const s=shapes[0];
  if(s.type==='rect')return `${nm(s.w)} × ${nm(s.h)} nm · ${s.material||'unassigned'}`;
  if(s.type==='circle')return `r ${nm(s.r)} nm circle · ${s.material||'unassigned'}`;
  return `${s.points.length}-vertex polygon · ${s.material||'unassigned'}`;
 }
 return `${shapes.length} shapes · ${[...new Set(shapes.map(s=>s.material||'unassigned'))].join(', ')}`;
}
function uniqueName(base,shapes){const used=new Set(shapes.map(s=>s.name.toLowerCase()));for(let i=1;;i++){const name=`${base} ${i}`;if(!used.has(name.toLowerCase()))return name;}}
export function newShape(type,shapes){
 const name=uniqueName(type==='rect'?'Rectangle':type==='circle'?'Circle':'Polygon',shapes);
 if(type==='rect')return {name,type,material:'Silicon',x:-200,y:300,w:400,h:200};
 if(type==='circle')return {name,type,material:'Silicon',cx:0,cy:600,r:150};
 if(type==='polygon')return {name,type,material:'Silicon',points:[[-200,300],[200,300],[0,600]]};
 throw new Error('Unknown shape type.');
}
export function duplicateShape(shape,shapes){
 const offset=100,name=uniqueName(shape.name.replace(/ copy( \d+)?$/,'').slice(0,28).trim()+' copy',shapes);
 const moved=shape.type==='circle'?{...shape,cx:shape.cx+offset}:shape.type==='rect'?{...shape,x:shape.x+offset}:{...shape,points:shape.points.map(([x,y])=>[x+offset,y])};
 try{return validateShape({...moved,name});}catch{return validateShape({...shape,points:shape.points?.map(p=>[...p]),name});}
}
// Exact translation (rounded once in nm) used by alignment; the caller validates the window.
export function translateShape(shape,dx,dy){
 if(shape.type==='rect')return {...shape,x:tidy(shape.x+dx),y:tidy(shape.y+dy)};
 if(shape.type==='circle')return {...shape,cx:tidy(shape.cx+dx),cy:tidy(shape.cy+dy)};
 return {...shape,points:shape.points.map(([x,y])=>[tidy(x+dx),tidy(y+dy)])};
}
export const ALIGN_ACTIONS=Object.freeze({'centre-x':'Centre on x = 0','rest-y':'Rest on y = 0','left-of':'Place left of','right-of':'Place right of','on-top':'Place on top of','below':'Place below','centre-on':'Centre on'});
// Bounds edges move to exact coordinates; a result outside the window is refused, not clamped.
export function alignShape(shape,action,reference=null){
 const b=shapeBounds(shape),r=reference&&shapeBounds(reference),cx=(b.xmin+b.xmax)/2,cy=(b.ymin+b.ymax)/2;
 if(!ALIGN_ACTIONS[action])throw new Error('Unknown alignment.');
 if(!['centre-x','rest-y'].includes(action)&&!r)throw new Error('Choose a reference shape.');
 const [dx,dy]={'centre-x':[-cx,0],'rest-y':[0,-b.ymin],'left-of':r&&[r.xmin-b.xmax,0],'right-of':r&&[r.xmax-b.xmin,0],'on-top':r&&[0,r.ymax-b.ymin],'below':r&&[0,r.ymin-b.ymax],'centre-on':r&&[(r.xmin+r.xmax)/2-cx,0]}[action];
 const moved=translateShape(shape,dx,dy);
 try{return validateShape(moved);}catch{throw new Error(`${ALIGN_ACTIONS[action]}${reference?' '+reference.name:''} would move ${shape.name} outside the window.`);}
}
