// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Round 15: the run banner's timing and place, the n_g hint above the modes table, the group-index
// and material words, both shares of a hybrid mode, the Library words, the wavelength chip's name,
// the tree warning badge's name and the Save As note. Plain text comparison only: no RegExp is built
// from a dynamic string.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const read=name=>fs.readFileSync(path.join(__dirname,STATIC,name),'utf8');
let M,A,W;
test.before(async()=>{M=await import(STATIC+'workspace-modes.mjs');A=await import(STATIC+'workspace-applications.mjs');W=await import(STATIC+'workspace-match.mjs');});

test('R2: the complete banner leaves after 6 s or at the next pointer press, key press or click',()=>{
 const app=read('workspace-app.mjs');
 assert.ok(app.includes('const DONE_BANNER_MS=6000;'));
 assert.ok(app.includes("for(const type of ['pointerdown','keydown','click'])document.addEventListener(type,()=>{if(jobPhase==='done')dismissDoneBanner();},true);"));
 assert.ok(app.includes("doneBannerTimer=state.phase==='done'?setTimeout(dismissDoneBanner,DONE_BANNER_MS):0;"));
 // only the complete phase is dismissed; Messages keeps the words (announceResult is unchanged)
 assert.ok(app.includes("function dismissDoneBanner(){clearTimeout(doneBannerTimer);doneBannerTimer=0;if(jobPhase!=='done')return;jobPhase='idle';refreshJobControls();}"));
 assert.ok(app.includes("if(state.phase==='done')announceResult(state.message);"));
});

test('R3: the modes table header reads n_g; the hint is a line above the table',()=>{
 const app=read('workspace-app.mjs'),css=read('workspace.css');
 assert.ok(app.includes("cell('th','n_g',{scope:'col',title:groupIndexHelp()}));"));
 assert.ok(app.includes("if(!hasGroupIndex(run))box.append(groupIndexHintLine('modes-table-hint'));"));
 assert.ok(!app.includes('groupIndexHeader'),'no hint inside a header');
 assert.ok(!css.includes('.th-hint'));
 assert.ok(css.includes('.modes-table .table-hint{'));
 assert.equal(M.GROUP_INDEX_HINT,'Off · turn on in Study or Optical modes');
});

test('R4: the group-index note names the material dispersion; Material data names physmat',()=>{
 assert.ok(M.GROUP_INDEX_NOTE.endsWith(' n_g includes the dispersion of the materials (evaluated at λ ± 1 nm).'));
 assert.equal(M.OPTICAL_MATERIAL_DATA,'physmat materials, evaluated at each wavelength solved');
 const app=read('workspace-app.mjs');
 assert.ok(app.includes("pair('Material data',OPTICAL_MATERIAL_DATA)"));
 assert.ok(!app.includes('Refractive indices at this wavelength'));
 // every material Studio's optical model offers is a physmat record
 const shapes=read('workspace-shapes.mjs'),line=shapes.split('\n').find(l=>l.startsWith('export const SHAPE_MATERIALS='));
 const refs=[...line.matchAll(/:'([^']*)'/g)].map(m=>m[1]);
 assert.ok(refs.length>=10&&refs.every(r=>r.startsWith('physmat:')),refs.join(','));
});

test('R5: a hybrid cell names both shares, which add to 100.0; TE-like and TM-like are unchanged',()=>{
 assert.equal(M.polarizationShare(.217),'21.7 % TE / 78.3 % TM');
 assert.equal(M.polarizationShare(.5),'50.0 % TE / 50.0 % TM');
 assert.equal(M.polarizationShare(.10001),'10.0 % TE / 90.0 % TM');
 assert.equal(M.polarizationShare(.12345),'12.3 % TE / 87.7 % TM');
 assert.equal(M.polarizationShare(.98213),'98.2 % TE');
 assert.equal(M.polarizationShare(.0315),'96.9 % TM (3.1 % TE)');
 for(let k=1001;k<9000;k++){const f=k/10000;assert.equal(M.polarizationWord(f),'hybrid');
  const text=M.polarizationShare(f),at=text.indexOf(' % TE / ');assert.ok(at>0&&text.endsWith(' % TM'),text);
  const te=text.slice(0,at),tm=text.slice(at+' % TE / '.length,-' % TM'.length);
  assert.equal(te+' % TE',M.tePercent(f));assert.equal(te,te.match(/^\d+\.\d$/)?.[0]);assert.equal(tm,tm.match(/^\d+\.\d$/)?.[0]);
  assert.equal(Number(te)*10+Number(tm)*10,1000,text);}
 const {rows}=M.modeTableRows([{re:2.1,im:0,fte:.217,loss:null}]);
 assert.equal(rows[0].polarization.text,'hybrid · 21.7 % TE / 78.3 % TM');
 // Compare reads the modes table's words
 const run={effective_index:[2.1],te_polarization_fraction:[.217],effective_area:[null],field:null,input:{model:{coreMesh:40}}};
 assert.equal(M.opticalModes(run)[0].fte,.217);
 assert.equal(W.unitPolarization(run,[0]),'hybrid · 21.7 % TE / 78.3 % TM');
});

test('R7: the Library statuses say what the model is, not "Live"',()=>{
 assert.deepEqual(A.APPLICATIONS.map(a=>a.status),['Optical mode solver','Heat conduction solver','Electric current and heat solver']);
 for(const app of [...A.APPLICATIONS,...A.COUPLED_TEMPLATES])assert.ok(!app.status.includes('Live'),app.status);
});

test('R8: the wavelength chip is a button named "Wavelength 1550 nm, edit"',()=>{
 const app=read('workspace-app.mjs');
 assert.ok(app.includes("chip=document.createElement('button');chip.type='button';chip.id='workflow-wavelength';"));
 assert.ok(app.includes("chip.setAttribute('aria-label',`Wavelength ${step.wavelength?step.wavelength.slice(2):''}, edit`);"));
});

test('R9: the tree warning badge names the physics and the problem as an image',()=>{
 const view=read('workspace-multiphysics-view.mjs');
 assert.ok(view.includes("const words=esc(`${physicsLabel(n)}: ${warned.get(n)}`);return `<span class=\"warn-badge\" role=\"img\" title=\"${words}\" aria-label=\"${words}\">!</span>`;"));
});

test('R10: each Library choice says what it does',()=>{
 // round 16 (S10): the button reads Open model; the description line says the runs stay
 assert.equal(A.CARD_OPEN_TEXT,'Open model');assert.equal(A.CARD_STAY_TEXT,'Runs stay in this tab until you close it.');
 assert.equal(A.CARD_START_NEW_TEXT,'Start new (no runs)');
 assert.equal(A.RESUME_NOT_NOW_TEXT,'Not now (choose a model below)');
 assert.equal(A.RESTORE_TEXT,'Restore from this browser');
 const src=read('workspace-applications.mjs');
 assert.ok(src.includes("action.className='card-action';action.textContent=CARD_OPEN_TEXT;"));
 assert.ok(src.includes("fresh.id=key+'-start-new';fresh.textContent=CARD_START_NEW_TEXT;"));
 assert.ok(src.includes("fresh.id='resume-start-new';fresh.textContent=RESUME_NOT_NOW_TEXT;"));
});

test('R1: the Save As name dialog says where later saves go (round 16 S11: this browser cannot write to the file)',()=>{
 const app=read('workspace-app.mjs');
 assert.ok(app.includes("(saveAs?' '+DOWNLOAD_SAVE_AS_NOTE:"));
 assert.ok(app.includes("const DOWNLOAD_SAVE_AS_NOTE='This browser cannot write to the file, so later saves download again under this name and may add “ (1)”.';"));
 assert.ok(!app.includes('Chrome and Edge save to the same file'));
});
