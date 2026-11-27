// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

//! Segment recovery (M4 stage 3 of the pre-registered 3D plan; design note section 3).
//!
//! Every input segment must become a union of edges of the tetrahedralization. Starting
//! from the Delaunay tetrahedralization of the input points, round by round, every
//! piece of a segment that is not an edge is split once, where Si and Gärtner's rules
//! put the point (Si's thesis and IJNME 2011; the choice of Diazzi et al. 2023), so only
//! missing pieces get points (see [`split_parameter`]):
//! - the reference point p is the mesh neighbour of the piece's ends strictly inside its
//!   diametral ball that sees it under the largest angle;
//! - a piece of a segment with an acute end c (two segments meeting there at less than
//!   90 degrees) is split on the sphere about c through p (rule 2), or by rule 3 when
//!   that point is nearer the piece's far end than p; points about one vertex so build
//!   its protecting spheres lazily, only on missing segments;
//! - another piece at |e - p| from its end e nearer p when that is under half the piece
//!   (rule 1);
//! - a segment with two acute ends, a piece without a reference point, and a target
//!   outside the middle 62/64 of the piece: the middle.
//!
//! The parameter is a short dyadic within a relative 2^-24 of the piece around the
//! target, preferring one whose point is exactly a double. A round looks again only at
//! segments with a missing piece and at segments with a vertex next to a point the last
//! round inserted: an insertion removes an edge only when both its ends are on the new
//! point's cavity, so both become the point's neighbours.
//!
//! New points are S points `(a, b, t)` of the input segment a-b, inserted by the same
//! Bowyer-Watson kernel with the exact mixed predicates, so the result is the Delaunay
//! tetrahedralization (under the index-ordered perturbation) of the input points and
//! the S points. A piece shorter than 2^-`max_depth` of its segment is an error, not a
//! hang: termination after rounding the parameter is not proven (as for Diazzi et al.).
//!
//! The segments must be elementary and pairwise non-crossing (the output of the PLC
//! check: no point strictly inside a segment), so S points never coincide.

use crate::delaunay::{self, Error, Mesh};
use crate::mixed::{MixedCounters, MixedPoints, SPoint};
use crate::predicates::P3;
use std::collections::HashMap;

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
    /// the acute input end the piece is protected from (`NONE_END`), or `BOTH` for a
    /// whole segment whose two ends are acute
    toward: u32,
}

const NONE_END: u32 = u32::MAX;
const BOTH: u32 = u32::MAX - 1;

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
        .map(|(k, s)| vec![Piece { seg: k as u32, t0: 0.0, t1: 1.0, u: s[0], v: s[1], toward: NONE_END }])
        .collect();
    let mut incident: Vec<Vec<u32>> = vec![Vec::new(); n];
    for (k, s) in segments.iter().enumerate() {
        incident[s[0] as usize].push(k as u32);
        incident[s[1] as usize].push(k as u32);
    }
    let acute: Vec<bool> = (0..n).map(|v| is_acute(points, segments, &incident[v], v)).collect();
    let mut centres = vec![false; n];
    for (k, s) in segments.iter().enumerate() {
        pieces[k][0].toward = match (acute[s[0] as usize], acute[s[1] as usize]) {
            (true, true) => BOTH,
            (true, false) => s[0],
            (false, true) => s[1],
            (false, false) => NONE_END,
        };
    }

    // the segments to look at in a round: at first all; then those with a missing piece
    // in the last round and those with a vertex next to a point it inserted (an edge
    // that an insertion removes has both ends on the new point's cavity, so both
    // become its neighbours); the other pieces are still edges
    let mut look: std::collections::BTreeSet<usize> = (0..segments.len()).collect();
    let mut seg_of_s: Vec<u32> = Vec::new();
    loop {
        // the pieces that are not edges
        let mut missing: Vec<(usize, usize)> = Vec::new();
        for &k in &look {
            for (i, p) in pieces[k].iter().enumerate() {
                if !mesh.has_edge(p.u, p.v) {
                    missing.push((k, i));
                }
            }
        }
        let mut next: std::collections::BTreeSet<usize> = missing.iter().map(|&(k, _)| k).collect();
        stats.rounds += 1;
        if missing.is_empty() {
            break;
        }
        // one split of each, from the back of each segment's list so indices stay valid;
        // a piece that an earlier split of this round made an edge is left alone
        for &(k, i) in missing.iter().rev() {
            let p = pieces[k][i];
            if mesh.has_edge(p.u, p.v) {
                continue;
            }
            let s = segments[k];
            let (t, rule) = split_parameter(&mut mesh, points, s, &p, &acute);
            if !(t > p.t0 && t < p.t1) {
                return Err(Error::Internal(format!(
                    "segment {}: a piece is too short to split (do segments cross?)", p.seg)));
            }
            let depth = (-(t - p.t0).min(p.t1 - t).log2()).ceil() as u32;
            if depth > max_depth {
                return Err(Error::Internal(format!(
                    "segment {} needs more than {max_depth} halvings near t = {}", p.seg, p.t0)));
            }
            let id = insert_s(&mut mesh, SPoint::seg(s[0], s[1], t), &mut stats)?;
            seg_of_s.push(k as u32);
            for w in mesh.neighbours(id) {
                if (w as usize) < n {
                    next.extend(incident[w as usize].iter().map(|&j| j as usize));
                } else {
                    next.insert(seg_of_s[w as usize - n] as usize);
                }
            }
            match rule {
                Rule::Midpoint | Rule::Near => stats.bisection_points += 1,
                Rule::Centre(c) => {
                    stats.protection_points += 1;
                    if !centres[c as usize] {
                        centres[c as usize] = true;
                        stats.protected_vertices += 1;
                    }
                }
            }
            stats.max_depth = stats.max_depth.max(depth);
            // the halves: a segment whose two ends are acute is first split at its middle,
            // and each half is then protected from its own end
            let (lo, hi) = match p.toward {
                BOTH => (s[0], s[1]),
                c => (c, c),
            };
            pieces[k][i] = Piece { t1: t, v: id, toward: lo, ..p };
            pieces[k].insert(i + 1, Piece { t0: t, u: id, toward: hi, ..p });
        }
        look = next;
    }

    let chains: Vec<Vec<u32>> = pieces.iter()
        .map(|ps| std::iter::once(ps[0].u).chain(ps.iter().map(|p| p.v)).collect())
        .collect();
    let tets = mesh.tets();
    let kernel = mesh.stats();
    Ok(Recovered { tets, s: mesh.g.s.clone(), chains, stats, kernel, mixed: mesh.g.n })
}

/// A PLC after segment recovery: the recovered tetrahedralization, every facet's
/// subfacets (its constrained Delaunay triangulation with the S points on its
/// sub-segments, as global indices) and the subfacets that are not yet faces of the
/// tetrahedralization (facet recovery's work).
pub struct PlcRecovered {
    pub rec: Recovered,
    pub subfacets: Vec<Vec<[u32; 3]>>,
    pub missing: Vec<(u32, [u32; 3])>,
    pub plane: MixedCounters,
}

/// The PLC check, segment recovery on its elementary sub-segments, then the subfacets.
pub fn recover_plc(plc: &crate::plc::Plc, max_depth: u32) -> Result<PlcRecovered, String> {
    let checked = crate::plc::check(plc).map_err(|e| e.msg)?;
    recover_checked(plc, checked, max_depth)
}

/// `recover_plc` after the caller's own PLC check (its result on this PLC).
pub fn recover_checked(plc: &crate::plc::Plc, checked: crate::plc::Checked, max_depth: u32)
    -> Result<PlcRecovered, String> {
    let clock = StageClock::start();
    let segs = checked.subsegments.clone();
    let rec = recover(&plc.points, &segs, max_depth).map_err(|e| e.to_string())?;
    clock.lap("segment recovery");
    let (subfacets, missing, plane_n) = {
    let chain_of: HashMap<(u32, u32), &Vec<u32>> = segs.iter().zip(&rec.chains)
        .map(|(s, c)| ((s[0].min(s[1]), s[0].max(s[1])), c)).collect();
    let plane = crate::mixed::MixedPlane {
        m: crate::mixed::Mixed::new(&plc.points, &rec.s),
        n: std::cell::Cell::new(MixedCounters::default()),
    };
    let chain = |e: &(u32, u32)| -> Result<&Vec<u32>, String> {
        chain_of.get(&(e.0.min(e.1), e.0.max(e.1))).copied()
            .ok_or_else(|| format!("sub-segment {}-{} has no recovered chain", e.0, e.1))
    };
    let mut subfacets = Vec::with_capacity(checked.facets.len());
    for (f, info) in checked.facets.iter().enumerate() {
        let mut points = info.points.clone();
        let mut boundary = Vec::new();
        let on_boundary: std::collections::HashSet<(u32, u32)> = info.boundary.iter().copied().collect();
        for e in &info.boundary {
            let c = chain(e)?;
            points.extend(&c[1..c.len() - 1]);
            boundary.extend(c.windows(2).map(|w| (w[0], w[1])));
        }
        let mut inner = Vec::new();
        for e in info.inner.iter().filter(|e| !on_boundary.contains(&(e.0.min(e.1), e.0.max(e.1)))) {
            let c = chain(e)?;
            points.extend(&c[1..c.len() - 1]);
            inner.extend(c.windows(2).map(|w| (w[0], w[1])));
        }
        let tris = crate::facet::cdt(&plane, info.axis, &points, &boundary, &inner, info.flip)
            .map_err(|(_, m)| format!("facet {f} with its segment points: {m}"))?;
        subfacets.push(tris);
    }
    let faces: std::collections::HashSet<[u32; 3]> = rec.tets.iter()
        .flat_map(|v| (0..4).map(move |i| {
            let mut k = [v[(i + 1) % 4], v[(i + 2) % 4], v[(i + 3) % 4]];
            k.sort_unstable();
            k
        }))
        .collect();
    let mut missing = Vec::new();
    for (f, tris) in subfacets.iter().enumerate() {
        for t in tris {
            let mut k = *t;
            k.sort_unstable();
            if !faces.contains(&k) {
                missing.push((f as u32, *t));
            }
        }
    }
    clock.lap("subfacets");
    (subfacets, missing, plane.n.get())
    };
    Ok(PlcRecovered { rec, subfacets, missing, plane: plane_n })
}

/// Stage timings on stderr when `MESHLOOM_PROFILE` is set (profiling only; no effect
/// on results).
pub struct StageClock(Option<std::cell::Cell<std::time::Instant>>);

impl StageClock {
    pub fn start() -> StageClock {
        StageClock(std::env::var_os("MESHLOOM_PROFILE").map(|_| std::cell::Cell::new(std::time::Instant::now())))
    }

    pub fn lap(&self, stage: &str) {
        if let Some(c) = &self.0 {
            let now = std::time::Instant::now();
            eprintln!("meshloom profile: {stage}: {:.3} s", (now - c.get()).as_secs_f64());
            c.set(now);
        }
    }
}

#[derive(Clone, Copy, Debug)]
enum Rule {
    /// the middle of the piece
    Midpoint,
    /// rule 1: on the sphere about the piece end nearer the reference point
    Near,
    /// rules 2 and 3: on a sphere about the acute input end c
    Centre(u32),
}

/// Where to split a missing piece of segment a-b (Si–Gärtner's rules, as in Si's thesis
/// and Diazzi et al. 2023). The reference point p is, among the mesh neighbours of the
/// piece's ends that lie strictly inside its diametral ball (exactly), the one seeing
/// the piece under the largest angle (in doubles; ties by index). With no such point,
/// or when a rule's point falls outside the middle 62/64 of the piece, the middle.
/// - Rule 1 (no acute end): the point at |u - p| from u when that is under half the
///   piece, else at |v - p| from v when that is, else the middle.
/// - Rule 2 (protected from the acute end c): the point at distance |c - p| from c;
///   rejected when it is nearer the far end than p, then
/// - Rule 3: with v0 that point and e the near end, at s(v0) - |p - v0| from c when
///   |p - v0| < |e - v0| / 2, else halfway between e and v0.
/// The parameter is a short dyadic within a relative 2^-24 of the piece around the
/// target, preferring an exact double point (so points of one centre lie on a common
/// sphere up to that).
fn split_parameter(mesh: &mut Mesh<MixedPoints>, points: &[P3], s: [u32; 2], p: &Piece, acute: &[bool]) -> (f64, Rule) {
    let _ = acute;
    let mid = (p.t0 + (p.t1 - p.t0) / 2.0, Rule::Midpoint);
    if p.toward == BOTH {
        return mid;
    }
    let m = mesh.g.view();
    let (pu, pv) = (m.from_id(p.u), m.from_id(p.v));
    // a point's coordinates rounded to doubles (segment points without big integers)
    let rounded = |m: &crate::mixed::Mixed, q: crate::mixed::Pt| -> P3 {
        if let crate::mixed::Pt::S(k) = q {
            let sp = m.s[k as usize];
            if sp.kind() == crate::mixed::Kind::Segment {
                let (a, b) = (&m.input[sp.a as usize], &m.input[sp.b as usize]);
                if let (Some(x), Some(y), Some(z)) = (rounded_coordinate(a[0], b[0], sp.t), rounded_coordinate(a[1], b[1], sp.t),
                                                      rounded_coordinate(a[2], b[2], sp.t)) {
                    return [x, y, z];
                }
            }
        }
        m.rounded(q)
    };
    let (xu, xv) = (rounded(&m, pu), rounded(&m, pv));
    let mut cand = mesh.neighbours(p.u);
    for w in mesh.neighbours(p.v) {
        if !cand.contains(&w) {
            cand.push(w);
        }
    }
    let m = mesh.g.view();
    let mut best: Option<(f64, u32, P3)> = None;
    for w in cand {
        if w == p.u || w == p.v {
            continue;
        }
        let pw = m.from_id(w);
        if !m.in_diametral_ball(pw, pu, pv) {
            continue;
        }
        let x = rounded(&m, pw);
        // cos of the angle u-w-v: smaller is wider
        let (a, b) = (sub(&xu, &x), sub(&xv, &x));
        let c = dot(&a, &b) / (dot(&a, &a) * dot(&b, &b)).sqrt();
        if best.is_none_or(|(bc, bw, _)| c < bc || (c == bc && w < bw)) {
            best = Some((c, w, x));
        }
    }
    let Some((_, _, xp)) = best else { return mid };
    let (pa, pb) = (&points[s[0] as usize], &points[s[1] as usize]);
    let len = dist(pa, pb);
    let span = p.t1 - p.t0;
    let (lo, hi) = (p.t0 + span / 64.0, p.t1 - span / 64.0);
    let (target, rule) = match p.toward {
        NONE_END => {
            let (du, dv, l) = (dist(&xu, &xp), dist(&xv, &xp), span * len);
            if du < l / 2.0 {
                (p.t0 + du / len, Rule::Near)
            } else if dv < l / 2.0 {
                (p.t1 - dv / len, Rule::Near)
            } else {
                return mid;
            }
        }
        c => {
            // distances along the segment from c
            let from_a = c == s[0];
            let sd = |t: f64| if from_a { t * len } else { (1.0 - t) * len };
            let to_t = |d: f64| if from_a { d / len } else { 1.0 - d / len };
            let xc = &points[c as usize];
            let (near, far) = if from_a { (p.t0, p.t1) } else { (p.t1, p.t0) };
            let r = dist(xc, &xp);
            let v0 = to_t(r);
            let at = |t: f64| -> P3 { std::array::from_fn(|k| pa[k] + t * (pb[k] - pa[k])) };
            let xv0 = at(v0);
            let xfar = at(far);
            if dist(&xv0, &xfar) >= dist(&xv0, &xp) {
                (v0, Rule::Centre(c)) // rule 2
            } else {
                let (se, s0) = (sd(near), sd(v0));
                let pv0 = dist(&xp, &xv0);
                let r3 = if pv0 < (s0 - se) / 2.0 { s0 - pv0 } else { se + (s0 - se) / 2.0 };
                (to_t(r3), Rule::Centre(c))
            }
        }
    };
    if !(target >= lo && target <= hi) {
        return mid;
    }
    let w = span * 2f64.powi(-24);
    let exact = |t: f64| exact_point(pa, pb, t);
    (pick_t((target - w).max(lo), (target + w).min(hi), exact), rule)
}

fn sub(a: &P3, b: &P3) -> P3 {
    [a[0] - b[0], a[1] - b[1], a[2] - b[2]]
}

fn dot(a: &P3, b: &P3) -> f64 {
    a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
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
    let s = [SPoint::seg(0, 1, t)];
    crate::mixed::Mixed::new(&input, &s).is_exact(crate::mixed::Pt::S(0))
}

fn two_sum(a: f64, b: f64) -> (f64, f64) {
    let s = a + b;
    let bb = s - a;
    (s, (a - (s - bb)) + (b - bb))
}

fn two_product(a: f64, b: f64) -> (f64, f64) {
    let p = a * b;
    (p, a.mul_add(b, -p))
}

/// Adds b to the nonoverlapping expansion e[..*n] (Shewchuk's grow-expansion, zeros
/// dropped).
fn grow(e: &mut [f64; 12], n: &mut usize, b: f64) {
    let mut q = b;
    let mut m = 0;
    for i in 0..*n {
        let (s, h) = two_sum(q, e[i]);
        q = s;
        if h != 0.0 {
            e[m] = h;
            m += 1;
        }
    }
    if q != 0.0 {
        e[m] = q;
        m += 1;
    }
    *n = m;
}

/// The exact a + t (b - a) as a nonoverlapping expansion (zeros dropped), with its
/// length; None when a term is not finite.
fn coordinate_expansion(a: f64, b: f64, t: f64) -> Option<([f64; 12], usize)> {
    let (s, es) = two_sum(b, -a);
    let (p, ep) = two_product(t, s);
    let (q, eq) = two_product(t, es);
    let terms = [a, p, ep, q, eq];
    if !terms.iter().all(|x| x.is_finite()) {
        return None;
    }
    let mut e = [0.0; 12];
    let mut n = 0;
    for x in terms {
        grow(&mut e, &mut n, x);
    }
    Some((e, n))
}

/// Sign of the expansion e[..n] minus x minus y, exactly.
fn sign_minus(e: &[f64; 12], n: usize, x: f64, y: f64) -> i8 {
    let mut f = *e;
    let mut m = n;
    grow(&mut f, &mut m, -x);
    grow(&mut f, &mut m, -y);
    if m == 0 { 0 } else if f[m - 1] > 0.0 { 1 } else { -1 }
}

/// a + t (b - a) rounded to the nearest double, ties to even (as
/// [`crate::mixed::Mixed::rounded`] for a segment point, without big integers).
fn rounded_coordinate(a: f64, b: f64, t: f64) -> Option<f64> {
    let (e, n) = coordinate_expansion(a, b, t)?;
    if n == 0 {
        return Some(0.0); // an exact zero is +0
    }
    let mut h: f64 = e[..n].iter().fold(0.0, |x, y| x + y);
    if !h.is_finite() {
        return None;
    }
    // move h to the double nearest the exact value: the exact value lies between the
    // midpoints to h's neighbours, a tie going to the even neighbour
    for _ in 0..4 {
        let (lo, hi) = (h.next_down(), h.next_up());
        // the midpoints h + (hi - h)/2 and h + (lo - h)/2, kept as two exact terms
        let above = sign_minus(&e, n, h, (hi - h) / 2.0);
        let below = sign_minus(&e, n, h, (lo - h) / 2.0);
        let even = |x: f64| x.to_bits() & 1 == 0;
        if above > 0 || (above == 0 && !even(h)) {
            h = hi;
        } else if below < 0 || (below == 0 && !even(h)) {
            h = lo;
        } else {
            return Some(h);
        }
    }
    None
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
        let mut g = MixedPoints::new(points.to_vec());
        for sp in &r.s {
            g.push(*sp);
        }
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

    /// The rounded segment points agree with the big-integer rounding.
    #[test]
    fn rounded_segment_points_agree_with_dyadic_arithmetic() {
        let mut s = 5u64;
        for k in 0..20000 {
            let pick = |s: &mut u64| match k % 3 {
                0 => (lcg(s) * 64.0).floor() / 8.0 - 4.0,
                1 => lcg(s) * 10.0 - 5.0,
                _ => (lcg(s) - 0.5) * 1e-20,
            };
            let a = [pick(&mut s), pick(&mut s), pick(&mut s)];
            let b = [pick(&mut s), pick(&mut s), pick(&mut s)];
            let t = if k % 2 == 0 { (lcg(&mut s) * 4096.0).floor().max(1.0) / 4096.0 } else { lcg(&mut s).max(1e-9) };
            let input = [a, b];
            let sp = [SPoint::seg(0, 1, t)];
            let want = crate::mixed::Mixed::new(&input, &sp).rounded(crate::mixed::Pt::S(0));
            let got: Vec<f64> = (0..3).map(|c| rounded_coordinate(a[c], b[c], t).unwrap()).collect();
            assert_eq!(got.iter().map(|x| x.to_bits()).collect::<Vec<_>>(), want.iter().map(|x| x.to_bits()).collect::<Vec<_>>(),
                       "{a:?} {b:?} {t}");
        }
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
        // only the origin is acute, and only missing pieces are split (Si's rules 2 and 3
        // about it): the 1 and 5 degree spokes cannot all be edges
        assert_eq!(r.stats.protected_vertices, 1, "{:?}", r.stats);
        assert!(r.stats.protection_points >= 1 && r.stats.protection_points < 40, "{:?}", r.stats);
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

    fn plc_of(points: Vec<P3>, facets: Vec<Vec<Vec<u32>>>) -> crate::plc::Plc {
        crate::plc::Plc { points, segments: Vec::new(), facets }
    }

    fn voxel(cells: &[[i32; 3]], tilt: bool) -> crate::plc::Plc {
        let set: HashSet<[i32; 3]> = cells.iter().copied().collect();
        let mut index: HashMap<[i32; 3], u32> = HashMap::new();
        let mut points = Vec::new();
        let mut facets = Vec::new();
        let mut pid = |c: [i32; 3], points: &mut Vec<P3>| *index.entry(c).or_insert_with(|| {
            let p = [c[0] as f64 * 0.25, c[1] as f64 * 0.25, c[2] as f64 * 0.25];
            points.push(if tilt {
                [2.0 * p[0] + p[1], -p[0] + 2.0 * p[1] + p[2], p[1] + 3.0 * p[2]]
            } else { p });
            points.len() as u32 - 1
        });
        for &c in cells {
            for axis in 0..3 {
                for side in [0, 1] {
                    let mut nb = c;
                    nb[axis] += if side == 1 { 1 } else { -1 };
                    if set.contains(&nb) {
                        continue;
                    }
                    let mut base = c;
                    base[axis] += side;
                    let (u, v) = [(1, 2), (2, 0), (0, 1)][axis];
                    let corners: Vec<u32> = [(0, 0), (1, 0), (1, 1), (0, 1)].iter().map(|&(du, dv)| {
                        let mut q = base;
                        q[u] += du;
                        q[v] += dv;
                        pid(q, &mut points)
                    }).collect();
                    facets.push(vec![corners]);
                }
            }
        }
        plc_of(points, facets)
    }

    #[test]
    fn subfacets_after_segment_recovery() {
        let fichera: Vec<[i32; 3]> = (0..8).map(|k| [k & 1, (k >> 1) & 1, (k >> 2) & 1]).filter(|c| *c != [1, 1, 1]).collect();
        let slab: Vec<[i32; 3]> = (0..12).map(|k| [k % 4, k / 4, 0]).collect();
        let mut prism_pts = Vec::new();
        for (h, rot) in [(0.0f64, 0.0f64), (1.0, 30.0)] {
            for k in 0..3 {
                let a = (120.0 * k as f64 + rot).to_radians();
                prism_pts.push([a.cos(), a.sin(), h]);
            }
        }
        let prism = plc_of(prism_pts, [[0, 2, 1], [3, 4, 5], [0, 1, 4], [0, 4, 3], [1, 2, 5], [1, 5, 4], [2, 0, 3], [2, 3, 5]]
            .iter().map(|t| vec![t.to_vec()]).collect());
        // two stacked cells with their interface as a facet, and free points just above and
        // below it: the interface triangles stop being Delaunay (hull faces never do)
        let mut cube = voxel(&[[0, 0, 0], [0, 0, 1]], false);
        let corner = |p: P3, pts: &[P3]| pts.iter().position(|q| *q == p).unwrap() as u32;
        let iface = vec![vec![corner([0.0, 0.0, 0.25], &cube.points), corner([0.25, 0.0, 0.25], &cube.points),
                              corner([0.25, 0.25, 0.25], &cube.points), corner([0.0, 0.25, 0.25], &cube.points)]];
        cube.facets.push(iface);
        let mut seed = 21u64;
        for k in 0..40 {
            let (u, v) = (0.02 + 0.21 * lcg(&mut seed), 0.02 + 0.21 * lcg(&mut seed));
            let d = 0.0005 + 0.01 * lcg(&mut seed);
            cube.points.push([u, v, if k % 2 == 0 { 0.25 + d } else { 0.25 - d }]);
        }
        let near = recover_plc(&cube, 60).unwrap();
        eprintln!("interface with near points: {} subfacets, {} missing", near.subfacets.iter().map(|t| t.len()).sum::<usize>(), near.missing.len());
        assert!(!near.missing.is_empty(), "facet recovery has work to do");
        for (name, plc) in [("fichera", voxel(&fichera, false)), ("fichera tilted", voxel(&fichera, true)),
                            ("slab", voxel(&slab, false)), ("slab tilted", voxel(&slab, true)), ("prism", prism)] {
            let r = recover_plc(&plc, 60).unwrap();
            // every subfacet set covers its facet: as many triangles as the facet needs
            assert!(r.subfacets.iter().all(|t| !t.is_empty()), "{name}");
            eprintln!("{name}: {} points, {} S points, {} subfacets, {} missing", plc.points.len(), r.rec.s.len(),
                      r.subfacets.iter().map(|t| t.len()).sum::<usize>(), r.missing.len());
        }
    }
}
