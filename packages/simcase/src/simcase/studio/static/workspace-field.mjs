// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

// The vector field of an optical result (section 5.3.4): node coordinates in metres, the complex
// centroid field "unnormalized_electric_field" (x, y, z) of unit 1 under exp(-i omega t). The page
// draws in micrometres (display only): ``nodes`` are the metre coordinates times 1e6.
export const FIELD_METADATA=Object.freeze({name:'unnormalized_electric_field',location:'triangle_centroids',components:['x','y','z'],unit:'1',normalization:'max_centroid_magnitude',time_convention:'exp(-i omega t)'});
/** count: the number of modes the samples hold (two, the count of version 7 runs, by default). */
export function readOpticalField(data,count=2){
 if(!Number.isInteger(count)||count<1||count>8)throw new Error('Invalid complex field samples.');
 const f=data?.vector_fields?.[0],coordinates=data?.node_coordinates,triangles=data?.triangles;
 if(!f||Object.entries(FIELD_METADATA).some(([key,value])=>JSON.stringify(f[key])!==JSON.stringify(value))||'amplitude_unit' in f)throw new Error('Unsupported optical field metadata.');
 if(data?.field_units?.node_coordinates!=='m')throw new Error('Field coordinates must be in metres.');
 if(!Array.isArray(coordinates)||coordinates.length<3||coordinates.length>250000||!coordinates.every(p=>Array.isArray(p)&&p.length===2&&p.every(Number.isFinite)))throw new Error('Invalid field coordinates.');
 const nodes=coordinates.map(p=>p.map(v=>v*1e6));
 if(!Array.isArray(triangles)||!triangles.length||triangles.length>500000||!triangles.every(t=>Array.isArray(t)&&t.length===3&&new Set(t).size===3&&t.every(i=>Number.isInteger(i)&&i>=0&&i<nodes.length)))throw new Error('Invalid field triangles.');
 for(const a of [f.real,f.imag])if(!Array.isArray(a)||a.length!==count||!a.every(mode=>Array.isArray(mode)&&mode.length===triangles.length&&mode.every(v=>Array.isArray(v)&&v.length===3&&v.every(Number.isFinite))))throw new Error('Invalid complex field samples.');
 return {node_coordinates:coordinates.map(p=>[...p]),nodes,triangles:triangles.map(t=>[...t]),real:f.real.map(m=>m.map(v=>[...v])),imag:f.imag.map(m=>m.map(v=>[...v]))};
}
export function fieldScalars(field,mode,component='magnitude'){
 if(!Number.isInteger(mode)||mode<0||mode>=field.real.length||!['magnitude','Ex','Ey','Ez'].includes(component))throw new Error('Invalid field selection.');
 const magnitudes=field.real[mode].map((v,i)=>Math.hypot(...v,...field.imag[mode][i]));
 let maximum=0;for(const v of magnitudes)maximum=Math.max(maximum,v);
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
