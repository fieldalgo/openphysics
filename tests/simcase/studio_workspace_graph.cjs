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
