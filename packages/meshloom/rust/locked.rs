// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

//! Locked facets with Steiner points inside the domain only (the 3D plan's design option
//! (B)): Gmsh's contract, the given surface triangles are kept as they are.
//!
//! Boundary recovery may put S points on a locked facet or on its edges (the bad points).
//! They are moved off the surface one at a time, as in the boundary-recovery papers that
//! relocate Steiner points from the boundary into the interior (Si and Gärtner, "3D
//! boundary recovery by constrained Delaunay tetrahedralization", IJNME 85, 2011; George
//! and Borouchaki, "Delaunay Triangulation and Meshing", 1998, boundary enforcement).
//! For a bad point s:
//!
//! 1. On every facet through s, the subfacets around s (a fan) are triangulated again
//!    without s: ear clipping of the fan's outer polygon with exact in-plane predicates.
//!    When s lies on a segment, the polygon's closing side (or, inside a facet, a
//!    diagonal) is that segment's piece between s's neighbours on it.
//! 2. The tetrahedra around s are split into sectors by the facets through s. Each
//!    sector's boundary is its link (the faces opposite s) plus the new triangles on its
//!    side; it is refilled as a cone from a new point inside the sector, on the segment
//!    from s towards the centroid of the sector's boundary. The tetrahedra around s are
//!    positive, so s sees its link strictly from inside and so does a point close enough
//!    to s; a point off the facets' planes on the sector's side sees the new triangles
//!    from inside. Each cone is taken only when every new tetrahedron has exact
//!    orient3d > 0 and the boundary is closed (every edge in two faces, in opposite
//!    directions): over a closed oriented surface the signed tetrahedra of a cone sum to
//!    its winding number, so all-positive ones tile the sector exactly once.
//!
//! The space outside the domain (reached from the hull without crossing a subfacet) is
//! dropped first: no output needs it, refinement drops it too, and the hull may hold bad
//! points. The bad points stay in the S table, unused; mesh output drops unused points.

use std::collections::{HashMap, HashSet};

use crate::delaunay::Geom;
use crate::facetrec::{Boundary, INWARD};
use crate::mixed::{MixedCounters, MixedPoints, SPoint};
use crate::predicates::P3;

/// Fractions of the way from a bad point to its sector's centroid tried for the new
/// point, farthest first (better shaped tetrahedra), down to close to the point (where
/// the cone is valid by continuity).
/// Layers of tetrahedra a sector may grow by when no point near s sees it.
const GROW_LAYERS: usize = 3;

const STEPS: [f64; 9] = [0.5, 0.25, 0.1, 0.03, 1e-2, 1e-3, 1e-4, 1e-5, 1e-6];

fn key(f: [u32; 3]) -> [u32; 3] {
    let mut k = f;
    k.sort_unstable();
    k
}

fn face(t: &[u32; 4], i: usize) -> [u32; 3] {
    INWARD[i].map(|j| t[j])
}

/// Counts of what `relocate` did.
#[derive(Clone, Copy, Debug, Default)]
pub struct LockedStats {
    /// S points moved off locked facets and their edges
    pub removed: u32,
    /// new points inside the domain
    pub interior: u32,
    /// sectors refilled
    pub cells: u32,
    /// points collapsed onto a neighbour instead (no new point)
    pub collapsed: u32,
}

/// The tetrahedra, with their faces, and the stars of the points to move.
struct Mesh {
    tets: Vec<[u32; 4]>,
    alive: Vec<bool>,
    faces: HashMap<[u32; 3], Vec<usize>>,
    star: HashMap<u32, Vec<usize>>,
}

impl Mesh {
    fn add(&mut self, t: [u32; 4]) {
        let r = self.tets.len();
        self.tets.push(t);
        self.alive.push(true);
        for i in 0..4 {
            self.faces.entry(key(face(&t, i))).or_default().push(r);
        }
        for v in t {
            if let Some(s) = self.star.get_mut(&v) {
                s.push(r);
            }
        }
    }

    fn remove(&mut self, r: usize) {
        self.alive[r] = false;
        let t = self.tets[r];
        for i in 0..4 {
            let k = key(face(&t, i));
            if let Some(l) = self.faces.get_mut(&k) {
                l.retain(|&u| u != r);
                if l.is_empty() {
                    self.faces.remove(&k);
                }
            }
        }
        for v in t {
            if let Some(s) = self.star.get_mut(&v) {
                s.retain(|&u| u != r);
            }
        }
    }
}

/// Moves every S point off the locked facets (see the module notes). `points` are the
/// input points.
pub fn relocate(points: &[P3], b: &mut Boundary, locked: &[u32]) -> Result<LockedStats, String> {
    let n_in = points.len() as u32;
    let mut bad: Vec<u32> = locked.iter()
        .filter_map(|&f| b.plc.subfacets.get(f as usize))
        .flat_map(|subs| subs.iter().flatten().copied())
        .filter(|&v| v >= n_in).collect();
    bad.sort_unstable();
    bad.dedup();
    let mut stats = LockedStats::default();
    if bad.is_empty() {
        return Ok(stats);
    }
    let mut g = MixedPoints::new(points.to_vec());
    g.s = b.plc.rec.s.clone();

    // subfacets and their facets
    let mut sub_of: HashMap<[u32; 3], Vec<u32>> = HashMap::new();
    for (f, subs) in b.plc.subfacets.iter().enumerate() {
        for s in subs {
            sub_of.entry(key(*s)).or_default().push(f as u32);
        }
    }

    // the exterior, dropped
    let mut faces: HashMap<[u32; 3], Vec<usize>> = HashMap::new();
    for (r, t) in b.tets.iter().enumerate() {
        for i in 0..4 {
            faces.entry(key(face(t, i))).or_default().push(r);
        }
    }
    let mut exterior: HashSet<usize> = HashSet::new();
    let mut stack: Vec<usize> = Vec::new();
    let mut hull: Vec<[u32; 3]> = faces.iter().filter(|(k, o)| o.len() == 1 && !sub_of.contains_key(*k)).map(|(k, _)| *k).collect();
    hull.sort_unstable();
    for k in hull {
        let r = faces[&k][0];
        if exterior.insert(r) {
            stack.push(r);
        }
    }
    while let Some(r) = stack.pop() {
        for i in 0..4 {
            let k = key(face(&b.tets[r], i));
            if sub_of.contains_key(&k) {
                continue;
            }
            for &u in &faces[&k] {
                if exterior.insert(u) {
                    stack.push(u);
                }
            }
        }
    }
    let mut m = Mesh { tets: Vec::new(), alive: Vec::new(), faces: HashMap::new(),
                       star: bad.iter().map(|&v| (v, Vec::new())).collect() };
    for (r, t) in b.tets.iter().enumerate() {
        if !exterior.contains(&r) {
            m.add(*t);
        }
    }

    // a point that cannot move yet waits until its neighbours have moved; the order is
    // fixed (increasing index, then the waiting points again), so the result is too
    let mut queue: Vec<u32> = bad.clone();
    loop {
        let mut wait: Vec<u32> = Vec::new();
        let mut last = String::new();
        for &s in &queue {
            match relocate_one(&mut g, &mut m, &mut b.plc.subfacets, &mut sub_of, &mut b.plc.rec.chains, s, &mut stats) {
                Ok(()) => stats.removed += 1,
                Err(e) => {
                    last = format!("locked facets: moving S point {s}: {e}");
                    wait.push(s);
                }
            }
        }
        if wait.is_empty() {
            break;
        }
        if wait.len() == queue.len() {
            return Err(format!("{last} ({} points could not move)", wait.len()));
        }
        queue = wait;
    }

    b.tets = (0..m.tets.len()).filter(|&r| m.alive[r]).map(|r| m.tets[r]).collect();
    b.plc.rec.s = g.s;
    Ok(stats)
}

fn relocate_one(g: &mut MixedPoints, m: &mut Mesh, subfacets: &mut [Vec<[u32; 3]>], sub_of: &mut HashMap<[u32; 3], Vec<u32>>,
                chains: &mut [Vec<u32>], s: u32, stats: &mut LockedStats) -> Result<(), String> {
    let star: Vec<usize> = m.star[&s].clone();
    if star.is_empty() {
        return Err("it is in no tetrahedron".into());
    }
    // s's neighbours on its segment, if it lies on one
    let along: Option<(u32, u32)> = chains.iter().find_map(|ch| {
        let i = ch.iter().position(|&v| v == s)?;
        (i > 0 && i + 1 < ch.len()).then(|| (ch[i - 1], ch[i + 1]))
    });
    // 1. the fans and their new triangles
    let mut fan_of: HashMap<u32, Vec<[u32; 3]>> = HashMap::new();
    let mut fan_faces: HashSet<[u32; 3]> = HashSet::new();
    let mut seen: HashSet<[u32; 3]> = HashSet::new();
    for &r in &star {
        for i in 0..4 {
            let k = key(face(&m.tets[r], i));
            if !k.contains(&s) || !seen.insert(k) {
                continue;
            }
            if let Some(fs) = sub_of.get(&k) {
                fan_faces.insert(k);
                for &f in fs {
                    let w = *subfacets[f as usize].iter().find(|x| key(**x) == k).unwrap();
                    fan_of.entry(f).or_default().push(w);
                }
            }
        }
    }
    let mut patch: HashMap<u32, Vec<[u32; 3]>> = HashMap::new();
    let mut fs: Vec<u32> = fan_of.keys().copied().collect();
    fs.sort_unstable();
    for &f in &fs {
        let fan = &fan_of[&f];
        if fan.len() != subfacets[f as usize].iter().filter(|x| x.contains(&s)).count() {
            return Err(format!("facet {f}: some of its subfacets around the point are not faces"));
        }
        patch.insert(f, retriangulate(g, fan, s, along).map_err(|e| format!("facet {f}: {e}"))?);
    }

    // 2. sectors: the star joined across faces through s that are not subfacets
    let in_star: HashSet<usize> = star.iter().copied().collect();
    let mut sector: HashMap<usize, usize> = HashMap::new();
    let mut sectors: Vec<Vec<usize>> = Vec::new();
    for &r in &star {
        if sector.contains_key(&r) {
            continue;
        }
        let c = sectors.len();
        sector.insert(r, c);
        let mut stack = vec![r];
        let mut members = Vec::new();
        while let Some(x) = stack.pop() {
            members.push(x);
            for i in 0..4 {
                let k = key(face(&m.tets[x], i));
                if !k.contains(&s) || fan_faces.contains(&k) {
                    continue;
                }
                for &u in &m.faces[&k] {
                    if u != x && in_star.contains(&u) && !sector.contains_key(&u) {
                        sector.insert(u, c);
                        stack.push(u);
                    }
                }
            }
        }
        members.sort_unstable();
        sectors.push(members);
    }

    let mut new: Vec<[u32; 4]> = Vec::new();
    let mut new_points: Vec<SPoint> = Vec::new();
    let mut taken: HashSet<usize> = HashSet::new();
    for members in &sectors {
        // boundary: the link, and the new triangles of every fan on this side, wound inward
        let mut bnd: Vec<[u32; 3]> = Vec::new();
        let mut touch: HashMap<u32, (usize, [u32; 3], u32)> = HashMap::new();
        for &r in members {
            for i in 0..4 {
                let f = face(&m.tets[r], i);
                let k = key(f);
                if !k.contains(&s) {
                    bnd.push(f);
                } else if fan_faces.contains(&k) {
                    for &fi in &sub_of[&k] {
                        let e = touch.entry(fi).or_insert((0, f, m.tets[r][i]));
                        e.0 += 1;
                    }
                }
            }
        }
        let mut tf: Vec<u32> = touch.keys().copied().collect();
        tf.sort_unstable();
        let refs: Vec<([u32; 3], u32)> = tf.iter().map(|fi| (touch[fi].1, touch[fi].2)).collect();
        let mut patch_part: Vec<[u32; 3]> = Vec::new();
        for fi in tf {
            let (n, f, opp) = touch[&fi];
            if n != fan_of[&fi].len() {
                return Err(format!("a sector touches {n} of the {} subfacets around it on facet {fi}", fan_of[&fi].len()));
            }
            let side = g.orient3d([f[0], f[1], f[2], opp]);
            for t in &patch[&fi] {
                let o = g.orient3d([t[0], t[1], t[2], opp]);
                if o == 0 {
                    return Err(format!("facet {fi}: a new triangle is coplanar with a vertex across it"));
                }
                patch_part.push(if o == side { *t } else { [t[1], t[0], t[2]] });
            }
        }
        let link_part = bnd.clone();
        bnd.extend(patch_part.iter().copied());
        // closed
        let mut dir: HashMap<(u32, u32), i32> = HashMap::new();
        for f in &bnd {
            for j in 0..3 {
                *dir.entry((f[j], f[(j + 1) % 3])).or_default() += 1;
            }
        }
        if dir.iter().any(|(&(a, c), &n)| n != 1 || dir.get(&(c, a)).copied() != Some(1)) {
            return Err("a sector's boundary is not closed".into());
        }
        // the new point: towards the centroid of the boundary, then along the sum of the
        // inward unit normals of the facets around the sector (inside a reflex wedge too,
        // where the centroid can lie beyond one facet's plane)
        let (p0, dirs, size) = {
            let v = g.view();
            let xyz = |x: u32| v.rounded(v.from_id(x));
            let p0 = xyz(s);
            let mut verts: Vec<u32> = bnd.iter().flatten().copied().collect();
            verts.sort_unstable();
            verts.dedup();
            let mut c = [0.0; 3];
            let mut size = f64::INFINITY;
            for &x in &verts {
                let q = xyz(x);
                for k in 0..3 {
                    c[k] += q[k];
                }
                size = size.min(((q[0] - p0[0]).powi(2) + (q[1] - p0[1]).powi(2) + (q[2] - p0[2]).powi(2)).sqrt());
            }
            let c = c.map(|x| x / verts.len() as f64);
            let mut nsum = [0.0f64; 3];
            for (f, opp) in &refs {
                let (a, b, cc, o) = (xyz(f[0]), xyz(f[1]), xyz(f[2]), xyz(*opp));
                let (u, w) = ([b[0] - a[0], b[1] - a[1], b[2] - a[2]], [cc[0] - a[0], cc[1] - a[1], cc[2] - a[2]]);
                let mut n = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]];
                let len = (n[0] * n[0] + n[1] * n[1] + n[2] * n[2]).sqrt();
                if !(len > 0.0) {
                    continue;
                }
                if (o[0] - a[0]) * n[0] + (o[1] - a[1]) * n[1] + (o[2] - a[2]) * n[2] < 0.0 {
                    n = n.map(|x| -x);
                }
                for k in 0..3 {
                    nsum[k] += n[k] / len;
                }
            }
            let to_c = [c[0] - p0[0], c[1] - p0[1], c[2] - p0[2]];
            let nl = (nsum[0] * nsum[0] + nsum[1] * nsum[1] + nsum[2] * nsum[2]).sqrt();
            let mut dirs = vec![to_c];
            if nl > 0.0 {
                dirs.push(nsum.map(|x| x / nl * size));
            }
            (p0, dirs, size)
        };
        // per direction: the fractions of STEPS, then fractions of the largest step that
        // keeps the point on the inner side of every face of the boundary (in doubles,
        // from the faces' planes; the exact test below decides)
        let limits: Vec<f64> = {
            let v = g.view();
            let xyz = |x: u32| v.rounded(v.from_id(x));
            dirs.iter().map(|d| {
                let mut lim = f64::INFINITY;
                for f in &bnd {
                    let (a, b, c) = (xyz(f[0]), xyz(f[1]), xyz(f[2]));
                    let (u, w) = ([b[0] - a[0], b[1] - a[1], b[2] - a[2]], [c[0] - a[0], c[1] - a[1], c[2] - a[2]]);
                    // orient3d(a, b, c, p) = (p - a) . ((b - a) x (c - a)): the inner side
                    let n = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]];
                    let dist = (p0[0] - a[0]) * n[0] + (p0[1] - a[1]) * n[1] + (p0[2] - a[2]) * n[2];
                    let dn = d[0] * n[0] + d[1] * n[1] + d[2] * n[2];
                    if dn < 0.0 && dist > 0.0 {
                        lim = lim.min(dist / -dn);
                    }
                }
                lim
            }).collect()
        };
        let mut found = None;
        'search: for (d, lim) in dirs.iter().zip(&limits) {
            let mut lams: Vec<f64> = STEPS.to_vec();
            if lim.is_finite() {
                lams.extend([0.5, 0.125, 1.0 / 64.0].map(|x| x * lim.min(1.0)));
            }
            for lam in lams {
                let p = [0, 1, 2].map(|k| p0[k] + lam * d[k]);
                if p == p0 || !p.iter().all(|x| x.is_finite()) {
                    continue;
                }
                let apex = g.push(SPoint::vol(p));
                let ok = bnd.iter().all(|f| g.orient3d([f[0], f[1], f[2], apex]) > 0);
                let sp = g.pop_s().unwrap();
                if ok {
                    found = Some(sp);
                    break 'search;
                }
            }
        }
        if found.is_none() {
            // last: a point inside the kernel of the sector (the points that see every face
            // of its boundary from inside), the centroid of the kernel's vertices within a
            // box around s; needed where s sits within rounding of a face's plane
            let cands = {
                let v = g.view();
                let pts: Vec<[P3; 3]> = bnd.iter().map(|f| f.map(|x| v.rounded(v.from_id(x)))).collect();
                kernel_points(&pts, p0, size)
            };
            for p in cands {
                let apex = g.push(SPoint::vol(p));
                let ok = bnd.iter().all(|f| g.orient3d([f[0], f[1], f[2], apex]) > 0);
                let sp = g.pop_s().unwrap();
                if ok {
                    found = Some(sp);
                    break;
                }
            }
        }
        let mut extra: Vec<usize> = Vec::new();
        if found.is_none() {
            // grow the sector by layers of tetrahedra across faces that are neither through s
            // nor subfacets, and look for a kernel point of the larger region
            let mut region: Vec<usize> = members.clone();
            for _layer in 0..GROW_LAYERS {
                let inr: HashSet<usize> = region.iter().copied().collect();
                let mut add: Vec<usize> = Vec::new();
                for &r in &region {
                    for i in 0..4 {
                        let k = key(face(&m.tets[r], i));
                        if k.contains(&s) || sub_of.contains_key(&k) {
                            continue;
                        }
                        for &u in m.faces.get(&k).into_iter().flatten() {
                            if !inr.contains(&u) && !in_star.contains(&u) && !taken.contains(&u) {
                                add.push(u);
                            }
                        }
                    }
                }
                add.sort_unstable();
                add.dedup();
                if add.is_empty() {
                    break;
                }
                region.extend(add);
                let Some(gb) = grown_boundary(m, sub_of, &region, s, &patch_part) else { break };
                let cands = {
                    let v = g.view();
                    let pts: Vec<[P3; 3]> = gb.iter().map(|f| f.map(|x| v.rounded(v.from_id(x)))).collect();
                    let far = region.iter().flat_map(|&r| m.tets[r]).map(|x| {
                        let q = v.rounded(v.from_id(x));
                        ((q[0] - p0[0]).powi(2) + (q[1] - p0[1]).powi(2) + (q[2] - p0[2]).powi(2)).sqrt()
                    }).fold(0.0f64, f64::max);
                    kernel_points(&pts, p0, far)
                };
                for p in cands {
                    let apex = g.push(SPoint::vol(p));
                    let ok = gb.iter().all(|f| g.orient3d([f[0], f[1], f[2], apex]) > 0);
                    let sp = g.pop_s().unwrap();
                    if ok {
                        found = Some(sp);
                        break;
                    }
                }
                if found.is_some() {
                    extra = region.iter().copied().filter(|r| !in_star.contains(r)).collect();
                    bnd = gb;
                    break;
                }
            }
        }
        let _ = &link_part;
        let Some(sp) = found else {
            // no point sees this sector (s lies within rounding of a face's plane): collapse
            // s onto a neighbour instead, with no new point
            return collapse(g, m, subfacets, sub_of, chains, s, &star, &fan_of, along, stats)
                .map_err(|e| format!("no point near it sees a sector of {} tetrahedra, and {e}", members.len()));
        };
        let apex = (g.input.len() + g.s.len() + new_points.len()) as u32;
        new.extend(bnd.iter().map(|f| [f[0], f[1], f[2], apex]));
        new_points.push(sp);
        for r in extra {
            taken.insert(r);
        }
    }

    // apply
    for sp in new_points {
        g.push(sp);
        stats.interior += 1;
    }
    stats.cells += sectors.len() as u32;
    for &r in star.iter().chain(taken.iter()) {
        m.remove(r);
    }
    for t in new {
        m.add(t);
    }
    for (&f, fan) in &fan_of {
        let gone: HashSet<[u32; 3]> = fan.iter().map(|x| key(*x)).collect();
        subfacets[f as usize].retain(|x| !gone.contains(&key(*x)));
        for k in &gone {
            if let Some(l) = sub_of.get_mut(k) {
                l.retain(|&x| x != f);
                if l.is_empty() {
                    sub_of.remove(k);
                }
            }
        }
        for t in &patch[&f] {
            subfacets[f as usize].push(*t);
            sub_of.entry(key(*t)).or_default().push(f);
        }
    }
    for ch in chains.iter_mut() {
        ch.retain(|&v| v != s);
    }
    Ok(())
}

/// Collapses s onto a neighbour q: on its segment, one of its two neighbours there; inside
/// a facet, a vertex of its fan. The tetrahedra with both s and q go; in the others q
/// takes s's place. Taken when every new tetrahedron has exact orient3d > 0, no face then
/// lies in more than two tetrahedra and no subfacet repeats: the tetrahedra around s keep
/// tiling the same space, and each facet's subfacets the same polygon.
#[allow(clippy::too_many_arguments)]
fn collapse(g: &mut MixedPoints, m: &mut Mesh, subfacets: &mut [Vec<[u32; 3]>], sub_of: &mut HashMap<[u32; 3], Vec<u32>>,
            chains: &mut [Vec<u32>], s: u32, star: &[usize], fan_of: &HashMap<u32, Vec<[u32; 3]>>,
            along: Option<(u32, u32)>, stats: &mut LockedStats) -> Result<(), String> {
    let mut cand: Vec<u32> = match along {
        Some((a, b)) => vec![a, b],
        None => {
            let mut c: Vec<u32> = fan_of.values().flatten().flatten().copied().filter(|&v| v != s).collect();
            c.sort_unstable();
            c.dedup();
            c
        }
    };
    cand.dedup();
    let in_star: HashSet<usize> = star.iter().copied().collect();
    'next: for q in cand {
        let mapped: Vec<[u32; 4]> = star.iter().map(|&r| m.tets[r]).filter(|t| !t.contains(&q))
            .map(|t| t.map(|v| if v == s { q } else { v })).collect();
        if mapped.iter().any(|t| g.orient3d(*t) <= 0) {
            continue;
        }
        let mut count: HashMap<[u32; 3], usize> = HashMap::new();
        for t in &mapped {
            for i in 0..4 {
                *count.entry(key(face(t, i))).or_default() += 1;
            }
        }
        for (k, c) in &count {
            let old = m.faces.get(k).map_or(0, |l| l.iter().filter(|r| !in_star.contains(r)).count());
            if old + c > 2 {
                continue 'next;
            }
        }
        let mut new_subs: Vec<(u32, Vec<[u32; 3]>)> = Vec::new();
        for (&f, fan) in fan_of {
            let mut subs: Vec<[u32; 3]> = fan.iter().filter(|t| !t.contains(&q))
                .map(|t| t.map(|v| if v == s { q } else { v })).collect();
            subs.sort_unstable();
            let keys: HashSet<[u32; 3]> = subs.iter().map(|t| key(*t)).collect();
            let gone: HashSet<[u32; 3]> = fan.iter().map(|t| key(*t)).collect();
            if keys.len() != subs.len() || subfacets[f as usize].iter().any(|x| !gone.contains(&key(*x)) && keys.contains(&key(*x)))
                || subs.iter().any(|t| !count.contains_key(&key(*t))) {
                continue 'next;
            }
            new_subs.push((f, subs));
        }
        // apply
        for &r in star {
            m.remove(r);
        }
        for t in mapped {
            m.add(t);
        }
        for (f, subs) in new_subs {
            let gone: HashSet<[u32; 3]> = fan_of[&f].iter().map(|x| key(*x)).collect();
            subfacets[f as usize].retain(|x| !gone.contains(&key(*x)));
            for k in &gone {
                if let Some(l) = sub_of.get_mut(k) {
                    l.retain(|&x| x != f);
                    if l.is_empty() {
                        sub_of.remove(k);
                    }
                }
            }
            for t in subs {
                subfacets[f as usize].push(t);
                sub_of.entry(key(t)).or_default().push(f);
            }
        }
        for ch in chains.iter_mut() {
            ch.retain(|&v| v != s);
        }
        stats.collapsed += 1;
        let _ = &g;
        return Ok(());
    }
    Err("no collapse onto a neighbour keeps every tetrahedron positive".into())
}

/// The fan of subfacets around s on one facet, triangulated again without s by ear
/// clipping (exact in-plane predicates), wound like the fan.
fn retriangulate(g: &MixedPoints, fan: &[[u32; 3]], s: u32, along: Option<(u32, u32)>) -> Result<Vec<[u32; 3]>, String> {
    // the outer polygon: each subfacet [s, x, y] (rotated) gives the side x -> y
    let mut next: HashMap<u32, u32> = HashMap::new();
    let mut prev: HashMap<u32, u32> = HashMap::new();
    for t in fan {
        let i = t.iter().position(|&v| v == s).unwrap();
        let (x, y) = (t[(i + 1) % 3], t[(i + 2) % 3]);
        if next.insert(x, y).is_some() || prev.insert(y, x).is_some() {
            return Err("its subfacets around the point are not a fan".into());
        }
    }
    let mut starts: Vec<u32> = next.keys().copied().filter(|v| !prev.contains_key(v)).collect();
    starts.sort_unstable();
    let open = !starts.is_empty();
    if starts.len() > 1 {
        return Err("its subfacets around the point are not one fan".into());
    }
    let s0 = if open { starts[0] } else { *next.keys().min().unwrap() };
    let mut poly = vec![s0];
    let mut v = s0;
    while let Some(&w) = next.get(&v) {
        if w == s0 {
            break;
        }
        if poly.len() > fan.len() + 1 {
            return Err("its fan does not close".into());
        }
        poly.push(w);
        v = w;
    }
    if poly.len() != fan.len() + usize::from(open) {
        return Err("its subfacets around the point are not one fan".into());
    }
    // the plane's dominant axis and the fan's orientation in it
    let mv = g.view();
    let xyz = |v: u32| mv.rounded(mv.from_id(v));
    let t0 = fan[0];
    let (a, b2, c) = (xyz(t0[0]), xyz(t0[1]), xyz(t0[2]));
    let (u, w) = ([b2[0] - a[0], b2[1] - a[1], b2[2] - a[2]], [c[0] - a[0], c[1] - a[1], c[2] - a[2]]);
    let nrm = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]];
    let axis = (0..3).max_by(|&i, &j| nrm[i].abs().total_cmp(&nrm[j].abs())).unwrap();
    let mut cnt = MixedCounters::default();
    let mut o2 = |p: u32, q: u32, r: u32| mv.orient2d_proj(axis, [p, q, r].map(|x| mv.from_id(x)), &mut cnt);
    let sign = o2(t0[0], t0[1], t0[2]);
    if sign == 0 {
        return Err("a subfacet around the point is degenerate in its plane".into());
    }
    // pieces: a closed fan inside a segment's piece splits along it
    let mut pieces: Vec<Vec<u32>> = vec![poly.clone()];
    if !open {
        if let Some((x, y)) = along {
            if let (Some(i), Some(j)) = (poly.iter().position(|&v| v == x), poly.iter().position(|&v| v == y)) {
                let (i, j) = (i.min(j), i.max(j));
                pieces = vec![poly[i..=j].to_vec(), poly[j..].iter().chain(&poly[..=i]).copied().collect()];
            }
        }
    }
    let mut out = Vec::new();
    for mut pl in pieces {
        while pl.len() > 3 {
            let n = pl.len();
            let mut ear = None;
            for i in 0..n {
                let (p, v, q) = (pl[(i + n - 1) % n], pl[i], pl[(i + 1) % n]);
                if o2(p, v, q) != sign {
                    continue;
                }
                let mut clear = true;
                for &x in &pl {
                    if x == p || x == v || x == q {
                        continue;
                    }
                    if o2(p, v, x) * sign >= 0 && o2(v, q, x) * sign >= 0 && o2(q, p, x) * sign >= 0 {
                        clear = false;
                        break;
                    }
                }
                if clear {
                    ear = Some(i);
                    break;
                }
            }
            let Some(i) = ear else { return Err("no ear in its polygon around the point".into()) };
            out.push([pl[(i + n - 1) % n], pl[i], pl[(i + 1) % n]]);
            pl.remove(i);
        }
        if o2(pl[0], pl[1], pl[2]) != sign {
            return Err("its polygon around the point has no area left".into());
        }
        out.push([pl[0], pl[1], pl[2]]);
    }
    Ok(out)
}

/// The boundary of a grown sector: the faces of its tetrahedra that are not through s and
/// not shared inside it, then the new fan triangles. None when the region straddles a
/// subfacet, its boundary is not closed, or a vertex other than s would be inside it.
fn grown_boundary(m: &Mesh, sub_of: &HashMap<[u32; 3], Vec<u32>>, region: &[usize], s: u32, patch_part: &[[u32; 3]])
                  -> Option<Vec<[u32; 3]>> {
    let inr: HashSet<usize> = region.iter().copied().collect();
    let mut out: Vec<[u32; 3]> = Vec::new();
    for &r in region {
        for i in 0..4 {
            let f = face(&m.tets[r], i);
            let k = key(f);
            if k.contains(&s) {
                continue;
            }
            let inside = m.faces.get(&k).into_iter().flatten().any(|&u| u != r && inr.contains(&u));
            if inside {
                if sub_of.contains_key(&k) {
                    return None;
                }
                continue;
            }
            out.push(f);
        }
    }
    out.extend(patch_part.iter().copied());
    let mut dir: HashMap<(u32, u32), i32> = HashMap::new();
    for f in &out {
        for j in 0..3 {
            *dir.entry((f[j], f[(j + 1) % 3])).or_default() += 1;
        }
    }
    if dir.iter().any(|(&(a, c), &n)| n != 1 || dir.get(&(c, a)).copied() != Some(1)) {
        return None;
    }
    let on: HashSet<u32> = out.iter().flatten().copied().collect();
    if region.iter().flat_map(|&r| m.tets[r]).any(|v| v != s && !on.contains(&v)) {
        return None;
    }
    Some(out)
}

/// Points inside the kernel of a closed boundary (faces wound inward), in doubles: the
/// centroid of the vertices of the kernel clipped to a box of half side `size` around `p0`,
/// then points between it and `p0`. The caller checks each exactly.
fn kernel_points(faces: &[[P3; 3]], p0: P3, size: f64) -> Vec<P3> {
    // half-spaces n . p >= c
    let mut hs: Vec<(P3, f64)> = Vec::new();
    for f in faces {
        let (a, b, c) = (f[0], f[1], f[2]);
        let (u, w) = ([b[0] - a[0], b[1] - a[1], b[2] - a[2]], [c[0] - a[0], c[1] - a[1], c[2] - a[2]]);
        let n = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]];
        let len = (n[0] * n[0] + n[1] * n[1] + n[2] * n[2]).sqrt();
        if len > 0.0 {
            let n = n.map(|x| x / len);
            hs.push((n, n[0] * a[0] + n[1] * a[1] + n[2] * a[2]));
        }
    }
    for k in 0..3 {
        let mut e = [0.0; 3];
        e[k] = 1.0;
        hs.push((e, p0[k] - size));
        e[k] = -1.0;
        hs.push((e, -(p0[k] + size)));
    }
    let tol = 1e-12 * size.max(f64::MIN_POSITIVE);
    let mut verts: Vec<P3> = Vec::new();
    let m = hs.len();
    for i in 0..m {
        for j in i + 1..m {
            for k in j + 1..m {
                let (a, b, c) = (hs[i].0, hs[j].0, hs[k].0);
                let det = a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0]) + a[2] * (b[0] * c[1] - b[1] * c[0]);
                if det.abs() < 1e-12 {
                    continue;
                }
                let r = [hs[i].1, hs[j].1, hs[k].1];
                // Cramer's rule
                let solve = |col: usize| {
                    let mut mm = [a, b, c];
                    for (row, rv) in mm.iter_mut().zip(r) {
                        row[col] = rv;
                    }
                    let (a, b, c) = (mm[0], mm[1], mm[2]);
                    (a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0]) + a[2] * (b[0] * c[1] - b[1] * c[0])) / det
                };
                let p = [solve(0), solve(1), solve(2)];
                if hs.iter().all(|(n, c)| n[0] * p[0] + n[1] * p[1] + n[2] * p[2] >= c - tol) {
                    verts.push(p);
                }
            }
        }
    }
    if verts.is_empty() {
        return Vec::new();
    }
    let mut cen = [0.0; 3];
    for p in &verts {
        for k in 0..3 {
            cen[k] += p[k];
        }
    }
    let cen = cen.map(|x| x / verts.len() as f64);
    [1.0, 0.5, 0.25, 0.1].iter().map(|&t| [0, 1, 2].map(|k| p0[k] + t * (cen[k] - p0[k]))).collect()
}
