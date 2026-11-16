// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
import {shapeBounds,shapeCorners,polygonArea} from './workspace-shapes.mjs';

// Form model of the Joule heating application: named material regions on a rectangle in mm
// (a background material and up to eight shapes, later shapes win where they overlap), each
// material with a thermal conductivity and an electrical conductivity, constant or the
// linear_resistivity model, and one electric and one thermal condition per side. The solver
// document is format 0.3 with a version 1 geometry block; its physics is joule.temperature2d
// when a used material has the model and joule.steady2d otherwise. Projects (version 7) store
// these inputs; results stay in the tab.
export const SIDES=Object.freeze(['left','right','bottom','top']);
export const MAX_JOULE_SHAPES=8,MAX_JOULE_MATERIALS=6,MAX_JOULE_POINTS=12;
// Studio's cap on the Picard iteration count (joule_regions_api.MAX_ITERATIONS, capability limits.max_iterations).
export const MAX_ITERATIONS=500;
export const STEADY='joule.steady2d',TEMPERATURE='joule.temperature2d';
export const PAIRS=Object.freeze({[STEADY]:Object.freeze(['joule.steady2d-regions-result-v2','electric-joule2d-p1-node-cell-regions-v2']),
 [TEMPERATURE]:Object.freeze(['joule.temperature2d-regions-result-v2','electric-joule2d-temperature-p1-node-cell-regions-v2'])});
export const PAYLOAD='studio-joule-regions-v1';
export const ELECTRIC_TYPES=Object.freeze({insulating:'Insulating',potential:'Fixed potential',current:'Inward current density'});
export const THERMAL_TYPES=Object.freeze({insulated:'Insulated (zero flux)',temperature:'Fixed temperature',flux:'Inward heat flux',convection:'Convection'});
// The documented iteration defaults of joule.temperature2d; temperature_tolerance has no default
// in the document format, so the form starts it at the value of the two-material check.
export const ITERATION_DEFAULTS=Object.freeze({initial_temperature:300,relaxation_factor:0.5,temperature_tolerance:1e-9,relative_tolerance:1e-10,iteration_limit:100});
const linear=(sigma,alpha)=>Object.freeze({model:'linear_resistivity',reference_conductivity:sigma,reference_temperature:300,coefficient:alpha,tmin:250,tmax:600});
// The two-material strip of the region Joule checks: A on the left half, B on the right.
export const DEFAULT_JOULE=Object.freeze({width:2,height:1,background:'A',elementSize:0.125,
 shapes:Object.freeze([Object.freeze({name:'b',type:'rect',material:'B',x:1,y:0,w:1,h:1})]),
 materials:Object.freeze([Object.freeze({name:'A',k:1.5,sigma:linear(2000,0.004)}),Object.freeze({name:'B',k:0.25,sigma:linear(500,-0.003)})]),
 sides:Object.freeze({left:Object.freeze({electric:Object.freeze({type:'potential',potential:0.2}),thermal:Object.freeze({type:'temperature',temperature:300})}),
  right:Object.freeze({electric:Object.freeze({type:'potential',potential:0}),thermal:Object.freeze({type:'temperature',temperature:320})}),
  bottom:Object.freeze({electric:Object.freeze({type:'insulating'}),thermal:Object.freeze({type:'insulated'})}),
  top:Object.freeze({electric:Object.freeze({type:'insulating'}),thermal:Object.freeze({type:'insulated'})})}),
 iteration:ITERATION_DEFAULTS});
const NAME=/^[A-Za-z][A-Za-z0-9_-]{0,31}$/;
const number=(value,name,{min=-Infinity,max=Infinity,positive=false,integer=false}={})=>{
 if(typeof value!=='number'||!Number.isFinite(value)||(integer&&!Number.isInteger(value))||value<min||value>max||(positive&&value<=0))throw new Error(`Invalid ${name}.`);
 return value;
};
function validateSigma(raw,where){
 if(raw?.model==='constant')return {model:'constant',value:number(raw.value,`${where} electrical conductivity [S/m]`,{positive:true,max:1e12})};
 if(raw?.model!=='linear_resistivity')throw new Error(`${where}: choose a constant conductivity or the linear resistivity model.`);
 const m={model:'linear_resistivity',reference_conductivity:number(raw.reference_conductivity,`${where} reference conductivity [S/m]`,{positive:true,max:1e12}),
  reference_temperature:number(raw.reference_temperature,`${where} reference temperature [K]`,{positive:true,max:1e5}),
  coefficient:number(raw.coefficient,`${where} resistivity temperature coefficient [1/K]`,{min:-1,max:1}),
  tmin:number(raw.tmin,`${where} lowest valid temperature [K]`,{positive:true,max:1e5}),tmax:number(raw.tmax,`${where} highest valid temperature [K]`,{positive:true,max:1e5})};
 if(!(m.tmin<m.tmax))throw new Error(`${where}: the valid temperature range needs lowest < highest.`);
 if(m.reference_temperature<m.tmin||m.reference_temperature>m.tmax)throw new Error(`${where}: the reference temperature must lie in the valid range.`);
 for(const t of [m.tmin,m.tmax])if(!(1+m.coefficient*(t-m.reference_temperature)>0))throw new Error(`${where}: the resistivity must stay positive over the valid range (check the coefficient).`);
 return m;
}
export function validateMaterial(raw,index=0){
 const where=`Material ${index+1}`;
 if(!raw||typeof raw!=='object')throw new Error(`${where} is missing.`);
 if(typeof raw.name!=='string'||!NAME.test(raw.name)||/^physmat/i.test(raw.name))throw new Error(`${where}: name must start with a letter and use 1–32 letters, digits, _ or -.`);
 return {name:raw.name,k:number(raw.k,`${raw.name} thermal conductivity [W/(m·K)]`,{positive:true,max:1e5}),sigma:validateSigma(raw.sigma,raw.name)};
}
const cross=(o,a,b)=>(a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0]);
function properCross(p,q,r,s){const d1=cross(r,s,p),d2=cross(r,s,q),d3=cross(p,q,r),d4=cross(p,q,s);return ((d1>0&&d2<0)||(d1<0&&d2>0))&&((d3>0&&d4<0)||(d3<0&&d4>0));}
export function validateJouleShape(raw,index,domain,materials){
 const where=`Shape ${index+1}`;
 if(!raw||typeof raw!=='object')throw new Error(`${where} is missing.`);
 if(typeof raw.name!=='string'||!NAME.test(raw.name)||raw.name.toLowerCase()==='background')throw new Error(`${where}: name must start with a letter, use 1–32 letters, digits, _ or -, and not be "background".`);
 if(!materials.includes(raw.material))throw new Error(`${raw.name}: choose one of the defined materials.`);
 let shape;
 if(raw.type==='rect')shape={name:raw.name,type:'rect',material:raw.material,x:number(raw.x,`${raw.name} x [mm]`),y:number(raw.y,`${raw.name} y [mm]`),w:number(raw.w,`${raw.name} width [mm]`,{positive:true}),h:number(raw.h,`${raw.name} height [mm]`,{positive:true})};
 else if(raw.type==='circle')shape={name:raw.name,type:'circle',material:raw.material,cx:number(raw.cx,`${raw.name} centre x [mm]`),cy:number(raw.cy,`${raw.name} centre y [mm]`),r:number(raw.r,`${raw.name} radius [mm]`,{positive:true})};
 else if(raw.type==='polygon'){
  if(!Array.isArray(raw.points)||raw.points.length<3||raw.points.length>MAX_JOULE_POINTS)throw new Error(`${raw.name}: a polygon needs 3–${MAX_JOULE_POINTS} vertices.`);
  const points=raw.points.map((p,i)=>{if(!Array.isArray(p)||p.length!==2)throw new Error(`${raw.name}: vertex ${i+1} needs x and y.`);return [number(p[0],`${raw.name} vertex ${i+1} x`),number(p[1],`${raw.name} vertex ${i+1} y`)];});
  const n=points.length;
  if(new Set(points.map(p=>p.join(','))).size!==n)throw new Error(`${raw.name}: a polygon vertex is repeated.`);
  for(let i=0;i<n;i++)for(let j=i+2;j<n;j++){if(i===0&&j===n-1)continue;if(properCross(points[i],points[(i+1)%n],points[j],points[(j+1)%n]))throw new Error(`${raw.name}: polygon edges ${i+1} and ${j+1} cross.`);}
  if(!(polygonArea(points)>0))throw new Error(`${raw.name}: the polygon has no area.`);
  shape={name:raw.name,type:'polygon',material:raw.material,points};
 }else throw new Error(`${where}: type must be rect, circle or polygon.`);
 const b=shapeBounds(shape);
 if(b.xmin<0||b.ymin<0||b.xmax>domain.width||b.ymax>domain.height)throw new Error(`${shape.name} must stay inside the domain 0…${domain.width} mm × 0…${domain.height} mm.`);
 return shape;
}
function validateElectric(raw,side){
 if(raw?.type==='insulating')return {type:'insulating'};
 if(raw?.type==='potential')return {type:'potential',potential:number(raw.potential,`${side} potential [V]`,{min:-1e6,max:1e6})};
 if(raw?.type==='current')return {type:'current',current:number(raw.current,`${side} inward current density [A/m²]`,{min:-1e12,max:1e12})};
 throw new Error(`Choose an electric condition for the ${side} side.`);
}
function validateThermalSide(raw,side){
 if(raw?.type==='insulated')return {type:'insulated'};
 if(raw?.type==='temperature')return {type:'temperature',temperature:number(raw.temperature,`${side} temperature [K]`,{positive:true,max:1e5})};
 if(raw?.type==='flux')return {type:'flux',flux:number(raw.flux,`${side} inward heat flux [W/m²]`,{min:-1e12,max:1e12})};
 if(raw?.type==='convection')return {type:'convection',h:number(raw.h,`${side} heat transfer coefficient [W/(m²·K)]`,{min:0,max:1e7}),ambient:number(raw.ambient,`${side} ambient temperature [K]`,{positive:true,max:1e5})};
 throw new Error(`Choose a thermal condition for the ${side} side.`);
}
export function validateIteration(raw){
 if(!raw||typeof raw!=='object')throw new Error('Iteration settings are missing.');
 return {initial_temperature:number(raw.initial_temperature,'initial temperature [K]',{positive:true,max:1e5}),
  relaxation_factor:number(raw.relaxation_factor,'relaxation factor',{positive:true,max:1}),
  temperature_tolerance:number(raw.temperature_tolerance,'temperature tolerance [K]',{positive:true,max:1e3}),
  relative_tolerance:number(raw.relative_tolerance,'relative tolerance',{positive:true,max:1}),
  iteration_limit:number(raw.iteration_limit,'iteration limit',{min:1,max:MAX_ITERATIONS,integer:true})};
}
// Structural checks: every value finite and in range, names unique, shapes inside the domain.
export function validateJoule(raw){
 if(!raw||typeof raw!=='object')throw new Error('Joule heating inputs are missing.');
 const j={width:number(raw.width,'domain width [mm]',{positive:true,min:1e-3,max:1e4}),height:number(raw.height,'domain height [mm]',{positive:true,min:1e-3,max:1e4})};
 if(!Array.isArray(raw.materials)||raw.materials.length<1||raw.materials.length>MAX_JOULE_MATERIALS)throw new Error(`Define 1–${MAX_JOULE_MATERIALS} materials.`);
 j.materials=raw.materials.map(validateMaterial);
 const names=j.materials.map(m=>m.name);
 if(new Set(names.map(n=>n.toLowerCase())).size!==names.length)throw new Error('Material names must be different.');
 if(!names.includes(raw.background))throw new Error('Choose the background material from the defined materials.');
 j.background=raw.background;
 if(!Array.isArray(raw.shapes)||raw.shapes.length>MAX_JOULE_SHAPES)throw new Error(`A design has at most ${MAX_JOULE_SHAPES} shapes.`);
 j.shapes=raw.shapes.map((s,i)=>validateJouleShape(s,i,j,names));
 if(new Set(j.shapes.map(s=>s.name.toLowerCase())).size!==j.shapes.length)throw new Error('Shape names must be different.');
 j.elementSize=number(raw.elementSize,'element size [mm]',{positive:true,max:Math.min(j.width,j.height)});
 j.sides={};
 for(const side of SIDES)j.sides[side]={electric:validateElectric(raw.sides?.[side]?.electric,side),thermal:validateThermalSide(raw.sides?.[side]?.thermal,side)};
 j.iteration=validateIteration(raw.iteration);
 return j;
}
// The materials the regions use, in table order.
export function usedMaterials(j){const used=new Set([j.background,...j.shapes.map(s=>s.material)]);return j.materials.filter(m=>used.has(m.name));}
export function jouleKind(j){return usedMaterials(j).some(m=>m.sigma.model==='linear_resistivity')?TEMPERATURE:STEADY;}
// Run readiness beyond structure: a potential fixes the electric level, a temperature or
// convection with h > 0 the thermal level; model ranges must hold every given temperature.
export function jouleBlock(j,limits=null){
 if(!SIDES.some(s=>j.sides[s].electric.type==='potential'))return 'Fix the potential of a side; otherwise the electric potential is undetermined.';
 if(!SIDES.some(s=>j.sides[s].thermal.type==='temperature'||(j.sides[s].thermal.type==='convection'&&j.sides[s].thermal.h>0)))return 'Fix the temperature of a side or add convection with h > 0; otherwise the temperature level is undetermined.';
 // adjacent sides that both fix a value meet at a corner node, which can hold one value only
 for(const [kind,type,key,what] of [['electric','potential','potential','potentials'],['thermal','temperature','temperature','temperatures']])
  for(const a of ['left','right'])for(const b of ['bottom','top']){const x=j.sides[a][kind],y=j.sides[b][kind];
   if(x.type===type&&y.type===type&&x[key]!==y[key])return `The ${a} and ${b} sides meet at a corner with two different fixed ${what}.`;}
 const models=usedMaterials(j).filter(m=>m.sigma.model==='linear_resistivity');
 if(models.length){
  const lo=Math.max(...models.map(m=>m.sigma.tmin)),hi=Math.min(...models.map(m=>m.sigma.tmax));
  if(lo>hi)return 'The valid temperature ranges of the model materials do not overlap.';
  const given=[['initial temperature',j.iteration.initial_temperature],...SIDES.flatMap(s=>{const t=j.sides[s].thermal;return t.type==='temperature'?[[`${s} temperature`,t.temperature]]:t.type==='convection'?[[`${s} ambient temperature`,t.ambient]]:[];})];
  const out=given.find(([,t])=>t<lo||t>hi);
  if(out)return `The ${out[0]} ${out[1]} K lies outside the valid range ${lo}…${hi} K of the model materials.`;
 }
 if(limits&&j.shapes.length>limits.max_shapes)return `The design has ${j.shapes.length} shapes; this server allows ${limits.max_shapes}.`;
 return '';
}
const q=(value,unit)=>`${value} ${unit}`;
function sigmaDocument(s){
 if(s.model==='constant')return q(s.value,'S/m');
 return {model:'linear_resistivity',reference_conductivity:q(s.reference_conductivity,'S/m'),reference_temperature:q(s.reference_temperature,'K'),
  resistivity_temperature_coefficient:q(s.coefficient,'1/K'),valid:{temperature:[q(s.tmin,'K'),q(s.tmax,'K')]}};
}
function feature(s){
 const base={name:s.name,type:s.type};
 if(s.type==='rect')return {...base,x:s.x,y:s.y,w:s.w,h:s.h,material:s.material};
 if(s.type==='circle')return {...base,cx:s.cx,cy:s.cy,r:s.r,material:s.material};
 return {...base,points:s.points.map(p=>[...p]),material:s.material};
}
// The format 0.3 document of the inputs: lengths in mm, other values in SI, each with its unit.
export function jouleDocument(raw){
 const j=validateJoule(raw),kind=jouleKind(j);
 const p={type:kind,prescribed_electric_potential:{},prescribed_temperature:{}};
 const current={},flux={},convection={};
 for(const side of SIDES){
  const e=j.sides[side].electric,t=j.sides[side].thermal;
  if(e.type==='potential')p.prescribed_electric_potential[side]=q(e.potential,'V');
  if(e.type==='current')current[side]=q(e.current,'A/m^2');
  if(t.type==='temperature')p.prescribed_temperature[side]=q(t.temperature,'K');
  if(t.type==='flux')flux[side]=q(t.flux,'W/m^2');
  if(t.type==='convection')convection[side]={heat_transfer_coefficient:q(t.h,'W/(m^2 K)'),ambient_temperature:q(t.ambient,'K')};
 }
 if(Object.keys(current).length)p.inward_current_density=current;
 if(Object.keys(flux).length)p.inward_heat_flux=flux;
 if(Object.keys(convection).length)p.convection=convection;
 if(kind===TEMPERATURE){const it=j.iteration;p.initial_temperature=q(it.initial_temperature,'K');
  p.iteration={relaxation_factor:it.relaxation_factor,temperature_tolerance:q(it.temperature_tolerance,'K'),relative_tolerance:it.relative_tolerance,iteration_limit:it.iteration_limit};}
 const materials={};for(const m of usedMaterials(j))materials[m.name]={electrical_conductivity:sigmaDocument(m.sigma),thermal_conductivity:q(m.k,'W/(m K)')};
 return {openphysics:'0.3',name:'Workspace Joule heating',
  geometry:{version:1,components:{xs:{dimension:'2d',length_unit:'mm',depth:null,domain:{xmin:0,xmax:j.width,ymin:0,ymax:j.height},
   background:{material:j.background},features:j.shapes.map(feature)}}},
  materials,physics:{j:p},mesh:{element_size:q(j.elementSize,'mm')},study:{type:'single'},results:{save_fields:true,plots:false}};
}
const fmt=v=>String(Number(v.toPrecision(6)));
export function sigmaText(s){return s.model==='constant'?`σ ${fmt(s.value)} S/m`:`σ(T) = ${fmt(s.reference_conductivity)} S/m / (1 + ${fmt(s.coefficient)} (T − ${fmt(s.reference_temperature)} K)), ${fmt(s.tmin)}…${fmt(s.tmax)} K`;}
export function electricText(e){return e.type==='insulating'?'insulating':e.type==='potential'?`V = ${fmt(e.potential)} V`:`inward J = ${fmt(e.current)} A/m²`;}
export function thermalText(t){return t.type==='insulated'?'insulated':t.type==='temperature'?`T = ${fmt(t.temperature)} K`:t.type==='flux'?`inward q = ${fmt(t.flux)} W/m²`:`h = ${fmt(t.h)} W/(m²·K), T∞ = ${fmt(t.ambient)} K`;}
export function jouleSummary(j){return `${fmt(j.width)} × ${fmt(j.height)} mm · ${j.shapes.length} shape${j.shapes.length===1?'':'s'} on ${j.background} · ${jouleKind(j)}`;}
function uniqueName(base,used){const taken=new Set(used.map(n=>n.toLowerCase()));for(let i=1;;i++){const name=`${base}${i}`;if(!taken.has(name.toLowerCase()))return name;}}
// A new shape in the middle quarter of the domain, of the first material.
export function newJouleShape(type,j){
 const name=uniqueName(type==='rect'?'rect':type==='circle'?'circle':'poly',j.shapes.map(s=>s.name)),material=j.materials[0].name;
 const cx=j.width/2,cy=j.height/2,a=Math.min(j.width,j.height)/4;
 if(type==='rect')return {name,type,material,x:cx-a,y:cy-a,w:2*a,h:2*a};
 if(type==='circle')return {name,type,material,cx,cy,r:a};
 return {name,type,material,points:[[cx-a,cy-a],[cx+a,cy-a],[cx,cy+a]]};
}
export function newJouleMaterial(j){return {name:uniqueName('M',j.materials.map(m=>m.name)),k:1,sigma:{model:'constant',value:1000}};}

// ---- Results ---------------------------------------------------------------------------------
const NODAL=Object.freeze(['temperature','electric_potential']);
export const RESULT_FIELDS=Object.freeze({temperature:['Temperature T','K'],electric_potential:['Electric potential V','V'],
 current_magnitude:['Current density |J|','A/m²'],joule_power_density:['Joule power density','W/m³'],heat_flux_magnitude:['Heat flux |q|','W/m²']});
const REQUIRED=['node_coordinates','triangles','triangle_regions','electric_potential','current_density','joule_power_density','temperature','heat_flux'];
const fail=message=>{throw new Error('Joule result: '+message);};
const isInt=v=>Number.isSafeInteger(v)&&v>=0;
// Shape and ownership checks of a finished job's payload before anything is drawn.
export function checkJoulePayload(raw,owner,kind){
 if(!raw||typeof raw!=='object'||raw.payload_format!==PAYLOAD)fail('unsupported payload format');
 for(const key of ['job','result_id','client_revision','request_seq'])if(raw[key]!==owner[key])fail('ownership mismatch');
 const pair=PAIRS[kind];if(!pair||raw.result_format!==pair[0]||raw.field_layout!==pair[1]||raw.kind!==kind)fail('result/layout pair');
 if(typeof raw.length_unit!=='string'||!(raw.display_length_in_m>0)||!Number.isFinite(raw.display_length_in_m))fail('display length');
 const a=raw.arrays;if(!a||typeof a!=='object')fail('arrays missing');
 for(const key of REQUIRED)if(!Array.isArray(a[key]))fail(key+' missing');
 const N=a.node_coordinates.length,M=a.triangles.length;
 if(N<3||!a.node_coordinates.every(p=>Array.isArray(p)&&p.length===2&&p.every(Number.isFinite)))fail('node_coordinates');
 if(M<1||!a.triangles.every(t=>Array.isArray(t)&&t.length===3&&t.every(v=>isInt(v)&&v<N)))fail('triangles');
 for(const key of NODAL)if(a[key].length!==N||!a[key].every(Number.isFinite))fail(key);
 for(const key of ['current_density','heat_flux'])if(a[key].length!==M||!a[key].every(v=>Array.isArray(v)&&v.length===2&&v.every(Number.isFinite)))fail(key);
 if(a.joule_power_density.length!==M||!a.joule_power_density.every(Number.isFinite))fail('joule_power_density');
 const s=raw.summary,names=s?.region_names;
 if(!Array.isArray(names)||!names.length||a.triangle_regions.length!==M||!a.triangle_regions.every(v=>isInt(v)&&v<names.length))fail('triangle_regions');
 if(!s.balance||typeof s.balance!=='object'||!Array.isArray(s.iterations))fail('summary');
 return raw;
}
function regionEdges(triangles,ids){
 const seen=new Map(),edges=[];
 triangles.forEach((t,i)=>{for(let k=0;k<3;k++){const a=t[k],b=t[(k+1)%3],key=a<b?a+','+b:b+','+a,prior=seen.get(key);
  if(prior===undefined)seen.set(key,i);else if(ids[prior]!==ids[i])edges.push([a,b]);}});
 return edges;
}
// A model for ThermalStudio.draw/sample: coordinates in the document's length unit.
export function jouleViewModel(payload,field='temperature'){
 const a=payload.arrays,scale=payload.display_length_in_m,info=RESULT_FIELDS[field];
 if(!info)fail('unknown field');
 const nodes=a.node_coordinates.map(p=>[p[0]/scale,p[1]/scale]);
 const nodal=NODAL.includes(field);
 const values=nodal?a[field].slice():field==='current_magnitude'?a.current_density.map(v=>Math.hypot(v[0],v[1])):field==='heat_flux_magnitude'?a.heat_flux.map(v=>Math.hypot(v[0],v[1])):a.joule_power_density.slice();
 if(!values.every(Number.isFinite))fail('field overflow');
 let min=Infinity,max=-Infinity,xmin=Infinity,xmax=-Infinity,ymin=Infinity,ymax=-Infinity;
 for(const v of values){min=Math.min(min,v);max=Math.max(max,v);}
 for(const [x,y] of nodes){xmin=Math.min(xmin,x);xmax=Math.max(xmax,x);ymin=Math.min(ymin,y);ymax=Math.max(ymax,y);}
 return {nodes,triangles:a.triangles,values,min,max,unit:info[1],field:info[0],nodal,domain:{xmin,xmax,ymin,ymax},lengthLabel:payload.length_unit,
  flux:field==='heat_flux_magnitude'?a.heat_flux:a.current_density,regions:{ids:a.triangle_regions,edges:regionEdges(a.triangles,a.triangle_regions)}};
}
const BALANCE=[['inward_electric_power_per_depth','Supplied electric power'],['joule_power_per_depth','Joule power'],['outward_heat_rate_per_depth','Outward heat'],
 ['minimum_temperature','Minimum temperature'],['maximum_temperature','Maximum temperature']];
// [label, text] rows of the balances and the terminal currents (per metre of depth).
export function balanceRows(summary){
 const b=summary.balance,rows=[],text=v=>v&&Number.isFinite(v.value)?`${Number(v.value.toPrecision(7))} ${v.unit}`:'—';
 for(const [key,label] of BALANCE)if(b[key])rows.push([label,text(b[key])]);
 for(const [name,v] of Object.entries(b.outward_current_per_depth||{}))rows.push([`Current out of ${name}`,text(v)]);
 return rows;
}
export function iterationRows(summary){
 return summary.iterations.map(r=>[r.iteration_count,r.temperature_change?.value,r.relative_electrical_conductivity_change?.value,r.maximum_temperature?.value]);
}

// ---- Run controller ----------------------------------------------------------------------------
// Validate, then run, then poll the job and check its payload. request(method, url, body)
// returns the reply object or throws an Error with the server's message. A newer call or
// stop() makes an older one return quietly.
export class JouleRunner{
 constructor({request,wait=ms=>new Promise(r=>setTimeout(r,ms)),onState=()=>{},limitMs=600000,now=()=>Date.now()}){
  Object.assign(this,{request,wait,onState,limitMs,now});this.generation=0;this.revision=0;this.sequence=0;this.busy=false;
 }
 stop(){this.generation++;this.busy=false;}
 async capability(){
  const caps=await this.request('GET','/api/capabilities');const c=caps?.[TEMPERATURE],s=caps?.[STEADY];
  if(!c||!s||c.validate!=='/api/joule/validate'||c.run!=='/api/joule/run'||c.geometry!=='regions')throw new Error('This Studio server does not run Joule heating.');
  return {run_enabled:c.run_enabled===true&&s.run_enabled===true,limits:c.limits};
 }
 async calculate(doc){
  const token=++this.generation,active=()=>token===this.generation,kind=doc.physics.j.type;this.busy=true;
  const tags=()=>({client_revision:++this.revision,request_seq:++this.sequence});
  try{
   this.onState({phase:'validating',message:'Validating the Joule heating inputs…'});
   const checked=await this.request('POST','/api/joule/validate',{doc,...tags()});if(!active())return null;
   if(checked?.ok!==true)throw new Error(checked?.error?.message||'The document was refused.');
   this.onState({phase:'running',message:'Solving Joule heating…'});
   const ownerTags=tags(),job=await this.request('POST','/api/joule/run',{doc,...ownerTags});if(!active())return null;
   if(typeof job?.job!=='string'||job.kind!==kind||job.client_revision!==ownerTags.client_revision||job.request_seq!==ownerTags.request_seq)throw new Error('The run reply does not match this request.');
   const deadline=this.now()+this.limitMs;
   while(active()){
    await this.wait(500);if(!active())return null;
    const state=await this.request('GET','/api/jobs/'+encodeURIComponent(job.job));if(!active())return null;
    if(state?.job!==job.job||state.result_id!==job.result_id)throw new Error('The job status does not match this run.');
    if(state.status==='error')throw new Error(state.error?.message||'The Joule job failed.');
    if(state.status==='done'){
     const raw=await this.request('GET','/api/jobs/'+encodeURIComponent(job.job)+'/result');if(!active())return null;
     return checkJoulePayload(raw,{job:job.job,result_id:job.result_id,client_revision:job.client_revision,request_seq:job.request_seq},kind);
    }
    if(state.status!=='running')throw new Error('Unknown job status.');
    if(this.now()>=deadline)throw new Error('Stopped waiting after ten minutes; the server may still be computing.');
   }
   return null;
  }finally{if(active())this.busy=false;}
 }
}
