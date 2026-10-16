// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Real shipped-page scenario. No fake API, result injection or renderer mutation.
import assert from 'node:assert/strict';
import {writeFile} from 'node:fs/promises';
import {join} from 'node:path';
import {assertCurrentFrameRange, assertHistoryObservation} from './transient_studio_observations.mjs';

export async function transientScenario({cdp, click, wait, sleep, snapshot, report, model, out}) {
  const evidence = report.transient = {status: 'incomplete', stages: [], frames: [], histories: []};
  await wait(() => cdp.eval('transientController?.state().cap?.run_enabled===true'), 'transient capability');
  await click('[data-tab="json"]');
  await cdp.eval('(()=>{const e=document.querySelector("#json");e.value='+JSON.stringify(JSON.stringify(model,null,2))+';e.dispatchEvent(new Event("input",{bubbles:true}));return true})()');
  await click('#applyJson');
  await wait(() => cdp.eval('!document.querySelector("#runBtn").disabled'), 'transient apply');
  await click('#validate');
  await wait(() => cdp.eval('!document.querySelector("#runBtn").disabled'), 'transient validate');
  await click('#runBtn');
  await wait(() => cdp.eval('!!transientController.state().frame&&!transientController.state().readActive'), 'transient final frame');
  const manifest = await cdp.eval('transientController.result()');
  assert.deepEqual(manifest.time_s, model.study.time_s, 'exact requested stored times');
  assert.equal(manifest.default_frame_index, manifest.time_s.length-1);
  evidence.manifest = manifest;

  async function painted(name, canvas='#fieldCanvas') {
    const before = report.stages.length;
    await snapshot('transient-'+name, canvas);
    assert.equal(report.stages.length, before+1);
    evidence.stages.push(report.stages.pop());
  }
  async function inspect(index, view) {
    await wait(() => cdp.eval('(()=>{const s=transientController.state();return !!s.frame&&!s.readActive&&s.index==='+index+'&&s.view==='+JSON.stringify(view)+'})()'), 'selected transient frame');
    await sleep(300);
    const actual = await cdp.eval('(()=>{const s=transientController.state();return {frame:s.frame,index:s.index,view:s.view,label:document.querySelector("#resInfo").textContent,selected:document.querySelector("#transientTime").value}})()');
    const parsed = actual.label.match(/^Saved index (\d+); t = (\S+) s; (\S+) \[([^\]]+)\]; current-frame raw (\S+) … (\S+); colours rescale per frame$/);
    assert.ok(parsed, 'raw current-frame time/range label');
    assert.equal(Number(parsed[1]), index); assert.equal(Number(actual.selected), index);
    assert.equal(parsed[3], view);
    const field = view==='temperature_k' ? view : 'heat_flux_w_m2';
    const requests = report.http.filter(x => {
      const u=new URL(x.url);return u.pathname.endsWith('/frame')&&u.searchParams.get('field')===field&&u.searchParams.get('time_index')===String(index)&&x.status===200;
    });
    assert.ok(requests.length, 'actual successful selected frame HTTP');
    const query = new URL(requests.at(-1).url).searchParams;
    assert.equal(query.get('result_id'), manifest.result_id);
    assertCurrentFrameRange(manifest,actual.frame,{field,timeIndex:index,frameSeq:Number(query.get('frame_seq')),shownTimeS:Number(parsed[2]),component:view},
      {minimum:Number(parsed[5]),maximum:Number(parsed[6]),unit:parsed[4],rangePolicy:'current-frame'});
    evidence.frames.push(actual);
  }
  async function select(index, view) {
    await cdp.eval('(()=>{const field=document.querySelector("#thermalField"),time=document.querySelector("#transientTime");field.value='+JSON.stringify(view)+';time.value='+index+';time.dispatchEvent(new Event("change",{bubbles:true}));return true})()');
    await inspect(index,view);
  }
  const last=manifest.time_s.length-1;
  await inspect(last,'temperature_k'); await painted('temperature-final');
  await select(0,'temperature_k'); await painted('temperature-initial');
  const middle=Math.floor(last/2);
  if(middle!==0&&middle!==last){await select(middle,'temperature_k');await painted('temperature-middle');}
  for(const view of ['qx','qy','magnitude']){await select(last,view);await painted(view);}

  const stop=Math.min(16,manifest.time_s.length);
  for(const [field,button,host] of [['heat_content_j_per_m','#transientReadH','#transientH'],['quadratic_functional_jk_per_m','#transientReadV','#transientV']]){
    await cdp.eval('document.querySelector("#transientPageStart").value="0"');
    await click(button);
    await wait(() => cdp.eval('!transientController.state().readActive&&!!transientController.state().pages['+JSON.stringify(field)+']'), 'explicit history page');
    const page=await cdp.eval('transientController.state().pages['+JSON.stringify(field)+']');
    const request=report.http.filter(x=>{const u=new URL(x.url);return u.pathname.endsWith('/history')&&u.searchParams.get('field')===field&&x.status===200;}).at(-1);
    assert.ok(request,'actual history HTTP'); const query=new URL(request.url).searchParams;
    assert.equal(query.get('result_id'),manifest.result_id);
    assertHistoryObservation(manifest,page,{field,start:0,stop,frameSeq:Number(query.get('frame_seq'))});
    const rows=await cdp.eval('Array.from(document.querySelectorAll('+JSON.stringify(host+' tr')+')).map(row=>Array.from(row.children).map(cell=>cell.textContent))');
    assert.equal(rows.length,stop);
    for(let i=0;i<stop;i++){
      assert.match(rows[i][0],new RegExp('^index '+i+'(?: \\(current frame\\))?$'));
      assert.equal(rows[i][1],'t = '+manifest.time_s[i]+' s');
      assert.equal(rows[i][2],String(page.arrays[field][i])+' '+page.unit);
    }
    evidence.histories.push({page,rows});
  }
  await click('[data-tab="mesh"]');await painted('mesh','#meshCanvas');
  await click('[data-tab="results"]');await painted('results-return');

  // A real GET is dispatched, then dirty input invalidates ownership in the SAME
  // JS task, before its asynchronous response can install a frame. Do not fake
  // response bodies or invoke production callbacks directly.
  await click('[data-tab="json"]');
  const beforeReads=report.http.filter(x=>new URL(x.url).pathname.endsWith('/frame')).length;
  evidence.staleStart=await cdp.eval('(()=>{const time=document.querySelector("#transientTime");time.value="0";time.dispatchEvent(new Event("change",{bubbles:true}));const started=transientController.state().readActive;const e=document.querySelector("#json");e.value+=" ";e.dispatchEvent(new Event("input",{bubbles:true}));return {started,revision:transientController.state().revision}})()');
  assert.equal(evidence.staleStart.started,true,'real read was active before dirty edit');
  await wait(() => cdp.eval('!transientController.state().readActive'), 'obsolete real read finally');
  assert.ok(report.http.filter(x=>new URL(x.url).pathname.endsWith('/frame')).length>beforeReads,'obsolete request actually reached HTTP');
  async function dirtyState(){return cdp.eval('(()=>{const s=transientController.state(),c=document.querySelector("#fieldCanvas"),r=c.getBoundingClientRect();return {status:document.getElementById("status").textContent,resultAbsent:s.manifest===null,frameAbsent:s.frame===null,validationAbsent:transientController.snapshot()===null,historyAbsent:Object.keys(s.pages).length===0&&["transientH","transientV"].every(id=>document.getElementById(id).textContent===""),controlsHidden:document.getElementById("transientControls").hidden&&document.getElementById("transientHistory").hidden&&document.getElementById("thermalControls").hidden,runDisabled:document.getElementById("runBtn").disabled,hoverAbsent:c.onmousemove===null,legacyAbsent:meshData===null&&resultData===null&&currentJob===null,labelsReset:document.getElementById("resInfo").textContent==="no results available"&&["meshInfo","meshLegend"].every(id=>document.getElementById(id).textContent===""),cleared:c.width===0||c.height===0||!c.getContext("2d").getImageData(0,0,c.width,c.height).data.some((v,i)=>i%4===3&&v!==0),cssWidth:r.width,cssHeight:r.height,width:c.width,height:c.height}})()');}
  function requireDirty(state){assert.equal(state.status,'validate current transient JSON','dirty status must not retain reading/result-ready text');for(const key of ['resultAbsent','frameAbsent','validationAbsent','historyAbsent','controlsHidden','runDisabled','hoverAbsent','legacyAbsent','labelsReset','cleared'])assert.equal(state[key],true,key);}
  evidence.dirtyHidden=await dirtyState();requireDirty(evidence.dirtyHidden);
  await click('[data-tab="results"]');await sleep(300);
  evidence.dirtyReturned=await dirtyState();requireDirty(evidence.dirtyReturned);
  assert.ok(evidence.dirtyReturned.cssWidth>0&&evidence.dirtyReturned.cssHeight>0);
  const png=await cdp.call('Page.captureScreenshot',{format:'png'});
  await writeFile(join(out,'transient-dirty-results.png'),Buffer.from(png.data,'base64'));
  // An explicit second user run restores a real result. Then a browser-local
  // offline fault rejects an obsolete read; no fake response or result is used.
  await click('[data-tab="json"]');await click('#applyJson');
  await wait(()=>cdp.eval('!document.querySelector("#runBtn").disabled'),'explicit transient revalidation');
  await click('#runBtn');
  await wait(()=>cdp.eval('!!transientController.state().frame&&!transientController.state().readActive'),'second real transient result');
  assert.notEqual(await cdp.eval('transientController.result().result_id'),manifest.result_id);
  const failuresBefore=report.transportFailures.length;
  evidence.staleError={fault:'browser-local offline transport; no response body or physics injection'};
  try{
    await cdp.call('Network.emulateNetworkConditions',{offline:true,latency:0,downloadThroughput:-1,uploadThroughput:-1});
    evidence.staleError.started=await cdp.eval('(()=>{const time=document.querySelector("#transientTime");time.value="0";time.dispatchEvent(new Event("change",{bubbles:true}));const started=transientController.state().readActive;const e=document.querySelector("#json");e.value+=" ";e.dispatchEvent(new Event("input",{bubbles:true}));return started})()');
    assert.equal(evidence.staleError.started,true);
    await wait(()=>cdp.eval('!transientController.state().readActive'),'obsolete failed read finally');
    await wait(()=>report.transportFailures.length>failuresBefore,'actual browser transport failure');
  }finally{
    await cdp.call('Network.emulateNetworkConditions',{offline:false,latency:0,downloadThroughput:-1,uploadThroughput:-1});
  }
  evidence.staleError.failures=report.transportFailures.slice(failuresBefore);
  await click('[data-tab="json"]');evidence.staleError.hidden=await dirtyState();requireDirty(evidence.staleError.hidden);
  await click('[data-tab="results"]');await sleep(300);
  evidence.staleError.returned=await dirtyState();requireDirty(evidence.staleError.returned);
  assert.ok(evidence.staleError.returned.cssWidth>0&&evidence.staleError.returned.cssHeight>0);
  const errorPng=await cdp.call('Page.captureScreenshot',{format:'png'});
  await writeFile(join(out,'transient-error-dirty-results.png'),Buffer.from(errorPng.data,'base64'));
  evidence.status='passed';
}
