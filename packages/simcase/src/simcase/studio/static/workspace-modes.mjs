// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
import {formatIndex} from './workspace-compare.mjs';

// The modes table of one run: | Mode | n_eff | Polarization | Loss |. Every number is defined on
// the saved centroid field unnormalized_electric_field, so Studio and the engine
// (te_polarization_fraction, simcase.mode_postprocessing) give the same value from the same samples.

export const RANKING_TEXT='Modes are ranked by effective index.';
export const POLARIZATION_HELP='TE = share of |E_x|² in |E_x|² + |E_y|², x horizontal';
export const LOSSLESS_NOTE='Lossless: all materials have k = 0 at this wavelength. Leakage and radiation are not computed in a closed window.';
// 1e-3, not smaller: the mesh splits a symmetric pair by 1e-4 to 6e-4 at 40-10 nm, below the solver's n_eff
// error at the same meshes, so two modes closer than 1e-3 cannot be told apart by this solver.
export const PAIR_TOLERANCE=1e-3;
const PAIR_TEXT='1e-3';
export const PAIR_TITLE=`Two modes whose n_eff differ by at most ${PAIR_TEXT}: a degenerate pair. Each member's polarization is not defined (any rotation within the pair is a solution); only the pair's TE share together is.`;
export const SOURCE_TEXT=Object.freeze({engine:'computed by the engine from the saved field',studio:'computed by Studio from the saved field'});
export const RUN_AGAIN='Run again to compute';

/** f_TE of one mode: Σ A_T |E_x|² / Σ A_T (|E_x|² + |E_y|²) over every triangle, with A_T from the
 * node coordinates (any length unit) and |E|² = re² + im², written as the engine writes it.
 * field: {node_coordinates, triangles, real, imag}, real/imag[mode][triangle] = [x, y, z].
 * null when the mode has no transverse field. */
export function teFraction(field,mode){
 const X=field.node_coordinates,re=field.real[mode],im=field.imag[mode];
 let num=0,den=0;
 field.triangles.forEach((t,i)=>{
  const p0=X[t[0]],p1=X[t[1]],p2=X[t[2]];
  const area=0.5*Math.abs((p1[0]-p0[0])*(p2[1]-p0[1])-(p1[1]-p0[1])*(p2[0]-p0[0]));
  const ex=re[i][0]*re[i][0]+im[i][0]*im[i][0],ey=re[i][1]*re[i][1]+im[i][1]*im[i][1];
  num+=area*ex;den+=area*ey;
 });
 den+=num;
 return den>0?num/den:null;
}
// Studio's words, not the engine's: TE-like at f_TE >= 0.9, TM-like at f_TE <= 0.1, else hybrid.
export function polarizationWord(f){return f>=0.9?'TE-like':f<=0.1?'TM-like':'hybrid';}
export const tePercent=f=>(f*100).toFixed(1)+' % TE';
/** The share a cell names: TE for TE-like and hybrid modes; for a TM-like mode the dominant TM share
 * first and its TE share after it, "96.9 % TM (3.1 % TE)", the two adding to 100.0. */
export function polarizationShare(f){
 if(polarizationWord(f)!=='TM-like')return tePercent(f);
 const te=(f*100).toFixed(1);return (100-Number(te)).toFixed(1)+' % TM ('+te+' % TE)';
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
/** Loss text from propagation_loss in dB/m (exp(-i omega t), Im n_eff > 0 is loss): dB/cm to 4
 * significant digits, or "lossless" when Im n_eff is exactly 0. */
export function lossText(im,dbPerM){
 if(im===0)return 'lossless';
 if(!Number.isFinite(dbPerM))return '—';
 return (dbPerM/100).toPrecision(4)+' dB/cm';
}
/** propagation_loss [dB/m] = (40 pi / ln 10) Im n_eff / lambda0, the engine's formula. */
export const propagationLoss=(im,lambda0)=>40*Math.PI/Math.LN10*im/lambda0;
/** The table rows. modes: [{re, im, fte (number or null), loss (dB/m or null)}]; missing: the
 * reason the fractions are absent ('' when they are present). One merged polarization cell per
 * degenerate group, on its first row with rowspan. */
export function modeTableRows(modes,{missing=''}={}){
 // a group is merged only when each member has its fraction (a result without them keeps its reason)
 const groups=degenerateGroups(modes.map(m=>m.re)).filter(g=>g.every(i=>Number.isFinite(modes[i].fte))),groupOf=new Map();groups.forEach(g=>g.forEach(i=>groupOf.set(i,g)));
 const rows=modes.map((m,i)=>{
  const row={mode:i+1,label:`Mode ${i+1}`,neff:formatIndex(m.re),loss:lossText(m.im,m.loss),lossless:m.im===0};
  const g=groupOf.get(i);
  if(g&&g.length>1){
   if(g[0]!==i){row.polarization=null;return row;}
   const values=g.map(j=>modes[j].fte),known=values.every(Number.isFinite),mean=known?values.reduce((a,b)=>a+b,0)/values.length:null;
   const name=g.length===2?'pair':`group of ${g.length}`;
   row.polarization={text:`${name} (n_eff within ${PAIR_TEXT}) · ${known?(mean*100).toFixed(0)+' % TE together':'—'}`,title:PAIR_TITLE,rowspan:g.length,pair:true,mean};
   return row;
  }
  row.polarization=Number.isFinite(m.fte)?{text:`${polarizationWord(m.fte)} · ${polarizationShare(m.fte)}`,title:POLARIZATION_HELP,rowspan:1,word:polarizationWord(m.fte)}:{text:'—',title:missing||'No transverse field',rowspan:1};
  return row;
 });
 return {rows,lossless:modes.some(m=>m.im===0),groups};
}
/** The field view's mode picker: "Mode 1 · TE-like · n_eff 2.44406001" (a pair member reads "pair"). */
export function modeOptionLabel(i,modes){
 const m=modes[i],inPair=degenerateGroups(modes.map(x=>x.re)).some(g=>g.includes(i)&&g.every(j=>Number.isFinite(modes[j].fte)));
 const word=inPair?'pair':Number.isFinite(m.fte)?polarizationWord(m.fte):null;
 return `Mode ${i+1}${word?' · '+word:''} · n_eff ${formatIndex(m.re)}`;
}
/** The modes of an optical run (two real indices and the vector samples). Studio computes f_TE
 * from the saved field unless the engine's values came with a fresh run. */
export function opticalModes(run){
 if(!run.te){const values=run.effective_index.map((_,i)=>teFraction(run.field,i));Object.defineProperty(run,'te',{value:{values,source:'studio'},enumerable:false,configurable:true,writable:true});}
 return run.effective_index.map((re,i)=>({re,im:0,fte:run.te.values[i],loss:null}));
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
 return {modes:re.map((r,i)=>({re:r,im:im[i]??0,fte:fits?fte[i]:null,loss:lossAt(i)})),missing:fits||!fte?missing:'The saved TE fractions do not match the modes',source:fits?'engine':null};
}
