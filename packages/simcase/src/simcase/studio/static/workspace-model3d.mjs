// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// The 3D model in the workspace (slice B of the Studio 3D view; docs/packages/simcase/workspace.md,
// "3D models"): pure helpers, no DOM and no network, so Node tests them. The model is a format 0.3
// document with one 3d component of boxes and slab layers; every edit returns a new document, which
// the page sends to /api/model3d/check, so the server's exact complex decides coverage and refusals.
// The ranges here are Studio's own guards against unusable sizes (design 5.2), not contract rules: a
// document opened from a file with other values is read as written.
import {betweenText} from './workspace-inputs.mjs';
import {canonicalJson,RUN_RECORD} from './workspace-model3d-session.mjs';
// Slice C's mesh words (estimateText, meshBlocked) live in /model3d-assets/model3d-mesh-model.mjs;
// the page passes them in (words), so this module keeps to the workspace assets and Node tests it.

/** The Library card of the 3D group (not an application card: it has its own group). */
export const CARD3D=Object.freeze({id:'layer-stack-3d',kind:'model3d',title:'Via in a layer stack (3D heat)',
 asset:'/model3d-assets/model3d-layer-stack-3d.json',sessionFile:'via-in-a-layer-stack-3d.json',status:'3D steady heat (experimental)',
 note:'Square via (the round via is the card Copper via through a slab)',
 description:'A silicon substrate, an oxide layer and top silicon, with a copper via through the oxide. Build the 3D geometry, mesh it and solve steady heat.'});
/** Card 2: a copper via (one cylinder) through a slab, in meshloom's via_in_slab builder shape. */
export const CARD3D_SLAB=Object.freeze({id:'via-slab-3d',kind:'model3d',title:'Copper via through a slab (3D heat)',
 asset:'/model3d-assets/model3d-via-slab-3d.json',sessionFile:'copper-via-through-a-slab-3d.json',status:'3D steady heat (experimental)',
 note:'Round via: one cylinder through the slab, in a meshloom builder shape',
 description:'A copper via through a slab, 300 K at the bottom and 301 K at the top. The curved shape is drawn for display; the mesh follows it to within its size.'});
/** The Library's 3D group, in order. */
export const CARDS3D=Object.freeze([CARD3D,CARD3D_SLAB]);
/** The card a document came from (its name is the card's title), or null. */
export const card3dOf=doc=>CARDS3D.find(c=>c.title===doc?.name)||null;

/** Add feature: Box, Layers, Cylinder and Sphere are taken; Extrude is greyed with its reason. */
export const FEATURE_TYPES=Object.freeze([
 {type:'box',label:'Box',available:true},
 {type:'layers',label:'Layers',available:true},
 {type:'extrude',label:'Extrude',available:false,reason:'Extrude comes with a later geometry step'},
 {type:'cylinder',label:'Cylinder',available:true},
 {type:'sphere',label:'Sphere',available:true},
]);
const TYPE_LABEL={box:'Box',layers:'Layers',extrude:'Extrude',cylinder:'Cylinder',sphere:'Sphere'};

const copy=doc=>JSON.parse(JSON.stringify(doc));
const fail=message=>{throw new Error(message);};

/** The name of the document's one 3d component (the first). */
export function componentName(doc){
 const comps=doc?.geometry?.components||{};
 return Object.keys(comps).find(n=>comps[n]?.dimension==='3d')??null;
}
const component=doc=>doc.geometry.components[componentName(doc)];

// ---- fields ------------------------------------------------------------------------------------

/** Metres per unit of the length units a 3D component uses. */
export const UNITS=Object.freeze({m:1,mm:1e-3,um:1e-6,'µm':1e-6,nm:1e-9});
/** A unit as shown: um → µm. */
export const shownUnit=unit=>unit==='um'?'µm':unit;
const num=v=>Number(Number(v).toPrecision(6));
const MAX_LAYERS=32;
const NAME=/^[A-Za-z_][A-Za-z0-9_]*$/;
const NUMBER=/^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$/;

/**
 * A length field as typed: a bare number (in the component's unit), a quantity ("12 um"), a
 * parameter name or an expression ("100 - w / 2"). Returns {value, si} with value as the document
 * stores it (a number, or the text) and si in metres when it can be known here (null for a name or
 * an expression, which the server evaluates), or {problem} for text that cannot be one.
 * rule: {positive} for a thickness.
 */
export function parseLength(raw,unit,rule={}){
 const text=String(raw??'').trim();
 if(!text)return {problem:'Enter a length: a number, a quantity such as 12 um, a parameter name or an expression.'};
 if(NUMBER.test(text)){
  const v=Number(text);if(!Number.isFinite(v))return {problem:`${text} is not a finite number.`};
  if(rule.positive&&!(v>0))return {problem:'positive'};
  return {value:v,si:v*UNITS[unit]};
 }
 const q=/^([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)\s+(\S+)$/.exec(text);
 if(q&&q[2] in UNITS){
  const v=Number(q[1]);if(!Number.isFinite(v))return {problem:`${q[1]} is not a finite number.`};
  if(rule.positive&&!(v>0))return {problem:'positive'};
  return {value:`${q[1]} ${q[2]}`,si:v*UNITS[q[2]]};
 }
 if(q)return {problem:`${q[2]} is not a length unit (m, mm, um, nm).`};
 if(/^[A-Za-z0-9_+\-*/(). ]+$/.test(text))return {value:text,si:null};
 return {problem:`${text} is not a number, a quantity, a parameter name or an expression.`};
}

/** The SI text shown beside a field: "= 1.2e-4 m", or "" when the server evaluates it. */
export function siText(si){return si===null||si===undefined?'':`= ${Number(si.toPrecision(6))} m`;}

/**
 * The note beside a field: "= t_ox (10 µm)" for a parameter name (with its value as written),
 * "= 0.00009 m" for a number or a quantity, "" for an expression (the server evaluates it).
 */
export function fieldNote(doc,key){
 const value=getField(doc,key);if(value===null||value===undefined||value==='')return '';
 const params=doc.geometry.parameters||{},text=String(value).trim();
 if(NAME.test(text)&&text in params)return `= ${text} (${String(params[text].value).replace(/\bum\b/g,'µm')})`;
 const p=parseLength(text,component(doc).length_unit);
 return p.problem?'':siText(p.si);
}

/** The fields of a node, in table order: [{key, label, kind, rule, optional}] (kind: length | name | material | fixed, shown read-only). */
export function fieldsOf(doc,node){
 if(node==='mesh')return [{key:'mesh.element_size',label:'element_size',kind:'length',rule:{meshSize:true}}];
 if(node==='domain')return ['xmin','xmax','ymin','ymax','zmin','zmax'].map(k=>({key:`domain.${k}`,label:k,kind:'length'}));
 const m=/^feature:(\d+)$/.exec(node);if(!m)return [];
 const i=+m[1],f=component(doc).features[i];if(!f)return [];
 const base=`features[${i}]`;
 if(f.type==='box')return [{key:`${base}.name`,label:'name',kind:'name'},
  ...['xmin','xmax','ymin','ymax','zmin','zmax'].map(k=>({key:`${base}.${k}`,label:k,kind:'length'})),
  {key:`${base}.material`,label:'material',kind:'material'},{key:`${base}.element_size`,label:'element_size',kind:'length',optional:true}];
 if(f.type==='layers')return [{key:`${base}.name`,label:'name',kind:'name'},{key:`${base}.z0`,label:'z0',kind:'length'},
  ...f.layers.flatMap((lay,j)=>[{key:`${base}.layers[${j}].name`,label:`layer ${j+1} name`,kind:'name'},
   {key:`${base}.layers[${j}].thickness`,label:`layer ${j+1} thickness`,kind:'length',rule:{positive:true}},
   {key:`${base}.layers[${j}].material`,label:`layer ${j+1} material`,kind:'material'}]),
  {key:`${base}.element_size`,label:'element_size',kind:'length',optional:true}];
 // a cylinder or sphere in a builder shape takes one size only (mesh.element_size): no element_size here
 if(f.type==='cylinder'||f.type==='sphere')return [{key:`${base}.name`,label:'name',kind:'name'},
  ...(f.type==='cylinder'?[{key:`${base}.axis`,label:'axis',kind:'fixed',value:'z (fixed)'}]:[]),
  ...(f.type==='cylinder'?['cx','cy','r','zmin','zmax']:['cx','cy','cz','r']).map(k=>({key:`${base}.${k}`,label:k,kind:'length'})),
  {key:`${base}.material`,label:'material',kind:'material'}];
 return [{key:`${base}.name`,label:'name',kind:'name'}];
}

const STEP=/([A-Za-z_][A-Za-z0-9_]*)|\[(\d+)\]/g;
const steps=key=>[...key.matchAll(STEP)].map(m=>m[2]!==undefined?+m[2]:m[1]);
/** The value at a component-relative key ("features[1].xmin"). */
const rootOf=(doc,key)=>key.startsWith('mesh.')?doc:component(doc);     // the mesh block is the document's
export function getField(doc,key){let at=rootOf(doc,key);for(const s of steps(key)){if(at==null)return undefined;at=at[s];}return at;}
/** A copy of doc with the value at key set (no checks: see editField); undefined removes the key. */
export function setField(doc,key,value){
 const out=copy(doc),path=steps(key);let at=rootOf(out,key);
 for(const s of path.slice(0,-1))at=at[s];
 if(value===undefined)delete at[path.at(-1)];else at[path.at(-1)]=value;return out;
}

// ---- ranges (design 5.2) ----
const AXES=['x','y','z'];
const cap=s=>s.charAt(0).toUpperCase()+s.slice(1);
/** A length in the component's unit, when the field's text gives one here (a number or a quantity). */
function inUnit(value,unit){const p=parseLength(value,unit);return p.problem||p.si===null?null:p.si/UNITS[unit];}
function rangeProblem(doc,key,v){
 const comp=component(doc),unit=comp.length_unit,u=shownUnit(unit),d=comp.domain||{};
 const between=(label,lo,hi)=>{
  const below=lo!==null&&!(v>lo.v||(lo.eq&&v===lo.v)),above=hi!==null&&!(v<hi.v||(hi.eq&&v===hi.v));
  if(!below&&!above)return null;
  if(lo!==null&&hi!==null)return betweenText(label,num(lo.v),num(hi.v),u);
  return lo!==null?`${label} must be greater than ${num(lo.v)} ${u}.`:`${label} must be less than ${num(hi.v)} ${u}.`;
 };
 const at=k=>{const x=inUnit(d[k],unit);return x;};
 let m=/^domain\.([xyz])(min|max)$/.exec(key);
 if(m){const other=at(m[1]+(m[2]==='min'?'max':'min'));if(other===null)return null;
  return between(`Domain ${m[1]} ${m[2]}`,m[2]==='max'?{v:other,eq:false}:null,m[2]==='min'?{v:other,eq:false}:null);}
 m=/^features\[(\d+)\]\.([xyz])(min|max)$/.exec(key);
 if(m){const f=comp.features[+m[1]],axis=m[2];
  // a cylinder's zmin < zmax only: its extent against the domain is the server's (a combination)
  const other=inUnit(f[axis+(m[3]==='min'?'max':'min')],unit),dmin=f.type==='cylinder'?null:at(axis+'min'),dmax=f.type==='cylinder'?null:at(axis+'max');
  const lo=m[3]==='min'?(dmin===null?null:{v:dmin,eq:true}):(other===null?null:{v:other,eq:false});
  const hi=m[3]==='min'?(other===null?null:{v:other,eq:false}):(dmax===null?null:{v:dmax,eq:true});
  return between(`${cap(f.name)} ${axis} ${m[3]}`,lo,hi);}
 // a cylinder's or sphere's radius: above 0. Its centre and radius against the domain are a
 // combination, which the server checks (the engine's stems, such as "crosses the side ...")
 m=/^features\[(\d+)\]\.r$/.exec(key);
 if(m)return between(`${cap(comp.features[+m[1]].name)} r`,{v:0,eq:false},null);
 m=/^(?:features\[(\d+)\]|mesh)\.element_size$/.exec(key);
 if(m){const ext=AXES.map(a=>{const lo=at(a+'min'),hi=at(a+'max');return lo===null||hi===null?null:hi-lo;});
  if(ext.includes(null))return null;
  const diag=Math.hypot(...ext),lo=Number((diag/400).toPrecision(3)),hi=Number((diag/4).toPrecision(3));
  const label=m[1]===undefined?'Mesh':cap(comp.features[+m[1]].name);
  return v<diag/400||v>diag/4?betweenText(`${label} element size`,lo,hi,u):null;}
 return null;
}
const thicknessLabel=(doc,key)=>{const m=/^features\[(\d+)\]\.layers\[(\d+)\]/.exec(key),f=component(doc).features[+m[1]];
 return `${cap(f.name)} ${f.layers[+m[2]].name} thickness`;};

/**
 * One field edit: {doc} with the field set, or {problem} when the text cannot be stored (the page
 * keeps it as a highlighted draft, which blocks Save, Mesh and Run until it is fixed or restored).
 */
export function editField(doc,field,raw){
 const unit=component(doc).length_unit;
 if(field.kind==='length'){
  if(field.optional&&String(raw??'').trim()==='')return {doc:setField(doc,field.key,undefined),si:null};
  const p=parseLength(raw,unit,field.rule);
  if(p.problem==='positive')return {problem:`${thicknessLabel(doc,field.key)} must be greater than 0 ${shownUnit(unit)}.`};
  if(field.rule?.meshSize&&(p.problem||p.si===null))return {problem:'A mesh size is a number or a quantity such as 20 um.'};
  if(p.problem)return {problem:p.problem};
  if(p.si!==null){const problem=rangeProblem(doc,field.key,p.si/UNITS[unit]);if(problem)return {problem};}
  // the document mesh block takes quantities: a bare number is in the component's unit
  const stored=field.rule?.meshSize&&typeof p.value==='number'?`${p.value} ${unit}`:p.value;
  return {doc:setField(doc,field.key,stored),si:p.si};
 }
 const text=String(raw??'').trim();
 if(field.kind==='name'){
  if(!NAME.test(text))return {problem:'A name starts with a letter or _ and holds letters, digits and _.'};
  const comp=component(doc),lm=/^features\[(\d+)\]\.layers\[(\d+)\]\.name$/.exec(field.key),fm=/^features\[(\d+)\]\.name$/.exec(field.key);
  if(lm){const f=comp.features[+lm[1]];if(f.layers.some((l,j)=>j!==+lm[2]&&l.name===text))return {problem:`${text} is already the name of another layer of ${f.name}.`};}
  if(fm&&comp.features.some((f,i)=>i!==+fm[1]&&f.name===text))return {problem:`${text} is already the name of another feature.`};
  return {doc:setField(doc,field.key,text)};
 }
 if(field.kind==='material'){
  if(text==='')return {doc:setField(doc,field.key,null)};       // void
  if(!(text in (doc.materials||{})))return {problem:`${text} is not a material of this model (${Object.keys(doc.materials||{}).join(', ')||'none'}).`};
  return {doc:setField(doc,field.key,text)};
 }
 return {problem:'This field cannot be edited here.'};
}

// ---- the tree --------------------------------------------------------------------------------

/** A feature's row label: "1 Layers stack", "2 Box via". */
export const featureLabel=(f,i)=>`${i+1} ${TYPE_LABEL[f.type]||f.type} ${f.name}`;

/** What a feature's row says beside its label: its layers, or a box's size. */
function featureSummary(comp,f){
 if(f.type==='layers')return f.layers.map(l=>l.name).join(' · ');
 if(f.type==='box'){const size=AXES.map(a=>{const lo=inUnit(f[a+'min'],comp.length_unit),hi=inUnit(f[a+'max'],comp.length_unit);return lo===null||hi===null?null:num(hi-lo);});
  return size.includes(null)?'':`${size.join(' × ')} ${shownUnit(comp.length_unit)}`;}
 if(f.type==='cylinder'||f.type==='sphere'){
  const v=k=>{const x=inUnit(f[k],comp.length_unit);return x===null?null:num(x);},u=shownUnit(comp.length_unit),r=v('r');
  if(r===null)return '';
  if(f.type==='sphere')return `r ${r} ${u}`;
  const z0=v('zmin'),z1=v('zmax');return z0===null||z1===null?`r ${r} ${u}`:`r ${r} ${u} · z ${z0}–${z1} ${u}`;}
 return '';
}
const plural=(n,one)=>`${n} ${one}${n===1?'':'s'}`;
/**
 * The tree rows (design 5.2, for this step): Component 1 · 3D · <unit>, with Parameters, Geometry 1
 * (Domain, the numbered features and Form result) and Materials. check: the last /api/model3d/check
 * answer for this document (or null); refused: the last refusal ({feature_index}) or null.
 * Each row: {key, label, level, note, problem}.
 */
export function treeRows(doc,check=null,refused=null,words=null,{runs=[]}={}){
 const comp=component(doc),rows=[],u=shownUnit(comp.length_unit),d=comp.domain||{};
 const params=Object.entries(doc.geometry.parameters||{});
 rows.push({key:'component',label:`Component 1 · 3D · ${u}`,level:1,note:'',problem:false});
 rows.push({key:'parameters',label:'Parameters',level:2,note:params.map(([n,p])=>`${n} = ${p.value}`).join(' · '),problem:!!refused&&/^geometry\.parameters\b/.test(refused.path||'')});
 rows.push({key:'geometry',label:'Geometry 1',level:2,note:'',problem:false});
 const ext=AXES.map(a=>{const lo=inUnit(d[a+'min'],comp.length_unit),hi=inUnit(d[a+'max'],comp.length_unit);return lo===null||hi===null?null:num(hi-lo);});
 const zFree=d.zmin===undefined&&d.zmax===undefined;
 rows.push({key:'domain',label:'Domain',level:3,note:ext[0]===null||ext[1]===null?'':zFree?`${ext[0]} × ${ext[1]} ${u}, z from the features`:ext[2]===null?`${ext[0]} × ${ext[1]} ${u}`:`${ext.join(' × ')} ${u}`,problem:false});
 const meshOff=meshRefusal(check);
 comp.features.forEach((f,i)=>{
  const cover=check?.features?.[i]?.text||'',summary=featureSummary(comp,f);
  rows.push({key:`feature:${i}`,label:featureLabel(f,i),level:3,note:[summary,cover&&`(${cover})`].filter(Boolean).join(' '),
   problem:refused?.feature_index===i||meshOff?.feature_index===i});
 });
 const faces=check?.display?.faces?.length;
 rows.push({key:'form',label:'Form result',level:3,note:refused?'refused':check?`${plural(check.regions.length,'region')}${faces===undefined?'':' · '+plural(faces,'face')}`:'',
  problem:!!refused&&refused.feature_index===null&&!/^geometry\.parameters\b/.test(refused.path||'')});
 rows.push({key:'materials',label:'Materials',level:2,note:Object.keys(doc.materials||{}).join(' · '),problem:false});
 const size=doc.mesh?.element_size,sizeText=size===undefined?'':`size ${String(size).replace(/\bum\b/g,'µm')}`;
 const est=!refused&&check?.mesh?.ok&&words?words.estimateText(check.mesh.estimate):'';
 rows.push(...heatRows(doc,check,refused));
 rows.push({key:'mesh',label:'Mesh 1',level:2,note:meshOff?'refused':[sizeText,est].filter(Boolean).join(' · '),
  problem:!!meshOff&&(meshOff.feature_index===null||meshOff.feature_index===undefined)});
 rows.push({key:'study',label:'Study 1 · Steady',level:2,note:'',problem:false});
 rows.push({key:'results',label:'Results',level:2,note:runs.length?`${runs.length} ${runs.length===1?'run':'runs'}`:'no run yet',problem:false});
 runs.forEach((r,i)=>rows.push({key:`run:${i+1}`,label:`Run ${i+1} · Temperature (surfaces)`,level:3,note:'',problem:false}));
 return rows;
}

// ---- feature operations (each a new document) ---------------------------------------------------

function uniqueName(comp,base){
 const taken=new Set([...comp.features.map(f=>f.name),...Object.keys(comp.selections||{})]);
 if(!taken.has(base))return base;
 for(let k=2;;k++)if(!taken.has(`${base}_${k}`))return `${base}_${k}`;
}

/** Move feature i up (-1) or down (+1); later features win, so the order is the model. */
export function moveFeature(doc,i,delta){
 const out=copy(doc),list=component(out).features,j=i+delta;
 if(j<0||j>=list.length)fail(delta<0?'The first feature cannot move up.':'The last feature cannot move down.');
 [list[i],list[j]]=[list[j],list[i]];return out;
}
/** Duplicate feature i right after it, named <name>_2 (or the next free number). */
export function duplicateFeature(doc,i){
 const out=copy(doc),comp=component(out),f=copy(comp.features[i]);
 f.name=uniqueName(comp,f.name);comp.features.splice(i+1,0,f);return out;
}
/** The notice after deleting feature i of doc: "via deleted; Undo restores it." */
export const deletedText=(doc,i)=>`${component(doc).features[i].name} deleted; Undo restores it.`;
/** Add a layer row at the top of layers feature i (1 to 32 rows). */
export function addLayer(doc,i){
 const out=copy(doc),f=component(out).features[i];
 if(f.layers.length>=MAX_LAYERS)fail('A layers feature holds 1 to 32 layers.');
 const taken=new Set(f.layers.map(l=>l.name));let name='layer',k=2;while(taken.has(name))name=`layer_${k++}`;
 const last=f.layers.at(-1);f.layers.push({name,thickness:typeof last?.thickness==='number'?last.thickness:1,material:last?.material??null});return out;
}
/** Remove layer row j of layers feature i (at least one stays). */
export function removeLayer(doc,i,j){
 const out=copy(doc),f=component(out).features[i];
 if(f.layers.length<=1)fail('A layers feature holds 1 to 32 layers.');
 f.layers.splice(j,1);return out;
}
/** Delete feature i (Undo restores it). */
export function deleteFeature(doc,i){const out=copy(doc);component(out).features.splice(i,1);return out;}
/**
 * A new feature at the end: a box in the middle of the domain, a layers feature with one slab, a
 * cylinder through the whole domain height at the x-y centre (r a quarter of the smaller x-y extent),
 * a sphere at the centre (r a quarter of the smallest extent). Whether a builder takes it is the
 * check's answer, in the engine's words.
 */
export function addFeature(doc,type){
 const kind=FEATURE_TYPES.find(t=>t.type===type);
 if(!kind)fail(`Unknown feature type ${type}.`);
 if(!kind.available)fail(kind.reason);
 const out=copy(doc),comp=component(out),d=comp.domain;
 const num=v=>typeof v==='number'?v:null;
 const mid=(a,b)=>num(d[a])!==null&&num(d[b])!==null?[(3*d[a]+d[b])/4,(d[a]+3*d[b])/4]:[0,1];
 const material=Object.keys(out.materials||{})[0]??null;
 if(type==='box'){const [x0,x1]=mid('xmin','xmax'),[y0,y1]=mid('ymin','ymax'),[z0,z1]=mid('zmin','zmax');
  comp.features.push({name:uniqueName(comp,'box'),type:'box',xmin:x0,xmax:x1,ymin:y0,ymax:y1,zmin:z0,zmax:z1,material});}
 else if(type==='cylinder'||type==='sphere'){
  const axes=type==='cylinder'?['x','y']:AXES,known=AXES.every(a=>num(d[a+'min'])!==null&&num(d[a+'max'])!==null);
  const c=a=>known?(d[a+'min']+d[a+'max'])/2:0,r=known?Math.min(...axes.map(a=>d[a+'max']-d[a+'min']))/4:0.25;
  comp.features.push(type==='cylinder'
   ?{name:uniqueName(comp,'cylinder'),type:'cylinder',cx:c('x'),cy:c('y'),r,zmin:known?d.zmin:0,zmax:known?d.zmax:1,material}
   :{name:uniqueName(comp,'sphere'),type:'sphere',cx:c('x'),cy:c('y'),cz:c('z'),r,material});}
 else{const [z0,z1]=mid('zmin','zmax');
  comp.features.push({name:uniqueName(comp,'layers'),type:'layers',z0,layers:[{name:'layer',thickness:z1-z0,material}]});}
 return out;
}

// ---- parameters ------------------------------------------------------------------------------

/** Add a parameter (a quantity such as "20 um", a number or an expression). */
export function addParameter(doc,name,value){
 if(!NAME.test(name))fail('A parameter name starts with a letter or _ and holds letters, digits and _.');
 const out=copy(doc),params=out.geometry.parameters||(out.geometry.parameters={});
 if(name in params)fail(`A parameter ${name} already exists.`);
 if(String(value??'').trim()==='')fail('A parameter value cannot be empty.');
 params[name]={value:NUMBER.test(String(value).trim())?Number(value):String(value).trim()};return out;
}
/** Set a parameter's value as typed. */
export function setParameter(doc,name,value){
 const out=copy(doc),params=out.geometry.parameters||{};
 if(!(name in params))fail(`Unknown parameter ${name}.`);
 if(String(value??'').trim()==='')fail('A parameter value cannot be empty.');
 params[name].value=NUMBER.test(String(value).trim())?Number(value):String(value).trim();return out;
}
/** The words of a field key for a person: "features[0].layers[1].thickness" → "stack.oxide thickness". */
export function fieldWords(doc,key){
 const comp=component(doc);
 let m=/^features\[(\d+)\]\.layers\[(\d+)\]\.(\w+)$/.exec(key);
 if(m){const f=comp.features[+m[1]],l=f?.layers?.[+m[2]];return f&&l?`${f.name}.${l.name} ${m[3]}`:key;}
 m=/^features\[(\d+)\]\.(\w+)$/.exec(key);
 if(m){const f=comp.features[+m[1]];return f?`${f.name} ${m[2]}`:key;}
 const p=/^parameters\.(\w+)$/.exec(key);if(p)return `parameter ${p[1]}`;
 return key.replace(/^domain\./,'domain ');
}
/** Field keys in the model's order: the domain, the features in order (each in table order), then the rest. */
function fieldOrder(doc,keys){
 const all=[...fieldsOf(doc,'domain'),...component(doc).features.flatMap((f,i)=>fieldsOf(doc,`feature:${i}`))].map(f=>f.key);
 const rank=k=>{const i=all.indexOf(k);return i<0?all.length:i;};
 return [...keys].sort((a,b)=>rank(a)-rank(b)||(a<b?-1:a>b?1:0));
}
/**
 * Delete a parameter; refused while it is used. usedBy: the check's list for it (field keys).
 * The refusal names its users in feature order: "t_ox is used by stack.oxide thickness."
 */
export function deleteParameter(doc,name,usedBy=[]){
 const out=copy(doc),params=out.geometry.parameters||{};
 if(!(name in params))fail(`Unknown parameter ${name}.`);
 if(usedBy.length)fail(`${name} is used by ${fieldOrder(doc,usedBy).map(k=>fieldWords(doc,k)).join(', ')}.`);
 delete params[name];if(!Object.keys(params).length)delete out.geometry.parameters;return out;
}

// ---- undo: one history of documents for the 3D model (no view state) ----------------------------

export class Model3dHistory{
 constructor(doc,limit=100){this.items=[JSON.stringify(doc)];this.at=0;this.limit=limit;}
 get doc(){return JSON.parse(this.items[this.at]);}
 /** Record a new document; an equal one records nothing. Returns whether it was recorded. */
 record(doc){
  const text=JSON.stringify(doc);if(text===this.items[this.at])return false;
  this.items=this.items.slice(0,this.at+1);this.items.push(text);
  if(this.items.length>this.limit)this.items.shift();this.at=this.items.length-1;return true;
 }
 get canUndo(){return this.at>0;}
 get canRedo(){return this.at<this.items.length-1;}
 undo(){if(this.canUndo)this.at--;return this.doc;}
 redo(){if(this.canRedo)this.at++;return this.doc;}
}

// ---- refusals and messages -------------------------------------------------------------------

/** The Messages entry of a refusal: the engine's words as written, the code and path under Details. */
export function refusalMessage(refusal){
 return {text:refusal.refused,details:refusal.code?`${refusal.code}${refusal.path?' at '+refusal.path:''}`:(refusal.path||''),
  feature:refusal.feature_index??null};
}
/** The refusal that blocks meshing in a check answer (the shape formed), or null. */
export const meshRefusal=check=>check?.mesh&&check.mesh.ok===false?check.mesh:null;
/**
 * Why Mesh is not offered, or null: a draft, the shape's refusal, the mesh refusal in the
 * engine's words, a running job (slice C's words), no check yet.
 */
export function meshReason({drafts=0,refused=null,check=null,running=false}={},words){
 if(drafts||refused)return blockReason({drafts,refused});
 const off=meshRefusal(check);
 return words.meshBlocked({estimate:check?.mesh?.ok?check.mesh.estimate:null,refused:off?off.refused:null,running});
}
/** Why Mesh and Run are not offered: a refusal, a draft, or (in this step) that they come later. */
export function blockReason({refused=null,drafts=0}={}){
 if(drafts)return `Correct the highlighted ${drafts===1?'field':'fields'} or restore ${drafts===1?'its':'their'} last valid ${drafts===1?'value':'values'} first.`;
 if(refused)return 'Fix 1 problem in Messages to mesh';
 return 'Heat comes in a later step of the 3D model.';
}

// ---- heat transfer (slice D): the thermal.steady3d block of the document ------------------------
export const HEAT='thermal.steady3d';
/** The document's thermal.steady3d block, or null. */
export const heatOf=doc=>doc?.physics?.heat?.type===HEAT?doc.physics.heat:null;
const shownQuantity=v=>String(v).replace(/W\/m\^3/g,'W/m³');
function heatRows(doc,check,refused){
 const h=heatOf(doc),off=!!h&&!refused&&check?.run&&check.run.ok===false;   // no heat block: the note says so, no mark
 const rows=[{key:'heat',label:'Heat transfer (3D)',level:2,note:h?'':'not set: Add a fixed temperature',problem:!!off}];
 if(!h)return rows;
 rows.push({key:'heat:k',label:'Thermal conductivity',level:3,note:'from Materials',problem:false});
 Object.entries(h.prescribed_temperature||{}).forEach(([name,v],i)=>
  rows.push({key:`heat:fixed:${name}`,label:`Fixed temperature ${i+1}`,level:3,note:`${name} · ${shownQuantity(v)}`,problem:false}));
 const src=h.heat_source_density;
 if(src!==undefined){
  const list=typeof src==='object'&&src!==null?Object.entries(src):[['every region',src]];
  list.forEach(([region,v],i)=>rows.push({key:`heat:source:${region}`,label:`Heat source ${i+1}`,level:3,note:`${region} · ${shownQuantity(v)}`,problem:false}));
 }
 rows.push({key:'heat:insulated',label:'Insulated',level:3,note:'every other outer face',problem:false});
 return rows;
}
const QNUM=/^([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)(?:\s*(\S.*))?$/;
// a quantity typed in a heat field: a number (in the field's unit) or a number and that unit
function quantity(raw,spec){
 const {label,unit,aliases,min,max,shown}=spec;
 const m=QNUM.exec(String(raw??'').trim());
 if(!m)return fail(`Enter ${label.toLowerCase()} as a number or a quantity such as ${min>0?min*100:1} ${shown}.`);
 const v=Number(m[1]);if(!Number.isFinite(v))return fail(`${m[1]} is not a finite number.`);
 if(m[2]!==undefined&&!aliases.includes(m[2]))return fail(`${m[2]} is not a ${label==='Fixed temperature'?'temperature':label==='Heat source'?'heat source density':'conductivity'} unit (${shown}).`);
 if(v<min||v>max)return fail(betweenText(label,spec.minText??min,spec.maxText??max,shown));
 return `${m[1]} ${unit}`;
}
const T_FIELD={label:'Fixed temperature',unit:'K',aliases:['K'],min:1,max:2000,shown:'K'};
const Q_FIELD={label:'Heat source',unit:'W/m^3',aliases:['W/m^3','W/m³'],min:-1e15,max:1e15,minText:'-1e15',maxText:'1e15',shown:'W/m³'};
const K_FIELD={label:'Thermal conductivity',unit:'W/(m K)',aliases:['W/(m K)','W/(m·K)','W/m/K'],min:1e-3,max:1e4,shown:'W/(m K)'};
function withHeat(doc){
 const out=copy(doc);out.physics=out.physics||{};
 if(!heatOf(out))out.physics.heat={type:HEAT};
 return out;
}
/** Set (or add) the fixed temperature on a boundary name: "300" or "300 K", 1 to 2000 K. */
export function setFixedTemperature(doc,name,raw){
 const value=quantity(raw,T_FIELD),out=withHeat(doc),h=out.physics.heat;
 h.prescribed_temperature={...(h.prescribed_temperature||{}),[name]:value};return out;
}
export function removeFixedTemperature(doc,name){
 const out=copy(doc),h=heatOf(out);if(!h?.prescribed_temperature)return out;
 delete h.prescribed_temperature[name];return out;
}
/** Set (or add) a heat source on a meshed region: W/m^3, -1e15 to 1e15. */
export function setHeatSource(doc,region,raw){
 const value=quantity(raw,Q_FIELD),out=withHeat(doc),h=out.physics.heat;
 const src=typeof h.heat_source_density==='object'&&h.heat_source_density!==null?h.heat_source_density:{};
 h.heat_source_density={...src,[region]:value};return out;
}
export function removeHeatSource(doc,region){
 const out=copy(doc),h=heatOf(out);if(!h||h.heat_source_density===undefined)return out;
 if(typeof h.heat_source_density==='object')delete h.heat_source_density[region];
 if(typeof h.heat_source_density!=='object'||!Object.keys(h.heat_source_density).length)delete h.heat_source_density;
 return out;
}
/** A material's thermal conductivity: W/(m K), 0.001 to 10000. */
export function setConductivity(doc,material,raw){
 const value=quantity(raw,K_FIELD),out=copy(doc);
 out.materials={...(out.materials||{})};out.materials[material]={...(out.materials[material]||{}),thermal_conductivity:value};return out;
}
/** The meshed regions a heat source can name (the check's display regions). */
export const editableRegions=check=>(check?.display?.regions||[]).map(r=>r.name);

const BUSY='Studio is already running one 3D heat model; wait for it or cancel it.';
/**
 * Why Run is not offered, or null, in this order: a draft, the shape's refusal, the mesh refusal,
 * the reader's refusal (the check's run part), a run going, and the refusal the last run of this
 * very document ended with (the unanchored group, known only on the mesh).
 */
export function runReason({drafts=0,refused=null,check=null,running=false,doc=null,failure=null}={},words){
 if(drafts)return blockReason({drafts});
 if(refused)return 'Fix 1 problem in Messages to run';
 if(!check)return 'Show a 3d component first.';
 const off=meshRefusal(check);if(off)return off.refused;
 if(check.run&&check.run.ok===false)return check.run.refused;
 if(running)return BUSY;
 if(failure&&doc&&canonicalJson(failure.document)===canonicalJson(doc))return failure.message;
 return null;
}
/** The index of the latest kept run whose document equals doc (key order aside), or -1. */
export function keptRunFor(doc,records){
 const text=canonicalJson(doc);
 for(let i=records.length-1;i>=0;i--)if(records[i].result===RUN_RECORD&&canonicalJson(records[i].document)===text)return i;
 return -1;
}
export const noNeedText=i=>`No need to run: Run ${i+1} already has these results.`;

// a diverging map (cool to warm): blue at the minimum, grey in the middle, red at the maximum
const STOPS=[[0.231,0.298,0.753],[0.865,0.865,0.865],[0.706,0.016,0.150]];
export function temperatureColor(t,tmin,tmax){
 const u=tmax>tmin?Math.min(1,Math.max(0,(t-tmin)/(tmax-tmin))):0.5,x=u*2,i=Math.min(1,Math.floor(x)),f=x-i;
 return STOPS[i].map((c,k)=>Number((c+(STOPS[i+1][k]-c)*f).toFixed(3)));
}
const sig=(v,n=6)=>Number(Number(v).toPrecision(n));
const sci=v=>Math.abs(v)<1e-3&&v!==0?Number(v).toPrecision(3):String(sig(v));
/** The values table of a run: [label, text] rows. */
export function valuesRows(values,unit){
 const per=UNITS[unit]||1,u=shownUnit(unit);
 const place=t=>`${sig(t.value)} ${t.unit} in ${t.region} at (${t.position_m.map(x=>sig(x/per,3)).join(', ')}) ${u}`;
 const rows=[['Temperature, max',place(values.temperature_max)],['Temperature, min',place(values.temperature_min)]];
 for(const [name,q] of Object.entries(values.heat_rate_by_selection||{}))rows.push([`Heat rate through ${name}`,`${sig(q.value)} ${q.unit}`]);
 rows.push(['Total heat source',`${sig(values.total_source.value)} ${values.total_source.unit}`]);
 rows.push(['Energy balance residual',`${sci(values.balance_residual.value)} ${values.balance_residual.unit} (${sci(values.relative_balance_residual.value)} of the source)`]);
 return rows;
}
const clock=s=>`${Math.floor(s/60)}:${String(Math.floor(s%60)).padStart(2,'0')}`;
/** The one-line progress of a run status answer. */
export function runProgress(s){
 if(s.status==='cancelled')return 'Run cancelled; nothing kept.';
 if(s.status==='error')return 'Run failed: '+(s.error?.message||'unknown error');
 if(s.status==='done')return 'Done';
 return `${{mesh:'Meshing',solve:'Solving',done:'Done'}[s.step]||'Running'} · ${clock(s.elapsed_s||0)}`+(s.longer_than_estimate?' · taking longer than the estimate':'');
}
/**
 * The boundary name "Use for → Fixed temperature" writes for a picked face: of the names that select
 * it alone, the one of the latest feature (later features win where they meet), else the first.
 */
export function boundaryNameFor(face,featureIds){
 const alone=face?.alone||[];if(!alone.length)return null;
 const rank=n=>featureIds.indexOf(n.split('.')[0]);
 return [...alone].sort((a,b)=>rank(b)-rank(a))[0];
}
