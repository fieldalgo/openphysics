// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

//! Facet recovery by cavity gift-wrapping, and the CDT verifier (M4 stage 4b of the
//! pre-registered 3D plan; design note section 4).
//!
//! After segment recovery every subfacet's edges on segments are edges of the
//! tetrahedralization, but a subfacet itself may not be a face. For each connected
//! region R of missing subfacets of one facet (plane P):
//! 1. **Cavity.** The tetrahedra whose interiors meet the interior of R are removed.
//!    The boundary of R consists of edges of the tetrahedralization (segment pieces
//!    and edges of subfacets that are faces), so no edge or vertex lies inside a
//!    cross-section: a tetrahedron crosses R exactly when a crossing point of one of
//!    its edges lies in a subfacet of R. A face lying in P inside R that is not a
//!    subfacet removes both its tetrahedra too.
//! 2. **Fill.** R splits the cavity into an upper and a lower half. Each half is
//!    filled by gift-wrapping from its boundary: the cavity faces on its side, the
//!    subfacets of R facing it and the constraint faces inside it (both sides). For
//!    a front face the new apex is, among the cavity vertices on that side that see
//!    it, the one whose sphere through the face holds no other (exact insphere with
//!    the index-ordered perturbation), so both halves make the same choices whatever
//!    the order of the front. A candidate whose tetrahedron would cross the front,
//!    hold a cavity vertex, or put a face into P that is not a subfacet is skipped.
//! 3. **Enlargement.** A cavity face between a new and a kept tetrahedron that is not
//!    a constraint and not locally Delaunay takes the kept tetrahedron into the
//!    cavity when that tetrahedron lies on one side of P, and the region is filled
//!    again. A face whose kept tetrahedron crosses P is counted as blocked (the
//!    Si–Gärtner gap) and left to the verifier.
//!
//! Every test is an exact orient3d or insphere over input and S points (`MixedPoints`).
//! The verifier checks the result from the arrays: positive tetrahedra, faces shared
//! by at most two on opposite sides, the hull unchanged, every vertex used, every
//! subfacet a face, every sub-segment piece an edge, and every interior face that is
//! not a subfacet locally Delaunay (the constrained Delaunay characterisation).

use std::collections::{HashMap, HashSet};

use crate::delaunay::Geom;
use crate::mixed::{MixedCounters, MixedPoints};
use crate::predicates::P3;

pub(crate) const NONE: u32 = u32::MAX;
/// For each vertex slot i of a positive tetrahedron, its opposite face oriented so
/// that the tetrahedron lies on the positive side.
pub(crate) const INWARD: [[usize; 3]; 4] = [[1, 3, 2], [0, 2, 3], [0, 3, 1], [0, 1, 2]];

#[derive(Debug, Clone, Copy, Default)]
pub struct FacetStats {
    /// missing regions filled (one per connected set of missing subfacets of a facet)
    pub regions: u32,
    pub removed: u32,
    pub created: u32,
    /// kept tetrahedra taken into a cavity across a face that was not locally Delaunay
    pub enlargements: u32,
    /// such faces whose kept tetrahedron crosses the facet plane (not enlarged)
    pub blocked: u32,
    /// gift-wrap apex choices
    pub apexes: u64,
    pub largest_cavity: u32,
    /// cavity sides filled by the Delaunay fast path, and by gift-wrapping
    pub fast: u32,
    pub wrapped: u32,
}

pub(crate) fn key(f: [u32; 3]) -> [u32; 3] {
    let mut k = f;
    k.sort_unstable();
    k
}

fn rotate_min(f: [u32; 3]) -> [u32; 3] {
    let i = (0..3).min_by_key(|&i| f[i]).unwrap();
    [f[i], f[(i + 1) % 3], f[(i + 2) % 3]]
}

pub(crate) fn face(t: &[u32; 4], i: usize) -> [u32; 3] {
    INWARD[i].map(|j| t[j])
}

pub(crate) struct Complex {
    pub(crate) tets: Vec<[u32; 4]>,
    pub(crate) alive: Vec<bool>,
    pub(crate) faces: HashMap<[u32; 3], [u32; 2]>,
    pub(crate) star: Vec<Vec<u32>>,
}

impl Complex {
    pub(crate) fn new(n: usize, tets: &[[u32; 4]]) -> Complex {
        let mut c = Complex { tets: Vec::new(), alive: Vec::new(), faces: HashMap::new(), star: vec![Vec::new(); n] };
        for t in tets {
            c.add(*t);
        }
        c
    }

    pub(crate) fn add(&mut self, v: [u32; 4]) -> u32 {
        let id = self.tets.len() as u32;
        self.tets.push(v);
        self.alive.push(true);
        for i in 0..4 {
            let e = self.faces.entry(key(face(&v, i))).or_insert([NONE, NONE]);
            if e[0] == NONE { e[0] = id } else { e[1] = id }
            self.star[v[i] as usize].push(id);
        }
        id
    }

    pub(crate) fn remove(&mut self, t: u32) {
        self.alive[t as usize] = false;
        let v = self.tets[t as usize];
        for i in 0..4 {
            let k = key(face(&v, i));
            let e = self.faces.get_mut(&k).unwrap();
            if e[0] == t { e[0] = e[1] }
            e[1] = NONE;
            if e[0] == NONE {
                self.faces.remove(&k);
            }
        }
        for x in v {
            let alive = &self.alive;
            self.star[x as usize].retain(|&s| alive[s as usize]);
        }
    }

    pub(crate) fn neighbor(&self, t: u32, k: &[u32; 3]) -> u32 {
        match self.faces.get(k) {
            Some(e) if e[0] == t => e[1],
            Some(e) => e[0],
            None => NONE,
        }
    }

    pub(crate) fn live(&self) -> Vec<[u32; 4]> {
        self.tets.iter().zip(&self.alive).filter(|(_, &a)| a).map(|(t, _)| *t).collect()
    }
}

/// Exact geometric context of one missing region.
struct Region<'a> {
    plane: [u32; 3],
    axis: usize,
    tris: &'a [[u32; 3]],
    keys: HashSet<[u32; 3]>,
    side: HashMap<u32, i8>,
}

impl Region<'_> {
    fn side(&mut self, g: &mut MixedPoints, v: u32) -> i8 {
        if let Some(&s) = self.side.get(&v) {
            return s;
        }
        let p = self.plane;
        let s = if p.contains(&v) { 0 } else { g.orient3d([p[0], p[1], p[2], v]) };
        self.side.insert(v, s);
        s
    }

    /// True when the interior of tetrahedron `v` meets the interior of the region.
    fn crosses(&mut self, g: &mut MixedPoints, constraints: &HashSet<[u32; 3]>, v: [u32; 4]) -> bool {
        let s = v.map(|x| self.side(g, x));
        if let (Some(i), Some(j)) = (s.iter().position(|&x| x > 0), s.iter().position(|&x| x < 0)) {
            let (u, w) = (v[i], v[j]);
            return self.tris.iter().any(|t| {
                let o = [g.orient3d([u, w, t[0], t[1]]), g.orient3d([u, w, t[1], t[2]]), g.orient3d([u, w, t[2], t[0]])];
                o.iter().all(|&x| x >= 0) || o.iter().all(|&x| x <= 0)
            });
        }
        // a face in the plane that is not a subfacet and overlaps the region
        (0..4).any(|i| {
            let f = face(&v, i);
            (0..3).all(|k| s[INWARD[i][k]] == 0)
                && !constraints.contains(&key(f))
                && self.tris.iter().any(|t| overlap_2d(g, self.axis, &f, t))
        })
    }
}

/// True when two triangles in one plane have overlapping interiors (exact projected
/// orientations; no separating edge line).
fn overlap_2d(g: &MixedPoints, axis: usize, a: &[u32; 3], b: &[u32; 3]) -> bool {
    let m = g.view();
    let mut n = MixedCounters::default();
    let o = |p: u32, q: u32, r: u32, n: &mut MixedCounters| m.orient2d_proj(axis, [p, q, r].map(|i| m.from_id(i)), n);
    for (x, y) in [(a, b), (b, a)] {
        for i in 0..3 {
            let (p, q, r) = (x[i], x[(i + 1) % 3], x[(i + 2) % 3]);
            let sr = o(p, q, r, &mut n);
            if y.iter().all(|&z| o(p, q, z, &mut n) * sr <= 0) {
                return false;
            }
        }
    }
    true
}

/// True when segment u-v meets triangle abc away from shared vertices (it passes
/// through the triangle's interior, an edge or a vertex while its ends are strictly
/// on opposite sides of the triangle's plane).
fn seg_tri(g: &mut MixedPoints, u: u32, v: u32, t: &[u32; 3]) -> bool {
    if t.contains(&u) || t.contains(&v) {
        return false;
    }
    let (s1, s2) = (g.orient3d([t[0], t[1], t[2], u]), g.orient3d([t[0], t[1], t[2], v]));
    if s1 * s2 >= 0 {
        return false;
    }
    let o = [g.orient3d([u, v, t[0], t[1]]), g.orient3d([u, v, t[1], t[2]]), g.orient3d([u, v, t[2], t[0]])];
    o.iter().all(|&x| x >= 0) || o.iter().all(|&x| x <= 0)
}

/// The front of one half-cavity: oriented faces (cavity to fill on the positive side),
/// grouped by vertex set (a constraint face inside the cavity is there twice).
#[derive(Default)]
struct Front {
    faces: HashMap<[u32; 3], Vec<[u32; 3]>>,
    order: Vec<[u32; 3]>,
}

impl Front {
    fn push(&mut self, f: [u32; 3]) {
        self.faces.entry(key(f)).or_default().push(rotate_min(f));
        self.order.push(key(f));
    }

    /// Removes the face with this orientation; true if it was there.
    fn take(&mut self, f: [u32; 3]) -> bool {
        let k = key(f);
        let r = rotate_min(f);
        if let Some(list) = self.faces.get_mut(&k) {
            if let Some(i) = list.iter().position(|x| *x == r) {
                list.swap_remove(i);
                if list.is_empty() {
                    self.faces.remove(&k);
                }
                return true;
            }
        }
        false
    }

    fn pop(&mut self) -> Option<[u32; 3]> {
        while let Some(k) = self.order.pop() {
            if let Some(list) = self.faces.get(&k) {
                let f = list[list.len() - 1];
                self.take(f);
                return Some(f);
            }
        }
        None
    }

    fn all(&self) -> impl Iterator<Item = &[u32; 3]> {
        self.faces.values().flatten()
    }
}

/// The cavity vertices of one side as a point set of their own (local index -> global
/// index), with the same exact predicates and the same perturbation by global index.
struct SubPoints<'a> {
    m: crate::mixed::Mixed<'a>,
    ids: &'a [u32],
    n: MixedCounters,
}

impl crate::delaunay::Geom for SubPoints<'_> {
    fn len(&self) -> usize {
        self.ids.len()
    }

    fn orient3d(&mut self, v: [u32; 4]) -> i8 {
        let p = v.map(|i| self.m.from_id(self.ids[i as usize]));
        self.m.orient3d(p, &mut self.n)
    }

    fn insphere_sos(&mut self, v: [u32; 5]) -> i8 {
        let p = v.map(|i| self.m.from_id(self.ids[i as usize]));
        self.m.insphere_sos(p, &mut self.n)
    }

    fn same(&self, a: u32, b: u32) -> bool {
        self.m.same(self.m.from_id(self.ids[a as usize]), self.m.from_id(self.ids[b as usize]))
    }

    fn collinear(&self, a: u32, b: u32, c: u32) -> bool {
        let p = [a, b, c].map(|i| self.m.from_id(self.ids[i as usize]));
        let mut n = MixedCounters::default();
        (0..3).all(|axis| self.m.orient2d_proj(axis, p, &mut n) == 0)
    }

    fn counters(&self) -> crate::predicates::Counters {
        self.n.input
    }
}

/// The fast path for one side of a cavity (design note section 4, step 2): the
/// Delaunay tetrahedralization of the side's vertices, of which the tetrahedra reached
/// from the inner side of the front without crossing it are kept. It succeeds only if
/// every front face is a face of that tetrahedralization and the kept tetrahedra are
/// bounded by exactly the front; otherwise None, and gift-wrapping fills the side.
fn fast_fill(g: &MixedPoints, front: &Front, verts: &[u32]) -> Option<Vec<[u32; 4]>> {
    if verts.len() < 4 {
        return None;
    }
    let m = g.view();
    let coords: Vec<P3> = verts.iter().map(|&v| m.rounded(m.from_id(v))).collect();
    let order = crate::delaunay::brio_order(&coords);
    let sub = SubPoints { m: g.view(), ids: verts, n: MixedCounters::default() };
    let mesh = crate::delaunay::Mesh::build(sub, &order, false).ok()?;
    let tets: Vec<[u32; 4]> = mesh.tets().iter().map(|t| t.map(|i| verts[i as usize])).collect();
    // oriented faces of the tetrahedralization: rotate_min(inward face) -> tetrahedron
    let mut by_face: HashMap<[u32; 3], usize> = HashMap::with_capacity(4 * tets.len());
    for (i, v) in tets.iter().enumerate() {
        for k in 0..4 {
            by_face.insert(rotate_min(face(v, k)), i);
        }
    }
    let walls: HashSet<[u32; 3]> = front.all().map(|f| key(*f)).collect();
    let mut keep = vec![false; tets.len()];
    let mut stack = Vec::new();
    for f in front.all() {
        let t = *by_face.get(&rotate_min(*f))?; // the tetrahedron on the front face's inner side
        if !keep[t] {
            keep[t] = true;
            stack.push(t);
        }
    }
    while let Some(t) = stack.pop() {
        let v = tets[t];
        for k in 0..4 {
            let f = face(&v, k);
            if walls.contains(&key(f)) {
                continue;
            }
            // the neighbour across f holds f with the opposite orientation
            let u = *by_face.get(&rotate_min([f[0], f[2], f[1]]))?; // a hull face: the cavity leaks
            if !keep[u] {
                keep[u] = true;
                stack.push(u);
            }
        }
    }
    let out: Vec<[u32; 4]> = tets.iter().zip(&keep).filter(|(_, &k)| k).map(|(t, _)| *t).collect();
    // the kept tetrahedra must be bounded by exactly the front (each front face once)
    let mut bound: HashMap<[u32; 3], u32> = HashMap::new();
    for v in &out {
        for k in 0..4 {
            *bound.entry(rotate_min(face(v, k))).or_default() += 1;
        }
    }
    let mut outer: Vec<[u32; 3]> = bound.keys().filter(|f| !bound.contains_key(&rotate_min([f[0], f[2], f[1]])))
        .copied().collect();
    let mut want: Vec<[u32; 3]> = front.all().map(|f| rotate_min(*f)).collect();
    // a constraint face inside the side is in the front twice; its two sides are both kept
    outer.sort_unstable();
    want.retain(|f| !front.faces.get(&key(*f)).is_some_and(|l| l.len() == 2));
    want.sort_unstable();
    if outer != want {
        return None;
    }
    Some(out)
}

/// Fills one half (sigma = +1 above the plane, -1 below) of the cavity `cav`.
fn fill_half(g: &mut MixedPoints, cx: &Complex, cav: &HashSet<u32>, reg: &mut Region, constraints: &HashSet<[u32; 3]>,
             sigma: i8, stats: &mut FacetStats, fast: bool) -> Result<Vec<[u32; 4]>, String> {
    let mut front = Front::default();
    let mut verts: Vec<u32> = Vec::new();
    let mut cav_sorted: Vec<u32> = cav.iter().copied().collect();
    cav_sorted.sort_unstable();
    for &t in &cav_sorted {
        let v = cx.tets[t as usize];
        for i in 0..4 {
            if sigma * reg.side(g, v[i]) >= 0 {
                verts.push(v[i]);
            }
            let f = face(&v, i);
            let k = key(f);
            let nb = cx.neighbor(t, &k);
            let s = f.map(|x| reg.side(g, x));
            let here = s.iter().any(|&x| sigma * x > 0);
            let there = s.iter().any(|&x| sigma * x < 0);
            if nb != NONE && cav.contains(&nb) {
                // inside the cavity: only a constraint face stays, on both sides
                if constraints.contains(&k) && t < nb {
                    if here && there {
                        return Err(format!("constraint face {k:?} crosses the facet plane inside a cavity"));
                    }
                    if !here && !there {
                        let up = reg.side(g, v[i]) * sigma > 0;
                        front.push(if up { f } else { [f[0], f[2], f[1]] });
                    } else if here {
                        front.push(f);
                        front.push([f[0], f[2], f[1]]);
                    }
                }
                continue;
            }
            if here && there {
                return Err(format!("cavity face {k:?} crosses the facet plane"));
            }
            if here || (!there && sigma * reg.side(g, v[i]) > 0) {
                front.push(f);
            }
        }
    }
    // the region's subfacets, facing this half
    let probe = *verts.iter().find(|&&x| reg.side(g, x) != 0).ok_or("a cavity has no vertex off the facet plane")?;
    let ps = reg.side(g, probe);
    for t in reg.tris.to_vec() {
        let agree = g.orient3d([t[0], t[1], t[2], probe]) * ps;
        front.push(if agree * sigma > 0 { t } else { [t[0], t[2], t[1]] });
    }
    verts.sort_unstable();
    verts.dedup();
    if let Some(out) = fast.then(|| fast_fill(g, &front, &verts)).flatten() {
        stats.fast += 1;
        return Ok(out);
    }
    stats.wrapped += 1;
    let limit = 64 + 8 * verts.len() * verts.len();
    let mut out = Vec::new();
    while let Some(f) = front.pop() {
        if out.len() > limit {
            return Err("gift-wrapping did not close the cavity".into());
        }
        let mut best: Option<u32> = None;
        for &q in &verts {
            if f.contains(&q) || g.orient3d([f[0], f[1], f[2], q]) <= 0 {
                continue;
            }
            if let Some(p) = best {
                if g.insphere_sos([f[0], f[1], f[2], p, q]) <= 0 {
                    continue;
                }
            }
            if fits(g, reg, &front, &verts, [f[0], f[1], f[2], q]) {
                best = Some(q);
            }
        }
        stats.apexes += 1;
        let p = best.ok_or_else(|| format!("no tetrahedron fits cavity face {f:?}"))?;
        let t = [f[0], f[1], f[2], p];
        for i in 0..3 {
            let inward = face(&t, i);
            if !front.take(inward) {
                front.push([inward[0], inward[2], inward[1]]);
            }
        }
        out.push(t);
    }
    Ok(out)
}

/// True when tetrahedron `t` (positive, built on a front face) lies in the unfilled
/// part of its half-cavity.
fn fits(g: &mut MixedPoints, reg: &mut Region, front: &Front, verts: &[u32], t: [u32; 4]) -> bool {
    for i in 0..3 {
        let f = face(&t, i);
        if f.iter().all(|&x| reg.side(g, x) == 0) && !reg.keys.contains(&key(f)) {
            return false;
        }
    }
    for &x in verts {
        if !t.contains(&x) && (0..4).all(|i| {
            let f = face(&t, i);
            g.orient3d([f[0], f[1], f[2], x]) > 0
        }) {
            return false;
        }
    }
    let edges = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)];
    for w in front.all() {
        if edges.iter().any(|&(a, b)| seg_tri(g, t[a], t[b], w)) {
            return false;
        }
        for i in 0..4 {
            let f = face(&t, i);
            if (0..3).any(|k| seg_tri(g, w[k], w[(k + 1) % 3], &f)) {
                return false;
            }
        }
    }
    true
}

/// Recovers every subfacet of `subfacets` as a face of the tetrahedralization `tets`
/// (vertices: global indices of `g`). Returns the new tetrahedralization.
pub fn recover_facets(g: &mut MixedPoints, tets: &[[u32; 4]], subfacets: &[Vec<[u32; 3]>])
                      -> Result<(Vec<[u32; 4]>, FacetStats), String> {
    recover_facets_with(g, tets, subfacets, true)
}

/// As [`recover_facets`]; `fast = false` fills every cavity side by gift-wrapping.
pub fn recover_facets_with(g: &mut MixedPoints, tets: &[[u32; 4]], subfacets: &[Vec<[u32; 3]>], fast: bool)
                           -> Result<(Vec<[u32; 4]>, FacetStats), String> {
    let n = g.len();
    let mut cx = Complex::new(n, tets);
    let constraints: HashSet<[u32; 3]> = subfacets.iter().flatten().map(|t| key(*t)).collect();
    let mut stats = FacetStats::default();
    for _pass in 0..4 * (constraints.len() + 1) {
        let missing: Vec<(usize, [u32; 3])> = subfacets.iter().enumerate()
            .flat_map(|(f, ts)| ts.iter().map(move |t| (f, *t)))
            .filter(|(_, t)| !cx.faces.contains_key(&key(*t)))
            .collect();
        let Some(&(f0, t0)) = missing.first() else {
            return Ok((cx.live(), stats));
        };
        // the connected region of missing subfacets of facet f0 containing t0
        let same: Vec<[u32; 3]> = missing.iter().filter(|(f, _)| *f == f0).map(|(_, t)| *t).collect();
        let mut region = vec![t0];
        let mut used = vec![false; same.len()];
        used[same.iter().position(|t| *t == t0).unwrap()] = true;
        let mut i = 0;
        while i < region.len() {
            let r = region[i];
            for (j, t) in same.iter().enumerate() {
                if !used[j] && (0..3).filter(|&k| r.contains(&t[k])).count() == 2 {
                    used[j] = true;
                    region.push(*t);
                }
            }
            i += 1;
        }
        let axis = (0..3).find(|&a| {
            let m = g.view();
            m.orient2d_proj(a, t0.map(|x| m.from_id(x)), &mut MixedCounters::default()) != 0
        }).ok_or("a subfacet is degenerate")?;
        let mut reg = Region { plane: t0, axis, tris: &region, keys: region.iter().map(|t| key(*t)).collect(), side: HashMap::new() };
        // 1. the cavity
        let mut cav: HashSet<u32> = HashSet::new();
        let mut seen: HashSet<u32> = HashSet::new();
        let mut stack: Vec<u32> = Vec::new();
        let rverts: HashSet<u32> = region.iter().flatten().copied().collect();
        for &v in &rverts {
            for &t in &cx.star[v as usize] {
                if seen.insert(t) && reg.crosses(g, &constraints, cx.tets[t as usize]) {
                    cav.insert(t);
                    stack.push(t);
                }
            }
        }
        while let Some(t) = stack.pop() {
            let v = cx.tets[t as usize];
            for i in 0..4 {
                let nb = cx.neighbor(t, &key(face(&v, i)));
                if nb != NONE && seen.insert(nb) && reg.crosses(g, &constraints, cx.tets[nb as usize]) {
                    cav.insert(nb);
                    stack.push(nb);
                }
            }
        }
        if cav.is_empty() {
            return Err(format!("facet {f0}: a missing subfacet {t0:?} meets no tetrahedron"));
        }
        // 2-3. fill, enlarging across faces that are not locally Delaunay
        let new = loop {
            let mut new = fill_half(g, &cx, &cav, &mut reg, &constraints, 1, &mut stats, fast)
                .map_err(|e| format!("facet {f0}, above: {e}"))?;
            new.extend(fill_half(g, &cx, &cav, &mut reg, &constraints, -1, &mut stats, fast)
                .map_err(|e| format!("facet {f0}, below: {e}"))?);
            let apex: HashMap<[u32; 3], u32> = new.iter()
                .flat_map(|t| (0..4).map(move |i| (key(face(t, i)), t[i]))).collect();
            let mut grow = Vec::new();
            for &t in &cav {
                let v = cx.tets[t as usize];
                for i in 0..4 {
                    let k = key(face(&v, i));
                    let nb = cx.neighbor(t, &k);
                    if nb == NONE || cav.contains(&nb) || constraints.contains(&k) {
                        continue;
                    }
                    let w = *apex.get(&k).ok_or_else(|| format!("facet {f0}: cavity face {k:?} was not filled"))?;
                    let o = cx.tets[nb as usize];
                    if g.insphere_sos([o[0], o[1], o[2], o[3], w]) > 0 {
                        let s = o.map(|x| reg.side(g, x));
                        if s.iter().all(|&x| x >= 0) || s.iter().all(|&x| x <= 0) {
                            grow.push(nb);
                        } else {
                            stats.blocked += 1;
                        }
                    }
                }
            }
            if grow.is_empty() {
                break new;
            }
            for t in grow {
                if cav.insert(t) {
                    stats.enlargements += 1;
                }
            }
        };
        let old: HashSet<u32> = cav.iter().flat_map(|&t| cx.tets[t as usize]).collect();
        let got: HashSet<u32> = new.iter().flatten().copied().collect();
        if let Some(v) = old.iter().find(|v| !got.contains(v)) {
            return Err(format!("facet {f0}: vertex {v} was left inside a cavity"));
        }
        stats.regions += 1;
        stats.removed += cav.len() as u32;
        stats.created += new.len() as u32;
        stats.largest_cavity = stats.largest_cavity.max(cav.len() as u32);
        for t in cav {
            cx.remove(t);
        }
        for t in new {
            cx.add(t);
        }
    }
    Err("facet recovery made no progress".into())
}

#[derive(Debug, Clone, Copy, Default)]
pub struct CdtReport {
    pub tets: usize,
    pub constrained_faces: usize,
    pub delaunay_faces: usize,
    pub hull_faces: usize,
}

/// Checks that `tets` is a constrained Delaunay tetrahedralization of all `g`'s
/// points with every subfacet a face, every chain of `chains` a path of edges and
/// the hull faces `hull` (sorted vertex triples).
pub fn verify_cdt(g: &mut MixedPoints, tets: &[[u32; 4]], subfacets: &[Vec<[u32; 3]>], chains: &[Vec<u32>],
                  hull: &HashSet<[u32; 3]>) -> Result<CdtReport, String> {
    let n = g.len();
    let mut used = vec![false; n];
    let mut faces: HashMap<[u32; 3], Vec<(u32, u32)>> = HashMap::new();
    let mut edges: HashSet<(u32, u32)> = HashSet::new();
    for (t, v) in tets.iter().enumerate() {
        if v.iter().any(|&x| x as usize >= n) {
            return Err(format!("tetrahedron {t} has a vertex out of range"));
        }
        if g.orient3d(*v) <= 0 {
            return Err(format!("tetrahedron {t} is not positively oriented"));
        }
        for i in 0..4 {
            used[v[i] as usize] = true;
            faces.entry(key(face(v, i))).or_default().push((t as u32, v[i]));
            for j in i + 1..4 {
                edges.insert((v[i].min(v[j]), v[i].max(v[j])));
            }
        }
    }
    if let Some(v) = used.iter().position(|&u| !u) {
        return Err(format!("vertex {v} is in no tetrahedron"));
    }
    let constraints: HashSet<[u32; 3]> = subfacets.iter().flatten().map(|t| key(*t)).collect();
    let mut r = CdtReport { tets: tets.len(), ..Default::default() };
    let mut hull_now = HashSet::new();
    for (k, list) in &faces {
        match list.as_slice() {
            [_] => {
                hull_now.insert(*k);
            }
            [(t1, w1), (_, w2)] => {
                let a = tets[*t1 as usize];
                if g.orient3d([k[0], k[1], k[2], *w1]) * g.orient3d([k[0], k[1], k[2], *w2]) >= 0 {
                    return Err(format!("face {k:?}: its two tetrahedra are on one side"));
                }
                if constraints.contains(k) {
                    r.constrained_faces += 1;
                } else if g.insphere_sos([a[0], a[1], a[2], a[3], *w2]) > 0 {
                    return Err(format!("face {k:?} is not a subfacet and is not locally Delaunay"));
                } else {
                    r.delaunay_faces += 1;
                }
            }
            _ => return Err(format!("face {k:?} is in more than two tetrahedra")),
        }
    }
    r.hull_faces = hull_now.len();
    if &hull_now != hull {
        return Err("the hull faces changed".into());
    }
    for k in &constraints {
        if !faces.contains_key(k) {
            return Err(format!("subfacet {k:?} is not a face"));
        }
    }
    for c in chains {
        for w in c.windows(2) {
            if !edges.contains(&(w[0].min(w[1]), w[0].max(w[1]))) {
                return Err(format!("segment piece {}-{} is not an edge", w[0], w[1]));
            }
        }
    }
    Ok(r)
}

/// Hull faces (sorted triples) of a tetrahedralization.
pub fn hull_faces(tets: &[[u32; 4]]) -> HashSet<[u32; 3]> {
    let mut count: HashMap<[u32; 3], u32> = HashMap::new();
    for v in tets {
        for i in 0..4 {
            *count.entry(key(face(v, i))).or_default() += 1;
        }
    }
    count.into_iter().filter(|(_, c)| *c == 1).map(|(k, _)| k).collect()
}

/// Boundary recovery of a PLC: check, segment recovery, subfacets, facet recovery,
/// then the CDT verifier.
pub struct Boundary {
    pub plc: crate::recovery::PlcRecovered,
    pub tets: Vec<[u32; 4]>,
    pub stats: FacetStats,
    pub report: CdtReport,
    pub mixed: MixedCounters,
}

pub fn recover_boundary(plc: &crate::plc::Plc, max_depth: u32) -> Result<Boundary, String> {
    let pr = crate::recovery::recover_plc(plc, max_depth)?;
    let mut g = MixedPoints::new(plc.points.clone());
    for s in &pr.rec.s {
        g.push(*s);
    }
    let hull = hull_faces(&pr.rec.tets);
    let (tets, stats) = recover_facets(&mut g, &pr.rec.tets, &pr.subfacets)?;
    let report = verify_cdt(&mut g, &tets, &pr.subfacets, &pr.rec.chains, &hull)?;
    Ok(Boundary { plc: pr, tets, stats, report, mixed: g.n })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::plc::Plc;

    /// Two stacked unit cubes with their interface at z = 1, and free points within
    /// 1e-6 to 1e-2 of it on both sides.
    fn stacked(extra: usize, seed: u64) -> Plc {
        let mut points = Vec::new();
        for z in 0..3 {
            for (x, y) in [(0, 0), (1, 0), (1, 1), (0, 1)] {
                points.push([x as f64, y as f64, z as f64]);
            }
        }
        let ring = |z: u32| (0..4).map(|k| 4 * z + k).collect::<Vec<u32>>();
        let mut facets = vec![vec![ring(0)], vec![ring(1)], vec![ring(2)]];
        for z in 0..2u32 {
            for k in 0..4u32 {
                let (a, b) = (4 * z + k, 4 * z + (k + 1) % 4);
                facets.push(vec![vec![a, b, b + 4, a + 4]]);
            }
        }
        let mut s = seed;
        let mut rnd = || {
            s = s.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
            (s >> 11) as f64 / (1u64 << 53) as f64
        };
        for k in 0..extra {
            let d = 10f64.powf(-6.0 + 4.0 * rnd());
            points.push([0.02 + 0.96 * rnd(), 0.02 + 0.96 * rnd(), 1.0 + if k % 2 == 0 { d } else { -d }]);
        }
        Plc { points, segments: Vec::new(), facets }
    }

    #[test]
    fn missing_subfacets_are_recovered_and_verified() {
        for seed in 1..6 {
            let plc = stacked(80, seed);
            let b = recover_boundary(&plc, 60).unwrap();
            assert!(!b.plc.missing.is_empty(), "seed {seed}: nothing to recover");
            assert!(b.stats.regions > 0 && b.stats.created > 0);
            assert_eq!(b.report.constrained_faces, 2, "the interface's two subfacets are interior faces");
        }
    }

    #[test]
    fn the_verifier_rejects_broken_results() {
        let plc = stacked(80, 3);
        let b = recover_boundary(&plc, 60).unwrap();
        let mut g = MixedPoints::new(plc.points.clone());
        for s in &b.plc.rec.s {
            g.push(*s);
        }
        let hull = hull_faces(&b.tets);
        let (sub, chains) = (&b.plc.subfacets, &b.plc.rec.chains);
        assert!(verify_cdt(&mut g, &b.tets, sub, chains, &hull).is_ok());
        // before facet recovery: a subfacet is not a face
        let e = verify_cdt(&mut g, &b.plc.rec.tets, sub, chains, &hull).unwrap_err();
        assert!(e.contains("subfacet"), "{e}");
        // a missing tetrahedron changes the hull
        let mut t = b.tets.clone();
        let interior = t.iter().position(|v| v.iter().all(|&x| x as usize >= 12)).unwrap();
        t.remove(interior);
        assert!(verify_cdt(&mut g, &t, sub, chains, &hull).is_err());
        // an inverted tetrahedron
        let mut t = b.tets.clone();
        t[0].swap(0, 1);
        assert!(verify_cdt(&mut g, &t, sub, chains, &hull).unwrap_err().contains("positively"));
        // a face that is not a subfacet and not locally Delaunay: the result without
        // the interface constraint is checked as if the interface were absent
        let mut no_interface = sub.clone();
        no_interface[1].clear();
        let e = verify_cdt(&mut g, &b.tets, &no_interface, chains, &hull).unwrap_err();
        assert!(e.contains("locally Delaunay"), "{e}");
    }

    #[test]
    fn fast_path_and_gift_wrapping_give_the_same_tetrahedralization() {
        // the constrained Delaunay tetrahedralization is unique under the perturbation
        for seed in 1..6 {
            let plc = stacked(120, seed);
            let pr = crate::recovery::recover_plc(&plc, 60).unwrap();
            let mut g = MixedPoints::new(plc.points.clone());
            for s in &pr.rec.s {
                g.push(*s);
            }
            let (fast, sf) = recover_facets_with(&mut g, &pr.rec.tets, &pr.subfacets, true).unwrap();
            let (slow, ss) = recover_facets_with(&mut g, &pr.rec.tets, &pr.subfacets, false).unwrap();
            assert!(sf.fast > 0 && sf.wrapped == 0 && ss.fast == 0 && ss.wrapped > 0);
            let canon = |t: &Vec<[u32; 4]>| {
                let mut v: Vec<[u32; 4]> = t.iter().map(|x| {
                    let mut y = *x;
                    y.sort_unstable();
                    y
                }).collect();
                v.sort_unstable();
                v
            };
            assert_eq!(canon(&fast), canon(&slow), "seed {seed}");
            let hull = hull_faces(&pr.rec.tets);
            verify_cdt(&mut g, &fast, &pr.subfacets, &pr.rec.chains, &hull).unwrap();
        }
    }
}
