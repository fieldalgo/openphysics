// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

import {validateProject} from './workspace-project.mjs';
import {readOpticalField,fieldScalars,FIELD_METADATA} from './workspace-field.mjs';
import {shapesBlock,shapeText} from './workspace-shapes.mjs';
export const MAX_SESSION_BYTES=16*1024*1024;
export const RUN_LIMIT=6;
// Session format 6 (units and naming batch): run records under the section 5.3.4 names
// (effective_index, node_coordinates in m), settings and view coordinates as quantity strings.
export const SESSION_VERSION=6;
export const OPTICAL_ADAPTER='optical-shapes-v7';
export const WINDOW_UM=Object.freeze({xmin:-1.5,xmax:1.5,ymin:-1.2,ymax:1.2});
const um=value=>value+' um';
export const OPTICAL_SETTINGS=Object.freeze({adapter:OPTICAL_ADAPTER,domain:Object.freeze({xmin:um(WINDOW_UM.xmin),xmax:um(WINDOW_UM.xmax),ymin:um(WINDOW_UM.ymin),ymax:um(WINDOW_UM.ymax)}),boundary:'PEC',mode_count:2,solver_version:'not reported'});
export function opticalSettings(wavelength=1550,coreMesh=30){if(!Number.isFinite(wavelength)||wavelength<1400||wavelength>1700||!Number.isFinite(coreMesh)||coreMesh<20||coreMesh>60)throw new Error('Unsupported wavelength or core mesh size.');return {...OPTICAL_SETTINGS,vacuum_wavelength:wavelength+' nm',core_element_size:coreMesh+' nm'};}
// Runs of earlier adapters came in sessions of versions 1-5, which are refused by name.
function expectedSettings(adapter,model){
 if(adapter!==OPTICAL_ADAPTER)throw new Error('Unsupported run settings or input mismatch.');
 return opticalSettings(model.wavelength,model.coreMesh);
}
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
export function csvCell(value){const text=String(value);const safe=typeof value==='string'&&/^\s*[=+@-]/.test(text)?"'"+text:text;return '"'+safe.replaceAll('"','""')+'"';}
export function runTableCsv(runs){
 const rows=[['job','name','pinned','completed_at','core_width_nm','core_height_nm','wavelength_nm','core_mesh_nm','core_material','shapes','candidate','neff','origin']];
 for(const r of runs){const shapes=r.input.model.shapes,single=shapes.length===1&&shapes[0].type==='rect'?shapes[0]:null;
  r.effective_index.forEach((n,i)=>rows.push([r.job,r.label||'',r.pinned===true,r.completedAt,single?single.w:'',single?single.h:'',r.input.model.wavelength,r.input.model.coreMesh,single?single.material:'',shapes.map(shapeText).join(' | '),i+1,n,r.origin]));}
 return rows.map(row=>row.map(csvCell).join(',')).join('\n')+'\n';
}
export function validateRun(record,imported=false){
 if(!record||typeof record.job!=='string'||!/^[a-f0-9]{8}$/.test(record.job))throw new Error('Invalid run identifier.');
 if(typeof record.completedAt!=='string'||!Number.isFinite(Date.parse(record.completedAt)))throw new Error('Invalid run timestamp.');

 if(record.input?.units?.width!=='nm'||record.input?.units?.temperature!=='K'||record.input?.units?.voltage!=='V')throw new Error('Invalid run units.');
 if(record.serverVersion!=null&&(typeof record.serverVersion!=='string'||!/^\d[0-9A-Za-z.+-]{0,63}$/.test(record.serverVersion)))throw new Error('Invalid server version.');
 if(record.pinned!==undefined&&typeof record.pinned!=='boolean')throw new Error('Invalid run pin state.');
 const input=validateProject(record.input);
 const settings=expectedSettings(record.settings?.adapter,input.model);
 if(!record.settings||Object.keys(record.settings).length!==Object.keys(settings).length||Object.keys(settings).some(k=>JSON.stringify(record.settings[k])!==JSON.stringify(settings[k])))throw new Error('Unsupported run settings or input mismatch.');
 if(input.model.electric||input.model.heat||input.model.structure||!input.model.optics||shapesBlock(input.model.shapes)||input.setup.materials.Oxide!=='Silica')throw new Error('Run is not a supported optical-only input.');
 if(!Array.isArray(record.effective_index)||record.effective_index.length!==2||!record.effective_index.every(Number.isFinite))throw new Error('Invalid effective indices.');
 const f=record.field;
 if(!f)throw new Error('Missing run fields.');
 const field=readOpticalField({node_coordinates:f.node_coordinates,field_units:{node_coordinates:'m'},triangles:f.triangles,vector_fields:[{...FIELD_METADATA,real:f.real,imag:f.imag}]});
 for(let mode=0;mode<2;mode++)fieldScalars(field,mode);
 return {pinned:record.pinned===true,label:validateRunLabel(record.label),serverVersion:record.serverVersion??null,job:record.job,completedAt:new Date(record.completedAt).toISOString(),settings:JSON.parse(JSON.stringify(settings)),input,signature:JSON.stringify(input),effective_index:[...record.effective_index],field,origin:imported?'imported':['imported','recovered'].includes(record.origin)?record.origin:'local'};
}
/** The session record of a run: the validated run without its derived display fields. */
function sessionRun(run){
 const {signature,field,...record}=validateRun(run);
 return {...record,field:{node_coordinates:field.node_coordinates,triangles:field.triangles,real:field.real,imag:field.imag}};
}
export function appendRun(runs,run){
 const previous=runs.find(r=>r.job===run.job);
 const next=[...runs.filter(r=>r.job!==run.job),previous?{...run,label:previous.label||run.label,pinned:previous.pinned||run.pinned}:run];
 while(next.length>RUN_LIMIT){const oldest=next.findIndex(r=>!r.pinned&&r.job!==run.job);if(oldest<0)throw new Error('All notebook slots are pinned. Unpin a run before retaining another result.');next.splice(oldest,1);}
 return next;
}
/** The field view in the page's micrometres (probe x, y and profile coordinate as numbers). */
export function validateView(view={mode:0,component:'magnitude',window:'Core region'}){
 if(!view||![0,1].includes(view.mode)||!['magnitude','Ex','Ey','Ez'].includes(view.component)||!['Core region','Full window'].includes(view.window))throw new Error('Unsupported saved field view.');
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
export function createSession(input,runs,selected,comparison,view={mode:0,component:'magnitude',window:'Core region'}){
 return {format:'openphysics-studio-session',version:SESSION_VERSION,input:validateProject(input),runs:runs.map(sessionRun),selected,comparison:[...comparison],view:sessionView(view)};
}
// Capture editable metadata now; serialize large, read-only field arrays after debounce.
// UI operations replace results rather than modifying their field samples in place.
export function captureSession(input,runs,selected,comparison,view){
 const capturedInput=validateProject(input),capturedView=validateView(view);
 const capturedRuns=runs.map(run=>({...run,input:validateProject(run.input),
  settings:JSON.parse(JSON.stringify(run.settings)),effective_index:[...run.effective_index]}));
 const capturedComparison=[...comparison];
 return ()=>JSON.stringify(createSession(capturedInput,capturedRuns,selected,capturedComparison,capturedView));
}

export function parseSession(text,{recovered=false}={}){
 if(new TextEncoder().encode(text).length>MAX_SESSION_BYTES)throw new Error('Session exceeds 16 MiB.');
 let doc;try{doc=JSON.parse(text);}catch{throw new Error('Session is not valid JSON.');}
 if(doc?.format==='openphysics-studio-session'&&[1,2,3,4,5].includes(doc.version))throw new Error(`This session (version ${doc.version}) was saved before the units and naming batch; its results are not read. Re-run the design and save a new session.`);
 if(doc?.format!=='openphysics-studio-session'||doc.version!==SESSION_VERSION||!Array.isArray(doc.runs)||doc.runs.length>RUN_LIMIT)throw new Error('Unsupported session format or run count.');
 if(doc.input?.units?.width!=='nm'||doc.input?.units?.temperature!=='K'||doc.input?.units?.voltage!=='V')throw new Error('Invalid session input units.');
 const input=validateProject(doc.input),runs=doc.runs.map(r=>{const run=validateRun(r,true);if(recovered)run.origin='recovered';return run;}),ids=runs.map(r=>r.job);
 if(new Set(ids).size!==ids.length)throw new Error('Duplicate run identifiers.');
 if(doc.selected!==null&&!ids.includes(doc.selected))throw new Error('Selected run is missing.');
 if(!Array.isArray(doc.comparison)||doc.comparison.length!==2||!doc.comparison.every(id=>id===null||ids.includes(id)))throw new Error('Invalid comparison selection.');
 const view=readView(doc.view||{mode:0,component:'magnitude',window:'Core region'});
 return {input,runs,selected:doc.selected,comparison:[...doc.comparison],view};
}


export function mergeRuns(existing,incoming){
 if(!incoming.length)throw new Error('The session contains no completed runs.');
 const result=[...existing],incomingIds=new Set(),added=[],reused=[];
 const identity=run=>JSON.stringify({input:run.input,settings:run.settings,effective_index:run.effective_index,field:{node_coordinates:run.field.node_coordinates,triangles:run.field.triangles,real:run.field.real,imag:run.field.imag},serverVersion:run.serverVersion??null});
 for(const raw of incoming){
  const run=validateRun(raw,true);if(incomingIds.has(run.job))throw new Error('Duplicate imported run identifier.');incomingIds.add(run.job);
  const prior=existing.find(r=>r.job===run.job);
  if(prior){if(identity(prior)!==identity(run))throw new Error('Conflicting result for job '+run.job+'. Existing notebook kept.');reused.push(run.job);}
  else{result.push(run);added.push(run.job);}
 }
 const evicted=[];
 while(result.length>RUN_LIMIT){const index=result.findIndex(run=>!run.pinned&&!incomingIds.has(run.job));if(index<0)throw new Error('Imported runs and pinned references exceed six slots. Unpin a reference or import a selected-run file.');evicted.push(result[index].job);result.splice(index,1);}
 return {runs:result,added,reused,evicted};
}
