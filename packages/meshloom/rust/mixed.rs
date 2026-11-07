// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

//! Points stored on input segments (S points) and the exact predicates over a mix of
//! input points and S points (M4 stage 2 of the pre-registered 3D plan).
//!
//! An S point is `(a, b, t)`: p = a + t (b - a) for the input points a and b and a
//! double t in (0, 1). Its coordinates are never rounded inside the mesher: a, b and t
//! are doubles, so every coordinate is an exact dyadic rational, and a predicate on S
//! points is a polynomial in doubles of degree up to 6 (orient3d) or 10 (insphere).
//!
//! Evaluation, in order:
//! 1. Only input points: the kernel's own predicates (expansion filters and exact
//!    expansions, M3).
//! 2. An interval filter: the same determinant in interval arithmetic, every operation
//!    widened outward by one ulp with `next_down`/`next_up` (round to nearest is checked
//!    at import). A result interval that excludes zero gives the sign.
//! 3. Exact dyadic big integers: each coordinate as integer times a power of two,
//!    aligned on addition, so the result is exact for any finite doubles.
//!
//! Ties of insphere and of the in-plane incircle are broken by the same index-ordered
//! perturbation as for input points, with the global index of an S point after all
//! input points (input count + its own index).

use crate::bigint::Big;
use crate::predicates::{self as pr, Counters, P3};

/// p = a + t (b - a) on the input segment a-b.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct SPoint {
    pub a: u32,
    pub b: u32,
    pub t: f64,
}

/// A point by kind and index: an input point, or an S point (index into the S table).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Pt {
    In(u32),
    S(u32),
}

/// Calls of the mixed predicates, by path. `interval` counts calls with an S point;
/// `exact` those the interval filter could not decide; `sos` perturbed ties.
#[derive(Default, Debug, Clone, Copy)]
pub struct MixedCounters {
    /// the input-point predicates' own counters (calls with input points only)
    pub input: Counters,
    pub calls: u64,
    pub interval: u64,
    pub exact: u64,
    pub sos: u64,
}

/// The input points and the S points of one mesh.
pub struct Mixed<'a> {
    pub input: &'a [P3],
    pub s: &'a [SPoint],
}

/// Checks an S table against the input points: existing, distinct ends and t a double
/// strictly between 0 and 1.
pub fn check_spoints(input: &[P3], s: &[SPoint]) -> Result<(), String> {
    for (k, sp) in s.iter().enumerate() {
        if sp.a as usize >= input.len() || sp.b as usize >= input.len() {
            return Err(format!("S point {k} refers to a point that does not exist"));
        }
        if sp.a == sp.b {
            return Err(format!("S point {k} lies on a segment with equal ends"));
        }
        if !(sp.t > 0.0 && sp.t < 1.0) {
            return Err(format!("S point {k} has t = {} outside (0, 1)", sp.t));
        }
    }
    Ok(())
}

impl<'a> Mixed<'a> {
    /// The global index: input points first, then S points.
    pub fn id(&self, p: Pt) -> u32 {
        match p {
            Pt::In(i) => i,
            Pt::S(k) => self.input.len() as u32 + k,
        }
    }

    pub fn from_id(&self, id: u32) -> Pt {
        let n = self.input.len() as u32;
        if id < n { Pt::In(id) } else { Pt::S(id - n) }
    }

    /// The point's coordinates rounded to the nearest doubles (for output and bounding
    /// boxes; never for a predicate).
    pub fn rounded(&self, p: Pt) -> P3 {
        match p {
            Pt::In(i) => self.input[i as usize],
            Pt::S(_) => {
                let e = self.exact(p);
                [e[0].to_f64(), e[1].to_f64(), e[2].to_f64()]
            }
        }
    }

    fn interval(&self, p: Pt) -> [Iv; 3] {
        match p {
            Pt::In(i) => self.input[i as usize].map(Iv::point),
            Pt::S(k) => {
                let sp = self.s[k as usize];
                let (a, b) = (&self.input[sp.a as usize], &self.input[sp.b as usize]);
                let t = Iv::point(sp.t);
                std::array::from_fn(|c| {
                    let (ac, bc) = (Iv::point(a[c]), Iv::point(b[c]));
                    ac.add(&t.mul(&bc.sub(&ac)))
                })
            }
        }
    }

    fn exact(&self, p: Pt) -> [Dy; 3] {
        match p {
            Pt::In(i) => self.input[i as usize].map(Dy::from_f64),
            Pt::S(k) => {
                let sp = self.s[k as usize];
                let (a, b) = (&self.input[sp.a as usize], &self.input[sp.b as usize]);
                let t = Dy::from_f64(sp.t);
                std::array::from_fn(|c| {
                    let (ac, bc) = (Dy::from_f64(a[c]), Dy::from_f64(b[c]));
                    ac.add(&t.mul(&bc.sub(&ac)))
                })
            }
        }
    }

    /// True when the two points are exactly equal.
    pub fn same(&self, a: Pt, b: Pt) -> bool {
        if let (Pt::In(i), Pt::In(j)) = (a, b) {
            return pr::same_point(&self.input[i as usize], &self.input[j as usize]);
        }
        let (x, y) = (self.exact(a), self.exact(b));
        (0..3).all(|k| x[k].sub(&y[k]).exact_sign() == 0)
    }

    /// True when the point's exact coordinates are doubles (so rounding it for output
    /// moves it nowhere).
    pub fn is_exact(&self, p: Pt) -> bool {
        match p {
            Pt::In(_) => true,
            Pt::S(_) => self.exact(p).iter().all(|c| {
                let x = c.to_f64();
                x.is_finite() && Dy::from_f64(x).sub(c).exact_sign() == 0
            }),
        }
    }

    fn input_only<const N: usize>(&self, p: &[Pt; N]) -> Option<[&P3; N]> {
        let mut out = [&self.input[0]; N];
        for (o, q) in out.iter_mut().zip(p) {
            match q {
                Pt::In(i) => *o = &self.input[*i as usize],
                Pt::S(_) => return None,
            }
        }
        Some(out)
    }

    /// Sign of det[b - a, c - a, d - a], as [`pr::orient3d`].
    pub fn orient3d(&self, p: [Pt; 4], n: &mut MixedCounters) -> i8 {
        n.calls += 1;
        if let Some(q) = self.input_only(&p) {
            return pr::orient3d(q[0], q[1], q[2], q[3], &mut n.input);
        }
        n.interval += 1;
        let iv = p.map(|q| self.interval(q));
        if let Some(s) = orient(&iv).sign() {
            return s;
        }
        n.exact += 1;
        orient(&p.map(|q| self.exact(q))).exact_sign()
    }

    /// Positive when e is inside the sphere through a positively oriented a, b, c, d,
    /// as [`pr::insphere`].
    pub fn insphere(&self, p: [Pt; 5], n: &mut MixedCounters) -> i8 {
        n.calls += 1;
        if let Some(q) = self.input_only(&p) {
            return pr::insphere(q[0], q[1], q[2], q[3], q[4], &mut n.input);
        }
        n.interval += 1;
        let iv = p.map(|q| self.interval(q));
        if let Some(s) = insph(&iv).sign() {
            return -s;
        }
        n.exact += 1;
        -insph(&p.map(|q| self.exact(q))).exact_sign()
    }

    /// insphere with ties broken by the index-ordered perturbation, as
    /// [`pr::insphere_sos`]: the first nonzero cofactor of the lifted column, taken
    /// from the largest global index down.
    pub fn insphere_sos(&self, p: [Pt; 5], n: &mut MixedCounters) -> i8 {
        let s = self.insphere(p, n);
        if s != 0 {
            return s;
        }
        n.sos += 1;
        let ids = p.map(|q| self.id(q));
        let mut order = [0usize, 1, 2, 3, 4];
        order.sort_unstable_by(|&i, &j| ids[j].cmp(&ids[i]));
        for &k in &order {
            let q = others::<5, 4>(&p, k);
            let o = self.orient3d(q, n);
            if o != 0 {
                return if k % 2 == 0 { -o } else { o };
            }
        }
        0
    }

    /// Sign of component `axis` of (b - a) x (c - a), as [`pr::orient2d_proj`].
    pub fn orient2d_proj(&self, axis: usize, p: [Pt; 3], n: &mut MixedCounters) -> i8 {
        n.calls += 1;
        if let Some(q) = self.input_only(&p) {
            return pr::orient2d_proj(axis, q[0], q[1], q[2]);
        }
        n.interval += 1;
        if let Some(s) = orient2(axis, &p.map(|q| self.interval(q))).sign() {
            return s;
        }
        n.exact += 1;
        orient2(axis, &p.map(|q| self.exact(q))).exact_sign()
    }

    /// In-plane circle test for coplanar points, as [`pr::incircle_plane`].
    pub fn incircle_plane(&self, axis: usize, p: [Pt; 4], n: &mut MixedCounters) -> i8 {
        n.calls += 1;
        if let Some(q) = self.input_only(&p) {
            return pr::incircle_plane(axis, q[0], q[1], q[2], q[3]);
        }
        n.interval += 1;
        if let Some(s) = incircle(axis, &p.map(|q| self.interval(q))).sign() {
            return s;
        }
        n.exact += 1;
        incircle(axis, &p.map(|q| self.exact(q))).exact_sign()
    }

    /// incircle_plane with the index-ordered perturbation, as
    /// [`pr::incircle_plane_sos`].
    pub fn incircle_plane_sos(&self, axis: usize, p: [Pt; 4], n: &mut MixedCounters) -> i8 {
        let s = self.incircle_plane(axis, p, n);
        if s != 0 {
            return s;
        }
        n.sos += 1;
        let ids = p.map(|q| self.id(q));
        let mut order = [0usize, 1, 2, 3];
        order.sort_unstable_by(|&i, &j| ids[j].cmp(&ids[i]));
        for &k in &order {
            let q = others::<4, 3>(&p, k);
            let o = self.orient2d_proj(axis, q, n);
            if o != 0 {
                return if k % 2 == 0 { o } else { -o };
            }
        }
        0
    }
}

/// The entries of `p` other than `k`, in order.
fn others<const N: usize, const M: usize>(p: &[Pt; N], k: usize) -> [Pt; M] {
    let mut q = [p[0]; M];
    let mut m = 0;
    for (r, x) in p.iter().enumerate() {
        if r != k {
            q[m] = *x;
            m += 1;
        }
    }
    q
}

// ------------------------------------------------------------ the determinants

trait Num: Clone {
    fn add(&self, o: &Self) -> Self;
    fn sub(&self, o: &Self) -> Self;
    fn mul(&self, o: &Self) -> Self;
}

fn diff<T: Num>(a: &[T; 3], b: &[T; 3]) -> [T; 3] {
    [a[0].sub(&b[0]), a[1].sub(&b[1]), a[2].sub(&b[2])]
}

fn det3<T: Num>(r0: &[T; 3], r1: &[T; 3], r2: &[T; 3]) -> T {
    let m0 = r1[1].mul(&r2[2]).sub(&r1[2].mul(&r2[1]));
    let m1 = r1[0].mul(&r2[2]).sub(&r1[2].mul(&r2[0]));
    let m2 = r1[0].mul(&r2[1]).sub(&r1[1].mul(&r2[0]));
    r0[0].mul(&m0).sub(&r0[1].mul(&m1)).add(&r0[2].mul(&m2))
}

/// det[b - a, c - a, d - a].
fn orient<T: Num>(p: &[[T; 3]; 4]) -> T {
    det3(&diff(&p[1], &p[0]), &diff(&p[2], &p[0]), &diff(&p[3], &p[0]))
}

/// det4 of the rows (p_i - e, |p_i - e|^2), i = 0..3, e = p[4]; insphere is its
/// negation.
fn insph<T: Num>(p: &[[T; 3]; 5]) -> T {
    let d: [[T; 3]; 4] = std::array::from_fn(|i| diff(&p[i], &p[4]));
    let l: [T; 4] = std::array::from_fn(|i| d[i][0].mul(&d[i][0]).add(&d[i][1].mul(&d[i][1])).add(&d[i][2].mul(&d[i][2])));
    // expansion along the lifted column: cofactor sign (-1)^(i + 3)
    let minor = |i: usize| {
        let r: Vec<&[T; 3]> = (0..4).filter(|&k| k != i).map(|k| &d[k]).collect();
        det3(r[0], r[1], r[2])
    };
    let t: [T; 4] = std::array::from_fn(|i| l[i].mul(&minor(i)));
    t[1].sub(&t[0]).add(&t[3].sub(&t[2]))
}

/// Component `axis` of (b - a) x (c - a).
fn orient2<T: Num>(axis: usize, p: &[[T; 3]; 3]) -> T {
    let (i, j) = pr::kept_axes(axis);
    let (u, v) = (diff(&p[1], &p[0]), diff(&p[2], &p[0]));
    u[i].mul(&v[j]).sub(&u[j].mul(&v[i]))
}

/// det[u_k - u_d, v_k - v_d, |p_k|^2 - |p_d|^2] over k = a, b, c.
fn incircle<T: Num>(axis: usize, p: &[[T; 3]; 4]) -> T {
    let (i, j) = pr::kept_axes(axis);
    let row = |q: &[T; 3]| {
        let w = (0..3).map(|k| q[k].sub(&p[3][k]).mul(&q[k].add(&p[3][k])))
            .reduce(|x, y| x.add(&y)).unwrap();
        [q[i].sub(&p[3][i]), q[j].sub(&p[3][j]), w]
    };
    det3(&row(&p[0]), &row(&p[1]), &row(&p[2]))
}

// ------------------------------------------------------------ intervals

/// A closed interval of doubles; every operation rounds outward by one ulp, which
/// contains the exact result under round to nearest (including at overflow and
/// underflow: an infinite or NaN bound only makes the filter fail).
#[derive(Clone, Copy, Debug)]
struct Iv {
    lo: f64,
    hi: f64,
}

impl Iv {
    fn point(x: f64) -> Iv {
        Iv { lo: x, hi: x }
    }

    /// The sign when the interval excludes zero.
    fn sign(&self) -> Option<i8> {
        if self.lo > 0.0 {
            Some(1)
        } else if self.hi < 0.0 {
            Some(-1)
        } else {
            None // contains zero, or a NaN bound
        }
    }
}

impl Num for Iv {
    fn add(&self, o: &Iv) -> Iv {
        Iv { lo: (self.lo + o.lo).next_down(), hi: (self.hi + o.hi).next_up() }
    }

    fn sub(&self, o: &Iv) -> Iv {
        Iv { lo: (self.lo - o.hi).next_down(), hi: (self.hi - o.lo).next_up() }
    }

    fn mul(&self, o: &Iv) -> Iv {
        let p = [self.lo * o.lo, self.lo * o.hi, self.hi * o.lo, self.hi * o.hi];
        if p.iter().any(|x| x.is_nan()) {
            return Iv { lo: f64::NEG_INFINITY, hi: f64::INFINITY };
        }
        let lo = p.iter().copied().fold(f64::INFINITY, f64::min);
        let hi = p.iter().copied().fold(f64::NEG_INFINITY, f64::max);
        Iv { lo: lo.next_down(), hi: hi.next_up() }
    }
}

// ------------------------------------------------------------ exact dyadic numbers

/// m * 2^e with a big integer m: exact sums and products of doubles.
#[derive(Clone, Debug)]
struct Dy {
    m: Big,
    e: i32,
}

impl Dy {
    fn from_f64(x: f64) -> Dy {
        let (m, e) = Big::from_f64(x);
        Dy { m, e }
    }

    fn exact_sign(&self) -> i8 {
        self.m.sign()
    }

    /// The nearest double (ties to even), for output coordinates.
    fn to_f64(&self) -> f64 {
        self.m.to_f64_scaled(self.e)
    }
}

impl Num for Dy {
    fn add(&self, o: &Dy) -> Dy {
        if self.m.sign() == 0 {
            return o.clone();
        }
        if o.m.sign() == 0 {
            return self.clone();
        }
        let e = self.e.min(o.e);
        let a = self.m.shl((self.e - e) as u32);
        let b = o.m.shl((o.e - e) as u32);
        Dy { m: a.add(&b), e }
    }

    fn sub(&self, o: &Dy) -> Dy {
        self.add(&Dy { m: o.m.neg(), e: o.e })
    }

    fn mul(&self, o: &Dy) -> Dy {
        Dy { m: self.m.mul(&o.m), e: self.e + o.e }
    }
}

/// Input points and a growing table of S points, owned: the geometry of a mesh into
/// which boundary recovery inserts points on segments. Global indices put the S points
/// after the input points.
pub struct MixedPoints {
    pub input: Vec<P3>,
    pub s: Vec<SPoint>,
    pub n: MixedCounters,
}

impl MixedPoints {
    pub fn new(input: Vec<P3>) -> MixedPoints {
        MixedPoints { input, s: Vec::new(), n: MixedCounters::default() }
    }

    pub fn view(&self) -> Mixed<'_> {
        Mixed { input: &self.input, s: &self.s }
    }

    /// Adds an S point; returns its global index.
    pub fn push(&mut self, sp: SPoint) -> u32 {
        self.s.push(sp);
        (self.input.len() + self.s.len() - 1) as u32
    }
}

impl crate::delaunay::Geom for MixedPoints {
    fn len(&self) -> usize {
        self.input.len() + self.s.len()
    }

    fn orient3d(&mut self, v: [u32; 4]) -> i8 {
        let m = Mixed { input: &self.input, s: &self.s };
        m.orient3d(v.map(|i| m.from_id(i)), &mut self.n)
    }

    fn insphere_sos(&mut self, v: [u32; 5]) -> i8 {
        let m = Mixed { input: &self.input, s: &self.s };
        m.insphere_sos(v.map(|i| m.from_id(i)), &mut self.n)
    }

    fn same(&self, a: u32, b: u32) -> bool {
        let m = self.view();
        m.same(m.from_id(a), m.from_id(b))
    }

    fn collinear(&self, a: u32, b: u32, c: u32) -> bool {
        let m = self.view();
        let p = [a, b, c].map(|i| m.from_id(i));
        let mut n = MixedCounters::default();
        (0..3).all(|axis| m.orient2d_proj(axis, p, &mut n) == 0)
    }

    fn counters(&self) -> Counters {
        self.n.input
    }
}

impl Mixed<'_> {
    /// Sign of (a - o) . (b - o), exactly.
    pub fn dot_sign(&self, o: Pt, a: Pt, b: Pt) -> i8 {
        let (eo, ea, eb) = (self.exact(o), self.exact(a), self.exact(b));
        let d = (0..3).map(|k| ea[k].sub(&eo[k]).mul(&eb[k].sub(&eo[k]))).reduce(|x, y| x.add(&y)).unwrap();
        d.exact_sign()
    }
}

/// The in-plane predicates of a facet triangulation over input and S points, by global
/// index. Counters are kept in a cell: the triangulation asks through `&self`.
pub struct MixedPlane<'a> {
    pub m: Mixed<'a>,
    pub n: std::cell::Cell<MixedCounters>,
}

impl crate::facet::PlanePred for MixedPlane<'_> {
    fn orient(&self, axis: usize, a: u32, b: u32, c: u32) -> i8 {
        let mut n = self.n.get();
        let s = self.m.orient2d_proj(axis, [a, b, c].map(|i| self.m.from_id(i)), &mut n);
        self.n.set(n);
        s
    }

    fn incircle_sos(&self, axis: usize, a: u32, b: u32, c: u32, d: u32) -> i8 {
        let mut n = self.n.get();
        let s = self.m.incircle_plane_sos(axis, [a, b, c, d].map(|i| self.m.from_id(i)), &mut n);
        self.n.set(n);
        s
    }

    fn between(&self, _axis: usize, a: u32, b: u32, c: u32) -> bool {
        let p = |i: u32| self.m.from_id(i);
        self.m.dot_sign(p(c), p(a), p(b)) < 0
    }

    fn same_direction(&self, _axis: usize, v: u32, x: u32, y: u32) -> bool {
        let p = |i: u32| self.m.from_id(i);
        self.m.dot_sign(p(v), p(x), p(y)) > 0
    }
}
