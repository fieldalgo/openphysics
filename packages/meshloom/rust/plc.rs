// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

//! Piecewise linear complexes (PLCs): the mesher's input, and its exact checks.
//!
//! A PLC is points, segments and planar facets (loops of point indices). Every facet
//! loop edge is an edge too. Before meshing, the PLC must be valid: points distinct and
//! in the kernel's range, facets exactly planar with simple loops, and every two cells
//! meeting in a union of cells (the import validity rule). Edges are split at the
//! points on them and each facet is triangulated with the points and sub-segments on
//! it by [`facet::triangulate_with`]; the intersection tests then work on these pieces
//! with exact orient3d (and 2D orientation in a projection for coplanar pieces), so
//! there is no tolerance. Candidate pairs come from a sweep over bounding boxes. Any
//! violation is an error naming the cells, with its witness type.

use crate::facet::{self, InputError};
use crate::predicates::{self as pr, Counters, P3};
use std::collections::{HashMap, HashSet};

pub struct Plc {
    pub points: Vec<P3>,
    pub segments: Vec<[u32; 2]>,
    pub facets: Vec<Vec<Vec<u32>>>,
}

#[derive(Debug, Default)]
pub struct Checked {
    /// All edge cells: the given segments and every loop edge, without repeats, as (min, max).
    pub segments: Vec<[u32; 2]>,
    /// Elementary sub-segments: the edges split at the points that lie on them.
    pub subsegments: Vec<[u32; 2]>,
    /// Facet triangles (each facet triangulated with the points and edges that lie on
    /// it), with the facet each belongs to. A triangle shared by coplanar facets, one
    /// inside the other, is listed once per facet.
    pub triangles: Vec<[u32; 3]>,
    pub triangle_facet: Vec<u32>,
    /// Elementary sub-segments on the boundary of an odd number of facets (witnesses of
    /// type 6): empty when the PLC is closed.
    pub open_subsegments: Vec<[u32; 2]>,
    pub pairs_tested: usize,
}

/// A cell of the PLC: an edge (index into `Checked::segments`) or a facet.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
enum Cell {
    Edge(u32),
    Facet(u32),
}

/// Checks that `plc` is a valid PLC: every two cells meet in a union of cells
/// (Shewchuk's and Diazzi's closure rule, lab protocol section 4 and owner decisions
/// 13-15 of 2026-11-07). So a point may lie inside an edge or a facet (a T-junction), an
/// edge inside a facet, and a facet inside a coplanar facet, or two coplanar facets may
/// overlap exactly in facets contained in both. Crossings, piercings, partial collinear
/// overlaps of edges and coplanar overlaps that no common cell covers are refused.
///
/// The check refines the cells into pieces: edges split at the points on them
/// (elementary sub-segments), facets triangulated with the points and sub-segments
/// that lie on them. Two pieces then meet only in shared faces, or the input is
/// invalid; and every piece shared by two cells must lie in a cell contained in both.
pub fn check(plc: &Plc) -> Result<Checked, InputError> {
    let malformed = |m: String| InputError::new(None, m);
    let bad = |w: u8, m: String| InputError::new(Some(w), m);
    let pts = &plc.points;
    facet::check_points(pts)?;
    let mut order: Vec<u32> = (0..pts.len() as u32).collect();
    order.sort_unstable_by(|&i, &j| pr::lex_cmp(&pts[i as usize], &pts[j as usize]));
    for w in order.windows(2) {
        if pr::same_point(&pts[w[0] as usize], &pts[w[1] as usize]) {
            return Err(malformed(format!("points {} and {} coincide", w[0].min(w[1]), w[0].max(w[1]))));
        }
    }
    if plc.facets.is_empty() {
        return Err(bad(0, "the PLC has no facets".into()));
    }
    let mut out = Checked::default();
    let mut seen = HashSet::new();
    let mut add_segment = |a: u32, b: u32, what: &str| -> Result<(), InputError> {
        if a as usize >= pts.len() || b as usize >= pts.len() {
            return Err(malformed(format!("{what} {a}-{b} refers to a point that does not exist")));
        }
        if a == b {
            return Err(bad(3, format!("{what} {a}-{b} has equal ends")));
        }
        if seen.insert((a.min(b), a.max(b))) {
            out.segments.push([a.min(b), a.max(b)]);
        }
        Ok(())
    };
    for s in &plc.segments {
        add_segment(s[0], s[1], "segment")?;
    }
    let mut vertex_sets: HashMap<Vec<u32>, usize> = HashMap::new();
    for (f, loops) in plc.facets.iter().enumerate() {
        for lp in loops {
            for k in 0..lp.len() {
                add_segment(lp[k], lp[(k + 1) % lp.len()], &format!("facet {f} edge"))?;
            }
        }
        let mut vs: Vec<u32> = loops.iter().flatten().copied().collect();
        vs.sort_unstable();
        vs.dedup();
        if let Some(g) = vertex_sets.insert(vs, f) {
            return Err(bad(4, format!("facets {g} and {f} have the same vertices")));
        }
    }
    let mut n = Counters::default();
    let mut tested = 0usize;

    // 1. points inside edges split them into elementary sub-segments
    let edges = out.segments.clone();
    let mut on_edge: Vec<Vec<u32>> = vec![Vec::new(); edges.len()];
    {
        let mut items: Vec<(bool, u32, [f64; 3], [f64; 3])> = Vec::new(); // (is point, index, lo, hi)
        for v in 0..pts.len() as u32 {
            items.push((true, v, pts[v as usize], pts[v as usize]));
        }
        for (e, ed) in edges.iter().enumerate() {
            let (lo, hi) = bbox(pts, ed);
            items.push((false, e as u32, lo, hi));
        }
        for_overlapping(&items.iter().map(|x| (x.2, x.3)).collect::<Vec<_>>(), |x, y| {
            let (a, b) = (&items[x], &items[y]);
            let (v, e) = match (a.0, b.0) {
                (true, false) => (a.1, b.1),
                (false, true) => (b.1, a.1),
                _ => return,
            };
            let [p, q] = edges[e as usize];
            if v != p && v != q && pr::collinear(&pts[p as usize], &pts[q as usize], &pts[v as usize])
                && strictly_inside(&pts[p as usize], &pts[q as usize], &pts[v as usize])
            {
                on_edge[e as usize].push(v);
            }
        });
    }
    let mut edge_subs: Vec<HashSet<(u32, u32)>> = Vec::with_capacity(edges.len());
    let mut sub_edges: HashMap<(u32, u32), Vec<u32>> = HashMap::new();
    for (e, &[p, q]) in edges.iter().enumerate() {
        let (pp, pq) = (&pts[p as usize], &pts[q as usize]);
        let k = (0..3).find(|&k| pp[k] != pq[k]).unwrap();
        let mut on = on_edge[e].clone();
        on.sort_by(|&x, &y| pts[x as usize][k].total_cmp(&pts[y as usize][k]));
        if pq[k] < pp[k] {
            on.reverse();
        }
        let mut set = HashSet::new();
        let mut prev = p;
        for v in on.into_iter().chain(std::iter::once(q)) {
            let key = (prev.min(v), prev.max(v));
            set.insert(key);
            sub_edges.entry(key).or_default().push(e as u32);
            prev = v;
        }
        edge_subs.push(set);
    }
    let mut subs: Vec<(u32, u32)> = sub_edges.keys().copied().collect();
    subs.sort_unstable();
    out.subsegments = subs.iter().map(|&(a, b)| [a, b]).collect();
    let edge_name = |e: u32| format!("segment {:?}", edges[e as usize]);

    // 2. two sub-segments meet only at a shared end (an identical piece is one key)
    {
        let boxes: Vec<_> = subs.iter().map(|&(a, b)| bbox(pts, &[a, b])).collect();
        let mut found = None;
        for_overlapping(&boxes, |x, y| {
            if found.is_some() {
                return;
            }
            tested += 1;
            let (s, t) = (subs[x], subs[y]);
            if !seg_seg_ok(pts, [s.0, s.1], [t.0, t.1], &mut n) {
                found = Some((s, t));
            }
        });
        if let Some((s, t)) = found {
            return Err(bad(5, format!("{} and {} intersect", edge_name(sub_edges[&s][0]), edge_name(sub_edges[&t][0]))));
        }
    }

    // 3. each facet triangulated with the points and sub-segments on its plane
    let mut facet_tris: Vec<HashSet<[u32; 3]>> = Vec::with_capacity(plc.facets.len());
    let mut facet_edges: Vec<HashSet<(u32, u32)>> = Vec::with_capacity(plc.facets.len());
    let mut by_x: Vec<u32> = (0..pts.len() as u32).collect();
    by_x.sort_unstable_by(|&i, &j| pts[i as usize][0].total_cmp(&pts[j as usize][0]));
    for (f, loops) in plc.facets.iter().enumerate() {
        let own: HashSet<u32> = loops.iter().flatten().copied().collect();
        let (lo, hi) = bbox(pts, &own.iter().copied().collect::<Vec<_>>());
        let plane = plane_of(pts, &loops[0]);
        let mut extra = Vec::new();
        if let Some((a, b, c)) = plane {
            let start = by_x.partition_point(|&i| pts[i as usize][0] < lo[0]);
            for &v in &by_x[start..] {
                let pv = &pts[v as usize];
                if pv[0] > hi[0] {
                    break;
                }
                if own.contains(&v) || (1..3).any(|k| pv[k] < lo[k] || pv[k] > hi[k]) {
                    continue;
                }
                if pr::orient3d(&pts[a as usize], &pts[b as usize], &pts[c as usize], pv, &mut n) == 0 {
                    extra.push(v);
                }
            }
        }
        let members: HashSet<u32> = own.iter().copied().chain(extra.iter().copied()).collect();
        let inner: Vec<(u32, u32)> = subs.iter().copied()
            .filter(|&(a, b)| members.contains(&a) && members.contains(&b)).collect();
        let t = facet::triangulate_with(pts, loops, &extra, &inner).map_err(|e| InputError::new(e.witness, format!("facet {f}: {}", e.msg)))?;
        let mut tris = HashSet::new();
        let mut eds = HashSet::new();
        for tri in &t.triangles {
            let mut k = *tri;
            k.sort_unstable();
            tris.insert(k);
            for (u, v) in [(k[0], k[1]), (k[1], k[2]), (k[0], k[2])] {
                eds.insert((u, v));
            }
        }
        out.triangle_facet.extend(std::iter::repeat_n(f as u32, t.triangles.len()));
        out.triangles.extend(t.triangles);
        facet_tris.push(tris);
        facet_edges.push(eds);
    }

    // closure (type 6): each elementary sub-segment on the boundary of an even number
    // of facets; a facet's boundary is its loop edges, each split into sub-segments
    {
        let index: HashMap<(u32, u32), usize> = edges.iter().enumerate().map(|(e, &[a, b])| ((a, b), e)).collect();
        let mut count: HashMap<(u32, u32), u32> = HashMap::new();
        for loops in &plc.facets {
            for lp in loops {
                for k in 0..lp.len() {
                    let (a, b) = (lp[k], lp[(k + 1) % lp.len()]);
                    for sub in &edge_subs[index[&(a.min(b), a.max(b))]] {
                        *count.entry(*sub).or_default() += 1;
                    }
                }
            }
        }
        out.open_subsegments = subs.iter().filter(|k| count.get(k).copied().unwrap_or(0) % 2 == 1)
            .map(|&(a, b)| [a, b]).collect();
    }

    // 4. every piece shared by two cells lies in a cell contained in both
    let contained = |h: Cell, s: Cell| -> bool {
        match (h, s) {
            _ if h == s => true,
            (Cell::Edge(a), Cell::Edge(b)) => edge_subs[a as usize].is_subset(&edge_subs[b as usize]),
            (Cell::Edge(a), Cell::Facet(f)) => edge_subs[a as usize].iter().all(|k| facet_edges[f as usize].contains(k)),
            (Cell::Facet(g), Cell::Facet(f)) => facet_tris[g as usize].is_subset(&facet_tris[f as usize]),
            (Cell::Facet(_), Cell::Edge(_)) => false,
        }
    };
    let name = |c: Cell| match c {
        Cell::Edge(e) => edge_name(e),
        Cell::Facet(f) => format!("facet {f}"),
    };
    let covered = |cells: &[Cell]| -> Result<(), InputError> {
        for x in 0..cells.len() {
            for y in x + 1..cells.len() {
                let (s, t) = (cells[x], cells[y]);
                if !cells.iter().any(|&h| contained(h, s) && contained(h, t)) {
                    return Err(bad(5, format!("{} and {} intersect in a part that no cell of both covers", name(s), name(t))));
                }
            }
        }
        Ok(())
    };
    let mut sub_cells: HashMap<(u32, u32), Vec<Cell>> = HashMap::new();
    for (k, es) in &sub_edges {
        sub_cells.entry(*k).or_default().extend(es.iter().map(|&e| Cell::Edge(e)));
    }
    let mut tri_cells: HashMap<[u32; 3], Vec<Cell>> = HashMap::new();
    for (f, (tris, eds)) in facet_tris.iter().zip(&facet_edges).enumerate() {
        for k in eds {
            sub_cells.entry(*k).or_default().push(Cell::Facet(f as u32));
        }
        for k in tris {
            tri_cells.entry(*k).or_default().push(Cell::Facet(f as u32));
        }
    }
    let mut sub_keys: Vec<_> = sub_cells.keys().copied().collect();
    sub_keys.sort_unstable();
    for k in &sub_keys {
        covered(&sub_cells[k])?;
    }
    let mut tri_keys: Vec<[u32; 3]> = tri_cells.keys().copied().collect();
    tri_keys.sort_unstable();
    for k in &tri_keys {
        covered(&tri_cells[k])?;
    }

    // 5. sub-segments against facet triangles, and triangles of different facets, meet
    //    only in shared faces
    let mut items: Vec<(bool, usize)> = subs.iter().enumerate().map(|(i, _)| (true, i)).collect();
    items.extend(tri_keys.iter().enumerate().map(|(i, _)| (false, i)));
    let boxes: Vec<_> = items.iter().map(|&(is_seg, i)| {
        if is_seg { bbox(pts, &[subs[i].0, subs[i].1]) } else { bbox(pts, &tri_keys[i]) }
    }).collect();
    let mut found: Option<(String, String)> = None;
    for_overlapping(&boxes, |x, y| {
        if found.is_some() {
            return;
        }
        let (a, b) = (items[x], items[y]);
        let ok = match (a, b) {
            ((true, _), (true, _)) => return, // checked in step 2
            ((true, i), (false, j)) | ((false, j), (true, i)) => {
                tested += 1;
                seg_tri_ok(pts, [subs[i].0, subs[i].1], tri_keys[j], &mut n)
            }
            ((false, i), (false, j)) => {
                let (ci, cj) = (&tri_cells[&tri_keys[i]], &tri_cells[&tri_keys[j]]);
                if ci.iter().any(|c| cj.contains(c)) {
                    return; // one facet's own triangulation
                }
                tested += 1;
                tri_tri_ok(pts, tri_keys[i], tri_keys[j], &mut n)
            }
        };
        if !ok {
            let piece = |(is_seg, i): (bool, usize)| {
                if is_seg {
                    sub_cells[&subs[i]].first().map(|&c| name(c)).unwrap_or_default()
                } else {
                    tri_cells[&tri_keys[i]].first().map(|&c| name(c)).unwrap_or_default()
                }
            };
            found = Some((piece(a), piece(b)));
        }
    });
    if let Some((x, y)) = found {
        return Err(bad(5, format!("{x} and {y} intersect")));
    }
    out.pairs_tested = tested;
    Ok(out)
}

/// Calls `f(i, j)` for every pair of boxes that overlap (closed), by a sweep over x.
fn for_overlapping(boxes: &[([f64; 3], [f64; 3])], mut f: impl FnMut(usize, usize)) {
    let mut order: Vec<usize> = (0..boxes.len()).collect();
    order.sort_unstable_by(|&a, &b| boxes[a].0[0].total_cmp(&boxes[b].0[0]));
    for x in 0..order.len() {
        let i = order[x];
        for &j in &order[x + 1..] {
            if boxes[j].0[0] > boxes[i].1[0] {
                break;
            }
            if (1..3).any(|k| boxes[j].0[k] > boxes[i].1[k] || boxes[i].0[k] > boxes[j].1[k]) {
                continue;
            }
            f(i, j);
        }
    }
}

/// Three non-collinear points of a loop, if any.
fn plane_of(pts: &[P3], lp: &[u32]) -> Option<(u32, u32, u32)> {
    let (a, b) = (*lp.first()?, *lp.get(1)?);
    let c = *lp.iter().find(|&&v| !pr::collinear(&pts[a as usize], &pts[b as usize], &pts[v as usize]))?;
    Some((a, b, c))
}

/// For c collinear with a-b: true when c lies strictly between a and b.
fn strictly_inside(a: &P3, b: &P3, c: &P3) -> bool {
    let k = (0..3).find(|&k| a[k] != b[k]).unwrap();
    c[k] > a[k].min(b[k]) && c[k] < a[k].max(b[k])
}

fn bbox(pts: &[P3], v: &[u32]) -> ([f64; 3], [f64; 3]) {
    let mut lo = [f64::INFINITY; 3];
    let mut hi = [f64::NEG_INFINITY; 3];
    for &i in v {
        for k in 0..3 {
            lo[k] = lo[k].min(pts[i as usize][k]);
            hi[k] = hi[k].max(pts[i as usize][k]);
        }
    }
    (lo, hi)
}

fn shared(a: &[u32], b: &[u32]) -> Vec<u32> {
    a.iter().copied().filter(|v| b.contains(v)).collect()
}

/// A projection axis in which the plane through a, b, c (not collinear) is one to one.
fn plane_axis(a: &P3, b: &P3, c: &P3) -> Option<usize> {
    let s = pr::normal_signs(a, b, c);
    (0..3).find(|&k| s[k] != 0)
}

/// For collinear points: true when c lies on the closed segment a-b.
fn between(a: &P3, b: &P3, c: &P3) -> bool {
    (0..3).all(|k| c[k] >= a[k].min(b[k]) && c[k] <= a[k].max(b[k]))
}

/// Closed segments p-q and r-s in one plane (projection `axis`), no shared ends.
fn segs_meet_2d(axis: usize, p: &P3, q: &P3, r: &P3, s: &P3) -> bool {
    let o1 = pr::orient2d_proj(axis, p, q, r);
    let o2 = pr::orient2d_proj(axis, p, q, s);
    let o3 = pr::orient2d_proj(axis, r, s, p);
    let o4 = pr::orient2d_proj(axis, r, s, q);
    if o1 == 0 && o2 == 0 {
        return between(p, q, r) || between(p, q, s) || between(r, s, p) || between(r, s, q);
    }
    o1 * o2 <= 0 && o3 * o4 <= 0
}

fn seg_seg_ok(pts: &[P3], a: [u32; 2], b: [u32; 2], n: &mut Counters) -> bool {
    let p = |v: u32| &pts[v as usize];
    let sh = shared(&a, &b);
    match sh.len() {
        2 => true, // the same segment (deduplicated, so never reached)
        1 => {
            let v = sh[0];
            let x = if a[0] == v { a[1] } else { a[0] };
            let y = if b[0] == v { b[1] } else { b[0] };
            // they overlap beyond v only when collinear and pointing the same way
            if !pr::collinear(p(v), p(x), p(y)) {
                return true;
            }
            !(0..3).any(|k| (p(x)[k] - p(v)[k]) * (p(y)[k] - p(v)[k]) > 0.0)
        }
        _ => {
            let (pp, pq, pr_, ps) = (p(a[0]), p(a[1]), p(b[0]), p(b[1]));
            if pr::orient3d(pp, pq, pr_, ps, n) != 0 {
                return true;
            }
            // coplanar: find a plane through three of them
            let tri = [(pp, pq, pr_), (pp, pq, ps), (pp, pr_, ps)];
            match tri.iter().find_map(|&(x, y, z)| plane_axis(x, y, z)) {
                Some(axis) => !segs_meet_2d(axis, pp, pq, pr_, ps),
                None => !(between(pp, pq, pr_) || between(pp, pq, ps) || between(pr_, ps, pp) || between(pr_, ps, pq)),
            }
        }
    }
}

/// True when closed segment p-q meets closed triangle a-b-c (no shared vertices).
fn seg_meets_tri(p: &P3, q: &P3, a: &P3, b: &P3, c: &P3, n: &mut Counters) -> bool {
    let op = pr::orient3d(a, b, c, p, n);
    let oq = pr::orient3d(a, b, c, q, n);
    if op * oq > 0 {
        return false;
    }
    if op == 0 && oq == 0 {
        let axis = plane_axis(a, b, c).unwrap();
        let inside = |x: &P3| {
            let s = [pr::orient2d_proj(axis, a, b, x), pr::orient2d_proj(axis, b, c, x), pr::orient2d_proj(axis, c, a, x)];
            s.iter().all(|&v| v >= 0) || s.iter().all(|&v| v <= 0)
        };
        return inside(p) || inside(q) || segs_meet_2d(axis, p, q, a, b) || segs_meet_2d(axis, p, q, b, c)
            || segs_meet_2d(axis, p, q, c, a);
    }
    // the line p-q crosses the plane at one point, inside the segment: is it in the triangle?
    let s = [pr::orient3d(p, q, a, b, n), pr::orient3d(p, q, b, c, n), pr::orient3d(p, q, c, a, n)];
    s.iter().all(|&v| v >= 0) || s.iter().all(|&v| v <= 0)
}

/// A sub-segment and a facet triangle meet only in a shared face. A sub-segment that is
/// an edge of the triangle is a shared face; whether its cells may share it is step 4.
fn seg_tri_ok(pts: &[P3], s: [u32; 2], t: [u32; 3], n: &mut Counters) -> bool {
    let p = |v: u32| &pts[v as usize];
    let sh = shared(&s, &t);
    match sh.len() {
        2 => true,
        1 => {
            // segment v-x and triangle v-y-z meet beyond v only when x is in the
            // triangle's plane and v-x enters the closed angle at v
            let v = sh[0];
            let x = if s[0] == v { s[1] } else { s[0] };
            let others: Vec<u32> = t.iter().copied().filter(|&w| w != v).collect();
            let (y, z) = (others[0], others[1]);
            if pr::orient3d(p(v), p(y), p(z), p(x), n) != 0 {
                return true;
            }
            let axis = plane_axis(p(v), p(y), p(z)).unwrap();
            let o = pr::orient2d_proj(axis, p(v), p(y), p(z));
            let a1 = pr::orient2d_proj(axis, p(v), p(y), p(x)) * o;
            let a2 = pr::orient2d_proj(axis, p(v), p(x), p(z)) * o;
            !(a1 >= 0 && a2 >= 0)
        }
        _ => !seg_meets_tri(p(s[0]), p(s[1]), p(t[0]), p(t[1]), p(t[2]), n),
    }
}

/// Triangles of two different facets meet only in a shared face (identical triangles are
/// one piece, handled in step 4).
fn tri_tri_ok(pts: &[P3], t: [u32; 3], u: [u32; 3], n: &mut Counters) -> bool {
    let p = |v: u32| &pts[v as usize];
    let sh = shared(&t, &u);
    match sh.len() {
        3 => false, // the same triangle in two facets
        2 => {
            // a common edge: they overlap only when coplanar on the same side of it (which
            // cells may share the edge is step 4)
            let a = *t.iter().find(|v| !sh.contains(v)).unwrap();
            let b = *u.iter().find(|v| !sh.contains(v)).unwrap();
            if pr::orient3d(p(sh[0]), p(sh[1]), p(a), p(b), n) != 0 {
                return true;
            }
            let axis = plane_axis(p(sh[0]), p(sh[1]), p(a)).unwrap();
            pr::orient2d_proj(axis, p(sh[0]), p(sh[1]), p(a)) * pr::orient2d_proj(axis, p(sh[0]), p(sh[1]), p(b)) < 0
        }
        _ => {
            // every edge of each against the other triangle (shared vertices allowed)
            let edges = |x: [u32; 3]| [[x[0], x[1]], [x[1], x[2]], [x[2], x[0]]];
            edges(t).iter().all(|&e| seg_tri_ok(pts, e, u, n)) && edges(u).iter().all(|&e| seg_tri_ok(pts, e, t, n))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cube() -> Plc {
        let mut points = Vec::new();
        for i in 0..8 {
            points.push([(i & 1) as f64, ((i >> 1) & 1) as f64, ((i >> 2) & 1) as f64]);
        }
        let facets = vec![
            vec![vec![0, 2, 3, 1]], vec![vec![4, 5, 7, 6]], vec![vec![0, 1, 5, 4]],
            vec![vec![2, 6, 7, 3]], vec![vec![0, 4, 6, 2]], vec![vec![1, 3, 7, 5]],
        ];
        Plc { points, segments: Vec::new(), facets }
    }

    #[test]
    fn the_unit_cube_is_valid() {
        let c = check(&cube()).unwrap();
        assert_eq!(c.segments.len(), 12);
        assert_eq!(c.triangles.len(), 12);
        assert!(c.open_subsegments.is_empty());
        let mut open = cube();
        open.facets.pop();
        assert_eq!(check(&open).unwrap().open_subsegments.len(), 4);
    }

    #[test]
    fn crossings_are_refused_and_contained_cells_are_valid() {
        let mut c = cube();
        c.points.push([0.5, 0.5, -1.0]);
        c.points.push([0.5, 0.5, 0.5]);
        c.segments.push([8, 9]); // pierces the bottom facet
        assert!(check(&c).unwrap_err().msg.contains("intersect"));
        let mut d = cube();
        d.points.push([0.5, 0.5, 0.0]); // a point inside the bottom facet, on a segment end
        d.points.push([0.5, 0.5, -1.0]);
        d.segments.push([8, 9]);
        check(&d).unwrap();
        let mut e = cube();
        e.points.push([0.5, 0.5, 0.5]);
        e.facets.push(vec![vec![0, 3, 8]]); // attached along the bottom facet's diagonal, inside it
        check(&e).unwrap();
        let mut g = cube();
        g.points.push([0.5, 0.5, 0.5]);
        g.facets.push(vec![vec![0, 1, 8]]); // attached along a cube edge
        check(&g).unwrap();
        let mut h = cube();
        h.points.push([0.5, 0.0, 0.0]);
        h.points.push([1.5, 0.0, 0.0]);
        h.segments.push([8, 9]); // overlaps half of the cube edge 0-1 and runs past it
        assert!(check(&h).unwrap_err().msg.contains("intersect"));
        let mut k = cube();
        k.points.push([0.5, 0.5, 0.0]);
        k.points.push([1.5, 0.5, 0.0]);
        k.segments.push([8, 9]); // starts inside the bottom facet and leaves through an edge
        assert!(check(&k).unwrap_err().msg.contains("intersect"));
        let mut m = cube();
        m.points.extend([[0.5, 0.5, 0.0], [1.5, 0.5, 0.0], [1.5, 1.5, 0.0], [0.5, 1.5, 0.0]]);
        m.facets.push(vec![vec![8, 9, 10, 11]]); // overlaps a quarter of the bottom facet
        assert!(check(&m).unwrap_err().msg.contains("intersect"));
        let mut q = cube();
        q.facets.push(vec![vec![0, 1, 3, 2]]); // the bottom facet again
        assert!(check(&q).unwrap_err().msg.contains("same vertices"));
        let mut z = cube();
        z.facets.clear();
        assert!(check(&z).unwrap_err().msg.contains("no facets"));
    }
}
