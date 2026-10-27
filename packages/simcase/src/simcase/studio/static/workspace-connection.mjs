// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
import {OPTICAL_SETTINGS} from './workspace-notebook.mjs';
import {WINDOW_NM,MAX_SHAPES,MAX_POINTS,SHAPE_MATERIALS} from './workspace-shapes.mjs';
export function checkWorkspaceCapabilities(caps){
 if(caps?.schema_version!==5||caps.adapter!=='optical-shapes-v5'||caps.optical!==true||caps.coupled!==false)throw new Error('Unsupported workspace contract. Update Studio and retry.');
 if(typeof caps.simcase_version!=='string'||!/^\d[0-9A-Za-z.+-]{0,63}$/.test(caps.simcase_version))throw new Error('Studio did not provide a valid package version.');
 const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
 if(!same(caps.window_nm,[WINDOW_NM.xmin,WINDOW_NM.xmax,WINDOW_NM.ymin,WINDOW_NM.ymax])||caps.max_shapes!==MAX_SHAPES||caps.max_polygon_vertices!==MAX_POINTS||!same(caps.shape_types,['rect','circle','polygon'])||!same(caps.materials,SHAPE_MATERIALS))throw new Error('Unsupported shape contract.');
 if(JSON.stringify(caps.wavelength_range_nm)!==JSON.stringify([1400,1700])||JSON.stringify(caps.core_mesh_range_nm)!==JSON.stringify([20,60]))throw new Error('Unsupported wavelength or core mesh range.');
 for(const key of ['window_um','boundary','candidates'])if(JSON.stringify(caps.settings?.[key])!==JSON.stringify(OPTICAL_SETTINGS[key]))throw new Error('Optical settings differ from this workspace contract.');
 if(typeof caps.server_instance!=='string'||! /^[a-f0-9]{32}$/.test(caps.server_instance))throw new Error('Invalid server instance.');
 return {version:caps.simcase_version,instance:caps.server_instance};
}
