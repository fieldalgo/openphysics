# 선형탄성·열탄성 문서

[English](../../../../../packages/simcase/mechanics2d.md) | **한국어**

`mechanics.elasticity2d`(등온)와 `mechanics.thermoelastic2d`(정상 열전도 후 같은 메시의 열응력)의
JSON/CLI 규범 원본은 위 영문 문서다. 이 페이지는 같은 계약의 한국어 안내다. 수치 풀이와 기존
허용오차는 [2D 탄성](../galerkin/elasticity2d.md), [직교좌표계 경계 traction](../galerkin/elasticity_traction.md),
[정상 열전도](../galerkin/thermal_steady2d.md), [열탄성 traction](../galerkin/thermoelastic_traction.md)
계약을 따르며, 이 adapter는 새로운 이산화를 추가하지 않는다.

## 범위·입력

`openphysics:"0.2"`, 이름 있는 physics 하나, `study:{"type":"single"}`,
`geometry.domain`의 `xmin,xmax,ymin,ymax` 직사각형, 양의 정수 `mesh.subdivisions:[nx,ny]`,
`materials:{}`를 사용한다. sweep·재메시·두께는 없다. 형상이 재료 영역을 선언하는 문서는
대신 [영역 계약](#재료-영역과-이름-있는-경계)을 따른다. 이 절과 다음 절은 직사각형 문서를 설명하며,
영역 계약은 이를 바꾸지 않는다. `units`에는 `length`만
(기존 길이 단위 중 하나) 들어가며, SI 접미사가 붙은 값은 길이 단위와 무관하게 그 SI 단위를
쓴다. 알 수 없는 키, 비유한 수, 숫자 대신 boolean, 모서리의 상충 조건은 거부한다. 할당 전
최대 200,000 삼각형을 검사한다. results 기본값은 `save_fields:true,plots:false`이며 plot과
Studio 실행은 지원하지 않는다. 직사각형·단위·메시·study·results 검사는
[정상 열전도 계약](thermal_steady2d.md)과 같다.

`mechanics.elasticity2d`의 physics 키(`units`에는 `length`만):

- `plane`: `"stress"` 또는 `"strain"`.
- `young_modulus_pa`(> 0), `poisson_ratio`(−1 < ν < 0.5, 양 끝 제외). 평면변형률 P1 요소는
  ν가 0.5에 가까워지면 locking이 생기므로 범위 통과가 정확도 보증은 아니다.
- `displacement_m`(필수): `{변: {"x": m, "y": m}}`. 변은 `left,right,bottom,top`이고 적은
  변마다 `x`, `y` 중 하나 이상이 필요하다. 적은 성분은 그 변의 모든 절점에 미터 단위로
  지정되고 다른 성분은 자유다. 인접한 두 변이 같은 성분을 지정하면 공유 모서리에서 값이
  같아야 한다.
- `body_force_n_m3`(선택): 상수 `[fx, fy]`, N/m³, 기본값 `[0, 0]`.
- `traction_pa`(선택): `{변: [tx, ty]}`, 전역 직교좌표계 Pa, 변을 따라 상수(법선/접선
  성분이 아님). 적지 않은 변은 traction이 0이다. 같은 변에서 변위가 지정된 성분의 traction은
  0이어야 한다(반력에 흡수될 뿐이기 때문).

**강체 모드 규칙.** 구속은 평면 강체 운동 u = (a − θy, b + θx) 세 개를 모두 막아야 한다.
어떤 변이 `x`를, 어떤 변이 `y`를 지정하고, 회전 θ가 막혀야 한다. 회전은 `left` 또는
`right`에 `x`를, `bottom` 또는 `top`에 `y`를, `bottom`과 `top` 양쪽에 `x`를, 또는 `left`와
`right` 양쪽에 `y`를 지정할 때만 막힌다. 수평 변 하나에 `x`, 수직 변 하나에 `y`만 지정하면
두 변의 모서리를 축으로 하는 hinge가 남으므로 거부한다. 이 규칙은 메시를 만들기 전에 문서만으로
판정하며, 생성한 메시에 대한 솔버의 rank 검사와 일치한다(테스트에서 모든 조합을 확인).

### 정상 열전도 후 열응력

`mechanics.thermoelastic2d`는 같은 역학 키에 `units.temperature:"K"`(필수),
`thermal_expansion_per_k`(유한, 부호 있음), `reference_temperature_k`(≥ 0)와
[정상 열전도](thermal_steady2d.md)·[경계조건](thermal_steady_boundary2d.md) 계약의 변별 상수 열 데이터를
더한다: `thermal_conductivity_w_mk`(> 0), `dirichlet_temperature_k`(변→K, 음수 아님, 모서리 일치),
선택적 `heat_source_w_m3`, `outward_flux_w_m2`(변→q·n), `convection`(변→`{h_w_m2k, ambient_temperature_k}`).
고정 변 하나 이상 또는 양의 h가 필요하고 고정 변에는 자연 경계조건을 줄 수 없다. runner는 메시에서
`galerkin.thermal.solve_steady_heat`를 풀고 `galerkin.thermoelasticity.freeze_temperature`로 절점 온도를
고정한 뒤 역학 인자로 `solve_thermoelasticity`를 호출한다. `traction_pa`는 Python 계약과 같이 **전체**
물리 σ·n이며 열 traction으로 보정하지 않는다. 연계는 단방향이다: 열로 되먹임 없음, 온도 의존 재료 없음,
교차 메시 전달 없음.

## 실행·저장

```sh
python -m simcase example elastic_plate > model.json
python -m simcase validate model.json
python -m simcase run model.json -o fresh-results
```

Python은 `Document.from_dict`/`Document.load`, `run(document)`,
`MechanicsRunResult.save(path)`를 사용한다. `fields`는 소유권이 분리된 숫자 배열 사본,
`summary()`는 JSON 호환 사본을 반환한다. 호출자 입력이나 반환 사본 변경은 계산 기록을 바꾸지
않는다. 결과의 `doc`은 별도 snapshot이며 수정하면 저장이 거부된다. EM 전용
`build_mesh`/`solve_point`에는 명시적 거부가 있다.

runner는 `galerkin.rectangle_mesh`를 미터 단위로 한 번 만들고(절점을 domain 원점으로 이동),
변의 절점을 `(node, component)` 순으로 정렬한 `{(node, component): m}`로 지정한 뒤 문서의
plane, E, ν, 체적력, traction으로 `galerkin.elasticity.solve_elasticity`를 호출한다. 문서
실행과 같은 인자의 직접 호출은 byte 단위로 같은 배열을 준다.

성공은 `model.json`, `log.txt`, `summary.json`, 선택적 `fields.npz`를 저장한다. 기존 출력
소유권·실패 정리 기능을 재사용하며 빈 폴더·symlink 포함 기존 경로는 거부한다. 성공 summary를
마지막에 쓰고 중단된 저장에는 `.incomplete`가 남는다. NPZ에는 숫자 배열과 Unicode
metadata만 있어 `allow_pickle=False`로 읽는다.

결과 ID는 `mechanics.elasticity2d-result-v1`, layout은 `mechanics2d-p1-v1`,
`mesh_length_unit`은 `m`이다. 저장 배열:

| 배열 | 모양 | 단위 | 의미 |
|---|---|---|---|
| `nodes_m` | (N,2) | m | 절점 좌표 |
| `triangles` | (T,3) | 1 | 연결 |
| `displacement_m` | (N,2) | m | 절점 (u_x, u_y) |
| `strain` | (T,3) | 1 | 요소 engineering 변형률 `exx, eyy, gxy`(γ_xy = 2 ε_xy) |
| `stress_pa` | (T,3) | Pa | 요소 응력 `sxx, syy, sxy` |
| `load_n_per_m`, `reaction_n_per_m`, `residual_n_per_m` | (N,2) | N/m | 체적력+traction의 consistent 하중; 지정 DOF의 K·u − load(그 외 0); 모든 DOF의 K·u − load |
| `dirichlet_node_ids`, `dirichlet_components`, `dirichlet_displacement_m` | (K,) | 1, 1, m | 지정 DOF(성분 0 = x, 1 = y)와 값 |

열탄성 결과(ID `mechanics.thermoelastic2d-result-v1`, layout `thermoelastic2d-p1-v1`)는 `strain`과
`load_n_per_m` 대신 다음을 저장한다:

| 배열 | 모양 | 단위 | 의미 |
|---|---|---|---|
| `temperature_k` | (N,) | K | 역학이 사용한 정상 열전도 해 |
| `heat_flux_w_m2` | (T,2) | W/m² | 요소 열유속 |
| `thermal_load_w_per_m`, `thermal_reaction_w_per_m`, `thermal_residual_w_per_m`, `prescribed_outward_heat_w_per_m`, `ambient_load_w_per_m`, `convective_outward_heat_w_per_m`, `thermal_system_rhs_w_per_m` | (N,) | W/m | 열 풀이의 절점 배열(flux·대류가 없으면 0) |
| `thermal_dirichlet_node_ids`, `dirichlet_temperature_k` | (K_T,) | 1, K | 온도 고정 절점과 값 |
| `total_strain`, `thermal_strain`, `elastic_strain` | (T,3) | 1 | `exx, eyy, gxy`; total = thermal + elastic |
| `stress_pa` | (T,3) | Pa | 탄성 변형률의 `sxx, syy, sxy` |
| `sigma_zz_pa`, `epsilon_zz` | (T,) | Pa, 1 | 면외 응력(평면변형률) 또는 변형률(평면응력) |
| `load_external_n_per_m`, `load_thermal_n_per_m`, `load_body_n_per_m`, `load_traction_n_per_m`, `reaction_n_per_m`, `residual_n_per_m` | (N,2) | N/m | 체적력+traction 하중, 열 등가 하중과 그 두 부분, 지정 DOF의 K·u − load, 모든 DOF의 K·u − load |

열탄성 summary에는 열팽창계수, 기준 온도, 전도도, 고정한 온도의 `temperature_snapshot` 해시(`mesh_hash`,
`temperature_hash`, `snapshot_hash`), 열 진단값(열원·외향 열과 그 차이 W/m, 자유 열 잔차, 최소·최대 온도),
외부·열 하중 합(N/m), 물리 탄성 에너지(J/m)가 더해진다. 힘 수지는 외부 하중 + 열 하중 + 반력이다.

변형률·응력은 P1 요소마다 상수다(`field_locations`는 `triangle_centroids`). summary가 성분
순서를 반복한다. 힘은 면외 깊이 1 m당 값이며 N이 아니다. summary에는 `status:"solved"`,
plane·재료, `field_units`, `field_locations`, `field_shapes`, 시간, 소프트웨어 버전과 진단값이
있다: 자유 DOF 잔차 노름(N/m), 성분별 적용 하중·지지 반력·그 합(N/m), 변형 에너지 ½ uᵀKu(J/m),
최대 변위 크기(m), 최대 응력 성분(Pa).

CLI 종료값: 입력 오류 2(출력 폴더 없음), 풀이·I/O 오류(규칙이 예상하지 못한 특이 행렬,
비유한 값, 이미 있는 출력) 1, 성공 0. 저장한 필드는 `simcase.export`로 ParaView에서 볼 수
있다([ParaView로 보기](overview.md#paraview로-보기)): 점 데이터 `displacement_m`과 N/m 절점
배열(z = 0 벡터; 열탄성 배치는 `temperature_k`와 W/m 절점 배열을 스칼라로 더함), 셀 데이터 `exx`,
`eyy`, `gxy`와 `sxx_pa`, `syy_pa`, `sxy_pa`(열탄성: `heat_flux_w_m2`, `sigma_zz_pa`, `epsilon_zz`와
`total_`, `thermal_`, `elastic_` 변형률 성분).
내보내기는 저장된 배열을 복사할 뿐 이 계약에 아무것도 더하지 않는다.

## 검증

`tests/simcase/test_mechanics.py`가 사전 등록한 gate를 담는다. 아래 값은 Linux, Python 3.12,
NumPy 2.5.4, SciPy 1.18.1(2026-11-02) 측정값이다.

| Gate | 기준 | 측정 |
|---|---|---|
| J1 | 문서 실행 == 같은 메시의 직접 `solve_elasticity`, byte 단위(평면응력·변형률, 원점 이동 mm domain, 체적력과 traction 둘) | 배열 여섯 개 모두 byte 일치 |
| J2 | `refsol.elasticity_traction.uniaxial`·`shear`, `m`,`mm`,`um`,`nm`, 두 plane: 변위·응력 상대오차 ≤ 1e-10 | 변위 ≤ 4.6e-15, 응력 ≤ 1.3e-14, 변형률 ≤ 9.1e-15 |
| J3 | 상수 체적력 막대 u = f/(λ+2μ)(Lx − x²/2, 0), x=0에서 x·y 고정, bottom·top에 y 고정: 분할 8,16,32에서 중심 변위 수렴 차수 ≥ 1.8 | 차수 1.95, 1.97(평면응력), 1.94, 1.97(평면변형률); 요소 응력 차수 0.95–0.98 |
| J4 | 잘못된 문서 32개(hinge, 한 성분만, 모서리 상충, 단위 누락·추가, 잘못된 plane, ν = 0.5·−1, 태그 수량, 지정 성분의 traction 등) exit 2, 출력 없음; 강체 규칙이 구속 집합 12개에서 솔버 rank 검사와 일치 | 모두 거부 |
| J5 | CLI validate/run/save, 기존 출력 거부(기존 summary 불변), 부분 저장 정리, 결과 사본·문서 snapshot 불변 | 통과 |
| J6 | Studio `/api/validate`·`_require_studio_physics`가 거부; Studio Node 검사 유지 | 통과, Node 247개 |
| J7 | `tools/wheel_consumers/test_mechanics_wheel.py`(단축 판·열탄성 막대 CLI, hinge 거부, VTU 내보내기)를 `check_platform_install.py`처럼 임시 폴더에서 `python -I`로 실행 | 통과 |
| K1 | 열탄성 문서 실행 == 같은 메시의 `solve_steady_heat` + `freeze_temperature` + `solve_thermoelasticity`, byte 단위(두 plane, 열원, flux·대류 변, 체적력, traction 둘) | 배열 16개 모두 byte 일치, snapshot 해시 동일 |
| K2 | 전단 0의 `refsol.thermoelastic_traction.uniform_combined`(법선응력 8·−2 MPa, +20 K), 네 변 Dirichlet의 균일 온도, `m`,`mm`,`um`,`nm`, 두 plane: 온도·변위·면내 및 zz 응력·전체 변형률 상대오차 ≤ 1e-10 | 온도 정확, 변위 ≤ 3.4e-15, 응력 ≤ 3.1e-14, σ_zz ≤ 1.1e-14, 변형률 ≤ 1.1e-14; 물리 에너지 1e-10 |
| K3 | 두 Dirichlet 변의 선형 온도를 받는 구속 막대, u_x = k α((T₁−T_ref)x + Gx²/2), k = 1+ν 또는 (1+ν)/(1−ν), 응력은 `refsol.thermoelastic_traction.parent_state`: 분할 8,16,32에서 변위 차수 ≥ 1.8 | 차수 1.95, 1.97(평면응력), 1.94, 1.97(평면변형률); 응력 차수 0.97–1.00; 온도 1e-9 K 재현 |
| K4 | 잘못된 열탄성 문서 16개(온도 단위 누락·비 K, 전도도 누락·0, α 누락·비유한, T_ref 음수·누락, 순수 Neumann 열, 음수·상충 온도, 고정 변의 flux, 음수 h, hinge, Joule 전용 키) exit 2, 출력 없음; `mechanics.elasticity2d`는 열 키를 거부 | 모두 거부 |

`refsol.elasticity_traction.polynomial_manufactured`와
`refsol.thermoelastic_traction.polynomial_manufactured`는 위치에 따라 변하는 체적력·traction·온도가
필요하고, 전단이 있는 `uniform_combined`에는 변위 성분이 상수인 변이 없어 변마다 상수인 이 문서로
표현할 수 없다. 그래서 J3·K3는 위의 2차 막대 해를 쓰며(테스트에서 Navier 방정식으로 솔버와
독립적으로 유도), K2는 전단 없는 `uniform_combined` 상태를 쓴다.

## 재료 영역과 이름 있는 경계

`geometry`에 `background`나 `shapes`가 있거나(0.2), 피처나 배경 재료가 있는
[버전 1 형상 블록](geometry_document.md)을 가진 `mechanics.elasticity2d`·`mechanics.thermoelastic2d`
문서는 여러 재료를 기술한다. [영역 열전도](thermal_regions2d.md)와 같은 형상·메시·경계 이름을 쓴다:
`mesh.size`(와 `min_angle`, 기본 28), 배경 위의 도형이나 피처, 나중 피처가 이긴다. 배경 재료가 없는
버전 1 균질 직사각형은 여전히 직사각형 문서다.

예제는 `elastic_regions`(내압을 받는 두꺼운 강관의 1/4, 구멍과 바깥면을 `boundary_tags`로 이름 붙임)와
`thermoelastic_regions`(50 K 가열한 강·알루미늄 바이메탈 띠, 왼쪽 끝 고정)다. 문서 예는
[영문 문서](../../../../../packages/simcase/mechanics2d.md#material-regions-and-named-boundaries)를 본다.

**재료.** 쓰인 재료마다 `young_modulus_pa`(> 0)와 `poisson_ratio`(−1 < ν < 0.5)가 있어야 한다.
열탄성 문서는 `thermal_expansion_per_k`(유한, 부호 있음)와 영역 열 키 `conductivity_w_mk`(> 0)도
필요하다. α는 선팽창 계수다. galerkin 인자 이름(`young_modulus`, `poisson_ratio`, `thermal_expansion_per_k`)에
문서의 SI 접미사를 붙인 것으로, E·ν·α는 직사각형 physics 키와 같다. 전도도 키는 영역 열의
`conductivity_w_mk`이며 직사각형 열탄성 physics 키 `thermal_conductivity_w_mk`가 아니다. 표에 그 이름을
쓰면 `conductivity_w_mk`를 쓰라고 알려 주며 거부한다. `materials` 표는 다른 영역 물리와 공유하며,
각 물리는 필요한 키를 읽고 있는 키는 모두 검사한다. 내장 광학 재료에서 성질을 가져오지 않는다.
`physics`의 `young_modulus_pa`, `poisson_ratio`, `thermal_expansion_per_k`,
`thermal_conductivity_w_mk`, `conductivity_w_mk`는 이름을 밝혀 거부한다.

**physics 키.** `type`, `plane`, `displacement_m`(필수)와 선택 `traction_pa`, `pressure_pa`,
`body_force_n_m3`(N/m³ 상수 `[fx, fy]`). 열탄성 문서는 `reference_temperature_k`(≥ 0, 필수)와 영역
열 키 `heat_source_w_m3`(수 또는 `{영역 이름: 수}`), `dirichlet_temperature_k`, `outward_flux_w_m2`,
`convection`을 더하며 영역 열 규칙을 따른다(Dirichlet 기준점 또는 양의 h; Dirichlet은 경계면 선택을
고정할 수 있고 flux·대류는 안 됨). `units`는 탄성이면 `length`만, 열탄성이면 `length`와
`temperature: "K"`다.

**경계 이름.** `displacement_m`, `traction_pa`, `pressure_pa`는 영역 열이 외부 데이터에 받는 이름을
받는다: 영역의 네 변, `boundary_tags` 이름, 빈 공간 피처 둘레의 `outer`, 곡선이 모두 외부에 있는 경계
선택. 경계면 선택은 이름을 밝혀 거부한다: galerkin은 외부 절점만 고정하고 traction은 외부 변이 필요하다.
이름 없는 외부 경계(빈 공간 둘레 포함)는 traction이 없다.

- `displacement_m`: `{이름: {"x": m, "y": m}}`. 적힌 성분을 그 경계의 모든 절점에 처방한다. 공유 절점을
  다른 값으로 고정하는 두 이름은 실행할 때 거부한다.
- `traction_pa`: `{이름: [tx, ty]}`, Pa 단위의 전역 직교좌표 상수 벡터.
- `pressure_pa`: `{이름: p}`(Pa), 경계 변마다 바깥 법선 `n`에 대한 traction `−p n`. 양의 압력이 물체를
  누른다. 곡선인 이름 있는 경계에 필요한 하중이다(기준 경계에서 galerkin `−p·normal` 콜백, 추종 갱신 없음).
- 한 경계에는 하중 하나: `traction_pa`와 `pressure_pa`에 같은 이름, 또는 메시 변을 공유하면서 둘 다
  하중을 받는 두 이름은 거부한다. 같은 변위 성분이 처방된 변의 0 아닌 traction·압력 성분은 직사각형처럼
  거부한다.

**강체 규칙.** 읽을 때 어떤 경계가 `x`를, 어떤 경계가 `y`를 고정해야 한다. 실행할 때 메시의 연결된
부분마다(빈 공간이 몸체를 나눌 수 있음) 평면 강체 운동 셋이 모두 막혀야 하며, 막히지 않은 부분은 그
영역 이름과 함께 거부한다. galerkin이 쓰는 rank 검사와 같다.

**거부.** 축대칭 구성 요소(평면 역학은 회전체를 기술하지 않음), 빈 공간 배경, 영역이 잘라 내거나 너무
얇은 피처·도형, `mesh.subdivisions`, plot, single이 아닌 study. 읽을 때 찾은 거부는 CLI 종료 코드 2,
메시에서 찾은 거부(고정되지 않은 부분, 두 번 고정된 공유 절점, 메시 변 없는 이름, 겹친 하중)는 영역 열처럼
종료 코드 1이다. 메시 상한(`max_input_vertices`, `max_nodes`, `max_triangles`,
[호출자를 위한 메시 상한](thermal_regions2d.md#호출자를-위한-메시-상한))은 영역 문서에 적용되며, 직사각형
문서는 거부한다.

**실행과 결과.** 실행기는 영역 열처럼 영역을 한 번 메시하고(문서의 마이크로미터 사본을 meshine으로 메시한 뒤 절점을 한 번
미터로 바꿈) E·ν·α를 영역 이름으로
대응시켜 `solve_elasticity`를, 또는 영역별 전도도로 `solve_steady_heat`, `freeze_temperature`,
`solve_thermoelasticity`를 부른다. 결과 ID는 `mechanics.elasticity2d-regions-result-v1`(배치
`mechanics2d-p1-regions-v1`)과 `mechanics.thermoelastic2d-regions-result-v1`(배치
`thermoelastic2d-p1-regions-v1`)이다. 배열은 직사각형 배치의 배열에 `triangle_regions`(삼각형마다 영역
번호, `int64`)를 더한 것이다. 요약은 스칼라 재료 항목 대신 `region_names`(`triangle_regions`의 번호
순서), `regions`(영역마다 재료, 삼각형 수, 메시 면적 m²), `materials` 표, 경계 데이터(`displacement_m`,
`traction_pa`, `pressure_pa`와 그 부호, 열탄성은 열 데이터), 메시(절점, 삼각형, 크기, 요청·달성 최소각)를
담는다. 진단, 단위, 저장은 직사각형 결과와 같다. `simcase.export`는 두 영역 배치를 아직 받지 않는다(지원하지 않는 필드
배치로 거부).

`units.length`를 따르는 것은 길이(형상, `mesh.size`)뿐이고, SI 접미사가 붙은 값은 길이 단위와 상관없이 SI다.
같은 문서를 m, mm, µm, nm로 쓰면 저장 배열이 비트까지 같다(같은 파일의 회귀 시험; 2026-11-08 독립 단위
검토가 측정, 사전 등록 아님). 저장 좌표는 마이크로미터 메시에 1e-6을 곱한 값이라 끝자리가 어긋날 수 있다
(0.1 m가 0.09999999999999999로 읽힘). 절점은 허용오차로 고른다.

**검증**(`tests/simcase/test_mechanics_regions.py`; R0–R7은 2026-11-08 코드 전에 HQ 작업 기록에
사전 등록했고 같은 날 Linux, Python 3.12, 고정 환경에서 측정):

| 검사 | 기준 | 측정 |
|---|---|---|
| R0 | `elastic_plate`·`thermoelastic_bar`: 저장 배열과 요약(시간·버전 제외) SHA-256 변경 전후 동일 | 동일 |
| R1 | 같은 메시에서 영역 실행 = galerkin 직접 호출, 바이트 동일(압력·traction·체적력 탄성과 영역별 열원·flux·대류 열탄성, 둘 다 두 평면). 역학 인자는 시험에서 실행기와 같은 방식으로 다시 만들므로 R1은 넘기기를, R2–R5는 물리(R4는 압력 부호)를 검사 | 바이트 동일 |
| R2 | 직렬 두 층(ν = 0, E 200·70 GPa), 버전 1과 0.2, 두 평면: 끝 변위 s(L₁/E₁ + L₂/E₂)와 σxx = s, 1e-10 이내 | 변위 ≤ 2.7e-15, 응력 ≤ 1.8e-14 |
| R3 | 병렬 두 층(ν = 0.3), 끝 변위 처방: 끝 반력 Σ E′ᵢhᵢ d/L, 1e-10 이내(평면응력 E′ = E, 평면변형률 E/(1−ν²)) | ≤ 2.2e-14 |
| R4 | Lamé 관(a = 3, b = 9 mm, 평면변형률, `boundary_tags` 이름으로 내압): h = 0.25 mm에서 최대 절점 반지름 오차 ≤ u_r(a)의 1e-2; h = 0.5, 0.25, 0.125 mm에서 차수 ≥ 1.8; 구멍 선택이 태그와 같은 변위 | 1.4e-2, 3.1e-3, 8.4e-4(차수 2.22, 1.89); 동일 |
| R5 | 구속된 두 층 자유 팽창(+50 K, ν = 0, 두 평면): 끝 변위 ΔT(α₁L₁ + α₂L₂)와 영역별 σyy = −EᵢαᵢΔT, 1e-10 이내 | ≤ 1.5e-14, ≤ 6.3e-15 |
| R5b | 직렬 전도(k 45·237 W/(m K), 400→300 K): 계면 온도 1e-9 이내, 끝 변위가 닫힌 적분식과 2e-3 이내 | 3.7e-16, 2.5e-6 |
| R6 | 이름 밝힌 거부 35개(변위·traction·압력의 경계면 선택, 모르는 이름, physics의 재료 키, 빠지거나 잘못된 재료 키, 빈 공간 배경, 떨어진 피처·도형, 축대칭, subdivisions, units, 고정되지 않은 부분, 두 번 고정된 공유 절점, 겹친 하중, 같은 이름이나 다른 이름으로 처방된 성분에 준 압력·traction, 메시 변 없는 변, 열탄성 열 거부); 읽을 때 CLI 종료 2·메시에서 1, 출력 없음; 접선으로 고정하고 법선으로 누른 경계는 받음 | 모두 거부; 받음 |
| R7 | 메시 상한이 영역 기계에 전달, 직사각형 문서는 거부 | 통과 |

R4의 크기는 h = 1 mm(16각형 구멍, 벽 두께에 요소 약 둘)의 첫 측정 뒤에 정했다. 그 수준에서 0.5 mm까지의
차수는 0.97로, 점근 범위 전이라 검사에서 뺐다. 사전 등록 밖의 검사: 바이메탈 예제의 끝 처짐이
Timoshenko 바이메탈 식(보 이론)과 1.3 % 이내이며 2 %로 검사한다.

## 한계

직사각형 문서: 균질 등방 직사각형 하나, 변마다 상수인 데이터. 영역 문서: 구간별 상수 등방 재료, 이름 있는
경계마다 상수 traction·압력, 경계면 변위·하중 없음, 축대칭 없음. 공통: 정적 소변형률, 단일 study. 일반
법선/접선·분포 traction, 점 하중, 동역학, 3D, Studio 양식은 없다. 열응력은 같은 메시의 정상 열전도에서
단방향으로만 온다: 역학 되먹임, 온도 의존 물성, 과도 온도, 외부에서 처방한 온도장은 없다(Python
[과도](../galerkin/transient_thermal_mechanical.md)·[처방 온도](../galerkin/prescribed_temperature_thermoelasticity.md)
흐름은 Python 전용). 구조적으로 유효한 모델도 수치적으로
실패할 수 있다(비압축성에 가까운 평면변형률, 극단적 종횡비). 입력 검증 통과는 정확도 보증이 아니다.
