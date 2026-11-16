// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

// The installed physics providers (GET /api/providers), shown as text. A provider's
// strings are data: every one is escaped, and nothing a provider supplies is run or
// inserted as markup (docs/packages/simcase/providers.md).
export const MAX_PROVIDERS=256;
const STATUSES=['available','unavailable'];
const UNREADABLE='Studio sent a provider list this page cannot read. Update Studio and retry.';
const ESCAPES={'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'};
export function escapeHtml(value){return String(value).replace(/[&<>"']/g,c=>ESCAPES[c]);}
const text=value=>typeof value==='string'&&value.length>0&&value.length<=4096;
const optionalText=value=>value===null||text(value);
// The checked list, as fresh plain objects; anything else in the reply is refused.
export function readProviders(data){
 const list=data?.providers;
 if(!Array.isArray(list)||list.length>MAX_PROVIDERS)throw new Error(UNREADABLE);
 return list.map(p=>{
  if(!p||typeof p!=='object'||Array.isArray(p))throw new Error(UNREADABLE);
  const {name,version,distribution,protocol,status,error,kinds}=p;
  if(!text(name)||!optionalText(version)||!optionalText(distribution)||!(protocol===null||Number.isSafeInteger(protocol))||!STATUSES.includes(status)||!optionalText(error)||!Array.isArray(kinds)||!kinds.every(text))throw new Error(UNREADABLE);
  if((status==='unavailable')!==(error!==null))throw new Error(UNREADABLE);
  return {name,version,distribution,protocol,status,error,kinds:[...kinds]};
 });
}
const cell=value=>`<td>${value===null?'<span class="muted">unknown</span>':escapeHtml(value)}</td>`;
// A table of the checked list: name, version, distribution, status and physics kinds,
// and the error of an unavailable provider on its own row.
export function providersHtml(list){
 if(list.length===0)return '<p class="muted">No physics providers are installed.</p>';
 const rows=list.map(p=>`<tr class="provider-${p.status}">${cell(p.name)}${cell(p.version)}${cell(p.distribution)}<td>${p.status==='available'?'Available':'Unavailable'}</td><td>${p.kinds.length?escapeHtml(p.kinds.join(', ')):'<span class="muted">none</span>'}</td></tr>`+(p.error===null?'':`<tr class="provider-error"><td colspan="5">${escapeHtml(p.error)}</td></tr>`)).join('');
 return `<table class="providers"><thead><tr><th scope="col">Provider</th><th scope="col">Version</th><th scope="col">Distribution</th><th scope="col">Status</th><th scope="col">Physics kinds</th></tr></thead><tbody>${rows}</tbody></table>`;
}
// Lists the providers into `target` each time `details` opens (one request at a time).
// A failure is shown as text; `request` is solverApi, whose error carries the reply's detail.
export function installProviderList(details,target,request){
 let pending=null;
 const load=async()=>{
  target.textContent='Listing installed physics…';
  try{target.innerHTML=providersHtml(readProviders(await request('/api/providers')));}
  catch(error){target.textContent='Installed physics could not be listed: '+(error?.message||'the request failed.');}
 };
 details.addEventListener('toggle',()=>{if(details.open&&!pending)pending=load().finally(()=>{pending=null;});});
 return ()=>pending;
}
