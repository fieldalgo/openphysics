# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Compare a vector TE slab with an independent infinite-cladding reference."""
import numpy as np
from galerkin import rectangle_mesh, solve_modes
from refsol.slab import modes

N_FILM, N_CLAD, THICKNESS, WAVELENGTH = 3.48, 1.444, 0.22, 1.55


def solve(scale, pad):
    # All lengths are micrometres; k0 uses the reciprocal unit.
    # Both material interfaces lie on rows of this structured mesh.
    height = 2 * pad + THICKNESS
    mesh = rectangle_mesh(.1, height, 2 * scale, round(height / .02) * scale)
    y = mesh.nodes[mesh.triangles].mean(axis=1)[:, 1]
    eps = np.where((y > pad) & (y < pad + THICKNESS), N_FILM**2, N_CLAD**2)
    pec = np.unique(np.concatenate(list(mesh.boundary.values())))
    values, _, _, _ = solve_modes(mesh, eps, 2 * np.pi / WAVELENGTH,
                                  n_target=N_FILM, num_modes=6, pec_nodes=pec)
    guided = values[(values > N_CLAD) & (values < N_FILM)]
    if not len(guided):
        raise RuntimeError('No guided candidate found')
    return float(np.max(guided))


def main():
    reference = modes(n_f=N_FILM, n_s=N_CLAD, n_c=N_CLAD,
                      d=THICKNESS, wavelength=WAVELENGTH, pol='TE')[0]
    print(f'Infinite-cladding TE0 reference: {reference:.9f}')
    rows = []
    for study, settings in (
        ('mesh', [(s, 1.5) for s in (1, 2, 4)]),
        ('window', [(4, p) for p in (.1, .5, 1.5)]),
    ):
        for scale, pad in settings:
            value = solve(scale, pad)
            error = abs(value - reference) / reference
            rows.append((study, scale, pad, value, error))
            print(f'{study:6s} scale={scale} pad_um={pad:.1f} '
                  f'neff={value:.9f} relative_error={error:.3e}')
    return reference, rows


if __name__ == '__main__':
    main()
