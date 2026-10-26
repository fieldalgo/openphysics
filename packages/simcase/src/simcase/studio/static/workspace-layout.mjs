// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

export const LAYOUT_KEY='openphysics.studio.layout.v1';
export const DEFAULT_LAYOUT=Object.freeze({tree:220,inspector:280});
export const LIMITS=Object.freeze({tree:Object.freeze([160,300]),inspector:Object.freeze([220,380])});
export function clampWidth(side,value){
 if(!Object.hasOwn(LIMITS,side)||!Number.isFinite(value))throw new Error('Invalid panel width.');
 const [min,max]=LIMITS[side];return Math.round(Math.max(min,Math.min(max,value)));
}
export function readLayout(text){
 try{const d=JSON.parse(text);if(d?.version!==1)throw Error();return {tree:clampWidth('tree',d.tree),inspector:clampWidth('inspector',d.inspector)};}
 catch{return {...DEFAULT_LAYOUT};}
}
export function keyWidth(side,value,key,shift=false){
 const [min,max]=LIMITS[side],direction=side==='tree'?1:-1,step=shift?40:10;
 if(key==='Home')return min;if(key==='End')return max;
 if(key==='ArrowLeft')return clampWidth(side,value-step*direction);
 if(key==='ArrowRight')return clampWidth(side,value+step*direction);
 return null;
}
export function installLayout(root,reset,status){
 let layout={...DEFAULT_LAYOUT},drag=null;
 try{layout=readLayout(localStorage.getItem(LAYOUT_KEY));}catch{/* Storage may be disabled. */}
 const handles={};
 function paint(){
  for(const side of Object.keys(LIMITS)){
   root.style.setProperty('--'+side+'-width',layout[side]+'px');
   handles[side]?.setAttribute('aria-valuenow',String(layout[side]));
   handles[side]?.setAttribute('aria-valuetext',layout[side]+' pixels');
  }
 }
 function save(){try{localStorage.setItem(LAYOUT_KEY,JSON.stringify({version:1,...layout}));status.textContent='Panel layout saved in this browser.';}catch{status.textContent='Panel layout changed for this tab; browser storage is unavailable.';}}
 function cancel(){if(!drag)return;layout[drag.side]=drag.width;const current=drag;drag=null;root.classList.remove('resizing');paint();if(current.handle.hasPointerCapture(current.id))current.handle.releasePointerCapture(current.id);status.textContent='Panel resize cancelled.';}
 for(const side of Object.keys(LIMITS)){
  const h=document.createElement('div');handles[side]=h;h.className='panel-divider divider-'+side;h.id='resize-'+side;h.tabIndex=0;
  h.setAttribute('role','separator');h.setAttribute('aria-orientation','vertical');h.setAttribute('aria-label',side==='tree'?'Resize model tree':'Resize properties panel');h.setAttribute('aria-controls',side==='tree'?'tree':'inspector');
  h.setAttribute('aria-valuemin',String(LIMITS[side][0]));h.setAttribute('aria-valuemax',String(LIMITS[side][1]));h.title='Drag or use Left/Right. Shift: larger step. Home/End: limits. Escape: cancel drag.';
  h.onpointerdown=e=>{if(e.button!==0)return;e.preventDefault();h.focus();drag={side,x:e.clientX,width:layout[side],id:e.pointerId,handle:h};h.setPointerCapture(e.pointerId);root.classList.add('resizing');};
  h.onpointermove=e=>{if(!drag||drag.id!==e.pointerId)return;layout[side]=clampWidth(side,drag.width+(e.clientX-drag.x)*(side==='tree'?1:-1));paint();};
  h.onpointerup=e=>{if(!drag||drag.id!==e.pointerId)return;drag=null;root.classList.remove('resizing');h.releasePointerCapture(e.pointerId);save();};
  h.onpointercancel=cancel;h.onlostpointercapture=cancel;
  h.onkeydown=e=>{if(e.key==='Escape'){cancel();return;}if(drag)return;const next=keyWidth(side,layout[side],e.key,e.shiftKey);if(next===null)return;e.preventDefault();layout[side]=next;paint();save();};
  root.append(h);
 }
 reset.onclick=()=>{cancel();layout={...DEFAULT_LAYOUT};paint();save();status.textContent+=' Default widths restored.';};
 paint();
}
