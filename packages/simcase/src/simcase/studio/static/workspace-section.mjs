// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
import {WINDOW_NM,shapeCorners,shapeBounds,designBounds} from './workspace-shapes.mjs';

// Equal x/y scale: 100 SVG units per micrometre (10 nm per unit), with screen y reversed.
export const toSvg=(x,y)=>[300+x/10,175-y/10];
export const toNm=(sx,sy)=>[(sx-300)*10,(175-sy)*10];
// Drawing-unit box of the window with its title and coordinate line, for Fit view.
export const WINDOW_VIEW=Object.freeze([145,38,310,272]);
export function shapesView(shapes){const b=designBounds(shapes),pad=20,[x0,y0]=toSvg(b.xmin,b.ymax),[x1,y1]=toSvg(b.xmax,b.ymin);const w=Math.max(x1-x0+2*pad,60),h=Math.max(y1-y0+2*pad,35);return [(x0+x1-w)/2,(y0+y1-h)/2,w,h];}
export const MATERIAL_FILL=Object.freeze({Silicon:'#2860bd','Silicon nitride':'#9fb7e8',Silica:'#4d6d7a',Air:'#15232c','Sapphire (ordinary)':'#c2a6e0','Lithium niobate (ordinary)':'#e7bc73','Indium phosphide':'#e08f8f','Gallium arsenide':'#d9d27a','Calcium fluoride':'#6f8f9a','Magnesium fluoride (ordinary)':'#5f7f8a','':'#a05a5a'});
const escape=text=>String(text).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]);
export function shapeSvgAttributes(shape){
 if(shape.type==='circle'){const [cx,cy]=toSvg(shape.cx,shape.cy);return {tag:'circle',attrs:{cx,cy,r:shape.r/10}};}
 return {tag:'polygon',attrs:{points:shapeCorners(shape).map(p=>toSvg(...p).join(',')).join(' ')}};
}
// Faint 100 nm grid with 500 nm major lines inside the window; display only.
export function gridSvg(){
 const lines=[];
 for(let x=WINDOW_NM.xmin+100;x<WINDOW_NM.xmax;x+=100){const [sx]=toSvg(x,0);lines.push(`<path d="M${sx} 55 V295" stroke-opacity="${x%500===0?.22:.09}"/>`);}
 for(let y=WINDOW_NM.ymin+100;y<WINDOW_NM.ymax;y+=100){const [,sy]=toSvg(0,y);lines.push(`<path d="M150 ${sy} H450" stroke-opacity="${y%500===0?.22:.09}"/>`);}
 return `<g data-grid="100 nm" stroke="#73859d" stroke-width=".5" vector-effect="non-scaling-stroke" pointer-events="none">${lines.join('')}</g>`;
}
// The PML of an open edge: a grey band outside the window, drawn narrower than its 1 µm (the
// drawing keeps the window in view), labelled with its true thickness.
export const PML_BAND=30;
function pmlBands(open,dx,dy,dw,dh){
 const B=PML_BAND,box={left:[dx-B,dy,B,dh],right:[dx+dw,dy,B,dh],bottom:[dx,dy+dh,dw,B],top:[dx,dy-B,dw,B]};
 return open.map(side=>{const [x,y,w,h]=box[side],cx=x+w/2,cy=y+h/2,vertical=side==='left'||side==='right';
  return `<g data-pml="${side}" role="img" aria-label="PML 1 µm outside the ${side} edge"><title>PML 1 µm outside the ${side} edge (band not to scale)</title><rect x="${x}" y="${y}" width="${w}" height="${h}" fill="#c3c9d1" stroke="#8a9bb2" stroke-width="1" stroke-dasharray="4 3" vector-effect="non-scaling-stroke"/><text x="${cx}" y="${cy+3}" font-size="9" fill="#354760" text-anchor="middle"${vertical?` transform="rotate(-90 ${cx} ${cy})"`:''}>PML 1 µm</text></g>`;}).join('');
}
/** The optical cross section. openEdges: the edges with an open boundary (a PML outside them). */
export function sectionSvg(shapes,{selected=0,selectedEdge=null,mode='Bodies',openEdges=[]}={}){
 const [dx,dy]=toSvg(WINDOW_NM.xmin,WINDOW_NM.ymax),dw=(WINDOW_NM.xmax-WINDOW_NM.xmin)/10,dh=(WINDOW_NM.ymax-WINDOW_NM.ymin)/10;
 const open=['left','right','bottom','top'].filter(side=>openEdges.includes(side));
 const pickable=mode==='Bodies';
 const body=shapes.map((s,i)=>{
  const {tag,attrs}=shapeSvgAttributes(s),on=i===selected;
  const label=`Select shape ${s.name} (${s.type}, ${s.material||'unassigned material'})`;
  const a=Object.entries(attrs).map(([k,v])=>`${k}="${v}"`).join(' ');
  return `<${tag} data-pick-shape="${i}" ${pickable?`role="button" tabindex="0" aria-label="${escape(label)}"`:'role="img" aria-label="'+escape(s.name)+'"'} ${a} fill="${MATERIAL_FILL[s.material]}" fill-opacity="${s.material==='Air'?1:.92}" stroke="${on&&pickable?'#d9480f':'#73859d'}" stroke-width="${on&&pickable?2.5:1}" ${s.material==='Air'?'stroke-dasharray="3 2"':''} vector-effect="non-scaling-stroke"/>`;
 }).join('');
 const paths={left:`M${dx} ${dy} v${dh}`,right:`M${dx+dw} ${dy} v${dh}`,top:`M${dx} ${dy} h${dw}`,bottom:`M${dx} ${dy+dh} h${dw}`};
 const hits={left:{x:dx-6,y:dy,w:12,h:dh},right:{x:dx+dw-6,y:dy,w:12,h:dh},top:{x:dx,y:dy-6,w:dw,h:12},bottom:{x:dx,y:dy+dh-6,w:dw,h:12}};
 const edges=mode==='Boundaries'?Object.entries(paths).map(([side,path])=>`<g data-pick-edge="optical-${side}" role="button" tabindex="0" aria-label="Select optical ${side} ${open.includes(side)?'open boundary (PML)':'PEC boundary'}"><rect x="${hits[side].x}" y="${hits[side].y}" width="${hits[side].w}" height="${hits[side].h}" fill="transparent"/><path d="${path}" fill="none" stroke="transparent" stroke-width="12"/><path d="${path}" fill="none" stroke="${selectedEdge==='optical-'+side?'#d9480f':'#2860bd'}" stroke-width="${selectedEdge==='optical-'+side?3.5:2}" vector-effect="non-scaling-stroke" pointer-events="none"/></g>`).join(''):'';
 const chosen=shapes[selected];let dims='';
 if(chosen&&pickable){
  const b=shapeBounds(chosen),[x0,y0]=toSvg(b.xmin,b.ymax),[x1,y1]=toSvg(b.xmax,b.ymin);
  dims=`<text x="${(x0+x1)/2}" y="${y0-6}">${escape(chosen.name)} · ${Math.round(b.xmax-b.xmin)} × ${Math.round(b.ymax-b.ymin)} nm extent</text>`;
 }
 return `<svg data-geometry-view="physical" viewBox="0 0 600 350" role="group" aria-label="Optical cross section in nanometres">
 <rect data-pick-body="Oxide" ${pickable?'role="button" tabindex="0" aria-label="Select silica background"':''} x="${dx}" y="${dy}" width="${dw}" height="${dh}" fill="#e4ebf3" stroke="#8a9bb2" stroke-width="1.5" vector-effect="non-scaling-stroke"/>
 ${gridSvg()}
 <path d="M150 175 H450 M300 55 V295" stroke="#8a9bb2" stroke-dasharray="3 4" stroke-width=".6" pointer-events="none"/>
 ${pmlBands(open,dx,dy,dw,dh)}${body}${edges}
 <g fill="#354760" font-size="10" text-anchor="middle" pointer-events="none">
 <text x="300" y="${open.includes('top')?14:47}">Optical cross section · equal x/y scale · later shapes win where they overlap</text>
 ${dims}
 <text x="300" y="${open.includes('bottom')?340:306}">x: −1500 … +1500 nm · y: −1200 … +1200 nm · silica background · ${open.length?`open boundary (PML 1 µm) on ${open.length} edge${open.length===1?'':'s'}`:'four fixed PEC edges'}</text>
 <text x="315" y="188">(0, 0)</text>
 </g></svg>`;
}
