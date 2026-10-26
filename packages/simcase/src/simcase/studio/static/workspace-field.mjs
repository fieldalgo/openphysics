// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

export function readOpticalField(data){
 const f=data?.vector_fields?.[0],nodes=data?.nodes,triangles=data?.triangles;
 if(!f||f.location!=='triangle_centroids'||f.normalization!=='max_centroid_magnitude'||f.amplitude_unit!=='relative'||JSON.stringify(f.components)!==JSON.stringify(['Ex','Ey','Ez']))throw new Error('Unsupported optical field metadata.');
 if(!Array.isArray(nodes)||nodes.length<3||nodes.length>250000||!nodes.every(p=>Array.isArray(p)&&p.length===2&&p.every(Number.isFinite)))throw new Error('Invalid field coordinates.');
 if(!Array.isArray(triangles)||!triangles.length||triangles.length>500000||!triangles.every(t=>Array.isArray(t)&&t.length===3&&new Set(t).size===3&&t.every(i=>Number.isInteger(i)&&i>=0&&i<nodes.length)))throw new Error('Invalid field triangles.');
 for(const a of [f.real,f.imag])if(!Array.isArray(a)||a.length!==2||!a.every(mode=>Array.isArray(mode)&&mode.length===triangles.length&&mode.every(v=>Array.isArray(v)&&v.length===3&&v.every(Number.isFinite))))throw new Error('Invalid complex field samples.');
 return {nodes:nodes.map(p=>[...p]),triangles:triangles.map(t=>[...t]),real:f.real.map(m=>m.map(v=>[...v])),imag:f.imag.map(m=>m.map(v=>[...v]))};
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
