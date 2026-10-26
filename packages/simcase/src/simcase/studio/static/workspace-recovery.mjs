// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
import {parseProject} from './workspace-project.mjs';
export const RECOVERY_KEY='openphysics.studio.recovery.v1';
export function readRecovery(storage){
 const raw=storage.getItem(RECOVERY_KEY);if(!raw)return null;
 if(new TextEncoder().encode(raw).length>70000)throw new Error('Recovery record is too large.');
 const record=JSON.parse(raw);
 if(record.version!==1||typeof record.savedAt!=='string'||!Number.isFinite(Date.parse(record.savedAt)))throw new Error('Invalid recovery record.');
 return {savedAt:record.savedAt,input:parseProject(JSON.stringify(record.input))};
}
export function writeRecovery(storage,input,now=new Date()){
 const checked=parseProject(JSON.stringify(input));
 storage.setItem(RECOVERY_KEY,JSON.stringify({version:1,savedAt:now.toISOString(),input:checked}));
}
