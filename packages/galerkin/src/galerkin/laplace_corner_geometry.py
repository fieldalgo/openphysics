# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Immutable parametric corner panels for an explicitly bounded rectangle."""
from dataclasses import dataclass
import numpy as np
from .laplace_two_ground import _admit, _positive, _integer

__all__ = ['CornerPanelGeometry', 'prepare_two_ground_corner_panels']


def _immutable(value, dtype=float):
    value=np.asarray(value,dtype=dtype)
    return np.frombuffer(value.tobytes(),dtype=dtype).reshape(value.shape)


@dataclass(frozen=True)
class CornerPanelGeometry:
    """Normalized descriptors; physical displacement is direction*length_unit_m.

    Each density starts at anchor+local_start and follows direction. Shared
    endpoint IDs are local to this snapshot. Faces follow admitted CCW order.
    Arrays own immutable byte storage and are independent of input polygons.
    """
    length_unit_m: float
    normalized_width: float
    normalized_height: float
    normalized_anchors: np.ndarray
    normalized_local_starts: np.ndarray
    normalized_directions: np.ndarray
    exponents: np.ndarray
    owners: np.ndarray
    faces: np.ndarray
    endpoint_ids: np.ndarray

    def __post_init__(self):
        for name in ('normalized_anchors','normalized_local_starts','normalized_directions','exponents'):
            object.__setattr__(self,name,_immutable(getattr(self,name)))
        for name in ('owners','faces','endpoint_ids'):
            object.__setattr__(self,name,_immutable(getattr(self,name),np.int64))

    @property
    def panel_count(self):return len(self.exponents)

    @property
    def normalized_starts(self):
        return _immutable(self.normalized_anchors+self.normalized_local_starts)

    @property
    def normalized_ends(self):
        return _immutable(self.normalized_anchors+self.normalized_local_starts+self.normalized_directions)

    @property
    def lengths_m(self):
        return _immutable(np.hypot(*self.normalized_directions.T)*self.length_unit_m)


def _basis(polygons,count):
    assert count>=16 and count%2==0
    anchors=[];local=[];directions=[];owners=[];faces=[];powers=[];starts=[];ends=[]
    vertex_count=sum(map(len,polygons));vertex_base=0;face_base=0
    for owner,polygon in enumerate(polygons):
        edge=np.roll(polygon,-1,axis=0)-polygon;length=np.linalg.norm(edge,axis=1)
        cosine=np.sum(-np.roll(edge,1,axis=0)*edge,axis=1)/(np.roll(length,1)*length)
        exponent=np.pi/(2*np.pi-np.arccos(np.clip(cosine,-1,1)))
        index=[0,*range(4,count-3),count]
        def phi(k):
            t=k/count;return t**3/(t**3+(1-t)**3)
        for j in range(len(polygon)):
            def ident(k):
                return vertex_base+j if k==0 else vertex_base+(j+1)%len(polygon) if k==count else vertex_count+(face_base+j)*(count+1)+k
            for i,k in zip(index,index[1:]):
                if k<=count//2:
                    u,v=phi(i),phi(k);anchor=polygon[j];origin=u*edge[j];direction=(v-u)*edge[j];a_id,b_id=ident(i),ident(k)
                else:
                    assert i>=count//2
                    u,v=phi(count-k),phi(count-i);anchor=polygon[(j+1)%len(polygon)];origin=-u*edge[j];direction=-(v-u)*edge[j];a_id,b_id=ident(k),ident(i)
                power=exponent[j] if i==0 else exponent[(j+1)%len(polygon)] if k==count else 1.
                anchors.append(anchor);local.append(origin);directions.append(direction);owners.append(owner);faces.append(face_base+j);powers.append(power);starts.append(a_id);ends.append(b_id)
        vertex_base+=len(polygon);face_base+=len(polygon)
    anchor,local,direction=map(np.array,(anchors,local,directions));a=anchor+local;b=a+direction
    geometry=dict(anchor=anchor,local=local,direction=direction,starts=np.array(starts),ends=np.array(ends))
    return a,b,np.array(owners),np.array(faces),np.array(powers),geometry


def prepare_two_ground_corner_panels(polygons, *, width, height, panels_per_edge=32):
    """Prepare corner densities; this does not assemble or solve a field.

    Coordinates and rectangle dimensions are metres. Reuse the convex,
    disjoint, strictly interior two-ground admission: width/height in
    [0.25,16] and the cluster at least its extent away from the side walls.
    Orient each admitted polygon CCW. Require even subdivisions 16..512.
    Merge the first four cubic intervals at either end of every edge into
    one power panel each, leaving n-6 panels per edge and at most 8192 total.
    Powers are pi/(2*pi-interior_angle); all other panels are constant.
    Reject unresolved edges, panel lengths and corner exponents explicitly.
    Existing solvers and their separate panel budgets remain unchanged.
    """
    width,height=_positive(width,'width'),_positive(height,'height')
    count=_integer(panels_per_edge,'panels_per_edge',16,512)
    if count%2:raise ValueError('panels_per_edge must be even')
    admitted,unit,w,h=_admit(polygons,width,height,1)
    if sum(map(len,admitted))*(count-6)>8192:
        raise ValueError('corner panel count exceeds 8192')
    a,b,owner,face,p,g=_basis(admitted,count)
    if not np.all(np.isfinite(p)) or np.any((p<=.5)|(p>1)):
        raise ValueError('corner exponent is unresolved')
    length=np.hypot(*g['direction'].T)
    if not np.isfinite(length).all() or np.any(length<=128*np.finfo(float).eps):
        raise ValueError('corner panel length is unresolved at domain scale')
    return CornerPanelGeometry(unit,w,h,g['anchor'],g['local'],g['direction'],p,
        owner,face,np.column_stack((g['starts'],g['ends'])))
