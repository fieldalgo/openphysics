// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
import {OPTICAL_SETTINGS} from './workspace-notebook.mjs';
export function checkWorkspaceCapabilities(caps){
 if(caps?.schema_version!==2||caps.adapter!=='optical-rectangle-v2'||caps.optical!==true||caps.coupled!==false)throw new Error('Unsupported workspace contract. Update Studio and retry.');
 if(typeof caps.simcase_version!=='string'||!/^\d[0-9A-Za-z.+-]{0,63}$/.test(caps.simcase_version))throw new Error('Studio did not provide a valid package version.');
 if(JSON.stringify(caps.height_range_nm)!==JSON.stringify([100,500]))throw new Error('Unsupported height range.');
 for(const key of ['wavelength_nm','core_mesh_nm','window_um','boundary','candidates'])if(JSON.stringify(caps.settings?.[key])!==JSON.stringify(OPTICAL_SETTINGS[key]))throw new Error('Optical settings differ from this workspace contract.');
 return {version:caps.simcase_version};
}
