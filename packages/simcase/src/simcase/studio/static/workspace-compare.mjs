// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
import {designSummary} from './workspace-shapes.mjs';

// A run as a table header names it: its number (its place in the run list) when given, its name
// (if any), size and wavelength: "Run 1 · design A · 600 × 300 nm · Silicon · λ 1550 nm".
export function runHeading(run,number=null){
 const name=Number.isInteger(number)?`Run ${number}${run.label?' · '+run.label:''} · `:run.label?run.label+' · ':'';
 return `${name}${designSummary(run.input.model)} · λ ${run.input.model.wavelength} nm`;
}
// A run's design as the run list and the Compare pickers name it (round 16): designSummary, and
// "open (PML 1 µm)" for a run with an open boundary (its PML thickness as the run kept it).
export function runDesign(run){
 const pml=run.settings?.boundary==='PML'?run.settings.pml?.thickness:null,t=typeof pml==='string'?Number.parseFloat(pml):NaN;
 return designSummary(run.input.model)+(Number.isFinite(t)?` · open (PML ${t/1000} µm)`:'');
}
// A Compare field panel heading: the side, then the run without repeating the side as its name
// (a run named "A" on side A reads "A · 600 × 300 nm · …", not "A · A · 600 × 300 nm · …").
export function fieldHeading(side,run,number=null){
 const named=run.label&&run.label.trim().toLowerCase()!==side.toLowerCase();
 return `${side} · ${runHeading(named?run:{...run,label:''},number)}`;
}
// The pair Compare opens with, as [A job, B job]: A the older and B the newer of the two newest
// runs (a run just computed is B, the run before it A). The run list shows the newest first, so B is
// above A there, and on Compare each of the two cards says which side it is (compareSide). [job, job]
// with one run, [null, null] with none.
export function defaultComparison(runs){
 if(!runs.length)return [null,null];
 return [(runs.at(-2)||runs.at(-1)).job,runs.at(-1).job];
}
// The side a run card names on Compare: "A", "B", "A and B" (one run on both sides) or ''.
export function compareSide(job,[a,b]){return job===a&&job===b?'A and B':job===a?'A':job===b?'B':'';}
// n_eff everywhere (results, mode select, Compare): 8 decimals.
export const formatIndex=value=>value.toFixed(8);
export const formatPercent=value=>value===null?'—':value.toFixed(4)+' %';
