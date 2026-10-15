# galerkin — 전자기 FEM 엔진(FieldAlgo 프로젝트)

[English](README.md) | **한국어**

[영어·한국어 문서와 번역 상태](https://github.com/fieldalgo/openphysics/blob/develop/docs/locales/ko/pages/index.md)

해석해 검증을 먼저 수행하는 방식으로 단계별 개발한 순수 Python(numpy + scipy.sparse) 유한요소 솔버 엔진입니다. 현재 2D 전자기, 정적 2D 탄성, 3D 공진기 고유모드를 다루며 다중물리 코어로 확장하도록 설계했습니다.

- **M1**: 정전기 — ∇·(ε∇V) = −ρ(P1 요소)
- **M2**: 주파수 영역 파동 — ∇²u + k²u = 0(복소 연산, 흡수 경계)
- **M2.5**: 원통형 PML(복소 좌표 신장 → 이방성 텐서 계수)
- **M3-prep**: Nédélec 변 요소 — H(curl)에서 도파로 고유모드 ∇×∇×E = k_c²E
- **M3a**: 유전체 도파로 단면 모드 솔버 — 횡방향 Nédélec / 종방향 절점 혼합 정식화, 유효 굴절률과 벡터 모드 분포
- **M3b**: 3D Maxwell — 사면체 Nédélec 변 요소, 직육면체 공진기 고유모드

공개 `solve_cavity_box` API는 진공 PEC 상자의 SI 주파수와 원시 변 장을 제공합니다. 목표 근처 탐색의 한계와 직육면체 군집 평균 수렴 gate를 복구한 교대 메시를 포함하는 [API와 수치 계약](docs/cavity_solver.md)을 참조하세요.

독립 `galerkin.elasticity` 하위 모듈은 평면응력 또는 평면변형률을 명시적으로 선택하는 균질 등방성 소변형 정적 P1 탄성을 풉니다. [탄성 API·단위·한계](docs/elasticity2d.md)와 [영어 예제](examples/elasticity2d.py)를 참조하세요. 두 파일은 sdist에 포함됩니다. 예제는 패키지 설치 후 저장소 루트 또는 풀어 놓은 galerkin sdist에서 실행할 수 있으며 simcase/Studio 모델이 아닙니다. 별도 [독립 탄성 검증](docs/elasticity2d_independent_validation.md)은 다항 제조해, 혼합 경계, 일/에너지 검사를 설명하며 계약 문서도 sdist에 byte 동일하게 포함됩니다.

벡터 모드는 축퇴 고유공간 방향을 포함하는 복소 횡·종방향 계수를 보존합니다. 장을 실수로 바꾸기 전에 [고유공간 신뢰성 계약](docs/eigenspace_reliability.md)을 읽으세요. 부분공간 추적을 추가하는 기능은 아닙니다.

독립 `galerkin.thermal` API는 체적 열원과 자연 단열 경계를 갖는 균질 등방성 정상 2D 열전도를 Kelvin으로 풉니다. [열 계약과 경계 부호](docs/thermal_steady2d.md)를 읽고 설치 후 [영어 열전도 예제](examples/thermal_steady2d.py)를 실행하세요. [독립 열 검증](docs/thermal_independent_validation.md)과 [역사적 수용 manifest](docs/thermal_independent_validation_manifest.json)는 최초 기록을 그대로 보존하며 sdist에 byte 동일하게 포함합니다. 정적 탄성은 전역 Cartesian 경계 표면하중도 받습니다. [표면하중 안내](docs/elasticity_traction.md), [영어 표면하중 예제](examples/elasticity_traction.py), [독립 수용검증](docs/elasticity_traction_independent_validation.md)을 참조하세요. 이 문서와 예제는 sdist에 포함됩니다. 어느 API도 과도해석, 열탄성 연성, simcase 또는 Studio 통합을 추가하지 않습니다.

별도 `galerkin.thermoelasticity` 하위 모듈은 명시적으로 주어진 동일 메시 절점-P1 Kelvin 장의 정적 기계 단계입니다. [SI 계약·불변 snapshot·물리적 3D 에너지](docs/prescribed_temperature_thermoelasticity.md)와 [영어 실행 예제](examples/prescribed_temperature_thermoelasticity.py)를 참조하세요. 둘 다 sdist에 byte 동일하게 포함됩니다. Alpha는 부호 있는 1/K, 변위는 m, 응력은 Pa, 하중/반력은 N/m, 물리적 탄성에너지는 두께당 J/m입니다. 열 방정식을 풀거나 열 결과를 자동 연결하거나 완전한 순차 연성 흐름을 검증하거나 simcase/Studio 통합을 추가하지 않습니다. 별도 [독립 기계 단계 수용검증](docs/prescribed_temperature_thermoelasticity_independent_validation.md)과 원래 oracle/시험도 변경 없이 sdist에 포함됩니다.

## 구성

독립 정상 열 솔버를 감싸는 헤드리스 JSON/API/CLI는 [simcase 열 문서 계약](https://github.com/fieldalgo/openphysics/blob/4ec9da9fcba661958a12f37bc445a543cb4ffc1c/packages/simcase/docs/thermal_steady2d.md)을 참조하세요. 이 래퍼는 명시적 길이 단위, Kelvin 입력, 수치 SI 결과 파일을 다룹니다. 이 엔진에 열전도 Studio 인터페이스나 자동 열–기계 흐름을 추가하지 않습니다.

```
galerkin/
  mesh.py         # Mesh data structure (boundary nodes + edges) + structured mesh generators
  assembly.py     # Stiffness K (scalar/tensor coefficients), mass M, boundary B, load vector
  solver.py       # Dirichlet reduction + scipy sparse direct solve (real/complex)
  postprocess.py  # E = -grad V, L2 error (complex-aware)
  pml.py          # Cylindrical PML coefficients (Collino-Monk complex stretching)
  edge.py         # Lowest-order Nédélec (Whitney) edge elements: numbering, signs, curl-curl, mass, edge-nodal coupling
  waveguide.py    # M3a: mixed edge/nodal vector mode solver, A x = -beta^2 B x
  mesh3d.py       # M3b: Mesh3D + box_mesh (Kuhn subdivision, six tets per cube)
  assembly3d.py   # M3b: P1 tetrahedron stiffness (scalar/tensor) and mass, closed form
  edge3d.py       # M3b: Whitney edge elements on tetrahedra, all matrices closed form
  cavity.py       # Public vacuum PEC box solver, SI output and projected gradient kernel
  gmsh.py         # M3b: read/write Gmsh .msh (ASCII 2.2 and 4.1) — Gmsh never linked
  interop.py      # from_mesher: adapt a mesh built elsewhere (meshine, gmshio, ...)
tests/
  test_electrostatics.py   # M1   coax potential and field
  test_helmholtz.py        # M2   guided wave, cylinder scattering, and the PML
  test_edge_elements.py    # M3-prep waveguide cutoffs, and the nodal counter-example
  test_slab_modes.py       # M3a  the 1D limit, where the polarizations separate
  test_fiber_modes.py      # M3a  step-index fibre vector modes
  test_hadley.py           # M3a  dielectric corners and the rib waveguide family
  test_cavity_modes.py     # M3b  3D cavity, structured and unstructured
  test_mesh_io.py          # M3b  the Gmsh reader
  test_interop.py          #      meshes built by meshine and gmshio
  test_pipeline.py         #      the two end-to-end example pipelines
  test_independence.py     #      the engine never imports its own answer key
examples/
  coax_convergence.py        # M1 validation: coaxial cable + convergence study
  waveguide_convergence.py   # M2 validation 1: plane wave in a guide + convergence
  cylinder_scattering.py     # M2 validation 2: cylinder scattering vs Bessel/Hankel series
  cylinder_scattering_pml.py # M2.5: first-order ABC vs PML convergence comparison
  waveguide_modes.py         # M3-prep: waveguide cutoff eigenmodes (Nedelec vs nodal)
  fiber_modes.py             # M3a: step-index fibre modes vs the exact vector dispersion relation
  cavity_modes.py            # M3b: rectangular PEC cavity spectrum, 3D
  rib_waveguide_scalar.py    # end-to-end: meshine -> galerkin P1 -> refsol Hadley
  rib_waveguide_vector.py    # the same chain with the M3a vector solver
  mesh_io.py                 # M3b: Gmsh reader gates — fixtures, round trip, physics
  visualize*.py              # Figure generation for each milestone
```

## 시험

엔진은 폐형식 및 출판된 참조해를 담는 별도 패키지 [galerkin-refsol](https://github.com/fieldalgo/openphysics/blob/2efbc413df5d3d36bcc4c9879b34ed88213b9217/packages/galerkin-refsol/README.md)로 평가합니다. 같은 저장소에 있지만 독립 구현을 유지하며, 참조 패키지는 평가 대상 솔버를 import하지 않습니다. `tests/test_independence.py`는 엔진이 참조 패키지를 import하지 않고 의존성도 numpy와 scipy뿐임을 강제합니다.

```bash
# From the repository root
python -m pip install -e packages/galerkin   # engine only: numpy and scipy
# Install the full local test stack using ../../README.md, then:
python -m pytest -q packages/galerkin/tests
python -m pytest -q packages/galerkin/tests -m "not slow"
```

모든 명령은 저장소 루트에서 실행하세요. 편집 가능 설치로 `galerkin`이 경로에 추가되므로 시험과 예제에 `PYTHONPATH=.`가 필요하지 않습니다.

예제는 test extra 없이 실행할 수 있도록 자체 해석해를 유지합니다. 두 시험이 이 독립 구현을 refsol과 대조해 두 구현이 서로 달라지지 않게 합니다.

## 실행

```bash
python packages/galerkin/examples/coax_convergence.py        # M1 validation
python packages/galerkin/examples/waveguide_convergence.py   # M2 convergence
python packages/galerkin/examples/cylinder_scattering.py     # M2 scattering
python packages/galerkin/examples/cylinder_scattering_pml.py # M2.5 ABC vs PML
python packages/galerkin/examples/waveguide_modes.py         # M3-prep eigenmodes
python packages/galerkin/examples/fiber_modes.py            # M3a step-index fibre
python packages/galerkin/examples/cavity_modes.py           # M3b 3D cavity
python packages/galerkin/examples/mesh_io.py       # M3b Gmsh reader
python packages/galerkin/examples/visualize.py      # figures
python packages/galerkin/examples/visualize_fiber.py  # M3a figure
python packages/galerkin/examples/visualize_cavity.py # M3b figure
```

## 검증 결과(2026-09-05)

아래 값은 해당 날짜의 역사적 측정이며 새 시험 보고가 아닙니다.

각 단계는 해석해 일치와 이론 수렴률을 함께 통과해야 합니다. 솔버는 그럴듯하게 틀릴 수 있는 소프트웨어이고, 수렴률은 이를 판별하는 기준입니다.

- **M1 동축 케이블**(V = ln(b/r)/ln(b/a)): L2 수렴률 1.91 → **2.00**(P1 이론: 2), 방사 방향 장 일치도 0.99998, |E| 평균 오차 0.6%
- **M2 유도 평면파**(u = e^{-ikx}, 정확한 1차 ABC): 수렴률 1.90 → **2.00**
- **M2 원통 산란**(ka = π): 부분파 급수 대비 상대 L2 오차 **1.1%** — 잔여 오차는 1차 ABC가 지배
- **M2.5 ABC 대 PML**: 세분화해도 ABC는 1.1%에 정체합니다. PML은 **0.029%**까지 2차 수렴(수렴률 1.98)을 유지합니다. 항등 텐서로 등방성 경로와 텐서 계수 조립을 대조했습니다(1e-16).
- **M3-prep 도파로 차단**(1×0.5 PEC): 처음 여섯 고유값 오차는 6.9e-4 이내, TE10 수렴률 **2.00**, curl kernel은 정확히 0입니다. 같은 문제를 절점 벡터 P1로 이산화하면 가짜 고유값이 생기며, 변 요소가 필요한 이유를 수치적으로 보여 줍니다.
- **M3a 계단형 굴절률 광섬유**(n_co = 1.5, n_cl = 1.0, V = 3.5, 6a의 PEC 벽): 네 유도모드 모두 정확한 벡터 분산관계와 **2.2e-4** 이내로 일치하며 HE11 유효 굴절률 수렴률은 **2.00**입니다. 두 독립 gate도 있습니다. 혼합 정식화가 균질 충전 PEC 도파로의 해석적 스펙트럼 β² = k₀²ε_r − k_c²을 수렴률 2.00으로 재현하고, 변–절점 결합 행렬이 5차 구적과 1.1e-15까지 일치합니다.

| 모드 | 정확한 n_eff | FEM | 상대 오차 |
|---|---|---|---|
| HE11 | 1.3581708032 | 1.3580873381 | 6.2e-05 |
| TE01 | 1.1853020171 | 1.1850794850 | 1.9e-04 |
| TM01 | 1.1300844597 | 1.1299299650 | 1.4e-04 |
| HE21 | 1.1219119218 | 1.1216662493 | 2.2e-04 |

핵심 물리는 분리입니다. 스칼라(LP) 이론은 TE01, TM01, HE21을 하나의 축퇴 군으로 만듭니다. 같은 메시에서 이 이론은 1.1848846의 이중 축퇴 LP11 하나를 반환하며 HE11은 1.5% 빗나갑니다. 벡터 솔버는 n_eff 차이 6.3e-2에 걸쳐 세 모드를 구분합니다.

`refsol.fiber.vector_modes` 자체의 약한 도파 광섬유(a = 4 um, 1.45/1.44, 1.55 um, V = 2.756, 세 LP11 성분 차이 2e-5 이내)에서도 대조했습니다. HE11 4.3e-6, TE01 8.8e-6, TM01 5.5e-6, HE21 7.4e-6이며 수렴 차수는 **1.99 / 1.90 / 2.11 / 1.97**입니다.

- **M3a의 1D 극한** — 평면 SOI 슬랩(220 nm, λ = 1.55)을 `refsol.slab.modes`와 대조했습니다. 가는 띠로 모델링하면 측벽이 편광을 선택합니다. 전기벽은 TE 군만, 자기벽은 TM 군만 남깁니다. 각각 **2.00 / 1.98** 차수로 2.851739와 2.056288에 수렴합니다.

어느 방향이 한계를 정하는지도 기록할 필요가 있습니다. TE 장은 슬랩을 가로지르는 방향으로만 변하지만 오차는 띠를 **따르는** 메시가 지배합니다. Whitney 기저는 삼각형 대각선을 통해 두 방향을 결합하므로 눈에 띄는 방향만 세분화하면 3.6e-4에서 정체합니다.

- **출판 벤치마크와 M3a 대조** — Hadley 유전체 모서리 문제(`refsol.benchmarks.DIELECTRIC_CORNERS`, 인용 정확도 ±1e-8)는 단위 정사각형의 한 모서리에 정사각형 코어를 두고 두 변은 PEC, 나머지는 PMC로 둡니다. 48×48 메시의 네 사례는 출판값과 4.0e-5, 6.3e-5, 9.5e-6, 7.1e-6 차이를 보이며 수렴 차수는 2.09, 2.01, 2.44입니다.

네 번째 사례는 2차에 도달하지 않고 약 **1차**로 수렴합니다. 고굴절률 영역이 재진입 유전체 모서리를 둘러싸며, 그곳의 장 특이성이 Hadley 논문의 연구 대상입니다. 이 결과는 다른 사례와 평균하지 않고 별도 시험으로 기록·고정합니다.

측정에는 위험한 혼동 요인이 있습니다. 회전 대칭이 없는 메시는 **축퇴한** HE11·HE21 쌍도 분리하며 이 인공 효과를 물리와 구별하기 어렵습니다. `disk_mesh`는 정확한 C_n 대칭을 유지하고, 인공 분리는 **1.2e-14**로 측정됐습니다. 혼동할 수 있는 물리 분리보다 열두 자릿수 작습니다.

두 번째 혼동 요인은 PEC 벽입니다. 열린 광섬유에는 벽이 없으며 벽의 편향은 메시 세분화로 줄지 않습니다. 무한 클래딩 정확해에 대한 수렴률이 정직하려면 이 편향이 이산화 오차보다 훨씬 작아야 합니다. 메시 크기를 고정하고 벽을 6a에서 8a로 옮겨 측정한 값은 **8.6e-9**로, 가장 미세한 메시의 이산화 오차 3.5e-5보다 4천 배 작습니다.

`examples/fiber_modes.py`에는 추가로 두 영구 gate가 있습니다.

- 조립은 정확한 Whitney 항등식 G(c) = M_t(c) C, S(c) C = 0, K(c) = C^T M_t(c) C를 만족합니다. C는 노드–변 접속(이산 gradient) 행렬이며 상대 잔차는 1.3e-15, 3.9e-15, 4.2e-16입니다. 방향 부호 오류가 그럴듯한 스펙트럼을 만들어도 이 검사는 통과할 수 없습니다.
- TM01 방사 장은 코어 경계에서 정확히 n_co²/n_cl² = **2.2500**만큼 뛰며 FEM 요소 값은 두 정확한 Bessel 분지를 따릅니다(`fiber_interface.png`). 이 불연속이 횡방향 장을 H(curl)에 두어야 하는 물리적 이유입니다.

- **M3b 직육면체 PEC 공진기**(1.0 × 0.8 × 0.6, Kuhn 사면체 메시): h = 0.05에서 처음 여섯 공진은 정확해와 **1.8e-3** 이내이며 비축퇴 모드의 수렴률은 **1.98 / 2.00 / 1.91**입니다.

| 모드 | 정확한 k² | FEM | 상대 오차 |
|---|---|---|---|
| TM110 | 25.2908613 | 25.2803032 | 4.2e-04 |
| TE101 | 37.2851722 | 37.2478457 | 1.0e-03 |
| TE011 | 42.8368247 | 42.8040753 | 7.7e-04 |
| TE111/TM111 | 52.7064291 | 52.7548173 | 9.2e-04 |
| TE111/TM111 | 52.7064291 | 52.7998679 | 1.8e-03 |
| TM210 | 54.8996745 | 54.8290346 | 1.3e-03 |

고유값을 신뢰하기 전에 세 구조적 gate를 실행합니다.

- **메시**: 각 내부 면은 정확히 두 사면체가 공유하고, 경계 면 개수는 정확하며 모든 부피는 양수이고 Euler V − E + F − T = 1이어야 합니다.
- **3D Whitney 항등식** — G(c) = M_t(c) C, S(c) C = 0, K(c) = Cᵀ M_t(c) C — 상대 잔차 2.1e-16, 1.3e-16, 6.8e-16.
- **이산 de Rham 정확성**: PEC 구속 변 공간에서 이산 curl kernel의 차원은 내부 노드 수와 정확히 같습니다(네 메시에서 1, 4, 12, 24). 이 정수 항등식이 물리 모드 사이에 가짜 모드가 나타날 수 없는 구조적 이유이며, 단지 관찰되지 않았다는 진술보다 훨씬 강합니다.

M3a와 정직하게 구분할 점이 있습니다. M3a 원판 메시는 정확한 C_n 회전 대칭으로 축퇴 쌍의 분리를 1.2e-14로 유지합니다. Kuhn 분할은 선호 대각선이 있어 대칭이 없으므로 정확히 축퇴한 TE111/TM111 쌍이 갈라집니다. 이는 이산화 인공 효과이며 실행은 이를 인공 효과로 측정·검사합니다. 분리는 **2.15** 차수로 사라집니다. 메시가 어느 경우에 속하는지에 따라 측정된 분리를 물리로 해석할 수 있는지가 결정됩니다.

- **M3b Gmsh 입력**. Gmsh는 GPL이므로 링크하지 않고 별도 실행 파일로 실행합니다. `gmsh.py`는 그 출력 파일을 읽습니다. ASCII 2.2·4.1, 사면체·삼각형, 경계 태그로 쓰는 physical group, 불연속 노드 태그 재매핑을 지원합니다. 바이너리와 고차 요소는 잘못 읽지 않고 거절합니다. 형식 문서에서 직접 작성한 fixture, 모든 경계 태그를 보존하는 왕복 변환, 읽어 들인 메시에서 다시 계산한 공진 스펙트럼의 세 방식으로 검증하며 마지막 차이는 **1.4e-14**입니다.

이제 Gmsh 자체가 쓴 두 형식의 파일로도 검사하고 `gmshio`의 독립 판독기와 동일 연결성을 교차 확인합니다. 이 항목이 이전에 기록했던 한계는 해소됐습니다.

- **외부에서 만든 메시**. `galerkin.from_mesher`는 `nodes`, `triangles` 또는 `tetrahedra`, `regions`, `region_names`, 경계 변 또는 면을 제공하는 객체를 변환합니다. `Mesh.by_region({"core": ..., "clad": ...})`는 영역 이름을 요소별 재료 배열로 바꿉니다. 엔진 의존성이 아닌 두 생성기 [meshine](https://github.com/FieldAlgo/meshine)(순수 numpy/scipy, 평면)과 [gmshio](https://github.com/FieldAlgo/gmshio)(별도 프로세스의 Gmsh 실행 파일)로 검증했습니다.

Hadley의 **리브 도파로** 여덟 사례(`refsol.benchmarks.RIB_WAVEGUIDES`, 인용 정확도 ±3e-6, 슬랩 두께 0–0.7 µm)는 meshine 메시에서 출판 준-TE 굴절률과 **1.2e-4** 이내입니다. 이 하한은 참조값이 아니라 리브와 슬랩이 만나는 재진입 유전체 모서리가 정합니다.

사례별 허용치를 만족해도 군 전체가 틀릴 수 있으므로 경향을 별도로 검사합니다. 출판 굴절률은 여덟 사례에 걸쳐 총 2.08e-3만큼 단조 증가하고, 이 범위를 9.4e-5까지 재현합니다.

- **전체 파이프라인**. `examples/rib_waveguide_scalar.py`와 `examples/rib_waveguide_vector.py`는 meshine 메시 생성 → galerkin 조립·풀이 → refsol 평가의 전체 흐름을 실행하며 솔버만 다릅니다. 스칼라 모델은 공기 경계의 편광 항을 놓쳐 Hadley 준-TE 값보다 약 **+2.5e-4 위**에 수렴합니다. 벡터 솔버는 **아래쪽**에서 접근해 h = 0.035에서 −3.6e-5에 도달하고 관측 차수는 0.90 → 1.77 → 2.34로 상승합니다.

Hadley의 명시 정확도 ±3e-6에는 **도달하지 못했습니다**. 원인은 가정하지 않고 측정했습니다. 계산 창 때문이 아니고(폭 18 → 34 µm로 바꾸면 n_eff 변화 1e-6), 형상이나 참조해 때문도 아닙니다. 2차 꼬리를 외삽하면 원거리장도 함께 세분화할 때 h ≈ 0.010이 필요합니다. meshine이 만들 수는 있지만 매 반복 모든 점을 다시 삼각분할하므로 빠르지 않습니다. 메시 생성기의 속도가 한계입니다.

기록할 함정이 있습니다. 원거리 요소 크기를 고정하고 리브 주변만 세분화하면 모드가 세분 영역 밖까지 퍼지므로 관측 차수는 **감소**(1.77, 1.06, 0.70)하고 약 −4e-5에서 정체합니다. 세분화 중 차수 정체는 특이성이 아니라 오차 바닥의 신호입니다. 특이성은 일정한 분수 차수를 유지합니다.

단위 정육면체의 gmshio 메시에서는 군집 평균이 **5.1e-3** 이내이고 해석 공진 사이에 가짜 모드는 나타나지 않습니다. 엄격한 2차 사다리 검사는 galerkin이 직접 만드는 구조화 메시에서 유지합니다. Gmsh의 `lc`는 목표 크기이므로 세분화 열의 두 메시는 중첩되지 않습니다. 그 수렴률을 적합하면 솔버뿐 아니라 생성기도 함께 측정하게 됩니다.

## 다음 단계

- **MFEM**은 문제 규모가 순수 Python 직접해법의 범위를 넘을 때의 생산 코어로 검토 중입니다. 이 3D 희소 분해는 네 코어에서 약 25k개 변 자유도까지 무리가 없으며, 그 이후에는 보조 공간 전처리기를 쓰는 반복 솔버가 필요합니다.
- **유전체 충전 및 열린 3D 문제**: 3D 텐서 계수 경로가 있으므로(`assemble_stiffness_3d`가 (T,3,3) 텐서를 받음) M2.5 PML을 옮길 수 있습니다. 부족한 것은 해석해를 갖는 3D 검증 사례입니다.
- **전자기 이후**: 조립 코어는 물리에 중립적입니다. 저수준 조립은 이방성 계수를 표현할 수 있지만, 현재 공개 정상 열전도 API는 균질 등방성 재료만 받습니다. Robin 경계도 이 등방성 API 범위입니다. 정적 탄성은 전용 벡터 절점 공간을 제공합니다. 과도 문제에는 시간 적분기, Stokes에는 P2 공간이 필요합니다. M3a의 두 장 블록 시스템이 각 연성 다중물리 문제에서 재사용하는 패턴입니다.

## 라이선스

Apache License 2.0 — [LICENSE](LICENSE), [NOTICE](NOTICE)를 참조하세요.

Copyright 2026 Yongha Kim (FieldAlgo)

Gmsh는 GPL-2.0-or-later의 별도 프로그램입니다. 이 엔진에 배포되거나 링크되지 않습니다. `galerkin.gmsh`는 공개 MSH ASCII 형식의 독립 판독기이며 Gmsh 자체를 사용할 때는 별도 실행 파일로 실행합니다. 따라서 GPL은 `galerkin` 또는 이를 사용하는 코드로 확장되지 않습니다.

이 프로젝트는 Gmsh 프로젝트와 제휴하지 않으며 그 프로젝트의 보증이나 지원을 받지 않습니다.


## 검토 후보: 열 경계 확장

독립 등방성 `galerkin.thermal` API는 처방 외향 열유속과 Robin 대류를 추가합니다.
[경계 계약](docs/locales/ko/pages/thermal_flux_robin.md),
[영어 예제](examples/thermal_flux_robin.py),
[독립 수용검증](docs/locales/ko/pages/thermal_flux_robin_independent_validation.md)을 참고하세요.
이 검토 후보는 게시된 릴리스나 최종 develop 수용이 아닙니다.
헤드리스 simcase JSON 계약은 여전히 flux/Robin 경계를 거부합니다. 독립 API 확장은
Studio에서 이를 활성화하거나 자동 연성을 추가하지 않습니다.
