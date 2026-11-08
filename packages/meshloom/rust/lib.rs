// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

//! Compiled kernel of meshloom: exact geometric predicates and the Delaunay
//! tetrahedralization (internal building blocks; the public mesher comes later).
//! Arrays cross the boundary as little-endian bytes, so the extension needs no
//! array crate; the Python side wraps them in numpy arrays.

mod bigint;
mod delaunay;
#[cfg(test)]
mod exact_ref;
mod facet;
mod facetrec;
mod mesh;
mod mixed;
mod plc;
mod predicates;
mod recovery;
mod refine;

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

/// Exact signs of one predicate over a batch of mixed points: `coords` the input
/// points (n x 3 doubles), `seg` the S points' segment ends (m x 2 int64) and `t` their
/// parameters (m doubles), `query` the global indices of each group (input points
/// 0..n, S points n..n+m). Returns (signs as int8 bytes, counters).
#[pyfunction]
#[pyo3(signature = (kind, coords, seg, t, query, axis=2))]
fn mixed_signs<'py>(py: Python<'py>, kind: &str, coords: &Bound<'py, PyBytes>, seg: &Bound<'py, PyBytes>,
                    t: &Bound<'py, PyBytes>, query: &Bound<'py, PyBytes>, axis: usize)
                    -> PyResult<(Bound<'py, PyBytes>, Bound<'py, PyDict>)> {
    check_environment()?;
    let k = match kind {
        "orient2d_proj" => 3,
        "orient3d" | "incircle_plane" | "incircle_plane_sos" => 4,
        "insphere" | "insphere_sos" => 5,
        _ => return Err(PyValueError::new_err(format!("unknown predicate {kind:?}"))),
    };
    if axis > 2 {
        return Err(PyValueError::new_err("axis must be 0, 1 or 2"));
    }
    let input = points(coords.as_bytes())?;
    if let Err(e) = delaunay::check_input(&input) {
        return Err(PyValueError::new_err(e.to_string()));
    }
    let ends = u32s(seg.as_bytes(), "segment end")?;
    let ts = f64s(t.as_bytes());
    if ends.len() != 2 * ts.len() {
        return Err(PyValueError::new_err("seg must hold 2 indices per S point and t one value"));
    }
    let s: Vec<mixed::SPoint> = ts.iter().enumerate()
        .map(|(j, &t)| mixed::SPoint::seg(ends[2 * j], ends[2 * j + 1], t)).collect();
    mixed::check_spoints(&input, &s).map_err(PyValueError::new_err)?;
    let q = u32s(query.as_bytes(), "query index")?;
    if q.len() % k != 0 {
        return Err(PyValueError::new_err(format!("{kind} takes groups of {k} points")));
    }
    let total = (input.len() + s.len()) as u32;
    if let Some(bad) = q.iter().find(|&&i| i >= total) {
        return Err(PyValueError::new_err(format!("query index {bad} refers to no point")));
    }
    let kind = kind.to_owned();
    let (out, n) = py.detach(move || {
        let m = mixed::Mixed { input: &input, s: &s };
        let mut n = mixed::MixedCounters::default();
        let out: Vec<u8> = q.chunks_exact(k).map(|g| {
            let p: Vec<mixed::Pt> = g.iter().map(|&i| m.from_id(i)).collect();
            let s = match kind.as_str() {
                "orient3d" => m.orient3d([p[0], p[1], p[2], p[3]], &mut n),
                "insphere" => m.insphere([p[0], p[1], p[2], p[3], p[4]], &mut n),
                "insphere_sos" => m.insphere_sos([p[0], p[1], p[2], p[3], p[4]], &mut n),
                "orient2d_proj" => m.orient2d_proj(axis, [p[0], p[1], p[2]], &mut n),
                "incircle_plane" => m.incircle_plane(axis, [p[0], p[1], p[2], p[3]], &mut n),
                _ => m.incircle_plane_sos(axis, [p[0], p[1], p[2], p[3]], &mut n),
            };
            s as u8
        }).collect();
        (out, n)
    });
    let d = PyDict::new(py);
    d.set_item("calls", n.calls)?;
    d.set_item("interval", n.interval)?;
    d.set_item("exact", n.exact)?;
    d.set_item("sos", n.sos)?;
    Ok((PyBytes::new(py, &out), d))
}

/// The output coordinates of S points: each coordinate of points[a] + t (points[b] -
/// points[a]) rounded once to the nearest double. Returns m x 3 doubles.
#[pyfunction]
fn spoint_coords<'py>(py: Python<'py>, coords: &Bound<'py, PyBytes>, seg: &Bound<'py, PyBytes>,
                      t: &Bound<'py, PyBytes>) -> PyResult<Bound<'py, PyBytes>> {
    check_environment()?;
    let input = points(coords.as_bytes())?;
    let ends = u32s(seg.as_bytes(), "segment end")?;
    let ts = f64s(t.as_bytes());
    if ends.len() != 2 * ts.len() {
        return Err(PyValueError::new_err("seg must hold 2 indices per S point and t one value"));
    }
    let s: Vec<mixed::SPoint> = ts.iter().enumerate()
        .map(|(j, &t)| mixed::SPoint::seg(ends[2 * j], ends[2 * j + 1], t)).collect();
    mixed::check_spoints(&input, &s).map_err(PyValueError::new_err)?;
    let m = mixed::Mixed { input: &input, s: &s };
    let out: Vec<f64> = (0..s.len() as u32).flat_map(|j| m.rounded(mixed::Pt::S(j))).collect();
    Ok(PyBytes::new(py, &out.iter().flat_map(|x| x.to_le_bytes()).collect::<Vec<u8>>()))
}

/// Segment recovery: `coords` n x 3 doubles, `segments` m x 2 int64 (elementary,
/// non-crossing), `max_depth` the halving limit per piece. Returns (tetrahedra T x 4,
/// S points' segments k x 2 and parameters k, chain lengths m and the concatenated
/// chains as int64 bytes, statistics).
#[pyfunction]
#[pyo3(signature = (coords, segments, max_depth=60))]
#[allow(clippy::type_complexity)]
fn recover_segments<'py>(py: Python<'py>, coords: &Bound<'py, PyBytes>, segments: &Bound<'py, PyBytes>, max_depth: u32)
    -> PyResult<(Bound<'py, PyBytes>, Bound<'py, PyBytes>, Bound<'py, PyBytes>, Bound<'py, PyBytes>,
                 Bound<'py, PyBytes>, Bound<'py, PyDict>)> {
    check_environment()?;
    let pts = points(coords.as_bytes())?;
    let seg = u32s(segments.as_bytes(), "segment index")?;
    if seg.len() % 2 != 0 {
        return Err(PyValueError::new_err("segments must hold 2 indices each"));
    }
    let segs: Vec<[u32; 2]> = seg.chunks_exact(2).map(|c| [c[0], c[1]]).collect();
    let r = py.detach(move || recovery::recover(&pts, &segs, max_depth)).map_err(|e| match e {
        delaunay::Error::Internal(_) => PyRuntimeError::new_err(e.to_string()),
        _ => PyValueError::new_err(e.to_string()),
    })?;
    let i64_bytes = |xs: Vec<u32>| -> PyResult<Bound<'py, PyBytes>> {
        PyBytes::new_with(py, 8 * xs.len(), |buf| {
            for (chunk, x) in buf.chunks_exact_mut(8).zip(&xs) {
                chunk.copy_from_slice(&(*x as i64).to_le_bytes());
            }
            Ok(())
        })
    };
    let tets = i64_bytes(r.tets.iter().flatten().copied().collect())?;
    let sseg = i64_bytes(r.s.iter().flat_map(|s| [s.a, s.b]).collect())?;
    let st: Vec<u8> = r.s.iter().flat_map(|s| s.t.to_le_bytes()).collect();
    let lens = i64_bytes(r.chains.iter().map(|c| c.len() as u32).collect())?;
    let chains = i64_bytes(r.chains.iter().flatten().copied().collect())?;
    let d = PyDict::new(py);
    d.set_item("rounds", r.stats.rounds)?;
    d.set_item("protected_vertices", r.stats.protected_vertices)?;
    d.set_item("protection_points", r.stats.protection_points)?;
    d.set_item("bisection_points", r.stats.bisection_points)?;
    d.set_item("max_depth", r.stats.max_depth)?;
    d.set_item("exact_points", r.stats.exact_points)?;
    d.set_item("mixed_calls", r.mixed.calls)?;
    d.set_item("mixed_interval", r.mixed.interval)?;
    d.set_item("mixed_exact", r.mixed.exact)?;
    d.set_item("mixed_sos", r.mixed.sos)?;
    d.set_item("input_exact", r.kernel.predicates.orient3d_exact + r.kernel.predicates.insphere_exact)?;
    d.set_item("walk_steps", r.kernel.walk_steps)?;
    d.set_item("cavity_tets", r.kernel.cavity_tets)?;
    d.set_item("inserted", r.kernel.inserted)?;
    Ok((tets, sseg, PyBytes::new(py, &st), lens, chains, d))
}

/// Boundary recovery so far: the PLC check, segment recovery, then every facet's
/// subfacets with the points added on its sub-segments. Returns (tetrahedra T x 4, S
/// points' segments k x 2 and parameters k, subfacets F x 3 with their facet F, missing
/// subfacets as indices into those, statistics).
#[pyfunction]
#[pyo3(signature = (coords, segments, facets, max_depth=60))]
#[allow(clippy::type_complexity)]
fn recover_plc<'py>(py: Python<'py>, coords: &Bound<'py, PyBytes>, segments: &Bound<'py, PyBytes>,
                    facets: Vec<Vec<Bound<'py, PyBytes>>>, max_depth: u32)
    -> PyResult<(Bound<'py, PyBytes>, Bound<'py, PyBytes>, Bound<'py, PyBytes>, Bound<'py, PyBytes>,
                 Bound<'py, PyBytes>, Bound<'py, PyBytes>, Bound<'py, PyDict>)> {
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
    let r = py.detach(move || recovery::recover_plc(&plc, max_depth)).map_err(PyValueError::new_err)?;
    let i64_bytes = |xs: Vec<u32>| -> PyResult<Bound<'py, PyBytes>> {
        PyBytes::new_with(py, 8 * xs.len(), |buf| {
            for (chunk, x) in buf.chunks_exact_mut(8).zip(&xs) {
                chunk.copy_from_slice(&(*x as i64).to_le_bytes());
            }
            Ok(())
        })
    };
    let mut sub = Vec::new();
    let mut owner = Vec::new();
    let mut index = std::collections::HashMap::new();
    for (f, tris) in r.subfacets.iter().enumerate() {
        for t in tris {
            index.insert((f as u32, *t), owner.len() as u32);
            sub.extend(t);
            owner.push(f as u32);
        }
    }
    let missing: Vec<u32> = r.missing.iter().map(|k| index[k]).collect();
    let d = PyDict::new(py);
    d.set_item("protection_points", r.rec.stats.protection_points)?;
    d.set_item("bisection_points", r.rec.stats.bisection_points)?;
    d.set_item("subfacets", owner.len())?;
    d.set_item("missing", missing.len())?;
    d.set_item("plane_exact", r.plane.exact)?;
    Ok((i64_bytes(r.rec.tets.iter().flatten().copied().collect())?,
        i64_bytes(r.rec.s.iter().flat_map(|s| [s.a, s.b]).collect())?,
        PyBytes::new(py, &r.rec.s.iter().flat_map(|s| s.t.to_le_bytes()).collect::<Vec<u8>>()),
        i64_bytes(sub)?, i64_bytes(owner)?, i64_bytes(missing)?, d))
}

/// Boundary recovery of a PLC (segments and facets): like `recover_plc`, then facet
/// recovery by cavity gift-wrapping and the constrained Delaunay verifier. Returns
/// (tetrahedra, S segments, S parameters, subfacets, subfacet facet, statistics).
#[pyfunction]
fn recover_boundary<'py>(py: Python<'py>, coords: &Bound<'py, PyBytes>, segments: &Bound<'py, PyBytes>,
                         facets: Vec<Vec<Bound<'py, PyBytes>>>, max_depth: u32)
    -> PyResult<(Bound<'py, PyBytes>, Bound<'py, PyBytes>, Bound<'py, PyBytes>, Bound<'py, PyBytes>,
                 Bound<'py, PyBytes>, Bound<'py, PyDict>)> {
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
    let r = py.detach(move || facetrec::recover_boundary(&plc, max_depth)).map_err(PyValueError::new_err)?;
    let i64_bytes = |xs: Vec<u32>| -> PyResult<Bound<'py, PyBytes>> {
        PyBytes::new_with(py, 8 * xs.len(), |buf| {
            for (chunk, x) in buf.chunks_exact_mut(8).zip(&xs) {
                chunk.copy_from_slice(&(*x as i64).to_le_bytes());
            }
            Ok(())
        })
    };
    let mut sub = Vec::new();
    let mut owner = Vec::new();
    for (f, tris) in r.plc.subfacets.iter().enumerate() {
        for t in tris {
            sub.extend(t);
            owner.push(f as u32);
        }
    }
    let d = PyDict::new(py);
    d.set_item("protection_points", r.plc.rec.stats.protection_points)?;
    d.set_item("bisection_points", r.plc.rec.stats.bisection_points)?;
    d.set_item("subfacets", owner.len())?;
    d.set_item("missing_after_segments", r.plc.missing.len())?;
    d.set_item("regions", r.stats.regions)?;
    d.set_item("removed", r.stats.removed)?;
    d.set_item("created", r.stats.created)?;
    d.set_item("enlargements", r.stats.enlargements)?;
    d.set_item("blocked", r.stats.blocked)?;
    d.set_item("apexes", r.stats.apexes)?;
    d.set_item("largest_cavity", r.stats.largest_cavity)?;
    d.set_item("fast_sides", r.stats.fast)?;
    d.set_item("wrapped_sides", r.stats.wrapped)?;
    d.set_item("constrained_faces", r.report.constrained_faces)?;
    d.set_item("delaunay_faces", r.report.delaunay_faces)?;
    d.set_item("hull_faces", r.report.hull_faces)?;
    d.set_item("tetrahedra", r.report.tets)?;
    d.set_item("mixed_exact", r.mixed.exact)?;
    Ok((i64_bytes(r.tets.iter().flatten().copied().collect())?,
        i64_bytes(r.plc.rec.s.iter().flat_map(|s| [s.a, s.b]).collect())?,
        PyBytes::new(py, &r.plc.rec.s.iter().flat_map(|s| s.t.to_le_bytes()).collect::<Vec<u8>>()),
        i64_bytes(sub)?, i64_bytes(owner)?, d))
}

/// Boundary recovery, regions, rounding and certification of a PLC. `domain` is
/// "regions" (every bounded component a region) or "parity" (the even-odd domain of
/// closed surfaces). Returns (nodes N x 3 doubles, tetrahedra, regions, boundary
/// facet per face, boundary faces, interface region pairs, interface faces, node
/// sources, region count) as bytes, and counters.
#[pyfunction]
#[pyo3(signature = (coords, segments, facets, domain, max_depth, h=0.0, ratio=0.0, alpha=1.0, max_points=0))]
#[allow(clippy::too_many_arguments)]
fn mesh_plc<'py>(py: Python<'py>, coords: &Bound<'py, PyBytes>, segments: &Bound<'py, PyBytes>,
                 facets: Vec<Vec<Bound<'py, PyBytes>>>, domain: &str, max_depth: u32, h: f64, ratio: f64,
                 alpha: f64, max_points: usize)
    -> PyResult<(Vec<Bound<'py, PyBytes>>, Bound<'py, PyDict>)> {
    check_environment()?;
    let domain = match domain {
        "regions" => mesh::Domain::Regions,
        "parity" => mesh::Domain::Parity,
        _ => return Err(PyValueError::new_err("domain must be 'regions' or 'parity'")),
    };
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
    // errors: ("RecoveryFail" | "NotClosed" | "RoundingFail" | "Internal", message, ids)
    let (m, b, rs) = py.detach(move || -> Result<_, (&'static str, String, Vec<u32>)> {
        let mut b = facetrec::recover_boundary(&plc, max_depth).map_err(|e| ("RecoveryFail", e, vec![]))?;
        let mut rs = refine::RefineStats::default();
        if h > 0.0 || ratio > 0.0 {
            let opt = refine::RefineOptions { h, alpha, ratio, max_points: if max_points > 0 { max_points } else { 5_000_000 } };
            rs = refine::refine(&plc, &mut b, opt).map_err(|e| ("RefineFail", e, vec![]))?;
        }
        let m = mesh::build(&plc.points, &b, domain).map_err(|e| match &e {
            mesh::MeshError::NotClosed { segment, facets } => {
                ("NotClosed", e.to_string(), segment.iter().chain(facets).copied().collect())
            }
            mesh::MeshError::Rounding(_) => ("RoundingFail", e.to_string(), vec![]),
            mesh::MeshError::Internal(_) => ("Internal", e.to_string(), vec![]),
        })?;
        Ok((m, b.stats, rs))
    }).map_err(|(kind, msg, ids)| PyValueError::new_err((kind, msg, ids)))?;
    let i64_bytes = |xs: Vec<u32>| -> PyResult<Bound<'py, PyBytes>> {
        PyBytes::new_with(py, 8 * xs.len(), |buf| {
            for (chunk, x) in buf.chunks_exact_mut(8).zip(&xs) {
                chunk.copy_from_slice(&(*x as i64).to_le_bytes());
            }
            Ok(())
        })
    };
    let out = vec![
        PyBytes::new(py, &m.nodes.iter().flatten().flat_map(|x| x.to_le_bytes()).collect::<Vec<u8>>()),
        i64_bytes(m.tets.iter().flatten().copied().collect())?,
        i64_bytes(m.regions.clone())?,
        i64_bytes(m.boundary.iter().map(|b| b.0).collect())?,
        i64_bytes(m.boundary.iter().flat_map(|b| b.1).collect())?,
        i64_bytes(m.interfaces.iter().flat_map(|i| [i.0, i.1]).collect())?,
        i64_bytes(m.interfaces.iter().flat_map(|i| i.2).collect())?,
        i64_bytes(m.source.clone())?,
    ];
    let d = PyDict::new(py);
    d.set_item("region_count", m.region_count)?;
    d.set_item("segment_points", rs.segment_points)?;
    d.set_item("facet_points", rs.facet_points)?;
    d.set_item("volume_points", rs.volume_points)?;
    d.set_item("rejected_points", rs.rejected)?;
    d.set_item("inverted_after_rounding", m.repair.inverted)?;
    d.set_item("flips23", m.repair.flips23)?;
    d.set_item("flips32", m.repair.flips32)?;
    d.set_item("regions_filled", b.regions)?;
    d.set_item("cavity_tetrahedra", b.removed)?;
    Ok((out, d))
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
    let f = py.detach(move || facet::triangulate(&pts, &loops)).map_err(|e| PyValueError::new_err(e.msg))?;
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
                  -> PyResult<(Bound<'py, PyBytes>, Bound<'py, PyBytes>, Bound<'py, PyBytes>,
                               Bound<'py, PyBytes>, Bound<'py, PyBytes>, usize)> {
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
    // a refusal carries (message, witness type or None, detail kind, detail indices)
    let c = py.detach(move || plc::check(&plc)).map_err(|e| {
        use facet::{At, Detail};
        let (kind, ids): (&str, Vec<i64>) = match &e.detail {
            Detail::None => ("", vec![]),
            Detail::NoFacets => ("no facets", vec![]),
            Detail::Vertex(i) => ("vertex", vec![*i as i64]),
            Detail::Facet(f) => ("facet", vec![*f as i64]),
            Detail::Facets(f, g) => ("facets", vec![*f as i64, *g as i64]),
            Detail::Point { cells: (f, g), at } => {
                let (kind, pieces): (&str, Vec<u32>) = match at {
                    At::Centroid(v) => ("centroid", v.clone()),
                    At::SegSeg(a, b) => ("segseg", a.iter().chain(b).copied().collect()),
                    At::SegTri(a, b) => ("segtri", a.iter().chain(b).copied().collect()),
                    At::TriTri(a, b) => ("tritri", a.iter().chain(b).copied().collect()),
                };
                // each cell as two numbers: (-1, facet) or a free segment's ends
                let cell = |c: &facet::CellRef| match c {
                    facet::CellRef::Facet(f) => [-1, *f as i64],
                    facet::CellRef::Segment([u, v]) => [*u as i64, *v as i64],
                };
                (kind, cell(f).into_iter().chain(cell(g)).chain(pieces.iter().map(|&x| x as i64)).collect())
            }
        };
        PyValueError::new_err((e.msg, e.witness, kind, ids))
    })?;
    let i64_bytes = |xs: Vec<u32>| -> PyResult<Bound<'py, PyBytes>> {
        PyBytes::new_with(py, 8 * xs.len(), |buf| {
            for (chunk, x) in buf.chunks_exact_mut(8).zip(&xs) {
                chunk.copy_from_slice(&(*x as i64).to_le_bytes());
            }
            Ok(())
        })
    };
    Ok((i64_bytes(c.segments.iter().flatten().copied().collect())?,
        i64_bytes(c.subsegments.iter().flatten().copied().collect())?,
        i64_bytes(c.triangles.iter().flatten().copied().collect())?,
        i64_bytes(c.triangle_facet)?,
        i64_bytes(c.open_subsegments.iter().flatten().copied().collect())?, c.pairs_tested))
}

#[pymodule]
fn _kernel(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(version, m)?)?;
    m.add_function(wrap_pyfunction!(two_product_probe, m)?)?;
    m.add_function(wrap_pyfunction!(predicate_signs, m)?)?;
    m.add_function(wrap_pyfunction!(mixed_signs, m)?)?;
    m.add_function(wrap_pyfunction!(spoint_coords, m)?)?;
    m.add_function(wrap_pyfunction!(recover_segments, m)?)?;
    m.add_function(wrap_pyfunction!(recover_plc, m)?)?;
    m.add_function(wrap_pyfunction!(recover_boundary, m)?)?;
    m.add_function(wrap_pyfunction!(mesh_plc, m)?)?;
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
