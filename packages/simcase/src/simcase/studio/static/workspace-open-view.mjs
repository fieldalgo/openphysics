// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

// The page parts of the open boundary (slice P2): the Outer boundary choice of Physics › Optical
// modes, the edge switch of Geometry › Boundaries, the Study summary and PML check option, and the
// Results parts of an open run (found line, PML check column, other candidates). HTML text or DOM
// nodes only; the page binds them.
import {BOUNDARY_CHOICES,OPEN_HELP,TARGET_HELP,PML_DETAILS,PML_WORDS,checkLabel,CHECK_NOTE,targetText,effectiveTarget,studySummary,openEdges,otherCandidates,otherCandidatesTitle,OTHER_CANDIDATES_NOTE,openFoundText,MOVE_TARGET_TEXT} from './workspace-open-run.mjs';
import {maxIndex,TARGET_FLOOR,hasOpenEdge} from './workspace-open-boundary.mjs';

const escape=text=>String(text).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]);
const pair=(a,b,id='')=>`<div class="pair"${id?` id="${id}"`:''}><span>${escape(a)}</span><strong>${escape(b)}</strong></div>`;
export const ALL_CLOSED_NOTE='Every edge is closed: a run is a closed window. Open an edge in Geometry › Boundaries.';

/** Physics › Optical modes: Outer boundary (Closed window / Open boundary), and with Open the
 * fixed PML, Search near n_eff and the fixed settings under Details. */
export function boundaryFieldHtml(ob,shapes){
 const open=!!ob,radio=(value)=>`<label class="radio-field"><input type="radio" name="outer-boundary" value="${value}"${(value==='open')===open?' checked':''}> ${escape(BOUNDARY_CHOICES[value])}</label>`;
 let html=`<fieldset class="boundary-choice" id="outer-boundary"><legend>Outer boundary</legend>${radio('closed')}${radio('open')}</fieldset><p class="input-note" id="open-boundary-help">${escape(OPEN_HELP)}</p>`;
 if(!open)return html;
 const nmax=maxIndex(shapes),t=effectiveTarget(ob,shapes);
 html+=pair('PML thickness',PML_WORDS,'pml-thickness')+`<label>Search near n_eff<input id="target-number" type="number" min="${TARGET_FLOOR}" max="${nmax}" step="0.001" value="${targetText(t)}" aria-describedby="target-help"></label><p class="input-note" id="target-help">${escape(TARGET_HELP)}</p>`;
 if(!hasOpenEdge(ob))html+=`<p class="input-note" id="all-edges-closed">${escape(ALL_CLOSED_NOTE)}</p>`;
 return html+`<details class="pml-details" id="pml-details"><summary>Details</summary><p>${escape(PML_DETAILS)}</p></details>`;
}
/** Study: the summary line and the PML check option (an open boundary only), else ''. */
export function studyOpenHtml(ob,shapes,checkOn,modeCount){
 const summary=studySummary(ob,shapes);if(!summary)return '';
 return `<p id="open-boundary-summary" class="next-run">${escape(summary)}</p><label class="check-field"><input id="pml-check" type="checkbox"${checkOn?' checked':''}> ${escape(checkLabel(modeCount))}</label><p class="input-note">${escape(CHECK_NOTE)}</p>`;
}
/** Geometry › Boundaries, an optical edge selected while Open boundary is chosen: its state and
 * the "Close this edge" switch. */
export function edgePanel(side,ob){
 const box=document.createElement('section');box.className='boundary-selection';
 const heading=document.createElement('h3'),note=document.createElement('p'),open=ob.edges[side]==='open';
 heading.textContent=`Optical ${side} boundary`+(open?' · Open (PML)':'');
 note.textContent=open?`${PML_WORDS} outside this edge: light that leaves the window here is absorbed. Shapes touching this edge continue through the layer.`:'PEC · fixed by the optical adapter. This edge is not a thermal boundary or a mechanical support.';
 const label=document.createElement('label');label.className='check-field';
 const input=document.createElement('input');input.type='checkbox';input.setAttribute('role','switch');input.id='close-edge';input.dataset.edge=side;input.checked=!open;input.setAttribute('aria-checked',String(!open));
 label.append(input,' Close this edge');box.append(heading,note,label);
 return box;
}
/** The found line of an open run: "Found 2 of 2 modes near n_eff 2.460." and the hint. */
export function foundLine(run){
 const p=document.createElement('p');p.id='modes-found';p.className='modes-found';
 p.textContent=openFoundText(run.effective_index.length,run.settings.mode_count,run.settings.pml.target)+'. '+MOVE_TARGET_TEXT;
 return p;
}
/** Other candidates (n) — not shown as modes: a disclosure with a table of n_eff, physical share
 * and reason; no field view. */
export function candidatesDisclosure(run){
 const rows=otherCandidates(run.open_boundary,run.effective_index,run.effective_index_im);
 const details=document.createElement('details');details.className='other-candidates';details.id='other-candidates';
 const summary=document.createElement('summary');summary.textContent=otherCandidatesTitle(rows.length);details.append(summary);
 const note=document.createElement('p');note.className='table-note';note.textContent=OTHER_CANDIDATES_NOTE;details.append(note);
 if(rows.length){
  const wrap=document.createElement('div');wrap.className='table-scroll';
  const table=document.createElement('table');table.id='other-candidates-table';
  const caption=document.createElement('caption');caption.textContent='Searched candidates not shown as modes';table.append(caption);
  const head=document.createElement('tr');for(const h of ['Candidate','n_eff','Physical share','Reason']){const th=document.createElement('th');th.scope='col';th.textContent=h;head.append(th);}
  const thead=document.createElement('thead');thead.append(head);table.append(thead);
  const body=document.createElement('tbody');
  for(const r of rows){const tr=document.createElement('tr');for(const [v,cls] of [[String(r.candidate),''],[r.neff,'num'],[r.share,'num'],[r.reason,'']]){const td=document.createElement('td');td.textContent=v;if(cls)td.className=cls;tr.append(td);}tr.dataset.candidate=String(r.candidate);body.append(tr);}
  table.append(body);wrap.append(table);details.append(wrap);
 }
 return details;
}
export {openEdges};
