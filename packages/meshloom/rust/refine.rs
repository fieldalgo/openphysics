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
}

struct State<'a> {
    g: MixedPoints,
    cx: Complex,
    xyz: Vec<P3>,
    inside: Vec<bool>,
    /// subfacet -> its facets (two where touching shells share it)
    sub: HashMap<[u32; 3], Vec<u32>>,
    /// subsegment -> chain index
    seg: HashMap<(u32, u32), u32>,
    chains: Vec<Vec<u32>>,
    /// per facet: three input points spanning its plane, and the projection axis
    frame: Vec<([u32; 3], usize)>,
    opt: RefineOptions,
    stats: RefineStats,
    segq: VecDeque<(u32, u32)>,
    subq: VecDeque<[u32; 3]>,
    tetq: BinaryHeap<(u64, std::cmp::Reverse<[u32; 4]>, u32)>,
    n: MixedCounters,
    _p: std::marker::PhantomData<&'a ()>,
}

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

    fn quality(&self, t: &[u32; 4]) -> Option<f64> {
        let p = t.map(|v| self.xyz[v as usize]);
        let c = circumcentre(p)?;
        let r = dot(&sub3(&c, &p[0]), &sub3(&c, &p[0])).sqrt();
        let mut lmin = f64::INFINITY;
        for i in 0..4 {
            for j in i + 1..4 {
                lmin = lmin.min(dot(&sub3(&p[i], &p[j]), &sub3(&p[i], &p[j])).sqrt());
            }
        }
        let mut bad: f64 = 0.0;
        if self.opt.ratio > 0.0 {
            bad = bad.max(r / lmin / self.opt.ratio);
        }
        if self.opt.h > 0.0 {
            bad = bad.max(r / (self.opt.alpha * self.opt.h));
        }
        (bad > 1.0).then_some(bad)
    }

    fn queue_tet(&mut self, t: u32) {
        if !self.inside[t as usize] {
            return;
        }
        let v = self.cx.tets[t as usize];
        if let Some(bad) = self.quality(&v) {
            let mut s = v;
            s.sort_unstable();
            self.tetq.push((bad.to_bits(), std::cmp::Reverse(s), t));
        }
    }

    fn encroached_segment(&mut self, e: (u32, u32)) -> bool {
        let around: Vec<u32> = self.cx.star[e.0 as usize].iter().copied()
            .filter(|&t| self.cx.alive[t as usize] && self.inside[t as usize] && self.cx.tets[t as usize].contains(&e.1))
            .collect();
        let m = self.g.view();
        around.iter().any(|&t| self.cx.tets[t as usize].iter()
            .filter(|&&w| w != e.0 && w != e.1)
            .any(|&w| m.in_diametral_ball(m.from_id(w), m.from_id(e.0), m.from_id(e.1))))
    }

    fn encroached_subfacet(&mut self, f: [u32; 3]) -> bool {
        let Some(o) = self.cx.faces.get(&f).copied() else { return false };
        let m = self.g.view();
        o.iter().filter(|&&t| t != NONE && self.inside[t as usize]).any(|&t| {
            let w = *self.cx.tets[t as usize].iter().find(|x| !f.contains(x)).unwrap();
            m.equatorial_sign(m.from_id(w), m.from_id(f[0]), m.from_id(f[1]), m.from_id(f[2])) < 0
        })
    }

    fn new_point(&mut self, sp: SPoint) -> u32 {
        let id = self.g.push(sp);
        let m = self.g.view();
        self.xyz.push(m.rounded(m.from_id(id)));
        self.cx.star.push(Vec::new());
        id
    }

    fn drop_point(&mut self, id: u32) {
        debug_assert_eq!(id as usize, self.xyz.len() - 1);
        self.g.s.pop();
        self.xyz.pop();
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
                    let w = self.cx.tets[u as usize];
                    self.g.insphere_sos([w[0], w[1], w[2], w[3], p]) > 0
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
        // ... and shrink it where it cannot grow: a tetrahedron (not a seed, which holds p)
        // with a boundary face p does not see strictly leaves the cavity (e.g. p on the
        // hull's plane, beyond a coplanar hull face); repeat, since that exposes its other
        // faces. What remains is star-shaped from p unless a seed is blocked, which the
        // insertion then refuses.
        let seedset: std::collections::HashSet<u32> = seeds.iter().copied().collect();
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
            let label = self.inside[t as usize];
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
                    if std::env::var_os("MESHLOOM_DEBUG_REFINE").is_some() {
                        let fl = self.sub.get(&k).cloned();
                        let segs: Vec<bool> = (0..3).map(|j| self.seg.contains_key(&ekey(k[j], k[(j + 1) % 3]))).collect();
                        let col: Vec<bool> = (0..3).map(|j| self.g.collinear(k[j], k[(j + 1) % 3], p)).collect();
                        eprintln!("DEBUG p {p} face {k:?} orient {o} sub {fl:?} segs {segs:?} collinear {col:?} cav {} plane {} u {}",
                                  cav.len(), plane.len(), u);
                    }
                    return Ok(false);
                }
                new.push((tet, label));
            }
        }
        let split_faces: Vec<([u32; 3], Vec<u32>)> = plane.iter().map(|k| (*k, self.sub[k].clone())).collect();
        for &t in cav {
            self.cx.remove(t);
        }
        let mut added = Vec::with_capacity(new.len());
        for (tet, label) in new {
            let id = self.cx.add(tet);
            if id as usize >= self.inside.len() {
                self.inside.resize(id as usize + 1, false);
            }
            self.inside[id as usize] = label;
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
            return Err(format!("refinement inserted more than {} points", self.opt.max_points));
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
        let tm = tu + (tv - tu) / 2.0;
        if !(tm > tu.min(tv) && tm < tu.max(tv)) {
            return Err(format!("refinement: subsegment {e:?} is too short to split"));
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

    /// Splits subfacet f at its circumcentre, or the subsegment it lies beyond.
    fn split_subfacet(&mut self, f: [u32; 3]) -> Result<(), String> {
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
                // beyond a subsegment of the facet: split the subsegment instead
                self.drop_point(p);
                self.stats.rejected += 1;
                return self.split_segment(ekey(ex, ey));
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
        let plane = self.plane_cavity(p, &[cur]);
        let seeds: Vec<u32> = plane.iter().flat_map(|k| self.cx.faces[k]).filter(|&t| t != NONE).collect();
        let cav = self.cavity(p, &seeds, &plane);
        let (_, es) = self.encroached_by(p, &cav);
        if let Some(&e) = es.first() {
            self.drop_point(p);
            self.stats.rejected += 1;
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
                return self.split_segment(e);
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
pub fn refine(plc: &crate::plc::Plc, b: &mut Boundary, opt: RefineOptions) -> Result<RefineStats, String> {
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
    let mut st = State {
        g, cx, xyz, inside, sub, seg, chains: b.plc.rec.chains.clone(), frame, opt, stats: RefineStats::default(),
        segq: VecDeque::new(), subq: VecDeque::new(), tetq: BinaryHeap::new(), n: MixedCounters::default(),
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
    loop {
        if let Some(e) = st.segq.pop_front() {
            if st.seg.contains_key(&e) && st.encroached_segment(e) {
                st.split_segment(e)?;
            }
            continue;
        }
        if let Some(f) = st.subq.pop_front() {
            if st.sub.contains_key(&f) && st.encroached_subfacet(f) {
                st.split_subfacet(f)?;
            }
            continue;
        }
        if let Some((_, std::cmp::Reverse(s), t)) = st.tetq.pop() {
            let mut v = st.cx.tets[t as usize];
            v.sort_unstable();
            if st.cx.alive[t as usize] && v == s && st.quality(&st.cx.tets[t as usize]).is_some() {
                st.split_tet(t)?;
            }
            continue;
        }
        break;
    }
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
