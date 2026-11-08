// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Pure helpers of the experimental geometry lab: no DOM, no network, so Node tests them.

/** A deep copy of a JSON document (the lab never edits the caller's object). */
export function copyDocument(doc){return JSON.parse(JSON.stringify(doc));}

/** Whether the document carries a version 1 geometry block (the lab reads nothing else). */
export function isVersion1(doc){
 return !!doc&&typeof doc==='object'&&!!doc.geometry&&typeof doc.geometry==='object'&&'version' in doc.geometry;
}

/**
 * A copy of `doc` with `geometry.parameters[name].value` replaced.
 * A finite number stays a JSON number; any other text is kept as an expression string,
 * which the engine evaluates or refuses by name.
 */
export function setParameter(doc,name,value){
 const out=copyDocument(doc);const params=out.geometry?.parameters;
 if(!params||typeof params[name]!=='object'||params[name]===null)throw new Error('Unknown parameter '+name);
 params[name].value=parseWritten(value);
 return out;
}

/** A field's text as the document should hold it: a number when it is one, else the trimmed text. */
export function parseWritten(value){
 if(typeof value==='number'){if(!Number.isFinite(value))throw new Error('A parameter value must be finite');return value;}
 const text=String(value).trim();
 if(text==='')throw new Error('A parameter value cannot be empty');
 return /^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$/.test(text)?Number(text):text;
}

/** A slider is offered for a parameter written as a plain number with a numeric [lo, hi] range. */
export function sliderOf(parameter){
 const r=parameter.range;
 if(typeof parameter.written!=='number'||!Array.isArray(r)||r.length!==2)return null;
 const [lo,hi]=r;
 if(typeof lo!=='number'||typeof hi!=='number'||!(hi>lo))return null;
 return {min:lo,max:hi,step:(hi-lo)/200};
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

/** What a selection or tag lights up: cell indices for regions, curve indices for boundaries. */
export function highlightOf(view,item){
 if(!item)return {cells:new Set(),curves:new Set()};
 if(item.kind==='region')return {cells:new Set(item.entries),curves:new Set()};
 if(item.kind==='region-name')return {cells:new Set(view.regions.find(r=>r.name===item.name)?.cells||[]),curves:new Set()};
 return {cells:new Set(),curves:new Set(item.entries||item.curves||[])};
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

/** An empty version 1 document to start from: one rect in a 2D domain, in micrometres. */
export function newDocument(){
 return {openphysics:'0.2',name:'New geometry',units:{length:'um'},geometry:{version:1,
  parameters:{w:{value:1,range:[0.2,2]}},
  components:{xs:{dimension:'2d',domain:{xmin:-2,xmax:2,ymin:-1,ymax:1},background:{material:'SiO2'},
   features:[{name:'core',type:'rect',x:'-w/2',y:-0.25,w:'w',h:0.5,material:'Si'}],finalize:'later_wins',
   selections:{core_wall:{boundary:{between:['core','background']}}}}}}};
}
