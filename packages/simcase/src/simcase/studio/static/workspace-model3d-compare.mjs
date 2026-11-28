// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Studio 3D Compare (C3): two kept runs of the one 3D model, A and B, side by side. Everything is read
// from the two run records (values, document, surface map); nothing is sent to the server and the pair
// is view state. Pure helpers here; workspace-model3d-view.mjs draws the page.
import {fieldWords,shownText,valuesRows} from './workspace-model3d.mjs';

export const NEEDS_TWO='Compare needs two runs of this 3D model.';
export const SAME_INPUTS='Same inputs.';
export const inputsText=list=>list.length?list.join('\n'):SAME_INPUTS;

const sig=(v,n=6)=>Number(Number(v).toPrecision(n));
const MINUS='−';
const count=n=>Number(n).toLocaleString('en-US');
/** B − A, computed directly. */
export const delta=(b,a)=>b-a;
/** A signed difference as shown: "+4.5 K", "−0.25 W", "0 K". */
function signed(d,unit=''){
 const tail=unit?` ${unit}`:'';
 if(d===0)return `0${tail}`;
 return `${d>0?'+':MINUS}${unit?sig(Math.abs(d)):count(Math.abs(d))}${tail}`;
}

/** The pickers' default: the two newest runs [A, B] (indices), or null with fewer than two. */
export const defaultPair=n=>n>=2?[n-2,n-1]:null;

/**
 * C3-1: the values table of two run records, [label, A, B, B − A] rows: each run's own values rows
 * (as its Results page writes them), then its mesh. Δ is B − A of the value behind the row; empty
 * where the row is not a number or a run lacks it ("—").
 */
export function compareRows(a,b,unit){
 const va=a.values,vb=b.values;
 const text=r=>Object.fromEntries(valuesRows(r.values,unit));
 const ta=text(a),tb=text(b);
 const number=(v,label)=>{
  if(label==='Temperature, max (whole model)')return [v.temperature_max.value,'K'];
  if(label==='Temperature, min (whole model)')return [v.temperature_min.value,'K'];
  if(label==='Total heat source')return [v.total_source.value,v.total_source.unit];
  const m=/^Heat rate through (.+)$/.exec(label);
  if(m){const q=v.heat_rate_by_selection?.[m[1]];return q?[q.value,q.unit]:null;}
  return null;
 };
 const labels=[...Object.keys(ta)];
 for(const k of Object.keys(tb))if(!labels.includes(k))labels.splice(labels.indexOf('Total heat source'),0,k);
 const rows=labels.map(label=>{
  const na=number(va,label),nb=number(vb,label);
  return [label,ta[label]??'—',tb[label]??'—',na&&nb?signed(delta(nb[0],na[0]),nb[1]):''];
 });
 const size=r=>r.document?.mesh?.element_size===undefined?'—':shownText(r.document.mesh.element_size);
 rows.push(['Mesh nodes',count(va.mesh.nodes),count(vb.mesh.nodes),signed(delta(vb.mesh.nodes,va.mesh.nodes))]);
 rows.push(['Mesh tetrahedra',count(va.mesh.tetrahedra),count(vb.mesh.tetrahedra),signed(delta(vb.mesh.tetrahedra,va.mesh.tetrahedra))]);
 rows.push(['Mesh route',String(va.mesh.route??'—'),String(vb.mesh.route??'—'),'']);
 rows.push(['Mesh element size',size(a),size(b),'']);
 return rows;
}

/**
 * V6: the line under the table about heat rates' sign: B − A is run B minus run A, in the run table's
 * convention (positive into the model). An example uses the first selection both runs have, when both
 * rates have the same sign and differ; null without heat rates.
 */
export function heatRateNote(va,vb){
 const qa=va?.heat_rate_by_selection||{},qb=vb?.heat_rate_by_selection||{};
 const names=Object.keys(qa).filter(k=>k in qb);
 if(!names.length)return null;
 const head="Heat rates keep the run table's sign: positive into the model, negative out of it. B − A is run B minus run A";
 const k=names[0],a=qa[k].value,b=qb[k].value,d=delta(b,a);
 if(d===0||Math.sign(a)!==Math.sign(b)||a===0)return `${head}.`;
 const out=a<0,more=out?d<0:d>0;
 return `${head}, so ${signed(d,qb[k].unit||'W')} through ${k} means ${more?'more':'less'} heat ${out?'leaves':'enters'} through ${k} in run B.`;
}

// ---- C3-2: the inputs that differ ----------------------------------------------------------------

const shown=v=>v===undefined?'none':typeof v==='object'&&v!==null?shownText(JSON.stringify(v)):shownText(String(v));
function leaves(value,at,out){
 if(Array.isArray(value)){value.forEach((v,i)=>leaves(v,`${at}[${i}]`,out));return out;}
 if(value&&typeof value==='object'){for(const [k,v] of Object.entries(value))leaves(v,at?`${at}.${k}`:k,out);return out;}
 out.set(at,value);return out;
}
const SECTIONS=['geometry','materials','physics','mesh'];
/** The words of a document path for a person, in the tree's terms. */
function pathWords(doc,p){
 let m=/^geometry\.parameters\.([^.]+)\.value$/.exec(p);if(m)return `Parameter ${m[1]}`;
 m=/^geometry\.components\.[^.]+\.domain\.(\w+)$/.exec(p);if(m)return `Domain ${m[1]}`;
 m=/^geometry\.components\.[^.]+\.selections\.(.+?)(\.|$)/.exec(p);if(m)return `Selection ${m[1]}`;
 m=/^geometry\.components\.[^.]+\.(features\[\d+\](?:\.layers\[\d+\])?\.\w+)$/.exec(p);if(m)return fieldWords(doc,m[1]);
 m=/^physics\.heat\.prescribed_temperature\.(.+)$/.exec(p);if(m)return `Fixed temperature ${m[1]}`;
 m=/^physics\.heat\.heat_source_density(?:\.(.+))?$/.exec(p);if(m)return m[1]?`Heat source ${m[1]}`:'Heat source';
 m=/^materials\.([^.]+)\.(\w+)$/.exec(p);if(m)return `${m[1]} ${m[2].replace(/_/g,' ')}`;
 m=/^mesh\.(\w+)$/.exec(p);if(m)return `Mesh ${m[1].replace(/_/g,' ')}`;
 return p;
}
/** Features added or removed between the two documents, by name. */
function featureChanges(da,db){
 const names=d=>Object.values(d.geometry?.components||{}).flatMap(c=>(c.features||[]).map(f=>f.name));
 const a=names(da),b=names(db);
 return [...b.filter(n=>!a.includes(n)).map(n=>`Feature ${n}: added`),...a.filter(n=>!b.includes(n)).map(n=>`Feature ${n}: removed`)];
}
/** C3-2: each document field where A and B differ: "Parameter t_ox: 10 µm → 5 µm" (none: []). */
export function inputChanges(da,db){
 const added=featureChanges(da,db);
 if(added.length)return added;                    // feature indices no longer line up: name the features only
 const out=[];
 for(const s of SECTIONS){
  const la=leaves(da[s],s,new Map()),lb=leaves(db[s],s,new Map());
  for(const p of new Set([...la.keys(),...lb.keys()])){
   const x=la.get(p),y=lb.get(p);
   if(JSON.stringify(x)===JSON.stringify(y))continue;
   out.push(`${pathWords(lb.has(p)?db:da,p)}: ${shown(x)} → ${shown(y)}`);
  }
 }
 return out;
}

// ---- C3-3: the same mesh --------------------------------------------------------------------------

/**
 * Whether two runs share a mesh: the record's mesh key (the SHA-256 of the document's canonical
 * geometry and mesh blocks; physics is not in it) and equal node and tetrahedron counts. This is
 * not a node-by-node identity; the record keeps no mesh digest.
 */
export const sameMesh=(va,vb)=>!!va?.mesh&&!!vb?.mesh&&va.mesh.key===vb.mesh.key&&va.mesh.nodes===vb.mesh.nodes&&va.mesh.tetrahedra===vb.mesh.tetrahedra;
/** C3-3: the notice when the meshes differ, or null. */
export function meshNotice(a,b){
 if(sameMesh(a.values,b.values))return null;
 const one=r=>`${count(r.values.mesh.nodes)} nodes, size ${r.document?.mesh?.element_size===undefined?'—':shownText(r.document.mesh.element_size)}`;
 return `The runs have different meshes (A: ${one(a)}; B: ${one(b)}). Values are compared; the surface temperature is not compared point by point.`;
}

// ---- C3-4: the surface ΔT on a shared mesh --------------------------------------------------------

/** B − A per surface node (both maps on one mesh), its range and largest magnitude; null when the maps differ in length. */
export function surfaceDelta(ta,tb){
 if(!ta||!tb||ta.length!==tb.length||!ta.length)return null;
 const d=new Float32Array(ta.length);let min=Infinity,max=-Infinity,maxAbs=0;
 for(let i=0;i<ta.length;i++){const x=tb[i]-ta[i];d[i]=x;if(x<min)min=x;if(x>max)max=x;if(Math.abs(x)>maxAbs)maxAbs=Math.abs(x);}
 return {delta:d,min,max,maxAbs};
}
const legendNumber=x=>String(sig(x)).replace('-',MINUS);
/** C3-4: the ΔT legend: "ΔT (B − A): −1–5 K · largest |ΔT| 5 K". */
export const deltaLegend=d=>`ΔT (B − A): ${legendNumber(d.min)}–${legendNumber(d.max)} K · largest |ΔT| ${legendNumber(d.maxAbs)} K`;
/** A Float32Array as base64 (the surface maps' encoding). */
export function encodeF32(arr){
 const bytes=new Uint8Array(arr.buffer,arr.byteOffset,arr.byteLength);
 if(typeof Buffer!=='undefined')return Buffer.from(bytes).toString('base64');
 let s='';for(let i=0;i<bytes.length;i+=0x8000)s+=String.fromCharCode(...bytes.subarray(i,i+0x8000));
 return btoa(s);
}
