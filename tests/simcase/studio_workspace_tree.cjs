// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// The model builder as an ARIA tree (workspace-tree.mjs): the markup helpers the optical, heat,
// Joule heating and multiphysics trees are drawn with. The keys and the drawn trees are checked
// in a real browser (tools/studio_browser), by role and accessible name.
const test=require('node:test');const assert=require('node:assert/strict');
const tree=import('../../packages/simcase/src/simcase/studio/static/workspace-tree.mjs');

test('round 10: one tree named "Model tree"; nodes are tree items with a level and a selection, one tab stop set when drawn',async()=>{
 const t=await tree;
 assert.equal(t.treeOpen(),'<div role="tree" aria-label="Model tree" class="model-tree">');
 assert.equal(t.itemAttributes(2,true),'role="treeitem" aria-level="2" aria-selected="true" tabindex="-1"');
 assert.equal(t.itemAttributes(3,false),'role="treeitem" aria-level="3" aria-selected="false" tabindex="-1"');
});
test('round 10: a group heading is a tree item at level 1 that opens and closes, not selectable; its name is escaped',async()=>{
 const t=await tree;
 const open=t.groupHeading('Component 1');
 assert.match(open,/^<button type="button" role="treeitem" class="tree-heading" aria-level="1" aria-expanded="true" data-tree-group="Component 1" tabindex="-1">/);
 assert.doesNotMatch(open,/aria-selected/);
 assert.match(t.groupHeading('Physics',false),/aria-expanded="false"/);
 assert.match(t.groupHeading('A & <B>'),/data-tree-group="A &amp; &lt;B&gt;"[^>]*><span aria-hidden="true">▾<\/span>A &amp; &lt;B&gt;<\/button>$/);
 const state=t.treeState();assert.ok(state.collapsed instanceof Set);assert.equal(state.collapsed.size,0);
});
