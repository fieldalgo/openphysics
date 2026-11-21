// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

// Form model for the public thermal.steady2d rectangle: lengths in mm, SI otherwise. The solver
// document is format 0.3: every value carries its unit. The form and saved projects (version 6)
// keep the inward heat flux under its registry name, as the document does (a positive value heats
// the plate).
export const SIDES=Object.freeze(['left','right','bottom','top']);
export const SIDE_TYPES=Object.freeze({insulated:'Insulated (zero flux)',temperature:'Fixed temperature',flux:'Inward heat flux',convection:'Convection'});
export const DEFAULT_THERMAL=Object.freeze({width:30,height:20,conductivity:12.5,source:0,nx:32,ny:16,
 sides:Object.freeze({left:Object.freeze({type:'temperature',temperature:280}),right:Object.freeze({type:'temperature',temperature:315}),bottom:Object.freeze({type:'insulated'}),top:Object.freeze({type:'insulated'})})});
const number=(value,name,{min=-Infinity,max=Infinity,positive=false,integer=false}={})=>{
 if(typeof value!=='number'||!Number.isFinite(value)||(integer&&!Number.isInteger(value))||value<min||value>max||(positive&&value<=0))throw new Error(`Invalid ${name}.`);
 return value;
};
export function validateSide(raw,side){
 if(!raw||!SIDE_TYPES[raw.type])throw new Error(`Choose a condition for the ${side} side.`);
 if(raw.type==='insulated')return {type:'insulated'};
 if(raw.type==='temperature')return {type:'temperature',temperature:number(raw.temperature,`${side} temperature [K]`,{min:0,max:1e5,positive:true})};
 if(raw.type==='flux')return {type:'flux',inward_heat_flux:number(raw.inward_heat_flux,`${side} inward heat flux [W/m²]`,{min:-1e9,max:1e9})};
 return {type:'convection',h:number(raw.h,`${side} heat transfer coefficient [W/(m²·K)]`,{min:0,max:1e7}),ambient:number(raw.ambient,`${side} ambient temperature [K]`,{min:0,max:1e5,positive:true})};
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
// A quantity string: the number as JavaScript writes it (the shortest text of the double) and its unit.
const q=(value,unit)=>`${value} ${unit}`;
export function heatDocument(raw){
 const t=validateThermal(raw),p={type:'thermal.steady2d',thermal_conductivity:q(t.conductivity,'W/(m K)'),
  heat_source_density:q(t.source,'W/m^3'),prescribed_temperature:{}};
 const flux={},convection={};
 for(const side of SIDES){const c=t.sides[side];
  if(c.type==='temperature')p.prescribed_temperature[side]=q(c.temperature,'K');
  if(c.type==='flux')flux[side]=q(c.inward_heat_flux,'W/m^2');
  if(c.type==='convection')convection[side]={heat_transfer_coefficient:q(c.h,'W/(m^2 K)'),ambient_temperature:q(c.ambient,'K')};
 }
 // Natural-condition keys select the boundary result format, so they appear only when used.
 if(Object.keys(flux).length)p.inward_heat_flux=flux;
 if(Object.keys(convection).length)p.convection=convection;
 return {openphysics:'0.3',name:'Workspace steady heat',geometry:{length_unit:'mm',depth:null,domain:{xmin:0,xmax:t.width,ymin:0,ymax:t.height}},materials:{},
  physics:{heat1:p},mesh:{subdivision_count:[t.nx,t.ny]},study:{type:'single'},results:{save_fields:true,plots:false}};
}
const fmt=v=>String(Math.round(v*1e6)/1e6);
export function sideText(c){
 if(c.type==='insulated')return 'insulated';
 if(c.type==='temperature')return `T = ${fmt(c.temperature)} K`;
 if(c.type==='flux')return `inward q = ${fmt(c.inward_heat_flux)} W/m²`;
 return `h = ${fmt(c.h)} W/(m²·K), T∞ = ${fmt(c.ambient)} K`;
}
export function thermalSummary(t){return `${fmt(t.width)} × ${fmt(t.height)} mm · k ${fmt(t.conductivity)} W/(m·K)${t.source?` · Q ${fmt(t.source)} W/m³`:''}`;}
