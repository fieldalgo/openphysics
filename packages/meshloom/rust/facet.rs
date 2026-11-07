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

#[derive(Debug)]
pub struct Facet {
    /// Triangles as global point indices, wound like the outer (first) loop.
    pub triangles: Vec<[u32; 3]>,
    /// The axis dropped for the in-plane predicates.
    pub axis: usize,
}

struct Tri<'a> {
    pts: &'a [P3],
    axis: usize,
    tris: Vec<[u32; 3]>, // counter-clockwise in the projection; ghosts as (a, b, GHOST)
    points: Vec<u32>,
    constraints: HashSet<(u32, u32)>,
}

impl<'a> Tri<'a> {
    fn p(&self, v: u32) -> &'a P3 {
        &self.pts[v as usize]
    }

    fn orient(&self, a: u32, b: u32, c: u32) -> i8 {
        pr::orient2d_proj(self.axis, self.p(a), self.p(b), self.p(c))
    }

    /// True when c is strictly inside the circle of the counter-clockwise a, b, x under
    /// the perturbation.
    fn in_circle(&self, a: u32, b: u32, x: u32, c: u32) -> bool {
        pr::incircle_plane_sos(self.axis, [self.p(a), self.p(b), self.p(x), self.p(c)], [a, b, x, c]) > 0
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
            let n = self.tris.iter().position(|u| u[2] != GHOST && has_edge(u, b, a)).unwrap();
            return self.conflict(n, q);
        }
        self.in_circle(a, b, c, q)
    }

    fn insert(&mut self, q: u32) -> Result<(), String> {
        let cavity: Vec<usize> = (0..self.tris.len()).filter(|&t| self.conflict(t, q)).collect();
        if cavity.is_empty() {
            return Err(format!("point {q} is in conflict with no triangle"));
        }
        let mut count: HashMap<(u32, u32), i32> = HashMap::new();
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
        let keep: HashSet<usize> = cavity.into_iter().collect();
        let mut tris: Vec<[u32; 3]> = self.tris.iter().enumerate().filter(|(i, _)| !keep.contains(i)).map(|(_, t)| *t).collect();
        tris.extend(new);
        self.tris = tris;
        Ok(())
    }

    fn has_edge(&self, a: u32, b: u32) -> bool {
        self.tris.iter().any(|t| has_edge(t, a, b) || has_edge(t, b, a))
    }

    /// Inserts the constraint a-b. It may not pass through a point or cross another
    /// constraint: callers split edges at the points on them, and crossings are input
    /// errors found before triangulating.
    fn insert_edge(&mut self, a: u32, b: u32) -> Result<(), String> {
        if let Some(&v) = self.points.iter().find(|&&v| v != a && v != b && self.orient(a, b, v) == 0 && strictly_between(self, a, b, v)) {
            return Err(format!("constraint {a}-{b} passes through point {v}"));
        }
        if self.has_edge(a, b) {
            self.constraints.insert((a.min(b), a.max(b)));
            return Ok(());
        }
        // triangles whose interior the open segment a-b crosses: those with an edge it
        // crosses properly
        let crossed: Vec<usize> = (0..self.tris.len())
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
        let keep: HashSet<usize> = crossed.into_iter().collect();
        let mut tris: Vec<[u32; 3]> = self.tris.iter().enumerate().filter(|(i, _)| !keep.contains(i)).map(|(_, t)| *t).collect();
        let mut fill = Vec::new();
        self.fill(b, a, &below, &mut fill); // b-a with the lower chain on its left
        self.fill(a, b, &above, &mut fill);
        tris.extend(fill);
        self.tris = tris;
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

fn has_edge(t: &[u32; 3], a: u32, b: u32) -> bool {
    edges(t).any(|(u, v)| u == a && v == b)
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
}

impl InputError {
    pub fn new(witness: Option<u8>, msg: impl Into<String>) -> Self {
        InputError { witness, msg: msg.into() }
    }
}

impl std::fmt::Display for InputError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.msg)
    }
}

/// The kernel's range check, as witness type 1 (too many points is not a witness).
pub(crate) fn check_points(pts: &[P3]) -> Result<(), InputError> {
    crate::delaunay::check_input(pts).map_err(|e| {
        let w = matches!(e, crate::delaunay::Error::Domain(_)).then_some(1);
        InputError::new(w, e.to_string())
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
    let malformed = |m: String| InputError::new(None, m);
    let bad = |w: u8, m: String| InputError::new(Some(w), m);
    if loops.is_empty() {
        return Err(malformed("a facet needs at least one loop".into()));
    }
    check_points(pts)?;
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

    let mut t = Tri { pts, axis, tris: Vec::new(), points: Vec::new(), constraints: HashSet::new() };
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

    // Delaunay triangulation of all the facet's points
    let order: Vec<u32> = loops.iter().flatten().copied().chain(extras.iter().copied()).collect();
    t.points = order.clone();
    let (x, y, z) = (a, b, c);
    let (y, z) = if t.orient(x, y, z) > 0 { (y, z) } else { (z, y) };
    t.tris = vec![[x, y, z], [y, x, GHOST], [z, y, GHOST], [x, z, GHOST]];
    for &v in &order {
        if v != x && v != y && v != z {
            t.insert(v).map_err(|m| bad(3, m))?;
        }
    }
    for &(p, q) in &boundary {
        t.insert_edge(p, q).map_err(|m| bad(3, m))?;
    }
    for &(p, q) in extra_edges {
        t.insert_edge(p, q).map_err(|m| bad(5, m))?;
    }
    // even-odd labelling from the outside: only the boundary pieces count
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
                    return Err(bad(3, "the loops do not bound a consistent region (even-odd labelling conflict)".into()));
                }
            }
        }
    }
    let flip = loop_orientation(pts, axis, outer) < 0;
    let triangles: Vec<[u32; 3]> = t.tris.iter().zip(&parity)
        .filter(|(tri, &p)| tri[2] != GHOST && p == 1)
        .map(|(tri, _)| if flip { [tri[0], tri[2], tri[1]] } else { *tri })
        .collect();
    if triangles.is_empty() {
        return Err(bad(3, "the facet has no area".into()));
    }
    Ok(Facet { triangles, axis })
}

/// True when closed segments p-q and r-s share any point other than one common end at
/// which they do not overlap.
fn segments_meet(t: &Tri, p: u32, q: u32, r: u32, s: u32) -> bool {
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
fn strictly_between(t: &Tri, a: u32, b: u32, c: u32) -> bool {
    let (pa, pb, pc) = (axis_coords(t, a), axis_coords(t, b), axis_coords(t, c));
    let k = if pa[0] != pb[0] { 0 } else { 1 };
    pc[k] > pa[k].min(pb[k]) && pc[k] < pa[k].max(pb[k])
}

fn axis_coords(t: &Tri, v: u32) -> [f64; 2] {
    let (i, j) = pr::kept_axes(t.axis);
    [t.p(v)[i], t.p(v)[j]]
}

/// For collinear v, x, y: true when x and y lie on the same side of v.
fn same_direction(t: &Tri, v: u32, x: u32, y: u32) -> bool {
    let (pv, px, py) = (axis_coords(t, v), axis_coords(t, x), axis_coords(t, y));
    (0..2).any(|k| (px[k] - pv[k]).signum() * (py[k] - pv[k]).signum() > 0.0 && px[k] != pv[k] && py[k] != pv[k])
}

/// For collinear points: true when c lies on the closed segment a-b.
fn on_segment(t: &Tri, a: u32, b: u32, c: u32) -> bool {
    let (pa, pb, pc) = (axis_coords(t, a), axis_coords(t, b), axis_coords(t, c));
    (0..2).all(|k| pc[k] >= pa[k].min(pb[k]) && pc[k] <= pa[k].max(pb[k]))
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
