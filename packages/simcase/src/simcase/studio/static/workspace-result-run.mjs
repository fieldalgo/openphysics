// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// The run the page keeps of an optical result (/api/jobs/<id>/result), as the result handler of
// workspace-app.mjs builds it: the modes found (1 to the count asked for), the open boundary's modes
// with their candidate record, or a closed-window search's modes above n = 1.45, with the engine's TE
// fractions, effective areas and group index of those modes. Run retention's Recompute Run N's fields
// builds the same run of the recomputed result and compares its values with the stored ones.
import {DEFAULT_MODE_COUNT,opticalSettings,closedTargetSettings,validateRun,engineRunValues,engineGroupIndex,engineGroupIndexReasons,resultTimings} from './workspace-notebook.mjs';
import {openResultValues,openSettings,keptValues} from './workspace-open-run.mjs';
import {closedResultValues} from './workspace-closed-target.mjs';
import {readOpticalField} from './workspace-field.mjs';

/** The modes of a result: {asked, re, im}; an error for a result that is not an optical one of
 * 1 to `asked` modes. pending: the job's record (modeCount). */
export function resultModes(result,pending){
 const asked=pending.modeCount??DEFAULT_MODE_COUNT,e=result.effective_index,re=Array.isArray(e?.values)?e.values[0]:e?.re?.[0],im=Array.isArray(e?.im)?e.im[0]:null;
 if(e?.unit!=='1'||!Array.isArray(re)||re.length<1||re.length>asked||!re.every(Number.isFinite)||(im!==null&&(!Array.isArray(im)||im.length!==re.length||!im.every(Number.isFinite))))throw new Error('Unsupported optical result.');
 return {asked,re,im};
}
/** The run of a result (validated, origin "local"), with groupIndexReasons (this tab only) when the
 * engine gave them. An open run keeps the server's compute time (timings {mesh, solve} in s to
 * 0.001 s, session version 16) when the result holds both numbers; a closed run keeps none. pending: the job's record (job, input, modeCount, openBoundary, searchTarget,
 * serverVersion). completedAt: the run's time (now unless given). */
export function runOfResult(result,pending,{completedAt=new Date().toISOString()}={}){
 const {asked,re,im}=resultModes(result,pending),input=pending.input;
 // an open boundary: the modes above n = 1.45 with their candidate record, and the engine's TE
 // fractions, effective areas (physical window) and group index of those modes (slice P3)
 const open=pending.openBoundary?(()=>{if(im===null)throw new Error('Unsupported optical result.');return openResultValues(result,re,im,pending.openBoundary.target);})():null;
 // a closed-window search (slice C2, A1): the modes above n = 1.45, with the engine's values of those modes
 const target=open?null:pending.searchTarget??null,near=target===null?null:closedResultValues(result,re,target);
 const kept=open?open.re:near?near.re:re,keptIm=open?open.im:im;
 const closedSettings=opticalSettings(input.model.wavelength,input.model.coreMesh,asked);
 const settings=open?openSettings(closedSettings,pending.openBoundary,input.model.shapes):near?closedTargetSettings(closedSettings,target):closedSettings;
 const completed=validateRun({job:pending.job,completedAt,settings,input,effective_index:keptIm?{re:[...kept],im:[...keptIm]}:[...kept],field:readOpticalField(open?open.data:near?near.data:result,kept.length,{open:!!open}),origin:'local',serverVersion:pending.serverVersion,
  ...(open&&resultTimings(result.timings)?{timings:resultTimings(result.timings)}:{}),
  ...(open?{open_boundary:open.record,...keptValues({...engineRunValues(result.summary,re.length),...engineGroupIndex(result.summary,re.length)},open.keep)}:near?keptValues({...engineRunValues(result.summary,re.length),...engineGroupIndex(result.summary,re.length)},near.keep):{
  // the engine's TE fractions and effective areas, kept with the run (a version 9 file keeps them)
  ...engineRunValues(result.summary,re.length),
  // the engine's group index with Also compute group index (a version 9 file keeps it)
  ...engineGroupIndex(result.summary,re.length)})});
 // the reason of each null n_g, in this tab only (a session file does not keep it)
 if(completed.group_index){const reasons=engineGroupIndexReasons(result.summary,re.length);if(reasons)completed.groupIndexReasons=open?open.keep.map(i=>reasons[i]):near?near.keep.map(i=>reasons[i]):reasons;}
 return completed;
}
