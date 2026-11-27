// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
import {fitShapeEdit} from './workspace-shapes.mjs';

export const INPUT_FIELDS=Object.freeze({
 height:Object.freeze({label:'Core height',unit:'nm',min:100,max:500,id:'height-number',node:'Geometry'}),
 width:Object.freeze({label:'Core width',unit:'nm',min:300,max:900,id:'width-number',node:'Geometry'}),
 wavelength:Object.freeze({label:'Wavelength',unit:'nm',min:1400,max:1700,id:'wavelength-number',node:'Optical modes'}),
 // the number of modes a run asks for: a whole number, no unit (page state; not in the project file)
 modeCount:Object.freeze({label:'Modes to find',unit:'',min:1,max:8,id:'mode-count-number',node:'Optical modes',integer:true}),
 coreMesh:Object.freeze({label:'Core mesh size',unit:'nm',min:20,max:60,id:'core-mesh-number',node:'Mesh'}),
 // Selected-shape properties; whole-shape limits (window, minimum size) are checked after parsing.
 shapeX:Object.freeze({label:'Left x',unit:'nm',min:-1500,max:1490,id:'shape-x',node:'Geometry',prop:'x'}),
 shapeY:Object.freeze({label:'Bottom y',unit:'nm',min:-1200,max:1190,id:'shape-y',node:'Geometry',prop:'y'}),
 shapeW:Object.freeze({label:'Width',unit:'nm',min:10,max:3000,id:'shape-w',node:'Geometry',prop:'w'}),
 shapeH:Object.freeze({label:'Height',unit:'nm',min:10,max:2400,id:'shape-h',node:'Geometry',prop:'h'}),
 shapeCx:Object.freeze({label:'Centre x',unit:'nm',min:-1490,max:1490,id:'shape-cx',node:'Geometry',prop:'cx'}),
 shapeCy:Object.freeze({label:'Centre y',unit:'nm',min:-1190,max:1190,id:'shape-cy',node:'Geometry',prop:'cy'}),
 shapeR:Object.freeze({label:'Radius',unit:'nm',min:10,max:1200,id:'shape-r',node:'Geometry',prop:'r'}),
 voltage:Object.freeze({label:'Applied voltage',unit:'V',min:0,max:10,id:'setup-voltage',node:'Electric currents'}),
 temperature:Object.freeze({label:'Boundary temperature',unit:'K',min:1,max:2000,id:'temperature',node:'Heat transfer'})
});
// The Messages line after a numeric edit: what changed, a Left x that a Width edit moved to keep
// the centre, and that nothing is computed until Run. afterResult: a result was just announced.
const signed=v=>String(v).replace(/^-/,'−');
// kept 'left' (round 16): the Width kept Left x at leftX, as centred the shape would leave the window.
// also: the refused values of the same shape applied after this edit ([{key, value}]).
export function editNoticeText(key,value,{leftX=null,afterResult=false,kept=null,also=[]}={}){
 const field=INPUT_FIELDS[key];if(!field)throw new Error('Unknown numeric field.');
 const unit=f=>f.unit?' '+f.unit:'';
 const moved=leftX===null?'':kept==='left'?` Left x kept at ${signed(leftX)} ${INPUT_FIELDS.shapeX.unit}: centred, the shape would leave the window.`:` Left x moved to ${signed(leftX)} ${INPUT_FIELDS.shapeX.unit} to keep the centre.`;
 const more=also.map(a=>` ${INPUT_FIELDS[a.key].label} set to ${signed(a.value)}${unit(INPUT_FIELDS[a.key])} too.`).join('');
 return `${field.label} set to ${signed(value)}${unit(field)}.${moved}${more} `+(afterResult?'Inputs changed since the last result. Run again to compute the new inputs.':'Run explicitly to compute new results.');
}
/** The range sentence of a refused value ("Core width must be between 300–900 nm."); the 3D builder uses it too. */
export const betweenText=(label,min,max,unit)=>`${label} must be between ${min}–${max}${unit?' '+unit:''}.`;
export function parseNumeric(key,raw){
 const field=INPUT_FIELDS[key];if(!field)throw new Error('Unknown numeric field.');
 const text=String(raw).trim(),range=`${field.min}–${field.max} ${field.unit}`;
 // a count: a whole number in its range, one message for every refusal
 if(field.integer){const whole=`${field.label} must be a whole number from ${field.min} to ${field.max}.`;
  if(!/^[+]?\d+$/.test(text))return {ok:false,message:whole};const n=Number(text);return n>=field.min&&n<=field.max?{ok:true,value:n}:{ok:false,message:whole};}
 if(!text)return {ok:false,message:`${field.label} is required. Enter ${range}.`};
 if(!/^[+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?$/i.test(text)||!Number.isFinite(Number(text)))return {ok:false,message:`${field.label} must be a finite number in ${range}.`};
 const value=Number(text);
 if(value<field.min||value>field.max)return {ok:false,message:betweenText(field.label,field.min,field.max,field.unit)};
 return {ok:true,value};
}
export class NumericDrafts {
 #pending=new Map();
 reject(key,raw,message){if(!INPUT_FIELDS[key])throw new Error('Unknown numeric field.');this.#pending.set(key,{key,raw:String(raw),message});return {ok:false,message};}
 get shapeInvalid(){return [...this.#pending.keys()].some(key=>INPUT_FIELDS[key].prop);}
 update(key,raw){const result=parseNumeric(key,raw);if(result.ok)this.#pending.delete(key);else this.#pending.set(key,{key,raw:String(raw),message:result.message});return result;}
 get(key){const d=this.#pending.get(key);return d?{...d}:null;}
 get issues(){return [...this.#pending.values()].map(d=>({...d}));}
 get invalid(){return this.#pending.size>0;}
 clear(key){if(key===undefined)this.#pending.clear();else this.#pending.delete(key);}
 assertValid(){if(this.invalid)throw new Error('Correct the highlighted inputs or restore their last valid values before saving or running.');}
}
// A refused shape draft is tried again when another field of the same shape changes (round 16):
// each draft (other than `except`) whose text is a number in range is applied to `shape` as typed
// now (fitShapeEdit), and its draft cleared. Returns {shape, applied: [{key, value, kept}]}.
export function retryShapeDrafts(drafts,shape,except,{index=0}={}){
 let current=shape;const applied=[];
 for(const d of drafts.issues){
  const field=INPUT_FIELDS[d.key];if(!field.prop||d.key===except)continue;
  const parsed=parseNumeric(d.key,d.raw);if(!parsed.ok)continue;
  try{const fit=fitShapeEdit(current,field.prop,parsed.value,{index});current=fit.shape;drafts.clear(d.key);applied.push({key:d.key,value:parsed.value,kept:fit.kept});}catch{}
 }
 return {shape:current,applied};
}
// The settings that differ between two inputs files (optical, version 7 or 8), from → to in the
// inspector's words, for "Use this run's inputs": "Width 700 → 600 nm · Modes to find 4 → 2".
// A shape's own fields are named alone when both inputs have one shape ("Width"), else after the
// shape ("Core width"); a different shape count reads "Shapes 1 → 2" and its own fields are not
// listed. Returns the list (empty when nothing listed differs).
const SHAPE_FIELDS=Object.freeze([['type','Shape type',''],['material','Material',''],['w','Width','nm'],['h','Height','nm'],['r','Radius','nm'],['x','Left x','nm'],['y','Bottom y','nm'],['cx','Centre x','nm'],['cy','Centre y','nm']]);
export function inputChanges(before,after){
 const out=[],show=v=>typeof v==='number'?signed(v):String(v);
 const add=(label,from,to,unit='')=>{if(from!==to)out.push(`${label} ${show(from)} → ${show(to)}${unit?' '+unit:''}`);};
 const a=before.model,b=after.model;
 add('Wavelength',a.wavelength,b.wavelength,'nm');add('Core mesh size',a.coreMesh,b.coreMesh,'nm');
 const sa=a.shapes||[],sb=b.shapes||[];
 if(sa.length!==sb.length)out.push(`Shapes ${sa.length} → ${sb.length}`);
 else{const one=sa.length===1;sa.forEach((s,i)=>{const t=sb[i],named=label=>one?label:`${t.name||'Shape '+(i+1)} ${label.charAt(0).toLowerCase()+label.slice(1)}`;
  for(const [key,label,unit] of SHAPE_FIELDS)if(key in s||key in t)add(named(label),s[key]??'—',t[key]??'—',unit);
  if((s.points||t.points)&&JSON.stringify(s.points)!==JSON.stringify(t.points))out.push(named('Vertices')+' changed');});}
 for(const body of Object.keys({...before.setup?.materials,...after.setup?.materials}))add(`${body} material`,before.setup?.materials?.[body]||'none',after.setup?.materials?.[body]||'none');
 add('Modes to find',a.modeCount??2,b.modeCount??2);
 add('Group index',a.groupIndex===true?'on':'off',b.groupIndex===true?'on':'off');
 return out;
}
