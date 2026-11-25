// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

import {validateProject,withoutStudy,withStudy,projectStudy,projectBoundary,STUDY_PROJECT_VERSION,OPEN_PROJECT_VERSION} from './workspace-project.mjs';
import {OPEN_ADAPTER,isOpenRun,checkOpenSettings,checkCandidateRecord,checkPmlCheck,modeCandidates} from './workspace-open-run.mjs';
import {CLOSED_TARGET_ADAPTER,checkClosedTarget} from './workspace-closed-target.mjs';
import {readOpticalField,fieldScalars,FIELD_METADATA,PML_FIELD_METADATA,physicalBounds,windowField} from './workspace-field.mjs';
import {isCompactRecord,decodeField,encodeField,compactRecord,isCompactField,markCompact,singlePrecision,compactFieldBytes,COMPACT_FIELD_KEYS} from './workspace-field-encoding.mjs';
import {shapesBlock,shapeText} from './workspace-shapes.mjs';
import {opticalModes} from './workspace-modes.mjs';
import {MULTIPHYSICS_VERSION,MULTIPHYSICS_VERSIONS,readMultiphysicsSession,sessionJson,recordDigest,sizeText} from './workspace-multiphysics-session.mjs';
import {MAX_SESSION_BYTES,FIELD_HEADROOM_BYTES,FIELD_BUDGET_BYTES,mbText} from './workspace-budget.mjs';
export {MAX_SESSION_BYTES};
// Run retention (design "Keeping more runs"): up to 20 runs keep their values in the tab, in files and
// in browser recovery; their fields are kept within the 16 MiB session (workspace-retention.mjs).
// A session file of versions 6 to 12 holds at most six runs (PREVIOUS_RUN_LIMIT): a session of more
// runs is written as version 13, which the previous Studio refuses by name.
export const RUN_LIMIT=20;
export const PREVIOUS_RUN_LIMIT=6;
// The fields of the runs are kept within the session less 16 KiB kept for the inputs (the field
// budget, workspace-retention.mjs): 16,760,832 bytes, "16.8 MB" (workspace-budget.mjs, shared with
// the heated model's maps).
export {FIELD_HEADROOM_BYTES,FIELD_BUDGET_BYTES,mbText};
// The run limit and the field budget, from RUN_LIMIT and FIELD_BUDGET_BYTES themselves, so the run
// list's note and the model tree's "Runs · N of M" never disagree (round 14); in digits.
// Round 25 (A1): the words say when fields move (only when a result or a recompute arrives) and that
// selecting a run does not bring its fields back (FIELDS_MOVE_TEXT, also in Results).
export const FIELDS_MOVE_TEXT=`Fields are kept up to ${mbText(FIELD_BUDGET_BYTES)}. When a result or a recompute arrives, Studio keeps the selected run's fields first, then pinned runs', then the newest. Selecting a run does not bring its fields back; Recompute does.`;
export const RUNS_KEPT_TEXT=`Up to ${RUN_LIMIT} runs are kept with their values. ${FIELDS_MOVE_TEXT}`;
export const runsNodeLabel=count=>`Runs · ${count} of ${RUN_LIMIT}`;
// Session format 7: the input is a project of version 7 (Joule heating inputs added); runs are
// unchanged, and a version 6 session is read with its input as a version 6 project. Format 6
// (units and naming batch): run records under the section 5.3.4 names (effective_index,
// node_coordinates in m), settings and view coordinates as quantity strings.
// Format 9 (optical sessions only): runs of 1 to 8 modes, complex indices, the engine's TE
// fractions and effective areas, runs without fields and a digest per run. A session that
// version 7 can hold (every run has two real modes, its fields, nothing else) is still written
// as version 7, byte for byte; version 9 is written once a run needs it.
// Format 10 (open boundary, slice P2): format 9 with runs of optical-shapes-v9, whose settings
// hold boundary "PML" and pml {thickness, open_edges, target}, the engine's candidate record
// (open_boundary) and, when it ran, the PML check (pml_check). Written only when a run has an open
// boundary or the inputs choose Open (inputs version 9); otherwise version 9 or 7, byte for byte.
export const SESSION_VERSION=7;
export const OPTICAL_SESSION_VERSION=9;
export const OPEN_SESSION_VERSION=10;
// Format 11 (Search near n_eff for closed-window runs, slice C2): format 10 with runs of
// optical-shapes-v10, whose settings hold search_target (the closed window's Search near n_eff) after
// mode_count, and whose modes are all above n = 1.45 (Studio leaves the others out). Written only
// when such a run is kept; otherwise version 10, 9 or 7, byte for byte.
export const CLOSED_TARGET_SESSION_VERSION=11;
// Format 12 (stable run numbers): format 11 with each run's number in the tab (`number`, after job,
// inside the run's digest). Every run of versions 9 to 11 is held. Written only when some run's
// number is not its place in the list (a run was dropped, or the tab numbered runs after an import);
// otherwise version 11, 10, 9 or 7, byte for byte. A file of an earlier version is numbered from 1
// in file order, as before.
export const NUMBERED_SESSION_VERSION=12;
// Format 13 (run retention): format 12 with 0 to 20 runs (versions 6 to 12 hold at most six). The run
// records are those of version 12 (the number, the same keys, the same digest). Written only when the
// session has more than six runs; otherwise version 12, 11, 10, 9 or 7, byte for byte. The previous
// Studio reads versions 6 to 12 and refuses a version 13 file by name before it counts the runs.
export const RUNS_SESSION_VERSION=13;
// Format 14 (compact fields, design "Compact field encoding"): format 13 whose runs may hold a compact
// field (workspace-field-encoding.mjs: float32 samples, float64 coordinates and uint32 triangles in
// base64); a run with a compact field also stores its TE fractions and effective areas. Written only
// when a run kept with its field holds it compact; otherwise version 13, 12, 11, 10, 9 or 7, byte for
// byte. The previous Studio reads versions 6 to 13 and refuses a version 14 file by name.
export const COMPACT_SESSION_VERSION=14;
/** Whether a version writes and reads the run number (versions 12 to 14). */
const numbered=version=>version===NUMBERED_SESSION_VERSION||version===RUNS_SESSION_VERSION||version===COMPACT_SESSION_VERSION;
// The adapter of this Studio: optical-shapes-v8 builds the document of optical-shapes-v7 with the
// mode count asked for (1 to 8). A version 7 run is a v8 run of two modes: its document is the same.
export const OPTICAL_ADAPTER='optical-shapes-v8';
export const V7_ADAPTER='optical-shapes-v7';
export const MODE_COUNT_RANGE=Object.freeze([1,8]);
export const DEFAULT_MODE_COUNT=2;
export const MODE_COUNT_TEXT='Modes to find must be a whole number from 1 to 8.';
/** A mode count of 1 to 8, or an error with MODE_COUNT_TEXT. */
export function checkModeCount(n){if(!Number.isInteger(n)||n<MODE_COUNT_RANGE[0]||n>MODE_COUNT_RANGE[1])throw new Error(MODE_COUNT_TEXT);return n;}
// The threshold the optical document asks for (effective_index_threshold): the engine keeps
// the modes with Re n_eff above it.
export const GUIDED_THRESHOLD=1.45;
/** "Found 3 of 8 modes above n = 1.45" when a run found fewer modes than asked, else ''. */
export const foundText=(found,asked)=>found<asked?`Found ${found} of ${asked} modes above n = ${GUIDED_THRESHOLD}`:'';
export const WINDOW_UM=Object.freeze({xmin:-1.5,xmax:1.5,ymin:-1.2,ymax:1.2});
const um=value=>value+' um';
export const OPTICAL_SETTINGS=Object.freeze({adapter:OPTICAL_ADAPTER,domain:Object.freeze({xmin:um(WINDOW_UM.xmin),xmax:um(WINDOW_UM.xmax),ymin:um(WINDOW_UM.ymin),ymax:um(WINDOW_UM.ymax)}),boundary:'PEC',solver_version:'not reported'});
function studyRange(wavelength,coreMesh){if(!Number.isFinite(wavelength)||wavelength<1400||wavelength>1700||!Number.isFinite(coreMesh)||coreMesh<20||coreMesh>60)throw new Error('Unsupported wavelength or core mesh size.');}
/** The settings of a run of this Studio (key order fixed: it is the order a file writes). */
export function opticalSettings(wavelength=1550,coreMesh=30,modeCount=DEFAULT_MODE_COUNT){
 studyRange(wavelength,coreMesh);checkModeCount(modeCount);const s=OPTICAL_SETTINGS;
 return {adapter:s.adapter,domain:s.domain,boundary:s.boundary,mode_count:modeCount,solver_version:s.solver_version,vacuum_wavelength:wavelength+' nm',core_element_size:coreMesh+' nm'};
}
/** The settings of a closed-window run with Search near n_eff t (optical-shapes-v10): the closed
 * settings with that adapter and search_target after mode_count. */
export function closedTargetSettings(settings,t){
 return {adapter:CLOSED_TARGET_ADAPTER,domain:settings.domain,boundary:settings.boundary,mode_count:settings.mode_count,search_target:t,solver_version:settings.solver_version,vacuum_wavelength:settings.vacuum_wavelength,core_element_size:settings.core_element_size};
}
/** Whether a run is a closed-window run with Search near n_eff (optical-shapes-v10). */
export const isClosedTargetRun=run=>run?.settings?.adapter===CLOSED_TARGET_ADAPTER;
/** The closed-window Search near n_eff of a run, or null. */
export const runSearchTarget=run=>isClosedTargetRun(run)?run.settings.search_target:null;
/** The settings a version 7 file writes for a run of two modes: those of optical-shapes-v7. */
export function v7Settings(settings){return {...settings,adapter:V7_ADAPTER,mode_count:2};}
// Runs of earlier adapters came in sessions of versions 1-5, which are refused by name.
function expectedSettings(settings,model,number){
 const adapter=settings?.adapter;
 if(adapter===V7_ADAPTER){studyRange(model.wavelength,model.coreMesh);return v7Settings(opticalSettings(model.wavelength,model.coreMesh));}
 if(adapter===CLOSED_TARGET_ADAPTER){
  const {search_target,...rest}=settings,closed=expectedSettings({...rest,adapter:OPTICAL_ADAPTER},model,number);
  try{checkClosedTarget(search_target,model.shapes);}catch(error){throw new Error(`${number?'Run '+number:'This run'}: invalid search target. ${error.message}`);}
  return closedTargetSettings(closed,search_target);
 }
 if(adapter===OPEN_ADAPTER){const closed=expectedSettings({...settings,adapter:OPTICAL_ADAPTER},model,number);return checkOpenSettings(settings,closed,model.shapes,number?'Run '+number:'This run');}
 if(adapter!==OPTICAL_ADAPTER)throw new Error('Unsupported run settings or input mismatch.');
 const n=settings.mode_count;
 if(!Number.isInteger(n)||n<MODE_COUNT_RANGE[0]||n>MODE_COUNT_RANGE[1])throw new Error(`${number?'Run '+number:'This run'} asks for ${typeof n==='number'&&Number.isFinite(n)?n:'an unknown number of'} modes; this Studio reads 1 to 8.`);
 return opticalSettings(model.wavelength,model.coreMesh,n);
}
/** The mode count a run asked for (2 for a version 7 run). */
export const runModeCount=run=>run.settings.mode_count;
/** The signature of a run's study: its input text, and its mode count when it is not 2 (a run of
 * two modes keeps the signature of the input alone, as before mode counts could change). */
export const studySignature=(input,modeCount=DEFAULT_MODE_COUNT,groupIndex=false,pml=null,searchTarget=null)=>JSON.stringify(input)+(modeCount===DEFAULT_MODE_COUNT?'':`\n${modeCount} modes`)+(groupIndex===true?'\ngroup index':'')+(pml?`\nopen boundary ${pml.open_edges.join(' ')} near ${pml.target}`:'')+(!pml&&searchTarget!=null?`\nnear ${searchTarget}`:'');
/** A length written with its unit ("0.15 um", "150 nm", "1.5e-7 m") in micrometres, the page's display
 * unit, and its value in metres; a bare number is refused. */
const LENGTH=/^([+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?) (nm|um|m)$/i;
export function parseLength(text){
 const found=typeof text==='string'?LENGTH.exec(text):null;
 if(!found||!Number.isFinite(Number(found[1])))throw new Error('expected a length with its unit, such as "0.15 um"');
 const value=Number(found[1]),unit=found[2];
 return {um:unit==='um'?value:unit==='nm'?value/1000:value*1e6,m:unit==='m'?value:unit==='nm'?value*1e-9:value*1e-6};
}
const inWindow=(metres,extent)=>Math.abs(metres)<=extent*1e-6*(1+1e-12);
export function validateRunLabel(value=''){
 if(typeof value!=='string'||value.length>80||/[\u0000-\u001f\u007f-\u009f]/.test(value))throw new Error('Run name must be at most 80 characters without control characters.');
 return value.trim();
}
// A value of the page's own unit in SI, by moving the decimal point of its shortest text (a correctly
// rounded parse, not a binary product): 220 nm -> 2.2e-7 m. A text that already has an exponent
// (1e-7) moves that exponent.
const si=(value,exponent)=>{if(value==='')return '';const [digits,power='0']=String(value).split(/e/i);return Number(`${digits}e${Number(power)+exponent}`);};
export function csvCell(value){const text=String(value);const safe=typeof value==='string'&&/^\s*[=+@-]/.test(text)?"'"+text:text;return '"'+safe.replaceAll('"','""')+'"';}
// The run table (units and naming batch): every quantity column is `name [unit]` with its SI value;
// identifier and text columns carry no unit.
// The columns up to origin are the earlier table's, in place: effective_index [1] is Re n_eff. Two
// columns follow: effective_index_imag [1], Im n_eff (exp(-iωt); a run of this tab keeps it in
// effective_index_im; 0 for a lossless run, whose n_eff is real), and group_index [1], n_g of a run with the group index ('' when the run has none
// or the mode has no value; Re n_g for an open run, whose n_g is complex).
export function runTableCsv(runs){
 const rows=[['job','name','pinned','completed_at','core_width [m]','core_height [m]','vacuum_wavelength [m]','core_element_size [m]','core_material','shapes','candidate','effective_index [1]','origin','effective_index_imag [1]','group_index [1]']];
 for(const r of runs){const shapes=r.input.model.shapes,single=shapes.length===1&&shapes[0].type==='rect'?shapes[0]:null;
  const e=r.effective_index,re=Array.isArray(e)?e:e.re,im=Array.isArray(e)?(Array.isArray(r.effective_index_im)?r.effective_index_im:null):e.im,ng=Array.isArray(r.group_index)?r.group_index:Array.isArray(r.group_index?.re)?r.group_index.re:null;
  re.forEach((n,i)=>rows.push([r.job,r.label||'',r.pinned===true,r.completedAt,si(single?single.w:'',-9),si(single?single.h:'',-9),si(r.input.model.wavelength,-9),si(r.input.model.coreMesh,-9),single?single.material:'',shapes.map(shapeText).join(' | '),i+1,n,r.origin,im?im[i]:0,ng&&Number.isFinite(ng[i])?ng[i]:'']));}
 return rows.map(row=>row.map(csvCell).join(',')).join('\n')+'\n';
}
const finiteList=(v,k)=>Array.isArray(v)&&v.length===k&&v.every(Number.isFinite);
const isObject=x=>x!==null&&typeof x==='object'&&!Array.isArray(x);
// a list of k entries, each a number for which ok holds or null
const valueList=(v,k,ok)=>Array.isArray(v)&&v.length===k&&v.every(x=>x===null||(Number.isFinite(x)&&ok(x)));
const METHOD=/^[^\u0000-\u001f\u007f-\u009f]{1,64}$/;
/** A run record, checked. format: 7 for a run of a version 6 or 7 file (two real modes, its
 * fields, nothing else read), 9 or 10 for a run of a version 9 or 10 file (all its keys checked),
 * absent for a run of this tab (a new result, or one read before). number: the run's place in a
 * file. A run of optical-shapes-v9 (an open boundary) is read from version 10 files only. */
export function validateRun(record,imported=false,{format=null,number=null,compact=false}={}){
 const which=number?`Run ${number}`:'This run';
 if(!record||typeof record.job!=='string'||!/^[a-f0-9]{8}$/.test(record.job))throw new Error('Invalid run identifier.');
 if(typeof record.completedAt!=='string'||!Number.isFinite(Date.parse(record.completedAt)))throw new Error('Invalid run timestamp.');

 if(record.input?.units?.width!=='nm'||record.input?.units?.temperature!=='K'||record.input?.units?.voltage!=='V')throw new Error('Invalid run units.');
 if(record.serverVersion!=null&&(typeof record.serverVersion!=='string'||!/^\d[0-9A-Za-z.+-]{0,63}$/.test(record.serverVersion)))throw new Error('Invalid server version.');
 if(record.pinned!==undefined&&typeof record.pinned!=='boolean')throw new Error('Invalid run pin state.');
 // a run keeps its inputs without study settings (version 6 or 7): its settings hold Modes to find
 if(record.input?.version===STUDY_PROJECT_VERSION)throw new Error('Unsupported run settings or input mismatch.');
 const input=validateProject(record.input);
 if(format===7&&record.settings?.adapter!==V7_ADAPTER)throw new Error('Unsupported run settings or input mismatch.');
 if(format===11&&![OPTICAL_ADAPTER,OPEN_ADAPTER,CLOSED_TARGET_ADAPTER].includes(record.settings?.adapter))throw new Error(`${which}: unsupported run settings (a version 11 file writes ${OPTICAL_ADAPTER}, ${OPEN_ADAPTER} or ${CLOSED_TARGET_ADAPTER}).`);
 if(format===10&&![OPTICAL_ADAPTER,OPEN_ADAPTER].includes(record.settings?.adapter))throw new Error(`${which}: unsupported run settings (a version 10 file writes ${OPTICAL_ADAPTER} or ${OPEN_ADAPTER}).`);
 if(format===9&&record.settings?.adapter!==OPTICAL_ADAPTER)throw new Error(`${which}: unsupported run settings (a version 9 file writes ${OPTICAL_ADAPTER}).`);
 const settings=expectedSettings(record.settings,input.model,number);
 if(!record.settings||Object.keys(record.settings).length!==Object.keys(settings).length||Object.keys(settings).some(k=>JSON.stringify(record.settings[k])!==JSON.stringify(settings[k])))throw new Error('Unsupported run settings or input mismatch.');
 if(input.model.electric||input.model.heat||input.model.structure||!input.model.optics||shapesBlock(input.model.shapes)||input.setup.materials.Oxide!=='Silica')throw new Error('Run is not a supported optical-only input.');
 const asked=settings.mode_count,e=record.effective_index;
 let re,im=null;
 if(Array.isArray(e)){re=e;if(format===null&&record.effective_index_im!==undefined)im=record.effective_index_im;}
 else if(format!==7&&isObject(e)&&Object.keys(e).length===2&&Array.isArray(e.re)&&Array.isArray(e.im)){re=e.re;im=e.im;}
 else throw new Error('Invalid effective indices.');
 const k=re.length;
 if(format===7||settings.adapter===V7_ADAPTER?!finiteList(re,2):(k<1||k>asked||!finiteList(re,k)||(im!==null&&!finiteList(im,k))))throw new Error('Invalid effective indices.');
 // a closed-window search run lists only modes above n = 1.45 (the others are left out, A1)
 if(settings.adapter===CLOSED_TARGET_ADAPTER&&re.some(x=>!(x>GUIDED_THRESHOLD)))throw new Error(`${which}: a closed-window search lists only modes above n = ${GUIDED_THRESHOLD}.`);
 if(format===9||format===10||format===11){
  if(re.some((x,i)=>i>0&&x>re[i-1]))throw new Error(`${which}: its effective indices are not ranked by Re n_eff.`);
  if(re.some(x=>!(x>GUIDED_THRESHOLD)))throw new Error(`${which}: an effective index is not above n = ${GUIDED_THRESHOLD}.`);
 }
 // the engine's values per mode (version 9 and this tab); a version 7 file holds none
 const extra={};
 if(format!==7){
  for(const [key,ok,text] of [['te_polarization_fraction',x=>x>=0&&x<=1,'TE fractions'],['effective_area',x=>x>0,'effective areas']]){
   if(record[key]===undefined)continue;
   if(!valueList(record[key],k,ok))throw new Error(`${which}: invalid saved ${text}.`);
   extra[key]=[...record[key]];
  }
  // n_g: k numbers or null; complex for an open run ({re, im} in a file, group_index and
  // group_index_im on a run of this tab), each mode null in both parts or in neither
  if(record.group_index!==undefined){
   const g=record.group_index,bad=()=>{throw new Error(`${which}: invalid saved group indices.`);};
   let gre=g,gim=null;
   if(isObject(g)){if(format===7||Object.keys(g).join()!=='re,im')bad();gre=g.re;gim=g.im;}
   else if(format===null&&record.group_index_im!==undefined)gim=record.group_index_im;
   if(!valueList(gre,k,()=>true)||(gim!==null&&(!valueList(gim,k,()=>true)||gre.some((x,i)=>(x===null)!==(gim[i]===null)))))bad();
   extra.group_index=[...gre];if(gim!==null)extra.group_index_im=[...gim];
  }
  if(record.group_index_method!==undefined){
   if(extra.group_index===undefined||typeof record.group_index_method!=='string'||!METHOD.test(record.group_index_method))throw new Error(`${which}: invalid group index method.`);
   extra.group_index_method=record.group_index_method;
  }
 }
 // an open run: the engine's candidate record (each mode one of its selected candidates), no
 // group index, and the PML check when it ran; a closed run has neither
 if(settings.adapter===OPEN_ADAPTER){
  if(extra.group_index!==undefined&&extra.group_index_im===undefined)throw new Error(`${which}: a run with an open boundary has a complex group index.`);
  if(im===null)throw new Error(`${which}: a run with an open boundary has complex effective indices.`);
  // a run of two searches (/3) holds exactly the searches of its target (slice T2)
  const ob=checkCandidateRecord(record.open_boundary,which,settings.pml.target);
  if(modeCandidates(ob,re,im).some(c=>c===null))throw new Error(`${which}: its modes are not the selected candidates of its open boundary record.`);
  extra.open_boundary=ob;
  if(record.pml_check!==undefined)extra.pml_check=checkPmlCheck(record.pml_check,k,which);
 }else if(record.open_boundary!==undefined||record.pml_check!==undefined)throw new Error(`${which}: a closed window has no open boundary record.`);
 else if(extra.group_index_im!==undefined)throw new Error(`${which}: a closed window has a real group index.`);
 let f=record.field,field=null,stored=null;
 // a compact field: the record of a version 14 file (its strings decoded and checked), or a field of
 // this tab already compact (its record kept with it); either is then read as nested numbers
 if(isCompactRecord(f)){
  if(format!==null&&!compact)throw new Error(`${which}: a compact field is read from a version 14 session file only.`);
  f=decodeField(f,format===7?2:k,which);
  stored=Object.freeze({...Object.fromEntries(COMPACT_FIELD_KEYS.map(key=>[key,record.field[key]])),counts:Object.freeze({...record.field.counts})});
 }else if(isCompactField(f))stored=compactRecord(f);
 if(stored&&(extra.te_polarization_fraction===undefined||extra.effective_area===undefined))throw new Error(`${which} has a compact field and no saved TE fractions and effective areas.`);
 if(f==null){
  // only a version 9 file leaves fields out (absent there; null on a run read from one)
  if(format===7||settings.adapter===V7_ADAPTER||(format===null&&f===undefined))throw new Error('Missing run fields.');
  if(extra.te_polarization_fraction===undefined||extra.effective_area===undefined)throw new Error(`${which} has no fields and no saved TE fractions and effective areas.`);
 }else{
  field=readOpticalField({node_coordinates:f.node_coordinates,field_units:{node_coordinates:'m'},triangles:f.triangles,vector_fields:[{...(settings.adapter===OPEN_ADAPTER?PML_FIELD_METADATA:FIELD_METADATA),real:f.real,imag:f.imag}]},format===7?2:k,{open:settings.adapter===OPEN_ADAPTER});
  for(let mode=0;mode<k;mode++)fieldScalars(field,mode);
  if(stored)markCompact(field,stored);
 }
 const run={pinned:record.pinned===true,label:validateRunLabel(record.label),serverVersion:record.serverVersion??null,job:record.job,completedAt:new Date(record.completedAt).toISOString(),settings:JSON.parse(JSON.stringify(settings)),input,signature:studySignature(input,asked,extra.group_index_method!==undefined,settings.pml??null,settings.search_target??null),effective_index:[...re],field,origin:imported?'imported':['imported','recovered'].includes(record.origin)?record.origin:'local'};
 if(im!==null)run.effective_index_im=[...im];
 return Object.assign(run,extra);
}
/** The engine's values of a new result to keep on its run: te_polarization_fraction and
 * effective_area of the first study point, when they are the engine's and have k entries. */
export function engineRunValues(summary,k){
 const out={},mp=summary?.mode_postprocessing;
 const take=(key,unit,ok)=>{const v=mp?.[key];if(v?.unit===unit&&valueList(v.values?.[0],k,ok))out[key]=[...v.values[0]];};
 take('te_polarization_fraction','1',x=>x>=0&&x<=1);take('effective_area','m^2',x=>x>0);
 return out;
}
/** The engine's group index of a new result (summary.group_index with group_index_method, the
 * single-study option results.group_index): {group_index: k numbers or null, group_index_method:
 * "central_difference <step> <tracker>"}, with group_index_im (k numbers or null) when n_g is
 * complex (an open boundary), or {} when the summary has none. */
export function engineGroupIndex(summary,k){
 const g=summary?.group_index,m=summary?.group_index_method;
 const complex=Array.isArray(g?.re)&&Array.isArray(g?.im),values=complex?g.re[0]:g?.values?.[0];
 if(!m||m.method!=='central_difference'||g?.unit!=='1'||!valueList(values,k,()=>true))return {};
 if(complex&&(!valueList(g.im[0],k,()=>true)||values.some((x,i)=>(x===null)!==(g.im[0][i]===null))))return {};
 const step=m.wavelength_step;
 if(step?.unit!=='m'||!(step.value>0)||typeof m.tracking!=='string'||!/^[a-z0-9-]{1,40}$/.test(m.tracking))return {};
 const method=`central_difference ${+(step.value*1e9).toPrecision(6)} nm ${m.tracking}`;
 return METHOD.test(method)?{group_index:[...values],...(complex?{group_index_im:[...g.im[0]]}:{}),group_index_method:method}:{};
}
/** The engine's reason of each null group index of a new result (summary.group_index_method.reasons):
 * k strings or null, or null. Kept on the run in this tab only: a session file does not hold them. */
export function engineGroupIndexReasons(summary,k){
 const r=summary?.group_index_method?.reasons;
 return Array.isArray(r)&&r.length===k&&r.every(x=>x===null||typeof x==='string')?[...r]:null;
}
const RUN_KEYS_9=['job','completedAt','label','pinned','origin','serverVersion','settings','input','effective_index','field','te_polarization_fraction','effective_area','group_index','group_index_method','digest'];
const RUN_KEYS_10=[...RUN_KEYS_9.slice(0,-1),'open_boundary','pml_check','digest'];
const RUN_KEYS_12=[RUN_KEYS_10[0],'number',...RUN_KEYS_10.slice(1)];
/** Whether n is a run number: a safe integer of at least 1. */
export const isRunNumber=n=>Number.isSafeInteger(n)&&n>=1;
/** A run's number: its own in the tab, else its place in the list (i: its index). */
export const runNumberAt=(run,i)=>Number.isInteger(run?.number)?run.number:i+1;
/** Whether a version 7 file holds a run: two real modes with their fields and nothing else. */
export const fitsVersion7=run=>run.settings.adapter===V7_ADAPTER||(run.settings.mode_count===2&&run.effective_index.length===2&&!run.effective_index_im&&run.field!==null&&run.group_index===undefined);
/** The record a file writes of a run. version 7: as before mode counts (the settings of
 * optical-shapes-v7, no engine values). version 9: every key in RUN_KEYS_9 order, the fields
 * left out when keepField is false (the TE fractions and areas the run shows are then written),
 * and the digest of the record. */
function sessionRun(run,version=SESSION_VERSION,keepField=true,number=null){
 const {signature,field,effective_index_im,te_polarization_fraction,effective_area,group_index,group_index_im,group_index_method,open_boundary,pml_check,...record}=validateRun(run);
 // a compact field is written again from its record (the strings it was read from or encoded to)
 const fields=field&&(compactRecord(field)??{node_coordinates:field.node_coordinates,triangles:field.triangles,real:field.real,imag:field.imag});
 if(version===SESSION_VERSION)return {...record,settings:v7Settings(record.settings),field:fields};
 const settings=record.settings.adapter===V7_ADAPTER?{...record.settings,adapter:OPTICAL_ADAPTER}:record.settings;
 const out={job:record.job,...(numbered(version)?{number}:{}),completedAt:record.completedAt,label:record.label,pinned:record.pinned,origin:record.origin,serverVersion:record.serverVersion,settings,input:record.input,
  effective_index:effective_index_im?{re:record.effective_index,im:effective_index_im}:record.effective_index};
 const shown=keepField&&fields?null:modeValues(run);
 if(keepField&&fields)out.field=fields;
 if(te_polarization_fraction||shown)out.te_polarization_fraction=shown?shown.te:te_polarization_fraction;
 if(effective_area||shown)out.effective_area=shown?shown.area:effective_area;
 if(group_index)out.group_index=group_index_im?{re:group_index,im:group_index_im}:group_index;
 if(group_index_method!==undefined)out.group_index_method=group_index_method;
 if(open_boundary)out.open_boundary=open_boundary;
 if(pml_check)out.pml_check=pml_check;
 return {...out,digest:recordDigest(out)};
}
// The TE fractions and effective areas a run shows (opticalModes keeps them on the run).
const modeValues=run=>{const modes=opticalModes(run);return {te:modes.map(m=>m.fte),area:modes.map(m=>m.area)};};
/** A run's field made compact (session version 14), in place: the run stores the TE fractions and
 * effective areas it showed (the engine's, or those computed from its float64 field for a run of a
 * version 6 or 7 file), then its field is encoded (workspace-field-encoding.mjs) and read back, so
 * the run holds the float32 samples a file holds. A run without a field, or already compact, is
 * unchanged. Returns the run. */
export function compactRunField(run){
 if(!run.field||isCompactField(run.field))return run;
 const shown=modeValues(run),f=run.field,record=encodeField(f);
 // the field a file of this record reads (validateRun): the same coordinates, nodes and triangles,
 // the samples rounded to float32 (what the decoder gives), and an open run's physical window
 const field={node_coordinates:f.node_coordinates,nodes:f.nodes,triangles:f.triangles,real:singlePrecision(f.real),imag:singlePrecision(f.imag)};
 if(f.physical)Object.defineProperty(field,'physical',{value:f.physical,enumerable:false});
 markCompact(field,Object.freeze({...record,counts:Object.freeze(record.counts)}));
 run.te_polarization_fraction=shown.te;run.effective_area=shown.area;run.field=field;
 return run;
}
const utf8Bytes=text=>new TextEncoder().encode(text).length;
// Run retention (workspace-retention.mjs): the bytes a run's field takes in a session file of version 9
// or later, the record written with its field less the record written without it (the record text
// does not depend on the other records, so a session's bytes are the sum of its records' bytes and
// its envelope). Computed once per field object and kept on the run (not enumerated).
const FIELD_BYTES=Symbol('field bytes');
export function runFieldBytes(run){
 if(!run.field)return 0;
 const cached=run[FIELD_BYTES];if(cached?.field===run.field)return cached.bytes;
 // a compact field: exact from its counts (its record's keys and the four base64 strings)
 const compact=compactRecord(run.field);
 const bytes=compact?compactFieldBytes(compact):utf8Bytes(sessionJson(sessionRun(run,OPTICAL_SESSION_VERSION,true)))-utf8Bytes(sessionJson(sessionRun(run,OPTICAL_SESSION_VERSION,false)));
 Object.defineProperty(run,FIELD_BYTES,{value:{field:run.field,bytes},enumerable:false,configurable:true,writable:true});
 return bytes;
}
/** The run as a session writes it without its field: field null, with the TE fractions and
 * effective areas it shows (as sessionRun writes them), its number and the tab's own keys kept. A
 * run of optical-shapes-v7 (read from a version 6 or 7 file) takes the settings of optical-shapes-v8,
 * as a file of version 9 or later writes them: a version 7 run always has its fields. */
export function withoutField(run){
 const shown=modeValues(run),settings=run.settings.adapter===V7_ADAPTER?{...run.settings,adapter:OPTICAL_ADAPTER}:run.settings;
 const copy={...run,settings,field:null,te_polarization_fraction:shown.te,effective_area:shown.area};
 if(Number.isInteger(run.number))copy.number=run.number;
 return copy;
}
/** The bytes of the session text of these runs with no field kept: its envelope and every run's
 * record without its field (a version of 9 or later). */
export function sessionBytesWithoutFields(input,runs,selected,comparison,view){
 return utf8Bytes(sessionText(input,runs.map(withoutField),selected,comparison,view,{keep:new Set()}));
}
/** A run's part of the save and recovery stamps: what makes a saved file stale. The PML check
 * arrives after its run, so it is part of it. */
export const runStampEntry=r=>[r.job,r.completedAt,r.label||'',r.pinned===true,...(r.pml_check?['pml check']:[])];
/** The inputs a session opens with: its own when they hold study settings or an outer boundary
 * (version 8 or 9), or when no run is selected; for an input of version 6 or 7, Modes to find and
 * the group index option of the selected run, as before. The outer boundary is never taken from a
 * run: only a version 10 file holds an open run, and it records the choice in its inputs. */
export function sessionStudyInput(input,selected){
 if([STUDY_PROJECT_VERSION,OPEN_PROJECT_VERSION].includes(input.version)||!selected)return input;
 return withStudy(input,{modeCount:runModeCount(selected),groupIndex:selected.group_index_method!==undefined});
}
/** The runs with the PML check of run `job` stored, and the selected run (the same object unless
 * it is that run). A run no longer kept cannot take its check: an error that says to detach. */
export function withPmlCheck(runs,selected,job,check){
 const run=runs.find(r=>r.job===job);
 if(!run)throw Object.assign(new Error('The run of this PML check is no longer kept; the check is not stored. Detach this job.'),{code:'solver-failed'});
 const checked=validateRun({...run,pml_check:check});if(Number.isInteger(run.inputRevision))checked.inputRevision=run.inputRevision;if(Number.isInteger(run.number))checked.number=run.number;
 return {runs:runs.map(r=>r===run?checked:r),selected:selected===run?checked:selected};
}
/** The runs with a new result: a run of a job already kept replaces it (its name and pin kept); above
 * the limit (RUN_LIMIT unless given) the oldest unpinned run other than the new one is dropped. */
export function appendRun(runs,run,limit=RUN_LIMIT){
 const previous=runs.find(r=>r.job===run.job);
 const next=[...runs.filter(r=>r.job!==run.job),previous?{...run,label:previous.label||run.label,pinned:previous.pinned||run.pinned}:run];
 while(next.length>limit){const oldest=next.findIndex(r=>!r.pinned&&r.job!==run.job);if(oldest<0)throw new Error('All notebook slots are pinned. Unpin a run before retaining another result.');next.splice(oldest,1);}
 return next;
}
/** The field view in the page's micrometres (probe x, y and profile coordinate as numbers). */
export function validateView(view={mode:0,component:'magnitude',window:'Core region'}){
 if(!view||!Number.isInteger(view.mode)||view.mode<0||view.mode>=MODE_COUNT_RANGE[1]||!['magnitude','Ex','Ey','Ez'].includes(view.component)||!['Core region','Full window'].includes(view.window))throw new Error('Unsupported saved field view.');
 const result={mode:view.mode,component:view.component,window:view.window};
 if(view.probe!==undefined){const p=view.probe;if(!p||typeof p.active!=='boolean'||!Number.isFinite(p.x)||!Number.isFinite(p.y)||p.x < -1.5||p.x > 1.5||p.y < -1.2||p.y > 1.2)throw new Error('Invalid saved probe position.');result.probe={x:p.x,y:p.y,active:p.active};}
 if(view.profile!==undefined){const p=view.profile,extent=p?.axis==='x'?1.2:1.5;if(!p||!['x','y'].includes(p.axis)||typeof p.open!=='boolean'||!Number.isFinite(p.coordinate)||Math.abs(p.coordinate)>extent)throw new Error('Invalid saved profile line.');result.profile={axis:p.axis,coordinate:p.coordinate,open:p.open};}
 return result;
}
/** The view as a session stores it: probe and profile coordinates as quantity strings. */
function sessionView(view){
 const v=validateView(view),out={mode:v.mode,component:v.component,window:v.window};
 if(v.probe)out.probe={x:um(v.probe.x),y:um(v.probe.y),active:v.probe.active};
 if(v.profile)out.profile={axis:v.profile.axis,coordinate:um(v.profile.coordinate),open:v.profile.open};
 return out;
}
/** A saved view back in the page's micrometres; each coordinate is checked against the window in SI. */
function readView(view){
 if(!view||typeof view!=='object')throw new Error('Unsupported saved field view.');
 const out={mode:view.mode,component:view.component,window:view.window};
 if(view.probe!==undefined){const p=view.probe;let x,y;try{x=parseLength(p?.x);y=parseLength(p?.y);}catch{throw new Error('Invalid saved probe position: write x and y with their unit, such as "0.15 um".');}
  if(!inWindow(x.m,WINDOW_UM.xmax)||!inWindow(y.m,WINDOW_UM.ymax))throw new Error('Invalid saved probe position.');out.probe={x:x.um,y:y.um,active:p.active};}
 if(view.profile!==undefined){const p=view.profile;let c;try{c=parseLength(p?.coordinate);}catch{throw new Error('Invalid saved profile line: write its coordinate with its unit, such as "0.15 um".');}
  if(!inWindow(c.m,p?.axis==='x'?WINDOW_UM.ymax:WINDOW_UM.xmax))throw new Error('Invalid saved profile line.');out.profile={axis:p.axis,coordinate:c.um,open:p.open};}
 return validateView(out);
}
/** The version a session of these runs is written as: 13 when it has more than six runs; 12 when a
 * run's number is not its place in the list; else 11 when a run is a closed-window search run; else 10 when a run has an open boundary or the
 * input chooses Open (version 9); else 7 when every run fits version 7 (and every field is kept)
 * and the input is of version 6 or 7, else 9 (an input of version 8, with study settings, is
 * held by version 9 only). */
export function sessionVersion(runs,view={mode:0},keep=null,input=null){
 // version 14 only when a run is written with a compact field
 if(runs.some(run=>isCompactField(run.field)&&(!keep||keep.has(run.job))))return COMPACT_SESSION_VERSION;
 // version 13 only above six runs: a session of six or fewer is written as before
 if(runs.length>PREVIOUS_RUN_LIMIT)return RUNS_SESSION_VERSION;
 // version 12 when a run's number is not its place in the list; a run without one is at its place
 if(runs.some((run,i)=>runNumberAt(run,i)!==i+1))return NUMBERED_SESSION_VERSION;
 if(runs.some(isClosedTargetRun))return CLOSED_TARGET_SESSION_VERSION;
 if(input?.version===OPEN_PROJECT_VERSION||runs.some(isOpenRun))return OPEN_SESSION_VERSION;
 if(input?.version===STUDY_PROJECT_VERSION)return OPTICAL_SESSION_VERSION;
 return runs.every(run=>fitsVersion7(run)&&(!keep||keep.has(run.job)))&&validateView(view).mode<2?SESSION_VERSION:OPTICAL_SESSION_VERSION;
}
/** The session object: version 7 (unchanged) or 9 by sessionVersion. keep: the jobs whose fields
 * are written (null: every run's). */
export function createSession(input,runs,selected,comparison,view={mode:0,component:'magnitude',window:'Core region'},{keep=null}={}){
 const checked=validateProject(input),version=sessionVersion(runs,view,keep,checked);
 if(version===SESSION_VERSION)return {format:'openphysics-studio-session',version,input:checked,runs:runs.map(run=>sessionRun(run)),selected,comparison:[...comparison],view:sessionView(view)};
 // what a version 9 reader refuses is not written: a run read from an earlier file whose indices
 // are not ranked above the threshold, or a view of a mode the selected run does not have
 runs.forEach((run,i)=>{const e=run.effective_index,re=Array.isArray(e)?e:e?.re??[];if(re.some((x,j)=>!(x>GUIDED_THRESHOLD)||(j>0&&x>re[j-1])))throw new Error(`Run ${i+1}: its effective indices are not ranked by Re n_eff above n = ${GUIDED_THRESHOLD}, so a version 9 session cannot hold it${checked.version===STUDY_PROJECT_VERSION&&sessionVersion(runs,view,keep)===SESSION_VERSION?' (the current Modes to find or group index option is saved in version 9 only; set 2 modes and the option off to save as version 7)':''}. Remove the run or save it in a session of its own.`);});
 const shown=runs.find(run=>run.job===selected);if(shown&&validateView(view).mode>=shown.effective_index.length)throw new Error('Unsupported saved field view.');
 // versions 12 and 13: the numbers a version 12 reader refuses are not written (strictly increasing safe integers)
 const numbers=runs.map(runNumberAt);
 if(numbered(version)&&numbers.some((n,i)=>!isRunNumber(n)||(i>0&&n<=numbers[i-1])))throw new Error('Run numbers must be whole numbers of at least 1, increasing in list order.');
 return {format:'openphysics-studio-session',version,application:'optical',input:checked,runs:runs.map((run,i)=>sessionRun(run,version,!keep||keep.has(run.job),numbers[i])),selected,comparison:[...comparison],view:sessionView(view)};
}
/** The file text of a session: version 7 as JSON.stringify writes it (as before), version 9 with
 * the number rules of version 8 (workspace-multiphysics-session.mjs: negative zero kept). */
export function sessionText(...args){
 const doc=createSession(...args);
 return doc.version===SESSION_VERSION?JSON.stringify(doc):sessionJson(doc);
}
/** The jobs whose fields a file over the limit keeps: the selected and the pinned runs. */
export const keptRuns=(runs,selected)=>new Set(runs.filter(run=>run.pinned||run.job===selected).map(run=>run.job));
/** Save session: {ok, text, bytes, notKept} when it fits (keepSelected: with the fields of the
 * selected and pinned runs only); else {ok: false, bytes, reduced: {bytes, notKept} or null,
 * refusal}. notKept: the numbers of the runs written without fields. */
// fill (browser recovery, round 23 E2 decision): with keepSelected, once the selected and pinned
// runs' fields fit, the fields of the other runs are added newest first (the largest run number
// first) while the text stays within the limit; a field that does not fit is left out and the next
// older one tried. The record format is unchanged: a run written without its field is as before.
export function writeOpticalSession(input,runs,selected,comparison,view,{keepSelected=false,limit=MAX_SESSION_BYTES,fill=false}={}){
 const size=text=>new TextEncoder().encode(text).length;
 const fullText=sessionText(input,runs,selected,comparison,view),full=size(fullText);
 // a run's number in this tab (round 17, U2), else its place in the list
 const number=(run,i)=>Number.isInteger(run.number)?run.number:i+1;
 const without=keep=>runs.map((run,i)=>!keep.has(run.job)||!run.field?number(run,i):0).filter(Boolean);
 if(full<=limit)return {ok:true,text:fullText,bytes:full,notKept:without(new Set(runs.filter(r=>r.field).map(r=>r.job)))};
 const keep=keptRuns(runs,selected),reducedText=sessionText(input,runs,selected,comparison,view,{keep}),reduced=size(reducedText),notKept=without(keep);
 // round 23 (E2): kept, the numbers of the runs written with their fields
 const kept=runs.map((run,i)=>keep.has(run.job)&&run.field?number(run,i):0).filter(Boolean);
 if(reduced<=limit&&keepSelected&&fill){
  let chosen=new Set(keep),text=reducedText,bytes=reduced;
  const others=runs.map((run,i)=>({run,n:number(run,i)})).filter(({run})=>run.field&&!keep.has(run.job)).sort((a,b)=>b.n-a.n);
  for(const {run} of others){const trial=new Set([...chosen,run.job]),t=sessionText(input,runs,selected,comparison,view,{keep:trial}),b=size(t);if(b<=limit){chosen=trial;text=t;bytes=b;}}
  return {ok:true,text,bytes,notKept:without(chosen),kept:runs.map((run,i)=>chosen.has(run.job)&&run.field?number(run,i):0).filter(Boolean),reduced:true};
 }
 if(reduced<=limit)return keepSelected?{ok:true,text:reducedText,bytes:reduced,notKept,kept,reduced:true}:{ok:false,bytes:full,reduced:{bytes:reduced,notKept,kept},refusal:null};
 return {ok:false,bytes:full,reduced:null,refusal:keptOverText(runs.map((run,i)=>({name:'Run '+number(run,i),selected:run.job===selected,pinned:!!run.pinned})).filter((_,i)=>keep.has(runs[i].job)),reduced)};
}
/** The refusal of a session whose selected and pinned runs are over the limit with their fields
 * (A3): the selected run and the pinned runs named apart, a pinned selected run among the pinned
 * ones. "Unpin" only when a pinned run is among them; a selected run alone is saved without its
 * fields once another run is selected. kept: [{name, selected, pinned}], in the runs' order. Its
 * first letter is lowered after the recovery error's "Recovery snapshot exceeds 16 MiB: ". */
export function keptOverText(kept,bytes){
 const pinned=kept.filter(r=>r.pinned),chosen=kept.find(r=>r.selected&&!r.pinned),list=rs=>rs.map(r=>r.name+(r.selected?' selected':'')).join(', ');
 const size=`${megabytes(bytes)} with ${kept.length>1?'their':'its'} fields, over the ${LIMIT_WORDS} session limit.`;
 if(!pinned.length)return `The selected run (${chosen?.name??'none'}) is ${size} Select a different run before saving, so this one is saved without its fields, or run it again with fewer modes.`;
 const parts=[...(chosen?[`the selected run (${chosen.name})`]:[]),`the pinned run${pinned.length>1?'s':''} (${list(pinned)})`].join(' and ');
 return `${parts[0].toUpperCase()+parts.slice(1)} ${kept.length>1?'are':'is'} ${size} ${pinned.length>1?'Unpin some of them.':'Unpin it.'}`;
}
/** S2: the Messages line when a new run makes the session go over the limit, from
 * writeOpticalSession's answer (null when it fits): the size and what File › Save will do. When
 * even the selected and pinned runs are over the limit, Save refuses with keptOverText's words and
 * browser recovery is off too, so the line says both (round 18 X4's line is then not posted).
 * Round 23 (E2) named the runs whose fields Save offers to keep and the runs whose fields browser
 * recovery leaves out (recoveryLeftOut: captureSession's make.dropped; it keeps the selected and
 * pinned fields and as many others as fit, newest first). Round 24 (B3, coordinator decision on the
 * round-24 findings): one unit, MB to one decimal (the limit, 16 MiB, is 16.8 MB), what is already
 * lost first, in plain words:
 *   "Session is now 17.0 MB, over the 16.8 MB limit. Browser recovery keeps every run's values; the
 *   field plots of Run 6 are not kept. File › Save will ask whether to keep the field plots of the
 *   selected and pinned runs only (Runs 1, 2 and 9)." */
export const LIMIT_WORDS='16.8 MB';
/** A size in MB to one decimal ("17.0 MB"); two decimals for a size over the limit that would read
 * as the limit itself ("16.79 MB", not "16.8 MB"). */
export function megabytes(bytes){
 const one=(bytes/1e6).toFixed(1);
 return `${bytes>MAX_SESSION_BYTES&&one===(MAX_SESSION_BYTES/1e6).toFixed(1)?(bytes/1e6).toFixed(2):one} MB`;
}
/** "Run 3 and Run 5", "Run 1, Run 2 and Run 4": runs named one by one (round 23, E2). */
export const runNames=numbers=>{const w=numbers.map(n=>'Run '+n);return w.length<3?w.join(' and '):w.slice(0,-1).join(', ')+' and '+w.at(-1);};
/** The restore's sentence when runs came back without fields (round 23, E2): " Fields not kept for
 * Run 1 and Run 2; their n_eff, TE fractions and effective areas were." or ''. */
export const fieldsNotKeptText=runs=>{const n=runs.filter(r=>!r.field&&Number.isInteger(r.number)).map(r=>r.number);return n.length?` Fields not kept for ${runNames(n)}; their n_eff, TE fractions and effective areas were.`:'';};
const runsWords=numbers=>{const w=numbers.map(String);return (numbers.length>1?'Runs ':'Run ')+(w.length<3?w.join(' and '):w.slice(0,-1).join(', ')+' and '+w.at(-1));};
export function sessionSizeText(out,recoveryLeftOut=null){
 if(!out||out.ok)return null;
 const over=`Session is now ${megabytes(out.bytes)}, over the ${LIMIT_WORDS} limit`;
 if(out.reduced){const kept=out.reduced.kept?.length?` (${runsWords(out.reduced.kept)})`:'';
  const left=recoveryLeftOut,browser=!Array.isArray(left)?'':left.length?` Browser recovery keeps every run's values; the field plots of ${runNames(left)} are not kept.`:" Browser recovery keeps every run's values and field plots.";
  return `${over}.${browser} File › Save will ask whether to keep the field plots of the selected and pinned runs only${kept}.`;}
 return `${over}, and File › Save will refuse: ${out.refusal} Browser recovery is off.`;
}
export function opticalOverflowQuestion(bytes){return `Session is ${sizeText(bytes)}; the limit is 16 MiB. Keep the fields of the selected and pinned runs only? The other runs keep n_eff, the TE fractions and the effective areas, but not their fields.`;}
// Capture editable metadata now; serialize large, read-only field arrays after debounce.
// UI operations replace results rather than modifying their field samples in place.
// Browser recovery keeps the file text, or the fields of the selected and pinned runs only when
// the file is over the limit (no dialog), as version 8 recovery does. Round 23 (E2): then the fields
// of the other runs too, newest first, as many as fit (writeOpticalSession's fill); make.dropped is
// the numbers of the runs whose fields this tab has and the snapshot left out ([] otherwise), so the
// header names them (it read "kept for recovery in this browser" alone while 5 runs' fields, about
// 17 MB, were left out of a 22 MB session). limit: the session limit (a test sets a smaller one).
export function captureSession(input,runs,selected,comparison,view,{limit=MAX_SESSION_BYTES}={}){
 const capturedInput=validateProject(input),capturedView=validateView(view);
 const capturedRuns=runs.map(run=>{const copy={...run,input:validateProject(run.input),
  settings:JSON.parse(JSON.stringify(run.settings)),effective_index:[...run.effective_index]};
  // the values the run shows, so a run written without its field keeps them
  for(const key of ['te','area'])if(run[key])Object.defineProperty(copy,key,{value:run[key],enumerable:false,configurable:true,writable:true});
  return copy;});
 const capturedComparison=[...comparison];
 // When the study settings of the input (version 8) need version 9 but a run cannot be held by it
 // (read from a version 6 or 7 file), recovery keeps the notebook as version 7 without those
 // settings, and the snapshot's note says what was not kept; Save session still refuses.
 const write=input=>writeOpticalSession(input,capturedRuns,selected,capturedComparison,capturedView,{keepSelected:true,limit,fill:true});
 const make=()=>{make.note='';make.dropped=[];let out;
  try{out=write(capturedInput);}catch(error){
   if(![STUDY_PROJECT_VERSION,OPEN_PROJECT_VERSION].includes(capturedInput.version))throw error;
   let plain;try{plain=write(withoutStudy(capturedInput));}catch{throw error;}
   out=plain;make.note=recoveryStudyNote(capturedInput);}
  // the code says why the header reads unavailable (round 17, U6: it read a bare "browser recovery unavailable")
  // the same words as Save session's refusal (A3), after what failed
  if(out.reduced===true){const had=new Set(capturedRuns.map((r,i)=>r.field?(Number.isInteger(r.number)?r.number:i+1):0).filter(Boolean));make.dropped=out.notKept.filter(n=>had.has(n));}
  if(!out.ok)throw Object.assign(new Error('Recovery snapshot exceeds 16 MiB: '+out.refusal[0].toLowerCase()+out.refusal.slice(1)),{code:'recovery-over-limit'});return out.text;};
 make.note='';make.dropped=[];return make;
}
/** The note of a recovery kept without the study settings of these inputs (version 8). */
export function recoveryStudyNote(input){
 const {modeCount,groupIndex}=projectStudy(input),openBoundary=projectBoundary(input),parts=[...(modeCount===2?[]:[`Modes to find ${modeCount}`]),...(groupIndex?['the group index option']:[]),...(openBoundary?['the outer boundary choice']:[])];
 return `Browser recovery kept this notebook without ${parts.join(' and ')}: a run read from an earlier file cannot be saved with ${parts.length>1?'them':'it'}. Set 2 modes and the option off, or remove that run, to keep them.`;
}
/** The refusal of a session file newer than a Studio reads (versions 6 to highest). */
export const newerVersionText=(version,highest)=>`This session file is version ${version}, newer than this Studio reads (versions 6–${highest}). Open it in a newer Studio.`;
const TOP_KEYS_9=['format','version','application','input','runs','selected','comparison','view'];
/** The optical session versions parseSession reads (6, 7 and 9): a project file's workspace entry
 * accepts these, so a later version is added here only (workspace-project-file.mjs). */
export const OPTICAL_SESSION_VERSIONS=Object.freeze([6,SESSION_VERSION,OPTICAL_SESSION_VERSION,OPEN_SESSION_VERSION,CLOSED_TARGET_SESSION_VERSION,NUMBERED_SESSION_VERSION,RUNS_SESSION_VERSION,COMPACT_SESSION_VERSION]);
/** The most runs a session file of this version holds: 20 in versions 13 and 14, six in versions 6 to 12. */
export const sessionRunLimit=version=>version===RUNS_SESSION_VERSION||version===COMPACT_SESSION_VERSION?RUN_LIMIT:PREVIOUS_RUN_LIMIT;

// Versions 6 and 7 are optical sessions, read as before; version 8 is a multiphysics model with
// its runs (workspace-multiphysics-session.mjs), whose result has application: 'multiphysics';
// version 9 is an optical session with application: 'optical'; versions 10 to 14 are optical and
// version 15 is a multiphysics model of more than six runs (run retention of the heated model).
/** The highest session version this Studio reads: 15, RUNS_MULTIPHYSICS_VERSION (the heated model's
 * run retention), written here as a number since the two modules import each other. */
export const HIGHEST_SESSION_VERSION=15;
export function parseSession(text,{recovered=false}={}){
 if(new TextEncoder().encode(text).length>MAX_SESSION_BYTES)throw new Error('Session exceeds 16 MiB.');
 let doc;try{doc=JSON.parse(text);}catch{
  // a leading byte order mark is removed for version 8 files only: optical files read as before
  try{doc=text.startsWith('\uFEFF')?JSON.parse(text.slice(1)):undefined;}catch{}
  if(doc?.format!=='openphysics-studio-session'||!MULTIPHYSICS_VERSIONS.includes(doc.version))throw new Error('Session is not valid JSON.');}
 if(doc?.format==='openphysics-studio-session'&&[1,2,3,4,5].includes(doc.version))throw new Error(`This session (version ${doc.version}) was saved before the units and naming batch; its results are not read. Re-run the design and save a new session.`);
 if(doc?.format==='openphysics-studio-session'&&Number.isInteger(doc.version)&&doc.version>HIGHEST_SESSION_VERSION)throw new Error(newerVersionText(doc.version,HIGHEST_SESSION_VERSION));
 if(doc?.format==='openphysics-studio-session'&&MULTIPHYSICS_VERSIONS.includes(doc.version))return readMultiphysicsSession(doc,{recovered});
 const twelve=doc?.version===NUMBERED_SESSION_VERSION||doc?.version===RUNS_SESSION_VERSION||doc?.version===COMPACT_SESSION_VERSION,eleven=doc?.version===CLOSED_TARGET_SESSION_VERSION||twelve,ten=doc?.version===OPEN_SESSION_VERSION||eleven,nine=doc?.version===OPTICAL_SESSION_VERSION||ten;
 if(doc?.format!=='openphysics-studio-session'||!OPTICAL_SESSION_VERSIONS.includes(doc.version)||!Array.isArray(doc.runs)||doc.runs.length>sessionRunLimit(doc.version))throw new Error('Unsupported session format or run count.');
 if(nine){
  const unknown=Object.keys(doc).find(k=>!TOP_KEYS_9.includes(k));if(unknown!==undefined)throw new Error(`Unknown key ${JSON.stringify(unknown)} in the session file.`);
  if(doc.application!=='optical')throw new Error(`A version ${doc.version} session file holds an optical model (application "optical").`);
  const missing=TOP_KEYS_9.find(k=>!Object.hasOwn(doc,k));if(missing!==undefined)throw new Error(`The session file has no ${JSON.stringify(missing)}.`);
 }
 if(doc.input?.units?.width!=='nm'||doc.input?.units?.temperature!=='K'||doc.input?.units?.voltage!=='V')throw new Error('Invalid session input units.');
 // the input of a version 6 or 7 session is an input file of version 6 or 7; version 9 also
 // holds one of version 8 (with study settings)
 // holds one of version 8 (with study settings), and version 10 one of version 9 (outer boundary)
 if(!nine&&[STUDY_PROJECT_VERSION,OPEN_PROJECT_VERSION].includes(doc.input?.version))throw new Error(`A version ${doc.version} session holds an input file of version 6 or 7.`);
 if(nine&&!ten&&doc.input?.version===OPEN_PROJECT_VERSION)throw new Error('A version 9 session holds an input file of version 6 to 8.');
 // version 12: each run's number, checked before the runs (by position): present, a safe integer of
 // at least 1, used once and strictly increasing in list order; an earlier file numbers from 1
 const numbers=doc.runs.map((r,i)=>i+1);
 if(twelve){
  doc.runs.forEach((r,i)=>{
   if(!isObject(r))throw new Error(`Run ${i+1} is not a run record.`);
   if(!Object.hasOwn(r,'number'))throw new Error(`Run ${i+1}: missing number.`);
   if(!isRunNumber(r.number))throw new Error(`Run ${i+1}: invalid run number.`);
   numbers[i]=r.number;
  });
  const twice=numbers.find((n,i)=>numbers.indexOf(n)!==i);if(twice!==undefined)throw new Error(`Two runs have the same number ${twice}.`);
  const back=numbers.findIndex((n,i)=>i>0&&n<=numbers[i-1]);if(back>0)throw new Error(`Run ${back+1} is numbered ${numbers[back]}, not after Run ${back}'s ${numbers[back-1]}.`);
 }
 const input=validateProject(doc.input),runs=doc.runs.map((r,i)=>{
  let record=r;
  if(nine){
   if(!isObject(r))throw new Error(`Run ${i+1} is not a run record.`);
   const unknown=Object.keys(r).find(k=>!(twelve?RUN_KEYS_12:ten?RUN_KEYS_10:RUN_KEYS_9).includes(k));if(unknown!==undefined)throw new Error(`Run ${i+1}: unknown key ${JSON.stringify(unknown)}.`);
   for(const key of ['label','pinned','origin','serverVersion','settings','input','effective_index','digest'])if(!Object.hasOwn(r,key))throw new Error(`Run ${i+1}: missing ${key}.`);
   if(typeof r.label!=='string'||typeof r.pinned!=='boolean'||!['local','imported','recovered'].includes(r.origin))throw new Error(`Run ${i+1}: invalid name, pin state or origin.`);
   if(typeof r.digest!=='string'||r.digest!==recordDigest(r))throw new Error(`Run ${i+1} changed after it was saved (its check value does not match).`);
  }else{
   // a version 6 or 7 run: its keys of version 7 only (any other key is not read, as before)
   record={job:r?.job,completedAt:r?.completedAt,label:r?.label,pinned:r?.pinned,origin:r?.origin,serverVersion:r?.serverVersion,settings:r?.settings,input:r?.input,effective_index:r?.effective_index,field:r?.field};
  }
  const run=validateRun(record,true,{format:eleven?11:ten?10:nine?9:7,number:numbers[i],compact:doc.version===COMPACT_SESSION_VERSION});if(recovered)run.origin='recovered';Object.defineProperty(run,'number',{value:numbers[i],writable:true,configurable:true,enumerable:false});return run;}),ids=runs.map(r=>r.job);
 if(new Set(ids).size!==ids.length)throw new Error('Duplicate run identifiers.');
 if(doc.selected!==null&&!ids.includes(doc.selected))throw new Error('Selected run is missing.');
 if(!Array.isArray(doc.comparison)||doc.comparison.length!==2||!doc.comparison.every(id=>id===null||ids.includes(id)))throw new Error('Invalid comparison selection.');
 // each run carries its number (stored in version 12, else its place) as a property that is not
 // enumerated: the parsed run records are those of earlier Studios, and a copy ({...run}) is a run
 // without a number; the page keeps the number on its own runs (completeLoad)
 const view=readView(doc.view||{mode:0,component:'magnitude',window:'Core region'});
 // a version 6 or 7 view shows mode 1 or 2; a version 9 view one of the selected run's modes
 const shown=doc.selected===null?MODE_COUNT_RANGE[1]:runs.find(r=>r.job===doc.selected).effective_index.length;
 if(view.mode>=(nine?shown:2))throw new Error('Unsupported saved field view.');
 return {input,runs,selected:doc.selected,comparison:[...doc.comparison],view};
}


/** Add runs from file: the runs with the incoming ones added; above the limit (RUN_LIMIT unless given)
 * the oldest unpinned runs not among the incoming ones are dropped (evicted). */
export function mergeRuns(existing,incoming,limit=RUN_LIMIT){
 if(!incoming.length)throw new Error('The session contains no completed runs.');
 const result=[...existing],incomingIds=new Set(),added=[],reused=[];
 const identity=run=>JSON.stringify({input:run.input,settings:{...run.settings,adapter:OPTICAL_ADAPTER},effective_index:run.effective_index,effective_index_im:run.effective_index_im??null,serverVersion:run.serverVersion??null});
 // the fields are compared when both runs have them: a file may have left them out (over 16 MiB)
 const fields=run=>JSON.stringify({node_coordinates:run.field.node_coordinates,triangles:run.field.triangles,real:run.field.real,imag:run.field.imag});
 // two open runs with valid physical bounds compare their samples on the window (C3): a file written
 // before the crop holds the full samples of a job whose new copy holds the window's only
 const windowed=run=>{const b=isOpenRun(run)?physicalBounds(run.open_boundary):null;return b?JSON.stringify(windowField(run.field,b)):null;};
 // a compact field (version 14) is compared by its strings: the other run's field encoded as the tab
 // would encode it (an open run's on its window)
 const encoded=run=>{const c=compactRecord(run.field);if(c)return JSON.stringify([c.node_coordinates,c.triangles,c.real,c.imag]);
  const b=isOpenRun(run)?physicalBounds(run.open_boundary):null;
  try{const e=encodeField(b?windowField(run.field,b):run.field);return JSON.stringify([e.node_coordinates,e.triangles,e.real,e.imag]);}catch{return null;}};
 const sameFields=(a,b)=>{
  if(isCompactField(a.field)||isCompactField(b.field)){const ea=encoded(a);return ea!==null&&ea===encoded(b);}
  const wa=windowed(a),wb=wa===null?null:windowed(b);return wa!==null&&wb!==null?wa===wb:fields(a)===fields(b);};
 const same=(a,b)=>identity(a)===identity(b)&&(!a.field||!b.field||sameFields(a,b));
 for(const raw of incoming){
  const run=validateRun(raw,true);if(incomingIds.has(run.job))throw new Error('Duplicate imported run identifier.');incomingIds.add(run.job);
  const prior=existing.find(r=>r.job===run.job);
  if(prior){if(!same(prior,run))throw new Error('Conflicting result for job '+run.job+'. Existing notebook kept.');reused.push(run.job);}
  else{result.push(run);added.push(run.job);}
 }
 const evicted=[];
 while(result.length>limit){const index=result.findIndex(run=>!run.pinned&&!incomingIds.has(run.job));if(index<0)throw new Error(`Imported runs and pinned references exceed ${limit} slots. Unpin a reference or import a selected-run file.`);evicted.push(result[index].job);result.splice(index,1);}
 return {runs:result,added,reused,evicted};
}
