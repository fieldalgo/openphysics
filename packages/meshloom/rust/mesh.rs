// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

//! Regions, rounding, certification and the tetrahedral mesh output (M4 stage 5 of the
//! pre-registered 3D plan; design note section 5).
//!
//! After boundary recovery the tetrahedra fill the convex hull and every subfacet is a
//! face. Then:
//! 1. **Components.** Tetrahedra joined by a face that is not a subfacet form one
//!    component. A component that reaches a hull face which is not a subfacet is outside.
//! 2. **Domain.** In `Regions` mode every other component is a region: the components
//!    of a multi-region PLC. In `Parity` mode (closed surfaces, the even-odd domain of
//!    the C14 protocol) a component's parity is the number of facets crossed from the
//!    outside, mod 2, and the odd components form one region; a component reached with
//!    both parities is a typed error naming the facet.
//! 3. **Rounding.** Every S point is rounded once to the nearest double; input points
//!    are kept bit for bit. Unused points are dropped and the rest renumbered.
//! 4. **Certification.** Every output tetrahedron must have exact `orient3d > 0` on
//!    the output doubles. A tetrahedron that rounding made flat or inverted is a typed
//!    error with its location (flip repair comes next); an invalid mesh is never returned.
//!
//! The output follows the plan's contract: nodes, tetrahedra, regions, boundary faces
//! by facet (wound outward), and interfaces between regions (wound from the lower
//! region to the higher).

use std::collections::{HashMap, HashSet};

use crate::facetrec::Boundary;
use crate::mixed::Mixed;
use crate::predicates::{orient3d_exact, P3};

const NONE: u32 = u32::MAX;
const INWARD: [[usize; 3]; 4] = [[1, 3, 2], [0, 2, 3], [0, 3, 1], [0, 1, 2]];

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Domain {
    /// every bounded component is its own region
    Regions,
    /// the odd-parity components form one region (even-odd domain of closed surfaces)
    Parity,
}

pub struct TetMesh {
    pub nodes: Vec<P3>,
    pub tets: Vec<[u32; 4]>,
    pub regions: Vec<u32>,
    pub region_count: u32,
    /// (facet, face wound outward)
    pub boundary: Vec<(u32, [u32; 3])>,
    /// (region a, region b, face wound from a to b), a < b
    pub interfaces: Vec<(u32, u32, [u32; 3])>,
    /// for each output node, its global point index (input points first, then S points)
    pub source: Vec<u32>,
    pub repair: RepairStats,
}

fn key(f: [u32; 3]) -> [u32; 3] {
    let mut k = f;
    k.sort_unstable();
    k
}

fn face(t: &[u32; 4], i: usize) -> [u32; 3] {
    INWARD[i].map(|j| t[j])
}

/// Labels, rounds and certifies the result of boundary recovery.
pub fn build(points: &[P3], b: &Boundary, domain: Domain) -> Result<TetMesh, String> {
    let tets = &b.tets;
    // the facets of each subfacet (two facets can share one, e.g. touching shells)
    let mut facet_of: HashMap<[u32; 3], u32> = HashMap::new();
    for (f, tris) in b.plc.subfacets.iter().enumerate() {
        for t in tris {
            facet_of.entry(key(*t)).or_insert(f as u32);
        }
    }
    let mut owners: HashMap<[u32; 3], Vec<(u32, usize)>> = HashMap::with_capacity(2 * tets.len());
    for (t, v) in tets.iter().enumerate() {
        for i in 0..4 {
            owners.entry(key(face(v, i))).or_default().push((t as u32, i));
        }
    }
    // 1. components across faces that are not subfacets
    let mut comp = vec![NONE; tets.len()];
    let mut ncomp = 0u32;
    for s in 0..tets.len() {
        if comp[s] != NONE {
            continue;
        }
        comp[s] = ncomp;
        let mut stack = vec![s as u32];
        while let Some(t) = stack.pop() {
            let v = tets[t as usize];
            for i in 0..4 {
                let k = key(face(&v, i));
                if facet_of.contains_key(&k) {
                    continue;
                }
                for &(u, _) in &owners[&k] {
                    if comp[u as usize] == NONE {
                        comp[u as usize] = ncomp;
                        stack.push(u);
                    }
                }
            }
        }
        ncomp += 1;
    }
    let mut outside = vec![false; ncomp as usize];
    for (k, list) in &owners {
        if list.len() == 1 && !facet_of.contains_key(k) {
            outside[comp[list[0].0 as usize] as usize] = true;
        }
    }
    // the component graph across subfacets
    let mut adj: Vec<Vec<(u32, u32)>> = vec![Vec::new(); ncomp as usize];
    for (k, list) in &owners {
        if let (Some(&f), [(a, _), (b2, _)]) = (facet_of.get(k), list.as_slice()) {
            let (ca, cb) = (comp[*a as usize], comp[*b2 as usize]);
            if ca != cb {
                adj[ca as usize].push((cb, f));
                adj[cb as usize].push((ca, f));
            }
        }
    }
    // 2. the domain: region index per component, NONE outside
    let mut region_of = vec![NONE; ncomp as usize];
    match domain {
        Domain::Regions => {
            for c in 0..ncomp as usize {
                if !outside[c] {
                    region_of[c] = 0; // numbered below by first appearance
                }
            }
        }
        Domain::Parity => {
            // node ncomp is the space beyond the hull: joined to a component through a
            // hull face, crossing a facet when that face is a subfacet
            let out = ncomp as usize;
            adj.push(Vec::new());
            for (k, list) in &owners {
                if let ([(t, _)], Some(&f)) = (list.as_slice(), facet_of.get(k)) {
                    let c = comp[*t as usize];
                    adj[out].push((c, f));
                    adj[c as usize].push((out as u32, f));
                }
            }
            let mut parity = vec![u8::MAX; ncomp as usize + 1];
            parity[out] = 0;
            let mut stack: Vec<u32> = vec![out as u32];
            for c in 0..ncomp as usize {
                if outside[c] {
                    parity[c] = 0;
                    stack.push(c as u32);
                }
            }
            while let Some(c) = stack.pop() {
                for &(d, f) in &adj[c as usize] {
                    let p = parity[c as usize] ^ 1;
                    if parity[d as usize] == u8::MAX {
                        parity[d as usize] = p;
                        stack.push(d);
                    } else if parity[d as usize] != p {
                        return Err(format!("facet {f}: the parity of the regions it separates is inconsistent"));
                    }
                }
            }
            if let Some(c) = parity.iter().position(|&p| p == u8::MAX) {
                return Err(format!("component {c} is not reached from the outside"));
            }
            for c in 0..ncomp as usize {
                if parity[c] == 1 {
                    region_of[c] = 0;
                }
            }
        }
    }
    // keep tetrahedra of the domain, regions numbered by first appearance
    let mut number: HashMap<u32, u32> = HashMap::new();
    let mut kept: Vec<usize> = Vec::new();
    let mut regions = Vec::new();
    for (t, &c) in comp.iter().enumerate() {
        if region_of[c as usize] == NONE {
            continue;
        }
        let key_c = if domain == Domain::Parity { 0 } else { c };
        let n = number.len() as u32;
        let r = *number.entry(key_c).or_insert(n);
        kept.push(t);
        regions.push(r);
    }
    if kept.is_empty() {
        return Err("the domain is empty".into());
    }
    let region_count = number.len() as u32;
    // 3. rounding and renumbering
    let m = Mixed { input: points, s: &b.plc.rec.s };
    let mut new_id: HashMap<u32, u32> = HashMap::new();
    let mut nodes: Vec<P3> = Vec::new();
    let mut source: Vec<u32> = Vec::new();
    let mut out_tets = Vec::with_capacity(kept.len());
    for &t in &kept {
        let v = tets[t].map(|g| {
            *new_id.entry(g).or_insert_with(|| {
                nodes.push(m.rounded(m.from_id(g)));
                source.push(g);
                (nodes.len() - 1) as u32
            })
        });
        out_tets.push(v);
    }
    // no duplicate nodes after rounding
    {
        let mut seen: HashMap<[u64; 3], u32> = HashMap::new();
        for (i, p) in nodes.iter().enumerate() {
            let k = p.map(|x| if x == 0.0 { 0 } else { x.to_bits() });
            if let Some(j) = seen.insert(k, i as u32) {
                return Err(format!("rounding made points {} and {} equal at {p:?}", source[j as usize], source[i]));
            }
        }
    }
    // 4. certification, with flip repair of what rounding made flat or inverted
    let fixed_faces: HashSet<[u32; 3]> = facet_of.keys()
        .filter_map(|k| Some(key(k.map(|g| new_id.get(&g).copied()).iter().copied().collect::<Option<Vec<u32>>>()?
            .try_into().ok()?))).collect();
    let fixed_edges: HashSet<(u32, u32)> = b.plc.rec.chains.iter()
        .flat_map(|c| c.windows(2).map(|w| (w[0], w[1])))
        .filter_map(|(a, c)| Some((*new_id.get(&a)?, *new_id.get(&c)?)))
        .map(|(a, c)| (a.min(c), a.max(c))).collect();
    let mut labels: Vec<u32> = (0..out_tets.len() as u32).collect();
    let rs = repair(&nodes, &mut out_tets, &mut labels, &fixed_faces, &fixed_edges)?;
    // flips stay inside one region
    let regions: Vec<u32> = labels.iter().map(|&l| regions[l as usize]).collect();
    for (t, v) in out_tets.iter().enumerate() {
        if orient(&nodes, *v) <= 0 {
            return Err(format!("tetrahedron {t} failed certification after repair"));
        }
    }
    {
        let mut count: HashMap<[u32; 3], u32> = HashMap::new();
        for v in &out_tets {
            for i in 0..4 {
                let c = count.entry(key(face(v, i))).or_default();
                *c += 1;
                if *c > 2 {
                    return Err(format!("face {:?} is in more than two tetrahedra after repair", key(face(v, i))));
                }
            }
        }
    }
    // boundary faces and interfaces, from the output arrays
    let facet_out: HashMap<[u32; 3], u32> = facet_of.iter()
        .filter_map(|(k, &f)| Some((key([*new_id.get(&k[0])?, *new_id.get(&k[1])?, *new_id.get(&k[2])?]), f)))
        .collect();
    let mut owners_out: HashMap<[u32; 3], Vec<usize>> = HashMap::with_capacity(2 * out_tets.len());
    for (j, v) in out_tets.iter().enumerate() {
        for i in 0..4 {
            owners_out.entry(key(face(v, i))).or_default().push(j);
        }
    }
    let mut boundary = Vec::new();
    let mut interfaces = Vec::new();
    for (j, v) in out_tets.iter().enumerate() {
        for i in 0..4 {
            let f = face(v, i);
            let k = key(f);
            let outward = [f[0], f[2], f[1]];
            let r = regions[j];
            match owners_out[&k].iter().copied().find(|&u| u != j) {
                None => {
                    let tag = *facet_out.get(&k).ok_or_else(|| format!("boundary face {k:?} of the domain is not a subfacet"))?;
                    boundary.push((tag, outward));
                }
                Some(u) if regions[u] > r => interfaces.push((r, regions[u], outward)),
                Some(_) => {}
            }
        }
    }
    Ok(TetMesh { nodes, tets: out_tets, regions, region_count, boundary, interfaces, source, repair: rs })
}

#[derive(Debug, Clone, Copy, Default)]
pub struct RepairStats {
    /// tetrahedra that rounding made flat or inverted
    pub inverted: u32,
    pub flips23: u32,
    pub flips32: u32,
    /// edge removals with a ring of four to seven tetrahedra
    pub removals: u32,
}

fn orient(nodes: &[P3], t: [u32; 4]) -> i8 {
    let p = t.map(|i| nodes[i as usize]);
    orient3d_exact(&p[0], &p[1], &p[2], &p[3])
}

/// True when replacing `gone` by `new` leaves every face in at most two tetrahedra and
/// adds no face twice (`faces` is the face map before the change).
fn local_ok(faces: &HashMap<[u32; 3], Vec<usize>>, tets: &[[u32; 4]], gone: &[usize], new: &[[u32; 4]]) -> bool {
    let mut delta: HashMap<[u32; 3], i32> = HashMap::new();
    for &r in gone {
        for i in 0..4 {
            *delta.entry(key(face(&tets[r], i))).or_default() -= 1;
        }
    }
    for v in new {
        for i in 0..4 {
            *delta.entry(key(face(v, i))).or_default() += 1;
        }
    }
    delta.iter().all(|(k, d)| faces.get(k).map_or(0, |l| l.len() as i32) + d <= 2)
}

/// Repairs tetrahedra that are flat or inverted on `nodes` by 2-3 and 3-2 flips that
/// keep every face of `fixed_faces` and every edge of `fixed_edges`. A flip is applied
/// only when all of its new tetrahedra are positive. `labels` follows the tetrahedra
/// (a flip never crosses a fixed face, so its tetrahedra share one label).
pub fn repair(nodes: &[P3], tets: &mut Vec<[u32; 4]>, labels: &mut Vec<u32>, fixed_faces: &HashSet<[u32; 3]>,
              fixed_edges: &HashSet<(u32, u32)>) -> Result<RepairStats, String> {
    let mut st = RepairStats::default();
    let bad0 = tets.iter().filter(|t| orient(nodes, **t) <= 0).count();
    st.inverted = bad0 as u32;
    if bad0 == 0 {
        return Ok(st);
    }
    let edge = |a: u32, b: u32| (a.min(b), a.max(b));
    for _round in 0..64 * (bad0 + 1) {
        let bad: Vec<usize> = (0..tets.len()).filter(|&t| orient(nodes, tets[t]) <= 0).collect();
        if bad.is_empty() {
            return Ok(st);
        }
        let mut faces: HashMap<[u32; 3], Vec<usize>> = HashMap::new();
        let mut edges: HashMap<(u32, u32), Vec<usize>> = HashMap::new();
        for (i, v) in tets.iter().enumerate() {
            for k in 0..4 {
                faces.entry(key(face(v, k))).or_default().push(i);
                for l in k + 1..4 {
                    edges.entry(edge(v[k], v[l])).or_default().push(i);
                }
            }
        }
        let mut done = false;
        for &t in &bad {
        // edge removal (3-2 for a ring of three, 4-4 for four, up to seven): the
        // tetrahedra around an edge of t replaced by a fan triangulation of the ring
        let v = tets[t];
        'edges: for k in 0..4 {
            for l in k + 1..4 {
                let (d, e) = (v[k], v[l]);
                if fixed_edges.contains(&edge(d, e)) {
                    continue;
                }
                let ring_tets = edges[&edge(d, e)].clone();
                let n = ring_tets.len();
                if !(3..=7).contains(&n) || ring_tets.iter().any(|&r| labels[r] != labels[t]) {
                    continue;
                }
                // faces through the edge must not be fixed; the ring in cyclic order
                let mut link: HashMap<u32, Vec<u32>> = HashMap::new();
                let mut blocked = false;
                for &r in &ring_tets {
                    let xy: Vec<u32> = tets[r].iter().copied().filter(|&x| x != d && x != e).collect();
                    for &x in &xy {
                        if fixed_faces.contains(&key([d, e, x])) {
                            blocked = true;
                        }
                    }
                    link.entry(xy[0]).or_default().push(xy[1]);
                    link.entry(xy[1]).or_default().push(xy[0]);
                }
                if blocked || link.len() != n || link.values().any(|w| w.len() != 2) {
                    continue; // an edge on the boundary, or a ring that is not a cycle
                }
                let start = *link.keys().min().unwrap();
                let mut ring = vec![start];
                let mut prev = start;
                let mut cur = link[&start][0];
                while cur != start {
                    ring.push(cur);
                    let next = if link[&cur][0] == prev { link[&cur][1] } else { link[&cur][0] };
                    prev = cur;
                    cur = next;
                }
                if ring.len() != n {
                    continue;
                }
                for apex in 0..n {
                    let mut new = Vec::with_capacity(2 * (n - 2));
                    let mut ok = true;
                    for j in 1..n - 1 {
                        let (x, y, z) = (ring[apex], ring[(apex + j) % n], ring[(apex + j + 1) % n]);
                        let (sd, se) = (orient(nodes, [x, y, z, d]), orient(nodes, [x, y, z, e]));
                        if sd == 0 || se == 0 || sd == se {
                            ok = false;
                            break;
                        }
                        new.push(if sd > 0 { [x, y, z, d] } else { [x, z, y, d] });
                        new.push(if se > 0 { [x, y, z, e] } else { [x, z, y, e] });
                    }
                    if !ok || !local_ok(&faces, tets, &ring_tets, &new) {
                        continue;
                    }
                    let lab = labels[t];
                    let mut gone = ring_tets.clone();
                    gone.sort_unstable_by(|x, y| y.cmp(x));
                    for r in gone {
                        tets.swap_remove(r);
                        labels.swap_remove(r);
                    }
                    labels.extend(std::iter::repeat_n(lab, new.len()));
                    tets.extend(new);
                    if n == 3 { st.flips32 += 1 } else { st.removals += 1 }
                    done = true;
                    break 'edges;
                }
            }
        }
        if !done {
            // 2-3: a face of t that is not fixed, with its neighbour
            for k in 0..4 {
                let f = face(&v, k);
                let fk = key(f);
                if fixed_faces.contains(&fk) {
                    continue;
                }
                let Some(u) = faces[&fk].iter().copied().find(|&u| u != t) else { continue };
                if labels[u] != labels[t] {
                    continue;
                }
                let d = v[k];
                let e = *tets[u].iter().find(|x| !f.contains(x)).unwrap();
                let s = [(f[0], f[1]), (f[1], f[2]), (f[2], f[0])].map(|(x, y)| orient(nodes, [x, y, d, e]));
                if s.iter().any(|&x| x == 0) || !(s.iter().all(|&x| x > 0) || s.iter().all(|&x| x < 0)) {
                    continue;
                }
                let new: Vec<[u32; 4]> = [(f[0], f[1]), (f[1], f[2]), (f[2], f[0])].iter()
                    .map(|&(x, y)| if s[0] > 0 { [x, y, d, e] } else { [y, x, d, e] }).collect();
                if new.iter().any(|n| orient(nodes, *n) <= 0) || edges.contains_key(&edge(d, e))
                    || !local_ok(&faces, tets, &[t, u], &new) {
                    continue;
                }
                let lab = labels[t];
                for r in if t > u { [t, u] } else { [u, t] } {
                    tets.swap_remove(r);
                    labels.swap_remove(r);
                }
                tets.extend(new);
                labels.extend([lab; 3]);
                st.flips23 += 1;
                done = true;
                break;
            }
        }
        if done {
            break;
        }
        }
        if !done {
            let p = tets[bad[0]].map(|i| nodes[i as usize]);
            return Err(format!("rounding to doubles made {} tetrahedra flat or inverted (one near {:?}), and no flip repairs them",
                               bad.len(), p[0]));
        }
    }
    Err("flip repair did not finish".into())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::plc::Plc;

    fn ring(base: u32) -> Vec<u32> {
        (0..4).map(|k| base + k).collect()
    }

    /// A box [0,a]^3 with an optional inner box [b,c]^3 (closed shells, no segments).
    fn boxes(inner: bool) -> Plc {
        let mut points = Vec::new();
        let mut facets = Vec::new();
        let add_box = |lo: f64, hi: f64, points: &mut Vec<P3>, facets: &mut Vec<Vec<Vec<u32>>>| {
            let b = points.len() as u32;
            for z in [lo, hi] {
                for (x, y) in [(lo, lo), (hi, lo), (hi, hi), (lo, hi)] {
                    points.push([x, y, z]);
                }
            }
            facets.push(vec![ring(b)]);
            facets.push(vec![ring(b + 4)]);
            for k in 0..4 {
                let (p, q) = (b + k, b + (k + 1) % 4);
                facets.push(vec![vec![p, q, q + 4, p + 4]]);
            }
        };
        add_box(0.0, 4.0, &mut points, &mut facets);
        if inner {
            add_box(1.0, 2.0, &mut points, &mut facets);
        }
        Plc { points, segments: Vec::new(), facets }
    }

    fn volume(m: &TetMesh, r: u32) -> f64 {
        m.tets.iter().zip(&m.regions).filter(|(_, &q)| q == r).map(|(t, _)| {
            let p = t.map(|i| m.nodes[i as usize]);
            let d = |a: P3, b: P3| [b[0] - a[0], b[1] - a[1], b[2] - a[2]];
            let (u, v, w) = (d(p[0], p[1]), d(p[0], p[2]), d(p[0], p[3]));
            (u[0] * (v[1] * w[2] - v[2] * w[1]) - u[1] * (v[0] * w[2] - v[2] * w[0]) + u[2] * (v[0] * w[1] - v[1] * w[0])) / 6.0
        }).sum()
    }

    #[test]
    fn nested_boxes_in_both_modes() {
        let plc = boxes(true);
        let b = crate::facetrec::recover_boundary(&plc, 60).unwrap();
        let m = build(&plc.points, &b, Domain::Regions).unwrap();
        assert_eq!(m.region_count, 2);
        let vols: Vec<f64> = (0..2).map(|r| volume(&m, r)).collect();
        let near = |x: f64, y: f64| (x - y).abs() <= 1e-12 * y;
        assert!(vols.iter().any(|&v| near(v, 1.0)) && vols.iter().any(|&v| near(v, 63.0)), "{vols:?}");
        assert_eq!(m.interfaces.len(), 12); // the inner box's 6 squares, 2 triangles each
        assert_eq!(m.boundary.len(), 12);
        let p = build(&plc.points, &b, Domain::Parity).unwrap();
        assert_eq!(p.region_count, 1);
        assert!(near(volume(&p, 0), 63.0)); // the shell between the boxes
        assert!(p.interfaces.is_empty());
        assert_eq!(p.boundary.len(), 24); // both boxes bound the shell
    }

    fn lcg(s: &mut u64) -> f64 {
        *s = s.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
        (*s >> 11) as f64 / (1u64 << 53) as f64
    }

    /// Delaunay tetrahedra of random points, then the points snapped to multiples of
    /// 2^-8 or 2^-10 (a coarse stand-in for rounding): flat and inverted tetrahedra
    /// appear. Interior ones must be repaired; ones against the fixed hull may be
    /// refused; whatever repair returns must be valid.
    #[test]
    fn flip_repair_on_snapped_points() {
        let (mut repaired, mut refused, mut flips, mut interior) = (0, 0, 0, 0);
        for (step, seed) in [8i32, 10].into_iter().flat_map(|s| (1..200u64).map(move |k| (s, k))) {
            let mut s = seed;
            // random points, then snapped to multiples of 2^-step
            let jit: Vec<P3> = (0..400).map(|_| [lcg(&mut s), lcg(&mut s), lcg(&mut s)]).collect();
            let q = (1u64 << step) as f64;
            let grid: Vec<P3> = jit.iter().map(|p| p.map(|x| (x * q).round() / q)).collect();
            let distinct: HashSet<[u64; 3]> = grid.iter().map(|p| p.map(f64::to_bits)).collect();
            if distinct.len() < grid.len() {
                continue; // equal points after rounding are refused before repair
            }
            let out = crate::delaunay::tetrahedralize(&jit, None).unwrap();
            let mut tets = out.tets.clone();
            let hull = crate::facetrec::hull_faces(&tets);
            let mut labels = vec![0u32; tets.len()];
            let before = tets.iter().filter(|t| orient(&grid, **t) <= 0).count();
            // inversions against the fixed boundary cannot be flipped away
            let on_hull = tets.iter().filter(|t| orient(&grid, **t) <= 0)
                .filter(|v| (0..4).any(|i| hull.contains(&key(face(v, i))))).count();
            if before > 0 && on_hull == 0 {
                interior += 1;
            }
            match repair(&grid, &mut tets, &mut labels, &hull, &HashSet::new()) {
                Ok(st) => {
                    assert_eq!(st.inverted as usize, before);
                    assert!(tets.iter().all(|t| orient(&grid, *t) > 0));
                    let mut count: HashMap<[u32; 3], u32> = HashMap::new();
                    for v in &tets {
                        for i in 0..4 {
                            *count.entry(key(face(v, i))).or_default() += 1;
                        }
                    }
                    assert!(count.values().all(|&c| c <= 2));
                    let now: HashSet<[u32; 3]> = count.iter().filter(|(_, &c)| c == 1).map(|(k, _)| *k).collect();
                    assert_eq!(now, hull, "the boundary is kept");
                    let used: HashSet<u32> = tets.iter().flatten().copied().collect();
                    assert_eq!(used.len(), grid.len());
                    if before > 0 {
                        repaired += 1;
                        flips += st.flips23 + st.flips32 + st.removals;
                    }
                }
                Err(_) => {
                    assert!(on_hull > 0, "seed {seed}: {before} interior inversions not repaired");
                    refused += 1;
                }
            }
        }
        assert!(interior > 0 && repaired >= interior && flips > 0, "repaired {repaired}, interior {interior}, refused {refused}");
        eprintln!("snapped points: {interior} with interior inversions, {repaired} repaired, {refused} refused (hull), {flips} flips");
    }
}
