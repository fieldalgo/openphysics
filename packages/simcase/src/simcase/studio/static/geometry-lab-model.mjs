// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Pure helpers of the experimental geometry lab: no DOM, no network, so Node tests them.

/** A deep copy of a JSON document (the lab never edits the caller's object). */
export function copyDocument(doc){return JSON.parse(JSON.stringify(doc));}

/** Whether the document carries a version 1 geometry block (the lab reads nothing else). */
export function isVersion1(doc){
 return !!doc&&typeof doc==='object'&&!!doc.geometry&&typeof doc.geometry==='object'&&'version' in doc.geometry;
}

/** A quantity string "<number> <unit>" as {number, unit}, else null. */
export function quantityOf(text){
 const m=typeof text==='string'?/^\s*([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?) (\S+)\s*$/.exec(text):null;
 return m&&Number.isFinite(Number(m[1]))?{number:Number(m[1]),unit:m[2]}:null;
}

/**
 * A copy of `doc` with `geometry.parameters[name].value` replaced.
 * A finite number stays a JSON number, except for a parameter written with its unit (format 0.3,
 * "0.5 um"): a bare number then keeps that unit. Any other text is kept as written (an
 * expression, or a quantity string), which the engine evaluates or refuses by name.
 */
export function setParameter(doc,name,value){
 const out=copyDocument(doc);const params=out.geometry?.parameters;
 if(!params||typeof params[name]!=='object'||params[name]===null)throw new Error('Unknown parameter '+name);
 const written=parseWritten(value),held=quantityOf(params[name].value);
 params[name].value=typeof written==='number'&&held?`${written} ${held.unit}`:written;
 return out;
}

/**
 * A field's text as the document should hold it: a number when it is one, else the trimmed
 * text (an expression). A number a double cannot hold (overflow, or a non-zero value that
 * underflows to zero) is refused rather than written as null or 0.
 */
export function parseWritten(value){
 if(typeof value==='number'){if(!Number.isFinite(value))throw new Error('A parameter value must be finite');return value;}
 const text=String(value).trim();
 if(text==='')throw new Error('A parameter value cannot be empty');
 if(!/^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$/.test(text))return text;
 const number=Number(text);
 if(!Number.isFinite(number))throw new Error(`${text} is too large for a number`);
 if(number===0&&/[1-9]/.test(text.replace(/[eE].*$/,'')))throw new Error(`${text} is too small for a number`);
 return number;
}

/**
 * A slider is offered for a parameter written as a plain number with a numeric [lo, hi] range.
 * Its step is a power of ten (at least 200 steps over the range), so slider values stay short
 * decimals in the saved document; `sliderValue` rounds a slider position to that step.
 */
export function sliderOf(parameter){
 const r=parameter.range;
 if(!Array.isArray(r)||r.length!==2)return null;
 // format 0.3: the value and both bounds written with one unit ("0.5 um", ["0.3 um", "0.9 um"])
 const q=quantityOf(parameter.written),bounds=r.map(quantityOf),unit=q?.unit;
 if(q&&bounds.every(b=>b&&b.unit===unit)){const s=sliderOf({written:q.number,range:bounds.map(b=>b.number)});return s&&{...s,unit};}
 if(typeof parameter.written!=='number')return null;
 const [lo,hi]=r;
 if(typeof lo!=='number'||typeof hi!=='number'||!Number.isFinite(lo)||!Number.isFinite(hi)||!(hi>lo))return null;
 const exponent=Math.floor(Math.log10((hi-lo)/200));
 return {min:lo,max:hi,step:10**exponent,decimals:Math.max(0,-exponent)};
}
export function sliderValue(slider,position){
 const v=Number(Number(position).toFixed(Math.min(slider.decimals,20)));
 return Math.min(slider.max,Math.max(slider.min,v));
}

/** The document as saved: two-space JSON with a final newline. */
export function serializeDocument(doc){return JSON.stringify(doc,null,2)+'\n';}

/** A file name for saving: the document name, made safe, with .json. */
export function saveName(doc){
 const base=String(doc?.name||'geometry').replace(/[^A-Za-z0-9._-]+/g,'_').replace(/^_+|_+$/g,'')||'geometry';
 return base.endsWith('.json')?base:base+'.json';
}

/**
 * Maps document coordinates to SVG pixels: the domain fills the box with `pad` pixels
 * around it, one scale for both axes, y pointing up.
 */
export function viewTransform(domain,width,height,pad=16){
 const w=domain.xmax-domain.xmin,h=domain.ymax-domain.ymin;
 const s=Math.min((width-2*pad)/w,(height-2*pad)/h);
 const ox=(width-s*w)/2,oy=(height-s*h)/2;
 return {scale:s,x:x=>ox+(x-domain.xmin)*s,y:y=>height-oy-(y-domain.ymin)*s};
}

const fmt=v=>Number(v.toFixed(3)).toString();

/** SVG path data of one curve's points. */
export function curvePath(points,view){
 return points.map(([x,y],i)=>(i?'L':'M')+fmt(view.x(x))+' '+fmt(view.y(y))).join(' ');
}

/** SVG path data of a cell: every loop closed; draw with fill-rule evenodd so holes stay empty. */
export function cellPath(cell,curves,view){
 return cell.loops.map(loop=>{
  const pts=[];
  for(const [index,forward] of loop){
   const p=curves[index].points,run=forward?p:[...p].reverse();
   pts.push(...(pts.length?run.slice(1):run));
  }
  return curvePath(pts,view)+' Z';
 }).join(' ');
}

/**
 * What a highlighted list row lights up in the current answer, looked up by its key
 * (`region:<name>`, `selection:<name>` or `tag:<tag>`) so that indices are never carried
 * from one evaluation to the next: cell indices for regions, curve indices for boundaries.
 */
export function highlightOf(view,key){
 const none={cells:new Set(),curves:new Set()};
 if(!key||!view)return none;
 const at=key.indexOf(':'),kind=key.slice(0,at),name=key.slice(at+1);
 if(kind==='region')return {cells:new Set(view.regions.find(r=>r.name===name)?.cells||[]),curves:new Set()};
 if(kind==='selection'){
  const s=view.selections.find(x=>x.name===name);if(!s)return none;
  return s.kind==='region'?{cells:new Set(s.entries),curves:new Set()}:{cells:new Set(),curves:new Set(s.entries)};
 }
 if(kind==='tag')return {cells:new Set(),curves:new Set(view.tags.find(t=>t.tag===name)?.curves||[])};
 return none;
}

/** The text shown for a refusal: the engine's own message, nothing added or removed. */
export function refusalText(status,body){
 if(body&&typeof body.refused==='string')return body.refused;
 if(body&&typeof body.detail==='string')return body.detail;
 if(body&&Array.isArray(body.detail))return body.detail.map(d=>d.msg||JSON.stringify(d)).join('; ');
 return 'The server answered '+status+' without a refusal message.';
}

/** A fixed palette by region order; void regions are drawn unfilled. */
const PALETTE=['#4e79a7','#f28e2b','#59a14f','#e15759','#76b7b2','#edc948','#b07aa1','#ff9da7','#9c755f','#bab0ac'];
export function regionColor(view,name){
 const regions=view.regions.filter(r=>r.name!=='background');
 if(name==='background')return '#d9dde3';
 const i=regions.findIndex(r=>r.name===name);
 return PALETTE[(i<0?0:i)%PALETTE.length];
}

/** A short area label in the document unit. */
export function areaLabel(area,unit){return Number(area.toPrecision(6)).toString()+' '+unit+'²';}

/** An empty version 1 document to start from (format 0.3): one rect in a 2D domain in micrometres,
 * its length parameter written with its unit. */
export function newDocument(){
 return {openphysics:'0.3',name:'New geometry',geometry:{version:1,
  parameters:{w:{value:'1 um',range:['0.2 um','2 um']}},
  components:{xs:{dimension:'2d',length_unit:'um',depth:null,domain:{xmin:-2,xmax:2,ymin:-1,ymax:1},background:{material:'physmat:SiO2'},
   features:[{name:'core',type:'rect',x:'-w/2',y:-0.25,w:'w',h:0.5,material:'physmat:Si'}],finalize:'later_wins',
   selections:{core_wall:{boundary:{between:['core','background']}}}}}}};
}
