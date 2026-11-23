// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

// A run with an open boundary (optical-shapes-v9, slice P2): its settings, the words of its
// results (loss, found line, the other candidates of the search) and the optional PML check, a
// second solve of the same document with PML strength 6. Pure functions: the page draws them.
import {EDGES,hasOpenEdge,defaultTarget,maxIndex,TARGET_FLOOR,PML_THICKNESS_DEFAULT_NM,checkOpenBoundary,OPEN_BOUNDARY_ADAPTER} from './workspace-open-boundary.mjs';
import {formatIndex} from './workspace-compare.mjs';

export const OPEN_ADAPTER=OPEN_BOUNDARY_ADAPTER;
export const PML_WORDS='PML 1 µm';
export const PML_THICKNESS_TEXT=PML_THICKNESS_DEFAULT_NM+' nm';
export const CANDIDATE_SCHEMA='openphysics.pml-candidates/2';
// Studio keeps the modes with Re n_eff above the silica threshold (the closed window's rule).
export const SILICA_THRESHOLD=1.45;

// -- the choice (Physics › Optical modes, Geometry › Boundaries) ------------------------------
export const BOUNDARY_CHOICES=Object.freeze({closed:'Closed window (PEC)',open:'Open boundary (PML)'});
export const OPEN_HELP='Open boundary adds an absorbing layer (PML) outside the window, so light that leaves the window is lost. Loss then includes leakage. Shapes touching an open edge continue through the layer.';
export const TARGET_HELP='Search near n_eff: the solver returns the modes nearest this effective index. Default (n_max + n_SiO2)/2, rounded to 0.01. A single search can miss modes far from it, notably near the cladding index (Re below about 1.6): lowering Search near n_eff finds them.';
export const PML_DETAILS='PML 1 µm (fixed) · strength 3, order 2 · minimum physical fraction 0.5 · 32 candidates searched';
export const GROUP_INDEX_OPEN_NOTE='Group index with an open boundary comes in a later version';
export const LATER_TITLE='Computed on the physical window in a later version';
/** "Also check the PML (2 more solves)": one solve per mode, n = Modes to find. */
export const checkLabel=n=>`Also check the PML (${n} more solve${n===1?'':'s'})`;
export const CHECK_NOTE='Solves the same mesh again with the PML twice as strong (strength 6), once near each mode found, and compares each mode: a leakage loss that changes is not converged.';
/** With an open edge the group index is not computed: its box is off and disabled. */
export const groupIndexLocked=ob=>hasOpenEdge(ob);
/** The open boundary of a new choice of Open: every edge open, the default target. */
export const openChoice=()=>({edges:Object.fromEntries(EDGES.map(e=>[e,'open'])),target:null});
/** The edges of an open boundary that are open, in the order left, right, bottom, top. */
export const openEdges=ob=>EDGES.filter(e=>ob?.edges?.[e]==='open');
/** "2.460": a target to 3 decimals, the text shown and kept with a run. */
export const targetText=t=>t.toFixed(3);
/** The target in effect: the edited one, or the default of these shapes (P1's, to 0.01). */
export const effectiveTarget=(ob,shapes)=>ob?.target??defaultTarget(shapes);
/** A typed Search near n_eff, kept to 3 decimals and checked (1.45 < target < n_max). */
export function parseTarget(text,shapes){
 const value=typeof text==='number'?text:Number(String(text).trim());
 const nmax=maxIndex(shapes);
 if(String(text).trim()===''||!Number.isFinite(value))throw new Error(`Search near n_eff must be a number between ${TARGET_FLOOR} and ${nmax}.`);
 const t=Math.round(value*1000)/1000;
 if(!(t>TARGET_FLOOR&&t<nmax))throw new Error(`Search near n_eff must lie between ${TARGET_FLOOR} and ${nmax}.`);
 return t;
}
/** The open boundary the builder reads (workspace-open-boundary.mjs), or null with every edge
 * closed or no choice: {edges, thickness, target}. */
export function builderBoundary(ob,shapes){
 if(!ob||!hasOpenEdge(ob))return null;
 return checkOpenBoundary({edges:ob.edges,thickness:PML_THICKNESS_DEFAULT_NM,target:effectiveTarget(ob,shapes)},shapes);
}
/** The open boundary of the page in a run's settings form {open_edges, target}, the part of the
 * study signature a run is compared by; null for a closed window or a target out of range. */
export function signaturePml(ob,shapes){
 try{const b=builderBoundary(ob,shapes);return b?{open_edges:openEdges(b),target:targetText(b.target)}:null;}catch{return null;}
}
/** "Open boundary · PML 1 µm · search near 2.460" (Study), or "" for a closed window. */
export function studySummary(ob,shapes){
 if(!ob||!hasOpenEdge(ob))return '';
 return `Open boundary · ${PML_WORDS} · search near ${targetText(effectiveTarget(ob,shapes))}`;
}
/** The section text of the drawing: "… · open boundary (PML 1 µm) on N edges" or "". */
export function sectionWords(ob){const n=openEdges(ob).length;return n?`open boundary (${PML_WORDS}) on ${n} edge${n===1?'':'s'}`:'';}

// -- the run's settings ------------------------------------------------------------------------
/** The settings of an open run: closed settings with adapter optical-shapes-v9, boundary PML and
 * pml {thickness, open_edges, target} (key order fixed: the order a file writes). */
export function openSettings(settings,ob,shapes){
 const b=builderBoundary(ob,shapes);if(!b)return settings;
 return {adapter:OPEN_ADAPTER,domain:settings.domain,boundary:'PML',mode_count:settings.mode_count,solver_version:settings.solver_version,vacuum_wavelength:settings.vacuum_wavelength,core_element_size:settings.core_element_size,pml:{thickness:PML_THICKNESS_TEXT,open_edges:openEdges(b),target:targetText(b.target)}};
}
export const isOpenRun=run=>run?.settings?.boundary==='PML';
/** The choice a run was made with: {edges, target} (target as sent). */
export function runChoice(run){
 if(!isOpenRun(run))return null;
 const open=new Set(run.settings.pml.open_edges);
 return {edges:Object.fromEntries(EDGES.map(e=>[e,open.has(e)?'open':'closed'])),target:Number(run.settings.pml.target)};
}
const TARGET_TEXT=/^\d\.\d{3}$/;
/** The pml block of an open run's settings, checked against its shapes; the expected settings. */
export function checkOpenSettings(settings,expected,shapes,which='This run'){
 const p=settings?.pml;
 if(settings?.boundary!=='PML'||!p||typeof p!=='object'||Object.keys(p).join()!=='thickness,open_edges,target')throw new Error(`${which}: invalid open boundary settings.`);
 if(p.thickness!==PML_THICKNESS_TEXT)throw new Error(`${which}: the PML thickness must be ${PML_THICKNESS_TEXT}.`);
 if(!Array.isArray(p.open_edges)||!p.open_edges.length||p.open_edges.join()!==EDGES.filter(e=>p.open_edges.includes(e)).join()||new Set(p.open_edges).size!==p.open_edges.length)throw new Error(`${which}: invalid open edges.`);
 if(typeof p.target!=='string'||!TARGET_TEXT.test(p.target))throw new Error(`${which}: invalid search target.`);
 const choice={edges:Object.fromEntries(EDGES.map(e=>[e,p.open_edges.includes(e)?'open':'closed'])),target:Number(p.target)};
 const out=openSettings(expected,choice,shapes);
 if(targetText(choice.target)!==p.target)throw new Error(`${which}: invalid search target.`);
 return out;
}

// -- loss and n_eff ----------------------------------------------------------------------------
export const LOSS_FLOOR=0.01;  // dB/cm: what the open boundary of a 3 x 2.4 um window resolves
export const FLOOR_TEXT='< 0.01 dB/cm';
export const FLOOR_HELP='Below what this open boundary resolves for a 3 × 2.4 µm window (0.01 dB/cm). The mode does not leak measurably here.';
export const MESH_ERROR_NOTE='At the default mesh this loss is about 3 % above the converged value (TE-like +2.8 %, TM-like +1.8 % on a strip over a substrate).';
export const OPEN_LOSS_HELP='Material absorption (k) and leakage into the PML of the open boundary';
export const OPEN_NOTE_EXTRA='Leakage depends on what lies outside the window: shapes touching an open edge continue through the PML.';
export const CLOSED_POINTER='For leakage, choose Open boundary in Physics › Optical modes.';
/** dB/cm of Im n_eff at lambda0 (m): 20 log10(e) k0 Im n_eff / 100. */
export const dbPerCm=(im,lambda0)=>40*Math.PI/Math.LN10*im/lambda0/100;
/** The loss cell of an open run: {text, title, value (dB/cm or null), floor}. status: the
 * candidate's attenuation_status ("numerically_unresolved" reads as below the floor). */
export function openLoss(im,lambda0,status=null){
 if(im===null||im===undefined||!Number.isFinite(im))return {text:'—',title:'No Im n_eff',value:null,floor:false};
 const value=dbPerCm(im,lambda0);
 if(status==='numerically_unresolved'||!(value>=LOSS_FLOOR))return {text:FLOOR_TEXT,title:FLOOR_HELP,value,floor:true};
 return {text:(value>=1e4?value.toFixed(0):value.toPrecision(4))+' dB/cm',title:OPEN_LOSS_HELP+'. '+MESH_ERROR_NOTE,value,floor:false};
}
/** "2.44227500 + 8.28e-5i": Re as a closed run shows it, Im to 3 significant digits. */
export function openIndexText(re,im){
 if(!Number.isFinite(im))return formatIndex(re);
 const t=Math.abs(im).toExponential(2);return `${formatIndex(re)} ${im<0||Object.is(im,-0)?'−':'+'} ${t}i`;
}

// -- the candidates of the search --------------------------------------------------------------
export const REASON_WORDS=Object.freeze({low_physical_l2_fraction:'Mostly in the PML (a PML mode)',negative_imaginary_index:'Gains power (not a passive mode)',pencil_residual:'Not converged (residual above 1e-8)',outside_requested_count:'Beyond the modes asked for',not_finite_forward:'Not a finite forward mode'});
export const BELOW_SILICA='Below the silica index (cladding radiation)';
const isObject=x=>x!==null&&typeof x==='object'&&!Array.isArray(x);
const REASON=/^[a-z0-9_]{1,48}$/;
/** The engine's candidate record of one study point, checked (the keys Studio reads); a copy. */
export function checkCandidateRecord(record,which='This run'){
 const bad=()=>{throw new Error(`${which}: invalid open boundary record.`);};
 if(!isObject(record)||record.schema!==CANDIDATE_SCHEMA||!Array.isArray(record.candidates)||record.candidates.length<1||record.candidates.length>64)bad();
 const numbers=new Set();
 for(const c of record.candidates){
  if(!isObject(c)||!Number.isInteger(c.candidate)||c.candidate<1||numbers.has(c.candidate))bad();numbers.add(c.candidate);
  const e=c.effective_index;if(!isObject(e)||!Number.isFinite(e.re)||!Number.isFinite(e.im))bad();
  if(!Number.isFinite(c.physical_l2_fraction)||!Array.isArray(c.reasons)||c.reasons.length>8||!c.reasons.every(r=>typeof r==='string'&&REASON.test(r))||typeof c.selected!=='boolean')bad();
  if(c.attenuation_status!==undefined&&typeof c.attenuation_status!=='string')bad();
 }
 if(!Array.isArray(record.selected_candidates)||!record.selected_candidates.every(n=>numbers.has(n)))bad();
 return JSON.parse(JSON.stringify(record));
}
const sameIndex=(c,re,im)=>c.effective_index.re===re&&c.effective_index.im===im;
/** The engine's modes of a new open result reduced to those Studio shows (Re n_eff above 1.45):
 * {keep: the indices kept, in the engine's order}. */
export const shownIndices=re=>re.map((x,i)=>x>SILICA_THRESHOLD?i:-1).filter(i=>i>=0);
/** The candidate of each shown mode (selected, same n_eff), or null. */
export function modeCandidates(record,re,im){
 return re.map((r,i)=>record.candidates.find(c=>c.selected&&sameIndex(c,r,im[i]))??null);
}
/** The searched candidates a run does not show, with their n_eff, physical share and reason. */
export function otherCandidates(record,re,im){
 const shown=new Set(modeCandidates(record,re,im).filter(Boolean).map(c=>c.candidate));
 return record.candidates.filter(c=>!shown.has(c.candidate)).map(c=>{
  const words=c.selected?[BELOW_SILICA]:c.reasons.filter(r=>r!=='selected_near_target').map(r=>REASON_WORDS[r]??r);
  return {candidate:c.candidate,neff:openIndexText(c.effective_index.re,c.effective_index.im),share:(c.physical_l2_fraction*100).toFixed(1)+' %',reason:words.join('; ')||BELOW_SILICA};
 });
}
export const otherCandidatesTitle=n=>`Other candidates (${n}) — not shown as modes`;
export const OTHER_CANDIDATES_NOTE='Each was searched and set aside for the reason given; no field view is offered for them. Physical share: the part of the mode in the window, not in the PML.';
/** "Found 2 of 2 modes near n_eff 2.460" (shown for every open run: the target matters). */
export const openFoundText=(found,asked,target)=>`Found ${found} of ${asked} modes near n_eff ${target}`;
export const MOVE_TARGET_TEXT='Move Search near n_eff (Physics › Optical modes) to find other modes.';
export const openTableTitle=()=>`Modes (open boundary, ${PML_WORDS})`;

// -- the PML check -----------------------------------------------------------------------------
export const CHECK_STRENGTH=6,CHECK_SEARCH=16;
/** The documents of the PML check of a run made from `doc`: one per mode, with strength 6, a search
 * of 16 and the target at that mode's Re n_eff to 6 decimals; everything else (the mesh) is doc's. */
export function checkDocuments(doc,re){
 return re.map(r=>{const d=JSON.parse(JSON.stringify(doc)),em=d.physics.em1;em.pml.pml_strength=CHECK_STRENGTH;em.pml.pml_search_mode_count=CHECK_SEARCH;em.target_effective_index=Math.round(r*1e6)/1e6;return d;});
}
export const PAIR_LIMIT=2e-3,RE_LIMIT=5e-4,LOSS_SHARE=0.02;
/** Within the pairing distance |Δn_eff| <= 2e-3. */
export const withinPair=delta=>delta<=PAIR_LIMIT;
/** The n_eff criterion of independence: |ΔRe| <= 5e-4. */
export const reIndependent=delta=>Math.abs(delta)<=RE_LIMIT;
/** The loss criterion: |L2 − L1| <= max(2 % of L1, 0.01 dB/cm). */
export const lossIndependent=(l1,l2)=>Math.abs(l2-l1)<=Math.max(LOSS_SHARE*Math.abs(l1),LOSS_FLOOR);
/** The second solve's eligible candidates: passed the engine's filter (selected, or set aside only
 * as beyond the count asked for) and Re n_eff above 1.45. */
export function eligibleCandidates(record){
 return record.candidates.filter(c=>c.reasons.length>0&&c.reasons.every(r=>r==='selected_near_target'||r==='outside_requested_count')&&c.effective_index.re>SILICA_THRESHOLD).map(c=>({re:c.effective_index.re,im:c.effective_index.im}));
}
/** Each first-solve mode paired with the nearest eligible candidate of the check solves (their
 * candidate records pooled), or null when none lies within 2e-3: the pml_check a run keeps. */
export function pairCheck(re,im,checkRecords){
 const pool=(Array.isArray(checkRecords)?checkRecords:[checkRecords]).flatMap(eligibleCandidates);
 return {pml_strength:CHECK_STRENGTH,paired:re.map((r,i)=>{
  let best=null,bestD=Infinity;
  for(const c of pool){const d=Math.hypot(c.re-r,c.im-im[i]);if(d<bestD){best=c;bestD=d;}}
  return best&&withinPair(bestD)?{re:best.re,im:best.im}:null;
 })};
}
export function checkPmlCheck(check,k,which='This run'){
 if(!isObject(check)||Object.keys(check).join()!=='pml_strength,paired'||check.pml_strength!==CHECK_STRENGTH||!Array.isArray(check.paired)||check.paired.length!==k||!check.paired.every(p=>p===null||(isObject(p)&&Object.keys(p).join()==='re,im'&&Number.isFinite(p.re)&&Number.isFinite(p.im))))throw new Error(`${which}: invalid PML check.`);
 return {pml_strength:CHECK_STRENGTH,paired:check.paired.map(p=>p&&{re:p.re,im:p.im})};
}
// "12 %", "0.1 %", "0.0038 %": two significant digits below 0.1 %, never "0.0 %"
const percent=x=>(x>=10?x.toFixed(0):x>=0.1?x.toFixed(1):x===0?'0':x.toPrecision(2))+' %';
export const NOT_FOUND_HELP='The check solve did not find this mode near the search value; this does not by itself mean the mode depends on the PML.';
export const DEPENDS_HELP='This loss changes with the PML; it is not a converged leakage loss.';
export const CHECK_HEADER='PML check';
export const CHECK_HELP='The same mesh solved again with PML strength 6, near each mode. PML-independent: Re n_eff within 5e-4 and the loss within max(2 %, 0.01 dB/cm).';
// Below the display floor the check solve (strength 6) leaves a larger residue than the run's
// solve: the template's TM-like mode, registered as independent, went 0.00480 -> 0.01706 dB/cm
// ("Depends on the PML: loss changes 256 %"). After that result: a mode whose cell reads
// "< 0.01 dB/cm" and whose check loss is below 0.05 dB/cm (about 3 x that residue) gets no verdict.
export const CHECK_FLOOR=0.05;
export const UNRESOLVED_TEXT=`PML check: no leakage resolved (both solves below ${CHECK_FLOOR} dB/cm)`;
export const UNRESOLVED_HELP='The check solve (strength 6) leaves a larger residue than the run\'s solve on tiny losses: below the display floor the check says only that no leakage is resolved; it does not certify independence.';
/** The verdict of one mode: {status: independent | depends | unresolved | not_found, text, title}.
 * status: the first solve's attenuation_status (numerically_unresolved reads as below the floor). */
export function checkVerdict(re,im,paired,lambda0,status=null){
 if(!paired)return {status:'not_found',text:'Not found in the check solve',title:NOT_FOUND_HELP};
 const l1=dbPerCm(im,lambda0),l2=dbPerCm(paired.im,lambda0),dRe=paired.re-re,lossOk=lossIndependent(l1,l2),reOk=reIndependent(dRe);
 if(openLoss(im,lambda0,status).floor&&l2<CHECK_FLOOR)return {status:'unresolved',text:UNRESOLVED_TEXT,title:UNRESOLVED_HELP};
 const change=l1>=LOSS_FLOOR?percent(Math.abs(l2-l1)/Math.abs(l1)*100):null;
 if(lossOk&&reOk)return {status:'independent',text:change?`PML check: loss changes ${change}`:`PML check: loss changes less than ${LOSS_FLOOR} dB/cm`,title:CHECK_HELP};
 const what=!lossOk?`loss changes ${change??Math.abs(l2-l1).toPrecision(2)+' dB/cm'}`:`Re n_eff changes ${Math.abs(dRe).toExponential(1)}`;
 return {status:'depends',text:`Depends on the PML: ${what}`,title:DEPENDS_HELP};
}

/** The candidate record of a check solve's result (its own record: the check keeps every
 * candidate, whatever Studio would show). */
export const checkResultRecord=result=>checkCandidateRecord(result?.summary?.open_boundary?.[0],'The PML check');

// -- Compare -----------------------------------------------------------------------------------
export const boundaryName=run=>isOpenRun(run)?`(open, ${PML_WORDS})`:'(closed)';
export const COMPARE_LOSS_NOTE='A counts material absorption only; B also counts leakage. Their difference is not a leakage loss.';
export const COMPARE_LOSS_NOTE_BA='B counts material absorption only; A also counts leakage. Their difference is not a leakage loss.';

// -- a new result ------------------------------------------------------------------------------
/** The modes of a new open result that Studio keeps: Re n_eff above 1.45, in the engine's order.
 * {re, im, keep (the engine's indices), record (the candidate record of the first point), data
 * (the result with the vector samples of the kept modes only)}. Throws when no mode is kept. */
export function openResultValues(result,re,im,target){
 const record=checkCandidateRecord(result?.summary?.open_boundary?.[0],'This result');
 const keep=shownIndices(re);
 if(!keep.length)throw new Error(`No mode above n = ${SILICA_THRESHOLD} was found near n_eff ${target}. ${MOVE_TARGET_TEXT}`);
 const vf=result.vector_fields?.[0],pick=a=>Array.isArray(a)?keep.map(i=>a[i]):a;
 const data=vf?{...result,vector_fields:[{...vf,real:pick(vf.real),imag:pick(vf.imag)},...result.vector_fields.slice(1)]}:result;
 return {re:keep.map(i=>re[i]),im:keep.map(i=>im[i]),keep,record,data};
}
