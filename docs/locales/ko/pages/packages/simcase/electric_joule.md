# 전기전도·Joule heating 문서

[English](../../../../../packages/simcase/electric_joule.md) | **한국어**

JSON/CLI 규범 원본은 위 영문 문서다. 이 페이지는 같은 계약의 한국어 안내다.
수치 풀이와 기존 허용오차는 [전기전도](../galerkin/electric_steady2d.md),
[단방향 Joule](../galerkin/joule_heating.md),
[온도 의존 Joule](../galerkin/temperature_joule_heating.md) 계약을 따른다.

## 범위·입력

이 절은 직사각형 형식이다. `electric.steady2d`는
[재료 영역](#재료-영역-전기-정상-전도)도 받는다.
`openphysics:"0.2"`, 이름 있는 physics 하나, `study:{"type":"single"}`,
`geometry.domain`의 `xmin,xmax,ymin,ymax` 직사각형, 양의 정수
`mesh.subdivisions:[nx,ny]`, `materials:{}`를 사용한다. 단일 균질 재료의
2D 정상 해석이다. 형상 목록·sweep·재메시·두께·추가 열원은 지원하지 않는다.
`units.length`는 기존 길이 단위 중 명시하고 Joule에는 `units.temperature:"K"`도
필요하다. SI 접미사가 붙은 값은 길이 단위와 무관하게 그 SI 단위를 쓴다.
알 수 없는 키, 비유한 수, 숫자 대신 boolean, 모서리의 상충 조건은 거부한다.
할당 전 최대 200,000 삼각형을 검사한다. results 기본값은
`save_fields:true,plots:false`이며 plot과 Studio 실행은 지원하지 않는다.

- `electric.steady2d`: 양의 `conductivity_s_m`, 변→전압의
  `dirichlet_potential_v`, 선택적인 변→외향 J·n `outward_current_a_m2`.
  적어도 한 전압 변이 필요하며 순수 Neumann/기준 전위 입력은 제외한다.
  나머지 변은 절연이다.
- `joule.steady2d`: 위 전기 입력과 양의 `thermal_conductivity_w_mk`,
  `dirichlet_temperature_k`, 선택적인 `outward_flux_w_m2`,
  변→`{h_w_m2k,ambient_temperature_k}`의 `convection`.
  온도와 h는 음수가 아니어야 하고 온도 고정 변 또는 양의 h가 필요하다.
  flux와 convection은 더해진다. 완전히 고정된 edge의 자연 경계 하중은 거부한다.
  같은 메시의 전기 결과가 유일한 열원이다.
- `joule.temperature2d`: `conductivity_s_m` 대신 `conductivity_model`,
  필수 스칼라 `initial_temperature_k`를 쓴다. 모델 필드는
  `type:"linear_resistivity"`, `reference_conductivity_s_m`,
  `reference_temperature_k`, `alpha_per_k`, `temperature_range_k:[lo,hi]`다.
  식은 `σ(T)=σ_ref/(1+α(T−T_ref))`다. 유한한 `0≤lo<hi`, 범위 내 T_ref,
  양의 σ_ref, 두 끝점의 유한한 양의 분모와 σ를 요구한다. 분모가 선형이므로
  이 검사가 선언 구간 전체를 보장한다. 초기·고정·주위 온도는 범위 안이어야 한다.
  반복 중 모든 절점의 범위를 기존 솔버가 검사한다. 외삽·잘라내기·임의 함수·
  표현식 실행·모듈 import는 없다.

변 이름은 `left,right,bottom,top`이다. 인접 고정 변은 공유 모서리에서 같은 값을
가져야 한다. 생성한 메시에서도 고정/자연 edge 충돌을 검사한다. 미터 단위 메시를
한 번 만들고, 각 삼각형 세 절점의 유효 범위를 검사한 뒤 산술평균 온도에서 σ를
평가한다. 열전도도는 온도에 무관하다.

온도 의존 입력의 선택적 `iteration`: `relaxation` 기본 .5(0 초과 1 이하),
`temperature_atol_k` 1e-8, `relative_tolerance` 1e-10, `max_iterations` 100.
허용오차는 양수, 최대 반복은 양의 정수다. 기존 완화 Picard 반복이 **완화 전**
온도·전도도 결함과 전기 재평가를 통한 비선형 열 잔차(정규화값 ≤1e-8)를 검사한다.
선형 잔차·보존 gate는 바꾸지 않는다. 정규화와 정지식은 위 솔버 계약을 참조한다.
문서는 항상 Picard 반복을 쓰며 Python API의 `method="newton"`은 이 형식에 없다.

## 재료 영역 (전기 정상 전도)

형상에 영역이 있는 `electric.steady2d` 문서(feature나 배경 재료가 있는
[버전 1 형상 블록](geometry_document.md), 또는 0.2 `shapes`)는
[영역 열](thermal_regions2d.md)과 같은 형상·메시·경계 이름을 쓴다.

- **전도도**
  - `materials.<name>.electrical_conductivity_s_m`(> 0)이 각 영역의 전도도다. 영역이 쓰는 모든 재료에 있어야 한다.
  - 같은 재료 표에 열 물성(`conductivity_w_mk`, `volumetric_heat_capacity_j_m3k`)을 함께 둘 수 있고, 물리마다 필요한 키만 읽는다.
  - 내장 광학 재료는 쓰지 않는다. physics 항목에는 `conductivity_s_m`을 두지 않는다.
- **경계 데이터**
  - `dirichlet_potential_v`와 `outward_current_a_m2`는 도메인 변, 형상이 선언한 외부 태그(`boundary_tags` 이름, 빈 공간 feature 경계의 `outer`), 외부 경계 선택을 받는다.
  - 두 영역 사이 경계면 선택은 둘 다 거부한다. 전기 솔버가 외부 절점만 고정하기 때문이다.
  - 다음은 이름을 밝혀 거부한다: 메시 변이 없는 이름, 같은 변에 전류를 준 두 이름, 다른 이름으로 고정된 경계의 변에 준 전류, 공유 절점을 서로 다른 전위로 고정하는 두 경계.
- **이름 없는 경계**: 빈 공간 경계를 포함해 이름 없는 외부 경계는 절연이다. 전위는 하나 이상 있어야 한다.
- **메시와 거부**: `mesh`는 영역 열처럼 `{"size", "min_angle", "controls"}`이고 영역 메시 한도가 적용된다. 빈 공간 배경과 축대칭 구성 요소는 거부한다.

**결과**
- 결과 형식은 `electric.steady2d-regions-result-v1`, 필드 layout은 `electric2d-p1-node-cell-regions-v1`이다.
- 필드는 직사각형 필드에 `triangle_regions`를 더한 것이다.
- 요약에는 `region_names`, `region_materials`, `region_conductivity_s_m`, `diagnostics.terminal_reaction_current_a_per_m`이 들어간다.
  - 마지막 값은 고정된 경계마다 나가는 전류이며 단위는 깊이 1 m당 A다.
  - 두 경계가 함께 고정한 절점은 먼저 적힌 경계에 센다.

`joule.steady2d`와 `joule.temperature2d`는 직사각형 형식을 유지하며, 영역 형상은 이름을 밝혀 거부한다.

독립 검증(`tests/simcase/test_electric_regions.py`, 미리 등록한 E1–E7):

| 확인 | 기준 | 결과 |
|---|---|---|
| 직렬 두 층 | 구간 선형 전위, I = V / Σ(L_i / (σ_i h)) | 절점 오차 1e-10 V 이하, 전류 상대 1e-10 |
| 병렬 두 층 | I = V Σ(σ_i h_i) / L | 상대 1e-10 |
| 동축 원형 전극(r = 3, 9 mm, 192각형) | I = 2πσ(V_a − V_b) / ln(b/a) | 메시 0.8, 0.4, 0.2 mm에서 상대 오차 2.0e-3, 6.6e-4, 1.4e-4(마지막 단계 차수 2.3) |
| Joule 전력 | 공급 전력 V·I | 상대 1e-10 |
| 직사각형 문서 | 이 변경 전 결과 | 직사각형 전기·Joule 예제 전부 비트 단위로 같음 |

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

성공은 `model.json`, `log.txt`, `summary.json`, 선택적 `fields.npz`를 저장한다.
기존 출력 소유권·실패 정리 기능을 재사용하며 빈 폴더·symlink 포함 기존 경로는
거부한다. 성공 summary를 마지막에 쓰고 중단된 저장에는 `.incomplete`가 남는다.
NPZ에는 숫자 배열과 Unicode metadata만 있어 `allow_pickle=False`로 읽는다.

결과 ID는 `<physics-type>-result-v1`, layout은 `electric-joule2d-p1-v1`이다.
좌표는 미터다. 절점: 전위 V, 전기 반력·외향 전류 하중·잔차 A/m, Joule 하중 W/m.
요소: 전기장 V/m, 전류밀도 A/m², σ S/m, Joule 밀도 W/m³.
Joule에는 절점 온도 K, 열 하중·반력·잔차·외향 하중·주위 하중·대류 외향·RHS W/m,
요소 열유속 W/m²도 있다. 각 물리의 고정 절점 ID와 지정값을 함께 저장한다.
온도 의존 결과에는 σ 평가에 쓴 T_i[K]와 summary의 전체 반복 이력이 추가된다.
열 결과 H(T_i)와 σ(T_i)의 평가 온도 차이는 수렴 기준으로 제한된다.
metadata가 각 필드의 모양·위치·단위를 명시한다.

적분 전류는 깊이당 A/m, 전력은 깊이당 W/m이며 A/W가 아니다. 전기 반력은 유입
공급 전류다. `sum(reaction-prescribed_outward_load)=0`을 검사한다.
공급 전력과 Joule 적분값, 열의
`sum(-reaction+prescribed_outward_load+convective_outward)`를 비교한다.
summary에 수지·자유 절점 잔차 노름·시간·소프트웨어 버전·반복 단위를 기록한다.
온도 결함은 K, 전도도·비선형 결함은 무차원, 전기/열 선형 잔차는 A/m과 W/m이다.

CLI 종료값: 입력 오류 2, 풀이·비수렴·I/O 오류 1, 성공 0.
비수렴·범위 이탈은 Python에서 `JouleConvergenceError`로 이유·완료 이력·마지막
절점 온도를 보존한다. CLI는 `status:"failed"` JSON 한 개로 이 근거를 stderr에
출력한다. 비유한 실패 온도는 null과 개수로 표시한다. **성공 출력 폴더를 만들지
않으며** 부분 성공으로 반환하지 않는다. 실패 근거는 stderr를 파일로 redirect해 보존한다.

## 검증·한계

직접 Python 호출과 결과를 비교하고 별도 1D 저항·발열 slab 해석식으로 단위 변환,
전류·전력·메시 수렴을 확인한다. 잘못된 키, 범위 이탈, 작은 완화에서의 비수렴,
기존 출력과 중단된 저장을 검사한다. 기존 솔버의 독립 도구 비교는 유지하며 새로운
이산화는 추가하지 않는다.

이 계약은 위의 직사각형과 영역 형식, 단일 study에 한정된다. Joule 문서의 영역별 물성,
경계면 전위, 축대칭 전도, 임의 σ 함수,
기준 전위만 주는 전류 조건, 과도, 3D, Studio, 릴리스는 제외한다. 저장한 필드는
`simcase.export`로 ParaView에서 볼 수 있다([ParaView로 보기](overview.md#paraview로-보기));
그 내보내기는 저장된 배열을 복사할 뿐 이 계약에 아무것도 더하지 않는다.
입력 검증 통과는 실제 수치 수렴 보장이 아니다.
