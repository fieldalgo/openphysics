// Copyright 2026 Yongha Kim (FieldAlgo); SPDX-License-Identifier: Apache-2.0
const test=require('node:test');const assert=require('node:assert/strict');
const graph=import('../../packages/simcase/src/simcase/studio/static/workspace-graph.mjs');
const all={electric:true,heat:true,structure:true,optics:true};
test('removing a thermal interface removes all dependent field-transfer wires',async()=>{
 const {graphConnections}=await graph;
 assert.equal(graphConnections(all).length,4);
 assert.deepEqual(graphConnections({...all,heat:false}),[]);
 assert.deepEqual(graphConnections({...all,structure:false}).map(e=>e.slice(0,2)),[
  ['electric-out','heat-in'],['heat-out','optical-in']]);
 assert.deepEqual(graphConnections({...all,optics:false}).map(e=>e.slice(0,2)),[
  ['electric-out','heat-in'],['heat-out','mechanical-in']]);
});
test('every displayed wire terminates on a named rendered socket, including optional branches',async()=>{
 const {graphConnections,renderConnectionGraph}=await graph;
 for(const state of [all,{...all,heat:false},{...all,structure:false},{...all,optics:false}]){
  const html=renderConnectionGraph(state,'Heat transfer',[]);
  const ports=[...html.matchAll(/data-port="([^"]+)"/g)].map(m=>m[1]);
  assert.equal(ports.length,new Set(ports).size);
  for(const [from,to] of graphConnections(state)){assert.ok(ports.includes(from));assert.ok(ports.includes(to));}
  assert.match(html,/Setup only · no coupled calculation/);
 }
});
test('curves retain exact socket endpoints and bounded return tangents for feedback-shaped routes',async()=>{
 const {curvePath}=await graph;
 for(const [a,b] of [[{x:274,y:100},{x:350,y:230}],[{x:920,y:380},{x:680,y:170}],[{x:920,y:380},{x:920,y:170}]]){
  const n=curvePath(a,b).match(/-?\d+(?:\.\d+)?/g).map(Number);
  assert.deepEqual(n.slice(0,2),[a.x,a.y]);assert.deepEqual(n.slice(-2),[b.x,b.y]);
  assert.equal(n[3],a.y);assert.equal(n[5],b.y);
  if(b.x<a.x){assert.ok(n[2]<=a.x+24);assert.ok(n[4]>=b.x-24);}
 }
});
test('the Joule heating graph wires Joule heat always and the σ(T) feedback only for temperature-dependent materials',async()=>{
 const {jouleConnections,renderJouleGraph}=await graph;
 assert.deepEqual(jouleConnections(false).map(e=>e.slice(0,2)),[['electric-out','heat-in']]);
 assert.deepEqual(jouleConnections(true).map(e=>e.slice(0,2)),[['electric-out','heat-in'],['heat-out','electric-sigma']]);
 assert.equal(jouleConnections(true)[1][4],'below');
 for(const [dependent,kind] of [[false,'joule.steady2d'],[true,'joule.temperature2d']]){
  const html=renderJouleGraph('Heat transfer',dependent,kind);
  const ports=[...html.matchAll(/data-port="([^"]+)"/g)].map(m=>m[1]);
  assert.equal(ports.length,new Set(ports).size);
  for(const [from,to] of jouleConnections(dependent)){assert.ok(ports.includes(from));assert.ok(ports.includes(to));}
  assert.equal(ports.includes('electric-sigma'),dependent);
  // Joule heating is a real coupled calculation: no setup-only badge, no interface toggles
  assert.doesNotMatch(html,/Setup only|data-toggle|Optical modes|Solid mechanics/);
  assert.match(html,new RegExp('Solved together · '+kind.replace('.','\\.')));
  const nodes=[...html.matchAll(/data-joule-node="([^"]+)"/g)].map(m=>m[1]);
  assert.deepEqual([...new Set(nodes)].sort(),['Electric currents','Heat transfer']);
  assert.match(html,/class="graph-node node-heat selected"/);
 }
});
test('a feedback loop leaves and enters its sockets horizontally and runs along the channel below',async()=>{
 const {loopPath}=await graph;
 const a={x:900,y:470},b={x:80,y:430},n=loopPath(a,b,520).match(/-?\d+(?:\.\d+)?/g).map(Number);
 assert.deepEqual(n.slice(0,2),[a.x,a.y]);assert.deepEqual(n.slice(-2),[b.x,b.y]);
 assert.equal(n[3],a.y);assert.ok(n[2]>a.x);assert.deepEqual(n.slice(6,8),[a.x,520]);
 assert.deepEqual(n.slice(8,10),[b.x,520]);assert.ok(n[12]<b.x);assert.equal(n[13],b.y);
});
