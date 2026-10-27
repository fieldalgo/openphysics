# galerkin — OpenPhysics 유한요소 해석 엔진

[English](../../../../../packages/galerkin/overview.md) | **한국어**

[전체 문서 색인](https://github.com/fieldalgo/openphysics/blob/main/docs/locales/ko/pages/index.md)

해석해 검증을 먼저 수행하는 방식으로 개발한 순수 Python(numpy + scipy.sparse) 유한요소 솔버
엔진입니다. 2D 전자기, 3D 공진기 고유모드, 정상·과도 2D 열전도, 정적 2D 탄성과 단방향
열전도→기계 workflow를 다룹니다. 실행 의존성은 numpy와 scipy뿐입니다.

## 해석할 수 있는 문제

각 독립 하위 모듈은 명시적으로 import합니다. 계약 문서는 단위·입력·결과·한계를 정의하고,
검증 보고는 독립 기준해와 고정 허용치를 기록합니다.

| 문제 | 진입점 | 계약·검증 | 예제 |
|---|---|---|---|
| 흡수 경계 또는 원통형 PML을 쓰는 2D 정전기·주파수 영역 파동 | `assemble_stiffness`, `solve_dirichlet`, `radial_pml_coeffs` | [단계별 검증 결과](milestone_validation.md) | `examples/galerkin/coax_convergence.py`, `examples/galerkin/cylinder_scattering_pml.py` |
| 도파로 차단 모드와 유전체 도파 모드: 스칼라 P1, 혼합 Nédélec/절점 전체 벡터 | `solve_modes` | [고유공간 신뢰성](eigenspace_reliability.md), [단계별 검증 결과](milestone_validation.md) | `examples/galerkin/fiber_modes.py`, `examples/galerkin/waveguide_modes.py` |
| 3D 진공 직육면체 PEC 공진기 고유모드, SI 주파수와 원시 변 장 | `solve_cavity_box` | [공진기 API](cavity_solver.md) | `examples/galerkin/cavity_modes.py` |
| 손실 유전·자성 직육면체 영역과 유한 전도도 벽을 갖는 3D 직육면체 공진기: 복소 주파수와 Q | `solve_material_cavity_box` | [재료 공진기](material_cavity.md) | — |
| 등방성 정상 2D 열전도, Dirichlet·단열 경계 | `galerkin.thermal.solve_steady_heat` | [계약](thermal_steady2d.md), [검증](thermal_independent_validation.md) | [thermal_steady2d.py](../../../../../../examples/galerkin/thermal_steady2d.py) |
| 같은 메시의 정상 전기→열 단방향 연성 | `galerkin.joule_heating.solve_steady_joule_heat` | [API·단위·검증](joule_heating.md) | [joule_heating.py](../../../../../../examples/galerkin/joule_heating.py) |
| 정상 열전도의 처방 외향 열유속과 Robin 대류 | `galerkin.thermal.solve_steady_heat` | [계약](thermal_flux_robin.md), [검증](thermal_flux_robin_independent_validation.md) | [thermal_flux_robin.py](../../../../../../examples/galerkin/thermal_flux_robin.py) |
| JAX·PyTorch에서 재료·열원·경계값에 대한 미분: 정상·과도 열, 정상 전기 전도, 탄성, 열탄성, 도파관 고유값과 필드 | JAX·PyTorch 입력을 준 `solve_steady_heat`, `solve_steady_electric`, `solve_transient_heat`, `solve_elasticity`, `solve_thermoelasticity`, `solve_modes` | [계약과 검증](differentiation.md) | — |
| 과도 2D 열전도: 고정 P1·일관 질량·후진 Euler, 시간변 Dirichlet과 단열 | `galerkin.transient_heat.solve_transient_heat` | [계약](transient_heat.md), [검증](transient_heat_validation.md), [독립 검증](transient_heat_independent_validation.md) | [transient_heat_convergence.py](../../../../../../examples/galerkin/transient_heat_convergence.py) |
| 정적 2D 선형탄성, 평면응력 또는 평면변형률 | `galerkin.elasticity.solve_elasticity` | [계약](elasticity2d.md), [검증](elasticity2d_independent_validation.md) | [elasticity2d.py](../../../../../../examples/galerkin/elasticity2d.py) |
| 탄성의 전역 Cartesian 경계 표면하중 | `galerkin.elasticity.solve_elasticity` | [계약](elasticity_traction.md), [검증](elasticity_traction_independent_validation.md) | [elasticity_traction.py](../../../../../../examples/galerkin/elasticity_traction.py) |
| 같은 메시의 처방 절점 Kelvin 장 아래 기계해석 | `galerkin.thermoelasticity.solve_thermoelasticity` | [계약](prescribed_temperature_thermoelasticity.md), [검증](prescribed_temperature_thermoelasticity_independent_validation.md) | [prescribed_temperature_thermoelasticity.py](../../../../../../examples/galerkin/prescribed_temperature_thermoelasticity.py) |
| 처방 온도장 기계단계의 전체 표면하중 | `galerkin.thermoelasticity.solve_thermoelasticity` | [계약](thermoelastic_traction.md), [검증](thermoelastic_traction_independent_validation.md) | [thermoelastic_traction.py](../../../../../../examples/galerkin/thermoelastic_traction.py) |
| 정상 열전도 후 같은 메시의 기계해석(단방향) | `galerkin.thermal_mechanical.solve_steady_thermoelasticity` | [계약](thermal_mechanical_workflow.md), [검증](thermal_mechanical_independent_validation.md) | [thermal_mechanical_workflow.py](../../../../../../examples/galerkin/thermal_mechanical_workflow.py) |
| 저장된 과도 열전도 시간 중 고른 시간의 준정적 기계해석(단방향) | `galerkin.transient_thermal_mechanical.solve_transient_thermoelasticity` | [계약](transient_thermal_mechanical.md) | [transient_thermal_mechanical.py](../../../../../../examples/galerkin/transient_thermal_mechanical.py) |
| 정상·과도 열전도, 탄성, 열탄성, 두 열→역학 workflow의 이름 있는 메시 영역별 구간 상수 재료 | 스칼라 k, c, Q, E, nu, alpha 대신 `{영역 이름: 값}` | [계약과 검증](multimaterial.md) | — |
| 공개 기준값 벤치마크: Timoshenko (1925) 바이메탈 띠와 NAFEMS T4 | 기존 열·기계 단계; 정답 `refsol.bimetal`, `refsol.thermal_convection` | [검증](public_benchmarks.md) | [public_benchmarks.py](../../../../../../examples/galerkin/public_benchmarks.py) |

단위는 각 계약을 따릅니다. 열전도와 기계해석은 SI 미터·초·Kelvin을 쓰며, 깊이당 열량은 W/m,
깊이당 기계 하중은 N/m, 깊이당 물리 탄성에너지는 J/m입니다. 벡터 모드는 축퇴 고유공간 방향을
포함한 복소 횡·종방향 계수를 보존합니다. 장을 실수로 바꾸기 전에 고유공간 신뢰성 계약을
읽으세요.

[simcase](../simcase/overview.md)
패키지는 이 중 일부를 JSON 문서로 제공합니다. 2D 모드, 직육면체 공진기(진공 PEC 또는 손실
재료와 도체 벽), 정상·과도 열전도(직사각형 또는 재료 영역)입니다. Python 전용 기능이 그곳에 자동으로 제공되지는 않습니다.

## 한계

- 열전도→기계 연성은 열로 되먹임이 없는 명시적 단방향 호출입니다. 정상 workflow는
  Dirichlet·단열 열전도만 받으며 별도 열유속/Robin이나 표면하중 확장을 받지 않습니다.
- 과도 열전도에는 열유속/Robin 입력, restart, 자동 연성이 없습니다. 선형 API는 유한한 음의
  Kelvin을 clamp하지 않습니다.
- 열·탄성 재료는 등방성이며 이름 있는 메시 영역마다 상수입니다([multimaterial](multimaterial.md)).
  이 열·탄성 계수는 온도에 따라 변하지 않습니다. 별도
  [Joule workflow](temperature_joule_heating.md)는 유효 범위가 있는 온도 의존 등방성 전기전도도를
  지원합니다. 기계해석은 선형 미소변형입니다. 표면하중 API는 전역
  Cartesian 하중을 받으며 scalar pressure 전용·로컬 프레임·follower 하중 API는 없습니다.
- `solve_cavity_box`는 진공 직육면체 PEC 상자를 다루고, `solve_material_cavity_box`는
  직육면체 손실 영역과 유한 전도도 벽을 더합니다. 목표 근처 탐색 한계는 각 계약을 읽으세요.
- 3D 희소 직접 분해는 네 코어에서 약 25k개 변 자유도까지 무리가 없습니다. 더 큰 문제에는
  반복 솔버가 필요합니다.

## 구성

```
src/galerkin/
  mesh.py         # Mesh data structure (boundary nodes + edges) + structured mesh generators
  assembly.py     # Stiffness K (scalar/tensor coefficients), mass M, boundary B, load vector
  solver.py       # Dirichlet reduction + scipy sparse direct solve (real/complex)
  postprocess.py  # E = -grad V, L2 error (complex-aware)
  pml.py          # Cylindrical PML coefficients (Collino-Monk complex stretching)
  edge.py         # Lowest-order Nédélec (Whitney) edge elements: numbering, signs, curl-curl, mass, edge-nodal coupling
  waveguide.py    # Mixed edge/nodal vector mode solver, A x = -beta^2 B x
  mesh3d.py       # Mesh3D + box_mesh (Kuhn subdivision, six tets per cube)
  assembly3d.py   # P1 tetrahedron stiffness (scalar/tensor) and mass, closed form
  edge3d.py       # Whitney edge elements on tetrahedra, all matrices closed form
  cavity.py       # Public vacuum PEC box solver, SI output and projected gradient kernel
  material_cavity.py # Box cavity with lossy materials and impedance walls: complex resonances and Q
  thermal.py      # Steady heat: Dirichlet, insulation, prescribed flux, Robin
  transient_heat.py               # Transient heat, backward Euler
  elasticity.py                   # Static plane stress/strain elasticity and traction
  thermoelasticity.py             # Mechanics under a prescribed temperature field
  thermal_mechanical.py           # Steady heat -> mechanics workflow
  transient_thermal_mechanical.py # Stored transient heat -> quasistatic mechanics
  gmsh.py         # Read/write Gmsh .msh (ASCII 2.2 and 4.1) — Gmsh never linked
  interop.py      # from_mesher: adapt a mesh built elsewhere (meshine, gmshio, ...)
```

해석해·수렴·독립 검증 시험, 예제, 문서는 패키지 밖, 저장소 루트의 `tests/galerkin/`,
`examples/galerkin/`, `docs/packages/galerkin/`(한국어는
`docs/locales/ko/pages/packages/galerkin/`)에 있습니다.

`galerkin.from_mesher`는 `nodes`, `triangles` 또는 `tetrahedra`, `regions`, `region_names`와
경계 변·면을 제공하는 객체를 변환하고, `Mesh.by_region({"core": ..., "clad": ...})`은 영역
이름을 요소별 재료 배열로 바꿉니다. meshine과 gmshio로 확인했으며 둘 다 엔진의 의존성이
아닙니다.

## 시험

엔진은 닫힌 형태 해와 출판된 기준해를 담은 별도 패키지
[galerkin-refsol](../galerkin-refsol/overview.md)로
채점합니다. 같은 저장소에 있지만 독립 구현이며, 기준해 패키지는 채점 대상 솔버를 import하지
않습니다. `tests/galerkin/test_independence.py`는 엔진이 기준해를 import하지 않고 의존성이 numpy와
scipy뿐임을 강제합니다.

```bash
# From the repository root
python -m pip install -e packages/galerkin   # engine only: numpy and scipy
# Install the full local test stack using the repository README.md, then:
python -m pytest -q tests/galerkin
python -m pytest -q tests/galerkin -m "not slow"
```

모든 명령은 저장소 루트에서 실행합니다. 편집 가능 설치가 `galerkin`을 경로에 넣으므로
시험과 예제는 `PYTHONPATH` 설정 없이 실행됩니다.

예제는 시험 extra 없이도 실행되도록 자체 해석해를 갖고 있으며, 두 시험이 이 독립 구현을
refsol과 대조해 둘이 어긋나지 않게 합니다. 전자기·공진기 솔버를 만들 때 기록한 측정은
[단계별 검증 결과](milestone_validation.md)에 있습니다.

## 실행

```bash
python examples/galerkin/coax_convergence.py        # electrostatics convergence
python examples/galerkin/waveguide_convergence.py   # Helmholtz convergence
python examples/galerkin/cylinder_scattering.py     # cylinder scattering
python examples/galerkin/cylinder_scattering_pml.py # ABC vs PML
python examples/galerkin/waveguide_modes.py         # waveguide cutoff eigenmodes
python examples/galerkin/fiber_modes.py             # step-index fibre vector modes
python examples/galerkin/cavity_modes.py            # 3D PEC cavity
python examples/galerkin/mesh_io.py                 # Gmsh reader
python examples/galerkin/thermal_steady2d.py        # steady heat
python examples/galerkin/elasticity_traction.py     # elasticity with traction
python examples/galerkin/thermoelastic_traction.py  # prescribed-temperature mechanics
python examples/galerkin/visualize.py               # figures
```

## 라이선스

Apache License 2.0 — [LICENSE](../../../../../../packages/galerkin/LICENSE), [NOTICE](../../../../../../packages/galerkin/NOTICE)를 참조하세요.

Copyright 2026 Yongha Kim (FieldAlgo)

Gmsh는 GPL-2.0-or-later의 별도 프로그램입니다. 이 엔진에 배포되거나 링크되지 않습니다.
`galerkin.gmsh`는 공개 MSH ASCII 형식의 독립 판독기이며 Gmsh 자체를 사용할 때는 별도 실행
파일로 실행합니다. 따라서 GPL은 `galerkin` 또는 이를 사용하는 코드로 확장되지 않습니다.

이 프로젝트는 Gmsh 프로젝트와 제휴하지 않으며 그 프로젝트의 보증이나 지원을 받지 않습니다.

[정상 전기전도: Python API, Joule 발열과 Neumann 기준 전위](electric_steady2d.md).
