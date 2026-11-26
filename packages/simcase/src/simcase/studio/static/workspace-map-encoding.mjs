// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

// Compact heated maps (multiphysics session version 17, encoding "f32-offset-base64-v1"; design
// "Session versions 16 and 17", section 3). A run's maps keep the layout of the server's reply with
// each array below replaced by one little-endian byte string in base64 (the helpers of compact optical
// fields, workspace-field-encoding.mjs: RFC 4648 standard alphabet, padded, no line breaks):
//   mesh.node_coordinates       nodes × 2 float64 (metres; lossless)
//   mesh.triangles              triangles × 3 uint32 (lossless)
//   mesh.regions                triangles × uint8 (lossless; at most 256 region names)
//   heat temperature.values     nodes × float32 offsets from the physics' range.min
//   coupled refractive_index.n  triangles × float32 offsets from n_base[region], beside it
//   coupled refractive_index.k  likewise with k_base (when k is not null)
//   coupled index_change        likewise with index_change_base (when not null)
// with mesh.encoding and mesh.counts {nodes, triangles}. Each base of a triangle map is float64, the
// map's value at the region's first triangle (0 for a region without triangles). A value decodes to
// base + float32, in float64: an offset rounds once to the nearest float32, so a temperature differs
// from the server's by at most 2^-24 of the heat range (plus one float64 rounding), and the core's
// index map, which spans about 5e-6 around 3.48, keeps every colour of the map. The coupled
// temperature is not stored: it is the mean of each triangle's 3 decoded node temperatures (the rule
// the version 8 reader checks to 1e-12). No compression: the size follows from the counts
// (compactMapChars), so the budget stays a sum and every browser writes the same bytes.
import {bytesToBase64,base64ToBytes} from './workspace-field-encoding.mjs';

export const MAP_ENCODING='f32-offset-base64-v1';
export const MAX_COMPACT_REGIONS=256;
// the smallest normal float32: a nonzero offset below it would become 0 or a subnormal
const FLOAT32_MIN_NORMAL=2**-126;
const MESH_KEYS=Object.freeze(['counts','encoding','field_units','node_coordinates','region_names','regions','triangles']);
const isObject=x=>x!==null&&typeof x==='object'&&!Array.isArray(x);
const b64Length=bytes=>4*Math.ceil(bytes/3);

// The compact record of a decoded result, kept on that result (not enumerated): a run read from a file
// is written again from the strings it was read from.
const COMPACT=Symbol('compact maps');
/** The compact record of a result the tab holds compact, or null for a result kept as text. */
export const compactMapsRecord=result=>result?.[COMPACT]??null;
export const isCompactResult=result=>!!result?.[COMPACT];
function markCompact(result,record){Object.defineProperty(result,COMPACT,{value:record,enumerable:false,configurable:true,writable:false});return result;}

/** The characters of the base64 strings of compact maps of these counts: 4⌈16N/3⌉ + 4⌈12M/3⌉ + 4⌈M/3⌉,
 * 4⌈4N/3⌉ per heat physics and 4⌈4M/3⌉ per coupled triangle map (n, and k and index_change when
 * present). The keys, counts and bases are extra. */
export function compactMapChars({nodes,triangles},{heat=1,triangleMaps=2}={}){
 return b64Length(16*nodes)+b64Length(12*triangles)+b64Length(triangles)+heat*b64Length(4*nodes)+triangleMaps*b64Length(4*triangles);
}
/** The base64 characters a compact record holds (its counts' compactMapChars). */
export function recordMapChars(record){
 let n=0;const add=s=>{if(typeof s==='string')n+=s.length;};
 add(record.mesh.node_coordinates);add(record.mesh.triangles);add(record.mesh.regions);
 for(const p of Object.values(record.physics||{})){
  if(p.type==='thermal.steady2d')add(p.temperature?.values);
  if(p.coupled){add(p.coupled.refractive_index?.n);add(p.coupled.refractive_index?.k);add(p.coupled.index_change);}
 }
 return n;
}

const view=bytes=>new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);
function f64(values){const b=new Uint8Array(8*values.length),v=view(b);values.forEach((x,i)=>v.setFloat64(8*i,x,true));return bytesToBase64(b);}
function u32(values){const b=new Uint8Array(4*values.length),v=view(b);values.forEach((x,i)=>v.setUint32(4*i,x,true));return bytesToBase64(b);}
function u8(values){return bytesToBase64(Uint8Array.from(values));}
// float32 offsets from a base per value (base(i)); null when one is beyond single precision
function offsets(values,base){
 const b=new Uint8Array(4*values.length),v=view(b);
 for(let i=0;i<values.length;i++){
  const x=values[i]-base(i),y=Math.fround(x);
  if(!Number.isFinite(y)||(x!==0&&Math.abs(y)<FLOAT32_MIN_NORMAL))return null;
  v.setFloat32(4*i,y,true);
 }
 return bytesToBase64(b);
}
/** The base of each region of a triangle map: its value at the region's first triangle, 0 without one. */
export function regionBases(values,regions,count){
 const base=new Array(count).fill(null);
 for(let i=0;i<regions.length;i++)if(base[regions[i]]===null)base[regions[i]]=values[i];
 return base.map(x=>x===null?0:x);
}
// the physics whose node temperatures a coupled em physics received (the coupling's source)
function sourceOf(document,name,physics){
 const c=Object.values(document?.couplings||{}).find(k=>k?.to===`${name}.temperature`),from=String(c?.from||'').split('.')[0];
 return physics[from]?.type==='thermal.steady2d'?from:null;
}

/** The compact record of a run's result (the server's layout, its arrays as above), or null when its
 * maps cannot be kept compact: more than 256 region names, an offset beyond single precision (an
 * overflow, or a nonzero offset below 2^-126), a coupled map whose source's node temperatures are not
 * in the result, or a result without a mesh. document: the run's model (its couplings). */
export function encodeMaps(result,document){
 const mesh=result?.mesh;
 if(!isObject(mesh)||!Array.isArray(mesh.node_coordinates)||!Array.isArray(mesh.triangles)||!Array.isArray(mesh.regions)||!Array.isArray(mesh.region_names))return null;
 if(mesh.region_names.length>MAX_COMPACT_REGIONS)return null;
 const N=mesh.node_coordinates.length,M=mesh.triangles.length,R=mesh.regions,count=mesh.region_names.length;
 const outMesh={encoding:MAP_ENCODING,counts:{nodes:N,triangles:M}};
 for(const [k,v] of Object.entries(mesh)){
  if(k==='node_coordinates')outMesh[k]=f64(v.flat());
  else if(k==='triangles')outMesh[k]=u32(v.flat());
  else if(k==='regions')outMesh[k]=u8(v);
  else outMesh[k]=v;
 }
 const physics={};
 for(const [name,p] of Object.entries(result.physics||{})){
  if(p.type==='thermal.steady2d'&&Array.isArray(p.temperature?.values)){
   const base=p.range?.min;if(!Number.isFinite(base))return null;
   const values=offsets(p.temperature.values,()=>base);if(values===null)return null;
   physics[name]={...p,temperature:{...p.temperature,values}};
  }else if(p.type==='em.modes2d'&&p.coupled){
   if(!sourceOf(document,name,result.physics))return null;
   const c=p.coupled,coupled={};
   const map=values=>{const base=regionBases(values,R,count),text=offsets(values,i=>base[R[i]]);return text===null?null:{text,base};};
   for(const [k,v] of Object.entries(c)){
    if(k==='temperature'){const {values,...rest}=v;coupled[k]=rest;}
    else if(k==='refractive_index'){
     const out={};
     for(const [q,a] of Object.entries(v)){
      if((q==='n'||q==='k')&&Array.isArray(a)){const m=map(a);if(!m)return null;out[q]=m.text;out[q+'_base']=m.base;}
      else out[q]=a;
     }
     coupled[k]=out;
    }else if(k==='index_change'&&Array.isArray(v)){const m=map(v);if(!m)return null;coupled[k]=m.text;coupled.index_change_base=m.base;}
    else coupled[k]=v;
   }
   physics[name]={...p,coupled};
  }else physics[name]=p;
 }
 const record={};
 for(const [k,v] of Object.entries(result))record[k]=k==='mesh'?outMesh:k==='physics'?physics:v;
 return record;
}

/** The result a compact record holds, as the server's layout of nested numbers (checkArrays' input,
 * the maps' drawing), with the coupled temperature computed as the triangle mean of the decoded node
 * temperatures and the record kept on it. Every check is refused by name: "Run 3's stored maps are not
 * well formed: …". document: the run's model. */
export function decodeMaps(record,document,which='This run'){
 const where=`${which}'s stored maps are not well formed`,bad=text=>{throw new Error(`${where}: ${text}.`);};
 const mesh=record?.mesh;
 if(!isObject(mesh))bad('the mesh is missing');
 if(mesh.encoding!==MAP_ENCODING)bad(`the maps are encoded as ${JSON.stringify(String(mesh.encoding))}, which this Studio does not read`);
 if(Object.keys(mesh).sort().join()!==MESH_KEYS.join())bad(`a compact mesh holds ${MESH_KEYS.join(', ')} and nothing else`);
 const c=mesh.counts;
 if(!isObject(c)||Object.keys(c).join()!=='nodes,triangles'||!Number.isSafeInteger(c.nodes)||c.nodes<1||!Number.isSafeInteger(c.triangles)||c.triangles<1)bad('its counts must be whole numbers of nodes and triangles, at least 1');
 const {nodes:N,triangles:M}=c,names=mesh.region_names;
 if(!Array.isArray(names)||!names.length||names.length>MAX_COMPACT_REGIONS||!names.every(n=>typeof n==='string'))bad(`region_names must be 1 to ${MAX_COMPACT_REGIONS} texts`);
 const bytes=(text,what,want)=>{const b=base64ToBytes(text);if(b===null)bad(`${what} is not canonical base64`);if(b.length!==want)bad(`${what} holds ${b.length} bytes; its counts give ${want}`);return view(b);};
 const X=bytes(mesh.node_coordinates,'node_coordinates',16*N),T=bytes(mesh.triangles,'triangles',12*M),G=bytes(mesh.regions,'regions',M);
 const P=new Array(N);for(let i=0;i<N;i++)P[i]=[X.getFloat64(16*i,true),X.getFloat64(16*i+8,true)];
 const tri=new Array(M);for(let i=0;i<M;i++)tri[i]=[T.getUint32(12*i,true),T.getUint32(12*i+4,true),T.getUint32(12*i+8,true)];
 const regions=new Array(M);for(let i=0;i<M;i++)regions[i]=G.getUint8(i);
 const outMesh={};
 for(const [k,v] of Object.entries(mesh)){if(k==='encoding'||k==='counts')continue;outMesh[k]=k==='node_coordinates'?P:k==='triangles'?tri:k==='regions'?regions:v;}
 const samples=(text,what,n,base)=>{const v=bytes(text,what,4*n),out=new Array(n);
  for(let i=0;i<n;i++){const y=v.getFloat32(4*i,true);if(!Number.isFinite(y))bad(`${what} holds a value that is not a finite number`);out[i]=base(i)+y;}
  return out;};
 const bases=(b,what)=>{if(!Array.isArray(b)||b.length!==names.length||!b.every(x=>typeof x==='number'&&Number.isFinite(x)))bad(`${what} must hold ${names.length} finite numbers, one per region`);return b;};
 const physics={},heat={};
 for(const [name,p] of Object.entries(record.physics||{})){
  if(p.type==='thermal.steady2d'&&p.temperature&&'values' in p.temperature){
   if(typeof p.temperature.values!=='string')bad(`the node temperature of ${name} is not a compact map`);
   const base=p.range?.min;if(typeof base!=='number'||!Number.isFinite(base))bad(`the heat range of ${name} is not well formed`);
   const values=samples(p.temperature.values,`${name} node temperature`,N,()=>base);
   heat[name]=values;physics[name]={...p,temperature:{...p.temperature,values}};
  }else physics[name]=p;
 }
 for(const [name,p] of Object.entries(record.physics||{})){
  if(!(p.type==='em.modes2d'&&p.coupled))continue;
  const k=p.coupled,from=sourceOf(document,name,record.physics),nodal=from?heat[from]:null;
  if(!nodal)bad(`the coupled maps of ${name} have no node temperatures to take the triangle means from`);
  if(!isObject(k.temperature)||'values' in k.temperature)bad(`a compact coupled temperature holds no values (it is the mean of the node temperatures)`);
  const coupled={};
  const tmap=(text,base,what)=>{const b=bases(base,`${what}_base`);return samples(text,what,M,i=>{const r=regions[i];if(r>=names.length)bad(`regions must hold ${M} integers in 0–${names.length-1}`);return b[r];});};
  for(const [key,v] of Object.entries(k)){
   if(key==='temperature')coupled[key]={...v,values:tri.map(t=>{for(const n of t)if(n>=N)bad(`triangle names node ${n}, outside 0–${N-1}`);return (nodal[t[0]]+nodal[t[1]]+nodal[t[2]])/3;})};
   else if(key==='refractive_index'){
    if(!isObject(v))bad('refractive_index is not well formed');
    const out={};
    for(const [q,a] of Object.entries(v)){
     if(q==='n_base'||q==='k_base')continue;
     if(q==='n'||(q==='k'&&a!==null)){if(typeof a!=='string')bad(`refractive_index.${q} is not a compact map`);out[q]=tmap(a,v[q+'_base'],`refractive_index.${q}`);}
     else out[q]=a;
    }
    if(v.k===null&&'k_base' in v)bad('refractive_index.k_base belongs to no map');
    coupled[key]=out;
   }else if(key==='index_change_base')continue;
   else if(key==='index_change'&&v!==null){if(typeof v!=='string')bad('index_change is not a compact map');coupled[key]=tmap(v,k.index_change_base,'index_change');}
   else coupled[key]=v;
  }
  if(k.index_change==null&&'index_change_base' in k)bad('index_change_base belongs to no map');
  physics[name]={...p,coupled};
 }
 const result={};
 for(const [k,v] of Object.entries(record))result[k]=k==='mesh'?outMesh:k==='physics'?physics:v;
 return markCompact(result,record);
}
/** A run's result made compact: the decoded result of its encoding, with the record kept on it (what
 * the tab holds, the values a file of it reads), or null when its maps cannot be kept compact. */
export function compactResult(result,document){
 if(isCompactResult(result))return result;
 const record=encodeMaps(result,document);
 return record?decodeMaps(record,document):null;
}
