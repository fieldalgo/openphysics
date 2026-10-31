// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

//! Piecewise linear complexes (PLCs): the mesher's input, and its exact checks.
//!
//! A PLC is points, segments and planar facets (loops of point indices). Every facet
//! loop edge is a segment. Before meshing, the PLC must be valid: points distinct,
//! facets exactly planar with simple loops, and no two of its pieces meeting except
//! in a shared point or a shared segment. Facets are triangulated by
//! [`facet::triangulate`]; the intersection tests then work on segments and facet
//! triangles, with exact orient3d (and 2D orientation in a projection for coplanar
//! pieces), so there is no tolerance. Candidate pairs come from a sweep over bounding
//! boxes. Any violation is an error naming the pieces.

use crate::facet;
use crate::predicates::{self as pr, Counters, P3};
use std::collections::HashSet;

pub struct Plc {
    pub points: Vec<P3>,
    pub segments: Vec<[u32; 2]>,
    pub facets: Vec<Vec<Vec<u32>>>,
}

#[derive(Debug, Default)]
pub struct Checked {
    /// All segments: the given ones and every loop edge, without repeats, as (min, max).
    pub segments: Vec<[u32; 2]>,
    /// Facet triangles, with the facet each belongs to.
    pub triangles: Vec<[u32; 3]>,
    pub triangle_facet: Vec<u32>,
    pub pairs_tested: usize,
}

pub fn check(plc: &Plc) -> Result<Checked, String> {
    let pts = &plc.points;
    crate::delaunay::check_input(pts).map_err(|e| e.to_string())?;
    let mut order: Vec<u32> = (0..pts.len() as u32).collect();
    order.sort_unstable_by(|&i, &j| pr::lex_cmp(&pts[i as usize], &pts[j as usize]));
    for w in order.windows(2) {
        if pr::same_point(&pts[w[0] as usize], &pts[w[1] as usize]) {
            return Err(format!("points {} and {} coincide", w[0].min(w[1]), w[0].max(w[1])));
        }
    }
    let mut out = Checked::default();
    let mut seen = HashSet::new();
    let mut add_segment = |a: u32, b: u32, what: &str| -> Result<(), String> {
        if a as usize >= pts.len() || b as usize >= pts.len() {
            return Err(format!("{what} {a}-{b} refers to a point that does not exist"));
        }
        if a == b {
            return Err(format!("{what} {a}-{b} has equal ends"));
        }
        if seen.insert((a.min(b), a.max(b))) {
            out.segments.push([a.min(b), a.max(b)]);
        }
        Ok(())
    };
    for s in &plc.segments {
        add_segment(s[0], s[1], "segment")?;
    }
    let mut loop_edges: HashSet<(u32, u32, u32)> = HashSet::new();
    for (f, loops) in plc.facets.iter().enumerate() {
        for lp in loops {
            for k in 0..lp.len() {
                let (a, b) = (lp[k], lp[(k + 1) % lp.len()]);
                add_segment(a, b, &format!("facet {f} edge"))?;
                loop_edges.insert((f as u32, a.min(b), a.max(b)));
            }
        }
        let t = facet::triangulate(pts, loops).map_err(|e| format!("facet {f}: {e}"))?;
        out.triangle_facet.extend(std::iter::repeat_n(f as u32, t.triangles.len()));
        out.triangles.extend(t.triangles);
    }
    // candidate pairs by a sweep over x
    #[derive(Clone, Copy)]
    enum Item {
        Seg(usize),
        Tri(usize),
    }
    let mut items: Vec<(Item, [f64; 3], [f64; 3])> = Vec::new();
    for k in 0..out.segments.len() {
        let (lo, hi) = bbox(pts, &out.segments[k]);
        items.push((Item::Seg(k), lo, hi));
    }
    for k in 0..out.triangles.len() {
        let (lo, hi) = bbox(pts, &out.triangles[k]);
        items.push((Item::Tri(k), lo, hi));
    }
    items.sort_unstable_by(|a, b| a.1[0].total_cmp(&b.1[0]));
    let mut n = Counters::default();
    let mut tested = 0usize;
    for x in 0..items.len() {
        for y in x + 1..items.len() {
            if items[y].1[0] > items[x].2[0] {
                break;
            }
            if (1..3).any(|k| items[y].1[k] > items[x].2[k] || items[x].1[k] > items[y].2[k]) {
                continue;
            }
            let (a, b) = (items[x].0, items[y].0);
            let ok = match (a, b) {
                (Item::Seg(i), Item::Seg(j)) => seg_seg_ok(pts, out.segments[i], out.segments[j], &mut n),
                (Item::Seg(i), Item::Tri(j)) | (Item::Tri(j), Item::Seg(i)) => {
                    // a segment may run along a facet's boundary, never inside it
                    let [a, b] = out.segments[i];
                    let on_boundary = loop_edges.contains(&(out.triangle_facet[j], a, b));
                    seg_tri_ok(pts, out.segments[i], out.triangles[j], on_boundary, &mut n)
                }
                (Item::Tri(i), Item::Tri(j)) => {
                    if out.triangle_facet[i] == out.triangle_facet[j] {
                        true // one facet's own triangulation
                    } else {
                        tri_tri_ok(pts, out.triangles[i], out.triangles[j], &seen, &mut n)
                    }
                }
            };
            tested += 1;
            if !ok {
                let name = |it: Item| match it {
                    Item::Seg(k) => format!("segment {:?}", out.segments[k]),
                    Item::Tri(k) => format!("facet {} (triangle {:?})", out.triangle_facet[k], out.triangles[k]),
                };
                return Err(format!("{} and {} intersect", name(a), name(b)));
            }
        }
    }
    out.pairs_tested = tested;
    Ok(out)
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

/// `on_boundary`: the segment is a loop edge of the triangle's facet. A segment that is
/// an edge of a facet triangle but not on the facet's boundary lies inside the facet.
fn seg_tri_ok(pts: &[P3], s: [u32; 2], t: [u32; 3], on_boundary: bool, n: &mut Counters) -> bool {
    let p = |v: u32| &pts[v as usize];
    let sh = shared(&s, &t);
    match sh.len() {
        2 => on_boundary,
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

/// Triangles of two different facets. `segments` holds every PLC segment as (min, max).
fn tri_tri_ok(pts: &[P3], t: [u32; 3], u: [u32; 3], segments: &HashSet<(u32, u32)>, n: &mut Counters) -> bool {
    let p = |v: u32| &pts[v as usize];
    let sh = shared(&t, &u);
    match sh.len() {
        3 => false, // the same triangle in two facets
        2 => {
            // facets may meet along a segment only (a common edge inside both would be a
            // crossing); then they overlap only when coplanar on the same side of it
            if !segments.contains(&(sh[0].min(sh[1]), sh[0].max(sh[1]))) {
                return false;
            }
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
            edges(t).iter().all(|&e| seg_tri_ok(pts, e, u, true, n)) && edges(u).iter().all(|&e| seg_tri_ok(pts, e, t, true, n))
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
    }

    #[test]
    fn piercing_and_touching_pieces_are_refused() {
        let mut c = cube();
        c.points.push([0.5, 0.5, -1.0]);
        c.points.push([0.5, 0.5, 0.5]);
        c.segments.push([8, 9]); // pierces the bottom facet
        assert!(check(&c).unwrap_err().contains("intersect"));
        let mut d = cube();
        d.points.push([0.5, 0.5, 0.0]); // a point inside the bottom facet, on a segment end
        d.points.push([0.5, 0.5, -1.0]);
        d.segments.push([8, 9]);
        assert!(check(&d).unwrap_err().contains("intersect"));
        let mut e = cube();
        e.points.push([0.5, 0.5, 0.5]);
        e.facets.push(vec![vec![0, 3, 8]]); // attached along the bottom facet's diagonal, inside it
        assert!(check(&e).is_err());
        let mut g = cube();
        g.points.push([0.5, 0.5, 0.5]);
        g.facets.push(vec![vec![0, 1, 8]]); // attached along a cube edge: valid
        check(&g).unwrap();
    }
}
