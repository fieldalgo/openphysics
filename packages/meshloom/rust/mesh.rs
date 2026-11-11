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
use crate::mixed::{Mixed, MixedCounters, Pt};
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

/// A region seed: a point and the region it names (`label`, an index into the caller's
/// names), or a hole (`label` < 0: the component holding it is not meshed).
#[derive(Debug, Clone, Copy)]
pub struct Seed {
    pub p: P3,
    pub label: i64,
}

/// Why `build` produced no mesh.
#[derive(Debug, Clone)]
pub enum MeshError {
    /// parity mode: an elementary segment (input points `segment`) lies on the boundary
    /// of an odd number of facets (`facets`), so the surface is not closed (witness 6)
    NotClosed { segment: [u32; 2], facets: Vec<u32> },
    /// rounding to doubles left points equal or tetrahedra that flips cannot repair
    Rounding(String),
    /// a region seed that names no single bounded component, or a component without one
    Seed(String),
    Internal(String),
}

impl std::fmt::Display for MeshError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            MeshError::NotClosed { segment, facets } => write!(f,
                "the segment {}-{} is on the boundary of {} facets {:?}: the surface is not closed", segment[0], segment[1],
                facets.len(), facets),
            MeshError::Rounding(m) | MeshError::Seed(m) | MeshError::Internal(m) => write!(f, "{m}"),
        }
    }
}

fn key(f: [u32; 3]) -> [u32; 3] {
    let mut k = f;
    k.sort_unstable();
    k
}

fn face(t: &[u32; 4], i: usize) -> [u32; 3] {
    INWARD[i].map(|j| t[j])
}

/// Labels, rounds and certifies the result of boundary recovery. With `seeds` (regions
/// mode only), each bounded component takes the label of the seeds inside it, or is
/// dropped if they mark a hole; every bounded component needs a seed, and a seed must lie
/// strictly inside one bounded component (exactly, against the unrounded points). Regions
/// are then numbered by label.
pub fn build(points: &[P3], b: &Boundary, domain: Domain, seeds: &[Seed]) -> Result<TetMesh, MeshError> {
    if domain == Domain::Parity {
        if !seeds.is_empty() {
            return Err(MeshError::Seed("region seeds need domain 'regions'".into()));
        }
        closed(points.len(), b)?;
    }
    build_inner(points, b, domain, seeds).map_err(|e| {
        if let Some(m) = e.strip_prefix("seed: ") {
            MeshError::Seed(m.to_string())
        } else if e.starts_with("rounding") || e.contains("repair") {
            MeshError::Rounding(e)
        } else {
            MeshError::Internal(e)
        }
    })
}

/// Witness 6 of the C14 validity rule: an elementary segment on the boundary of an odd
/// number of facets. A facet's boundary edges are the edges used once by its subfacets.
fn closed(n: usize, b: &Boundary) -> Result<(), MeshError> {
    let mut on: HashMap<(u32, u32), Vec<u32>> = HashMap::new();
    for (f, tris) in b.plc.subfacets.iter().enumerate() {
        let mut uses: HashMap<(u32, u32), u32> = HashMap::new();
        for t in tris {
            for k in 0..3 {
                let (u, v) = (t[k], t[(k + 1) % 3]);
                *uses.entry((u.min(v), u.max(v))).or_default() += 1;
            }
        }
        for (e, c) in uses {
            if c == 1 {
                on.entry(e).or_default().push(f as u32);
            }
        }
    }
    let mut odd: Vec<((u32, u32), Vec<u32>)> = on.into_iter().filter(|(_, fs)| fs.len() % 2 == 1).collect();
    odd.sort_unstable();
    if let Some(((u, v), mut facets)) = odd.into_iter().next() {
        facets.sort_unstable();
        let s = &b.plc.rec.s;
        // the input segment this piece lies on
        let seg = |x: u32| (x as usize >= n).then(|| { let p = s[x as usize - n]; [p.a, p.b] });
        let segment = seg(u).or_else(|| seg(v)).unwrap_or([u, v]);
        return Err(MeshError::NotClosed { segment: [segment[0].min(segment[1]), segment[0].max(segment[1])], facets });
    }
    Ok(())
}

/// The bounded component that each seed lies strictly inside, exactly: a seed is located
/// in every tetrahedron whose closed region holds it (all four orientations >= 0), with
/// the S points unrounded; one component must hold it.
fn locate_seeds(points: &[P3], b: &Boundary, comp: &[u32], outside: &[bool], seeds: &[Seed])
                -> Result<Vec<u32>, String> {
    let n = points.len() as u32;
    let mut ext = points.to_vec();
    ext.extend(seeds.iter().map(|s| s.p));
    let m = Mixed { input: &ext, s: &b.plc.rec.s };
    let orig = Mixed { input: points, s: &b.plc.rec.s };
    let mut cnt = MixedCounters::default();
    let mut out = Vec::with_capacity(seeds.len());
    for (j, sd) in seeds.iter().enumerate() {
        if !sd.p.iter().all(|x| x.is_finite()) {
            return Err(format!("seed: region seed {j} has a coordinate that is not finite"));
        }
        let q = Pt::In(n + j as u32);
        let mut found: Vec<u32> = Vec::new();
        for (t, v) in b.tets.iter().enumerate() {
            let p = v.map(|g| orig.from_id(g));
            // the tetrahedron's faces with the seed in place of each vertex in turn
            let inside = (0..4).all(|i| {
                let mut w = p;
                w[i] = q;
                m.orient3d(w, &mut cnt) >= 0
            });
            if inside && !found.contains(&comp[t]) {
                found.push(comp[t]);
            }
        }
        match found.as_slice() {
            [] => return Err(format!("seed: region seed {j} at {:?} lies outside the input's convex hull", sd.p)),
            [c] if !outside[*c as usize] => out.push(*c),
            [_] => return Err(format!("seed: region seed {j} at {:?} lies outside every closed region", sd.p)),
            _ => return Err(format!("seed: region seed {j} at {:?} lies on a facet between regions", sd.p)),
        }
    }
    Ok(out)
}

fn build_inner(points: &[P3], b: &Boundary, domain: Domain, seeds: &[Seed]) -> Result<TetMesh, String> {
    let tets = &b.tets;
    // the facets of each subfacet (two facets can share one, e.g. touching shells)
    // facets per subfacet: a face shared by two touching shells is crossed twice
    let mut multiplicity: HashMap<[u32; 3], u32> = HashMap::new();
    let mut facet_of: HashMap<[u32; 3], u32> = HashMap::new();
    for (f, tris) in b.plc.subfacets.iter().enumerate() {
        for t in tris {
            facet_of.entry(key(*t)).or_insert(f as u32);
            *multiplicity.entry(key(*t)).or_default() += 1;
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
    // (component, facet, parity change: the number of facets on the face, mod 2)
    let mut adj: Vec<Vec<(u32, u32, u8)>> = vec![Vec::new(); ncomp as usize];
    for (k, list) in &owners {
        if let (Some(&f), [(a, _), (b2, _)]) = (facet_of.get(k), list.as_slice()) {
            let (ca, cb) = (comp[*a as usize], comp[*b2 as usize]);
            if ca != cb {
                let flip = (multiplicity[k] % 2) as u8;
                adj[ca as usize].push((cb, f, flip));
                adj[cb as usize].push((ca, f, flip));
            }
        }
    }
    // 2. the domain: region index per component, NONE outside
    let mut region_of = vec![NONE; ncomp as usize];
    // with seeds, each bounded component's label (NONE for a hole), and regions are numbered
    // by label instead of by first appearance
    let mut label_of: Vec<Option<i64>> = vec![None; ncomp as usize];
    if !seeds.is_empty() {
        let at = locate_seeds(points, b, &comp, &outside, seeds)?;
        for (j, (&c, sd)) in at.iter().zip(seeds).enumerate() {
            match label_of[c as usize] {
                Some(l) if l != sd.label.max(-1) => {
                    return Err(format!("seed: region seeds in one region name two regions (seed {j} at {:?})", sd.p));
                }
                _ => label_of[c as usize] = Some(sd.label.max(-1)),
            }
        }
        if let Some(c) = (0..ncomp as usize).find(|&c| !outside[c] && label_of[c].is_none()) {
            let t = comp.iter().position(|&x| x == c as u32).unwrap();
            let m = Mixed { input: points, s: &b.plc.rec.s };
            let q = tets[t].map(|g| m.rounded(m.from_id(g)));
            let w = [0, 1, 2].map(|k| (q[0][k] + q[1][k] + q[2][k] + q[3][k]) / 4.0);
            return Err(format!("seed: a region has no seed (one of its points: {w:?})"));
        }
    }
    match domain {
        Domain::Regions => {
            for c in 0..ncomp as usize {
                if !outside[c] {
                    region_of[c] = match label_of[c] {
                        Some(l) if l < 0 => NONE, // a hole
                        _ => 0,                   // numbered below
                    };
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
                    let flip = (multiplicity[k] % 2) as u8;
                    adj[out].push((c, f, flip));
                    adj[c as usize].push((out as u32, f, flip));
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
                for &(d, f, flip) in &adj[c as usize] {
                    let p = parity[c as usize] ^ flip;
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
        let r = if let Some(Some(l)) = label_of.get(c as usize) {
            *l as u32 // by label
        } else {
            let key_c = if domain == Domain::Parity { 0 } else { c };
            let n = number.len() as u32;
            *number.entry(key_c).or_insert(n)
        };
        kept.push(t);
        regions.push(r);
    }
    if kept.is_empty() {
        return Err("the domain is empty".into());
    }
    let region_count = if seeds.is_empty() {
        number.len() as u32
    } else {
        // labels 0..k-1, every one named by a seed in a meshed component
        let k = seeds.iter().map(|s| s.label + 1).max().unwrap_or(0).max(0) as u32;
        let used: HashSet<u32> = regions.iter().copied().collect();
        if (0..k).any(|l| !used.contains(&l)) {
            return Err("seed: a region name has no seed inside a meshed region".into());
        }
        k
    };
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
    // 4. certification, with flip repair of what rounding made flat or inverted. The
    // subfacets, by facet, may be re-triangulated inside their facet; a subfacet of two
    // facets (touching shells) is pinned.
    let out_key = |k: &[u32; 3]| Some(key([*new_id.get(&k[0])?, *new_id.get(&k[1])?, *new_id.get(&k[2])?]));
    let mut facet_out: HashMap<[u32; 3], u32> = facet_of.iter().filter_map(|(k, &f)| Some((out_key(k)?, f))).collect();
    let pinned: HashSet<[u32; 3]> = multiplicity.iter().filter(|(_, &m)| m > 1).filter_map(|(k, _)| out_key(k)).collect();
    let fixed_edges: HashSet<(u32, u32)> = b.plc.rec.chains.iter()
        .flat_map(|c| c.windows(2).map(|w| (w[0], w[1])))
        .filter_map(|(a, c)| Some((*new_id.get(&a)?, *new_id.get(&c)?)))
        .map(|(a, c)| (a.min(c), a.max(c))).collect();
    // the labels are the regions: a flip replaces tetrahedra of one region only (a label
    // per tetrahedron would forbid every flip)
    let mut labels = regions;
    let boundary_before = {
        let mut c: HashMap<[u32; 3], u32> = HashMap::new();
        for v in &out_tets {
            for i in 0..4 {
                *c.entry(key(face(v, i))).or_default() += 1;
            }
        }
        c.values().filter(|&&n| n == 1).count()
    };
    let rs = repair(&mut nodes, &mut out_tets, &mut labels, &mut facet_out, &pinned, &fixed_edges)?;
    source.resize(nodes.len(), NONE); // points the repair added have no global index
    let regions = labels;
    for (t, v) in out_tets.iter().enumerate() {
        if orient(&nodes, *v) <= 0 {
            return Err(format!("tetrahedron {t} failed certification after repair"));
        }
    }
    // every face in at most two tetrahedra, which use it with opposite windings (so they lie
    // on its two sides); with every tetrahedron positive and the faces used once being the
    // domain's boundary, the tetrahedra then tile the domain exactly once
    {
        let rot = |f: [u32; 3]| {
            let m = (0..3).min_by_key(|&j| f[j]).unwrap();
            [f[m], f[(m + 1) % 3], f[(m + 2) % 3]]
        };
        let mut seen: HashMap<[u32; 3], ([u32; 3], u32)> = HashMap::new();
        for v in &out_tets {
            for i in 0..4 {
                let f = rot(face(v, i));
                let e = seen.entry(key(f)).or_insert((f, 0));
                e.1 += 1;
                if e.1 > 2 {
                    return Err(format!("face {:?} is in more than two tetrahedra after repair", key(f)));
                }
                if e.1 == 2 && e.0 != [f[0], f[2], f[1]] {
                    return Err(format!("face {:?} has both of its tetrahedra on one side after repair", key(f)));
                }
            }
        }
        let used_once = seen.values().filter(|(_, c)| *c == 1).count();
        if used_once != boundary_before {
            return Err(format!("repair changed the number of boundary faces from {boundary_before} to {used_once}"));
        }
    }
    // boundary faces and interfaces, from the output arrays
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
    /// edge removals of an edge inside one facet, which re-triangulate the facet there
    pub facet_flips: u32,
    /// cavities around an inverted tetrahedron refilled as a cone from one of their vertices
    /// or from a new point
    pub cavity_fills: u32,
    /// new points inside the domain, one per cavity filled from a new point (their
    /// `source` is `NONE`)
    pub points_added: u32,
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

/// The cavity fill of `repair`: the tetrahedron `t` and its neighbours across faces that
/// are neither fixed nor pinned (one label), grown by up to `CAVITY_LAYERS` layers, are
/// replaced by the cone over the cavity's boundary from one of its vertices or, when no
/// vertex will do, from a new point inside it (the centroid of one of its positive
/// tetrahedra, appended to the nodes as index `nodes.len()`). The cone is taken only when
/// all of its tetrahedra are positive, every vertex of the cavity lies on its boundary,
/// the boundary is a closed surface (every edge in two of its faces) and every fixed edge
/// of the cavity survives. Over a closed oriented surface the cone's signed tetrahedra sum
/// to the surface's winding number, so all-positive ones tile the cavity exactly once; the
/// boundary, fixed faces included, is kept.
/// Returns (removed tetrahedra, new tetrahedra, label, the new point if any).
#[allow(clippy::too_many_arguments)]
fn cavity_fill(nodes: &[P3], tets: &[[u32; 4]], labels: &[u32], faces: &HashMap<[u32; 3], Vec<usize>>,
               fixed: &HashMap<[u32; 3], u32>, pinned: &HashSet<[u32; 3]>, fixed_edges: &HashSet<(u32, u32)>,
               t: usize) -> Option<(Vec<usize>, Vec<[u32; 4]>, u32, Option<P3>)> {
    // seeds: t alone, then t with the stars (in its label) of its four vertices, so that a
    // point that rounding moved is wholly inside the cavity
    let mut star: Vec<usize> = (0..4).flat_map(|k| star_of(tets, labels, faces, fixed, pinned, t, tets[t][k])).collect();
    star.sort_unstable();
    star.dedup();
    fill_from(nodes, tets, labels, faces, fixed, pinned, fixed_edges, vec![t])
        .or_else(|| fill_from(nodes, tets, labels, faces, fixed, pinned, fixed_edges, star))
        .or_else(|| (0..4).find_map(|k| lift(nodes, tets, labels, faces, fixed, pinned, fixed_edges, t, tets[t][k])))
}

/// The tetrahedra around `v` reached from `t` (which has `v`) across faces through `v`
/// that are neither fixed nor pinned, in `t`'s label: `v`'s star on `t`'s side of the
/// fixed faces, found by walking instead of scanning every tetrahedron.
fn star_of(tets: &[[u32; 4]], labels: &[u32], faces: &HashMap<[u32; 3], Vec<usize>>, fixed: &HashMap<[u32; 3], u32>,
           pinned: &HashSet<[u32; 3]>, t: usize, v: u32) -> Vec<usize> {
    let mut seen: HashSet<usize> = HashSet::from([t]);
    let mut stack = vec![t];
    let mut out = Vec::new();
    while let Some(r) = stack.pop() {
        out.push(r);
        for i in 0..4 {
            let k = key(face(&tets[r], i));
            if !k.contains(&v) || fixed.contains_key(&k) || pinned.contains(&k) {
                continue;
            }
            for &u in &faces[&k] {
                if labels[u] == labels[t] && seen.insert(u) {
                    stack.push(u);
                }
            }
        }
    }
    out.sort_unstable();
    out
}

/// The star (in `t`'s label) of a vertex `v` of `t` on fixed faces, refilled as the cone from
/// `v` lifted into the domain along the inward normal of those faces: rounding moves a
/// point on a facet by an ulp or so, which can put it on the wrong side of a face of its
/// link; the lifted point sees the link as `v` should, and the fixed faces around `v` from
/// inside. Lifts of 1e-9 to 1e-1 of the star's size are tried, smallest first.
#[allow(clippy::too_many_arguments)]
fn lift(nodes: &[P3], tets: &[[u32; 4]], labels: &[u32], faces: &HashMap<[u32; 3], Vec<usize>>,
        fixed: &HashMap<[u32; 3], u32>, pinned: &HashSet<[u32; 3]>, fixed_edges: &HashSet<(u32, u32)>,
        t: usize, v: u32) -> Option<(Vec<usize>, Vec<[u32; 4]>, u32, Option<P3>)> {
    let lab = labels[t];
    let edge = |a: u32, b: u32| (a.min(b), a.max(b));
    let cav = star_of(tets, labels, faces, fixed, pinned, t, v);
    let inside: HashSet<usize> = cav.iter().copied().collect();
    let mut bnd: Vec<[u32; 3]> = Vec::new();
    for &r in &cav {
        for i in 0..4 {
            let f = face(&tets[r], i);
            let k = key(f);
            if !faces[&k].iter().any(|&u| u != r && inside.contains(&u)) {
                bnd.push(f);
            } else if fixed.contains_key(&k) || pinned.contains(&k) {
                return None; // the star crosses a fixed face
            }
        }
    }
    // inward normal of the fixed faces at v (face() is wound so that its normal points inward)
    let mut n = [0.0f64; 3];
    for f in bnd.iter().filter(|f| f.contains(&v) && (fixed.contains_key(&key(**f)) || pinned.contains(&key(**f)))) {
        let [a, b, c] = f.map(|i| nodes[i as usize]);
        let (u, w) = ([b[0] - a[0], b[1] - a[1], b[2] - a[2]], [c[0] - a[0], c[1] - a[1], c[2] - a[2]]);
        let m = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]];
        let len = (m[0] * m[0] + m[1] * m[1] + m[2] * m[2]).sqrt();
        if len > 0.0 {
            for c in 0..3 {
                n[c] += m[c] / len;
            }
        }
    }
    let nlen = (n[0] * n[0] + n[1] * n[1] + n[2] * n[2]).sqrt();
    if !(nlen > 0.0) {
        return None;
    }
    let p0 = nodes[v as usize];
    let size = cav.iter().flat_map(|&r| tets[r]).map(|i| {
        let q = nodes[i as usize];
        ((q[0] - p0[0]).powi(2) + (q[1] - p0[1]).powi(2) + (q[2] - p0[2]).powi(2)).sqrt()
    }).fold(0.0, f64::max);
    let cav_fixed: Vec<(u32, u32)> = cav.iter()
        .flat_map(|&r| (0..4).flat_map(move |k| (k + 1..4).map(move |l| (r, k, l))))
        .map(|(r, k, l)| edge(tets[r][k], tets[r][l])).filter(|e| fixed_edges.contains(e)).collect();
    let apex = nodes.len() as u32;
    let mut ext = nodes.to_vec();
    ext.push(p0);
    for h in [1e-9, 1e-7, 1e-5, 1e-3, 1e-1] {
        let p = [0, 1, 2].map(|c| p0[c] + h * size * n[c] / nlen);
        if p == p0 {
            continue;
        }
        ext[apex as usize] = p;
        let new: Vec<[u32; 4]> = bnd.iter().map(|f| [f[0], f[1], f[2], apex]).collect();
        if new.iter().any(|q| orient(&ext, *q) <= 0) {
            continue;
        }
        let kept: HashSet<(u32, u32)> = new.iter()
            .flat_map(|q| (0..4).flat_map(move |k| (k + 1..4).map(move |l| edge(q[k], q[l])))).collect();
        if cav_fixed.iter().any(|e| !kept.contains(e)) || !local_ok(faces, tets, &cav, &new) {
            continue;
        }
        return Some((cav, new, lab, Some(p)));
    }
    None
}

#[allow(clippy::too_many_arguments)]
fn fill_from(nodes: &[P3], tets: &[[u32; 4]], labels: &[u32], faces: &HashMap<[u32; 3], Vec<usize>>,
             fixed: &HashMap<[u32; 3], u32>, pinned: &HashSet<[u32; 3]>, fixed_edges: &HashSet<(u32, u32)>,
             seed: Vec<usize>) -> Option<(Vec<usize>, Vec<[u32; 4]>, u32, Option<P3>)> {
    const CAVITY_LAYERS: usize = 3;
    const CAVITY_MAX: usize = 96;
    let lab = labels[seed[0]];
    let edge = |a: u32, b: u32| (a.min(b), a.max(b));
    let mut inside: HashSet<usize> = seed.iter().copied().collect();
    let mut cav: Vec<usize> = seed;
    for layer in 0..=CAVITY_LAYERS {
        // grow by one layer across faces that are neither fixed nor pinned
        let mut add = Vec::new();
        for &r in &cav {
            for i in 0..4 {
                let k = key(face(&tets[r], i));
                if fixed.contains_key(&k) || pinned.contains(&k) {
                    continue;
                }
                for &u in &faces[&k] {
                    if !inside.contains(&u) && labels[u] == lab && !add.contains(&u) {
                        add.push(u);
                    }
                }
            }
        }
        if layer > 0 {
            if add.is_empty() || cav.len() + add.len() > CAVITY_MAX {
                return None;
            }
            add.sort_unstable();
            inside.extend(add.iter().copied());
            cav.extend(add);
        }
        // the cavity's boundary: faces of its tetrahedra not shared inside it, oriented inward
        let mut bnd: Vec<[u32; 3]> = Vec::new();
        let mut inner_fixed = false;
        for &r in &cav {
            for i in 0..4 {
                let f = face(&tets[r], i);
                let k = key(f);
                if !faces[&k].iter().any(|&u| u != r && inside.contains(&u)) {
                    bnd.push(f);
                } else if fixed.contains_key(&k) || pinned.contains(&k) {
                    inner_fixed = true; // a seed's star across a fixed face: that face would be lost
                }
            }
        }
        if inner_fixed {
            return None;
        }
        let mut edge_use: HashMap<(u32, u32), u32> = HashMap::new();
        for f in &bnd {
            for j in 0..3 {
                *edge_use.entry(edge(f[j], f[(j + 1) % 3])).or_default() += 1;
            }
        }
        if edge_use.values().any(|&c| c != 2) {
            continue; // not a closed surface yet
        }
        let on_bnd: HashSet<u32> = bnd.iter().flatten().copied().collect();
        let verts: Vec<u32> = {
            let mut v: Vec<u32> = cav.iter().flat_map(|&r| tets[r]).collect();
            v.sort_unstable();
            v.dedup();
            v
        };
        if verts.iter().any(|v| !on_bnd.contains(v)) {
            continue; // a vertex inside the cavity would be lost
        }
        let cav_fixed: Vec<(u32, u32)> = cav.iter()
            .flat_map(|&r| (0..4).flat_map(move |k| (k + 1..4).map(move |l| (k, l))).map(move |(k, l)| (r, k, l)))
            .map(|(r, k, l)| edge(tets[r][k], tets[r][l])).filter(|e| fixed_edges.contains(e)).collect();
        for &v in &verts {
            let new: Vec<[u32; 4]> = bnd.iter().filter(|f| !f.contains(&v)).map(|f| [f[0], f[1], f[2], v]).collect();
            if new.iter().any(|n| orient(nodes, *n) <= 0) {
                continue;
            }
            let kept: HashSet<(u32, u32)> = new.iter()
                .flat_map(|n| (0..4).flat_map(move |k| (k + 1..4).map(move |l| edge(n[k], n[l])))).collect();
            if cav_fixed.iter().any(|e| !kept.contains(e)) {
                continue;
            }
            if !local_ok(faces, tets, &cav, &new) {
                continue;
            }
            return Some((cav.clone(), new, lab, None));
        }
        // no vertex sees the whole boundary (typically a ridge between near-coplanar facets that
        // rounding made slightly reflex, with the cavity's vertices on those facets): a new point
        // inside the cavity as the apex, the centroid of one of its positive tetrahedra
        let mut cands: Vec<P3> = cav.iter().filter(|&&r| orient(nodes, tets[r]) > 0).map(|&r| {
            let q = tets[r].map(|i| nodes[i as usize]);
            [0, 1, 2].map(|c| (q[0][c] + q[1][c] + q[2][c] + q[3][c]) / 4.0)
        }).collect();
        cands.dedup();
        let apex = nodes.len() as u32;
        let mut ext = nodes.to_vec();
        ext.push([0.0; 3]);
        for p in cands {
            ext[apex as usize] = p;
            let new: Vec<[u32; 4]> = bnd.iter().map(|f| [f[0], f[1], f[2], apex]).collect();
            if new.iter().any(|n| orient(&ext, *n) <= 0) {
                continue;
            }
            let kept: HashSet<(u32, u32)> = new.iter()
                .flat_map(|n| (0..4).flat_map(move |k| (k + 1..4).map(move |l| edge(n[k], n[l])))).collect();
            if cav_fixed.iter().any(|e| !kept.contains(e)) || !local_ok(faces, tets, &cav, &new) {
                continue;
            }
            return Some((cav.clone(), new, lab, Some(p)));
        }
    }
    None
}

/// Repairs tetrahedra that are flat or inverted on `nodes` by flips: 2-3, and edge
/// removal (3-2 for a ring of three, up to a ring of seven). A flip is applied only when
/// all of its new tetrahedra are positive and no face ends in three tetrahedra.
///
/// `fixed` maps each fixed face (a subfacet) to its facet. A flip never removes a fixed
/// face, an edge of `fixed_edges` or a face of `pinned`, with one exception: the
/// removal of an edge `de` that lies inside one facet (its only fixed faces are `dex`
/// and `dey`, of that facet, neither pinned) may replace them by `xyd` and `xye`, which
/// cover the same part of the facet when the quadrilateral `dxey` is convex; all-positive
/// new tetrahedra on both sides of the facet (or on its one meshed side) require that.
/// `fixed` follows such flips. `labels` follows the tetrahedra: each new tetrahedron
/// takes the label of the old one across its ring edge, so labels change only across
/// fixed faces.
pub fn repair(nodes: &mut Vec<P3>, tets: &mut Vec<[u32; 4]>, labels: &mut Vec<u32>, fixed: &mut HashMap<[u32; 3], u32>,
              pinned: &HashSet<[u32; 3]>, fixed_edges: &HashSet<(u32, u32)>) -> Result<RepairStats, String> {
    let mut st = RepairStats::default();
    let bad0 = tets.iter().filter(|t| orient(nodes, **t) <= 0).count();
    st.inverted = bad0 as u32;
    if bad0 == 0 {
        return Ok(st);
    }
    let edge = |a: u32, b: u32| (a.min(b), a.max(b));
    // Each round repairs every bad tetrahedron it can on tetrahedra no other repair of the
    // round touched, then rebuilds the maps once: every operation keeps the boundary faces
    // of what it replaces, so repairs on disjoint tetrahedra do not interfere.
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
        let mut dirty: HashSet<usize> = HashSet::new();
        let mut made_edges: HashSet<(u32, u32)> = HashSet::new();
        let mut ops: Vec<Op> = Vec::new();
        for &t in &bad {
            if dirty.contains(&t) {
                continue;
            }
            if let Some(op) = flip_op(nodes, tets, labels, &faces, &edges, fixed, pinned, fixed_edges, &dirty,
                                      &made_edges, t) {
                if let Some((dex, dey, xyd, xye, f)) = op.facet {
                    fixed.remove(&dex);
                    fixed.remove(&dey);
                    fixed.insert(xyd, f);
                    fixed.insert(xye, f);
                }
                dirty.extend(op.gone.iter().copied());
                made_edges.extend(op.new.iter().flat_map(|n| (0..4).flat_map(move |k| (k + 1..4).map(move |l| edge(n[k], n[l])))));
                ops.push(op);
            }
        }
        if ops.is_empty() {
            // no flip anywhere: cavity fills
            for &t in &bad {
                if dirty.contains(&t) {
                    continue;
                }
                if let Some((gone, new, lab, point)) = cavity_fill(nodes, tets, labels, &faces, fixed, pinned, fixed_edges, t) {
                    if gone.iter().any(|r| dirty.contains(r)) {
                        continue;
                    }
                    dirty.extend(gone.iter().copied());
                    let labs = vec![lab; new.len()];
                    ops.push(Op { gone, new, labs, point, facet: None, kind: OpKind::Fill });
                }
            }
        }
        if ops.is_empty() {
            let p = tets[bad[0]].map(|i| nodes[i as usize]);
            return Err(format!("rounding to doubles made {} tetrahedra flat or inverted (one near {:?}), and no flip repairs them",
                               bad.len(), p[0]));
        }
        // apply: a new point takes the next node index (cavity_fill named it nodes.len())
        let placeholder = nodes.len() as u32;
        let mut gone_all: Vec<usize> = Vec::new();
        let mut add_tets: Vec<[u32; 4]> = Vec::new();
        let mut add_labels: Vec<u32> = Vec::new();
        for op in ops {
            let mut new = op.new;
            if let Some(p) = op.point {
                let idx = nodes.len() as u32;
                nodes.push(p);
                st.points_added += 1;
                for n in new.iter_mut() {
                    for x in n.iter_mut() {
                        if *x == placeholder {
                            *x = idx;
                        }
                    }
                }
            }
            match op.kind {
                OpKind::Flip23 => st.flips23 += 1,
                OpKind::Flip32 => st.flips32 += 1,
                OpKind::Removal => st.removals += 1,
                OpKind::Facet => st.facet_flips += 1,
                OpKind::Fill => st.cavity_fills += 1,
            }
            gone_all.extend(op.gone);
            add_tets.extend(new);
            add_labels.extend(op.labs);
        }
        gone_all.sort_unstable_by(|x, y| y.cmp(x));
        for r in gone_all {
            tets.swap_remove(r);
            labels.swap_remove(r);
        }
        tets.extend(add_tets);
        labels.extend(add_labels);
    }
    Err("flip repair did not finish".into())
}

#[derive(Clone, Copy)]
enum OpKind {
    Flip23,
    Flip32,
    Removal,
    Facet,
    Fill,
}

/// One repair: the tetrahedra it removes, the ones it adds with their labels, a new
/// point (for a cavity fill from a new point), and for an in-facet removal the fixed
/// faces it replaces (`dex`, `dey` by `xyd`, `xye`, of facet `f`).
struct Op {
    gone: Vec<usize>,
    new: Vec<[u32; 4]>,
    labs: Vec<u32>,
    point: Option<P3>,
    facet: Option<([u32; 3], [u32; 3], [u32; 3], [u32; 3], u32)>,
    kind: OpKind,
}

/// A flip that repairs `t`, touching no tetrahedron of `dirty` and making no edge of
/// `made` (an edge another repair of this round made): edge removal (3-2 for a ring of
/// three, up to seven), in-facet edge removal, or 2-3.
#[allow(clippy::too_many_arguments)]
fn flip_op(nodes: &[P3], tets: &[[u32; 4]], labels: &[u32], faces: &HashMap<[u32; 3], Vec<usize>>,
           edges: &HashMap<(u32, u32), Vec<usize>>, fixed: &HashMap<[u32; 3], u32>, pinned: &HashSet<[u32; 3]>,
           fixed_edges: &HashSet<(u32, u32)>, dirty: &HashSet<usize>, made: &HashSet<(u32, u32)>,
           t: usize) -> Option<Op> {
    let edge = |a: u32, b: u32| (a.min(b), a.max(b));
    // edge removal (3-2 for a ring of three, 4-4 for four, up to seven): the
    // tetrahedra around an edge of t replaced by a fan triangulation of the ring
    let v = tets[t];
    for k in 0..4 {
        for l in k + 1..4 {
            let (d, e) = (v[k], v[l]);
            if fixed_edges.contains(&edge(d, e)) {
                continue;
            }
            let ring_tets = edges[&edge(d, e)].clone();
            let n = ring_tets.len();
            if !(3..=7).contains(&n) || ring_tets.iter().any(|r| dirty.contains(r)) {
                continue;
            }
            // the link of the edge, and the third vertices of the fixed faces through it
            let mut link: HashMap<u32, Vec<u32>> = HashMap::new();
            let mut label_of: HashMap<(u32, u32), u32> = HashMap::new();
            let mut fx: Vec<u32> = Vec::new();
            for &r in &ring_tets {
                let xy: Vec<u32> = tets[r].iter().copied().filter(|&x| x != d && x != e).collect();
                for &x in &xy {
                    let k = key([d, e, x]);
                    if (fixed.contains_key(&k) || pinned.contains(&k)) && !fx.contains(&x) {
                        fx.push(x);
                    }
                }
                link.entry(xy[0]).or_default().push(xy[1]);
                link.entry(xy[1]).or_default().push(xy[0]);
                label_of.insert(edge(xy[0], xy[1]), labels[r]);
            }
            // in-facet: exactly two fixed faces through the edge, of one facet, not pinned
            let infacet = match fx.as_slice() {
                [] => false,
                [x, y] => {
                    let (kx, ky) = (key([d, e, *x]), key([d, e, *y]));
                    if pinned.contains(&kx) || pinned.contains(&ky) || fixed.get(&kx) != fixed.get(&ky) {
                        continue;
                    }
                    true
                }
                _ => continue,
            };
            if !infacet && ring_tets.iter().any(|&r| labels[r] != labels[t]) {
                continue;
            }
            // the ring in order: a cycle, or (one meshed side of a facet) a path from x to y
            let ends: Vec<u32> = link.iter().filter(|(_, w)| w.len() == 1).map(|(&x, _)| x).collect();
            let cycle = ends.is_empty() && link.len() == n && link.values().all(|w| w.len() == 2);
            let path = infacet && link.len() == n + 1 && ends.len() == 2 && fx.iter().all(|x| ends.contains(x))
                && link.values().all(|w| w.len() <= 2);
            if !cycle && !path {
                continue; // an edge on the boundary, or a ring that is not a cycle
            }
            let start = if path { fx[0] } else { *link.keys().min().unwrap() };
            let mut ring = vec![start];
            let mut prev = u32::MAX;
            let mut cur = start;
            loop {
                let next = link[&cur].iter().copied().find(|&w| w != prev);
                match next {
                    Some(w) if w != start => {
                        ring.push(w);
                        prev = cur;
                        cur = w;
                    }
                    _ => break,
                }
                if ring.len() > n + 1 {
                    break;
                }
            }
            let m = ring.len();
            if m != if path { n + 1 } else { n } {
                continue;
            }
            // fan apexes: any ring vertex, or (in-facet) x or y, so that the chord xy is made
            let apexes: Vec<usize> = if infacet {
                fx.iter().map(|x| ring.iter().position(|r| r == x).unwrap()).collect()
            } else {
                (0..m).collect()
            };
            for apex in apexes {
                let mut new = Vec::with_capacity(2 * m);
                let mut lab = Vec::with_capacity(2 * m);
                let mut ok = true;
                let mut side: Option<i8> = None;
                // fan triangles (apex, ring[a], ring[a + 1]) over the ring edges not at the apex
                let steps = if path { m - 1 } else { m };
                for s in 0..steps {
                    let (a, b) = (s, (s + 1) % m);
                    if a == apex || b == apex {
                        continue;
                    }
                    // the fan's triangles are taken in the ring's order, so d must lie on one
                    // and the same side of all of them and e on the other: tetrahedra oriented
                    // one by one would each be positive but could overlap their neighbours
                    let (x, y, z) = (ring[apex], ring[a], ring[b]);
                    let (sd, se) = (orient(nodes, [x, y, z, d]), orient(nodes, [x, y, z, e]));
                    if sd == 0 || se == 0 || sd == se || side.is_some_and(|s| s != sd) {
                        ok = false;
                        break;
                    }
                    side = Some(sd);
                    let l = label_of[&edge(y, z)];
                    new.push(if sd > 0 { [x, y, z, d] } else { [x, z, y, d] });
                    new.push(if se > 0 { [x, y, z, e] } else { [x, z, y, e] });
                    lab.extend([l, l]);
                }
                let new_edge = |n: &[u32; 4]| (0..4).any(|k| (k + 1..4).any(|l| made.contains(&edge(n[k], n[l]))));
                if !ok || new.is_empty() || new.iter().any(new_edge) || !local_ok(faces, tets, &ring_tets, &new) {
                    continue;
                }
                let facet = if infacet {
                    let f = fixed[&key([d, e, fx[0]])];
                    Some((key([d, e, fx[0]]), key([d, e, fx[1]]), key([fx[0], fx[1], d]), key([fx[0], fx[1], e]), f))
                } else {
                    None
                };
                let kind = if infacet { OpKind::Facet } else if n == 3 { OpKind::Flip32 } else { OpKind::Removal };
                return Some(Op { gone: ring_tets, new, labs: lab, point: None, facet, kind });
            }
        }
    }
    // 2-3: a face of t that is not fixed, with its neighbour
    for k in 0..4 {
        let f = face(&v, k);
        let fk = key(f);
        if fixed.contains_key(&fk) || pinned.contains(&fk) {
            continue;
        }
        let Some(u) = faces[&fk].iter().copied().find(|&u| u != t) else { continue };
        if labels[u] != labels[t] || dirty.contains(&u) {
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
        if new.iter().any(|n| orient(nodes, *n) <= 0) || edges.contains_key(&edge(d, e)) || made.contains(&edge(d, e))
            || !local_ok(faces, tets, &[t, u], &new) {
            continue;
        }
        let lab = labels[t];
        return Some(Op { gone: vec![t, u], new, labs: vec![lab; 3], point: None, facet: None, kind: OpKind::Flip23 });
    }
    None
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
        let m = build(&plc.points, &b, Domain::Regions, &[]).unwrap();
        assert_eq!(m.region_count, 2);
        let vols: Vec<f64> = (0..2).map(|r| volume(&m, r)).collect();
        let near = |x: f64, y: f64| (x - y).abs() <= 1e-12 * y;
        assert!(vols.iter().any(|&v| near(v, 1.0)) && vols.iter().any(|&v| near(v, 63.0)), "{vols:?}");
        assert_eq!(m.interfaces.len(), 12); // the inner box's 6 squares, 2 triangles each
        assert_eq!(m.boundary.len(), 12);
        let p = build(&plc.points, &b, Domain::Parity, &[]).unwrap();
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
    /// appear. Whatever repair returns must be valid (positive, faces in at most two
    /// tetrahedra with opposite windings, the hull kept, no point lost); interior-only
    /// inversions must be repaired at least as often as measured; ones against the fixed
    /// hull may be refused.
    #[test]
    fn flip_repair_on_snapped_points() {
        // Interior-only inversions repaired: 14 of 15 (2026-11-11). The first version of this
        // test asserted all 15, but its edge removal oriented each new tetrahedron on its own
        // and left two tetrahedra on one side of a face in 10 seeds (5 at 2^-8, 5 at 2^-10), which
        // the test did not check; it now checks windings, and repair keeps fans consistent.
        const INTERIOR_MIN: u32 = 14;
        let (mut repaired, mut refused, mut flips, mut interior, mut interior_repaired) = (0, 0, 0, 0, 0);
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
            // every hull face its own facet: no two hull faces share a facet, so nothing flips in one
            let mut fixed: HashMap<[u32; 3], u32> = hull.iter().enumerate().map(|(i, k)| (*k, i as u32)).collect();
            let mut grid = grid.clone();
            match repair(&mut grid, &mut tets, &mut labels, &mut fixed, &HashSet::new(), &HashSet::new()) {
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
                    // the two tetrahedra of a face use it with opposite windings (no overlap)
                    let rot = |f: [u32; 3]| {
                        let m = (0..3).min_by_key(|&j| f[j]).unwrap();
                        [f[m], f[(m + 1) % 3], f[(m + 2) % 3]]
                    };
                    let mut seen: HashMap<[u32; 3], [u32; 3]> = HashMap::new();
                    for v in &tets {
                        for i in 0..4 {
                            let f = rot(face(v, i));
                            if let Some(g) = seen.insert(key(f), f) {
                                assert_eq!(g, [f[0], f[2], f[1]], "seed {seed}: two tetrahedra on one side of a face");
                            }
                        }
                    }
                    let now: HashSet<[u32; 3]> = count.iter().filter(|(_, &c)| c == 1).map(|(k, _)| *k).collect();
                    assert_eq!(now, hull, "the boundary is kept");
                    let used: HashSet<u32> = tets.iter().flatten().copied().collect();
                    assert_eq!(used.len(), grid.len());
                    if before > 0 {
                        repaired += 1;
                        if on_hull == 0 {
                            interior_repaired += 1;
                        }
                        flips += st.flips23 + st.flips32 + st.removals + st.cavity_fills;
                    }
                }
                Err(_) => {
                    refused += 1;
                }
            }
        }
        eprintln!("snapped points: {interior} with interior inversions only, {interior_repaired} of them repaired; \
                   {repaired} repaired, {refused} refused; {flips} flips and fills");
        assert!(interior > 0 && interior_repaired >= INTERIOR_MIN.min(interior) && flips > 0,
                "repaired {repaired}, interior {interior_repaired} of {interior}, refused {refused}");
    }
}
