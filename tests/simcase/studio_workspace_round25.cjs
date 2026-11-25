// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Round 25: usability fixes of the optical model (A1 to A4, pre-registered P1 to P4).
// Plain text comparison only: no RegExp is built from a dynamic string.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const read=name=>fs.readFileSync(path.join(__dirname,STATIC,name),'utf8');

test('P3 (A3): a named pair read from a file is kept because it is named, so the newest-pair offer appears',async()=>{
 const C=await import(STATIC+'workspace-compare.mjs');
 const runs=[1,2,3].map(n=>({job:'j'+n,number:n,...(n<3?{label:'Design '+'AB'[n-1]}:{})}));
 const named=['j1','j2'];
 // read from a file: the named pair is not the default one, yet not picked by hand
 assert.equal(C.pairChosen(runs,named),false);
 // an unnamed pair that is not the default, or a pair with one named run: picked, as before
 const plain=[1,2,3].map(n=>({job:'j'+n,number:n,label:''}));
 assert.equal(C.pairChosen(plain,['j1','j2']),true);
 assert.equal(C.pairChosen([{job:'j1',label:'Design A'},{job:'j2',label:''},{job:'j3',label:''}],['j1','j2']),true);
 // the default pair is never picked; one named run on both sides is not a named pair
 assert.equal(C.pairChosen(runs,['j2','j3']),false);
 assert.equal(C.pairChosen(runs,['j1','j1']),true);
 // one new run after the file: the pair stays (named) and Compare offers the two newest
 const after=[...runs,{job:'j4',number:4,label:''}],picked=C.pairChosen(runs,named);
 assert.deepEqual(C.comparisonAfterRun(after,named,picked),named);
 assert.deepEqual(C.newestPairOffer(after,named,picked),['j3','j4']);
 // the page reads a file's pair through pairChosen, unchanged in shape
 assert.ok(read('workspace-app.mjs').includes('compareIds=[...session.comparison];comparePicked=pairChosen(runs,compareIds);'));
});

