// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

//! Constrained Delaunay refinement (M5 stage 2 of the pre-registered 3D plan; lab
//! design note m5-refinement.md).
//!
//! Starts from the constrained Delaunay tetrahedralization of boundary recovery and
//! inserts points until no subsegment or subfacet is encroached and no tetrahedron of
//! the domain is too large (circumradius R > alpha h) or skinny (R / shortest edge >
//! B). Split classes in priority order:
//! 1. an encroached subsegment (a vertex strictly inside its diametral ball) is split
//!    at its midpoint, an S point on its input segment;
//! 2. an encroached subfacet (a vertex strictly inside its equatorial ball) is split at
//!    its circumcentre, an F point exactly in its facet's plane; if that point lies
//!    beyond a subsegment of the facet, or would encroach a subsegment, the subsegment
//!    is split instead;
//! 3. a bad tetrahedron is split at its circumcentre, a volume point (doubles); if the
//!    point lies beyond a subfacet, or would encroach a subfacet or a subsegment, those
//!    are queued and the point is not inserted.
//!
//! Every insertion is constrained Bowyer-Watson: the cavity is the set of tetrahedra
//! whose circumspheres contain the point (exact insphere with the index-ordered
//! perturbation), reached without crossing a subfacet, except subfacets that contain
//! the point, which are split with it. The number of inserted points is capped: hitting
//! the cap is an error, never a hang.

use std::collections::{BinaryHeap, HashMap, VecDeque};

use crate::delaunay::Geom;
use crate::facetrec::{face, key, Boundary, Complex, NONE};
use crate::mixed::{MixedCounters, MixedPoints, Pt, SPoint};
use crate::predicates::P3;

#[derive(Debug, Clone, Copy)]
pub struct RefineOptions {
    /// target size: split a tetrahedron when R > alpha h (0: no size bound)
    pub h: f64,
    pub alpha: f64,
    /// radius-edge bound B (0: no quality bound)
    pub ratio: f64,
    pub max_points: usize,
}

#[derive(Debug, Clone, Copy, Default)]
pub struct RefineStats {
    pub segment_points: u32,
    pub facet_points: u32,
    pub volume_points: u32,
    pub rejected: u32,
    /// insertions that fell back to the minimal cavity (the tetrahedra holding the point)
    pub minimal: u32,
    /// subsegments left unsplit because doubles cannot split them (small input angles)
    pub exempt: u32,
    /// encroached subfacets left unsplit by the small-angle rule
    pub exempt_faces: u32,
    /// points inserted to remove slivers (dihedral refinement, M6 step 1)
    pub sliver_points: u32,
    /// slivers left: below the dihedral bound when refinement ended
    pub slivers_left: u32,
    /// volume vertices moved to remove slivers (M6 step 2)
    pub sliver_moves: u32,
}

struct State<'a> {
    g: MixedPoints,
    cx: Complex,
    xyz: Vec<P3>,
    /// insertion radius per vertex: an input vertex's shortest incident edge at the start,
    /// an inserted point's distance to its nearest neighbour when inserted (small-angle rule)
    rins: Vec<f64>,
    inside: Vec<bool>,
    /// per tetrahedron: the size h of its region (0: no size bound; negative: a hole, not
    /// refined for quality or size)
    hsz: Vec<f64>,
    /// subfacet -> its facets (two where touching shells share it)
    sub: HashMap<[u32; 3], Vec<u32>>,
    /// subsegment -> chain index
    seg: HashMap<(u32, u32), u32>,
    chains: Vec<Vec<u32>>,
    /// per input vertex: whether two segments meet there at less than 60 degrees
    small_apex: Vec<bool>,
    /// the subfacets being split on the current call chain
    splitting: Vec<[u32; 3]>,
    /// per facet: three input points spanning its plane, and the projection axis
    frame: Vec<([u32; 3], usize)>,
    opt: RefineOptions,
    stats: RefineStats,
    segq: VecDeque<(u32, u32)>,
    subq: VecDeque<[u32; 3]>,
    tetq: BinaryHeap<(u64, std::cmp::Reverse<[u32; 4]>, u32)>,
    /// slivers (minimum dihedral below DIHEDRAL_MIN), the lowest priority, worst first
    dihq: BinaryHeap<(std::cmp::Reverse<u64>, std::cmp::Reverse<[u32; 4]>, u32)>,
    n: MixedCounters,
    _p: std::marker::PhantomData<&'a ()>,
}

/// M6 step 1: a tetrahedron (with a size) whose smallest dihedral angle is below this many
/// degrees is split at the lowest priority, unless its circumradius is below
/// SLIVER_FILTER h (its circumcentre would come too close to a vertex), up to
/// SLIVER_CAP times the points refinement inserted before (lfs-free cap).
const DIHEDRAL_MIN: f64 = 15.0;
const SLIVER_FILTER: f64 = 0.7;
const SLIVER_CAP: f64 = 0.10;

fn ekey(a: u32, b: u32) -> (u32, u32) {
    (a.min(b), a.max(b))
}

fn sub3(a: &P3, b: &P3) -> P3 {
    [a[0] - b[0], a[1] - b[1], a[2] - b[2]]
}

fn dot(a: &P3, b: &P3) -> f64 {
    a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
}

fn cross(a: &P3, b: &P3) -> P3 {
    [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]
}

/// Circumcentre of a tetrahedron (doubles; for choosing points and ordering only).
fn circumcentre(p: [P3; 4]) -> Option<P3> {
    let (a, b, c) = (sub3(&p[1], &p[0]), sub3(&p[2], &p[0]), sub3(&p[3], &p[0]));
    let d = 2.0 * dot(&a, &cross(&b, &c));
    if d == 0.0 || !d.is_finite() {
        return None;
    }
    let (aa, bb, cc) = (dot(&a, &a), dot(&b, &b), dot(&c, &c));
    let (bc, ca, ab) = (cross(&b, &c), cross(&c, &a), cross(&a, &b));
    let o: P3 = std::array::from_fn(|k| p[0][k] + (aa * bc[k] + bb * ca[k] + cc * ab[k]) / d);
    o.iter().all(|x| x.is_finite()).then_some(o)
}

impl State<'_> {
    fn pt(&self, v: u32) -> Pt {
        self.g.view().from_id(v)
    }

    fn orient(&mut self, v: [u32; 4]) -> i8 {
        self.g.orient3d(v)
    }

    fn proj(&mut self, axis: usize, a: u32, b: u32, c: u32) -> i8 {
        let m = self.g.view();
        m.orient2d_proj(axis, [a, b, c].map(|i| m.from_id(i)), &mut self.n)
    }

    /// True when point p lies in the closed triangle f of facet `fi` (p in its plane).
    fn in_closed_face(&mut self, f: [u32; 3], fi: u32, p: u32) -> bool {
        if self.orient([f[0], f[1], f[2], p]) != 0 {
            return false;
        }
        let axis = self.frame[fi as usize].1;
        let s0 = self.proj(axis, f[0], f[1], f[2]);
        (0..3).all(|k| self.proj(axis, f[k], f[(k + 1) % 3], p) * s0 >= 0)
    }

    fn quality(&self, id: u32) -> Option<f64> {
        let hs = self.hsz[id as usize];
        if hs < 0.0 {
            return None; // a hole
        }
        let t = &self.cx.tets[id as usize];
        let p = t.map(|v| self.xyz[v as usize]);
        let c = circumcentre(p)?;
        let r = dot(&sub3(&c, &p[0]), &sub3(&c, &p[0])).sqrt();
        let mut lmin = f64::INFINITY;
        let mut short = (0, 1);
        for i in 0..4 {
            for j in i + 1..4 {
                let l = dot(&sub3(&p[i], &p[j]), &sub3(&p[i], &p[j])).sqrt();
                if l < lmin {
                    lmin = l;
                    short = (i, j);
                }
            }
        }
        let mut bad: f64 = 0.0;
        if self.opt.ratio > 0.0 {
            // small-angle rule (Shewchuk 1998 section 9): a tetrahedron that is bad only by its
            // radius-edge ratio is exempt when its circumcentre's insertion radius (its
            // circumradius) would be smaller than its parent's, the newer end of its shortest edge
            let parent = t[short.0].max(t[short.1]) as usize;
            if r >= self.rins[parent] && !self.seditious(t[short.0], t[short.1]) {
                bad = bad.max(r / lmin / self.opt.ratio);
            }
        }
        if hs > 0.0 {
            bad = bad.max(r / (self.opt.alpha * hs));
        }
        (bad > 1.0).then_some(bad)
    }

    /// Whether edge u-v is seditious (Shewchuk 2002, 2D): u and v are segment points on two
    /// segments that share an input endpoint z and meet there at less than 60 degrees, at the
    /// same distance from z (the concentric shells of `split_segment`). A tetrahedron whose
    /// shortest edge is seditious is skinny because of the input angle; splitting it would
    /// cascade towards z.
    fn seditious(&self, u: u32, v: u32) -> bool {
        let n = self.g.input.len();
        if (u as usize) < n || (v as usize) < n {
            return false;
        }
        let (su, sv) = (&self.g.s[u as usize - n], &self.g.s[v as usize - n]);
        if su.c != NONE || sv.c != NONE || su.a == NONE || sv.a == NONE {
            return false;
        }
        let (cu, cv) = ([su.a, su.b], [sv.a, sv.b]);
        let Some(&z) = cu.iter().find(|x| cv.contains(x)) else { return false };
        if cu.contains(&cv[0]) && cu.contains(&cv[1]) {
            return false; // the same segment
        }
        let other = |c: [u32; 2]| if c[0] == z { c[1] } else { c[0] };
        let pz = self.xyz[z as usize];
        let (du, dv) = (sub3(&self.xyz[u as usize], &pz), sub3(&self.xyz[v as usize], &pz));
        let (lu, lv) = (dot(&du, &du).sqrt(), dot(&dv, &dv).sqrt());
        if (lu - lv).abs() > 1e-6 * lu.max(lv) {
            return false;
        }
        let (eu, ev) = (sub3(&self.xyz[other(cu) as usize], &pz), sub3(&self.xyz[other(cv) as usize], &pz));
        dot(&eu, &ev) > 0.5 * dot(&eu, &eu).sqrt() * dot(&ev, &ev).sqrt()
    }

    fn queue_tet(&mut self, t: u32) {
        if !self.inside[t as usize] {
            return;
        }
        let v = self.cx.tets[t as usize];
        if let Some(bad) = self.quality(t) {
            let mut s = v;
            s.sort_unstable();
            self.tetq.push((bad.to_bits(), std::cmp::Reverse(s), t));
        } else if self.hsz[t as usize] > 0.0 {
            let d = self.min_dihedral(t);
            if d < DIHEDRAL_MIN {
                let mut s = v;
                s.sort_unstable();
                self.dihq.push((std::cmp::Reverse(d.to_bits()), std::cmp::Reverse(s), t));
            }
        }
    }

    /// M6 step 2: move volume vertices of the slivers left (deterministic directions:
    /// away from the opposite face, then towards the centroid of the vertex's star), keeping
    /// the connectivity; a move is kept only if every tetrahedron around the vertex stays
    /// positive (exact orient3d) and the smallest dihedral angle around it grows. Volume
    /// points are triples of doubles, so the moved point is exact. The mesh is no longer
    /// Delaunay there; it stays constrained (no constraint vertex moves).
    fn perturb_slivers(&mut self) {
        let n = self.g.input.len();
        for _round in 0..4 {
            let mut sl: Vec<([u32; 4], u32)> = (0..self.cx.tets.len() as u32)
                .filter(|&t| self.cx.alive[t as usize] && self.inside[t as usize] && self.hsz[t as usize] > 0.0
                    && self.min_dihedral(t) < DIHEDRAL_MIN)
                .map(|t| {
                    let mut k = self.cx.tets[t as usize];
                    k.sort_unstable();
                    (k, t)
                }).collect();
            sl.sort_unstable();
            let mut moved = 0;
            for (_, t) in sl {
                if !self.cx.alive[t as usize] || self.min_dihedral(t) >= DIHEDRAL_MIN {
                    continue;
                }
                let tv = self.cx.tets[t as usize];
                for (i, &v) in tv.iter().enumerate() {
                    if (v as usize) < n || self.g.s[v as usize - n].kind() != crate::mixed::Kind::Volume {
                        continue;
                    }
                    let star: Vec<u32> = self.cx.star[v as usize].iter().copied()
                        .filter(|&u| self.cx.alive[u as usize]).collect();
                    let base = star.iter().map(|&u| self.min_dihedral(u)).fold(180.0, f64::min);
                    let p0 = self.xyz[v as usize];
                    // away from the opposite face of t (raises its volume)
                    let o: Vec<P3> = (0..4).filter(|&j| j != i).map(|j| self.xyz[tv[j] as usize]).collect();
                    let nrm = cross(&sub3(&o[1], &o[0]), &sub3(&o[2], &o[0]));
                    let nn = dot(&nrm, &nrm).sqrt();
                    let side = dot(&nrm, &sub3(&p0, &o[0]));
                    let lmin = (0..4).flat_map(|a| (a + 1..4).map(move |b| (a, b)))
                        .map(|(a, b)| dot(&sub3(&self.xyz[tv[a] as usize], &self.xyz[tv[b] as usize]),
                                          &sub3(&self.xyz[tv[a] as usize], &self.xyz[tv[b] as usize])).sqrt())
                        .fold(f64::INFINITY, f64::min);
                    let mut cands: Vec<P3> = Vec::new();
                    if nn > 0.0 {
                        let u = nrm.map(|x| x / nn * side.signum());
                        for f in [0.5, 0.25, 0.1] {
                            cands.push(std::array::from_fn(|k| p0[k] + f * lmin * u[k]));
                        }
                    }
                    let mut cen = [0.0; 3];
                    let mut cnt = 0.0;
                    for &u in &star {
                        for &w in &self.cx.tets[u as usize] {
                            if w != v {
                                let q = self.xyz[w as usize];
                                for k in 0..3 {
                                    cen[k] += q[k];
                                }
                                cnt += 1.0;
                            }
                        }
                    }
                    if cnt > 0.0 {
                        for f in [1.0, 0.5, 0.25] {
                            cands.push(std::array::from_fn(|k| p0[k] + f * (cen[k] / cnt - p0[k])));
                        }
                    }
                    let mut done = false;
                    for c in cands {
                        if !c.iter().all(|x| x.is_finite()) {
                            continue;
                        }
                        self.set_volume_point(v, c);
                        let ok = star.iter().all(|&u| {
                            let w = self.cx.tets[u as usize];
                            self.orient(w) > 0
                        });
                        if ok && star.iter().map(|&u| self.min_dihedral(u)).fold(180.0, f64::min) > base + 1e-9 {
                            done = true;
                            break;
                        }
                        self.set_volume_point(v, p0);
                    }
                    if done {
                        moved += 1;
                        if self.min_dihedral(t) >= DIHEDRAL_MIN {
                            break;
                        }
                    }
                }
            }
            if moved == 0 {
                break;
            }
            self.stats.sliver_moves += moved;
        }
    }

    fn set_volume_point(&mut self, v: u32, p: P3) {
        let n = self.g.input.len();
        self.g.s[v as usize - n] = SPoint::vol(p);
        self.xyz[v as usize] = p;
    }

    /// The smallest dihedral angle of tetrahedron t, in degrees (doubles).
    fn min_dihedral(&self, t: u32) -> f64 {
        let x = self.cx.tets[t as usize].map(|v| self.xyz[v as usize]);
        let mut m = 180.0f64;
        for (i, j, k, l) in [(0, 1, 2, 3), (0, 2, 1, 3), (0, 3, 1, 2), (1, 2, 0, 3), (1, 3, 0, 2), (2, 3, 0, 1)] {
            let e = sub3(&x[j], &x[i]);
            let (n1, n2) = (cross(&e, &sub3(&x[k], &x[i])), cross(&e, &sub3(&x[l], &x[i])));
            let d = (dot(&n1, &n1) * dot(&n2, &n2)).sqrt();
            if d > 0.0 {
                m = m.min((dot(&n1, &n2) / d).clamp(-1.0, 1.0).acos().to_degrees());
            } else {
                return 0.0;
            }
        }
        m
    }

    /// A vertex in the diametral ball of subsegment e, among the vertices of its tetrahedra.
    fn segment_encroacher(&mut self, e: (u32, u32)) -> Option<u32> {
        let around: Vec<u32> = self.cx.star[e.0 as usize].iter().copied()
            .filter(|&t| self.cx.alive[t as usize] && self.inside[t as usize] && self.cx.tets[t as usize].contains(&e.1))
            .collect();
        let m = self.g.view();
        around.iter().flat_map(|&t| self.cx.tets[t as usize]).filter(|&w| w != e.0 && w != e.1)
            .find(|&w| m.in_diametral_ball(m.from_id(w), m.from_id(e.0), m.from_id(e.1)))
    }

    /// Small-angle rule for subsegments: e is exempt when half its length is below `parent`.
    /// Called with half the insertion radius a rejected point would have had: a point in e's
    /// diametral ball lies within e's length of an endpoint, so with that endpoint visible its
    /// insertion radius is below e's length; the rule fires only where the endpoint is hidden
    /// behind a constraint, near a small input angle, where splitting e would cascade.
    fn segment_exempt_r(&self, e: (u32, u32), parent: f64) -> bool {
        let d = sub3(&self.xyz[e.1 as usize], &self.xyz[e.0 as usize]);
        dot(&d, &d).sqrt() / 2.0 < parent
    }

    /// A vertex in the equatorial ball of subfacet f, among the apexes of its tetrahedra.
    fn encroacher(&mut self, f: [u32; 3]) -> Option<u32> {
        let o = self.cx.faces.get(&f).copied()?;
        let m = self.g.view();
        o.iter().filter(|&&t| t != NONE && self.inside[t as usize]).map(|&t| {
            *self.cx.tets[t as usize].iter().find(|x| !f.contains(x)).unwrap()
        }).find(|&w| m.equatorial_sign(m.from_id(w), m.from_id(f[0]), m.from_id(f[1]), m.from_id(f[2])) < 0)
    }

    /// Whether vertex w lies on a facet G that is none of subfacet f's facets and meets f's
    /// facet F at a dihedral angle below 60 degrees, measured at the line where their planes
    /// meet, between the half-plane of F holding f's centroid and the half-plane of G holding
    /// w. Such a vertex encroaches f only because the facets meet at a small angle; splitting
    /// f for it would grade the mesh towards their shared line without end, so f is left
    /// encroached (the triangulation is constrained and needs no conforming split).
    fn small_angle(&self, w: u32, f: &[u32; 3]) -> bool {
        let mine = &self.sub[f];
        let mut theirs: Vec<u32> = Vec::new();
        for &t in &self.cx.star[w as usize] {
            if !self.cx.alive[t as usize] {
                continue;
            }
            for i in 0..4 {
                let k = key(face(&self.cx.tets[t as usize], i));
                if let Some(l) = k.contains(&w).then(|| self.sub.get(&k)).flatten() {
                    if l.iter().any(|x| mine.contains(x)) {
                        return false;
                    }
                    theirs.extend(l.iter().copied());
                }
            }
        }
        self.angle_below_60(f, self.xyz[w as usize], &theirs)
    }

    fn angle_below_60(&self, f: &[u32; 3], pw: P3, theirs: &[u32]) -> bool {
        let mine = &self.sub[f];
        let plane = |fi: u32| -> (P3, f64) {
            let [a, b, c] = self.frame[fi as usize].0.map(|v| self.xyz[v as usize]);
            let n = cross(&sub3(&b, &a), &sub3(&c, &a));
            let l = dot(&n, &n).sqrt();
            let n = n.map(|x| x / l);
            (n, dot(&n, &a))
        };
        let x = f.map(|v| self.xyz[v as usize]);
        let cf: P3 = std::array::from_fn(|k| (x[0][k] + x[1][k] + x[2][k]) / 3.0);
        let (n1, d1) = plane(mine[0]);
        let mut theirs = theirs.to_vec();
        theirs.sort_unstable();
        theirs.dedup();
        theirs.iter().any(|&g| {
            let (n2, d2) = plane(g);
            let dir = cross(&n1, &n2);
            let dd = dot(&dir, &dir);
            if !(dd > 1e-12) {
                return false; // parallel planes
            }
            let (a, b) = (cross(&n2, &dir), cross(&dir, &n1));
            let pl: P3 = std::array::from_fn(|k| (d1 * a[k] + d2 * b[k]) / dd);
            let perp = |v: P3| -> P3 {
                let s = dot(&v, &dir) / dd;
                std::array::from_fn(|k| v[k] - s * dir[k])
            };
            let (uf, ug) = (perp(sub3(&cf, &pl)), perp(sub3(&pw, &pl)));
            let (lf, lg) = (dot(&uf, &uf).sqrt(), dot(&ug, &ug).sqrt());
            lf > 0.0 && lg > 0.0 && dot(&uf, &ug) > 0.5 * lf * lg
        })
    }

    /// Small-angle rule for subfacets: a subfacet encroached by a vertex w is exempt when its
    /// split point's insertion radius (the subfacet's circumradius) would be below w's
    /// insertion radius over sqrt 2. That happens only where features meet at a small angle
    /// (below about 45 degrees), where splitting would cascade.
    fn subfacet_exempt(&self, f: [u32; 3], w: u32) -> bool {
        self.subfacet_exempt_r(f, self.rins[w as usize])
    }

    /// The same rule against a given parent insertion radius: f's circumradius x sqrt 2 below it.
    fn subfacet_exempt_r(&self, f: [u32; 3], parent: f64) -> bool {
        let x = f.map(|v| self.xyz[v as usize]);
        let (a, b) = (sub3(&x[1], &x[0]), sub3(&x[2], &x[0]));
        let n = cross(&a, &b);
        let nn = dot(&n, &n);
        if !(nn > 0.0) {
            return false;
        }
        // circumradius of a triangle: |a||b||a-b| / (2 |a x b|)
        let c = sub3(&a, &b);
        let rc = (dot(&a, &a) * dot(&b, &b) * dot(&c, &c)).sqrt() / (2.0 * nn.sqrt());
        rc * std::f64::consts::SQRT_2 < parent
    }

    fn new_point(&mut self, sp: SPoint) -> u32 {
        let id = self.g.push(sp);
        let m = self.g.view();
        self.xyz.push(m.rounded(m.from_id(id)));
        self.rins.push(f64::INFINITY);
        self.cx.star.push(Vec::new());
        id
    }

    fn drop_point(&mut self, id: u32) {
        debug_assert_eq!(id as usize, self.xyz.len() - 1);
        self.g.s.pop();
        self.xyz.pop();
        self.rins.pop();
        self.cx.star.pop();
    }

    /// The 2D cavity of a point p on a facet: the subfacets of the facets of `start`
    /// (subfacets containing p) whose circumcircles contain p strictly (p is in their
    /// plane, so this is the exact equatorial-ball test), reached across subfacet edges
    /// that are not subsegments.
    fn plane_cavity(&mut self, p: u32, start: &[[u32; 3]]) -> Vec<[u32; 3]> {
        let mut set: Vec<[u32; 3]> = start.to_vec();
        set.sort_unstable();
        set.dedup();
        let mut i = 0;
        while i < set.len() {
            let f = set[i];
            let fl = self.sub[&f].clone();
            for j in 0..3 {
                let (x, y) = (f[j], f[(j + 1) % 3]);
                if self.seg.contains_key(&ekey(x, y)) {
                    continue;
                }
                let cand: Vec<[u32; 3]> = self.cx.star[x as usize].iter().filter(|&&t| self.cx.alive[t as usize])
                    .flat_map(|&t| (0..4).map(move |k| (t, k)))
                    .map(|(t, k)| key(face(&self.cx.tets[t as usize], k)))
                    .filter(|k| *k != f && k.contains(&x) && k.contains(&y) && self.sub.get(k).is_some_and(|l| *l == fl))
                    .collect();
                for k in cand {
                    if set.contains(&k) || self.orient([k[0], k[1], k[2], p]) != 0 {
                        continue;
                    }
                    let m = self.g.view();
                    if m.equatorial_sign(m.from_id(p), m.from_id(k[0]), m.from_id(k[1]), m.from_id(k[2])) < 0 {
                        set.push(k);
                    }
                }
            }
            i += 1;
        }
        set
    }

    /// The cavity of point p seeded by `seeds` (tetrahedra containing p in their
    /// closure): tetrahedra whose circumspheres contain p, reached across faces that are
    /// not subfacets, or across the subfacets of `plane` (p's 2D cavity).
    fn cavity(&mut self, p: u32, seeds: &[u32], plane: &[[u32; 3]]) -> Vec<u32> {
        let mut inc: HashMap<u32, ()> = HashMap::new();
        let mut list: Vec<u32> = Vec::new();
        let mut stack: Vec<u32> = Vec::new();
        // the tetrahedra on both sides of every subfacet the 2D cavity replaces belong to the
        // cavity whether or not the search below reaches them
        let mut all: Vec<u32> = seeds.to_vec();
        for k in plane {
            if let Some(o) = self.cx.faces.get(k) {
                all.extend(o.iter().copied().filter(|&t| t != NONE && self.inside[t as usize]));
            }
        }
        let seeds: &[u32] = &all;
        for &s in seeds {
            if inc.insert(s, ()).is_none() {
                list.push(s);
                stack.push(s);
            }
        }
        while let Some(t) = stack.pop() {
            let v = self.cx.tets[t as usize];
            for i in 0..4 {
                let k = key(face(&v, i));
                let u = self.cx.neighbor(t, &k);
                if u == NONE || inc.contains_key(&u) {
                    continue;
                }
                let take = if self.sub.contains_key(&k) {
                    plane.contains(&k)
                } else {
                    // only across a face that p sees from t's side: the cavity grows away from
                    // p and never around a constraint's edge to its far side
                    let f = face(&v, i);
                    let w = self.cx.tets[u as usize];
                    self.orient([f[0], f[1], f[2], p]) >= 0 && self.g.insphere_sos([w[0], w[1], w[2], w[3], p]) > 0
                };
                if take {
                    inc.insert(u, ());
                    list.push(u);
                    stack.push(u);
                }
            }
        }
        // Star-shaped from p: a boundary face that p does not see strictly (p in its plane,
        // e.g. on its circumcircle with the perturbation leaving it outside) would make a
        // flat or inverted tetrahedron. Grow the cavity across such faces while they are not
        // constraints; the insertion still checks every new tetrahedron.
        let mut grown = true;
        let mut rounds = 0;
        while grown && rounds < 64 {
            grown = false;
            rounds += 1;
            let mut add: Vec<u32> = Vec::new();
            for &t in &list {
                let v = self.cx.tets[t as usize];
                for i in 0..4 {
                    let f = face(&v, i);
                    let k = key(f);
                    if f.contains(&p) || plane.contains(&k) || self.sub.contains_key(&k) {
                        continue;
                    }
                    let u = self.cx.neighbor(t, &k);
                    if u == NONE || inc.contains_key(&u) || add.contains(&u) {
                        continue;
                    }
                    if self.orient([f[0], f[1], f[2], p]) <= 0 {
                        add.push(u);
                    }
                }
            }
            for u in add {
                inc.insert(u, ());
                list.push(u);
                grown = true;
            }
        }
        // Not around a constraint: where the cavity holds both sides of a subfacet outside
        // the 2D cavity, the side p does not lie on is hidden from p by that subfacet; drop it
        // and keep what the seeds still reach without it
        loop {
            let mut hidden: Vec<u32> = Vec::new();
            for &t in &list {
                let v = self.cx.tets[t as usize];
                for i in 0..4 {
                    let f = face(&v, i);
                    let k = key(f);
                    if !self.sub.contains_key(&k) || plane.contains(&k) || seeds.contains(&t) {
                        continue;
                    }
                    let u = self.cx.neighbor(t, &k);
                    if u == NONE || !inc.contains_key(&u) {
                        continue;
                    }
                    // f is wound inward for t: p strictly on the other side means t is hidden;
                    // p in f's plane (a coplanar subfacet across a subsegment, outside the 2D
                    // cavity) means both sides stay as they are
                    if self.orient([f[0], f[1], f[2], p]) <= 0 {
                        hidden.push(t);
                    }
                }
            }
            if hidden.is_empty() {
                break;
            }
            for t in &hidden {
                inc.remove(t);
            }
            let mut keep: HashMap<u32, ()> = HashMap::new();
            let mut st: Vec<u32> = seeds.iter().copied().filter(|t| inc.contains_key(t)).collect();
            for &t in &st {
                keep.insert(t, ());
            }
            while let Some(t) = st.pop() {
                let v = self.cx.tets[t as usize];
                for i in 0..4 {
                    let k = key(face(&v, i));
                    if self.sub.contains_key(&k) && !plane.contains(&k) {
                        continue;
                    }
                    let u = self.cx.neighbor(t, &k);
                    if u != NONE && inc.contains_key(&u) && !keep.contains_key(&u) {
                        keep.insert(u, ());
                        st.push(u);
                    }
                }
            }
            inc = keep;
            list.retain(|t| inc.contains_key(t));
        }
        // ... and shrink it where it cannot grow: a tetrahedron (not a seed, which holds p)
        // with a boundary face p does not see strictly leaves the cavity (e.g. p on the
        // hull's plane, beyond a coplanar hull face); repeat, since that exposes its other
        // faces. What remains is star-shaped from p unless a seed is blocked, which the
        // insertion then refuses.
        // tetrahedra on the subfacets the 2D cavity replaces stay (as seeds do): dropping one
        // would leave its old face open on that side of the facet
        let mut seedset: std::collections::HashSet<u32> = seeds.iter().copied().collect();
        for k in plane {
            if let Some(o) = self.cx.faces.get(k) {
                seedset.extend(o.iter().copied().filter(|&t| t != NONE && self.inside[t as usize] && inc.contains_key(&t)));
            }
        }
        loop {
            let mut drop: Vec<u32> = Vec::new();
            for &t in &list {
                if seedset.contains(&t) {
                    continue;
                }
                let v = self.cx.tets[t as usize];
                let blocked = (0..4).any(|i| {
                    let f = face(&v, i);
                    let k = key(f);
                    if f.contains(&p) || plane.contains(&k) {
                        return false;
                    }
                    let u = self.cx.neighbor(t, &k);
                    if u != NONE && inc.contains_key(&u) {
                        return false;
                    }
                    // after the growth above, only hull faces, constraints and faces of
                    // tetrahedra this loop removed can be left unseen
                    self.orient([f[0], f[1], f[2], p]) <= 0
                });
                if blocked {
                    drop.push(t);
                }
            }
            if drop.is_empty() {
                break;
            }
            for t in drop {
                inc.remove(&t);
            }
            list.retain(|t| inc.contains_key(t));
        }
        list.sort_unstable();
        list
    }

    /// Inserts p into its minimal cavity, when the Delaunay one is not star-shaped: the
    /// tetrahedra whose closed region holds p (found from `seeds`, which do), with the
    /// subfacets among their faces that p lies on as the 2D cavity. Every boundary face of
    /// that cavity is then seen by p (a face through p is shared by two of its tetrahedra,
    /// or is a hull face p splits), so the cone is valid; it is not Delaunay there, which
    /// later splits and flips may improve.
    fn insert_minimal(&mut self, p: u32, seeds: &[u32]) -> Result<bool, String> {
        self.stats.minimal += 1;
        let holds = |st: &mut Self, t: u32| {
            let v = st.cx.tets[t as usize];
            (0..4).all(|i| {
                let f = face(&v, i);
                st.orient([f[0], f[1], f[2], p]) >= 0
            })
        };
        let mut inc: std::collections::HashSet<u32> = std::collections::HashSet::new();
        let mut stack: Vec<u32> = Vec::new();
        for &s in seeds {
            if self.cx.alive[s as usize] && holds(self, s) && inc.insert(s) {
                stack.push(s);
            }
        }
        while let Some(t) = stack.pop() {
            let v = self.cx.tets[t as usize];
            for i in 0..4 {
                let f = face(&v, i);
                if self.orient([f[0], f[1], f[2], p]) != 0 {
                    continue; // p is not on this face: its neighbour does not hold p
                }
                let u = self.cx.neighbor(t, &key(f));
                if u != NONE && !inc.contains(&u) && holds(self, u) {
                    inc.insert(u);
                    stack.push(u);
                }
            }
        }
        let mut cav: Vec<u32> = inc.iter().copied().collect();
        cav.sort_unstable();
        let mut plane: Vec<[u32; 3]> = Vec::new();
        for &t in &cav {
            let v = self.cx.tets[t as usize];
            for i in 0..4 {
                let f = face(&v, i);
                let k = key(f);
                if self.sub.contains_key(&k) && !plane.contains(&k) && self.orient([f[0], f[1], f[2], p]) == 0 {
                    plane.push(k);
                }
            }
        }
        plane.sort_unstable();
        self.insert(p, &cav, &plane)
    }

    /// The constraint faces and edges on the boundary of a cavity that p encroaches.
    fn encroached_by(&mut self, p: u32, cav: &[u32]) -> (Vec<[u32; 3]>, Vec<(u32, u32)>) {
        let set: std::collections::HashSet<u32> = cav.iter().copied().collect();
        let (mut fs, mut es) = (Vec::new(), Vec::new());
        let m = self.g.view();
        for &t in cav {
            let v = self.cx.tets[t as usize];
            for i in 0..4 {
                let f = face(&v, i);
                let k = key(f);
                let u = self.cx.neighbor(t, &k);
                if u != NONE && set.contains(&u) {
                    if self.sub.contains_key(&k) {
                        fs.push(k); // a subfacet with the cavity on both sides: p would swallow it
                    }
                    continue;
                }
                if self.sub.contains_key(&k) && m.equatorial_sign(m.from_id(p), m.from_id(k[0]), m.from_id(k[1]), m.from_id(k[2])) < 0 {
                    fs.push(k);
                }
                for j in 0..3 {
                    let e = ekey(k[j], k[(j + 1) % 3]);
                    if self.seg.contains_key(&e) && m.in_diametral_ball(m.from_id(p), m.from_id(e.0), m.from_id(e.1)) {
                        es.push(e);
                    }
                }
            }
        }
        fs.sort_unstable();
        fs.dedup();
        es.sort_unstable();
        es.dedup();
        (fs, es)
    }

    /// Replaces the cavity by the tetrahedra joining p to its boundary faces, and the
    /// 2D cavity `plane` by the triangles joining p to its boundary edges. Returns false,
    /// changing nothing, when a new tetrahedron would not be positive.
    fn insert(&mut self, p: u32, cav: &[u32], plane: &[[u32; 3]]) -> Result<bool, String> {
        let set: std::collections::HashSet<u32> = cav.iter().copied().collect();
        let mut new = Vec::new();
        let mut touched: Vec<[u32; 3]> = Vec::new();
        for &t in cav {
            let v = self.cx.tets[t as usize];
            let label = (self.inside[t as usize], self.hsz[t as usize]);
            for i in 0..4 {
                let f = face(&v, i);
                let k = key(f);
                if plane.contains(&k) {
                    continue;
                }
                if self.sub.contains_key(&k) {
                    touched.push(k);
                }
                let u = self.cx.neighbor(t, &k);
                if u != NONE && set.contains(&u) {
                    continue;
                }
                if f.contains(&p) {
                    continue;
                }
                let tet = [f[0], f[1], f[2], p];
                let o = self.orient(tet);
                if o == 0 && u == NONE && (0..3).any(|j| self.g.collinear(f[j], f[(j + 1) % 3], p)) {
                    // a hull face with p on one of its edges (the subsegment p splits): p splits
                    // it into two hull faces, which are faces of the tetrahedra joining p to the
                    // neighbouring boundary faces; it is not joined to p itself
                    continue;
                }
                if o <= 0 {
                    return Ok(false);
                }
                new.push((tet, label));
            }
        }
        // Before changing anything: every boundary edge (x, y) of the 2D cavity that is not
        // collinear with p must become a face [x, y, p] of a new tetrahedron, or the split
        // subfacets would not be faces. Refuse (changing nothing) if one does not, so that the
        // caller can fall back to the minimal cavity.
        {
            let made: std::collections::HashSet<[u32; 3]> = new.iter()
                .flat_map(|(tet, _): &([u32; 4], (bool, f64))| (0..4).map(move |i| key(face(tet, i))))
                .filter(|k| k.contains(&p)).collect();
            let mut ec: HashMap<(u32, u32), u32> = HashMap::new();
            for k in plane {
                for j in 0..3 {
                    *ec.entry(ekey(k[j], k[(j + 1) % 3])).or_default() += 1;
                }
            }
            let mut bad: Vec<(u32, u32)> = ec.into_iter().filter(|(_, c)| *c == 1).map(|(e, _)| e)
                .filter(|e| !made.contains(&key([e.0, e.1, p]))).collect();
            bad.retain(|e| !self.g.collinear(e.0, e.1, p));
            // a constraint the cavity would swallow: a subfacet outside the 2D cavity with
            // tetrahedra of the cavity on both sides (the cavity can reach its other side
            // around the facet's edge), or a subsegment that is no edge of a new tetrahedron
            // and that p does not split
            let swallowed_face = cav.iter().any(|&t| {
                let v = self.cx.tets[t as usize];
                (0..4).any(|i| {
                    let k = key(face(&v, i));
                    if !self.sub.contains_key(&k) || plane.contains(&k) {
                        return false;
                    }
                    let u = self.cx.neighbor(t, &k);
                    u != NONE && set.contains(&u)
                })
            });
            let new_edges: std::collections::HashSet<(u32, u32)> = new.iter()
                .flat_map(|(tet, _): &([u32; 4], (bool, f64))| (0..4).flat_map(move |k| (k + 1..4).map(move |l| ekey(tet[k], tet[l]))))
                .collect();
            let swallowed_edge = cav.iter().any(|&t| {
                let v = self.cx.tets[t as usize];
                (0..4).any(|k| (k + 1..4).any(|l| {
                    let e = ekey(v[k], v[l]);
                    self.seg.contains_key(&e) && !new_edges.contains(&e) && !self.g.collinear(e.0, e.1, p)
                }))
            });
            // every tetrahedron on a subfacet the 2D cavity replaces must be in the cavity,
            // or its old face would be left open (the cavity shrank on one side of the facet)
            let one_sided = plane.iter().any(|k| self.cx.faces.get(k).is_some_and(|o| o.iter().any(|&t| t != NONE && self.inside[t as usize] && !set.contains(&t))));
            if swallowed_face || swallowed_edge || one_sided {
                return Ok(false);
            }
            if !bad.is_empty() {
                return Ok(false);
            }
        }
        let split_faces: Vec<([u32; 3], Vec<u32>)> = plane.iter().map(|k| (*k, self.sub[k].clone())).collect();
        for &t in cav {
            self.cx.remove(t);
        }
        // p's insertion radius: its distance to the nearest vertex it is joined to
        let pp = self.xyz[p as usize];
        self.rins[p as usize] = new.iter().flat_map(|(tet, _)| tet.iter().copied()).filter(|&v| v != p)
            .map(|v| dot(&sub3(&self.xyz[v as usize], &pp), &sub3(&self.xyz[v as usize], &pp)).sqrt())
            .fold(f64::INFINITY, f64::min);
        let mut added = Vec::with_capacity(new.len());
        for (tet, label) in new {
            let id = self.cx.add(tet);
            if id as usize >= self.inside.len() {
                self.inside.resize(id as usize + 1, false);
                self.hsz.resize(id as usize + 1, 0.0);
            }
            self.inside[id as usize] = label.0;
            self.hsz[id as usize] = label.1;
            added.push(id);
        }
        // subsegments containing p: the S point's segment piece
        let edges: Vec<(u32, u32)> = split_faces.iter()
            .flat_map(|(k, _)| [(k[0], k[1]), (k[1], k[2]), (k[0], k[2])])
            .map(|(a, b)| ekey(a, b)).filter(|e| self.seg.contains_key(e)).collect();
        for e in edges {
            if self.g.collinear(e.0, e.1, p) {
                if let Some(c) = self.seg.remove(&e) {
                    let chain = &mut self.chains[c as usize];
                    let i = chain.windows(2).position(|w| ekey(w[0], w[1]) == e).unwrap();
                    chain.insert(i + 1, p);
                    for e2 in [ekey(e.0, p), ekey(p, e.1)] {
                        self.seg.insert(e2, c);
                        self.segq.push_back(e2);
                    }
                }
            }
        }
        // a lone subsegment (no subfacet through it) containing p
        if self.g.s[(p as usize) - self.g.input.len()].kind() == crate::mixed::Kind::Segment {
            let sp = self.g.s[(p as usize) - self.g.input.len()];
            let lone: Vec<(u32, u32)> = self.seg.keys().copied()
                .filter(|e| {
                    let c = &self.chains[self.seg[e] as usize];
                    (c[0] == sp.a && c[c.len() - 1] == sp.b) || (c[0] == sp.b && c[c.len() - 1] == sp.a)
                })
                .filter(|e| e.0 != p && e.1 != p).collect();
            for e in lone {
                if self.g.collinear(e.0, e.1, p) && self.g.view().dot_sign(self.pt(p), self.pt(e.0), self.pt(e.1)) < 0 {
                    let c = self.seg.remove(&e).unwrap();
                    let chain = &mut self.chains[c as usize];
                    let i = chain.windows(2).position(|w| ekey(w[0], w[1]) == e).unwrap();
                    chain.insert(i + 1, p);
                    for e2 in [ekey(e.0, p), ekey(p, e.1)] {
                        self.seg.insert(e2, c);
                        self.segq.push_back(e2);
                    }
                }
            }
        }
        // the 2D cavity: its boundary edges joined to p, per facet list
        let mut ecount: HashMap<(u32, u32), (u32, Vec<u32>)> = HashMap::new();
        for (k, fl) in &split_faces {
            self.sub.remove(k);
            for j in 0..3 {
                let e = ekey(k[j], k[(j + 1) % 3]);
                ecount.entry(e).or_insert((0, fl.clone())).0 += 1;
            }
        }
        let mut bnd: Vec<((u32, u32), Vec<u32>)> = ecount.into_iter().filter(|(_, (c, _))| *c == 1)
            .map(|(e, (_, fl))| (e, fl)).collect();
        bnd.sort_unstable();
        for ((x, y), fl) in bnd {
            if self.g.collinear(x, y, p) {
                continue;
            }
            let nk = key([x, y, p]);
            if !self.cx.faces.contains_key(&nk) {
                return Err(format!("refinement: the split subfacet {nk:?} is not a face"));
            }
            self.sub.insert(nk, fl);
            self.subq.push_back(nk);
        }
        for k in touched {
            self.subq.push_back(k);
        }
        for id in added {
            let v = self.cx.tets[id as usize];
            for i in 0..4 {
                let k = key(face(&v, i));
                for j in 0..3 {
                    let e = ekey(k[j], k[(j + 1) % 3]);
                    if self.seg.contains_key(&e) {
                        self.segq.push_back(e);
                    }
                }
                if self.sub.contains_key(&k) {
                    self.subq.push_back(k);
                }
            }
            self.queue_tet(id);
        }
        if self.g.s.len() > self.opt.max_points {
            let s = &self.stats;
            return Err(format!("refinement inserted more than {} points (segment {}, facet {}, volume {}; rejected {}, \
                                minimal cavities {}, exempt subsegments {}, exempt subfacets {})", self.opt.max_points,
                               s.segment_points, s.facet_points, s.volume_points, s.rejected, s.minimal, s.exempt,
                               s.exempt_faces));
        }
        Ok(true)
    }

    fn split_segment(&mut self, e: (u32, u32)) -> Result<(), String> {
        let c = self.seg[&e];
        let chain = &self.chains[c as usize];
        let (a, b) = (chain[0], chain[chain.len() - 1]);
        let t_of = |v: u32, st: &Self| -> f64 {
            if v == a { 0.0 } else if v == b { 1.0 } else { st.g.s[v as usize - st.g.input.len()].t }
        };
        let (tu, tv) = (t_of(e.0, self), t_of(e.1, self));
        let mut tm = tu + (tv - tu) / 2.0;
        // concentric shells (Ruppert 1995; Shewchuk 2002, section 4): a subsegment with exactly
        // one input endpoint splits at the power-of-two distance from that endpoint nearest its
        // midpoint, so that subsegments meeting at a small input angle split at equal radii and
        // stop encroaching each other
        let apex = |v: u32| (v == a || v == b) && self.small_apex[v as usize];
        let (ia, ib) = (apex(e.0), apex(e.1));
        if ia != ib {
            let d = sub3(&self.xyz[b as usize], &self.xyz[a as usize]);
            let len = dot(&d, &d).sqrt();
            let (t0, t1) = if ia { (tu, tv) } else { (tv, tu) };
            let half = (t1 - t0).abs() * len / 2.0;
            if len > 0.0 && half > 0.0 {
                let r = 2f64.powf((half.log2()).round());
                let tr = t0 + (t1 - t0).signum() * r / len;
                if (tr - t0).abs() > (t1 - t0).abs() / 3.0 && (tr - t0).abs() < 2.0 * (t1 - t0).abs() / 3.0 {
                    tm = tr;
                }
            }
        }
        if !(tm > tu.min(tv) && tm < tu.max(tv)) {
            // a subsegment that doubles cannot split (a cascade at a small input angle): left as
            // it is and counted
            self.stats.exempt += 1;
            return Ok(());
        }
        let p = self.new_point(SPoint::seg(a, b, tm));
        let seeds: Vec<u32> = self.cx.star[e.0 as usize].iter().copied()
            .filter(|&t| self.cx.alive[t as usize] && self.cx.tets[t as usize].contains(&e.1)).collect();
        let start: Vec<[u32; 3]> = seeds.iter().flat_map(|&t| (0..4).map(move |i| (t, i)))
            .map(|(t, i)| key(face(&self.cx.tets[t as usize], i)))
            .filter(|k| k.contains(&e.0) && k.contains(&e.1) && self.sub.contains_key(k)).collect();
        let plane = self.plane_cavity(p, &start);
        let cav = self.cavity(p, &seeds, &plane);
        if !self.insert(p, &cav, &plane)? && !self.insert_minimal(p, &seeds)? {
            self.drop_point(p);
            return Err(format!("refinement: the cavity of segment point {p} is not star-shaped"));
        }
        self.stats.segment_points += 1;
        Ok(())
    }

    /// Splits subfacet f at its circumcentre, or what that point encroaches. A subfacet
    /// already being split further up this chain (two facets whose circumcentres encroach
    /// each other) is left as it is and counted, so the chain ends.
    fn split_subfacet(&mut self, f: [u32; 3]) -> Result<(), String> {
        if self.splitting.contains(&f) || self.splitting.len() >= 64 {
            self.stats.exempt_faces += 1;
            return Ok(());
        }
        self.splitting.push(f);
        let r = self.split_subfacet_at(f);
        self.splitting.pop();
        r
    }

    fn split_subfacet_at(&mut self, f: [u32; 3]) -> Result<(), String> {
        let fi = self.sub[&f][0];
        let ([a, b, c], _axis) = self.frame[fi as usize];
        let x = f.map(|v| self.xyz[v as usize]);
        // circumcentre of the triangle in its plane
        let (u, w) = (sub3(&x[1], &x[0]), sub3(&x[2], &x[0]));
        let nrm = cross(&u, &w);
        let nn = dot(&nrm, &nrm);
        if nn == 0.0 {
            return Err(format!("refinement: subfacet {f:?} is degenerate in doubles"));
        }
        let (wn, nu) = (cross(&w, &nrm), cross(&nrm, &u));
        let o: P3 = std::array::from_fn(|k| x[0][k] + (dot(&u, &u) * wn[k] + dot(&w, &w) * nu[k]) / (2.0 * nn));
        // the circumcentre as a + s (b - a) + r (c - a), least squares in doubles
        let (pa, pb, pc) = (self.xyz[a as usize], self.xyz[b as usize], self.xyz[c as usize]);
        let (e1, e2, d) = (sub3(&pb, &pa), sub3(&pc, &pa), sub3(&o, &pa));
        let (g11, g12, g22) = (dot(&e1, &e1), dot(&e1, &e2), dot(&e2, &e2));
        let (r1, r2) = (dot(&e1, &d), dot(&e2, &d));
        let det = g11 * g22 - g12 * g12;
        let (s, r) = ((r1 * g22 - r2 * g12) / det, (g11 * r2 - g12 * r1) / det);
        if !(s.is_finite() && r.is_finite()) {
            return Err(format!("refinement: no frame for facet {fi}"));
        }
        let p = self.new_point(SPoint::fac(a, b, c, s, r));
        // walk across the facet's subfacets to the one holding p
        let mut cur = f;
        let mut steps = 0;
        loop {
            steps += 1;
            if steps > 10_000 {
                self.drop_point(p);
                return Err("refinement: the walk on a facet did not end".into());
            }
            if self.in_closed_face(cur, fi, p) {
                break;
            }
            let axis = self.frame[fi as usize].1;
            let s0 = self.proj(axis, cur[0], cur[1], cur[2]);
            let j = (0..3).find(|&j| self.proj(axis, cur[j], cur[(j + 1) % 3], p) * s0 < 0).unwrap();
            let (ex, ey) = (cur[j], cur[(j + 1) % 3]);
            if self.seg.contains_key(&ekey(ex, ey)) {
                // beyond a subsegment of the facet: split the subsegment instead if p
                // encroaches it; otherwise f's circumcentre lies outside the facet past a
                // subsegment it does not encroach (the facet's triangulation is constrained,
                // not Delaunay), and splitting that subsegment would not change f: leave f
                let (ex, ey) = ekey(ex, ey);
                let enc = {
                    let m = self.g.view();
                    m.in_diametral_ball(m.from_id(p), m.from_id(ex), m.from_id(ey))
                };
                // ... or the subsegment is longer than f's circumradius, so splitting it still
                // refines at f's scale (a halving cascade towards a corner never does)
                let d = sub3(&self.xyz[ey as usize], &self.xyz[ex as usize]);
                let rc = dot(&sub3(&o, &x[0]), &sub3(&o, &x[0])).sqrt();
                let enc = enc || dot(&d, &d).sqrt() > rc;
                self.drop_point(p);
                self.stats.rejected += 1;
                if enc {
                    return self.split_segment((ex, ey));
                }
                self.stats.exempt_faces += 1;
                return Ok(());
            }
            let next = self.cx.star[ex as usize].iter().filter(|&&t| self.cx.alive[t as usize])
                .flat_map(|&t| (0..4).map(move |i| (t, i)))
                .map(|(t, i)| key(face(&self.cx.tets[t as usize], i)))
                .find(|k| *k != cur && k.contains(&ex) && k.contains(&ey) && self.sub.get(k).is_some_and(|l| l.contains(&fi)));
            match next {
                Some(k) => cur = k,
                None => {
                    self.drop_point(p);
                    return Err(format!("refinement: facet {fi} has no subfacet across {ex}-{ey}"));
                }
            }
        }
        if cur.iter().any(|&v| self.xyz[v as usize] == self.xyz[p as usize]) {
            // the circumcentre is (in doubles) a vertex already: an earlier split at the same
            // point could not remove f
            self.drop_point(p);
            self.stats.exempt_faces += 1;
            return Ok(());
        }
        let plane = self.plane_cavity(p, &[cur]);
        let seeds: Vec<u32> = plane.iter().flat_map(|k| self.cx.faces[k]).filter(|&t| t != NONE).collect();
        let cav = self.cavity(p, &seeds, &plane);
        let (_, es) = self.encroached_by(p, &cav);
        if let Some(&e) = es.first() {
            self.drop_point(p);
            self.stats.rejected += 1;
            let rc = dot(&sub3(&o, &x[0]), &sub3(&o, &x[0])).sqrt();
            if self.segment_exempt_r(e, rc / 2.0) {
                // a facet point that encroaches a subsegment of an adjacent feature at a small
                // angle: leave both
                self.stats.exempt_faces += 1;
                return Ok(());
            }
            return self.split_segment(e);
        }
        if !self.insert(p, &cav, &plane)? && !self.insert_minimal(p, &seeds)? {
            self.drop_point(p);
            self.stats.rejected += 1;
            return Err(format!("refinement: the cavity of facet point {p} is not star-shaped"));
        }
        self.stats.facet_points += 1;
        Ok(())
    }

    /// Splits a bad tetrahedron at its circumcentre, unless the point is rejected.
    fn split_tet(&mut self, t: u32) -> Result<(), String> {
        let v = self.cx.tets[t as usize];
        let Some(c) = circumcentre(v.map(|x| self.xyz[x as usize])) else { return Ok(()) };
        let rt = dot(&sub3(&c, &self.xyz[v[0] as usize]), &sub3(&c, &self.xyz[v[0] as usize])).sqrt();
        let p = self.new_point(SPoint::vol(c));
        // walk from t to the tetrahedron holding p
        let mut cur = t;
        let mut steps = 0;
        let found = loop {
            steps += 1;
            if steps > 100_000 {
                self.drop_point(p);
                return Err("refinement: the walk to a circumcentre did not end".into());
            }
            let w = self.cx.tets[cur as usize];
            let mut moved = false;
            for i in 0..4 {
                let f = face(&w, i);
                if self.orient([f[0], f[1], f[2], p]) < 0 {
                    let k = key(f);
                    let u = self.cx.neighbor(cur, &k);
                    if self.sub.contains_key(&k) || u == NONE || !self.inside[u as usize] {
                        // beyond a subfacet: split it instead
                        self.drop_point(p);
                        self.stats.rejected += 1;
                        if self.sub.contains_key(&k) {
                            // the circumcentre lies beyond a subfacet it need not encroach (a
                            // constrained triangulation): near a small angle a large circumradius
                            // meets a small subfacet, and splitting it would cascade; leave both
                            if self.subfacet_exempt_r(k, rt) || v.iter().any(|&x| self.small_angle(x, &k)) {
                                self.stats.exempt_faces += 1;
                                return Ok(());
                            }
                            return self.split_subfacet(k);
                        }
                        return Ok(());
                    }
                    cur = u;
                    moved = true;
                    break;
                }
            }
            if !moved {
                break cur;
            }
        };
        // a circumcentre on a subfacet: split the subfacet instead
        let w = self.cx.tets[found as usize];
        if w.iter().any(|&x| self.xyz[x as usize] == self.xyz[p as usize]) {
            // the circumcentre is (in doubles) a vertex already: t survived an earlier
            // insertion of the same point; leave it
            self.drop_point(p);
            self.stats.rejected += 1;
            return Ok(());
        }
        for i in 0..4 {
            let k = key(face(&w, i));
            if let Some(fi) = self.sub.get(&k).map(|l| l[0]) {
                if self.in_closed_face(k, fi, p) {
                    self.drop_point(p);
                    self.stats.rejected += 1;
                    return self.split_subfacet(k);
                }
            }
        }
        let cav = self.cavity(p, &[found], &[]);
        let (fs, es) = self.encroached_by(p, &cav);
        if !fs.is_empty() || !es.is_empty() {
            // the circumcentre encroaches: split what it encroaches (subsegments first)
            self.drop_point(p);
            self.stats.rejected += 1;
            if let Some(&e) = es.first() {
                if self.segment_exempt_r(e, rt / 2.0) {
                    self.stats.exempt += 1;
                    return Ok(());
                }
                return self.split_segment(e);
            }
            if self.subfacet_exempt_r(fs[0], rt / std::f64::consts::SQRT_2) || v.iter().any(|&x| self.small_angle(x, &fs[0])) {
                self.stats.exempt_faces += 1;
                return Ok(());
            }
            return self.split_subfacet(fs[0]);
        }
        if !self.insert(p, &cav, &[])? && !self.insert_minimal(p, &[found])? {
            self.drop_point(p);
            self.stats.rejected += 1;
            return Ok(());
        }
        self.stats.volume_points += 1;
        Ok(())
    }
}

/// Refines the result of boundary recovery in place: its tetrahedra, Steiner points,
/// subfacets and segment chains change; every other tetrahedron of the convex hull is
/// kept.
/// `seeds` and `label_h` (regions mode): the region seeds of `mesh::build` and a size per
/// seed label; a component holding a seed with label L is refined to `label_h[L]` (the
/// smallest if several seeds name it; `opt.h` where `label_h[L]` is not positive), a hole
/// (label < 0) is not refined for quality or size, and every other component to `opt.h`.
/// A seed that `mesh::build` would refuse is refused here with the same message.
pub fn refine(plc: &crate::plc::Plc, b: &mut Boundary, opt: RefineOptions, seeds: &[crate::mesh::Seed],
              label_h: &[f64]) -> Result<RefineStats, String> {
    let mut g = MixedPoints::new(plc.points.clone());
    for s in &b.plc.rec.s {
        g.push(*s);
    }
    let total = g.len();
    let cx = Complex::new(total, &b.tets);
    let m = g.view();
    let xyz: Vec<P3> = (0..total as u32).map(|v| m.rounded(m.from_id(v))).collect();
    let mut sub = HashMap::new();
    for (fi, tris) in b.plc.subfacets.iter().enumerate() {
        for t in tris {
            sub.entry(key(*t)).or_insert_with(Vec::new).push(fi as u32);
        }
    }
    let mut seg = HashMap::new();
    for (c, chain) in b.plc.rec.chains.iter().enumerate() {
        for w in chain.windows(2) {
            seg.insert(ekey(w[0], w[1]), c as u32);
        }
    }
    // per facet: three non-collinear input points of its outer loop and an axis
    let mut frame = Vec::with_capacity(plc.facets.len());
    for (fi, loops) in plc.facets.iter().enumerate() {
        let lp = &loops[0];
        let mut f = None;
        'search: for i in 0..lp.len() {
            for j in i + 1..lp.len() {
                for k in j + 1..lp.len() {
                    if !g.collinear(lp[i], lp[j], lp[k]) {
                        f = Some([lp[i], lp[j], lp[k]]);
                        break 'search;
                    }
                }
            }
        }
        let f = f.ok_or_else(|| format!("facet {fi} has no three non-collinear points"))?;
        let mut n = MixedCounters::default();
        let axis = (0..3).find(|&a| m.orient2d_proj(a, f.map(|i| m.from_id(i)), &mut n) != 0).unwrap();
        frame.push((f, axis));
    }
    // the domain: components across faces that are not subfacets; outside where a
    // component reaches a hull face that is not a subfacet
    let mut comp = vec![NONE; cx.tets.len()];
    let mut outside = Vec::new();
    for s in 0..cx.tets.len() {
        if comp[s] != NONE {
            continue;
        }
        let c = outside.len() as u32;
        outside.push(false);
        comp[s] = c;
        let mut stack = vec![s as u32];
        while let Some(t) = stack.pop() {
            let v = cx.tets[t as usize];
            for i in 0..4 {
                let k = key(face(&v, i));
                if sub.contains_key(&k) {
                    continue;
                }
                let u = cx.neighbor(t, &k);
                if u == NONE {
                    outside[c as usize] = true;
                } else if comp[u as usize] == NONE {
                    comp[u as usize] = c;
                    stack.push(u);
                }
            }
        }
    }
    let inside: Vec<bool> = comp.iter().map(|&c| !outside[c as usize]).collect();
    // the size of each component: opt.h, or its seeds' (regions mode)
    let mut comp_h = vec![opt.h; outside.len()];
    if !seeds.is_empty() {
        let at = crate::mesh::locate_seeds(&plc.points, b, &comp, &outside, seeds)?;
        let mut set = vec![false; outside.len()];
        for (sd, &c) in seeds.iter().zip(&at) {
            let c = c as usize;
            let h = if sd.label < 0 {
                -1.0
            } else {
                label_h.get(sd.label as usize).copied().filter(|h| *h > 0.0).unwrap_or(opt.h)
            };
            // a hole stays a hole (build refuses a hole and a name together); else the smallest
            comp_h[c] = if !set[c] || h < 0.0 { h } else if comp_h[c] < 0.0 { comp_h[c] } else { comp_h[c].min(h) };
            set[c] = true;
        }
    }
    let hsz: Vec<f64> = comp.iter().map(|&c| comp_h[c as usize]).collect();
    let hmin = comp_h.iter().copied().filter(|h| *h > 0.0).fold(f64::INFINITY, f64::min);
    let mut rins = vec![f64::INFINITY; xyz.len()];
    for (t, v) in cx.tets.iter().enumerate() {
        if !cx.alive[t] {
            continue;
        }
        for i in 0..4 {
            for j in i + 1..4 {
                let (a, b) = (v[i] as usize, v[j] as usize);
                let d = dot(&sub3(&xyz[a], &xyz[b]), &sub3(&xyz[a], &xyz[b])).sqrt();
                rins[a] = rins[a].min(d);
                rins[b] = rins[b].min(d);
            }
        }
    }
    // the point cap (the M5 stop rule: a typed error, never a hang): given, or derived from
    // the size field, 20 x (volume inside / h^3) + 200 x (facet area / h^2) + 100 x (vertices at
    // the start), at least 1000 (boundary points scale with area, so thin layers need the area
    // term); with no size field, 100 x the vertices at the start; with a ratio bound, plus
    // 200 x (facet area / shortest input edge^2); at most 5,000,000
    let mut opt = opt;
    if opt.max_points == 0 {
        let vol: f64 = cx.tets.iter().enumerate().filter(|(t, _)| cx.alive[*t] && inside[*t]).map(|(_, v)| {
            let q = v.map(|i| xyz[i as usize]);
            let (a, b, c) = (sub3(&q[1], &q[0]), sub3(&q[2], &q[0]), sub3(&q[3], &q[0]));
            (dot(&a, &cross(&b, &c)) / 6.0).abs()
        }).sum();
        let area: f64 = sub.keys().map(|k| {
            let (a, b) = (sub3(&xyz[k[1] as usize], &xyz[k[0] as usize]), sub3(&xyz[k[2] as usize], &xyz[k[0] as usize]));
            let c = cross(&a, &b);
            dot(&c, &c).sqrt() / 2.0
        }).sum();
        let n0 = xyz.len() as f64;
        let mut est = if hmin.is_finite() {
            20.0 * vol / hmin.powi(3) + 200.0 * area / hmin.powi(2) + 100.0 * n0
        } else {
            100.0 * n0
        };
        if opt.ratio > 0.0 {
            // the ratio bound grades the mesh down to the input's shortest edge, whatever h is:
            // the area term again at that edge length
            let lmin = rins.iter().copied().filter(|r| r.is_finite() && *r > 0.0).fold(f64::INFINITY, f64::min);
            if lmin.is_finite() {
                est += 200.0 * area / (lmin * lmin);
            }
        }
        opt.max_points = (est.min(5.0e6) as usize).max(1000);
    }
    // input vertices where two segments meet at less than 60 degrees: the apexes of the
    // concentric shells of split_segment
    let mut small_apex = vec![false; xyz.len()];
    {
        let mut dirs: HashMap<u32, Vec<P3>> = HashMap::new();
        for ch in &b.plc.rec.chains {
            let (a, z) = (ch[0], ch[ch.len() - 1]);
            if a == z {
                continue;
            }
            let d = sub3(&xyz[z as usize], &xyz[a as usize]);
            dirs.entry(a).or_default().push(d);
            dirs.entry(z).or_default().push(d.map(|x| -x));
        }
        for (v, ds) in dirs {
            let small = ds.iter().enumerate().any(|(i, u)| ds[i + 1..].iter().any(|w| {
                dot(u, w) > 0.5 * dot(u, u).sqrt() * dot(w, w).sqrt()
            }));
            small_apex[v as usize] = small;
        }
    }
    let mut st = State {
        g, cx, xyz, rins, inside, hsz, sub, seg, chains: b.plc.rec.chains.clone(), small_apex, splitting: Vec::new(), frame, opt, stats: RefineStats::default(),
        segq: VecDeque::new(), subq: VecDeque::new(), tetq: BinaryHeap::new(), dihq: BinaryHeap::new(), n: MixedCounters::default(),
        _p: std::marker::PhantomData,
    };
    let mut keys: Vec<(u32, u32)> = st.seg.keys().copied().collect();
    keys.sort_unstable();
    st.segq.extend(keys);
    let mut fkeys: Vec<[u32; 3]> = st.sub.keys().copied().collect();
    fkeys.sort_unstable();
    st.subq.extend(fkeys);
    for t in 0..st.cx.tets.len() as u32 {
        st.queue_tet(t);
    }
    let mut sliver_budget: Option<u32> = None;
    loop {
        if let Some(e) = st.segq.pop_front() {
            if st.seg.contains_key(&e) {
                if st.segment_encroacher(e).is_some() {
                    st.split_segment(e)?;
                }
            }
            continue;
        }
        if let Some(f) = st.subq.pop_front() {
            if st.sub.contains_key(&f) {
                if let Some(w) = st.encroacher(f) {
                    if st.small_angle(w, &f) || st.subfacet_exempt(f, w) {
                        st.stats.exempt_faces += 1;
                    } else {
                        st.split_subfacet(f)?;
                    }
                }
            }
            continue;
        }
        if let Some((_, std::cmp::Reverse(s), t)) = st.tetq.pop() {
            let mut v = st.cx.tets[t as usize];
            v.sort_unstable();
            if st.cx.alive[t as usize] && v == s && st.quality(t).is_some() {
                let before = st.g.s.len();
                st.split_tet(t)?;
                if st.g.s.len() > before && st.cx.alive[t as usize] {
                    // a rejected circumcentre split a subsegment or subfacet that left t: retry t
                    st.queue_tet(t);
                }
            }
            continue;
        }
        // M6 step 1: slivers, once nothing else is left, within the cap
        if let Some((_, std::cmp::Reverse(s), t)) = st.dihq.pop() {
            if sliver_budget.is_none() {
                sliver_budget = Some(((st.g.s.len() as f64) * SLIVER_CAP).ceil() as u32);
            }
            let mut v = st.cx.tets[t as usize];
            v.sort_unstable();
            if !st.cx.alive[t as usize] || v != s || st.stats.sliver_points >= sliver_budget.unwrap() {
                continue;
            }
            let hs = st.hsz[t as usize];
            if !(hs > 0.0) || st.min_dihedral(t) >= DIHEDRAL_MIN {
                continue;
            }
            let x = st.cx.tets[t as usize].map(|q| st.xyz[q as usize]);
            let Some(c) = circumcentre(x) else { continue };
            let r = dot(&sub3(&c, &x[0]), &sub3(&c, &x[0])).sqrt();
            if r < SLIVER_FILTER * st.opt.alpha * hs {
                continue;
            }
            let before = (st.g.s.len(), st.stats.volume_points);
            st.split_tet(t)?;
            if st.g.s.len() > before.0 {
                st.stats.sliver_points += 1;
                if st.stats.volume_points > before.1 {
                    st.stats.volume_points -= 1; // counted as a sliver point instead
                }
            }
            continue;
        }
        break;
    }
    st.perturb_slivers();
    st.stats.slivers_left = (0..st.cx.tets.len() as u32)
        .filter(|&t| st.cx.alive[t as usize] && st.inside[t as usize] && st.hsz[t as usize] > 0.0
            && st.min_dihedral(t) < DIHEDRAL_MIN)
        .count() as u32;
    // write back
    b.tets = st.cx.live();
    let mut subs: Vec<Vec<[u32; 3]>> = vec![Vec::new(); plc.facets.len()];
    let mut all: Vec<([u32; 3], Vec<u32>)> = st.sub.iter().map(|(k, f)| (*k, f.clone())).collect();
    all.sort_unstable();
    for (k, fl) in all {
        for f in fl {
            subs[f as usize].push(k); // a subfacet shared by touching shells stays in both
        }
    }
    b.plc.subfacets = subs;
    b.plc.rec.s = st.g.s.clone();
    b.plc.rec.chains = st.chains;
    Ok(st.stats)
}
