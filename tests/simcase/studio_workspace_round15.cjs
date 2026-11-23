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
