// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

// The guided / leaky note of an open-boundary mode (slice S2 of the design draft measured on main
// 2318e5f). Beyond an open window edge the structure does not change along the edge's normal: the
// shapes along that edge continue through the PML (applyOpenBoundary), so the PML holds the edge's
// material profile, semi-infinite. A mode can carry power away through the edge exactly when its
// Re n_eff lies below the highest transverse cutoff index of that profile. Studio does not solve
// the profile; it reads two bounds off the shapes, at the run's wavelength (INDEX_TABLE):
//  n_hi(e): the largest index on the edge (the extruded profile, silica where no shape covers it,
//           and any shape that touches the edge without continuing through the layer: a circle's
//           chord, a polygon's vertex). The cutoff is at most n_hi(e).
//  n_lo(e): the largest index of a material that fills a half-space beyond e (one material along
//           the whole edge) or a quarter-space (the PML corner at an end of e whose other edge is
//           open, filled by a polygon along both edges, else silica). The cutoff is at least n_lo(e).
// With x = Re n_eff and δ = CHANNEL_DELTA (the mesh error of Re n_eff at the coarsest core mesh,
// 1.3e-2 measured, times 1.5), over the open edges:
//  leaky:  some n_lo(e) > x + δ (the regions giving it, highest index first): a channel exists;
//  guided: every n_hi(e) < x − δ: no channel exists (the materials are lossless, so the exact
//          Im n_eff is 0 and the loss shown is numerical);
//  layer:  neither, and a material above x + δ reaches an open edge only as a layer (its own modes
//          decide): no claim;
//  near:   otherwise, x within δ of an edge index: no claim.
// |x − n| ≤ δ is always on the no-claim side. A closed run gets nothing. The decision uses only data
// the run stores (Re n_eff, the input shapes, the open edges, the wavelength), no field: a run whose
// fields were made compact or dropped is classified the same. A guard compares it with the loss:
// "guided" is shown only when Im n_eff is within the engine's gain bound b (pml_modes.md), and a
// leaky mode whose Im n_eff is within b says the solve resolves no leakage loss.
import {WINDOW_NM,shapeCorners} from './workspace-shapes.mjs';
import {touchedEdges} from './workspace-modes.mjs';
import {indexAt,EDGES} from './workspace-open-boundary.mjs';
import {isOpenRun,modeCandidates} from './workspace-open-run.mjs';

export const CHANNEL_DELTA=0.02;
// K of the engine's gain bound (simcase.physics_pml_modes.GAIN_BOUND_FACTOR)
export const GAIN_BOUND_FACTOR=1e-2;
export const BACKGROUND_NAME='the silica background';
const BACKGROUND='Silica';
const NEAR=1e-6;
// each edge: the axis along it, where it lies, and its two corners (the edge at each end)
const SIDE={left:{along:1,axis:0,at:WINDOW_NM.xmin,ends:['bottom','top']},right:{along:1,axis:0,at:WINDOW_NM.xmax,ends:['bottom','top']},
 bottom:{along:0,axis:1,at:WINDOW_NM.ymin,ends:['left','right']},top:{along:0,axis:1,at:WINDOW_NM.ymax,ends:['left','right']}};
const LIMIT=[[WINDOW_NM.xmin,WINDOW_NM.xmax],[WINDOW_NM.ymin,WINDOW_NM.ymax]];
const onEdge=(p,e)=>Math.abs(p[SIDE[e].axis]-SIDE[e].at)<=NEAR;
const corner=(e,f)=>{const p=[0,0];p[SIDE[e].axis]=SIDE[e].at;p[SIDE[f].axis]=SIDE[f].at;return p;};
const same=(p,q)=>Math.abs(p[0]-q[0])<=NEAR&&Math.abs(p[1]-q[1])<=NEAR;
/** The gain bound of a mode: max(1e-10, K f_pml) max(1, |Re n_eff|); a nonfinite f_pml gives the floor. */
export function gainBound(re,pmlFraction){
 const scale=Number.isFinite(pmlFraction)?Math.max(1e-10,GAIN_BOUND_FACTOR*pmlFraction):1e-10;
 return scale*Math.max(1,Math.abs(re));
}
// the segments of a polygon (or rect) along edge e, as intervals of the coordinate along it
function intervalsOn(points,e){
 const out=[],a=SIDE[e].along;
 points.forEach((p,i)=>{const q=points[(i+1)%points.length];if(onEdge(p,e)&&onEdge(q,e)){const lo=Math.max(Math.min(p[a],q[a]),LIMIT[a][0]),hi=Math.min(Math.max(p[a],q[a]),LIMIT[a][1]);if(hi-lo>NEAR)out.push([lo,hi]);}});
 return out;
}
// a polygon with a vertex at the corner of e and f whose two segments there lie along e and f: it
// fills the PML corner square (extendPolygon) when both edges are open
function fillsCorner(points,e,f){
 const c=corner(e,f),n=points.length;
 return points.some((p,i)=>{if(!same(p,c))return false;const b=points[(i+n-1)%n],d=points[(i+1)%n];
  return (onEdge(b,e)&&onEdge(d,f))||(onEdge(b,f)&&onEdge(d,e));});
}
const region=(shapes,k,nm)=>k<0?{key:'background',order:shapes.length,name:BACKGROUND_NAME,n:indexAt(BACKGROUND,nm)}:{key:'shape'+k,order:k,name:shapes[k].name,n:indexAt(shapes[k].material,nm)};
const highest=list=>{const seen=new Map();for(const r of list)if(!seen.has(r.key))seen.set(r.key,r);return [...seen.values()].sort((a,b)=>b.n-a.n||a.order-b.order);};
const top=list=>list.length?Math.max(...list.map(r=>r.n)):-Infinity;
/** Per open edge (in the order left, right, bottom, top): {nLo, nHi, lo, hi}, the bounds of §1.2
 * and the regions ({key, name, n}, highest index first) giving them; nLo −Infinity without a half-
 * or quarter-space. null when a material index is not in the table (another wavelength). */
export function edgeProfiles(shapes,openEdges,wavelengthNm){
 const open=new Set(openEdges),polys=shapes.map(s=>s.type==='circle'?null:shapeCorners(s)),out={};
 for(const e of EDGES.filter(x=>open.has(x))){
  const a=SIDE[e].along,[from,to]=LIMIT[a],cover=polys.map(p=>p?intervalsOn(p,e):[]);
  // the profile beyond e: the later shape wins where shapes overlap, silica elsewhere
  const cuts=[...new Set([from,to,...cover.flat(2)])].sort((x,y)=>x-y),pieces=[];
  for(let i=0;i+1<cuts.length;i++){const lo=cuts[i],hi=cuts[i+1];if(hi-lo<=NEAR)continue;const mid=(lo+hi)/2;
   let owner=-1;for(let k=shapes.length-1;k>=0;k--)if(cover[k].some(([u,v])=>u<=mid&&mid<=v)){owner=k;break;}
   const last=pieces.at(-1);if(last&&last.owner===owner)last.hi=hi;else pieces.push({lo,hi,owner});}
  const hi=pieces.map(p=>region(shapes,p.owner,wavelengthNm));
  // a shape touching e without continuing through the layer: a circle, a polygon at a vertex only
  shapes.forEach((s,k)=>{if(touchedEdges(s).includes(e)&&!cover[k].length)hi.push(region(shapes,k,wavelengthNm));});
  const lo=[];
  if(pieces.length===1)lo.push(region(shapes,pieces[0].owner,wavelengthNm));
  for(const f of SIDE[e].ends)if(open.has(f)){let owner=-1;for(let k=shapes.length-1;k>=0;k--)if(polys[k]&&fillsCorner(polys[k],e,f)){owner=k;break;}lo.push(region(shapes,owner,wavelengthNm));}
  if([...hi,...lo].some(r=>typeof r.n!=='number'))return null;
  out[e]={nLo:top(lo),nHi:top(hi),lo:highest(lo),hi:highest(hi)};
 }
 return out;
}
// differences to 1e-9, so that x = n ± δ is exactly on the no-claim side
const gap=(a,b)=>Math.round((a-b)*1e9)/1e9;
/** The category of Re n_eff x against the bounds of edgeProfiles: {kind ('leaky', 'guided',
 * 'layer' or 'near'), regions, n (the first region's index), sides (layer: the open edges the
 * layer reaches)}. */
export function classifyIndex(x,profiles,delta=CHANNEL_DELTA){
 const edges=Object.keys(profiles),all=edges.flatMap(e=>profiles[e].hi);
 const leak=highest(edges.flatMap(e=>profiles[e].lo.filter(r=>gap(r.n,x)>delta)));
 const done=(kind,regions,sides=[])=>({kind,regions:regions.map(({name,n})=>({name,n})),n:regions[0]?.n??null,sides});
 if(leak.length)return done('leaky',leak);
 if(edges.every(e=>gap(x,profiles[e].nHi)>delta))return done('guided',highest(all).slice(0,1));
 const layer=highest(all.filter(r=>gap(r.n,x)>delta));
 if(layer.length)return done('layer',layer.slice(0,1),edges.filter(e=>profiles[e].hi.some(r=>r.key===layer[0].key)));
 return done('near',highest(all).slice(0,1));
}
const WAVELENGTH=/^(\d+(?:\.\d+)?) nm$/;
/** Per mode of an open run: {mode, kind, regions, n, sides, x, im, bound, resolved (Im n_eff > b)};
 * [] for a closed run, or a run whose wavelength or materials are not in the index table. */
export function modeChannel(run){
 if(!isOpenRun(run))return [];
 // the page's run keeps effective_index (Re) and effective_index_im; a file writes {re, im}
 const e=run.effective_index,re=Array.isArray(e)?e:e?.re,im=(Array.isArray(e)?run.effective_index_im:e?.im)??[];
 const m=WAVELENGTH.exec(String(run.settings.vacuum_wavelength??'')),nm=m?Number(m[1]):run.input?.model?.wavelength,shapes=run.input?.model?.shapes;
 if(typeof nm!=='number'||!Array.isArray(shapes)||!Array.isArray(re))return [];
 const profiles=edgeProfiles(shapes,run.settings.pml?.open_edges??[],nm);
 if(!profiles||!Object.keys(profiles).length)return [];
 const record=run.open_boundary,picks=record&&Array.isArray(record.candidates)?modeCandidates(record,re,im):[];
 return re.map((x,mode)=>{
  const c=picks[mode],f=Number.isFinite(c?.pml_l2_fraction)?c.pml_l2_fraction:Number.isFinite(c?.physical_l2_fraction)?1-c.physical_l2_fraction:Number.NaN;
  const bound=gainBound(x,f),i=im[mode];
  return {mode,...classifyIndex(x,profiles),x,im:i,bound,resolved:Number.isFinite(i)&&i>bound};
 });
}
const fix=v=>v.toFixed(3);
const SIDE_ORDER=['left','right','bottom','top'];
const sideWords=list=>{const s=SIDE_ORDER.filter(e=>list.includes(e));return s.length<3?s.join(' and '):s.slice(0,-1).join(', ')+' and '+s.at(-1);};
const names=list=>list.length<3?list.join(' and '):list.slice(0,-1).join(', ')+' and '+list.at(-1);
/** The words of §4.1. With `follows` the text continues a region note: "It is a leaky mode", "It is
 * guided", "Re n_eff …". A leaky mode not resolved (Im n_eff within b) keeps its first sentence and
 * says the solve resolves no leakage loss. */
export function channelText(mode,c,{resolved=true,follows=false}={}){
 const k=mode+1,x=fix(c.x),r=c.regions,first=r[0];
 if(c.kind==='leaky'){
  const many=r.length>1,head=(follows?'It':`Mode ${k}`)+' is a leaky mode: ';
  return head+`Re n_eff ${x} is below the index of ${names(r.map(q=>`${q.name} (${fix(q.n)})`))}, which ${many?'reach':'reaches'} the open window edge, so light can leak into ${names(r.map(q=>q.name))}.`
   +(resolved?' The loss shown is that leakage; it is part of this structure, not a fault of the solve.':' This solve resolves no leakage loss.');
 }
 if(c.kind==='guided')return (follows?'It':`Mode ${k}`)+` is guided: Re n_eff ${x} is above the index of every material at the open window edges (the highest is ${first.name}, ${fix(first.n)}), so it cannot leak. The loss shown is numerical (mesh and PML), not leakage.`;
 const head=follows?'':`Mode ${k}: `;
 if(c.kind==='near')return head+`Re n_eff ${x} is within ${CHANNEL_DELTA} of the index of ${first.name} (${fix(first.n)}) at the open window edge, closer than this solve resolves; Studio does not say whether it is guided or leaky.`;
 const many=c.sides.length>1;
 return head+`Re n_eff ${x} is below the index of ${first.name} (${fix(first.n)}), which reaches the open ${sideWords(c.sides)} ${many?'edges':'edge'} only as a layer. Whether light can leak into it depends on that layer's own modes, which Studio does not compute; Studio does not say whether this mode is guided or leaky.`;
}
/** The guided / leaky notes of a run: [{mode, kind, text}] for each mode with one; a guided mode
 * whose Im n_eff exceeds the gain bound gets none (the category and the loss disagree). */
export function channelNotes(run){
 return modeChannel(run).flatMap(c=>c.kind==='guided'&&c.resolved?[]:[{mode:c.mode,kind:c.kind,text:channelText(c.mode,c,{resolved:c.resolved})}]);
}
/** A region note (core or edge) with the channel text of the same mode after it. */
export const combinedNote=(regionText,mode,c)=>`${regionText} ${channelText(mode,c,{resolved:c.resolved,follows:true})}`;
/** Slice S3: the notes of the modes table. `edge` and `core` are the table's maps (mode → text) of
 * the region notes; a mode with one of them gets the channel text after it, in the same note (the
 * maps are updated in place). The others' channel texts are returned: a Map mode → {kind, text}, a
 * note row of their own. A closed run leaves both maps as they are and returns an empty Map. */
export function placeChannelNotes(run,edge,core){
 const alone=new Map();
 for(const c of modeChannel(run)){
  if(c.kind==='guided'&&c.resolved)continue;
  const map=edge.has(c.mode)?edge:core.has(c.mode)?core:null;
  if(map)map.set(c.mode,combinedNote(map.get(c.mode),c.mode,c));
  else alone.set(c.mode,{kind:c.kind,text:channelText(c.mode,c,{resolved:c.resolved})});
 }
 return alone;
}
