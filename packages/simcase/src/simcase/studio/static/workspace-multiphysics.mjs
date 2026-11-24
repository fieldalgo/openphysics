// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

// Multiphysics models (contract D2): pure functions over the document tree itself.
// The workspace keeps a multiphysics model as its document: physics entries, couplings and
// study.loops are edited in place and the whole tree is sent to /api/multiphysics/*. Nothing
// here runs physics; the server's check (the rules of simcase validate) decides what is valid,
// and these functions put its diagnostics into words and places on screen.

export const ENVELOPE='0.3/multiphysics.1';
export const SIDES=Object.freeze(['left','right','bottom','top']);
//: physmat's thermo-optic model of the two library materials the coupled modes input reads
export const PHYSMAT_THERMO_OPTIC=Object.freeze({'physmat:Si':Object.freeze({label:'Silicon',coefficient:1.8e-4,reference:300}),'physmat:SiO2':Object.freeze({label:'Silica',coefficient:1.0e-5,reference:300})});
const LIBRARY_NAMES={'physmat:Si':'Silicon','physmat:SiO2':'Silica','physmat:Si3N4':'Silicon nitride','physmat:vacuum':'Vacuum'};
const QUANTITY_WORDS={joule_power_density:'Joule heat',heat_flux:'heat flux',electric_potential:'electric potential',effective_index:'effective index',current_density:'current density',electric_field:'electric field'};
const LOCATION_WORDS={node:'per node',element:'per triangle',scalar:'one value per mode',grid:'per grid cell'};
const clone=x=>JSON.parse(JSON.stringify(x));
const isObject=x=>x!==null&&typeof x==='object'&&!Array.isArray(x);

// ---- names and words ------------------------------------------------------------------------
export function quantityWords(quantity){return QUANTITY_WORDS[quantity]||String(quantity).replace(/_/g,' ');}
export function unitText(unit){return String(unit).replace(/\^2/g,'²').replace(/\^3/g,'³').replace(/\^-1/g,'⁻¹').replace(/\bum\b/g,'µm');}
export function locationWords(location){return LOCATION_WORDS[location]||location;}
// "heat1" -> "Heat 1"; another name is shown as written
export function physicsLabel(name){const m=/^([a-z]+)_?(\d+)$/.exec(String(name));return m?m[1][0].toUpperCase()+m[1].slice(1)+' '+m[2]:String(name);}
export function physicsNames(doc){return isObject(doc?.physics)?Object.keys(doc.physics):[];}
export function couplingNames(doc){return isObject(doc?.couplings)?Object.keys(doc.couplings):[];}
// the catalog of installed types from /api/multiphysics/capabilities: type -> {label, ports, ...}
export function kindCatalog(caps){
 const types=new Map(),providers=[];
 for(const p of caps?.providers||[]){
  providers.push({name:p.name,version:p.version,status:p.status,error:p.error,types:(p.types||[]).map(t=>t.type)});
  for(const t of p.types||[])if(!types.has(t.type))types.set(t.type,{...t,provider:p.name});
 }
 return {types,providers};
}
export function portsOf(doc,catalog,name){const type=doc?.physics?.[name]?.type;return catalog.types.get(type)?.ports||[];}
export function findPort(doc,catalog,spec){
 const [physics,port]=splitSpec(spec);if(!(physics in (doc.physics||{})))return null;
 return portsOf(doc,catalog,physics).find(p=>p.name===port)||null;
}
export function splitSpec(spec){const s=String(spec??''),i=s.indexOf('.');return i<0?[s,'']:[s.slice(0,i),s.slice(i+1)];}
export function portLabel(spec){const [physics,port]=splitSpec(spec);return `${physicsLabel(physics)} ${quantityWords(port)}`;}
export function couplingTitle(doc,name){const c=doc.couplings?.[name];if(!isObject(c))return name;return `${portLabel(c.from)} → ${portLabel(c.to)}`;}

// ---- the envelope ---------------------------------------------------------------------------
// A document with couplings or physics of two kinds is a multiphysics document; one with one
// kind and no couplings is written as format 0.3. Empty couplings and loops are left out. Only
// those two spellings are switched: another format is kept, so the check refuses it by name.
// Applied after an edit that adds or removes physics, couplings or loops, never on open.
export function normalizeEnvelope(doc){
 if(doc?.openphysics!=='0.3'&&doc?.openphysics!==ENVELOPE)return clone(doc);
 const next=clone(doc);
 if(isObject(next.couplings)&&!Object.keys(next.couplings).length)delete next.couplings;
 if(isObject(next.study)&&Array.isArray(next.study.loops)&&!next.study.loops.length)delete next.study.loops;
 if(isObject(next.study)&&!Object.keys(next.study).length)delete next.study;
 const types=new Set(Object.values(next.physics||{}).map(p=>p?.type));
 next.openphysics=(couplingNames(next).length||types.size>1)?ENVELOPE:'0.3';
 return next;
}
export const isMultiphysics=doc=>doc?.openphysics===ENVELOPE;

// ---- physics --------------------------------------------------------------------------------
export function newPhysicsName(doc,prefix){let i=1;while(`${prefix}${i}` in (doc.physics||{}))i++;return `${prefix}${i}`;}
// {doc, name, becameMultiphysics}: the entry the type starts with, under the next free name
export function addPhysics(doc,typeInfo){
 if(!typeInfo?.addable)throw new Error(`${typeInfo?.type||'This physics'} ${typeInfo?.reason||'cannot be added here'}.`);
 const name=newPhysicsName(doc,typeInfo.prefix),next=clone(doc);next.physics={...(next.physics||{}),[name]:clone(typeInfo.entry)};
 const out=normalizeEnvelope(next);return {doc:out,name,becameMultiphysics:!isMultiphysics(doc)&&isMultiphysics(out)};
}
// The couplings that name the physics stay, and the check shows them as problems to fix.
export function removePhysics(doc,name){const next=clone(doc);delete next.physics[name];return normalizeEnvelope(next);}

// ---- couplings ------------------------------------------------------------------------------
export function couplingFileName(doc,from,to){
 const base=`${splitSpec(from)[0]}_to_${splitSpec(to)[0]}`;let name=base,i=2;
 while(name in (doc.couplings||{}))name=`${base}_${i++}`;return name;
}
// What the From picker lists: every output port; one value per mode is not a field to send.
// (Which outputs a kind sends to couplings is the engine's check; the To list greys every
// input that cannot take the chosen output.)
export function sourceChoices(doc,catalog){
 const out=[];
 for(const name of physicsNames(doc))for(const port of portsOf(doc,catalog,name))if(port.direction==='output'){
  const ok=port.location==='node'||port.location==='element';
  out.push({spec:`${name}.${port.name}`,label:`${physicsLabel(name)} ${quantityWords(port.name)}`,port,ok,
   // reason: the short words the From list shows; detail: the longer sentence its tooltip gives
   reason:ok?null:port.location==='scalar'?'single numbers, not a map':`${locationWords(port.location)}, not on the mesh`,
   detail:ok?null:`${physicsLabel(name)} ${quantityWords(port.name)} is ${locationWords(port.location)}, not a field on the mesh`});
 }
 return out;
}
// The From list of a coupling added for one input (`to`): only the outputs that input can take
// (pairProblem null), so a temperature input is never offered one value per mode. Without `to`,
// every output, the ones that are not fields greyed with their reason (sourceChoices).
export function sourceChoicesFor(doc,catalog,to){
 const all=sourceChoices(doc,catalog);
 return to?all.filter(s=>s.ok&&pairProblem(doc,catalog,s.spec,to)===null):all;
}
// Why `to` cannot take `from` (null when it can): the rules the engine checks, in words.
export function pairProblem(doc,catalog,from,to){
 const out=findPort(doc,catalog,from),inp=findPort(doc,catalog,to);
 if(!out||out.direction!=='output')return 'choose an output to send from';
 if(!inp||inp.direction!=='input')return 'not an input';
 if(splitSpec(from)[0]===splitSpec(to)[0])return 'a physics cannot feed itself';
 if(out.quantity!==inp.quantity)return `${quantityWords(inp.quantity)} is not ${/^[aeiou]/.test(quantityWords(out.quantity))?'an':'a'} ${quantityWords(out.quantity)}`;
 if(out.unit!==inp.unit)return `unit ${unitText(out.unit)}, this input expects ${unitText(inp.unit)}`;
 if(!(out.location===inp.location||(out.location==='node'&&inp.location==='element')))return `${locationWords(out.location)} values cannot feed an input ${locationWords(inp.location)}`;
 if((inp.combine||'single')==='single'){
  const taken=couplingNames(doc).find(c=>doc.couplings[c]?.to===to);
  if(taken)return `Already receives ${portLabel(doc.couplings[taken].from)}; this input takes one source.`;
 }
 return null;
}
// What the To picker lists for a chosen output: every input port, compatible or with its reason.
export function targetChoices(doc,catalog,from){
 const out=[];
 for(const name of physicsNames(doc))for(const port of portsOf(doc,catalog,name))if(port.direction==='input'){
  const spec=`${name}.${port.name}`,reason=pairProblem(doc,catalog,from,spec);
  out.push({spec,label:`${physicsLabel(name)} ${quantityWords(port.name)}`,port,ok:!reason,reason});
 }
 return out;
}
// The note the dialog shows for a pair (how the values arrive).
export function transferNote(doc,catalog,from,to){
 const out=findPort(doc,catalog,from),inp=findPort(doc,catalog,to);
 const base='Same mesh (both use Mesh 1)';
 if(out&&inp&&out.location==='node'&&inp.location==='element')return base+' · each triangle gets the mean of its 3 nodes';
 return base+' · values arrive unchanged';
}
export function addCoupling(doc,catalog,from,to){
 const problem=pairProblem(doc,catalog,from,to);if(problem)throw new Error(problem);
 const name=couplingFileName(doc,from,to),next=clone(doc);next.couplings={...(next.couplings||{}),[name]:{from,to,transfer:'same_mesh'}};
 return {doc:normalizeEnvelope(next),name};
}
export function removeCoupling(doc,name){const next=clone(doc);delete next.couplings[name];return normalizeEnvelope(next);}
// The coupling an unconnected input could obviously take: the first compatible output.
export function suggestedCouplings(doc,catalog){
 const out=[];
 for(const name of physicsNames(doc))for(const port of portsOf(doc,catalog,name)){
  if(port.direction!=='input')continue;const to=`${name}.${port.name}`;
  if(couplingNames(doc).some(c=>doc.couplings[c]?.to===to))continue;
  const source=sourceChoices(doc,catalog).find(s=>s.ok&&!pairProblem(doc,catalog,s.spec,to));
  if(source)out.push({from:source.spec,to});
 }
 return out;
}
export function suggestionText(s){
 const [target]=splitSpec(s.to),[source]=splitSpec(s.from);
 const why=splitSpec(s.to)[1]==='temperature'&&/^modes/.test(target)?' so the refractive index follows the heater':'';
 return `${physicsLabel(target)} can take its ${quantityWords(splitSpec(s.to)[1])} from ${physicsLabel(source)}. Connect ${portLabel(s.from)} to ${portLabel(s.to)}${why}.`;
}

// ---- loops ----------------------------------------------------------------------------------
// Accept iteration step: the loop entry the engine proposed in its cycle diagnostic.
export function acceptLoop(doc,proposal){
 const existing=loopIndexOf(doc,proposal.physics||[]);if(existing>=0)return {doc:clone(doc),index:existing,already:true};
 const next=clone(doc);next.study=isObject(next.study)?next.study:{type:'single'};
 next.study.loops=[...(Array.isArray(next.study.loops)?next.study.loops:[]),clone(proposal)];
 return {doc:next,index:next.study.loops.length-1};
}
export function removeLoop(doc,index){const next=clone(doc);next.study.loops.splice(index,1);return normalizeEnvelope(next);}
export function loopText(loop){return `fixed point · up to ${loop.max_iterations} · relaxation ${loop.relaxation}`;}
export function loopIndexOf(doc,members){
 const loops=Array.isArray(doc?.study?.loops)?doc.study.loops:[],key=[...members].sort().join('\u0000');
 return loops.findIndex(l=>Array.isArray(l?.physics)&&[...l.physics].sort().join('\u0000')===key);
}

// ---- materials ------------------------------------------------------------------------------
function geometryBlock(doc){const g=doc?.geometry;if(!isObject(g))return null;return g.version===1&&isObject(g.components)?Object.values(g.components)[0]:g;}
export function geometryOf(doc){return geometryBlock(doc);}
// The graphics footer: the geometry's length unit by name (µm), or that it is not set.
export function lengthsNote(doc){const u=geometryBlock(doc)?.length_unit;return (typeof u==='string'&&u.trim()?`Lengths in ${unitText(u.trim())}`:'Lengths in the geometry’s unit (not set)')+'; other values carry their units. Run solves every physics in solve order.';}
// Each material the regions use, in drawing order: {ref, local, label, regions}.
export function materialUses(doc){
 const block=geometryBlock(doc),uses=new Map();
 const add=(ref,region)=>{if(typeof ref!=='string')return;if(!uses.has(ref))uses.set(ref,[]);uses.get(ref).push(region);};
 for(const f of block?.features||[])add(f.material,f.name);
 add(block?.background?.material,'background');
 return [...uses].map(([ref,regions])=>({ref,local:!ref.startsWith('physmat:'),regions,label:materialLabel(ref,regions)}));
}
export function materialLabel(ref,regions=[]){
 const base=ref.startsWith('physmat:')?(LIBRARY_NAMES[ref]||ref.slice(8)):ref[0].toUpperCase()+ref.slice(1);
 const named=regions.filter(r=>r.toLowerCase()!==base.toLowerCase());
 return named.length?`${base} (${named.join(', ')})`:base;
}
export function modesTemperatureCoupled(doc,name){return couplingNames(doc).some(c=>doc.couplings[c]?.to===`${name}.temperature`);}
export function anyTemperatureCoupled(doc){return physicsNames(doc).some(n=>doc.physics[n]?.type==='em.modes2d'&&modesTemperatureCoupled(doc,n));}
// The physmat material whose thermo-optic data a local optical record is offered.
export function physmatFor(record){const n=typeof record?.refractive_index==='number'?record.refractive_index:parseFloat(record?.refractive_index);return n>2.5?'physmat:Si':'physmat:SiO2';}
export function fillThermoOptic(doc,material,ref=physmatFor(doc.materials?.[material])){
 const data=PHYSMAT_THERMO_OPTIC[ref],next=clone(doc),record=next.materials[material];
 record.thermo_optic_coefficient=`${data.coefficient.toExponential(1)} 1/K`;record.reference_temperature=`${data.reference} K`;
 record.source=`${record.source?record.source+'; ':''}thermo-optic data copied from ${ref} (physmat)`;
 return next;
}
// Switch every region of a local material to the physmat material (the record stays unused).
export function usePhysmat(doc,material,ref){
 const next=clone(doc),block=geometryBlock(next);
 for(const f of block.features||[])if(f.material===material)f.material=ref;
 if(block.background?.material===material)block.background.material=ref;
 return next;
}
export function fillText(ref){const d=PHYSMAT_THERMO_OPTIC[ref];return `Fill from ${ref} (${d.coefficient.toExponential(1)} 1/K at ${d.reference} K)`;}

// ---- validation messages --------------------------------------------------------------------
// Engine diagnostics as the workspace shows them: the node where the problem is fixed, a plain
// message, a one-click fix when there is one, and the engine's code and text under Details.
const pathSegments=path=>String(path||'').replace(/\[(\d+)\]/g,'.$1').split('.').filter(Boolean);
const list=items=>items.length<=1?items.join(''):items.slice(0,-1).join(', ')+' and '+items.at(-1);
function couplingMessage(doc,catalog,cname,field,d){
 const c=doc.couplings?.[cname]||{},title=`Coupling ${couplingTitle(doc,cname)}`,remove={action:'remove-coupling',coupling:cname,label:'Remove coupling'};
 const node='coupling:'+cname,labels=list(physicsNames(doc).map(physicsLabel));
 if(d.code==='E-COUPLING-PAIR'){
  const out=findPort(doc,catalog,c.from),inp=findPort(doc,catalog,c.to),[src]=splitSpec(c.from),[dst]=splitSpec(c.to);
  if(out&&inp&&out.quantity!==inp.quantity)return {node,fix:remove,cause:`${quantityWords(out.quantity)} ≠ ${quantityWords(inp.quantity)}`,text:`${title}: ${physicsLabel(src)} sends ${quantityWords(out.quantity)}, but ${portLabel(c.to)} takes ${quantityWords(inp.quantity)}. Connect an output that sends ${quantityWords(inp.quantity)}, or remove this coupling.`};
  if(out&&inp&&out.unit!==inp.unit)return {node,fix:remove,cause:`${unitText(out.unit)} ≠ ${unitText(inp.unit)}`,text:`${title}: units differ. ${physicsLabel(src)} sends ${quantityWords(out.quantity)} in ${unitText(out.unit)}; ${physicsLabel(dst)} expects ${unitText(inp.unit)}. Couplings do not convert units. Connect ${/^[aeiou]/.test(quantityWords(inp.quantity))?'an':'a'} ${quantityWords(inp.quantity)} output in ${unitText(inp.unit)}, or remove this coupling.`};
  return {node,fix:remove,cause:'values do not fit',text:`${title}: ${physicsLabel(src)} sends values ${locationWords(out?.location)}, which ${portLabel(c.to)} (${locationWords(inp?.location)}) cannot take. Remove this coupling.`};
 }
 if(field==='transfer'){
  const key=/does not read mesh\.([A-Za-z_]+)/.exec(d.message)?.[1];
  if(key){const ignoring=/but ([A-Za-z_][A-Za-z0-9_]*) does not read/.exec(d.message)?.[1],[a]=splitSpec(c.from),[b]=splitSpec(c.to),reader=ignoring===a?b:a,words=`mesh ${quantityWords(key)}`;
   return {node:'mesh',cause:'meshes differ',fix:{action:'remove-mesh-key',key,label:`Remove ${words}`},text:`${physicsLabel(a)} and ${physicsLabel(b)} would build different meshes: ${words} is read only by ${physicsLabel(reader)}. Remove ${words} so both use the same mesh.`};}
  return {node,cause:'unknown transfer',fix:{action:'use-same-mesh',coupling:cname,label:'Use same mesh'},text:`Coupling ${cname} uses transfer “${c.transfer}”, which this release does not have. Use “Same mesh”: both physics use Mesh 1.`};
 }
 if(field==='from'||field==='to'){
  const spec=c[field],[physics,port]=splitSpec(spec),direction=field==='from'?'output':'input';
  if(!(physics in (doc.physics||{})))return {node,fix:remove,cause:'unknown physics',text:`Coupling ${cname} names a physics “${physics}” that is not in this model. Choose one of ${labels||'the physics of this model'}, or remove the coupling.`};
  const ports=portsOf(doc,catalog,physics),found=ports.find(p=>p.name===port);
  if(field==='to'&&found&&found.direction==='input'&&/takes one coupling/.test(d.message)){
   const sources=couplingNames(doc).filter(n=>doc.couplings[n]?.to===spec).map(n=>physicsLabel(splitSpec(doc.couplings[n].from)[0]));
   return {node:'physics:'+physics,cause:'second source',fix:null,text:`${portLabel(spec)} takes one source but receives ${sources.length===2?'two':sources.length}: ${list(sources.map(s=>'from '+s))}. Remove one of the couplings.`};
  }
  if(field==='from'&&found&&found.direction==='output'&&/does not couple in this release/.test(d.message)){
   const coupled=(/its coupled outputs: (.*)$/.exec(d.message)?.[1]||'').split(', ').filter(x=>x&&x!=='none').map(quantityWords);
   return {node,fix:remove,cause:'not sent',text:`${title}: ${physicsLabel(physics)} does not send ${quantityWords(port)} to couplings in this release. Its coupled outputs are ${list(coupled)||'none'}. Choose one, or remove the coupling.`};
  }
  const names=ports.filter(p=>p.direction===direction).map(p=>quantityWords(p.name));
  return {node,fix:remove,cause:`no ${direction} ${port}`,text:`Coupling ${cname}: ${physicsLabel(physics)} has no ${direction} “${port}”. Its ${direction}s are ${list(names)||'none'}. Choose one, or remove the coupling.`};
 }
 if(/to itself/.test(d.message)){const [p]=splitSpec(c.from);return {node,fix:remove,cause:'feeds itself',text:`Coupling ${cname} connects ${physicsLabel(p)} to itself. A physics cannot feed its own input; remove this coupling.`};}
 return {node,fix:null,cause:'invalid',text:d.message};
}
function cycleMessage(doc,catalog,d){
 const proposal=d.suggestions?.[0]?.value;if(!isObject(proposal))return {node:'study',text:d.message,fix:null};
 const members=proposal.physics,inside=couplingNames(doc).map(n=>({n,...doc.couplings[n]})).filter(c=>members.includes(splitSpec(c.from)[0])&&members.includes(splitSpec(c.to)[0]));
 const needs=inside.map(c=>`${physicsLabel(splitSpec(c.to)[0])} needs the ${quantityWords(findPort(doc,catalog,c.from)?.quantity||splitSpec(c.from)[1])} from ${physicsLabel(splitSpec(c.from)[0])}`);
 const t=proposal.tolerance||{};
 return {node:'study',members,fix:{action:'accept-loop',proposal,label:'Accept iteration step'},
  text:`${list(members.map(physicsLabel))} depend on each other. ${needs.join(', and ')}. Solve them together with an iteration step: fixed point, stop when ${portLabel(t.port)} changes by at most ${t.value}, up to ${proposal.max_iterations} iterations, relaxation ${proposal.relaxation}.`};
}
function materialMessage(doc,name,d){
 const uses=materialUses(doc),use=uses.find(u=>u.ref===name),label=use?.label||materialLabel(name);
 if(d.code==='E-PROPERTY-MISSING'&&/thermo-optic/.test(d.message)){
  const modes=physicsNames(doc).find(n=>doc.physics[n].type==='em.modes2d'&&modesTemperatureCoupled(doc,n));
  const source=modes?couplingNames(doc).map(c=>doc.couplings[c]).find(c=>c.to===`${modes}.temperature`):null;
  const ref=physmatFor(doc.materials?.[name]);
  return {node:'material:'+name,fields:['thermo_optic_coefficient','reference_temperature'],fix:{action:'fill-physmat',material:name,ref,label:fillText(ref)},
   text:`${label} has no thermo-optic data, but ${physicsLabel(modes||'modes1')} takes its temperature from ${physicsLabel(splitSpec(source?.from)[0]||'heat1')}, so every optical material needs a thermo-optic coefficient (1/K) and a reference temperature (K). Add them in Materials > ${label}.`};
 }
 const keys={thermo_optic_coefficient:'thermo-optic coefficient',reference_temperature:'reference temperature'},missing=pathSegments(d.path)[2];
 if(d.code==='E-KEY-MISSING'&&keys[missing]){const other=missing==='thermo_optic_coefficient'?'reference_temperature':'thermo_optic_coefficient',ref=physmatFor(doc.materials?.[name]);
  return {node:'material:'+name,fields:[missing],fix:{action:'fill-physmat',material:name,ref,label:fillText(ref)},
   text:`${label} gives a ${keys[other]} but no ${keys[missing]}; the thermo-optic model n = n₀ + (dn/dT)(T − T_ref) needs both. Add the ${keys[missing]} in Materials > ${label}.`};}
 return {node:'material:'+name,fix:null,text:`${label}: ${d.message}`};
}
export function nodeOfPath(path){
 const s=pathSegments(path);
 if(s[0]==='couplings'&&s[1])return 'coupling:'+s[1];
 if(s[0]==='physics'&&s[1])return 'physics:'+s[1];
 if(s[0]==='materials'&&s[1])return 'material:'+s[1];
 if(s[0]==='study'&&s[1]==='loops'&&/^\d+$/.test(s[2]||''))return 'loop:'+s[2];
 if(['mesh','study','geometry'].includes(s[0]))return s[0];
 return 'model';
}
export function mapDiagnostics(doc,catalog,diagnostics){
 const out=[],seen=new Set();
 for(const d of diagnostics||[]){
  if(d.severity!=='error'&&d.severity!=='warning')continue;
  const s=pathSegments(d.path);let m;
  if(s[0]==='couplings'&&s[1]&&doc.couplings?.[s[1]]!==undefined)m=couplingMessage(doc,catalog,s[1],s[2],d);
  else if(d.code==='E-COUPLING-CYCLE')m=cycleMessage(doc,catalog,d);
  else if(s[0]==='materials'&&s[1])m=materialMessage(doc,s[1],d);
  else m={node:nodeOfPath(d.path),fix:null,text:d.message};
  const key=m.node+'\u0000'+m.text;if(seen.has(key))continue;seen.add(key);
  out.push({severity:d.severity,code:d.code,path:d.path,detail:d.message,...m});
 }
 return out;
}
// Problem counts per tree node (errors only); a material problem also counts on Materials.
export function problemCounts(messages){
 const counts={};
 for(const m of messages){if(m.severity!=='error')continue;counts[m.node]=(counts[m.node]||0)+1;if(m.node.startsWith('material:'))counts.materials=(counts.materials||0)+1;if(m.node.startsWith('loop:'))counts.study=(counts.study||0)+1;}
 return counts;
}
export function runBlockText(errorCount,refusal){
 if(refusal)return refusal;
 return errorCount?`Fix ${errorCount} problem${errorCount===1?'':'s'} in Messages to run`:'';
}

// ---- the Connections view -------------------------------------------------------------------
// Nodes in solve-order columns, a wire per coupling (red and dashed when its check failed, with
// the short cause), and a box around each cycle (amber without its loop, blue with it).
const QUANTITY_COLOR={temperature:'temperature',joule_power_density:'power',heat_source_density:'power',displacement:'geometry',electric_potential:'voltage',effective_index:'optical'};
export function connectionLayout(doc,catalog,order,messages=[]){
 const names=physicsNames(doc),groups=(order&&order.length?order:names.map(n=>[n])).filter(g=>g.every(n=>names.includes(n)));
 const placed=new Set(groups.flat());for(const n of names)if(!placed.has(n))groups.push([n]);
 const nodes=[],boxes=[];
 groups.forEach((group,column)=>{
  const cycle=group.length>1;
  group.forEach((name,row)=>{
   const pins=portsOf(doc,catalog,name).filter(p=>p.location!=='scalar'||p.direction==='output').map(p=>({...p,id:`${name}--${p.direction}--${p.name}`}));
   const warnings=unsourcedInputs(doc,catalog).filter(w=>w.physics===name).map(w=>w.text);
   nodes.push({name,label:physicsLabel(name),type:doc.physics[name].type,typeLabel:catalog.types.get(doc.physics[name].type)?.label||doc.physics[name].type,column,row,badge:column+1,cycle,pins,warnings});
  });
  if(cycle){const loop=loopIndexOf(doc,group);boxes.push({members:[...group],column,accepted:loop>=0,loop,
   label:loop>=0?`Iteration step ${loop+1} · ${loopText(doc.study.loops[loop])}`:`Cycle: ${list(group.map(physicsLabel))} need an iteration step`});}
 });
 const byNode=Object.fromEntries(nodes.map(n=>[n.name,n])),wires=[],dangling=[];
 for(const cname of couplingNames(doc)){
  const c=doc.couplings[cname],[src,out]=splitSpec(c?.from),[dst,inp]=splitSpec(c?.to),problem=messages.find(m=>m.node==='coupling:'+cname&&m.severity==='error')||messages.find(m=>m.severity==='error'&&m.path?.startsWith(`couplings.${cname}`));
  if(!byNode[src]||!byNode[dst]){dangling.push({coupling:cname,title:couplingTitle(doc,cname),cause:problem?.cause||'unknown physics'});continue;}
  const pin=(node,port,direction)=>{let p=node.pins.find(x=>x.name===port&&x.direction===direction);
   if(!p){p={name:port,direction,quantity:port,unit:'?',location:'?',missing:true,id:`${node.name}--${direction}--${port}`};node.pins.push(p);}return p;};
  const a=pin(byNode[src],out,'output'),b=pin(byNode[dst],inp,'input');
  const backward=byNode[dst].column<=byNode[src].column;
  wires.push({coupling:cname,from:a.id,to:b.id,title:couplingTitle(doc,cname),color:QUANTITY_COLOR[a.quantity]||'temperature',invalid:!!problem,cause:problem?.cause||null,route:backward?'below':'curve'});
 }
 return {nodes,wires,boxes,dangling,columns:groups.length};
}
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function renderMultiphysicsGraph(layout,selection,states={}){
 const pin=(node,p)=>`<button class="graph-port ${p.direction==='input'?'input':'output'} ${QUANTITY_COLOR[p.quantity]||'temperature'}${p.missing?' missing':''}" data-port="${esc(p.id)}" data-mp-select="physics:${esc(node.name)}" title="${esc(quantityWords(p.name))}: ${p.direction==='input'?'an input':'an output'} of ${esc(node.label)}. To connect ports, use Add coupling…" aria-label="${esc(node.label)} ${p.direction} ${esc(quantityWords(p.name))}${p.missing?' (not a port of this physics)':', '+esc(unitText(p.unit))+', '+esc(locationWords(p.location))}"><i class="port-dot" aria-hidden="true"></i><span>${esc(quantityWords(p.name))}<small>${p.missing?'not a port':esc(unitText(p.unit))+' · '+esc(locationWords(p.location))+(p.direction==='input'?' · '+((p.combine||'single')==='single'?'one source':'sources add'):'')}</small></span></button>`;
 const column=c=>layout.nodes.filter(n=>n.column===c);
 const node=n=>{const state=states[n.name];return `<article class="graph-node mp-node ${selection==='physics:'+n.name?'selected':''}" data-mp-node="${esc(n.name)}"><button class="graph-node-title" data-mp-select="physics:${esc(n.name)}" aria-pressed="${selection==='physics:'+n.name}"><span class="order-badge${n.cycle?' cycle':''}" aria-label="solve order ${n.badge}">${n.badge}</span>${esc(n.label)}<small>${esc(n.typeLabel)} · ${esc(n.type)}</small>${state?`<small class="mp-state ${esc(state.state)}">${esc(state.text)}</small>`:''}${(n.warnings||[]).map(w=>`<small class="mp-warn" data-mp-warning="${esc(n.name)}"><b aria-hidden="true">!</b> ${esc(w)}</small>`).join('')}</button><div class="graph-ports mp-ports">${[...n.pins.filter(p=>p.direction==='input'),...n.pins.filter(p=>p.direction==='output')].map(p=>pin(n,p)).join('')}</div></article>`;};
 const cols=Array.from({length:layout.columns},(_,c)=>{const box=layout.boxes.find(b=>b.column===c);const inner=column(c).map(node).join('');
  return box?`<div class="mp-column"><div class="mp-cycle ${box.accepted?'accepted':'open'}" data-mp-cycle="${esc(box.members.join(','))}"><span class="mp-cycle-label">${esc(box.label)}</span>${inner}</div></div>`:`<div class="mp-column">${inner}</div>`;}).join('');
 const wires=layout.wires.map(w=>[w.from,w.to,w.color+(w.invalid?' invalid':''),w.title+(w.cause?' · '+w.cause:''),w.route,w.coupling,w.cause]);
 const marks=layout.wires.filter(w=>w.invalid).map(w=>`<button class="mp-wire-mark" data-mp-select="coupling:${esc(w.coupling)}" data-mark-for="${esc(w.coupling)}"><b aria-hidden="true">!</b> ${esc(w.cause||'problem')}</button>`).join('');
 const dangling=layout.dangling.map(d=>`<li><button data-mp-select="coupling:${esc(d.coupling)}"><b aria-hidden="true">!</b> ${esc(d.title)} · ${esc(d.cause)}</button></li>`).join('');
 return `<div class="graph-scroll" tabindex="0" role="region" aria-label="Physics connection diagram; scroll sideways on small screens"><div class="graph-stage mp-stage" data-edges='${esc(JSON.stringify(wires))}'><svg class="graph-wires" aria-hidden="true"></svg>${cols}<div class="mp-marks">${marks}</div></div></div>${dangling?`<ul class="mp-dangling" aria-label="Couplings that cannot be drawn">${dangling}</ul>`:''}`;
}

// The two ends of each drawn wire: the positions of the ports its coupling joins, by port id
// (point(id) -> {x, y} of that port's dot, or null when it is not drawn). Every port has its
// own row with its dot on the node edge, so a wire never starts beside another port.
export function wireEnds(edges,point){
 return edges.map(([from,to,,,route,coupling])=>{const a=point(from),c=point(to);return a&&c?{coupling,route,from:a,to:c}:null;});
}

// ---- running --------------------------------------------------------------------------------
const seconds=s=>`${Number(s).toFixed(s<10?1:0)} s`;
export function formatValue(v){if(v===0)return '0';return Math.abs(v)>=1e-3&&Math.abs(v)<1e5?String(Number(v.toPrecision(3))):v.toExponential(1);}
// One row per solve-order group: its state from the progress events of the run.
export function progressRows(order,doc,events=[],status='running',error=null){
 const rows=order.map(group=>{const loop=group.length>1?loopIndexOf(doc,group):-1;
  return {group,label:group.length>1?`Iteration step ${loop+1} · ${group.map(physicsLabel).join(' ⇄ ')}`:physicsLabel(group[0]),state:'waiting',text:'Waiting',loop,max:loop>=0?doc.study.loops[loop].max_iterations:null,residuals:[]};});
 const rowOf=physics=>rows.find(r=>r.group.includes(Array.isArray(physics)?physics[0]:physics));
 for(const e of events){const r=rowOf(e.physics);if(!r)continue;
  if(e.event==='physics_started'&&r.group.length===1){r.state='solving';r.text='Solving…';}
  else if(e.event==='physics_finished'&&r.group.length===1){r.state='done';r.text='Done in '+seconds(e.seconds);}
  else if(e.event==='loop_started'){r.state='solving';r.text='Solving…';}
  else if(e.event==='loop_iteration'){r.residuals.push({iteration:e.iteration,value:e.residual,unit:e.unit});r.text=`Iteration ${e.iteration} of up to ${r.max} · max |Δ| ${formatValue(e.residual)} ${unitText(e.unit)}`;}
  else if(e.event==='loop_finished'){r.state='done';r.text=`Settled in ${e.iterations} iterations`;}
 }
 if(status!=='running')for(const r of rows){
  if(r.state==='solving'){
   if(status==='error'&&error?.code==='E-LOOP-DIVERGED'){r.state='did-not-settle';r.text=`Did not settle in ${r.max} iterations`;}
   else if(status==='error'){r.state='failed';r.text='Failed';}
   else if(status==='stopped'){r.state='not-run';r.text='Stopped';}
  }else if(r.state==='waiting'&&status!=='done'){r.state='not-run';r.text='Not run';}
 }
 return rows;
}
export function failureText(error,doc){
 if(!error)return '';
 if(error.code==='E-LOOP-DIVERGED'){
  const r=error.residuals||[],last=r.at(-1),group=Array.isArray(error.physics)?error.physics:[],loop=loopIndexOf(doc,group),l=doc.study?.loops?.[loop];
  return `${group.map(physicsLabel).join(' ⇄ ')} did not settle in ${l?.max_iterations??r.length+1} iterations. The largest change in the last iteration was ${last===undefined?'not measured':formatValue(last)+' '+unitText(error.unit)} (target ${l?.tolerance?.value??'the tolerance'}). No results were kept, because the last iteration is not a solution. Lower the relaxation (for example 0.3) or raise the iteration limit, then run again.`;
 }
 if(error.physics&&!Array.isArray(error.physics))return `${physicsLabel(error.physics)} failed, so the run kept no result: ${error.message}`;
 return error.message;
}

// ---- results --------------------------------------------------------------------------------
const count=n=>Number(n).toLocaleString('en-US');
function range(values){let lo=Infinity,hi=-Infinity;for(const v of values){if(v<lo)lo=v;if(v>hi)hi=v;}return [lo,hi];}
// The coupling check of a run: what each coupling sent and received, and its check result.
// counts: {nodes, triangles} of a run whose maps a session file did not keep; the sent range is
// then its heat range, and the received values are one per triangle.
export function couplingCheckRows(result,doc,counts=null){
 const nodes=counts?counts.nodes:result.mesh.node_coordinates.length,triangles=counts?counts.triangles:result.mesh.triangles.length;
 return Object.entries(result.couplings||{}).map(([name,c])=>{
  const [src,port]=splitSpec(c.from),sent=result.physics[src]?.[port]?.values,[dst]=splitSpec(c.to),received=result.physics[dst]?.coupled?.[splitSpec(c.to)[1]]?.values;
  const stored=!sent&&counts&&port==='temperature'&&result.physics[src]?.range;
  const where=c.location==='node'?'node':'triangle',[lo,hi]=sent?range(sent):stored?[stored.min,stored.max]:[NaN,NaN];
  const sentText=`${count(sent?sent.length:c.location==='node'?nodes:triangles)} ${where} ${quantityWords(c.quantity)}s${sent||stored?`, ${lo.toFixed(1)}–${hi.toFixed(1)} ${unitText(c.unit)}`:''}`;
  const receivedCount=received?received.length:counts&&result.physics[dst]?.coupled?triangles:null;
  const elementInput=receivedCount===triangles&&c.location==='node';
  const receivedText=receivedCount!==null?`${count(receivedCount)} ${elementInput?'triangle means (mean of 3 nodes)':'values'}`:'—';
  const diff=c.max_abs_difference||{value:null,unit:c.unit},passed=c.mesh_signature==='match'&&diff.value===0;
  const check=c.conservation_residual!==null&&c.conservation_residual!==undefined?`${passed?'Passed':'Failed'} · conservation |Σ sent − Σ received| / |Σ sent| = ${formatValue(c.conservation_residual)}`:`${passed?'Passed':'Failed'} · max |received − sent| = ${diff.value} ${unitText(diff.unit)} · same mesh: ${c.location} values arrived unchanged`;
  return {name,title:couplingTitle(doc,name)||name,from:c.from,to:c.to,sent:sentText,received:receivedText,check,passed};
 });
}
export function effectiveIndexRows(payload){
 const series=payload.effective_index,values=Array.isArray(series?.values)?series.values:Array.isArray(series?.re)?series.re:[];
 const rows=[];values.forEach((point,i)=>(Array.isArray(point)?point:[point]).forEach((v,m)=>rows.push({point:i,mode:m+1,value:v})));return rows;
}
// The sentence under a modes table, in the words of the optical application (RANKING_TEXT of
// workspace-modes.mjs), and the number of modes the model asks for, named by its setting.
export const RANKING_CAVEAT='Modes are ranked by effective index.';
// past: the model changed since the run, so the count is the run's, not the model's.
export function modeCountText(doc,name,{past=false}={}){
 const n=doc?.physics?.[name]?.mode_count,where=`${physicsLabel(name)} › Modes to find`;
 return Number.isInteger(n)?`${past?'This run asked for':'This model asks for'} ${n} ${n===1?'mode':'modes'}: ${where}`:`The number of modes is set in ${where}`;
}
// The Results pages of a run: one per physics, then the coupling check.
export function resultPages(result){return [...Object.keys(result.physics).map(n=>({id:'results:'+n,label:physicsLabel(n)})),...(Object.keys(result.couplings||{}).length?[{id:'results:check',label:'Coupling check'}]:[])];}
// The document of one physics alone, uncoupled: format 0.3 with no couplings or thermo-optic keys.
export function uncoupledDocument(doc,name){
 const next=clone(doc);next.physics={[name]:next.physics[name]};delete next.couplings;
 if(isObject(next.study))delete next.study.loops;
 for(const record of Object.values(next.materials||{}))if(isObject(record)){delete record.thermo_optic_coefficient;delete record.reference_temperature;}
 next.name=`${doc.name||'Model'} · ${physicsLabel(name)} alone`;
 return normalizeEnvelope(next);
}

// ---- what a run still says about the model --------------------------------------------------
// JSON with the keys of every object sorted: two documents of the same content have the same
// text, whatever order their edits wrote the keys in (a coupling removed and added back).
export function canonicalJson(x){
 if(Array.isArray(x))return '['+x.map(canonicalJson).join(',')+']';
 if(isObject(x))return '{'+Object.keys(x).sort().map(k=>JSON.stringify(k)+':'+canonicalJson(x[k])).join(',')+'}';
 return JSON.stringify(x);
}
export const sameContent=(a,b)=>canonicalJson(a)===canonicalJson(b);
// 'none' before a first run, 'current' while the model is the one the last run solved, else 'stale'
export function runFreshness(run,doc){return !run?'none':sameContent(run.doc,doc)?'current':'stale';}
// The rows of a run this tab did not compute: where each result came from, with no solve times.
// An iteration step keeps its count of iterations, a result of the run, not a time.
export function originRows(rows,origin){
 const text=origin==='imported'?'From file':origin==='recovered'?'From this browser':null;
 return text?rows.map(r=>r.state!=='done'?r:{...r,text:r.group?.length>1?`${r.text} · ${text.toLowerCase()}`:text}):rows;
}
// What one solve step (a physics, or the physics of an iteration step) reads: its own physics
// entries, the couplings into them, the shared parts of the model (geometry, materials, mesh,
// study, its name and any other part, not the envelope spelling, which a coupling removal can
// switch) and, through those couplings, every step upstream. The name is kept so the rows never
// read current while the run as a whole (runFreshness) is out of date.
export function stepInputs(doc,group){
 const shared=Object.fromEntries(Object.entries(isObject(doc)?doc:{}).filter(([k])=>!['openphysics','physics','couplings'].includes(k)));
 const seen=new Set(),physics={},into={};
 const visit=name=>{
  if(seen.has(name))return;seen.add(name);physics[name]=doc?.physics?.[name]??null;
  for(const c of couplingNames(doc)){const link=doc.couplings[c];if(splitSpec(link?.to)[0]!==name)continue;into[c]=link;visit(splitSpec(link?.from)[0]);}
 };
 for(const name of group)visit(name);
 return canonicalJson({shared,physics,couplings:into});
}
// 'current' when an edit left the step's own inputs and everything that flows into it as the run
// solved them: removing only the coupling into the optical modes leaves the heat step current.
export function stepFreshness(runDoc,doc,group){return stepInputs(runDoc,group)===stepInputs(doc,group)?'current':'stale';}
// The rows of the last run once the model changed: each keeps what it did, marked out of date.
// With the run's model and the current one, only the steps whose inputs changed are marked.
export function staleRows(rows,runDoc,doc){
 const stale=r=>runDoc===undefined||!Array.isArray(r.group)||stepFreshness(runDoc,doc,r.group)==='stale';
 return rows.map(r=>stale(r)?{...r,state:'stale',text:`Out of date (last run: ${r.text})`}:r);
}
// 'again' once an edit made the model differ from the last run and a later edit (Undo, the
// same coupling added back) made it equal again: the results are current once more.
export function freshnessAgain(freshness,diverged){return freshness==='current'&&diverged?'again':freshness;}
// The one sentence every place shows when the model equals the last run again.
// says what Run would do, so the sentence does not read as a request to run
// A run in the dock and the footer: "Run 2 · design A" when it is named, as the optical app says
// it; an unnamed run keeps the words it had ("run 2" inside a sentence).
const runWords=(runId,label,inSentence=false)=>label?`Run ${runId} · ${label}`:`${inSentence?'run':'Run'} ${runId}`;
// It says first that nothing needs running, then what Run would still do (a copy).
export const matchesAgainText=(runId,label='')=>`No need to run: ${runWords(runId,label)} already has these results. Run study adds a copy with the same values`;
export function editNotice(message,freshness,runId,label=''){return message+(freshness==='again'?` ${matchesAgainText(runId,label)}.`:' Press Run to compute the new model.');}
// Where a result shown as current came from, when this tab did not compute it (optical and
// multiphysics alike); null for a run computed here.
export const originText=origin=>origin==='imported'?'read from file, not recomputed':origin==='recovered'?'recovered from this browser, not recomputed':null;
// The dock heading and the footer for the state of the model and its last run. origin: where
// that run came from ('local', 'imported' or 'recovered'); a run not computed in this tab says so.
export function sequenceHeading(freshness,runId,origin='local',label=''){
 const run=runWords(runId,label);
 if(freshness==='again')return matchesAgainText(runId,label);
 if(freshness==='current'&&originText(origin))return `${run} · ${originText(origin)}`;
 if(freshness==='current')return `${run} · solved from the current model`;
 if(freshness==='stale')return `${run} · the model changed since; press Run to update`;
 return 'Nothing is computed until you press Run';
}
export const HAS_RESULTS_MODEL='has the results of the current model';
export function readyStatus(freshness,runId,origin='local',label=''){
 const run=runWords(runId,label);
 if(freshness==='again')return matchesAgainText(runId,label);
 // round 20 (Z1): a run read from file or recovered with the model's results says so, without asking for a run
 if(freshness==='current'&&originText(origin))return `${run} · ${originText(origin)} · ${HAS_RESULTS_MODEL}`;
 if(freshness==='current')return `${run} matches the model · press Run to solve again`;
 if(freshness==='stale')return `Model edited since ${runWords(runId,label,true)} · press Run to update`;
 return 'Model checked · press Run';
}
// The content key of one physics solved alone: an uncoupled column is valid for a run whose
// document gives the same uncoupled document, decided by content, not by the order of runs.
export function baselineKey(doc,name){return canonicalJson(uncoupledDocument(doc,name));}
// The optical physics whose temperature a coupling sets: they get a heater-off comparison.
export function baselinePhysics(doc){return physicsNames(doc).filter(n=>doc.physics[n]?.type==='em.modes2d'&&modesTemperatureCoupled(doc,n));}
// The "Also solve without heater" option beside Run: shown for every multiphysics model, and
// disabled with its reason while no coupling sets an optical temperature (nothing to switch off).
// on: the option as chosen, kept for when a temperature coupling comes back.
export function baselineOptionState(doc,{on=false,busy=false}={}){
 const names=baselinePhysics(doc);
 if(!names.length)return {available:false,disabled:true,checked:false,reason:'needs a temperature coupling',
  title:'Needs a temperature coupling: no coupling sets an optical temperature, so there is no heater to switch off. Add one from a heat physics with Add coupling….'};
 return {available:true,disabled:busy,checked:on,reason:'',
  title:`After the coupled run, also solve ${names.map(physicsLabel).join(' and ')} alone with no temperature input (about 1 s), for the n_eff without heater`};
}
// The Messages words when an edit (a coupling added back, Undo, Redo) makes the option
// available again and it returns ticked as it was chosen; '' when nothing returned.
export function baselineReturnText(before,after,on){
 return on&&!baselineOptionState(before,{on}).checked&&baselineOptionState(after,{on}).checked?' “Also solve without heater” is ticked again.':'';
}
// Δn_eff in the 8-decimal format of the n_eff columns, always signed: +0.00215086
export function shiftText(coupled,alone){const d=Number(coupled)-Number(alone);if(!Number.isFinite(d))return '—';const t=Math.abs(d).toFixed(8);return (d<0&&Number(t)!==0?'−':'+')+t;}
// The reference temperature every material of the model shares (K), or null when the materials
// have none or differ. Without a coupled temperature the modes solve applies no index change, so
// each material keeps n₀, its index at its own T_ref.
export function sharedReferenceTemperature(doc){
 const values=new Set();
 for(const u of materialUses(doc)){
  if(u.ref.startsWith('physmat:')){const t=PHYSMAT_THERMO_OPTIC[u.ref];if(!t)return null;values.add(t.reference);continue;}
  const raw=doc.materials?.[u.ref]?.reference_temperature,m=/^\s*([-+]?\d+(?:\.\d*)?(?:[eE][-+]?\d+)?)\s*K\s*$/.exec(String(raw??''));
  if(typeof raw==='number')values.add(raw);else if(m)values.add(Number(m[1]));else return null;
 }
 return values.size===1?[...values][0]:null;
}
const atReference=doc=>{const t=sharedReferenceTemperature(doc);return t===null?'every material keeps its index n₀':`every material keeps n₀, its index at T_ref = ${t} K`;};
// What the heater-off column is, in the words of what the engine does for it.
export function baselineText(doc,name){return `without heater = ${physicsLabel(name)} alone with no temperature input: ${atReference(doc)}.`;}
// The inputs that take a temperature no coupling gives, while a physics of the model could:
// [{physics, port, text}] (a warning; the model still runs).
export function unsourcedInputs(doc,catalog){
 return suggestedCouplings(doc,catalog).filter(s=>splitSpec(s.to)[1]==='temperature'&&doc.physics[splitSpec(s.to)[0]]?.type==='em.modes2d').map(s=>{
  const t=sharedReferenceTemperature(doc);
  return {physics:splitSpec(s.to)[0],port:'temperature',from:s.from,to:s.to,text:`Temperature input has no source: ${t===null?'each material uses its index n₀':`uses n₀ at T_ref (${t} K)`}`};});
}
