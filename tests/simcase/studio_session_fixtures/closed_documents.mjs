// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// The closed-window optical documents of K1 (design "Search near n_eff for closed-window runs"):
// {label: the document's JSON text}. Run once with the static folder of main 13f07f4 (before
// optical-shapes-v10) to write optical-documents-closed-13f07f4.json:
//   node closed_documents.mjs <static folder URL>/ > optical-documents-closed-13f07f4.json
// tests/simcase/studio_closed_target.cjs builds the same states with this Studio's builder.
export const STRIP={name:'Core',type:'rect',material:'Silicon',x:-250,y:0,w:500,h:220};
export const SUBSTRATE={name:'Substrate',type:'rect',material:'Silicon',x:-1500,y:-1200,w:3000,h:700};
const optical={electric:false,heat:false,structure:false,optics:true,wavelength:1550,coreMesh:30};
export const SETUP={materials:{Core:'Silicon',Oxide:'Silica',Heater:''}};
const CLOSED={edges:{left:'closed',right:'closed',bottom:'closed',top:'closed'}};
/** [label, state] of every closed document K1 covers. */
export function closedStates(){
 const out=[];
 for(const [kind,shapes] of [['template',undefined],['strip over substrate',[STRIP,SUBSTRATE]]])
  for(const modeCount of [1,2,8])for(const groupIndex of [false,true]){
   const state={...optical,width:500,height:220,...(shapes?{shapes}:{}),modeCount,...(groupIndex?{groupIndex}:{})};
   out.push([`${kind} · ${modeCount} modes${groupIndex?' · n_g':''}`,state]);
   out.push([`${kind} · ${modeCount} modes${groupIndex?' · n_g':''} · every edge closed`,{...state,openBoundary:CLOSED}]);
  }
 return out;
}
if(process.argv[2]){
 const O=await import(process.argv[2]+'workspace-optical.mjs');
 process.stdout.write(JSON.stringify(Object.fromEntries(closedStates().map(([label,state])=>[label,JSON.stringify(O.opticalDocument(state,SETUP))])),null,1)+'\n');
}
