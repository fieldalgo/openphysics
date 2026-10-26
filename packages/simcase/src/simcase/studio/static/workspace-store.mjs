// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

import {validateProject} from './workspace-project.mjs';
import {EditHistory} from './workspace-history.mjs';

// Revisions identify input transitions in this open tab, not persisted solver versions.
export class WorkspaceStore {
 #history;
 #saved=null;
 #revision=0;
 constructor(input){this.#history=new EditHistory(validateProject(input));}
 get document(){return JSON.parse(this.#history.items[this.#history.index]);}
 get signature(){return this.#history.items[this.#history.index];}
 get revision(){return this.#revision;}
 get dirty(){return this.#saved!==this.signature;}
 get canUndo(){return this.#history.canUndo;}
 get canRedo(){return this.#history.canRedo;}
 record(input,group=null){
  const doc=validateProject(input),before=this.signature;
  this.#history.record(doc,group);
  if(this.signature!==before)this.#revision++;
  return this.document;
 }
 endGroup(){this.#history.endGroup();}
 markSaved(){this.#saved=this.signature;}
 replace(input,{saved=false,resetHistory=false}={}){
  const doc=validateProject(input);
  if(resetHistory){
   const changed=JSON.stringify(doc)!==this.signature;
   this.#history=new EditHistory(doc);
   if(changed)this.#revision++;
  }else{this.endGroup();this.record(doc);this.endGroup();}
  if(saved)this.markSaved();
  return this.document;
 }
 undo(){const before=this.signature,doc=this.#history.undo();if(this.signature!==before)this.#revision++;return doc;}
 redo(){const before=this.signature,doc=this.#history.redo();if(this.signature!==before)this.#revision++;return doc;}
 capture(){return {revision:this.#revision,signature:this.signature,input:this.document};}
}
