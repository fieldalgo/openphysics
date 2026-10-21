// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Real shipped-page scenario for heat documents with material regions: the shipped
// steady and transient region examples through the installed server. No fake API,
// result injection or renderer mutation.
import assert from 'node:assert/strict';
import {writeFile} from 'node:fs/promises';
import {join} from 'node:path';

export async function regionScenario({cdp, click, wait, sleep, snapshot, report, steadyModel, transientModel, out}) {
  const evidence = report.regions = {status: 'incomplete', stages: [], steady: {}, transient: {}};
  await wait(() => cdp.eval('thermalController.state().cap?.regions?.run_enabled===true'
    + '&&transientController.state().cap?.regions?.run_enabled===true'), 'region capability');

  async function painted(name, canvas) {
    const before = report.stages.length;
    await snapshot('region-'+name, canvas);
    assert.equal(report.stages.length, before+1);
    evidence.stages.push(report.stages.pop());
  }
  async function apply(model) {
    await click('[data-tab="json"]');
    await cdp.eval('(()=>{const e=document.querySelector("#json");e.value='+JSON.stringify(JSON.stringify(model, null, 2))
      +';e.dispatchEvent(new Event("input",{bubbles:true}));return true})()');
    await click('#applyJson');
  }
  // A real mouse move over the field canvas at a point in document length units.
  async function hover(modelExpression, x, y) {
    const at = await cdp.eval('(()=>{const m='+modelExpression+',c=document.querySelector("#fieldCanvas"),r=c.getBoundingClientRect();'
      + 'const t=ThermalStudio.transform(m,r.width,r.height);return {x:r.left+t.X('+x+'),y:r.top+t.Y('+y+')}})()');
    await cdp.call('Input.dispatchMouseEvent', {type: 'mouseMoved', x: at.x, y: at.y});
    await sleep(200);
    return cdp.eval('document.querySelector("#resInfo").textContent');
  }
  const legend = () => cdp.eval('(()=>{const l=document.querySelector("#meshLegend .region-list");'
    + 'return l?{count:l.children.length,text:l.textContent,info:document.querySelector("#meshInfo").textContent}:null})()');
  const regionTable = () => cdp.eval('(()=>{const t=document.querySelector("#resTable").lastElementChild;'
    + 'return t&&t.tagName==="TABLE"?{className:t.className,rows:t.tBodies[0].rows.length,'
    + 'header:Array.from(t.tHead.rows[0].cells).map(c=>c.textContent)}:null})()');

  // Steady region example.
  const steadyName = JSON.stringify(steadyModel.name);
  const validated = () => cdp.eval('thermalController.supports(doc)&&doc.name==='+steadyName
    + '&&thermalController.gate.validated?.name==='+steadyName
    + '&&!thermalController.gate.dirty&&!thermalController.gate.busy&&!document.querySelector("#runBtn").disabled');
  await apply(steadyModel);
  await wait(validated, 'steady region model validated');
  await click('#validate');
  await wait(validated, 'explicit steady region validation');
  await click('#runBtn');
  await wait(() => cdp.eval('document.querySelector("#status").textContent==="steady thermal result ready"'), 'steady region result');
  evidence.steady.payload = await cdp.eval('(()=>{const p=thermalController.result();return {payloadFormat:p.payload_format,'
    + 'resultFormat:p.result_format,regions:p.regions.rows.map(r=>[r.name,r.material,r.cells])}})()');
  assert.equal(evidence.steady.payload.payloadFormat, 'studio-thermal-steady-regions-v1');
  await painted('steady-temperature', '#fieldCanvas');
  await click('[data-tab="mesh"]');
  await painted('steady-mesh', '#meshCanvas');
  evidence.steady.legend = await wait(legend, 'steady region legend');
  assert.equal(evidence.steady.legend.count, 3);
  assert.ok(evidence.steady.legend.text.includes('heater — copper'), 'legend names the heater and its material');
  assert.match(evidence.steady.legend.info, /, 3 regions; axes /);
  await click('[data-tab="results"]');
  await painted('steady-results-return', '#fieldCanvas');
  evidence.steady.table = await regionTable();
  assert.ok(evidence.steady.table, 'region table is the last child of #resTable');
  assert.equal(evidence.steady.table.rows, 3);
  evidence.steady.hover = await hover('ThermalStudio.viewModel(thermalController.result(),'
    + 'document.querySelector("#thermalField").value||"temperature_k")', 20, 8);
  assert.ok(evidence.steady.hover.includes('region heater (copper)'), 'hover names the heater');

  // A dirty edit clears every view, the legend and the region table included.
  await click('[data-tab="json"]');
  await cdp.eval('(()=>{const e=document.querySelector("#json");e.value+=" ";e.dispatchEvent(new Event("input",{bubbles:true}));return true})()');
  const dirty = () => cdp.eval('(()=>{const c=document.querySelector("#fieldCanvas");return {'
    + 'cleared:c.width===0||c.height===0||!c.getContext("2d").getImageData(0,0,c.width,c.height).data.some((v,i)=>i%4===3&&v!==0),'
    + 'resultAbsent:thermalController.result()===null,runDisabled:document.querySelector("#runBtn").disabled,'
    + 'labelsReset:document.querySelector("#resInfo").textContent==="no results available"'
    + '&&["meshInfo","meshLegend"].every(id=>document.getElementById(id).textContent===""),'
    + 'tableCleared:document.querySelector("#resTable").children.length===0,hoverAbsent:c.onmousemove===null}})()');
  evidence.steady.dirtyHidden = await dirty();
  await click('[data-tab="results"]');await sleep(300);
  evidence.steady.dirtyReturned = await dirty();
  for (const state of [evidence.steady.dirtyHidden, evidence.steady.dirtyReturned])
    for (const [key, value] of Object.entries(state)) assert.equal(value, true, 'dirty steady region view: '+key);

  // Transient region example.
  await apply(transientModel);
  await wait(() => cdp.eval('!document.querySelector("#runBtn").disabled'), 'transient region apply');
  await click('#validate');
  await wait(() => cdp.eval('!document.querySelector("#runBtn").disabled'), 'transient region validate');
  await click('#runBtn');
  await wait(() => cdp.eval('!!transientController.state().frame&&!transientController.state().readActive'), 'transient region frame');
  evidence.transient.manifest = await cdp.eval('(()=>{const m=transientController.result();return {payloadFormat:m.payload_format,'
    + 'resultFormat:m.result_format,times:m.time_s.length,regions:m.regions.rows.map(r=>[r.name,r.material,r.cells])}})()');
  assert.equal(evidence.transient.manifest.payloadFormat, 'studio-thermal-transient-regions-v1');
  await sleep(300);
  evidence.transient.label = await cdp.eval('document.querySelector("#resInfo").textContent');
  assert.match(evidence.transient.label,
    /^Saved index (\d+); t = (\S+) s; (\S+) \[([^\]]+)\]; current-frame raw (\S+) … (\S+); colours rescale per frame$/);
  await painted('transient-temperature', '#fieldCanvas');
  evidence.transient.table = await regionTable();
  assert.ok(evidence.transient.table && evidence.transient.table.rows === 2, 'transient region table');
  assert.ok(evidence.transient.table.header.includes('ρc [J/(m³·K)]'));
  await click('[data-tab="mesh"]');
  await painted('transient-mesh', '#meshCanvas');
  evidence.transient.legend = await wait(legend, 'transient region legend');
  assert.equal(evidence.transient.legend.count, 2);
  await click('[data-tab="results"]');
  await painted('transient-results-return', '#fieldCanvas');
  evidence.transient.hover = await hover('(()=>{const s=transientController.state();'
    + 'return TransientThermalStudio.model(transientController.result(),s.frame,s.view)})()', 5, 2.5);
  assert.ok(evidence.transient.hover.includes('region steel_plate (steel)'), 'hover names the steel plate');
  const png = await cdp.call('Page.captureScreenshot', {format: 'png'});
  await writeFile(join(out, 'region-final.png'), Buffer.from(png.data, 'base64'));
  evidence.status = 'passed';
}
