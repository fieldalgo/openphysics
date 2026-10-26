# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Document validation for modal complex coordinates."""
import math


def validate(p, domain, where, error):
    def fail(message): raise error(f'{where}: {message}')
    def number(value,label,positive=False):
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or (positive and value<=0):
            fail(f'{label} must be finite'+(' and positive' if positive else ''))
    if 'bend' in p and 'pml' not in p: fail('bend requires pml')
    if 'pml' not in p: return
    if 'n_target' not in p: fail('pml requires explicit positive n_target')
    c=p['pml']
    if not isinstance(c,dict) or set(c)-{'thickness','strength','order','min_physical_fraction'}:
        fail('pml accepts thickness, strength, order and min_physical_fraction')
    widths=c.get('thickness')
    if not isinstance(widths,dict) or not widths or set(widths)-{'left','right','bottom','top'}:
        fail('pml.thickness must map domain faces to lengths')
    for side,width in widths.items():
        number(width,'pml.thickness.'+side)
        if width<0: fail('PML thickness cannot be negative')
        if width>0 and p['boundary'].get(side)!='pec': fail('PML outer faces require PEC')
    if not any(v>0 for v in widths.values()): fail('at least one PML thickness must be positive')
    if widths.get('left',0)+widths.get('right',0)>=domain['xmax']-domain['xmin'] or widths.get('bottom',0)+widths.get('top',0)>=domain['ymax']-domain['ymin']:
        fail('PML strips leave no physical window')
    number(c.get('strength',3.),'pml.strength',True)
    order=c.get('order',2)
    if isinstance(order,bool) or not isinstance(order,int) or order not in (2,3,4): fail('pml.order must be integer 2, 3 or 4')
    fraction=c.get('min_physical_fraction',.1)
    number(fraction,'pml.min_physical_fraction')
    if not 0<=fraction<=1: fail('pml.min_physical_fraction must be in [0,1]')
    if 'bend' in p:
        b=p['bend']
        if not isinstance(b,dict) or set(b)-{'radius','axis','origin'}: fail('bend accepts radius, axis, origin')
        number(b.get('radius'),'bend.radius',True)
        number(b.get('origin',0.),'bend.origin')
        axis=b.get('axis','x')
        if axis not in ('x','y'): fail('bend.axis must be x or y (outward direction)')
        if b['radius']+domain[axis+'min']-b.get('origin',0.)<=0: fail('entire bend domain must have positive radius')
