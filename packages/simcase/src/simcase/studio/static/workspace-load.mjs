// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

// File and storage reads share one intent: an older completion cannot reopen a
// dialog or replace a newer choice. A changed workspace requires a fresh review.
export class LatestWorkspaceLoad {
 constructor(context){this.context=context;this.sequence=0;}
 invalidate(){this.sequence++;}
 async read(reader){
  const sequence=++this.sequence,context=this.context();
  try{
   const value=await reader();
   if(sequence!==this.sequence)return null;
   if(context!==this.context())throw new Error('The workspace changed while reading. Open the file or recovery again to review the current state.');
   return {value};
  }catch(error){if(sequence!==this.sequence)return null;throw error;}
 }
}
