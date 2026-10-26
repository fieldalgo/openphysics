// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

export const INPUT_FIELDS=Object.freeze({
 height:Object.freeze({label:'Core height',unit:'nm',min:100,max:500,id:'height-number',node:'Geometry'}),
 width:Object.freeze({label:'Core width',unit:'nm',min:300,max:900,id:'width-number',node:'Geometry'}),
 wavelength:Object.freeze({label:'Wavelength',unit:'nm',min:1400,max:1700,id:'wavelength-number',node:'Optical modes'}),
 coreMesh:Object.freeze({label:'Core mesh size',unit:'nm',min:20,max:60,id:'core-mesh-number',node:'Mesh'}),
 voltage:Object.freeze({label:'Applied voltage',unit:'V',min:0,max:10,id:'setup-voltage',node:'Electric currents'}),
 temperature:Object.freeze({label:'Boundary temperature',unit:'K',min:1,max:2000,id:'temperature',node:'Heat transfer'})
});
export function parseNumeric(key,raw){
 const field=INPUT_FIELDS[key];if(!field)throw new Error('Unknown numeric field.');
 const text=String(raw).trim(),range=`${field.min}–${field.max} ${field.unit}`;
 if(!text)return {ok:false,message:`${field.label} is required. Enter ${range}.`};
 if(!/^[+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?$/i.test(text)||!Number.isFinite(Number(text)))return {ok:false,message:`${field.label} must be a finite number in ${range}.`};
 const value=Number(text);
 if(value<field.min||value>field.max)return {ok:false,message:`${field.label} must be between ${range}.`};
 return {ok:true,value};
}
export class NumericDrafts {
 #pending=new Map();
 update(key,raw){const result=parseNumeric(key,raw);if(result.ok)this.#pending.delete(key);else this.#pending.set(key,{key,raw:String(raw),message:result.message});return result;}
 get(key){const d=this.#pending.get(key);return d?{...d}:null;}
 get issues(){return [...this.#pending.values()].map(d=>({...d}));}
 get invalid(){return this.#pending.size>0;}
 clear(key){if(key===undefined)this.#pending.clear();else this.#pending.delete(key);}
 assertValid(){if(this.invalid)throw new Error('Correct the highlighted inputs or restore their last valid values before saving or running.');}
}
