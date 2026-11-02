# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Finite-metal volume meshes for longitudinal current diffusion.

This is a separate magnetic-domain contract: box grounds become finite-width
metal plates with explicit thickness, surrounded by explicit magnetic padding.
The existing dielectric-only cross-section mesh is not changed or reused.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

import numpy as np
from galerkin import from_mesher
from meshine import Domain, generate

from .crosssection import CrossSection, Trace
from .conductor_diffusion import conductor_impedance, _indices
from .network import _scalar

__all__ = ['MeshedConductors', 'mesh_conductor_section']


@dataclass(frozen=True)
class MeshedConductors:
    """Full magnetic mesh, metal triangle groups and explicit construction inputs."""
    mesh: object
    signals: dict
    ground: np.ndarray
    magnetic_boundary: np.ndarray
    settings: dict
    layer_triangles: dict | None = None

    def __post_init__(self):
        def readonly(name,value,size,allow_empty=False):
            if allow_empty and np.asarray(value).shape == (0,):
                a = np.array([],dtype=int)
            else:
                a = _indices(name,value,size)
            a.setflags(write=False)
            return a
        object.__setattr__(self,'signals',MappingProxyType(
            {k:readonly(k,v,self.mesh.num_triangles) for k,v in self.signals.items()}))
        object.__setattr__(self,'ground',readonly('ground',self.ground,self.mesh.num_triangles))
        object.__setattr__(self,'magnetic_boundary',readonly(
            'magnetic_boundary',self.magnetic_boundary,self.mesh.num_nodes))
        object.__setattr__(self,'settings',MappingProxyType(dict(self.settings)))
        if self.layer_triangles is not None:
            object.__setattr__(self,'layer_triangles',MappingProxyType(
                {k:readonly(k,v,self.mesh.num_triangles,True) for k,v in self.layer_triangles.items()}))

    def impedance(self, frequency, *, conductivity, relative_permeability=1.0, keep_fields=False):
        return conductor_impedance(self.mesh,frequency,signals=self.signals,ground=self.ground,
            magnetic_boundary=self.magnetic_boundary,conductivity=conductivity,
            relative_permeability=relative_permeability,keep_fields=keep_fields)


def mesh_conductor_section(section, *, ground_thickness, padding, metal_size,
                           far_size, grade=.2, min_angle=28.0,
                           dielectric_interfaces=False):
    """Build a conforming volume mesh including finite trace/reference metal.

    Positive-thickness rectangular and centred tapered traces are supported.
    Bottom/top plates have the section width and extend out of its dielectric
    box; side grounds extend outward and join horizontal plates without overlap.
    Ground traces and all plates form one common longitudinal reference group.
    The magnetic box extends padding beyond every side of that construction.

    metal_size and far_size are target edge sizes, not an error estimate. The
    diffusion solver independently checks the actual metal edges against skin
    depth. Relative permeability is uniform; dielectric layer eps is not used.
    dielectric_interfaces=True also resolves the finite dielectric box/layers
    and records their triangle sets; the exterior remains nonconducting space.
    """
    if type(dielectric_interfaces) is not bool:
        raise ValueError('dielectric_interfaces must be boolean')
    if not isinstance(section,CrossSection):
        raise TypeError('section must be a CrossSection')
    values = {k:_scalar(k,v) for k,v in dict(ground_thickness=ground_thickness,
              padding=padding,metal_size=metal_size,far_size=far_size,min_angle=min_angle).items()}
    grade = _scalar('grade',grade,zero=True)
    if values['far_size'] < values['metal_size'] or values['min_angle'] >= 34:
        raise ValueError('need far_size >= metal_size and 0 < min_angle < 34')
    if any(trace.thickness <= 0 for trace in section.traces):
        raise ValueError('volume current diffusion requires finite-thickness traces')
    thickness,padding,metal_size,far_size,min_angle = (
        values[k] for k in ('ground_thickness','padding','metal_size','far_size','min_angle'))
    w,h = section.width,section.height
    solids = list(section.traces)
    bottom,top = section.bottom == 'ground',section.top == 'ground'
    low,high = -thickness if bottom else 0., h+thickness if top else h
    if bottom:
        solids.append(Trace('_bottom',0,w,-thickness,thickness,ground=True))
    if top:
        solids.append(Trace('_top',0,w,h,thickness,ground=True))
    if section.sides == 'ground':
        for side in (-1,1):
            solids.append(Trace('_side',side*(w+thickness)/2,thickness,low,high-low,ground=True))
    if not any(trace.ground for trace in solids):
        raise ValueError('at least one finite reference conductor is required')
    names = tuple(trace.name for trace in solids if not trace.ground)
    if not names:
        raise ValueError('at least one signal conductor is required')
    identifiers = {name:f'signal-{i}' for i,name in enumerate(names)}
    xmin = min(-w/2,*(trace.xmin for trace in solids))-padding
    xmax = max(w/2,*(trace.xmax for trace in solids))+padding
    ymin,ymax = low-padding,high+padding
    layer_heights = np.r_[0.,np.cumsum([layer.thickness for layer in section.layers])]
    ys = {ymin,ymax,*(trace.y for trace in solids),*(trace.y1 for trace in solids)}
    if dielectric_interfaces:
        ys.update(layer_heights)
    ys = sorted(ys)
    domain = Domain(size=far_size)
    tolerance = 1e-12*max(xmax-xmin,ymax-ymin)

    def region(name,left,right,y0,y1):
        widths = np.asarray(right)-left
        if np.min(widths) < -tolerance:
            raise ValueError('metal regions overlap in the magnetic construction')
        if np.max(widths) <= tolerance:
            return
        domain.add_region(name,[(left[0],y0),(right[0],y0),(right[1],y1),(left[1],y1)],
                          size=metal_size if name == 'reference' or name.startswith('signal-') else far_size)

    def space(left,right,y0,y1):
        midpoint = (y0+y1)/2
        if not dielectric_interfaces or midpoint < 0 or midpoint >= h:
            region('space',left,right,y0,y1)
            return
        layer = int(np.searchsorted(layer_heights,midpoint,side='right')-1)
        for lower,upper,name in ((-np.inf,-w/2,'space'),
                                 (-w/2,w/2,f'dielectric-{layer}'),
                                 (w/2,np.inf,'space')):
            lo,hi = np.maximum(left,lower),np.minimum(right,upper)
            if np.max(hi-lo) > tolerance:
                region(name,lo,hi,y0,y1)

    # Slabs preserve all polygon interfaces, including tapered faces and plate
    # T-junctions. Unlike holes, the metal interiors are themselves regions.
    for y0,y1 in zip(ys[:-1],ys[1:]):
        midpoint = (y0+y1)/2
        active = sorted((trace for trace in solids if trace.y < midpoint < trace.y1),key=lambda t:t.x)
        left = np.array([xmin,xmin])
        for trace in active:
            halfwidth = trace.width_at(np.array([y0,y1]))/2
            lo,hi = trace.x-halfwidth,trace.x+halfwidth
            space(left,lo,y0,y1)
            region('reference' if trace.ground else identifiers[trace.name],lo,hi,y0,y1)
            left = hi
        space(left,np.array([xmax,xmax]),y0,y1)

    def size_fn(x,y):
        distance = np.min(np.stack([trace.distance(x,y) for trace in solids]),axis=0)
        return np.minimum(metal_size+grade*distance,far_size)

    mesh = from_mesher(generate(domain,'outer',size_fn=size_fn,min_angle=min_angle,candidate_order='stable'))
    labels = np.asarray(mesh.region_names)[mesh.regions]
    signals = {name:np.flatnonzero(labels == identifier) for name,identifier in identifiers.items()}
    ground = np.flatnonzero(labels == 'reference')
    layers = ({layer.name:np.flatnonzero(labels == f'dielectric-{i}')
               for i,layer in enumerate(section.layers)} if dielectric_interfaces else None)
    return MeshedConductors(mesh,signals,ground,mesh.boundary['outer'],
        dict(values,grade=grade,dielectric_interfaces=dielectric_interfaces),layers)
