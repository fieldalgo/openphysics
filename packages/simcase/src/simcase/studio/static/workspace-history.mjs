// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

export class EditHistory {
  constructor(value,limit=60){this.limit=limit;this.items=[JSON.stringify(value)];this.index=0;this.group=null;}
  record(value,group=null){
    const text=JSON.stringify(value);
    if(text===this.items[this.index])return;
    this.items.length=this.index+1;
    if(group!==null&&this.group===group&&this.index>0)this.items[this.index]=text;
    else{this.items.push(text);this.index++;if(this.items.length>this.limit+1){this.items.shift();this.index--;}}
    this.group=group;
  }
  endGroup(){this.group=null;}
  get canUndo(){return this.index>0;}
  get canRedo(){return this.index<this.items.length-1;}
  undo(){this.endGroup();if(this.canUndo)this.index--;return JSON.parse(this.items[this.index]);}
  redo(){this.endGroup();if(this.canRedo)this.index++;return JSON.parse(this.items[this.index]);}
}
