# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Public-reference benchmarks in one figure: bimetal strip and NAFEMS T4.

Left: the deformed bimetal strip (Timoshenko 1925 thermostat) coloured by the
axial stress, with the closed-form arc. Middle: the NAFEMS T4 temperature field
with the published target point. Right: mesh convergence of the strip curvature
and of the T4 point temperature against the exact references.

    python examples/galerkin/public_benchmarks.py out-dir [--quick]

Writes public_benchmarks.png and public_benchmarks.json (the numbers in the
caption). The gates live in tests/galerkin/test_public_benchmarks.py; this
script only draws.
"""
import json
import sys
from pathlib import Path

import numpy as np

from galerkin.mesh import layered_rectangle_mesh, rectangle_mesh
from galerkin.thermal import solve_steady_heat
from galerkin.thermoelasticity import freeze_temperature, solve_thermoelasticity
from refsol import bimetal
from refsol import thermal_convection as tc

T1 = T2 = .5e-3
LENGTH = 20e-3
E, NU, ALPHA = [200e9, 70e9], [.3, .33], [12e-6, 23e-6]
DT, TREF, KELVIN = 100., 293.15, 273.15
STRIP = dict(thicknesses=[T1, T2], young_moduli=E, poisson_ratios=NU, expansions=ALPHA,
             temperature_change=DT, length=LENGTH)
P, TARGET = tc.NAFEMS_T4, tc.NAFEMS_T4_TARGET


def solve_strip(n):
    mesh = layered_rectangle_mesh([T1, T1+T2], LENGTH, [n, n], 40*n, ['layer1', 'layer2'])
    snapshot = freeze_temperature(mesh, np.full(len(mesh.nodes), TREF+DT))
    supports = {(0, 0): 0., (0, 1): 0., (40*n*(2*n+1), 0): 0.}
    r = solve_thermoelasticity(
        mesh, snapshot, reference_temperature_k=TREF, plane='stress', dirichlet=supports,
        thermal_expansion_per_k={'layer1': ALPHA[0], 'layer2': ALPHA[1]},
        young_modulus={'layer1': E[0], 'layer2': E[1]},
        poisson_ratio={'layer1': NU[0], 'layer2': NU[1]})
    ids = mesh.boundary['left']
    y = mesh.nodes[ids, 1]
    sel = (y >= LENGTH/4) & (y <= 3*LENGTH/4)
    curvature = -2*np.polyfit(y[sel], r.displacement[ids[sel], 0], 2)[0]
    return mesh, r, curvature


def solve_t4(n):
    mesh = rectangle_mesh(P.width, P.height, 6*n, 10*n)
    hot = {int(i): P.bottom_temperature+KELVIN for i in mesh.boundary['bottom']}
    r = solve_steady_heat(mesh, conductivity=P.conductivity, dirichlet=hot,
                          convection={'right': (P.convection, P.ambient+KELVIN),
                                      'top': (P.convection, P.ambient+KELVIN)})
    celsius = r.temperature-KELVIN
    node = np.flatnonzero(np.isclose(mesh.nodes[:, 0], TARGET.point[0]) & np.isclose(mesh.nodes[:, 1], TARGET.point[1]))[0]
    return mesh, celsius, float(celsius[node])


def main(argv):
    quick = '--quick' in argv
    args = [a for a in argv if not a.startswith('--')]
    if len(args) != 1:
        raise SystemExit(__doc__)
    out = Path(args[0])
    out.mkdir(parents=True, exist_ok=True)
    levels = (1, 2, 4) if quick else (1, 2, 4, 8, 16)
    kappa = bimetal.curvature([T1, T2], E, ALPHA, DT).curvature
    exact_t4 = tc.series(np.array([TARGET.point]), P, terms=300).temperature[0]
    strip_rows, t4_rows = [], []
    for n in levels:
        mesh, r, k = solve_strip(n)
        strip_rows.append(dict(n=n, triangles=mesh.num_triangles, element_m=(T1+T2)/(2*n),
                               curvature_per_m=k, relative_error=k/kappa-1))
        mesh_t, celsius, value = solve_t4(n)
        t4_rows.append(dict(n=n, triangles=mesh_t.num_triangles, element_m=P.height/(10*n),
                            temperature_c=value, error_c=value-exact_t4))
    values = dict(bimetal=dict(closed_form_curvature_per_m=kappa, radius_m=1/kappa, rows=strip_rows,
                               source='S. Timoshenko, J. Opt. Soc. Am. 11, 233-255 (1925), doi:10.1364/JOSA.11.000233'),
                  nafems_t4=dict(exact_c=exact_t4, published_c=TARGET.value, published_precision_c=TARGET.quoted_precision,
                                 rows=t4_rows, source=TARGET.source))
    (out/'public_benchmarks.json').write_text(json.dumps(values, indent=1), encoding='utf-8')
    draw(out/'public_benchmarks.png', mesh, r, mesh_t, celsius, values)
    return values


def draw(path, mesh, r, mesh_t, celsius, values):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.tri as mtri
    fig, axes = plt.subplots(1, 3, figsize=(15.5, 5.2), gridspec_kw=dict(width_ratios=[1.35, .85, 1.1]))
    # Strip: axis y drawn horizontally, thickness x vertically (stretched), displacement scaled.
    scale = .1*LENGTH/np.max(abs(r.displacement))
    y, x = mesh.nodes[:, 1]+scale*r.displacement[:, 1], mesh.nodes[:, 0]+scale*r.displacement[:, 0]
    tri = mtri.Triangulation(y*1e3, x*1e3, mesh.triangles)
    ax = axes[0]
    peak = np.max(abs(r.stress[:, 1]))/1e6
    im = ax.tripcolor(tri, r.stress[:, 1]/1e6, cmap='RdBu_r', shading='flat', vmin=-peak, vmax=peak)
    kappa = values['bimetal']['closed_form_curvature_per_m']
    ys = np.linspace(0, LENGTH, 200)
    ax.plot(ys*1e3, scale*(-kappa*ys**2/2+kappa*LENGTH/2*ys)*1e3, 'k--', lw=1.4,
            label='closed-form arc of the x = 0 face (Timoshenko 1925)')
    ax.plot([0, LENGTH*1e3], [0, 0], color='.55', lw=1, label='undeformed face')
    ax.set_xlabel('along the strip, mm')
    ax.set_ylabel('across the strip, mm (axis stretched; displacement x%d)' % round(scale))
    ax.set_title('Bimetal strip (0.5 mm + 0.5 mm), +100 K, plane stress, %d P1 triangles'
                 % mesh.num_triangles, fontsize=9.5)
    ax.legend(loc='upper left', fontsize=8, frameon=False)
    ax.set_ylim(-.3, 3.2)
    fig.colorbar(im, ax=ax, label='axial stress, MPa', shrink=.85, pad=.02)
    # T4 field
    ax = axes[1]
    tri_t = mtri.Triangulation(mesh_t.nodes[:, 0], mesh_t.nodes[:, 1], mesh_t.triangles)
    im = ax.tricontourf(tri_t, celsius, levels=20, cmap='inferno')
    ax.plot(*TARGET.point, 'wo', mec='k', ms=7)
    ax.annotate('(0.6, 0.2) m\nNAFEMS target %.1f °C\nexact series %.3f °C\nFEM %.3f °C' % (
        TARGET.value, values['nafems_t4']['exact_c'], values['nafems_t4']['rows'][-1]['temperature_c']),
        TARGET.point, xytext=(.04, .5), fontsize=8, color='w',
        arrowprops=dict(arrowstyle='-', color='w', lw=.8))
    ax.set_aspect('equal')
    ax.set_xlabel('x, m'); ax.set_ylabel('y, m')
    ax.set_title('NAFEMS T4: 100 °C edge, insulated left,\nconvection h = 750 W/(m² K) to 0 °C', fontsize=9.5)
    fig.colorbar(im, ax=ax, label='temperature, °C', shrink=.85, pad=.02)
    # Convergence against refinement level n (element size h0/n)
    ax = axes[2]
    rows = values['bimetal']['rows']
    ax.loglog([q['n'] for q in rows], [abs(q['relative_error']) for q in rows], 'o-',
              label='strip curvature vs closed form (h = 0.5 mm / n)')
    rows_t = values['nafems_t4']['rows']
    ax.loglog([q['n'] for q in rows_t], [abs(q['error_c'])/values['nafems_t4']['exact_c'] for q in rows_t], 's-',
              label='T4 temperature at (0.6, 0.2) vs exact series (h = 0.1 m / n)')
    n = np.array([q['n'] for q in rows], dtype=float)
    ax.loglog(n, abs(rows[0]['relative_error'])/n**2, 'k:', lw=1, label='second order')
    ax.loglog(n, abs(rows_t[0]['error_c'])/values['nafems_t4']['exact_c']/n**2, 'k:', lw=1)
    ax.set_xlabel('refinement level n'); ax.set_ylabel('relative error')
    ax.set_title('Mesh convergence against the exact references', fontsize=9.5)
    ax.grid(True, which='both', alpha=.3); ax.legend(fontsize=8, frameon=False, loc='lower left')
    fig.suptitle('OpenPhysics (galerkin) against public references: Timoshenko (1925) bimetal thermostat and '
                 'NAFEMS T4 (target 18.3 °C as quoted by DIANA FEA and FEATool)', fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


if __name__ == '__main__':
    main(sys.argv[1:])
