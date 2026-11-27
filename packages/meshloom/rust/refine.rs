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
use crate::facetrec::{face, key, Boundary, Complex, FastKey, NONE};
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
    /// volume vertex moves by smoothing (M6 step 3)
    pub smooth_moves: u32,
    /// 2-3 and 3-2 flips that improved quality (M6 step 3)
    pub flips: u32,
    /// edge removals (rings of 4 or more tetrahedra) that improved quality
    pub edge_removals: u32,
    /// Lawson flips restoring the Delaunay property after insertions.
    pub lawson_flips: u32,
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
    sub: HashMap<[u32; 3], Vec<u32>, FastKey>,
    /// subsegment -> chain index
    seg: HashMap<(u32, u32), u32, FastKey>,
    chains: Vec<Vec<u32>>,
    /// input segment (its end points, as ekey) -> its chains: the pieces an S point of that
    /// segment may split, found without scanning every subsegment
    chain_of: HashMap<(u32, u32), Vec<u32>>,
    /// per input vertex: whether two segments meet there at less than 60 degrees
    small_apex: Vec<bool>,
    /// per input vertex: the other end points of the input segments that end there
    seg_ends: Vec<Vec<u32>>,
    /// per chain: whether every input facet with that segment on its boundary is a single,
    /// unlocked triangle (the input is a free triangle surface there)
    tri_chain: Vec<bool>,
    /// per input vertex: whether every input segment ending there is one of tri_chain (an
    /// input vertex of a triangle surface, which the polygon path would have as a Steiner
    /// point on its facet)
    tri_vertex: Vec<bool>,
    /// While flip_improve runs: faces and edges whose flip was refused, until a tetrahedron
    /// on them is replaced (a refusal depends only on those tetrahedra)
    clean_faces: std::collections::HashSet<[u32; 3], FastKey>,
    clean_e32: std::collections::HashSet<(u32, u32), FastKey>,
    clean_er: std::collections::HashSet<(u32, u32), FastKey>,
    track_clean: bool,
    /// per facet: its input vertices, and the input edges of its loops
    fverts: Vec<Vec<u32>>,
    fedges: Vec<Vec<(u32, u32)>>,
    /// facets the caller locked (curved surfaces sampled on the surface): no point is
    /// inserted on them or on their edges
    locked_facet: Vec<bool>,
    locked_edge: std::collections::HashSet<(u32, u32)>,
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
    /// a graded size field (`h` given as a function): the size at a point is the smaller of
    /// its region's and the field's there
    size: Option<&'a crate::size::SizeField>,
    _p: std::marker::PhantomData<&'a ()>,
}

/// M6 step 1: a tetrahedron (with a size) whose smallest dihedral angle is below this many
/// degrees is split at the lowest priority, unless its circumradius is below
/// SLIVER_FILTER h (its circumcentre would come too close to a vertex), up to
/// SLIVER_CAP times the points refinement inserted before (lfs-free cap).
const DIHEDRAL_MIN: f64 = 15.0;
const SLIVER_FILTER: f64 = 0.7;
const SLIVER_CAP: f64 = 0.10;
/// Boundary size (M6 design note; turned on after sliver removal, the owner's decision of
/// 2026-11-20): a subsegment longer than SEG_C alpha h, or a subfacet whose circumradius
/// exceeds FAC_C alpha h (h of the regions around them), is split even when not
/// encroached, so the boundary is discretized to the size before the volume.
/// FAC_C and ALPHA (Python) were chosen together on V8's C2 and C3 rows (2026-11-21:
/// FAC_C 0.68 with ALPHA 0.99-1.0 and 0.7 with 1.0 meet all of them, 0.5 and 0.75 do not), so V8 is
/// not an independent check of them.
const SEG_C: f64 = 1.0;
const FAC_C: f64 = 0.68;
/// Smoothing takes a move that raises the mean q of the star while its worst q stays at
/// least min(before, SMOOTH_FLOOR) (and the dihedral and ratio rules hold).
const SMOOTH_FLOOR: f64 = 0.5;
/// How often a tetrahedron whose circumcentre split a constraint instead is tried again.
const MAX_RETRIES: u8 = 3;
/// A tetrahedron whose circumcentre lies beyond a subfacet it may not split is split at the
/// circumcentre's projection on the facet when its longest edge exceeds LARGE_EDGE alpha h
/// and no vertex is within PROJECT_GAP alpha h of that point.
const LARGE_EDGE: f64 = 1.5;
const PROJECT_GAP: f64 = 0.5;
/// Lawson flips after one insertion, at most (they end on their own; this is a guard).
const LAWSON_CAP: u32 = 10_000;
/// A facet's frame triple is kept when the squared sine of its angle exceeds this (in
/// doubles); below it the s, r system of a facet point is ill-conditioned.
const FRAME_SIN2: f64 = 1e-8;
/// Small-angle rule for subsegments (encroachment): two input segments meeting below this
/// angle's cosine span a small angle. 60 degrees, the bound of small_apex (the 30-degree
/// variant measured in the (C) study's iteration 1 was slower and no better).
const SPAN_COS: f64 = 0.5;
/// Cosine of the smallest angle a triangle can have and still meet the radius-edge bound b
/// (its ratio is at least 1 / (2 sin theta) for its smallest angle theta; a tetrahedron is
/// at least as bad as any of its faces): an input angle below it forces a worse element.
fn ratio_cos(b: f64) -> f64 {
    let s = 1.0 / (2.0 * b);
    if s >= 1.0 { 0.0 } else { (1.0 - s * s).sqrt() }
}
/// Facet quality bound: a subfacet with a larger radius-edge ratio is split (2D Ruppert's
/// sqrt(2) with a margin).
const SUB_RATIO: f64 = 1.5;
/// A fast hasher for small integer keys (the shape memo), in place of the default SipHash:
/// the keys are vertex indices, not untrusted input.
/// Edge removal: the largest ring of tetrahedra around an edge it considers.
const EDGE_RING_MAX: usize = 7;

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

/// The vertex pairs (i, j) of the six edges of a tetrahedron with the other two (k, l).
const DIHEDRAL_PAIRS: [(usize, usize, usize, usize); 6] = [(0, 1, 2, 3), (0, 2, 1, 3), (0, 3, 1, 2), (1, 2, 0, 3), (1, 3, 0, 2), (2, 3, 0, 1)];

/// The smallest of the angles (degrees, at most 180) whose cosines have maximum `c`
/// (NEG_INFINITY: none, 180). One arc cosine for six: acos is decreasing and
/// to_degrees increasing, so this is min over the six of acos(c_i) in degrees, as
/// computed one by one before 2026-11-27, with a monotone libm acos (glibc's is
/// correctly rounded).
fn smallest_angle(c: f64) -> f64 {
    if c == f64::NEG_INFINITY { 180.0 } else { 180.0f64.min(c.acos().to_degrees()) }
}

/// q = 3 r_in / R of a tetrahedron with no degenerate face pair (shape's q, doubles).
fn shape_q(x: &[P3; 4]) -> f64 {
    let (a, b, c) = (sub3(&x[1], &x[0]), sub3(&x[2], &x[0]), sub3(&x[3], &x[0]));
    let v6 = dot(&a, &cross(&b, &c)).abs();
    let area = |p: P3, q: P3, r: P3| { let n = cross(&sub3(&q, &p), &sub3(&r, &p)); dot(&n, &n).sqrt() / 2.0 };
    let s = area(x[1], x[2], x[3]) + area(x[0], x[2], x[3]) + area(x[0], x[1], x[3]) + area(x[0], x[1], x[2]);
    let num: P3 = std::array::from_fn(|k| dot(&a, &a) * cross(&b, &c)[k] + dot(&b, &b) * cross(&c, &a)[k]
                                           + dot(&c, &c) * cross(&a, &b)[k]);
    let r = dot(&num, &num).sqrt() / (2.0 * v6);
    if r > 0.0 { 3.0 * (v6 / 2.0 / s) / r } else { 0.0 }
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

    /// The size at x of a simplex whose regions' size is `hs`: `hs`, or with a graded size
    /// field the smaller of `hs` and the field at x (`hs` <= 0: no size, or a hole).
    fn size_at(&self, hs: f64, x: &P3) -> f64 {
        match self.size {
            Some(f) if hs > 0.0 => hs.min(f.at(x)),
            _ => hs,
        }
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
        let hs = self.size_at(hs, &c);
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
            if r >= self.rins[parent] && !self.seditious(t[short.0], t[short.1]) && !self.spans_angle_below(t[short.0], t[short.1], ratio_cos(self.opt.ratio)) {
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
                    if !self.movable(v) {
                        continue;
                    }
                    let star: Vec<u32> = self.cx.star[v as usize].iter().copied()
                        .filter(|&u| self.cx.alive[u as usize]).collect();
                    let base = star.iter().map(|&u| self.min_dihedral(u)).fold(180.0, f64::min);
                    let rcap = self.rho_cap(&star);
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
                        if ok && star.iter().map(|&u| self.min_dihedral(u)).fold(180.0, f64::min) > base + 1e-9
                            && star.iter().all(|&u| self.tet_rho(u) <= rcap) {
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

    /// Quality q = 3 r_in / R of tetrahedron t (1 for the regular tetrahedron; doubles).
    fn tet_q(&self, t: u32) -> f64 {
        let x = self.cx.tets[t as usize].map(|v| self.xyz[v as usize]);
        let (a, b, c) = (sub3(&x[1], &x[0]), sub3(&x[2], &x[0]), sub3(&x[3], &x[0]));
        let v6 = dot(&a, &cross(&b, &c));
        if !(v6 > 0.0) {
            return 0.0;
        }
        let area = |p: P3, q: P3, r: P3| { let n = cross(&sub3(&q, &p), &sub3(&r, &p)); dot(&n, &n).sqrt() / 2.0 };
        let s = area(x[1], x[2], x[3]) + area(x[0], x[2], x[3]) + area(x[0], x[1], x[3]) + area(x[0], x[1], x[2]);
        let rin = 3.0 * (v6 / 6.0) / s;
        let num: P3 = std::array::from_fn(|k| dot(&a, &a) * cross(&b, &c)[k] + dot(&b, &b) * cross(&c, &a)[k]
                                               + dot(&c, &c) * cross(&a, &b)[k]);
        let r = dot(&num, &num).sqrt() / (2.0 * v6);
        3.0 * rin / r
    }

    /// M6 step 3 (first part): smoothing. Each volume vertex, in index order, moves towards
    /// the centroid of its star's other vertices (by 1, 1/2 or 1/4 of the way) when every
    /// tetrahedron around it stays positive (exact orient3d), the worst quality q around it
    /// grows and the smallest dihedral angle around it does not fall (below 15 degrees);
    /// three passes. Constraint vertices do not move.
    fn smooth(&mut self) {
        let n = self.g.input.len();
        for _pass in 0..5 {
            let mut moved = 0u32;
            for v in n as u32..(n + self.g.s.len()) as u32 {
                if !self.movable(v) {
                    continue;
                }
                let star: Vec<u32> = self.cx.star[v as usize].iter().copied()
                    .filter(|&u| self.cx.alive[u as usize]).collect();
                if star.is_empty() || star.iter().any(|&u| !self.inside[u as usize]) {
                    continue;
                }
                // q of each tetrahedron of the star, once per position: worst and mean from it
                let qs = |st: &Self| star.iter().map(|&u| st.tet_q(u)).collect::<Vec<f64>>();
                let worst = |q: &[f64]| q.iter().copied().fold(1.0f64, f64::min);
                let mean = |q: &[f64]| q.iter().sum::<f64>();
                let q0 = qs(self);
                let base = worst(&q0);
                let mbase = mean(&q0);
                let dmin = |st: &Self| star.iter().map(|&u| st.min_dihedral(u)).fold(180.0f64, f64::min);
                let dbase = dmin(self).min(DIHEDRAL_MIN);
                let rcap = self.rho_cap(&star);
                let p0 = self.xyz[v as usize];
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
                for f in [1.0, 0.5, 0.25] {
                    let c: P3 = std::array::from_fn(|k| p0[k] + f * (cen[k] / cnt - p0[k]));
                    self.set_volume_point(v, c);
                    let ok = star.iter().all(|&u| {
                        let w = self.cx.tets[u as usize];
                        self.orient(w) > 0
                    });
                    // a better worst tetrahedron, or the same worst and a better star on average
                    let q1 = if ok { qs(self) } else { Vec::new() };
                    let w = if ok { worst(&q1) } else { 0.0 };
                    if ok && (w > base + 1e-12 || (w >= base.min(SMOOTH_FLOOR) && mean(&q1) > mbase + 1e-9)) && dmin(self) >= dbase
                        && star.iter().all(|&u| self.tet_rho(u) <= rcap) {
                        moved += 1;
                        break;
                    }
                    self.set_volume_point(v, p0);
                }
            }
            self.stats.smooth_moves += moved;
            if moved == 0 {
                break;
            }
        }
    }

    /// Whether vertex v may move: a volume point whose tetrahedra are all inside the domain
    /// and none of whose faces through v is a subfacet (a volume point can lie on a facet's
    /// plane, or be a vertex of a face shared with another shell).
    fn movable(&self, v: u32) -> bool {
        let n = self.g.input.len();
        if (v as usize) < n || self.g.s[v as usize - n].kind() != crate::mixed::Kind::Volume {
            return false;
        }
        self.cx.star[v as usize].iter().filter(|&&u| self.cx.alive[u as usize]).all(|&u| {
            self.inside[u as usize] && {
                let w = self.cx.tets[u as usize];
                (0..4).all(|i| {
                    let k = key(face(&w, i));
                    !k.contains(&v) || !self.sub.contains_key(&k)
                })
            }
        })
    }

    /// Radius-edge ratio of tetrahedron t (doubles).
    fn tet_rho(&self, t: u32) -> f64 {
        let x = self.cx.tets[t as usize].map(|v| self.xyz[v as usize]);
        let Some(c) = circumcentre(x) else { return f64::INFINITY };
        let r = dot(&sub3(&c, &x[0]), &sub3(&c, &x[0])).sqrt();
        let l = (0..4).flat_map(|a| (a + 1..4).map(move |b| (a, b)))
            .map(|(a, b)| dot(&sub3(&x[a], &x[b]), &sub3(&x[a], &x[b])).sqrt()).fold(f64::INFINITY, f64::min);
        r / l
    }

    /// The largest radius-edge ratio a move may leave around a vertex: the bound of
    /// refinement, or what was there before when that is already above it (exempt
    /// tetrahedra near small angles); improvement never breaks V7.
    fn rho_cap(&self, star: &[u32]) -> f64 {
        let before = star.iter().map(|&u| self.tet_rho(u)).fold(0.0f64, f64::max);
        if self.opt.ratio > 0.0 { before.max(self.opt.ratio) } else { f64::INFINITY }
    }

    /// Whether facet point v may slide in its facet's plane: an F point not on a subsegment
    /// whose subfacets all belong to the same facets (one facet, or the shared facet of
    /// touching shells). Every tetrahedron around it stays, inside the domain or not.
    fn slidable(&self, v: u32) -> bool {
        let n = self.g.input.len();
        if (v as usize) < n || self.g.s[v as usize - n].kind() != crate::mixed::Kind::Facet {
            return false;
        }
        let mut owner: Option<&Vec<u32>> = None;
        for &u in self.cx.star[v as usize].iter().filter(|&&u| self.cx.alive[u as usize]) {
            let w = self.cx.tets[u as usize];
            for i in 0..4 {
                let k = key(face(&w, i));
                if !k.contains(&v) {
                    continue;
                }
                if let Some(l) = self.sub.get(&k) {
                    match owner {
                        None => owner = Some(l),
                        Some(o) if o != l => return false,
                        _ => {}
                    }
                }
            }
            for a in 0..4 {
                if w[a] != v && self.seg.contains_key(&ekey(v, w[a])) {
                    return false;
                }
            }
        }
        owner.is_some()
    }

    /// Moves facet point v to (about) p, keeping it exactly in its plane: p as
    /// a + s (b - a) + r (c - a) on v's own three input points, least squares in doubles.
    fn set_facet_point(&mut self, v: u32, sp: SPoint) {
        let n = self.g.input.len();
        self.g.set_s(v as usize - n, sp);
        let m = self.g.view();
        self.xyz[v as usize] = m.rounded(m.from_id(v));
    }

    fn facet_point_at(&self, v: u32, p: P3) -> Option<SPoint> {
        let n = self.g.input.len();
        let old = self.g.s[v as usize - n];
        let (pa, pb, pc) = (self.xyz[old.a as usize], self.xyz[old.b as usize], self.xyz[old.c as usize]);
        let (e1, e2, d) = (sub3(&pb, &pa), sub3(&pc, &pa), sub3(&p, &pa));
        let (g11, g12, g22) = (dot(&e1, &e1), dot(&e1, &e2), dot(&e2, &e2));
        let (r1, r2) = (dot(&e1, &d), dot(&e2, &d));
        let det = g11 * g22 - g12 * g12;
        let (s, r) = ((r1 * g22 - r2 * g12) / det, (g11 * r2 - g12 * r1) / det);
        (s.is_finite() && r.is_finite()).then(|| SPoint::fac(old.a, old.b, old.c, s, r))
    }

    /// Smoothing of facet points in their planes, by the rules of `smooth` on the
    /// tetrahedra inside the domain; every tetrahedron around the point keeps its orientation.
    fn slide_facets(&mut self) {
        let n = self.g.input.len();
        for _pass in 0..5 {
            let mut moved = 0u32;
            for v in n as u32..(n + self.g.s.len()) as u32 {
                if !self.slidable(v) {
                    continue;
                }
                let all: Vec<u32> = self.cx.star[v as usize].iter().copied()
                    .filter(|&u| self.cx.alive[u as usize]).collect();
                let star: Vec<u32> = all.iter().copied().filter(|&u| self.inside[u as usize]).collect();
                if star.is_empty() {
                    continue;
                }
                // the target: the centroid of v's neighbours in the facet (the other vertices
                // of its subfacets), which lies in the facet's plane
                let mut ring: Vec<u32> = Vec::new();
                for &u in &all {
                    let w = self.cx.tets[u as usize];
                    for i in 0..4 {
                        let k = key(face(&w, i));
                        if k.contains(&v) && self.sub.contains_key(&k) {
                            ring.extend(k.iter().copied().filter(|&x| x != v));
                        }
                    }
                }
                ring.sort_unstable();
                ring.dedup();
                if ring.len() < 3 {
                    continue;
                }
                let mut cen = [0.0; 3];
                for &w in &ring {
                    for k in 0..3 {
                        cen[k] += self.xyz[w as usize][k] / ring.len() as f64;
                    }
                }
                let worst = |st: &Self| star.iter().map(|&u| st.tet_q(u)).fold(1.0f64, f64::min);
                let mean = |st: &Self| star.iter().map(|&u| st.tet_q(u)).sum::<f64>();
                let dmin = |st: &Self| star.iter().map(|&u| st.min_dihedral(u)).fold(180.0f64, f64::min);
                let (base, mbase, dbase) = (worst(self), mean(self), dmin(self).min(DIHEDRAL_MIN));
                let rcap = self.rho_cap(&star);
                let old = self.g.s[v as usize - n];
                let p0 = self.xyz[v as usize];
                for f in [1.0, 0.5, 0.25] {
                    let c: P3 = std::array::from_fn(|k| p0[k] + f * (cen[k] - p0[k]));
                    let Some(sp) = self.facet_point_at(v, c) else { break };
                    self.set_facet_point(v, sp);
                    let ok = all.iter().all(|&u| {
                        let w = self.cx.tets[u as usize];
                        self.orient(w) > 0
                    });
                    let w = if ok { worst(self) } else { 0.0 };
                    if ok && (w > base + 1e-12 || (w >= base.min(SMOOTH_FLOOR) && mean(self) > mbase + 1e-9)) && dmin(self) >= dbase
                        && star.iter().all(|&u| self.tet_rho(u) <= rcap) {
                        moved += 1;
                        break;
                    }
                    self.set_facet_point(v, old);
                }
            }
            self.stats.smooth_moves += moved;
            if moved == 0 {
                break;
            }
        }
    }

    /// Smoothing of segment points along their segments, by the rules of `slide_facets`:
    /// the target is the centroid of the point's neighbours projected on the segment,
    /// strictly between the two vertices next to it on the segment.
    fn slide_segments(&mut self) {
        let n = self.g.input.len();
        for _pass in 0..5 {
            let mut moved = 0u32;
            for v in n as u32..(n + self.g.s.len()) as u32 {
                let old = self.g.s[v as usize - n];
                if old.kind() != crate::mixed::Kind::Segment {
                    continue;
                }
                let all: Vec<u32> = self.cx.star[v as usize].iter().copied()
                    .filter(|&u| self.cx.alive[u as usize]).collect();
                let star: Vec<u32> = all.iter().copied().filter(|&u| self.inside[u as usize]).collect();
                if star.is_empty() {
                    continue;
                }
                let mut nb: Vec<u32> = all.iter().flat_map(|&u| self.cx.tets[u as usize]).filter(|&x| x != v).collect();
                nb.sort_unstable();
                nb.dedup();
                let ends: Vec<u32> = nb.iter().copied().filter(|&x| self.seg.contains_key(&ekey(v, x))).collect();
                if ends.len() != 2 {
                    continue;
                }
                let (pa, pb) = (self.xyz[old.a as usize], self.xyz[old.b as usize]);
                let d = sub3(&pb, &pa);
                let dd = dot(&d, &d);
                let par = |x: &P3| dot(&sub3(x, &pa), &d) / dd;
                let (t0, t1) = {
                    let (u, w) = (par(&self.xyz[ends[0] as usize]), par(&self.xyz[ends[1] as usize]));
                    (u.min(w), u.max(w))
                };
                let tc = nb.iter().map(|&x| par(&self.xyz[x as usize])).sum::<f64>() / nb.len() as f64;
                let worst = |st: &Self| star.iter().map(|&u| st.tet_q(u)).fold(1.0f64, f64::min);
                let mean = |st: &Self| star.iter().map(|&u| st.tet_q(u)).sum::<f64>();
                let dmin = |st: &Self| star.iter().map(|&u| st.min_dihedral(u)).fold(180.0f64, f64::min);
                let (base, mbase, dbase) = (worst(self), mean(self), dmin(self).min(DIHEDRAL_MIN));
                let rcap = self.rho_cap(&star);
                for f in [1.0, 0.5, 0.25] {
                    let t = old.t + f * (tc - old.t);
                    let lo = t0 + 0.1 * (t1 - t0);
                    let hi = t1 - 0.1 * (t1 - t0);
                    if !(t > lo && t < hi && t > 0.0 && t < 1.0) {
                        continue;
                    }
                    self.set_facet_point(v, SPoint::seg(old.a, old.b, t));
                    let ok = all.iter().all(|&u| {
                        let w = self.cx.tets[u as usize];
                        self.orient(w) > 0
                    });
                    let w = if ok { worst(self) } else { 0.0 };
                    if ok && (w > base + 1e-12 || (w >= base.min(SMOOTH_FLOOR) && mean(self) > mbase + 1e-9)) && dmin(self) >= dbase
                        && star.iter().all(|&u| self.tet_rho(u) <= rcap) {
                        moved += 1;
                        break;
                    }
                    self.set_facet_point(v, old);
                }
            }
            self.stats.smooth_moves += moved;
            if moved == 0 {
                break;
            }
        }
    }

    fn set_volume_point(&mut self, v: u32, p: P3) {
        let n = self.g.input.len();
        self.g.set_s(v as usize - n, SPoint::vol(p));
        self.xyz[v as usize] = p;
    }

    /// (smallest dihedral angle in degrees, q) of four vertices, positive or not (doubles),
    /// computed on the vertices in sorted order so that it does not depend on their order.
    /// Until 2026-11-27 a memo by sorted vertex set returned the value of the first order
    /// queried; it held about 60% of peak memory on V14's graded 1M cube.
    fn shape(&self, mut v: [u32; 4]) -> (f64, f64) {
        v.sort_unstable();
        self.shape_of(v)
    }

    fn shape_of(&self, v: [u32; 4]) -> (f64, f64) {
        let x = v.map(|i| self.xyz[i as usize]);
        let mut c = f64::NEG_INFINITY;
        for (i, j, k, l) in DIHEDRAL_PAIRS {
            let e = sub3(&x[j], &x[i]);
            let (n1, n2) = (cross(&e, &sub3(&x[k], &x[i])), cross(&e, &sub3(&x[l], &x[i])));
            let d = (dot(&n1, &n1) * dot(&n2, &n2)).sqrt();
            if !(d > 0.0) {
                return (0.0, 0.0);
            }
            c = c.max((dot(&n1, &n2) / d).clamp(-1.0, 1.0));
        }
        (smallest_angle(c), shape_q(&x))
    }

    /// shape(v).1 alone, bit for bit: the same degeneracy test without the six arc cosines.
    fn q_of(&self, mut v: [u32; 4]) -> f64 {
        v.sort_unstable();
        let x = v.map(|i| self.xyz[i as usize]);
        for (i, j, k, l) in DIHEDRAL_PAIRS {
            let e = sub3(&x[j], &x[i]);
            let (n1, n2) = (cross(&e, &sub3(&x[k], &x[i])), cross(&e, &sub3(&x[l], &x[i])));
            if !((dot(&n1, &n1) * dot(&n2, &n2)).sqrt() > 0.0) {
                return 0.0;
            }
        }
        shape_q(&x)
    }

    /// The (dihedral, q) of each tetrahedron, computed once for worst_of and badness_of.
    fn shapes(&self, ts: &[[u32; 4]]) -> Vec<(f64, f64)> {
        ts.iter().map(|t| self.shape(*t)).collect()
    }

    /// The worst (dihedral, q) of a set of tetrahedra, compared dihedral first (below 15
    /// degrees), then q.
    fn worst_of(s: &[(f64, f64)]) -> (f64, f64) {
        s.iter().fold((180.0, 1.0), |a, b| (a.0.min(b.0), a.1.min(b.1)))
    }

    /// The sum of badness 1/q - 1 over tetrahedra (0 for regular ones): the energy that
    /// flips lower when they keep the worst shape at least min(before, SMOOTH_FLOOR).
    fn badness_of(s: &[(f64, f64)]) -> f64 {
        s.iter().map(|&(_, q)| if q > 0.0 { 1.0 / q - 1.0 } else { f64::INFINITY }).sum()
    }

    /// A replacement is taken when it raises the worst (dihedral, q), or keeps the worst at
    /// least the floors and lowers the total badness. `old` holds the replaced
    /// tetrahedra's shapes; each shape is computed once (shape is a function of the
    /// vertex set, so this decides as computing them again would).
    fn accept(&self, old: &[(f64, f64)], new: &[[u32; 4]]) -> bool {
        let ns = self.shapes(new);
        let (wn, wo) = (Self::worst_of(&ns), Self::worst_of(old));
        if Self::better(wn, wo) {
            return true;
        }
        wn.0 >= wo.0.min(DIHEDRAL_MIN) && wn.1 >= wo.1.min(SMOOTH_FLOOR) && Self::badness_of(&ns) < Self::badness_of(old) - 1e-9
    }

    fn better(new: (f64, f64), old: (f64, f64)) -> bool {
        let (nd, od) = (new.0.min(DIHEDRAL_MIN), old.0.min(DIHEDRAL_MIN));
        nd > od + 1e-9 || (nd >= od && new.1 > old.1 + 1e-9)
    }

    /// Orders four vertices so that orient3d is positive; None if they are coplanar.
    fn positive(&mut self, mut v: [u32; 4]) -> Option<[u32; 4]> {
        match self.orient(v) {
            o if o > 0 => Some(v),
            o if o < 0 => {
                v.swap(0, 1);
                Some(v)
            }
            _ => None,
        }
    }

    fn replace(&mut self, old: &[u32], new: &[[u32; 4]]) {
        let (ins, hs) = (self.inside[old[0] as usize], self.hsz[old[0] as usize]);
        for &t in old {
            self.cx.remove(t);
        }
        for &v in new {
            let id = self.cx.add(v);
            if id as usize >= self.inside.len() {
                self.inside.resize(id as usize + 1, false);
                self.hsz.resize(id as usize + 1, 0.0);
            }
            self.inside[id as usize] = ins;
            self.hsz[id as usize] = hs;
            self.mark_dirty(v);
        }
    }

    /// A new tetrahedron v: while flip_improve runs, its faces and edges may flip again.
    fn mark_dirty(&mut self, v: [u32; 4]) {
        if !self.track_clean {
            return;
        }
        for i in 0..4 {
            self.clean_faces.remove(&key(face(&v, i)));
            for j in i + 1..4 {
                let e = ekey(v[i], v[j]);
                self.clean_e32.remove(&e);
                self.clean_er.remove(&e);
            }
        }
    }

    /// M6 step 3 (second part): 2-3 and 3-2 flips inside the domain that raise the worst
    /// (dihedral, q) of the tetrahedra they replace, never across a subfacet or removing a
    /// subsegment; exact orient3d for every new tetrahedron. Faces and edges are visited in
    /// sorted order (deterministic); up to four passes.
    fn flip_improve(&mut self) {
        self.track_clean = true;
        self.flip_passes();
        self.track_clean = false;
        self.clean_faces.clear();
        self.clean_e32.clear();
        self.clean_er.clear();
    }

    fn flip_passes(&mut self) {
        for _pass in 0..4 {
            let mut done = 0u32;
            // 2-3 across interior faces
            let mut faces: Vec<[u32; 3]> = self.cx.interior_faces().into_iter()
                .filter(|k| !self.sub.contains_key(k)).collect();
            faces.sort_unstable();
            for k in faces {
                if self.clean_faces.contains(&k) {
                    continue; // rejected before, and no tetrahedron on it changed since
                }
                if self.try_23(k) {
                    done += 1;
                } else {
                    self.clean_faces.insert(k);
                }
            }
            // 3-2 removing an edge with three tetrahedra
            let mut edges: Vec<(u32, u32)> = Vec::new();
            for t in 0..self.cx.tets.len() as u32 {
                if !self.cx.alive[t as usize] || !self.inside[t as usize] {
                    continue;
                }
                let v = self.cx.tets[t as usize];
                for a in 0..4 {
                    for b in a + 1..4 {
                        edges.push(ekey(v[a], v[b]));
                    }
                }
            }
            edges.sort_unstable();
            edges.dedup();
            for (a, b) in edges {
                if self.clean_e32.contains(&(a, b)) {
                    continue;
                }
                if self.try_32(a, b) {
                    done += 1;
                } else {
                    self.clean_e32.insert((a, b));
                }
            }
            done += self.edge_removal();
            self.stats.flips += done;
            if done == 0 {
                break;
            }
        }
    }

    /// One 2-3 flip try across face k (the body of flip_passes' first loop): true when it
    /// flipped. A refusal depends only on the two tetrahedra on k, so flip_passes skips k
    /// until a tetrahedron on it is replaced.
    fn try_23(&mut self, k: [u32; 3]) -> bool {
        let Some(o) = self.cx.face_tets(&k) else { return false };
        if o[0] == NONE || o[1] == NONE || self.sub.contains_key(&k) {
            return false;
        }
        let (t1, t2) = (o[0], o[1]);
        if !self.inside[t1 as usize] || !self.inside[t2 as usize] || self.hsz[t1 as usize] != self.hsz[t2 as usize] {
            return false;
        }
        let (v1, v2) = (self.cx.tets[t1 as usize], self.cx.tets[t2 as usize]);
        let d = *v1.iter().find(|x| !k.contains(x)).unwrap();
        let e = *v2.iter().find(|x| !k.contains(x)).unwrap();
        let os = self.shapes(&[v1, v2]);
        let old = Self::worst_of(&os);
        if old.0 >= DIHEDRAL_MIN && old.1 > 0.9 {
            return false; // not worth a flip
        }
        // the cheap test first: shape (and so accept) does not depend on vertex order;
        // then each exact orientation once (convex_23 asks the same three)
        let cand: [[u32; 4]; 3] = std::array::from_fn(|j| [k[j], k[(j + 1) % 3], d, e]);
        if !self.accept(&os, &cand) {
            return false;
        }
        let o: [i8; 3] = std::array::from_fn(|j| self.orient(cand[j]));
        if o[0] == 0 || o.iter().any(|&x| x != o[0]) {
            return false; // a flat new tetrahedron, or de not through the face (convex_23)
        }
        let new: Vec<[u32; 4]> = cand.iter().map(|&c| if o[0] > 0 { c } else { [c[1], c[0], c[2], c[3]] }).collect();
        if self.rho_ok(&[v1, v2], &new) {
            self.replace(&[t1, t2], &new);
            return true;
        }
        false
    }

    /// One 3-2 flip try removing edge ab (the body of flip_passes' second loop).
    fn try_32(&mut self, a: u32, b: u32) -> bool {
        if self.seg.contains_key(&(a, b)) {
            return false;
        }
        let ring: Vec<u32> = self.cx.star[a as usize].iter().copied()
            .filter(|&t| self.cx.alive[t as usize] && self.cx.tets[t as usize].contains(&b)).collect();
        if ring.len() != 3 || ring.iter().any(|&t| !self.inside[t as usize] || self.hsz[t as usize] != self.hsz[ring[0] as usize]) {
            return false;
        }
        // the faces through the edge must not be constraints, and the edge must be interior
        let mut others: Vec<u32> = Vec::new();
        let mut bad = false;
        for &t in &ring {
            let v = self.cx.tets[t as usize];
            for i in 0..4 {
                let k = key(face(&v, i));
                if k.contains(&a) && k.contains(&b) && (self.sub.contains_key(&k) || self.cx.neighbor(t, &k) == NONE) {
                    bad = true;
                }
            }
            others.extend(v.iter().copied().filter(|&x| x != a && x != b));
        }
        others.sort_unstable();
        others.dedup();
        if bad || others.len() != 3 {
            return false;
        }
        let oldv: Vec<[u32; 4]> = ring.iter().map(|&t| self.cx.tets[t as usize]).collect();
        let os = self.shapes(&oldv);
        let old = Self::worst_of(&os);
        if old.0 >= DIHEDRAL_MIN && old.1 > 0.9 {
            return false;
        }
        let tri = [others[0], others[1], others[2]];
        // the cheap test first (shape does not depend on vertex order), then each exact
        // orientation once
        let (c1, c2) = ([tri[0], tri[1], tri[2], a], [tri[0], tri[1], tri[2], b]);
        if !self.accept(&os, &[c1, c2]) {
            return false;
        }
        // a and b on opposite sides of the triangle: the two new tetrahedra fill the ring
        let (sa, sb) = (self.orient(c1), self.orient(c2));
        if sa * sb >= 0 || !self.convex_23(&tri, a, b) {
            return false; // the edge must pass through the triangle's interior
        }
        let flip = |c: [u32; 4], o: i8| if o > 0 { c } else { [c[1], c[0], c[2], c[3]] };
        let (n1, n2) = (flip(c1, sa), flip(c2, sb));
        if self.rho_ok(&oldv, &[n1, n2]) {
            self.replace(&ring, &[n1, n2]);
            return true;
        }
        false
    }

    /// Edge removal: an interior edge ab (not a subsegment, no subfacet through it) with a
    /// ring of 4 to EDGE_RING_MAX tetrahedra of one region is replaced by the 2(n - 2)
    /// tetrahedra joining a and b to a triangulation of its ring polygon, chosen by dynamic
    /// programming for the best worst q, when that raises the ring's worst (dihedral, q) and
    /// keeps V7. Every new tetrahedron has exact orient3d of the ring's sign.
    fn edge_removal(&mut self) -> u32 {
        let mut edges: Vec<(u32, u32)> = Vec::new();
        for t in 0..self.cx.tets.len() as u32 {
            if !self.cx.alive[t as usize] || !self.inside[t as usize] {
                continue;
            }
            // q first: the dihedral angle decides only when q > 0.9
            if self.q_of(self.cx.tets[t as usize]) > 0.9 && self.shape(self.cx.tets[t as usize]).0 >= DIHEDRAL_MIN {
                continue;
            }
            let v = self.cx.tets[t as usize];
            for a in 0..4 {
                for b in a + 1..4 {
                    edges.push(ekey(v[a], v[b]));
                }
            }
        }
        edges.sort_unstable();
        edges.dedup();
        let mut done = 0;
        for (a, b) in edges {
            if self.clean_er.contains(&(a, b)) {
                continue;
            }
            if self.try_er(a, b) {
                done += 1;
            } else {
                self.clean_er.insert((a, b));
            }
        }
        self.stats.edge_removals += done;
        done
    }

    /// One edge-removal try at ab (the body of edge_removal's loop): true when it replaced the
    /// ring. A refusal depends only on the ring of tetrahedra around ab.
    fn try_er(&mut self, a: u32, b: u32) -> bool {
        if self.seg.contains_key(&(a, b)) {
            return false;
        }
        let ring: Vec<u32> = self.cx.star[a as usize].iter().copied()
            .filter(|&t| self.cx.alive[t as usize] && self.cx.tets[t as usize].contains(&b)).collect();
        let n = ring.len();
        if n < 4 || n > EDGE_RING_MAX
            || ring.iter().any(|&t| !self.inside[t as usize] || self.hsz[t as usize] != self.hsz[ring[0] as usize]) {
            return false;
        }
        // the ring polygon in cyclic order: each tetrahedron joins two consecutive vertices
        let mut pairs: Vec<(u32, u32)> = Vec::with_capacity(n);
        // the faces through ab: a face without a tetrahedron on its other side, or a
        // subfacet, refuses the removal. The tetrahedron across such a face holds a and b,
        // so it is in the ring: a face has one there exactly when it occurs twice among the
        // ring's faces (no lookup in the face table)
        let mut through: Vec<[u32; 3]> = Vec::with_capacity(2 * n);
        for &t in &ring {
            let v = self.cx.tets[t as usize];
            let o: Vec<u32> = v.iter().copied().filter(|&x| x != a && x != b).collect();
            pairs.push((o[0], o[1]));
            for i in 0..4 {
                let k = key(face(&v, i));
                if k.contains(&a) && k.contains(&b) {
                    through.push(k);
                }
            }
        }
        through.sort_unstable();
        let mut bad = through.len() != 2 * n;
        let mut i = 0;
        while !bad && i < through.len() {
            bad = i + 1 >= through.len() || through[i + 1] != through[i] || (i + 2 < through.len() && through[i + 2] == through[i])
                || self.sub.contains_key(&through[i]);
            i += 2;
        }
        if bad {
            return false;
        }
        let mut poly: Vec<u32> = vec![pairs[0].0, pairs[0].1];
        let mut used = vec![false; n];
        used[0] = true;
        while poly.len() < n {
            let last = *poly.last().unwrap();
            let Some(i) = (0..n).find(|&i| !used[i] && (pairs[i].0 == last || pairs[i].1 == last)) else { break };
            used[i] = true;
            poly.push(if pairs[i].0 == last { pairs[i].1 } else { pairs[i].0 });
        }
        let closes = (0..n).any(|i| !used[i] && {
            let (x, y) = pairs[i];
            (x == poly[n - 1] && y == poly[0]) || (y == poly[n - 1] && x == poly[0])
        });
        if poly.len() != n || !closes {
            return false;
        }
        let old: Vec<[u32; 4]> = ring.iter().map(|&t| self.cx.tets[t as usize]).collect();
        // the sign a must have against every triangle of the polygon, from a fan triangle
        // of the ring (consecutive vertices keep the orientation of the cycle)
        let sa = self.orient([poly[0], poly[1], poly[2], a]);
        if sa == 0 {
            return false;
        }
        // best[i][j]: (worst q, split k) of the polygon chain i..j, triangles (i, k, j)
        // tri_q[(i * n + k) * n + j]: the q of triangle (i, k, j)'s two tetrahedra, once each
        let mut tri_q: Vec<Option<f64>> = vec![None; n * n * n];
        let mut best = vec![vec![(f64::NEG_INFINITY, usize::MAX); n]; n];
        for i in 0..n - 1 {
            best[i][i + 1] = (f64::INFINITY, usize::MAX);
        }
        for len in 2..n {
            for i in 0..n - len {
                let j = i + len;
                for k in i + 1..j {
                    let q = *tri_q[(i * n + k) * n + j].get_or_insert_with(|| {
                        let tr = [poly[i], poly[k], poly[j]];
                        if self.g.orient3d([tr[0], tr[1], tr[2], a]) != sa || self.g.orient3d([tr[0], tr[1], tr[2], b]) != -sa {
                            return f64::NEG_INFINITY;
                        }
                        let ta = if sa > 0 { [tr[0], tr[1], tr[2], a] } else { [tr[1], tr[0], tr[2], a] };
                        let tb = if sa > 0 { [tr[1], tr[0], tr[2], b] } else { [tr[0], tr[1], tr[2], b] };
                        self.q_of(ta).min(self.q_of(tb))
                    });
                    let v = q.min(best[i][k].0).min(best[k][j].0);
                    if v > best[i][j].0 {
                        best[i][j] = (v, k);
                    }
                }
            }
        }
        if !(best[0][n - 1].0 > 0.0) {
            return false;
        }
        let mut tris: Vec<[u32; 3]> = Vec::new();
        let mut st = vec![(0usize, n - 1)];
        while let Some((i, j)) = st.pop() {
            if j <= i + 1 {
                continue;
            }
            let k = best[i][j].1;
            tris.push([poly[i], poly[k], poly[j]]);
            st.push((i, k));
            st.push((k, j));
        }
        let mut new: Vec<[u32; 4]> = Vec::with_capacity(2 * tris.len());
        for tr in &tris {
            if sa > 0 {
                new.push([tr[0], tr[1], tr[2], a]);
                new.push([tr[1], tr[0], tr[2], b]);
            } else {
                new.push([tr[1], tr[0], tr[2], a]);
                new.push([tr[0], tr[1], tr[2], b]);
            }
        }
        if new.iter().any(|t| self.orient(*t) <= 0) {
            return false;
        }
        if self.accept(&self.shapes(&old), &new) && self.rho_ok(&old, &new) {
            self.replace(&ring, &new);
            return true;
        }
        false
    }

    /// Replaces tetrahedra `old` by `new` (labels of old[0]) and returns the new ids.
    fn replace_ids(&mut self, old: &[u32], new: &[[u32; 4]]) -> Vec<u32> {
        let (ins, hs) = (self.inside[old[0] as usize], self.hsz[old[0] as usize]);
        for &t in old {
            self.cx.remove(t);
        }
        new.iter().map(|&v| {
            let id = self.cx.add(v);
            if id as usize >= self.inside.len() {
                self.inside.resize(id as usize + 1, false);
                self.hsz.resize(id as usize + 1, 0.0);
            }
            self.inside[id as usize] = ins;
            self.hsz[id as usize] = hs;
            self.mark_dirty(v);
            id
        }).collect()
    }

    /// Restores the constrained Delaunay property around new tetrahedra after an insertion
    /// whose cavity was cut short (it grows only across faces the point sees): Lawson's
    /// 2-3 and 3-2 flips of interior faces whose neighbour's apex lies in the circumsphere
    /// (exact insphere with symbolic perturbation), never across a subfacet, never removing
    /// a subsegment, between tetrahedra of the same region; outside the domain too, where
    /// a non-Delaunay filling makes the cavities of later facet points non-star-shaped. Each such flip lowers the lifted
    /// triangulation, so the flips end; LAWSON_CAP bounds them all the same. Returns the
    /// tetrahedra that replace `start`, for the queues.
    fn lawson(&mut self, start: Vec<u32>) -> Vec<u32> {
        let mut made: Vec<u32> = start.clone();
        let mut stack: Vec<[u32; 3]> = Vec::new();
        let push = |st: &Self, t: u32, stack: &mut Vec<[u32; 3]>| {
            let v = st.cx.tets[t as usize];
            for i in 0..4 {
                stack.push(key(face(&v, i)));
            }
        };
        for &t in &start {
            push(self, t, &mut stack);
        }
        let mut flips = 0u32;
        while let Some(k) = stack.pop() {
            if flips >= LAWSON_CAP {
                break;
            }
            if self.sub.contains_key(&k) {
                continue;
            }
            let Some(o) = self.cx.face_tets(&k) else { continue };
            if o[0] == NONE || o[1] == NONE {
                continue;
            }
            let (t1, t2) = (o[0], o[1]);
            if !self.cx.alive[t1 as usize] || !self.cx.alive[t2 as usize] || self.inside[t1 as usize] != self.inside[t2 as usize]
                || self.hsz[t1 as usize] != self.hsz[t2 as usize] {
                continue;
            }
            let (v1, v2) = (self.cx.tets[t1 as usize], self.cx.tets[t2 as usize]);
            let d = *v1.iter().find(|x| !k.contains(x)).unwrap();
            let e = *v2.iter().find(|x| !k.contains(x)).unwrap();
            if self.g.insphere_sos([v1[0], v1[1], v1[2], v1[3], e]) <= 0 {
                continue;
            }
            // 2-3: the edge de crosses the face's interior
            if self.convex_23(&k, d, e) {
                let mut new = Vec::with_capacity(3);
                for j in 0..3 {
                    if let Some(t) = self.positive([k[j], k[(j + 1) % 3], d, e]) {
                        new.push(t);
                    }
                }
                if new.len() == 3 {
                    let ids = self.replace_ids(&[t1, t2], &new);
                    for &t in &ids {
                        push(self, t, &mut stack);
                    }
                    made.extend(ids);
                    flips += 1;
                    continue;
                }
            }
            // 3-2: an edge of the face with exactly three tetrahedra around it
            for j in 0..3 {
                let (a, b) = (k[j], k[(j + 1) % 3]);
                if self.seg.contains_key(&ekey(a, b)) {
                    continue;
                }
                let ring: Vec<u32> = self.cx.star[a as usize].iter().copied()
                    .filter(|&t| self.cx.alive[t as usize] && self.cx.tets[t as usize].contains(&b)).collect();
                if ring.len() != 3 || ring.iter().any(|&t| self.inside[t as usize] != self.inside[t1 as usize] || self.hsz[t as usize] != self.hsz[t1 as usize]) {
                    continue;
                }
                let mut others: Vec<u32> = Vec::new();
                let mut bad = false;
                for &t in &ring {
                    let v = self.cx.tets[t as usize];
                    for i in 0..4 {
                        let f = key(face(&v, i));
                        if f.contains(&a) && f.contains(&b) && (self.sub.contains_key(&f) || self.cx.neighbor(t, &f) == NONE) {
                            bad = true;
                        }
                    }
                    others.extend(v.iter().copied().filter(|&x| x != a && x != b));
                }
                others.sort_unstable();
                others.dedup();
                if bad || others.len() != 3 {
                    continue;
                }
                let tri = [others[0], others[1], others[2]];
                let (sa, sb) = (self.orient([tri[0], tri[1], tri[2], a]), self.orient([tri[0], tri[1], tri[2], b]));
                if sa * sb >= 0 || !self.convex_23(&tri, a, b) {
                    continue;
                }
                let (Some(n1), Some(n2)) = (self.positive([tri[0], tri[1], tri[2], a]), self.positive([tri[0], tri[1], tri[2], b])) else { continue };
                let ids = self.replace_ids(&ring, &[n1, n2]);
                for &t in &ids {
                    push(self, t, &mut stack);
                }
                made.extend(ids);
                flips += 1;
                break;
            }
        }
        self.stats.lawson_flips += flips;
        made.retain(|&t| self.cx.alive[t as usize]);
        made.sort_unstable();
        made.dedup();
        made
    }

    /// A flip keeps V7: its new tetrahedra stay within the refinement bound, or within the
    /// worst ratio of the tetrahedra it replaces when that is already above it.
    fn rho_ok(&self, old: &[[u32; 4]], new: &[[u32; 4]]) -> bool {
        if !(self.opt.ratio > 0.0) {
            return true;
        }
        let rho = |v: &[u32; 4]| {
            let x = v.map(|i| self.xyz[i as usize]);
            match circumcentre(x) {
                Some(c) => {
                    let r = dot(&sub3(&c, &x[0]), &sub3(&c, &x[0])).sqrt();
                    let l = (0..4).flat_map(|a| (a + 1..4).map(move |b| (a, b)))
                        .map(|(a, b)| dot(&sub3(&x[a], &x[b]), &sub3(&x[a], &x[b])).sqrt()).fold(f64::INFINITY, f64::min);
                    r / l
                }
                None => f64::INFINITY,
            }
        };
        let cap = old.iter().map(rho).fold(0.0f64, f64::max).max(self.opt.ratio);
        new.iter().all(|v| rho(v) <= cap)
    }

    /// Whether the edge d-e crosses the interior of triangle k (a 2-3 flip is valid).
    fn convex_23(&mut self, k: &[u32; 3], d: u32, e: u32) -> bool {
        let o = self.orient([k[0], k[1], d, e]);
        o != 0 && (1..3).all(|j| self.orient([k[j], k[(j + 1) % 3], d, e]) == o)
    }

    /// The smallest dihedral angle of tetrahedron t, in degrees (doubles).
    fn min_dihedral(&self, t: u32) -> f64 {
        let x = self.cx.tets[t as usize].map(|v| self.xyz[v as usize]);
        let mut c = f64::NEG_INFINITY;
        for (i, j, k, l) in DIHEDRAL_PAIRS {
            let e = sub3(&x[j], &x[i]);
            let (n1, n2) = (cross(&e, &sub3(&x[k], &x[i])), cross(&e, &sub3(&x[l], &x[i])));
            let d = (dot(&n1, &n1) * dot(&n2, &n2)).sqrt();
            if d > 0.0 {
                c = c.max((dot(&n1, &n2) / d).clamp(-1.0, 1.0));
            } else {
                return 0.0;
            }
        }
        smallest_angle(c)
    }

    /// The size at a boundary simplex: the smallest positive size of the tetrahedra (inside
    /// the domain) in `ts`; 0 when none has one.
    fn local_h(&self, ts: impl Iterator<Item = u32>) -> f64 {
        ts.filter(|&t| t != NONE && self.inside[t as usize]).map(|t| self.hsz[t as usize])
            .filter(|h| *h > 0.0).fold(0.0, |a: f64, h| if a == 0.0 { h } else { a.min(h) })
    }

    /// Boundary size: a subsegment longer than SEG_C alpha h of the regions around it.
    fn segment_too_long(&self, e: (u32, u32)) -> bool {
        let ts = self.cx.star[e.0 as usize].iter().copied()
            .filter(|&t| self.cx.alive[t as usize] && self.cx.tets[t as usize].contains(&e.1));
        let (a, b) = (self.xyz[e.0 as usize], self.xyz[e.1 as usize]);
        let h = self.size_at(self.local_h(ts), &[0, 1, 2].map(|k| 0.5 * (a[k] + b[k])));
        let d = sub3(&b, &a);
        // an unsplit input segment whose facets are all single triangles is bounded as their
        // edges are: it is too long when no triangle on it meets the subfacet size bound (half
        // its length, the smallest circumradius of a triangle on it, above FAC_C alpha h);
        // once split, its pieces are sized as segments
        let whole = self.seg.get(&e).is_some_and(|&k| {
            let ch = &self.chains[k as usize];
            self.tri_chain[k as usize] && ch.len() == 2
        });
        let c = if whole { 2.0 * FAC_C } else { SEG_C };
        h > 0.0 && dot(&d, &d).sqrt() > c * self.opt.alpha * h
    }

    /// Boundary size: a subfacet whose circumradius exceeds FAC_C alpha h of its regions.
    fn subfacet_too_large(&self, f: [u32; 3]) -> bool {
        let Some(o) = self.cx.face_tets(&f) else { return false };
        let h = self.local_h(o.iter().copied());
        if !(h > 0.0) {
            return false;
        }
        let x = f.map(|v| self.xyz[v as usize]);
        let (a, b) = (sub3(&x[1], &x[0]), sub3(&x[2], &x[0]));
        let n = cross(&a, &b);
        let nn = dot(&n, &n);
        let h = if self.size.is_some() {
            // the field at the subfacet's circumcentre (its centroid when degenerate)
            let c = if nn > 0.0 {
                let (la, lb) = (dot(&a, &a), dot(&b, &b));
                let u = cross(&n, &a);
                let v = cross(&b, &n);
                let w = [0, 1, 2].map(|k| (lb * u[k] + la * v[k]) / (2.0 * nn));
                [0, 1, 2].map(|k| x[0][k] + w[k])
            } else {
                [0, 1, 2].map(|k| (x[0][k] + x[1][k] + x[2][k]) / 3.0)
            };
            self.size_at(h, &c)
        } else {
            h
        };
        let cc = sub3(&a, &b);
        let (la, lb, lc) = (dot(&a, &a), dot(&b, &b), dot(&cc, &cc));
        let (u, v) = if la <= lb && la <= lc { (f[0], f[1]) } else if lb <= lc { (f[0], f[2]) } else { (f[1], f[2]) };
        // inside a small input angle the circumradius of a skinny subfacet is not its size:
        // half its longest edge is (the smallest circumradius a triangle with that edge has)
        let size = if self.spans_angle_below(u, v, ratio_cos(SUB_RATIO)) { la.max(lb).max(lc).sqrt() / 2.0 } else if nn > 0.0 {
            (la * lb * lc).sqrt() / (2.0 * nn.sqrt())
        } else {
            0.0
        };
        nn > 0.0 && size > FAC_C * self.opt.alpha * h
    }

    /// Facet quality: a subfacet whose radius-edge ratio (circumradius over its shortest
    /// edge) exceeds SUB_RATIO, when refinement has a ratio bound and none of its vertices
    /// is the apex of a small input angle. A skinny subfacet makes every tetrahedron on it
    /// a sliver or a needle that no interior move can repair.
    fn subfacet_skinny(&self, f: [u32; 3]) -> bool {
        if !(self.opt.ratio > 0.0) || f.iter().any(|&v| (v as usize) < self.small_apex.len() && self.small_apex[v as usize]) {
            return false;
        }
        let Some(o) = self.cx.face_tets(&f) else { return false };
        if !(self.local_h(o.iter().copied()) > 0.0) {
            return false;
        }
        let x = f.map(|v| self.xyz[v as usize]);
        let (a, b) = (sub3(&x[1], &x[0]), sub3(&x[2], &x[0]));
        let n = cross(&a, &b);
        let nn = dot(&n, &n);
        let c = sub3(&a, &b);
        let (la, lb, lc) = (dot(&a, &a), dot(&b, &b), dot(&c, &c));
        if !(nn > 0.0) {
            return false;
        }
        let rc = (la * lb * lc).sqrt() / (2.0 * nn.sqrt());
        if !(rc > SUB_RATIO * la.min(lb).min(lc).sqrt()) {
            return false;
        }
        // small-angle rule (Miller, Pav and Walkington 2003): a skinny subfacet whose shortest
        // edge spans an input angle too small for any triangle to meet SUB_RATIO (its end points
        // on two segments that meet at an input vertex below that angle) is left
        let (u, v) = if la <= lb && la <= lc { (f[0], f[1]) } else if lb <= lc { (f[0], f[2]) } else { (f[1], f[2]) };
        !self.spans_angle_below(u, v, ratio_cos(SUB_RATIO))
    }

    /// The input segments a vertex lies on, as (end, end): a segment point's own, or every
    /// segment that ends at an input vertex.
    fn segments_at(&self, v: u32) -> Vec<(u32, u32)> {
        let n = self.g.input.len();
        if (v as usize) < n {
            return self.seg_ends[v as usize].iter().map(|&w| (v, w)).collect();
        }
        let sp = &self.g.s[v as usize - n];
        if sp.c == NONE && sp.b != NONE { vec![(sp.a, sp.b)] } else { Vec::new() }
    }

    /// Whether input segment chain c meets facet fi at a small angle: one end of c is a
    /// vertex of fi, c is not an edge of fi, and c leaves that vertex at less than 60 degrees
    /// to fi's plane (the bound of small_apex and of the facet-facet rule).
    fn seg_facet_small(&self, c: u32, fi: u32) -> bool {
        let ch = &self.chains[c as usize];
        let (a, b) = (ch[0], ch[ch.len() - 1]);
        let fv = &self.fverts[fi as usize];
        if self.fedges[fi as usize].binary_search(&ekey(a, b)).is_ok() {
            return false;
        }
        let [p, q, r] = self.frame[fi as usize].0.map(|v| self.xyz[v as usize]);
        let n = cross(&sub3(&q, &p), &sub3(&r, &p));
        let nl = dot(&n, &n).sqrt();
        [(a, b), (b, a)].iter().any(|&(z, o)| {
            if fv.binary_search(&z).is_err() {
                return false;
            }
            let u = sub3(&self.xyz[o as usize], &self.xyz[z as usize]);
            let ul = dot(&u, &u).sqrt();
            // sine of the angle to the plane below sin 60 degrees
            nl > 0.0 && ul > 0.0 && dot(&u, &n).abs() < 0.8660254037844387 * ul * nl
        })
    }

    /// The input segment chains a vertex lies on.
    fn chains_at(&self, w: u32) -> Vec<u32> {
        let mut out = Vec::new();
        for (p, q) in self.segments_at(w) {
            if let Some(l) = self.chain_of.get(&ekey(p, q)) {
                out.extend(l.iter().copied());
            }
        }
        out
    }

    /// The facets a vertex lies on (those of the subfacets around it).
    fn facets_at(&self, w: u32) -> Vec<u32> {
        let mut out = Vec::new();
        for &t in &self.cx.star[w as usize] {
            if !self.cx.alive[t as usize] {
                continue;
            }
            for i in 0..4 {
                let k = key(face(&self.cx.tets[t as usize], i));
                if k.contains(&w) {
                    if let Some(l) = self.sub.get(&k) {
                        out.extend(l.iter().copied());
                    }
                }
            }
        }
        out.sort_unstable();
        out.dedup();
        out
    }

    /// Segment-facet small-angle rule for a subfacet f encroached by w: w lies on a segment
    /// that meets f's facet at a small angle.
    fn seg_facet_exempt(&self, w: u32, f: &[u32; 3]) -> bool {
        self.chains_at(w).iter().any(|&c| self.sub[f].iter().any(|&fi| self.seg_facet_small(c, fi)))
    }

    /// Whether boundary vertex q lies on a triangle surface: an input vertex of one, or a
    /// segment or facet point whose input vertices all are.
    fn on_tri_surface(&self, q: u32) -> bool {
        let n = self.g.input.len();
        if (q as usize) < n {
            return self.tri_vertex[q as usize];
        }
        let sp = &self.g.s[q as usize - n];
        if sp.b == NONE {
            return false; // a volume point
        }
        [sp.a, sp.b, sp.c].iter().filter(|&&x| x != NONE).all(|&x| (x as usize) < n && self.tri_vertex[x as usize])
    }

    /// Whether u and v lie on two different input segments that meet at an input vertex
    /// z at an angle below the SPAN_COS angle (z the apex of a small input angle).
    fn spans_small_angle(&self, u: u32, v: u32) -> bool {
        self.spans_angle_below(u, v, SPAN_COS)
    }

    /// Whether u and v lie on two different input segments meeting at an input vertex z at
    /// an angle whose cosine is above cos_bound.
    fn spans_angle_below(&self, u: u32, v: u32, cos_bound: f64) -> bool {
        let (su, sv) = (self.segments_at(u), self.segments_at(v));
        su.iter().any(|&(p, q)| sv.iter().any(|&(r, s)| {
            if ekey(p, q) == ekey(r, s) {
                return false;
            }
            [p, q].iter().any(|&z| {
                if !(z == r || z == s) || !self.small_apex[z as usize] {
                    return false;
                }
                let (a, b) = (if p == z { q } else { p }, if r == z { s } else { r });
                let (da, db) = (sub3(&self.xyz[a as usize], &self.xyz[z as usize]), sub3(&self.xyz[b as usize], &self.xyz[z as usize]));
                dot(&da, &db) > cos_bound * dot(&da, &da).sqrt() * dot(&db, &db).sqrt()
            })
        }))
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
        let o = self.cx.face_tets(&f)?;
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
        self.g.pop_s();
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
            if let Some(o) = self.cx.face_tets(k) {
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
            if let Some(o) = self.cx.face_tets(k) {
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
            let one_sided = plane.iter().any(|k| self.cx.face_tets(k).is_some_and(|o| o.iter().any(|&t| t != NONE && self.inside[t as usize] && !set.contains(&t))));
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
            let lone: Vec<(u32, u32)> = self.chain_of.get(&ekey(sp.a, sp.b)).into_iter().flatten()
                .flat_map(|&c| self.chains[c as usize].windows(2).map(|w| ekey(w[0], w[1])).collect::<Vec<_>>())
                .filter(|e| self.seg.contains_key(e) && e.0 != p && e.1 != p).collect();
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
            if !self.cx.has_face(&nk) {
                return Err(format!("refinement: the split subfacet {nk:?} is not a face"));
            }
            self.sub.insert(nk, fl);
            self.subq.push_back(nk);
        }
        for k in touched {
            self.subq.push_back(k);
        }
        let added = self.lawson(added);
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
        if self.locked_edge.contains(&e) {
            // an edge of a locked (curved) facet: a point on it would lie off the surface
            self.stats.exempt += 1;
            return Ok(());
        }
        let c = self.seg[&e];
        let chain = &self.chains[c as usize];
        let (a, b) = (chain[0], chain[chain.len() - 1]);
        let t_of = |v: u32, st: &Self| -> f64 {
            if v == a { 0.0 } else if v == b { 1.0 } else { st.g.s[v as usize - st.g.input.len()].t }
        };
        let (tu, tv) = (t_of(e.0, self), t_of(e.1, self));
        let mut tm = tu + (tv - tu) / 2.0;
        // concentric shells (Ruppert 1995; Shewchuk 2002, section 4): a subsegment with exactly
        // one input endpoint splits at a power-of-two distance from that endpoint, between a
        // third and two thirds of its length, so that subsegments meeting at a small input angle
        // split at equal radii and stop encroaching each other
        let apex = |v: u32| (v == a || v == b) && self.small_apex[v as usize];
        let (ia, ib) = (apex(e.0), apex(e.1));
        if ia != ib {
            let d = sub3(&self.xyz[b as usize], &self.xyz[a as usize]);
            let len = dot(&d, &d).sqrt();
            let (t0, t1) = if ia { (tu, tv) } else { (tv, tu) };
            let piece = (t1 - t0).abs() * len;
            if len > 0.0 && piece > 0.0 {
                // the power of two in [piece/3, 2 piece/3), which always exists (rounding the
                // midpoint's exponent can land outside that window; the midpoint split then left
                // pieces at unequal radii around a fan of segments, which encroached each other
                // until their points met in doubles)
                let r = 2f64.powf((piece / 3.0).log2().ceil());
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
        self.split_facet_toward(f, None)
    }

    /// Splits subfacet f's facet at f's circumcentre or, with a target (q, gap), at q's
    /// projection on the facet's plane when no vertex of the subfacet holding it is nearer
    /// than gap.
    fn split_facet_toward(&mut self, f: [u32; 3], target: Option<(P3, f64)>) -> Result<(), String> {
        if self.sub[&f].iter().any(|&fi| self.locked_facet[fi as usize]) {
            // a subfacet of a locked (curved) facet is never split
            self.stats.exempt_faces += 1;
            return Ok(());
        }
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
        // a target's coordinates: the least-squares frame below projects them on the plane
        let o: P3 = target.map(|q| q.0).unwrap_or(o);
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
        if let Some((_, gap)) = target {
            let pp = self.xyz[p as usize];
            if cur.iter().any(|&v| { let d = sub3(&self.xyz[v as usize], &pp); dot(&d, &d) < gap * gap }) {
                self.drop_point(p);
                self.stats.exempt_faces += 1;
                return Ok(());
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
        if target.is_none() && !plane.contains(&f) {
            // the 2D cavity p sees leaves f (an obtuse f whose circumcentre lies in another
            // subfacet, past a facet triangulation that is not Delaunay): inserting p would
            // not remove f, and every later try at f would find p there while tetrahedra
            // next to f split towards the facet without end; leave f
            self.drop_point(p);
            self.stats.rejected += 1;
            self.stats.exempt_faces += 1;
            return Ok(());
        }
        let seeds: Vec<u32> = plane.iter().flat_map(|k| self.cx.face_tets(k).unwrap()).filter(|&t| t != NONE).collect();
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
            if self.seg.get(&e).is_some_and(|&c| self.sub[&f].iter().any(|&fi| self.seg_facet_small(c, fi))) {
                // a facet point next to a segment that meets the facet at a small angle:
                // leave both (splitting either would cascade between them)
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
                // a straight walk can cycle in a constrained, non-Delaunay triangulation:
                // leave this tetrahedron (counted as a rejected point)
                self.drop_point(p);
                self.stats.rejected += 1;
                return Ok(());
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
                                // a tetrahedron far above the size field is not left: the
                                // circumcentre's projection on the facet lies in its
                                // circumsphere, so a facet point there removes it
                                let hs = self.size_at(self.hsz[t as usize], &c);
                                let xs = v.map(|q| self.xyz[q as usize]);
                                let longest = (0..4).flat_map(|a| (a + 1..4).map(move |b| (a, b)))
                                    .map(|(a, b)| dot(&sub3(&xs[a], &xs[b]), &sub3(&xs[a], &xs[b])).sqrt())
                                    .fold(0.0f64, f64::max);
                                if hs > 0.0 && longest > LARGE_EDGE * self.opt.alpha * hs
                                    && !v.iter().any(|&x| self.small_angle(x, &k)) {
                                    return self.split_facet_toward(k, Some((c, PROJECT_GAP * self.opt.alpha * hs)));
                                }
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
        if !cav.contains(&t) {
            // the cavity p sees leaves t: inserting p would not remove t, and a neighbour with
            // nearly the same circumsphere would then insert a point next to p (an edge far
            // below h, and a ratio cascade from it); leave t
            self.drop_point(p);
            self.stats.rejected += 1;
            return Ok(());
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
/// `size` (a graded size field, `h` given as a function) bounds the size further: a
/// simplex is sized by the smaller of its region's size and the field at its circumcentre
/// (a subsegment: its midpoint); without it the output is the same as before the field.
pub fn refine(plc: &crate::plc::Plc, b: &mut Boundary, opt: RefineOptions, seeds: &[crate::mesh::Seed],
              label_h: &[f64], locked: &[u32], size: Option<&crate::size::SizeField>) -> Result<RefineStats, String> {
    let mut g = MixedPoints::new(plc.points.clone());
    for s in &b.plc.rec.s {
        g.push(*s);
    }
    let total = g.len();
    let cx = Complex::new(total, &b.tets);
    let m = g.view();
    let xyz: Vec<P3> = (0..total as u32).map(|v| m.rounded(m.from_id(v))).collect();
    let mut sub = HashMap::with_hasher(FastKey);
    for (fi, tris) in b.plc.subfacets.iter().enumerate() {
        for t in tris {
            sub.entry(key(*t)).or_insert_with(Vec::new).push(fi as u32);
        }
    }
    let mut seg = HashMap::with_hasher(FastKey);
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
        let mut f = f.ok_or_else(|| format!("facet {fi} has no three non-collinear points"))?;
        // the facet points are a + s (b - a) + r (c - a), with s and r solved in doubles: three
        // points that are collinear in doubles to rounding only (points along one long edge of
        // a polygon) leave that system singular. Such a triple is replaced by a well-spread
        // one: the loop point farthest from the first, then the one farthest from their line
        let sin2 = |t: [u32; 3]| -> f64 {
            let (e1, e2) = (sub3(&xyz[t[1] as usize], &xyz[t[0] as usize]), sub3(&xyz[t[2] as usize], &xyz[t[0] as usize]));
            let c = cross(&e1, &e2);
            dot(&c, &c) / (dot(&e1, &e1) * dot(&e2, &e2))
        };
        if !(sin2(f) > FRAME_SIN2) {
            let a = lp[0];
            let d2 = |u: u32, v: u32| { let d = sub3(&xyz[u as usize], &xyz[v as usize]); dot(&d, &d) };
            let b = *lp.iter().max_by(|&&u, &&v| d2(u, a).total_cmp(&d2(v, a))).unwrap();
            let ab = sub3(&xyz[b as usize], &xyz[a as usize]);
            let off = |u: u32| { let c = cross(&ab, &sub3(&xyz[u as usize], &xyz[a as usize])); dot(&c, &c) };
            let c = *lp.iter().max_by(|&&u, &&v| off(u).total_cmp(&off(v))).unwrap();
            if a != b && b != c && a != c && !g.collinear(a, b, c) && sin2([a, b, c]) > sin2(f) {
                f = [a, b, c];
            }
        }
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
    // with a graded size field, the cap's estimate uses its smallest size
    let hmin = size.map_or(hmin, |f| if hmin.is_finite() { hmin.min(f.min) } else { hmin });
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
    let mut seg_ends: Vec<Vec<u32>> = vec![Vec::new(); xyz.len()];
    let fverts: Vec<Vec<u32>> = plc.facets.iter().map(|loops| {
        let mut v: Vec<u32> = loops.iter().flatten().copied().collect();
        v.sort_unstable();
        v.dedup();
        v
    }).collect();
    let fedges: Vec<Vec<(u32, u32)>> = plc.facets.iter().map(|loops| {
        let mut v: Vec<(u32, u32)> = loops.iter().flat_map(|lp| (0..lp.len()).map(move |i| ekey(lp[i], lp[(i + 1) % lp.len()]))).collect();
        v.sort_unstable();
        v.dedup();
        v
    }).collect();
    let tri_chain: Vec<bool> = {
        // (edge) -> (facets on it, of which triangles)
        // an unlocked facet of one triangle: locked facets (curved surfaces) get no points and
        // keep their own rules
        let is_locked: std::collections::HashSet<u32> = locked.iter().copied().collect();
        let mut on: HashMap<(u32, u32), (u32, u32)> = HashMap::new();
        for (fi, loops) in plc.facets.iter().enumerate() {
            let tri = loops.len() == 1 && loops[0].len() == 3 && !is_locked.contains(&(fi as u32));
            for lp in loops {
                for i in 0..lp.len() {
                    let e = on.entry(ekey(lp[i], lp[(i + 1) % lp.len()])).or_insert((0, 0));
                    e.0 += 1;
                    e.1 += tri as u32;
                }
            }
        }
        b.plc.rec.chains.iter().map(|ch| {
            on.get(&ekey(ch[0], ch[ch.len() - 1])).is_some_and(|&(n, t)| n > 0 && n == t)
        }).collect()
    };
    for ch in &b.plc.rec.chains {
        let (a, z) = (ch[0], ch[ch.len() - 1]);
        if a != z {
            seg_ends[a as usize].push(z);
            seg_ends[z as usize].push(a);
        }
    }
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
    let mut locked_facet = vec![false; plc.facets.len()];
    let mut locked_edge: std::collections::HashSet<(u32, u32)> = std::collections::HashSet::new();
    for &fi in locked {
        let Some(f) = plc.facets.get(fi as usize) else { return Err(format!("locked facet {fi} does not exist")) };
        locked_facet[fi as usize] = true;
        for lp in f {
            for j in 0..lp.len() {
                locked_edge.insert(ekey(lp[j], lp[(j + 1) % lp.len()]));
            }
        }
    }
    let mut chain_of: HashMap<(u32, u32), Vec<u32>> = HashMap::new();
    for (c, ch) in b.plc.rec.chains.iter().enumerate() {
        chain_of.entry(ekey(ch[0], ch[ch.len() - 1])).or_default().push(c as u32);
    }
    let tri_vertex: Vec<bool> = {
        let (mut all, mut tri) = (vec![0u32; xyz.len()], vec![0u32; xyz.len()]);
        for (c, ch) in b.plc.rec.chains.iter().enumerate() {
            for z in [ch[0], ch[ch.len() - 1]] {
                all[z as usize] += 1;
                tri[z as usize] += tri_chain[c] as u32;
            }
        }
        (0..plc.points.len()).map(|v| all[v] > 0 && all[v] == tri[v]).collect()
    };
    let mut st = State {
        g, cx, xyz, rins, inside, hsz, sub, seg, chains: b.plc.rec.chains.clone(), chain_of, small_apex, seg_ends, tri_chain, tri_vertex, clean_faces: std::collections::HashSet::with_hasher(FastKey), clean_e32: std::collections::HashSet::with_hasher(FastKey), clean_er: std::collections::HashSet::with_hasher(FastKey), track_clean: false, fverts, fedges, locked_facet, locked_edge, splitting: Vec::new(), frame, opt, stats: RefineStats::default(),
        segq: VecDeque::new(), subq: VecDeque::new(), tetq: BinaryHeap::new(), dihq: BinaryHeap::new(), n: MixedCounters::default(),
        size,
        _p: std::marker::PhantomData,
    };
    // the tetrahedra outside the domain (the rest of the convex hull and the holes) take no
    // part: every face between them and the domain is a subfacet, so without them the
    // domain's boundary is a hull boundary, as a convex domain's always is. Kept, their
    // filling had to be retriangulated around every facet point on the boundary, where its
    // flat, non-Delaunay tetrahedra (grid points, coplanar sets) left no star-shaped cavity
    for t in 0..st.cx.tets.len() as u32 {
        if st.cx.alive[t as usize] && !st.inside[t as usize] {
            st.cx.remove(t);
        }
    }
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
    let mut retries: HashMap<[u32; 4], u8> = HashMap::new();
    loop {
        if let Some(e) = st.segq.pop_front() {
            if st.seg.contains_key(&e) {
                let mut enc = st.segment_encroacher(e);
                if let Some(w) = enc {
                    // small-angle rule for subsegments: a vertex on another segment that meets
                    // e's segment at a small input angle encroaches e only because of that angle
                    // (the boundary is already recovered, so e needs no conforming split)
                    if st.spans_small_angle(w, e.0) && st.spans_small_angle(w, e.1) {
                        st.stats.exempt += 1;
                        enc = None;
                    }
                }
                if let Some(w) = enc {
                    if st.seg.get(&e).is_some_and(|&c| st.facets_at(w).iter().any(|&fi| st.seg_facet_small(c, fi))) {
                        st.stats.exempt += 1;
                        enc = None;
                    }
                }
                if enc.is_some() || st.segment_too_long(e) {
                    st.split_segment(e)?;
                }
            }
            continue;
        }
        if let Some(f) = st.subq.pop_front() {
            if st.sub.contains_key(&f) {
                if let Some(w) = st.encroacher(f) {
                    if st.small_angle(w, &f) || st.subfacet_exempt(f, w) || st.seg_facet_exempt(w, &f) {
                        st.stats.exempt_faces += 1;
                    } else {
                        st.split_subfacet(f)?;
                    }
                } else if st.subfacet_too_large(f) || st.subfacet_skinny(f) {
                    st.split_subfacet(f)?;
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
                    // a rejected circumcentre split a subsegment or subfacet that left t: retry t,
                    // a few times only (a circumcentre on a facet whose splits never reach t
                    // would otherwise split ever smaller subfacets around one point)
                    let n = retries.entry(s).or_insert(0u8);
                    *n += 1;
                    if *n <= MAX_RETRIES {
                        st.queue_tet(t);
                    } else {
                        st.stats.exempt += 1;
                    }
                }
            }
            continue;
        }
        // M6 step 1: slivers, once nothing else is left, within the cap
        if let Some((_, std::cmp::Reverse(s), t)) = st.dihq.pop() {
            if sliver_budget.is_none() {
                // the points refinement inserted, with the input vertices of triangle surfaces (the
                // polygon path inserts those as facet points)
                let base = st.g.s.len() + st.tri_vertex.iter().filter(|&&x| x).count();
                sliver_budget = Some(((base as f64) * SLIVER_CAP).ceil() as u32);
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
            let hs = st.size_at(hs, &c);
            // the filter leaves small slivers to the perturbation, which moves volume vertices
            // only: a sliver with none (its vertices all on the boundary, as across a layer
            // thinner than h) is split whatever its size
            // ... and so is a sliver at an input vertex of a triangle surface, which the
            // perturbation cannot move (the polygon path has a facet point there, which slides)
            let fixed = st.cx.tets[t as usize].iter().all(|&q| !st.movable(q))
                || st.cx.tets[t as usize].iter().any(|&q| !st.movable(q) && st.on_tri_surface(q));
            if r < SLIVER_FILTER * st.opt.alpha * hs && !fixed {
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
    if std::env::var("MESHLOOM_DIAG").is_ok() {
        let (mut faces, mut bad) = (0u64, 0u64);
        for t in 0..st.cx.tets.len() as u32 {
            if !st.cx.alive[t as usize] || !st.inside[t as usize] { continue; }
            let w = st.cx.tets[t as usize];
            for i in 0..4 {
                let k = key(face(&w, i));
                if st.sub.contains_key(&k) { continue; }
                let u = st.cx.neighbor(t, &k);
                if u == NONE || u < t || !st.inside[u as usize] { continue; }
                faces += 1;
                let o = *st.cx.tets[u as usize].iter().find(|x| !k.contains(x)).unwrap();
                if st.g.insphere_sos([w[0], w[1], w[2], w[3], o]) > 0 { bad += 1; }
            }
        }
        eprintln!("DIAG interior faces {faces} non-Delaunay {bad}");
    }
    for _ in 0..2 {
        st.perturb_slivers();
        st.flip_improve();
        st.smooth();
        st.slide_facets();
        st.slide_segments();
        st.flip_improve();
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
