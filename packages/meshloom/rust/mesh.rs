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
    let region_of_tet: HashMap<usize, u32> = kept.iter().copied().zip(regions.iter().copied()).collect();
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
    // 4. certification
    for (t, v) in out_tets.iter().enumerate() {
        let p = v.map(|i| nodes[i as usize]);
        if orient3d_exact(&p[0], &p[1], &p[2], &p[3]) <= 0 {
            return Err(format!("rounding to doubles made tetrahedron {t} flat or inverted near {:?} (no flip repair yet)", p[0]));
        }
    }
    // boundary faces and interfaces
    let mut boundary = Vec::new();
    let mut interfaces = Vec::new();
    let mut seen_iface: HashSet<[u32; 3]> = HashSet::new();
    for (j, &t) in kept.iter().enumerate() {
        let v = tets[t];
        for i in 0..4 {
            let k = key(face(&v, i));
            let other = owners[&k].iter().find(|(u, _)| *u as usize != t).map(|(u, _)| *u as usize);
            let r = regions[j];
            let outward = {
                let f = face(&out_tets[j], i);
                [f[0], f[2], f[1]]
            };
            match other.and_then(|u| region_of_tet.get(&u).copied()) {
                None => {
                    let f = *facet_of.get(&k).ok_or_else(|| format!("boundary face {k:?} of the domain is not a subfacet"))?;
                    boundary.push((f, outward));
                }
                Some(r2) if r2 != r => {
                    if r < r2 && seen_iface.insert(k) {
                        interfaces.push((r, r2, outward));
                    }
                }
                Some(_) => {}
            }
        }
    }
    Ok(TetMesh { nodes, tets: out_tets, regions, region_count, boundary, interfaces, source })
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
}
