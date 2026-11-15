// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

// An overview of the existing one-way setup. Ports inspect their interface;
// they do not expose arbitrary wiring or claim executable field transfers.
export function graphConnections(state){
 const edges=[];
 if(state.electric!==false&&state.heat)edges.push(['electric-out','heat-in','power','Joule heat → heat source']);
 if(state.heat&&state.optics)edges.push(['heat-out','optical-in','temperature','Temperature → optical material']);
 if(state.heat&&state.structure)edges.push(['heat-out','mechanical-in','temperature','Temperature → thermal strain']);
 if(state.heat&&state.structure&&state.optics)edges.push(['mechanical-out','optical-geometry','geometry','Displacement → geometry update']);
 return edges;
}
export function curvePath(from,to){
 if(Math.abs(to.x-from.x)<1)return `M ${from.x} ${from.y} C ${from.x+24} ${from.y}, ${to.x+24} ${to.y}, ${to.x} ${to.y}`;
 const reach=to.x<from.x?24:Math.max(36,(to.x-from.x)*.5);
 return `M ${from.x} ${from.y} C ${from.x+reach} ${from.y}, ${to.x-reach} ${to.y}, ${to.x} ${to.y}`;
}
export function renderConnectionGraph(state,selection,sequence,optionsOpen=false){
 const port=(id,name,label,quantity,color,side)=>`<button class="graph-port ${side} ${color}" data-port="${id}" data-select="${name}" aria-label="Inspect ${name}: ${label}, ${quantity}"><i class="port-dot" aria-hidden="true"></i><span>${label}<small>${quantity}</small></span></button>`;
 const node=(id,name,field,enabled,ports)=>`<article class="graph-node node-${id} ${enabled?'':'excluded'} ${selection===name?'selected':''}"><button class="graph-node-title" data-select="${name}" aria-pressed="${selection===name}">${name}<small>${field} · ${enabled?'Setup interface':'Not included'}</small></button><div class="graph-ports">${ports}</div></article>`;
 return `<div class="graph-heading"><h2>Physics connections</h2><span class="setup-badge">Setup only · no coupled calculation</span></div><p class="graph-intro">Select a node or port to inspect its properties. The tree and diagram share the same setup.</p>
 <div class="graph-scroll" tabindex="0" role="region" aria-label="Physics connection diagram; scroll horizontally on small screens">
 <div class="graph-stage" data-edges='${JSON.stringify(graphConnections(state))}'>
 <svg class="graph-wires" aria-hidden="true"></svg>
 ${node('electric','Electric currents','Electrical',state.electric!==false,port('electric-in','Electric currents','Applied voltage','V','voltage','input')+port('electric-out','Electric currents','Joule heat','W/m³','power','output'))}
 ${node('heat','Heat transfer','Thermal',state.heat,port('heat-in','Heat transfer','Heat source','W/m³','power','input')+port('heat-out','Heat transfer','Temperature T','K','temperature','output'))}
 ${node('optical','Optical modes','Electromagnetic',state.optics,port('optical-in','Optical modes','Temperature','K → n(T)','temperature','input')+port('optical-out','Optical modes','Effective index','n_eff · 1','optical','output')+port('optical-geometry','Optical modes','Geometry update','m','geometry','input right-port'))}
 ${node('mechanical','Solid mechanics','Mechanical',state.heat&&state.structure,port('mechanical-in','Solid mechanics','Thermal strain','from T · K','temperature','input')+port('mechanical-out','Solid mechanics','Displacement','m','geometry','output'))}
 <div class="graph-key"><span class="power">● Heat source</span><span class="temperature">● Temperature</span><span class="geometry">● Geometry</span></div>
 </div></div>
 <div class="graph-summary"><section><h3>Study · setup sequence</h3><ol>${sequence.map(n=>`<li>${n}</li>`).join('')}</ol></section><section><h3>Checks · before running</h3><p><span class="setup-badge">Not available</span> Coupled execution</p><p>Field mapping, deformed mesh and material laws are pending. Two-way feedback is not configured.</p></section></div>
 <details class="graph-options" ${optionsOpen?'open':''}><summary>Included interfaces</summary><div>
 <label><input data-toggle="heat" type="checkbox" ${state.heat?'checked':''}> Joule heating → Heat transfer</label>
 <label><input data-toggle="structure" type="checkbox" ${state.structure?'checked':''} ${!state.heat?'disabled':''}> Thermal expansion → Solid mechanics</label>
 <label><input data-toggle="optics" type="checkbox" ${state.optics?'checked':''}> Optical modes · material / geometry update</label>
 </div></details>`;
}
export function installConnectionGraph(host,onOptions=()=>{}){
 const stage=host.querySelector('.graph-stage');if(!stage)return ()=>{};
 const options=host.querySelector('.graph-options');
 const toggle=()=>onOptions(options.open);options.addEventListener('toggle',toggle);
 const svg=stage.querySelector('.graph-wires');
 const edges=JSON.parse(stage.dataset.edges);
 const draw=()=>{
  const bounds=stage.getBoundingClientRect();
  svg.setAttribute('viewBox',`0 0 ${bounds.width} ${bounds.height}`);
  const point=id=>{const r=stage.querySelector(`[data-port="${id}"] .port-dot`).getBoundingClientRect();return {x:r.x+r.width/2-bounds.x,y:r.y+r.height/2-bounds.y};};
  svg.replaceChildren(...edges.map(([from,to,color,label])=>{
   const path=document.createElementNS('http://www.w3.org/2000/svg','path');
   path.setAttribute('d',curvePath(point(from),point(to)));path.setAttribute('class',color);
   path.dataset.from=from;path.dataset.to=to;
   const title=document.createElementNS('http://www.w3.org/2000/svg','title');title.textContent=label;path.append(title);return path;
  }));
 };
 const observer=new ResizeObserver(draw);observer.observe(stage);
 stage.querySelectorAll('.graph-node').forEach(node=>observer.observe(node));
 draw();return ()=>{observer.disconnect();options.removeEventListener('toggle',toggle);};
}
