// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

// The vector field of an optical result (section 5.3.4): node coordinates in metres, the complex
// centroid field "unnormalized_electric_field" (x, y, z) of unit 1 under exp(-i omega t). The page
// draws in micrometres (display only): ``nodes`` are the metre coordinates times 1e6.
export const FIELD_METADATA=Object.freeze({name:'unnormalized_electric_field',location:'triangle_centroids',components:['x','y','z'],unit:'1',normalization:'max_centroid_magnitude',time_convention:'exp(-i omega t)'});
// A result with an open boundary (PML) normalizes each mode to its largest centroid |E| in the
// physical window (the engine's pml-vector-edge-nodal-v2 fields; inside the PML they are not
// physical): the same metadata with this normalization. A session keeps it implied by the run's
// boundary "PML".
export const PML_FIELD_METADATA=Object.freeze({...FIELD_METADATA,normalization:'physical_max_centroid_magnitude'});
/** The physical bounds [[x0, y0], [x1, y1]] in metres of an open run's candidate record
 * (physical_bounds, {unit: 'm', values}), or null when it has none that is valid. */
export function physicalBounds(record){
 const b=record?.physical_bounds,v=b?.values;
 if(b?.unit!=='m'||!Array.isArray(v)||v.length!==2||!v.every(p=>Array.isArray(p)&&p.length===2&&p.every(Number.isFinite)))return null;
 return v[0][0]<v[1][0]&&v[0][1]<v[1][1]?[[v[0][0],v[0][1]],[v[1][0],v[1][1]]]:null;
}
/** For each triangle, whether it meets the closed window bounds [[x0, y0], [x1, y1]] (metres, the
 * stored coordinates): its bounding box overlaps the window and none of its three edge normals
 * separates it from the window's corners (the separating-axis test). A triangle that only touches
 * the window at a corner or along an edge meets it. */
export function meetsWindow(field,[[x0,y0],[x1,y1]]){
 const X=field.node_coordinates,corners=[[x0,y0],[x1,y0],[x1,y1],[x0,y1]];
 return field.triangles.map(t=>{
  const p=[X[t[0]],X[t[1]],X[t[2]]];
  if(Math.max(p[0][0],p[1][0],p[2][0])<x0||Math.min(p[0][0],p[1][0],p[2][0])>x1||Math.max(p[0][1],p[1][1],p[2][1])<y0||Math.min(p[0][1],p[1][1],p[2][1])>y1)return false;
  for(let e=0;e<3;e++){
   const a=p[e],c=p[(e+1)%3],o=p[(e+2)%3],nx=c[1]-a[1],ny=a[0]-c[0],side=q=>(q[0]-a[0])*nx+(q[1]-a[1])*ny,s=side(o);
   if(s>0?corners.every(q=>side(q)<0):s<0?corners.every(q=>side(q)>0):false)return false;
  }
  return true;
 });
}
/** The margin of the crop (C5''): 1/150 of the window's longer side, in metres. drawField clips the
 * field view to the window with antialiasing, so a triangle just outside the window still tints the
 * edge pixels it partly covers; with the triangles within this margin kept, the pictures at the
 * window edge are unchanged whenever the plot spends at least 150 device px on that side (Results
 * always does). For the 3 × 2.4 µm window it is 20 nm. */
export const windowMargin=([[x0,y0],[x1,y1]])=>Math.max(x1-x0,y1-y0)/150;
/** The samples of a new open run on its physical window (crop rule C5''): the triangles that meet
 * the closed bounds grown on each side by windowMargin (meetsWindow), in their order, their nodes
 * renumbered in first-use order; no coordinate or sample value changes. The PML beyond the margin is
 * not kept. Every triangle whose centroid lies inside the bounds meets them, so the physical window
 * of the result is that of the full samples, and cropping again changes nothing. field:
 * {node_coordinates, triangles, real, imag}, real/imag[mode][triangle]; the result has these four
 * keys (and regions, per triangle, when the field has them). */
export function windowField(field,bounds){
 const d=windowMargin(bounds),[[x0,y0],[x1,y1]]=bounds,keep=meetsWindow(field,[[x0-d,y0-d],[x1+d,y1+d]]),number=new Map(),node_coordinates=[],triangles=[];
 field.triangles.forEach((t,i)=>{if(keep[i])triangles.push(t.map(n=>{if(!number.has(n)){number.set(n,node_coordinates.length);node_coordinates.push(field.node_coordinates[n]);}return number.get(n);}));});
 const kept=list=>list.filter((_,i)=>keep[i]);
 return {node_coordinates,triangles,real:field.real.map(kept),imag:field.imag.map(kept),...(Array.isArray(field.regions)?{regions:kept(field.regions)}:{})};
}
/** count: the number of modes the samples hold (two, the count of version 7 runs, by default).
 * open: the samples of a result with an open boundary (PML_FIELD_METADATA). */
export function readOpticalField(data,count=2,{open=false}={}){
 if(!Number.isInteger(count)||count<1||count>8)throw new Error('Invalid complex field samples.');
 const f=data?.vector_fields?.[0],coordinates=data?.node_coordinates,triangles=data?.triangles,metadata=open?PML_FIELD_METADATA:FIELD_METADATA;
 if(!f||Object.entries(metadata).some(([key,value])=>JSON.stringify(f[key])!==JSON.stringify(value))||'amplitude_unit' in f)throw new Error('Unsupported optical field metadata.');
 if(data?.field_units?.node_coordinates!=='m')throw new Error('Field coordinates must be in metres.');
 if(!Array.isArray(coordinates)||coordinates.length<3||coordinates.length>250000||!coordinates.every(p=>Array.isArray(p)&&p.length===2&&p.every(Number.isFinite)))throw new Error('Invalid field coordinates.');
 const nodes=coordinates.map(p=>p.map(v=>v*1e6));
 if(!Array.isArray(triangles)||!triangles.length||triangles.length>500000||!triangles.every(t=>Array.isArray(t)&&t.length===3&&new Set(t).size===3&&t.every(i=>Number.isInteger(i)&&i>=0&&i<nodes.length)))throw new Error('Invalid field triangles.');
 for(const a of [f.real,f.imag])if(!Array.isArray(a)||a.length!==count||!a.every(mode=>Array.isArray(mode)&&mode.length===triangles.length&&mode.every(v=>Array.isArray(v)&&v.length===3&&v.every(Number.isFinite))))throw new Error('Invalid complex field samples.');
 const out={node_coordinates:coordinates.map(p=>[...p]),nodes,triangles:triangles.map(t=>[...t]),real:f.real.map(m=>m.map(v=>[...v])),imag:f.imag.map(m=>m.map(v=>[...v]))};
 // an open boundary: the triangles whose centroid lies in the physical window (µm), the ones the
 // engine normalizes over (not written to a file: the run's boundary implies it)
 if(open){const inside=Uint8Array.from(out.triangles,t=>{const x=(nodes[t[0]][0]+nodes[t[1]][0]+nodes[t[2]][0])/3,y=(nodes[t[0]][1]+nodes[t[1]][1]+nodes[t[2]][1])/3;return Math.abs(x)<=1.5*(1+1e-12)&&Math.abs(y)<=1.2*(1+1e-12)?1:0;});Object.defineProperty(out,'physical',{value:inside,enumerable:false});}
 return out;
}
/** The field of one mode normalized to its largest centroid |E|: over every triangle, or over the
 * physical window for a field of an open boundary (field.physical; in the PML it is not physical). */
export function fieldScalars(field,mode,component='magnitude'){
 if(!Number.isInteger(mode)||mode<0||mode>=field.real.length||!['magnitude','Ex','Ey','Ez'].includes(component))throw new Error('Invalid field selection.');
 const magnitudes=field.real[mode].map((v,i)=>Math.hypot(...v,...field.imag[mode][i]));
 let maximum=0;magnitudes.forEach((v,i)=>{if(!field.physical||field.physical[i])maximum=Math.max(maximum,v);});
 if(!Number.isFinite(maximum))throw new Error('Field magnitude overflow.');
 const index=['Ex','Ey','Ez'].indexOf(component);
 const values=index<0?magnitudes:field.real[mode].map((v,i)=>Math.hypot(v[index],field.imag[mode][i][index]));
 return {values:values.map(v=>maximum===0?0:v/maximum),maximum};
}
// Plot axes in nanometres (display only; the views and the stored state stay in µm).
// Ticks fall on round nanometre values (1, 2, 2.5 or 5 × 10^k nm, whole nm) inside [min, max]
// µm: the finest such step with 2 to maxTicks ticks; if none has, the step with the fewest
// ticks above one (a short axis may then hold one more than maxTicks).
export function nmTicks(min,max,maxTicks=5){
 if(!Number.isFinite(min)||!Number.isFinite(max)||!(max>min)||!(maxTicks>=2))throw new Error('Invalid axis range.');
 const lo=min*1000,hi=max*1000,count=step=>Math.floor(hi/step+1e-9)-Math.ceil(lo/step-1e-9)+1;
 const steps=[];for(let power=Math.max(1,10**Math.floor(Math.log10((hi-lo)/maxTicks)));steps.length<40;power*=10)steps.push(power,2*power,...(power>=10?[2.5*power]:[]),5*power);
 const step=steps.find(s=>count(s)>=2&&count(s)<=maxTicks)??steps.filter(s=>count(s)>=2).at(-1)??steps[0];
 const ticks=[];for(let k=Math.ceil(lo/step-1e-9);k<=Math.floor(hi/step+1e-9);k++)ticks.push(k===0?0:Number((k*step).toPrecision(12))/1000);
 return ticks;
}
// A µm coordinate as nanometres for display, at most `digits` decimals without trailing
// zeros, e.g. formatNm(-0.57) → "−570", formatNm(0.1234567, 1) → "123.5".
export const formatNm=(um,digits=0)=>{const nm=um*1000,text=String(Number(Math.abs(nm).toFixed(digits)));return (nm<0&&text!=='0'?'−':'')+text;};
