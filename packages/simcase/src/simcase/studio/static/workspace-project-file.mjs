// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

// The project file, version 1 (docs/packages/simcase/workspace.md, "Project files"): every model
// of a Studio tab in one file. One compact JSON object, keys in this order:
//   {"format":"openphysics-studio-project","version":1,"name","savedAt","studio","active","models":[…]}
// and each model {id, kind, title, card, bytes, digest, session}. session is the model's session
// object as it is today, unchanged: written alone by its own writer it is byte for byte the session
// file Studio writes for it (version 7 through JSON.stringify, versions 8 and 9 through
// sessionJson, which keeps negative zero). bytes and digest are the UTF-8 length and
// "sha256:<hex>" of that writer's text; the reader rebuilds the text from the parsed object and
// checks both, then reads it with parseSession and all of its checks. The digest detects damage
// and edits; it is not an authentication. name, savedAt, studio, title and card are for display
// only and are in no digest.
import {parseSession,OPTICAL_SESSION_VERSIONS,SESSION_VERSION,MAX_SESSION_BYTES} from './workspace-notebook.mjs';
import {MULTIPHYSICS_VERSION,sessionJson,sha256Hex,byteLength,sizeText} from './workspace-multiphysics-session.mjs';

export const PROJECT_FORMAT='openphysics-studio-project';
export const PROJECT_FILE_VERSION=1;
/** The whole file, checked before it is parsed. */
export const MAX_PROJECT_BYTES=64*1024*1024;
/** One model: today's session limit, so every model still exports as a session file. */
export const MAX_ENTRY_BYTES=MAX_SESSION_BYTES;
export const MAX_MODELS=8;
/** Version 1 holds up to 7 multiphysics models; this Studio holds one per tab. */
export const MAX_MULTIPHYSICS=7;
export const PROJECT_KEYS=Object.freeze(['format','version','name','savedAt','studio','active','models']);
export const ENTRY_KEYS=Object.freeze(['id','kind','title','card','bytes','digest','session']);
export const KINDS=Object.freeze(['workspace','multiphysics']);
export const CARDS=Object.freeze(['optical','heat','joule','heated-waveguide']);
export const UNTITLED_PROJECT='Untitled project';
export const NAME_LIMIT=80;
/** The session versions each kind holds: an optical session (parseSession's own list) or a
 * multiphysics one. */
export const KIND_VERSIONS=Object.freeze({workspace:OPTICAL_SESSION_VERSIONS,multiphysics:Object.freeze([MULTIPHYSICS_VERSION])});
const CONTROL=/[\u0000-\u001f\u007f-\u009f]/;
const ID=/^m\d{1,3}$/;
const DIGEST=/^sha256:[0-9a-f]{64}$/;
const isObject=x=>x!==null&&typeof x==='object'&&!Array.isArray(x);
const fail=message=>{throw new Error(message);};

/** A project name: trimmed, 1 to 80 characters, no control characters; else a named refusal. */
export function validateProjectName(value){
 if(typeof value!=='string')fail('A project name is text.');
 const name=value.trim();
 if(!name)fail(`A project name needs 1 to ${NAME_LIMIT} characters.`);
 if(CONTROL.test(name))fail('A project name cannot hold control characters.');
 if([...name].length>NAME_LIMIT)fail(`A project name has at most ${NAME_LIMIT} characters.`);
 return name;
}
/** The file name a save suggests for a project: its name in lowercase words joined by hyphens
 * ("Heater study" → heater-study.json), untitled-project.json for an untitled project, never a
 * model file's name. */
export function projectFileName(name){
 const s=String(name??'').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-+|-+$/g,'').slice(0,60).replace(/-+$/,'');
 return (s||'untitled-project')+'.json';
}
/** The name an untitled project takes when it is first saved: the chosen file's stem as written
 * ("design-a-ng.json" → "design-a-ng"), cut to 80 characters. */
export function nameFromFile(fileName){
 const stem=String(fileName??'').replace(/\.json$/i,'').replace(CONTROL,'').trim();
 try{return validateProjectName([...stem].slice(0,NAME_LIMIT).join(''));}catch{return UNTITLED_PROJECT;}
}
/** The text a session object's own writer gives: versions 6 and 7 through JSON.stringify, as Studio
 * writes version 7; every other version through sessionJson (versions 8 and 9: negative zero kept). */
export function sessionWriterText(session){
 return session?.version===6||session?.version===SESSION_VERSION?JSON.stringify(session):sessionJson(session);
}
/** A model entry from its session text, as its writer gave it: {id, kind, title, card, text,
 * bytes, digest}. */
export function projectEntry({id,kind,title,card=null,text}){
 return {id,kind,title,card,text,bytes:byteLength(text),digest:'sha256:'+sha256Hex(text)};
}
const plural=(n,word)=>`${n} ${word}${n===1?'':'s'}`;
const andList=items=>items.length<2?items.join(''):items.slice(0,-1).join(', ')+' and '+items.at(-1);
/** The refusal of a save over the limit: the size, and the largest models whose own files would
 * bring it under. */
export function overLimitText(bytes,entries,limit=MAX_PROJECT_BYTES){
 const sorted=[...entries].sort((a,b)=>b.bytes-a.bytes),named=[];let left=bytes;
 for(const e of sorted){if(left<=limit)break;named.push(e);left-=e.bytes;}
 const what=andList(named.map(e=>`${e.title} (${sizeText(e.bytes)})`));
 return `The project is ${sizeText(bytes)}, over the 64 MiB limit. Export ${what} to ${named.length===1?'its own file':'their own files'}, or remove runs.`;
}
/**
 * The project file text. project: {name, savedAt, studio, active, entries} where entries are
 * projectEntry results in Library order. Returns {ok: true, text, bytes} or {ok: false, bytes,
 * refusal} over the limit. The envelope is written compactly, its keys in the contract's order,
 * and each session is its writer's text unchanged.
 */
export function writeProject({name,savedAt,studio,active,entries},{limit=MAX_PROJECT_BYTES}={}){
 const checked=validateProjectName(name);
 if(!entries.length||entries.length>MAX_MODELS)fail(`A project holds 1 to ${MAX_MODELS} models.`);
 if(!entries.some(e=>e.id===active))fail('The model shown is not in the project.');
 const head=`{"format":${JSON.stringify(PROJECT_FORMAT)},"version":${PROJECT_FILE_VERSION},"name":${JSON.stringify(checked)},"savedAt":${JSON.stringify(savedAt)},"studio":${JSON.stringify(String(studio))},"active":${JSON.stringify(active)},"models":[`;
 const pieces=entries.map(e=>{
  if(e.bytes>MAX_ENTRY_BYTES)fail(`${e.title} is ${sizeText(e.bytes)}, over the 16 MiB session limit.`);
  return `{"id":${JSON.stringify(e.id)},"kind":${JSON.stringify(e.kind)},"title":${JSON.stringify(e.title)},"card":${JSON.stringify(e.card)},"bytes":${e.bytes},"digest":${JSON.stringify(e.digest)},"session":`;});
 const bytes=byteLength(head)+2+pieces.reduce((n,p,i)=>n+byteLength(p)+entries[i].bytes+1,0)+Math.max(0,entries.length-1);
 if(bytes>limit)return {ok:false,bytes,refusal:overLimitText(bytes,entries,limit)};
 return {ok:true,bytes,text:head+pieces.map((p,i)=>p+entries[i].text+'}').join(',')+']}'};
}
/** The refusal of a project file newer than this Studio reads. */
export const newerProjectText=version=>`This project file is version ${version}, newer than this Studio reads (version ${PROJECT_FILE_VERSION}). Open it in a newer Studio.`;
/** Whether a parsed JSON value is a project file (any version): the File › Open route. */
export const isProjectDocument=doc=>isObject(doc)&&doc.format===PROJECT_FORMAT;

// A model's name in a message: its title when it is one a file may show, else its id.
const titleOf=(raw,i)=>typeof raw?.title==='string'&&raw.title&&!CONTROL.test(raw.title)&&[...raw.title].length<=200?raw.title:typeof raw?.id==='string'&&ID.test(raw.id)?raw.id:`Model ${i+1}`;
/**
 * Reads a project file's text: every check runs before anything is returned, and the first failure
 * throws a message that names the model and the check. Returns {name, savedAt, studio, active,
 * models: [{id, kind, title, card, bytes, digest, text, session}]}, where session is parseSession's
 * reading of the entry (a multiphysics one still lists the documents the server must check).
 * Steps (the contract's reading order): the size before parsing; valid JSON, a leading byte order
 * mark removed; the envelope; then per entry the kind against the session version, the rebuilt
 * text's bytes and digest, and parseSession with the model's title before its message.
 */
export function readProject(text,{limit=MAX_PROJECT_BYTES,parse=JSON.parse}={}){
 if(typeof text!=='string')fail('A project file is text.');
 const size=byteLength(text);
 if(size>limit)fail(`This project file is ${sizeText(size)}, over the 64 MiB limit.`);
 let doc;try{doc=parse(text.startsWith('﻿')?text.slice(1):text);}catch{fail('This project file is not valid JSON.');}
 if(!isProject(doc))fail('This is not a project file.');
 if(Number.isInteger(doc.version)&&doc.version>PROJECT_FILE_VERSION)fail(newerProjectText(doc.version));
 if(doc.version!==PROJECT_FILE_VERSION)fail('Unsupported project file version.');
 const unknown=Object.keys(doc).find(k=>!PROJECT_KEYS.includes(k));if(unknown!==undefined)fail(`Unknown key ${JSON.stringify(unknown)} in the project file.`);
 const missing=PROJECT_KEYS.find(k=>!Object.hasOwn(doc,k));if(missing!==undefined)fail(`The project file has no ${JSON.stringify(missing)}.`);
 let name;try{name=validateProjectName(doc.name);}catch(e){fail(`The project name is not one Studio writes: ${e.message}`);}
 if(name!==doc.name)fail('The project name is not one Studio writes: it has spaces at its start or end.');
 if(typeof doc.savedAt!=='string'||!Number.isFinite(Date.parse(doc.savedAt)))fail('The project file has an invalid save time.');
 if(typeof doc.studio!=='string'||doc.studio.length>64||CONTROL.test(doc.studio))fail('The project file has an invalid Studio version.');
 if(!Array.isArray(doc.models)||doc.models.length<1||doc.models.length>MAX_MODELS)fail(`A project file holds 1 to ${MAX_MODELS} models.`);
 const ids=new Set();let workspaces=0,multi=0;
 doc.models.forEach((raw,i)=>{
  const what=titleOf(raw,i);
  if(!isObject(raw))fail(`Model ${i+1} of the project file is not a model entry.`);
  const extra=Object.keys(raw).find(k=>!ENTRY_KEYS.includes(k));if(extra!==undefined)fail(`${what}: unknown key ${JSON.stringify(extra)}.`);
  const absent=ENTRY_KEYS.find(k=>!Object.hasOwn(raw,k));if(absent!==undefined)fail(`${what}: missing ${absent}.`);
  if(typeof raw.id!=='string'||!ID.test(raw.id))fail(`${what} has an invalid id (m followed by 1 to 3 digits).`);
  if(ids.has(raw.id))fail(`Two models have the same id ${raw.id}.`);ids.add(raw.id);
  if(!KINDS.includes(raw.kind))fail(`${what} is of an unknown kind.`);
  if(raw.kind==='workspace')workspaces++;else multi++;
  if(typeof raw.title!=='string'||!raw.title||CONTROL.test(raw.title)||[...raw.title].length>200)fail(`Model ${i+1} has an invalid title.`);
  if(raw.card!==null&&!CARDS.includes(raw.card))fail(`${what} names an unknown Library card.`);
  if(!Number.isInteger(raw.bytes)||raw.bytes<0)fail(`${what} has an invalid size.`);
  if(typeof raw.digest!=='string'||!DIGEST.test(raw.digest))fail(`${what} has an invalid check value.`);
  if(!isObject(raw.session))fail(`${what} has no session.`);
 });
 if(workspaces>1)fail('A project file holds at most one workspace model.');
 if(multi>MAX_MULTIPHYSICS)fail(`A project file holds at most ${MAX_MULTIPHYSICS} multiphysics models.`);
 if(typeof doc.active!=='string'||!ids.has(doc.active))fail('The model to show (active) is not in the project file.');
 const models=doc.models.map(raw=>{
  const what=raw.title,s=raw.session,known=[...KIND_VERSIONS.workspace,...KIND_VERSIONS.multiphysics];
  // a session of a version this Studio reads must be of the entry's kind; any other version is
  // refused below by parseSession's own words (a newer one by name)
  if(s.format==='openphysics-studio-session'&&known.includes(s.version)&&!KIND_VERSIONS[raw.kind].includes(s.version))
   fail(`${what} is a ${raw.kind} model, but its session is of version ${s.version}${raw.kind==='workspace'?' (a multiphysics session)':' (an optical session)'}.`);
  let entryText;try{entryText=sessionWriterText(s);}catch(e){fail(`${what}: ${e.message}`);}
  const bytes=byteLength(entryText);
  if(bytes>MAX_ENTRY_BYTES)fail(`${what} is ${sizeText(bytes)}, over the 16 MiB session limit.`);
  if(bytes!==raw.bytes)fail(`${what} changed after it was saved (its size does not match).`);
  if('sha256:'+sha256Hex(entryText)!==raw.digest)fail(`${what} changed after it was saved (its check value does not match).`);
  let session;try{session=parseSession(entryText);}catch(e){fail(`${what}: ${e.message}`);}
  return {id:raw.id,kind:raw.kind,title:raw.title,card:raw.card,bytes,digest:raw.digest,text:entryText,session};
 });
 return {name,savedAt:doc.savedAt,studio:doc.studio,active:doc.active,models};
}
const isProject=isProjectDocument;
/** The models of a project in words, for the save notice and the open message:
 * "Optical waveguide (2 runs, the comparison) and Heated silicon waveguide (1 run, the
 * without-heater result)". items: [{title, parts}] with parts a list of words. */
export function modelsText(items){
 return andList(items.map(m=>m.parts.length?`${m.title} (${m.parts.join(', ')})`:m.title));
}
/** The words of one model's contents: its runs, then what else it holds. */
export function modelParts({runs=0,comparison=false,baseline=false,inputsOnly=false}){
 if(inputsOnly)return ['inputs'];
 return [runs?plural(runs,'run'):'no runs',...(comparison?['the comparison']:[]),...(baseline?['the without-heater result']:[])];
}
/** The one save notice of a project. via: 'picker' or 'download'; known/again: Save downloaded
 * under the remembered name; after: the sentence that follows; notKept: [{title, runs:[n]}] the
 * models whose runs keep values only (the 16 MiB rule). */
export function projectSavedNotice({name,file,via='download',known=false,again=false,models,notKept=[],after=''}){
 const start=via==='picker'?`Saved ${name} to ${file}`:known&&again?`Downloaded ${file} again`:`Project file ${file} sent to your browser's Downloads`;
 const left=notKept.map(m=>` ${m.title} keeps values only for ${andList(m.runs.map(n=>'Run '+n))}, without ${m.kind==='multiphysics'?'maps':'fields'}.`).join('');
 return `${start}: ${modelsText(models)}.`+left+after;
}
