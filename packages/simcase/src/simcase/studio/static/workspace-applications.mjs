// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

// Workspace adapter availability, not a claim about the entire solver library.
export const APPLICATIONS=Object.freeze([
 Object.freeze({id:'optical',title:'Optical waveguide',status:'Live optical calculation',available:true,description:'Edit the core, calculate optical modes, compare fields and save results.',scope:'2D cross section in silica · rectangles, circles, polygons · wavelength and core mesh',physics:Object.freeze({electric:false,heat:false,structure:false,optics:true})}),
 Object.freeze({id:'heat',title:'Steady heat conduction',status:'Live heat calculation',available:true,description:'Edit a rectangular plate, its conductivity, heat source and side conditions, then compute temperature and heat flux.',scope:'2D rectangle · uniform k and source · fixed temperature, insulation, flux or convection per side',physics:Object.freeze({electric:false,heat:true,structure:false,optics:false})}),
 Object.freeze({id:'multi',title:'Heated optical waveguide',status:'Setup only · calculation unavailable',available:false,description:'Arrange electric, thermal, structural and optical interfaces in one model.',scope:'Conceptual regions and boundaries · coupled adapter pending',physics:Object.freeze({electric:true,heat:true,structure:true,optics:true})})
]);
export function templatePhysics(id){
 const application=APPLICATIONS.find(a=>a.id===id);
 if(!application)throw new Error('Unknown application template.');
 return {...application.physics};
}
// What the landing page offers to resume: the latest browser session and the
// earlier ones (C1), each as {runs, savedAt}. Empty when there is nothing.
export function resumeChoices(latest,earlier=[],when=t=>new Date(t).toLocaleString()){
 const line=(label,item)=>label+' · '+item.runs+(item.runs===1?' run':' runs')+' · saved '+when(item.savedAt);
 const choices=[];
 if(latest)choices.push({kind:'latest',label:line('Last session in this browser',latest)});
 // index: the record's place in storage, which recovery reads (given by the caller, else the position)
 earlier.forEach((item,position)=>choices.push({kind:'earlier',index:item.index??position,label:line('Earlier session',item)}));
 return choices;
}
// resume: optional {latest, earlier, onLatest(button), onEarlier(index, button),
// onOpenFile(), onStartNew()}; shown above the templates when there is something.
function resumeCard(resume){
 const choices=resumeChoices(resume.latest,resume.earlier);if(!choices.length)return null;
 const card=document.createElement('section');card.className='resume-card';card.setAttribute('aria-labelledby','resume-heading');
 const heading=document.createElement('h3');heading.id='resume-heading';heading.textContent='Continue where you left off';
 const note=document.createElement('p');note.textContent='Completed runs from this browser can be brought back without recomputing. Starting new keeps them as earlier sessions.';
 const actions=document.createElement('div');actions.className='resume-actions';
 for(const choice of choices){
  const button=document.createElement('button');button.type='button';button.textContent=(choice.kind==='latest'?'Recover: ':'Recover earlier: ')+choice.label;
  if(choice.kind==='latest'){button.className='primary';button.id='resume-latest';button.onclick=()=>resume.onLatest(button);}
  else{button.dataset.resumeEarlier=String(choice.index);button.onclick=()=>resume.onEarlier(choice.index,button);}
  actions.append(button);
 }
 const open=document.createElement('button');open.type='button';open.id='resume-open-file';open.textContent='Open session file…';open.onclick=()=>resume.onOpenFile();
 const fresh=document.createElement('button');fresh.type='button';fresh.id='resume-start-new';fresh.textContent='Start new';fresh.onclick=()=>resume.onStartNew();
 actions.append(open,fresh);card.append(heading,note,actions);return card;
}
export function renderApplications(host,resume=null){
 host.replaceChildren();
 const card=resume?resumeCard(resume):null;if(card)host.append(card);
 const heading=document.createElement('h2');heading.textContent='Choose a starting model';
 const intro=document.createElement('p');intro.textContent='One workspace for model setup, studies and results. Check what can run before you start.';
 const cards=document.createElement('div');cards.className='cards';
 for(const app of APPLICATIONS){
  const button=document.createElement('button');button.dataset.template=app.id;
  const title=document.createElement('strong');title.textContent=app.title;
  const status=document.createElement('span');status.className='application-status'+(app.available?' available':'');status.textContent=app.status;
  const description=document.createElement('p');description.textContent=app.description;
  const scope=document.createElement('span');scope.textContent=app.scope;
  button.append(title,status,description,scope);cards.append(button);
 }
 const contract=document.createElement('section');contract.className='application-contract';
 contract.innerHTML='<h3>What this workspace supports</h3><ul><li>Optical: up to 8 rectangles, circles or polygons of ten lossless materials (silicon, silicon nitride, silica, air, sapphire, lithium niobate, InP, GaAs, CaF2, MgF2) in a silica background; wavelength 1400–1700 nm, core mesh 20–60 nm, two candidates.</li><li>Steady heat: one homogeneous rectangle with constant conductivity and source; each side insulated, at fixed temperature, with inward heat flux or with convection. Results stay in the tab.</li><li>Multiphysics: edit the setup and connections. Electrical heating and mechanical deformation do not run here yet.</li><li>Existing thermal Studio views remain separate from this workspace.</li></ul><p>Choosing a template changes physics selections, retains dimensions and run history, and can be undone. Save session to keep inputs and completed results.</p>';
 host.append(heading,intro,cards,contract);
}
