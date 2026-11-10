# 선형탄성·열탄성 문서

[English](../../../../../packages/simcase/mechanics2d.md) | **한국어**

`mechanics.elasticity2d`(등온)와 `mechanics.thermoelastic2d`(정상 열전도 후 같은 메시의 열응력)의
JSON/CLI 규범 원본은 위 영문 문서다. 이 페이지는 같은 계약의 한국어 안내다. 수치 풀이와 기존
허용오차는 [2D 탄성](../galerkin/elasticity2d.md), [직교좌표계 경계 traction](../galerkin/elasticity_traction.md),
[정상 열전도](../galerkin/thermal_steady2d.md), [열탄성 traction](../galerkin/thermoelastic_traction.md)
계약을 따르며, 이 adapter는 새로운 이산화를 추가하지 않는다.

## 범위·입력

문서는 [형식 0.3](document_format.md)이다. 모든 값이 단위를 함께 쓰고(`"200 GPa"`, `"0 mm"`,
`"1 MPa"`) 키는 레지스트리 물리량 이름이다. 형식 0.2 역학 문서는 이름을 밝혀 거부한다(`E-FORMAT`).
이름 있는 physics 하나, `study:{"type":"single"}`(기본값), 평면 직사각형 `geometry`를 쓴다.
`geometry`에는 `length_unit`(예: `m`, `mm`, `um`), `depth`(깊이 1 m당 결과면 `null`, `"10 mm"` 같은
길이면 총량이 더해진다. 평면응력에서는 판 두께다), 그 단위의 일반 숫자인 네 `domain` 경계가 있다.
`mesh`는 양의 정수 `subdivision_count:[nx,ny]`, `materials`는 `{}`다. sweep·재메시는 없다. 형상이 재료
영역을 선언하는 문서는 대신 [영역 계약](#재료-영역과-이름-있는-경계)을 따른다. 이 절과 다음 절은 직사각형
문서를 설명한다. 알 수 없는 키(`E-KEY-UNKNOWN`), 비유한 수, 숫자 대신 boolean, 모서리의 상충 조건은
거부한다. 할당 전 최대 200,000 삼각형을 검사한다. results 기본값은 `save_fields:true,plots:false`이며
plot과 Studio 실행은 지원하지 않는다.

`mechanics.elasticity2d`의 physics 항목:

| 키 | 값 |
|---|---|
| `plane` | `"stress"` 또는 `"strain"`(필수) |
| `youngs_modulus` | 양수, 예: `"200 GPa"`(메뉴 `Pa kPa MPa GPa psi ksi`; `"200 mPa"`는 밀리파스칼이라 거부). `young_modulus`, `E`는 "did you mean youngs_modulus"와 함께 알 수 없는 키다 |
| `poisson_ratio` | 단위 없는 수, −1 < ν < 0.5(양 끝 제외). 문자열은 거부한다. 0 미만과 0.49 초과는 경고(`W-MAGNITUDE`). 평면변형률 P1 요소는 ν가 0.5에 가까워지면 locking이 생기므로 범위 통과가 정확도 보증은 아니다 |
| `prescribed_displacement` | 필수: `{변: {"x": "0 mm", "y": "0 mm"}}`. 변은 `left,right,bottom,top`, 적은 변마다 `x`, `y` 중 하나 이상(메뉴 `pm nm um mm m in mil`; `"0 mm"`도 써야 한다). 적은 성분은 그 변의 모든 절점에 지정되고 다른 성분은 자유다. 인접한 두 변이 같은 성분을 지정하면 공유 모서리에서 값이 같아야 한다(SI 값으로 비교). `z`, `r`, `"fixed"`는 거부한다 |
| `traction` | 선택: `{변: ["1 MPa", "0 MPa"]}` 또는 `{변: {"unit": "MPa", "values": [1, 0]}}`. 정확히 두 성분인 전역 직교좌표 벡터이며 변을 따라 상수다(법선/접선 성분이 아님). 성분 객체는 거부한다: 빠진 성분이 자유로 읽힐 수 있다. 같은 변에서 변위가 지정된 성분의 traction은 0이어야 한다(반력에 흡수될 뿐이기 때문) |
| `body_force_density` | 선택: `["0 N/m^3", "-77000 N/m^3"]`(메뉴 `N/m^3 kN/m^3 N/mm^3`). 없으면 체적력이 없으며 `defaults_applied`에 기록한다 |

변위도 traction도 없는 변은 traction이 없으며 `physics.<name>.traction.<side>`에 `I-DEFAULT-BOUNDARY`로
한 번 보고한다. 이름을 밝혀 거부하는 것: 직사각형의 `gauge_pressure`(traction을 쓰거나 영역 문서를 쓸 것),
`absolute_pressure`(`E-ABSOLUTE-AS-LOAD`: 절대압은 하중이 아니다), `force`와 `force_per_depth`(점 하중 없음),
`gravitational_acceleration`(중력에는 이 릴리스가 읽지 않는 질량 밀도가 필요하다. 무게는 `body_force_density`로
준다), `mechanics.elasticity2d`의 열 단계 키 모두.

**강체 모드 규칙.** 구속은 평면 강체 운동 u = (a − θy, b + θx) 세 개를 모두 막아야 한다.
어떤 변이 `x`를, 어떤 변이 `y`를 지정하고, 회전 θ가 막혀야 한다. 회전은 `left` 또는
`right`에 `x`를, `bottom` 또는 `top`에 `y`를, `bottom`과 `top` 양쪽에 `x`를, 또는 `left`와
`right` 양쪽에 `y`를 지정할 때만 막힌다. 수평 변 하나에 `x`, 수직 변 하나에 `y`만 지정하면
두 변의 모서리를 축으로 하는 hinge가 남으므로 거부한다. 이 규칙은 메시를 만들기 전에 문서만으로
판정하며, 생성한 메시에 대한 솔버의 rank 검사와 일치한다(테스트에서 모든 조합을 확인).

### 정상 열전도 후 열응력

`mechanics.thermoelastic2d`는 같은 역학 키에 다음을 더한다:

| 키 | 값 |
|---|---|
| `stress_free_temperature` | 필수, 0 K보다 큰 절대온도, 예: `"293.15 K"`, `"20 degC"`. 물체에 열변형률이 없는 온도다. `reference_temperature`는 "did you mean stress_free_temperature"와 함께 알 수 없는 키다 |
| `linear_expansion_coefficient` | 유한, 부호 있음, 예: `"23 ppm/K"`(메뉴 `1/K ppm/K um/(m K)`; `"23 ppm/degC"`는 K로 고치는 fix와 함께 거부). `mean_linear_expansion_coefficient`, `volumetric_expansion_coefficient`는 이름을 밝혀 거부한다 |
| `thermal_conductivity` | 양수, 예: `"237 W/(m K)"` |
| `prescribed_temperature.<side>` | 0 K보다 큰 절대온도. 필수이며 양의 대류 계수가 온도를 고정하면 `{}`일 수 있다 |
| `inward_heat_flux.<side>` | 선택, **몸체로 들어가는 쪽이 양수**(0.2 `outward_flux_w_m2`의 부호를 뒤집은 값). `outward_heat_flux`는 알 수 없는 키다("inputs are inward_") |
| `convection.<side>` | `{"heat_transfer_coefficient": "25 W/(m^2 K)", "ambient_temperature": "300 K"}` |
| `heat_source_density` | 선택, 예: `"20000 W/m^3"`. 없으면 열원이 없다(`defaults_applied`) |

이는 [정상 열전도](thermal_steady2d.md)·[경계조건](thermal_steady_boundary2d.md) 계약의 변별 상수 열
데이터다: 고정 변 하나 이상 또는 양의 대류 계수가 필요하고, 고정 변에는 자연 경계조건을 줄 수 없으며,
모서리 값이 일치해야 한다. 열 조건이 없는 변은 단열이며 `physics.<name>.inward_heat_flux.<side>`에
`I-DEFAULT-BOUNDARY`로 보고한다. 절대온도(무응력·고정·주위 온도)는 0 K보다 커야 한다(`E-DOMAIN`).
형식 0.2는 0 K를 허용했다. runner는 메시에서 `galerkin.thermal.solve_steady_heat`를 풀고
`galerkin.thermoelasticity.freeze_temperature`로 절점 온도를 고정한 뒤 역학 인자로
`solve_thermoelasticity`를 호출한다. `traction`은 Python 계약과 같이 **전체** 물리 σ·n이며 열
traction으로 보정하지 않는다. 연계는 단방향이다: 열로 되먹임 없음, 온도 의존 재료 없음, 교차 메시
전달 없음.

형식 0.2 키는 새 이름을 알려 주며 거부한다(`E-KEY-UNKNOWN`). 바깥쪽 열유속은 값의 부호를 뒤집어
쓰라고 알려 주며, 의미가 바뀌므로 자동 fix는 주지 않는다:

| 형식 0.2 | 형식 0.3 |
|---|---|
| `units.length`, `units.temperature` | `geometry.length_unit`; 모든 값이 단위를 함께 쓴다 |
| `mesh.subdivisions` | `mesh.subdivision_count` |
| `young_modulus_pa` | `youngs_modulus` |
| `displacement_m` | `prescribed_displacement` |
| `traction_pa` | `traction` |
| `body_force_n_m3` | `body_force_density` |
| `pressure_pa`(영역) | `gauge_pressure`, 부호 그대로 |
| `reference_temperature_k` | `stress_free_temperature` |
| `thermal_expansion_per_k` | `linear_expansion_coefficient` |
| `thermal_conductivity_w_mk`, 재료 표의 `conductivity_w_mk` | `thermal_conductivity` |
| `dirichlet_temperature_k` | `prescribed_temperature` |
| `outward_flux_w_m2` | `inward_heat_flux` = −이전 값 |
| `convection.<side>.{h_w_m2k, ambient_temperature_k}` | `convection.<side>.{heat_transfer_coefficient, ambient_temperature}` |
| `heat_source_w_m3` | `heat_source_density` |
| `mesh.size`, `mesh.min_angle`(영역) | `mesh.element_size`(단위를 쓴 길이), `mesh.minimum_angle`(기본 `"28 deg"`) |

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
plane, E, ν, 체적력(없으면 `(0, 0)`), 문서 순서의 traction으로 `galerkin.elasticity.solve_elasticity`를
호출한다. 문서 실행과 같은 인자의 직접 호출은 byte 단위로 같은 배열을 준다.

성공은 `model.json`(작성한 문서), `log.txt`(첫 줄은 범위, 마지막은 모든 진단), `summary.json`, 선택적
`fields.npz`를 저장한다. 기존 출력 소유권·실패 정리 기능을 재사용하며 빈 폴더·symlink 포함 기존 경로는
거부한다. 성공 summary를 마지막에 쓰고 중단된 저장에는 `.incomplete`가 남는다. NPZ에는 숫자 배열과
Unicode metadata만 있어 `allow_pickle=False`로 읽는다.

결과 식별자: `mechanics.elasticity2d-result-v2`와 layout `mechanics2d-p1-v2`,
`mechanics.thermoelastic2d-result-v2`와 layout `thermoelastic2d-p1-v2`(형식 0.2 식별자 `-result-v1`,
`mechanics2d-p1-v1`, `thermoelastic2d-p1-v1`은 폐기되었고 `simcase export`가 이름을 밝혀 거부한다).
모든 값은 SI다:

| NPZ 키 | 모양 | 단위 | 의미 |
|---|---|---|---|
| `node_coordinates` | (N,2) | m | 절점 좌표 |
| `triangles` | (T,3) | (구조) | 연결 |
| `displacement`(x, y) | (N,2) | m | 절점 (u_x, u_y) |
| `strain` | (T,3) | 1 | 요소 변형률, 성분 `strain_xx, strain_yy, engineering_shear_strain_xy`(γ_xy = 2 ε_xy). 열탄성은 전체 변형률 |
| `stress` | (T,3) | Pa | 요소 응력 `stress_xx, stress_yy, stress_xy` |
| `applied_force_per_depth` | (N,2) | N/m | 체적력+traction의 consistent 하중 |
| `reaction_force_per_depth` | (N,2) | N/m | 지정 DOF의 K·u − load(그 외 0): 구속이 물체에 주는 힘 |
| `residual_force_per_depth` | (N,2) | N/m | 모든 DOF의 K·u − load |
| `prescribed_node_ids`, `prescribed_components`, `prescribed_displacement` | (K,) | (구조), (구조), m | 지정 DOF(성분 0 = x, 1 = y)와 값 |

열탄성 결과는 다음을 더한다:

| NPZ 키 | 모양 | 단위 | 의미 |
|---|---|---|---|
| `temperature`, `heat_flux`, `generated_heat_rate_per_depth`, `reaction_heat_rate_per_depth`, `residual_heat_rate_per_depth`, `outward_prescribed_heat_rate_per_depth`, `ambient_convective_heat_rate_per_depth`, `outward_convective_heat_rate_per_depth`, `applied_heat_rate_per_depth`, `thermal_prescribed_node_ids`, `prescribed_temperature` | | K, W/m², W/m | 역학이 사용한 정상 열전도 해. [열전도](thermal_steady_boundary2d.md)와 같다(flux·대류가 없으면 열률은 0) |
| `thermal_strain`, `elastic_strain` | (T,3) | 1 | 성분 `thermal_strain_xx, …, engineering_shear_thermal_strain_xy`, `elastic_`도 같다. `strain` = thermal + elastic |
| `stress_zz`, `strain_zz` | (T,) | Pa, 1 | 면외 응력(평면변형률) 또는 변형률(평면응력) |
| `thermal_equivalent_force_per_depth`, `applied_body_force_per_depth`, `applied_traction_force_per_depth` | (N,2) | N/m | 열 등가 하중과 `applied_force_per_depth`의 두 부분 |

변형률·응력은 P1 요소마다 상수다(`field_locations`는 `triangle_centroids`). `field_components`가 각
배열의 성분 이름을 준다. `summary.json`에는 식별자, `diagnostics` 목록, `defaults_applied`,
`resolved_inputs`(각 입력의 작성 문자열, SI 값, 단위), `extent` 줄, `timing.wall_time`, `field_units`,
`field_locations`, `field_shapes`, `field_components`, `plane`, `youngs_modulus`, `poisson_ratio`(단위 없는 수),
주었을 때의 `body_force_density`, `mesh`(`nodes`, `triangles`), `study`, `balance`가 있으며 값마다
`{"value", "unit"}`(x·y 힘은 `{"unit", "values"}`)이다. 열탄성 summary는 `linear_expansion_coefficient`,
`thermal_conductivity`, `stress_free_temperature`와 고정한 온도의 `temperature_snapshot` 해시(`mesh_hash`,
`temperature_hash`, `snapshot_hash`)를 더한다.

| `balance` 키 | 의미 | 단위 |
|---|---|---|
| `applied_force_per_depth` | 성분별 적용(외부) 하중 합 | N/m |
| 열탄성: `thermal_equivalent_force_per_depth` | 열 등가 하중 합 | N/m |
| `reaction_force_per_depth` | 지지 반력 합 | N/m |
| `force_imbalance_per_depth` | 성분별 적용(+열) 하중 + 반력 | N/m |
| `maximum_residual_force_per_depth` | 자유 DOF 최대 잔차 | N/m |
| `strain_energy_per_depth` | 탄성: ½ uᵀKu; 열탄성: 물리 탄성 에너지 ½ ∫ σ:ε_el | J/m |
| 열탄성: `stiffness_energy_functional_per_depth` | 솔버의 ½ uᵀKu(열 하중 항을 포함하므로 저장 에너지가 아님) | J/m |
| `maximum_displacement` | 최대 절점 변위 크기 | m |
| `maximum_stress` | 요소 전체에서 면내 직교 응력 성분 절댓값의 최대 | Pa |
| 열탄성: `generated_heat_rate_per_depth`, `outward_heat_rate_per_depth`, `heat_rate_imbalance_per_depth`, `maximum_residual_heat_rate_per_depth`, `minimum_temperature`, `maximum_temperature` | 열 단계, Joule 가열과 같다 | W/m, K |

`depth`가 있으면 `*_per_depth` 값마다 총량(`applied_force`, `strain_energy`, …, 깊이당 값 × 깊이)이
뒤따른다. 없으면 결과는 깊이 1 m당이며 총량은 없다. 열탄성 결과에서 형식 0.2의 `strain_energy_j_per_m`은
`stiffness_energy_functional_per_depth`, `physical_elastic_energy_j_per_m`은 `strain_energy_per_depth`가
되었다. 형식 0.2의 `units`, `mesh_length_unit`, `diagnostic_units`, 성분 목록은 없어졌다.

CLI 종료값: 입력 오류 2(출력 폴더 없음), 풀이·I/O 오류(규칙이 예상하지 못한 특이 행렬,
비유한 값, 이미 있는 출력) 1, 성공 0. 저장한 필드는 `simcase.export`로 ParaView에서 볼 수
있다([ParaView로 보기](overview.md#paraview로-보기)): 점 데이터 `displacement`와 절점 힘 배열(z = 0 벡터;
열탄성 배치는 `temperature`와 절점 열률을 스칼라로 더함), 셀 데이터는 이름 있는 성분마다 스칼라 하나
(`strain_xx`, `strain_yy`, `engineering_shear_strain_xy`, `stress_xx`, `stress_yy`, `stress_xy`; 열탄성:
`heat_flux`, `stress_zz`, `strain_zz`와 `thermal_strain_…`, `elastic_strain_…` 성분), FieldData `units`와
`conventions` 블록이다. 내보내기는 저장된 배열을 복사할 뿐 이 계약에 다른 것을 더하지 않는다.

## 검증

`tests/simcase/test_mechanics.py`가 사전 등록한 gate를 담는다. 아래 값은 Linux, Python 3.12,
NumPy 2.5.4, SciPy 1.18.1(2026-11-02, 형식 0.2) 측정값이며, 형식 0.3이라고 적은 행은 2026-11-10에 쟀다.

| Gate | 기준 | 측정 |
|---|---|---|
| J1 | 문서 실행 == 같은 메시의 직접 `solve_elasticity`, byte 단위(평면응력·변형률, 원점 이동 mm domain, 체적력과 traction 둘) | 배열 여섯 개 모두 byte 일치 |
| J2 | `refsol.elasticity_traction.uniaxial`·`shear`, `m`,`mm`,`um`,`nm`, 두 plane: 변위·응력 상대오차 ≤ 1e-10 | 변위 ≤ 4.6e-15, 응력 ≤ 1.3e-14, 변형률 ≤ 9.1e-15 |
| J3 | 상수 체적력 막대 u = f/(λ+2μ)(Lx − x²/2, 0), x=0에서 x·y 고정, bottom·top에 y 고정: 분할 8,16,32에서 중심 변위 수렴 차수 ≥ 1.8 | 차수 1.95, 1.97(평면응력), 1.94, 1.97(평면변형률); 요소 응력 차수 0.95–0.98 |
| J4 | 잘못된 문서 33개(hinge, 한 성분만, 모서리 상충, 단위 없는 변위, `units` 블록, 길이 단위 누락·알 수 없음, 잘못된 plane, ν = 0.5·−1, 태그 목록, 지정 성분의 traction 등) exit 2, 출력 없음; 강체 규칙이 구속 집합 12개에서 솔버 rank 검사와 일치 | 모두 거부 |
| J5 | CLI validate/run/save, 기존 출력 거부(기존 summary 불변), 부분 저장 정리, 결과 사본·문서 snapshot 불변 | 통과 |
| J6 | Studio `/api/validate`·`_require_studio_physics`가 거부; Studio Node 검사 유지 | 통과 |
| J7 | `tools/wheel_consumers/test_mechanics_wheel.py`(단축 판·열탄성 막대 CLI, hinge 거부, VTU 내보내기)를 `check_platform_install.py`처럼 임시 폴더에서 `python -I`로 실행 | 통과 |
| K1 | 열탄성 문서 실행 == 같은 메시의 `solve_steady_heat` + `freeze_temperature` + `solve_thermoelasticity`, byte 단위(두 plane, 열원, flux·대류 변, 체적력, traction 둘) | 배열 16개 모두 byte 일치, snapshot 해시 동일 |
| K2 | 전단 0의 `refsol.thermoelastic_traction.uniform_combined`(법선응력 8·−2 MPa, +20 K), 네 변 고정 온도의 균일 온도, `m`,`mm`,`um`,`nm`, 두 plane: 온도·변위·면내 및 zz 응력·전체 변형률 상대오차 ≤ 1e-10 | 온도 정확, 변위 ≤ 3.4e-15, 응력 ≤ 3.1e-14, σ_zz ≤ 1.1e-14, 변형률 ≤ 1.1e-14; 물리 에너지 1e-10 |
| K3 | 두 고정 온도 변의 선형 온도를 받는 구속 막대, u_x = k α((T₁−T₀)x + Gx²/2), k = 1+ν 또는 (1+ν)/(1−ν), T₀는 무응력 온도, 응력은 `refsol.thermoelastic_traction.parent_state`: 분할 8,16,32에서 변위 차수 ≥ 1.8 | 차수 1.95, 1.97(평면응력), 1.94, 1.97(평면변형률); 응력 차수 0.97–1.00; 온도 1e-9 K 재현 |
| K4 | 잘못된 열탄성 문서 16개(`units` 블록, 화씨 온도, 전도도 누락·0, α 누락·비유한, 무응력 온도 음수·누락, 순수 Neumann 열, 음수·상충 온도, 고정 변의 flux, 음수 h, hinge, Joule 전용 키) exit 2, 출력 없음; `mechanics.elasticity2d`는 열 키를 거부 | 모두 거부 |
| J2, K2(형식 0.3) | 같은 gate를 형식 0.3 문서로. 길이 단위 사본은 picometre 격자로 읽는다 | J2 변위 ≤ 3.6e-15, 응력 ≤ 1.0e-14, 변형률 ≤ 9.1e-15; K2 온도 정확, 변위 ≤ 2.5e-15, 응력 ≤ 2.7e-14, σ_zz ≤ 8.6e-15, 변형률 ≤ 7.8e-15 |
| J3, K3(형식 0.3) | 같은 gate를 형식 0.3 문서로 | 같은 차수: 변위 1.95, 1.97과 1.94, 1.97; 요소 응력 0.94–0.98(J3), 0.97–1.00(K3) |
| 철자(형식 0.3) | `elastic_plate`, `thermoelastic_regions`, K1 직사각형의 값을 다른 철자와 메뉴 단위(`"200000 MPa"`, `"29000 ksi"` = `"29000000 psi"`, `"23 um/(m K)"`, `"20 degC"`, `"100 barg"`, 태그 배열 등)와 문자 별칭으로 다시 씀: 같은 SI 트리, 저장 배열, 요약 | 비트 동일; 별칭은 fix를 붙임 |
| 길이 단위(형식 0.3) | 네 예제의 형상 숫자를 m, mm, µm, nm로, 4 × 0.8 in 판을 101.6 × 20.32 mm 판과: 같은 picometre 정수, 배열, 요약; mm 숫자를 m로 선언하면 경고(직사각형, `W-GEOMETRY-SCALE`)하거나 메시 전에 거부(영역, `E-MESH-ESTIMATE`) | 비트 동일, 영역 각은 1e-13 상대 이내(최대 61 ulp); 경고와 거부 |
| 깊이(형식 0.3) | `depth` `null`, `"1 m"`, `"10 mm"`, `"40 mm"`: 깊이당 배열과 값 동일, 총량은 깊이당 값 × 깊이와 정확히 같음; `"0 m"`와 빠진 깊이는 거부 | 비트 동일; 거부 |
| 거부와 진단(형식 0.3) | G3 M5와 §4.6–4.7의 거부 111개를 코드와 경로로; `I-PM-ROUNDING`, `W-PM-ROUNDING`, `W-MAGNITUDE`(확인함·안 함), `I-UNUSED-PROPERTY`, `W-GAUGE-ATMOSPHERIC`, `I-DEFAULT-BOUNDARY`가 validate, run, `log.txt`, `summary.json`, `metadata_json`에 모두 나타남 | 명세대로 |
| 계기압 부호(형식 0.3) | `elastic_regions` 구멍의 양의 `gauge_pressure`가 구멍을 바깥으로 민다 | 구멍 절점마다 반지름 변위 > 0 |

`refsol.elasticity_traction.polynomial_manufactured`와
`refsol.thermoelastic_traction.polynomial_manufactured`는 위치에 따라 변하는 체적력·traction·온도가
필요하고, 전단이 있는 `uniform_combined`에는 변위 성분이 상수인 변이 없어 변마다 상수인 이 문서로
표현할 수 없다. 그래서 J3·K3는 위의 2차 막대 해를 쓰며(테스트에서 Navier 방정식으로 솔버와
독립적으로 유도), K2는 전단 없는 `uniform_combined` 상태를 쓴다.

철자·길이 단위 불변성, 깊이 총량, 거부와 그 경로, 진단, 결과 이름, 내보내기는
`tests/simcase/test_units_mechanics.py`가 검사한다. 단위·이름 일괄 변경 이후 이 검사들은 형식 0.3 문서로
돈다. 변경 전 코드의 0.2 문서와 변환한 문서는 배포 예제와 J1, K1, R1, R2, R4, R5 경우에서 같은 솔버 입력과
같은 저장 바이트를 준다(`tools/units_batch`). 그래서 J1, K1과 아래 영역 수치는 그대로다.

## 재료 영역과 이름 있는 경계

`geometry`에 `background`나 `shapes`가 있거나, 피처나 배경 재료가 있는
[버전 1 형상 블록](geometry_document.md)을 가진 `mechanics.elasticity2d`·`mechanics.thermoelastic2d`
문서는 여러 재료를 기술한다. [영역 열전도](thermal_regions2d.md)와 같은 형상·메시·경계 이름을 쓴다:
`mesh.element_size`(와 `minimum_angle`, 기본 `"28 deg"`), 배경 위의 도형이나 피처, 나중 피처가 이긴다.
배경 재료가 없는 버전 1 균질 직사각형은 여전히 직사각형 문서다.

예제는 `elastic_regions`(내압을 받는 두꺼운 강관의 1/4, 구멍과 바깥면을 `boundary_tags`로 이름 붙임)와
`thermoelastic_regions`(50 K 가열한 강·알루미늄 바이메탈 띠, 왼쪽 끝 고정)다. 문서 예는
[영문 문서](../../../../../packages/simcase/mechanics2d.md#material-regions-and-named-boundaries)를 본다.

**재료.** 쓰인 재료마다 `youngs_modulus`(> 0)와 `poisson_ratio`(−1 < ν < 0.5)가 있어야 한다. 열탄성
문서는 `linear_expansion_coefficient`(유한, 부호 있음)와 영역 열이 읽는 이름인 `thermal_conductivity`(> 0)도
필요하다(형식 0.2는 표에서 이를 `conductivity_w_mk`라 부르고 `thermal_conductivity_w_mk`를 거부했다. 이제
둘은 한 이름이다). 빠진 성질은 `E-PROPERTY-MISSING`, 이번 실행이 읽지 않는 성질(탄성 문서의
`thermal_conductivity` 등)은 `I-UNUSED-PROPERTY`로 보고한다. `shear_modulus`, `bulk_modulus`,
`elasticity_tensor`와 평균·체적 팽창 계수는 이름을 밝혀 거부한다. `materials` 표는 다른 영역 물리와
공유한다. 라이브러리 재료(`physmat:...`)는 아직 이 종류의 역학 성질을 갖지 않아 이름을 밝혀 거부한다.
`physics`의 `youngs_modulus`, `poisson_ratio`, `linear_expansion_coefficient`, `thermal_conductivity`는
이름을 밝혀 거부한다("from materials.<m>").

**physics 키.** `type`, `plane`, `prescribed_displacement`(필수)와 선택 `traction`, `gauge_pressure`,
`body_force_density`. 열탄성 문서는 `stress_free_temperature`(필수)와 영역 열 키 `heat_source_density`(값
하나 또는 `{영역 이름: 값}`), `prescribed_temperature`, `inward_heat_flux`, `convection`을 더하며 영역 열
규칙을 따른다(고정 온도 또는 양의 대류 계수; 고정 온도는 경계면 선택을 고정할 수 있고 flux·대류는 안 됨).

**경계 이름.** `prescribed_displacement`, `traction`, `gauge_pressure`는 영역 열이 외부 데이터에 받는
이름을 받는다: 영역의 네 변, `boundary_tags` 이름, 빈 공간 피처 둘레의 `outer`, 곡선이 모두 외부에 있는
경계 선택. 경계면 선택은 이름을 밝혀 거부한다: galerkin은 외부 절점만 고정하고 traction은 외부 변이
필요하다. 이름 없는 외부 경계(빈 공간 둘레 포함)는 traction이 없으며, 그중 영역의 변은
`I-DEFAULT-BOUNDARY`로 보고한다.

- `prescribed_displacement`: `{이름: {"x": "0 mm", "y": "0 mm"}}`. 적힌 성분을 그 경계의 모든 절점에
  처방한다. 공유 절점을 다른 값으로 고정하는 두 이름은 실행할 때 거부한다.
- `traction`: `{이름: ["1 MPa", "0 MPa"]}`, 전역 직교좌표 상수 벡터.
- `gauge_pressure`: `{이름: "10 MPa"}`, 주위보다 높은 압력(메뉴 `Pa kPa MPa GPa bar mbar psi ksi barg psig`).
  경계 변마다 바깥 법선 `n`에 대한 traction `−gauge_pressure · n`으로 준다: **양의 계기압은 물체를 누른다**.
  0.2 `pressure_pa`와 부호가 같다(기준 경계에서 galerkin `−p·normal` 콜백, 추종 갱신 없음). 절대압(`"10 bara"`,
  `"10 psia"`, `absolute_pressure` 키)은 거부하고(`E-ABSOLUTE-AS-LOAD`), `atm`은 메뉴에 없으며, 90–110 kPa
  사이 값은 경고한다(`W-GAUGE-ATMOSPHERIC`: 대기 절대압처럼 보인다).
- 한 경계에는 하중 하나: `traction`과 `gauge_pressure`에 같은 이름, 또는 메시 변을 공유하면서 둘 다
  하중을 받는 두 이름은 거부한다. 같은 변위 성분이 처방된 변의 0 아닌 traction·압력 성분은 직사각형처럼
  거부한다.

**강체 규칙.** 읽을 때 어떤 경계가 `x`를, 어떤 경계가 `y`를 고정해야 한다. 실행할 때 메시의 연결된
부분마다(빈 공간이 몸체를 나눌 수 있음) 평면 강체 운동 셋이 모두 막혀야 하며, 막히지 않은 부분은 그
영역 이름과 함께 거부한다. galerkin이 쓰는 rank 검사와 같다.

**거부.** 축대칭 구성 요소(평면 역학은 회전체를 기술하지 않음), 빈 공간 배경, 영역이 잘라 내거나 너무
얇은 피처·도형, `mesh.subdivision_count`, plot, single이 아닌 study. 읽을 때 찾은 거부는 CLI 종료 코드 2,
메시에서 찾은 거부(고정되지 않은 부분, 두 번 고정된 공유 절점, 메시 변 없는 이름, 겹친 하중)는 영역 열처럼
종료 코드 1이다. 메시 상한(`max_input_vertices`, `max_nodes`, `max_triangles`,
[호출자를 위한 메시 상한](thermal_regions2d.md#호출자를-위한-메시-상한))은 영역 문서에 적용되며, 직사각형
문서는 거부한다. 밀리미터 숫자를 미터로 선언한 영역 문서는 요소 수 추정으로 메시 전에 거부한다
(`E-MESH-ESTIMATE`: `elastic_regions`는 약 6.5e8, `thermoelastic_regions`는 3.2e9 삼각형, 상한 600,000).

**실행과 결과.** 실행기는 영역 열처럼 영역을 한 번 메시하고(문서의 마이크로미터 사본을 meshine으로 메시한 뒤
절점을 한 번 미터로 바꿈) E·ν·α를 영역 이름으로 대응시켜 `solve_elasticity`를, 또는 영역별 전도도로
`solve_steady_heat`, `freeze_temperature`, `solve_thermoelasticity`를 부른다. 결과 ID는
`mechanics.elasticity2d-regions-result-v2`(배치 `mechanics2d-p1-regions-v2`)와
`mechanics.thermoelastic2d-regions-result-v2`(배치 `thermoelastic2d-p1-regions-v2`)이다. 배열은 직사각형
배치의 배열에 `triangle_regions`(삼각형마다 영역 번호, `int64`)를 더한 것이다. 요약은 스칼라 재료 항목 대신
`region_names`(`triangle_regions`의 번호 순서), `regions`(영역마다 재료, 삼각형 수, 메시 `area`), SI의
`materials` 표, 경계 데이터(`prescribed_displacement`, `traction`, `gauge_pressure`와 `gauge_pressure_sign`,
열탄성은 열 데이터; `inward_heat_flux` 메아리는 몸체로 들어가는 쪽이 양수), 메시(`nodes`, `triangles`,
rad 단위 `minimum_triangle_angle`)를 담는다. 진단, `balance`, 저장은 직사각형 결과와 같다.
`simcase.export`는 두 영역 배치를 아직 받지 않는다(지원하지 않는 필드 배치로 거부).

`length_unit`을 따르는 것은 형상 숫자(domain과 피처)뿐이고 다른 값은 모두 자기 단위를 함께 쓴다. 같은
문서를 m, mm, µm, nm로 쓰면 저장 배열과 요약이 비트까지 같다. 예외는 달성한 최소 삼각형 각으로, 문서
자신의 숫자로 만든 삼각분할에서 재므로 1e-13 상대 이내에서 움직인다(이 예제에서 최대 61 ulp). 저장
좌표는 마이크로미터 메시에 1e-6을 곱한 값이라 끝자리가 어긋날 수 있다(0.1 m가 0.09999999999999999로
읽힘). 절점은 허용오차로 고른다.

**검증**(`tests/simcase/test_mechanics_regions.py`; R0–R7은 2026-11-08 코드 전에 HQ 작업 기록에
사전 등록했고 같은 날 Linux, Python 3.12, 고정 환경에서 측정):

| 검사 | 기준 | 측정 |
|---|---|---|
| R0 | `elastic_plate`·`thermoelastic_bar`: 저장 배열과 요약(시간·버전 제외) SHA-256 변경 전후 동일 | 동일 |
| R1 | 같은 메시에서 영역 실행 = galerkin 직접 호출, 바이트 동일(계기압·traction·체적력 탄성과 영역별 열원·flux·대류 열탄성, 둘 다 두 평면). 역학 인자는 시험에서 실행기와 같은 방식으로 다시 만들므로 R1은 넘기기를, R2–R5는 물리(R4는 압력 부호)를 검사 | 바이트 동일 |
| R2 | 직렬 두 층(ν = 0, E 200·70 GPa), 버전 1과 평면 영역, 두 평면: 끝 변위 s(L₁/E₁ + L₂/E₂)와 σxx = s, 1e-10 이내 | 변위 ≤ 2.7e-15, 응력 ≤ 1.8e-14 |
| R3 | 병렬 두 층(ν = 0.3), 끝 변위 처방: 끝 반력 Σ E′ᵢhᵢ d/L, 1e-10 이내(평면응력 E′ = E, 평면변형률 E/(1−ν²)) | ≤ 2.2e-14 |
| R4 | Lamé 관(a = 3, b = 9 mm, 평면변형률, `boundary_tags` 이름으로 내부 계기압): h = 0.25 mm에서 최대 절점 반지름 오차 ≤ u_r(a)의 1e-2; h = 0.5, 0.25, 0.125 mm에서 차수 ≥ 1.8; 구멍 선택이 태그와 같은 변위 | 1.4e-2, 3.1e-3, 8.4e-4(차수 2.22, 1.89); 동일 |
| R5 | 구속된 두 층 자유 팽창(+50 K, ν = 0, 두 평면): 끝 변위 ΔT(α₁L₁ + α₂L₂)와 영역별 σyy = −EᵢαᵢΔT, 1e-10 이내 | ≤ 1.5e-14, ≤ 6.3e-15 |
| R5b | 직렬 전도(k 45·237 W/(m K), 400→300 K): 계면 온도 1e-9 이내, 끝 변위가 닫힌 적분식과 2e-3 이내 | 3.7e-16, 2.5e-6 |
| R6 | 코드와 경로를 밝힌 거부(변위·traction·계기압의 경계면 선택, 모르는 이름, physics의 재료 키, 빠지거나 잘못된 재료 키, 빈 공간 배경, 떨어진 피처·도형, 축대칭, `subdivision_count`, `units` 블록, 길이 단위 누락, 고정되지 않은 부분, 두 번 고정된 공유 절점, 겹친 하중, 같은 이름이나 다른 이름으로 처방된 성분에 준 계기압·traction, 메시 변 없는 변, 열탄성 열 거부); 읽을 때 CLI 종료 2·메시에서 1, 출력 없음; 접선으로 고정하고 법선으로 누른 경계는 받음 | 모두 거부; 받음 |
| R7 | 메시 상한이 영역 역학에 전달, 직사각형 문서는 거부 | 통과 |

R4의 크기는 h = 1 mm(16각형 구멍, 벽 두께에 요소 약 둘)의 첫 측정 뒤에 정했다. 그 수준에서 0.5 mm까지의
차수는 0.97로, 점근 범위 전이라 검사에서 뺐다. 사전 등록 밖의 검사: 바이메탈 예제의 끝 처짐이
Timoshenko 바이메탈 식(보 이론)과 1.3 % 이내이며 2 %로 검사한다.

## 한계

직사각형 문서: 균질 등방 직사각형 하나, 변마다 상수인 데이터. 영역 문서: 구간별 상수 등방 재료, 이름 있는
경계마다 상수 traction·계기압, 경계면 변위·하중 없음, 축대칭 없음. 공통: 정적 소변형률, 단일 study. 일반
법선/접선·분포 traction, 점 하중, 질량 밀도에서 오는 중력, 동역학, 3D, Studio 양식은 없다. 열응력은 같은
메시의 정상 열전도에서 단방향으로만 온다: 역학 되먹임, 온도 의존 물성, 과도 온도, 외부에서 처방한 온도장은
없다(Python [과도](../galerkin/transient_thermal_mechanical.md)·[처방 온도](../galerkin/prescribed_temperature_thermoelasticity.md)
흐름은 Python 전용). 구조적으로 유효한 모델도 수치적으로 실패할 수 있다(비압축성에 가까운 평면변형률,
극단적 종횡비). 입력 검증 통과는 정확도 보증이 아니다.
