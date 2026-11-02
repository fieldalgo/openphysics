// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

//! Delaunay tetrahedralization of a point set by Bowyer–Watson insertion.
//!
//! Storage is one flat index array: four vertex indices and four neighbour links per
//! tetrahedron, interleaved, a link being `4 * neighbour + slot` so the back pointer needs no
//! search; neighbour i is across the face opposite vertex i. A ghost vertex closes
//! the hull: the ghost tetrahedron `(a, b, c, GHOST)` stands for the outside beyond
//! hull face abc, wound so that replacing GHOST by a point beyond the face gives a
//! positive tetrahedron, and the ghost always sits in slot 3. Every tetrahedron thus
//! obeys one rule: replacing vertex i by p keeps it positive iff p is on vertex i's
//! side of face i.
//!
//! Points are inserted in a biased randomized order (BRIO, Amenta–Choi–Rote 2003)
//! with Hilbert order inside each round (Skilling 2004), located by a visibility walk
//! (Devillers–Pion–Teillaud 2002) and inserted by carving the conflict cavity.
//! insphere ties are broken by the index-ordered symbolic perturbation of
//! [`predicates::insphere_sos`], so the result is a function of the points and their
//! indices only, not of the insertion order.

use crate::predicates::{self as pr, Counters, P3};

pub const GHOST: u32 = u32::MAX;
const FREE: u32 = u32::MAX - 1;

#[derive(Clone, Copy, Debug, Default)]
pub struct Stats {
    pub predicates: Counters,
    pub inserted: u64,
    pub duplicates: u64,
    pub walk_steps: u64,
    pub walk_fallbacks: u64,
    pub cavity_tets: u64,
}

#[derive(Debug)]
pub enum Error {
    Degenerate(&'static str),
    Domain(usize),
    TooMany,
    Order(&'static str),
    Internal(String),
}

impl std::fmt::Display for Error {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Error::Degenerate(s) => write!(f, "degenerate input: {s}"),
            Error::Domain(i) => write!(f, "point {i} has a coordinate that is not finite or outside \
                                             0 or [2^-120, 2^120] in magnitude"),
            Error::TooMany => write!(f, "too many points for 32-bit vertex indices"),
            Error::Order(s) => write!(f, "invalid insertion order: {s}"),
            Error::Internal(s) => write!(f, "internal error: {s}"),
        }
    }
}

pub struct Output {
    /// Finite tetrahedra, positively oriented.
    pub tets: Vec<[u32; 4]>,
    /// For each input point, the vertex it duplicates, or itself.
    pub vertex_of: Vec<u32>,
    pub stats: Stats,
}

struct Mesh<'a> {
    pts: &'a [P3],
    // per tetrahedron: 4 vertices, then 4 links (interleaved, so one cache line holds both)
    data: Vec<u32>,
    mark: Vec<u32>,
    free: Vec<u32>,
    epoch: u32,
    last: u32,
    rng: u64,
    stats: Stats,
    stack: Vec<u32>,
    cavity: Vec<u32>,
    boundary: Vec<([u32; 4], u32, u32)>,
    // open-addressing table that pairs the new tetrahedra by cavity boundary edge;
    // `glue_stamp` marks the live entries of the current insertion
    glue: Vec<(u64, u32)>,
    glue_stamp: Vec<u32>,
}

enum Located {
    Tet(u32),
    Duplicate(u32),
}

pub fn check_input(pts: &[P3]) -> Result<(), Error> {
    if pts.len() >= (FREE - 1) as usize {
        return Err(Error::TooMany);
    }
    for (i, p) in pts.iter().enumerate() {
        if !p.iter().all(|x| x.is_finite() && pr::in_domain(*x)) {
            return Err(Error::Domain(i));
        }
    }
    Ok(())
}

/// Delaunay tetrahedralization of `pts`. `order`, when given, is the insertion order
/// (a permutation of all indices); otherwise BRIO with Hilbert rounds is used.
pub fn tetrahedralize(pts: &[P3], order: Option<&[u32]>) -> Result<Output, Error> {
    check_input(pts)?;
    let order: Vec<u32> = match order {
        Some(o) => {
            let mut seen = vec![false; pts.len()];
            if o.len() != pts.len() {
                return Err(Error::Order("length differs from the number of points"));
            }
            for &i in o {
                if i as usize >= pts.len() || seen[i as usize] {
                    return Err(Error::Order("not a permutation of the point indices"));
                }
                seen[i as usize] = true;
            }
            o.to_vec()
        }
        None => brio_order(pts),
    };
    // equal points: the lowest index is the vertex, the others are left out
    let mut vertex_of: Vec<u32> = (0..pts.len() as u32).collect();
    let mut by_point: Vec<u32> = vertex_of.clone();
    by_point.sort_unstable_by(|&i, &j| pr::lex_cmp(&pts[i as usize], &pts[j as usize]).then(i.cmp(&j)));
    for w in by_point.windows(2) {
        if pr::same_point(&pts[w[0] as usize], &pts[w[1] as usize]) {
            vertex_of[w[1] as usize] = vertex_of[w[0] as usize];
        }
    }
    let order: Vec<u32> = order.into_iter().filter(|&i| vertex_of[i as usize] == i).collect();
    let mut m = Mesh::new(pts);
    m.stats.duplicates = (pts.len() - order.len()) as u64;
    let first = m.start(&order)?;
    for &i in &order {
        if first.contains(&i) {
            continue;
        }
        if let Some(v) = m.insert(i)? {
            return Err(Error::Internal(format!("point {i} equals vertex {v} after deduplication")));
        }
    }
    m.stats.inserted += 4;
    let mut tets = Vec::with_capacity(m.data.len() / 8);
    for t in 0..m.data.len() / 8 {
        let v = &m.data[8 * t..8 * t + 4];
        if v[0] != FREE && v[3] != GHOST {
            tets.push([v[0], v[1], v[2], v[3]]);
        }
    }
    Ok(Output { tets, vertex_of, stats: m.stats })
}

impl<'a> Mesh<'a> {
    fn new(pts: &'a [P3]) -> Self {
        let cap = 7 * pts.len() + 16;
        Mesh {
            pts,
            data: Vec::with_capacity(8 * cap),
            mark: Vec::with_capacity(cap),
            free: Vec::new(),
            epoch: 0,
            last: 0,
            rng: 0x9E37_79B9_7F4A_7C15,
            stats: Stats::default(),
            stack: Vec::new(),
            cavity: Vec::new(),
            boundary: Vec::new(),
            glue: Vec::new(),
            glue_stamp: Vec::new(),
        }
    }

    #[inline]
    fn p(&self, v: u32) -> &'a P3 {
        &self.pts[v as usize]
    }

    fn alloc(&mut self, v: [u32; 4]) -> u32 {
        if let Some(t) = self.free.pop() {
            self.data[8 * t as usize..8 * t as usize + 4].copy_from_slice(&v);
            t
        } else {
            let t = (self.data.len() / 8) as u32;
            self.data.extend_from_slice(&v);
            self.data.extend_from_slice(&[u32::MAX; 4]);
            self.mark.push(0);
            t
        }
    }

    #[inline(always)]
    fn adj(&self, link: u32) -> u32 {
        self.data[(8 * (link >> 2) + 4 + (link & 3)) as usize]
    }

    #[inline(always)]
    fn set_adj(&mut self, link: u32, to: u32) {
        self.data[(8 * (link >> 2) + 4 + (link & 3)) as usize] = to;
    }

    #[inline]
    fn verts(&self, t: u32) -> [u32; 4] {
        let i = 8 * t as usize;
        [self.data[i], self.data[i + 1], self.data[i + 2], self.data[i + 3]]
    }

    #[inline]
    fn next_rand(&mut self) -> u64 {
        // xorshift64*: a fixed sequence, so runs are reproducible
        self.rng ^= self.rng >> 12;
        self.rng ^= self.rng << 25;
        self.rng ^= self.rng >> 27;
        self.rng.wrapping_mul(0x2545_F491_4F6C_DD1D)
    }

    /// First tetrahedron from the first affinely independent points of `order`.
    fn start(&mut self, order: &[u32]) -> Result<[u32; 4], Error> {
        let n = &mut Counters::default();
        let a = *order.first().ok_or(Error::Degenerate("fewer than 4 points"))?;
        let pa = self.p(a);
        let b = *order.iter().find(|&&i| !pr::same_point(self.p(i), pa))
            .ok_or(Error::Degenerate("all points coincide"))?;
        let pb = self.p(b);
        let c = *order.iter().find(|&&i| !pr::collinear(pa, pb, self.p(i)))
            .ok_or(Error::Degenerate("all points are collinear"))?;
        let pc = self.p(c);
        let d = *order.iter().find(|&&i| pr::orient3d(pa, pb, pc, self.p(i), n) != 0)
            .ok_or(Error::Degenerate("all points are coplanar"))?;
        let (c, d) = if pr::orient3d(pa, pb, pc, self.p(d), n) > 0 { (c, d) } else { (d, c) };
        self.stats.predicates.orient3d += n.orient3d;
        self.stats.predicates.orient3d_exact += n.orient3d_exact;

        let v = [a, b, c, d];
        let t0 = self.alloc(v);
        let mut ghosts = [0u32; 4];
        for (i, g) in ghosts.iter_mut().enumerate() {
            let gv = if i == 3 {
                [v[1], v[0], v[2], GHOST]
            } else {
                let mut w = v;
                w[i] = v[3];
                w[3] = GHOST;
                w
            };
            *g = self.alloc(gv);
            self.set_adj(4 * t0 + i as u32, 4 * *g + 3);
            self.set_adj(4 * *g + 3, 4 * t0 + i as u32);
        }
        // glue the ghosts to each other by their faces through GHOST
        let mut faces: Vec<([u32; 3], u32)> = Vec::new();
        for &g in &ghosts {
            let w = self.verts(g);
            for j in 0..3 {
                let mut f = [0u32; 3];
                let mut k = 0;
                for (s, &x) in w.iter().enumerate() {
                    if s != j {
                        f[k] = x;
                        k += 1;
                    }
                }
                f.sort_unstable();
                faces.push((f, 4 * g + j as u32));
            }
        }
        faces.sort_unstable();
        for pair in faces.chunks(2) {
            if pair.len() != 2 || pair[0].0 != pair[1].0 {
                return Err(Error::Internal("initial ghosts do not pair up".into()));
            }
            self.set_adj(pair[0].1, pair[1].1);
            self.set_adj(pair[1].1, pair[0].1);
        }
        self.last = t0;
        Ok(v)
    }

    /// True when tetrahedron t conflicts with point index q.
    #[inline]
    fn conflict(&mut self, t: u32, q: u32) -> bool {
        let v = self.verts(t);
        let pq = self.p(q);
        if v[3] == GHOST {
            let o = pr::orient3d(self.p(v[0]), self.p(v[1]), self.p(v[2]), pq, &mut self.stats.predicates);
            if o != 0 {
                return o > 0;
            }
            // on the hull plane: the half-space is the limit of the sphere of the finite
            // tetrahedron across the face
            let nb = self.adj(4 * t + 3) >> 2;
            return self.conflict(nb, q);
        }
        let p = [self.p(v[0]), self.p(v[1]), self.p(v[2]), self.p(v[3]), pq];
        pr::insphere_sos(p, [v[0], v[1], v[2], v[3], q], &mut self.stats.predicates) > 0
    }

    fn locate(&mut self, q: u32) -> Result<Located, Error> {
        let pq = self.p(q);
        let mut t = self.last;
        let limit = self.data.len() / 8 + 16;
        let mut steps = 0usize;
        'walk: loop {
            let v = self.verts(t);
            if v[3] == GHOST {
                return Ok(Located::Tet(t));
            }
            let r = (self.next_rand() & 3) as usize;
            for k in 0..4 {
                let i = (r + k) & 3;
                let mut w = [self.p(v[0]), self.p(v[1]), self.p(v[2]), self.p(v[3])];
                w[i] = pq;
                if pr::orient3d(w[0], w[1], w[2], w[3], &mut self.stats.predicates) < 0 {
                    t = self.adj(4 * t + i as u32) >> 2;
                    steps += 1;
                    self.stats.walk_steps += 1;
                    if steps > limit {
                        break 'walk;
                    }
                    continue 'walk;
                }
            }
            return Ok(Located::Tet(t));
        }
        // a visibility walk cannot cycle in a Delaunay triangulation; scan as a guard
        self.stats.walk_fallbacks += 1;
        let mut outside = None;
        for t in 0..(self.data.len() / 8) as u32 {
            let v = self.verts(t);
            if v[0] == FREE {
                continue;
            }
            if v[3] == GHOST {
                if outside.is_none()
                    && pr::orient3d(self.p(v[0]), self.p(v[1]), self.p(v[2]), pq, &mut self.stats.predicates) > 0
                {
                    outside = Some(t);
                }
                continue;
            }
            if let Some(&x) = v.iter().find(|&&x| pr::same_point(self.p(x), pq)) {
                return Ok(Located::Duplicate(x));
            }
            let inside = (0..4).all(|i| {
                let mut w = [self.p(v[0]), self.p(v[1]), self.p(v[2]), self.p(v[3])];
                w[i] = pq;
                pr::orient3d(w[0], w[1], w[2], w[3], &mut self.stats.predicates) >= 0
            });
            if inside {
                return Ok(Located::Tet(t));
            }
        }
        outside.map(Located::Tet).ok_or_else(|| Error::Internal(format!("point {q} not located")))
    }

    /// Inserts point q; returns the vertex it duplicates, if any.
    fn insert(&mut self, q: u32) -> Result<Option<u32>, Error> {
        let t0 = match self.locate(q)? {
            Located::Duplicate(v) => return Ok(Some(v)),
            Located::Tet(t) => t,
        };
        self.epoch += 1;
        let (inside, outside) = (2 * self.epoch, 2 * self.epoch + 1);
        if !self.conflict(t0, q) {
            return Err(Error::Internal(format!("point {q}: the located tetrahedron is not in conflict")));
        }
        self.stack.clear();
        self.cavity.clear();
        self.boundary.clear();
        self.mark[t0 as usize] = inside;
        self.stack.push(t0);
        while let Some(c) = self.stack.pop() {
            self.cavity.push(c);
            for i in 0..4u32 {
                let link = self.adj(4 * c + i);
                let nb = link >> 2;
                let m = self.mark[nb as usize];
                if m == inside {
                    continue;
                }
                if m != outside {
                    if self.conflict(nb, q) {
                        self.mark[nb as usize] = inside;
                        self.stack.push(nb);
                        continue;
                    }
                    self.mark[nb as usize] = outside;
                }
                let mut v = self.verts(c);
                v[i as usize] = q;
                self.boundary.push((v, i, link));
            }
        }
        self.stats.cavity_tets += self.cavity.len() as u64;
        for k in 0..self.cavity.len() {
            let c = self.cavity[k];
            self.data[8 * c as usize] = FREE;
            self.free.push(c);
        }
        let want = (4 * self.boundary.len()).next_power_of_two().max(64);
        if self.glue.len() < want {
            self.glue = vec![(0, 0); want];
            self.glue_stamp = vec![0; want];
        }
        let mask = self.glue.len() - 1;
        let stamp = self.epoch;
        let mut finite = None;
        let mut pending = 0usize;
        for k in 0..self.boundary.len() {
            let (v, i, link) = self.boundary[k];
            let t = self.alloc(v);
            self.set_adj(4 * t + i, link);
            self.set_adj(link, 4 * t + i);
            for j in 0..4u32 {
                if j == i {
                    continue;
                }
                // the face opposite slot j holds q and the two vertices outside slots i, j
                let mut e = [0u32; 2];
                let mut m = 0;
                for s in 0..4u32 {
                    if s != i && s != j {
                        e[m] = v[s as usize];
                        m += 1;
                    }
                }
                let key = ((e[0].min(e[1]) as u64) << 32) | e[0].max(e[1]) as u64;
                let here = 4 * t + j;
                let mut h = (key.wrapping_mul(0x9E37_79B9_7F4A_7C15) >> 40) as usize & mask;
                loop {
                    if self.glue_stamp[h] != stamp {
                        self.glue_stamp[h] = stamp;
                        self.glue[h] = (key, here);
                        pending += 1;
                        break;
                    }
                    if self.glue[h].0 == key && self.glue[h].1 != u32::MAX {
                        let there = self.glue[h].1;
                        self.set_adj(here, there);
                        self.set_adj(there, here);
                        self.glue[h].1 = u32::MAX; // paired; the slot stays occupied for probing
                        pending -= 1;
                        break;
                    }
                    h = (h + 1) & mask;
                }
            }
            if v[3] != GHOST {
                finite = Some(t);
            }
        }
        if pending != 0 {
            return Err(Error::Internal(format!("point {q}: the cavity boundary is not a closed surface")));
        }
        self.last = finite.ok_or_else(|| Error::Internal(format!("point {q}: no finite tetrahedron created")))?;
        self.stats.inserted += 1;
        Ok(None)
    }
}

// ---------------------------------------------------------------- insertion order

fn splitmix64(mut x: u64) -> u64 {
    x = x.wrapping_add(0x9E37_79B9_7F4A_7C15);
    x = (x ^ (x >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
    x = (x ^ (x >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
    x ^ (x >> 31)
}

/// 3D Hilbert key of coordinates on `bits` bits per axis (Skilling 2004).
pub fn hilbert3(mut x: [u32; 3], bits: u32) -> u64 {
    let m = 1u32 << (bits - 1);
    let mut q = m;
    while q > 1 {
        let p = q - 1;
        for i in 0..3 {
            if x[i] & q != 0 {
                x[0] ^= p;
            } else {
                let t = (x[0] ^ x[i]) & p;
                x[0] ^= t;
                x[i] ^= t;
            }
        }
        q >>= 1;
    }
    for i in 1..3 {
        x[i] ^= x[i - 1];
    }
    let mut t = 0;
    q = m;
    while q > 1 {
        if x[2] & q != 0 {
            t ^= q - 1;
        }
        q >>= 1;
    }
    for xi in x.iter_mut() {
        *xi ^= t;
    }
    let mut key = 0u64;
    for b in (0..bits).rev() {
        for xi in x {
            key = (key << 1) | ((xi >> b) & 1) as u64;
        }
    }
    key
}

/// Biased randomized insertion order: point i joins round r with probability 2^-(r+1)
/// from a hash of i; rounds are inserted from the sparsest to the last half, each in
/// Hilbert order.
pub fn brio_order(pts: &[P3]) -> Vec<u32> {
    const BITS: u32 = 21;
    let n = pts.len();
    let rounds = (usize::BITS - n.max(2).leading_zeros()).max(1);
    let mut lo = [f64::INFINITY; 3];
    let mut hi = [f64::NEG_INFINITY; 3];
    for p in pts {
        for k in 0..3 {
            lo[k] = lo[k].min(p[k]);
            hi[k] = hi[k].max(p[k]);
        }
    }
    let scale: Vec<f64> = (0..3)
        .map(|k| if hi[k] > lo[k] { ((1u32 << BITS) - 1) as f64 / (hi[k] - lo[k]) } else { 0.0 })
        .collect();
    let mut keys: Vec<(u32, u64, u32)> = pts
        .iter()
        .enumerate()
        .map(|(i, p)| {
            let r = splitmix64(i as u64 ^ 0x6D65_7368_6C6F_6F6D).trailing_zeros().min(rounds - 1);
            let mut c = [0u32; 3];
            for k in 0..3 {
                c[k] = (((p[k] - lo[k]) * scale[k]) as u32).min((1u32 << BITS) - 1);
            }
            (rounds - 1 - r, hilbert3(c, BITS), i as u32)
        })
        .collect();
    keys.sort_unstable();
    keys.into_iter().map(|k| k.2).collect()
}

// ---------------------------------------------------------------- verification

#[derive(Clone, Copy, Debug, Default)]
pub struct Report {
    pub vertices: usize,
    pub edges: usize,
    pub faces: usize,
    pub tets: usize,
    pub hull_faces: usize,
    pub interior_faces: usize,
    pub predicates: Counters,
}

/// Checks that `tets` is the Delaunay tetrahedralization of the distinct points of
/// `pts` under the index-ordered perturbation, from the arrays alone: every
/// tetrahedron positive (exact); every face in one or two tetrahedra lying on its two
/// sides; every interior face locally Delaunay; every hull edge locally convex (on a
/// flat hull, locally Delaunay in the plane through the ghost rule); Euler
/// characteristic 1; every distinct point a vertex.
pub fn verify(pts: &[P3], tets: &[[u32; 4]]) -> Result<Report, String> {
    check_input(pts).map_err(|e| e.to_string())?;
    let mut n = Counters::default();
    let p = |v: u32| &pts[v as usize];
    for (t, v) in tets.iter().enumerate() {
        if v.iter().any(|&x| x as usize >= pts.len()) {
            return Err(format!("tetrahedron {t} has a vertex index out of range"));
        }
        if pr::orient3d(p(v[0]), p(v[1]), p(v[2]), p(v[3]), &mut n) <= 0 {
            return Err(format!("tetrahedron {t} is not positively oriented"));
        }
    }
    // faces: sorted vertex triple, tetrahedron, slot
    let mut faces: Vec<([u32; 3], u32, u8)> = Vec::with_capacity(4 * tets.len());
    for (t, v) in tets.iter().enumerate() {
        for i in 0..4 {
            let mut f = [0u32; 3];
            let mut k = 0;
            for (s, &x) in v.iter().enumerate() {
                if s != i {
                    f[k] = x;
                    k += 1;
                }
            }
            f.sort_unstable();
            faces.push((f, t as u32, i as u8));
        }
    }
    faces.sort_unstable();
    let mut report = Report { tets: tets.len(), ..Report::default() };
    // hull faces wound outward, with their tetrahedron
    let mut hull: Vec<([u32; 3], u32)> = Vec::new();
    let mut k = 0;
    while k < faces.len() {
        let mut j = k + 1;
        while j < faces.len() && faces[j].0 == faces[k].0 {
            j += 1;
        }
        report.faces += 1;
        match j - k {
            1 => {
                let (_, t, i) = faces[k];
                let v = tets[t as usize];
                let f = if i == 3 {
                    [v[1], v[0], v[2]]
                } else {
                    let mut w = v;
                    w[i as usize] = v[3];
                    [w[0], w[1], w[2]]
                };
                hull.push((f, t));
            }
            2 => {
                report.interior_faces += 1;
                let (_, t1, i1) = faces[k];
                let (_, t2, i2) = faces[k + 1];
                let v1 = tets[t1 as usize];
                let e = tets[t2 as usize][i2 as usize];
                let mut w = [p(v1[0]), p(v1[1]), p(v1[2]), p(v1[3])];
                w[i1 as usize] = p(e);
                if pr::orient3d(w[0], w[1], w[2], w[3], &mut n) >= 0 {
                    return Err(format!("tetrahedra {t1} and {t2} overlap across a shared face"));
                }
                let s = pr::insphere_sos([p(v1[0]), p(v1[1]), p(v1[2]), p(v1[3]), p(e)], [v1[0], v1[1], v1[2], v1[3], e], &mut n);
                if s >= 0 {
                    return Err(format!("face between tetrahedra {t1} and {t2} is not locally Delaunay"));
                }
            }
            _ => return Err(format!("face {:?} is shared by {} tetrahedra", faces[k].0, j - k)),
        }
        k = j;
    }
    report.hull_faces = hull.len();
    // hull edges: each directed edge once, paired with its reverse
    let mut dir: Vec<((u32, u32), u32)> = Vec::with_capacity(3 * hull.len());
    for (h, (f, _)) in hull.iter().enumerate() {
        for e in 0..3 {
            dir.push(((f[e], f[(e + 1) % 3]), h as u32));
        }
    }
    dir.sort_unstable();
    for w in dir.windows(2) {
        if w[0].0 == w[1].0 {
            return Err(format!("hull edge {:?} is used twice in the same direction", w[0].0));
        }
    }
    for &((a, b), h) in &dir {
        let other = match dir.binary_search_by(|x| x.0.cmp(&(b, a))) {
            Ok(i) => dir[i].1,
            Err(_) => return Err(format!("hull edge ({a}, {b}) has no opposite hull face")),
        };
        let (f, t) = hull[h as usize];
        let g = hull[other as usize].0;
        let e = *g.iter().find(|&&x| x != a && x != b).unwrap();
        let o = pr::orient3d(p(f[0]), p(f[1]), p(f[2]), p(e), &mut n);
        let convex = if o != 0 {
            o < 0
        } else {
            let v = tets[t as usize];
            pr::insphere_sos([p(v[0]), p(v[1]), p(v[2]), p(v[3]), p(e)], [v[0], v[1], v[2], v[3], e], &mut n) < 0
        };
        if !convex {
            return Err(format!("hull edge ({a}, {b}) is not locally convex"));
        }
    }
    let mut edges: Vec<(u32, u32)> = Vec::with_capacity(6 * tets.len());
    for v in tets {
        for i in 0..4 {
            for j in i + 1..4 {
                edges.push((v[i].min(v[j]), v[i].max(v[j])));
            }
        }
    }
    edges.sort_unstable();
    edges.dedup();
    report.edges = edges.len();
    let mut verts: Vec<u32> = tets.iter().flatten().copied().collect();
    verts.sort_unstable();
    verts.dedup();
    report.vertices = verts.len();
    let euler = report.vertices as i64 - report.edges as i64 + report.faces as i64 - report.tets as i64;
    if euler != 1 {
        return Err(format!("Euler characteristic {euler}, expected 1"));
    }
    let mut distinct: Vec<&P3> = pts.iter().collect();
    distinct.sort_unstable_by(|a, b| pr::lex_cmp(a, b));
    distinct.dedup_by(|a, b| pr::same_point(a, b));
    if distinct.len() != report.vertices {
        return Err(format!("{} distinct points but {} vertices", distinct.len(), report.vertices));
    }
    report.predicates = n;
    Ok(report)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn lcg(seed: &mut u64) -> f64 {
        *seed = seed.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
        (*seed >> 11) as f64 / (1u64 << 53) as f64
    }

    fn canonical(t: &[[u32; 4]]) -> Vec<[u32; 4]> {
        let mut c: Vec<[u32; 4]> = t.iter().map(|v| {
            let mut s = *v;
            s.sort_unstable();
            s
        }).collect();
        c.sort_unstable();
        c
    }

    #[test]
    fn random_points_give_a_verified_triangulation() {
        let mut s = 7u64;
        let pts: Vec<P3> = (0..2000).map(|_| [lcg(&mut s), lcg(&mut s), lcg(&mut s)]).collect();
        let out = tetrahedralize(&pts, None).unwrap();
        verify(&pts, &out.tets).unwrap();
        assert_eq!(out.stats.inserted, 2000);
    }

    #[test]
    fn lattice_is_order_independent() {
        let mut pts = Vec::new();
        for i in 0..6 {
            for j in 0..6 {
                for k in 0..6 {
                    pts.push([i as f64 * 0.1, j as f64 * 0.1, k as f64 * 0.1]);
                }
            }
        }
        let a = tetrahedralize(&pts, None).unwrap();
        verify(&pts, &a.tets).unwrap();
        let rev: Vec<u32> = (0..pts.len() as u32).rev().collect();
        let b = tetrahedralize(&pts, Some(&rev)).unwrap();
        assert_eq!(canonical(&a.tets), canonical(&b.tets));
        // a 5^3 cube of unit cells: volume 0.125 split into tetrahedra
        let vol: f64 = a.tets.iter().map(|v| {
            let p = |i: usize| pts[v[i] as usize];
            let (u, w, z) = (sub(p(1), p(0)), sub(p(2), p(0)), sub(p(3), p(0)));
            (u[0] * (w[1] * z[2] - w[2] * z[1]) + u[1] * (w[2] * z[0] - w[0] * z[2]) + u[2] * (w[0] * z[1] - w[1] * z[0])) / 6.0
        }).sum();
        assert!((vol - 0.125).abs() < 1e-12);
    }

    fn sub(a: P3, b: P3) -> P3 {
        [a[0] - b[0], a[1] - b[1], a[2] - b[2]]
    }

    #[test]
    fn duplicates_and_degenerate_inputs() {
        let mut pts = vec![[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0], [1.0, 0.0, 0.0]];
        let out = tetrahedralize(&pts, None).unwrap();
        assert_eq!(out.tets.len(), 1);
        assert_eq!(out.vertex_of[4], 1);
        verify(&pts, &out.tets).unwrap();
        pts[3] = [1.0, 1.0, 0.0];
        assert!(matches!(tetrahedralize(&pts, None), Err(Error::Degenerate(_))));
    }

    #[test]
    fn hilbert_keys_are_a_bijection_on_a_small_grid() {
        let mut keys: Vec<u64> = Vec::new();
        for i in 0..8 {
            for j in 0..8 {
                for k in 0..8 {
                    keys.push(hilbert3([i, j, k], 3));
                }
            }
        }
        keys.sort_unstable();
        assert_eq!(keys, (0..512).collect::<Vec<u64>>());
    }
}
