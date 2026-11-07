// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

//! Signed big integers (32-bit limbs) for the exact paths that expansion arithmetic
//! cannot take: predicates on points stored on segments, whose degree in the input
//! doubles is too high for an underflow-free expansion. Only what those determinants
//! need: add, subtract, multiply, shift left and sign. Written for M3's test
//! reference and promoted here in M4.

use std::cmp::Ordering;

#[derive(Clone, Debug, PartialEq, Eq)]
pub(crate) struct Big {
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
    pub(crate) fn zero() -> Big {
        Big { neg: false, mag: Vec::new() }
    }

    pub(crate) fn sign(&self) -> i8 {
        if self.mag.is_empty() { 0 } else if self.neg { -1 } else { 1 }
    }

    pub(crate) fn from_u64_shl(m: u64, shift: u32, neg: bool) -> Big {
        let mut mag = vec![0u32; (shift / 32) as usize];
        let s = shift % 32;
        let wide = (m as u128) << s;
        for k in 0..4 {
            mag.push((wide >> (32 * k)) as u32);
        }
        trim(&mut mag);
        Big { neg: neg && !mag.is_empty(), mag }
    }

    pub(crate) fn add(&self, o: &Big) -> Big {
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

    pub(crate) fn neg(&self) -> Big {
        Big { neg: !self.neg && !self.mag.is_empty(), mag: self.mag.clone() }
    }

    #[cfg(test)]
    pub(crate) fn sub(&self, o: &Big) -> Big {
        self.add(&o.neg())
    }

    pub(crate) fn mul(&self, o: &Big) -> Big {
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

    pub(crate) fn bits(&self) -> u32 {
        match self.mag.last() {
            None => 0,
            Some(&top) => 32 * (self.mag.len() as u32 - 1) + (32 - top.leading_zeros()),
        }
    }

    #[cfg(test)]
    pub(crate) fn pow2(k: u32) -> Big {
        Big::from_u64_shl(1, k, false)
    }

    /// self * 2^k.
    pub(crate) fn shl(&self, k: u32) -> Big {
        if self.mag.is_empty() || k == 0 {
            return self.clone();
        }
        let (words, bits) = ((k / 32) as usize, k % 32);
        let mut mag = vec![0u32; words];
        let mut carry = 0u32;
        for &w in &self.mag {
            if bits == 0 {
                mag.push(w);
            } else {
                mag.push((w << bits) | carry);
                carry = w >> (32 - bits);
            }
        }
        if carry != 0 {
            mag.push(carry);
        }
        Big { neg: self.neg, mag }
    }

    fn bit(&self, k: u32) -> bool {
        let w = (k / 32) as usize;
        w < self.mag.len() && (self.mag[w] >> (k % 32)) & 1 == 1
    }

    /// True when any of the bits below position k is set.
    fn any_below(&self, k: u32) -> bool {
        let w = (k / 32) as usize;
        self.mag.iter().take(w.min(self.mag.len())).any(|&x| x != 0)
            || (w < self.mag.len() && self.mag[w] & ((1u32 << (k % 32)) - 1) != 0)
    }

    /// floor(|self| / 2^k) for a result below 2^64.
    fn shr_u64(&self, k: u32) -> u64 {
        let mut r = 0u64;
        for b in 0..64 {
            if self.bit(k + b) {
                r |= 1 << b;
            }
        }
        r
    }

    /// self * 2^e rounded to the nearest double, ties to even (infinite past the range).
    pub(crate) fn to_f64_scaled(&self, e: i32) -> f64 {
        if self.mag.is_empty() {
            return 0.0;
        }
        let sign = if self.neg { -1.0 } else { 1.0 };
        let top = self.bits() as i64 - 1 + e as i64; // exponent of the leading bit
        if top > 1023 {
            return sign * f64::INFINITY;
        }
        // the unit of the last significand bit: 2^(top - 52), or 2^-1074 for subnormals
        let unit = (top - 52).max(-1074);
        let shift = unit - e as i64;
        let q: u64 = if shift <= 0 {
            self.shr_u64(0) << (-shift) as u32
        } else {
            let s = shift as u32;
            let mut q = self.shr_u64(s);
            let half = self.bit(s - 1);
            let sticky = self.any_below(s - 1);
            if half && (sticky || q & 1 == 1) {
                q += 1;
            }
            q
        };
        // q < 2^54, so q is exact as a double; scale in two exact steps
        let (h1, h2) = (unit / 2, unit - unit / 2);
        let v = q as f64 * 2f64.powi(h1 as i32) * 2f64.powi(h2 as i32);
        sign * v
    }

    /// The exact value of a double, as (integer, exponent): x = m * 2^e. Zero is (0, 0).
    pub(crate) fn from_f64(x: f64) -> (Big, i32) {
        if x == 0.0 {
            return (Big::zero(), 0);
        }
        let (m, e, neg) = decompose(x);
        (Big::from_u64_shl(m, 0, neg), e)
    }
}

/// (odd integer mantissa, exponent of its unit, sign) with |x| = m * 2^e, for x != 0.
pub(crate) fn decompose(x: f64) -> (u64, i32, bool) {
    let bits = x.to_bits();
    let neg = bits >> 63 == 1;
    let exp = ((bits >> 52) & 0x7ff) as i32;
    let frac = bits & ((1u64 << 52) - 1);
    let (m, e) = if exp == 0 { (frac, -1074) } else { (frac | (1u64 << 52), exp - 1075) };
    let tz = m.trailing_zeros();
    (m >> tz, e + tz as i32, neg)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn of(x: i128) -> Big {
        let (neg, m) = (x < 0, x.unsigned_abs());
        let lo = Big::from_u64_shl(m as u64, 0, false);
        let hi = Big::from_u64_shl((m >> 64) as u64, 64, false);
        let b = lo.add(&hi);
        if neg { b.neg() } else { b }
    }

    #[test]
    fn arithmetic_agrees_with_i128() {
        let mut s = 0x9e37_79b9_7f4a_7c15u64;
        let mut next = || {
            s ^= s << 13;
            s ^= s >> 7;
            s ^= s << 17;
            s
        };
        for _ in 0..20000 {
            let a = (next() as i64 >> (next() % 60)) as i128;
            let b = (next() as i64 >> (next() % 60)) as i128;
            assert_eq!(of(a).add(&of(b)), of(a + b));
            assert_eq!(of(a).sub(&of(b)), of(a - b));
            assert_eq!(of(a).mul(&of(b)), of(a * b));
            let k = (next() % 60) as u32;
            if a.unsigned_abs() < (1u128 << 64) {
                assert_eq!(of(a).shl(k), of(a << k));
            }
            assert_eq!(of(a).sign(), a.signum() as i8);
        }
        assert_eq!(Big::pow2(100).bits(), 101);
        assert_eq!(Big::from_f64(-0.75), (of(-3), -2));
        assert_eq!(Big::from_f64(0.0).0.sign(), 0);
    }

    #[test]
    fn rounding_to_doubles_is_correct() {
        // every double round-trips, including subnormals and the largest finite
        for x in [1.0, -0.1, 3.0e-310, -5.0e-324, f64::MAX, f64::MIN_POSITIVE, 1.5e300, 2f64.powi(-1000)] {
            let (m, e) = Big::from_f64(x);
            assert_eq!(m.to_f64_scaled(e), x);
        }
        // halfway cases round to even; just above half rounds up
        let one = Big::pow2(53); // 2^53 = 1.0 * 2^53
        assert_eq!(one.add(&Big::pow2(0)).to_f64_scaled(-53), 1.0); // 1 + 2^-53: tie, to even
        assert_eq!(one.add(&Big::pow2(0)).add(&Big::pow2(1)).to_f64_scaled(-53), 1.0 + 2.0 * f64::EPSILON / 2.0 * 2.0);
        assert_eq!(Big::pow2(60).add(&Big::pow2(0)).to_f64_scaled(0), 2f64.powi(60)); // sticky below half
        assert_eq!(Big::pow2(2000).to_f64_scaled(0), f64::INFINITY);
        assert_eq!(Big::pow2(0).to_f64_scaled(-1076), 0.0); // a quarter of the smallest subnormal
        assert_eq!(Big::pow2(0).add(&Big::pow2(1)).to_f64_scaled(-1076), 5.0e-324); // 3/4: up
    }
}
