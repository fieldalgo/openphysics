// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

export function opticalBlock(state,setup){
 if(state.electric!==false||state.heat||state.structure||!state.optics)return 'Choose Applications → Optical waveguide. Coupled physics are not connected.';
 if(!['Silicon','Silicon nitride'].includes(setup.materials.Core)||setup.materials.Oxide!=='Silica')return 'Supported materials: silicon or silicon nitride core in silica.';
 return '';
}
export function opticalDocument(state,setup){
 const block=opticalBlock(state,setup);if(block)throw new Error(block);
 const width=state.width/1000;
 return {openphysics:'0.2',name:'Workspace optical study',units:{length:'um'},geometry:{domain:{xmin:-1.5,xmax:1.5,ymin:-1.2,ymax:1.2},background:{material:'SiO2'},shapes:[{name:'core',type:'rect',x:-width/2,y:0,w:width,h:0.22,material:setup.materials.Core==='Silicon'?'Si':'Si3N4',mesh_size:0.03}]},physics:{em1:{type:'em.modes2d',formulation:'vector',wavelength:1.55,num_modes:2,n_cladding:1.45,boundary:{left:'pec',right:'pec',top:'pec',bottom:'pec'}}},mesh:{size:0.25,grading:{center:[0,0.11],near:0.03,far:0.16,distance:1}},study:{type:'single'},results:{save_fields:true,plots:false}};
}
