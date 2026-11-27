// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// The 3D model's session file (decision F2; docs/packages/simcase/workspace.md, "3D models"):
//   {"format":"openphysics-studio-session","version":1,"application":"model3d","document":{…},"view":{…}}
// version 1 holds the format 0.3 document of the model (a version 1 geometry block) and, if any,
// the view it was saved with; runs come with a later version. It is written compactly, keys in this
// order, and read back with every check before anything is used. The 16 MiB session limit applies.
// parseSession (workspace-notebook.mjs) sends a file with application "model3d" here before its own
// version rules, so the other session files read exactly as before.
import {sessionJson,sha256Hex,byteLength,sizeText} from './workspace-multiphysics-session.mjs';

export const MODEL3D_APPLICATION='model3d';
export const MODEL3D_SESSION_VERSION=1;
const MAX_BYTES=16*1024*1024;
const KEYS=Object.freeze(['format','version','application','document','view']);
const isObject=x=>x!==null&&typeof x==='object'&&!Array.isArray(x);
const fail=message=>{throw new Error(message);};

/** Whether a parsed session file holds a 3D model (it is then read here, whatever its version). */
export const isModel3dSession=doc=>isObject(doc)&&doc.format==='openphysics-studio-session'&&doc.application===MODEL3D_APPLICATION;

/** The document's digest: SHA-256 of its compact JSON text, keys in the order the document holds them. */
export const documentDigest=doc=>sha256Hex(sessionJson(doc));

/** The session text of a 3D model: its document and, when given, its view (not part of Undo). */
export function writeModel3dSession(document,view=null){
 checkDocument(document);
 const out={format:'openphysics-studio-session',version:MODEL3D_SESSION_VERSION,application:MODEL3D_APPLICATION,document};
 if(view!==null&&view!==undefined){if(!isObject(view))fail('The model3d session has an invalid view.');out.view=view;}
 const text=sessionJson(out),bytes=byteLength(text);
 if(bytes>MAX_BYTES)fail(`The 3D model is ${sizeText(bytes)}, over the 16 MiB session limit.`);
 return text;
}

function checkDocument(document){
 if(!isObject(document))fail('The model3d session holds no document.');
 if(document.openphysics!=='0.3')fail('The model3d session holds a document that is not format 0.3.');
 if(!isObject(document.geometry)||document.geometry.version!==1)fail('The model3d session holds a document without a version 1 geometry block.');
}

/** A parsed model3d session file checked: {application, version, document, view, runs: []}. */
export function readModel3dSession(doc){
 if(Number.isInteger(doc.version)&&doc.version>MODEL3D_SESSION_VERSION)
  fail(`This model3d session is version ${doc.version}, newer than this Studio reads (version ${MODEL3D_SESSION_VERSION}). Open it in a newer Studio.`);
 if(doc.version!==MODEL3D_SESSION_VERSION)fail('Unsupported model3d session version.');
 const unknown=Object.keys(doc).find(k=>!KEYS.includes(k));if(unknown!==undefined)fail(`Unknown key ${JSON.stringify(unknown)} in the model3d session.`);
 checkDocument(doc.document);
 if(Object.hasOwn(doc,'view')&&!isObject(doc.view))fail('The model3d session has an invalid view.');
 return {application:MODEL3D_APPLICATION,version:doc.version,document:doc.document,view:doc.view??null,runs:[]};
}
