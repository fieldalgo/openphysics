// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Drive the actual shipped script with late server responses after thermal JSON import.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {test}=require('node:test');
const html=fs.readFileSync(process.env.SIMCASE_INDEPENDENT_HTML || path.join(__dirname,'../simcase/studio/static/index.html'),'utf8');
const thermal={openphysics:'0.2',name:'Imported thermal',units:{length:'mm',temperature:'K'},geometry:{domain:{xmin:0,xmax:30,ymin:0,ymax:20}},materials:{},physics:{heat:{type:'thermal.steady2d',conductivity_w_mk:12.5,heat_source_w_m3:100000,dirichlet_temperature_k:{left:280,right:315}}},mesh:{subdivisions:[4,4]},study:{type:'single'},results:{save_fields:true,plots:false}};
const em={openphysics:'0.2',name:'Old EM',units:{length:'um'},geometry:{domain:{xmin:0,xmax:1,ymin:0,ymax:1},background:{material:'vacuum'},shapes:[]},materials:{},physics:{em1:{type:'em.modes2d',wavelength:1.55,num_modes:1,formulation:'scalar',boundary:{}}},mesh:{size:.2},study:{type:'single'},results:{plots:false}};
function page(){
  const elements=new Map();
  const canvas=new Proxy({}, {get:(t,k)=>t[k]||(()=>{}),set:(t,k,v)=>{t[k]=v;return true;}});
  function element(id){
    if(!elements.has(id))elements.set(id,{value:'',innerHTML:'',textContent:'',hidden:false,disabled:false,width:640,height:400,style:{},children:[],classList:{toggle(){},add(){},remove(){}},appendChild(v){this.children.push(v);},querySelectorAll:()=>[],getContext:()=>canvas,getBoundingClientRect:()=>({width:640,height:400}),addEventListener(){}});
    return elements.get(id);
  }
  const ctx=vm.createContext({document:{getElementById:element,querySelectorAll:()=>[],createElement:()=>({})},window:{devicePixelRatio:1,addEventListener(){}},fetch:()=>new Promise(()=>{}),setTimeout:cb=>cb(),console});
  vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1],ctx);
  vm.runInContext(`doc=${JSON.stringify(em)};`,ctx);
  return {element,ctx,run:code=>vm.runInContext(code,ctx)};
}
async function applyThermal(p){
  p.element('json').value=JSON.stringify(thermal);
  await p.element('applyJson').onclick();
  assert.equal(p.run('Object.values(doc.physics)[0].type'),'thermal.steady2d','raw imported document must remain available');
}
function deferred(){let resolve;const promise=new Promise(r=>{resolve=r;});return {promise,resolve};}
const oldResult={nodes:[[0,0],[1,0],[0,1]],triangles:[[0,1,2]],fields:[[[1,2,3]]],vector_fields:null,parameter:null,values:[1.55],neff:[[1.5]],summary:{units:{length:'um'}},timings:{},group_index:null};

test('late completed EM result cannot repopulate after thermal import',async()=>{
  const p=page(),late=deferred(),ready=deferred();
  p.ctx.post=async(url)=>url==='/api/validate'?{ok:false,error:'headless-only'}:{job:'old-job'};
  p.ctx.get=async(url)=>{if(url.endsWith('/result')){ready.resolve();return late.promise;}return {status:'done',log:[]};};
  p.run('api.post=post;api.get=get;');
  const running=p.run('doRun()');await ready.promise;await applyThermal(p);
  late.resolve(oldResult);await running;
  assert.equal(p.run('resultData'),null,'stale EM result must remain discarded');
});

test('late mesh cannot repopulate after thermal import',async()=>{
  const p=page(),late=deferred(),ready=deferred();
  p.ctx.post=async(url)=>{if(url==='/api/mesh'){ready.resolve();return late.promise;}return {ok:false,error:'headless-only'};};
  p.run('api.post=post;');const meshing=p.run('doMesh()');await ready.promise;await applyThermal(p);
  late.resolve({stats:{nodes:3,triangles:1,min_angle:45},nodes:[[0,0],[1,0],[0,1]],triangles:[[0,1,2]],region_names:[],region_materials:{}});await meshing;
  assert.equal(p.run('meshData'),null,'stale EM mesh must remain discarded');
});

test('late validation cannot replace imported thermal document',async()=>{
  const p=page(),late=deferred(),ready=deferred();let count=0;
  p.ctx.post=async()=>{if(count++===0){ready.resolve();return late.promise;}return {ok:false,error:'headless-only'};};
  p.run('api.post=post;');const validating=p.run('doValidate()');await ready.promise;await applyThermal(p);
  late.resolve({ok:true,doc:em,summary:'old valid EM',notes:[]});
  // The production renderer can fail while trying to restore old data; that is
  // not an excuse to replace the current document. Inspect state after delivery.
  await validating.catch(()=>{});
  assert.equal(p.run('Object.values(doc.physics)[0].type'),'thermal.steady2d','stale validation must not replace newer raw document');
});
