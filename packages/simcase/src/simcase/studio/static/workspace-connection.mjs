// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
import {OPTICAL_SETTINGS,OPTICAL_ADAPTER,MODE_COUNT_RANGE,DEFAULT_MODE_COUNT} from './workspace-notebook.mjs';
import {WINDOW_NM,MAX_SHAPES,MAX_POINTS,SHAPE_MATERIALS} from './workspace-shapes.mjs';
const nm=value=>value+' nm';
export function checkWorkspaceCapabilities(caps){
 if(caps?.schema_version!==8||caps.adapter!==OPTICAL_ADAPTER||caps.optical!==true||caps.coupled!==false)throw new Error('Unsupported workspace contract. Update Studio and retry.');
 if(typeof caps.simcase_version!=='string'||!/^\d[0-9A-Za-z.+-]{0,63}$/.test(caps.simcase_version))throw new Error('Studio did not provide a valid package version.');
 const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
 if(!same(caps.domain,{xmin:nm(WINDOW_NM.xmin),xmax:nm(WINDOW_NM.xmax),ymin:nm(WINDOW_NM.ymin),ymax:nm(WINDOW_NM.ymax)})||caps.max_shapes!==MAX_SHAPES||caps.max_polygon_vertices!==MAX_POINTS||!same(caps.shape_types,['rect','circle','polygon'])||!same(caps.materials,SHAPE_MATERIALS))throw new Error('Unsupported shape contract.');
 if(!same(caps.vacuum_wavelength_range,['1400 nm','1700 nm'])||!same(caps.core_element_size_range,['20 nm','60 nm']))throw new Error('Unsupported wavelength or core mesh range.');
 for(const key of ['domain','boundary'])if(JSON.stringify(caps.settings?.[key])!==JSON.stringify(OPTICAL_SETTINGS[key]))throw new Error('Optical settings differ from this workspace contract.');
 // version 8: the mode count is the page's (1 to 8), not a fixed setting
 if(caps.settings?.mode_count!==undefined||!same(caps.mode_count_range,MODE_COUNT_RANGE)||caps.mode_count_default!==DEFAULT_MODE_COUNT)throw new Error('Optical settings differ from this workspace contract.');
 if(typeof caps.server_instance!=='string'||! /^[a-f0-9]{32}$/.test(caps.server_instance))throw new Error('Invalid server instance.');
 return {version:caps.simcase_version,instance:caps.server_instance};
}
// What a failed request means for the connection. 'restarted': the server answered
// with another instance (a restart). 'unreachable': no answer at all. 'request': any
// other failure, which says nothing about the connection.
export function connectionFailure(error){
 if(error?.status===409&&/restarted or changed/.test(String(error.message)))return 'restarted';
 if(error instanceof TypeError||error?.name==='TypeError')return 'unreachable';
 return 'request';
}
export const RESTARTED_MESSAGE='Studio was restarted. This page reconnected to the new server; your inputs and retained results are unchanged. Select Run optical study again.';
export const UNREACHABLE_MESSAGE='Studio server is not reachable. Start Studio again with the same command and keep this address; this page reconnects by itself.';
// A refused or failed request as one line: "<what> request failed: <reason>. Inputs and earlier
// results are unchanged." The server's reason ends with no full stop of its own (for example
// "...: maximum iterations exceeded"), so one is added when it has none.
export function requestFailedText(what,reason){
 const text=String(reason).trim();
 return `${what} request failed: ${text}${/[.!?]$/.test(text)?'':'.'} Inputs and earlier results are unchanged.`;
}
export const RECONNECTED_MESSAGE='Reconnected to Studio. Your inputs and retained results are unchanged.';
