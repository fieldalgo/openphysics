// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
import {validateShapes,legacyCoreShape,shapesBlock,solverShapes,gradingCentre} from './workspace-shapes.mjs';

/** The study's quantity strings: the vacuum wavelength and the core element size in nm. */
export function opticalStudy(wavelengthNm=1550,coreMeshNm=30){
 if(!Number.isFinite(wavelengthNm)||wavelengthNm<1400||wavelengthNm>1700)throw new Error('Wavelength must be 1400–1700 nm.');
 if(!Number.isFinite(coreMeshNm)||coreMeshNm<20||coreMeshNm>60)throw new Error('Core mesh size must be 20–60 nm.');
 return {vacuumWavelength:wavelengthNm+' nm',coreElementSize:coreMeshNm+' nm'};
}
export function opticalBlock(state,setup){
 if(state.electric!==false||state.heat||state.structure||!state.optics)return 'Choose Applications → Optical waveguide. Coupled physics are not connected.';
 if(setup.materials.Oxide!=='Silica')return 'The optical background must be silica.';
 return shapesBlock(designShapes(state,setup));
}
export function designShapes(state,setup){return validateShapes(state.shapes??[legacyCoreShape(state.width,state.height??220,setup.materials.Core)]);}
/** The format 0.3 solver document: the design's nanometres as written, every other length a quantity string. */
export function opticalDocument(state,setup){
 const block=opticalBlock(state,setup);if(block)throw new Error(block);
 const coreMesh=state.coreMesh??30,shapes=designShapes(state,setup),study=opticalStudy(state.wavelength??1550,coreMesh),[cx,cy]=gradingCentre(shapes);
 return {openphysics:'0.3',name:'Workspace optical study',geometry:{length_unit:'nm',depth:null,domain:{xmin:-1500,xmax:1500,ymin:-1200,ymax:1200},background:{material:'physmat:SiO2'},shapes:solverShapes(shapes,coreMesh)},physics:{em1:{type:'em.modes2d',formulation:'vector',vacuum_wavelength:study.vacuumWavelength,mode_count:2,effective_index_threshold:1.45,boundary:{left:'pec',right:'pec',top:'pec',bottom:'pec'}}},mesh:{element_size:'250 nm',grading:{position:[cx+' nm',cy+' nm'],near:study.coreElementSize,far:'160 nm',refinement_distance:'1000 nm'}},study:{type:'single'},results:{save_fields:true,plots:false}};
}
