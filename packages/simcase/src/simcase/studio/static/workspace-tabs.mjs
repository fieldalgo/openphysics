// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

// The page tabs above the workbench (Library, Model, Connections, Results, Compare) as an ARIA
// tablist: the shown page's tab is aria-selected and the one tab stop; Left and Right move to the
// previous and next tab and open its page, Home and End to the first and last.
const tabs = nav => [...nav.querySelectorAll('[role=tab]')];

/** Marks the tab of page as selected (aria-selected, tabindex 0) and the others not (tabindex -1). */
export function markPageTabs(nav, page) {
  for (const tab of tabs(nav)) {
    const on = tab.dataset.page === page;
    tab.setAttribute('aria-selected', String(on));
    tab.tabIndex = on ? 0 : -1;
  }
}

/** The tab a key moves to from the tab at index i of n tabs, or null for another key. */
export function tabKeyTarget(key, i, n) {
  if (key === 'ArrowRight') return (i + 1) % n;
  if (key === 'ArrowLeft') return (i - 1 + n) % n;
  if (key === 'Home') return 0;
  if (key === 'End') return n - 1;
  return null;
}

/** Arrow-key movement: the key's target tab is focused and clicked (its page opens). */
export function installPageTabs(nav) {
  nav.addEventListener('keydown', event => {
    const list = tabs(nav), i = list.indexOf(event.target);
    if (i < 0 || event.altKey || event.ctrlKey || event.metaKey) return;
    const target = tabKeyTarget(event.key, i, list.length);
    if (target === null) return;
    event.preventDefault();
    list[target].focus();
    list[target].click();
  });
}
