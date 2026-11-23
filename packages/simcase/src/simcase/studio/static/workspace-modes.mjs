// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
import {formatIndex} from './workspace-compare.mjs';
import {isOpenRun,NO_WINDOW_TITLE} from './workspace-open-run.mjs';

// The modes table of one run: | Mode | n_eff | Polarization | Absorption loss (dB/cm) | A_eff (µm²) |. Every number is
// defined on the saved centroid field unnormalized_electric_field, so Studio and the engine
// (te_polarization_fraction, effective_area, simcase.mode_postprocessing) give the same value from
// the same samples.

export const RANKING_TEXT='Modes are ranked by effective index.';
export const POLARIZATION_HELP='TE = share of |E_x|² in |E_x|² + |E_y|², x horizontal';
// The loss column of a closed window counts material absorption (k) only: its header, the help of
// every cell and the note under the table say so; "0 dB/cm" is a lossless run, not a computed leak.
// A result with an open boundary (PML) has an Im n_eff that includes leakage into the PML: its
// column is "Loss (dB/cm)", with its own help.
export const LOSS_HEADER='Absorption loss (dB/cm)';
export const PML_LOSS_HEADER='Loss (dB/cm)';
export const ABSORPTION_HELP='Absorption (material k) only; leakage and radiation are not computed in a closed window';
export const PML_LOSS_HELP='Material absorption (k) and leakage into the PML of the open boundary';
export const ABSORPTION_NOTE='Absorption loss counts material absorption (k) only. Leakage and radiation are not computed in a closed window.';
export const LOSSLESS_NOTE='Absorption loss counts material absorption (k) only: all materials have k = 0 at this wavelength, so it is 0 dB/cm. Leakage and radiation are not computed in a closed window.';
export const PML_LOSS_NOTE='Loss includes material absorption (k) and leakage into the PML of the open boundary. Leakage depends on what lies outside the window: shapes touching an open edge continue through the PML.';
/** The loss column of a table: {header, help, note}; open: the result has an open boundary (PML);
 * lossless: every mode has Im n_eff exactly 0. */
export function lossColumn({open=false,lossless=false}={}){
 if(open)return {header:PML_LOSS_HEADER,help:PML_LOSS_HELP,note:PML_LOSS_NOTE};
 return {header:LOSS_HEADER,help:ABSORPTION_HELP,note:lossless?LOSSLESS_NOTE:ABSORPTION_NOTE};
}
// 1e-3, not smaller: the mesh splits a symmetric pair by 1e-4 to 6e-4 at 40-10 nm, below the solver's n_eff
// error at the same meshes, so two modes closer than 1e-3 cannot be told apart by this solver.
export const PAIR_TOLERANCE=1e-3;
const PAIR_TEXT='1e-3';
export const PAIR_TITLE=`Two modes whose n_eff differ by at most ${PAIR_TEXT}: a degenerate pair. Each member's polarization is not defined (any rotation within the pair is a solution); only the pair's TE share together is.`;
export const SOURCE_TEXT=Object.freeze({engine:'computed by the engine from the saved field',studio:'computed by Studio from the saved field',file:'saved in the session file; its fields were not kept',
 engineWindow:'computed by the engine from the saved field on the physical window (PML excluded)',studioWindow:'computed by Studio from the saved field on the physical window (PML excluded)',noWindow:NO_WINDOW_TITLE.toLowerCase()});
export const RUN_AGAIN='Run again to compute';
export const AREA_HELP='Effective area (∫|E|²)²/∫|E|⁴ over the window, all three field components';
export const AREA_PAIR_NOTE='A member of a degenerate pair: its effective area depends on the rotation within the pair, which any solution may choose.';
export const SCALAR_AREA_HELP='Effective area (∫|φ|²)²/∫|φ|⁴ of the scalar mode field over the window';
export const AREA_MEAN_NOTE='Mean of the pair members: each member’s effective area is defined only up to a rotation within the pair.';

/** The physical window of an open run: for each triangle, whether its centroid (p0 + p1 + p2) / 3
 * lies inside bounds [[x0, y0], [x1, y1]] (the engine's physical_bounds, the coordinates' unit),
 * the bounds included; written as the engine writes it (simcase.mode_postprocessing.physical_window). */
export function physicalWindow(field,bounds){
 const X=field.node_coordinates,[[x0,y0],[x1,y1]]=bounds;
 return field.triangles.map(t=>{const cx=(X[t[0]][0]+X[t[1]][0]+X[t[2]][0])/3,cy=(X[t[0]][1]+X[t[1]][1]+X[t[2]][1])/3;return cx>=x0&&cx<=x1&&cy>=y0&&cy<=y1;});
}
/** The physical bounds [[x0, y0], [x1, y1]] in metres of an open run's candidate record
 * (physical_bounds, {unit: 'm', values}), or null when it has none that is valid. */
export function physicalBounds(record){
 const b=record?.physical_bounds,v=b?.values;
 if(b?.unit!=='m'||!Array.isArray(v)||v.length!==2||!v.every(p=>Array.isArray(p)&&p.length===2&&p.every(Number.isFinite)))return null;
 return v[0][0]<v[1][0]&&v[0][1]<v[1][1]?[[v[0][0],v[0][1]],[v[1][0],v[1][1]]]:null;
}
/** f_TE of one mode: Σ A_T |E_x|² / Σ A_T (|E_x|² + |E_y|²) over every triangle (or over those of
 * `window`, physicalWindow's list, for an open run), with A_T from the node coordinates (any length
 * unit) and |E|² = re² + im², written as the engine writes it.
 * field: {node_coordinates, triangles, real, imag}, real/imag[mode][triangle] = [x, y, z].
 * null when the mode has no transverse field. */
export function teFraction(field,mode,window=null){
 const X=field.node_coordinates,re=field.real[mode],im=field.imag[mode];
 let num=0,den=0;
 field.triangles.forEach((t,i)=>{
  if(window&&!window[i])return;
  const p0=X[t[0]],p1=X[t[1]],p2=X[t[2]];
  const area=0.5*Math.abs((p1[0]-p0[0])*(p2[1]-p0[1])-(p1[1]-p0[1])*(p2[0]-p0[0]));
  const ex=re[i][0]*re[i][0]+im[i][0]*im[i][0],ey=re[i][1]*re[i][1]+im[i][1]*im[i][1];
  num+=area*ex;den+=area*ey;
 });
 den+=num;
 return den>0?num/den:null;
}
/** A_eff of one mode: (Σ A_T |E_T|²)² / Σ A_T |E_T|⁴ over every triangle (or those of `window`),
 * |E|² = |E_x|² + |E_y|² + |E_z|², in the node coordinates' unit squared (metres for Studio runs),
 * written as the engine writes it (simcase.mode_postprocessing.effective_area). null when the mode
 * has no field. */
export function effectiveArea(field,mode,window=null){
 const X=field.node_coordinates,re=field.real[mode],im=field.imag[mode];
 let num=0,den=0;
 field.triangles.forEach((t,i)=>{
  if(window&&!window[i])return;
  const p0=X[t[0]],p1=X[t[1]],p2=X[t[2]];
  const area=0.5*Math.abs((p1[0]-p0[0])*(p2[1]-p0[1])-(p1[1]-p0[1])*(p2[0]-p0[0]));
  const r=re[i],m=im[i],d=(r[0]*r[0]+m[0]*m[0])+(r[1]*r[1]+m[1]*m[1])+(r[2]*r[2]+m[2]*m[2]);
  num+=area*d;den+=area*(d*d);
 });
 return den>0?num*num/den:null;
}
/** An area in m² as µm² to 4 significant digits (whole µm² from 1000 µm² up, never an exponent),
 * "—" when unknown. */
export const areaText=a=>{if(!Number.isFinite(a))return '—';const u=a*1e12;return Math.abs(u)>=1000?u.toFixed(0):u.toPrecision(4);};
// Studio's words, not the engine's: TE-like at f_TE >= 0.9, TM-like at f_TE <= 0.1, else hybrid.
export function polarizationWord(f){return f>=0.9?'TE-like':f<=0.1?'TM-like':'hybrid';}
export const tePercent=f=>(f*100).toFixed(1)+' % TE';
/** The share a cell names: TE for a TE-like mode; for a TM-like mode the dominant TM share first and
 * its TE share after it, "96.9 % TM (3.1 % TE)"; for a hybrid mode both, "21.7 % TE / 78.3 % TM".
 * One fraction, one rounding: TE is f × 100 to one decimal (toFixed(1)) and TM is 100 minus that
 * rounded TE, so the two always add to 100.0. */
export function polarizationShare(f){
 const word=polarizationWord(f);if(word==='TE-like')return tePercent(f);
 const te=(f*100).toFixed(1),tm=(100-Number(te)).toFixed(1);
 return word==='TM-like'?tm+' % TM ('+te+' % TE)':te+' % TE / '+tm+' % TM';
}
/** Groups of consecutive modes (rows of the table, in the run's order) whose Re n_eff all lie
 * within 1e-3 of each other (the whole group, not a chain): a group of two is a degenerate pair.
 * Modes outside a group are not listed. */
export function degenerateGroups(re){
 // "at most 1e-3" with the rounding of the decimal values allowed
 const close=(a,b)=>Math.abs(a-b)<=PAIR_TOLERANCE*(1+1e-9),groups=[];
 for(let i=0;i<re.length;){
  let j=i+1,lo=re[i],hi=re[i];
  while(j<re.length&&close(Math.min(lo,re[j]),Math.max(hi,re[j]))){lo=Math.min(lo,re[j]);hi=Math.max(hi,re[j]);j++;}
  if(j-i>1)groups.push(Array.from({length:j-i},(_,k)=>i+k));
  i=j;
 }
 return groups;
}
/** Loss text from propagation_loss in dB/m (exp(-i omega t), Im n_eff > 0 is loss):
 * dB/cm = 20 log10(e) k0 Im(n_eff) / 100 with k0 = 2 pi / lambda0 in 1/m, to 4 significant digits;
 * "0 dB/cm" when Im n_eff is exactly 0 (a real n_eff: the engine solved a problem without loss).
 * No threshold: a nonzero Im n_eff, however small, is shown as it is. */
export function lossText(im,dbPerM){
 if(im===0)return '0 dB/cm';
 if(!Number.isFinite(dbPerM))return '—';
 return (dbPerM/100).toPrecision(4)+' dB/cm';
}
/** propagation_loss [dB/m] = (40 pi / ln 10) Im n_eff / lambda0, the engine's formula. */
export const propagationLoss=(im,lambda0)=>40*Math.PI/Math.LN10*im/lambda0;
/** The table rows. modes: [{re, im, fte (number or null), loss (dB/m or null), area (m² or null)}];
 * missing: the reason the fractions are absent ('' when they are present); areaMissing: the same
 * for the effective areas. One merged polarization cell per degenerate group, on its first row
 * with rowspan; each member keeps its own effective area, with a note. */
export function modeTableRows(modes,{missing='',areaMissing='',areaHelp=AREA_HELP,polarizationHelp=POLARIZATION_HELP,open=false}={}){
 const allLossless=modes.length>0&&modes.every(m=>m.im===0),column=lossColumn({open,lossless:allLossless});
 const close=new Set(degenerateGroups(modes.map(m=>m.re)).flat());
 // a group is merged only when each member has its fraction (a result without them keeps its reason)
 const groups=degenerateGroups(modes.map(m=>m.re)).filter(g=>g.every(i=>Number.isFinite(modes[i].fte))),groupOf=new Map();groups.forEach(g=>g.forEach(i=>groupOf.set(i,g)));
 const rows=modes.map((m,i)=>{
  const row={mode:i+1,label:`Mode ${i+1}`,neff:formatIndex(m.re),loss:lossText(m.im,m.loss),lossless:m.im===0,lossTitle:column.help};
  row.area=Number.isFinite(m.area)?{text:areaText(m.area),value:m.area,title:close.has(i)?areaHelp+'. '+AREA_PAIR_NOTE:areaHelp}:{text:'—',value:null,title:areaMissing||'No field: no effective area'};
  const g=groupOf.get(i);
  if(g&&g.length>1){
   if(g[0]!==i){row.polarization=null;return row;}
   const values=g.map(j=>modes[j].fte),known=values.every(Number.isFinite),mean=known?values.reduce((a,b)=>a+b,0)/values.length:null;
   const name=g.length===2?'pair':`group of ${g.length}`;
   row.polarization={text:`${name} (n_eff within ${PAIR_TEXT}) · ${known?(mean*100).toFixed(0)+' % TE together':'—'}`,title:PAIR_TITLE,rowspan:g.length,pair:true,mean};
   return row;
  }
  row.polarization=Number.isFinite(m.fte)?{text:`${polarizationWord(m.fte)} · ${polarizationShare(m.fte)}`,title:polarizationHelp,rowspan:1,word:polarizationWord(m.fte)}:{text:'—',title:missing||'No transverse field',rowspan:1};
  return row;
 });
 return {rows,lossless:modes.some(m=>m.im===0),groups,loss:column};
}
/** The field view's mode picker: "Mode 1 · TE-like · n_eff 2.44406001" (a pair member reads "pair"). */
export function modeOptionLabel(i,modes){
 const m=modes[i],inPair=degenerateGroups(modes.map(x=>x.re)).some(g=>g.includes(i)&&g.every(j=>Number.isFinite(modes[j].fte)));
 const word=inPair?'pair':Number.isFinite(m.fte)?polarizationWord(m.fte):null;
 return `Mode ${i+1}${word?' · '+word:''} · n_eff ${formatIndex(m.re)}`;
}
// The n_g column: the engine's group index of a run run with Also compute group index (Study),
// n_g = n_eff - λ0 dn_eff/dλ0 by a central difference over λ0 ± the step; "—" otherwise.
export const groupIndexHelp=(step='1 nm')=>`n_g = n_eff − λ0 dn_eff/dλ0: central difference over λ0 ± ${step} (3 solves), materials evaluated at each wavelength`;
export const GROUP_INDEX_OFF_HELP='Turn on Also compute group index in Study or Optical modes';
// The box's note in Study and Optical modes, the message when it is ticked or cleared, and the
// visible hint under an n_g header when no run shown computed n_g.
export const GROUP_INDEX_NOTE='Also solves at λ ± 1 nm and takes n_g from the change (about 3× slower). Off: one solve, no n_g. n_g includes the dispersion of the materials (evaluated at λ ± 1 nm).';
export const groupIndexNotice=on=>on?'Group index on: the next run also solves at λ ± 1 nm and gives n_g (about 3× slower).':'Group index off: the next run is one solve, without n_g.';
// Optical modes › Material data: the materials are physmat records (SHAPE_MATERIALS), whose index the
// engine evaluates at each wavelength it solves (λ, and λ ± 1 nm with the group index).
export const OPTICAL_MATERIAL_DATA='physmat materials, evaluated at each wavelength solved';
export const GROUP_INDEX_HINT='Off · turn on in Study or Optical modes';
/** Whether a run computed n_g (it has the engine's group_index). */
export const hasGroupIndex=run=>Array.isArray(run?.group_index);
// An open run's n_g is complex (its n_eff is): the cell shows Re n_g, its help Im n_g.
export const OPEN_GROUP_INDEX_NOTE='With an open boundary n_eff and n_g are complex: Re n_g is shown';
// The measured mesh error of n_g (slice P3, V11: the leaky slab, Re n_g error 5.24e-3 at the default
// mesh, 2.81e-3 and 1.50e-3 on halving; almost all of it the error of n_eff itself).
export const OPEN_GROUP_INDEX_MESH_NOTE='At the default mesh n_g is about 5e-3 low in the slab check; the error comes from n_eff and shrinks when the core mesh is refined.';
export const groupIndexKeptHelp=(step='1 nm')=>`Not matched at λ0 ± ${step}; the reason is not kept in session files`;
/** The step of a run's group_index_method ("central_difference 1 nm electric-l2-assignment-v1"), or null. */
export function groupIndexStep(method){const m=/^central_difference (\S+ (?:pm|nm|um|m)) \S+$/.exec(method??'');return m?m[1]:null;}
const methodStep=method=>groupIndexStep(method)??'1 nm';
/** The n_g cell of mode i of a run: {text, value, title}. A run without group_index: "—", with the
 * help to turn the option on; a mode the engine could not match (null): "—" with the engine's
 * reason when this tab has it (groupIndexReasons, not written to files), else the kept-in-files note. */
export function groupIndexCell(run,i){
 if(!Array.isArray(run.group_index))return {text:'—',value:null,title:GROUP_INDEX_OFF_HELP};
 const v=run.group_index[i],step=methodStep(run.group_index_method);
 const im=Array.isArray(run.group_index_im)?run.group_index_im[i]:null;
 if(Number.isFinite(v))return {text:v.toFixed(4),value:v,title:groupIndexHelp(step)+(Number.isFinite(im)?`. ${OPEN_GROUP_INDEX_NOTE}; Im n_g ${im.toExponential(2)}. ${OPEN_GROUP_INDEX_MESH_NOTE}`:'')};
 const reason=run.groupIndexReasons?.[i];
 return {text:'—',value:null,title:typeof reason==='string'&&reason?'Not matched: '+reason:groupIndexKeptHelp(step)};
}
/** The modes of an optical run (1 to 8 modes, real or complex indices, its vector samples or,
 * for a run of a file without fields, the values saved with it). f_TE and A_eff: the engine's
 * when they came with the run, else computed by Studio from the saved field; for an open run on
 * its physical window (the PML excluded), whose bounds its candidate record holds. */
export function opticalModes(run){
 const keep=(key,values,source)=>Object.defineProperty(run,key,{value:{values,source},enumerable:false,configurable:true,writable:true});
 const source=run.field?'engine':'file';
 if(isOpenRun(run)){
  const bounds=physicalBounds(run.open_boundary),window=run.field&&bounds?physicalWindow(run.field,bounds):null;
  const computed=(key,f)=>window?keep(key,run.effective_index.map((_,i)=>f(run.field,i,window)),'studioWindow'):keep(key,run.effective_index.map(()=>null),'noWindow');
  if(!run.te)run.te_polarization_fraction?keep('te',run.te_polarization_fraction,run.field?'engineWindow':'file'):computed('te',teFraction);
  if(!run.area)run.effective_area?keep('area',run.effective_area,run.field?'engineWindow':'file'):computed('area',effectiveArea);
 }
 if(!run.te)run.te_polarization_fraction?keep('te',run.te_polarization_fraction,source):keep('te',run.effective_index.map((_,i)=>teFraction(run.field,i)),'studio');
 // a run without samples and without saved areas (a test may build one) has no A_eff
 if(!run.area)run.effective_area?keep('area',run.effective_area,source):keep('area',run.effective_index.map((_,i)=>run.field?effectiveArea(run.field,i):null),'studio');
 const im=run.effective_index_im;
 return run.effective_index.map((re,i)=>({re,im:im?im[i]:0,fte:run.te.values[i],loss:im&&im[i]!==0?propagationLoss(im[i],run.input.model.wavelength*1e-9):null,area:run.area.values[i]}));
}
/** The engine's effective_area (m²) of the first study point in a summary, or null. */
export function engineEffectiveArea(summary){
 const v=summary?.mode_postprocessing?.effective_area;
 if(!v||v.unit!=='m^2'||!Array.isArray(v.values?.[0]))return null;
 // an area that is not positive is not the engine's: the whole list is refused
 if(!v.values[0].every(x=>x===null||(Number.isFinite(x)&&x>0)))return null;
 return v.values[0].map(x=>Number.isFinite(x)?x:null);
}
/** The engine's te_polarization_fraction of the first study point in a summary, or null. */
export function engineTeFraction(summary){
 const v=summary?.mode_postprocessing?.te_polarization_fraction;
 if(!v||v.unit!=='1'||!Array.isArray(v.values?.[0]))return null;
 // a fraction outside [0, 1] is not the engine's: the whole list is refused
 if(!v.values[0].every(x=>x===null||(Number.isFinite(x)&&x>=0&&x<=1)))return null;
 return v.values[0].map(x=>Number.isFinite(x)?x:null);
}
/** The modes of an em.modes2d physics of a multiphysics reply: real or complex {re, im}
 * effective indices, the engine's fractions (absent for scalar results and for runs saved before
 * the fraction existed) and propagation_loss. */
export function physicsModes(p){
 const s=p.effective_index,re=Array.isArray(s?.values)?s.values[0]:Array.isArray(s?.re)?s.re[0]:[],im=Array.isArray(s?.im)?s.im[0]:re.map(()=>0);
 const fte=engineTeFraction(p.summary),loss=p.summary?.propagation_loss?.unit==='dB/m'?p.summary.propagation_loss.values?.[0]:null;
 const vector=p.summary?.formulation==='vector';
 const missing=fte?'':!vector?'Scalar formulation: no polarization (choose the vector formulation)':p.summary?.open_boundary?'PML result: its fields are in stretched coordinates, so no polarization is computed':RUN_AGAIN+': this run was saved before Studio kept the TE fraction';
 const lambda0=p.vacuum_wavelength?.unit==='m'?p.vacuum_wavelength.values?.[0]:null;
 const lossAt=i=>Array.isArray(loss)&&Number.isFinite(loss[i])?loss[i]:Number.isFinite(lambda0)&&Number.isFinite(im[i])?propagationLoss(im[i],lambda0):null;
 const fits=fte&&fte.length===re.length;
 const area=engineEffectiveArea(p.summary),areaFits=area&&area.length===re.length;
 const areaMissing=areaFits?'':area?'The saved effective areas do not match the modes':p.summary?.open_boundary?'PML result: its fields are in stretched coordinates, so no effective area is computed':RUN_AGAIN+': this run was saved before Studio kept the effective area';
 return {modes:re.map((r,i)=>({re:r,im:im[i]??0,fte:fits?fte[i]:null,loss:lossAt(i),area:areaFits?area[i]:null})),missing:fits||!fte?missing:'The saved TE fractions do not match the modes',source:fits?'engine':null,areaMissing,areaSource:areaFits?'engine':null,areaHelp:vector?AREA_HELP:SCALAR_AREA_HELP,open:!!p.summary?.open_boundary};
}
