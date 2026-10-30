# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Save/restore a local mask and a concave conductor; check mesh refinement."""
from sipi import CrossSection, CrossSectionDocument, Layer, PolygonTrace
from sipi.templates import microstrip, with_surface_mask

mesh = dict(edge_size=10e-6, far_size=.2e-3, grade=.15)
fine = dict(edge_size=5e-6, far_size=.1e-3, grade=.075)
bare = microstrip(width=.4e-3, substrate_height=1e-3, eps_r=4,
                  thickness=.1e-3, air_height=1e-3, box_width=4e-3)
masked = with_surface_mask(bare, thickness=.03e-3, eps_r=3.5,
                           tan_delta=.02, gap_fill_height=.08e-3)
polygon = CrossSection([Layer('substrate',1e-3,4),Layer('air',1e-3)],
    [PolygonTrace('signal',[(-.3e-3,1e-3),(.3e-3,1e-3),(.2e-3,1.2e-3),
                             (0,1.2e-3),(0,1.1e-3),(-.3e-3,1.1e-3)])],4e-3)
for name, section in (('mask',masked),('polygon',polygon)):
    doc = CrossSectionDocument(section,mesh=mesh)
    restored = CrossSectionDocument.loads(doc.dumps())
    coarse = restored.analyze()
    refined = restored.section.analyze(**fine)
    change = abs(coarse.z0/refined.z0-1)
    print(f'{name}: {doc.to_dict()["schema"]}, Z={coarse.z0:.6f} -> {refined.z0:.6f} ohm; '
          f'mesh change={change:.4%}')
    assert change < .005
