// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

//! Constrained Delaunay triangulation of one planar facet of a PLC.
//!
//! A facet is a set of loops of point indices (an outer loop and holes, combined by
//! the even-odd rule) whose points must be exactly coplanar. Orientation inside the
//! plane is the 2D orientation after dropping the axis along which the facet normal
//! is largest (exact; projection keeps orientation). Circle tests use
//! [`predicates::incircle_plane`], which is exact for the true in-plane circle, with
//! ties broken by the same index-ordered perturbation as the 3D kernel, so a facet
//! triangulation agrees with the tetrahedralization around it.
//!
//! The steps: Bowyer–Watson Delaunay triangulation of the loop points with a ghost
//! vertex, insertion of each missing loop edge by removing the triangles it crosses
//! and refilling the two sides by the recursive constrained-Delaunay polygon fill
//! (Anglada 1997), then even-odd labelling by flood fill from the ghosts. Facets are
//! small, so the data structure is a plain triangle list with linear scans.

use crate::predicates::{self as pr, P3};
use std::collections::{HashMap, HashSet};

const GHOST: u32 = u32::MAX;

/// A fast hasher for the small integer keys of the triangulation's lookup tables
/// (multiply-rotate, as in rustc's FxHash). A table that is iterated must give a
/// result that does not depend on the order (as with the standard, randomly seeded
/// hasher).
#[derive(Default, Clone, Copy)]
pub(crate) struct Fx(u64);

impl std::hash::Hasher for Fx {
    fn finish(&self) -> u64 {
        self.0
    }

    fn write(&mut self, bytes: &[u8]) {
        for &b in bytes {
            self.write_u64(b as u64);
        }
    }

    fn write_u32(&mut self, x: u32) {
        self.write_u64(x as u64);
    }

    fn write_u64(&mut self, x: u64) {
        self.0 = (self.0.rotate_left(5) ^ x).wrapping_mul(0x51_7c_c1_b7_27_22_0a_95);
    }

    fn write_usize(&mut self, x: usize) {
        self.write_u64(x as u64);
    }
}

pub(crate) type FxMap<K, V> = HashMap<K, V, std::hash::BuildHasherDefault<Fx>>;
pub(crate) type FxSet<K> = HashSet<K, std::hash::BuildHasherDefault<Fx>>;

#[derive(Debug)]
pub struct Facet {
    /// Triangles as global point indices, wound like the outer (first) loop.
    pub triangles: Vec<[u32; 3]>,
    /// The axis dropped for the in-plane predicates.
    pub axis: usize,
    /// True when the outer loop runs clockwise in that projection (the triangles are
    /// then wound clockwise too).
    pub flip: bool,
}

/// The in-plane predicates a facet triangulation needs, by point index: orientation
/// and the perturbed circle test in the projection along `axis`, and the order of
/// collinear points. Input points use [`Plain2`]; points on segments use
/// [`crate::mixed::Mixed`].
pub(crate) trait PlanePred {
    fn orient(&self, axis: usize, a: u32, b: u32, c: u32) -> i8;
    /// incircle_plane with the index-ordered perturbation.
    fn incircle_sos(&self, axis: usize, a: u32, b: u32, c: u32, d: u32) -> i8;
    /// For c collinear with a and b: c strictly between them.
    fn between(&self, axis: usize, a: u32, b: u32, c: u32) -> bool;
    /// For collinear v, x, y: x and y on the same side of v.
    fn same_direction(&self, axis: usize, v: u32, x: u32, y: u32) -> bool;
}

/// Input points: the expansion predicates and coordinate comparisons.
pub(crate) struct Plain2<'a> {
    pub pts: &'a [P3],
}

impl Plain2<'_> {
    fn xy(&self, axis: usize, v: u32) -> [f64; 2] {
        let (i, j) = pr::kept_axes(axis);
        [self.pts[v as usize][i], self.pts[v as usize][j]]
    }
}

impl PlanePred for Plain2<'_> {
    fn orient(&self, axis: usize, a: u32, b: u32, c: u32) -> i8 {
        let p = |v: u32| &self.pts[v as usize];
        pr::orient2d_proj(axis, p(a), p(b), p(c))
    }

    fn incircle_sos(&self, axis: usize, a: u32, b: u32, c: u32, d: u32) -> i8 {
        let p = |v: u32| &self.pts[v as usize];
        pr::incircle_plane_sos(axis, [p(a), p(b), p(c), p(d)], [a, b, c, d])
    }

    fn between(&self, axis: usize, a: u32, b: u32, c: u32) -> bool {
        let (pa, pb, pc) = (self.xy(axis, a), self.xy(axis, b), self.xy(axis, c));
        let k = if pa[0] != pb[0] { 0 } else { 1 };
        pc[k] > pa[k].min(pb[k]) && pc[k] < pa[k].max(pb[k])
    }

    fn same_direction(&self, axis: usize, v: u32, x: u32, y: u32) -> bool {
        let (pv, px, py) = (self.xy(axis, v), self.xy(axis, x), self.xy(axis, y));
        (0..2).any(|k| (px[k] - pv[k]).signum() * (py[k] - pv[k]).signum() > 0.0 && px[k] != pv[k] && py[k] != pv[k])
    }
}

/// The triangulation: triangle slots in creation order, of which the live ones (in
/// slot order) are the triangulation. A removed triangle leaves a dead slot and new
/// ones are appended, so the live order is the order a list that drops the removed
/// triangles and appends the new ones would have. Each directed edge of a live
/// triangle maps to its slot (the adjacency).
struct Tri<'a, P: PlanePred> {
    pred: &'a P,
    axis: usize,
    tris: Vec<[u32; 3]>, // counter-clockwise in the projection; ghosts as (a, b, GHOST)
    alive: Vec<bool>,
    edge: FxMap<(u32, u32), usize>,
    last: usize,
    points: Vec<u32>,
    constraints: HashSet<(u32, u32)>,
}

impl<'a, P: PlanePred> Tri<'a, P> {
    fn new(pred: &'a P, axis: usize, points: Vec<u32>) -> Tri<'a, P> {
        Tri { pred, axis, tris: Vec::new(), alive: Vec::new(), edge: FxMap::default(), last: 0, points,
              constraints: HashSet::new() }
    }

    fn add(&mut self, t: [u32; 3]) {
        let k = self.tris.len();
        self.tris.push(t);
        self.alive.push(true);
        for (u, v) in edges(&t) {
            self.edge.insert((u, v), k);
        }
        self.last = k;
    }

    fn kill(&mut self, k: usize) {
        self.alive[k] = false;
        for (u, v) in edges(&self.tris[k]) {
            if self.edge.get(&(u, v)) == Some(&k) {
                self.edge.remove(&(u, v));
            }
        }
    }

    /// The live triangles' slots, in order.
    fn live(&self) -> impl Iterator<Item = usize> + '_ {
        (0..self.tris.len()).filter(move |&k| self.alive[k])
    }

    /// A triangle in conflict with q: a visibility walk from the last new triangle,
    /// else (a walk that does not end in conflict) the first in slot order.
    fn seed(&self, q: u32) -> Option<usize> {
        let mut t = if self.alive.get(self.last) == Some(&true) { self.last } else { self.live().next()? };
        let mut steps = 0;
        'walk: while steps <= self.tris.len() {
            steps += 1;
            let tri = self.tris[t];
            if tri[2] != GHOST {
                for (u, v) in edges(&tri) {
                    if self.orient(u, v, q) < 0 {
                        match self.edge.get(&(v, u)) {
                            Some(&n) => {
                                t = n;
                                continue 'walk;
                            }
                            None => break 'walk,
                        }
                    }
                }
            }
            if self.conflict(t, q) {
                return Some(t);
            }
            if tri[2] == GHOST && steps == 1 {
                // a walk that starts at a ghost goes into the triangle across its edge
                if let Some(&n) = self.edge.get(&(tri[1], tri[0])) {
                    t = n;
                    continue;
                }
            }
            break;
        }
        self.live().find(|&t| self.conflict(t, q))
    }
    fn orient(&self, a: u32, b: u32, c: u32) -> i8 {
        self.pred.orient(self.axis, a, b, c)
    }

    /// True when c is strictly inside the circle of the counter-clockwise a, b, x under
    /// the perturbation.
    fn in_circle(&self, a: u32, b: u32, x: u32, c: u32) -> bool {
        self.pred.incircle_sos(self.axis, a, b, x, c) > 0
    }

    fn conflict(&self, t: usize, q: u32) -> bool {
        let [a, b, c] = self.tris[t];
        if c == GHOST {
            let o = self.orient(a, b, q);
            if o != 0 {
                return o > 0;
            }
            // on the hull line: the half-plane is the limit of the circle of the finite
            // triangle across the edge
            let n = self.edge[&(b, a)];
            return self.conflict(n, q);
        }
        self.in_circle(a, b, c, q)
    }

    /// The triangles in conflict with q, in slot order: the conflict region is
    /// connected across edges (it is star-shaped from q), so a search from one of them
    /// finds them all.
    fn cavity(&self, q: u32) -> Vec<usize> {
        let Some(s) = self.seed(q) else { return Vec::new() };
        let mut seen: FxSet<usize> = FxSet::default();
        seen.insert(s);
        let mut stack = vec![s];
        let mut out = Vec::new();
        while let Some(t) = stack.pop() {
            out.push(t);
            for (u, v) in edges(&self.tris[t]) {
                if let Some(&n) = self.edge.get(&(v, u)) {
                    if seen.insert(n) && self.conflict(n, q) {
                        stack.push(n);
                    }
                }
            }
        }
        out.sort_unstable();
        debug_assert_eq!(out, self.live().filter(|&t| self.conflict(t, q)).collect::<Vec<_>>());
        out
    }

    fn insert(&mut self, q: u32) -> Result<(), String> {
        let cavity = self.cavity(q);
        if cavity.is_empty() {
            return Err(format!("point {q} is in conflict with no triangle"));
        }
        let mut count: FxMap<(u32, u32), i32> = FxMap::default();
        for &t in &cavity {
            for (u, v) in edges(&self.tris[t]) {
                *count.entry((u.min(v), u.max(v))).or_default() += 1;
            }
        }
        let mut new = Vec::new();
        for &t in &cavity {
            for (u, v) in edges(&self.tris[t]) {
                if count[&(u.min(v), u.max(v))] == 1 {
                    new.push(ghost_last([u, v, q]));
                }
            }
        }
        for &t in &cavity {
            self.kill(t);
        }
        for t in new {
            self.add(t);
        }
        Ok(())
    }

    fn has_edge(&self, a: u32, b: u32) -> bool {
        self.edge.contains_key(&(a, b)) || self.edge.contains_key(&(b, a))
    }

    /// Inserts the constraint a-b. It may not pass through a point or cross another
    /// constraint: callers split edges at the points on them, and crossings are input
    /// errors found before triangulating.
    fn insert_edge(&mut self, a: u32, b: u32) -> Result<(), String> {
        // an edge of the triangulation holds no point inside it
        if self.has_edge(a, b) {
            self.constraints.insert((a.min(b), a.max(b)));
            return Ok(());
        }
        if let Some(&v) = self.points.iter().find(|&&v| v != a && v != b && self.orient(a, b, v) == 0 && strictly_between(self, a, b, v)) {
            return Err(format!("constraint {a}-{b} passes through point {v}"));
        }
        if self.has_edge(a, b) {
            self.constraints.insert((a.min(b), a.max(b)));
            return Ok(());
        }
        // triangles whose interior the open segment a-b crosses: those with an edge it
        // crosses properly
        let crossed: Vec<usize> = self.live()
            .filter(|&t| {
                let tri = self.tris[t];
                tri[2] != GHOST
                    && edges(&tri).any(|(u, v)| {
                        u != a && u != b && v != a && v != b
                            && self.orient(a, b, u) * self.orient(a, b, v) < 0
                            && self.orient(u, v, a) * self.orient(u, v, b) < 0
                    })
            })
            .collect();
        if crossed.is_empty() {
            return Err(format!("constraint {a}-{b} crosses no triangle and is not an edge"));
        }
        for &t in &crossed {
            for (u, v) in edges(&self.tris[t]) {
                if self.constraints.contains(&(u.min(v), u.max(v)))
                    && self.orient(a, b, u) * self.orient(a, b, v) < 0
                    && self.orient(u, v, a) * self.orient(u, v, b) < 0
                {
                    return Err(format!("constraints {a}-{b} and {u}-{v} cross"));
                }
            }
        }
        // boundary of the removed region, as directed edges in counter-clockwise order
        let mut count: HashMap<(u32, u32), i32> = HashMap::new();
        for &t in &crossed {
            for (u, v) in edges(&self.tris[t]) {
                *count.entry((u.min(v), u.max(v))).or_default() += 1;
            }
        }
        let mut next: HashMap<u32, u32> = HashMap::new();
        for &t in &crossed {
            for (u, v) in edges(&self.tris[t]) {
                if count[&(u.min(v), u.max(v))] == 1 && next.insert(u, v).is_some() {
                    return Err(format!("constraint {a}-{b}: the crossed region is not a simple polygon"));
                }
            }
        }
        let chain = |from: u32, to: u32| -> Result<Vec<u32>, String> {
            let mut out = Vec::new();
            let mut v = *next.get(&from).ok_or("broken cavity boundary")?;
            while v != to {
                out.push(v);
                v = *next.get(&v).ok_or("broken cavity boundary")?;
                if out.len() > next.len() {
                    return Err("cavity boundary does not close".into());
                }
            }
            Ok(out)
        };
        let below = chain(a, b)?; // counter-clockwise from a to b runs right of a-b
        let above = chain(b, a)?;
        let mut fill = Vec::new();
        self.fill(b, a, &below, &mut fill); // b-a with the lower chain on its left
        self.fill(a, b, &above, &mut fill);
        for &t in &crossed {
            self.kill(t);
        }
        for t in fill {
            self.add(t);
        }
        self.constraints.insert((a.min(b), a.max(b)));
        Ok(())
    }

    /// Constrained Delaunay fill of the pseudo-polygon a, chain..., b lying left of a-b
    /// (Anglada 1997): the chain vertex whose circle with a, b holds no other chain
    /// vertex makes the triangle; recurse on both sides.
    fn fill(&self, a: u32, b: u32, chain: &[u32], out: &mut Vec<[u32; 3]>) {
        if chain.is_empty() {
            return;
        }
        let mut c = 0;
        for k in 1..chain.len() {
            if self.in_circle(a, b, chain[c], chain[k]) {
                c = k;
            }
        }
        out.push([a, b, chain[c]]);
        // the chain runs from b back to a; vertices before c lie next to b
        self.fill(chain[c], b, &chain[..c], out);
        self.fill(a, chain[c], &chain[c + 1..], out);
    }
}

fn edges(t: &[u32; 3]) -> impl Iterator<Item = (u32, u32)> + '_ {
    (0..3).map(move |i| (t[i], t[(i + 1) % 3]))
}

fn ghost_last(t: [u32; 3]) -> [u32; 3] {
    match t.iter().position(|&v| v == GHOST) {
        Some(0) => [t[1], t[2], t[0]],
        Some(1) => [t[2], t[0], t[1]],
        _ => t,
    }
}

/// Exact sign of the projected signed area of a loop.
fn loop_orientation(pts: &[P3], axis: usize, lp: &[u32]) -> i8 {
    let (i, j) = pr::kept_axes(axis);
    let coords: Vec<[f64; 2]> = lp.iter().map(|&v| [pts[v as usize][i], pts[v as usize][j]]).collect();
    pr::polygon_area_sign(&coords)
}

/// Why an input is refused: the message, and the witness type of the import validity
/// rule (lab protocol section 4) when the refusal is one: 1 a coordinate outside the
/// kernel's range, 2 a repeated vertex in a facet, 3 a degenerate, non-planar or
/// non-simple facet, 4 two facets with the same vertices, 5 two cells whose intersection
/// is not a union of cells, 0 no facets. `None` for malformed arrays (an index that
/// does not exist, coincident points).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct InputError {
    pub witness: Option<u8>,
    pub msg: String,
    /// What the witness names, for a checker to confirm it.
    pub detail: Detail,
}

/// The cells a refusal names. Points of type 5 are given by the pieces whose exact
/// intersection holds them, so that they stay exact rationals.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub enum Detail {
    #[default]
    None,
    NoFacets,
    Vertex(u32),
    Facet(u32),
    /// Two facets (type 4, or type 5 with `at`).
    Facets(u32, u32),
    /// Type 5: two cells (facets when the cells lie in facets) and the pieces in whose
    /// intersection the witness point lies.
    Point { cells: (CellRef, CellRef), at: At },
}

/// A cell named by a witness: a facet, or a free segment by its end points.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CellRef {
    Facet(u32),
    Segment([u32; 2]),
}

/// Where a type-5 witness point lies: the centroid of a piece shared by the two facets
/// without a cell of both covering it, or in the intersection of two crossing pieces.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum At {
    Centroid(Vec<u32>),
    SegSeg([u32; 2], [u32; 2]),
    SegTri([u32; 2], [u32; 3]),
    TriTri([u32; 3], [u32; 3]),
}

impl InputError {
    pub fn new(witness: Option<u8>, msg: impl Into<String>) -> Self {
        InputError { witness, msg: msg.into(), detail: Detail::None }
    }

    pub fn with(mut self, detail: Detail) -> Self {
        self.detail = detail;
        self
    }
}

impl std::fmt::Display for InputError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.msg)
    }
}

/// The kernel's range check, as witness type 1 (too many points is not a witness).
pub(crate) fn check_points(pts: &[P3]) -> Result<(), InputError> {
    crate::delaunay::check_input(pts).map_err(|e| match e {
        crate::delaunay::Error::Domain(i) => InputError::new(Some(1), e.to_string()).with(Detail::Vertex(i as u32)),
        _ => InputError::new(None, e.to_string()),
    })
}

/// Constrained Delaunay triangulation of the facet bounded by `loops`.
pub fn triangulate(pts: &[P3], loops: &[Vec<u32>]) -> Result<Facet, InputError> {
    triangulate_with(pts, loops, &[], &[])
}

/// Constrained Delaunay triangulation of the facet bounded by `loops`, with more points
/// of its plane (`extra_points`) and more constraint edges between them
/// (`extra_edges`), as a PLC needs for the vertices and edges that lie on a facet. Loop
/// edges are split at the extra points on them; only loop edges bound the facet (even-odd),
/// so extra points and edges outside it change nothing inside. Extra edges may not pass
/// through a point or cross each other or a loop edge.
pub fn triangulate_with(pts: &[P3], loops: &[Vec<u32>], extra_points: &[u32], extra_edges: &[(u32, u32)])
                        -> Result<Facet, InputError> {
    if loops.is_empty() {
        return Err(InputError::new(None, "a facet needs at least one loop".to_string()));
    }
    check_points(pts)?;
    triangulate_checked(pts, loops, extra_points, extra_edges)
}

/// [`triangulate_with`] on points the caller has already checked with
/// [`check_points`] (the PLC check checks them once, not once per facet).
pub(crate) fn triangulate_checked(pts: &[P3], loops: &[Vec<u32>], extra_points: &[u32], extra_edges: &[(u32, u32)])
                                  -> Result<Facet, InputError> {
    let malformed = |m: String| InputError::new(None, m);
    let bad = |w: u8, m: String| InputError::new(Some(w), m);
    if loops.is_empty() {
        return Err(malformed("a facet needs at least one loop".into()));
    }
    let mut seen = HashSet::new();
    for (l, lp) in loops.iter().enumerate() {
        if lp.len() < 3 {
            return Err(bad(3, format!("loop {l} has fewer than 3 points")));
        }
        for &v in lp {
            if v as usize >= pts.len() {
                return Err(malformed(format!("loop {l} refers to point {v}, which does not exist")));
            }
            if !seen.insert(v) {
                return Err(bad(2, format!("point {v} appears twice in the facet's loops")));
            }
        }
    }
    let outer = &loops[0];
    let a = outer[0];
    let b = outer[1];
    let pa = &pts[a as usize];
    let pb = &pts[b as usize];
    let c = *outer.iter().find(|&&v| !pr::collinear(pa, pb, &pts[v as usize]))
        .ok_or_else(|| bad(3, "the facet's outer loop is collinear".into()))?;
    let pc = &pts[c as usize];
    let mut cnt = pr::Counters::default();
    for lp in loops {
        for &v in lp {
            if pr::orient3d(pa, pb, pc, &pts[v as usize], &mut cnt) != 0 {
                return Err(bad(3, format!("point {v} is not in the facet's plane")));
            }
        }
    }
    // drop the axis where the normal is largest among its exactly nonzero components
    let signs = pr::normal_signs(pa, pb, pc);
    let approx = {
        let u = [pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2]];
        let w = [pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2]];
        [(u[1] * w[2] - u[2] * w[1]).abs(), (u[2] * w[0] - u[0] * w[2]).abs(), (u[0] * w[1] - u[1] * w[0]).abs()]
    };
    let axis = (0..3).filter(|&k| signs[k] != 0)
        .max_by(|&x, &y| approx[x].total_cmp(&approx[y]))
        .ok_or_else(|| bad(3, "the facet's normal is zero".into()))?;

    let plain = Plain2 { pts };
    let t = Tri::new(&plain, axis, Vec::new());
    let cons: Vec<(u32, u32)> = loops.iter()
        .flat_map(|lp| (0..lp.len()).map(move |k| (lp[k], lp[(k + 1) % lp.len()])))
        .collect();
    // simple loops: no two constraint edges meet except at a shared end, where they
    // must not overlap
    for x in 0..cons.len() {
        for y in x + 1..cons.len() {
            let (p, q) = cons[x];
            let (r, s) = cons[y];
            if segments_meet(&t, p, q, r, s) {
                return Err(bad(3, format!("loop edges {p}-{q} and {r}-{s} intersect")));
            }
        }
    }

    // the extra points must lie on the plane too
    let mut extras: Vec<u32> = Vec::new();
    for &v in extra_points {
        if v as usize >= pts.len() {
            return Err(malformed(format!("extra point {v} does not exist")));
        }
        if seen.contains(&v) || extras.contains(&v) {
            continue;
        }
        if pr::orient3d(pa, pb, pc, &pts[v as usize], &mut cnt) != 0 {
            return Err(malformed(format!("extra point {v} is not in the facet's plane")));
        }
        extras.push(v);
    }
    // loop edges split at the extra points on them: the boundary pieces
    let mut boundary: Vec<(u32, u32)> = Vec::new();
    let (i, j) = pr::kept_axes(axis);
    for &(p, q) in &cons {
        let mut on: Vec<u32> = extras.iter().copied()
            .filter(|&v| t.orient(p, q, v) == 0 && strictly_between(&t, p, q, v)).collect();
        let k = if pts[p as usize][i] != pts[q as usize][i] { i } else { j };
        let up = pts[q as usize][k] > pts[p as usize][k];
        on.sort_by(|&x, &y| {
            let o = pts[x as usize][k].total_cmp(&pts[y as usize][k]);
            if up { o } else { o.reverse() }
        });
        let mut prev = p;
        for v in on {
            boundary.push((prev, v));
            prev = v;
        }
        boundary.push((prev, q));
    }
    for &(p, q) in extra_edges {
        for v in [p, q] {
            if !seen.contains(&v) && !extras.contains(&v) {
                return Err(malformed(format!("extra edge {p}-{q} ends at point {v}, which is not a facet point")));
            }
        }
    }

    // Delaunay triangulation of all the facet's points, then the constraints
    let order: Vec<u32> = loops.iter().flatten().copied().chain(extras.iter().copied()).collect();
    let flip = loop_orientation(pts, axis, outer) < 0;
    let triangles = cdt(&plain, axis, &order, &boundary, extra_edges, flip).map_err(|(w, m)| bad(w, m))?;
    if triangles.is_empty() {
        return Err(bad(3, "the facet has no area".into()));
    }
    Ok(Facet { triangles, axis, flip })
}

/// Constrained Delaunay triangulation of `points` in the plane (projected along
/// `axis`), with the `boundary` pieces and the `inner` edges as constraints, labelled
/// even-odd from the outside by the boundary pieces only. Returns the inside triangles,
/// counter-clockwise in the projection (clockwise when `flip`). Errors carry the witness
/// type: 3 for the facet itself, 5 when an inner edge cannot be inserted.
pub(crate) fn cdt<P: PlanePred>(pred: &P, axis: usize, points: &[u32], boundary: &[(u32, u32)],
                                inner: &[(u32, u32)], flip: bool) -> Result<Vec<[u32; 3]>, (u8, String)> {
    let mut t = Tri::new(pred, axis, points.to_vec());
    let x = *points.first().ok_or((3, "the facet has no points".to_string()))?;
    let y = *points.iter().find(|&&v| v != x).ok_or((3, "the facet has one point".to_string()))?;
    let z = *points.iter().find(|&&v| t.orient(x, y, v) != 0).ok_or((3, "the facet's points are collinear".to_string()))?;
    let (y, z) = if t.orient(x, y, z) > 0 { (y, z) } else { (z, y) };
    for tri in [[x, y, z], [y, x, GHOST], [z, y, GHOST], [x, z, GHOST]] {
        t.add(tri);
    }
    for &v in points {
        if v != x && v != y && v != z {
            t.insert(v).map_err(|m| (3, m))?;
        }
    }
    for &(p, q) in boundary {
        t.insert_edge(p, q).map_err(|m| (3, m))?;
    }
    for &(p, q) in inner {
        t.insert_edge(p, q).map_err(|m| (5, m))?;
    }
    // even-odd labelling from the outside: only the boundary pieces count
    let live: Vec<[u32; 3]> = t.live().map(|k| t.tris[k]).collect();
    t.tris = live;
    let constraint: HashSet<(u32, u32)> = boundary.iter().map(|&(p, q)| (p.min(q), p.max(q))).collect();
    let mut by_edge: HashMap<(u32, u32), usize> = HashMap::new();
    for (k, tri) in t.tris.iter().enumerate() {
        for (u, v) in edges(tri) {
            by_edge.insert((u, v), k);
        }
    }
    let mut parity = vec![u8::MAX; t.tris.len()];
    let mut stack: Vec<usize> = (0..t.tris.len()).filter(|&k| t.tris[k][2] == GHOST).collect();
    for &k in &stack {
        parity[k] = 0;
    }
    while let Some(k) = stack.pop() {
        for (u, v) in edges(&t.tris[k]) {
            if let Some(&n) = by_edge.get(&(v, u)) {
                let p = parity[k] ^ constraint.contains(&(u.min(v), u.max(v))) as u8;
                if parity[n] == u8::MAX {
                    parity[n] = p;
                    stack.push(n);
                } else if parity[n] != p {
                    return Err((3, "the loops do not bound a consistent region (even-odd labelling conflict)".into()));
                }
            }
        }
    }
    Ok(t.tris.iter().zip(&parity)
        .filter(|(tri, &p)| tri[2] != GHOST && p == 1)
        .map(|(tri, _)| if flip { [tri[0], tri[2], tri[1]] } else { *tri })
        .collect())
}

/// True when closed segments p-q and r-s share any point other than one common end at
/// which they do not overlap.
fn segments_meet<P: PlanePred>(t: &Tri<P>, p: u32, q: u32, r: u32, s: u32) -> bool {
    let shared = [p, q].iter().filter(|v| **v == r || **v == s).count();
    if shared == 2 {
        return true; // the same edge twice
    }
    if shared == 1 {
        let v = if p == r || p == s { p } else { q };
        let x = if v == p { q } else { p };
        let y = if v == r { s } else { r };
        // overlap only when collinear and pointing the same way from v
        return t.orient(v, x, y) == 0 && same_direction(t, v, x, y);
    }
    let o1 = t.orient(p, q, r);
    let o2 = t.orient(p, q, s);
    let o3 = t.orient(r, s, p);
    let o4 = t.orient(r, s, q);
    if o1 == 0 && o2 == 0 {
        // collinear: overlap when an end of one lies on the other
        return on_segment(t, p, q, r) || on_segment(t, p, q, s) || on_segment(t, r, s, p) || on_segment(t, r, s, q);
    }
    o1 * o2 <= 0 && o3 * o4 <= 0
}

/// For c collinear with a-b: true when c lies strictly between a and b.
fn strictly_between<P: PlanePred>(t: &Tri<P>, a: u32, b: u32, c: u32) -> bool {
    t.pred.between(t.axis, a, b, c)
}

/// For collinear v, x, y: true when x and y lie on the same side of v.
fn same_direction<P: PlanePred>(t: &Tri<P>, v: u32, x: u32, y: u32) -> bool {
    t.pred.same_direction(t.axis, v, x, y)
}

/// For collinear points: true when c lies on the closed segment a-b (distinct indices
/// are distinct points).
fn on_segment<P: PlanePred>(t: &Tri<P>, a: u32, b: u32, c: u32) -> bool {
    c == a || c == b || t.pred.between(t.axis, a, b, c)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn embed(o: [f64; 3], e1: [f64; 3], e2: [f64; 3], uv: &[[f64; 2]]) -> Vec<P3> {
        uv.iter().map(|&[u, v]| [o[0] + u * e1[0] + v * e2[0], o[1] + u * e1[1] + v * e2[1], o[2] + u * e1[2] + v * e2[2]]).collect()
    }

    #[test]
    fn square_with_a_hole_on_a_tilted_plane() {
        let uv = [[0.0, 0.0], [4.0, 0.0], [4.0, 4.0], [0.0, 4.0], [1.0, 1.0], [1.0, 3.0], [3.0, 3.0], [3.0, 1.0]];
        let pts = embed([1.0, -2.0, 0.5], [1.0, 2.0, 2.0], [2.0, 1.0, -2.0], &uv);
        let f = triangulate(&pts, &[vec![0, 1, 2, 3], vec![4, 5, 6, 7]]).unwrap();
        // n + 2h - 2 triangles for n boundary points and h holes
        assert_eq!(f.triangles.len(), 8);
        let used: HashSet<u32> = f.triangles.iter().flatten().copied().collect();
        assert_eq!(used.len(), 8);
    }

    #[test]
    fn non_planar_and_crossing_loops_are_refused() {
        let pts = vec![[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [0.0, 1.0, 1e-3]];
        assert!(triangulate(&pts, &[vec![0, 1, 2, 3]]).unwrap_err().msg.contains("plane"));
        let bow = vec![[0.0, 0.0, 0.0], [1.0, 1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]];
        assert!(triangulate(&bow, &[vec![0, 1, 2, 3]]).unwrap_err().msg.contains("intersect"));
    }
}
