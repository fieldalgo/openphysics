// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

import {validateProject,withoutStudy,projectStudy,projectBoundary,STUDY_PROJECT_VERSION,OPEN_PROJECT_VERSION} from './workspace-project.mjs';
import {OPEN_ADAPTER,isOpenRun,checkOpenSettings,checkCandidateRecord,checkPmlCheck,modeCandidates} from './workspace-open-run.mjs';
import {readOpticalField,fieldScalars,FIELD_METADATA,PML_FIELD_METADATA} from './workspace-field.mjs';
import {shapesBlock,shapeText} from './workspace-shapes.mjs';
import {opticalModes} from './workspace-modes.mjs';
import {MULTIPHYSICS_VERSION,readMultiphysicsSession,sessionJson,recordDigest,sizeText} from './workspace-multiphysics-session.mjs';
export const MAX_SESSION_BYTES=16*1024*1024;
export const RUN_LIMIT=6;
// The run limit in words, from RUN_LIMIT itself, so the run list's note and the model tree's
// "Runs · N of M" never disagree (round 14).
const NUMBER_WORDS=Object.freeze(['zero','one','two','three','four','five','six','seven','eight','nine','ten','eleven','twelve']);
export const RUNS_KEPT_TEXT=`Up to ${NUMBER_WORDS[RUN_LIMIT]} runs are kept.`;
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
/** The settings a version 7 file writes for a run of two modes: those of optical-shapes-v7. */
export function v7Settings(settings){return {...settings,adapter:V7_ADAPTER,mode_count:2};}
// Runs of earlier adapters came in sessions of versions 1-5, which are refused by name.
function expectedSettings(settings,model,number){
 const adapter=settings?.adapter;
 if(adapter===V7_ADAPTER){studyRange(model.wavelength,model.coreMesh);return v7Settings(opticalSettings(model.wavelength,model.coreMesh));}
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
export const studySignature=(input,modeCount=DEFAULT_MODE_COUNT,groupIndex=false,pml=null)=>JSON.stringify(input)+(modeCount===DEFAULT_MODE_COUNT?'':`\n${modeCount} modes`)+(groupIndex===true?'\ngroup index':'')+(pml?`\nopen boundary ${pml.open_edges.join(' ')} near ${pml.target}`:'');
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
// or the mode has no value).
export function runTableCsv(runs){
 const rows=[['job','name','pinned','completed_at','core_width [m]','core_height [m]','vacuum_wavelength [m]','core_element_size [m]','core_material','shapes','candidate','effective_index [1]','origin','effective_index_imag [1]','group_index [1]']];
 for(const r of runs){const shapes=r.input.model.shapes,single=shapes.length===1&&shapes[0].type==='rect'?shapes[0]:null;
  const e=r.effective_index,re=Array.isArray(e)?e:e.re,im=Array.isArray(e)?(Array.isArray(r.effective_index_im)?r.effective_index_im:null):e.im,ng=Array.isArray(r.group_index)?r.group_index:null;
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
export function validateRun(record,imported=false,{format=null,number=null}={}){
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
 if(format===9||format===10){
  if(re.some((x,i)=>i>0&&x>re[i-1]))throw new Error(`${which}: its effective indices are not ranked by Re n_eff.`);
  if(re.some(x=>!(x>GUIDED_THRESHOLD)))throw new Error(`${which}: an effective index is not above n = ${GUIDED_THRESHOLD}.`);
 }
 // the engine's values per mode (version 9 and this tab); a version 7 file holds none
 const extra={};
 if(format!==7){
  for(const [key,ok,text] of [['te_polarization_fraction',x=>x>=0&&x<=1,'TE fractions'],['effective_area',x=>x>0,'effective areas'],['group_index',()=>true,'group indices']]){
   if(record[key]===undefined)continue;
   if(!valueList(record[key],k,ok))throw new Error(`${which}: invalid saved ${text}.`);
   extra[key]=[...record[key]];
  }
  if(record.group_index_method!==undefined){
   if(extra.group_index===undefined||typeof record.group_index_method!=='string'||!METHOD.test(record.group_index_method))throw new Error(`${which}: invalid group index method.`);
   extra.group_index_method=record.group_index_method;
  }
 }
 // an open run: the engine's candidate record (each mode one of its selected candidates), no
 // group index, and the PML check when it ran; a closed run has neither
 if(settings.adapter===OPEN_ADAPTER){
  if(extra.group_index!==undefined)throw new Error(`${which}: a run with an open boundary has no group index.`);
  if(im===null)throw new Error(`${which}: a run with an open boundary has complex effective indices.`);
  const ob=checkCandidateRecord(record.open_boundary,which);
  if(modeCandidates(ob,re,im).some(c=>c===null))throw new Error(`${which}: its modes are not the selected candidates of its open boundary record.`);
  extra.open_boundary=ob;
  if(record.pml_check!==undefined)extra.pml_check=checkPmlCheck(record.pml_check,k,which);
 }else if(record.open_boundary!==undefined||record.pml_check!==undefined)throw new Error(`${which}: a closed window has no open boundary record.`);
 const f=record.field;let field=null;
 if(f==null){
  // only a version 9 file leaves fields out (absent there; null on a run read from one)
  if(format===7||settings.adapter===V7_ADAPTER||(format===null&&f===undefined))throw new Error('Missing run fields.');
  if(extra.te_polarization_fraction===undefined||extra.effective_area===undefined)throw new Error(`${which} has no fields and no saved TE fractions and effective areas.`);
 }else{
  field=readOpticalField({node_coordinates:f.node_coordinates,field_units:{node_coordinates:'m'},triangles:f.triangles,vector_fields:[{...(settings.adapter===OPEN_ADAPTER?PML_FIELD_METADATA:FIELD_METADATA),real:f.real,imag:f.imag}]},format===7?2:k,{open:settings.adapter===OPEN_ADAPTER});
  for(let mode=0;mode<k;mode++)fieldScalars(field,mode);
 }
 const run={pinned:record.pinned===true,label:validateRunLabel(record.label),serverVersion:record.serverVersion??null,job:record.job,completedAt:new Date(record.completedAt).toISOString(),settings:JSON.parse(JSON.stringify(settings)),input,signature:studySignature(input,asked,extra.group_index_method!==undefined,settings.pml??null),effective_index:[...re],field,origin:imported?'imported':['imported','recovered'].includes(record.origin)?record.origin:'local'};
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
 * "central_difference <step> <tracker>"}, or {} when the summary has none. */
export function engineGroupIndex(summary,k){
 const g=summary?.group_index,m=summary?.group_index_method;
 if(!m||m.method!=='central_difference'||g?.unit!=='1'||!valueList(g.values?.[0],k,()=>true))return {};
 const step=m.wavelength_step;
 if(step?.unit!=='m'||!(step.value>0)||typeof m.tracking!=='string'||!/^[a-z0-9-]{1,40}$/.test(m.tracking))return {};
 const method=`central_difference ${+(step.value*1e9).toPrecision(6)} nm ${m.tracking}`;
 return METHOD.test(method)?{group_index:[...g.values[0]],group_index_method:method}:{};
}
/** The engine's reason of each null group index of a new result (summary.group_index_method.reasons):
 * k strings or null, or null. Kept on the run in this tab only: a session file does not hold them. */
export function engineGroupIndexReasons(summary,k){
 const r=summary?.group_index_method?.reasons;
 return Array.isArray(r)&&r.length===k&&r.every(x=>x===null||typeof x==='string')?[...r]:null;
}
const RUN_KEYS_9=['job','completedAt','label','pinned','origin','serverVersion','settings','input','effective_index','field','te_polarization_fraction','effective_area','group_index','group_index_method','digest'];
const RUN_KEYS_10=[...RUN_KEYS_9.slice(0,-1),'open_boundary','pml_check','digest'];
/** Whether a version 7 file holds a run: two real modes with their fields and nothing else. */
export const fitsVersion7=run=>run.settings.adapter===V7_ADAPTER||(run.settings.mode_count===2&&run.effective_index.length===2&&!run.effective_index_im&&run.field!==null&&run.group_index===undefined);
/** The record a file writes of a run. version 7: as before mode counts (the settings of
 * optical-shapes-v7, no engine values). version 9: every key in RUN_KEYS_9 order, the fields
 * left out when keepField is false (the TE fractions and areas the run shows are then written),
 * and the digest of the record. */
function sessionRun(run,version=SESSION_VERSION,keepField=true){
 const {signature,field,effective_index_im,te_polarization_fraction,effective_area,group_index,group_index_method,open_boundary,pml_check,...record}=validateRun(run);
 const fields=field&&{node_coordinates:field.node_coordinates,triangles:field.triangles,real:field.real,imag:field.imag};
 if(version===SESSION_VERSION)return {...record,settings:v7Settings(record.settings),field:fields};
 const settings=record.settings.adapter===V7_ADAPTER?{...record.settings,adapter:OPTICAL_ADAPTER}:record.settings;
 const out={job:record.job,completedAt:record.completedAt,label:record.label,pinned:record.pinned,origin:record.origin,serverVersion:record.serverVersion,settings,input:record.input,
  effective_index:effective_index_im?{re:record.effective_index,im:effective_index_im}:record.effective_index};
 const shown=keepField&&fields?null:modeValues(run);
 if(keepField&&fields)out.field=fields;
 if(te_polarization_fraction||shown)out.te_polarization_fraction=shown?shown.te:te_polarization_fraction;
 if(effective_area||shown)out.effective_area=shown?shown.area:effective_area;
 if(group_index)out.group_index=group_index;
 if(group_index_method!==undefined)out.group_index_method=group_index_method;
 if(open_boundary)out.open_boundary=open_boundary;
 if(pml_check)out.pml_check=pml_check;
 return {...out,digest:recordDigest(out)};
}
// The TE fractions and effective areas a run shows (opticalModes keeps them on the run).
const modeValues=run=>{const modes=opticalModes(run);return {te:modes.map(m=>m.fte),area:modes.map(m=>m.area)};};
export function appendRun(runs,run){
 const previous=runs.find(r=>r.job===run.job);
 const next=[...runs.filter(r=>r.job!==run.job),previous?{...run,label:previous.label||run.label,pinned:previous.pinned||run.pinned}:run];
 while(next.length>RUN_LIMIT){const oldest=next.findIndex(r=>!r.pinned&&r.job!==run.job);if(oldest<0)throw new Error('All notebook slots are pinned. Unpin a run before retaining another result.');next.splice(oldest,1);}
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
/** The version a session of these runs is written as: 10 when a run has an open boundary or the
 * input chooses Open (version 9); else 7 when every run fits version 7 (and every field is kept)
 * and the input is of version 6 or 7, else 9 (an input of version 8, with study settings, is
 * held by version 9 only). */
export function sessionVersion(runs,view={mode:0},keep=null,input=null){
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
 return {format:'openphysics-studio-session',version,application:'optical',input:checked,runs:runs.map(run=>sessionRun(run,version,!keep||keep.has(run.job))),selected,comparison:[...comparison],view:sessionView(view)};
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
export function writeOpticalSession(input,runs,selected,comparison,view,{keepSelected=false,limit=MAX_SESSION_BYTES}={}){
 const size=text=>new TextEncoder().encode(text).length;
 const fullText=sessionText(input,runs,selected,comparison,view),full=size(fullText);
 const without=keep=>runs.map((run,i)=>!keep.has(run.job)||!run.field?i+1:0).filter(Boolean);
 if(full<=limit)return {ok:true,text:fullText,bytes:full,notKept:without(new Set(runs.filter(r=>r.field).map(r=>r.job)))};
 const keep=keptRuns(runs,selected),reducedText=sessionText(input,runs,selected,comparison,view,{keep}),reduced=size(reducedText),notKept=without(keep);
 if(reduced<=limit)return keepSelected?{ok:true,text:reducedText,bytes:reduced,notKept}:{ok:false,bytes:full,reduced:{bytes:reduced,notKept},refusal:null};
 const kept=runs.map((run,i)=>keep.has(run.job)?'Run '+(i+1):null).filter(Boolean);
 return {ok:false,bytes:full,reduced:null,refusal:`The selected and pinned runs (${kept.join(', ')}) are ${sizeText(reduced)} with their fields, over the 16 MiB session limit. Unpin some of them.`};
}
export function opticalOverflowQuestion(bytes){return `Session is ${sizeText(bytes)}; the limit is 16 MiB. Keep the fields of the selected and pinned runs only? The other runs keep n_eff, the TE fractions and the effective areas, but not their fields.`;}
// Capture editable metadata now; serialize large, read-only field arrays after debounce.
// UI operations replace results rather than modifying their field samples in place.
// Browser recovery keeps the file text, or the fields of the selected and pinned runs only when
// the file is over the limit (no dialog), as version 8 recovery does.
export function captureSession(input,runs,selected,comparison,view){
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
 const write=input=>writeOpticalSession(input,capturedRuns,selected,capturedComparison,capturedView,{keepSelected:true});
 const make=()=>{make.note='';let out;
  try{out=write(capturedInput);}catch(error){
   if(![STUDY_PROJECT_VERSION,OPEN_PROJECT_VERSION].includes(capturedInput.version))throw error;
   let plain;try{plain=write(withoutStudy(capturedInput));}catch{throw error;}
   out=plain;make.note=recoveryStudyNote(capturedInput);}
  if(!out.ok)throw new Error('Recovery snapshot exceeds 16 MiB. Save selected runs to files.');return out.text;};
 make.note='';return make;
}
/** The note of a recovery kept without the study settings of these inputs (version 8). */
export function recoveryStudyNote(input){
 const {modeCount,groupIndex}=projectStudy(input),openBoundary=projectBoundary(input),parts=[...(modeCount===2?[]:[`Modes to find ${modeCount}`]),...(groupIndex?['the group index option']:[]),...(openBoundary?['the outer boundary choice']:[])];
 return `Browser recovery kept this notebook without ${parts.join(' and ')}: a run read from an earlier file cannot be saved with ${parts.length>1?'them':'it'}. Set 2 modes and the option off, or remove that run, to keep them.`;
}
/** The refusal of a session file newer than a Studio reads (versions 6 to highest). */
export const newerVersionText=(version,highest)=>`This session file is version ${version}, newer than this Studio reads (versions 6–${highest}). Open it in a newer Studio.`;
const TOP_KEYS_9=['format','version','application','input','runs','selected','comparison','view'];

// Versions 6 and 7 are optical sessions, read as before; version 8 is a multiphysics model with
// its runs (workspace-multiphysics-session.mjs), whose result has application: 'multiphysics';
// version 9 is an optical session with application: 'optical'.
export function parseSession(text,{recovered=false}={}){
 if(new TextEncoder().encode(text).length>MAX_SESSION_BYTES)throw new Error('Session exceeds 16 MiB.');
 let doc;try{doc=JSON.parse(text);}catch{
  // a leading byte order mark is removed for version 8 files only: optical files read as before
  try{doc=text.startsWith('\uFEFF')?JSON.parse(text.slice(1)):undefined;}catch{}
  if(doc?.format!=='openphysics-studio-session'||doc.version!==MULTIPHYSICS_VERSION)throw new Error('Session is not valid JSON.');}
 if(doc?.format==='openphysics-studio-session'&&[1,2,3,4,5].includes(doc.version))throw new Error(`This session (version ${doc.version}) was saved before the units and naming batch; its results are not read. Re-run the design and save a new session.`);
 if(doc?.format==='openphysics-studio-session'&&Number.isInteger(doc.version)&&doc.version>OPEN_SESSION_VERSION)throw new Error(newerVersionText(doc.version,OPEN_SESSION_VERSION));
 if(doc?.format==='openphysics-studio-session'&&doc.version===MULTIPHYSICS_VERSION)return readMultiphysicsSession(doc,{recovered});
 const nine=doc?.version===OPTICAL_SESSION_VERSION||doc?.version===OPEN_SESSION_VERSION,ten=doc?.version===OPEN_SESSION_VERSION;
 if(doc?.format!=='openphysics-studio-session'||![6,SESSION_VERSION,OPTICAL_SESSION_VERSION,OPEN_SESSION_VERSION].includes(doc.version)||!Array.isArray(doc.runs)||doc.runs.length>RUN_LIMIT)throw new Error('Unsupported session format or run count.');
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
 const input=validateProject(doc.input),runs=doc.runs.map((r,i)=>{
  let record=r;
  if(nine){
   if(!isObject(r))throw new Error(`Run ${i+1} is not a run record.`);
   const unknown=Object.keys(r).find(k=>!(ten?RUN_KEYS_10:RUN_KEYS_9).includes(k));if(unknown!==undefined)throw new Error(`Run ${i+1}: unknown key ${JSON.stringify(unknown)}.`);
   for(const key of ['label','pinned','origin','serverVersion','settings','input','effective_index','digest'])if(!Object.hasOwn(r,key))throw new Error(`Run ${i+1}: missing ${key}.`);
   if(typeof r.label!=='string'||typeof r.pinned!=='boolean'||!['local','imported','recovered'].includes(r.origin))throw new Error(`Run ${i+1}: invalid name, pin state or origin.`);
   if(typeof r.digest!=='string'||r.digest!==recordDigest(r))throw new Error(`Run ${i+1} changed after it was saved (its check value does not match).`);
  }else{
   // a version 6 or 7 run: its keys of version 7 only (any other key is not read, as before)
   record={job:r?.job,completedAt:r?.completedAt,label:r?.label,pinned:r?.pinned,origin:r?.origin,serverVersion:r?.serverVersion,settings:r?.settings,input:r?.input,effective_index:r?.effective_index,field:r?.field};
  }
  const run=validateRun(record,true,{format:ten?10:nine?9:7,number:i+1});if(recovered)run.origin='recovered';return run;}),ids=runs.map(r=>r.job);
 if(new Set(ids).size!==ids.length)throw new Error('Duplicate run identifiers.');
 if(doc.selected!==null&&!ids.includes(doc.selected))throw new Error('Selected run is missing.');
 if(!Array.isArray(doc.comparison)||doc.comparison.length!==2||!doc.comparison.every(id=>id===null||ids.includes(id)))throw new Error('Invalid comparison selection.');
 const view=readView(doc.view||{mode:0,component:'magnitude',window:'Core region'});
 // a version 6 or 7 view shows mode 1 or 2; a version 9 view one of the selected run's modes
 const shown=doc.selected===null?MODE_COUNT_RANGE[1]:runs.find(r=>r.job===doc.selected).effective_index.length;
 if(view.mode>=(nine?shown:2))throw new Error('Unsupported saved field view.');
 return {input,runs,selected:doc.selected,comparison:[...doc.comparison],view};
}


export function mergeRuns(existing,incoming){
 if(!incoming.length)throw new Error('The session contains no completed runs.');
 const result=[...existing],incomingIds=new Set(),added=[],reused=[];
 const identity=run=>JSON.stringify({input:run.input,settings:{...run.settings,adapter:OPTICAL_ADAPTER},effective_index:run.effective_index,effective_index_im:run.effective_index_im??null,serverVersion:run.serverVersion??null});
 // the fields are compared when both runs have them: a file may have left them out (over 16 MiB)
 const fields=run=>JSON.stringify({node_coordinates:run.field.node_coordinates,triangles:run.field.triangles,real:run.field.real,imag:run.field.imag});
 const same=(a,b)=>identity(a)===identity(b)&&(!a.field||!b.field||fields(a)===fields(b));
 for(const raw of incoming){
  const run=validateRun(raw,true);if(incomingIds.has(run.job))throw new Error('Duplicate imported run identifier.');incomingIds.add(run.job);
  const prior=existing.find(r=>r.job===run.job);
  if(prior){if(!same(prior,run))throw new Error('Conflicting result for job '+run.job+'. Existing notebook kept.');reused.push(run.job);}
  else{result.push(run);added.push(run.job);}
 }
 const evicted=[];
 while(result.length>RUN_LIMIT){const index=result.findIndex(run=>!run.pinned&&!incomingIds.has(run.job));if(index<0)throw new Error('Imported runs and pinned references exceed six slots. Unpin a reference or import a selected-run file.');evicted.push(result[index].job);result.splice(index,1);}
 return {runs:result,added,reused,evicted};
}
