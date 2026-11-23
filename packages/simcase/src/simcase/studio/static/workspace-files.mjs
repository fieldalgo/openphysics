// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

// File › Save and Save As: where a session file goes. Where the browser has a save picker
// (showSaveFilePicker, secure contexts in Chromium browsers), Save As asks for a file and keeps
// its handle, so Save writes that file again without a dialog. Elsewhere, or when the picker
// cannot be used, Studio asks for a file name and the browser downloads the file; the name is
// remembered as the model's current file, so Save downloads under it again without asking (a
// download cannot replace the earlier file). The words say what happened: "Saved to <name>" after
// a picker write, "sent to your browser's Downloads" after a download, never more.

/** The id the picker remembers its last folder under. */
export const PICKER_ID = 'openphysics-project';
/** The one file type the picker offers. */
export const PICKER_TYPES = Object.freeze([Object.freeze({description: 'OpenPhysics session file (JSON)', accept: Object.freeze({'application/json': Object.freeze(['.json'])})})]);

/** A file name the name dialog accepts: letters, digits, spaces, ".", "_", "-", "(" and ")" only,
 * trimmed, with ".json" added when missing; fallback when nothing is left. */
export function sanitizeFileName(name, fallback = 'session.json') {
  // the name without its .json, without leading dots (hidden files) or trailing dots and spaces
  let base = String(name ?? '').replace(/[^A-Za-z0-9 ._()-]+/g, '').replace(/\s+/g, ' ').trim().replace(/\.json$/i, '');
  base = base.replace(/^[.\s]+/, '').replace(/[.\s]+$/, '').slice(0, 195).replace(/[.\s]+$/, '');
  return /[A-Za-z0-9]/.test(base) ? base + '.json' : fallback;
}

/** A model file's name from its model name: lowercase words joined by hyphens, e.g.
 * "Optical waveguide" → optical-waveguide.json; "model.json" when nothing is left. */
export function modelFileName(name) {
  const s = String(name ?? '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 60).replace(/-+$/, '');
  return (s || 'model') + '.json';
}

/** Whether Save As can use the browser's save picker. An automated browser
 * (navigator.webdriver, e.g. headless Chromium) has the function but rejects every call at once
 * as AbortError, which reads as a user cancel: it takes the name dialog and a download instead. */
export function pickerAvailable(win = globalThis) {
  return !!win && win.isSecureContext === true && typeof win.showSaveFilePicker === 'function' && win.navigator?.webdriver !== true;
}

/** The picker's options: the suggested name, one JSON type and the remembered folder id; startIn
 * (the current file, whose folder the picker then opens) only once a file was chosen. Without
 * startIn the id alone restores the folder last picked under it (WICG File System Access
 * §3.2.2 Starting Directory). */
export function pickerOptions(suggestedName, handle = null) {
  const options = {suggestedName, types: PICKER_TYPES.map(t => ({description: t.description, accept: {'application/json': [...t.accept['application/json']]}})), id: PICKER_ID};
  if (handle) options.startIn = handle;
  return options;
}

// ---- The current file of a model ----
// One file name per model: the name Save As or the Save name dialog chose, the file the picker
// wrote, or the file File › Open read. scope names the model it belongs to (the open model and how
// many opens, model switches and resets came before); any of those moves the scope on, so the
// name, and a picker handle with it, is dropped. how: 'picker' (handle kept), 'download' or 'opened'.

/** The current file record, or null for a name the name dialog would not accept. */
export function rememberFile({name, handle = null, how, scope}) {
  if (typeof name !== 'string' || !/^[A-Za-z0-9._ ()-]{1,200}\.json$/i.test(name) || !['picker', 'download', 'opened'].includes(how)) return null;
  return {name, handle: how === 'picker' ? handle : null, how, scope};
}
/** The current file of the model whose scope is given, or null when it belongs to another one. */
export function currentFileFor(file, scope) {
  return file && file.scope === scope ? file : null;
}
/** The name a save suggests: the current file's, else the model-based name. */
export function suggestedSaveName(file, fallback) {
  return file ? file.name : fallback;
}
/** What Save or Save As does with this current file (or null):
 *  'write'    the picker's file again (Save with a kept handle);
 *  'picker'   ask in the browser's save picker;
 *  'download' download at once under the current name (Save, no picker, a known name);
 *  'ask'      Studio's name dialog, then a download. */
export function saveRoute(file, {saveAs = false, picker = false} = {}) {
  if (!saveAs && file?.handle) return 'write';
  if (picker) return 'picker';
  if (!saveAs && file) return 'download';
  return 'ask';
}
/** The sentence after a download under a name already downloaded: the browser cannot replace it. */
export function downloadAgainNote(name) {
  return `A download cannot replace the earlier file, so your browser may name it ${String(name).replace(/\.json$/i, '')} (1).json.`;
}

/** Writes text to a file handle. Chromium writes to a temporary file and replaces the file only
 * on close, so a failed write is aborted and leaves the old file whole. */
export async function writeHandle(handle, text) {
  const writable = await handle.createWritable();
  try {
    await writable.write(text);
  } catch (error) {
    try { await writable.abort(); } catch {}
    throw error;
  }
  await writable.close();
}

const errorText = error => (error && (error.message || error.name)) || String(error);

/**
 * Saves text to a file. target: the current file {handle, name} (handle null when it was
 * downloaded or opened), or null. saveAs: ask for a file even when there is a target. Returns a
 * promise of one of
 *   {status: 'saved', handle, name}            written through the picker or the target;
 *   {status: 'known', name}                    no picker, Save, a known name: download it as is;
 *   {status: 'cancelled'}                      the user closed the picker;
 *   {status: 'failed', name, error, fresh}     the write failed: a kept file is unchanged; a file
 *                                              just chosen (fresh) may have been created empty;
 *   {status: 'unavailable', error}             no picker, or it threw: ask for a name instead.
 * The picker is called before anything is awaited, so it stays inside the click or key press.
 */
export function saveToFile(text, {suggestedName, target = null, saveAs = false, win = globalThis}) {
  const route = saveRoute(target, {saveAs, picker: pickerAvailable(win)});
  if (route === 'write') {
    return writeHandle(target.handle, text).then(() => ({status: 'saved', handle: target.handle, name: target.name}),
      error => ({status: 'failed', name: target.name, error: errorText(error), fresh: false}));
  }
  if (route === 'download') return Promise.resolve({status: 'known', name: target.name});
  if (route === 'ask') return Promise.resolve({status: 'unavailable', error: null});
  let picked;
  try { picked = win.showSaveFilePicker(pickerOptions(suggestedName, target?.handle || null)); }
  catch (error) { picked = Promise.reject(error); }
  return Promise.resolve(picked).then(handle => {
    const name = String(handle?.name || suggestedName);
    // a file just chosen in the picker: Chromium may already have created or emptied it
    return writeHandle(handle, text).then(() => ({status: 'saved', handle, name}),
      error => ({status: 'failed', name, error: errorText(error), fresh: true}));
  }, error => error?.name === 'AbortError' ? {status: 'cancelled'} : {status: 'unavailable', error: errorText(error)});
}

/** The notice for a save that did not write: a cancel, or a failed write. */
export function notWrittenNotice(result, {saveAs}) {
  if (result.status === 'cancelled') return `${saveAs ? 'Save As' : 'Save'} cancelled; nothing was written.`;
  if (result.status === 'failed') return `Session not saved: ${result.name} could not be written (${result.error}); `+(result.fresh ? 'the browser may have left it empty.' : 'the file is unchanged.');
  return 'Session not saved: nothing was written.';
}
