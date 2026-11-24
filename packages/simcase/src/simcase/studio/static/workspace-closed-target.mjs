// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

// optical-shapes-v10: Search near n_eff in a closed window (design "Search near n_eff for
// closed-window runs", slice C1). With a target t and every edge closed, the optical document's
// em1 gets target_effective_index t after its other keys: the engine then returns the mode_count
// eigenvalues nearest t (Re > 0, no threshold), listed by descending Re n_eff. Without a target the
// document is the optical-shapes-v8 or -v9 one, byte for byte. No engine change.
import {maxIndex,defaultTarget,TARGET_FLOOR} from './workspace-open-boundary.mjs';

export const CLOSED_TARGET_ADAPTER='optical-shapes-v10';
// The query a workspace request with a closed-window target carries (capabilities v10).
export const CLOSED_TARGET_QUERY='workspace_capabilities=10';
export {defaultTarget};

/** A closed-window Search near n_eff, checked: a number kept to 3 decimals, above 1.45 and below
 * the design's largest index at 1550 nm (the open boundary's bounds). */
export function checkClosedTarget(t,shapes){
 const nmax=maxIndex(shapes);
 if(typeof t!=='number'||!Number.isFinite(t)||Math.round(t*1000)/1000!==t||!(t>TARGET_FLOOR&&t<nmax))throw new Error(`Search near n_eff must lie between ${TARGET_FLOOR} and ${nmax} (3 decimals).`);
 return t;
}

/** The optical-shapes-v10 document: the closed document `doc` with target_effective_index t
 * (checked) after the other em1 keys. */
export function applyClosedTarget(doc,t){
 const em=doc.physics.em1;
 return {...doc,physics:{em1:{...em,target_effective_index:t}}};
}
