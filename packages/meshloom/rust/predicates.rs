// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

//! Exact geometric predicates on IEEE doubles.
//!
//! Each predicate first evaluates its determinant in doubles and accepts the sign
//! when it exceeds the static error bound of Shewchuk (1997, stage A). Otherwise it
//! evaluates the determinant exactly with floating-point expansions (two-sum,
//! Dekker two-product without FMA, expansion sum and scaling with zero
//! elimination; Shewchuk 1997, section 2). Exactness needs every coordinate in
//! [`in_domain`]; callers check that once per input.
//!
//! Sign conventions:
//! * `orient3d(a, b, c, d) = det[b - a, c - a, d - a]`, positive for a positively
//!   oriented tetrahedron;
//! * `insphere(a, b, c, d, e) > 0` when e is strictly inside the sphere through
//!   a, b, c, d and `orient3d(a, b, c, d) > 0` (the sign flips with the orientation);
//! * `incircle3d(a, b, c, d) > 0` for coplanar points when d is strictly inside the
//!   circle through a, b, c (no projection: circles are not kept by projections).

use std::cmp::Ordering;
use std::hint::black_box;

pub type P3 = [f64; 3];

/// Coordinates with |x| in [2^-120, 2^120] or zero keep every exact evaluation free
/// of underflow and overflow: products have degree at most 6 and every component is
/// a multiple of 2^(6 L) with L >= -172, and every Dekker split stays below 2^996.
pub const DOMAIN_MIN: f64 = 7.523163845262640e-37; // 2^-120
pub const DOMAIN_MAX: f64 = 1.329227995784916e36; // 2^120

pub fn in_domain(x: f64) -> bool {
    x == 0.0 || (x.abs() >= DOMAIN_MIN && x.abs() <= DOMAIN_MAX)
}

/// The arithmetic the predicates assume: round to nearest even, gradual underflow
/// (no flush-to-zero or denormals-are-zero). Another extension in the process can
/// change the FP state, so the kernel probes it at every entry.
pub fn fp_environment_ok() -> bool {
    let one = black_box(1.0f64);
    let e = black_box(f64::EPSILON); // 2^-52
    let tiny = black_box(f64::from_bits(1)); // smallest subnormal
    let subnormals = tiny * one != 0.0 && black_box(f64::MIN_POSITIVE) / black_box(2.0) != 0.0;
    let nearest = one + e * 0.5 == one && one + e * 0.75 == one + e && -one - e * 0.75 == -one - e
        && one + e * 0.25 == one;
    let (p, err) = two_product(black_box(1.0 + f64::EPSILON), black_box(1.0 + f64::EPSILON));
    let dekker = p == 1.0 + 2.0 * f64::EPSILON && err == f64::EPSILON * f64::EPSILON;
    subnormals && nearest && dekker
}

// ---------------------------------------------------------------- error-free transforms

#[inline(always)]
fn two_sum(a: f64, b: f64) -> (f64, f64) {
    let x = a + b;
    let bv = x - a;
    let av = x - bv;
    (x, (a - av) + (b - bv))
}

#[inline(always)]
fn fast_two_sum(a: f64, b: f64) -> (f64, f64) {
    // |a| >= |b| or a == 0
    let x = a + b;
    (x, b - (x - a))
}

#[inline(always)]
fn two_diff(a: f64, b: f64) -> (f64, f64) {
    let x = a - b;
    let bv = a - x;
    let av = x + bv;
    (x, (a - av) + (bv - b))
}

/// p = fl(a*b), a*b = p + e exactly (Dekker splitting, no FMA).
#[inline(always)]
pub fn two_product(a: f64, b: f64) -> (f64, f64) {
    const SPLITTER: f64 = 134_217_729.0; // 2^27 + 1
    let p = a * b;
    let split = |x: f64| {
        let c = SPLITTER * x;
        let hi = c - (c - x);
        (hi, x - hi)
    };
    let (ah, al) = split(a);
    let (bh, bl) = split(b);
    let e = ((ah * bh - p) + ah * bl + al * bh) + al * bl;
    (p, e)
}

// ---------------------------------------------------------------- expansions

/// A nonoverlapping expansion, components in increasing magnitude, zero-free except
/// that the zero expansion is `[0.0]`.
#[derive(Clone, Debug)]
pub struct Expansion(Vec<f64>);

impl Expansion {
    fn diff(a: f64, b: f64) -> Self {
        let (x, y) = two_diff(a, b);
        if y != 0.0 { Expansion(vec![y, x]) } else { Expansion(vec![x]) }
    }

    /// Sign of the value: the sign of the largest component.
    pub fn sign(&self) -> i8 {
        let top = *self.0.last().unwrap();
        if top > 0.0 { 1 } else if top < 0.0 { -1 } else { 0 }
    }

    fn neg(&self) -> Self {
        Expansion(self.0.iter().map(|x| -x).collect())
    }

    /// fast_expansion_sum_zeroelim (Shewchuk 1997, Fig. 8 with zero elimination).
    fn add(&self, f: &Expansion) -> Self {
        let e = &self.0;
        let f = &f.0;
        let mut h = Vec::with_capacity(e.len() + f.len());
        let (mut ei, mut fi) = (0usize, 0usize);
        let mut enow = e[0];
        let mut fnow = f[0];
        let mut q;
        if (fnow > enow) == (fnow > -enow) {
            q = enow;
            ei += 1;
            enow = if ei < e.len() { e[ei] } else { 0.0 };
        } else {
            q = fnow;
            fi += 1;
            fnow = if fi < f.len() { f[fi] } else { 0.0 };
        }
        if ei < e.len() && fi < f.len() {
            let (qn, hh) = if (fnow > enow) == (fnow > -enow) {
                let r = fast_two_sum(enow, q);
                ei += 1;
                enow = if ei < e.len() { e[ei] } else { 0.0 };
                r
            } else {
                let r = fast_two_sum(fnow, q);
                fi += 1;
                fnow = if fi < f.len() { f[fi] } else { 0.0 };
                r
            };
            q = qn;
            if hh != 0.0 {
                h.push(hh);
            }
            while ei < e.len() && fi < f.len() {
                let (qn, hh) = if (fnow > enow) == (fnow > -enow) {
                    let r = two_sum(q, enow);
                    ei += 1;
                    enow = if ei < e.len() { e[ei] } else { 0.0 };
                    r
                } else {
                    let r = two_sum(q, fnow);
                    fi += 1;
                    fnow = if fi < f.len() { f[fi] } else { 0.0 };
                    r
                };
                q = qn;
                if hh != 0.0 {
                    h.push(hh);
                }
            }
        }
        while ei < e.len() {
            let (qn, hh) = two_sum(q, enow);
            ei += 1;
            enow = if ei < e.len() { e[ei] } else { 0.0 };
            q = qn;
            if hh != 0.0 {
                h.push(hh);
            }
        }
        while fi < f.len() {
            let (qn, hh) = two_sum(q, fnow);
            fi += 1;
            fnow = if fi < f.len() { f[fi] } else { 0.0 };
            q = qn;
            if hh != 0.0 {
                h.push(hh);
            }
        }
        if q != 0.0 || h.is_empty() {
            h.push(q);
        }
        Expansion(h)
    }

    fn sub(&self, f: &Expansion) -> Self {
        self.add(&f.neg())
    }

    /// scale_expansion_zeroelim (Shewchuk 1997, Fig. 13 with zero elimination).
    fn scale(&self, b: f64) -> Self {
        let e = &self.0;
        let mut h = Vec::with_capacity(2 * e.len());
        let (mut q, hh) = two_product(e[0], b);
        if hh != 0.0 {
            h.push(hh);
        }
        for &ei in &e[1..] {
            let (p1, p0) = two_product(ei, b);
            let (sum, hh) = two_sum(q, p0);
            if hh != 0.0 {
                h.push(hh);
            }
            let (qn, hh) = fast_two_sum(p1, sum);
            q = qn;
            if hh != 0.0 {
                h.push(hh);
            }
        }
        if q != 0.0 || h.is_empty() {
            h.push(q);
        }
        Expansion(h)
    }

    fn mul(&self, f: &Expansion) -> Self {
        let mut acc = self.scale(f.0[0]);
        for &fj in &f.0[1..] {
            acc = acc.add(&self.scale(fj));
        }
        acc
    }
}

fn diff3(p: &P3, q: &P3) -> [Expansion; 3] {
    [Expansion::diff(p[0], q[0]), Expansion::diff(p[1], q[1]), Expansion::diff(p[2], q[2])]
}

fn det3_exact(u: &[Expansion; 3], v: &[Expansion; 3], w: &[Expansion; 3]) -> Expansion {
    // u . (v x w)
    let m0 = v[1].mul(&w[2]).sub(&v[2].mul(&w[1]));
    let m1 = v[2].mul(&w[0]).sub(&v[0].mul(&w[2]));
    let m2 = v[0].mul(&w[1]).sub(&v[1].mul(&w[0]));
    u[0].mul(&m0).add(&u[1].mul(&m1)).add(&u[2].mul(&m2))
}

fn cross_exact(u: &[Expansion; 3], v: &[Expansion; 3]) -> [Expansion; 3] {
    [
        u[1].mul(&v[2]).sub(&u[2].mul(&v[1])),
        u[2].mul(&v[0]).sub(&u[0].mul(&v[2])),
        u[0].mul(&v[1]).sub(&u[1].mul(&v[0])),
    ]
}

fn dot_exact(u: &[Expansion; 3], v: &[Expansion; 3]) -> Expansion {
    u[0].mul(&v[0]).add(&u[1].mul(&v[1])).add(&u[2].mul(&v[2]))
}

// ---------------------------------------------------------------- statistics

/// How often each predicate needed its exact stage (V15 counters).
#[derive(Clone, Copy, Debug, Default)]
pub struct Counters {
    pub orient3d: u64,
    pub orient3d_exact: u64,
    pub insphere: u64,
    pub insphere_exact: u64,
    pub insphere_sos: u64,
}

// ---------------------------------------------------------------- orient3d

const EPS: f64 = 1.1102230246251565e-16; // 2^-53
const O3D_ERRBOUND_A: f64 = (7.0 + 56.0 * EPS) * EPS;
const ISP_ERRBOUND_A: f64 = (16.0 + 224.0 * EPS) * EPS;

pub fn orient3d_exact(a: &P3, b: &P3, c: &P3, d: &P3) -> i8 {
    det3_exact(&diff3(b, a), &diff3(c, a), &diff3(d, a)).sign()
}

/// Sign of det[b - a, c - a, d - a].
#[inline]
pub fn orient3d(a: &P3, b: &P3, c: &P3, d: &P3, n: &mut Counters) -> i8 {
    n.orient3d += 1;
    let (ux, uy, uz) = (b[0] - a[0], b[1] - a[1], b[2] - a[2]);
    let (vx, vy, vz) = (c[0] - a[0], c[1] - a[1], c[2] - a[2]);
    let (wx, wy, wz) = (d[0] - a[0], d[1] - a[1], d[2] - a[2]);
    let vywz = vy * wz;
    let vzwy = vz * wy;
    let vzwx = vz * wx;
    let vxwz = vx * wz;
    let vxwy = vx * wy;
    let vywx = vy * wx;
    let det = ux * (vywz - vzwy) + uy * (vzwx - vxwz) + uz * (vxwy - vywx);
    let permanent = (vywz.abs() + vzwy.abs()) * ux.abs() + (vzwx.abs() + vxwz.abs()) * uy.abs()
        + (vxwy.abs() + vywx.abs()) * uz.abs();
    let bound = O3D_ERRBOUND_A * permanent;
    if det > bound {
        return 1;
    }
    if -det > bound {
        return -1;
    }
    n.orient3d_exact += 1;
    orient3d_exact(a, b, c, d)
}

// ---------------------------------------------------------------- insphere

pub fn insphere_exact(a: &P3, b: &P3, c: &P3, d: &P3, e: &P3) -> i8 {
    // Shewchuk's determinant det[p - e, |p - e|^2] is positive for a point inside when
    // his orientation is positive, which is ours negated.
    let rows = [diff3(a, e), diff3(b, e), diff3(c, e), diff3(d, e)];
    let lift: Vec<Expansion> = rows.iter().map(|r| dot_exact(r, r)).collect();
    let m = |i: usize, j: usize, k: usize| det3_exact(&rows[i], &rows[j], &rows[k]);
    // det4 along the lifted column: sum_i (-1)^(i+3) lift_i det3(other rows)
    let det = lift[1].mul(&m(0, 2, 3)).sub(&lift[0].mul(&m(1, 2, 3)))
        .add(&lift[3].mul(&m(0, 1, 2)).sub(&lift[2].mul(&m(0, 1, 3))));
    -det.sign()
}

/// Sign of the insphere determinant (see the module notes).
#[inline]
pub fn insphere(a: &P3, b: &P3, c: &P3, d: &P3, e: &P3, n: &mut Counters) -> i8 {
    n.insphere += 1;
    let aex = a[0] - e[0];
    let bex = b[0] - e[0];
    let cex = c[0] - e[0];
    let dex = d[0] - e[0];
    let aey = a[1] - e[1];
    let bey = b[1] - e[1];
    let cey = c[1] - e[1];
    let dey = d[1] - e[1];
    let aez = a[2] - e[2];
    let bez = b[2] - e[2];
    let cez = c[2] - e[2];
    let dez = d[2] - e[2];

    let aexbey = aex * bey;
    let bexaey = bex * aey;
    let ab = aexbey - bexaey;
    let bexcey = bex * cey;
    let cexbey = cex * bey;
    let bc = bexcey - cexbey;
    let cexdey = cex * dey;
    let dexcey = dex * cey;
    let cd = cexdey - dexcey;
    let dexaey = dex * aey;
    let aexdey = aex * dey;
    let da = dexaey - aexdey;
    let aexcey = aex * cey;
    let cexaey = cex * aey;
    let ac = aexcey - cexaey;
    let bexdey = bex * dey;
    let dexbey = dex * bey;
    let bd = bexdey - dexbey;

    let abc = aez * bc - bez * ac + cez * ab;
    let bcd = bez * cd - cez * bd + dez * bc;
    let cda = cez * da + dez * ac + aez * cd;
    let dab = dez * ab + aez * bd + bez * da;

    let alift = aex * aex + aey * aey + aez * aez;
    let blift = bex * bex + bey * bey + bez * bez;
    let clift = cex * cex + cey * cey + cez * cez;
    let dlift = dex * dex + dey * dey + dez * dez;

    let det = (dlift * abc - clift * dab) + (blift * cda - alift * bcd);

    let (aez, bez, cez, dez) = (aez.abs(), bez.abs(), cez.abs(), dez.abs());
    let (aexbey, bexaey, bexcey, cexbey) = (aexbey.abs(), bexaey.abs(), bexcey.abs(), cexbey.abs());
    let (cexdey, dexcey, dexaey, aexdey) = (cexdey.abs(), dexcey.abs(), dexaey.abs(), aexdey.abs());
    let (aexcey, cexaey, bexdey, dexbey) = (aexcey.abs(), cexaey.abs(), bexdey.abs(), dexbey.abs());
    let permanent = ((cexdey + dexcey) * bez + (dexbey + bexdey) * cez + (bexcey + cexbey) * dez) * alift
        + ((dexaey + aexdey) * cez + (aexcey + cexaey) * dez + (cexdey + dexcey) * aez) * blift
        + ((aexbey + bexaey) * dez + (bexdey + dexbey) * aez + (dexaey + aexdey) * bez) * clift
        + ((bexcey + cexbey) * aez + (cexaey + aexcey) * bez + (aexbey + bexaey) * cez) * dlift;
    let bound = ISP_ERRBOUND_A * permanent;
    if det > bound {
        return -1;
    }
    if -det > bound {
        return 1;
    }
    n.insphere_exact += 1;
    insphere_exact(a, b, c, d, e)
}

/// insphere with ties broken by Simulation of Simplicity: the lifted coordinate of
/// the point with global index i is raised by eps^(N - i), so the highest index
/// carries the largest perturbation. Requires distinct points and
/// orient3d(a, b, c, d) != 0; then it never returns 0.
pub fn insphere_sos(p: [&P3; 5], ids: [u32; 5], n: &mut Counters) -> i8 {
    let s = insphere(p[0], p[1], p[2], p[3], p[4], n);
    if s != 0 {
        return s;
    }
    n.insphere_sos += 1;
    let mut order = [0usize, 1, 2, 3, 4];
    order.sort_unstable_by(|&i, &j| ids[j].cmp(&ids[i]));
    for &k in &order {
        // cofactor of the lifted entry of row k in det5[p, |p|^2, 1] is
        // (-1)^k orient3d(the other four in order); insphere = -det5
        let mut q = [p[0]; 4];
        let mut m = 0;
        for (r, pr) in p.iter().enumerate() {
            if r != k {
                q[m] = pr;
                m += 1;
            }
        }
        let o = orient3d(q[0], q[1], q[2], q[3], n);
        if o != 0 {
            return if k % 2 == 0 { -o } else { o };
        }
    }
    0
}

// ---------------------------------------------------------------- in-plane incircle

/// For coplanar a, b, c, d: positive when d is strictly inside the circle through
/// a, b, c. Evaluated exactly as
/// -(|u|^2 (v x w).n - |v|^2 (u x w).n + |w|^2 (u x v).n) with u = b - a, v = c - a,
/// w = d - a and n = u x v: |n| times the 2D determinant det[u, v, w; lifted] in the
/// plane with abc counter-clockwise, which is negative inside. Zero when abc is collinear.
pub fn incircle3d(a: &P3, b: &P3, c: &P3, d: &P3) -> i8 {
    let u = diff3(b, a);
    let v = diff3(c, a);
    let w = diff3(d, a);
    let nrm = cross_exact(&u, &v);
    let uu = dot_exact(&u, &u);
    let vv = dot_exact(&v, &v);
    let ww = dot_exact(&w, &w);
    let t1 = uu.mul(&dot_exact(&cross_exact(&v, &w), &nrm));
    let t2 = vv.mul(&dot_exact(&cross_exact(&u, &w), &nrm));
    let t3 = ww.mul(&dot_exact(&nrm, &nrm));
    -t1.sub(&t2).add(&t3).sign()
}

/// True when a, b, c are exactly collinear (the cross product of b - a and c - a is 0).
pub fn collinear(a: &P3, b: &P3, c: &P3) -> bool {
    let u = diff3(b, a);
    let v = diff3(c, a);
    cross_exact(&u, &v).iter().all(|x| x.sign() == 0)
}

pub fn same_point(a: &P3, b: &P3) -> bool {
    a[0] == b[0] && a[1] == b[1] && a[2] == b[2]
}

pub fn lex_cmp(a: &P3, b: &P3) -> Ordering {
    a.iter().zip(b).map(|(x, y)| x.total_cmp(y)).find(|o| *o != Ordering::Equal).unwrap_or(Ordering::Equal)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn environment_probe_passes() {
        assert!(fp_environment_ok());
    }

    #[test]
    fn signs_follow_the_conventions() {
        let mut n = Counters::default();
        let (a, b, c, d) = ([0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]);
        assert_eq!(orient3d(&a, &b, &c, &d, &mut n), 1);
        assert_eq!(orient3d(&a, &c, &b, &d, &mut n), -1);
        assert_eq!(insphere(&a, &b, &c, &d, &[0.25, 0.25, 0.25], &mut n), 1);
        assert_eq!(insphere(&a, &b, &c, &d, &[2.0, 2.0, 2.0], &mut n), -1);
        assert_eq!(insphere(&a, &b, &c, &d, &[1.0, 1.0, 1.0], &mut n), 0);
        assert_eq!(insphere_exact(&a, &b, &c, &d, &[0.25, 0.25, 0.25]), 1);
        assert_eq!(incircle3d(&b, &c, &d, &[0.3, 0.3, 0.4]), 1);
        assert_eq!(incircle3d(&b, &c, &d, &[-1.0, 1.0, 1.0]), -1);
    }
}
