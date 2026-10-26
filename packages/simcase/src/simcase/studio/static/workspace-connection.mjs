// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
import {OPTICAL_SETTINGS} from './workspace-notebook.mjs';
export function checkWorkspaceCapabilities(caps){
 if(caps?.schema_version!==1||caps.adapter!=='optical-fixed-v1'||caps.optical!==true||caps.coupled!==false)throw new Error('Unsupported workspace contract. Update Studio and retry.');
 if(typeof caps.simcase_version!=='string'||!/^\d[0-9A-Za-z.+-]{0,63}$/.test(caps.simcase_version))throw new Error('Studio did not provide a valid package version.');
 for(const key of ['height_nm','wavelength_nm','core_mesh_nm','window_um','boundary','candidates'])if(JSON.stringify(caps.settings?.[key])!==JSON.stringify(OPTICAL_SETTINGS[key]))throw new Error('Optical settings differ from this workspace contract.');
 return {version:caps.simcase_version};
}
