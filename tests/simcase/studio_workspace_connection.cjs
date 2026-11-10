// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
const {test,before}=require('node:test');const assert=require('node:assert/strict');
let checkWorkspaceCapabilities,connectionFailure;
before(async()=>({checkWorkspaceCapabilities,connectionFailure}=await import('../../packages/simcase/src/simcase/studio/static/workspace-connection.mjs')));
// the /api/workspace/capabilities/v6 contract of the units and naming batch: adapter optical-shapes-v7,
// quantity strings under registry names, physmat: material names
const capabilities=()=>({schema_version:6,server_instance:'a'.repeat(32),adapter:'optical-shapes-v7',domain:{xmin:'-1500 nm',xmax:'1500 nm',ymin:'-1200 nm',ymax:'1200 nm'},max_shapes:8,max_polygon_vertices:12,shape_types:['rect','circle','polygon'],materials:{Silicon:'physmat:Si','Silicon nitride':'physmat:Si3N4',Silica:'physmat:SiO2',Air:'physmat:vacuum','Sapphire (ordinary)':'physmat:Al2O3','Lithium niobate (ordinary)':'physmat:LiNbO3','Indium phosphide':'physmat:InP','Gallium arsenide':'physmat:GaAs','Calcium fluoride':'physmat:CaF2','Magnesium fluoride (ordinary)':'physmat:MgF2'},vacuum_wavelength_range:['1400 nm','1700 nm'],core_element_size_range:['20 nm','60 nm'],simcase_version:'0.1.0',optical:true,coupled:false,settings:{domain:{xmin:'-1.5 um',xmax:'1.5 um',ymin:'-1.2 um',ymax:'1.2 um'},boundary:'PEC',mode_count:2}});
test('known contract reports version without enabling coupled calculation',()=>assert.deepEqual(checkWorkspaceCapabilities(capabilities()),{version:'0.1.0',instance:'a'.repeat(32)}));
test('missing, future or incompatible capabilities fail closed',()=>{
 for(const change of [c=>c.schema_version=4,c=>c.schema_version=5,c=>c.schema_version=7,c=>c.adapter='optical-shapes-v5',c=>c.adapter='optical-shapes-v6',c=>c.max_shapes=20,c=>c.domain.xmin='-3000 nm',c=>c.shape_types=['rect'],c=>delete c.materials.Air,c=>c.materials.Silicon='Si',c=>c.max_polygon_vertices=64,c=>c.vacuum_wavelength_range=['400 nm','2000 nm'],c=>delete c.core_element_size_range,c=>c.settings.mode_count=4,c=>c.settings.domain.xmax='3 um',c=>delete c.server_instance,c=>c.server_instance=123,c=>c.optical=false,c=>c.coupled=true,c=>delete c.settings,c=>c.simcase_version='<html>',c=>c.adapter='unknown']){const c=capabilities();change(c);assert.throws(()=>checkWorkspaceCapabilities(c));}
 assert.throws(()=>checkWorkspaceCapabilities(null));
});
test('a failed request is classified as a restart, a lost server or an ordinary failure',()=>{
 const restarted=Object.assign(new Error('The Studio server restarted or changed; reconnect before submitting new work. Previous jobs cannot be resumed on this server.'),{status:409});
 assert.equal(connectionFailure(restarted),'restarted');
 assert.equal(connectionFailure(new TypeError('Failed to fetch')),'unreachable');
 // a 409 for another reason (a job that is still running) is not a restart
 assert.equal(connectionFailure(Object.assign(new Error('job is running'),{status:409})),'request');
 assert.equal(connectionFailure(Object.assign(new Error('bad input'),{status:400})),'request');
 assert.equal(connectionFailure(Object.assign(new Error('aborted'),{name:'AbortError'})),'request');
 assert.equal(connectionFailure(undefined),'request');
});
