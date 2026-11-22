// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
import {SIDES,ELECTRIC_TYPES,THERMAL_TYPES,MAX_JOULE_SHAPES,MAX_JOULE_MATERIALS,MAX_ITERATIONS,MAX_NEWTON_ITERATIONS,METHODS,TEMPERATURE,RESULT_FIELDS,validateJoule,jouleBlock,jouleDocument,jouleKind,
 usedMaterials,sigmaText,electricText,thermalText,jouleSummary,newJouleShape,newJouleMaterial,jouleViewModel,balanceRows,iterationRows,iterationMethod,iterationText,withMethod,iterationBlock,JouleRunner} from './workspace-joule.mjs';
import {shapeCorners} from './workspace-shapes.mjs';
import {requestFailedText} from './workspace-connection.mjs';
import {renderJouleGraph} from './workspace-graph.mjs';
import {runInputsLine} from './workspace-workflow.mjs';

export const JOULE_NODES=Object.freeze(['Geometry','Materials','Electric currents','Heat transfer','Mesh','Study']);
const FILLS=['#5b7f95','#b5784f','#7c9a5a','#9a6a9e','#c9a64a','#4f8f8a'];
const clone=x=>JSON.parse(JSON.stringify(x));
const fmt=v=>String(Number(Number(v).toPrecision(6)));

// The Joule heating application's views. ctx: {$, escapeHtml, pair, notice, ui, getJoule(),
// commit(next, message) -> bool (validates, records the edit and renders), render(), request}.
export function createJouleView(ctx){
 const {$,escapeHtml:esc,pair,notice,ui}=ctx;
 const drafts=new Map();let epoch=0,shapeIndex=0,field='temperature',arrows=true,probe=null,resize=null,result=null,error=null,cap=null,capError=null;
 const runner=new JouleRunner({request:ctx.request,onState:s=>{phase=s.message;refreshControls();}});let phase='';
 const j=()=>ctx.getJoule();
 const signature=()=>JSON.stringify(j());
 const fill=name=>FILLS[Math.max(0,j().materials.findIndex(m=>m.name===name))%FILLS.length];
 async function loadCapability(){try{cap=await runner.capability();capError=null;}catch(e){cap=null;capError=e.message;}refreshControls();}
 function block(){
  if(capError)return capError;if(!cap)return 'Checking whether this server runs Joule heating…';if(!cap.run_enabled)return 'This server does not enable Joule heating runs.';
  if(drafts.size)return 'Correct or restore the highlighted Joule inputs before running.';
  if(ctx.otherBusy?.())return 'A heat job holds the server job slot; wait for it to finish.';
  if(jouleKind(j())===TEMPERATURE){const b=iterationBlock(j().iteration,cap.limits);if(b)return b;}
  return jouleBlock(j(),cap.limits);
 }
 // A path into the inputs: "width", "materials.0.k", "sides.left.thermal.h", "shapes.1.points".
 const get=path=>path.split('.').reduce((o,k)=>o?.[k],j());
 function set(path,value,message){
  const next=clone(j()),keys=path.split('.');let target=next;for(const k of keys.slice(0,-1))target=target[k];target[keys.at(-1)]=value;
  try{validateJoule(next);}catch(e){drafts.set(path,{raw:typeof value==='number'&&Number.isNaN(value)?'':String(value),message:e.message});ctx.render();return false;}
  drafts.delete(path);return ctx.commit(next,message);
 }
 function input(path,label,attrs=''){
  const d=drafts.get(path);return `<label>${label}<input data-joule="${path}" type="number" step="any" ${attrs} value="${esc(d?d.raw:get(path))}" aria-invalid="${!!d}"></label>${d?`<p class="input-hint" role="alert">${esc(d.message)} Last valid value is retained.</p>`:''}`;
 }
 const select=(path,options,current,label)=>`<label>${label}<select data-joule-select="${path}">${Object.entries(options).map(([k,v])=>`<option value="${esc(k)}" ${k===current?'selected':''}>${esc(v)}</option>`).join('')}</select></label>`;
 const materialOptions=()=>Object.fromEntries(j().materials.map(m=>[m.name,m.name]));
 function geometryPanel(){
  const s=j(),n=s.shapes.length;shapeIndex=Math.min(shapeIndex,Math.max(0,n-1));
  let html=input('width','Domain width [mm]','min="0.001"')+input('height','Domain height [mm]','min="0.001"')+pair('Origin','Lower-left corner at (0, 0)')+select('background',materialOptions(),s.background,'Background material');
  html+=`<h3>Shapes (later shapes win where they overlap)</h3><div class="shape-list" role="group" aria-label="Joule shapes in draw order">${s.shapes.map((sh,i)=>`<button type="button" class="shape-item" data-joule-shape="${i}" aria-pressed="${i===shapeIndex}"><span class="swatch" style="background:${fill(sh.material)}"></span>${i+1}. ${esc(sh.name)} · ${sh.type} · ${esc(sh.material)}</button>`).join('')||'<p class="muted">No shapes: the background fills the domain.</p>'}</div>`;
  html+=`<div class="toolbar shape-actions">${['rect','circle','polygon'].map(t=>`<button type="button" data-joule-add="${t}" ${n>=MAX_JOULE_SHAPES?'disabled':''}>Add ${t==='rect'?'rectangle':t}</button>`).join('')}<button type="button" id="joule-delete-shape" ${n?'':'disabled'}>Delete shape</button></div>`;
  if(n){const sh=s.shapes[shapeIndex],base=`shapes.${shapeIndex}`;
   html+=`<h3>${esc(sh.name)}</h3><label>Name<input data-joule-text="${base}.name" type="text" maxlength="32" value="${esc(drafts.get(base+'.name')?.raw??sh.name)}" aria-invalid="${drafts.has(base+'.name')}"></label>${drafts.has(base+'.name')?`<p class="input-hint" role="alert">${esc(drafts.get(base+'.name').message)} Last valid value is retained.</p>`:''}`+select(`${base}.material`,materialOptions(),sh.material,'Material');
   if(sh.type==='rect')html+=input(`${base}.x`,'x [mm]')+input(`${base}.y`,'y [mm]')+input(`${base}.w`,'Width [mm]','min="0"')+input(`${base}.h`,'Height [mm]','min="0"');
   else if(sh.type==='circle')html+=input(`${base}.cx`,'Centre x [mm]')+input(`${base}.cy`,'Centre y [mm]')+input(`${base}.r`,'Radius [mm]','min="0"');
   else html+=`<label>Vertices [mm] · one "x, y" per line, 3–12 points<textarea id="joule-points" rows="${Math.min(12,sh.points.length+1)}" spellcheck="false">${sh.points.map(p=>p.join(', ')).join('\n')}</textarea></label><p class="input-hint" id="joule-points-hint">Applied when the field loses focus. Edges may not cross.</p>`;
  }
  return html+`<p>Up to ${MAX_JOULE_SHAPES} shapes inside the domain. Each shape is a named region; the rest is the region "background".</p>`;
 }
 function materialsPanel(){
  const s=j(),used=new Set(usedMaterials(s).map(m=>m.name));
  let html=s.materials.map((m,i)=>{const b=`materials.${i}`,lin=m.sigma.model==='linear_resistivity';
   return `<fieldset class="heat-side"><legend><span class="swatch" style="background:${fill(m.name)}"></span> ${esc(m.name)}${used.has(m.name)?'':' · unused'}</legend><label>Name<input data-joule-rename="${i}" type="text" maxlength="32" value="${esc(m.name)}"></label>`+input(`${b}.k`,'Thermal conductivity k [W/(m·K)]','min="0"')+
    select(`${b}.sigma.model`,{constant:'Constant electrical conductivity',linear_resistivity:'Linear resistivity model σ(T)'},m.sigma.model,'Electrical conductivity')+
    (lin?input(`${b}.sigma.reference_conductivity`,'Reference conductivity σ₀ [S/m]','min="0"')+input(`${b}.sigma.reference_temperature`,'Reference temperature T₀ [K]','min="0"')+input(`${b}.sigma.coefficient`,'Resistivity temperature coefficient α [1/K]')+input(`${b}.sigma.tmin`,'Valid from [K]','min="0"')+input(`${b}.sigma.tmax`,'Valid to [K]','min="0"')
     :input(`${b}.sigma.value`,'Electrical conductivity σ [S/m]','min="0"'))+
    `<button type="button" data-joule-delete-material="${i}" ${used.has(m.name)||s.materials.length<=1?'disabled':''}>Delete material</button></fieldset>`;}).join('');
  return html+`<button type="button" id="joule-add-material" ${s.materials.length>=MAX_JOULE_MATERIALS?'disabled':''}>Add material</button><p>σ(T) = σ₀ / (1 + α (T − T₀)) inside its valid range. When a used material has this model the study is joule.temperature2d (Picard or Newton iteration, chosen under Study); with constant materials it is joule.steady2d.</p>`;
 }
 function sidesPanel(kind){
  return SIDES.map(side=>{const c=j().sides[side][kind],b=`sides.${side}.${kind}`;let fields='';
   if(kind==='electric')fields=c.type==='potential'?input(`${b}.potential`,'Potential [V]'):c.type==='current'?input(`${b}.current`,'Inward current density [A/m²] (positive enters the body)'):'';
   else fields=c.type==='temperature'?input(`${b}.temperature`,'Temperature [K]','min="0"'):c.type==='flux'?input(`${b}.flux`,'Inward heat flux [W/m²] (positive enters the body)'):c.type==='convection'?input(`${b}.h`,'Heat transfer coefficient h [W/(m²·K)]','min="0"')+input(`${b}.ambient`,'Ambient temperature [K]','min="0"'):'';
   return `<fieldset class="heat-side" data-joule-side-box="${side}"><legend>${side[0].toUpperCase()+side.slice(1)} side</legend><label>Condition<select data-joule-type="${b}">${Object.entries(kind==='electric'?ELECTRIC_TYPES:THERMAL_TYPES).map(([k,v])=>`<option value="${k}" ${k===c.type?'selected':''}>${v}</option>`).join('')}</select></label>${fields}</fieldset>`;}).join('')+
   (kind==='electric'?'<p>At least one fixed potential sets the electric level. Other sides are electrically insulating.</p>':'<p>At least one fixed temperature or convection with h > 0 sets the temperature level. The only heat source is the Joule heating.</p>');
 }
 function inspector(){
  let html='<span class="muted">SELECTION</span><h2>'+ui.selection+'</h2>';const s=j();
  if(ui.selection==='Geometry')html+=geometryPanel();
  else if(ui.selection==='Materials')html+=materialsPanel();
  else if(ui.selection==='Electric currents')html+=sidesPanel('electric');
  else if(ui.selection==='Heat transfer')html+=sidesPanel('thermal');
  else if(ui.selection==='Mesh')html+=input('elementSize','Element size [mm]','min="0"')+'<p>Unstructured P1 triangles that follow the region boundaries. The node and triangle limits of this server apply when the job meshes; the actual mesh is shown with the result.</p>';
  else{const newton=s.iteration.method==='newton';html+=pair('Physics',jouleKind(s))+(jouleKind(s)===TEMPERATURE?select('iteration.method',METHODS,s.iteration.method,'Iteration method')+input('iteration.initial_temperature','Initial temperature [K]','min="0"')+(newton?'':input('iteration.relaxation_factor','Relaxation factor (0, 1]','min="0" max="1"'))+input('iteration.temperature_tolerance','Temperature tolerance [K]','min="0"')+input('iteration.relative_tolerance','Relative tolerance','min="0" max="1"')+input('iteration.iteration_limit',newton?`Newton step limit (at most ${MAX_NEWTON_ITERATIONS})`:`Iteration limit (at most ${MAX_ITERATIONS})`,'min="1" step="1"')+
   (newton?`<p>Newton steps of the potential and temperature together, each halved until it reduces the temperature defect; the same convergence tests as Picard, and no relaxation. Studio allows ${MAX_NEWTON_ITERATIONS} steps (each evaluates up to 31 candidates). Use it when Picard is slow or stops at its limit.</p>`:'<p>Picard iteration; the defaults are the documented ones (relaxation 0.5, relative tolerance 1e-10, 100 iterations).</p>'):'<p>All used materials have constant conductivity: one coupled solve, no iteration.</p>');}
  if(drafts.size)html+='<button id="joule-discard-drafts">Restore last valid values</button>';
  return html;
 }
 function bindInspector(){
  document.querySelectorAll('[data-joule]').forEach(el=>el.onchange=()=>{const raw=el.value.trim();set(el.dataset.joule,raw===''?NaN:Number(raw),'Joule input updated.');});
  document.querySelectorAll('[data-joule-text]').forEach(el=>el.onchange=()=>set(el.dataset.jouleText,el.value.trim(),'Shape renamed.'));
  document.querySelectorAll('[data-joule-select]').forEach(el=>el.onchange=()=>{const path=el.dataset.jouleSelect;
   if(path.endsWith('.sigma.model')){for(const key of [...drafts.keys()])if(key.startsWith(path.slice(0,-6)+'.'))drafts.delete(key);const next=el.value==='constant'?{model:'constant',value:1000}:{model:'linear_resistivity',reference_conductivity:1000,reference_temperature:300,coefficient:0.004,tmin:250,tmax:600};set(path.slice(0,-6),next,'Conductivity model changed.');}
   else if(path==='iteration.method'){
    const it=withMethod(j().iteration,el.value);
    drafts.delete('iteration.iteration_limit');drafts.delete('iteration.relaxation_factor');set('iteration',it,`Iteration method: ${METHODS[el.value]}, limit ${it.iteration_limit}.`);}
   else set(path,el.value,'Material assignment updated.');});
  document.querySelectorAll('[data-joule-type]').forEach(el=>el.onchange=()=>{const path=el.dataset.jouleType,type=el.value,defaults={insulating:{type},potential:{type,potential:0},current:{type,current:0},insulated:{type},temperature:{type,temperature:300},flux:{type,flux:0},convection:{type,h:10,ambient:300}};
   for(const key of [...drafts.keys()])if(key.startsWith(path+'.'))drafts.delete(key);set(path,defaults[type],`${path.split('.')[1]} side: ${type}.`);});
  document.querySelectorAll('[data-joule-rename]').forEach(el=>el.onchange=()=>{const i=+el.dataset.jouleRename,next=clone(j()),old=next.materials[i].name,name=el.value.trim();next.materials[i].name=name;
   if(next.background===old)next.background=name;for(const sh of next.shapes)if(sh.material===old)sh.material=name;if(!ctx.commit(next,`Material ${old} renamed ${name}.`))el.value=old;});
  document.querySelectorAll('[data-joule-shape]').forEach(el=>el.onclick=()=>{shapeIndex=+el.dataset.jouleShape;ctx.render();});
  document.querySelectorAll('[data-joule-add]').forEach(el=>el.onclick=()=>{const next=clone(j()),shape=newJouleShape(el.dataset.jouleAdd,next);next.shapes.push(shape);if(ctx.commit(next,shape.name+' added on top.'))shapeIndex=next.shapes.length-1;ctx.render();});
  const del=$('joule-delete-shape');if(del)del.onclick=()=>{const next=clone(j()),[gone]=next.shapes.splice(shapeIndex,1);for(const key of [...drafts.keys()])if(key.startsWith('shapes.'))drafts.delete(key);shapeIndex=Math.max(0,shapeIndex-1);ctx.commit(next,gone.name+' deleted; Undo restores it.');};
  const add=$('joule-add-material');if(add)add.onclick=()=>{const next=clone(j()),m=newJouleMaterial(next);next.materials.push(m);ctx.commit(next,'Material '+m.name+' added.');};
  document.querySelectorAll('[data-joule-delete-material]').forEach(el=>el.onclick=()=>{const next=clone(j()),[gone]=next.materials.splice(+el.dataset.jouleDeleteMaterial,1);for(const key of [...drafts.keys()])if(key.startsWith('materials.'))drafts.delete(key);ctx.commit(next,'Material '+gone.name+' deleted.');});
  const points=$('joule-points');if(points)points.onchange=()=>{try{
   const parsed=points.value.trim().split(/\n+/).map((line,i)=>{const parts=line.split(/[\s,;]+/).filter(Boolean);if(parts.length!==2)throw new Error(`Vertex line ${i+1} needs x and y.`);return parts.map(v=>{const n=Number(v);if(!Number.isFinite(n))throw new Error(`Vertex line ${i+1} must contain numbers.`);return n;});});
   const next=clone(j());next.shapes[shapeIndex].points=parsed;validateJoule(next);ctx.commit(next,'Vertices updated.');
  }catch(e){$('joule-points-hint').textContent=e.message+' Vertices unchanged.';points.setAttribute('aria-invalid','true');notice(e.message+' Vertices unchanged.');}};
  const discard=$('joule-discard-drafts');if(discard)discard.onclick=()=>{drafts.clear();ctx.render();notice('Invalid Joule drafts discarded. Last valid inputs retained.');};
 }
 function svg(){
  const s=j(),scale=Math.min(440/s.width,230/s.height),w=s.width*scale,h=s.height*scale,x0=300-w/2,y0=175-h/2,X=x=>x0+x*scale,Y=y=>y0+h-y*scale;
  const shapes=s.shapes.map((sh,i)=>{const attrs=`fill="${fill(sh.material)}" stroke="${ui.selection==='Geometry'&&i===shapeIndex?'#2860bd':'#ffffff'}" stroke-width="${i===shapeIndex?2:1}" data-joule-pick="${i}" role="button" tabindex="0" aria-label="Select shape ${esc(sh.name)}"`;
   if(sh.type==='circle')return `<circle cx="${X(sh.cx)}" cy="${Y(sh.cy)}" r="${sh.r*scale}" ${attrs}/>`;
   return `<polygon points="${shapeCorners(sh).map(([x,y])=>X(x)+','+Y(y)).join(' ')}" ${attrs}/>`;}).join('');
  const edges={left:[x0,y0,x0,y0+h],right:[x0+w,y0,x0+w,y0+h],bottom:[x0,y0+h,x0+w,y0+h],top:[x0,y0,x0+w,y0]};
  const labels={left:[x0-8,y0+h/2,'end'],right:[x0+w+8,y0+h/2,'start'],bottom:[300,y0+h+18,'middle'],top:[300,y0-10,'middle']};
  const sides=SIDES.map(side=>{const [a,b,c,d]=edges[side],[lx,ly,anchor]=labels[side],e=s.sides[side].electric,t=s.sides[side].thermal,text=`${electricText(e)} · ${thermalText(t)}`;
   return `<g data-joule-side="${side}" role="button" tabindex="0" aria-label="Select ${side} side: ${esc(text)}"><path d="M${a} ${b} L${c} ${d}" stroke="transparent" stroke-width="14"/><path d="M${a} ${b} L${c} ${d}" stroke="${e.type==='potential'?'#b9772c':'#7a939f'}" stroke-width="2.5" pointer-events="none"/><text x="${lx}" y="${ly}" text-anchor="${anchor}" fill="#34445b" font-size="9" pointer-events="none">${esc(text)}</text></g>`;}).join('');
  return `<svg data-geometry-view="joule" viewBox="0 0 600 350" role="group" aria-label="Joule heating regions, ${esc(jouleSummary(s))}"><rect x="${x0}" y="${y0}" width="${w}" height="${h}" fill="${fill(s.background)}" stroke="none"/>${shapes}${sides}<text x="300" y="22" text-anchor="middle" fill="#34445b" font-size="11">${esc(jouleSummary(s))} · element ${fmt(s.elementSize)} mm</text><text x="${x0}" y="${y0+h+32}" fill="#5b6d82" font-size="10">(0, 0)</text><text x="${x0+w}" y="${y0-22}" text-anchor="end" fill="#5b6d82" font-size="10">(${fmt(s.width)}, ${fmt(s.height)}) mm</text></svg>`;
 }
 function bindSvg(){
  const bind=(el,fn)=>{el.onclick=fn;el.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();fn();}};};
  document.querySelectorAll('[data-joule-side]').forEach(el=>bind(el,()=>{ui.selection=ui.selection==='Heat transfer'?'Heat transfer':'Electric currents';ctx.render();document.querySelector(`[data-joule-side-box="${el.dataset.jouleSide}"] select`)?.focus();}));
  document.querySelectorAll('[data-joule-pick]').forEach(el=>bind(el,()=>{shapeIndex=+el.dataset.joulePick;ui.selection='Geometry';ctx.render();}));
 }
 function study(){
  const s=j(),host=$('canvas'),b=block();
  host.innerHTML='<h2>Joule heating study</h2><p>Review the regions and conditions, then run. Run validates the current inputs through the Studio Joule routes and then solves them.</p>'+pair('Model',esc(jouleSummary(s)))+
   usedMaterials(s).map(m=>pair(esc(m.name),esc(`${sigmaText(m.sigma)} · k ${fmt(m.k)} W/(m·K)`))).join('')+SIDES.map(side=>pair(side[0].toUpperCase()+side.slice(1),esc(electricText(s.sides[side].electric)+' · '+thermalText(s.sides[side].thermal)))).join('')+pair('Mesh',`element size ${fmt(s.elementSize)} mm`);
  if(b)host.insertAdjacentHTML('beforeend',`<p class="validation-warning">${esc(b)}</p>`);
  host.insertAdjacentHTML('beforeend','<p id="joule-message" role="status"></p>');
  const details=document.createElement('details');details.className='solver-document';const title=document.createElement('summary');title.textContent='Solver document · lengths in mm, other values in SI with their units';const body=document.createElement('pre');
  try{body.textContent=JSON.stringify(jouleDocument(s),null,2);}catch(e){body.textContent=e.message;}details.append(title,body);host.append(details);
 }
 function results(){
  const host=$('canvas');resize?.disconnect();
  if(!result){host.innerHTML='<h2>No Joule heating result in this tab</h2><p>Edit the model and run the study. Joule heating results are kept in this tab only; saved projects and sessions keep the inputs.</p>';$('inspector').innerHTML='<h2>Joule heating results</h2><p>No completed run.</p>';return;}
  const run=result,p=run.payload,summary=p.summary,same=run.signature===signature();
  host.innerHTML='<h2>Joule heating result</h2>';
  const desc=document.createElement('p');desc.textContent=`${runInputsLine([jouleSummary(run.input)],[jouleSummary(j())])} · ${p.result_format}`;host.append(desc);
  const bar=document.createElement('div');bar.className='toolbar';bar.innerHTML=`<label>Field <select id="joule-field">${Object.entries(RESULT_FIELDS).map(([k,[l,u]])=>`<option value="${k}" ${k===field?'selected':''}>${l} [${u}]</option>`).join('')}</select></label><label><input id="joule-arrows" type="checkbox" ${arrows?'checked':''}> Arrows on cell fields</label>`;host.append(bar);
  const card=document.createElement('div');card.className='heat-plot';const canvas=document.createElement('canvas');canvas.id='joule-field-canvas';canvas.style.cssText='display:block;width:100%;height:var(--plot-height,360px);cursor:crosshair';canvas.setAttribute('role','img');card.append(canvas);host.append(card);
  const out=document.createElement('p');out.id='joule-probe';out.setAttribute('role','status');host.append(out);
  const note=document.createElement('p');note.textContent='Temperature and potential are interpolated linearly inside each triangle (P1); |J|, Joule power density and |q| are constant per triangle, and arrows show current density (or heat flux for |q|). Lines mark region boundaries. Colours span this result\'s own range.';host.append(note);
  const T=globalThis.ThermalStudio;
  const draw=()=>{if(!canvas.isConnected||!T)return;try{const model=jouleViewModel(p,field);T.draw(canvas,model,{arrows});canvas.setAttribute('aria-label',`${model.field} ${model.min} to ${model.max} ${model.unit}`);
   if(probe){const v=T.sample(model,probe);out.textContent=v===null?'No triangle contains this point.':`At (${probe[0].toFixed(4)}, ${probe[1].toFixed(4)}) ${model.lengthLabel}: ${model.field} = ${v.toPrecision(6)} ${model.unit}${model.nodal?' (P1 interpolation)':' (triangle value)'}`;}else out.textContent='No point selected.';
   canvas.onclick=event=>{const r=canvas.getBoundingClientRect(),tr=T.transform(model,Math.round(r.width),Math.round(r.height));probe=tr.inverse(event.clientX-r.left,event.clientY-r.top);draw();};
  }catch(e){out.textContent='Plot unavailable: '+e.message;}};
  $('joule-field').onchange=()=>{field=$('joule-field').value;draw();};$('joule-arrows').onchange=()=>{arrows=$('joule-arrows').checked;draw();};
  resize=new ResizeObserver(draw);resize.observe(canvas);draw();
  const rows=balanceRows(summary),history=iterationRows(summary),num=v=>Number.isFinite(v)?esc(String(Number(v.toPrecision(4)))):'—';
  $('inspector').innerHTML='<h2>Joule heating result</h2>'+pair('Inputs',same?'Same as the current inputs':'Current inputs differ from this run')+pair('Physics',esc(summary.physics_type))+pair('Nodes',p.arrays.node_coordinates.length)+pair('Triangles',p.arrays.triangles.length)+
   '<h3>Balances per metre of depth</h3>'+rows.map(([l,v])=>pair(esc(l),esc(v))).join('')+
   '<h3>Solution</h3>'+(history.length?pair(iterationMethod(summary)==='newton'?'Newton steps':'Picard iterations',history.length)+'<p>The iteration history is in the Solver log of the study dock.</p>':'<p>One coupled solve (constant conductivities).</p>')+
   pair('Completed',new Date(run.completedAt).toLocaleTimeString());
  const restore=document.createElement('button');restore.textContent='Restore run inputs';restore.disabled=same;restore.onclick=()=>ctx.commit(clone(run.input),'Joule inputs restored from the run.');$('inspector').append(restore);
 }
 // The study dock's solver log: the Picard or Newton history and the power balance of the shown result.
 function solverLog(){
  const log=$('solver-log');if(!log)return;const show=ui.page==='Results'&&!!result;log.hidden=!show;if(!show)return;
  const summary=result.payload.summary,rows=balanceRows(summary).slice(0,3),history=iterationRows(summary),num=v=>Number.isFinite(v)?esc(String(Number(v.toPrecision(4)))):'—',last=history.at(-1);
  log.querySelector('summary').innerHTML='<b>Solver log</b>'+(history.length?`${esc(iterationText(summary))} · last |ΔT| ${num(last[1])} K · Δσ/σ ${num(last[2])}`:'One coupled solve · constant conductivities')+' · '+rows.map(([l,v])=>esc(l)+' '+esc(v)).join(' · ');
  log.querySelector('.dock-log-body').innerHTML=history.length?`<table aria-label="${iterationMethod(summary)==='newton'?'Newton steps':'Picard iterations'}"><thead><tr><th scope="col">#</th><th scope="col">|ΔT| [K]</th><th scope="col">Δσ/σ</th><th scope="col">T max [K]</th></tr></thead><tbody>${history.map(r=>`<tr><td>${r[0]}</td><td>${num(r[1])}</td><td>${num(r[2])}</td><td>${num(r[3])}</td></tr>`).join('')}</tbody></table>`:'<p>The conductivities are constant, so the electric and heat problems were solved once without iteration.</p>';
 }
 function refreshControls(){
  const button=$('run-joule');if(!button)return;const on=ctx.active();button.hidden=!on;if(!on)return;$('run-optical').hidden=true;$('run-heat').hidden=true;
  const b=block();button.disabled=!!b||runner.busy;button.textContent=runner.busy?'Computing…':'Run Joule heating study';
  $('status').textContent=drafts.size?'Input errors · correct or restore the last valid values':runner.busy?'Joule heating calculation running':b?'Joule input not ready · '+b:'Joule heating solver ready · explicit Run required';
  const message=$('joule-message');if(message)message.textContent=error?requestFailedText('Joule',error):runner.busy?phase:'';
 }
 async function run(){
  if(runner.busy||block())return;
  const input=clone(j()),doc=jouleDocument(input),started=epoch;error=null;ctx.beforeRun?.();refreshControls();
  try{const payload=await runner.calculate(doc);if(!payload)return;
   // a file opened meanwhile replaced the design: its run is not this design's result
   if(started!==epoch){notice('A Joule heating run of the inputs before the file was opened finished; its result was discarded.');return;}
   result={input,signature:JSON.stringify(input),payload,completedAt:new Date().toISOString()};probe=null;
   if(ctx.active()){ui.page='Results';ctx.render();(ctx.announceResult||notice)('Joule heating calculation complete. The result keeps the inputs it was run with; it is kept in this tab only.');}
   else notice('A Joule heating result is ready; choose Models → Joule heating to see it.');
  }catch(e){if(started!==epoch)return;error=e.message;notice('Joule heating run failed: '+e.message+(/[.!?]$/.test(e.message)?'':'.')+' Inputs unchanged.');}
  finally{refreshControls();ctx.onIdle?.();}
 }
 function page(){
  document.querySelector('main').classList.remove('comparing');document.querySelector('main').classList.toggle('choosing',ui.page==='Applications');
  $('sequence').innerHTML=`<span>Joule heating · ${jouleKind(j())}</span><span>Run validates the current inputs, then solves</span><span>Mesh convergence not certified</span>`;
  document.querySelector('.workspace > .toolbar').style.display=ui.page==='Model'?'flex':'none';
  document.querySelector('.workspace > .note').textContent=ui.page==='Results'?'Joule heating results belong to the inputs captured at Run.':ui.page==='Connections'?'One Joule heating study solves both interfaces; the wires show the quantities it passes between them.':'Lengths in mm, temperatures in K, other quantities in SI. Select a side or a shape in the drawing.';
  if(ui.page==='Model'&&ui.selection==='Study')study();
  if(ui.page==='Results')results();
  if(ui.page==='Compare')$('canvas').innerHTML='<h2>Compare</h2><p>Comparison is available for optical runs. Joule heating results are shown one at a time in Results.</p>';
  if(ui.page==='Connections'){const kind=jouleKind(j());$('canvas').innerHTML=renderJouleGraph(ui.selection,kind===TEMPERATURE,kind);
   document.querySelectorAll('[data-joule-node]').forEach(b=>b.onclick=()=>{ui.selection=b.dataset.jouleNode;ctx.render();});}
  bindSvg();solverLog();refreshControls();
 }
 return {svg,inspector,bindInspector,page,run,refreshControls,loadCapability,// undo/redo: drafts go, the run and its result stay (labelled an earlier snapshot)
  clearDrafts:()=>{drafts.clear();error=null;refreshControls();},
  // a file or recovery replaces the design: drafts, result and error go; a running job is still
  // followed to its end (it holds the server's job slot) and its result discarded
  reset:()=>{drafts.clear();result=null;error=null;epoch++;refreshControls();},busy:()=>runner.busy,hasDrafts:()=>drafts.size>0,hasResult:()=>result!==null,disconnect:()=>resize?.disconnect()};
}
