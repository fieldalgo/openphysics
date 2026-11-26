// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

//! A graded size field h(x) for refinement: a background octree whose cells carry the size
//! sampled at their eight corners, read by trilinear interpolation in the leaf that holds
//! the point. The caller's function is sampled once, in Python, before refinement, so
//! refinement never calls back into Python. A point outside the octree's cube is clamped
//! onto it. Sources: the size at a tetrahedron's circumcentre decides whether it is split,
//! as with a user size function in Ruppert (1995) and Shewchuk (1997, thesis); the
//! background grid holding the size is Gmsh's "background mesh" (Gmsh reference manual,
//! mesh size fields).

use crate::predicates::P3;

#[derive(Debug, Clone)]
pub struct SizeField {
    /// the octree's cube: its lowest corner and edge length
    lo: P3,
    len: f64,
    /// per node: the index of its first of 8 consecutive children, or -1 for a leaf
    child: Vec<i64>,
    /// per node: the size at its corners, corner index ix + 2 iy + 4 iz
    corner: Vec<[f64; 8]>,
    /// the smallest and largest size sampled
    pub min: f64,
    pub max: f64,
}

impl SizeField {
    /// Checks the arrays from Python: a cube with a positive finite edge, children that
    /// point to later nodes (so the descent ends), positive finite sizes.
    pub fn new(cube: [f64; 4], child: Vec<i64>, corner: Vec<[f64; 8]>) -> Result<Self, String> {
        let n = child.len();
        if n == 0 || corner.len() != n {
            return Err("size field: one child index and 8 corner sizes per node, at least one node".into());
        }
        if !cube.iter().all(|x| x.is_finite()) || !(cube[3] > 0.0) {
            return Err("size field: the cube needs finite coordinates and an edge > 0".into());
        }
        for (i, &c) in child.iter().enumerate() {
            if c != -1 && !(c > i as i64 && (c as usize).checked_add(8).is_some_and(|e| e <= n)) {
                return Err(format!("size field: node {i} has child index {c}"));
            }
        }
        let (mut min, mut max) = (f64::INFINITY, 0.0f64);
        for v in corner.iter().flatten() {
            if !(v.is_finite() && *v > 0.0) {
                return Err(format!("size field: a size must be finite and > 0, got {v}"));
            }
            min = min.min(*v);
            max = max.max(*v);
        }
        Ok(SizeField { lo: [cube[0], cube[1], cube[2]], len: cube[3], child, corner, min, max })
    }

    /// h at x: trilinear in the leaf holding x (x clamped onto the cube).
    pub fn at(&self, x: &P3) -> f64 {
        let mut lo = self.lo;
        let mut len = self.len;
        let mut node = 0usize;
        let mut p = [0.0; 3];
        for k in 0..3 {
            p[k] = if x[k].is_nan() { lo[k] } else { x[k].clamp(lo[k], lo[k] + len) };
        }
        while self.child[node] >= 0 {
            let half = len * 0.5;
            let mut oct = 0;
            for k in 0..3 {
                if p[k] >= lo[k] + half {
                    oct |= 1 << k;
                    lo[k] += half;
                }
            }
            node = self.child[node] as usize + oct;
            len = half;
        }
        let t = [0, 1, 2].map(|k| ((p[k] - lo[k]) / len).clamp(0.0, 1.0));
        let c = &self.corner[node];
        let mut h = 0.0;
        for (i, v) in c.iter().enumerate() {
            let w = (0..3).map(|k| if i >> k & 1 == 1 { t[k] } else { 1.0 - t[k] }).product::<f64>();
            h += w * v;
        }
        // rounding can take a weighted mean just outside its corners' range
        h.clamp(c.iter().copied().fold(f64::INFINITY, f64::min), c.iter().copied().fold(0.0, f64::max))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_linear_field_is_read_exactly_at_corners_and_in_between() {
        // one root with h = 1 + x + 2y + 4z at its corners, then split once
        let f = |x: f64, y: f64, z: f64| 1.0 + x + 2.0 * y + 4.0 * z;
        let corners = |lo: P3, l: f64| -> [f64; 8] {
            std::array::from_fn(|i| f(lo[0] + l * (i & 1) as f64, lo[1] + l * (i >> 1 & 1) as f64, lo[2] + l * (i >> 2 & 1) as f64))
        };
        let mut child = vec![1];
        let mut corner = vec![corners([0.0; 3], 1.0)];
        for o in 0..8 {
            child.push(-1);
            corner.push(corners([0.5 * (o & 1) as f64, 0.5 * (o >> 1 & 1) as f64, 0.5 * (o >> 2 & 1) as f64], 0.5));
        }
        let s = SizeField::new([0.0, 0.0, 0.0, 1.0], child, corner).unwrap();
        for p in [[0.25, 0.75, 0.5], [0.0, 0.0, 0.0], [1.0, 1.0, 1.0], [0.6, 0.1, 0.9]] {
            assert!((s.at(&p) - f(p[0], p[1], p[2])).abs() < 1e-12, "{p:?}");
        }
        assert_eq!(s.at(&[-5.0, 0.0, 0.0]), f(0.0, 0.0, 0.0)); // clamped
        assert_eq!((s.min, s.max), (1.0, 8.0));
    }

    #[test]
    fn bad_arrays_are_refused() {
        assert!(SizeField::new([0.0, 0.0, 0.0, 1.0], vec![0], vec![[1.0; 8]]).is_err()); // a cycle
        assert!(SizeField::new([0.0, 0.0, 0.0, 1.0], vec![-1], vec![[0.0; 8]]).is_err());
        assert!(SizeField::new([0.0, 0.0, 0.0, 0.0], vec![-1], vec![[1.0; 8]]).is_err());
        assert!(SizeField::new([0.0, 0.0, 0.0, 1.0], vec![1], vec![[1.0; 8]; 2]).is_err()); // children beyond
    }
}
