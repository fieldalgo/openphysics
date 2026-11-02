// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

//! Test-only reference for V16: the predicates recomputed with big integers. Each
//! case's doubles are written exactly as integers times one common power of two, and
//! every determinant is expanded by cofactors in integer arithmetic. It shares no
//! code with the expansion arithmetic it checks. The perturbed insphere is checked
//! through the full 5 x 5 lifted determinant with an explicit, small enough
//! perturbation, not through the cofactor rule the kernel uses.

use crate::predicates::{self as pr, Counters, P3};
use std::cmp::Ordering;

#[derive(Clone, Debug, PartialEq, Eq)]
struct Big {
    neg: bool,
    mag: Vec<u32>, // little-endian, no trailing zeros; empty = 0
}

fn trim(v: &mut Vec<u32>) {
    while v.last() == Some(&0) {
        v.pop();
    }
}

fn cmp_mag(a: &[u32], b: &[u32]) -> Ordering {
    a.len().cmp(&b.len()).then_with(|| a.iter().rev().cmp(b.iter().rev()))
}

fn add_mag(a: &[u32], b: &[u32]) -> Vec<u32> {
    let mut r = Vec::with_capacity(a.len().max(b.len()) + 1);
    let mut carry = 0u64;
    for i in 0..a.len().max(b.len()) {
        let s = *a.get(i).unwrap_or(&0) as u64 + *b.get(i).unwrap_or(&0) as u64 + carry;
        r.push(s as u32);
        carry = s >> 32;
    }
    r.push(carry as u32);
    trim(&mut r);
    r
}

fn sub_mag(a: &[u32], b: &[u32]) -> Vec<u32> {
    // |a| >= |b|
    let mut r = Vec::with_capacity(a.len());
    let mut borrow = 0i64;
    for i in 0..a.len() {
        let mut s = a[i] as i64 - *b.get(i).unwrap_or(&0) as i64 - borrow;
        borrow = 0;
        if s < 0 {
            s += 1 << 32;
            borrow = 1;
        }
        r.push(s as u32);
    }
    trim(&mut r);
    r
}

impl Big {
    fn zero() -> Big {
        Big { neg: false, mag: Vec::new() }
    }

    fn sign(&self) -> i8 {
        if self.mag.is_empty() { 0 } else if self.neg { -1 } else { 1 }
    }

    fn from_u64_shl(m: u64, shift: u32, neg: bool) -> Big {
        let mut mag = vec![0u32; (shift / 32) as usize];
        let s = shift % 32;
        let wide = (m as u128) << s;
        for k in 0..4 {
            mag.push((wide >> (32 * k)) as u32);
        }
        trim(&mut mag);
        Big { neg: neg && !mag.is_empty(), mag }
    }

    fn add(&self, o: &Big) -> Big {
        if self.neg == o.neg {
            let mag = add_mag(&self.mag, &o.mag);
            return Big { neg: self.neg && !mag.is_empty(), mag };
        }
        match cmp_mag(&self.mag, &o.mag) {
            Ordering::Equal => Big::zero(),
            Ordering::Greater => Big { neg: self.neg, mag: sub_mag(&self.mag, &o.mag) },
            Ordering::Less => Big { neg: o.neg, mag: sub_mag(&o.mag, &self.mag) },
        }
    }

    fn neg(&self) -> Big {
        Big { neg: !self.neg && !self.mag.is_empty(), mag: self.mag.clone() }
    }

    fn sub(&self, o: &Big) -> Big {
        self.add(&o.neg())
    }

    fn mul(&self, o: &Big) -> Big {
        if self.mag.is_empty() || o.mag.is_empty() {
            return Big::zero();
        }
        let mut r = vec![0u32; self.mag.len() + o.mag.len()];
        for (i, &a) in self.mag.iter().enumerate() {
            let mut carry = 0u64;
            for (j, &b) in o.mag.iter().enumerate() {
                let t = r[i + j] as u64 + a as u64 * b as u64 + carry;
                r[i + j] = t as u32;
                carry = t >> 32;
            }
            let mut k = i + o.mag.len();
            while carry != 0 {
                let t = r[k] as u64 + carry;
                r[k] = t as u32;
                carry = t >> 32;
                k += 1;
            }
        }
        trim(&mut r);
        Big { neg: self.neg != o.neg, mag: r }
    }

    fn bits(&self) -> u32 {
        match self.mag.last() {
            None => 0,
            Some(&top) => 32 * (self.mag.len() as u32 - 1) + (32 - top.leading_zeros()),
        }
    }

    fn pow2(k: u32) -> Big {
        Big::from_u64_shl(1, k, false)
    }
}

/// (odd integer mantissa, exponent of its unit, sign) with |x| = m * 2^e, for x != 0.
fn decompose(x: f64) -> (u64, i32, bool) {
    let bits = x.to_bits();
    let neg = bits >> 63 == 1;
    let exp = ((bits >> 52) & 0x7ff) as i32;
    let frac = bits & ((1u64 << 52) - 1);
    let (m, e) = if exp == 0 { (frac, -1074) } else { (frac | (1u64 << 52), exp - 1075) };
    let tz = m.trailing_zeros();
    (m >> tz, e + tz as i32, neg)
}

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
    let q = integers(p);
    let rows = vec![sub3(&q[1], &q[0]).to_vec(), sub3(&q[2], &q[0]).to_vec(), sub3(&q[3], &q[0]).to_vec()];
    det(&rows).sign()
}

pub fn insphere(p: &[P3; 5]) -> i8 {
    let q = integers(p);
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
    let q = integers(p);
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
