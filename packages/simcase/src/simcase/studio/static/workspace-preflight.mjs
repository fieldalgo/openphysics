// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

// A coded diagnostic of /api/validate (units and naming batch: diagnostics replace notes).
const diagnostic=d=>d!==null&&typeof d==='object'&&['code','severity','path','message'].every(k=>typeof d[k]==='string');
export class OpticalPreflight {
 constructor(api,onChange=()=>{}){this.api=api;this.onChange=onChange;this.busy=false;this.record=null;this.error='';}
 async check(input,doc,serverInstance){
  if(this.busy)return;
  const capture=JSON.parse(JSON.stringify(input)),document=JSON.parse(JSON.stringify(doc));
  this.busy=true;this.error='';this.onChange();
  try{
   const response=await this.api('/api/validate?workspace_instance='+encodeURIComponent(serverInstance),{doc:document});
   if(typeof response?.ok!=='boolean')throw new Error('Invalid validation response.');
   if(!response.ok&&typeof response.error!=='string')throw new Error('Validation failed without a description.');
   if(response.ok&&typeof response.summary!=='string')throw new Error('Invalid validation summary.');
   if(response.ok&&(!Array.isArray(response.diagnostics)||!response.diagnostics.every(diagnostic)))throw new Error('Invalid validation diagnostics.');
   const diagnostics=Array.isArray(response.diagnostics)&&response.diagnostics.every(diagnostic)?response.diagnostics.map(({code,severity,path,message})=>({code,severity,path,message})):[];
   this.record={input:capture,signature:JSON.stringify(capture),serverInstance,checkedAt:new Date().toISOString(),ok:response.ok,error:response.ok?'':response.error,summary:response.ok?response.summary:'',diagnostics};
  }catch(error){this.error=error.message;}finally{this.busy=false;this.onChange();}
 }
}
