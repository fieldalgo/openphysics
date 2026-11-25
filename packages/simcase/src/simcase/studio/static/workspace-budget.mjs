// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// The run-retention budget (design "Keeping more runs", sections 3.2 and 7), shared by the optical
// model's fields (workspace-retention.mjs) and the heated model's maps
// (workspace-multiphysics-session.mjs). This module imports nothing, so both can use it.
//
// The budget is the 16 MiB session less 16 KiB kept for the inputs: 16,760,832 bytes, "16.8 MB".
// When a field or a map arrives, those kept are, while the session text with them is within the
// budget: 1. the selected run's (kept even when it alone is over the budget); 2. the runs' whose
// field or maps arrived (`first`), when not selected; 3. the pinned runs', newest first (the largest
// run number first); 4. the other runs', newest first. One that does not fit is skipped and the next
// older one tried.
export const MAX_SESSION_BYTES=16*1024*1024;
export const FIELD_HEADROOM_BYTES=16*1024;
export const FIELD_BUDGET_BYTES=MAX_SESSION_BYTES-FIELD_HEADROOM_BYTES;
/** A size in MB with one decimal ("16.8 MB"), as every limit of run retention is said. */
export const mbText=bytes=>`${(bytes/1e6).toFixed(1)} MB`;
const newestFirst=(a,b)=>b.number-a.number;

/** The runs (each with a field or maps) in the order they are kept: the selected run's, the jobs of
 * `first`, then pinned newest first, then the others newest first. */
export function budgetOrder(runs,selected,first=[]){
 const chosen=runs.filter(r=>r.job===selected);
 for(const job of first){const r=runs.find(x=>x.job===job);if(r&&!chosen.includes(r))chosen.push(r);}
 const rest=runs.filter(r=>!chosen.includes(r));
 return [...chosen,...rest.filter(r=>r.pinned).sort(newestFirst),...rest.filter(r=>!r.pinned).sort(newestFirst)];
}
/** The ordered runs the budget keeps: {kept, letGo, total}. base: the session bytes without any of
 * them; bytes(run): the bytes a run's field or maps add (cached record sums). The first run, when it
 * is the selected one, is kept even alone over the budget. */
export function budgetChoose(ordered,{base,bytes,selected,budget=FIELD_BUDGET_BYTES}){
 let total=base;const kept=[],letGo=[];
 ordered.forEach((r,i)=>{const b=bytes(r);
  if(total+b<=budget||(i===0&&r.job===selected)){kept.push(r);total+=b;}else letGo.push(r);});
 return {kept,letGo,total};
}

