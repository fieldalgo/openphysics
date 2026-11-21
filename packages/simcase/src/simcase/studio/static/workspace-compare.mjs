// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
import {designSummary} from './workspace-shapes.mjs';

// The Compare table: one row per candidate rank of two runs. Ranks are the solver's
// ordering by effective index, not modes matched across designs.
export function compareRows(a,b){
 const n=Math.min(a.length,b.length);
 return Array.from({length:n},(_,i)=>{const delta=b[i]-a[i];return {rank:i+1,a:a[i],b:b[i],delta,percent:a[i]===0?null:delta/a[i]*100};});
}
// A run as a table header names it: its name (if any), size and wavelength.
export function runHeading(run){
 return `${run.label?run.label+' · ':''}${designSummary(run.input.model)} · λ ${run.input.model.wavelength} nm`;
}
export const formatIndex=value=>value.toFixed(8);
export const formatPercent=value=>value===null?'—':value.toFixed(4)+' %';
