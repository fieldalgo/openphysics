// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

//! Test-only reference for V16: the predicates recomputed with big integers. Each
//! case's doubles are written exactly as integers times one common power of two, and
//! every determinant is expanded by cofactors in integer arithmetic. It shares no
//! code with the expansion arithmetic it checks. The perturbed insphere is checked
//! through the full 5 x 5 lifted determinant with an explicit, small enough
//! perturbation, not through the cofactor rule the kernel uses.

use crate::bigint::{decompose, Big};
use crate::predicates::{self as pr, Counters, P3};

/// The points of one case as integers on a common scale 2^e0.
fn integers(pts: &[P3]) -> Vec<[Big; 3]> {
    let e0 = pts.iter().flatten().filter(|x| **x != 0.0).map(|&x| {
        decompose(x).1
    }).min().unwrap_or(0);
    pts.iter().map(|p| {
        let conv = |x: f64| {
            if x == 0.0 {
                return Big::zero();
            }
            let (m, e, neg) = decompose(x);
            Big::from_u64_shl(m, (e - e0) as u32, neg)
        };
        [conv(p[0]), conv(p[1]), conv(p[2])]
    }).collect()
}

fn sub3(a: &[Big; 3], b: &[Big; 3]) -> [Big; 3] {
    [a[0].sub(&b[0]), a[1].sub(&b[1]), a[2].sub(&b[2])]
}

fn dot(a: &[Big; 3], b: &[Big; 3]) -> Big {
    a[0].mul(&b[0]).add(&a[1].mul(&b[1])).add(&a[2].mul(&b[2]))
}

fn cross(a: &[Big; 3], b: &[Big; 3]) -> [Big; 3] {
    [
        a[1].mul(&b[2]).sub(&a[2].mul(&b[1])),
        a[2].mul(&b[0]).sub(&a[0].mul(&b[2])),
        a[0].mul(&b[1]).sub(&a[1].mul(&b[0])),
    ]
}

/// Determinant of a square matrix by cofactor expansion along the first row.
fn det(m: &[Vec<Big>]) -> Big {
    let n = m.len();
    if n == 1 {
        return m[0][0].clone();
    }
    let mut acc = Big::zero();
    for j in 0..n {
        if m[0][j].sign() == 0 {
            continue;
        }
        let minor: Vec<Vec<Big>> = m[1..].iter()
            .map(|row| row.iter().enumerate().filter(|(k, _)| *k != j).map(|(_, x)| x.clone()).collect())
            .collect();
        let t = m[0][j].mul(&det(&minor));
        acc = if j % 2 == 0 { acc.add(&t) } else { acc.sub(&t) };
    }
    acc
}

pub fn orient3d(p: &[P3; 4]) -> i8 {
    orient3d_q(&integers(p))
}

fn orient3d_q(q: &[[Big; 3]]) -> i8 {
    let rows = vec![sub3(&q[1], &q[0]).to_vec(), sub3(&q[2], &q[0]).to_vec(), sub3(&q[3], &q[0]).to_vec()];
    det(&rows).sign()
}

pub fn insphere(p: &[P3; 5]) -> i8 {
    insphere_q(&integers(p))
}

fn insphere_q(q: &[[Big; 3]]) -> i8 {
    let rows: Vec<Vec<Big>> = (0..4).map(|i| {
        let d = sub3(&q[i], &q[4]);
        let l = dot(&d, &d);
        vec![d[0].clone(), d[1].clone(), d[2].clone(), l]
    }).collect();
    -det(&rows).sign()
}

/// -det5[p, |p|^2 + delta^(rank + 1), 1] with rank 0 for the largest id, for a delta
/// small enough that the perturbation terms are ordered by their power.
pub fn insphere_sos(p: &[P3; 5], ids: [u32; 5]) -> i8 {
    insphere_sos_q(&integers(p), ids)
}

fn insphere_sos_q(q: &[[Big; 3]], ids: [u32; 5]) -> i8 {
    let coord_bits = q.iter().flatten().map(|x| x.bits()).max().unwrap_or(1);
    // every 4 x 4 cofactor is below 2^(3 coord_bits + 2 coord_bits + 8); one power of delta
    // more must dwarf the sum of all of them
    let b = 6 * coord_bits + 32;
    let mut rank = [0u32; 5];
    for i in 0..5 {
        rank[i] = (0..5).filter(|&j| ids[j] > ids[i]).count() as u32;
    }
    let rows: Vec<Vec<Big>> = (0..5).map(|i| {
        let l = dot(&q[i], &q[i]).mul(&Big::pow2(5 * b)).add(&Big::pow2((4 - rank[i]) * b));
        vec![q[i][0].clone(), q[i][1].clone(), q[i][2].clone(), l, Big::from_u64_shl(1, 0, false)]
    }).collect();
    // the coordinate columns are not scaled, the lifted one by 2^(5b): a positive factor
    -det(&rows).sign()
}

pub fn incircle3d(p: &[P3; 4]) -> i8 {
    let q = integers(p);
    let u = sub3(&q[1], &q[0]);
    let v = sub3(&q[2], &q[0]);
    let w = sub3(&q[3], &q[0]);
    let n = cross(&u, &v);
    let t = dot(&u, &u).mul(&dot(&cross(&v, &w), &n))
        .sub(&dot(&v, &v).mul(&dot(&cross(&u, &w), &n)))
        .add(&dot(&w, &w).mul(&dot(&n, &n)));
    -t.sign()
}

/// Component `axis` of (b - a) x (c - a).
pub fn orient2d_proj(axis: usize, p: &[P3; 3]) -> i8 {
    orient2d_proj_q(axis, &integers(p))
}

fn orient2d_proj_q(axis: usize, q: &[[Big; 3]]) -> i8 {
    cross(&sub3(&q[1], &q[0]), &sub3(&q[2], &q[0]))[axis].sign()
}

fn kept(axis: usize) -> (usize, usize) {
    match axis {
        0 => (1, 2),
        1 => (2, 0),
        _ => (0, 1),
    }
}

/// det4[u, v, |p|^2, 1] over a, b, c, d (projected u, v; 3D squared norm).
pub fn incircle_plane(axis: usize, p: &[P3; 4]) -> i8 {
    incircle_plane_q(axis, &integers(p))
}

fn incircle_plane_q(axis: usize, q: &[[Big; 3]]) -> i8 {
    let (i, j) = kept(axis);
    let rows: Vec<Vec<Big>> = (0..4)
        .map(|k| vec![q[k][i].clone(), q[k][j].clone(), dot(&q[k], &q[k]), Big::from_u64_shl(1, 0, false)])
        .collect();
    det(&rows).sign()
}

/// The same with the lifted column raised by delta^(rank + 1), rank 0 for the largest id,
/// for a delta small enough to order the powers.
pub fn incircle_plane_sos(axis: usize, p: &[P3; 4], ids: [u32; 4]) -> i8 {
    incircle_plane_sos_q(axis, &integers(p), ids)
}

fn incircle_plane_sos_q(axis: usize, q: &[[Big; 3]], ids: [u32; 4]) -> i8 {
    let (i, j) = kept(axis);
    let coord_bits = q.iter().flatten().map(|x| x.bits()).max().unwrap_or(1);
    let b = 4 * coord_bits + 32;
    let rows: Vec<Vec<Big>> = (0..4)
        .map(|k| {
            let rank = (0..4).filter(|&m| ids[m] > ids[k]).count() as u32;
            let l = dot(&q[k], &q[k]).mul(&Big::pow2(4 * b)).add(&Big::pow2((3 - rank) * b));
            vec![q[k][i].clone(), q[k][j].clone(), l, Big::from_u64_shl(1, 0, false)]
        })
        .collect();
    det(&rows).sign()
}

// ---------------------------------------------------------------- V16 case generators

pub struct Rng(pub u64);

impl Rng {
    pub fn next(&mut self) -> u64 {
        self.0 = self.0.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
        let mut x = self.0;
        x ^= x >> 33;
        x = x.wrapping_mul(0xff51afd7ed558ccd);
        x ^ (x >> 33)
    }
    pub fn unit(&mut self) -> f64 {
        (self.next() >> 11) as f64 / (1u64 << 53) as f64
    }
    pub fn int(&mut self, n: u64) -> i64 {
        (self.next() % n) as i64
    }
    pub fn point(&mut self) -> P3 {
        [self.unit() * 2.0 - 1.0, self.unit() * 2.0 - 1.0, self.unit() * 2.0 - 1.0]
    }
}

fn nudge(x: f64, k: i64) -> f64 {
    if k == 0 || x == 0.0 {
        return x;
    }
    let bits = x.to_bits() as i64;
    f64::from_bits((bits + k) as u64)
}

fn scale(p: P3, s: f64) -> P3 {
    [p[0] * s, p[1] * s, p[2] * s]
}

/// A random power of two that keeps every coordinate of a case inside the domain.
fn domain_scale(r: &mut Rng) -> f64 {
    2f64.powi(r.int(160) as i32 - 80)
}

/// Integer points on the sphere x^2 + y^2 + z^2 = 3^2 7^2 (and more), by sign and
/// coordinate permutations of a few known representations.
fn sphere_points() -> Vec<P3> {
    let reps = [[21.0, 0.0, 0.0], [19.0, 8.0, 4.0], [16.0, 13.0, 4.0], [17.0, 4.0, 12.0], [14.0, 14.0, 7.0],
                [16.0, 11.0, 8.0], [20.0, 5.0, 4.0]];
    let mut out = Vec::new();
    for r in reps {
        let r: [f64; 3] = r;
        for perm in [[0, 1, 2], [0, 2, 1], [1, 0, 2], [1, 2, 0], [2, 0, 1], [2, 1, 0]] {
            for s in 0..8 {
                let p = [
                    r[perm[0]] * if s & 1 == 1 { -1.0 } else { 1.0 },
                    r[perm[1]] * if s & 2 == 2 { -1.0 } else { 1.0 },
                    r[perm[2]] * if s & 4 == 4 { -1.0 } else { 1.0 },
                ];
                if p[0] * p[0] + p[1] * p[1] + p[2] * p[2] == 441.0 && !out.contains(&p) {
                    out.push(p);
                }
            }
        }
    }
    out
}

pub fn orient_case(r: &mut Rng, adversarial: bool) -> [P3; 4] {
    if !adversarial {
        return [r.point(), r.point(), r.point(), r.point()];
    }
    let s = domain_scale(r);
    let (a, b, c) = (r.point(), r.point(), r.point());
    let d = match r.int(4) {
        0 => {
            // on the plane abc up to rounding, then a few ulps off
            let (u, v) = (r.unit(), r.unit());
            let mut d = [0.0; 3];
            for k in 0..3 {
                d[k] = nudge(a[k] + u * (b[k] - a[k]) + v * (c[k] - a[k]), r.int(5) - 2);
            }
            d
        }
        1 => {
            // exactly coplanar dyadic points on the tilted plane x + 2y - z = 0
            let q = |r: &mut Rng| {
                let (x, y) = (r.int(64) as f64 / 8.0, r.int(64) as f64 / 8.0);
                scale([x, y, x + 2.0 * y], s)
            };
            return [q(r), q(r), q(r), q(r)];
        }
        2 => {
            // collinear-ish: d on the line ab
            let t = r.unit();
            [a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]), a[2] + t * (b[2] - a[2])]
        }
        _ => {
            // tiny tetrahedron far from the origin
            let o = [1.0e3, -2.0e3, 0.5e3];
            return [o, [nudge(o[0], 1), o[1], o[2]], [o[0], nudge(o[1], 1), o[2]],
                    [o[0], o[1], nudge(o[2], r.int(3) - 1)]].map(|p| scale(p, s));
        }
    };
    [a, b, c, d].map(|p| scale(p, s))
}

pub fn insphere_case(r: &mut Rng, adversarial: bool, sphere: &[P3]) -> [P3; 5] {
    if !adversarial {
        return [r.point(), r.point(), r.point(), r.point(), r.point()];
    }
    let s = domain_scale(r);
    let pick = |r: &mut Rng| sphere[r.int(sphere.len() as u64) as usize];
    let mut p = [pick(r), pick(r), pick(r), pick(r), pick(r)];
    match r.int(3) {
        0 => {}
        1 => {
            let k = r.int(5) as usize;
            let c = r.int(3) as usize;
            p[k][c] = nudge(p[k][c], if r.int(2) == 0 { 1 } else { -1 });
        }
        _ => {
            // box corners: cospherical, often coplanar
            let c = |r: &mut Rng| [r.int(2) as f64, r.int(2) as f64 * 0.5, r.int(2) as f64 * 0.25];
            p = [c(r), c(r), c(r), c(r), c(r)];
        }
    }
    p.map(|q| scale(q, s))
}

pub fn incircle_case(r: &mut Rng, adversarial: bool) -> [P3; 4] {
    // a conformal integer embedding of the plane: e1 = (1, 2, 2), e2 = (2, 1, -2)
    let o = [r.int(16) as f64, r.int(16) as f64, r.int(16) as f64];
    let embed = |x: f64, y: f64| [o[0] + x + 2.0 * y, o[1] + 2.0 * x + y, o[2] + 2.0 * x - 2.0 * y];
    let s = domain_scale(r);
    if !adversarial {
        let q = |r: &mut Rng| embed((r.int(1 << 20) as f64) / 1024.0, (r.int(1 << 20) as f64) / 1024.0);
        return [q(r), q(r), q(r), q(r)].map(|p| scale(p, s));
    }
    // cocircular: (+-5, 0), (0, +-5), (+-3, +-4), (+-4, +-3), sometimes one ulp off
    let circle = [[5.0, 0.0], [-5.0, 0.0], [0.0, 5.0], [0.0, -5.0], [3.0, 4.0], [-3.0, 4.0], [3.0, -4.0],
                  [-3.0, -4.0], [4.0, 3.0], [-4.0, 3.0], [4.0, -3.0], [-4.0, -3.0]];
    let mut p = [0usize; 4].map(|_| {
        let c = circle[r.int(12) as usize];
        embed(c[0], c[1])
    });
    if r.int(2) == 0 {
        let k = r.int(4) as usize;
        let c = r.int(3) as usize;
        p[3 - k % 4][c] = nudge(p[3 - k % 4][c], 1);
    }
    p.map(|q| scale(q, s))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn distinct(p: &[P3]) -> bool {
        (0..p.len()).all(|i| (i + 1..p.len()).all(|j| !pr::same_point(&p[i], &p[j])))
    }

    fn run(random: usize, adversarial: usize, seed: u64) {
        let mut r = Rng(seed);
        let sphere = sphere_points();
        assert!(sphere.len() >= 40);
        let mut n = Counters::default();
        let mut zeros = [0usize; 4];
        for k in 0..random + adversarial {
            let adv = k >= random;
            let p = orient_case(&mut r, adv);
            assert!(p.iter().flatten().all(|x| pr::in_domain(*x)));
            let s = pr::orient3d(&p[0], &p[1], &p[2], &p[3], &mut n);
            assert_eq!(s, orient3d(&p), "orient3d {p:?}");
            zeros[0] += (s == 0) as usize;

            let q = insphere_case(&mut r, adv, &sphere);
            let s = pr::insphere(&q[0], &q[1], &q[2], &q[3], &q[4], &mut n);
            assert_eq!(s, insphere(&q), "insphere {q:?}");
            zeros[1] += (s == 0) as usize;
            if distinct(&q) && orient3d(&[q[0], q[1], q[2], q[3]]) != 0 {
                let ids = [r.int(1000) as u32, 0, 0, 0, 0];
                let mut ids = ids;
                for i in 1..5 {
                    ids[i] = ids[i - 1] + 1 + r.int(5) as u32;
                }
                // shuffle the ids over the rows
                for i in (1..5).rev() {
                    let j = r.int(i as u64 + 1) as usize;
                    ids.swap(i, j);
                }
                let so = pr::insphere_sos([&q[0], &q[1], &q[2], &q[3], &q[4]], ids, &mut n);
                assert_ne!(so, 0);
                assert_eq!(so, insphere_sos(&q, ids), "insphere_sos {q:?} {ids:?}");
                zeros[2] += (s == 0) as usize;
            }

            let c = incircle_case(&mut r, adv);
            let s = pr::incircle3d(&c[0], &c[1], &c[2], &c[3]);
            assert_eq!(s, incircle3d(&c), "incircle3d {c:?}");
            zeros[3] += (s == 0) as usize;
        }
        // the adversarial half must actually reach the degenerate cases
        if adversarial > 0 {
            assert!(zeros.iter().all(|&z| z > adversarial / 50), "{zeros:?}");
        }
    }

    /// Coplanar cases on the conformal integer embedding: the in-plane predicates
    /// against big integers, and the 2D perturbation against the 3D one (a coplanar
    /// point is inside the perturbed circle of a, b, c exactly when it is inside the
    /// perturbed sphere of a, b, c and any point off the plane).
    fn run_plane(cases: usize, seed: u64) {
        let mut r = Rng(seed);
        let mut n = Counters::default();
        let mut ties = 0;
        for k in 0..cases {
            let c = incircle_case(&mut r, k % 2 == 1);
            let normal = pr::normal_signs(&c[0], &c[1], &c[2]);
            for axis in 0..3 {
                assert_eq!(pr::orient2d_proj(axis, &c[0], &c[1], &c[2]), orient2d_proj(axis, &[c[0], c[1], c[2]]));
                assert_eq!(normal[axis], orient2d_proj(axis, &[c[0], c[1], c[2]]));
                if normal[axis] == 0 {
                    continue;
                }
                assert_eq!(pr::incircle_plane(axis, &c[0], &c[1], &c[2], &c[3]), incircle_plane(axis, &c), "{c:?}");
                if !distinct(&c) {
                    continue;
                }
                let ids = [r.int(50) as u32, 50 + r.int(50) as u32, 100 + r.int(50) as u32, 150 + r.int(50) as u32];
                let mut ids = ids;
                for i in (1..4).rev() {
                    let j = r.int(i as u64 + 1) as usize;
                    ids.swap(i, j);
                }
                let s2 = pr::incircle_plane_sos(axis, [&c[0], &c[1], &c[2], &c[3]], ids);
                // the 1-ulp nudges leave some cases off the plane: the in-plane meaning
                // (and the 2D-3D agreement) holds for exactly coplanar points only
                let coplanar = pr::orient3d(&c[0], &c[1], &c[2], &c[3], &mut n) == 0;
                if coplanar && pr::orient2d_proj(axis, &c[0], &c[1], &c[2]) != 0 {
                    assert_ne!(s2, 0);
                    assert_eq!(s2, incircle_plane_sos(axis, &c, ids), "{c:?} {ids:?}");
                    ties += (pr::incircle_plane(axis, &c[0], &c[1], &c[2], &c[3]) == 0) as usize;
                    // the same decision from the 3D perturbation, with an off-plane point
                    let (mut t, mut ti) = ([c[0], c[1], c[2]], [ids[0], ids[1], ids[2]]);
                    if pr::orient2d_proj(axis, &t[0], &t[1], &t[2]) < 0 {
                        t.swap(1, 2);
                        ti.swap(1, 2);
                    }
                    let inside2 = pr::incircle_plane_sos(axis, [&t[0], &t[1], &t[2], &c[3]], [ti[0], ti[1], ti[2], ids[3]]) > 0;
                    for (off, xid) in [(1.0, 1000), (-1.0, 1000), (1.0, 0), (-3.0, 7)] {
                        let mut x = t[0];
                        x[(axis + 1) % 3] += off;
                        x[axis] += 2.0 * off;
                        let (mut u, mut ui) = (t, ti);
                        let o = pr::orient3d(&u[0], &u[1], &u[2], &x, &mut n);
                        if o == 0 {
                            continue;
                        }
                        if o < 0 {
                            u.swap(1, 2);
                            ui.swap(1, 2);
                        }
                        let inside3 = pr::insphere_sos([&u[0], &u[1], &u[2], &x, &c[3]], [ui[0], ui[1], ui[2], xid, ids[3]], &mut n) > 0;
                        assert_eq!(inside2, inside3, "{c:?} {ids:?} x={x:?}");
                    }
                }
            }
        }
        assert!(ties > cases / 10, "{ties}");
    }

    #[test]
    fn in_plane_predicates_agree_with_exact_integers_and_the_3d_perturbation() {
        run_plane(4_000, 26);
    }

    /// V16 in CI: 10^4 random and 10^4 adversarial cases per predicate.
    #[test]
    fn v16_predicates_agree_with_exact_integers() {
        let n = std::env::var("V16_N").ok().and_then(|s| s.parse().ok()).unwrap_or(10_000);
        run(n, n, 16);
    }

    /// V16 outside CI: 10^6 random and 10^5 adversarial cases per predicate
    /// (`cargo test --release -- --ignored`).
    #[test]
    #[ignore]
    fn v16_predicates_agree_with_exact_integers_large() {
        run(1_000_000, 100_000, 1016);
    }
}

// ---------------------------------------------------------------- mixed points (M4)

/// A point of a mixed case for the reference: an input point, or the S point
/// a + t (b - a) of a segment, given by its doubles.
#[derive(Clone, Copy, Debug)]
pub enum RefPt {
    In(P3),
    S(P3, P3, f64),
}

/// A term of a coordinate as (mantissa, exponent, negative): a double, or the product
/// of two doubles. None for zero.
fn term(x: f64, y: Option<f64>) -> Option<(u128, i32, bool)> {
    if x == 0.0 || y == Some(0.0) {
        return None;
    }
    let (mx, ex, nx) = decompose(x);
    Some(match y {
        None => (mx as u128, ex, nx),
        Some(y) => {
            let (my, ey, ny) = decompose(y);
            (mx as u128 * my as u128, ex + ey, nx != ny)
        }
    })
}

fn big_u128(m: u128, shift: u32, neg: bool) -> Big {
    Big::from_u64_shl(m as u64, shift, neg).add(&Big::from_u64_shl((m >> 64) as u64, shift + 64, neg))
}

/// The coordinates of a mixed case as integers on one common scale 2^e0: an S
/// coordinate is a_k + t b_k - t a_k, three terms whose smallest exponent sets e0.
fn mixed_integers(pts: &[RefPt]) -> Vec<[Big; 3]> {
    let terms: Vec<[Vec<(u128, i32, bool)>; 3]> = pts.iter().map(|p| std::array::from_fn(|k| match p {
        RefPt::In(x) => term(x[k], None).into_iter().collect(),
        RefPt::S(a, b, t) => [term(a[k], None), term(*t, Some(b[k])), term(*t, Some(a[k])).map(|(m, e, n)| (m, e, !n))]
            .into_iter().flatten().collect(),
    })).collect();
    let e0 = terms.iter().flatten().flatten().map(|t| t.1).min().unwrap_or(0);
    terms.iter().map(|c| std::array::from_fn(|k| {
        c[k].iter().fold(Big::zero(), |acc, &(m, e, neg)| acc.add(&big_u128(m, (e - e0) as u32, neg)))
    })).collect()
}

pub fn orient3d_mixed(p: &[RefPt; 4]) -> i8 {
    orient3d_q(&mixed_integers(p))
}

pub fn insphere_mixed(p: &[RefPt; 5]) -> i8 {
    insphere_q(&mixed_integers(p))
}

pub fn insphere_sos_mixed(p: &[RefPt; 5], ids: [u32; 5]) -> i8 {
    insphere_sos_q(&mixed_integers(p), ids)
}

pub fn orient2d_proj_mixed(axis: usize, p: &[RefPt; 3]) -> i8 {
    orient2d_proj_q(axis, &mixed_integers(p))
}

pub fn incircle_plane_mixed(axis: usize, p: &[RefPt; 4]) -> i8 {
    incircle_plane_q(axis, &mixed_integers(p))
}

pub fn incircle_plane_sos_mixed(axis: usize, p: &[RefPt; 4], ids: [u32; 4]) -> i8 {
    incircle_plane_sos_q(axis, &mixed_integers(p), ids)
}

/// Exactly equal points of a mixed case (by their integers on the common scale).
pub fn mixed_distinct(p: &[RefPt]) -> bool {
    let q = mixed_integers(p);
    (0..q.len()).all(|i| (i + 1..q.len()).all(|j| q[i] != q[j]))
}

#[cfg(test)]
mod mixed_tests {
    use super::*;
    use crate::mixed::{Mixed, MixedCounters, Pt, SPoint};

    /// A mixed case: the input points, the S table and the query, plus the same query
    /// for the reference.
    struct Case {
        input: Vec<P3>,
        s: Vec<SPoint>,
        query: Vec<Pt>,
        refs: Vec<RefPt>,
    }

    impl Case {
        fn new() -> Case {
            Case { input: Vec::new(), s: Vec::new(), query: Vec::new(), refs: Vec::new() }
        }

        fn input(&mut self, x: P3) -> u32 {
            self.input.push(x);
            self.input.len() as u32 - 1
        }

        fn push_in(&mut self, x: P3) {
            let i = self.input(x);
            self.query.push(Pt::In(i));
            self.refs.push(RefPt::In(x));
        }

        fn push_s(&mut self, a: P3, b: P3, t: f64) {
            let (ia, ib) = (self.input(a), self.input(b));
            self.s.push(SPoint::seg(ia, ib, t));
            self.query.push(Pt::S(self.s.len() as u32 - 1));
            self.refs.push(RefPt::S(a, b, t));
        }

        fn mixed(&self) -> Mixed<'_> {
            Mixed { input: &self.input, s: &self.s }
        }

        fn ids<const N: usize>(&self) -> [u32; N] {
            let m = self.mixed();
            std::array::from_fn(|k| m.id(self.query[k]))
        }

        fn q<const N: usize>(&self) -> [Pt; N] {
            std::array::from_fn(|k| self.query[k])
        }

        fn r<const N: usize>(&self) -> [RefPt; N] {
            std::array::from_fn(|k| self.refs[k])
        }
    }

    fn t_of(r: &mut Rng) -> f64 {
        match r.int(5) {
            0 => 2f64.powi(-(1 + r.int(50) as i32)),                     // close to a
            1 => 1.0 - 2f64.powi(-(1 + r.int(52) as i32)),               // close to b
            2 => (1 + r.int(15)) as f64 / 16.0,                          // dyadic
            _ => r.unit().clamp(f64::MIN_POSITIVE, 1.0 - f64::EPSILON),  // any double
        }
    }

    /// Positions for a predicate on N points (`kind`: 0 orient3d, 1 insphere, 2 plane),
    /// each turned into an input point or an S point near or exactly at it.
    fn case(r: &mut Rng, adversarial: bool, n: usize, kind: usize, sphere: &[P3]) -> Case {
        let s = domain_scale(r);
        let mut c = Case::new();
        if !adversarial {
            for _ in 0..n {
                if r.int(2) == 0 {
                    c.push_in(r.point());
                } else {
                    let (a, b) = (r.point(), r.point());
                    c.push_s(a, b, t_of(r));
                }
            }
            return c;
        }
        // the exact position of each point, and how an S point reaches it exactly:
        // integer offsets d with a = x - d, b = x + 3d and t = 1/4, or x -+ d and 1/2
        let embed = |x: f64, y: f64| [x + 2.0 * y, 2.0 * x + y, 2.0 * x - 2.0 * y];
        let pos: Vec<P3> = match kind {
            0 => match r.int(3) {
                // exactly coplanar lattice points on the tilted plane x + 2y - z = 0
                0 | 1 => (0..n).map(|_| {
                    let (x, y) = (r.int(64) as f64, r.int(64) as f64);
                    [x, y, x + 2.0 * y]
                }).collect(),
                // a tiny tetrahedron far from the origin
                _ => {
                    let o = [1.0e3, -2.0e3, 0.5e3];
                    vec![o, [nudge(o[0], 1), o[1], o[2]], [o[0], nudge(o[1], 1), o[2]],
                         [o[0], o[1], nudge(o[2], r.int(3) - 1)]][..n].to_vec()
                }
            },
            1 => {
                let pick = |r: &mut Rng| sphere[r.int(sphere.len() as u64) as usize];
                (0..n).map(|_| pick(r)).collect()
            }
            _ => {
                let circle = [[5.0, 0.0], [-5.0, 0.0], [0.0, 5.0], [0.0, -5.0], [3.0, 4.0], [-3.0, 4.0],
                              [3.0, -4.0], [-3.0, -4.0], [4.0, 3.0], [-4.0, 3.0], [4.0, -3.0], [-4.0, -3.0]];
                (0..n).map(|_| {
                    let q = circle[r.int(12) as usize];
                    embed(q[0], q[1])
                }).collect()
            }
        };
        let far = pos.iter().flatten().any(|x| x.abs() >= 1.0e3);
        for (k, x) in pos.iter().enumerate() {
            if r.int(3) == 0 {
                c.push_in(scale(*x, s));
                continue;
            }
            // a direction that keeps the S point's segment in the case's plane, if any
            let d = match kind {
                0 if !far => {
                    let (u, v) = (r.int(5) as f64 - 2.0, r.int(5) as f64 - 2.0 + 0.5);
                    [u, v, u + 2.0 * v]
                }
                2 => {
                    let (u, v) = (r.int(5) as f64 - 2.0, r.int(5) as f64 - 2.0 + 0.5);
                    embed(u, v)
                }
                _ => [1.0 + r.int(3) as f64, -2.0, 3.0],
            };
            let (mut a, mut b, t) = if far {
                // segment through a far point: exact when the ends are, near-degenerate
                ([x[0] - 1.0, x[1], x[2]], [x[0] + 1.0, x[1], x[2]], 0.5)
            } else if r.int(2) == 0 {
                ([x[0] - d[0], x[1] - d[1], x[2] - d[2]], [x[0] + d[0], x[1] + d[1], x[2] + d[2]], 0.5)
            } else {
                ([x[0] - d[0], x[1] - d[1], x[2] - d[2]], [x[0] + 3.0 * d[0], x[1] + 3.0 * d[1], x[2] + 3.0 * d[2]], 0.25)
            };
            if r.int(4) == 0 {
                // one end a few ulps off: the S point leaves the plane or sphere by a tiny amount
                let j = r.int(3) as usize;
                if r.int(2) == 0 {
                    a[j] = nudge(a[j], r.int(5) - 2);
                } else {
                    b[j] = nudge(b[j], r.int(5) - 2);
                }
            }
            let t = if r.int(5) == 0 && k % 2 == 0 { t_of(r) } else { t };
            c.push_s(scale(a, s), scale(b, s), t);
        }
        c
    }

    #[derive(Default, Debug)]
    struct Tally {
        zeros: [usize; 4],
        sos: usize,
        exact_double_checks: usize,
        n: MixedCounters,
    }

    fn run_mixed(random: usize, adversarial: usize, seed: u64) -> Tally {
        let mut r = Rng(seed);
        let sphere = sphere_points();
        let mut t = Tally::default();
        for k in 0..random + adversarial {
            let adv = k >= random;

            // orient3d
            let c = case(&mut r, adv, 4, 0, &sphere);
            let m = c.mixed();
            crate::mixed::check_spoints(&c.input, &c.s).unwrap();
            let s = m.orient3d(c.q(), &mut t.n);
            assert_eq!(s, orient3d_mixed(&c.r()), "orient3d {:?} {:?}", c.refs, c.s);
            t.zeros[0] += (s == 0) as usize;

            // insphere, and the perturbed one on distinct points with a proper tetrahedron
            let c = case(&mut r, adv, 5, 1, &sphere);
            let m = c.mixed();
            let s = m.insphere(c.q(), &mut t.n);
            assert_eq!(s, insphere_mixed(&c.r()), "insphere {:?}", c.refs);
            t.zeros[1] += (s == 0) as usize;
            let r4: [RefPt; 4] = std::array::from_fn(|i| c.refs[i]);
            if mixed_distinct(&c.refs) && orient3d_mixed(&r4) != 0 {
                let so = m.insphere_sos(c.q(), &mut t.n);
                assert_ne!(so, 0);
                assert_eq!(so, insphere_sos_mixed(&c.r(), c.ids()), "insphere_sos {:?}", c.refs);
                t.sos += (s == 0) as usize;
            }

            // in-plane predicates on every axis whose normal component is nonzero
            let c = case(&mut r, adv, 4, 2, &sphere);
            let m = c.mixed();
            let r3: [RefPt; 3] = std::array::from_fn(|i| c.refs[i]);
            let coplanar = orient3d_mixed(&c.r()) == 0;
            for axis in 0..3 {
                let o = m.orient2d_proj(axis, std::array::from_fn(|i| c.query[i]), &mut t.n);
                assert_eq!(o, orient2d_proj_mixed(axis, &r3), "orient2d_proj {:?}", c.refs);
                t.zeros[2] += (o == 0) as usize;
                if o == 0 {
                    continue;
                }
                let s = m.incircle_plane(axis, c.q(), &mut t.n);
                assert_eq!(s, incircle_plane_mixed(axis, &c.r()), "incircle_plane {:?}", c.refs);
                t.zeros[3] += (s == 0) as usize;
                if coplanar && mixed_distinct(&c.refs) {
                    let so = m.incircle_plane_sos(axis, c.q(), &mut t.n);
                    assert_ne!(so, 0);
                    assert_eq!(so, incircle_plane_sos_mixed(axis, &c.r(), c.ids()), "incircle_plane_sos {:?}", c.refs);
                }
            }

            // S points whose exact coordinates are doubles agree with the input-point
            // predicates on those doubles (an independent check: expansions, M3)
            if adv {
                let c = case(&mut r, true, 5, 1, &sphere);
                let m = c.mixed();
                // a rounded point is exact when it equals the S point on a common scale
                let exact: Vec<Option<P3>> = c.query.iter().zip(&c.refs).map(|(&p, rp)| {
                    let x = m.rounded(p);
                    let both = mixed_integers(&[RefPt::In(x), *rp]);
                    (both[0] == both[1]).then_some(x)
                }).collect();
                if exact.iter().all(|x| x.is_some()) {
                    let x: Vec<P3> = exact.into_iter().map(|x| x.unwrap()).collect();
                    let mut n = Counters::default();
                    assert_eq!(m.orient3d([c.query[0], c.query[1], c.query[2], c.query[3]], &mut t.n),
                               pr::orient3d(&x[0], &x[1], &x[2], &x[3], &mut n));
                    assert_eq!(m.insphere(c.q(), &mut t.n), pr::insphere(&x[0], &x[1], &x[2], &x[3], &x[4], &mut n));
                    let distinct = (0..5).all(|i| (i + 1..5).all(|j| !pr::same_point(&x[i], &x[j])));
                    if distinct && pr::orient3d(&x[0], &x[1], &x[2], &x[3], &mut n) != 0 {
                        assert_eq!(m.insphere_sos(c.q(), &mut t.n),
                                   pr::insphere_sos([&x[0], &x[1], &x[2], &x[3], &x[4]], c.ids(), &mut n));
                    }
                    t.exact_double_checks += 1;
                }
            }
        }
        t
    }

    /// V16 for mixed points in CI: 10^4 random and 10^4 adversarial cases per predicate.
    #[test]
    fn v16_mixed_predicates_agree_with_exact_integers() {
        let n = std::env::var("V16_N").ok().and_then(|s| s.parse().ok()).unwrap_or(10_000);
        let t = run_mixed(n, n, 216);
        eprintln!("{t:?}");
        // the adversarial half reaches the degenerate cases and the exact path
        assert!(t.zeros.iter().all(|&z| z > n / 50), "{t:?}");
        assert!(t.sos > n / 50 && t.exact_double_checks > n / 10, "{t:?}");
        assert!(t.n.exact > (n / 20) as u64, "{t:?}");
    }

    /// V16 for mixed points outside CI: 10^6 random and 10^5 adversarial cases.
    #[test]
    #[ignore]
    fn v16_mixed_predicates_agree_with_exact_integers_large() {
        let t = run_mixed(1_000_000, 100_000, 1216);
        eprintln!("{t:?}");
    }

    #[test]
    fn rounded_s_points_are_the_nearest_doubles_and_bad_tables_are_refused() {
        let input = [[0.0, 0.0, 0.0], [1.0, 3.0, 0.1]];
        let s = [SPoint::seg(0, 1, 1.0 / 3.0)];
        let m = Mixed { input: &input, s: &s };
        let x = m.rounded(Pt::S(0));
        // a is the origin, so the exact point is t * b: one correctly rounded product
        // per coordinate is the nearest double
        let want: Vec<f64> = (0..3).map(|k| (1.0 / 3.0) * input[1][k]).collect();
        assert_eq!(x.to_vec(), want);
        // a sum that rounds: the nearest double of a + t (b - a), against the reference
        let input2 = [[1.0, -0.1, 7.0], [3.0, 0.3, -2.0]];
        let s2 = [SPoint::seg(0, 1, 0.1)];
        let m2 = Mixed { input: &input2, s: &s2 };
        let y = m2.rounded(Pt::S(0));
        for k in 0..3 {
            // |exact - y| <= half an ulp of y: compare against the neighbours
            for nb in [y[k].next_up(), y[k].next_down()] {
                let mut z = y;
                z[k] = nb;
                let qz = mixed_integers(&[RefPt::S(input2[0], input2[1], 0.1), RefPt::In(y), RefPt::In(z)]);
                let d_y = qz[0][k].sub(&qz[1][k]);
                let d_z = qz[0][k].sub(&qz[2][k]);
                let mag = |b: &Big| if b.sign() < 0 { b.neg() } else { b.clone() };
                assert!(mag(&d_y).sub(&mag(&d_z)).sign() <= 0, "coordinate {k} is not the nearest double");
            }
        }

        assert_eq!(m.id(Pt::S(0)), 2);
        assert_eq!(m.from_id(2), Pt::S(0));
        assert!(crate::mixed::check_spoints(&input, &[SPoint::seg(0, 0, 0.5)]).is_err());
        assert!(crate::mixed::check_spoints(&input, &[SPoint::seg(0, 1, 1.0)]).is_err());
        assert!(crate::mixed::check_spoints(&input, &[SPoint::seg(0, 2, 0.5)]).is_err());
        assert!(crate::mixed::check_spoints(&input, &[SPoint::seg(0, 1, f64::NAN)]).is_err());
    }
}
