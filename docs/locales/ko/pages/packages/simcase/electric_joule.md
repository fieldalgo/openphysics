# 전기전도·Joule heating 문서

[English](../../../../../packages/simcase/electric_joule.md) | **한국어**

JSON/CLI 규범 원본은 위 영문 문서다. 이 페이지는 같은 계약의 한국어 안내다.
수치 풀이와 기존 허용오차는 [전기전도](../galerkin/electric_steady2d.md),
[단방향 Joule](../galerkin/joule_heating.md),
[온도 의존 Joule](../galerkin/temperature_joule_heating.md) 계약을 따른다.

## 범위·입력

이 절은 직사각형 형식이다. `electric.steady2d`와 `joule.steady2d`는
[재료 영역](#재료-영역-전기-정상-전도)도 받는다.
문서는 [형식 0.3](document_format.md)이다. 모든 값이 단위를 함께 쓰고(`"2 S/m"`, `"1 V"`,
`"300 K"`) 키는 레지스트리 물리량 이름이다. 형식 0.2 전기·Joule 문서는 이름을 밝혀
거부한다(`E-FORMAT`). 이름 있는 physics 하나, `study:{"type":"single"}`(기본값), 평면
직사각형 `geometry`를 쓴다. `geometry`에는 `length_unit`(예: `m`, `mm`, `um`),
`depth`(깊이 1 m당 결과면 `null`, `"40 mm"` 같은 길이면 총량이 더해진다), 그 단위의 일반
숫자인 네 `domain` 경계가 있다. `mesh`는 양의 정수 `subdivision_count:[nx,ny]`, `materials`는
`{}`다. 형상 목록·sweep·재메시·추가 열원은 지원하지 않는다. 알 수 없는 키(`E-KEY-UNKNOWN`),
비유한 수, 숫자 대신 boolean, 모서리의 상충 조건은 거부한다. 할당 전 최대 200,000 삼각형을
검사한다. results 기본값은 `save_fields:true,plots:false`이며 plot과 Studio 실행은 지원하지
않는다.

physics 항목:

| 키 | 종류 | 값 |
|---|---|---|
| `electrical_conductivity` | `electric.steady2d`, `joule.steady2d` | 양수, 예: `"2 S/m"`(메뉴 `S/m kS/m MS/m S/cm`; `"2 mS/m"`은 밀리지멘스 매 미터라 제안과 함께 거부). 모델 형식은 이름을 밝혀 거부한다: 이 종류에는 평가 온도가 없다 |
| `prescribed_electric_potential.<side>` | 세 종류 모두 | 예: `"1 V"`(메뉴 `uV mV V kV`); `"0 V"`도 써야 한다. 변 하나 이상 |
| `inward_current_density.<side>` | 세 종류 모두 | 선택, 예: `"2 A/m^2"`, **몸체로 들어가는 쪽이 양수**(0.2 `outward_current_a_m2`의 부호를 뒤집은 값). 전위 고정 변과 겹치면 거부한다. 단자 총량(`inward_current`, `inward_current_per_depth`)은 이름을 밝혀 거부한다 |
| `thermal_conductivity` | Joule | 양수, 예: `"1 W/(m K)"` |
| `prescribed_temperature.<side>` | Joule | 0 K보다 큰 절대온도, 예: `"300 K"`, `"26.85 degC"`. 키는 필수이며 대류가 온도를 고정하면 `{}`일 수 있다 |
| `inward_heat_flux.<side>` | Joule | 선택, 몸체로 들어가는 쪽이 양수(0.2 `outward_flux_w_m2`의 부호를 뒤집은 값). 같은 변의 대류와 더해진다 |
| `convection.<side>` | Joule | `{"heat_transfer_coefficient": "4 W/(m^2 K)", "ambient_temperature": "300 K"}` |
| `heat_source_density` | Joule | 이름을 밝혀 거부: 전류가 유일한 열원이다 |
| `electrical_conductivity`(모델) | `joule.temperature2d` | 필수, 아래 참조. 여기서 상수는 `E-VALUE-FORM` |
| `initial_temperature` | `joule.temperature2d` | 필수, 0 K보다 크고 `valid.temperature` 안 |
| `iteration` | `joule.temperature2d` | 필수, 아래 참조 |

변 이름은 `left,right,bottom,top`이다. 인접 고정 변은 공유 모서리에서 같은 값을 가져야 한다(SI
값으로 비교). 생성한 메시에서도 고정/자연 edge 충돌을 검사한다. 전기 조건이 없는 변은 전기적으로
절연이며 `physics.<name>.inward_current_density.<side>`에 `I-DEFAULT-BOUNDARY`로 한 번 보고한다.
열 조건이 없는 Joule 변은 단열이며 `physics.<name>.inward_heat_flux.<side>`에 보고한다. Joule
문서에는 고정 온도 또는 양의 대류 계수가 필요하다(순수 Neumann은 거부). 완전히 고정된 edge의
자연 경계 하중은 거부한다. 같은 메시의 전기 결과가 유일한 Joule 열원이다. 절대온도(고정·주위·
초기·기준 온도와 `valid` 경계)는 0 K보다 커야 한다(`E-DOMAIN`). 형식 0.2는 0 K를 허용했다.

`joule.temperature2d`는 `electrical_conductivity`를 모델로 준다.

```json
"electrical_conductivity": {
  "model": "linear_resistivity",
  "reference_conductivity": "2 S/m",
  "reference_temperature": "300 K",
  "resistivity_temperature_coefficient": "0.01 1/K",
  "valid": {"temperature": ["290 K", "400 K"]}
}
```

`σ(T) = reference_conductivity / (1 + resistivity_temperature_coefficient (T − reference_temperature))`로
형식 0.2와 같은 식이다. `reference_conductivity`는 양수, `reference_temperature`는
`valid.temperature` 안(`E-OUTSIDE-VALID`)이어야 하고, 범위 양 끝에서 분모와 전도도가 유한한
양수여야 한다. 분모가 선형이므로 이 검사가 구간 전체를 보장한다. 초기·고정·주위 온도는 구간
안이어야 한다(그 값의 경로에 `E-OUTSIDE-VALID`). `reference_resistivity`는 이름을 밝혀 거부하고,
`alpha`와 `conductivity_temperature_coefficient`는 `linear_resistivity`의 알 수 없는 키다. 반복 중
모든 절점 온도의 범위를 기존 솔버가 검사한다. 외삽·잘라내기·임의 함수·표현식 실행·모듈
import는 없다. 미터 단위 메시를 한 번 만들고, 각 삼각형 세 절점을 범위와 비교한 뒤 산술평균
온도에서 σ를 평가한다. 열전도도는 온도에 무관하다.

`iteration`(`temperature_tolerance`에 차원 있는 기본값이 없어서 필수): `relaxation_factor`(기본
0.5, `defaults_applied`에 기록; 레지스트리는 2까지 허용하지만 이 종류는 0 초과 1 이하),
`temperature_tolerance`(필수, 예: `"1e-8 K"`, `"1e-5 mK"`; `"1e-8 degC"`는 제안만 붙여 거부),
`relative_tolerance`(기본 1e-10, 1 이하), `iteration_limit`(기본 100, 양의 정수). 기존 완화
Picard 반복이 **완화 전** 온도·전도도 변화와 전기 재평가를 통한 비선형 열 잔차(≤1e-8)를
검사한다. 정지 조건은 `|ΔT| ≤ temperature_tolerance + relative_tolerance max(|T_i|, |H(T_i)|)`다.
선형 잔차·보존 gate는 바꾸지 않는다. 정규화와 정지식은 위 솔버 계약을 참조한다. 문서는 항상
Picard 반복을 쓰며 Python API의 `method="newton"`은 이 형식에 없다.

형식 0.2 키는 새 이름을 알려 주며 거부한다(`E-KEY-UNKNOWN`). 두 outward 입력은 부호를 뒤집은
값을 쓰라고 안내하며, 뜻이 바뀌므로 자동 수정은 없다.

| 형식 0.2 | 형식 0.3 |
|---|---|
| `units.length`, `units.temperature` | `geometry.length_unit`; 다른 값은 모두 단위를 함께 쓴다 |
| `mesh.subdivisions` | `mesh.subdivision_count` |
| `conductivity_s_m` | `electrical_conductivity` |
| `dirichlet_potential_v` | `prescribed_electric_potential` |
| `outward_current_a_m2` | `inward_current_density` = −이전 값 |
| `thermal_conductivity_w_mk` | `thermal_conductivity` |
| `dirichlet_temperature_k` | `prescribed_temperature` |
| `outward_flux_w_m2` | `inward_heat_flux` = −이전 값 |
| `convection.<side>.{h_w_m2k, ambient_temperature_k}` | `convection.<side>.{heat_transfer_coefficient, ambient_temperature}` |
| `conductivity_model`(`type`, `reference_conductivity_s_m`, `reference_temperature_k`, `alpha_per_k`, `temperature_range_k`) | `electrical_conductivity`(`model`, `reference_conductivity`, `reference_temperature`, `resistivity_temperature_coefficient`, `valid.temperature`) |
| `initial_temperature_k` | `initial_temperature` |
| `iteration.{relaxation, temperature_atol_k, relative_tolerance, max_iterations}` | `iteration.{relaxation_factor, temperature_tolerance, relative_tolerance, iteration_limit}` |

## 재료 영역 (전기 정상 전도)

형상에 영역이 있는 `electric.steady2d` 문서(feature나 배경 재료가 있는
[버전 1 형상 블록](geometry_document.md), 또는 평면 `background`와 `shapes`)는
[영역 열](thermal_regions2d.md)과 같은 형상·메시·경계 이름을 쓴다.

- **전도도**
  - `materials.<name>.electrical_conductivity`(양수, 예: `"58 MS/m"`)가 각 영역의 전도도다. 영역이 쓰는 모든 재료에 있어야 한다(`E-PROPERTY-MISSING`).
  - 같은 재료 표에 열 물성(`thermal_conductivity`, `volumetric_heat_capacity`)을 함께 둘 수 있다. 이 실행이 읽지 않는 물성은 `I-UNUSED-PROPERTY`로 보고한다. 재료의 모델 형식은 거부한다.
  - 라이브러리 재료(`physmat:...`)는 아직 이 물리의 전기전도도를 주지 않으므로 이름을 밝혀 거부한다. physics 항목에는 `electrical_conductivity`를 두지 않는다.
- **경계 데이터**
  - `prescribed_electric_potential`과 `inward_current_density`는 도메인 변, 형상이 선언한 외부 태그(`boundary_tags` 이름, 빈 공간 feature 경계의 `outer`), 외부 경계 선택을 받는다.
  - 두 영역 사이 경계면 선택은 둘 다 거부한다. 전기 솔버가 외부 절점만 고정하기 때문이다.
  - 다음은 이름을 밝혀 거부한다: 메시 변이 없는 이름, 같은 변에 전류를 준 두 이름, 다른 이름으로 고정된 경계의 변에 준 전류, 공유 절점을 서로 다른 전위로 고정하는 두 경계. 모르는 이름은 `E-SELECTION-UNKNOWN`이다.
- **이름 없는 경계**: 빈 공간 경계를 포함해 이름 없는 외부 경계는 전기적으로 절연이며, 조건 없는 도메인 변은 `I-DEFAULT-BOUNDARY`로 보고한다. 전위는 하나 이상 있어야 한다.
- **메시와 거부**: `mesh`는 영역 열처럼 `{"element_size", "minimum_angle", "element_count_limit", "controls"}`이고 영역 메시 한도가 적용된다. 빈 공간 배경과 축대칭 구성 요소는 거부한다.

**결과**
- 결과 형식은 `electric.steady2d-regions-result-v2`, 필드 layout은 `electric2d-p1-node-cell-regions-v2`이다.
- 필드는 직사각형 필드에 `triangle_regions`를 더한 것이다.
- 요약에는 `region_names`, `regions.<region>.{material, electrical_conductivity}`, `mesh.minimum_triangle_angle`(rad), `balance.outward_current_per_depth.<name>`이 더해진다.
  - 마지막 값은 고정된 경계마다 도체에서 나가는 전류이며(**몸체 밖으로 나가는 쪽이 양수**: 들어가는 쪽이 양수인 0.2 `diagnostics.terminal_reaction_current_a_per_m`의 부호를 뒤집은 값) 단위는 깊이 1 m당 A다.
  - 두 경계가 함께 고정한 절점은 이름 순서로 먼저인 경계에 센다.
- 같은 메시 변에 전위 이름 둘을 주거나, 고정 전위가 하나도 없는 도체 부분이 있으면 이름을 밝혀 거부한다.
- 영역 결과도 직사각형 결과처럼 VTU로 내보내며, 셀 데이터 `triangle_regions`가 더해진다.

영역 위의 정상 Joule 가열은 [다음 절](#재료-영역-정상-joule-가열)에 있다. `joule.temperature2d`는 직사각형 형식을 유지하며, 영역 형상은 리더가 그 키를 요구하기 전에 이름을 밝혀 거부한다.

독립 검증(`tests/simcase/test_electric_regions.py`, 미리 등록한 E1–E7):

| 확인 | 기준 | 결과 |
|---|---|---|
| 직렬 두 층 | 구간 선형 전위, I = V / Σ(L_i / (σ_i h)) | 절점 오차 1e-10 V 이하, 전류 상대 1e-10 |
| 병렬 두 층 | I = V Σ(σ_i h_i) / L | 상대 1e-10 |
| 동축 원형 전극(r = 3, 9 mm, 192각형) | I = 2πσ(V_a − V_b) / ln(b/a) | 메시 0.8, 0.4, 0.2 mm에서 상대 오차 2.0e-3, 6.6e-4, 1.4e-4(마지막 단계 차수 2.3) |
| Joule 전력 | 공급 전력 V·I | 상대 1e-10 |
| 직사각형 문서 | 이 변경 전 결과 | 직사각형 전기·Joule 예제 전부 비트 단위로 같음 |

## 재료 영역 (정상 Joule 가열)

형상에 영역이 있는 `joule.steady2d` 문서는 위의 영역 전기 전도를 풀고, 그 Joule 발열로
[영역 열](thermal_regions2d.md)을 데운다. 메시는 하나다.

- **전도도**
  - 영역이 쓰는 모든 재료에 `electrical_conductivity`와 `thermal_conductivity`가 둘 다 있어야 한다.
  - physics 항목에는 둘 다 두지 않고 `heat_source_density`도 두지 않는다. 열원은 전류뿐이다(다른 열원을 더하는 것은 지원하지 않는다).
- **경계 데이터**
  - `prescribed_electric_potential`과 `inward_current_density`는 영역 전기 전도가 받는 이름(외부 경계만)을 받는다.
  - `prescribed_temperature`, `inward_heat_flux`, `convection`은 영역 열이 받는 이름을 받는다. 그래서 고정 온도는 경계면 선택도 고정할 수 있다.
  - 전위가 하나 이상, 그리고 고정 온도나 양수 대류 계수가 있어야 한다.
- **그 밖**: 축대칭 구성 요소와 빈 공간 배경은 거부하며, 영역 메시 한도가 적용된다.

솔버는 열 하중이 절점마다 Joule 하중과 같은지, 바깥으로 나가는 열이 Joule 전력과 같은지 확인한다.

**결과**
- 결과 형식은 `joule.steady2d-regions-result-v2`, 필드 layout은 `electric-joule2d-p1-node-cell-regions-v2`이다.
- 필드는 직사각형 Joule 필드에 `triangle_regions`를 더한 것이다. 요약에는 `regions.<region>.{material, electrical_conductivity, thermal_conductivity}`, `mesh.minimum_triangle_angle`, 단자 전류가 들어간다.
- 직사각형 Joule 결과처럼 VTU로 내보내며 `triangle_regions`가 더해진다.
- 영역 위의 온도 의존 전도도(`joule.temperature2d`)는 아직 지원하지 않는다.

독립 검증(`tests/simcase/test_joule_regions.py`, 미리 등록한 J1–J7). 오차는 절점 온도 오차의 최댓값을 온도 상승으로 나눈 값이다.

| 확인 | 기준 | 결과 |
|---|---|---|
| 직렬 두 재료, 양 끝 Dirichlet | 구간 이차 T(x), T와 k dT/dx 연속 | 메시 0.25, 0.125, 0.0625 mm에서 2.1e-2, 4.6e-3, 1.1e-3(차수 2.1) |
| 같은 띠, 한 끝 대류 | Robin 끝 조건 | 1.2e-2, 2.7e-3, 6.5e-4(차수 2.1) |
| 같은 온도로 고정한 동축 전극(192각형) | T(r) − T0 = −C (ln r − ln a)(ln r − ln b) / 2, C = σV² / (k ln²(b/a)) | 0.4, 0.2, 0.1 mm에서 3.8e-3, 1.8e-3, 4.9e-4(마지막 단계 차수 1.9) |
| 전력 | 공급 V·I, Joule, 바깥으로 나가는 열 | 상대 1.4e-14까지 같음 |
| 직사각형 문서 | 이 변경 전 결과 | `joule_rectangle`, `joule_temperature`, `electric_rectangle` 필드 해시가 직전 커밋과 같음(작성 때 확인; 시험은 직사각형 경로를 타는지 확인) |

동축 확인은 0.8, 0.4, 0.2 mm로 미리 등록했고 거기서 실패했다. 마지막 단계 차수가 1.03이었다. 가장 큰 절점 오차는 Joule 발열(∝ 1/r²)이 가장 가파른 안쪽 전극 옆(r ≈ 3.3 mm)에 있고, 이 거친 비정렬 메시(h/a ≥ 0.07)에서는 아직 점근 영역이 아니다. 같은 메시에서 정확한 해석 발열로 영역 열만 풀어도 같은 꺾임이 나오므로(1.58, 1.17, 0.1 mm에서 1.99) Joule 결합 탓이 아니고, 원의 변 수를 메시와 함께 늘려도 꺾임이 남으므로(1.10, 1.40, 1.67) 고정된 경계 해상도 탓도 아니다. 같은 메시에서 면적 가중 L2 오차는 고르게 수렴한다(차수 1.60, 1.71, 2.16). 기준값은 그대로이고, 메시 열만 한 단계 더 곱다.

단위·이름 일괄 변경 이후 이 검증은 0.2 문서를 변환한 형식 0.3 문서로 돈다. 변경 전 코드의 0.2
문서와 변환한 문서는 같은 솔버 입력과 같은 저장 바이트를 내므로(`tools/units_batch`) 위 숫자는
모두 그대로다.

## 실행·저장

```sh
python -m simcase example joule_temperature > model.json
python -m simcase validate model.json
python -m simcase run model.json -o fresh-results
```

Python은 `Document.from_dict`/`Document.load`, `run(document)`,
`ElectricJouleRunResult.save(path)`를 사용한다. `fields`는 소유권이 분리된
숫자 배열 사본, `summary()`는 JSON 호환 사본을 반환한다. 호출자 입력이나 반환
사본 변경은 계산 기록을 바꾸지 않는다. 결과의 `doc`은 별도 snapshot이며 수정하면
저장이 거부된다. EM 전용 `build_mesh`/`solve_point`에는 명시적 거부가 있다.

성공은 `model.json`(작성한 문서), `log.txt`(첫 줄은 범위 줄, 끝은 모든 진단), `summary.json`,
선택적 `fields.npz`를 저장한다. 기존 출력 소유권·실패 정리 기능을 재사용하며 빈 폴더·symlink
포함 기존 경로는 거부한다. 성공 summary를 마지막에 쓰고 중단된 저장에는 `.incomplete`가
남는다. NPZ에는 숫자 배열과 Unicode metadata만 있어 `allow_pickle=False`로 읽는다.

결과 식별자는 `<physics-type>-result-v2`, layout은 `electric-joule2d-p1-v2`다(형식 0.2 식별자
`-result-v1`과 `electric-joule2d-p1-v1`은 은퇴했고 `simcase export`가 이름을 밝혀 거부한다).
값은 모두 SI다.

| NPZ 키 | 위치 | 단위 |
|---|---|---|
| `node_coordinates` | 절점 | m |
| `triangles` | 연결 | (구조) |
| `electric_potential` | 절점 | V |
| `electric_field`(x, y) | 삼각형 무게중심 | V/m |
| `current_density`(x, y) | 삼각형 무게중심 | A/m^2 |
| `electrical_conductivity` | 삼각형 무게중심 | S/m |
| `joule_power_density` | 삼각형 무게중심 | W/m^3 |
| `joule_power_per_depth` | 절점, Joule 하중 | W/m |
| `reaction_current_per_depth` | 절점, 고정 전위가 몸체로 주입하는 전류 | A/m |
| `outward_prescribed_current_per_depth` | 절점, 지정 전류 하중, 밖으로 양수 | A/m |
| `residual_current_per_depth` | 절점 | A/m |
| `electric_prescribed_node_ids`, `prescribed_electric_potential` | 전위 고정 절점 | (구조), V |
| Joule: `temperature`, `heat_flux`, `generated_heat_rate_per_depth`, `reaction_heat_rate_per_depth`, `residual_heat_rate_per_depth`, `outward_prescribed_heat_rate_per_depth`, `ambient_convective_heat_rate_per_depth`, `outward_convective_heat_rate_per_depth`, `applied_heat_rate_per_depth`, `thermal_prescribed_node_ids`, `prescribed_temperature` | [열](thermal_steady_boundary2d.md)과 같음 | K, W/m^2, W/m |
| `joule.temperature2d`: `evaluation_temperature` | 절점, σ를 평가한 T_i | K |

돌려주는 열 결과는 H(T_i)이고 σ는 T_i에서 평가한 값이며, 수렴 시 두 온도의 차이는 수렴 기준으로
제한된다.

`summary.json`에는 식별자, `diagnostics` 목록, `defaults_applied`, `resolved_inputs`(입력마다 작성한
글, SI 값, 단위), `extent` 줄, `timing.wall_time`, `field_units`·`field_locations`·`field_shapes`·
`field_components` 표, `mesh`(`nodes`, `triangles`), `study`, `balance`가 있고 값은 모두
`{"value", "unit"}`이다.

| `balance` 키 | 뜻 | 단위 |
|---|---|---|
| `current_imbalance_per_depth` | sum(반력 − 밖으로 지정 하중) | A/m |
| `maximum_residual_current_per_depth` | 자유 절점의 가장 큰 잔차 | A/m |
| `inward_electric_power_per_depth` | 공급 전력 sum(V I) | W/m |
| `joule_power_per_depth` | Joule 발열 적분 | W/m |
| `electric_power_imbalance_per_depth` | 공급 − Joule | W/m |
| Joule: `outward_heat_rate_per_depth` | sum(−반력 + 밖으로 지정 + 밖으로 대류) | W/m |
| Joule: `heat_rate_imbalance_per_depth`, `maximum_residual_heat_rate_per_depth` | 밖으로 − 열원; 자유 절점 최대 잔차 | W/m |
| Joule: `minimum_temperature`, `maximum_temperature` | | K |
| 영역: `outward_current_per_depth.<name>` | 고정 경계마다, 밖으로 양수 | A/m |

`depth`가 있으면 `*_per_depth` 값마다 그 총량(`joule_power`, `outward_current.<name>`, …, 깊이당
값 × 깊이)이 뒤따른다. `joule.temperature2d`는 `iterations`를 더한다. Picard 단계마다 기록 하나이며
`iteration_count`, `temperature_change`(K), `relative_electrical_conductivity_change`,
`minimum_temperature`, `maximum_temperature`, `maximum_residual_current_per_depth`,
`maximum_residual_heat_rate_per_depth`, `relative_residual`과 그 단계의 수지 열을 담는다. 값마다
단위가 붙으므로 0.2의 `iteration_units` 표는 없어졌고, `units`와 `mesh_length_unit`도 없다.

CLI 종료값: 입력 오류 2, 풀이·비수렴·I/O 오류 1, 성공 0.
비수렴·범위 이탈은 Python에서 `JouleConvergenceError`로 이유·완료 이력·마지막
절점 온도를 보존한다. CLI는 이 근거를 stderr에 JSON 한 개로 출력한다: `status:"failed"`,
`reason`, `iterations`(위 기록), 비유한 값을 `null`로 쓴
`last_iterate: {"temperature": {"unit": "K", "values": [...]}}`, `nonfinite_temperature_count`.
**성공 출력 폴더를 만들지 않으며** 부분 성공으로 반환하지 않는다. 실패 근거는 stderr를 파일로
redirect해 보존한다.

## 검증·한계

직접 Python 호출과 결과를 비교하고 별도 1D 저항·발열 slab 해석식으로 단위 변환,
전류·전력·메시 수렴을 확인한다. 잘못된 키, 범위 이탈, 작은 완화에서의 비수렴,
기존 출력과 중단된 저장을 검사한다. 표기·길이 단위 불변성, 깊이 총량, 거부, 결과 이름은
`tests/simcase/test_units_electric_joule.py`가 검사한다. 기존 솔버의 독립 도구 비교는 유지하며
새로운 이산화는 추가하지 않는다.

이 계약은 위의 직사각형과 영역 형식, 단일 study에 한정된다. 온도 의존 Joule 문서의 영역 형상,
경계면 전위, 축대칭 전도, 임의 σ 함수, 기준 전위만 주는 전류 조건, 단자 총량, 과도, 3D,
Studio, 릴리스는 제외한다. 저장한 필드는 `simcase.export`로 ParaView에서 볼 수 있다
([ParaView로 보기](overview.md#paraview로-보기)). 그 내보내기는 저장된 배열을 복사하고 FieldData
`units`와 `conventions` 블록을 더할 뿐 이 계약에 다른 것을 더하지 않는다. 입력 검증 통과는
실제 수치 수렴 보장이 아니다.
