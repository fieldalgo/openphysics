# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Centred tapered trace under a planar dielectric coating, with a mesh check."""
from sipi import CrossSectionDocument
from sipi.templates import coated_microstrip


def main():
    section = coated_microstrip(width=.6e-3, top_width=.4e-3, thickness=.1e-3,
                                substrate_height=1e-3, eps_r=4,
                                coating_height=.2e-3, coating_eps_r=3.5,
                                coating_tan_delta=.02, air_height=2e-3, box_width=6e-3)
    mesh = dict(edge_size=5e-6, far_size=.25e-3, grade=.15)
    document = CrossSectionDocument(section, mesh=mesh)
    restored = CrossSectionDocument.loads(document.dumps())
    initial = restored.analyze()
    refined = section.analyze(**{key: value/2 for key, value in mesh.items()})
    print(f"Input schema: {document.to_dict()['schema']}")
    print(f"Initial Z0: {initial.z0:.6f} ohm; refined: {refined.z0:.6f} ohm")
    print(f"Relative mesh change: {abs(initial.z0/refined.z0-1):.6%}")
    print('Planar filling only; domain truncation and actual mask shape need separate checks.')


if __name__ == '__main__':
    main()
