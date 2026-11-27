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
//! there is no tolerance. Candidate pairs of cells without a common vertex come from a
//! uniform grid ([`grid_pairs`]); pairs that share a vertex can meet only near it (both
//! are convex) and are checked in that vertex's star ([`star_pairs`]), a large planar
//! fan at once by the angular order of its rays. Any violation is an error naming the
//! cells, with its witness type: the first failing pair of the bounding-box sweep, so
//! the witness does not depend on the broad phase.

use crate::facet::{self, At, CellRef, Detail, InputError};
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
    /// What each facet's triangulation was built from, to rebuild it with points added
    /// on its sub-segments (boundary recovery).
    pub facets: Vec<FacetInfo>,
    /// Elementary sub-segments on the boundary of an odd number of facets (witnesses of
    /// type 6): empty when the PLC is closed.
    pub open_subsegments: Vec<[u32; 2]>,
    pub pairs_tested: usize,
}

/// A facet's points (its own and the coplanar points inside it), its boundary pieces
/// (the sub-segments of its loops), its inner constraints (the other sub-segments on
/// it), the projection axis and whether its outer loop is clockwise there.
#[derive(Debug, Clone, Default)]
pub struct FacetInfo {
    pub points: Vec<u32>,
    pub boundary: Vec<(u32, u32)>,
    pub inner: Vec<(u32, u32)>,
    pub axis: usize,
    pub flip: bool,
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
    let clock = crate::recovery::StageClock::start();
    let r = check_inner(plc);
    clock.lap("PLC check");
    r
}

fn check_inner(plc: &Plc) -> Result<Checked, InputError> {
    let clock = crate::recovery::StageClock::start();
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
        return Err(bad(0, "the PLC has no facets".into()).with(Detail::NoFacets));
    }
    let mut out = Checked::default();
    let mut seen = HashSet::new();
    let mut add_segment = |a: u32, b: u32, facet: Option<usize>| -> Result<(), InputError> {
        let what = facet.map_or("segment".to_string(), |f| format!("facet {f} edge"));
        if a as usize >= pts.len() || b as usize >= pts.len() {
            return Err(malformed(format!("{what} {a}-{b} refers to a point that does not exist")));
        }
        if a == b {
            // a loop that repeats a vertex (type 2); a free segment with equal ends is degenerate
            return Err(match facet {
                Some(f) => bad(2, format!("{what} {a}-{b} repeats a vertex")).with(Detail::Facet(f as u32)),
                None => bad(3, format!("{what} {a}-{b} has equal ends")),
            });
        }
        if seen.insert((a.min(b), a.max(b))) {
            out.segments.push([a.min(b), a.max(b)]);
        }
        Ok(())
    };
    for s in &plc.segments {
        add_segment(s[0], s[1], None)?;
    }
    let mut vertex_sets: HashMap<Vec<u32>, usize> = HashMap::new();
    for (f, loops) in plc.facets.iter().enumerate() {
        for lp in loops {
            for k in 0..lp.len() {
                add_segment(lp[k], lp[(k + 1) % lp.len()], Some(f))?;
            }
        }
        let mut vs: Vec<u32> = loops.iter().flatten().copied().collect();
        vs.sort_unstable();
        vs.dedup();
        if let Some(g) = vertex_sets.insert(vs, f) {
            return Err(bad(4, format!("facets {g} and {f} have the same vertices")).with(Detail::Facets(g as u32, f as u32)));
        }
    }
    let mut n = Counters::default();
    let mut tested = 0usize;

    clock.lap("PLC check, input");
    // the broad phase's grid: cells about the median edge extent
    let grid = {
        let mut ext: Vec<f64> = out.segments.iter()
            .map(|&[a, b]| (0..3).map(|k| (pts[a as usize][k] - pts[b as usize][k]).abs()).fold(0.0, f64::max))
            .collect();
        let mid = ext.len() / 2;
        let cell = if ext.is_empty() { 0.0 } else { *ext.select_nth_unstable_by(mid, |a, b| a.total_cmp(b)).1 };
        Grid::new(pts, cell)
    };

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
        let verts: Vec<Verts> = items.iter()
            .map(|x| if x.0 { [x.1, u32::MAX, u32::MAX] } else { let [p, q] = edges[x.1 as usize]; [p, q, u32::MAX] })
            .collect();
        let cells: Vec<Vec<u64>> = items.iter().zip(&verts)
            .map(|(x, vs)| if x.0 { grid.cells(&[pts[x.1 as usize]]) } else { grid.cells(&[pts[vs[0] as usize], pts[vs[1] as usize]]) })
            .collect();
        let boxes: Vec<_> = items.iter().map(|x| (x.2, x.3)).collect();
        grid_pairs(&cells, &verts, &boxes, |x, y| items[x].0 != items[y].0, |x, y| {
            let (a, b) = (&items[x], &items[y]);
            let (v, e) = if a.0 { (a.1, b.1) } else { (b.1, a.1) };
            let [p, q] = edges[e as usize];
            if v != p && v != q && pr::collinear(&pts[p as usize], &pts[q as usize], &pts[v as usize])
                && strictly_inside(&pts[p as usize], &pts[q as usize], &pts[v as usize])
            {
                on_edge[e as usize].push(v);
            }
            true
        });
    }
    clock.lap("PLC check, 1 points on edges");
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
    // the facets with each edge in a loop, to name type-5 witnesses by two facets
    let mut edge_facets: Vec<Vec<u32>> = vec![Vec::new(); edges.len()];
    {
        let index: HashMap<(u32, u32), usize> = edges.iter().enumerate().map(|(e, &[a, b])| ((a, b), e)).collect();
        for (f, loops) in plc.facets.iter().enumerate() {
            for lp in loops {
                for k in 0..lp.len() {
                    let (a, b) = (lp[k], lp[(k + 1) % lp.len()]);
                    let e = index[&(a.min(b), a.max(b))];
                    if !edge_facets[e].contains(&(f as u32)) {
                        edge_facets[e].push(f as u32);
                    }
                }
            }
        }
    }
    let sub_facets = |s: (u32, u32)| -> Vec<u32> {
        let mut v: Vec<u32> = sub_edges[&s].iter().flat_map(|&e| edge_facets[e as usize].iter().copied()).collect();
        v.sort_unstable();
        v.dedup();
        v
    };
    // two different facets, one from each list; else the cells themselves (a free
    // segment by its ends)
    let pick = |a: &[u32], b: &[u32], ca: CellRef, cb: CellRef| -> (CellRef, CellRef) {
        a.iter().flat_map(|&f| b.iter().map(move |&g| (f, g))).find(|(f, g)| f != g)
            .map_or((ca, cb), |(f, g)| (CellRef::Facet(f), CellRef::Facet(g)))
    };
    let cell_ref = |e: u32| CellRef::Segment(edges[e as usize]);

    // the sub-segments' grid cells (steps 2 and 5)
    let sub_grid_cells: Vec<Vec<u64>> = subs.iter().map(|&(a, b)| grid.cells(&[pts[a as usize], pts[b as usize]])).collect();
    // 2. two sub-segments meet only at a shared end (an identical piece is one key)
    {
        let boxes: Vec<_> = subs.iter().map(|&(a, b)| bbox(pts, &[a, b])).collect();
        let verts: Vec<Verts> = subs.iter().map(|&(a, b)| [a, b, u32::MAX]).collect();
        let cells = &sub_grid_cells;
        let mut bad_pair = false;
        let mut test = |x: usize, y: usize| -> bool {
            tested += 1;
            let (s, t) = (subs[x], subs[y]);
            bad_pair = !seg_seg_ok(pts, [s.0, s.1], [t.0, t.1], &mut n);
            !bad_pair
        };
        let ok = grid_pairs(&cells, &verts, &boxes, |_, _| true, &mut test)
            && star_pairs(pts.len(), &verts, |v, star| {
                if star.len() < 3 {
                    return None;
                }
                let mut ends: Vec<u32> = star.iter().map(|&i| { let s = subs[i as usize]; if s.0 == v { s.1 } else { s.0 } }).collect();
                segment_star_ok(pts, v, &mut ends).then_some(true)
            }, &mut test);
        // a failure: the witness is the first failing pair of the full sweep
        let mut found = None;
        if !ok {
            for_overlapping(&boxes, |x, y| {
                if found.is_some() {
                    return;
                }
                let (s, t) = (subs[x], subs[y]);
                if !seg_seg_ok(pts, [s.0, s.1], [t.0, t.1], &mut n) {
                    found = Some((s, t));
                }
            });
        }
        if let Some((s, t)) = found {
            let e = bad(5, format!("{} and {} intersect", edge_name(sub_edges[&s][0]), edge_name(sub_edges[&t][0])));
            let at = At::SegSeg([s.0, s.1], [t.0, t.1]);
            let cells = pick(&sub_facets(s), &sub_facets(t), cell_ref(sub_edges[&s][0]), cell_ref(sub_edges[&t][0]));
            return Err(e.with(Detail::Point { cells, at }));
        }
    }

    clock.lap("PLC check, 2 sub-segment pairs");
    // 3. each facet triangulated with the points and sub-segments on its plane
    let mut facet_tris: Vec<HashSet<[u32; 3]>> = Vec::with_capacity(plc.facets.len());
    let mut facet_edges: Vec<HashSet<(u32, u32)>> = Vec::with_capacity(plc.facets.len());
    let mut by_x: Vec<u32> = (0..pts.len() as u32).collect();
    by_x.sort_unstable_by(|&i, &j| pts[i as usize][0].total_cmp(&pts[j as usize][0]));
    let edge_index: HashMap<(u32, u32), usize> = edges.iter().enumerate().map(|(e, &[a, b])| ((a, b), e)).collect();
    // the points by grid cell (sorted), and each point's place in by_x: a facet visits
    // the points in its box's cells, in the order of by_x; a facet whose box spans many
    // more cells than there are points scans by_x instead
    let mut x_rank = vec![0u32; pts.len()];
    for (r, &v) in by_x.iter().enumerate() {
        x_rank[v as usize] = r as u32;
    }
    let mut point_cells: Vec<(u64, u32)> = (0..pts.len() as u32).map(|v| (grid.cells(&[pts[v as usize]])[0], v)).collect();
    point_cells.sort_unstable();
    // the sub-segments at each point, so that a facet visits only those at its members
    let sub_index: HashMap<(u32, u32), u32> = subs.iter().enumerate().map(|(i, &k)| (k, i as u32)).collect();
    let mut subs_at: Vec<Vec<u32>> = vec![Vec::new(); pts.len()];
    for (i, &(a, b)) in subs.iter().enumerate() {
        subs_at[a as usize].push(i as u32);
        subs_at[b as usize].push(i as u32);
    }
    for (f, loops) in plc.facets.iter().enumerate() {
        let own: HashSet<u32> = loops.iter().flatten().copied().collect();
        let (lo, hi) = bbox(pts, &own.iter().copied().collect::<Vec<_>>());
        let plane = plane_of(pts, &loops[0]);
        let mut extra = Vec::new();
        if let Some((a, b, c)) = plane {
            let mut near: Vec<u32> = Vec::new();
            // a facet that is one triangle takes only the points on it (closed); its
            // cells are those the triangle meets
            let tri: Option<[u32; 3]> = (loops.len() == 1 && loops[0].len() == 3).then(|| [loops[0][0], loops[0][1], loops[0][2]]);
            let tri_axis = tri.and_then(|t| plane_axis(&pts[t[0] as usize], &pts[t[1] as usize], &pts[t[2] as usize]));
            if let Some(t) = tri {
                for k in grid.cells(&[pts[t[0] as usize], pts[t[1] as usize], pts[t[2] as usize]]) {
                    let start = point_cells.partition_point(|x| x.0 < k);
                    near.extend(point_cells[start..].iter().take_while(|x| x.0 == k).map(|x| x.1));
                }
                near.sort_unstable_by_key(|&v| x_rank[v as usize]);
                near.dedup();
            } else if grid.box_cells(&lo, &hi) <= 64 + pts.len() as u64 / 8 {
                // the points in the cells of the box widened by the margin (all of the
                // listed points with a cell there: a point lies in its own cell)
                let mut keys = Vec::new();
                grid.cells_of_box(&lo, &hi, &mut keys);
                for k in keys {
                    let start = point_cells.partition_point(|x| x.0 < k);
                    near.extend(point_cells[start..].iter().take_while(|x| x.0 == k).map(|x| x.1));
                }
                near.sort_unstable_by_key(|&v| x_rank[v as usize]);
            } else {
                let start = by_x.partition_point(|&i| pts[i as usize][0] < lo[0]);
                near.extend(by_x[start..].iter().take_while(|&&v| pts[v as usize][0] <= hi[0]));
            }
            for v in near {
                let pv = &pts[v as usize];
                if own.contains(&v) || (0..3).any(|k| pv[k] < lo[k] || pv[k] > hi[k]) {
                    continue;
                }
                if let Some(t) = tri {
                    // off the triangle (in projection): not on it, whatever its plane
                    let axis = tri_axis.unwrap();
                    let o = |i: usize, j: usize| pr::orient2d_proj(axis, &pts[t[i] as usize], &pts[t[j] as usize], pv);
                    let s = [o(0, 1), o(1, 2), o(2, 0)];
                    if !(s.iter().all(|&x| x >= 0) || s.iter().all(|&x| x <= 0)) {
                        continue;
                    }
                }
                if pr::orient3d(&pts[a as usize], &pts[b as usize], &pts[c as usize], pv, &mut n) == 0 {
                    extra.push(v);
                }
            }
        }
        let members: HashSet<u32> = own.iter().copied().chain(extra.iter().copied()).collect();
        // the sub-segments with both ends among the members, in the order of subs
        let mut at: Vec<u32> = if members.len() <= 64 {
            // the pairs of members that are sub-segments (a vertex such as a fan's centre
            // may have far more sub-segments than the facet has members)
            let mv: Vec<u32> = members.iter().copied().collect();
            let mut found = Vec::new();
            for x in 0..mv.len() {
                for y in x + 1..mv.len() {
                    if let Some(&i) = sub_index.get(&(mv[x].min(mv[y]), mv[x].max(mv[y]))) {
                        found.push(i);
                    }
                }
            }
            found
        } else {
            members.iter().flat_map(|&v| subs_at[v as usize].iter().copied())
                .filter(|&i| { let (a, b) = subs[i as usize]; members.contains(&a) && members.contains(&b) }).collect()
        };
        at.sort_unstable();
        at.dedup();
        let inner: Vec<(u32, u32)> = at.iter().map(|&i| subs[i as usize]).collect();
        let t = facet::triangulate_checked(pts, loops, &extra, &inner).map_err(|e| {
            let named = InputError::new(e.witness, format!("facet {f}: {}", e.msg));
            match e.witness {
                Some(2 | 3) => named.with(Detail::Facet(f as u32)),
                _ => named,
            }
        })?;
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
        let mut boundary: Vec<(u32, u32)> = loops.iter()
            .flat_map(|lp| (0..lp.len()).map(move |k| (lp[k], lp[(k + 1) % lp.len()])))
            .flat_map(|(a, b)| edge_subs[edge_index[&(a.min(b), a.max(b))]].iter().copied())
            .collect();
        boundary.sort_unstable();
        boundary.dedup();
        let mut points: Vec<u32> = loops.iter().flatten().copied().chain(extra.iter().copied()).collect();
        points.dedup();
        out.facets.push(FacetInfo { points, boundary, inner: inner.clone(), axis: t.axis, flip: t.flip });
        out.triangle_facet.extend(std::iter::repeat_n(f as u32, t.triangles.len()));
        out.triangles.extend(t.triangles);
        facet_tris.push(tris);
        facet_edges.push(eds);
    }

    clock.lap("PLC check, 3 facets");
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
    let as_ref = |c: Cell| match c {
        Cell::Facet(f) => CellRef::Facet(f),
        Cell::Edge(e) => cell_ref(e),
    };
    let facets_of = |c: Cell| -> Vec<u32> {
        match c {
            Cell::Facet(f) => vec![f],
            Cell::Edge(e) => edge_facets[e as usize].clone(),
        }
    };
    // the piece `piece` lies in every cell of `cells`; it is a witness when two of them
    // contain no common cell that contains it. Two facets are preferred, as the
    // witness names facets; otherwise the facets of the two cells.
    let covered = |cells: &[Cell], piece: Vec<u32>| -> Result<(), InputError> {
        let bad_pair = |s: Cell, t: Cell| !cells.iter().any(|&h| contained(h, s) && contained(h, t));
        let mut first = None;
        for x in 0..cells.len() {
            for y in x + 1..cells.len() {
                let (s, t) = (cells[x], cells[y]);
                if bad_pair(s, t) {
                    if matches!((s, t), (Cell::Facet(_), Cell::Facet(_))) {
                        first = Some((s, t));
                        break;
                    }
                    first.get_or_insert((s, t));
                }
            }
            if matches!(first, Some((Cell::Facet(_), Cell::Facet(_)))) {
                break;
            }
        }
        let Some((s, t)) = first else { return Ok(()) };
        let e = bad(5, format!("{} and {} intersect in a part that no cell of both covers", name(s), name(t)));
        let cells = pick(&facets_of(s), &facets_of(t), as_ref(s), as_ref(t));
        Err(e.with(Detail::Point { cells, at: At::Centroid(piece) }))
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
        covered(&sub_cells[k], vec![k.0, k.1])?;
    }
    let mut tri_keys: Vec<[u32; 3]> = tri_cells.keys().copied().collect();
    tri_keys.sort_unstable();
    for k in &tri_keys {
        covered(&tri_cells[k], k.to_vec())?;
    }

    clock.lap("PLC check, 4 shared pieces");
    // 5. sub-segments against facet triangles, and triangles of different facets, meet
    //    only in shared faces
    let mut items: Vec<(bool, usize)> = subs.iter().enumerate().map(|(i, _)| (true, i)).collect();
    items.extend(tri_keys.iter().enumerate().map(|(i, _)| (false, i)));
    let boxes: Vec<_> = items.iter().map(|&(is_seg, i)| {
        if is_seg { bbox(pts, &[subs[i].0, subs[i].1]) } else { bbox(pts, &tri_keys[i]) }
    }).collect();
    let mut found: Option<((bool, usize), (bool, usize))> = None;
    let tri_cell: Vec<&Vec<Cell>> = tri_keys.iter().map(|k| &tri_cells[k]).collect();
    let pair_ok = |x: usize, y: usize, n: &mut Counters| -> Option<bool> {
        match (items[x], items[y]) {
            ((true, _), (true, _)) => None,
            ((true, i), (false, j)) | ((false, j), (true, i)) => Some(seg_tri_ok(pts, [subs[i].0, subs[i].1], tri_keys[j], n)),
            ((false, i), (false, j)) => {
                let (ci, cj) = (tri_cell[i], tri_cell[j]);
                if ci.iter().any(|c| cj.contains(c)) {
                    return None;
                }
                Some(tri_tri_ok(pts, tri_keys[i], tri_keys[j], n))
            }
        }
    };
    let verts: Vec<Verts> = items.iter()
        .map(|&(is_seg, i)| if is_seg { [subs[i].0, subs[i].1, u32::MAX] } else { tri_keys[i] })
        .collect();
    let cells: Vec<Vec<u64>> = items.iter().zip(&verts)
        .map(|(&(is_seg, i), vs)| if is_seg { sub_grid_cells[i].clone() } else {
            grid.cells(&vs.iter().map(|&v| pts[v as usize]).collect::<Vec<_>>())
        })
        .collect();
    let failed = std::cell::Cell::new(false);
    {
        let nc = std::cell::RefCell::new(&mut n);
        let count = std::cell::Cell::new(0usize);
        let test = |x: usize, y: usize| -> bool {
            if let Some(ok) = pair_ok(x, y, &mut nc.borrow_mut()) {
                count.set(count.get() + 1);
                if !ok {
                    failed.set(true);
                }
            }
            !failed.get()
        };
        let fast = |v: u32, star: &[u32]| -> Option<bool> {
            if star.len() < 4 {
                return None;
            }
            // the plane of the first triangle at v; items in it are checked by their
            // angular order, the others pair by pair
            let t = star.iter().find(|&&i| !items[i as usize].0)?;
            let others = |i: u32| -> Vec<u32> { verts[i as usize].iter().copied().filter(|&w| w != v && w != u32::MAX).collect() };
            let o = others(*t);
            let (pa, pb) = (&pts[o[0] as usize], &pts[o[1] as usize]);
            let axis = plane_axis(&pts[v as usize], pa, pb)?;
            let mut inplane = Vec::new();
            let mut rest = Vec::new();
            for &i in star {
                let w = others(i);
                if w.iter().all(|&x| pr::orient3d(&pts[v as usize], pa, pb, &pts[x as usize], &mut Counters::default()) == 0) {
                    inplane.push((w[0], *w.get(1).unwrap_or(&u32::MAX)));
                } else {
                    rest.push(i);
                }
            }
            if rest.len() * star.len() > 1 << 22 || !planar_star_ok(pts, v, axis, &inplane) {
                return None;
            }
            // the pairs with an item off the plane, at their smallest shared vertex
            for &r in &rest {
                for &x in star {
                    if x == r || (rest.contains(&x) && x < r) {
                        continue;
                    }
                    let (i, j) = (r.min(x) as usize, r.max(x) as usize);
                    let low = verts[i].iter().filter(|&&w| w != u32::MAX && verts[j].contains(&w)).min();
                    if low == Some(&v) && !test(i, j) {
                        return Some(false);
                    }
                }
            }
            Some(true)
        };
        let ok = grid_pairs(&cells, &verts, &boxes, |x, y| !(items[x].0 && items[y].0), test);
        let ok = ok && !failed.get() && star_pairs(pts.len(), &verts, |v, star| {
            let r = fast(v, star);
            if r == Some(false) { None } else { r }
        }, test);
        if !ok {
            failed.set(true);
        }
        tested += count.get();
    }
    // a failure: the witness is the first failing pair of the full sweep
    if failed.get() { for_overlapping(&boxes, |x, y| {
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
                let (ci, cj) = (tri_cell[i], tri_cell[j]);
                if ci.iter().any(|c| cj.contains(c)) {
                    return; // one facet's own triangulation
                }
                tested += 1;
                tri_tri_ok(pts, tri_keys[i], tri_keys[j], &mut n)
            }
        };
        if !ok {
            found = Some((a, b));
        }
    }); }
    if let Some((a, b)) = found {
        let cells = |(is_seg, i): (bool, usize)| -> &Vec<Cell> {
            if is_seg { &sub_cells[&subs[i]] } else { &tri_cells[&tri_keys[i]] }
        };
        let facets = |p: (bool, usize)| -> Vec<u32> {
            let mut v: Vec<u32> = cells(p).iter().flat_map(|&c| facets_of(c)).collect();
            v.dedup();
            v
        };
        let (a, b) = if a.0 || !b.0 { (a, b) } else { (b, a) }; // a segment first
        let e = bad(5, format!("{} and {} intersect", name(cells(a)[0]), name(cells(b)[0])));
        let at = match (a, b) {
            ((true, i), (false, j)) => At::SegTri([subs[i].0, subs[i].1], tri_keys[j]),
            ((false, i), (false, j)) => At::TriTri(tri_keys[i], tri_keys[j]),
            _ => unreachable!("segment pairs are checked in step 2"),
        };
        let cells = pick(&facets(a), &facets(b), as_ref(cells(a)[0]), as_ref(cells(b)[0]));
        return Err(e.with(Detail::Point { cells, at }));
    }
    out.pairs_tested = tested;
    clock.lap("PLC check, 5 crossings");
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

/// For p, q in the plane of a, b, c (projection `axis`): closed segment p-q meets
/// closed triangle a-b-c.
fn seg_meets_tri_2d(axis: usize, p: &P3, q: &P3, a: &P3, b: &P3, c: &P3) -> bool {
    let inside = |x: &P3| {
        let s = [pr::orient2d_proj(axis, a, b, x), pr::orient2d_proj(axis, b, c, x), pr::orient2d_proj(axis, c, a, x)];
        s.iter().all(|&v| v >= 0) || s.iter().all(|&v| v <= 0)
    };
    inside(p) || inside(q) || segs_meet_2d(axis, p, q, a, b) || segs_meet_2d(axis, p, q, b, c)
        || segs_meet_2d(axis, p, q, c, a)
}

/// True when closed segment p-q meets closed triangle a-b-c (no shared vertices).
fn seg_meets_tri(p: &P3, q: &P3, a: &P3, b: &P3, c: &P3, n: &mut Counters) -> bool {
    let op = pr::orient3d(a, b, c, p, n);
    let oq = pr::orient3d(a, b, c, q, n);
    if op * oq > 0 {
        return false;
    }
    if op == 0 && oq == 0 {
        return seg_meets_tri_2d(plane_axis(a, b, c).unwrap(), p, q, a, b, c);
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
        0 => {
            // u wholly on one side of t's plane: disjoint; coplanar: the closed triangles
            // in a projection, as the edge tests below would decide without orient3d
            let o = u.map(|w| pr::orient3d(p(t[0]), p(t[1]), p(t[2]), p(w), n));
            if o.iter().all(|&x| x > 0) || o.iter().all(|&x| x < 0) {
                return true;
            }
            if o.iter().all(|&x| x == 0) {
                let axis = plane_axis(p(t[0]), p(t[1]), p(t[2])).unwrap();
                let edges = |x: [u32; 3]| [[x[0], x[1]], [x[1], x[2]], [x[2], x[0]]];
                let meets = |e: [u32; 2], x: [u32; 3]| seg_meets_tri_2d(axis, p(e[0]), p(e[1]), p(x[0]), p(x[1]), p(x[2]));
                return !(edges(t).iter().any(|&e| meets(e, u)) || edges(u).iter().any(|&e| meets(e, t)));
            }
            let edges = |x: [u32; 3]| [[x[0], x[1]], [x[1], x[2]], [x[2], x[0]]];
            edges(t).iter().all(|&e| seg_tri_ok(pts, e, u, n)) && edges(u).iter().all(|&e| seg_tri_ok(pts, e, t, n))
        }
        _ => {
            // every edge of each against the other triangle (shared vertices allowed)
            let edges = |x: [u32; 3]| [[x[0], x[1]], [x[1], x[2]], [x[2], x[0]]];
            edges(t).iter().all(|&e| seg_tri_ok(pts, e, u, n)) && edges(u).iter().all(|&e| seg_tri_ok(pts, e, t, n))
        }
    }
}

// ------------------------------------------------------------ broad phase

/// A uniform grid of cubes of edge `cell` over the points' bounding box, for the
/// candidate pairs of the intersection tests. An item (point, segment or triangle) is
/// listed in the cells met by the boxes of its pieces: it is bisected (longest edge, in
/// doubles) until a piece's box spans at most one cell edge per axis, and each piece's
/// box is widened by a margin far above the rounding of the midpoints, so every cell the
/// exact item meets is listed; extra cells only cost time.
struct Grid {
    lo: [f64; 3],
    cell: f64,
    margin: f64,
    n: [u64; 3],
}

impl Grid {
    fn new(pts: &[P3], cell: f64) -> Grid {
        let mut lo = [f64::INFINITY; 3];
        let mut hi = [f64::NEG_INFINITY; 3];
        let mut m = 0.0f64;
        for p in pts {
            for k in 0..3 {
                lo[k] = lo[k].min(p[k]);
                hi[k] = hi[k].max(p[k]);
                m = m.max(p[k].abs());
            }
        }
        let ext = (0..3).map(|k| hi[k] - lo[k]).fold(0.0, f64::max);
        // at most 2^20 cells along an axis
        let floor = ext / (1u64 << 20) as f64;
        let cell = if cell.is_finite() && cell > 0.0 { cell.max(floor) } else { ext / 64.0 };
        let cell = if cell > 0.0 && cell.is_finite() { cell } else { 1.0 };
        let n = std::array::from_fn(|k| (((hi[k] - lo[k]) / cell) as u64 + 1).min(1 << 21));
        Grid { lo, cell, margin: m * 1e-12 + f64::MIN_POSITIVE, n }
    }

    fn coord(&self, x: f64, k: usize) -> u64 {
        let c = ((x - self.lo[k]) / self.cell).floor();
        if c >= 0.0 { (c as u64).min(self.n[k] - 1) } else { 0 }
    }

    fn key(c: [u64; 3]) -> u64 {
        (c[0] << 42) | (c[1] << 21) | c[2]
    }

    /// The number of cells of a box widened by the margin.
    fn box_cells(&self, lo: &[f64; 3], hi: &[f64; 3]) -> u64 {
        (0..3).map(|k| self.coord(hi[k] + self.margin, k) - self.coord(lo[k] - self.margin, k) + 1).product()
    }

    fn cells_of_box(&self, lo: &[f64; 3], hi: &[f64; 3], out: &mut Vec<u64>) {
        let a: [u64; 3] = std::array::from_fn(|k| self.coord(lo[k] - self.margin, k));
        let b: [u64; 3] = std::array::from_fn(|k| self.coord(hi[k] + self.margin, k));
        for x in a[0]..=b[0] {
            for y in a[1]..=b[1] {
                for z in a[2]..=b[2] {
                    out.push(Grid::key([x, y, z]));
                }
            }
        }
    }

    /// The cells of the simplex with 1, 2 or 3 vertices `v`, sorted, without repeats.
    fn cells(&self, v: &[P3]) -> Vec<u64> {
        let mut out = Vec::new();
        self.cells_rec(v, 48, &mut out);
        out.sort_unstable();
        out.dedup();
        out
    }

    fn cells_rec(&self, v: &[P3], depth: u32, out: &mut Vec<u64>) {
        let mut lo = v[0];
        let mut hi = v[0];
        for p in &v[1..] {
            for k in 0..3 {
                lo[k] = lo[k].min(p[k]);
                hi[k] = hi[k].max(p[k]);
            }
        }
        if v.len() == 1 || depth == 0 || (0..3).all(|k| hi[k] - lo[k] <= self.cell) {
            self.cells_of_box(&lo, &hi, out);
            return;
        }
        let len2 = |a: &P3, b: &P3| (0..3).map(|k| (a[k] - b[k]) * (a[k] - b[k])).sum::<f64>();
        let mid = |a: &P3, b: &P3| -> P3 { std::array::from_fn(|k| 0.5 * a[k] + 0.5 * b[k]) };
        if v.len() == 2 {
            let m = mid(&v[0], &v[1]);
            self.cells_rec(&[v[0], m], depth - 1, out);
            self.cells_rec(&[m, v[1]], depth - 1, out);
            return;
        }
        let (i, j, k) = [(0, 1, 2), (1, 2, 0), (2, 0, 1)].into_iter()
            .max_by(|x, y| len2(&v[x.0], &v[x.1]).total_cmp(&len2(&v[y.0], &v[y.1]))).unwrap();
        let m = mid(&v[i], &v[j]);
        self.cells_rec(&[v[i], m, v[k]], depth - 1, out);
        self.cells_rec(&[m, v[j], v[k]], depth - 1, out);
    }
}

/// The vertices of an item (u32::MAX for none).
type Verts = [u32; 3];

fn share_vertex(a: &Verts, b: &Verts) -> bool {
    a.iter().any(|&v| v != u32::MAX && b.contains(&v))
}

fn boxes_meet(a: &([f64; 3], [f64; 3]), b: &([f64; 3], [f64; 3])) -> bool {
    (0..3).all(|k| a.0[k] <= b.1[k] && b.0[k] <= a.1[k])
}

/// The first cell two sorted cell lists have in common.
fn first_common(a: &[u64], b: &[u64]) -> Option<u64> {
    let (mut i, mut j) = (0, 0);
    while i < a.len() && j < b.len() {
        match a[i].cmp(&b[j]) {
            std::cmp::Ordering::Less => i += 1,
            std::cmp::Ordering::Greater => j += 1,
            std::cmp::Ordering::Equal => return Some(a[i]),
        }
    }
    None
}

/// Calls `f(i, j)` (i < j) once for each pair of items that share a grid cell, share no
/// vertex, have meeting closed boxes and pass `keep`; stops when `f` returns false. Two
/// items that share a vertex v meet beyond v only arbitrarily close to v (both are
/// convex), so those pairs are the stars' business ([`star_pairs`]). In a crowded cell
/// the items through the vertex most of them share are not paired with each other.
fn grid_pairs(cells: &[Vec<u64>], verts: &[Verts], boxes: &[([f64; 3], [f64; 3])],
              keep: impl Fn(usize, usize) -> bool, mut f: impl FnMut(usize, usize) -> bool) -> bool {
    let mut reg: Vec<(u64, u32)> = cells.iter().enumerate()
        .flat_map(|(i, cs)| cs.iter().map(move |&c| (c, i as u32))).collect();
    reg.sort_unstable();
    let mut emit = |c: u64, x: u32, y: u32| -> bool {
        let (i, j) = (x.min(y) as usize, x.max(y) as usize);
        if i == j || share_vertex(&verts[i], &verts[j]) || !boxes_meet(&boxes[i], &boxes[j]) || !keep(i, j) {
            return true;
        }
        if cells[i].len() > 1 && cells[j].len() > 1 && first_common(&cells[i], &cells[j]) != Some(c) {
            return true; // met in an earlier cell
        }
        f(i, j)
    };
    let mut s = 0;
    while s < reg.len() {
        let c = reg[s].0;
        let mut e = s;
        while e < reg.len() && reg[e].0 == c {
            e += 1;
        }
        let items: Vec<u32> = reg[s..e].iter().map(|x| x.1).collect();
        if !cell_pairs(&items, verts, &mut |x, y| emit(c, x, y)) {
            return false;
        }
        s = e;
    }
    true
}

fn cell_pairs(items: &[u32], verts: &[Verts], emit: &mut impl FnMut(u32, u32) -> bool) -> bool {
    let all = |emit: &mut dyn FnMut(u32, u32) -> bool| {
        for a in 0..items.len() {
            for b in a + 1..items.len() {
                if !emit(items[a], items[b]) {
                    return false;
                }
            }
        }
        true
    };
    if items.len() <= 32 {
        return all(emit);
    }
    let mut count: HashMap<u32, u32> = HashMap::new();
    for &i in items {
        for &v in &verts[i as usize] {
            if v != u32::MAX {
                *count.entry(v).or_default() += 1;
            }
        }
    }
    let (h, k) = count.iter().map(|(&v, &c)| (v, c)).max_by_key(|&(v, c)| (c, std::cmp::Reverse(v))).unwrap_or((0, 0));
    if (k as usize) * 8 <= items.len() {
        return all(emit);
    }
    let (hub, rest): (Vec<u32>, Vec<u32>) = items.iter().partition(|&&i| verts[i as usize].contains(&h));
    if !cell_pairs(&rest, verts, emit) {
        return false;
    }
    for &r in &rest {
        for &x in &hub {
            if !emit(r, x) {
                return false;
            }
        }
    }
    true
}

/// Calls `f(i, j)` (i < j) once for each pair of items that share a vertex, at the
/// smallest vertex they share, until it returns false. `fast(v, star)` may decide a whole
/// star at once: Some(true) when every pair there passes, then those pairs are skipped
/// (pairs it cannot decide are visited as usual).
fn star_pairs(n: usize, verts: &[Verts], mut fast: impl FnMut(u32, &[u32]) -> Option<bool>,
              mut f: impl FnMut(usize, usize) -> bool) -> bool {
    let mut at: Vec<Vec<u32>> = vec![Vec::new(); n];
    for (i, vs) in verts.iter().enumerate() {
        for &v in vs {
            if v != u32::MAX {
                at[v as usize].push(i as u32);
            }
        }
    }
    for v in 0..n as u32 {
        let star = &at[v as usize];
        if star.len() < 2 || fast(v, star) == Some(true) {
            continue;
        }
        for a in 0..star.len() {
            for b in a + 1..star.len() {
                let (i, j) = (star[a].min(star[b]) as usize, star[a].max(star[b]) as usize);
                let low = verts[i].iter().filter(|&&w| w != u32::MAX && verts[j].contains(&w)).min();
                if low == Some(&v) && !f(i, j) {
                    return false;
                }
            }
        }
    }
    true
}

/// Sign of each coordinate of p - v.
fn signs3(v: &P3, p: &P3) -> [i8; 3] {
    std::array::from_fn(|k| (p[k] > v[k]) as i8 - (p[k] < v[k]) as i8)
}

/// A strict weak order of directions from v (exact): by the signs of the coordinates,
/// then by angle in the xy, xz and yz projections in turn (inside one orthant every
/// projection spans at most a quarter turn). Equal exactly for the same direction.
fn dir_cmp(v: &P3, p: &P3, q: &P3) -> std::cmp::Ordering {
    let (sp, sq) = (signs3(v, p), signs3(v, q));
    if sp != sq {
        return sp.cmp(&sq);
    }
    for axis in [2, 1, 0] {
        match pr::orient2d_proj(axis, v, p, q) {
            0 => continue,
            o if o > 0 => return std::cmp::Ordering::Less,
            _ => return std::cmp::Ordering::Greater,
        }
    }
    std::cmp::Ordering::Equal
}

/// Sub-segments at v (their other ends `ends`) meet only at v when no two point the
/// same way.
fn segment_star_ok(pts: &[P3], v: u32, ends: &mut [u32]) -> bool {
    let pv = &pts[v as usize];
    ends.sort_by(|&x, &y| dir_cmp(pv, &pts[x as usize], &pts[y as usize]));
    ends.windows(2).all(|w| dir_cmp(pv, &pts[w[0] as usize], &pts[w[1] as usize]) != std::cmp::Ordering::Equal)
}

/// For the items at v in the plane of the triangle `plane` (each a triangle v-a-b or a
/// segment v-x, given by its other vertices): true when they meet pairwise only at v or
/// along a common edge, triangles on opposite sides of it (exact, by the angular order of
/// their rays around v); false when that cannot be shown this way.
fn planar_star_ok(pts: &[P3], v: u32, axis: usize, items: &[(u32, u32)]) -> bool {
    let p = |i: u32| &pts[i as usize];
    let pv = p(v);
    let o2 = |a: u32, b: u32| pr::orient2d_proj(axis, pv, p(a), p(b));
    let (ki, kj) = pr::kept_axes(axis);
    let rays: Vec<u32> = {
        let mut r: Vec<u32> = items.iter().flat_map(|&(a, b)| if b == u32::MAX { vec![a] } else { vec![a, b] }).collect();
        r.sort_unstable();
        r.dedup();
        r
    };
    let d0 = rays[0];
    let class = |r: u32| -> u8 {
        match o2(d0, r) {
            o if o > 0 => 1,
            o if o < 0 => 3,
            _ => {
                let sg = |x: &P3, k: usize| (x[k] > pv[k]) as i8 - (x[k] < pv[k]) as i8;
                let same = [ki, kj].iter().all(|&k| sg(p(r), k) == sg(p(d0), k));
                if same { 0 } else { 2 }
            }
        }
    };
    let cmp = |a: &(u8, u32), b: &(u8, u32)| -> std::cmp::Ordering {
        if a.0 != b.0 {
            return a.0.cmp(&b.0);
        }
        if a.0 == 1 || a.0 == 3 {
            match o2(a.1, b.1) {
                o if o > 0 => return std::cmp::Ordering::Less,
                o if o < 0 => return std::cmp::Ordering::Greater,
                _ => {}
            }
        }
        std::cmp::Ordering::Equal
    };
    let mut keyed: Vec<(u8, u32)> = rays.iter().map(|&r| (class(r), r)).collect();
    keyed.sort_by(cmp);
    let mut rank: HashMap<u32, usize> = HashMap::new();
    let mut owner: Vec<u32> = Vec::new(); // the vertex on each rank (two different: overlap)
    for (i, x) in keyed.iter().enumerate() {
        if i > 0 && cmp(&keyed[i - 1], x) == std::cmp::Ordering::Equal {
            return false; // two vertices on one ray from v
        }
        rank.insert(x.1, owner.len());
        owner.push(x.1);
    }
    let r = owner.len();
    if r < 2 {
        return false;
    }
    // sectors cover the gaps between consecutive ranks (gap g: rank g to g + 1 mod r)
    let mut gaps = vec![0i32; r + 1];
    let mut inner = vec![0i32; r + 1]; // ranks strictly inside a sector
    let cover = |s: usize, e: usize, d: &mut Vec<i32>, from_next: bool| {
        // the cyclic range s..e (gaps) or s+1..e (ranks)
        let s0 = if from_next { (s + 1) % r } else { s };
        if s0 == e {
            return;
        }
        if s0 < e {
            d[s0] += 1;
            d[e] -= 1;
        } else {
            d[s0] += 1;
            d[r] -= 1;
            d[0] += 1;
            d[e] -= 1;
        }
    };
    let mut segs = Vec::new();
    for &(a, b) in items {
        if b == u32::MAX {
            segs.push(rank[&a]);
            continue;
        }
        let (s, e) = if o2(a, b) > 0 { (rank[&a], rank[&b]) } else { (rank[&b], rank[&a]) };
        cover(s, e, &mut gaps, false);
        cover(s, e, &mut inner, true);
    }
    let prefix = |d: &Vec<i32>| -> Vec<i32> {
        let mut acc = 0;
        d[..r].iter().map(|x| { acc += x; acc }).collect()
    };
    let (g, inn) = (prefix(&gaps), prefix(&inner));
    g.iter().all(|&c| c <= 1) && segs.iter().all(|&k| inn[k] == 0)
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

    fn lcg(s: &mut u64) -> f64 {
        *s = s.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
        (*s >> 11) as f64 / (1u64 << 53) as f64
    }

    /// Random points (some on a coarse grid, so many boxes touch exactly), items of 1-3
    /// of them, and a hub vertex in many items (a fan).
    fn random_items(seed: u64) -> (Vec<P3>, Vec<Verts>) {
        let mut s = seed;
        let mut pts = Vec::new();
        for k in 0..60 {
            let g = [(lcg(&mut s) * 6.0).floor(), (lcg(&mut s) * 6.0).floor(), (lcg(&mut s) * 2.0).floor()];
            if k % 2 == 0 && !pts.contains(&g) {
                pts.push(g);
            } else {
                pts.push([lcg(&mut s) * 6.0, lcg(&mut s) * 6.0, lcg(&mut s) * 2.0]);
            }
        }
        let mut items = Vec::new();
        for k in 0..400 {
            let mut pick = || (lcg(&mut s) * pts.len() as f64) as u32;
            let mut v = [pick(), pick(), pick()];
            if k % 3 == 0 {
                v[0] = 7; // the hub
            }
            match k % 4 {
                0 => v[2] = u32::MAX,
                1 if k % 8 == 1 => { v[1] = u32::MAX; v[2] = u32::MAX; }
                _ => {}
            }
            let used: Vec<u32> = v.iter().copied().filter(|&x| x != u32::MAX).collect();
            let mut d = used.clone();
            d.sort_unstable();
            d.dedup();
            let flat = used.len() == 3 && pr::collinear(&pts[used[0] as usize], &pts[used[1] as usize], &pts[used[2] as usize]);
            if d.len() == used.len() && !flat {
                items.push(v);
            }
        }
        (pts, items)
    }

    #[test]
    fn grid_and_stars_visit_the_pairs_of_the_sweep() {
        for seed in 1..6 {
            let (pts, items) = random_items(seed);
            for cell in [0.3, 1.0, 5.0] {
                let grid = Grid::new(&pts, cell);
                let at = |vs: &Verts| vs.iter().filter(|&&v| v != u32::MAX).map(|&v| pts[v as usize]).collect::<Vec<_>>();
                let cells: Vec<Vec<u64>> = items.iter().map(|vs| grid.cells(&at(vs))).collect();
                let boxes: Vec<_> = items.iter()
                    .map(|vs| bbox(&pts, &vs.iter().copied().filter(|&v| v != u32::MAX).collect::<Vec<_>>())).collect();
                let mut want_disjoint = HashSet::new();
                let mut want_shared = HashSet::new();
                for_overlapping(&boxes, |x, y| {
                    let p = (x.min(y), x.max(y));
                    if share_vertex(&items[x], &items[y]) { want_shared.insert(p) } else { want_disjoint.insert(p) };
                });
                let mut got = Vec::new();
                grid_pairs(&cells, &items, &boxes, |_, _| true, |i, j| { got.push((i, j)); true });
                let n = got.len();
                let got_set: HashSet<_> = got.into_iter().collect();
                assert_eq!(n, got_set.len(), "a pair visited twice");
                // only pairs of the sweep, and every disjoint pair that meets (exactly)
                assert!(got_set.is_subset(&want_disjoint), "seed {seed}, cell {cell}: a pair outside the sweep");
                let mut n = Counters::default();
                let mut meeting = 0;
                for &(i, j) in &want_disjoint {
                    let used = |vs: &Verts| vs.iter().copied().filter(|&v| v != u32::MAX).collect::<Vec<_>>();
                    let (a, b) = (used(&items[i]), used(&items[j]));
                    let meets = match (a.len(), b.len()) {
                        (2, 2) => !seg_seg_ok(&pts, [a[0], a[1]], [b[0], b[1]], &mut n),
                        (2, 3) => !seg_tri_ok(&pts, [a[0], a[1]], [b[0], b[1], b[2]], &mut n),
                        (3, 2) => !seg_tri_ok(&pts, [b[0], b[1]], [a[0], a[1], a[2]], &mut n),
                        (3, 3) => !tri_tri_ok(&pts, [a[0], a[1], a[2]], [b[0], b[1], b[2]], &mut n),
                        _ => false,
                    };
                    if meets {
                        meeting += 1;
                        assert!(got_set.contains(&(i, j)), "seed {seed}, cell {cell}: missed {:?} {:?} pts {:?} cells {:?} {:?}", items[i], items[j],
                            items[i].iter().chain(items[j].iter()).filter(|&&v| v != u32::MAX).map(|&v| pts[v as usize]).collect::<Vec<_>>(), cells[i], cells[j]);
                    }
                }
                assert!(meeting > 50, "too few meeting pairs: {meeting}");
                let mut star = Vec::new();
                star_pairs(pts.len(), &items, |_, _| None, |i, j| { star.push((i, j)); true });
                let n = star.len();
                let star_set: HashSet<_> = star.into_iter().collect();
                assert_eq!(n, star_set.len(), "a shared pair visited twice");
                assert_eq!(star_set, want_shared);
            }
        }
    }

    /// A fan of triangles (and spokes) around v in a tilted plane; with `overlap`, one
    /// extra triangle overlaps a neighbour or a spoke enters a triangle.
    fn fan(k: usize, overlap: usize) -> (Vec<P3>, u32, Vec<(u32, u32)>) {
        // the plane z = x + 2 y - 1, exactly (x and y on a 2^-20 grid)
        let at = |a: f64, r: f64| -> P3 {
            let q = |t: f64| (t * 1048576.0).round() / 1048576.0;
            let (x, y) = (q(0.25 + r * a.cos()), q(-1.5 + r * a.sin()));
            [x, y, x + 2.0 * y - 1.0]
        };
        let o = at(0.0, 0.0);
        let mut pts = vec![o];
        for i in 0..k {
            pts.push(at(2.0 * std::f64::consts::PI * i as f64 / k as f64, 1.0 + (i % 3) as f64 * 0.25));
        }
        let mut items: Vec<(u32, u32)> = (0..k as u32).map(|i| (1 + i, 1 + (i + 1) % k as u32)).collect();
        items.extend((0..k as u32).step_by(5).map(|i| (1 + i, u32::MAX)));
        match overlap {
            1 => items.push((1, 3)),                    // covers the first two triangles' common ray
            2 => {
                pts.push(at(0.5 * 2.0 * std::f64::consts::PI / k as f64, 0.5));
                items.push((pts.len() as u32 - 1, u32::MAX)); // a spoke inside the first triangle
            }
            3 => {
                pts.push(at(0.0, 0.5));
                items.push((pts.len() as u32 - 1, u32::MAX)); // a spoke along the first ray, shorter
            }
            _ => {}
        }
        (pts, 0, items)
    }

    #[test]
    fn the_planar_star_check_is_never_wrong() {
        for k in [3, 4, 7, 40, 200] {
            for overlap in 0..4 {
                let (pts, v, items) = fan(k, overlap);
                let axis = plane_axis(&pts[0], &pts[1], &pts[2]).unwrap();
                let ok = planar_star_ok(&pts, v, axis, &items);
                let mut n = Counters::default();
                let all_ok = (0..items.len()).all(|x| (x + 1..items.len()).all(|y| {
                    let (a, b) = (items[x], items[y]);
                    match (a.1 == u32::MAX, b.1 == u32::MAX) {
                        (true, true) => true,
                        (true, false) => seg_tri_ok(&pts, [v, a.0], [v, b.0, b.1], &mut n),
                        (false, true) => seg_tri_ok(&pts, [v, b.0], [v, a.0, a.1], &mut n),
                        (false, false) => tri_tri_ok(&pts, [v, a.0, a.1], [v, b.0, b.1], &mut n),
                    }
                }));
                assert!(!ok || all_ok, "k {k}, overlap {overlap}: the fast check passed an invalid star");
                if overlap == 0 && k >= 4 {
                    assert!(ok, "k {k}: a valid fan should pass the fast check");
                }
                if overlap > 0 {
                    assert!(!all_ok, "k {k}, overlap {overlap}: the test case should be invalid");
                }
            }
        }
    }

    /// A closed cylinder with fan caps of k sides.
    fn cylinder(k: usize) -> Plc {
        let mut points = Vec::new();
        for z in [0.0, 1.0] {
            for i in 0..k {
                let a = 2.0 * std::f64::consts::PI * i as f64 / k as f64;
                points.push([a.cos(), a.sin(), z]);
            }
        }
        points.push([0.0, 0.0, 0.0]);
        points.push([0.0, 0.0, 1.0]);
        let (k32, cb, ct) = (k as u32, 2 * k as u32, 2 * k as u32 + 1);
        let mut facets = Vec::new();
        for i in 0..k32 {
            let j = (i + 1) % k32;
            facets.push(vec![vec![cb, j, i]]);
            facets.push(vec![vec![ct, i + k32, j + k32]]);
            facets.push(vec![vec![i, j, j + k32]]);
            facets.push(vec![vec![i, j + k32, i + k32]]);
        }
        Plc { points, segments: Vec::new(), facets }
    }

    #[test]
    fn fans_are_checked_through_their_stars() {
        let c = check(&cylinder(300)).unwrap();
        assert!(c.open_subsegments.is_empty());
        assert!(c.pairs_tested < 300 * 300, "the fan pairs should not all be tested: {}", c.pairs_tested);
        // a cap triangle folded over its neighbour: the same witness as the full sweep's
        let mut bad = cylinder(300);
        let ct = 2 * 300 + 1;
        bad.facets.push(vec![vec![ct, 300, 302]]);
        let e = check(&bad).unwrap_err();
        assert_eq!(e.witness, Some(5), "{}", e.msg);
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
