// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

export const MAX_BYTES = 65536;
export const DRAFT_KEY = 'openphysics.studio.workspace.v1';
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
  if (!doc || doc.format !== 'openphysics-studio-workspace' || ![1,2].includes(doc.version)) throw new Error('Unsupported project format or version.');
  const s = doc.model, c = doc.setup;
  if (!s || !c || !c.materials) throw new Error('Project inputs are missing.');
  if(doc.version===2&&doc.units?.height!=='nm')throw new Error('Invalid height units.');
  if(doc.version===1&&s.height!==undefined)throw new Error('Height requires project version 2.');
  const model = {
    height: doc.version===1?220:number(s.height,100,500,'core height'),
    width: number(s.width, 300, 900, 'core width'),
    voltage: number(s.voltage, 0, 10, 'voltage'),
    electric: bool(s.electric, 'electric interface'),
    heat: bool(s.heat, 'heat interface'),
    structure: bool(s.structure, 'structural interface'),
    optics: bool(s.optics, 'optical interface'),
  };
  if (model.heat && !model.electric) throw new Error('This prototype requires electric currents for Joule heating.');
  const materials = {};
  for (const body of ['Core', 'Oxide', 'Heater']) materials[body] = choices(c.materials[body], ['', 'Silicon', 'Silica', 'Silicon nitride', 'Platinum'], `${body} material`);
  const setup = {
    materials,
    temperature: number(c.temperature, 1, 2000, 'temperature'),
    cooling: choices(c.cooling, ['', 'Oxide bottom: fixed temperature'], 'thermal boundary'),
    fixed: choices(c.fixed, ['', 'Left end fixed', 'Both ends fixed'], 'fixed support'),
    terminal: choices(c.terminal, ['', 'Heater start / heater end'], 'terminal pair'),
  };
  return {format: 'openphysics-studio-workspace', version: 2, units: {height:'nm',width: 'nm', voltage: 'V', temperature: 'K'}, model, setup};
}
export function parseProject(text) {
  if (new TextEncoder().encode(text).byteLength > MAX_BYTES) throw new Error('Project exceeds 64 KiB.');
  let doc;
  try { doc = JSON.parse(text); } catch { throw new Error('Project is not valid JSON.'); }
  if (doc?.units?.width !== 'nm' || doc?.units?.voltage !== 'V' || doc?.units?.temperature !== 'K') throw new Error('Unsupported or missing project units.');
  return validateProject(doc);
}
export function snapshot(state, setup) {
  return validateProject({format:'openphysics-studio-workspace',version:2,units:{height:'nm'},model:{height:220,...state,electric:state.electric!==false},setup});
}
