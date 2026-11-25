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

/** The picker's file type for a project file (File › Save and Save As). */
export const PROJECT_PICKER_DESCRIPTION = 'OpenPhysics project file (JSON)';

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
export function pickerOptions(suggestedName, handle = null, description = null) {
  const options = {suggestedName, types: PICKER_TYPES.map(t => ({description: description || t.description, accept: {'application/json': [...t.accept['application/json']]}})), id: PICKER_ID};
  if (handle) options.startIn = handle;
  return options;
}

// ---- The current file of a model ----
// One file name per model: the name Save As or the Save name dialog chose, the file the picker
// wrote, or the file File › Open read. scope names the model it belongs to (the open model and how
// many opens, model switches and resets came before); any of those moves the scope on, so the
// name, and a picker handle with it, is dropped. how: 'picker' (handle kept), 'download', 'opened',
// or 'recovered' (a browser restore whose record still matched the session file it names).

/** The current file record, or null for a name the name dialog would not accept. */
export function rememberFile({name, handle = null, how, scope}) {
  if (typeof name !== 'string' || !/^[A-Za-z0-9._ ()-]{1,200}\.json$/i.test(name) || !['picker', 'download', 'opened', 'recovered'].includes(how)) return null;
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
/** The Save As name dialog's line on what later saves do (round 14). */
export const LATER_SAVES_NOTE = 'Later saves download again under this name; your browser may add “ (1)”.';

/** Round 25 (A2): whether Save asks before it downloads a file again: on the download path (no
 * picker), Save (not Save As) of a file this tab already downloaded (how 'download'). A file opened
 * or recovered is downloaded at once by its first Save, as before; a picker file is written again. */
export function asksBeforeDownloadAgain(file, {saveAs = false, picker = false} = {}) {
  return !!file && file.how === 'download' && saveRoute(file, {saveAs, picker}) === 'download';
}
/** The question: "Download design-a-ng.json again? This browser cannot replace the earlier file and
 * may name the new one design-a-ng (1).json." Round 29 (L3): n, the repeat it asks about ("(2)" for
 * the second, as the header then says). */
export function downloadAgainQuestion(name, n = 1) {
  return `Download ${name} again? This browser cannot replace the earlier file and may name the new one ${downloadAgainName(name, n)}.`;
}
/** Round 29 (L3): which repeat of `name` the next Download again of a project file is: 1 after a first
 * download, else one more than the count its record (target, the file record before it) holds. Save
 * As and Open keep a new record, so the count starts again. */
export function nextDownloadAgain(target, name) {
  return (target?.how === 'download' && target.name === name && Number.isInteger(target.repeat) ? target.repeat : 0) + 1;
}
/** The name the question says a browser may give the new download: "design-a-ng (1).json". Round 29
 * (L3): n, the repeat of the same name in this tab (1 for the first Download again): "design-a-ng
 * (2).json" for the second. */
export function downloadAgainName(name, n = 1) {
  const stem = name.replace(/\.json$/i, ''), extension = name.slice(stem.length);
  return `${stem} (${Number.isInteger(n) && n >= 1 ? n : 1})${extension}`;
}
/** Its buttons, in order: download under the same name, the Save As name dialog, nothing written. */
export const DOWNLOAD_AGAIN_BUTTONS = Object.freeze(['Download again', 'Save As…', 'Cancel']);

/** The sentence after a download under a name already downloaded: the browser cannot replace it.
 * Round 18 (X5): "a number such as (1)", since a browser that already has a (1) copy adds (2). */
export function downloadAgainNote() {
  return 'A download cannot replace the earlier file, so your browser may add a number such as “ (1)” to its name.';
}

/** The Save and Save As name dialog's line on what a project file will hold (round 18, X5): every
 * model with its run count, "The file will hold Optical waveguide (2 runs) and Heated silicon
 * waveguide (1 run)." models: [{title, runs}]; a model without runs reads "(no runs)". */
export function fileHoldsText(models) {
  const one = m => `${m.title} (${m.runs > 0 ? `${m.runs} ${m.runs === 1 ? 'run' : 'runs'}` : 'no runs'})`;
  const list = models.map(one);
  const words = list.length > 1 ? `${list.slice(0, -1).join(', ')} and ${list.at(-1)}` : list[0] || 'no model';
  return `The file will hold ${words}.`;
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
export function saveToFile(text, {suggestedName, target = null, saveAs = false, win = globalThis, description = null}) {
  // text may be a function of the file's name, called once the name is known: a project file
  // holds its name, which an untitled project takes from the file chosen (P3)
  const textFor = name => typeof text === 'function' ? text(name) : text;
  const route = saveRoute(target, {saveAs, picker: pickerAvailable(win)});
  if (route === 'write') {
    return Promise.resolve().then(() => writeHandle(target.handle, textFor(target.name))).then(() => ({status: 'saved', handle: target.handle, name: target.name}),
      error => ({status: 'failed', name: target.name, error: errorText(error), fresh: false}));
  }
  if (route === 'download') return Promise.resolve({status: 'known', name: target.name});
  if (route === 'ask') return Promise.resolve({status: 'unavailable', error: null});
  let picked;
  try { picked = win.showSaveFilePicker(pickerOptions(suggestedName, target?.handle || null, description)); }
  catch (error) { picked = Promise.reject(error); }
  return Promise.resolve(picked).then(handle => {
    const name = String(handle?.name || suggestedName);
    // a file just chosen in the picker: Chromium may already have created or emptied it
    return Promise.resolve().then(() => writeHandle(handle, textFor(name))).then(() => ({status: 'saved', handle, name}),
      error => ({status: 'failed', name, error: errorText(error), fresh: true}));
  }, error => error?.name === 'AbortError' ? {status: 'cancelled'} : {status: 'unavailable', error: errorText(error)});
}

/** The notice for a save that did not write: a cancel, or a failed write. */
export function notWrittenNotice(result, {saveAs, kind = 'Session'}) {
  if (result.status === 'cancelled') return `${saveAs ? 'Save As' : 'Save'} cancelled; nothing was written.`;
  if (result.status === 'failed') return `${kind} not saved: ${result.name} could not be written (${result.error}); `+(result.fresh ? 'the browser may have left it empty.' : 'the file is unchanged.');
  return `${kind} not saved: nothing was written.`;
}
