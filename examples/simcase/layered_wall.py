# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Run, save and optionally export the two-layer thermal tutorial document."""
import argparse
from pathlib import Path

import numpy as np
from simcase import Document, run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path, help='new or empty result directory')
    parser.add_argument('--mesh-size-mm', type=float, default=2.)
    parser.add_argument('--export', action='store_true', help='requires simcase[export]')
    args = parser.parse_args()
    # Fail before a solve/save if the requested optional exporter is unavailable.
    if args.export:
        import meshio  # noqa: F401
        from simcase.export import export_fields

    document = Document.load(Path(__file__).with_suffix('.json'))
    document.data['mesh']['size'] = args.mesh_size_mm
    result = run(document, verbose=False)
    out = result.save(args.output)
    with np.load(out / 'fields.npz', allow_pickle=False) as fields:
        print(f"Temperature range (K): {fields['temperature_k'].min():.6f} "
              f"{fields['temperature_k'].max():.6f}")
        print(f"Mean x flux (W/m^2): {fields['heat_flux_w_m2'][:, 0].mean():.6f}")
        print(f"Thermostat input (W/m): {fields['reaction_w_per_m'].sum():.6f}")
        print(f"Convective output (W/m): {fields['convective_outward_w_per_m'].sum():.6f}")
        print(f"Triangles: {len(fields['triangles'])}")
    if args.export:
        export_fields(out / 'fields.npz', out / 'view.vtu')
    print(f'Saved: {out}')


if __name__ == '__main__':
    main()
