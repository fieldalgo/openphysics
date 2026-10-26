// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
const {test,before}=require('node:test');const assert=require('node:assert/strict');
let checkWorkspaceCapabilities;
before(async()=>({checkWorkspaceCapabilities}=await import('../../packages/simcase/src/simcase/studio/static/workspace-connection.mjs')));
const capabilities=()=>({schema_version:1,adapter:'optical-fixed-v1',simcase_version:'0.1.0',optical:true,coupled:false,settings:{height_nm:220,wavelength_nm:1550,core_mesh_nm:30,window_um:[-1.5,1.5,-1.2,1.2],boundary:'PEC',candidates:2}});
test('known contract reports version without enabling coupled calculation',()=>assert.deepEqual(checkWorkspaceCapabilities(capabilities()),{version:'0.1.0'}));
test('missing, future or incompatible capabilities fail closed',()=>{
 for(const change of [c=>c.schema_version=2,c=>c.optical=false,c=>c.coupled=true,c=>c.settings.height_nm=300,c=>delete c.settings,c=>c.simcase_version='<html>',c=>c.adapter='unknown']){const c=capabilities();change(c);assert.throws(()=>checkWorkspaceCapabilities(c));}
 assert.throws(()=>checkWorkspaceCapabilities(null));
});
