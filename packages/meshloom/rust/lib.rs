// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

//! Compiled kernel of meshloom. This skeleton carries only what the packaging
//! needs to prove: the extension loads on every wheel platform, reports the
//! version it was built as, and computes IEEE double products without fused
//! multiply-add, which every exact predicate of the later kernel relies on.

use pyo3::prelude::*;

/// Error-free product: returns (p, e) with p = fl(a*b) and a*b = p + e exactly,
/// by Dekker's splitting, which needs only + - * and no FMA. Exact for |a|, |b| < 2^996
/// when the error term does not underflow.
fn two_product(a: f64, b: f64) -> (f64, f64) {
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

/// Exactness probe for the wheel tests: the error term of a*b computed with
/// plain operations. Python compares it with the exact rational residual; an
/// FMA contraction or a wrong rounding mode makes the two disagree.
#[pyfunction]
fn two_product_probe(a: f64, b: f64) -> (f64, f64) {
    two_product(a, b)
}

/// Version of the compiled kernel; must equal the Python package version.
#[pyfunction]
fn version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

#[pymodule]
fn _kernel(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(version, m)?)?;
    m.add_function(wrap_pyfunction!(two_product_probe, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::two_product;

    #[test]
    fn product_error_is_exact_for_powers_of_two_offsets() {
        let a = 1.0 + f64::EPSILON;
        let (p, e) = two_product(a, a);
        // (1+u)^2 = 1 + 2u + u^2: p = 1 + 2u, e = u^2
        assert_eq!(p, 1.0 + 2.0 * f64::EPSILON);
        assert_eq!(e, f64::EPSILON * f64::EPSILON);
    }
}
