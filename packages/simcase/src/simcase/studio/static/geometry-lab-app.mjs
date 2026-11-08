// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// The experimental geometry lab page: holds one version 1 document, sends it whole to the
// exact engine on every edit, and draws what the engine answers.
import {areaLabel,cellPath,copyDocument,curvePath,highlightOf,isVersion1,newDocument,refusalText,
 regionColor,saveName,serializeDocument,setParameter,sliderOf,viewTransform} from './geometry-lab-model.mjs';
import {STARTERS} from './geometry-lab-starters.mjs';

const $=id=>document.getElementById(id);
const SVG='http://www.w3.org/2000/svg';
const state={doc:null,component:null,view:null,highlight:null,request:0};

function el(tag,attrs={},text){
 const e=tag.startsWith('svg:')?document.createElementNS(SVG,tag.slice(4)):document.createElement(tag);
 for(const [k,v] of Object.entries(attrs))e.setAttribute(k,v);
 if(text!==undefined)e.textContent=text;
 return e;
}
function status(text){$('status').textContent=text;}

async function evaluate(){
 const id=++state.request;
 status('Evaluating…');
 let response,body;
 try{
  response=await fetch('/api/geometry-lab/evaluate',{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({doc:state.doc,component:state.component})});
  body=await response.json().catch(()=>null);
 }catch(error){if(id===state.request)refuse('The Studio server could not be reached: '+error.message);return;}
 if(id!==state.request)return;            // a later edit is already on its way
 if(!response.ok||!body||body.ok!==true){refuse(refusalText(response.status,body));return;}
 state.view=body;state.component=body.component;
 $('refusal').hidden=true;$('view').classList.remove('stale');
 render();
 status(`Evaluated ${body.component}: ${body.regions.length} regions, ${body.cells.length} cells, ${body.curves.length} curves.`);
}

function refuse(text){
 $('refusal').textContent='Refused: '+text;$('refusal').hidden=false;
 $('view').classList.add('stale');
 status(state.view?'Not evaluated: the drawing shows the last accepted document.':'Not evaluated.');
}

function load(doc){
 if(!isVersion1(doc)){refuse('the document has no version 1 geometry block; this lab reads only version 1 documents.');return;}
 state.doc=copyDocument(doc);state.component=null;state.view=null;state.highlight=null;
 $('save-file').disabled=false;
 renderParameters();evaluate();
}

function renderParameters(){
 const rows=$('parameter-rows');rows.replaceChildren();
 const params=Object.entries(state.doc.geometry.parameters||{});
 $('no-parameters').hidden=params.length>0;
 for(const [name,entry] of params){
  const box=el('div',{class:'param'});
  const text=el('input',{type:'text',id:'param-'+name,'aria-label':name,spellcheck:'false'});
  text.value=String(entry.value);
  box.append(el('label',{for:'param-'+name},name),text);
  const slider=sliderOf({written:entry.value,range:entry.range});
  let range=null;
  if(slider){
   range=el('input',{type:'range',min:slider.min,max:slider.max,step:slider.step,'aria-label':name+' slider'});
   range.value=String(entry.value);
   range.addEventListener('input',()=>{text.value=range.value;edit(name,Number(range.value));});
   box.append(range,el('small',{},`range ${slider.min} … ${slider.max}`));
  }
  text.addEventListener('change',()=>{
   const ok=edit(name,text.value);
   if(ok&&range&&typeof state.doc.geometry.parameters[name].value==='number')range.value=text.value;
  });
  box.append(el('small',{class:'evaluated',id:'value-'+name}));
  rows.append(box);
 }
}

function edit(name,value){
 try{state.doc=setParameter(state.doc,name,value);}catch(error){refuse(error.message);return false;}
 evaluate();return true;
}

function render(){
 const v=state.view,svg=$('view');
 const view=viewTransform(v.domain,800,560);
 const lit=highlightOf(v,state.highlight);
 svg.replaceChildren();
 for(const cell of v.cells){
  const cls='cell'+(cell.void?' void':'')+(lit.cells.has(cell.index)?' lit':'');
  const p=el('svg:path',{class:cls,d:cellPath(cell,v.curves,view),'data-cell':cell.index});
  if(!cell.void)p.setAttribute('fill',regionColor(v,cell.region));
  p.append(el('svg:title',{},`${cell.region} (cell ${cell.index}, ${cell.material===null?'void':cell.material})`));
  svg.append(p);
 }
 for(const curve of v.curves){
  const p=el('svg:path',{class:'curve'+(lit.curves.has(curve.index)?' lit':''),d:curvePath(curve.points,view),'data-curve':curve.index});
  p.append(el('svg:title',{},`curve ${curve.index}: ${curve.provenance.join(' ')}${curve.tag?' · tag '+curve.tag:''}`));
  svg.append(p);
 }
 $('unit').textContent=`${v.component} (${v.dimension}) · lengths in ${v.unit}`;
 for(const p of v.parameters){const e=$('value-'+p.name);if(e)e.textContent=`= ${p.value} ${p.kind==='length'?v.unit:''}`;}
 const select=$('component');select.replaceChildren(...v.components.map(n=>{const o=el('option',{value:n},n);o.selected=n===v.component;return o;}));
 select.disabled=v.components.length<2;
 list('regions',v.regions.map(r=>({key:'region:'+r.name,item:{kind:'region-name',name:r.name},swatch:r.void?null:regionColor(v,r.name),
  label:r.name,detail:`${r.void?'void':r.material} · ${areaLabel(r.area,v.unit)}`})));
 list('selections',v.selections.map(s=>({key:'selection:'+s.name,item:s,label:s.name,detail:`${s.kind} · ${s.entries.length}`})),'No named selections.');
 list('tags',v.tags.map(t=>({key:'tag:'+t.tag,item:{kind:'boundary',curves:t.curves},label:t.tag,detail:`${t.curves.length} curves`})));
 $('summary').textContent=v.summary;
}

function list(id,rows,empty='None.'){
 const ul=$(id);ul.replaceChildren();
 if(!rows.length){ul.append(el('li',{class:'muted'},empty));return;}
 for(const row of rows){
  const li=el('li',{'data-key':row.key,tabindex:'0'});
  if(state.highlight?.key===row.key)li.classList.add('active');
  if(row.swatch!==undefined){const s=el('span',{class:'swatch'+(row.swatch?'':' void')});if(row.swatch)s.style.background=row.swatch;li.append(s);}
  li.append(el('code',{},row.label),el('small',{},row.detail));
  const pick=()=>{state.highlight=state.highlight?.key===row.key?null:{...row.item,key:row.key};render();};
  li.addEventListener('click',pick);
  li.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();pick();}});
  ul.append(li);
 }
}

$('starter').addEventListener('change',()=>{
 const key=$('starter').value;if(!key)return;
 load(key==='new'?newDocument():STARTERS[key]);
});
$('open-file').addEventListener('click',()=>$('file').click());
$('file').addEventListener('change',async()=>{
 const file=$('file').files[0];if(!file)return;
 try{load(JSON.parse(await file.text()));}catch(error){refuse(`${file.name} is not JSON: ${error.message}`);}
 $('file').value='';
});
$('component').addEventListener('change',()=>{state.component=$('component').value;state.highlight=null;evaluate();});
$('save-file').addEventListener('click',()=>{
 const blob=new Blob([serializeDocument(state.doc)],{type:'application/json'});
 const url=URL.createObjectURL(blob),a=el('a',{href:url,download:saveName(state.doc)});
 document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
 status('Saved '+saveName(state.doc)+' (the document as edited, version 1 geometry).');
});
