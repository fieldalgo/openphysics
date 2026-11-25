// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Slice S2 of the guided / leaky notes of open-boundary modes (design draft measured on main
// 2318e5f, gates pre-registered there): workspace-mode-channel.mjs, a pure classification from data
// a run stores (Re n_eff, the input shapes, the open edges, the wavelength, the index table of S1).
// G10: the unit table of the draft's §3.2.1 and the exact texts of §4.1 and §4.2. A closed run gives
// []; a run without fields is still classified. No solve. Plain text comparison only.
const test=require('node:test');const assert=require('node:assert/strict');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
let C,B;
test.before(async()=>{C=await import(STATIC+'workspace-mode-channel.mjs');B=await import(STATIC+'workspace-open-boundary.mjs');});

const strip={name:'Core',type:'rect',material:'Silicon',x:-250,y:0,w:500,h:220};
const substrate={name:'Substrate',type:'rect',material:'Silicon',x:-1500,y:-1200,w:3000,h:700};
const ALL=['left','right','bottom','top'];
const SI=()=>B.indexAt('Silicon',1550),SIO2=()=>B.indexAt('Silica',1550);
const profiles=(shapes,open,nm=1550)=>C.edgeProfiles(shapes,open,nm);
const kindOf=(shapes,open,x,nm=1550)=>C.classifyIndex(x,C.edgeProfiles(shapes,open,nm));
// an open run as Studio keeps it (no field: the category needs none)
const openRun=(shapes,open,re,im,{pml=null,nm=1550,boundary='PML'}={})=>({job:'0000000c',settings:{adapter:'optical-shapes-v9',boundary,mode_count:re.length,vacuum_wavelength:nm+' nm',core_element_size:'30 nm',
  ...(boundary==='PML'?{pml:{thickness:'1000 nm',open_edges:open,target:'2.460'}}:{})},
 input:{model:{shapes}},effective_index:boundary==='PML'?{re,im}:re,
 ...(boundary==='PML'?{open_boundary:{schema:'openphysics.pml-candidates/2',selected_candidates:re.map((_,i)=>i+1),
  candidates:re.map((r,i)=>({candidate:i+1,effective_index:{re:r,im:im[i]},physical_l2_fraction:1-(pml?.[i]??1e-3),pml_l2_fraction:pml?.[i]??1e-3,reasons:['selected_near_target'],selected:true}))}}:{})});

test('G10: the T16 shapes with every edge open: Substrate fills the bottom and both lower corners',()=>{
 const p=profiles([strip,substrate],ALL);
 assert.deepEqual(Object.keys(p),ALL);
 for(const e of ['bottom','left','right'])assert.equal(p[e].nLo,SI(),e);
 assert.equal(p.bottom.nHi,SI());assert.equal(p.top.nLo,SIO2());assert.equal(p.top.nHi,SIO2());
 assert.deepEqual(p.bottom.lo.map(r=>r.name),['Substrate']);
 const c=kindOf([strip,substrate],ALL,2.441);
 assert.equal(c.kind,'leaky');assert.deepEqual(c.regions.map(r=>[r.name,r.n]),[['Substrate',SI()]]);
});

test('G10: the T16 shapes with the bottom edge closed: no claim, a layer on the left and right',()=>{
 const p=profiles([strip,substrate],['left','right','top']);
 assert.deepEqual(Object.keys(p),['left','right','top']);
 // the top-left corner is silica; the bottom-left corner is not open on both sides
 assert.equal(p.left.nLo,SIO2());assert.equal(p.left.nHi,SI());assert.equal(p.right.nLo,SIO2());assert.equal(p.right.nHi,SI());
 const c=kindOf([strip,substrate],['left','right','top'],2.441);
 assert.equal(c.kind,'layer');assert.deepEqual(c.regions.map(r=>r.name),['Substrate']);assert.deepEqual(c.sides,['left','right']);
});

test('G10: the T16 shapes with only the top edge open: guided at 1.485',()=>{
 const c=kindOf([strip,substrate],['top'],1.485);
 assert.equal(c.kind,'guided');assert.deepEqual(c.regions.map(r=>[r.name,r.n]),[[C.BACKGROUND_NAME,SIO2()]]);
});

test('G10: the template: every edge is uniform silica; 1.460 is too close, 1.470 is guided',()=>{
 const p=profiles([strip],ALL);
 for(const e of ALL){assert.equal(p[e].nLo,SIO2(),e);assert.equal(p[e].nHi,SIO2(),e);}
 assert.equal(kindOf([strip],ALL,1.460).kind,'near');assert.deepEqual(kindOf([strip],ALL,1.460).regions.map(r=>r.name),[C.BACKGROUND_NAME]);
 assert.equal(kindOf([strip],ALL,1.470).kind,'guided');
});

test('G10: a rect covering the whole bottom edge between closed left and right edges: n_lo is its index',()=>{
 const p=profiles([strip,substrate],['bottom','top']);
 assert.equal(p.bottom.nLo,SI());assert.equal(p.bottom.nHi,SI());
 const nitride={...substrate,material:'Silicon nitride'};
 assert.equal(profiles([strip,nitride],['bottom']).bottom.nLo,B.indexAt('Silicon nitride',1550));
});

test('G10: polygons and circles touching an edge: the extruded profile, a circle\'s chord, corners filled only between two open edges',()=>{
 // a triangle with legs along the bottom and left edges, its right angle at the bottom-left corner
 const wedge={name:'Wedge',type:'polygon',material:'Silicon',points:[[-1500,-1200],[0,-1200],[-1500,0]]};
 let p=profiles([strip,wedge],ALL);
 // the bottom edge: Wedge from -1500 to 0, silica after; the corner square is Wedge's
 assert.equal(p.bottom.nHi,SI());assert.equal(p.bottom.nLo,SI());assert.deepEqual(p.bottom.lo.map(r=>r.name),['Wedge',C.BACKGROUND_NAME]);
 assert.equal(p.left.nLo,SI());
 // the right edge does not meet Wedge: its lower corner is silica
 assert.equal(p.right.nHi,SIO2());assert.equal(p.right.nLo,SIO2());
 // with the left edge closed, the bottom-left corner is not a quarter-space: Wedge reaches the bottom only as a layer
 p=profiles([strip,wedge],['right','bottom','top']);
 assert.equal(p.bottom.nHi,SI());assert.equal(p.bottom.nLo,SIO2());
 assert.equal(kindOf([strip,wedge],['right','bottom','top'],2.44).kind,'layer');
 // a polygon touching the bottom edge along a segment that is not at a corner: a layer
 const foot={name:'Foot',type:'polygon',material:'Gallium arsenide',points:[[-500,-1200],[500,-1200],[0,-800]]};
 p=profiles([strip,foot],ALL);
 assert.equal(p.bottom.nHi,B.indexAt('Gallium arsenide',1550));assert.equal(p.bottom.nLo,SIO2());
 // a circle touching the top edge contributes its chord (a point): its index is in n_hi, never in n_lo
 const ball={name:'Ball',type:'circle',material:'Indium phosphide',cx:0,cy:1100,r:100};
 p=profiles([strip,ball],ALL);
 assert.equal(p.top.nHi,B.indexAt('Indium phosphide',1550));assert.equal(p.top.nLo,SIO2());
 assert.equal(kindOf([strip,ball],ALL,2.44).kind,'layer');
 // a polygon vertex at the corner whose edges are not along both window edges does not fill the corner
 const spike={name:'Spike',type:'polygon',material:'Silicon',points:[[-1500,-1200],[-1000,-1200],[-1200,-900]]};
 p=profiles([strip,spike],ALL);
 assert.equal(p.left.nLo,SIO2());assert.equal(p.bottom.nLo,SIO2());assert.equal(p.bottom.nHi,SI());
});

test('G10: two shapes of different index on one edge: n_hi is the larger; the later shape wins where they overlap',()=>{
 const left={name:'Left',type:'rect',material:'Silicon nitride',x:-1500,y:-1200,w:1500,h:300};
 const right={name:'Right',type:'rect',material:'Indium phosphide',x:0,y:-1200,w:1500,h:300};
 let p=profiles([strip,left,right],['bottom']);
 assert.equal(p.bottom.nHi,B.indexAt('Indium phosphide',1550));
 // a later rect over the whole bottom edge hides both: the profile beyond the edge is the later one alone
 const cover={name:'Cover',type:'rect',material:'Sapphire (ordinary)',x:-1500,y:-1200,w:3000,h:200};
 p=profiles([strip,left,right,cover],['bottom']);
 assert.equal(p.bottom.nLo,B.indexAt('Sapphire (ordinary)',1550));assert.equal(p.bottom.nHi,B.indexAt('Sapphire (ordinary)',1550));
 // the earlier one over a later partial one: the full-width cover first, then Right on top
 p=profiles([strip,cover,right],['bottom']);
 assert.equal(p.bottom.nHi,B.indexAt('Indium phosphide',1550));assert.equal(p.bottom.nLo,-Infinity);
 // several regions above x + δ: every one listed, highest index first (Phosphide fills the left edge
 // and the bottom-left corner, Nitride the bottom-right corner)
 const c=kindOf([strip,{...left,x:-1500,w:3000,material:'Silicon nitride',name:'Nitride'},{...right,name:'Phosphide',y:-1200,x:-1500,w:300,h:2400}],['left','right','bottom'],1.6);
 assert.equal(c.kind,'leaky');assert.deepEqual(c.regions.map(r=>r.name),['Phosphide','Nitride']);
});

test('G10: an Air shape covering an open edge: n_lo is 1, never leaky for a listed mode',()=>{
 const air={name:'Gap',type:'rect',material:'Air',x:-1500,y:-1200,w:3000,h:300};
 const p=profiles([strip,air],['bottom']);
 assert.equal(p.bottom.nLo,1);assert.equal(p.bottom.nHi,1);
 assert.equal(kindOf([strip,air],['bottom'],1.4501).kind,'guided');
});

test('G10: x exactly n ± δ is no claim (inclusive on the no-claim side)',()=>{
 assert.equal(C.CHANNEL_DELTA,0.02);
 const n=SIO2(),s=SI();
 assert.equal(kindOf([strip],ALL,n+0.02).kind,'near');
 assert.equal(kindOf([strip],ALL,n+0.02+1e-6).kind,'guided');
 assert.equal(kindOf([strip,substrate],ALL,s-0.02).kind,'near');
 assert.equal(kindOf([strip,substrate],ALL,s-0.02-1e-6).kind,'leaky');
});

test('G10: the material indices are those of the run\'s wavelength',()=>{
 const p=profiles([strip,substrate],ALL,1400);
 assert.equal(p.bottom.nLo,B.indexAt('Silicon',1400));assert.equal(p.top.nHi,B.indexAt('Silica',1400));
 // the template at 1400 nm: silica is 1.44578, so 1.464 is within δ there and guided at 1550 nm
 assert.equal(kindOf([strip],ALL,1.465,1400).kind,'near');assert.equal(kindOf([strip],ALL,1.465,1550).kind,'guided');
});

test('the texts of §4.1 (standalone and after a region note)',()=>{
 const sub=[{name:'Substrate',n:3.47772}];
 assert.equal(C.channelText(0,{kind:'leaky',x:2.44126,regions:sub},{resolved:true}),'Mode 1 is a leaky mode: Re n_eff 2.441 is below the index of Substrate (3.478), which reaches the open window edge, so light can leak into Substrate. The loss shown is that leakage; it is part of this structure, not a fault of the solve.');
 assert.equal(C.channelText(0,{kind:'leaky',x:2.44126,regions:sub},{resolved:true,follows:true}),'It is a leaky mode: Re n_eff 2.441 is below the index of Substrate (3.478), which reaches the open window edge, so light can leak into Substrate. The loss shown is that leakage; it is part of this structure, not a fault of the solve.');
 assert.equal(C.channelText(1,{kind:'leaky',x:2.44126,regions:sub},{resolved:false}),'Mode 2 is a leaky mode: Re n_eff 2.441 is below the index of Substrate (3.478), which reaches the open window edge, so light can leak into Substrate. This solve resolves no leakage loss.');
 assert.equal(C.channelText(1,{kind:'leaky',x:1.6,regions:[{name:'Phosphide',n:3.16493},{name:'Nitride',n:1.99628}]},{resolved:true}),'Mode 2 is a leaky mode: Re n_eff 1.600 is below the index of Phosphide (3.165) and Nitride (1.996), which reach the open window edge, so light can leak into Phosphide and Nitride. The loss shown is that leakage; it is part of this structure, not a fault of the solve.');
 const bg=[{name:C.BACKGROUND_NAME,n:1.44402}];
 assert.equal(C.channelText(0,{kind:'guided',x:2.4429,regions:bg},{resolved:true}),'Mode 1 is guided: Re n_eff 2.443 is above the index of every material at the open window edges (the highest is the silica background, 1.444), so it cannot leak. The loss shown is numerical (mesh and PML), not leakage.');
 assert.equal(C.channelText(0,{kind:'guided',x:2.4429,regions:bg},{resolved:true,follows:true}),'It is guided: Re n_eff 2.443 is above the index of every material at the open window edges (the highest is the silica background, 1.444), so it cannot leak. The loss shown is numerical (mesh and PML), not leakage.');
 assert.equal(C.channelText(2,{kind:'near',x:1.46,regions:bg},{resolved:true}),'Mode 3: Re n_eff 1.460 is within 0.02 of the index of the silica background (1.444) at the open window edge, closer than this solve resolves; Studio does not say whether it is guided or leaky.');
 assert.equal(C.channelText(2,{kind:'near',x:1.46,regions:bg},{resolved:true,follows:true}),'Re n_eff 1.460 is within 0.02 of the index of the silica background (1.444) at the open window edge, closer than this solve resolves; Studio does not say whether it is guided or leaky.');
 // §4.2, G5: the mode near 2.441 with the bottom edge closed
 assert.equal(C.channelText(0,{kind:'layer',x:2.44110903,regions:sub,sides:['left','right']},{resolved:true}),'Mode 1: Re n_eff 2.441 is below the index of Substrate (3.478), which reaches the open left and right edges only as a layer. Whether light can leak into it depends on that layer\'s own modes, which Studio does not compute; Studio does not say whether this mode is guided or leaky.');
 assert.equal(C.channelText(0,{kind:'layer',x:2.44,regions:sub,sides:['bottom']},{resolved:true,follows:true}),'Re n_eff 2.440 is below the index of Substrate (3.478), which reaches the open bottom edge only as a layer. Whether light can leak into it depends on that layer\'s own modes, which Studio does not compute; Studio does not say whether this mode is guided or leaky.');
});

test('the gain bound: b = max(1e-10, 1e-2 f_pml) max(1, |Re n_eff|), as the engine\'s',()=>{
 assert.equal(C.gainBound(2.44,1e-3),1e-5*2.44);assert.equal(C.gainBound(0.5,1e-3),1e-5);
 assert.equal(C.gainBound(2,1e-12),2e-10);assert.equal(C.gainBound(2,Number.NaN),2e-10);
});

test('modeChannel and channelNotes on runs: a closed run gives [], a run without fields is classified, the guard',()=>{
 // a closed run: nothing
 assert.deepEqual(C.modeChannel(openRun([strip,substrate],[],[2.9,2.73],[],{boundary:'PEC'})),[]);
 assert.deepEqual(C.channelNotes(openRun([strip,substrate],[],[2.9,2.73],[],{boundary:'PEC'})),[]);
 assert.deepEqual(C.modeChannel(null),[]);
 // T16-like, no field
 const run=openRun([strip,substrate],ALL,[2.44126325,1.77279036,1.48642654],[8.28e-5,2.857e-3,7.92e-3],{pml:[2e-4,4.8e-3,0.0217]});
 assert.equal(run.field,undefined);
 const c=C.modeChannel(run);
 assert.deepEqual(c.map(m=>[m.mode,m.kind,m.resolved]),[[0,'leaky',true],[1,'leaky',true],[2,'leaky',true]]);
 assert.deepEqual(C.channelNotes(run).map(n=>[n.mode,n.kind,n.text]),[
  [0,'leaky','Mode 1 is a leaky mode: Re n_eff 2.441 is below the index of Substrate (3.478), which reaches the open window edge, so light can leak into Substrate. The loss shown is that leakage; it is part of this structure, not a fault of the solve.'],
  [1,'leaky','Mode 2 is a leaky mode: Re n_eff 1.773 is below the index of Substrate (3.478), which reaches the open window edge, so light can leak into Substrate. The loss shown is that leakage; it is part of this structure, not a fault of the solve.'],
  [2,'leaky','Mode 3 is a leaky mode: Re n_eff 1.486 is below the index of Substrate (3.478), which reaches the open window edge, so light can leak into Substrate. The loss shown is that leakage; it is part of this structure, not a fault of the solve.']]);
 // a leaky mode whose loss is within the bound: the unresolved variant
 const quiet=openRun([strip,substrate],ALL,[2.44],[1e-7],{pml:[1e-3]});
 assert.equal(C.channelNotes(quiet)[0].text,'Mode 1 is a leaky mode: Re n_eff 2.440 is below the index of Substrate (3.478), which reaches the open window edge, so light can leak into Substrate. This solve resolves no leakage loss.');
 // guided within the bound: shown; guided beyond it: no category text
 const template=openRun([strip],ALL,[2.4429,1.77],[-5e-12,1.36e-8],{pml:[1e-6,1.8e-6/1.77/1e-2]});
 assert.deepEqual(C.channelNotes(template).map(n=>[n.mode,n.kind]),[[0,'guided'],[1,'guided']]);
 const loud=openRun([strip],ALL,[2.4429],[1e-4],{pml:[1e-3]});
 assert.equal(C.modeChannel(loud)[0].kind,'guided');assert.equal(C.modeChannel(loud)[0].resolved,true);
 assert.deepEqual(C.channelNotes(loud),[]);
 // a mode without its candidate record: the engine's floor 1e-10 max(1, |Re|)
 const bare={...template,open_boundary:undefined};
 assert.deepEqual(C.modeChannel(bare).map(m=>m.bound),[1e-10*2.4429,1e-10*1.77]);
 // the page's form of a run (effective_index Re, effective_index_im; input.model.wavelength) reads the same
 const page={...run,settings:{...run.settings,vacuum_wavelength:undefined},input:{model:{shapes:run.input.model.shapes,wavelength:1550}},effective_index:run.effective_index.re,effective_index_im:run.effective_index.im};
 assert.deepEqual(C.modeChannel(page),C.modeChannel(run));
 // a wavelength Studio cannot read: no category
 assert.deepEqual(C.modeChannel({...run,settings:{...run.settings,vacuum_wavelength:'1.55 um'}}),[]);
 assert.deepEqual(C.modeChannel({...page,input:{model:{shapes:run.input.model.shapes,wavelength:1400.5}}}).map(c=>c.kind),['leaky','leaky','leaky']);
 assert.deepEqual(C.modeChannel(openRun([strip],ALL,[2.44],[0],{nm:1800})),[]);
});

test('the combined note: the region note, then the channel text reworded',()=>{
 const note=C.combinedNote('Mode 1 is the core mode: 64 % of |E|² in the window (PML excluded) is in Core, which does not touch the window edge.',0,{kind:'leaky',x:2.44126325,regions:[{name:'Substrate',n:3.47772}],resolved:true});
 assert.equal(note,'Mode 1 is the core mode: 64 % of |E|² in the window (PML excluded) is in Core, which does not touch the window edge. It is a leaky mode: Re n_eff 2.441 is below the index of Substrate (3.478), which reaches the open window edge, so light can leak into Substrate. The loss shown is that leakage; it is part of this structure, not a fault of the solve.');
});
