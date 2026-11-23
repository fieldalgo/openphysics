// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

// optical-shapes-v9: the open boundary of the optical document. A perfectly matched layer (PML)
// of thickness t lies outside the 3 x 2.4 um window on each open edge: the solver domain grows by
// t there, the outer wall stays PEC, and a shape that lies along an open edge continues through
// the layer. Closed edges stay the PEC walls of optical-shapes-v8, and with every edge closed the
// document is the optical-shapes-v8 one, byte for byte.
import {WINDOW_NM,SHAPE_MATERIALS} from './workspace-shapes.mjs';

export const OPEN_BOUNDARY_ADAPTER='optical-shapes-v9';
export const EDGES=Object.freeze(['left','right','bottom','top']);
// 1 um only for now: on a fixed mesh a thicker layer changes no result, and it adds PML modes near
// the search target that push guided ones out of the candidates.
export const PML_THICKNESS_RANGE_NM=Object.freeze([1000,1000]);
export const PML_THICKNESS_DEFAULT_NM=1000;
// The fixed settings of a Studio open boundary (the engine's pml keys).
export const PML_FIXED=Object.freeze({pml_strength:3,pml_order:2,pml_minimum_physical_fraction:0.5,pml_search_mode_count:32});
// The second search of an open run (slice T2): 16 candidates near t_low = (t + n_SiO2) / 2 to two
// decimals, for modes close to the silica index that a search near t alone can miss.
export const ADDITIONAL_SEARCH_COUNT=16;
// Refractive indices at 1550 nm of the Studio materials (physmat, four decimals), for the default
// search target only: (n_max + n_SiO2) / 2 rounded to two decimals. A Python test checks them.
export const INDEX_1550=Object.freeze({Silicon:3.4777,'Silicon nitride':1.9963,Silica:1.4440,Air:1,'Sapphire (ordinary)':1.7462,'Lithium niobate (ordinary)':2.2111,'Indium phosphide':3.1649,'Gallium arsenide':3.3702,'Calcium fluoride':1.426,'Magnesium fluoride (ordinary)':1.3705});
export const SILICA_INDEX=INDEX_1550.Silica;
export const TARGET_FLOOR=1.45;
// Below this target t_low would round to the 1.45 floor: such a run searches near t only.
export const LOWER_SEARCH_FROM=1.466;

const isOpen=(ob,edge)=>Boolean(ob&&ob.edges&&ob.edges[edge]==='open');
/** True when some edge of the open boundary is open. */
export function hasOpenEdge(ob){return EDGES.some(e=>isOpen(ob,e));}
/** The largest index of the design's materials at 1550 nm. */
export function maxIndex(shapes){return Math.max(SILICA_INDEX,...shapes.map(s=>INDEX_1550[s.material]??0));}
/** The default "Search near n_eff": (n_max + n_SiO2) / 2 to two decimals (2.46 for a silicon core). */
export function defaultTarget(shapes){return Math.round((maxIndex(shapes)+SILICA_INDEX)/2*100)/100;}

/** The second search target: (t + 1.444) / 2 to two decimals, halves rounded up, in integer
 * thousandths so that every platform and the server's check agree (2.46 -> 1.95, 2.20 -> 1.82,
 * 1.60 -> 1.52, 1.72 -> 1.58). null below LOWER_SEARCH_FROM (t_low would be the 1.45 floor). */
export function lowerTarget(t){
 const m=Math.round(t*1000);
 if(m<Math.round(LOWER_SEARCH_FROM*1000))return null;
 return Math.floor((m+Math.round(SILICA_INDEX*1000)+10)/20)/100;
}

/** The open boundary checked: {edges, thickness (nm), target, lowTarget (lowerTarget, or null)},
 * defaults filled in. With every edge closed only the edge words are checked: thickness and
 * target are not read then. */
export function checkOpenBoundary(ob,shapes){
 if(ob==null||typeof ob!=='object')throw new Error('Invalid open boundary.');
 const edges={};
 for(const e of EDGES){const v=ob.edges?.[e]??'closed';if(v!=='open'&&v!=='closed')throw new Error(`The ${e} edge must be open or closed.`);edges[e]=v;}
 if(!EDGES.some(e=>edges[e]==='open'))return {edges};
 const t=ob.thickness??PML_THICKNESS_DEFAULT_NM,[lo,hi]=PML_THICKNESS_RANGE_NM;
 if(!Number.isInteger(t)||t<lo||t>hi)throw new Error(lo===hi?`PML thickness must be ${lo} nm (${lo/1000} µm).`:`PML thickness must be a whole number of nm from ${lo} to ${hi} (${lo/1000}–${hi/1000} µm).`);
 const nmax=maxIndex(shapes),target=ob.target??defaultTarget(shapes);
 if(typeof target!=='number'||!Number.isFinite(target)||target<=TARGET_FLOOR||target>=nmax)throw new Error(`Search near n_eff must lie between ${TARGET_FLOOR} and ${nmax}.`);
 return {edges,thickness:t,target,lowTarget:lowerTarget(target)};
}

const tidy=value=>Math.round(value*1e6)/1e6;
// The outward normal of each edge, and where the edge lies.
const SIDE={left:{axis:0,at:WINDOW_NM.xmin,dir:-1},right:{axis:0,at:WINDOW_NM.xmax,dir:1},bottom:{axis:1,at:WINDOW_NM.ymin,dir:-1},top:{axis:1,at:WINDOW_NM.ymax,dir:1}};
// A vertex within 1e-6 nm of an open window edge (the rounding of shape corners) lies on it.
const NEAR=1e-6;
const onEdge=(p,e)=>Math.abs(p[SIDE[e].axis]-SIDE[e].at)<=NEAR;
function sideOf(p,q,edges){
 for(const e of EDGES)if(edges[e]==='open'&&onEdge(p,e)&&onEdge(q,e))return e;
 return null;
}
// a vertex on open edges moved onto them exactly, so the layer meets the shape with no gap
function snap(p,edges){const q=[...p];for(const e of EDGES)if(edges[e]==='open'&&onEdge(p,e))q[SIDE[e].axis]=SIDE[e].at;return q;}
const push=(p,e,t)=>{const {axis,at,dir}=SIDE[e],q=[...p];q[axis]=tidy(at+dir*t);return q;};
const collinear=(a,b,c)=>(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])===0;
// on a window edge or on the outer line of its layer: the vertices the extrusion makes redundant
const onLine=(p,edges,t)=>EDGES.some(e=>edges[e]==='open'&&(p[SIDE[e].axis]===SIDE[e].at||p[SIDE[e].axis]===tidy(SIDE[e].at+SIDE[e].dir*t)));
/** A polygon (solver points in nm) with each edge along an open window edge pushed out by t
 * through the layer, the corner square filled where two pushed edges meet, and collinear
 * vertices removed. Edges inside the window are untouched. */
export function extendPolygon(points,edges,t){
 const n=points.length,side=points.map((p,i)=>sideOf(p,points[(i+1)%n],edges));
 if(!side.some(Boolean))return points;
 const out=[];
 for(let i=0;i<n;i++){
  const p=snap(points[i],edges),before=side[(i+n-1)%n],after=side[i];
  if(before&&after&&before!==after)out.push(push(p,before,t),push(push(p,before,t),after,t),push(p,after,t));
  else if(before&&after)out.push(push(p,before,t));
  else if(before)out.push(push(p,before,t),p);
  else if(after)out.push(p,push(p,after,t));
  else out.push(p);
 }
 // drop repeated vertices, and collinear ones on a window edge or a layer's outer line (the
 // extrusion's), until none is left; the design's own vertices inside the window stay
 let pts=out.filter((p,i)=>{const q=out[(i+1)%out.length];return p[0]!==q[0]||p[1]!==q[1];});
 for(let changed=true;changed&&pts.length>3;){
  changed=false;
  for(let i=0;i<pts.length;i++){const a=pts[(i+pts.length-1)%pts.length],b=pts[i],c=pts[(i+1)%pts.length];if(onLine(b,edges,t)&&collinear(a,b,c)){pts.splice(i,1);changed=true;break;}}
 }
 return pts;
}

/** The optical-shapes-v9 document: the optical-shapes-v8 document `doc` with the open boundary
 * `ob` (checked) applied, and from t = 1.466 the second search near lowerTarget(t)
 * (pml.pml_additional_searches). With every edge closed it returns `doc` itself. */
export function applyOpenBoundary(doc,ob){
 if(!hasOpenEdge(ob))return doc;
 const t=ob.thickness,d=doc.geometry.domain,open=EDGES.filter(e=>ob.edges[e]==='open');
 const domain={xmin:isOpen(ob,'left')?tidy(d.xmin-t):d.xmin,xmax:isOpen(ob,'right')?tidy(d.xmax+t):d.xmax,ymin:isOpen(ob,'bottom')?tidy(d.ymin-t):d.ymin,ymax:isOpen(ob,'top')?tidy(d.ymax+t):d.ymax};
 const shapes=doc.geometry.shapes.map(s=>s.type==='polygon'?{...s,points:extendPolygon(s.points,ob.edges,t)}:s);
 const em=doc.physics.em1,low=lowerTarget(ob.target),pml={pml_thickness:Object.fromEntries(open.map(e=>[e,t+' nm'])),...PML_FIXED,
  ...(low===null?{}:{pml_additional_searches:[{target_effective_index:low,pml_search_mode_count:ADDITIONAL_SEARCH_COUNT}]})};
 const physics={em1:{...em,target_effective_index:ob.target,pml}};
 return {...doc,geometry:{...doc.geometry,domain,shapes},physics};
}
