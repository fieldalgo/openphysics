// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

//! Segment recovery (M4 stage 3 of the pre-registered 3D plan; design note section 3).
//!
//! Every input segment must become a union of edges of the tetrahedralization. Starting
//! from the Delaunay tetrahedralization of the input points:
//! 1. **Protection at acute vertices** (Shewchuk 2002, step i), lazily: when a piece
//!    that ends at a vertex where two segments meet at less than 90 degrees is not an
//!    edge, each segment at that vertex gets a point at distance r = min(l/3, 2d/3, h/2)
//!    from it (l the shortest incident segment, d the distance to the nearest other
//!    input point, h the distance to the first split already on an incident segment).
//!    Vertices whose segments are all edges are left alone: on a triangulated surface
//!    every vertex has an acute pair, and eager protection would split every segment. All points of one vertex lie at the
//!    same distance up to a relative 2^-30 (the parameter is the shortest dyadic
//!    fraction in that window, preferring one whose point is exactly a double), so the
//!    pieces from the vertex are Gabriel and halving them splits all incident segments
//!    on common spheres r/2, r/4, ... (concentric shells).
//! 2. **Recursive bisection** of every other piece of a segment that is not an edge of
//!    the current tetrahedralization, round by round until every piece is an edge.
//!
//! New points are S points `(a, b, t)` of the input segment a-b, inserted by the same
//! Bowyer-Watson kernel with the exact mixed predicates, so the result is the Delaunay
//! tetrahedralization (under the index-ordered perturbation) of the input points and
//! the S points. A piece that would need more than `max_depth` halvings is an error,
//! not a hang: termination of bisection after rounded protection is not proven (design
//! note, open point).
//!
//! The segments must be elementary and pairwise non-crossing (the output of the PLC
//! check: no point strictly inside a segment), so S points never coincide.

use crate::delaunay::{self, Error, Mesh};
use crate::mixed::{MixedCounters, MixedPoints, Pt, SPoint};
use crate::predicates::P3;

#[derive(Debug, Clone, Copy, Default)]
pub struct RecoveryStats {
    pub rounds: u32,
    pub protected_vertices: u32,
    pub protection_points: u32,
    pub bisection_points: u32,
    pub max_depth: u32,
    /// S points whose parameter puts the point exactly on a double
    pub exact_points: u32,
}

pub struct Recovered {
    pub tets: Vec<[u32; 4]>,
    pub s: Vec<SPoint>,
    /// For each segment, its vertices (global indices) in order from a to b.
    pub chains: Vec<Vec<u32>>,
    pub stats: RecoveryStats,
    pub kernel: delaunay::Stats,
    pub mixed: MixedCounters,
}

#[derive(Clone, Copy, Debug)]
struct Piece {
    seg: u32,
    t0: f64,
    t1: f64,
    u: u32,
    v: u32,
    depth: u32,
}

fn dist(a: &P3, b: &P3) -> f64 {
    ((a[0] - b[0]).powi(2) + (a[1] - b[1]).powi(2) + (a[2] - b[2]).powi(2)).sqrt()
}

/// A dyadic parameter in [lo, hi] (0 < lo <= hi < 1): the one with the fewest bits
/// whose point a + t (b - a) is exactly a double in every coordinate, else the one
/// with the fewest bits.
fn pick_t(lo: f64, hi: f64, exact: impl Fn(f64) -> bool) -> f64 {
    let mut fallback = None;
    for j in 1..=60 {
        let scale = 2f64.powi(j);
        let first = (lo * scale).ceil();
        let last = (hi * scale).floor();
        if first > last {
            continue;
        }
        // a few candidates per level, from the middle of the window out
        let mid = ((first + last) / 2.0).floor();
        for k in [mid, mid + 1.0, first, last] {
            if k < first || k > last {
                continue;
            }
            let t = k / scale;
            if t <= 0.0 || t >= 1.0 {
                continue;
            }
            if exact(t) {
                return t;
            }
            fallback.get_or_insert(t);
        }
        if j >= 40 && fallback.is_some() {
            break;
        }
    }
    fallback.unwrap_or((lo + hi) / 2.0)
}

/// Recovers every segment of `segments` (indices into `points`) as a union of edges.
pub fn recover(points: &[P3], segments: &[[u32; 2]], max_depth: u32) -> Result<Recovered, Error> {
    delaunay::check_input(points)?;
    let n = points.len();
    for (k, s) in segments.iter().enumerate() {
        if s[0] as usize >= n || s[1] as usize >= n {
            return Err(Error::Input(format!("segment {k} refers to a point that does not exist")));
        }
        if s[0] == s[1] {
            return Err(Error::Input(format!("segment {k} has equal ends")));
        }
    }
    let order = delaunay::brio_order(points);
    // distinct points are required: S points are placed between input points
    {
        let mut by: Vec<u32> = (0..n as u32).collect();
        by.sort_unstable_by(|&i, &j| crate::predicates::lex_cmp(&points[i as usize], &points[j as usize]));
        if let Some(w) = by.windows(2).find(|w| crate::predicates::same_point(&points[w[0] as usize], &points[w[1] as usize])) {
            return Err(Error::Input(format!("points {} and {} coincide", w[0].min(w[1]), w[0].max(w[1]))));
        }
    }
    let mut mesh = Mesh::build(MixedPoints::new(points.to_vec()), &order, true)?;
    let mut stats = RecoveryStats::default();

    // pieces of each segment, in order along it
    let mut pieces: Vec<Vec<Piece>> = segments.iter().enumerate()
        .map(|(k, s)| vec![Piece { seg: k as u32, t0: 0.0, t1: 1.0, u: s[0], v: s[1], depth: 0 }])
        .collect();
    let mut incident: Vec<Vec<u32>> = vec![Vec::new(); n];
    for (k, s) in segments.iter().enumerate() {
        incident[s[0] as usize].push(k as u32);
        incident[s[1] as usize].push(k as u32);
    }
    let nearest = nearest_distances(points);
    let mut protected = vec![false; n];

    loop {
        // the pieces that are not edges, and the acute, unprotected vertices they end at
        let mut missing: Vec<(usize, usize)> = Vec::new();
        let mut protect: Vec<usize> = Vec::new();
        for (k, ps) in pieces.iter().enumerate() {
            for (i, p) in ps.iter().enumerate() {
                if mesh.has_edge(p.u, p.v) {
                    continue;
                }
                missing.push((k, i));
                let s = segments[k];
                for (end, at) in [(s[0] as usize, p.t0 == 0.0), (s[1] as usize, p.t1 == 1.0)] {
                    if at && !protected[end] && is_acute(points, segments, &incident[end], end) {
                        protected[end] = true;
                        protect.push(end);
                    }
                }
            }
        }
        stats.rounds += 1;
        if missing.is_empty() {
            break;
        }
        if !protect.is_empty() {
            // 1. protection (lazily, where a missing piece ends at an acute vertex): every
            //    incident segment gets a point at the same distance r from the vertex
            for v in protect {
                stats.protected_vertices += 1;
                let pv = &points[v];
                let mut r = 2.0 * nearest[v] / 3.0;
                for &k in &incident[v] {
                    let s = segments[k as usize];
                    let len = dist(&points[s[0] as usize], &points[s[1] as usize]);
                    r = r.min(len / 3.0);
                    // stay inside the first piece from v, whatever splits it already has
                    let ps = &pieces[k as usize];
                    let near = if s[0] as usize == v { ps[0].t1 } else { 1.0 - ps[ps.len() - 1].t0 };
                    r = r.min(near * len / 2.0);
                }
                for &k in &incident[v] {
                    let s = segments[k as usize];
                    let (a, b) = (&points[s[0] as usize], &points[s[1] as usize]);
                    let tr = r / dist(a, b);
                    let exact = |t: f64| exact_point(a, b, t);
                    // the same distance r from v, up to a relative 2^-30: the pieces from
                    // v are Gabriel and halving keeps concentric shells r/2, r/4, ...
                    let w = tr * 2f64.powi(-30);
                    let t = if s[0] as usize == v { pick_t(tr - w, tr, exact) } else { pick_t(1.0 - tr, 1.0 - tr + w, exact) };
                    let _ = pv;
                    let id = insert_s(&mut mesh, SPoint { a: s[0], b: s[1], t }, &mut stats)?;
                    stats.protection_points += 1;
                    let ps = &mut pieces[k as usize];
                    let i = ps.iter().position(|p| p.t0 < t && t < p.t1).ok_or_else(|| {
                        Error::Internal(format!("segment {k}: no piece holds the protection point"))
                    })?;
                    let p = ps[i];
                    ps[i] = Piece { t1: t, v: id, ..p };
                    ps.insert(i + 1, Piece { t0: t, u: id, ..p });
                }
            }
            continue;
        }
        // 2. bisection of every missing piece
        for &(k, i) in missing.iter().rev() {
            let p = pieces[k][i];
            if p.depth >= max_depth {
                return Err(Error::Internal(format!(
                    "segment {} needs more than {max_depth} halvings near t = {}", p.seg, p.t0)));
            }
            let tm = p.t0 + (p.t1 - p.t0) / 2.0;
            if !(tm > p.t0 && tm < p.t1) {
                return Err(Error::Internal(format!(
                    "segment {}: a piece is too short to split (do segments cross?)", p.seg)));
            }
            let s = segments[k];
            let id = insert_s(&mut mesh, SPoint { a: s[0], b: s[1], t: tm }, &mut stats)?;
            stats.bisection_points += 1;
            stats.max_depth = stats.max_depth.max(p.depth + 1);
            pieces[k][i] = Piece { t1: tm, v: id, depth: p.depth + 1, ..p };
            pieces[k].insert(i + 1, Piece { t0: tm, u: id, depth: p.depth + 1, ..p });
        }
    }

    let chains: Vec<Vec<u32>> = pieces.iter()
        .map(|ps| std::iter::once(ps[0].u).chain(ps.iter().map(|p| p.v)).collect())
        .collect();
    let tets = mesh.tets();
    let kernel = mesh.stats();
    Ok(Recovered { tets, s: mesh.g.s.clone(), chains, stats, kernel, mixed: mesh.g.n })
}

/// True when two of the segments `inc` at vertex v meet at less than 90 degrees.
fn is_acute(points: &[P3], segments: &[[u32; 2]], inc: &[u32], v: usize) -> bool {
    let pv = &points[v];
    let other = |k: u32| {
        let s = segments[k as usize];
        &points[if s[0] as usize == v { s[1] } else { s[0] } as usize]
    };
    inc.iter().enumerate().any(|(i, &k1)| inc[i + 1..].iter().any(|&k2| {
        let (a, b) = (other(k1), other(k2));
        (0..3).map(|c| (a[c] - pv[c]) * (b[c] - pv[c])).sum::<f64>() > 0.0
    }))
}

fn exact_point(a: &P3, b: &P3, t: f64) -> bool {
    let input = [*a, *b];
    let s = [SPoint { a: 0, b: 1, t }];
    crate::mixed::Mixed { input: &input, s: &s }.is_exact(Pt::S(0))
}

fn insert_s(mesh: &mut Mesh<MixedPoints>, sp: SPoint, stats: &mut RecoveryStats) -> Result<u32, Error> {
    let id = mesh.g.push(sp);
    if exact_point(&mesh.g.input[sp.a as usize], &mesh.g.input[sp.b as usize], sp.t) {
        stats.exact_points += 1;
    }
    match mesh.insert(id)? {
        None => Ok(id),
        Some(v) => Err(Error::Internal(format!("the point on segment {}-{} at t = {} equals vertex {v}", sp.a, sp.b, sp.t))),
    }
}

/// For each point, the distance to the nearest other point (a sweep over x with a
/// shrinking window; exact choice of the radius is not needed).
fn nearest_distances(points: &[P3]) -> Vec<f64> {
    let mut by: Vec<u32> = (0..points.len() as u32).collect();
    by.sort_unstable_by(|&i, &j| points[i as usize][0].total_cmp(&points[j as usize][0]));
    let mut best = vec![f64::INFINITY; points.len()];
    for x in 0..by.len() {
        let i = by[x] as usize;
        for &j in &by[x + 1..] {
            let j = j as usize;
            let dx = points[j][0] - points[i][0];
            if dx > best[i] {
                break;
            }
            let d = dist(&points[i], &points[j]);
            best[i] = best[i].min(d);
            best[j] = best[j].min(d);
        }
    }
    // the backward direction: the window above covers it for i, but j's best may need
    // points before it; a second pass in reverse order completes it
    for x in (0..by.len()).rev() {
        let i = by[x] as usize;
        for &j in by[..x].iter().rev() {
            let j = j as usize;
            let dx = points[i][0] - points[j][0];
            if dx > best[i] {
                break;
            }
            best[i] = best[i].min(dist(&points[i], &points[j]));
        }
    }
    best
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::delaunay::verify_with;
    use std::collections::HashSet;

    fn lcg(s: &mut u64) -> f64 {
        *s = s.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
        (*s >> 11) as f64 / (1u64 << 53) as f64
    }

    /// Recovers, then checks the result from the arrays: Delaunay over the input and S
    /// points (exact, under the perturbation), every segment a chain of edges from a to
    /// b through its own S points with increasing t.
    fn check(points: &[P3], segments: &[[u32; 2]]) -> Recovered {
        let r = recover(points, segments, 60).unwrap();
        let mut g = MixedPoints { input: points.to_vec(), s: r.s.clone(), n: MixedCounters::default() };
        verify_with(&mut g, points.len() + r.s.len(), &r.tets).unwrap();
        let edges: HashSet<(u32, u32)> = r.tets.iter()
            .flat_map(|v| (0..4).flat_map(move |i| (i + 1..4).map(move |j| (v[i].min(v[j]), v[i].max(v[j])))))
            .collect();
        let mut used = HashSet::new();
        for (k, c) in r.chains.iter().enumerate() {
            let s = segments[k];
            assert_eq!((c[0], *c.last().unwrap()), (s[0], s[1]), "segment {k}");
            for w in c.windows(2) {
                assert!(edges.contains(&(w[0].min(w[1]), w[0].max(w[1]))), "segment {k}: {w:?} is not an edge");
            }
            let mut last = 0.0;
            for &x in &c[1..c.len() - 1] {
                let sp = r.s[x as usize - points.len()];
                assert_eq!([sp.a, sp.b], s, "segment {k}");
                assert!(sp.t > last);
                last = sp.t;
                assert!(used.insert(x), "S point {x} on two segments");
            }
        }
        assert_eq!(used.len(), r.s.len());
        assert_eq!(r.s.len() as u32, r.stats.protection_points + r.stats.bisection_points);
        r
    }

    #[test]
    fn long_segments_through_a_point_cloud_are_recovered() {
        let mut s = 11u64;
        let mut pts: Vec<P3> = (0..600).map(|_| [lcg(&mut s), lcg(&mut s), lcg(&mut s)]).collect();
        // segments between far corners of the cloud: they pass close to many points
        let base = pts.len() as u32;
        // (three pairwise skew segments: crossing segments are invalid input)
        for c in [[-0.1, -0.1, -0.1], [1.1, 1.1, 1.1], [1.1, -0.1, 0.3], [-0.1, 1.1, 0.7], [0.4, 1.1, -0.1], [0.65, -0.1, 1.1]] {
            pts.push(c);
        }
        let segs = vec![[base, base + 1], [base + 2, base + 3], [base + 4, base + 5], [3, 77], [5, 401], [99, 500]];
        let r = check(&pts, &segs);
        assert!(r.stats.bisection_points > 0, "{:?}", r.stats);
        eprintln!("cloud: {:?} {:?}", r.stats, r.mixed);
    }

    #[test]
    fn acute_fans_are_protected() {
        // segments from the origin at 1, 5 and 30 degrees in the xy-plane, plus a cloud
        let mut s = 3u64;
        let mut pts: Vec<P3> = vec![[0.0, 0.0, 0.0]];
        let mut segs = Vec::new();
        for deg in [0.0f64, 1.0, 5.0, 30.0] {
            let a = deg.to_radians();
            pts.push([a.cos(), a.sin(), 0.0]);
            segs.push([0, pts.len() as u32 - 1]);
        }
        for _ in 0..300 {
            pts.push([lcg(&mut s) * 2.0 - 0.5, lcg(&mut s) * 2.0 - 1.0, lcg(&mut s) * 0.2 - 0.1]);
        }
        let r = check(&pts, &segs);
        assert_eq!(r.stats.protected_vertices, 1, "{:?}", r.stats);
        assert_eq!(r.stats.protection_points, 4);
        eprintln!("fan: {:?}", r.stats);
    }

    #[test]
    fn cell_diagonals_of_a_cospherical_lattice_are_recovered() {
        let n = 5;
        let mut pts = Vec::new();
        let id = |i: usize, j: usize, k: usize| (i * n * n + j * n + k) as u32;
        for i in 0..n {
            for j in 0..n {
                for k in 0..n {
                    pts.push([i as f64 * 0.25, j as f64 * 0.25, k as f64 * 0.25]);
                }
            }
        }
        let mut segs = Vec::new();
        for i in 0..n - 1 {
            for j in 0..n - 1 {
                // a body diagonal of every cell in one layer, the other face diagonal in the next
                segs.push([id(i, j, 1), id(i + 1, j + 1, 2)]);
                segs.push([id(i + 1, j, 3), id(i, j + 1, 3)]);
            }
        }
        let r = check(&pts, &segs);
        eprintln!("lattice: {:?}", r.stats);
    }

    #[test]
    fn a_twisted_prism_and_its_segments_are_recovered() {
        // Schonhardt: two triangles, the top one twisted by 30 degrees, joined by the
        // diagonals of the twisted side faces
        let mut pts = Vec::new();
        for (h, rot) in [(0.0f64, 0.0f64), (1.0, 30.0)] {
            for k in 0..3 {
                let a = (120.0 * k as f64 + rot).to_radians();
                pts.push([a.cos(), a.sin(), h]);
            }
        }
        let segs = vec![[0, 1], [1, 2], [2, 0], [3, 4], [4, 5], [5, 3], [0, 3], [1, 4], [2, 5], [0, 4], [1, 5], [2, 3]];
        let r = check(&pts, &segs);
        eprintln!("prism: {:?}", r.stats);
    }

    #[test]
    fn too_deep_recovery_and_bad_input_are_errors() {
        let mut s = 5u64;
        let mut pts: Vec<P3> = (0..400).map(|_| [lcg(&mut s), lcg(&mut s), lcg(&mut s)]).collect();
        pts.push([-0.1, -0.1, -0.1]);
        pts.push([1.1, 1.1, 1.1]);
        let segs = [[400, 401]];
        assert!(matches!(recover(&pts, &segs, 1), Err(Error::Internal(m)) if m.contains("halvings")));
        assert!(matches!(recover(&pts, &[[0, 0]], 60), Err(Error::Input(_))));
        assert!(matches!(recover(&pts, &[[0, 999]], 60), Err(Error::Input(_))));
        let mut twice = pts.clone();
        twice.push(pts[7]);
        assert!(matches!(recover(&twice, &[[0, 1]], 60), Err(Error::Input(m)) if m.contains("coincide")));
    }
}
