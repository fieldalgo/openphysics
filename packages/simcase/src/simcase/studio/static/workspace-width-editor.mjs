// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
export function draggedWidth(startWidth, delta, side) {
 if (![startWidth,delta].every(Number.isFinite) || ![-1,1].includes(side)) throw new Error('Invalid width gesture');
 return Math.min(900, Math.max(300, Math.round(startWidth + side * delta * 20)));
}
export function draggedHeight(startHeight, delta) {
 if (![startHeight,delta].every(Number.isFinite)) throw new Error('Invalid height gesture');
 return Math.min(500, Math.max(100, Math.round(startHeight - delta * 10)));
}
export function installWidthEditor(host,{width,height=220,blocked,commit,commitHeight}) {
 const svg=host.querySelector('svg[data-geometry-view="physical"]');
 if(!svg)return ()=>{};
 const ns='http://www.w3.org/2000/svg';
 const make=(tag,attrs)=>{const e=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,v);return e;};
 const preview=make('rect',{y:175-height/10,height:height/10,fill:'none',stroke:'#fff0a8','stroke-dasharray':'3 2','pointer-events':'none',visibility:'hidden'});
 svg.append(preview);
 const message=document.createElement('p');message.className='muted';message.setAttribute('role','status');
 const help='Drag a side edge for symmetric width or the top edge for height; the bottom stays at y = 0. Release to apply; Escape cancels. Arrow keys: 10 nm; Shift: 1 nm.';
 message.textContent=help;host.append(message);
 let gesture=null;const handles=[];
 const position=(e,inverse,axis)=>{try{const x=new DOMPoint(e.clientX,e.clientY).matrixTransform(inverse)[axis];return Number.isFinite(x)?x:null;}catch{return null;}};
 const finish=apply=>{
  if(!gesture)return;const g=gesture;gesture=null;preview.setAttribute('visibility','hidden');
  if(g.handle.hasPointerCapture(g.id))g.handle.releasePointerCapture(g.id);
  message.textContent=apply?help:'Resize cancelled. Model unchanged.';
  if(apply&&!blocked()&&g.value!==g.initial){g.apply(g.value);host.querySelector('[aria-label="'+g.handle.getAttribute('aria-label')+'"]')?.focus();}
 };
 const cancel=()=>finish(false);for(const event of ['blur','resize','pagehide'])window.addEventListener(event,cancel);
 for(const side of (commitHeight?[-1,1,0]:[-1,1])){
  const vertical=side===0,initial=vertical?height:width,min=vertical?100:300,max=vertical?500:900,axis=vertical?'y':'x',apply=vertical?commitHeight:commit;
  const next=delta=>vertical?draggedHeight(height,delta):draggedWidth(width,delta,side);
  const handle=make('rect',{x:vertical?300-width/20+4:300+side*width/20-4,y:172-height/10,width:vertical?width/10-8:8,height:vertical?6:height/10+6,fill:'#fff0a8',role:'slider',tabindex:0,'aria-label':vertical?'Resize core top edge':side<0?'Resize core left edge':'Resize core right edge','aria-valuemin':min,'aria-valuemax':max,'aria-valuenow':initial,'aria-valuetext':initial+' nm','aria-orientation':vertical?'vertical':'horizontal'});
  handle.style.cursor=vertical?'ns-resize':'ew-resize';handle.style.touchAction='none';svg.append(handle);handles.push(handle);
  handle.onclick=e=>e.stopPropagation();
  handle.onpointerdown=e=>{
   if(e.button!==0||gesture)return;e.preventDefault();e.stopPropagation();
   if(blocked()){message.textContent='Resolve invalid inputs before resizing.';return;}
   let inverse;try{inverse=svg.getScreenCTM()?.inverse();}catch{return;}if(!inverse)return;const start=position(e,inverse,axis);if(start===null)return;
   handle.focus();gesture={id:e.pointerId,handle,start,inverse,value:initial,initial,apply,side};handle.setPointerCapture(e.pointerId);
  };
  handle.onpointermove=e=>{
   if(!gesture||gesture.id!==e.pointerId)return;
   const x=position(e,gesture.inverse,axis);if(x===null){cancel();return;}
   gesture.value=next(x-gesture.start);
   const w=vertical?width:gesture.value,h=vertical?gesture.value:height;
   preview.setAttribute('x',300-w/20);preview.setAttribute('width',w/10);preview.setAttribute('y',175-h/10);preview.setAttribute('height',h/10);preview.setAttribute('visibility','visible');
   message.textContent='Preview: '+gesture.value+' nm. Release to apply; Escape cancels.';
  };
  handle.onpointerup=e=>{if(gesture?.id!==e.pointerId)return;const x=position(e,gesture.inverse,axis);if(x===null){cancel();return;}gesture.value=x===gesture.start?initial:next(x-gesture.start);finish(true);};
  handle.onpointercancel=e=>{if(gesture?.id===e.pointerId)cancel();};handle.onlostpointercapture=handle.onpointercancel;
  handle.onkeydown=e=>{
   if(e.key==='Escape'){e.preventDefault();e.stopPropagation();cancel();return;}
   if(gesture||e.ctrlKey||e.metaKey||e.altKey||!(vertical?['ArrowUp','ArrowDown','Home','End']:['ArrowLeft','ArrowRight','Home','End']).includes(e.key))return;
   e.preventDefault();e.stopPropagation();if(blocked()){message.textContent='Resolve invalid inputs before resizing.';return;}
   const value=e.key==='Home'?min:e.key==='End'?max:Math.max(min,Math.min(max,initial+(vertical?(e.key==='ArrowUp'?1:-1):(e.key==='ArrowRight'?1:-1)*side)*(e.shiftKey?1:10)));
   if(value!==initial){apply(value);host.querySelector('[aria-label="'+handle.getAttribute('aria-label')+'"]')?.focus();}
  };
 }
 return ()=>{cancel();for(const event of ['blur','resize','pagehide'])window.removeEventListener(event,cancel);message.remove();preview.remove();handles.forEach(handle=>handle.remove());};
}
