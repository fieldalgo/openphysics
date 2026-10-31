// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

//! Compiled kernel of meshloom: exact geometric predicates and the Delaunay
//! tetrahedralization (internal building blocks; the public mesher comes later).
//! Arrays cross the boundary as little-endian bytes, so the extension needs no
//! array crate; the Python side wraps them in numpy arrays.

mod delaunay;
#[cfg(test)]
mod exact_ref;
mod facet;
mod plc;
mod predicates;

use predicates::{two_product, P3};
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict};

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

fn check_environment() -> PyResult<()> {
    if predicates::fp_environment_ok() {
        Ok(())
    } else {
        Err(PyRuntimeError::new_err("the floating-point environment is not IEEE round-to-nearest with \
                                     gradual underflow (another extension may have set flush-to-zero); \
                                     exact predicates would be wrong"))
    }
}

fn f64s(b: &[u8]) -> Vec<f64> {
    b.chunks_exact(8).map(|c| f64::from_le_bytes(c.try_into().unwrap())).collect()
}

fn points(b: &[u8]) -> PyResult<Vec<P3>> {
    if b.len() % 24 != 0 {
        return Err(PyValueError::new_err("point data must hold 3 doubles per point"));
    }
    Ok(f64s(b).chunks_exact(3).map(|c| [c[0], c[1], c[2]]).collect())
}

fn u32s(b: &[u8], what: &str) -> PyResult<Vec<u32>> {
    b.chunks_exact(8)
        .map(|c| {
            let x = i64::from_le_bytes(c.try_into().unwrap());
            u32::try_from(x).map_err(|_| PyValueError::new_err(format!("{what} out of range: {x}")))
        })
        .collect()
}

fn counters<'py>(py: Python<'py>, d: &Bound<'py, PyDict>, n: &predicates::Counters) -> PyResult<()> {
    let _ = py;
    d.set_item("orient3d", n.orient3d)?;
    d.set_item("orient3d_exact", n.orient3d_exact)?;
    d.set_item("insphere", n.insphere)?;
    d.set_item("insphere_exact", n.insphere_exact)?;
    d.set_item("insphere_sos", n.insphere_sos)?;
    Ok(())
}

/// Signs of one predicate over a batch: `coords` holds n groups of k points
/// (k = 4 for orient3d and incircle3d, 5 for insphere and insphere_sos), `ids` the
/// global indices for insphere_sos (n x 5 int64). Returns n int8 signs.
#[pyfunction]
#[pyo3(signature = (kind, coords, ids=None, axis=2))]
fn predicate_signs<'py>(py: Python<'py>, kind: &str, coords: &Bound<'py, PyBytes>,
                        ids: Option<&Bound<'py, PyBytes>>, axis: usize) -> PyResult<Bound<'py, PyBytes>> {
    check_environment()?;
    let k = match kind {
        "orient2d_proj" => 3,
        "orient3d" | "incircle3d" | "incircle_plane" | "incircle_plane_sos" => 4,
        "insphere" | "insphere_sos" => 5,
        _ => return Err(PyValueError::new_err(format!("unknown predicate {kind:?}"))),
    };
    let pts = points(coords.as_bytes())?;
    if pts.len() % k != 0 {
        return Err(PyValueError::new_err(format!("{kind} takes groups of {k} points")));
    }
    if let Err(e) = delaunay::check_input(&pts) {
        return Err(PyValueError::new_err(e.to_string()));
    }
    if axis > 2 {
        return Err(PyValueError::new_err("axis must be 0, 1 or 2"));
    }
    let sos = kind.ends_with("_sos");
    let ids = match (sos, ids) {
        (true, Some(b)) => u32s(b.as_bytes(), "index")?,
        (true, None) => return Err(PyValueError::new_err(format!("{kind} needs ids"))),
        _ => Vec::new(),
    };
    if sos && ids.len() != pts.len() {
        return Err(PyValueError::new_err("ids must hold one index per point"));
    }
    let kind = kind.to_owned();
    let out: Vec<u8> = py.detach(move || {
        let mut n = predicates::Counters::default();
        pts.chunks_exact(k).enumerate().map(|(g, q)| {
            let s = match kind.as_str() {
                "orient3d" => predicates::orient3d(&q[0], &q[1], &q[2], &q[3], &mut n),
                "incircle3d" => predicates::incircle3d(&q[0], &q[1], &q[2], &q[3]),
                "insphere" => predicates::insphere(&q[0], &q[1], &q[2], &q[3], &q[4], &mut n),
                "orient2d_proj" => predicates::orient2d_proj(axis, &q[0], &q[1], &q[2]),
                "incircle_plane" => predicates::incircle_plane(axis, &q[0], &q[1], &q[2], &q[3]),
                "incircle_plane_sos" => {
                    let i = &ids[4 * g..4 * g + 4];
                    predicates::incircle_plane_sos(axis, [&q[0], &q[1], &q[2], &q[3]], [i[0], i[1], i[2], i[3]])
                }
                _ => {
                    let i = &ids[5 * g..5 * g + 5];
                    predicates::insphere_sos([&q[0], &q[1], &q[2], &q[3], &q[4]], [i[0], i[1], i[2], i[3], i[4]], &mut n)
                }
            };
            s as u8
        }).collect()
    });
    Ok(PyBytes::new(py, &out))
}

/// Delaunay tetrahedralization: `coords` n x 3 doubles, `order` an optional
/// insertion order (n int64). Returns (tetrahedra as T x 4 int64 bytes, for each
/// point the vertex it duplicates or itself as n int64 bytes, statistics).
#[pyfunction]
#[pyo3(name = "delaunay", signature = (coords, order=None))]
fn tetrahedralize<'py>(py: Python<'py>, coords: &Bound<'py, PyBytes>, order: Option<&Bound<'py, PyBytes>>)
                 -> PyResult<(Bound<'py, PyBytes>, Bound<'py, PyBytes>, Bound<'py, PyDict>)> {
    check_environment()?;
    let pts = points(coords.as_bytes())?;
    let order = order.map(|b| u32s(b.as_bytes(), "order entry")).transpose()?;
    let out = py.detach(move || delaunay::tetrahedralize(&pts, order.as_deref()))
        .map_err(|e| match e {
            delaunay::Error::Internal(_) => PyRuntimeError::new_err(e.to_string()),
            _ => PyValueError::new_err(e.to_string()),
        })?;
    let i64_bytes = |xs: &mut dyn Iterator<Item = u32>, n: usize| -> PyResult<Bound<'py, PyBytes>> {
        PyBytes::new_with(py, 8 * n, |buf| {
            for (chunk, x) in buf.chunks_exact_mut(8).zip(xs) {
                chunk.copy_from_slice(&(x as i64).to_le_bytes());
            }
            Ok(())
        })
    };
    let tets = i64_bytes(&mut out.tets.iter().flatten().copied(), 4 * out.tets.len())?;
    let vertex_of = i64_bytes(&mut out.vertex_of.iter().copied(), out.vertex_of.len())?;
    let s = &out.stats;
    let d = PyDict::new(py);
    counters(py, &d, &s.predicates)?;
    d.set_item("inserted", s.inserted)?;
    d.set_item("duplicates", s.duplicates)?;
    d.set_item("walk_steps", s.walk_steps)?;
    d.set_item("walk_fallbacks", s.walk_fallbacks)?;
    d.set_item("cavity_tets", s.cavity_tets)?;
    Ok((tets, vertex_of, d))
}

/// Checks a Delaunay tetrahedralization from its arrays alone (see
/// `delaunay::verify`); raises ValueError naming the first violation.
#[pyfunction]
fn verify_delaunay<'py>(py: Python<'py>, coords: &Bound<'py, PyBytes>, tets: &Bound<'py, PyBytes>)
                        -> PyResult<Bound<'py, PyDict>> {
    check_environment()?;
    let pts = points(coords.as_bytes())?;
    let t = u32s(tets.as_bytes(), "vertex index")?;
    if t.len() % 4 != 0 {
        return Err(PyValueError::new_err("tetrahedra must hold 4 indices each"));
    }
    let t: Vec<[u32; 4]> = t.chunks_exact(4).map(|c| [c[0], c[1], c[2], c[3]]).collect();
    let r = py.detach(move || delaunay::verify(&pts, &t)).map_err(PyValueError::new_err)?;
    let d = PyDict::new(py);
    counters(py, &d, &r.predicates)?;
    for (k, v) in [("vertices", r.vertices), ("edges", r.edges), ("faces", r.faces), ("tets", r.tets),
                   ("hull_faces", r.hull_faces), ("interior_faces", r.interior_faces)] {
        d.set_item(k, v)?;
    }
    Ok(d)
}

/// Constrained Delaunay triangulation of one planar facet: `coords` n x 3 doubles,
/// `loops` a list of int64 index arrays (outer loop first, holes after, even-odd).
/// Returns (triangles as T x 3 int64 bytes wound like the outer loop, dropped axis).
#[pyfunction]
fn triangulate_facet<'py>(py: Python<'py>, coords: &Bound<'py, PyBytes>, loops: Vec<Bound<'py, PyBytes>>)
                          -> PyResult<(Bound<'py, PyBytes>, usize)> {
    check_environment()?;
    let pts = points(coords.as_bytes())?;
    let loops: Vec<Vec<u32>> = loops.iter().map(|b| u32s(b.as_bytes(), "loop index")).collect::<PyResult<_>>()?;
    let f = py.detach(move || facet::triangulate(&pts, &loops)).map_err(PyValueError::new_err)?;
    let tris = PyBytes::new_with(py, 24 * f.triangles.len(), |buf| {
        for (chunk, x) in buf.chunks_exact_mut(8).zip(f.triangles.iter().flatten()) {
            chunk.copy_from_slice(&(*x as i64).to_le_bytes());
        }
        Ok(())
    })?;
    Ok((tris, f.axis))
}

/// Exact validity check of a PLC: `coords` n x 3 doubles, `segments` m x 2 int64 bytes,
/// `facets` a list of facets, each a list of int64 loop arrays. Raises ValueError naming
/// the first violation; returns (all segments as int64 bytes, facet triangles as int64
/// bytes, the facet of each triangle as int64 bytes, number of candidate pairs tested).
#[pyfunction]
fn check_plc<'py>(py: Python<'py>, coords: &Bound<'py, PyBytes>, segments: &Bound<'py, PyBytes>,
                  facets: Vec<Vec<Bound<'py, PyBytes>>>)
                  -> PyResult<(Bound<'py, PyBytes>, Bound<'py, PyBytes>, Bound<'py, PyBytes>, usize)> {
    check_environment()?;
    let points = points(coords.as_bytes())?;
    let seg = u32s(segments.as_bytes(), "segment index")?;
    if seg.len() % 2 != 0 {
        return Err(PyValueError::new_err("segments must hold 2 indices each"));
    }
    let segments: Vec<[u32; 2]> = seg.chunks_exact(2).map(|c| [c[0], c[1]]).collect();
    let facets: Vec<Vec<Vec<u32>>> = facets.iter()
        .map(|f| f.iter().map(|b| u32s(b.as_bytes(), "loop index")).collect::<PyResult<_>>())
        .collect::<PyResult<_>>()?;
    let plc = plc::Plc { points, segments, facets };
    let c = py.detach(move || plc::check(&plc)).map_err(PyValueError::new_err)?;
    let i64_bytes = |xs: Vec<u32>| -> PyResult<Bound<'py, PyBytes>> {
        PyBytes::new_with(py, 8 * xs.len(), |buf| {
            for (chunk, x) in buf.chunks_exact_mut(8).zip(&xs) {
                chunk.copy_from_slice(&(*x as i64).to_le_bytes());
            }
            Ok(())
        })
    };
    Ok((i64_bytes(c.segments.iter().flatten().copied().collect())?,
        i64_bytes(c.triangles.iter().flatten().copied().collect())?,
        i64_bytes(c.triangle_facet)?, c.pairs_tested))
}

#[pymodule]
fn _kernel(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(version, m)?)?;
    m.add_function(wrap_pyfunction!(two_product_probe, m)?)?;
    m.add_function(wrap_pyfunction!(predicate_signs, m)?)?;
    m.add_function(wrap_pyfunction!(tetrahedralize, m)?)?;
    m.add_function(wrap_pyfunction!(verify_delaunay, m)?)?;
    m.add_function(wrap_pyfunction!(triangulate_facet, m)?)?;
    m.add_function(wrap_pyfunction!(check_plc, m)?)?;
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
