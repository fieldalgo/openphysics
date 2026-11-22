// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

import {validateShapes,legacyCoreShape} from './workspace-shapes.mjs';
import {validateThermal,DEFAULT_THERMAL} from './workspace-heat.mjs';
import {validateJoule,DEFAULT_JOULE} from './workspace-joule.mjs';

export const MAX_BYTES = 65536;
// Project version 7 adds the Joule heating application's inputs (model.joule, lengths in mm,
// units.joule_length); a version 6 project is read with the default Joule inputs. Version 6 (units
// and naming batch) stores the heat plate's inward heat flux under its registry name; versions 1-5
// are refused by name. Version 8 is version 7 with the study settings of the optical
// application: model.modeCount (Modes to find, 1 to 8, written only when not 2) and
// model.groupIndex (true, written only when Also compute group index is on). Inputs with the
// default settings are written as version 7, byte for byte; a version 6 or 7 file is read with
// the defaults (2 modes, group index off).
export const PROJECT_VERSION = 7;
export const STUDY_PROJECT_VERSION = 8;
export const DEFAULT_STUDY = Object.freeze({modeCount: 2, groupIndex: false});
const READ_VERSIONS = [6, PROJECT_VERSION, STUDY_PROJECT_VERSION];
export const DRAFT_KEY = 'openphysics.studio.workspace.v2';
const choices = (value, values, name) => {
  if (!values.includes(value)) throw new Error(`Invalid ${name}.`);
  return value;
};
const number = (value, min, max, name) => {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < min || value > max) throw new Error(`Invalid ${name}.`);
  return value;
};
const bool = (value, name) => {
  if (typeof value !== 'boolean') throw new Error(`Invalid ${name}.`);
  return value;
};
export function validateProject(doc) {
  if (doc?.format === 'openphysics-studio-workspace' && [1,2,3,4,5].includes(doc.version)) throw new Error(`This project (version ${doc.version}) was saved before the units and naming batch and is not read. Enter its inputs again and save a new project.`);
  if (!doc || doc.format !== 'openphysics-studio-workspace' || !READ_VERSIONS.includes(doc.version)) throw new Error('Unsupported project format or version.');
  const s = doc.model, c = doc.setup;
  if (!s || !c || !c.materials) throw new Error('Project inputs are missing.');
  if(doc.units?.height!=='nm')throw new Error('Invalid height units.');
  if(doc.units?.wavelength!=='nm'||doc.units?.core_mesh!=='nm')throw new Error('Invalid optical study units.');
  if(doc.units?.shapes!=='nm')throw new Error('Invalid shape units.');
  if(doc.units?.thermal_length!=='mm')throw new Error('Invalid heat plate units.');
  if(doc.version!==6&&doc.units?.joule_length!=='mm')throw new Error('Invalid Joule heating units.');
  const model = {
    height: number(s.height,100,500,'core height'),
    wavelength: number(s.wavelength,1400,1700,'wavelength'),
    coreMesh: number(s.coreMesh,20,60,'core mesh size'),
    width: number(s.width, 300, 900, 'core width'),
    voltage: number(s.voltage, 0, 10, 'voltage'),
    electric: bool(s.electric, 'electric interface'),
    heat: bool(s.heat, 'heat interface'),
    structure: bool(s.structure, 'structural interface'),
    optics: bool(s.optics, 'optical interface'),
  };
  model.shapes = validateShapes(s.shapes);
  model.thermal = validateThermal(s.thermal);
  model.joule = validateJoule(doc.version === 6 ? DEFAULT_JOULE : s.joule);
  // Heat alone is the steady heat application; heat with other physics still needs the electric source.
  if (model.heat && !model.electric && (model.structure || model.optics)) throw new Error('This prototype requires electric currents for Joule heating.');
  const materials = {};
  for (const body of ['Core', 'Oxide', 'Heater']) materials[body] = choices(c.materials[body], ['', 'Silicon', 'Silica', 'Silicon nitride', 'Platinum'], `${body} material`);
  const setup = {
    materials,
    temperature: number(c.temperature, 1, 2000, 'temperature'),
    cooling: choices(c.cooling, ['', 'Oxide bottom: fixed temperature'], 'thermal boundary'),
    fixed: choices(c.fixed, ['', 'Left end fixed', 'Both ends fixed'], 'fixed support'),
    terminal: choices(c.terminal, ['', 'Heater start / heater end'], 'terminal pair'),
  };
  let version = PROJECT_VERSION;
  if (doc.version === STUDY_PROJECT_VERSION) {
    if (s.modeCount !== undefined && (!Number.isInteger(s.modeCount) || s.modeCount < 1 || s.modeCount > 8)) throw new Error('Invalid Modes to find (a whole number from 1 to 8).');
    if (s.groupIndex !== undefined && typeof s.groupIndex !== 'boolean') throw new Error('Invalid group index option.');
    if (s.modeCount !== undefined && s.modeCount !== DEFAULT_STUDY.modeCount) model.modeCount = s.modeCount;
    if (s.groupIndex === true) model.groupIndex = true;
    if (model.modeCount !== undefined || model.groupIndex !== undefined) version = STUDY_PROJECT_VERSION;
  }
  return {format: 'openphysics-studio-workspace', version, units: {height:'nm',width: 'nm',wavelength:'nm',core_mesh:'nm',shapes:'nm',thermal_length:'mm',joule_length:'mm', voltage: 'V', temperature: 'K'}, model, setup};
}
export function parseProject(text) {
  if (new TextEncoder().encode(text).byteLength > MAX_BYTES) throw new Error('Project exceeds 64 KiB.');
  let doc;
  try { doc = JSON.parse(text); } catch { throw new Error('Project is not valid JSON.'); }
  if (doc?.units?.width !== 'nm' || doc?.units?.voltage !== 'V' || doc?.units?.temperature !== 'K') throw new Error('Unsupported or missing project units.');
  return validateProject(doc);
}
export function snapshot(state, setup) {
  return validateProject({format:'openphysics-studio-workspace',version:PROJECT_VERSION,units:{height:'nm',wavelength:'nm',core_mesh:'nm',shapes:'nm',thermal_length:'mm',joule_length:'mm'},model:{height:220,wavelength:1550,coreMesh:30,thermal:DEFAULT_THERMAL,joule:DEFAULT_JOULE,...state,shapes:state.shapes??[legacyCoreShape(state.width,state.height??220,setup.materials.Core)],electric:state.electric!==false},setup});
}
/** The study settings an inputs object holds: {modeCount, groupIndex} (the defaults for version 6 or 7). */
export function projectStudy(doc) {
  return {modeCount: doc.model.modeCount ?? DEFAULT_STUDY.modeCount, groupIndex: doc.model.groupIndex === true};
}
/** Inputs without study settings (version 7): the inputs a run keeps. */
export function withoutStudy(doc) {
  if (doc.version !== STUDY_PROJECT_VERSION) return validateProject(doc);
  const {modeCount, groupIndex, ...model} = doc.model;
  return validateProject({...doc, version: PROJECT_VERSION, model});
}
/** The inputs file object of these inputs with these study settings: version 7 when the settings
 * are the defaults (byte for byte as before), else version 8. */
export function withStudy(doc, {modeCount = DEFAULT_STUDY.modeCount, groupIndex = false} = {}) {
  const base = withoutStudy(doc);
  if (modeCount === DEFAULT_STUDY.modeCount && groupIndex !== true) return base;
  return validateProject({...base, version: STUDY_PROJECT_VERSION, model: {...base.model, ...(modeCount === DEFAULT_STUDY.modeCount ? {} : {modeCount}), ...(groupIndex === true ? {groupIndex: true} : {})}});
}
