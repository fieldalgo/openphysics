// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

// The model builder as an ARIA tree (WAI-ARIA tree view pattern), for the optical, heat and Joule
// heating models and the multiphysics model alike. One role="tree" named "Model tree"; each node a
// <button role="treeitem"> with aria-level and, when it can be chosen, aria-selected; each group
// heading (Component 1, Physics, ...) a treeitem with aria-expanded that shows or hides its nodes.
// The flat markup carries the hierarchy in aria-level. One tab stop: the selected node, else the
// first; Up/Down move between visible items, Home/End to the first/last, Enter or Space selects a
// node (its click handler, unchanged) or opens and closes a group, Right opens a group or moves to
// its first node, Left closes a group or moves from a node to its parent (the item one level up).

export const TREE_NAME='Model tree';
const esc=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]);

/** The tree's opening tag: one role="tree" with its accessible name. */
export const treeOpen=()=>`<div role="tree" aria-label="${TREE_NAME}" class="model-tree">`;
/** A group heading: a treeitem at level 1 with aria-expanded, not itself selectable. */
// name: the key its open state is kept under; label: the words shown (default the name)
export function groupHeading(name,expanded=true,label=name){
 return `<button type="button" role="treeitem" class="tree-heading" aria-level="1" aria-expanded="${expanded}" data-tree-group="${esc(name)}" tabindex="-1"><span aria-hidden="true">${expanded?'▾':'▸'}</span>${esc(label)}</button>`;
}
/** The ARIA attributes of a node: level (1 for a node outside any group, 2 in a group, 3 indented
 * under another node) and whether it is the selected one. */
export const itemAttributes=(level,selected)=>`role="treeitem" aria-level="${level}" aria-selected="${selected?'true':'false'}" tabindex="-1"`;

// A key that names one item across redraws.
const keyOf=el=>el?.dataset.node!=null?'node:'+el.dataset.node:el?.dataset.mpNode!=null?'mp:'+el.dataset.mpNode:el?.dataset.treeGroup!=null?'group:'+el.dataset.treeGroup:null;
const find=(tree,key)=>[...tree.querySelectorAll('[role=treeitem]')].find(el=>keyOf(el)===key)||null;

/** The optical tree's Results group (round 14), as the multiphysics tree has one: a heading
 * "Results · run N" (N the run shown) over "Runs · N of M" (runsLabel), which opens Results, and,
 * with two runs or more, "Compare", which opens Compare. A node is selected while its page is
 * shown. '' without runs. */
export function resultsGroup({runs=0,shownRun=null,page,expanded=true,runsLabel}){
 if(!runs)return '';
 const nodes=[['results:runs',runsLabel,'▤',page==='Results'],...(runs>1?[['results:compare','Compare','⇆',page==='Compare']]:[])];
 return '<section class="tree-group" role="none">'+groupHeading('Results',expanded,`Results · run ${shownRun||runs}`)+nodes.map(([id,label,mark,selected])=>`<button type="button" data-node="${esc(id)}" ${itemAttributes(2,selected)}><span class="tree-node-mark" aria-hidden="true">${mark}</span>${esc(label)}</button>`).join('')+'</section>';
}
/** Collapsed groups of one tree, kept for the tab (not saved anywhere). */
export function treeState(){return {collapsed:new Set(),focusKey:null};}

/** Wires the tree in host after its markup is drawn: hides the nodes of collapsed groups, sets the
 * one tab stop, the keys and the group headings' toggle. redraw(): draws the tree again (after a
 * group opens or closes). The nodes' own click handlers are the caller's and stay as they are. */
export function bindTree(host,state,redraw){
 const tree=host.querySelector('[role=tree]');if(!tree)return;
 // the nodes of a collapsed group are hidden; the heading shows the state
 for(const heading of tree.querySelectorAll('.tree-heading')){
  const open=!state.collapsed.has(heading.dataset.treeGroup);
  heading.setAttribute('aria-expanded',String(open));heading.firstElementChild.textContent=open?'▾':'▸';
  for(const el of heading.closest('.tree-group')?.querySelectorAll('[role=treeitem]:not(.tree-heading),.tree-empty')||[])el.hidden=!open;
  heading.onclick=()=>{state.focusKey=keyOf(heading);if(open)state.collapsed.add(heading.dataset.treeGroup);else state.collapsed.delete(heading.dataset.treeGroup);redraw();};
 }
 const visible=()=>[...tree.querySelectorAll('[role=treeitem]')].filter(el=>!el.hidden);
 const items=visible();if(!items.length)return;
 // one tab stop: the selected node, else the first item; the arrows move it while the tree has the
 // focus, and it goes back to the selected node when the focus leaves the tree
 const home=()=>visible().find(el=>el.getAttribute('aria-selected')==='true')||visible()[0];
 const roving=target=>{for(const el of tree.querySelectorAll('[role=treeitem]'))el.tabIndex=el===target?0:-1;};
 roving(home());
 tree.addEventListener('focusout',event=>{if(!tree.contains(event.relatedTarget))roving(home());});
 const move=target=>{if(!target)return;roving(target);state.focusKey=keyOf(target);target.focus();};
 tree.addEventListener('focusin',event=>{const el=event.target.closest?.('[role=treeitem]');if(el){roving(el);state.focusKey=keyOf(el);}});
 tree.addEventListener('keydown',event=>{
  const current=event.target.closest?.('[role=treeitem]');if(!current||event.altKey||event.ctrlKey||event.metaKey)return;
  const list=visible(),i=list.indexOf(current),heading=current.classList.contains('tree-heading');
  const level=+current.getAttribute('aria-level')||1;
  let handled=true;
  switch(event.key){
   case 'ArrowDown':move(list[i+1]);break;
   case 'ArrowUp':move(list[i-1]);break;
   case 'Home':move(list[0]);break;
   case 'End':move(list.at(-1));break;
   case 'ArrowRight':
    if(heading&&current.getAttribute('aria-expanded')==='false')current.click();
    else if(heading&&+list[i+1]?.getAttribute('aria-level')>level)move(list[i+1]);
    break;
   case 'ArrowLeft':
    if(heading&&current.getAttribute('aria-expanded')==='true')current.click();
    else if(level>1){for(let j=i-1;j>=0;j--)if(+list[j].getAttribute('aria-level')<level){move(list[j]);break;}}
    break;
   case 'Enter':case ' ':state.focusKey=keyOf(current);current.click();break;
   default:handled=false;
  }
  if(handled)event.preventDefault();
 });
 // a native button would click again on the Space keyup
 tree.addEventListener('keyup',event=>{if(event.key===' '&&event.target.closest?.('[role=treeitem]'))event.preventDefault();});
}
/** Before a redraw of the tree: remembers the focused item so the redraw can put the focus back. */
export function treeFocus(host,state){const el=document.activeElement;if(el&&host.contains(el)&&el.getAttribute('role')==='treeitem'){state.focusKey=keyOf(el);return true;}return false;}
/** After a redraw: the focus back on the same item, when the tree had it. */
export function restoreTreeFocus(host,state,had){if(!had)return;const el=find(host,state.focusKey);if(el&&!el.hidden)el.focus({preventScroll:true});}
