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
// A Compare field panel heading: the side, then the run without repeating the side as its name
// (a run named "A" on side A reads "A · 600 × 300 nm · …", not "A · A · 600 × 300 nm · …").
export function fieldHeading(side,run){
 const named=run.label&&run.label.trim().toLowerCase()!==side.toLowerCase();
 return `${side} · ${runHeading(named?run:{...run,label:''})}`;
}
// n_eff everywhere (results, candidate select, Compare): 8 decimals.
export const formatIndex=value=>value.toFixed(8);
export const formatPercent=value=>value===null?'—':value.toFixed(4)+' %';
