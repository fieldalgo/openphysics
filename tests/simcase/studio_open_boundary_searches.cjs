// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Slice T2: the second search of an open run. The builder adds pml.pml_additional_searches (16 near
// t_low = (t + 1.444) / 2 to two decimals) from a target of 1.466; the run's record is the engine's
// /3, checked against its target; the words of two searches (field, Study, found line, candidates);
// a /2 run of P2 reads as before; the PML check searches once.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const fixture=name=>fs.readFileSync(path.join(__dirname,'studio_session_fixtures',name),'utf8');
let O,B,R,V;
test.before(async()=>{O=await import(STATIC+'workspace-optical.mjs');B=await import(STATIC+'workspace-open-boundary.mjs');R=await import(STATIC+'workspace-open-run.mjs');V=await import(STATIC+'workspace-open-view.mjs');});
const setup=()=>({materials:{Core:'Silicon',Oxide:'Silica',Heater:''}});
const STRIP={name:'Core',type:'rect',material:'Silicon',x:-250,y:0,w:500,h:220};
const state=(extra={})=>({height:220,width:500,wavelength:1550,coreMesh:30,electric:false,heat:false,structure:false,optics:true,shapes:[STRIP],...extra});
const ALL={left:'open',right:'open',bottom:'open',top:'open'};
const CLOSED={left:'closed',right:'closed',bottom:'closed',top:'closed'};

// -- W9 (blind) --------------------------------------------------------------------------------
test('W9: every edge closed is the optical-shapes-v8 document byte for byte, with 1, 2 and 8 modes and any target',()=>{
 for(const [n,file] of [[1,'optical-document-template-v8-1.json'],[2,'optical-document-template-v7.json'],[8,'optical-document-template-v8-8.json']])
  for(const target of [undefined,2.46,2.2,1.466,1.465])
   assert.equal(JSON.stringify(O.opticalDocument(state({modeCount:n,openBoundary:{edges:CLOSED,...(target===undefined?{}:{target})}}),setup())),fixture(file));
});
test('W9: t_low = (t + 1.444) / 2 to two decimals for the default target of each guiding material, and an edited one',()=>{
 // worked by hand: the default target (n + 1.444) / 2 to 0.01 (P1), then (t + 1.444) / 2 to 0.01
 const cases={Silicon:[2.46,1.95],'Sapphire (ordinary)':[1.60,1.52],'Silicon nitride':[1.72,1.58],'Lithium niobate (ordinary)':[1.83,1.64],
  'Indium phosphide':[2.30,1.87],'Gallium arsenide':[2.41,1.93]};
 for(const [material,[t,low]] of Object.entries(cases)){
  const shapes=[{...STRIP,material}];
  assert.equal(B.defaultTarget(shapes),t,material);assert.equal(B.lowerTarget(t),low,material);
  const doc=O.opticalDocument(state({shapes,openBoundary:{edges:ALL}}),setup());
  assert.equal(doc.physics.em1.target_effective_index,t,material);
  assert.deepEqual(doc.physics.em1.pml.pml_additional_searches,[{target_effective_index:low,pml_search_mode_count:16}],material);
  assert.ok(low>1.45&&low<t,material);
 }
 assert.equal(B.lowerTarget(2.2),1.82);
 assert.deepEqual(O.opticalDocument(state({openBoundary:{edges:ALL,target:2.2}}),setup()).physics.em1.pml.pml_additional_searches,[{target_effective_index:1.82,pml_search_mode_count:16}]);
});
test('W9: t_low for every target of 3 decimals: half up, above the 1.45 floor from 1.466; none below',()=>{
 // an independent formula in BigInt thousandths: floor(((m + 1444) * 5 + 50) / 100) hundredths
 for(let m=1451;m<=3477;m++){
  const t=m/1000,low=B.lowerTarget(t);
  if(m<1466){assert.equal(low,null,String(t));continue;}
  const hundredths=Number(((BigInt(m)+1444n)*5n+50n)/100n);
  assert.equal(low,hundredths/100,String(t));assert.ok(low>1.45&&low<t,String(t));
 }
 // the threshold (decision D1): at 1.465 t_low would round to the floor 1.45, at 1.466 it is 1.46
 assert.equal(B.lowerTarget(1.465),null);assert.equal(B.lowerTarget(1.466),1.46);assert.equal(B.lowerTarget(2.466),1.96);
 const below=O.opticalDocument(state({openBoundary:{edges:ALL,target:1.465}}),setup()),at=O.opticalDocument(state({openBoundary:{edges:ALL,target:1.466}}),setup());
 assert.equal('pml_additional_searches' in below.physics.em1.pml,false);
 assert.deepEqual(at.physics.em1.pml.pml_additional_searches,[{target_effective_index:1.46,pml_search_mode_count:16}]);
 assert.equal(B.checkOpenBoundary({edges:ALL,target:1.465},[STRIP]).lowTarget,null);assert.equal(B.checkOpenBoundary({edges:ALL},[STRIP]).lowTarget,1.95);
});
test('the open document is the single-search one with the key after the fixed settings; the PML check documents are P2\'s byte for byte',()=>{
 const doc=O.opticalDocument(state({openBoundary:{edges:ALL}}),setup()),single=JSON.parse(JSON.stringify(doc));
 delete single.physics.em1.pml.pml_additional_searches;
 assert.deepEqual(Object.keys(doc.physics.em1.pml),['pml_thickness','pml_strength','pml_order','pml_minimum_physical_fraction','pml_search_mode_count','pml_additional_searches']);
 const re=[2.4429090610269997,1.7699957790296044];
 assert.equal(JSON.stringify(R.checkDocuments(doc,re)),JSON.stringify(R.checkDocuments(single,re)));
});

// -- the record of a run ---------------------------------------------------------------------
const candidate=(n,search,re,im,fraction,reasons,extra={})=>({candidate:n,search,effective_index:{re,im,unit:'1',time_convention:'exp(-i omega t)'},relative_residual:1e-14,physical_l2_fraction:fraction,pml_l2_fraction:1-fraction,reasons,
 selected:reasons.includes('selected_descending_real_index'),attenuation_status:'resolved_sign',...extra});
const three=(cands,searches=[[2.46,32],[1.95,16]])=>({schema:'openphysics.pml-candidates/3',candidates:cands,selected_candidates:cands.filter(c=>c.selected).map(c=>c.candidate),
 searches:searches.map(([t,n],i)=>({search:i+1,target_effective_index:t,search_mode_count:n,candidate_count:cands.filter(c=>c.search===i+1).length})),selection:'descending_real_index',
 pml_minimum_physical_fraction:0.5,relative_residual_threshold:1e-8,stability:'not_checked',classification:'heuristic_candidates',mode_count:2,returned_mode_count:2});
const CANDS=()=>[candidate(1,1,2.44126325,8.28e-5,0.999,['selected_descending_real_index']),candidate(2,1,2.3,0.7,2e-9,['low_physical_l2_fraction']),
 candidate(3,1,1.77279036,2.857e-3,0.998,['selected_descending_real_index']),candidate(4,2,1.77279036,2.857e-3,0.998,['duplicate_candidate'],{duplicate_of:3,duplicate_effective_index_distance:0,duplicate_field_overlap:1}),
 candidate(5,2,1.48642654,7.92e-3,0.978,['outside_requested_count']),candidate(6,2,1.6,0.04,0.3,['low_physical_l2_fraction','duplicate_candidate'],{duplicate_of:2,duplicate_effective_index_distance:0,duplicate_field_overlap:1}),
 candidate(7,2,1.44,1e-3,0.9,['low_physical_l2_fraction'])];
const RE=[2.44126325,1.77279036],IM=[8.28e-5,2.857e-3];
test('a /3 record holds exactly the searches of its target; a /2 record is P2\'s',()=>{
 const ok=three(CANDS());
 assert.deepEqual(R.checkCandidateRecord(ok,'Run 1','2.460'),ok);
 assert.deepEqual(R.checkCandidateRecord(ok,'Run 1'),ok);
 const bad=[three(CANDS(),[[2.46,32],[1.94,16]]),three(CANDS(),[[2.46,32],[1.95,15]]),three(CANDS(),[[2.46,16],[1.95,16]]),three(CANDS(),[[2.46,32]]),
  {...ok,searches:[...ok.searches,{search:3,target_effective_index:1.7,search_mode_count:16,candidate_count:0}]},
  three(CANDS().map(c=>c.candidate===5?{...c,search:3}:c)),three(CANDS().map(c=>c.candidate===4?{...c,duplicate_of:99}:c)),{...ok,schema:'openphysics.pml-candidates/4'}];
 for(const record of bad)assert.throws(()=>R.checkCandidateRecord(record,'Run 1','2.460'),{message:'Run 1: invalid open boundary record.'});
 // another target: its own searches, not 2.46's
 assert.throws(()=>R.checkCandidateRecord(ok,'Run 1','2.300'),{message:'Run 1: invalid open boundary record.'});
 assert.deepEqual(R.checkCandidateRecord(three(CANDS(),[[2.3,32],[1.87,16]]),'Run 1','2.300').searches[1].target_effective_index,1.87);
 // a target below 1.466 has one search: a /3 record of it is refused
 assert.throws(()=>R.checkCandidateRecord(three(CANDS(),[[1.465,32],[1.45,16]]),'Run 1','1.465'),{message:'Run 1: invalid open boundary record.'});
 // the PML check searches once: a /3 check record is refused
 assert.throws(()=>R.checkResultRecord({summary:{open_boundary:[ok]}}),{message:'The PML check: invalid open boundary record.'});
});

// -- the words -------------------------------------------------------------------------------
test('the words of two searches: field, help, details, Study, found line, the no-mode error',()=>{
 assert.deepEqual(['2.460','2.455','2.500','1.600','3.400'].map(Number).map(R.shortTarget),['2.46','2.455','2.50','1.60','3.40']);
 assert.equal(R.lowerTargetText(1.95),'Also searches near 1.95, for modes close to the silica index.');
 assert.equal(R.searchesHelp(1.95),'Studio searches for modes near this index and near a second index halfway to the silica index (1.95). Modes are listed by n_eff, highest first. The default is halfway between the core and silica indices: (n_core + 1.444)/2.');
 const html=V.boundaryFieldHtml(R.openChoice(),[STRIP]);
 assert.ok(html.includes('<p class="input-note" id="lower-target">Also searches near 1.95, for modes close to the silica index.</p>'),html);
 assert.ok(html.includes('aria-describedby="lower-target target-help"'),html);
 assert.ok(html.includes('value="2.460"'),html);                       // the input keeps 3 decimals
 assert.ok(html.includes('32 candidates searched near n_eff, 16 near the second index'),html);
 // below 1.466: P2's words, no second target
 const one=V.boundaryFieldHtml({...R.openChoice(),target:1.465},[STRIP]);
 assert.ok(!one.includes('lower-target')&&one.includes(R.TARGET_HELP)&&one.includes(R.PML_DETAILS+'</p>'),one);
 assert.equal(R.studySummary(R.openChoice(),[STRIP]),'Open boundary · PML 1 µm · searches near 2.46 and 1.95');
 assert.equal(R.runFoundText(1,2,'2.460',three(CANDS())),"Found 1 of 2 modes near n_eff 2.46 and 1.95 (Studio's second search, halfway to the silica index). Move Search near n_eff to find other modes.");
 assert.equal(R.runFoundText(2,2,'2.460',{schema:'openphysics.pml-candidates/2'}),'Found 2 of 2 modes near n_eff 2.460. Move Search near n_eff (Physics › Optical modes) to find other modes.');
 const low=three([candidate(1,1,1.44,1e-3,0.9,['selected_descending_real_index']),candidate(2,2,1.43,1e-3,0.9,['outside_requested_count'])]);
 assert.throws(()=>R.openResultValues({summary:{open_boundary:[low]}},[1.44],[1e-3],2.46),{message:'No mode above n = 1.45 was found near n_eff 2.46 and 1.95. Move Search near n_eff to find other modes.'});
});
test('the candidates of two searches: the Search column, duplicates left out and counted',()=>{
 const record=three(CANDS()),rows=R.otherCandidates(record,RE,IM);
 assert.deepEqual(rows.map(r=>[r.candidate,r.search,r.reason]),[[2,'near 2.46','Mostly in the PML (a PML mode)'],[5,'near 1.95','Beyond the modes asked for'],[7,'near 1.95','Mostly in the PML (a PML mode)']]);
 assert.equal(R.duplicateCount(record),2);
 assert.equal(R.otherCandidatesTitle(rows.length,R.duplicateCount(record)),'Other candidates (3) — not shown as modes · 2 found by both searches');
 assert.equal(R.otherCandidatesTitle(41,3),'Other candidates (41) — not shown as modes · 3 found by both searches');
 assert.equal(R.otherCandidatesTitle(41,1),'Other candidates (41) — not shown as modes · 1 found by both searches');
 assert.equal(R.otherCandidatesTitle(41,0),'Other candidates (41) — not shown as modes');
 // modes listed by descending Re: the selected candidates, as the engine ranks them
 assert.deepEqual(R.modeCandidates(record,RE,IM).map(c=>c.candidate),[1,3]);
 // the second solve's eligible candidates of a /3 record: the selected and those beyond the count, not the duplicates
 assert.deepEqual(R.eligibleCandidates(record).map(c=>c.re),[2.44126325,1.77279036,1.48642654]);
});

// -- amendment (a): a version 10 file of P2 (single-search runs, records /2) ------------------------
// optical-v10-open-f8ece10.json was written by f8ece10's Studio: its browser check's open-boundary
// stage (template run all open with the PML check, the closed template, the strip over a substrate
// with the PML check) saved the project on Linux; the optical session was then written again by
// f8ece10's own sessionText with no fields kept (the path of a session over the limit), so the
// file is small. The words below are those f8ece10's page showed for these runs in that check.
const F8='optical-v10-open-f8ece10.json';
const P2_FOUND='Found 2 of 2 modes near n_eff 2.460. Move Search near n_eff (Physics › Optical modes) to find other modes.';
test('amendment (a): a version 10 file of P2 opens with the same values and words',async()=>{
 const N=await import(STATIC+'workspace-notebook.mjs');
 const text=fixture(F8),raw=JSON.parse(text),s=N.parseSession(text);
 assert.equal(raw.version,10);assert.equal(s.runs.length,3);
 const open=s.runs.filter(r=>r.settings.boundary==='PML');assert.equal(open.length,2);
 s.runs.forEach((run,i)=>{
  const saved=raw.runs[i].effective_index,re=Array.isArray(saved)?saved:saved.re;
  assert.deepEqual(run.effective_index,re);if(!Array.isArray(saved))assert.deepEqual(run.effective_index_im,saved.im);
 });
 const screen=run=>{
  const cands=R.modeCandidates(run.open_boundary,run.effective_index,run.effective_index_im),rows=R.otherCandidates(run.open_boundary,run.effective_index,run.effective_index_im);
  return {found:R.runFoundText(run.effective_index.length,run.settings.mode_count,run.settings.pml.target,run.open_boundary),
   neff:run.effective_index.map((r,i)=>R.openIndexText(r,run.effective_index_im[i])),
   loss:run.effective_index.map((r,i)=>R.openLoss(run.effective_index_im[i],1.55e-6,cands[i].attenuation_status).text),
   check:run.effective_index.map((r,i)=>{const v=R.checkVerdict(r,run.effective_index_im[i],run.pml_check.paired[i],1.55e-6,cands[i].attenuation_status);return [v.status,v.text];}),
   candidates:R.otherCandidatesTitle(rows.length,R.duplicateCount(run.open_boundary)),search:rows.some(r=>'search' in r)};
 };
 for(const run of open){assert.equal(run.open_boundary.schema,'openphysics.pml-candidates/2');assert.equal(run.settings.pml.target,'2.460');}
 assert.deepEqual(screen(open[0]),{found:P2_FOUND,neff:['2.44290906 − 5.12e-12i','1.76999578 + 1.36e-8i'],loss:['< 0.01 dB/cm','< 0.01 dB/cm'],
  check:[['unresolved','PML check: no leakage resolved (both solves below 0.05 dB/cm)'],['unresolved','PML check: no leakage resolved (both solves below 0.05 dB/cm)']],
  candidates:'Other candidates (30) — not shown as modes',search:false});
 assert.deepEqual(screen(open[1]),{found:P2_FOUND,neff:['2.44126325 + 8.28e-5i','1.77279036 + 2.86e-3i'],loss:['29.15 dB/cm','1006 dB/cm'],
  check:[['independent','PML check: loss changes 0.0038 %'],['independent','PML check: loss changes 0.016 %']],
  candidates:'Other candidates (30) — not shown as modes',search:false});
 // the file is written again as it was read (V15): the session text of the same state is the file's
 assert.equal(N.sessionText(s.input,s.runs,s.selected,s.comparison,s.view,{keep:new Set()}),text);
});
test('amendment (a): running a P2 run again builds the document of both searches from its inputs',async()=>{
 const N=await import(STATIC+'workspace-notebook.mjs');
 const s=N.parseSession(fixture(F8)),leak=s.runs.filter(r=>r.settings.boundary==='PML')[1];
 const model=leak.input.model,choice=R.runChoice(leak);
 assert.deepEqual(choice,{edges:ALL,target:2.46});
 const doc=O.opticalDocument({...model,modeCount:leak.settings.mode_count,openBoundary:choice},leak.input.setup);
 assert.equal(JSON.stringify(doc),fixture('optical-document-strip-substrate-open-searches.json'));
});
