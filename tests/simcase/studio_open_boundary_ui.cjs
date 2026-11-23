// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Open boundary in Studio (slice P2): the choice, Search near n_eff, the run's settings, the loss
// cells of an open run (V14), the other candidates, the PML check (pairing and independence at
// their thresholds), Compare's per-side words, the matching window, the inputs file of version 9
// and the optical session of version 10 (V15).
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const fixture=name=>fs.readFileSync(path.join(__dirname,'studio_session_fixtures',name),'utf8');
let R,N,P,O,B,M,S,X,J,W;
test.before(async()=>{
 R=await import(STATIC+'workspace-open-run.mjs');N=await import(STATIC+'workspace-notebook.mjs');P=await import(STATIC+'workspace-project.mjs');
 O=await import(STATIC+'workspace-optical.mjs');B=await import(STATIC+'workspace-open-boundary.mjs');M=await import(STATIC+'workspace-modes.mjs');
 S=await import(STATIC+'workspace-multiphysics-session.mjs');X=await import(STATIC+'workspace-match.mjs');J=await import(STATIC+'workspace-job.mjs');
 W=await import(STATIC+'workspace-workflow.mjs');
});
const LAMBDA=1.55e-6;
// the hand formula, written out here rather than taken from the module: 40 pi / ln 10 Im n / lambda0 / 100
const handDbPerCm=im=>40*Math.PI/Math.log(10)*im/LAMBDA/100;
const nextUp=x=>{const b=new DataView(new ArrayBuffer(8));b.setFloat64(0,x);b.setBigUint64(0,b.getBigUint64(0)+1n);return b.getFloat64(0);};
const nextDown=x=>{const b=new DataView(new ArrayBuffer(8));b.setFloat64(0,x);b.setBigUint64(0,b.getBigUint64(0)-1n);return b.getFloat64(0);};
const ALL={left:'open',right:'open',bottom:'open',top:'open'};
const STRIP={name:'Core',type:'rect',material:'Silicon',x:-250,y:0,w:500,h:220};
const SUBSTRATE={name:'Substrate',type:'rect',material:'Silicon',x:-1500,y:-1200,w:3000,h:700};
const setup=()=>({materials:{Core:'Silicon',Oxide:'Silica',Heater:''},temperature:293.15,cooling:'',fixed:'',terminal:''});
const input=(shapes=[STRIP])=>P.snapshot({width:500,voltage:1,electric:false,heat:false,structure:false,optics:true,wavelength:1550,coreMesh:30,shapes},setup());

// -- V14 Loss text --------------------------------------------------------------------------
test('V14: the loss of an open run to 4 significant digits, by the hand formula',()=>{
 // the strip over a substrate (P1, default mesh): TE-like 29.1528, TM-like 1005.964 dB/cm
 assert.equal(handDbPerCm(8.2797609e-5).toFixed(3),'29.153');
 assert.equal(R.openLoss(8.2797609e-5,LAMBDA).text,'29.15 dB/cm');
 assert.equal(R.openLoss(2.857064e-3,LAMBDA).text,'1006 dB/cm');
 // 10^4 dB/cm and more: whole dB/cm, never an exponent
 assert.equal(R.openLoss(3.5e-2,LAMBDA).text,R.dbPerCm(3.5e-2,LAMBDA).toFixed(0)+' dB/cm');assert.doesNotMatch(R.openLoss(3.5e-2,LAMBDA).text,/e/);
 for(const im of [1e-6,3.3e-5,8.2797609e-5,2.857064e-3,7.92e-3])assert.equal(R.dbPerCm(im,LAMBDA),handDbPerCm(im));
 const cell=R.openLoss(8.2797609e-5,LAMBDA);
 assert.equal(cell.floor,false);
 assert.equal(cell.title,'Material absorption (k) and leakage into the PML of the open boundary. At the default mesh this loss is about 3 % above the converged value (TE-like +2.8 %, TM-like +1.8 % on a strip over a substrate).');
});
test('V14: "< 0.01 dB/cm" below 0.01 dB/cm, for a negative Im and for numerically_unresolved; "—" without Im',()=>{
 // the Im n_eff of exactly 0.01 dB/cm, and the next double below it
 const at=0.01*LAMBDA*100*Math.log(10)/(40*Math.PI);
 let im=at;while(R.dbPerCm(im,LAMBDA)<0.01)im=nextUp(im);while(R.dbPerCm(nextDown(im),LAMBDA)>=0.01)im=nextDown(im);
 assert.ok(R.dbPerCm(im,LAMBDA)>=0.01&&R.dbPerCm(nextDown(im),LAMBDA)<0.01);
 assert.equal(R.openLoss(im,LAMBDA).text,'0.01000 dB/cm');
 assert.equal(R.openLoss(nextDown(im),LAMBDA).text,'< 0.01 dB/cm');
 const help='Below what this open boundary resolves for a 3 × 2.4 µm window (0.01 dB/cm). The mode does not leak measurably here.';
 // -1e-3 (|loss| 352 dB/cm) was here until the V14 change of slice T2 (decided by the coordinator):
 // a negative Im whose |loss| reaches 0.01 dB/cm now reads "not resolved (|loss| < X dB/cm)", below
 for(const [value,status] of [[nextDown(im),null],[-5.1e-12,null],[-6.17e-9,null],[0,null],[1.36e-8,null],[1e-3,'numerically_unresolved']]){
  const c=R.openLoss(value,LAMBDA,status);assert.equal(c.text,'< 0.01 dB/cm',String(value));assert.equal(c.title,help);assert.equal(c.floor,true);
 }
 for(const value of [null,undefined,NaN])assert.equal(R.openLoss(value,LAMBDA).text,'—');
 // a closed run keeps lossText: no threshold, 4 significant digits
 assert.equal(M.lossText(1e-15,M.propagationLoss(1e-15,LAMBDA)),'3.521e-10 dB/cm');assert.equal(M.lossText(0,null),'0 dB/cm');
});
test('n_eff of an open run: Re as a closed run shows it, Im to 3 significant digits',()=>{
 assert.equal(R.openIndexText(2.442275,8.28e-5),'2.44227500 + 8.28e-5i');
 assert.equal(R.openIndexText(2.4429090610269997,-5.1183914206486975e-12),'2.44290906 − 5.12e-12i');
 assert.equal(R.openIndexText(1.4864,7.92e-3),'1.48640000 + 7.92e-3i');
});

// -- the choice and the settings ------------------------------------------------------------
test('Search near n_eff: the default 2.46 (P1, to 0.01) is shown 2.460; edits are kept to 3 decimals; the range is exclusive',()=>{
 assert.equal(R.targetText(B.defaultTarget([STRIP])),'2.460');
 assert.equal(R.parseTarget('2.3',[STRIP]),2.3);assert.equal(R.parseTarget(' 2.34567 ',[STRIP]),2.346);assert.equal(R.parseTarget('1.6',[STRIP]),1.6);
 for(const bad of ['1.45','1.4504','3.4777','4','','x'])assert.throws(()=>R.parseTarget(bad,[STRIP]),/Search near n_eff must/,bad);
 assert.equal(R.parseTarget('1.4505',[STRIP]),1.451);
 // slice T2: both searches; one search below a target of 1.466
 assert.equal(R.studySummary(R.openChoice(),[STRIP]),'Open boundary · PML 1 µm · searches near 2.46 and 1.95');
 assert.equal(R.studySummary({...R.openChoice(),target:2.2},[STRIP]),'Open boundary · PML 1 µm · searches near 2.20 and 1.82');
 assert.equal(R.studySummary({...R.openChoice(),target:2.455},[STRIP]),'Open boundary · PML 1 µm · searches near 2.455 and 1.95');
 assert.equal(R.studySummary({...R.openChoice(),target:1.465},[STRIP]),'Open boundary · PML 1 µm · search near 1.465');
 assert.equal(R.studySummary(null,[STRIP]),'');
 assert.equal(R.sectionWords(R.openChoice()),'open boundary (PML 1 µm) on 4 edges');
 assert.equal(R.sectionWords({edges:{...ALL,bottom:'closed',top:'closed',left:'closed'}}),'open boundary (PML 1 µm) on 1 edge');
});
test('the document of the page: the default target is P1\'s; an edit changes target_effective_index only',()=>{
 const state={height:220,width:500,wavelength:1550,coreMesh:30,electric:false,heat:false,structure:false,optics:true,shapes:[STRIP]};
 const base=O.opticalDocument({...state,openBoundary:{edges:ALL}},setup());
 assert.deepEqual(O.opticalDocument({...state,openBoundary:R.openChoice()},setup()),base);
 const edited=O.opticalDocument({...state,openBoundary:{...R.openChoice(),target:2.3}},setup());
 assert.equal(edited.physics.em1.target_effective_index,2.3);
 // slice T2: and the second search with it, (2.3 + 1.444) / 2 = 1.872 -> 1.87
 assert.deepEqual(edited.physics.em1.pml.pml_additional_searches,[{target_effective_index:1.87,pml_search_mode_count:16}]);
 assert.deepEqual({...edited,physics:{em1:{...edited.physics.em1,target_effective_index:2.46,pml:{...edited.physics.em1.pml,pml_additional_searches:[{target_effective_index:1.95,pml_search_mode_count:16}]}}}},base);
 // Geometry › Boundaries: one edge closed drops its side of the PML block and of the domain
 const closed=O.opticalDocument({...state,openBoundary:{edges:{...ALL,bottom:'closed'}}},setup());
 assert.deepEqual(Object.keys(closed.physics.em1.pml.pml_thickness),['left','right','top']);
 assert.equal(closed.geometry.domain.ymin,-1200);assert.equal(closed.geometry.domain.ymax,2200);
});
test('an open run\'s settings: adapter optical-shapes-v9, boundary PML and pml {thickness, open_edges, target}',()=>{
 const s=R.openSettings(N.opticalSettings(1550,30,2),{edges:{...ALL,top:'closed'},target:null},[STRIP]);
 assert.deepEqual(Object.keys(s),['adapter','domain','boundary','mode_count','solver_version','vacuum_wavelength','core_element_size','pml']);
 assert.equal(s.adapter,'optical-shapes-v9');assert.equal(s.boundary,'PML');
 assert.deepEqual(s.pml,{thickness:'1000 nm',open_edges:['left','right','bottom'],target:'2.460'});
 // every edge closed: the closed settings, unchanged
 assert.deepEqual(R.openSettings(N.opticalSettings(),{edges:{left:'closed',right:'closed',bottom:'closed',top:'closed'}},[STRIP]),N.opticalSettings());
 assert.deepEqual(R.runChoice({settings:s}),{edges:{...ALL,top:'closed'},target:2.46});
 // the signature tells an open run from a closed one of the same inputs
 assert.notEqual(N.studySignature(input(),2,false,s.pml),N.studySignature(input(),2,false));
 assert.equal(N.studySignature(input(),2,false,null),N.studySignature(input(),2,false));
 assert.equal(W.nextRunText(input(),2,false,s.pml),'Next run uses 500 × 220 nm · Silicon · λ 1550 nm · core mesh 30 nm · Modes to find 2 · open boundary (PML 1 µm) on 3 edges · search near 2.460');
});

// -- the candidates ---------------------------------------------------------------------------
const candidate=(n,re,im,fraction,reasons,extra={})=>({candidate:n,effective_index:{re,im,unit:'1',time_convention:'exp(-i omega t)'},relative_residual:1e-14,physical_l2_fraction:fraction,pml_l2_fraction:1-fraction,reasons,selected:reasons.includes('selected_near_target'),attenuation_status:Math.abs(im)<=1e-10*Math.max(1,Math.abs(re))?'numerically_unresolved':'resolved_sign',...extra});
// the template's search as the engine records it (its values, shortened)
const record=(cands=[candidate(1,2.4429090610269997,-5.1183914206486975e-12,0.99999999,['selected_near_target']),candidate(2,2.3293726320901316,0.7679,2.2e-9,['low_physical_l2_fraction']),
 candidate(3,1.7699957790296044,1.3625383684228314e-08,0.99993,['selected_near_target']),candidate(4,1.4923038712341017,-2.674e-07,0.98311,['negative_imaginary_index']),
 candidate(5,1.4357,0.0098,0.1418,['low_physical_l2_fraction']),candidate(6,2.1,1e-3,0.9,['pencil_residual']),candidate(7,1.9,2e-4,0.95,['outside_requested_count'])])=>
 ({schema:'openphysics.pml-candidates/2',candidates:cands,selected_candidates:cands.filter(c=>c.selected).map(c=>c.candidate),pml_minimum_physical_fraction:0.5,relative_residual_threshold:1e-8,stability:'not_checked',classification:'heuristic_candidates',mode_count:2,returned_mode_count:2});
const RE=[2.4429090610269997,1.7699957790296044],IM=[-5.1183914206486975e-12,1.3625383684228314e-08];
test('the other candidates: every searched candidate not shown, with n_eff, physical share and the reason in words',()=>{
 const rows=R.otherCandidates(record(),RE,IM);
 assert.equal(R.otherCandidatesTitle(rows.length),'Other candidates (5) — not shown as modes');
 assert.deepEqual(rows.map(r=>[r.candidate,r.reason]),[[2,'Mostly in the PML (a PML mode)'],[4,'Gains power (not a passive mode)'],[5,'Mostly in the PML (a PML mode)'],[6,'Not converged (residual above 1e-8)'],[7,'Beyond the modes asked for']]);
 assert.deepEqual(rows[1],{candidate:4,neff:'1.49230387 − 2.67e-7i',share:'98.3 %',reason:'Gains power (not a passive mode)'});
 // a selected candidate at or below 1.45: Studio's silica rule
 const low=record([candidate(1,2.44,1e-6,0.99,['selected_near_target']),candidate(2,1.44,1e-3,0.9,['selected_near_target'])]);
 const values=R.openResultValues({summary:{open_boundary:[low]},vector_fields:[{real:[['a'],['b']],imag:[['c'],['d']]}]},[2.44,1.44],[1e-6,1e-3],'2.460');
 assert.deepEqual([values.re,values.im,values.keep],[[2.44],[1e-6],[0]]);assert.deepEqual(values.data.vector_fields[0].real,[['a']]);
 assert.deepEqual(R.otherCandidates(low,values.re,values.im).map(r=>r.reason),['Below the silica index (cladding radiation)']);
 assert.throws(()=>R.openResultValues({summary:{open_boundary:[low]}},[1.44],[1e-3],'1.600'),{message:'No mode above n = 1.45 was found near n_eff 1.600. Move Search near n_eff (Physics › Optical modes) to find other modes.'});
 assert.equal(R.openFoundText(2,2,'2.460'),'Found 2 of 2 modes near n_eff 2.460');
 assert.equal(R.openTableTitle(),'Modes (open boundary, PML 1 µm)');
});

test('V14 (changed in slice T2): a negative Im n_eff whose |loss| reaches 0.01 dB/cm is not resolved, below X rounded up to 2 digits',()=>{
 // hand values at 1550 nm: 40 pi / ln 10 * 2.67e-7 / 1.55e-6 / 100 = 0.0940 dB/cm -> X = 0.095
 assert.ok(Math.abs(handDbPerCm(2.67e-7)-0.0940099)<1e-6);
 const neg=R.openLoss(-2.67e-7,LAMBDA);
 assert.deepEqual(neg,{text:'not resolved (|loss| < 0.095 dB/cm)',title:'The solve gives a small negative Im n_eff within the PML\'s numerical noise; the loss is below about 0.095 dB/cm.',value:-handDbPerCm(2.67e-7),floor:false});
 // -6.17e-9 is 0.0022 dB/cm: below the floor as before; a positive loss is unchanged
 assert.equal(R.openLoss(-6.17e-9,LAMBDA).text,'< 0.01 dB/cm');assert.equal(R.openLoss(-6.17e-9,LAMBDA).floor,true);
 assert.equal(R.openLoss(8.28e-5,LAMBDA).text,'29.15 dB/cm');
 assert.equal(R.openLoss(-1e-3,LAMBDA).text,'not resolved (|loss| < 360 dB/cm)');
 // exactly at the floor, negative: not resolved below 0.010; the next double inside: below the floor
 const at=0.01*LAMBDA*100*Math.log(10)/(40*Math.PI);let im=at;while(R.dbPerCm(im,LAMBDA)<0.01)im=nextUp(im);while(R.dbPerCm(nextDown(im),LAMBDA)>=0.01)im=nextDown(im);
 assert.equal(R.openLoss(-im,LAMBDA).text,'not resolved (|loss| < 0.010 dB/cm)');assert.equal(R.openLoss(-nextDown(im),LAMBDA).text,'< 0.01 dB/cm');
 // numerically_unresolved keeps the floor words
 assert.equal(R.openLoss(-1e-3,LAMBDA,'numerically_unresolved').text,'< 0.01 dB/cm');
 // X: rounded up to 2 significant digits, exact 2-digit values kept
 assert.deepEqual([0.094,0.0940099,0.07,0.0999,0.995,9.91,10,12.01,351.9,1234].map(R.lossBoundText),['0.094','0.095','0.070','0.10','1.0','10','10','13','360','1300']);
});

// -- the PML check ----------------------------------------------------------------------------
test('PML check: pairing within |Δn_eff| <= 2e-3, the thresholds exactly at their boundaries',()=>{
 assert.equal(R.withinPair(2e-3),true);assert.equal(R.withinPair(nextUp(2e-3)),false);
 assert.equal(R.reIndependent(5e-4),true);assert.equal(R.reIndependent(-5e-4),true);assert.equal(R.reIndependent(nextUp(5e-4)),false);
 // the loss: max(2 % of L1, 0.01 dB/cm), each branch at its boundary
 assert.equal(R.lossIndependent(100,102),true);assert.equal(R.lossIndependent(100,98),true);assert.equal(R.lossIndependent(100,nextUp(102)),false);
 assert.equal(R.lossIndependent(0,0.01),true);assert.equal(R.lossIndependent(0,nextUp(0.01)),false);assert.equal(R.lossIndependent(0.25,0.25-0.0078125),true);
});
test('PML check: each mode paired with the nearest eligible candidate; a mode not found again; the verdict words',()=>{
 // eligible: selected or beyond the count, Re > 1.45; PML modes, gain and residual failures are not
 const check=record([candidate(1,2.4429,1e-11,0.999,['selected_near_target']),candidate(2,1.7701,1.4e-8,0.9999,['outside_requested_count']),
  candidate(3,2.4428,0.1,0.01,['low_physical_l2_fraction']),candidate(4,1.7699957,1e-8,0.99,['pencil_residual'])]);
 const paired=R.pairCheck(RE,IM,check);
 assert.deepEqual(paired,{pml_strength:6,paired:[{re:2.4429,im:1e-11},{re:1.7701,im:1.4e-8}]});
 assert.deepEqual(R.eligibleCandidates(check).length,2);
 // nothing within 2e-3: not found
 assert.deepEqual(R.pairCheck([2.0],[1e-4],check).paired,[null]);
 assert.deepEqual(R.checkVerdict(2.0,1e-4,null,LAMBDA),{status:'not_found',text:'Not found in the check solve',title:'The check solve did not find this mode near the search value; this does not by itself mean the mode depends on the PML.'});
 // below the display floor with a check loss below 0.05 dB/cm: no verdict (decision after the template
 // TM-like result 0.00480 -> 0.01706 dB/cm, registered as independent)
 const unresolved={status:'unresolved',text:'PML check: no leakage resolved (both solves below 0.05 dB/cm)',title:'The check solve (strength 6) leaves a larger residue than the run\'s solve on tiny losses: below the display floor the check says only that no leakage is resolved; it does not certify independence.'};
 assert.deepEqual(R.checkVerdict(RE[0],IM[0],paired.paired[0],LAMBDA),unresolved);
 const im0=0.00480*LAMBDA*100*Math.log(10)/(40*Math.PI),im17=0.01706*LAMBDA*100*Math.log(10)/(40*Math.PI);
 assert.deepEqual(R.checkVerdict(1.77,im0,{re:1.77,im:im17},LAMBDA),unresolved);
 // the check at 0.05 dB/cm exactly, or above: the existing rule ("Depends on the PML")
 const at=0.05*LAMBDA*100*Math.log(10)/(40*Math.PI);let i5=at;while(R.dbPerCm(i5,LAMBDA)<0.05)i5=nextUp(i5);while(R.dbPerCm(nextDown(i5),LAMBDA)>=0.05)i5=nextDown(i5);
 assert.equal(R.checkVerdict(1.77,im0,{re:1.77,im:i5},LAMBDA).status,'depends');assert.deepEqual(R.checkVerdict(1.77,im0,{re:1.77,im:nextDown(i5)},LAMBDA),unresolved);
 // numerically_unresolved reads as below the floor; a first solve at the floor keeps the rule
 const big=8.5e-8;assert.deepEqual(R.checkVerdict(1.77,big,{re:1.77,im:big},LAMBDA,'numerically_unresolved'),unresolved);
 assert.equal(R.checkVerdict(1.77,big,{re:1.77,im:big},LAMBDA).status,'independent');
 const l=8.2797609e-5;
 assert.deepEqual(R.checkVerdict(2.441263,l,{re:2.441263,im:l*1.001},LAMBDA),{status:'independent',text:'PML check: loss changes 0.1 %',title:R.CHECK_HELP});
 assert.equal(R.checkVerdict(2.441263,l,{re:2.441263,im:l*(1-3.8e-5)},LAMBDA).text,'PML check: loss changes 0.0038 %');
 // depends: the loss by 12 %, or Re n_eff by more than 5e-4
 const d=R.checkVerdict(2.441263,l,{re:2.441263,im:l*1.12},LAMBDA);
 assert.deepEqual(d,{status:'depends',text:'Depends on the PML: loss changes 12 %',title:'This loss changes with the PML; it is not a converged leakage loss.'});
 assert.equal(R.checkVerdict(2.441263,l,{re:2.441263+7e-4,im:l},LAMBDA).text,'Depends on the PML: Re n_eff changes 7.0e-4');
 assert.deepEqual(R.checkPmlCheck(paired,2),paired);
 for(const bad of [{...paired,pml_strength:3},{pml_strength:6,paired:[null]},{pml_strength:6,paired:[{re:1},null]},{...paired,extra:1}])assert.throws(()=>R.checkPmlCheck(bad,2),/invalid PML check/);
});

test('PML check (c1): one document per mode, strength 6, search 16, target at its Re n_eff; the candidates pooled',()=>{
 const state={height:220,width:500,wavelength:1550,coreMesh:30,electric:false,heat:false,structure:false,optics:true,shapes:[STRIP]};
 const doc=O.opticalDocument({...state,openBoundary:R.openChoice()},setup()),docs=R.checkDocuments(doc,RE);
 assert.equal(docs.length,2);
 docs.forEach((d,i)=>{const em=d.physics.em1;assert.deepEqual([em.pml.pml_strength,em.pml.pml_search_mode_count,em.target_effective_index],[6,16,[2.442909,1.769996][i]]);
  // everything else is the run's document: the same geometry and mesh
  // slice T2: one search, near the mode; the run's second search is not repeated
  assert.equal('pml_additional_searches' in em.pml,false);
  assert.deepEqual({...d,physics:{em1:{...em,target_effective_index:2.46,pml:{...em.pml,pml_strength:3,pml_search_mode_count:32,pml_additional_searches:[{target_effective_index:1.95,pml_search_mode_count:16}]}}}},doc);});
 assert.equal(R.checkLabel(2),'Also check the PML (2 more solves)');assert.equal(R.checkLabel(1),'Also check the PML (1 more solve)');
 // pooled: the TE-like mode from one solve, the TM-like one from another
 const first=record([candidate(1,2.4429,1e-11,0.999,['selected_near_target'])]),second=record([candidate(1,1.7701,1.4e-8,0.9999,['selected_near_target'])]);
 assert.deepEqual(R.pairCheck(RE,IM,[first,second]).paired,[{re:2.4429,im:1e-11},{re:1.7701,im:1.4e-8}]);
 assert.deepEqual(R.pairCheck(RE,IM,[first]).paired,[{re:2.4429,im:1e-11},null]);
});
test('review: a check whose selected modes are all at or below 1.45 still pairs with its other eligible candidates',()=>{
 const result={summary:{open_boundary:[record([candidate(1,1.44,1e-3,0.9,['selected_near_target']),candidate(2,1.7700,1.4e-8,0.99,['outside_requested_count'])])]}};
 const rec=R.checkResultRecord(result);
 assert.deepEqual(R.pairCheck([1.77],[1.36e-8],[rec]).paired,[{re:1.77,im:1.4e-8}]);
});
test('slice P3: the group index is no longer locked with an open edge; the PML check documents leave it out',()=>{
 assert.equal(R.groupIndexLocked,undefined);assert.equal(R.GROUP_INDEX_OPEN_NOTE,undefined);
 const doc={physics:{em1:{pml:{pml_strength:3,pml_search_mode_count:32},target_effective_index:2.46}},results:{plots:false,group_index:{wavelength_step:'1 nm'}}};
 const docs=R.checkDocuments(doc,[2.4429,1.77]);
 assert.deepEqual(docs.map(d=>d.results),[{plots:false},{plots:false}]);assert.deepEqual(doc.results.group_index,{wavelength_step:'1 nm'});
 assert.deepEqual(docs.map(d=>[d.physics.em1.pml.pml_strength,d.physics.em1.target_effective_index]),[[6,2.4429],[6,1.77]]);
});
test('slice P3: the engine values of a new open result follow the modes Studio keeps',()=>{
 assert.deepEqual(R.keptValues({te_polarization_fraction:[0.98,0.5,0.04],group_index:[4.19,null,3.73],group_index_im:[1e-10,null,1e-8],group_index_method:'central_difference 1 nm electric-l2-assignment-v1'},[0,2]),
  {te_polarization_fraction:[0.98,0.04],group_index:[4.19,3.73],group_index_im:[1e-10,1e-8],group_index_method:'central_difference 1 nm electric-l2-assignment-v1'});
});

// -- Compare ----------------------------------------------------------------------------------
test('Compare: run names say (closed) or (open, PML 1 µm); the loss note when the sides differ',()=>{
 assert.equal(R.boundaryName({settings:N.opticalSettings()}),'(closed)');
 assert.equal(R.boundaryName({settings:{boundary:'PML'}}),'(open, PML 1 µm)');
 assert.equal(R.COMPARE_LOSS_NOTE,'A counts material absorption only; B also counts leakage. Their difference is not a leakage loss.');
});
// Slice P3: matching with an open run is on, on its physical window. Replaces P2's "matching is off"
// test (V13 failed blind at 0.99; the criteria registered after that result, V13a-c, pass:
// tests/simcase/test_open_boundary_mode_identity.py).
// A square mesh of n x n cells over [-h, h]^2 (metres), two modes: E_x = 1 and E_y = 1 per triangle.
function squareRun(n,h,open=null){
 const X=[],T=[];for(let j=0;j<=n;j++)for(let i=0;i<=n;i++)X.push([-h+2*h*i/n,-h+2*h*j/n]);
 for(let j=0;j<n;j++)for(let i=0;i<n;i++){const p=j*(n+1)+i;T.push([p,p+1,p+n+2],[p,p+n+2,p+n+1]);}
 const mode=c=>T.map(()=>c===0?[1,0,0]:[0,1,0]),zero=()=>T.map(()=>[0,0,0]);
 const run={settings:open?{boundary:'PML'}:N.opticalSettings(),input:{model:{coreMesh:30}},effective_index:[2.44,1.77],field:{node_coordinates:X,triangles:T,real:[mode(0),mode(1)],imag:[zero(),zero()]}};
 if(open)run.open_boundary={physical_bounds:{unit:'m',values:open}};
 return run;
}
test('slice P3: an open run is matched on its physical window (the triangles inside physical_bounds)',()=>{
 const closed=squareRun(10,1e-6),open=squareRun(20,2e-6,[[-1e-6,-1e-6],[1e-6,1e-6]]);
 const side=X.matchSide(open);
 // the 10 x 10 inner cells of the 20 x 20 mesh: 200 triangles, and the window is the physical one
 assert.equal(side.field.triangles.length,200);assert.deepEqual(side.window,{x0:-1e-6,x1:1e-6,y0:-1e-6,y1:1e-6});
 assert.equal(side.field.real[0].length,200);assert.equal(X.matchSide(closed).window,undefined);
 for(const [a,b] of [[closed,open],[open,closed],[open,open]]){
  const m=X.opticalMatch(a,b);assert.equal(m.disabled,undefined);
  assert.deepEqual([m.grid.x0,m.grid.x1,m.grid.y0,m.grid.y1],[-1e-6,1e-6,-1e-6,1e-6]);
  assert.deepEqual(m.pairs.map(p=>[p.unitA,p.unitB,p.accepted,Number(p.eta.toFixed(12))]),[[[0],[0],true,1],[[1],[1],true,1]]);
  assert.deepEqual(X.compareMatchRows(m).map(r=>r.kind),['match','match']);
 }
});
test('slice P3: an open run without physical bounds is listed unmatched, with the reason',()=>{
 const closed=squareRun(4,1e-6),open=squareRun(4,1e-6,[[-1e-6,-1e-6],[1e-6,1e-6]]);delete open.open_boundary;
 const m=X.opticalMatch(closed,open);assert.equal(m.disabled,'An open run without its physical window is not matched');assert.deepEqual(m.pairs,[]);
 assert.deepEqual(X.compareMatchRows(m).map(r=>r.text),['A mode 1: not matched (an open run without its physical window is not matched)','A mode 2: not matched (an open run without its physical window is not matched)',
  'B mode 1: not matched (an open run without its physical window is not matched)','B mode 2: not matched (an open run without its physical window is not matched)']);
});
test('slice P3: Studio computes an open run\'s TE fraction and effective area on its physical window',()=>{
 const open=squareRun(20,2e-6,[[-1e-6,-1e-6],[1e-6,1e-6]]);
 // TE outside the window, so a whole-mesh sum would differ
 open.field.real[1]=open.field.real[1].map((v,k)=>M.physicalWindow(open.field,[[-1e-6,-1e-6],[1e-6,1e-6]])[k]?v:[1,0,0]);
 const modes=M.opticalModes(open);
 assert.deepEqual(modes.map(m=>m.fte),[1,0]);assert.ok(Math.abs(modes[0].area/4e-12-1)<1e-12);
 assert.equal(open.te.source,'studioWindow');assert.equal(M.SOURCE_TEXT.studioWindow,'computed by Studio from the saved field on the physical window (PML excluded)');
 const none=squareRun(4,1e-6,[[-1e-6,-1e-6],[1e-6,1e-6]]);delete none.open_boundary;
 assert.deepEqual(M.opticalModes(none).map(m=>[m.fte,m.area]),[[null,null],[null,null]]);assert.equal(none.te.source,'noWindow');
 // the engine's values, when the run has them
 const engine=squareRun(4,1e-6,[[-1e-6,-1e-6],[1e-6,1e-6]]);engine.te_polarization_fraction=[0.98,0.05];engine.effective_area=[1.9e-13,3.4e-13];
 assert.deepEqual(M.opticalModes(engine).map(m=>[m.fte,m.area]),[[0.98,1.9e-13],[0.05,3.4e-13]]);assert.equal(engine.te.source,'engineWindow');
});

// -- V15 Files --------------------------------------------------------------------------------
test('inputs version 9: written only when Open is chosen, round-trips bit for bit; version 7 and 8 otherwise',()=>{
 const base=input();
 assert.equal(JSON.stringify(P.withStudy(base,{})),JSON.stringify(base));assert.equal(P.withStudy(base,{openBoundary:null}).version,7);
 assert.equal(P.withStudy(base,{modeCount:3,openBoundary:null}).version,8);
 const v9=P.withStudy(base,{modeCount:3,openBoundary:{edges:{...ALL,top:'closed'},target:null}});
 assert.equal(v9.version,9);assert.deepEqual(v9.model.openBoundary,{edges:{...ALL,top:'closed'}});
 const text=JSON.stringify(v9);assert.equal(JSON.stringify(P.parseProject(text)),text);
 const edited=P.withStudy(base,{openBoundary:{edges:ALL,target:2.3}});assert.equal(edited.model.openBoundary.target,2.3);assert.equal(JSON.stringify(P.parseProject(JSON.stringify(edited))),JSON.stringify(edited));
 assert.deepEqual(P.projectBoundary(edited),{edges:ALL,target:2.3});assert.equal(P.projectBoundary(base),null);
 assert.equal(JSON.stringify(P.withoutStudy(edited)),JSON.stringify(base));
 // slice P3: the group index with an open boundary (was refused by name); it round-trips
 const both=P.withStudy(base,{groupIndex:true,openBoundary:{edges:ALL,target:null}});
 assert.deepEqual([both.version,both.model.groupIndex],[9,true]);assert.equal(JSON.stringify(P.parseProject(JSON.stringify(both))),JSON.stringify(both));
 const doc=JSON.parse(JSON.stringify(edited));
 for(const [f,message] of [[d=>{delete d.model.openBoundary;},/holds an outer boundary/],[d=>{d.model.openBoundary.target=2.3456;},/Invalid Search near n_eff/],[d=>{d.model.openBoundary.target=1.45;},/Invalid Search near n_eff/],
  [d=>{d.model.openBoundary.edges.left='pml';},/Invalid left edge/],[d=>{delete d.model.openBoundary.edges.top;},/Invalid outer boundary/]]){
  const c=JSON.parse(JSON.stringify(doc));f(c);assert.throws(()=>P.parseProject(JSON.stringify(c)),message);
 }
});
// a field of k modes over the grown window (nodes in the PML too)
const field=k=>({node_coordinates:[[-2.5e-6,-2.2e-6],[2.5e-6,-2.2e-6],[-2.5e-6,2.2e-6],[2.5e-6,2.2e-6]],triangles:[[0,1,2],[1,3,2]],
 real:Array.from({length:k},(_,m)=>[[1,0.25*m,-0],[0.5,-0.125,1e-3*(m+1)]]),imag:Array.from({length:k},(_,m)=>[[0,1e-9*m,0],[-2e-3,0,0]])});
const openRun=(job,extra={})=>({job,completedAt:'2026-11-23T01:00:00.000Z',settings:R.openSettings(N.opticalSettings(1550,30,2),R.openChoice(),[STRIP]),input:input(),
 effective_index:{re:[...RE],im:[...IM]},field:field(2),origin:'imported',serverVersion:'0.0.0',open_boundary:record(),...extra});
// imported: a file read back keeps that origin, so the texts compare byte for byte
const closedRun=job=>({job,completedAt:'2026-11-22T01:00:00.000Z',settings:N.opticalSettings(1550,30,2),input:input(),effective_index:[2.44,1.77],field:{...field(2),node_coordinates:[[-1.5e-6,-1.2e-6],[1.5e-6,-1.2e-6],[-1.5e-6,1.2e-6],[1.5e-6,1.2e-6]]},origin:'imported',serverVersion:'0.0.0'});
const view={mode:0,component:'magnitude',window:'Core region'};
test('V15: a session with an open run is version 10 and round-trips bit for bit, with its record and PML check',()=>{
 const check=R.pairCheck(RE,IM,record());
 const runs=[closedRun('0000000a'),openRun('0000000b',{pml_check:check})];
 const text=N.sessionText(input(),runs,'0000000b',['0000000a','0000000b'],view);
 const doc=JSON.parse(text);assert.equal(doc.version,10);assert.equal(doc.application,'optical');
 assert.deepEqual(Object.keys(doc.runs[1]),['job','completedAt','label','pinned','origin','serverVersion','settings','input','effective_index','field','te_polarization_fraction','effective_area','open_boundary','pml_check','digest'].filter(k=>k in doc.runs[1]));
 assert.deepEqual(doc.runs[1].settings.pml,{thickness:'1000 nm',open_edges:['left','right','bottom','top'],target:'2.460'});
 assert.equal(doc.runs[1].settings.adapter,'optical-shapes-v9');assert.equal(doc.runs[1].settings.boundary,'PML');
 assert.deepEqual(doc.runs[1].pml_check,check);assert.deepEqual(doc.runs[1].open_boundary,record());
 // the closed run of the same file keeps optical-shapes-v8
 assert.equal(doc.runs[0].settings.adapter,'optical-shapes-v8');assert.equal(doc.runs[0].open_boundary,undefined);
 const back=N.parseSession(text);
 assert.equal(N.sessionText(back.input,back.runs,back.selected,back.comparison,back.view),text);
 assert.deepEqual(back.runs[1].pml_check,check);assert.equal(R.isOpenRun(back.runs[1]),true);
 // this test's record has no physical_bounds: no physical window, so no TE fraction or A_eff ("—")
 assert.deepEqual(M.opticalModes(back.runs[1]).map(m=>[m.fte,m.area]),[[null,null],[null,null]]);
 // a v10 file without fields keeps the nulls
 const small=N.sessionText(input(),runs,'0000000b',['0000000a','0000000b'],view,{keep:new Set(['0000000b'])});
 assert.deepEqual(JSON.parse(small).runs.map(r=>r.field===undefined),[true,false]);
 const backSmall=N.parseSession(small);assert.equal(N.sessionText(backSmall.input,backSmall.runs,backSmall.selected,backSmall.comparison,backSmall.view,{keep:new Set(['0000000b'])}),small);
});
test('slice P3: an open run keeps the engine values and a complex group index; a P2 run is written as it was',()=>{
 const bounds={unit:'m',values:[[-1.5e-6,-1.2e-6],[1.5e-6,1.2e-6]]};
 const p2=openRun('0000000b',{open_boundary:{...record(),physical_bounds:bounds}});
 const p3=openRun('0000000c',{open_boundary:{...record(),physical_bounds:bounds},te_polarization_fraction:[0.98149,0.04635],effective_area:[1.9234e-13,3.4396e-13],
  group_index:{re:[4.19003092,null],im:[-1.69e-10,null]},group_index_method:'central_difference 1 nm electric-l2-assignment-v1'});
 const text=N.sessionText(input(),[p2,p3],'0000000c',['0000000b','0000000c'],view),doc=JSON.parse(text);
 assert.equal(doc.version,10);
 // the P2 run: no new key
 assert.deepEqual(['te_polarization_fraction','effective_area','group_index'].map(k=>k in doc.runs[0]),[false,false,false]);
 assert.deepEqual(Object.keys(doc.runs[1]),['job','completedAt','label','pinned','origin','serverVersion','settings','input','effective_index','field','te_polarization_fraction','effective_area','group_index','group_index_method','open_boundary','digest']);
 assert.deepEqual(doc.runs[1].group_index,{re:[4.19003092,null],im:[-1.69e-10,null]});
 const back=N.parseSession(text);assert.equal(N.sessionText(back.input,back.runs,back.selected,back.comparison,back.view),text);
 const run=back.runs[1];assert.deepEqual([run.group_index,run.group_index_im],[[4.19003092,null],[-1.69e-10,null]]);
 assert.deepEqual(M.opticalModes(run).map(m=>[m.fte,m.area]),[[0.98149,1.9234e-13],[0.04635,3.4396e-13]]);
 // the P2 run: Studio computes them on the window of its physical_bounds (the whole 3 x 2.4 um field here)
 const modes=M.opticalModes(back.runs[0]);assert.equal(back.runs[0].te.source,'studioWindow');
 assert.ok(modes.every(m=>Number.isFinite(m.fte)&&m.area>0));
 // n_g: Re shown, Im in the help
 const cell=M.groupIndexCell(run,0);assert.equal(cell.text,'4.1900');assert.ok(cell.title.endsWith(': Re n_g is shown; Im n_g -1.69e-10. At the default mesh n_g is about 5e-3 low in the slab check; the error comes from n_eff and shrinks when the core mesh is refined.'),cell.title);
 assert.equal(M.groupIndexCell(run,1).text,'—');
 // refusals: an open run's n_g must be complex, a closed run's real; null in both parts or neither
 const redigest=d=>{for(const r of d.runs){delete r.digest;r.digest=S.recordDigest(r);}return d;};
 const edit=f=>{const d=JSON.parse(text);f(d);return S.sessionJson(redigest(d));};
 for(const [f,message] of [
  [d=>{d.runs[1].group_index=d.runs[1].group_index.re;},'Run 2: a run with an open boundary has a complex group index.'],
  [d=>{d.runs[1].group_index.im[1]=0;},'Run 2: invalid saved group indices.'],
  [d=>{d.runs[1].group_index={im:[0,null],re:[4.19,null]};},'Run 2: invalid saved group indices.'],
 ])assert.throws(()=>N.parseSession(edit(f)),{message},message);
 const closed=JSON.parse(N.sessionText(P.withStudy(input(),{modeCount:2,groupIndex:true}),[{...closedRun('0000000a'),group_index:[4.2,3.7],group_index_method:'central_difference 1 nm electric-l2-assignment-v1'}],'0000000a',['0000000a','0000000a'],view));
 assert.deepEqual(closed.runs[0].group_index,[4.2,3.7]);
 closed.runs[0].group_index={re:[4.2,3.7],im:[0,0]};
 assert.throws(()=>N.parseSession(S.sessionJson(redigest(closed))),{message:'Run 1: a closed window has a real group index.'});
});
test('V15: the inputs choosing Open need version 10 too; without either, version 9 and 7 are written as before',()=>{
 const v9=P.withStudy(input(),{openBoundary:R.openChoice()});
 const text=N.sessionText(v9,[closedRun('0000000a')],'0000000a',['0000000a','0000000a'],view);
 assert.equal(JSON.parse(text).version,10);
 const back=N.parseSession(text);assert.equal(back.input.version,9);assert.equal(N.sessionText(back.input,back.runs,back.selected,back.comparison,back.view),text);
 assert.equal(JSON.parse(N.sessionText(input(),[closedRun('0000000a')],'0000000a',['0000000a','0000000a'],view)).version,7);
 assert.equal(JSON.parse(N.sessionText(P.withStudy(input(),{modeCount:3}),[closedRun('0000000a')],'0000000a',['0000000a','0000000a'],view)).version,9);
});
test('V15: what a version 10 file may hold is checked by name',()=>{
 const runs=[openRun('0000000b',{pml_check:R.pairCheck(RE,IM,record())})];
 const text=N.sessionText(input(),runs,'0000000b',['0000000b','0000000b'],view);
 const redigest=d=>{for(const r of d.runs){delete r.digest;r.digest=S.recordDigest(r);}return d;};
 const edit=f=>{const d=JSON.parse(text);f(d);return S.sessionJson(redigest(d));};
 for(const [f,message] of [
  [d=>{d.version=9;},'Run 1: unknown key "open_boundary".'],
  [d=>{d.runs[0].settings.pml.thickness='2000 nm';},'Run 1: the PML thickness must be 1000 nm.'],
  [d=>{d.runs[0].settings.pml.open_edges=['top','left'];},'Run 1: invalid open edges.'],
  [d=>{d.runs[0].settings.pml.target='2.46';},'Run 1: invalid search target.'],
  [d=>{d.runs[0].settings.pml.target='1.450';},'Search near n_eff must lie between 1.45 and 3.4777.'],
  [d=>{d.runs[0].settings.boundary='PEC';},'Run 1: invalid open boundary settings.'],
  [d=>{d.runs[0].settings.adapter='optical-shapes-v10';},'Run 1: unsupported run settings (a version 10 file writes optical-shapes-v8 or optical-shapes-v9).'],
  [d=>{delete d.runs[0].open_boundary;},'Run 1: invalid open boundary record.'],
  [d=>{d.runs[0].open_boundary.candidates[0].effective_index.re=2.5;},'Run 1: its modes are not the selected candidates of its open boundary record.'],
  [d=>{d.runs[0].pml_check.pml_strength=3;},'Run 1: invalid PML check.'],
  [d=>{d.runs[0].effective_index=d.runs[0].effective_index.re;},'Run 1: a run with an open boundary has complex effective indices.'],
 ])assert.throws(()=>N.parseSession(edit(f)),{message},message);
 // a closed run holds no open boundary record
 const closed=N.sessionText(P.withStudy(input(),{openBoundary:R.openChoice()}),[closedRun('0000000a')],'0000000a',['0000000a','0000000a'],view);
 const d=JSON.parse(closed);d.runs[0].pml_check={pml_strength:6,paired:[null,null]};
 assert.throws(()=>N.parseSession(S.sessionJson(redigest(d))),{message:'Run 1: a closed window has no open boundary record.'});
 // a version 9 session does not hold inputs of version 9
 const nine=JSON.parse(closed);nine.version=9;assert.throws(()=>N.parseSession(S.sessionJson(redigest(nine))),{message:'A version 9 session holds an input file of version 6 to 8.'});
});
test('review: the save and recovery stamps change when a run\'s PML check arrives',()=>{
 const run=N.validateRun(openRun('0000000b'));
 const before=JSON.stringify(N.runStampEntry(run)),after=JSON.stringify(N.runStampEntry({...run,pml_check:R.pairCheck(RE,IM,record())}));
 assert.notEqual(before,after);
 // a closed run's entry is as before
 assert.deepEqual(N.runStampEntry(N.validateRun(closedRun('0000000a'))),['0000000a','2026-11-22T01:00:00.000Z','',false]);
});
test('review: a session opens with its own outer boundary choice; only v6/v7 inputs take the selected run\'s study',()=>{
 const open=N.validateRun(openRun('0000000b'));
 // a version 10 file whose inputs chose Closed (version 7) and an open run: the inputs stay closed
 assert.deepEqual(N.sessionStudyInput(input(),open),input());
 assert.equal(P.projectBoundary(N.sessionStudyInput(input(),open)),null);
 const v9=P.withStudy(input(),{openBoundary:R.openChoice()});assert.equal(N.sessionStudyInput(v9,open),v9);
 // as before: a version 7 input takes Modes to find of the selected run
 const four=N.validateRun({...closedRun('0000000a'),settings:N.opticalSettings(1550,30,4)});
 assert.equal(N.sessionStudyInput(input(),four).model.modeCount,4);
});
test('review: a PML check is stored on its run without changing the selected run; a run no longer kept cannot take it',()=>{
 const a=N.validateRun(closedRun('0000000a')),b=N.validateRun(openRun('0000000b')),check=R.pairCheck(RE,IM,record());
 const done=N.withPmlCheck([a,b],a,'0000000b',check);
 assert.equal(done.selected,a);assert.deepEqual(done.runs[1].pml_check,check);assert.equal(done.runs[0],a);
 assert.equal(N.withPmlCheck([a,b],b,'0000000b',check).selected.pml_check.pml_strength,6);
 assert.throws(()=>N.withPmlCheck([a],a,'0000000b',check),e=>e.code==='solver-failed'&&/no longer kept; the check is not stored\. Detach this job\./.test(e.message));
});
test('a pending job keeps its open boundary, the PML check request and the run a check belongs to',()=>{
 const base={version:1,job:'0000000c',serverInstance:'0'.repeat(32),serverVersion:'0.0.0',startedAt:'2026-11-23T01:00:00.000Z',revision:0,input:input()};
 assert.deepEqual(J.validatePending({...base,openBoundary:{edges:ALL,target:2.46},pmlCheck:true}).openBoundary,{edges:ALL,target:2.46});
 assert.deepEqual((({checkOf,checkIndex,checkCount})=>[checkOf,checkIndex,checkCount])(J.validatePending({...base,openBoundary:{edges:ALL,target:2.46},checkOf:'0000000b',checkIndex:1,checkCount:2})),['0000000b',1,2]);
 assert.equal(J.validatePending(base).openBoundary,undefined);
 for(const bad of [{pmlCheck:true},{openBoundary:{edges:ALL}},{openBoundary:{edges:{left:'closed',right:'closed',bottom:'closed',top:'closed'},target:2.46}},{openBoundary:{edges:ALL,target:2.46},checkOf:'x',checkIndex:0,checkCount:1},{openBoundary:{edges:ALL,target:2.46},pmlCheck:true,checkOf:'0000000b',checkIndex:0,checkCount:1},
  {openBoundary:{edges:ALL,target:2.46},checkOf:'0000000b'},{openBoundary:{edges:ALL,target:2.46},checkOf:'0000000b',checkIndex:2,checkCount:2},{checkIndex:0}])
  assert.throws(()=>J.validatePending({...base,...bad}),/Invalid pending/);
});
