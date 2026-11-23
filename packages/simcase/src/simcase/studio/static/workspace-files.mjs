// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

// File › Save and Save As: where a session file goes. Where the browser has a save picker
// (showSaveFilePicker, secure contexts in Chromium browsers), Save As asks for a file and keeps
// its handle, so Save writes that file again without a dialog. Elsewhere, or when the picker
// cannot be used, Studio asks for a file name and the browser downloads the file. The words say
// what happened: "Saved to <name>" after a picker write, "sent to your browser's Downloads" after
// a download, never more.

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

/** The picker's options: the suggested name, one JSON type, the remembered folder id, and the
 * current file (or Documents) to start in. */
export function pickerOptions(suggestedName, handle = null) {
  return {suggestedName, types: PICKER_TYPES.map(t => ({description: t.description, accept: {'application/json': [...t.accept['application/json']]}})), id: PICKER_ID, startIn: handle || 'documents'};
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
 * Saves text to a file. target: {handle, name} of the file last chosen in the picker, or null.
 * saveAs: ask for a file even when there is a target. Returns a promise of one of
 *   {status: 'saved', handle, name}            written through the picker or the target;
 *   {status: 'cancelled'}                      the user closed the picker;
 *   {status: 'failed', name, error}            the write failed; the file is unchanged;
 *   {status: 'unavailable', error}             no picker, or it threw: ask for a name instead.
 * The picker is called before anything is awaited, so it stays inside the click or key press.
 */
export function saveToFile(text, {suggestedName, target = null, saveAs = false, win = globalThis}) {
  if (target && !saveAs) {
    return writeHandle(target.handle, text).then(() => ({status: 'saved', handle: target.handle, name: target.name}),
      error => ({status: 'failed', name: target.name, error: errorText(error)}));
  }
  if (!pickerAvailable(win)) return Promise.resolve({status: 'unavailable', error: null});
  let picked;
  try { picked = win.showSaveFilePicker(pickerOptions(suggestedName, target?.handle || null)); }
  catch (error) { picked = Promise.reject(error); }
  return Promise.resolve(picked).then(handle => {
    const name = String(handle?.name || suggestedName);
    return writeHandle(handle, text).then(() => ({status: 'saved', handle, name}),
      error => ({status: 'failed', name, error: errorText(error)}));
  }, error => error?.name === 'AbortError' ? {status: 'cancelled'} : {status: 'unavailable', error: errorText(error)});
}

/** The notice for a save that did not write: a cancel, or a failed write. */
export function notWrittenNotice(result, {saveAs}) {
  if (result.status === 'cancelled') return `${saveAs ? 'Save As' : 'Save'} cancelled; nothing was written.`;
  if (result.status === 'failed') return `Session not saved: ${result.name} could not be written (${result.error}); the file is unchanged.`;
  return 'Session not saved: nothing was written.';
}
