// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

// The File and Edit menus at the left of the ribbon: menu buttons (aria-haspopup="menu") that
// open role="menu" lists of role="menuitem" buttons, with submenus (File › Export, File ›
// Browser copy). Keyboard: Enter, Space or Down opens a menu on its first item, Up on its last;
// Up, Down, Home and End move; Right opens a submenu (or the next menu), Left closes it (or goes
// to the previous menu); Escape closes one level and returns focus; Tab closes every menu. A
// pointer click outside closes them. Choosing an item closes the menus before its action runs,
// in the same click or key press, so an action that needs it (the save picker) keeps it.

const items = menu => [...menu.children].map(c => c.matches('[role=menuitem]') ? c : c.querySelector(':scope>[role=menuitem]')).filter(b => b && !b.hidden && !b.disabled && !b.closest('[hidden]'));
const submenuOf = item => item.getAttribute('aria-haspopup') === 'menu' ? document.getElementById(item.getAttribute('aria-controls')) : null;

/** buttons: the menu buttons in order (File, Edit). Each controls its menu by aria-controls. */
export function setupMenus(buttons) {
  const menuOf = button => document.getElementById(button.getAttribute('aria-controls'));
  const openSubmenus = [];
  function closeSub(item) {
    const sub = submenuOf(item);
    if (!sub || sub.hidden) return;
    for (const inner of items(sub)) closeSub(inner);
    sub.hidden = true; item.setAttribute('aria-expanded', 'false');
    const i = openSubmenus.indexOf(item); if (i >= 0) openSubmenus.splice(i, 1);
  }
  function close(button, {focus = false} = {}) {
    const menu = menuOf(button);
    for (const item of [...menu.querySelectorAll('[aria-haspopup=menu]')]) closeSub(item);
    menu.hidden = true; button.setAttribute('aria-expanded', 'false');
    if (focus) button.focus();
  }
  const closeAll = opts => { for (const b of buttons) if (b.getAttribute('aria-expanded') === 'true') close(b, opts); };
  function open(button, which = 'first') {
    for (const b of buttons) if (b !== button) close(b);
    const menu = menuOf(button);
    menu.hidden = false; button.setAttribute('aria-expanded', 'true');
    const list = items(menu);
    if (which) list[which === 'last' ? list.length - 1 : 0]?.focus();
  }
  function openSub(item) {
    const sub = submenuOf(item);
    if (!sub) return false;
    for (const sibling of items(item.closest('[role=menu]'))) if (sibling !== item) closeSub(sibling);
    sub.hidden = false; item.setAttribute('aria-expanded', 'true'); openSubmenus.push(item);
    items(sub)[0]?.focus();
    return true;
  }
  const move = (menu, from, step) => {
    const list = items(menu); if (!list.length) return;
    const i = list.indexOf(from);
    list[(i + step + list.length) % list.length].focus();
  };
  for (const button of buttons) {
    const menu = menuOf(button);
    button.addEventListener('click', () => { if (button.getAttribute('aria-expanded') === 'true') close(button); else open(button, null); });
    button.addEventListener('keydown', event => {
      if (event.key === 'ArrowDown' || event.key === 'Enter' || event.key === ' ') { event.preventDefault(); open(button, 'first'); }
      else if (event.key === 'ArrowUp') { event.preventDefault(); open(button, 'last'); }
      else if (event.key === 'Escape' && button.getAttribute('aria-expanded') === 'true') { event.preventDefault(); close(button); }
    });
    menu.addEventListener('keydown', event => {
      const item = event.target.closest('[role=menuitem]'); if (!item) return;
      const list = item.closest('[role=menu]'), top = list === menu, index = buttons.indexOf(button);
      const key = event.key;
      if (key === 'ArrowDown' || key === 'ArrowUp') { event.preventDefault(); move(list, item, key === 'ArrowDown' ? 1 : -1); }
      else if (key === 'Home' || key === 'End') { event.preventDefault(); const l = items(list); l[key === 'Home' ? 0 : l.length - 1]?.focus(); }
      else if (key === 'ArrowRight') { event.preventDefault(); if (!openSub(item) && buttons.length > 1) open(buttons[(index + 1) % buttons.length]); }
      else if (key === 'ArrowLeft') {
        event.preventDefault();
        if (!top) { const parent = document.querySelector(`[aria-controls="${list.id}"]`); closeSub(parent); parent.focus(); }
        else if (buttons.length > 1) open(buttons[(index - 1 + buttons.length) % buttons.length]);
      } else if (key === 'Escape') {
        event.preventDefault(); event.stopPropagation();
        if (!top) { const parent = document.querySelector(`[aria-controls="${list.id}"]`); closeSub(parent); parent.focus(); }
        else close(button, {focus: true});
      } else if (key === 'Tab') closeAll();
      else if ((key === 'Enter' || key === ' ') && submenuOf(item)) { event.preventDefault(); openSub(item); }
    });
    menu.addEventListener('click', event => {
      const item = event.target.closest('[role=menuitem]'); if (!item || item.disabled) return;
      if (submenuOf(item)) { if (item.getAttribute('aria-expanded') === 'true') closeSub(item); else openSub(item); return; }
      // the item's own click handler runs after this one, in the same event
      if (button.getAttribute('aria-expanded') === 'true') close(button, {focus: true});
    }, true);
  }
  document.addEventListener('pointerdown', event => { if (!buttons.some(b => b.parentElement.contains(event.target))) closeAll(); });
  return {closeAll};
}
