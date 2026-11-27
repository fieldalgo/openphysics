// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Pure helpers of the experimental 3D mesh job: the estimate's words, the steps Studio knows,
// the elapsed time and the mesh stats. No DOM, no WebGL, no network, so Node tests them.

/** The steps of a mesh job, in order, as the status route names them. */
export const STEPS=['forming','meshing','checking','ready'];
export const CANCEL_LABEL='Cancel meshing';
export const CANCELLED='Meshing cancelled; nothing kept.';
export const LONGER='taking longer than the estimate';

/** Elapsed time as m:ss. */
export function elapsedText(seconds){
 const s=Math.max(0,Math.floor(seconds));return Math.floor(s/60)+':'+String(s%60).padStart(2,'0');
}

/** A count rounded to two significant figures, with thousands separators: 47787 -> "48,000". */
export function roundedCount(n){
 if(!(n>=0))return '0';
 if(n<100)return String(Math.round(n));
 const e=Math.pow(10,Math.floor(Math.log10(n))-1);
 return (Math.round(n/e)*e).toLocaleString('en-US');
}

/** A duration in the estimate's rounding: under 1 s; seconds to one significant figure up to a
 * minute ("about 30 s"); whole minutes above ("about 3 min"). */
export function durationText(seconds){
 if(!(seconds>=1))return 'under 1 s';
 if(seconds<9.5)return `about ${Math.round(seconds)} s`;
 if(seconds<59.5){const e=Math.pow(10,Math.floor(Math.log10(seconds)));return `about ${Math.round(seconds/e)*e} s`;}
 return `about ${Math.max(1,Math.round(seconds/60))} min`;
}

/** "Estimate 48,000 tetrahedra · about 30 s" of an estimate answer ({tetrahedra, seconds}). */
export function estimateText(estimate){
 return `Estimate ${roundedCount(estimate.tetrahedra)} tetrahedra · ${durationText(estimate.seconds)}`;
}

/** The step list of a status answer: [{key, label, state: 'done'|'current'|'todo'}]. The meshing
 * step carries the expected time. A cancelled or failed job marks no step current. */
export function stepList(status){
 const labels={forming:'Forming geometry',meshing:`Meshing (expected ${durationText(status.expected_s)})`,
  checking:'Checking the mesh',ready:'Ready'};
 const at=status.status==='done'?STEPS.length-1:STEPS.indexOf(status.step);
 const live=status.status==='running'||status.status==='done';
 return STEPS.map((key,i)=>({key,label:labels[key],
  state:status.status==='done'||i<at?'done':i===at&&live?'current':'todo'}));
}

/** Whether to add "taking longer than the estimate": a running job past twice its estimate. */
export function longer(status){
 return status.status==='running'&&status.elapsed_s>2*status.expected_s;
}

/** The one-line progress of a status answer. */
export function progressText(status){
 const steps=stepList(status),current=steps.find(s=>s.state==='current');
 if(status.status==='cancelled')return CANCELLED;
 if(status.status==='error')return 'Meshing failed: '+(status.error?.message||'unknown error');
 if(status.status==='done')return status.reused?'Ready (the kept mesh of this geometry and mesh block)':'Ready';
 return `${current?current.label:'Meshing'} · ${elapsedText(status.elapsed_s)}`+(longer(status)?' · '+LONGER:'');
}

/** The stats rows of a mesh answer. */
export function statsRows(view){
 const s=view.stats,q=x=>Number(x).toFixed(3);
 return [['Nodes',s.nodes.toLocaleString('en-US')],['Tetrahedra',s.tetrahedra.toLocaleString('en-US')],
  ['Regions',String(s.regions)],['Quality, min',q(s.quality_min)],['Quality, median',q(s.quality_median)],
  ['Surface triangles',s.surface_triangles.toLocaleString('en-US')]];
}

/** Why Mesh is disabled, or null: no 3d component shown, an estimate refusal, a job running. */
export function meshBlocked({estimate,refused,running}){
 if(running)return 'A mesh job is running; wait for it or cancel it.';
 if(refused)return refused;
 if(!estimate)return 'Show a 3d component first.';
 return null;
}

/** Per-vertex colours of a mesh answer: each triangle's corners take its region's colour times
 * the face's shade; returns non-indexed positions and colours (three floats per corner). */
export function triangleColors(positions,indices,regionOf,colorOf,shadeOf,shown){
 const n=indices.length/3;let m=0;
 for(let t=0;t<n;t++)if(shown(t))m++;
 const pos=new Float32Array(9*m),col=new Float32Array(9*m);let k=0;
 for(let t=0;t<n;t++){
  if(!shown(t))continue;
  const c=colorOf(regionOf(t)),s=shadeOf(t);
  for(let j=0;j<3;j++){
   const i=indices[3*t+j];
   pos[k]=positions[3*i];pos[k+1]=positions[3*i+1];pos[k+2]=positions[3*i+2];
   col[k]=c[0]*s;col[k+1]=c[1]*s;col[k+2]=c[2]*s;k+=3;
  }
 }
 return {positions:pos,colors:col};
}
