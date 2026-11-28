# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Circular limit of the explicit linear field against the analytic grounded line,
split from test_laplace_corner_linear_field.py.

The test makes its own uncached solves (16 panels, 16 and 24 vertices) and uses none of the
module's cached ones, so it runs as its own file at no extra solve and the CI test parts
(tools/shards/openphysics_shard.py) can balance it apart from the cached ones.
"""
import numpy as np

from test_laplace_corner_linear_field import solve


def test_circular_limit_against_analytic_grounded_line(record_property):
    # The finite upper plane remains explicit. Geometry refinement approaches
    # the circle; the separate polygon/panel/outer study bounds that bias.
    radius,center_height=.1,.5
    width,height=256.,128.
    b=np.sqrt(center_height**2-radius**2)
    expected=np.array([2*np.pi/np.arccosh(center_height/radius),
        center_height/(2*np.pi*radius*b),1/(2*np.pi*b)])
    errors=[];values=[]
    for vertices in (16,24):
        angle=np.arange(vertices)*2*np.pi/vertices+np.pi/vertices
        circumradius=radius/np.cos(np.pi/vertices)
        polygon=np.column_stack((width/2+circumradius*np.cos(angle),
                                 center_height+circumradius*np.sin(angle)))
        result=solve([polygon],width=width,height=height,panels_per_edge=16,ground_modes=4096)
        actual=np.array([result.whole.capacitance_per_permittivity[0,0],
            result.whole.current_gram[0,0,0],result.whole.current_gram[1:,0,0].sum()])
        values.append(actual.tolist());errors.append(abs(actual-expected)/abs(expected))
    assert np.all(errors[1]<errors[0])
    assert np.max(errors[1])<.005
    record_property('linear_corner_circular_limit',repr((values,[x.tolist() for x in errors])))
