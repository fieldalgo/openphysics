// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

// Display coordinates only: never convert this schematic camera into model units.
export class SchematicCamera {
  constructor() { this.fit(); }
  fit() { this.zoom = 1; this.x = 300; this.y = 175; }
  // Show a drawing-unit box as large as the zoom limits allow, centred.
  fitTo([x, y, width, height]) {
    if (![x, y, width, height].every(Number.isFinite) || width <= 0 || height <= 0) return;
    this.zoom = Math.min(4, Math.max(1, Math.min(600 / width, 350 / height)));
    this.x = x + width / 2; this.y = y + height / 2;
    this.constrain();
  }
  scale(factor) {
    if (!Number.isFinite(factor) || factor <= 0) return;
    this.zoom = Math.min(4, Math.max(1, this.zoom * factor));
    this.constrain();
  }
  pan(dx, dy) {
    if (!Number.isFinite(dx) || !Number.isFinite(dy)) return;
    this.x += dx * 600 / this.zoom;
    this.y += dy * 350 / this.zoom;
    this.constrain();
  }
  constrain() {
    const width = 600 / this.zoom, height = 350 / this.zoom;
    this.x = Math.min(600 - width / 2, Math.max(width / 2, this.x));
    this.y = Math.min(350 - height / 2, Math.max(height / 2, this.y));
  }
  get box() { return [this.x - 300 / this.zoom, this.y - 175 / this.zoom, 600 / this.zoom, 350 / this.zoom]; }
}

export function installViewport(host, camera, { fit = () => camera.fit(), fitShapes = null, onChange = null } = {}) {
  const svg = host.querySelector('svg[role="group"]');
  if (!svg) return;
  const bar = document.createElement('div');
  bar.className = 'toolbar viewport-tools';
  bar.setAttribute('role', 'group');
  bar.setAttribute('aria-label', 'Geometry view controls');
  const output = document.createElement('output');
  output.setAttribute('aria-live', 'polite');
  const refresh = () => {
    // Width edits replace the SVG while retaining these controls.
    const current = host.querySelector('svg[role="group"]');
    if (!current) return;
    current.setAttribute('viewBox', camera.box.join(' '));
    // Labels and handles keep their screen size at any zoom (see workspace.css and the shape editor).
    current.style.setProperty('--view-scale', String(1 / camera.zoom));
    current.setAttribute('tabindex', '0');
    current.setAttribute('aria-describedby', 'schematic-navigation-help');
    current.onkeydown = event => {
      if (event.target !== current || event.ctrlKey || event.metaKey || event.altKey) return;
      const action = keys[event.key];
      if (action) { event.preventDefault(); action(); refresh(); }
    };
    output.textContent = Math.round(camera.zoom * 100) + (current.dataset.geometryView==='physical'?'% · optical section (nm)':'% · schematic');
    zoomOut.disabled = camera.zoom <= 1;
    zoomIn.disabled = camera.zoom >= 4;
    onChange?.();
  };
  const keys = {
    '+': () => camera.scale(1.25), '=': () => camera.scale(1.25),
    '-': () => camera.scale(0.8), Home: fit,
    ArrowLeft: () => camera.pan(-0.1, 0), ArrowRight: () => camera.pan(0.1, 0),
    ArrowUp: () => camera.pan(0, -0.1), ArrowDown: () => camera.pan(0, 0.1),
  };
  const button = (label, key) => {
    const el = document.createElement('button'); el.type = 'button';
    el.textContent = label; el.onclick = () => { keys[key](); refresh(); };
    bar.append(el); return el;
  };
  const zoomOut = button('Zoom out', '-'), zoomIn = button('Zoom in', '+');
  button('Fit view', 'Home');
  if (fitShapes) { const el = document.createElement('button'); el.type = 'button'; el.textContent = 'Fit shapes'; el.onclick = () => { fitShapes(); refresh(); }; bar.append(el); }
  button('Pan left', 'ArrowLeft'); button('Pan right', 'ArrowRight');
  button('Pan up', 'ArrowUp'); button('Pan down', 'ArrowDown');
  bar.append(output);
  const help = document.createElement('p'); help.id = 'schematic-navigation-help';
  help.className = 'muted';
  help.textContent = 'Focus the drawing: + / − to zoom, arrows to pan, Home to fit. View changes do not edit the model.';
  host.prepend(bar); host.append(help); refresh();
  return refresh;
}
