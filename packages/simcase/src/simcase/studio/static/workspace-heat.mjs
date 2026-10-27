// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

// Form model for the public thermal.steady2d rectangle: lengths in mm, SI otherwise.
export const SIDES=Object.freeze(['left','right','bottom','top']);
export const SIDE_TYPES=Object.freeze({insulated:'Insulated (zero flux)',temperature:'Fixed temperature',flux:'Outward heat flux',convection:'Convection'});
export const DEFAULT_THERMAL=Object.freeze({width:30,height:20,conductivity:12.5,source:0,nx:32,ny:16,
 sides:Object.freeze({left:Object.freeze({type:'temperature',temperature:280}),right:Object.freeze({type:'temperature',temperature:315}),bottom:Object.freeze({type:'insulated'}),top:Object.freeze({type:'insulated'})})});
const number=(value,name,{min=-Infinity,max=Infinity,positive=false,integer=false}={})=>{
 if(typeof value!=='number'||!Number.isFinite(value)||(integer&&!Number.isInteger(value))||value<min||value>max||(positive&&value<=0))throw new Error(`Invalid ${name}.`);
 return value;
};
export function validateSide(raw,side){
 if(!raw||!SIDE_TYPES[raw.type])throw new Error(`Choose a condition for the ${side} side.`);
 if(raw.type==='insulated')return {type:'insulated'};
 if(raw.type==='temperature')return {type:'temperature',temperature:number(raw.temperature,`${side} temperature [K]`,{min:0,max:1e5})};
 if(raw.type==='flux')return {type:'flux',flux:number(raw.flux,`${side} outward heat flux [W/m²]`,{min:-1e9,max:1e9})};
 return {type:'convection',h:number(raw.h,`${side} heat transfer coefficient [W/(m²·K)]`,{min:0,max:1e7}),ambient:number(raw.ambient,`${side} ambient temperature [K]`,{min:0,max:1e5})};
}
// Structural checks plus the public contract's anchor and corner rules; mesh limits come from the server.
export function validateThermal(raw){
 if(!raw||typeof raw!=='object')throw new Error('Heat inputs are missing.');
 const t={width:number(raw.width,'width [mm]',{min:1e-3,max:1e4}),height:number(raw.height,'height [mm]',{min:1e-3,max:1e4}),
  conductivity:number(raw.conductivity,'thermal conductivity [W/(m·K)]',{positive:true,max:1e5}),source:number(raw.source,'heat source [W/m³]',{min:-1e12,max:1e12}),
  nx:number(raw.nx,'x divisions',{min:1,max:400,integer:true}),ny:number(raw.ny,'y divisions',{min:1,max:400,integer:true}),sides:{}};
 for(const side of SIDES)t.sides[side]=validateSide(raw.sides?.[side],side);
 return t;
}
export function thermalBlock(t,limits=null){
 const fixed=SIDES.filter(s=>t.sides[s].type==='temperature');
 if(!fixed.length&&!SIDES.some(s=>t.sides[s].type==='convection'&&t.sides[s].h>0))return 'Fix the temperature of a side or add convection with h > 0; otherwise the temperature level is undetermined.';
 for(const a of ['left','right'])for(const b of ['bottom','top'])
  if(fixed.includes(a)&&fixed.includes(b)&&t.sides[a].temperature!==t.sides[b].temperature)return `The ${a} and ${b} sides meet at a corner with two different fixed temperatures.`;
 if(limits&&((t.nx+1)*(t.ny+1)>limits.max_nodes||2*t.nx*t.ny>limits.max_triangles))return `The mesh has ${(t.nx+1)*(t.ny+1)} nodes and ${2*t.nx*t.ny} triangles; this server allows ${limits.max_nodes} and ${limits.max_triangles}.`;
 return '';
}
export function heatDocument(raw){
 const t=validateThermal(raw),p={type:'thermal.steady2d',conductivity_w_mk:t.conductivity,heat_source_w_m3:t.source,dirichlet_temperature_k:{}};
 const flux={},convection={};
 for(const side of SIDES){const c=t.sides[side];
  if(c.type==='temperature')p.dirichlet_temperature_k[side]=c.temperature;
  if(c.type==='flux')flux[side]=c.flux;
  if(c.type==='convection')convection[side]={h_w_m2k:c.h,ambient_temperature_k:c.ambient};
 }
 // Natural-condition keys select the v2 result format, so they appear only when used.
 if(Object.keys(flux).length)p.outward_flux_w_m2=flux;
 if(Object.keys(convection).length)p.convection=convection;
 return {openphysics:'0.2',name:'Workspace steady heat',units:{length:'mm',temperature:'K'},geometry:{domain:{xmin:0,xmax:t.width,ymin:0,ymax:t.height}},materials:{},
  physics:{heat1:p},mesh:{subdivisions:[t.nx,t.ny]},study:{type:'single'},results:{save_fields:true,plots:false}};
}
const fmt=v=>String(Math.round(v*1e6)/1e6);
export function sideText(c){
 if(c.type==='insulated')return 'insulated';
 if(c.type==='temperature')return `T = ${fmt(c.temperature)} K`;
 if(c.type==='flux')return `outward q = ${fmt(c.flux)} W/m²`;
 return `h = ${fmt(c.h)} W/(m²·K), T∞ = ${fmt(c.ambient)} K`;
}
export function thermalSummary(t){return `${fmt(t.width)} × ${fmt(t.height)} mm · k ${fmt(t.conductivity)} W/(m·K)${t.source?` · Q ${fmt(t.source)} W/m³`:''}`;}
