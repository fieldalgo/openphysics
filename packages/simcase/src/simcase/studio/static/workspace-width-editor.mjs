// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
export function draggedWidth(startWidth, delta, side) {
 if (![startWidth,delta].every(Number.isFinite) || ![-1,1].includes(side)) throw new Error('Invalid width gesture');
 return Math.min(900, Math.max(300, Math.round(startWidth + side * delta * 20)));
}
export function installWidthEditor(host,{width,blocked,commit}) {
 const svg=host.querySelector('svg[data-geometry-view="physical"]');
 if(!svg)return ()=>{};
 const ns='http://www.w3.org/2000/svg';
 const make=(tag,attrs)=>{const e=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,v);return e;};
 const preview=make('rect',{y:153,height:22,fill:'none',stroke:'#fff0a8','stroke-dasharray':'3 2','pointer-events':'none',visibility:'hidden'});
 svg.append(preview);
 const message=document.createElement('p');message.className='muted';message.setAttribute('role','status');
 const help='Drag a core edge to resize symmetrically. Release to apply; Escape cancels. Arrow keys: 10 nm; Shift: 1 nm.';
 message.textContent=help;host.append(message);
 let gesture=null;const handles=[];
 const position=(e,inverse)=>{try{const x=new DOMPoint(e.clientX,e.clientY).matrixTransform(inverse).x;return Number.isFinite(x)?x:null;}catch{return null;}};
 const finish=apply=>{
  if(!gesture)return;const g=gesture;gesture=null;preview.setAttribute('visibility','hidden');
  if(g.handle.hasPointerCapture(g.id))g.handle.releasePointerCapture(g.id);
  message.textContent=apply?help:'Resize cancelled. Model unchanged.';
  if(apply&&!blocked()&&g.value!==width){commit(g.value);host.querySelector('[aria-label="'+g.handle.getAttribute('aria-label')+'"]')?.focus();}
 };
 const cancel=()=>finish(false);for(const event of ['blur','resize','pagehide'])window.addEventListener(event,cancel);
 for(const side of [-1,1]){
  const handle=make('rect',{x:300+side*width/20-4,y:150,width:8,height:28,fill:'#fff0a8',role:'slider',tabindex:0,'aria-label':side<0?'Resize core left edge':'Resize core right edge','aria-valuemin':300,'aria-valuemax':900,'aria-valuenow':width,'aria-valuetext':width+' nm','aria-orientation':'horizontal'});
  handle.style.cursor='ew-resize';handle.style.touchAction='none';svg.append(handle);handles.push(handle);
  handle.onclick=e=>e.stopPropagation();
  handle.onpointerdown=e=>{
   if(e.button!==0||gesture)return;e.preventDefault();e.stopPropagation();
   if(blocked()){message.textContent='Resolve invalid inputs before resizing.';return;}
   let inverse;try{inverse=svg.getScreenCTM()?.inverse();}catch{return;}if(!inverse)return;const start=position(e,inverse);if(start===null)return;
   handle.focus();gesture={id:e.pointerId,handle,start,inverse,value:width,side};handle.setPointerCapture(e.pointerId);
  };
  handle.onpointermove=e=>{
   if(!gesture||gesture.id!==e.pointerId)return;
   const x=position(e,gesture.inverse);if(x===null){cancel();return;}
   gesture.value=draggedWidth(width,x-gesture.start,side);
   preview.setAttribute('x',300-gesture.value/20);preview.setAttribute('width',gesture.value/10);preview.setAttribute('visibility','visible');
   message.textContent='Preview: '+gesture.value+' nm. Release to apply; Escape cancels.';
  };
  handle.onpointerup=e=>{if(gesture?.id!==e.pointerId)return;const x=position(e,gesture.inverse);if(x===null){cancel();return;}gesture.value=x===gesture.start?width:draggedWidth(width,x-gesture.start,side);finish(true);};
  handle.onpointercancel=e=>{if(gesture?.id===e.pointerId)cancel();};handle.onlostpointercapture=handle.onpointercancel;
  handle.onkeydown=e=>{
   if(e.key==='Escape'){e.preventDefault();e.stopPropagation();cancel();return;}
   if(gesture||e.ctrlKey||e.metaKey||e.altKey||!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;
   e.preventDefault();e.stopPropagation();if(blocked()){message.textContent='Resolve invalid inputs before resizing.';return;}
   const value=e.key==='Home'?300:e.key==='End'?900:Math.max(300,Math.min(900,width+(e.key==='ArrowRight'?1:-1)*side*(e.shiftKey?1:10)));
   if(value!==width){commit(value);host.querySelector('[aria-label="'+handle.getAttribute('aria-label')+'"]')?.focus();}
  };
 }
 return ()=>{cancel();for(const event of ['blur','resize','pagehide'])window.removeEventListener(event,cancel);message.remove();preview.remove();handles.forEach(handle=>handle.remove());};
}
