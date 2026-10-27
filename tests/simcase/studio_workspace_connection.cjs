// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
const {test,before}=require('node:test');const assert=require('node:assert/strict');
let checkWorkspaceCapabilities;
before(async()=>({checkWorkspaceCapabilities}=await import('../../packages/simcase/src/simcase/studio/static/workspace-connection.mjs')));
const capabilities=()=>({schema_version:4,server_instance:'a'.repeat(32),adapter:'optical-shapes-v4',window_nm:[-1500,1500,-1200,1200],max_shapes:8,max_polygon_vertices:12,shape_types:['rect','circle','polygon'],materials:{Silicon:'Si','Silicon nitride':'Si3N4',Silica:'SiO2',Air:'vacuum'},wavelength_range_nm:[1400,1700],core_mesh_range_nm:[20,60],simcase_version:'0.1.0',optical:true,coupled:false,settings:{window_um:[-1.5,1.5,-1.2,1.2],boundary:'PEC',candidates:2}});
test('known contract reports version without enabling coupled calculation',()=>assert.deepEqual(checkWorkspaceCapabilities(capabilities()),{version:'0.1.0',instance:'a'.repeat(32)}));
test('missing, future or incompatible capabilities fail closed',()=>{
 for(const change of [c=>c.schema_version=3,c=>c.schema_version=5,c=>c.max_shapes=20,c=>c.window_nm=[-3000,3000,-1200,1200],c=>c.shape_types=['rect'],c=>delete c.materials.Air,c=>c.max_polygon_vertices=64,c=>c.wavelength_range_nm=[400,2000],c=>delete c.core_mesh_range_nm,c=>c.settings.candidates=4,c=>delete c.server_instance,c=>c.server_instance=123,c=>c.optical=false,c=>c.coupled=true,c=>delete c.settings,c=>c.simcase_version='<html>',c=>c.adapter='unknown']){const c=capabilities();change(c);assert.throws(()=>checkWorkspaceCapabilities(c));}
 assert.throws(()=>checkWorkspaceCapabilities(null));
});
