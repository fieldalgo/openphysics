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
`materials:{}`를 사용한다. 도형·영역·sweep·재메시·두께는 없다. `units`에는 `length`만
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

## 한계

균질 등방 직사각형 하나, 변마다 상수인 데이터, 정적 소변형률, 단일 study. 영역·도형, 법선/접선
traction, 분포·점 하중, 동역학, 3D, Studio 양식은 없다. 열응력은 같은 메시의 정상 열전도에서
단방향으로만 온다: 역학 되먹임, 온도 의존 물성, 과도 온도, 외부에서 처방한 온도장은 없다(Python
[과도](../galerkin/transient_thermal_mechanical.md)·[처방 온도](../galerkin/prescribed_temperature_thermoelasticity.md)
흐름은 Python 전용). 구조적으로 유효한 모델도 수치적으로
실패할 수 있다(비압축성에 가까운 평면변형률, 극단적 종횡비). 입력 검증 통과는 정확도 보증이 아니다.
