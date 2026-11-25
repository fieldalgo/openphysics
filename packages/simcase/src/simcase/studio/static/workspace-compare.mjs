// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
import {designSummary} from './workspace-shapes.mjs';

// A run's boundary as every run label names it (round 18, X6): "open (PML 1 µm)" for a run with an
// open boundary (its PML thickness as the run kept it), "closed near 2.46" for a closed window with
// Search near n_eff (slice C2), else "closed" (a PEC window).
export function boundaryTag(run){
 const pml=run.settings?.boundary==='PML'?run.settings.pml?.thickness:null,t=typeof pml==='string'?Number.parseFloat(pml):NaN;
 // a closed window with Search near n_eff (slice C2): "closed near 2.46"
 if(run.settings?.boundary!=='PML'&&typeof run.settings?.search_target==='number')return `closed near ${String(run.settings.search_target)}`;
 return run.settings?.boundary==='PML'?`open (PML ${Number.isFinite(t)?t/1000:1} µm)`:'closed';
}
// A run as a table header names it: its number (its place in the run list) when given, its name
// (if any), its boundary, size and wavelength: "Run 1 · design A · closed · 600 × 300 nm · Silicon ·
// λ 1550 nm".
export function runHeading(run,number=null){
 const name=Number.isInteger(number)?`Run ${number}${run.label?' · '+run.label:''} · `:run.label?run.label+' · ':'';
 return `${name}${runDesign(run)} · λ ${run.input.model.wavelength} nm`;
}
// A run's design as the run list and the Compare pickers name it: the boundary first, right after
// the run number and name (round 18, X6), then designSummary, so a label cut short in a picker
// still shows it: "open (PML 1 µm) · Core 500 × 220 + Substrate 3000 × 700 nm · Silicon".
// Round 21 (W3): then what the study computed when it is not the default, so two runs of one design
// read apart: " · 4 modes" (" · 1 mode") when Modes to find was not 2, " · n_g" when the group index
// was computed, both before the geometry, so a picker cut at its end still shows them:
// "open (PML 1 µm) · 4 modes · n_g · Core 500 × 220 + Substrate 3000 × 700 nm · Silicon".
export const STUDY_DEFAULT_MODES=2;
export function studyTag(run){
 const modes=run.settings?.mode_count,count=Number.isInteger(modes)&&modes!==STUDY_DEFAULT_MODES?` · ${modes} ${modes===1?'mode':'modes'}`:'';
 return count+(Array.isArray(run.group_index)?' · n_g':'');
}
export function runDesign(run){
 return boundaryTag(run)+studyTag(run)+' · '+designSummary(run.input.model);
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
// Whether Compare keeps its pair when new runs come (round 16): a pair the user picked on Compare
// (picked), or one whose two runs are both named; never one run on both sides (the pair a single
// run gives). Otherwise the default pair is the two newest.
export function pairKept(runs,[a,b],picked=false){
 const ra=runs.find(r=>r.job===a),rb=runs.find(r=>r.job===b);
 return !!ra&&!!rb&&a!==b&&(picked||!!ra.label&&!!rb.label);
}
// The pair after a run is added: the kept pair, else the default (defaultComparison).
export function comparisonAfterRun(runs,ids,picked=false){return pairKept(runs,ids,picked)?[...ids]:defaultComparison(runs);}
// A pair read from a file or browser recovery is kept when it is not the default pair (someone
// chose it) or when both runs are named.
export const pairChosen=(runs,ids)=>{const d=defaultComparison(runs);return ids[0]!==d[0]||ids[1]!==d[1];};
// The newest run outside a pair, when it is newer than both runs of the pair (runs oldest first),
// for the line "Run 5 is newer than this pair · Compare Run 5 with B"; else null.
export function newerThanPair(runs,[a,b]){
 const last=runs.at(-1),ia=runs.findIndex(r=>r.job===a),ib=runs.findIndex(r=>r.job===b);
 return last&&ia>=0&&ib>=0&&runs.length-1>Math.max(ia,ib)?last:null;
}
// Round 24 (B4, coordinator decision on the round-24 findings): the pair Compare offers in one action
// when runs newer than the shown pair exist and the pair was not picked by hand (picked: a pair
// chosen on Compare, or a pair read from a file or recovery that is not the default one): the two
// newest, [A job, B job] as defaultComparison gives them, for "Compare the two newest: Run 6 and
// Run 7"; else null (a pair picked by hand keeps "Compare Run 7 with B" and is never replaced).
export function newestPairOffer(runs,ids,picked=false){
 if(picked||!newerThanPair(runs,ids))return null;
 const d=defaultComparison(runs);return d[0]===d[1]?null:d;
}
// The side a run card names on Compare: "A", "B", "A and B" (one run on both sides) or ''.
export function compareSide(job,[a,b]){return job===a&&job===b?'A and B':job===a?'A':job===b?'B':'';}
// n_eff everywhere (results, mode select, Compare): 8 decimals.
export const formatIndex=value=>value.toFixed(8);
export const formatPercent=value=>value===null?'—':value.toFixed(4)+' %';
