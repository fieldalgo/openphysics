// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
import {opticalGeometry} from './workspace-optical.mjs';

// Equal x/y scale: 100 SVG units per micrometre, with screen y reversed.
export function opticalSection(widthNm){
 const {domain,core}=opticalGeometry(widthNm);
 const rect=(x,y,w,h)=>({x:300+100*x,y:175-100*(y+h),width:100*w,height:100*h});
 return {domain:rect(domain.xmin,domain.ymin,domain.xmax-domain.xmin,domain.ymax-domain.ymin),core:rect(core.x,core.y,core.w,core.h)};
}
export function sectionSvg(widthNm,selectedBody,selectedEdge,mode){
 const {domain:d,core:c}=opticalSection(widthNm);
 const body=(name,r,fill)=>`<rect data-pick-body="${name}" role="button" tabindex="0" aria-label="Select ${name} body" x="${r.x}" y="${r.y}" width="${r.width}" height="${r.height}" fill="${fill}" stroke="${selectedBody===name?'#fff0a8':'#7a939f'}" stroke-width="1.5" vector-effect="non-scaling-stroke"/>`;
 const paths={left:`M${d.x} ${d.y} v${d.height}`,right:`M${d.x+d.width} ${d.y} v${d.height}`,top:`M${d.x} ${d.y} h${d.width}`,bottom:`M${d.x} ${d.y+d.height} h${d.width}`};
 const hits={left:{x:d.x-6,y:d.y,w:12,h:d.height},right:{x:d.x+d.width-6,y:d.y,w:12,h:d.height},top:{x:d.x,y:d.y-6,w:d.width,h:12},bottom:{x:d.x,y:d.y+d.height-6,w:d.width,h:12}};
 const edges=mode==='Boundaries'?Object.entries(paths).map(([side,path])=>`<g data-pick-edge="optical-${side}" role="button" tabindex="0" aria-label="Select optical ${side} PEC boundary"><rect x="${hits[side].x}" y="${hits[side].y}" width="${hits[side].w}" height="${hits[side].h}" fill="transparent"/><path d="${path}" fill="none" stroke="transparent" stroke-width="12"/><path d="${path}" fill="none" stroke="${selectedEdge==='optical-'+side?'#fff0a8':'#80d7c0'}" stroke-width="2" vector-effect="non-scaling-stroke" pointer-events="none"/></g>`).join(''):'';
 return `<svg data-geometry-view="physical" viewBox="0 0 600 350" role="group" aria-label="Optical cross section in nanometres">
 ${body('Oxide',d,'#273f4a')}
 <path d="M150 175 H450 M300 55 V295" stroke="#7a939f" stroke-dasharray="3 4" stroke-width=".6" pointer-events="none"/>
 ${body('Core',c,'#80d7c0')}${edges}
 <g fill="#e2e9ed" font-size="10" text-anchor="middle" pointer-events="none">
 <text x="300" y="35">Optical cross section · equal x/y scale</text>
 <text x="300" y="${c.y-10}">Core · ${widthNm} × 220 nm</text>
 <text x="300" y="315">x: −1500 … +1500 nm · y: −1200 … +1200 nm</text>
 <text x="300" y="335">Silica background · four fixed PEC edges · no heater</text>
 <text x="${c.x+c.width+34}" y="${c.y+15}">220 nm</text>
 <text x="${c.x+c.width/2}" y="202">${widthNm} nm</text>
 <text x="315" y="188">(0, 0)</text>
 </g>
 <g stroke="#e2e9ed" fill="none" stroke-width=".7" pointer-events="none">
 <path d="M${c.x} 182 V195 M${c.x+c.width} 182 V195 M${c.x} 191 H${c.x+c.width}"/>
 <path d="M${c.x+c.width+6} ${c.y} h10 M${c.x+c.width+6} ${c.y+c.height} h10 M${c.x+c.width+11} ${c.y} v${c.height}"/>
 </g></svg>`;
}
