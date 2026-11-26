// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Library recovery after a restart (after rounds 26–30), as the Studio browser checks read it: one
// box with one button per piece of work (#resume-newest, at most one #resume-other), each with its
// detail line, older copies folded under the closed #earlier-copies, and model cards with a plain
// "Kept in this browser · N runs · Restore at the top of the page" line instead of restore buttons.
// Every function takes the page object of a check (page.eval, page.call) and a size function.
import assert from 'node:assert/strict';

// The Library as an agent sees it. Restore buttons are counted with checkVisibility(): the content of
// a closed <details> still has a box in Chromium. The Workspace tools footer is left out.
export const LIBRARY_RESTORE_STATE = `(()=>{
 const visible=[...document.querySelectorAll('button')].filter(b=>/^Restore/.test(b.textContent)&&b.checkVisibility()&&!b.closest('#workspace-tools'));
 const piece=id=>{const b=document.getElementById(id);if(!b)return null;const d=document.getElementById(b.getAttribute('aria-describedby')||'');
  return {text:b.textContent,detail:d?.textContent??null,describedBy:b.getAttribute('aria-describedby'),record:b.dataset.resumeRecord??null,pair:b.dataset.resumePair??null,primary:b.classList.contains('primary'),visible:b.checkVisibility()};};
 const box=document.getElementById('resume-box'),copies=document.getElementById('earlier-copies');
 return {visible:visible.map(b=>b.textContent),
  box:box?{open:box.open,heading:box.querySelector('summary')?.textContent??null,note:box.querySelector('.resume-note')?.textContent??null}:null,
  newest:piece('resume-newest'),other:piece('resume-other'),
  copies:copies?{open:copies.open,summary:copies.querySelector('summary')?.textContent??null,entries:[...copies.querySelectorAll('button')].map(b=>({text:b.textContent,record:b.dataset.resumeRecord,detail:b.nextElementSibling?.textContent??null}))}:null,
  cardLines:Object.fromEntries([...document.querySelectorAll('.cards [data-template]')].filter(c=>c.querySelector('.card-kept')).map(c=>[c.dataset.template,c.querySelector('.card-kept').textContent])),
  cardButtons:['resume-optical','resume-heated-waveguide','optical-start-new','heated-waveguide-start-new'].filter(id=>document.getElementById(id)),
  cardResume:document.querySelectorAll('.card-resume,.card-slot').length,
  openFile:[...document.querySelectorAll('#canvas button')].filter(b=>/^Open file…$/.test(b.textContent)).length,
  restoredSeparately:document.body.textContent.includes('restored separately')};
})()`;

export const libraryRestore = page => page.eval(LIBRARY_RESTORE_STATE);

// What holds in every state: no card restore buttons, one Open file…, no "(restored separately)",
// and card lines exactly for the given models ({template: runs}).
export function assertLibraryRestore(state, {visible, cards = {}}, tag) {
  const json = JSON.stringify(state);
  assert.equal(state.visible.length, visible, `${tag}: visible restore buttons ${json}`);
  assert.deepEqual(state.cardButtons, [], `${tag}: no card restore buttons`); assert.equal(state.cardResume, 0, tag);
  assert.equal(state.openFile, 1, `${tag}: one Open file…`); assert.equal(state.restoredSeparately, false, tag);
  const kept = runs => `Kept in this browser · ${runs} ${runs === 1 ? 'run' : 'runs'} · Restore at the top of the page`;
  assert.deepEqual(state.cardLines, Object.fromEntries(Object.entries(cards).map(([card, runs]) => [card, kept(runs)])), `${tag}: card lines ${json}`);
  if (state.newest) {
    assert.equal(state.newest.primary, true, tag); assert.equal(state.newest.describedBy, 'resume-newest-detail', tag);
    assert.ok(state.newest.text.startsWith('Restore newest from this browser: '), state.newest.text);
    assert.ok(state.newest.detail.startsWith('Kept in this browser '), state.newest.detail);
  }
  if (state.other) assert.ok(state.other.detail.startsWith('Older · kept in this browser '), state.other.detail);
  if (state.copies) {
    assert.equal(state.copies.summary, `Earlier copies in this browser (${state.copies.entries.length})`, tag);
    for (const e of state.copies.entries) { assert.ok(e.text.startsWith('Restore '), e.text); assert.ok(/^(?:Older copy|Copy without runs) · kept in this browser /.test(e.detail), e.detail); }
  }
}

// The first screen (round 9, tightened): at 1280 × 800 and 390 × 844 the bottoms of #resume-newest and
// #resume-newest-detail are at most the visible bottom of the Library pane (#canvas) and the viewport.
// size(width, height, mobile) sets the viewport; restore: the size to go back to.
export async function assertFirstScreen(page, size, tag, restore = [1440, 900, false]) {
  const out = {};
  for (const [width, height, mobile] of [[1280, 800, false], [390, 844, true]]) {
    await size(width, height, mobile); await new Promise(r => setTimeout(r, 400));
    const m = await page.eval(`(()=>{const c=document.getElementById('canvas');c.scrollTop=0;scrollTo(0,0);const q=id=>{const e=document.getElementById(id);return e?Math.round(e.getBoundingClientRect().bottom*10)/10:null};
      return {newest:q('resume-newest'),detail:q('resume-newest-detail'),pane:Math.round(c.getBoundingClientRect().bottom*10)/10,viewport:innerHeight,overflow:document.documentElement.scrollWidth-document.documentElement.clientWidth};})()`);
    out[width] = m;
    // the Library before any model holds runs: no horizontal overflow at either size
    assert.equal(m.overflow, 0, `${tag}: the Library overflows by ${m.overflow}px at ${width} × ${height}`);
    for (const key of ['newest', 'detail']) {
      assert.ok(m[key] !== null && m[key] <= m.pane && m[key] <= height, `${tag}: #resume-${key === 'newest' ? 'newest' : 'newest-detail'} bottom ${m[key]} at ${width} × ${height} (pane ${m.pane})`);
    }
  }
  await size(...restore); await new Promise(r => setTimeout(r, 300));
  return out;
}

// The accessible description of #resume-newest is its detail line (aria-describedby).
export async function assertNewestDescription(page, tag) {
  await page.call('Accessibility.enable').catch(() => {});
  const {root} = await page.call('DOM.getDocument', {depth: 0});
  const {nodeId} = await page.call('DOM.querySelector', {nodeId: root.nodeId, selector: '#resume-newest'});
  const {nodes} = await page.call('Accessibility.getPartialAXTree', {nodeId, fetchRelatives: false});
  const description = nodes[0]?.description?.value ?? null, detail = await page.eval("document.getElementById('resume-newest-detail').textContent");
  assert.equal(description, detail, `${tag}: the accessible description of #resume-newest`);
  return description;
}

// Amendment A1: Not now closes the box instead of hiding it. After it no restore button is visible on
// the Library, the heading is still in the first screen, and opening the box shows the same buttons.
export async function assertNotNow(page, tag) {
  const before = await libraryRestore(page);
  await page.eval("document.getElementById('resume-start-new').click()"); await new Promise(r => setTimeout(r, 300));
  const closed = await libraryRestore(page);
  const heading = await page.eval("(()=>{const s=document.querySelector('#resume-box>summary').getBoundingClientRect(),c=document.getElementById('canvas').getBoundingClientRect();return {bottom:s.bottom,pane:c.bottom,viewport:innerHeight}})()");
  assert.equal(closed.box?.open, false, `${tag}: Not now closes the box`); assert.deepEqual(closed.visible, [], `${tag}: no restore button after Not now`);
  assert.ok(heading.bottom <= heading.pane && heading.bottom <= heading.viewport, `${tag}: the heading stays in the first screen ${JSON.stringify(heading)}`);
  await page.eval("document.querySelector('#resume-box>summary').click()"); await new Promise(r => setTimeout(r, 300));
  const reopened = await libraryRestore(page);
  assert.equal(reopened.box?.open, true, tag); assert.deepEqual(reopened.visible, before.visible, `${tag}: the same buttons again`);
  return {before: before.visible, closed: closed.visible, heading, reopened: reopened.visible};
}
