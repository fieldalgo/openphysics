// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

// The vector field of an optical result (section 5.3.4): node coordinates in metres, the complex
// centroid field "unnormalized_electric_field" (x, y, z) of unit 1 under exp(-i omega t). The page
// draws in micrometres (display only): ``nodes`` are the metre coordinates times 1e6.
export const FIELD_METADATA=Object.freeze({name:'unnormalized_electric_field',location:'triangle_centroids',components:['x','y','z'],unit:'1',normalization:'max_centroid_magnitude',time_convention:'exp(-i omega t)'});
export function readOpticalField(data){
 const f=data?.vector_fields?.[0],coordinates=data?.node_coordinates,triangles=data?.triangles;
 if(!f||Object.entries(FIELD_METADATA).some(([key,value])=>JSON.stringify(f[key])!==JSON.stringify(value))||'amplitude_unit' in f)throw new Error('Unsupported optical field metadata.');
 if(data?.field_units?.node_coordinates!=='m')throw new Error('Field coordinates must be in metres.');
 if(!Array.isArray(coordinates)||coordinates.length<3||coordinates.length>250000||!coordinates.every(p=>Array.isArray(p)&&p.length===2&&p.every(Number.isFinite)))throw new Error('Invalid field coordinates.');
 const nodes=coordinates.map(p=>p.map(v=>v*1e6));
 if(!Array.isArray(triangles)||!triangles.length||triangles.length>500000||!triangles.every(t=>Array.isArray(t)&&t.length===3&&new Set(t).size===3&&t.every(i=>Number.isInteger(i)&&i>=0&&i<nodes.length)))throw new Error('Invalid field triangles.');
 for(const a of [f.real,f.imag])if(!Array.isArray(a)||a.length!==2||!a.every(mode=>Array.isArray(mode)&&mode.length===triangles.length&&mode.every(v=>Array.isArray(v)&&v.length===3&&v.every(Number.isFinite))))throw new Error('Invalid complex field samples.');
 return {node_coordinates:coordinates.map(p=>[...p]),nodes,triangles:triangles.map(t=>[...t]),real:f.real.map(m=>m.map(v=>[...v])),imag:f.imag.map(m=>m.map(v=>[...v]))};
}
export function fieldScalars(field,mode,component='magnitude'){
 if(![0,1].includes(mode)||!['magnitude','Ex','Ey','Ez'].includes(component))throw new Error('Invalid field selection.');
 const magnitudes=field.real[mode].map((v,i)=>Math.hypot(...v,...field.imag[mode][i]));
 let maximum=0;for(const v of magnitudes)maximum=Math.max(maximum,v);
 if(!Number.isFinite(maximum))throw new Error('Field magnitude overflow.');
 const index=['Ex','Ey','Ez'].indexOf(component);
 const values=index<0?magnitudes:field.real[mode].map((v,i)=>Math.hypot(v[index],field.imag[mode][i][index]));
 return {values:values.map(v=>maximum===0?0:v/maximum),maximum};
}
