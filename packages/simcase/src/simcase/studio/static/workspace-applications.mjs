// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

// Workspace adapter availability, not a claim about the entire solver library.
export const APPLICATIONS=Object.freeze([
 Object.freeze({id:'optical',title:'Optical waveguide',status:'Live optical calculation',available:true,description:'Edit the core, calculate optical modes, compare fields and save results.',scope:'2D cross section in silica · rectangles, circles, polygons · wavelength and core mesh',physics:Object.freeze({electric:false,heat:false,structure:false,optics:true})}),
 Object.freeze({id:'heat',title:'Steady heat conduction',status:'Live heat calculation',available:true,description:'Edit a rectangular plate, its conductivity, heat source and side conditions, then compute temperature and heat flux.',scope:'2D rectangle · uniform k and source · fixed temperature, insulation, flux or convection per side',physics:Object.freeze({electric:false,heat:true,structure:false,optics:false})}),
 Object.freeze({id:'joule',title:'Joule heating',status:'Live Joule heating calculation',available:true,description:'Place conductors of named materials in a rectangle, give each its electrical and thermal conductivity (constant or temperature-dependent), set side potentials and thermal conditions, then compute temperature, potential, current and Joule power.',scope:'2D named material regions in mm · constant or linear-resistivity σ(T) · potential or current and temperature, flux or convection per side',physics:Object.freeze({electric:true,heat:true,structure:false,optics:false})}),
]);
// Coupled models (contract D2): the card opens a multiphysics document; one Run solves every
// physics in the order its couplings give.
export const COUPLED_TEMPLATES=Object.freeze([
 Object.freeze({id:'heated-waveguide',title:'Heated silicon waveguide',status:'Heat → optical modes · coupled',available:true,description:'A silicon core under a heater: steady heat gives the temperature, and the optical modes take n(T) from it on one shared mesh.',scope:'500 × 220 nm core on oxide · 2 µm heater 1.1 µm above · bottom at 300 K · λ 1550 nm'})
]);
export function templatePhysics(id){
 const application=APPLICATIONS.find(a=>a.id===id);
 if(!application)throw new Error('Unknown model template.');
 return {...application.physics};
}
// The runs of a stored session by name, oldest first: a run's name, else "Run <number>" (an
// optical run is numbered by its place in the list, a multiphysics run by its own number).
export function sessionRunNames(session){
 return (session?.runs||[]).map((run,i)=>run.label||`Run ${Number.isInteger(run.number)?run.number:i+1}`);
}
// One stored session as a recovery list names it: the model, the run count and the run names
// ("Optical waveguide · 2 runs · design A, Run 2"), so two entries never read alike.
export function sessionLine(item){
 return (item.model?item.model+' · ':'')+item.runs+(item.runs===1?' run':' runs')+(item.names?.length?' · '+item.names.join(', '):'');
}
// What the landing page offers to resume: the latest browser session and the
// earlier ones (C1), each as {runs, savedAt, model, names}: model names the session's model and
// names its runs (sessionLine). Empty when there is nothing.
export function resumeChoices(latest,earlier=[],when=t=>new Date(t).toLocaleString()){
 const line=(label,item)=>label+' · '+sessionLine(item)+' · saved '+when(item.savedAt);
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
 const portable=document.createElement('p');portable.className='resume-portable';portable.textContent='A session file is the copy that moves between computers; browser recovery stays in this browser.';
 const actions=document.createElement('div');actions.className='resume-actions';
 for(const choice of choices){
  const button=document.createElement('button');button.type='button';button.textContent=(choice.kind==='latest'?'Recover (this browser only): ':'Recover earlier (this browser only): ')+choice.label;
  if(choice.kind==='latest'){button.className='primary';button.id='resume-latest';button.onclick=()=>resume.onLatest(button);}
  else{button.dataset.resumeEarlier=String(choice.index);button.onclick=()=>resume.onEarlier(choice.index,button);}
  actions.append(button);
 }
 const open=document.createElement('button');open.type='button';open.id='resume-open-file';open.textContent='Open session file (portable)…';open.onclick=()=>resume.onOpenFile();
 const fresh=document.createElement('button');fresh.type='button';fresh.id='resume-start-new';fresh.textContent='Start new';fresh.onclick=()=>resume.onStartNew();
 actions.append(open,fresh);card.append(heading,note,actions,portable);return card;
}
// The Models page notes: what each model supports and what Save session keeps of it. A session
// file holds the inputs of every single-physics model and the optical runs, or a multiphysics
// model with its runs; heat and Joule heating results are not written to it.
export const CHOOSER_NOTES=Object.freeze([
 'Optical: up to 8 rectangles, circles or polygons of ten lossless materials (silicon, silicon nitride, silica, air, sapphire, lithium niobate, InP, GaAs, CaF2, MgF2) in a silica background; wavelength 1400–1700 nm, core mesh 20–60 nm, two modes. Save session keeps the inputs, the runs and the comparison.',
 'Steady heat: one homogeneous rectangle with constant conductivity and source; each side insulated, at fixed temperature, with inward heat flux or with convection. Save session keeps the plate inputs; heat results stay in this tab.',
 'Joule heating: a rectangle in mm with up to 8 rectangles, circles or polygons over a background material, up to 6 materials with thermal conductivity and a constant or linear-resistivity electrical conductivity; each side insulating, at fixed potential or with inward current, and insulated, at fixed temperature, with inward heat flux or with convection. Temperature-dependent materials iterate (Picard, or Newton chosen under Study). Save session keeps the inputs; Joule heating results stay in this tab.',
 'Heated silicon waveguide: a multiphysics model of steady heat and optical modes on one mesh. Add or remove physics and couplings, check them before running, and run every physics in solve order. Save session keeps the model with its runs, their names and pins, and the without-heater results.'
]);
export const CHOOSER_CHOICE='Choosing a model sets which physics it solves. Dimensions you entered and runs you completed are kept, and Undo takes the choice back between the optical, steady heat and Joule heating models. The heated silicon waveguide has its own Undo for its edits: to leave it, choose another model here.';
export function renderApplications(host,resume=null){
 host.replaceChildren();
 const card=resume?resumeCard(resume):null;if(card)host.append(card);
 const heading=document.createElement('h2');heading.textContent='Choose a starting model';
 const intro=document.createElement('p');intro.textContent='One workspace for model setup, studies and results. Check what can run before you start.';
 const cards=document.createElement('div');cards.className='cards';
 for(const app of [...APPLICATIONS,...COUPLED_TEMPLATES]){
  const button=document.createElement('button');button.dataset.template=app.id;
  const title=document.createElement('strong');title.textContent=app.title;
  const status=document.createElement('span');status.className='application-status'+(app.available?' available':'');status.textContent=app.status;
  const description=document.createElement('p');description.textContent=app.description;
  const scope=document.createElement('span');scope.textContent=app.scope;
  button.append(title,status,description,scope);cards.append(button);
 }
 const contract=document.createElement('section');contract.className='application-contract';
 const contractTitle=document.createElement('h3');contractTitle.textContent='What this workspace supports';
 const list=document.createElement('ul');for(const text of CHOOSER_NOTES){const item=document.createElement('li');item.textContent=text;list.append(item);}
 const choice=document.createElement('p');choice.textContent=CHOOSER_CHOICE;contract.append(contractTitle,list,choice);
 host.append(heading,intro,cards,contract);
}
