// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
import {WINDOW_NM,MIN_SIZE_NM,shapeBounds,shapeCorners,validateShape} from './workspace-shapes.mjs';
import {toNm,shapeSvgAttributes} from './workspace-section.mjs';

export const snapNm=(value,step=5)=>Math.round(value/step)*step;
const clamp=(v,lo,hi)=>Math.min(hi,Math.max(lo,v));
// Translate, then shift back so the whole shape stays inside the window.
export function moveShape(shape,dx,dy){
 if(![dx,dy].every(Number.isFinite))throw new Error('Invalid move.');
 const b=shapeBounds(shape),w=WINDOW_NM;
 const tx=clamp(dx,w.xmin-b.xmin,w.xmax-b.xmax),ty=clamp(dy,w.ymin-b.ymin,w.ymax-b.ymax);
 if(shape.type==='rect')return {...shape,x:shape.x+tx,y:shape.y+ty};
 if(shape.type==='circle')return {...shape,cx:shape.cx+tx,cy:shape.cy+ty};
 return {...shape,points:shape.points.map(([x,y])=>[x+tx,y+ty])};
}
// Move one rectangle edge to a coordinate, keeping the opposite edge fixed.
export function resizeRect(shape,edge,value){
 if(shape.type!=='rect'||!Number.isFinite(value))throw new Error('Invalid rectangle resize.');
 const w=WINDOW_NM,x1=shape.x+shape.w,y1=shape.y+shape.h;
 if(edge==='left'){const x=clamp(value,w.xmin,x1-MIN_SIZE_NM);return {...shape,x,w:x1-x};}
 if(edge==='right'){const x=clamp(value,shape.x+MIN_SIZE_NM,w.xmax);return {...shape,w:x-shape.x};}
 if(edge==='bottom'){const y=clamp(value,w.ymin,y1-MIN_SIZE_NM);return {...shape,y,h:y1-y};}
 if(edge==='top'){const y=clamp(value,shape.y+MIN_SIZE_NM,w.ymax);return {...shape,h:y-shape.y};}
 throw new Error('Unknown edge.');
}
export function resizeCircle(shape,radius){
 if(shape.type!=='circle'||!Number.isFinite(radius))throw new Error('Invalid circle resize.');
 const w=WINDOW_NM,limit=Math.min(shape.cx-w.xmin,w.xmax-shape.cx,shape.cy-w.ymin,w.ymax-shape.cy);
 return {...shape,r:clamp(radius,MIN_SIZE_NM,limit)};
}
export function moveVertex(shape,index,x,y){
 if(shape.type!=='polygon'||!Number.isInteger(index)||index<0||index>=shape.points.length||![x,y].every(Number.isFinite))throw new Error('Invalid vertex move.');
 const w=WINDOW_NM;return {...shape,points:shape.points.map((p,i)=>i===index?[clamp(x,w.xmin,w.xmax),clamp(y,w.ymin,w.ymax)]:[...p])};
}
const HELP='Drag the selected shape to move it, or drag a yellow handle to resize. Release to apply; Escape cancels. With the shape or a handle focused, arrow keys move 10 nm (Shift: 1 nm). Positions snap to 5 nm while dragging.';

export function installShapeEditor(host,{shape,index,blocked,commit}){
 const svg=host.querySelector('svg[data-geometry-view="physical"]');
 const target=svg?.querySelector(`[data-pick-shape="${index}"]`);
 if(!svg||!target||!shape)return ()=>{};
 const ns='http://www.w3.org/2000/svg',make=(tag,attrs)=>{const e=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,v);return e;};
 const message=document.createElement('p');message.className='muted';message.setAttribute('role','status');message.textContent=HELP;host.append(message);
 const original=shapeSvgAttributes(shape).attrs;
 const show=candidate=>{for(const [k,v] of Object.entries(shapeSvgAttributes(candidate).attrs))target.setAttribute(k,v);};
 const restore=()=>{for(const [k,v] of Object.entries(original))target.setAttribute(k,v);};
 const handles=[];let gesture=null;
 const point=(e,inverse)=>{try{const p=new DOMPoint(e.clientX,e.clientY).matrixTransform(inverse);return Number.isFinite(p.x)&&Number.isFinite(p.y)?toNm(p.x,p.y):null;}catch{return null;}};
 const apply=(candidate,label)=>{
  if(blocked()){message.textContent='Resolve invalid inputs before editing the drawing.';restore();return;}
  let checked;try{checked=validateShape(candidate,index);}catch(error){message.textContent=error.message+' Shape unchanged.';restore();return;}
  if(JSON.stringify(checked)===JSON.stringify(shape)){restore();message.textContent=HELP;return;}
  commit(checked,label);
 };
 const finish=ok=>{if(!gesture)return;const g=gesture;gesture=null;if(g.element.hasPointerCapture?.(g.id))g.element.releasePointerCapture(g.id);if(ok&&g.moved&&g.candidate)apply(g.candidate,g.label);else{restore();message.textContent=ok?HELP:'Edit cancelled. Shape unchanged.';}};
 const cancel=()=>finish(false);for(const event of ['blur','resize','pagehide'])window.addEventListener(event,cancel);
 const begin=(element,e,update,label)=>{
  if(e.button!==0||gesture)return;
  if(blocked()){message.textContent='Resolve invalid inputs before editing the drawing.';return;}
  let inverse;try{inverse=svg.getScreenCTM()?.inverse();}catch{return;}if(!inverse)return;
  const start=point(e,inverse);if(!start)return;
  e.stopPropagation();gesture={id:e.pointerId,element,start,inverse,update,label,moved:false,candidate:null};element.setPointerCapture?.(e.pointerId);
 };
 const drag=(e)=>{
  if(!gesture||gesture.id!==e.pointerId)return;const p=point(e,gesture.inverse);if(!p){cancel();return;}
  const dx=p[0]-gesture.start[0],dy=p[1]-gesture.start[1];if(!gesture.moved&&Math.hypot(dx,dy)<3)return;
  gesture.moved=true;e.preventDefault();
  try{gesture.candidate=gesture.update(p,dx,dy);show(gesture.candidate);message.textContent='Preview: release to apply; Escape cancels.';}catch(error){message.textContent=error.message;}
 };
 const wire=(element,update,label,keyStep)=>{
  element.style.touchAction='none';
  element.addEventListener('pointerdown',e=>begin(element,e,update,label));
  element.addEventListener('pointermove',drag);
  element.addEventListener('pointerup',e=>{if(gesture?.id===e.pointerId){if(gesture.moved)e.stopPropagation();finish(true);}});
  element.addEventListener('pointercancel',e=>{if(gesture?.id===e.pointerId)cancel();});
  element.addEventListener('lostpointercapture',e=>{if(gesture?.id===e.pointerId)cancel();});
  element.addEventListener('keydown',e=>{
   if(e.key==='Escape'&&gesture){e.preventDefault();e.stopPropagation();cancel();return;}
   const delta={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,1],ArrowDown:[0,-1]}[e.key];
   if(!delta||e.ctrlKey||e.metaKey||e.altKey||gesture)return;
   e.preventDefault();e.stopPropagation();const step=e.shiftKey?1:10;
   try{apply(keyStep(delta[0]*step,delta[1]*step),label);}catch(error){message.textContent=error.message;}
  });
 };
 wire(target,(p,dx,dy)=>moveShape(shape,snapNm(dx),snapNm(dy)),`${shape.name} moved`,(dx,dy)=>moveShape(shape,dx,dy));
 target.style.cursor='move';
 const handle=(attrs,label,update,keyStep,cursor,value)=>{
  const h=make('rect',{...attrs,fill:'#fff0a8',role:'slider',tabindex:0,'aria-label':label,'aria-valuetext':value,'data-handle':label,'vector-effect':'non-scaling-stroke'});
  h.style.cursor=cursor;svg.append(h);handles.push(h);wire(h,update,label.replace(/^Resize|^Move/,m=>m==='Move'?'Moved':'Resized'),keyStep);
 };
 const b=shapeBounds(shape),[sx0,sy0]=[300+b.xmin/10,175-b.ymax/10],[sx1,sy1]=[300+b.xmax/10,175-b.ymin/10];
 if(shape.type==='rect'){
  const t=2;
  handle({x:sx0-t,y:sy0+t,width:2*t,height:Math.max(1,sy1-sy0-2*t)},`Resize ${shape.name} left edge`,p=>resizeRect(shape,'left',snapNm(p[0])),dx=>resizeRect(shape,'left',shape.x+dx),'ew-resize',`x ${shape.x} nm`);
  handle({x:sx1-t,y:sy0+t,width:2*t,height:Math.max(1,sy1-sy0-2*t)},`Resize ${shape.name} right edge`,p=>resizeRect(shape,'right',snapNm(p[0])),dx=>resizeRect(shape,'right',shape.x+shape.w+dx),'ew-resize',`x ${shape.x+shape.w} nm`);
  handle({x:sx0+t,y:sy0-t,width:Math.max(1,sx1-sx0-2*t),height:2*t},`Resize ${shape.name} top edge`,p=>resizeRect(shape,'top',snapNm(p[1])),(dx,dy)=>resizeRect(shape,'top',shape.y+shape.h+dy),'ns-resize',`y ${shape.y+shape.h} nm`);
  handle({x:sx0+t,y:sy1-t,width:Math.max(1,sx1-sx0-2*t),height:2*t},`Resize ${shape.name} bottom edge`,p=>resizeRect(shape,'bottom',snapNm(p[1])),(dx,dy)=>resizeRect(shape,'bottom',shape.y+dy),'ns-resize',`y ${shape.y} nm`);
 }else if(shape.type==='circle'){
  handle({x:sx1-3,y:175-shape.cy/10-3,width:6,height:6},`Resize ${shape.name} radius`,p=>resizeCircle(shape,snapNm(Math.hypot(p[0]-shape.cx,p[1]-shape.cy))),dx=>resizeCircle(shape,shape.r+dx),'ew-resize',`radius ${shape.r} nm`);
 }else{
  shapeCorners(shape).forEach(([x,y],i)=>handle({x:300+x/10-3,y:175-y/10-3,width:6,height:6},`Move ${shape.name} vertex ${i+1}`,p=>moveVertex(shape,i,snapNm(p[0]),snapNm(p[1])),(dx,dy)=>moveVertex(shape,i,x+dx,y+dy),'move',`(${x}, ${y}) nm`));
 }
 return ()=>{cancel();for(const event of ['blur','resize','pagehide'])window.removeEventListener(event,cancel);message.remove();handles.forEach(h=>h.remove());restore();target.style.cursor='';};
}
