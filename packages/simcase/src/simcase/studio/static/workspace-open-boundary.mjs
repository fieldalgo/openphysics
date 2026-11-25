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
// Slice S1 (decision D1 of the guided / leaky notes): the real index of the same ten materials at
// 1400 to 1700 nm every 10 nm (physmat, five decimals), for the material indices at a run's
// wavelength (workspace-mode-channel.mjs). Linear interpolation is within 1e-4 of physmat at every
// nanometre of the range (tests/simcase/test_studio_index_table.py; 7.5e-6 at most, measured). It
// is a frozen copy: Studio reads no material data when it shows a run. INDEX_1550 is unchanged.
export const INDEX_TABLE=Object.freeze({from_nm:1400,to_nm:1700,step_nm:10,index:Object.freeze({
 Silicon:[3.49231,3.49117,3.49007,3.48898,3.48793,3.48689,3.48588,3.4849,3.48393,3.48299,3.48206,3.48116,3.48027,3.4794,3.47856,3.47772,3.47691,3.47611,3.47533,3.47456,3.47381,3.47307,3.47235,3.47164,3.47095,3.47027,3.4696,3.46894,3.4683,3.46767,3.46705],
 'Silicon nitride':[2.00051,2.00022,1.99994,1.99965,1.99937,1.99909,1.9988,1.99852,1.99824,1.99796,1.99768,1.9974,1.99712,1.99684,1.99656,1.99628,1.996,1.99572,1.99544,1.99516,1.99488,1.9946,1.99433,1.99405,1.99377,1.99349,1.99321,1.99293,1.99265,1.99237,1.99208],
 Silica:[1.44578,1.44566,1.44555,1.44543,1.44532,1.4452,1.44509,1.44497,1.44485,1.44474,1.44462,1.4445,1.44438,1.44426,1.44414,1.44402,1.4439,1.44378,1.44366,1.44354,1.44342,1.4433,1.44317,1.44305,1.44293,1.4428,1.44268,1.44255,1.44243,1.4423,1.44217],
 Air:[1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
 'Sapphire (ordinary)':[1.74875,1.74858,1.74841,1.74824,1.74807,1.7479,1.74773,1.74756,1.74739,1.74722,1.74705,1.74687,1.7467,1.74653,1.74636,1.74618,1.74601,1.74583,1.74566,1.74548,1.7453,1.74513,1.74495,1.74477,1.74459,1.74441,1.74423,1.74405,1.74387,1.74369,1.74351],
 'Lithium niobate (ordinary)':[2.21644,2.21607,2.2157,2.21533,2.21496,2.2146,2.21424,2.21389,2.21353,2.21318,2.21283,2.21248,2.21214,2.21179,2.21145,2.21111,2.21077,2.21044,2.2101,2.20977,2.20944,2.2091,2.20877,2.20845,2.20812,2.20779,2.20747,2.20714,2.20682,2.2065,2.20618],
 'Indium phosphide':[3.18519,3.18358,3.18201,3.18048,3.179,3.17755,3.17614,3.17476,3.17342,3.17212,3.17085,3.1696,3.16839,3.16721,3.16606,3.16493,3.16383,3.16275,3.1617,3.16068,3.15967,3.15869,3.15773,3.1568,3.15588,3.15498,3.1541,3.15324,3.1524,3.15157,3.15077],
 'Gallium arsenide':[3.38895,3.38748,3.38605,3.38465,3.38328,3.38195,3.38065,3.37938,3.37813,3.37692,3.37573,3.37457,3.37343,3.37232,3.37123,3.37017,3.36913,3.36811,3.36711,3.36613,3.36517,3.36424,3.36332,3.36242,3.36153,3.36067,3.35982,3.35899,3.35817,3.35737,3.35659],
 'Calcium fluoride':[1.42673,1.42668,1.42663,1.42659,1.42654,1.42649,1.42645,1.4264,1.42635,1.4263,1.42626,1.42621,1.42616,1.42612,1.42607,1.42602,1.42598,1.42593,1.42588,1.42584,1.42579,1.42574,1.4257,1.42565,1.4256,1.42556,1.42551,1.42546,1.42542,1.42537,1.42532],
 'Magnesium fluoride (ordinary)':[1.37134,1.37128,1.37123,1.37118,1.37112,1.37107,1.37101,1.37096,1.3709,1.37085,1.37079,1.37074,1.37068,1.37063,1.37057,1.37052,1.37046,1.37041,1.37035,1.3703,1.37024,1.37018,1.37013,1.37007,1.37001,1.36996,1.3699,1.36984,1.36979,1.36973,1.36967]
})});
/** The real index of a Studio material at a vacuum wavelength in nm, linearly interpolated in
 * INDEX_TABLE; null for another material or a wavelength outside 1400–1700 nm. */
export function indexAt(material,wavelengthNm){
 const values=Object.hasOwn(INDEX_TABLE.index,material)?INDEX_TABLE.index[material]:null,{from_nm:a,to_nm:b,step_nm:h}=INDEX_TABLE;
 if(!values||typeof wavelengthNm!=='number'||!(wavelengthNm>=a&&wavelengthNm<=b))return null;
 const k=Math.min(Math.floor((wavelengthNm-a)/h),values.length-2),t=(wavelengthNm-a-k*h)/h;
 return t===0?values[k]:t===1?values[k+1]:values[k]+t*(values[k+1]-values[k]);
}
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
