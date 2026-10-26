// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
const {test,before}=require('node:test');const assert=require('node:assert/strict');
let checkWorkspaceCapabilities;
before(async()=>({checkWorkspaceCapabilities}=await import('../../packages/simcase/src/simcase/studio/static/workspace-connection.mjs')));
const capabilities=()=>({schema_version:3,server_instance:'a'.repeat(32),adapter:'optical-rectangle-v3',height_range_nm:[100,500],wavelength_range_nm:[1400,1700],core_mesh_range_nm:[20,60],simcase_version:'0.1.0',optical:true,coupled:false,settings:{window_um:[-1.5,1.5,-1.2,1.2],boundary:'PEC',candidates:2}});
test('known contract reports version without enabling coupled calculation',()=>assert.deepEqual(checkWorkspaceCapabilities(capabilities()),{version:'0.1.0',instance:'a'.repeat(32)}));
test('missing, future or incompatible capabilities fail closed',()=>{
 for(const change of [c=>c.schema_version=2,c=>c.schema_version=4,c=>c.wavelength_range_nm=[400,2000],c=>delete c.core_mesh_range_nm,c=>c.settings.candidates=4,c=>delete c.server_instance,c=>c.server_instance=123,c=>c.optical=false,c=>c.coupled=true,c=>c.height_range_nm=[50,1000],c=>delete c.settings,c=>c.simcase_version='<html>',c=>c.adapter='unknown']){const c=capabilities();change(c);assert.throws(()=>checkWorkspaceCapabilities(c));}
 assert.throws(()=>checkWorkspaceCapabilities(null));
});
