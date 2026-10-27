// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
import {validateShapes,legacyCoreShape,shapesBlock,solverShapes,gradingCentre} from './workspace-shapes.mjs';

export function opticalStudy(wavelengthNm=1550,coreMeshNm=30){
 if(!Number.isFinite(wavelengthNm)||wavelengthNm<1400||wavelengthNm>1700)throw new Error('Wavelength must be 1400–1700 nm.');
 if(!Number.isFinite(coreMeshNm)||coreMeshNm<20||coreMeshNm>60)throw new Error('Core mesh size must be 20–60 nm.');
 return {wavelength:wavelengthNm/1000,coreMesh:coreMeshNm/1000};
}
export function opticalBlock(state,setup){
 if(state.electric!==false||state.heat||state.structure||!state.optics)return 'Choose Applications → Optical waveguide. Coupled physics are not connected.';
 if(setup.materials.Oxide!=='Silica')return 'The optical background must be silica.';
 return shapesBlock(designShapes(state,setup));
}
export function designShapes(state,setup){return validateShapes(state.shapes??[legacyCoreShape(state.width,state.height??220,setup.materials.Core)]);}
export function opticalDocument(state,setup){
 const block=opticalBlock(state,setup);if(block)throw new Error(block);
 const shapes=designShapes(state,setup),study=opticalStudy(state.wavelength??1550,state.coreMesh??30);
 return {openphysics:'0.2',name:'Workspace optical study',units:{length:'um'},geometry:{domain:{xmin:-1.5,xmax:1.5,ymin:-1.2,ymax:1.2},background:{material:'SiO2'},shapes:solverShapes(shapes,study.coreMesh)},physics:{em1:{type:'em.modes2d',formulation:'vector',wavelength:study.wavelength,num_modes:2,n_cladding:1.45,boundary:{left:'pec',right:'pec',top:'pec',bottom:'pec'}}},mesh:{size:0.25,grading:{center:gradingCentre(shapes),near:study.coreMesh,far:0.16,distance:1}},study:{type:'single'},results:{save_fields:true,plots:false}};
}
