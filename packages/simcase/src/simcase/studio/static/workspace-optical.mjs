// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
import {validateShapes,legacyCoreShape,shapesBlock,solverShapes,gradingCentre} from './workspace-shapes.mjs';
import {DEFAULT_MODE_COUNT,checkModeCount} from './workspace-notebook.mjs';
import {checkOpenBoundary,hasOpenEdge,applyOpenBoundary} from './workspace-open-boundary.mjs';

/** The study's quantity strings: the vacuum wavelength and the core element size in nm. */
export function opticalStudy(wavelengthNm=1550,coreMeshNm=30){
 if(!Number.isFinite(wavelengthNm)||wavelengthNm<1400||wavelengthNm>1700)throw new Error('Wavelength must be 1400–1700 nm.');
 if(!Number.isFinite(coreMeshNm)||coreMeshNm<20||coreMeshNm>60)throw new Error('Core mesh size must be 20–60 nm.');
 return {vacuumWavelength:wavelengthNm+' nm',coreElementSize:coreMeshNm+' nm'};
}
export function opticalBlock(state,setup){
 if(state.electric!==false||state.heat||state.structure||!state.optics)return 'Choose Library → Optical waveguide. Coupled physics are not connected.';
 if(setup.materials.Oxide!=='Silica')return 'The optical background must be silica.';
 return shapesBlock(designShapes(state,setup));
}
export function designShapes(state,setup){return validateShapes(state.shapes??[legacyCoreShape(state.width,state.height??220,setup.materials.Core)]);}
/** The wavelength step of Also compute group index: results.group_index.wavelength_step. */
export const GROUP_INDEX_STEP='1 nm';
/** The document with results.group_index ({wavelength_step: step}) added after the other
 * results keys: the group index of the single study by a central difference over λ0 ± step. */
export function withGroupIndex(doc,step=GROUP_INDEX_STEP){return {...doc,results:{...doc.results,group_index:{wavelength_step:step}}};}
// the step of a run's group_index_method (one parser, the modes table's)
export {groupIndexStep} from './workspace-modes.mjs';
/** The format 0.3 solver document: the design's nanometres as written, every other length a quantity string.
 * optical-shapes-v8: mode_count is the page's Modes to find (1 to 8, 2 by default); with 2 the
 * document is the one optical-shapes-v7 wrote. With state.groupIndex (Also compute group index)
 * it also has results.group_index; without it, it is the optical-shapes-v8 document as before. A
 * run's document is its settings' document, with withGroupIndex(doc, groupIndexStep(method)) when
 * the run has a group_index_method.
 * optical-shapes-v9: with state.openBoundary (workspace-open-boundary.mjs) and an open edge, the
 * window gets a PML outside it on each open edge; with every edge closed, or without it, the
 * document is the optical-shapes-v8 one byte for byte. The group index is not offered with an
 * open boundary. */
export function opticalDocument(state,setup){
 const block=opticalBlock(state,setup);if(block)throw new Error(block);
 const coreMesh=state.coreMesh??30,modeCount=checkModeCount(state.modeCount??DEFAULT_MODE_COUNT),shapes=designShapes(state,setup),study=opticalStudy(state.wavelength??1550,coreMesh),[cx,cy]=gradingCentre(shapes);
 const doc={openphysics:'0.3',name:'Workspace optical study',geometry:{length_unit:'nm',depth:null,domain:{xmin:-1500,xmax:1500,ymin:-1200,ymax:1200},background:{material:'physmat:SiO2'},shapes:solverShapes(shapes,coreMesh)},physics:{em1:{type:'em.modes2d',formulation:'vector',vacuum_wavelength:study.vacuumWavelength,mode_count:modeCount,effective_index_threshold:1.45,boundary:{left:'pec',right:'pec',top:'pec',bottom:'pec'}}},mesh:{element_size:'250 nm',grading:{position:[cx+' nm',cy+' nm'],near:study.coreElementSize,far:'160 nm',refinement_distance:'1000 nm'}},study:{type:'single'},results:{save_fields:true,plots:false}};
 const open=state.openBoundary==null?null:checkOpenBoundary(state.openBoundary,shapes);
 if(open&&hasOpenEdge(open)){
  if(state.groupIndex===true)throw new Error('Group index is not computed with an open boundary; close every edge to compute it.');
  return applyOpenBoundary(doc,open);
 }
 return state.groupIndex===true?withGroupIndex(doc):doc;
}
