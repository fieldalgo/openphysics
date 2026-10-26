// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

export async function solverApi(path,body,fetchImpl=globalThis.fetch){
 const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),120000);
 try{const response=await fetchImpl(path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined,signal:controller.signal});let data;try{data=await response.json();}catch{throw new Error('Use the solver-enabled workspace server. Response is not JSON.');}if(!response.ok)throw Object.assign(new Error(typeof data.detail==='string'?data.detail:'Local solver request failed.'),{status:response.status});return data;}finally{clearTimeout(timeout);}
}
