// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

// Workspace adapter availability, not a claim about the entire solver library.
export const APPLICATIONS=Object.freeze([
 Object.freeze({id:'optical',title:'Optical waveguide',status:'Live optical calculation',available:true,description:'Edit the core, calculate optical modes, compare fields and save results.',scope:'2D cross section in silica · rectangles, circles, polygons · wavelength and core mesh',physics:Object.freeze({electric:false,heat:false,structure:false,optics:true})}),
 Object.freeze({id:'multi',title:'Heated optical waveguide',status:'Setup only · calculation unavailable',available:false,description:'Arrange electric, thermal, structural and optical interfaces in one model.',scope:'Conceptual regions and boundaries · coupled adapter pending',physics:Object.freeze({electric:true,heat:true,structure:true,optics:true})})
]);
export function templatePhysics(id){
 const application=APPLICATIONS.find(a=>a.id===id);
 if(!application)throw new Error('Unknown application template.');
 return {...application.physics};
}
export function renderApplications(host){
 host.replaceChildren();
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
 contract.innerHTML='<h3>What this workspace supports</h3><ul><li>Optical: up to 8 rectangles, circles or polygons of ten lossless materials (silicon, silicon nitride, silica, air, sapphire, lithium niobate, InP, GaAs, CaF2, MgF2) in a silica background; wavelength 1400–1700 nm, core mesh 20–60 nm, two candidates.</li><li>Multiphysics: edit the setup and connections. Electrical heating and mechanical deformation do not run here yet.</li><li>Existing thermal Studio views remain separate from this workspace.</li></ul><p>Choosing a template changes physics selections, retains dimensions and run history, and can be undone. Save session to keep inputs and completed results.</p>';
 host.append(heading,intro,cards,contract);
}
