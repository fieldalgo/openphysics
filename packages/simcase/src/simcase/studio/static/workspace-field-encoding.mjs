// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

// Compact optical fields (session version 14, encoding "f32-base64-v1"). A field is kept as four
// little-endian byte strings in base64 (RFC 4648, standard alphabet, padded, no line breaks):
//   node_coordinates  nodes × 2 float64 (metres; lossless)
//   triangles         triangles × 3 uint32 (lossless)
//   real, imag        modes × triangles × 3 float32 (each sample rounded to nearest)
// The order inside each is today's nesting flattened: mode, then triangle, then x, y, z; node, then
// x, y; triangle, then its three indices. No compression: a field's size follows from its counts
// (compactFieldChars), so the run-retention budget stays a sum and every browser writes the same
// bytes. The platform's btoa and atob are used over chunks of bytes; DataView fixes the byte order,
// so a big-endian platform reads and writes the same numbers.

export const FIELD_ENCODING='f32-base64-v1';
/** The keys of a compact field, in the order a file writes them (and the reader requires). */
export const COMPACT_FIELD_KEYS=Object.freeze(['encoding','counts','node_coordinates','triangles','real','imag']);
const COUNT_KEYS=['modes','nodes','triangles'];
// readOpticalField's limits (workspace-field.mjs): 1 to 8 modes, 3 to 250,000 nodes, 1 to 500,000 triangles
export const COMPACT_LIMITS=Object.freeze({modes:[1,8],nodes:[3,250000],triangles:[1,500000]});

// The encoded strings of a field the tab holds compact: kept on the field object (not enumerated), so
// a field read from a file is written again from the strings it was read from.
const COMPACT=Symbol('compact field');
/** The compact record of a field ({encoding, counts, node_coordinates, triangles, real, imag}), or
 * null for a field kept as text. */
export const compactRecord=field=>field?.[COMPACT]??null;
export const isCompactField=field=>!!field?.[COMPACT];
/** The field object marked compact with its record (the object itself, returned). */
export function markCompact(field,record){
 Object.defineProperty(field,COMPACT,{value:record,enumerable:false,configurable:true,writable:false});
 return field;
}

const b64Length=bytes=>4*Math.ceil(bytes/3);
/** The characters of the four base64 strings of a field of these counts:
 * 32·k·T + 4⌈16N/3⌉ + 4⌈12T/3⌉ (the keys and counts of the record are extra). */
export function compactFieldChars({modes,nodes,triangles}){
 return 2*b64Length(12*modes*triangles)+b64Length(16*nodes)+b64Length(12*triangles);
}

const CHUNK=0x8000;
/** Bytes to standard padded base64, built in chunks (String.fromCharCode takes a bounded argument list). */
export function bytesToBase64(bytes){
 const parts=[];
 for(let i=0;i<bytes.length;i+=CHUNK)parts.push(String.fromCharCode.apply(null,bytes.subarray(i,i+CHUNK)));
 return btoa(parts.join(''));
}
/** Standard padded base64 to bytes, or null when the text is not canonical (another alphabet,
 * missing padding, white space, or padding bits that are not zero). atob accepts some of these, so
 * the bytes are encoded again and must give the same text. */
export function base64ToBytes(text){
 if(typeof text!=='string'||text.length%4!==0)return null;
 let binary;try{binary=atob(text);}catch{return null;}
 const bytes=new Uint8Array(binary.length);
 for(let i=0;i<binary.length;i++)bytes[i]=binary.charCodeAt(i);
 // canonical: the bytes encode to the same text (the unused bits of the last group are zero)
 return bytesToBase64(bytes)===text?bytes:null;
}

// the platform's byte order: typed arrays are written directly on a little-endian platform, else
// through a DataView (the bytes are little-endian either way)
const LITTLE=new Uint8Array(new Uint16Array([1]).buffer)[0]===1;
// the smallest normal float32: a nonzero sample below it would become 0 or a subnormal
const FLOAT32_MIN_NORMAL=2**-126;
/** The compact record of a field {node_coordinates (metres), triangles, real, imag} (nested arrays,
 * real/imag[mode][triangle][x, y, z]). Each sample is rounded to the nearest float32. A field with a
 * sample float32 cannot hold is refused: one that overflows to ±Infinity, or a nonzero sample that
 * would become 0 or a subnormal (no sample silently becomes 0; an exact zero is kept, its sign too). */
export function encodeField(field){
 const modes=field.real.length,nodes=field.node_coordinates.length,triangles=field.triangles.length;
 const X=new Float64Array(2*nodes);field.node_coordinates.forEach((p,i)=>{X[2*i]=p[0];X[2*i+1]=p[1];});
 const T=new Uint32Array(3*triangles);field.triangles.forEach((t,i)=>{T[3*i]=t[0];T[3*i+1]=t[1];T[3*i+2]=t[2];});
 const samples=part=>{
  const a=new Float32Array(3*modes*triangles);let o=0;
  for(const mode of part)for(const v of mode){
   for(let c=0;c<3;c++){const x=v[c];a[o+c]=x;const y=a[o+c];if(!Number.isFinite(y)||(x!==0&&Math.abs(y)<FLOAT32_MIN_NORMAL))throw new Error('A field sample is beyond single precision.');}
   o+=3;
  }
  return bytesToBase64(LITTLE?new Uint8Array(a.buffer):swap(new Uint8Array(a.buffer),4));
 };
 return {encoding:FIELD_ENCODING,counts:{modes,nodes,triangles},node_coordinates:bytesToBase64(LITTLE?new Uint8Array(X.buffer):swap(new Uint8Array(X.buffer),8)),
  triangles:bytesToBase64(LITTLE?new Uint8Array(T.buffer):swap(new Uint8Array(T.buffer),4)),real:samples(field.real),imag:samples(field.imag)};
}
// the bytes of each value reversed (a big-endian platform's typed array to little-endian bytes)
function swap(bytes,size){const out=new Uint8Array(bytes.length);for(let i=0;i<bytes.length;i+=size)for(let b=0;b<size;b++)out[i+b]=bytes[i+size-1-b];return out;}
/** The samples a compact field holds for nested samples (each rounded to float32, -0 kept). */
export const singlePrecision=part=>part.map(mode=>mode.map(v=>[Math.fround(v[0]),Math.fround(v[1]),Math.fround(v[2])]));
/** The bytes a compact field adds to its run's record in a session ("field":{…}, and the comma). */
export function compactFieldBytes(record){
 const c=record.counts;
 return `"field":{"encoding":"${record.encoding}","counts":{"modes":${c.modes},"nodes":${c.nodes},"triangles":${c.triangles}},"node_coordinates":"","triangles":"","real":"","imag":""},`.length+compactFieldChars(c);
}

const isObject=x=>x!==null&&typeof x==='object'&&!Array.isArray(x);
/** Whether a stored field is a compact record (it names an encoding) rather than nested numbers. */
export const isCompactRecord=f=>isObject(f)&&Object.hasOwn(f,'encoding');

/** The field a compact record holds, as nested arrays {node_coordinates, triangles, real, imag}
 * (readOpticalField's input), each check refused by name with the run's name (which, "Run 3").
 * modeCount: the run's number of modes. */
export function decodeField(record,modeCount,which='This run'){
 const name=`${which}'s compact field`;
 if(!isObject(record))throw new Error(`${name} is not a field record.`);
 if(record.encoding!==FIELD_ENCODING)throw new Error(`${which}'s field is encoded as ${JSON.stringify(String(record.encoding))}, which this Studio does not read.`);
 if(Object.keys(record).join()!==COMPACT_FIELD_KEYS.join())throw new Error(`${name} must hold ${COMPACT_FIELD_KEYS.join(', ')} in this order, and nothing else.`);
 const c=record.counts;
 if(!isObject(c)||Object.keys(c).join()!==COUNT_KEYS.join()||COUNT_KEYS.some(k=>!Number.isInteger(c[k])||c[k]<COMPACT_LIMITS[k][0]||c[k]>COMPACT_LIMITS[k][1]))
  throw new Error(`${name} counts must be whole numbers: modes 1 to 8, nodes 3 to 250000, triangles 1 to 500000.`);
 if(c.modes!==modeCount)throw new Error(`${name} holds ${c.modes} modes; the run has ${modeCount}.`);
 const bytes=(key,want)=>{
  const b=base64ToBytes(record[key]);
  if(b===null)throw new Error(`${name} ${key} is not canonical base64.`);
  if(b.length!==want)throw new Error(`${name} ${key} holds ${b.length} bytes; its counts give ${want}.`);
  return new DataView(b.buffer,b.byteOffset,b.byteLength);
 };
 const {modes,nodes,triangles}=c;
 const X=bytes('node_coordinates',16*nodes),T=bytes('triangles',12*triangles),R=bytes('real',12*modes*triangles),I=bytes('imag',12*modes*triangles);
 const node_coordinates=new Array(nodes);
 for(let i=0;i<nodes;i++){
  const p=[X.getFloat64(16*i,true),X.getFloat64(16*i+8,true)];
  if(!p.every(Number.isFinite))throw new Error(`${name} node_coordinates holds a value that is not a finite number.`);
  node_coordinates[i]=p;
 }
 const tri=new Array(triangles);
 for(let i=0;i<triangles;i++){
  const t=[T.getUint32(12*i,true),T.getUint32(12*i+4,true),T.getUint32(12*i+8,true)];
  const out=t.find(n=>n>=nodes);if(out!==undefined)throw new Error(`${name} triangle ${i} names node ${out}, outside 0–${nodes-1}.`);
  if(t[0]===t[1]||t[1]===t[2]||t[0]===t[2])throw new Error(`${name} triangle ${i} repeats a node.`);
  tri[i]=t;
 }
 const samples=(view,key)=>{
  const out=new Array(modes);let o=0;
  for(let m=0;m<modes;m++){
   const mode=out[m]=new Array(triangles);
   for(let i=0;i<triangles;i++){
    const v=[view.getFloat32(o,true),view.getFloat32(o+4,true),view.getFloat32(o+8,true)];o+=12;
    if(!v.every(Number.isFinite))throw new Error(`${name} ${key} holds a value that is not a finite number.`);
    mode[i]=v;
   }
  }
  return out;
 };
 return {node_coordinates,triangles:tri,real:samples(R,'real'),imag:samples(I,'imag')};
}
