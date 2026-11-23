// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
import {degenerateGroups,polarizationWord,polarizationShare,tePercent,modeTableRows,opticalModes,areaText,lossText,lossColumn,groupIndexCell,AREA_HELP,AREA_MEAN_NOTE,AREA_PAIR_NOTE} from './workspace-modes.mjs';
import {isOpenRun,openLoss,LOSS_FLOOR,FLOOR_TEXT,FLOOR_HELP} from './workspace-open-run.mjs';

// Matching the modes of two runs by field overlap, in Studio only (the engine never sees both
// runs). Each run keeps its own centroid samples, so the overlap is taken on a common grid:
// uniform points over the intersection of the two windows, spacing ½ · min(core element size of
// A, of B), at most 400 × 400 points. A point samples the centroid E_t = (E_x, E_y) of the
// triangle that contains it; a point in no triangle of a run is left out of every sum.
// η(a, b) = |Σ conj(E_A,a)·E_B,b|² / (Σ|E_A,a|² · Σ|E_B,b|²), E_t only like the engine's tracker,
// and invariant under each mode's phase and scale. A degenerate pair (M1's rule, workspace-modes)
// is one unit, matched by the mean squared cosine of the principal angles between the spans.

export const MATCH_THRESHOLD=0.8;       // the tracker's mode_tracking_threshold
export const MATCH_MARGIN=0.1;          // the tracker's mode_tracking_margin_threshold
export const MAX_GRID_POINTS=400;       // per axis
export const MAX_MATCH_MODES=8;         // units per run for the brute-force assignment
export const MATCH_NOTE='Matched by field overlap ≥ 0.8 on a common grid. A low overlap means the mode changed shape between designs.';
export const COMPARE_MATCH_TEXT='Compare matches them between runs by field overlap.';

/** The window of a run: the bounding box of its node coordinates. */
export function fieldWindow(field){
 let x0=Infinity,x1=-Infinity,y0=Infinity,y1=-Infinity;
 for(const [x,y] of field.node_coordinates){if(x<x0)x0=x;if(x>x1)x1=x;if(y<y0)y0=y;if(y>y1)y1=y;}
 return {x0,x1,y0,y1};
}
/** The common grid: cell centres of n_x × n_y cells over the intersection of the two windows,
 * n = min(cap, ceil(L / s)), so the spacing is at most s (or L / cap). null when the windows
 * do not overlap. */
export function commonGrid(fieldA,fieldB,spacing,{cap=MAX_GRID_POINTS}={}){
 if(!(spacing>0))throw new Error('The grid spacing must be positive.');
 const a=fieldWindow(fieldA),b=fieldWindow(fieldB);
 const x0=Math.max(a.x0,b.x0),x1=Math.min(a.x1,b.x1),y0=Math.max(a.y0,b.y0),y1=Math.min(a.y1,b.y1);
 if(!(x1>x0&&y1>y0))return null;
 const nx=Math.max(1,Math.min(cap,Math.ceil((x1-x0)/spacing*(1-1e-12)))),ny=Math.max(1,Math.min(cap,Math.ceil((y1-y0)/spacing*(1-1e-12))));
 return {x0,x1,y0,y1,nx,ny,dx:(x1-x0)/nx,dy:(y1-y0)/ny};
}
/** For each grid point (index j·n_x + i), the triangle of the run that contains it, or -1.
 * A point on an edge shared by two triangles takes the first. */
export function locate(field,grid){
 const {x0,y0,nx,ny,dx,dy}=grid,X=field.node_coordinates,out=new Int32Array(nx*ny).fill(-1);
 field.triangles.forEach((t,k)=>{
  const [ax,ay]=X[t[0]],[bx,by]=X[t[1]],[cx,cy]=X[t[2]];
  const det=(bx-ax)*(cy-ay)-(by-ay)*(cx-ax);if(det===0)return;
  const i0=Math.max(0,Math.ceil((Math.min(ax,bx,cx)-x0)/dx-0.5)),i1=Math.min(nx-1,Math.floor((Math.max(ax,bx,cx)-x0)/dx-0.5));
  const j0=Math.max(0,Math.ceil((Math.min(ay,by,cy)-y0)/dy-0.5)),j1=Math.min(ny-1,Math.floor((Math.max(ay,by,cy)-y0)/dy-0.5));
  for(let j=j0;j<=j1;j++){const y=y0+(j+0.5)*dy;for(let i=i0;i<=i1;i++){
   const p=j*nx+i;if(out[p]!==-1)continue;const x=x0+(i+0.5)*dx;
   // barycentric coordinates, inside with a round-off allowance on the edges
   const l1=((x-ax)*(cy-ay)-(y-ay)*(cx-ax))/det,l2=((bx-ax)*(y-ay)-(by-ay)*(x-ax))/det,eps=-1e-12;
   if(l1>=eps&&l2>=eps&&1-l1-l2>=eps)out[p]=k;
  }}
 });
 return out;
}
// complex numbers as [re, im]
const cmul=(a,b)=>[a[0]*b[0]-a[1]*b[1],a[0]*b[1]+a[1]*b[0]],cconj=a=>[a[0],-a[1]],cadd=(a,b)=>[a[0]+b[0],a[1]+b[1]];
const cdiv=(a,b)=>{const d=b[0]*b[0]+b[1]*b[1];return [(a[0]*b[0]+a[1]*b[1])/d,(a[1]*b[0]-a[0]*b[1])/d];};
/** Solve G X = R for a small complex G (Gaussian elimination with partial pivoting); null when
 * G is singular to round-off relative to its diagonal. */
function solve(G,R){
 const n=G.length,m=R[0].length,A=G.map((row,i)=>[...row.map(v=>[...v]),...R[i].map(v=>[...v])]);
 const scale=Math.max(...G.map((row,i)=>Math.hypot(...row[i])));
 for(let c=0;c<n;c++){
  let p=c;for(let r=c+1;r<n;r++)if(Math.hypot(...A[r][c])>Math.hypot(...A[p][c]))p=r;
  if(!(Math.hypot(...A[p][c])>1e-12*scale))return null;
  [A[c],A[p]]=[A[p],A[c]];
  for(let r=0;r<n;r++){if(r===c)continue;const f=cdiv(A[r][c],A[c][c]);for(let k=c;k<n+m;k++){const v=cmul(f,A[c][k]);A[r][k]=[A[r][k][0]-v[0],A[r][k][1]-v[1]];}}
 }
 return A.map((row,i)=>row.slice(n).map(v=>cdiv(v,row[i])));
}
/** Σσ² over the principal angles between span U and span V: trace(G_U⁻¹ C G_V⁻¹ Cᴴ) with the
 * Gram matrices G_U, G_V and the cross products C = ⟨U, V⟩. 0 when a span has no field. */
function squaredCosines(gram,ui,vi){
 const G=(I,J)=>I.map(i=>J.map(j=>gram[i][j]));
 const GU=G(ui,ui),GV=G(vi,vi),C=G(ui,vi);
 if(ui.some(i=>!(gram[i][i][0]>0))||vi.some(j=>!(gram[j][j][0]>0)))return 0;
 const X=solve(GU,C),Ch=vi.map((_,r)=>ui.map((_,c)=>cconj(C[c][r]))),Y=solve(GV,Ch);
 if(!X||!Y)return 0;
 let t=0;for(let i=0;i<ui.length;i++)for(let k=0;k<vi.length;k++)t+=cmul(X[i][k],Y[k][i])[0];
 return Math.min(Math.max(t,0),Math.min(ui.length,vi.length));
}
/** The units of a run in rank order: a degenerate group as one unit, every other mode alone. */
export function modeUnits(re){
 const groups=degenerateGroups(re),units=[];
 for(let i=0;i<re.length;){const g=groups.find(x=>x[0]===i);if(g){units.push(g);i=g.at(-1)+1;}else{units.push([i]);i++;}}
 return units;
}
/** The one-to-one assignment of units with the largest total η, by brute force over every
 * injective map of the smaller side into the larger (the first maximum found wins). */
export function bestAssignment(eta){
 const nA=eta.length,nB=nA?eta[0].length:0,flip=nA>nB,rows=flip?nB:nA,cols=flip?nA:nB,at=(r,c)=>flip?eta[c][r]:eta[r][c];
 let best=-Infinity,choice=[];const used=new Array(cols).fill(false),current=[];
 (function search(r,total){
  if(r===rows){if(total>best){best=total;choice=[...current];}return;}
  for(let c=0;c<cols;c++){if(used[c])continue;used[c]=true;current.push(c);search(r+1,total+at(r,c));current.pop();used[c]=false;}
 })(0,0);
 return choice.map((c,r)=>flip?[c,r]:[r,c]);
}
/**
 * Match the modes of runs A and B. Each side: {field: {node_coordinates (m), triangles, real,
 * imag}, neff: [Re n_eff, ...], coreSize: core element size in the coordinates' unit}.
 * options.spacing overrides ½ · min(coreSize); options.cap the 400 points per axis.
 * Returns {grid, points, unitsA, unitsB, eta (units × units), pairs: [{a, b, eta, accepted,
 * rowNext, columnNext, delta}], rows (per A unit: {unit, match|null, best}), unmatchedB
 * ([{unit, best}])}; or {error} when the windows do not overlap or a run has too many modes.
 */
export function matchModes(A,B,{spacing=null,cap=MAX_GRID_POINTS}={}){
 const unitsA=modeUnits(A.neff),unitsB=modeUnits(B.neff);
 if(unitsA.length>MAX_MATCH_MODES||unitsB.length>MAX_MATCH_MODES)return {error:`Matching compares at most ${MAX_MATCH_MODES} modes per run.`};
 const s=spacing??0.5*Math.min(A.coreSize,B.coreSize);
 const grid=commonGrid(A.field,B.field,s,{cap});if(!grid)return {error:'The two runs\' windows do not overlap.'};
 const la=locate(A.field,grid),lb=locate(B.field,grid);
 const points=[];for(let p=0;p<la.length;p++)if(la[p]>=0&&lb[p]>=0)points.push(p);
 if(!points.length)return {error:'No grid point lies in both meshes.'};
 // the transverse samples of every mode of both runs on the common points: [mode][point][Ex re, Ex im, Ey re, Ey im]
 const samples=(field,loc,n)=>Array.from({length:n},(_,m)=>{const re=field.real[m],im=field.imag[m],out=new Float64Array(points.length*4);
  points.forEach((p,q)=>{const t=loc[p];out[4*q]=re[t][0];out[4*q+1]=im[t][0];out[4*q+2]=re[t][1];out[4*q+3]=im[t][1];});return out;});
 const all=[...samples(A.field,la,A.neff.length),...samples(B.field,lb,B.neff.length)],n=all.length;
 // Gram matrix ⟨u, v⟩ = Σ conj(u)·v over every mode of both runs (uniform cells: the area cancels)
 const gram=Array.from({length:n},()=>new Array(n));
 for(let i=0;i<n;i++)for(let j=i;j<n;j++){
  const u=all[i],v=all[j];let re=0,im=0;
  for(let k=0;k<u.length;k+=2){re+=u[k]*v[k]+u[k+1]*v[k+1];im+=u[k]*v[k+1]-u[k+1]*v[k];}
  gram[i][j]=[re,im];gram[j][i]=[re,-im];
 }
 const off=A.neff.length;
 const eta=unitsA.map(u=>unitsB.map(v=>squaredCosines(gram,u,v.map(j=>j+off))/Math.max(u.length,v.length)));
 const mean=(re,u)=>u.reduce((t,i)=>t+re[i],0)/u.length;
 const next=(values,skip)=>values.reduce((m,v,k)=>k===skip?m:Math.max(m,v),0);
 const pairs=bestAssignment(eta).map(([i,j])=>{
  const value=eta[i][j],rowNext=next(eta[i],j),columnNext=next(eta.map(r=>r[j]),i);
  const accepted=value>=MATCH_THRESHOLD&&value-rowNext>=MATCH_MARGIN-1e-12&&value-columnNext>=MATCH_MARGIN-1e-12;
  return {a:i,b:j,unitA:unitsA[i],unitB:unitsB[j],eta:value,accepted,rowNext,columnNext,delta:mean(B.neff,unitsB[j])-mean(A.neff,unitsA[i])};
 });
 const argmax=values=>values.reduce((k,v,i)=>v>values[k]?i:k,0);
 const rows=unitsA.map((unit,i)=>{const match=pairs.find(p=>p.a===i&&p.accepted)||null,k=argmax(eta[i]);return {unit,match,best:unitsB.length?{eta:eta[i][k],unit:unitsB[k]}:null};});
 const unmatchedB=unitsB.map((unit,j)=>({unit,j})).filter(({j})=>!pairs.some(p=>p.b===j&&p.accepted)).map(({unit,j})=>{const column=eta.map(r=>r[j]),k=argmax(column);return {unit,best:unitsA.length?{eta:column[k],unit:unitsA[k]}:null};});
 return {grid,spacing:s,points:points.length,unitsA,unitsB,eta,pairs,rows,unmatchedB};
}

// ---- Words -------------------------------------------------------------------------------
/** "mode 1", or "modes 1–2 (pair)" for a degenerate pair (ranks from 1). */
export function unitName(unit){
 if(unit.length===1)return `mode ${unit[0]+1}`;
 return `modes ${unit[0]+1}–${unit.at(-1)+1} (${unit.length===2?'pair':'group of '+unit.length})`;
}
/** An overlap to 2 decimals; below the threshold never printed as "0.80". */
export function formatOverlap(eta){
 const text=eta.toFixed(2);
 return eta<MATCH_THRESHOLD&&text==='0.80'?(Math.floor(eta*1000)/1000).toFixed(3):text;
}
// a difference that rounds to zero reads +0.00000000, never −0.00000000
export const formatDelta=d=>(d>=0||Math.abs(d).toFixed(8)===(0).toFixed(8)?'+':'−')+Math.abs(d).toFixed(8);
/** "A mode 1 ↔ B mode 1 · overlap 0.99 · Δn_eff +0.00214000" */
export function matchText(pair){
 return `A ${unitName(pair.unitA)} ↔ B ${unitName(pair.unitB)} · overlap ${formatOverlap(pair.eta)} · Δn_eff ${formatDelta(pair.delta)}`;
}
/** "A mode 2: no match in B (best overlap 0.43, with B mode 2)"; side is the unmatched side. */
export function noMatchText(side,unit,best){
 const other=side==='A'?'B':'A';
 return `${side} ${unitName(unit)}: no match in ${other}${best?` (best overlap ${formatOverlap(best.eta)}, with ${other} ${unitName(best.unit)})`:''}`;
}

// ---- Optical runs -----------------------------------------------------------------------
const cache=new WeakMap();
// Matching with an open run on either side is off (slice P2, V13): on the template, a closed and an
// open run gave overlaps of 0.9903 (TE-like) and 0.9875 (TM-like) on the physical window, below the
// 0.99 registered. Every mode is then listed unmatched, each run with its own columns.
export const MATCH_OPEN_TEXT='Matching with an open boundary comes in a later version';
/** The rows of two runs that are not matched: every unit of A, then every unit of B. */
export function unmatchedModes(neffA,neffB){
 return {pairs:[],disabled:MATCH_OPEN_TEXT,rows:modeUnits(neffA).map(unit=>({unit,match:null,best:null})),unmatchedB:modeUnits(neffB).map(unit=>({unit,best:null}))};
}
/** The match of two optical runs (two-mode Studio runs, core mesh in nm, samples in metres),
 * kept per pair of run objects: a run's samples never change. With an open run on either side,
 * unmatchedModes. */
export function opticalMatch(a,b){
 let byB=cache.get(a);if(!byB){byB=new WeakMap();cache.set(a,byB);}
 if(!byB.has(b)&&(isOpenRun(a)||isOpenRun(b)))byB.set(b,unmatchedModes(a.effective_index,b.effective_index));
 if(!byB.has(b))byB.set(b,matchModes({field:a.field,neff:a.effective_index,coreSize:a.input.model.coreMesh*1e-9},{field:b.field,neff:b.effective_index,coreSize:b.input.model.coreMesh*1e-9}));
 return byB.get(b);
}
/** The polarization words of one unit of a run, as its modes table shows them. */
export function unitPolarization(run,unit){
 const {rows}=modeTableRows(opticalModes(run)),cell=rows[unit[0]].polarization;
 if(cell)return cell.text;
 const f=opticalModes(run)[unit[0]].fte;return Number.isFinite(f)?`${polarizationWord(f)} · ${polarizationWord(f)==='hybrid'?polarizationShare(f):tePercent(f)}`:'—';
}
/** The effective area of one unit of a run, {text, value, title}: the mode's, in µm², or for a
 * degenerate pair "mean x" (each member's value depends on the rotation within the pair). */
export function unitArea(run,unit){
 const modes=opticalModes(run),values=unit.map(i=>modes[i].area);
 if(!values.every(Number.isFinite))return {text:'—',value:null,title:AREA_HELP};
 if(unit.length===1){const pair=degenerateGroups(modes.map(m=>m.re)).some(g=>g.includes(unit[0]));return {text:areaText(values[0]),value:values[0],title:pair?AREA_HELP+'. '+AREA_PAIR_NOTE:AREA_HELP};}
 const mean=values.reduce((t,v)=>t+v,0)/values.length;
 return {text:'mean '+areaText(mean),value:mean,title:AREA_HELP+'. '+AREA_MEAN_NOTE};
}
/** The absorption loss of one unit of a run, {text, value, title}, as its modes table shows it:
 * the mode's ("0 dB/cm" for Im n_eff exactly 0), or for a degenerate pair "mean x dB/cm" of the
 * members' dB/cm ("0 dB/cm" when every member is lossless); "—" without a unit or a value. The
 * values come from the saved indices, so a run without fields has them too. */
export function unitLoss(run,unit){
 // each side's own column: absorption only for a closed window, with leakage for an open boundary
 const help=lossColumn({open:isOpenRun(run)}).help;
 if(!unit)return {text:'—',value:null,title:help};
 if(isOpenRun(run)){
  const lambda0=run.input.model.wavelength*1e-9,im=run.effective_index_im;
  if(unit.length===1){const i=unit[0],c=run.open_boundary.candidates.find(x=>x.selected&&x.effective_index.re===run.effective_index[i]&&x.effective_index.im===im[i]),cell=openLoss(im[i],lambda0,c?.attenuation_status??null);return {text:cell.text,value:cell.value,title:cell.title};}
  const cells=unit.map(i=>openLoss(im[i],lambda0)),mean=cells.reduce((t,c)=>t+c.value,0)/cells.length;
  return mean>=LOSS_FLOOR?{text:'mean '+mean.toPrecision(4)+' dB/cm',value:mean,title:help}:{text:'mean '+FLOOR_TEXT,value:mean,title:FLOOR_HELP};
 }
 const modes=opticalModes(run),members=unit.map(i=>modes[i]);
 if(members.every(m=>m.im===0))return {text:'0 dB/cm',value:0,title:help};
 if(unit.length===1){const m=members[0],text=lossText(m.im,m.loss);return {text,value:text==='—'?null:m.loss/100,title:help};}
 if(!members.every(m=>Number.isFinite(m.loss)||m.im===0))return {text:'—',value:null,title:help};
 const mean=members.reduce((t,m)=>t+(m.im===0?0:m.loss),0)/members.length;
 // lossText's digits for a nonzero Im n_eff: dB/m → dB/cm to 4 significant digits
 return {text:'mean '+(mean/100).toPrecision(4)+' dB/cm',value:mean/100,title:help};
}
/** The group index of one unit of a run, {text, value, title}, as its modes table shows it: the
 * mode's, or for a degenerate pair "mean x" of the members' n_g ("—" when a member has none). */
export function unitGroupIndex(run,unit){
 if(!unit)return {text:'—',value:null,title:''};
 const cells=unit.map(i=>groupIndexCell(run,i));
 if(unit.length===1||cells.some(c=>c.value===null))return unit.length===1?cells[0]:{...cells.find(c=>c.value===null)};
 const mean=cells.reduce((t,c)=>t+c.value,0)/cells.length;
 return {text:'mean '+mean.toFixed(4),value:mean,title:cells[0].title};
}
/** The Compare table rows of a match: accepted pairs and unmatched A units in A's rank order,
 * then the unmatched B units. kind: 'match' | 'a' | 'b'. */
export function compareMatchRows(match){
 const out=[];
 // matching off (an open run): each mode is listed with the reason, never "no match"
 if(match.disabled){
  for(const row of match.rows)out.push({kind:'a',text:`A ${unitName(row.unit)}: not matched (${match.disabled.toLowerCase()})`,unitA:row.unit,unitB:null,best:null});
  for(const u of match.unmatchedB)out.push({kind:'b',text:`B ${unitName(u.unit)}: not matched (${match.disabled.toLowerCase()})`,unitA:null,unitB:u.unit,best:null});
  return out;
 }
 for(const row of match.rows){
  if(row.match)out.push({kind:'match',text:matchText(row.match),pair:row.match,unitA:row.unit,unitB:row.match.unitB});
  else out.push({kind:'a',text:noMatchText('A',row.unit,row.best),unitA:row.unit,unitB:null,best:row.best});
 }
 for(const u of match.unmatchedB)out.push({kind:'b',text:noMatchText('B',u.unit,u.best),unitA:null,unitB:u.unit,best:u.best});
 return out;
}
/** The field picker of Compare: one entry per matched mode, {a, b, label}; a matched pair gives
 * one entry per member, in rank order (any rotation within a pair is a solution). */
// runs: optional {a, b}, the two runs: a single-mode pair then names its polarization word, once
// when A and B agree ("… · overlap 0.98 · TM-like"), else both ("… · A TE-like, B hybrid").
export function fieldChoices(match,runs={}){
 const out=[],word=(run,i)=>{const f=run?opticalModes(run)[i]?.fte:null;return Number.isFinite(f)?polarizationWord(f):null;};
 const words=(a,b)=>{const wa=word(runs.a,a),wb=word(runs.b,b);return !wa||!wb?'':wa===wb?' · '+wa:` · A ${wa}, B ${wb}`;};
 for(const p of match.pairs?.filter(x=>x.accepted)??[]){
  if(p.unitA.length===1&&p.unitB.length===1){out.push({a:p.unitA[0],b:p.unitB[0],label:`A mode ${p.unitA[0]+1} ↔ B mode ${p.unitB[0]+1} · overlap ${formatOverlap(p.eta)}${words(p.unitA[0],p.unitB[0])}`});continue;}
  p.unitA.forEach((a,k)=>{const b=p.unitB[Math.min(k,p.unitB.length-1)];out.push({a,b,label:`A mode ${a+1} ↔ B mode ${b+1} (pair, any rotation) · overlap ${formatOverlap(p.eta)}`});});
 }
 return out.sort((x,y)=>x.a-y.a);
}
