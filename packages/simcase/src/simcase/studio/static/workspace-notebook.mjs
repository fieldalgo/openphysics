// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

import {validateProject} from './workspace-project.mjs';
import {readOpticalField,fieldScalars} from './workspace-field.mjs';
import {legacyCoreShape,shapesBlock,shapeText,V4_MATERIALS} from './workspace-shapes.mjs';
export const MAX_SESSION_BYTES=16*1024*1024;
export const RUN_LIMIT=6;
export const OPTICAL_SETTINGS=Object.freeze({adapter:'optical-fixed-v1',height_nm:220,wavelength_nm:1550,core_mesh_nm:30,window_um:[-1.5,1.5,-1.2,1.2],boundary:'PEC',candidates:2,solver_version:'not reported'});
export function opticalSettings(wavelength=1550,coreMesh=30){if(!Number.isFinite(wavelength)||wavelength<1400||wavelength>1700||!Number.isFinite(coreMesh)||coreMesh<20||coreMesh>60)throw new Error('Unsupported wavelength or core mesh size.');const {height_nm,...fixed}=OPTICAL_SETTINGS;return {...fixed,adapter:'optical-shapes-v5',wavelength_nm:wavelength,core_mesh_nm:coreMesh};}
// Earlier adapters computed one centred rectangular core; v1/v2 also fixed 1550 nm / 30 nm.
const LEGACY_ADAPTERS=['optical-fixed-v1','optical-rectangle-v2','optical-rectangle-v3'];
function expectedSettings(adapter,model,setup){
 // v4 offered four materials; its runs keep their adapter name.
 if(adapter==='optical-shapes-v4'){if(!model.shapes.every(s=>V4_MATERIALS.includes(s.material)))throw new Error('Unsupported run settings or input mismatch.');return {...opticalSettings(model.wavelength,model.coreMesh),adapter};}
 if(!LEGACY_ADAPTERS.includes(adapter))return opticalSettings(model.wavelength,model.coreMesh);
 const core=legacyCoreShape(model.width,model.height,setup.materials.Core);
 if(!core.material||JSON.stringify(model.shapes)!==JSON.stringify([core]))throw new Error('Unsupported run settings or input mismatch.');
 if(adapter!=='optical-rectangle-v3'&&(model.wavelength!==1550||model.coreMesh!==30))throw new Error('Unsupported run settings or input mismatch.');
 if(adapter==='optical-fixed-v1')return OPTICAL_SETTINGS;
 const settings={...OPTICAL_SETTINGS,adapter,height_nm:model.height};
 return adapter==='optical-rectangle-v3'?{...settings,wavelength_nm:model.wavelength,core_mesh_nm:model.coreMesh}:settings;
}
export function validateRunLabel(value=''){
 if(typeof value!=='string'||value.length>80||/[\u0000-\u001f\u007f-\u009f]/.test(value))throw new Error('Run name must be at most 80 characters without control characters.');
 return value.trim();
}
export function csvCell(value){const text=String(value);const safe=typeof value==='string'&&/^\s*[=+@-]/.test(text)?"'"+text:text;return '"'+safe.replaceAll('"','""')+'"';}
export function runTableCsv(runs){
 const rows=[['job','name','pinned','completed_at','core_width_nm','core_height_nm','wavelength_nm','core_mesh_nm','core_material','shapes','candidate','neff','origin']];
 for(const r of runs){const shapes=r.input.model.shapes,single=shapes.length===1&&shapes[0].type==='rect'?shapes[0]:null;
  r.neff.forEach((n,i)=>rows.push([r.job,r.label||'',r.pinned===true,r.completedAt,single?single.w:'',single?single.h:'',r.input.model.wavelength,r.input.model.coreMesh,single?single.material:'',shapes.map(shapeText).join(' | '),i+1,n,r.origin]));}
 return rows.map(row=>row.map(csvCell).join(',')).join('\n')+'\n';
}
export function validateRun(record,imported=false){
 if(!record||typeof record.job!=='string'||!/^[a-f0-9]{8}$/.test(record.job))throw new Error('Invalid run identifier.');
 if(typeof record.completedAt!=='string'||!Number.isFinite(Date.parse(record.completedAt)))throw new Error('Invalid run timestamp.');

 if(record.input?.units?.width!=='nm'||record.input?.units?.temperature!=='K'||record.input?.units?.voltage!=='V')throw new Error('Invalid run units.');
 if(record.serverVersion!=null&&(typeof record.serverVersion!=='string'||!/^\d[0-9A-Za-z.+-]{0,63}$/.test(record.serverVersion)))throw new Error('Invalid server version.');
 if(record.pinned!==undefined&&typeof record.pinned!=='boolean')throw new Error('Invalid run pin state.');
 const input=validateProject(record.input);
 const settings=expectedSettings(record.settings?.adapter,input.model,input.setup);
 if(!record.settings||record.settings.height_nm!==settings.height_nm||Object.keys(settings).some(k=>JSON.stringify(record.settings[k])!==JSON.stringify(settings[k])))throw new Error('Unsupported run settings or input mismatch.');
 if(input.model.electric||input.model.heat||input.model.structure||!input.model.optics||shapesBlock(input.model.shapes)||input.setup.materials.Oxide!=='Silica')throw new Error('Run is not a supported optical-only input.');
 if(!Array.isArray(record.neff)||record.neff.length!==2||!record.neff.every(Number.isFinite))throw new Error('Invalid effective indices.');
 const f=record.field;
 if(!f)throw new Error('Missing run fields.');
 const field=readOpticalField({nodes:f.nodes,triangles:f.triangles,vector_fields:[{location:'triangle_centroids',components:['Ex','Ey','Ez'],normalization:'max_centroid_magnitude',amplitude_unit:'relative',real:f.real,imag:f.imag}]});
 for(let mode=0;mode<2;mode++)fieldScalars(field,mode);
 return {pinned:record.pinned===true,label:validateRunLabel(record.label),serverVersion:record.serverVersion??null,job:record.job,completedAt:new Date(record.completedAt).toISOString(),settings:JSON.parse(JSON.stringify(settings)),input,signature:JSON.stringify(input),neff:[...record.neff],field,origin:imported?'imported':['imported','recovered'].includes(record.origin)?record.origin:'local'};
}
export function appendRun(runs,run){
 const previous=runs.find(r=>r.job===run.job);
 const next=[...runs.filter(r=>r.job!==run.job),previous?{...run,label:previous.label||run.label,pinned:previous.pinned||run.pinned}:run];
 while(next.length>RUN_LIMIT){const oldest=next.findIndex(r=>!r.pinned&&r.job!==run.job);if(oldest<0)throw new Error('All notebook slots are pinned. Unpin a run before retaining another result.');next.splice(oldest,1);}
 return next;
}
export function validateView(view={mode:0,component:'magnitude',window:'Core region'}){
 if(!view||![0,1].includes(view.mode)||!['magnitude','Ex','Ey','Ez'].includes(view.component)||!['Core region','Full window'].includes(view.window))throw new Error('Unsupported saved field view.');
 const result={mode:view.mode,component:view.component,window:view.window};
 if(view.probe!==undefined){const p=view.probe;if(!p||typeof p.active!=='boolean'||!Number.isFinite(p.x)||!Number.isFinite(p.y)||p.x < -1.5||p.x > 1.5||p.y < -1.2||p.y > 1.2)throw new Error('Invalid saved probe position.');result.probe={x:p.x,y:p.y,active:p.active};}
 if(view.profile!==undefined){const p=view.profile,extent=p?.axis==='x'?1.2:1.5;if(!p||!['x','y'].includes(p.axis)||typeof p.open!=='boolean'||!Number.isFinite(p.coordinate)||Math.abs(p.coordinate)>extent)throw new Error('Invalid saved profile line.');result.profile={axis:p.axis,coordinate:p.coordinate,open:p.open};}
 return result;
}
export function createSession(input,runs,selected,comparison,view={mode:0,component:'magnitude',window:'Core region'}){
 return {format:'openphysics-studio-session',version:5,input:validateProject(input),runs:runs.map(r=>validateRun(r)),selected,comparison:[...comparison],view:validateView(view)};
}
// Capture editable metadata now; serialize large, read-only field arrays after debounce.
// UI operations replace results rather than modifying their field samples in place.
export function captureSession(input,runs,selected,comparison,view){
 const capturedInput=validateProject(input),capturedView=validateView(view);
 const capturedRuns=runs.map(run=>({...run,input:validateProject(run.input),
  settings:JSON.parse(JSON.stringify(run.settings)),neff:[...run.neff]}));
 const capturedComparison=[...comparison];
 return ()=>JSON.stringify(createSession(capturedInput,capturedRuns,selected,capturedComparison,capturedView));
}

export function parseSession(text,{recovered=false}={}){
 if(new TextEncoder().encode(text).length>MAX_SESSION_BYTES)throw new Error('Session exceeds 16 MiB.');
 let doc;try{doc=JSON.parse(text);}catch{throw new Error('Session is not valid JSON.');}
 if(doc?.format!=='openphysics-studio-session'||![1,2,3,4,5].includes(doc.version)||!Array.isArray(doc.runs)||doc.runs.length>RUN_LIMIT)throw new Error('Unsupported session format or run count.');
 if(doc.input?.units?.width!=='nm'||doc.input?.units?.temperature!=='K'||doc.input?.units?.voltage!=='V')throw new Error('Invalid session input units.');
 const input=validateProject(doc.input),runs=doc.runs.map(r=>{const run=validateRun(r,true);if(recovered)run.origin='recovered';return run;}),ids=runs.map(r=>r.job);
 if(new Set(ids).size!==ids.length)throw new Error('Duplicate run identifiers.');
 if(doc.selected!==null&&!ids.includes(doc.selected))throw new Error('Selected run is missing.');
 if(!Array.isArray(doc.comparison)||doc.comparison.length!==2||!doc.comparison.every(id=>id===null||ids.includes(id)))throw new Error('Invalid comparison selection.');
 const view=validateView(doc.view||{mode:0,component:'magnitude',window:'Core region'});
 return {input,runs,selected:doc.selected,comparison:[...doc.comparison],view};
}


export function mergeRuns(existing,incoming){
 if(!incoming.length)throw new Error('The session contains no completed runs.');
 const result=[...existing],incomingIds=new Set(),added=[],reused=[];
 const identity=run=>JSON.stringify({input:run.input,settings:run.settings,neff:run.neff,field:run.field,serverVersion:run.serverVersion??null});
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
