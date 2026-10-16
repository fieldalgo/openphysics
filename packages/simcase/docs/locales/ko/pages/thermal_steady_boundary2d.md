# 정상 외향 열유속·대류 문서

[English](../../../thermal_steady_boundary2d.md)

## 계약과 구현 상태

이 페이지는 `thermal.steady2d`의 경계 확장 입출력 계약을 설명합니다.
[기존 정상 열전도 가이드](thermal_steady2d.md)는 기존 headless 경로를 설명합니다.
문서 기준 `6d6eac56d1dddb8bdfe3f23d6db78d674487a42b`의 공개 reader/runtime에는
이 확장이 아직 구현되지 않았습니다. 독립 경계 helper
`1c408be05e8f103e8436502610e03c763493d200`는 입력·메시 검사를 구현하며,
공개 JSON/CLI 해석·저장은 구현하지 않습니다. Runtime과 schema 연결은 별도입니다.
아래 예제는 계약 예제이며 성공 실행을 관측한 결과가 아닙니다.
이 초안은 새로운 source·설치본·CI·플랫폼 수용을 주장하지 않습니다.

## 입력과 지원 범위

형식 `"openphysics": "0.2"`, 단일 `thermal.steady2d` physics,
균질 직사각형, P1 삼각형, 상수 등방
`conductivity_w_mk > 0` W/(m K), 부호 있는 상수
`heat_source_w_m3` W/m³(기본 0)을 사용합니다. 길이 단위와
`temperature: "K"`를 선언합니다. 형상은 미터로 변환하며 SI 접미사는
선언된 길이 단위와 독립입니다. 메시 분할수는 불리언이 아닌 양의 JSON 정수입니다.
Study는 single, plots는 false입니다.

| Physics 필드 | 계약 |
| --- | --- |
| `dirichlet_temperature_k` | 필수 side→온도 매핑; 유한한 입력 K >= 0 |
| `outward_flux_w_m2` | 선택적 side→부호 있는 상수 g 매핑, W/m² |
| `convection` | 선택적 side→객체 매핑; 정확히 `h_w_m2k`, `ambient_temperature_k` 포함 |
| `h_w_m2k` | 유한한 h >= 0, W/(m² K) |
| `ambient_temperature_k` | 유한한 주변 K >= 0; h=0일 때도 검사 |

Side 이름은 정확히 left/right/bottom/top입니다. 지정하지 않은 자연 경계는
단열입니다. Null, 수치 필드의 불리언, 비유한 수, 알 수 없는 키, callback,
side 상수 대신 배열은 거절합니다. 부호 있는 열원과 외향 flux는 유효합니다.
입력 비음수 Kelvin은 문서 정책이며 유한한 음수 계산 온도는 clamp 없이 보존합니다.

같은 지정 모서리 온도는 중복을 제거하고 상충 값은 거절합니다.
한 side의 flux와 대류는 가산됩니다. 각 조건 종류는 완전하고 중복 없는 외곽
edge를 선택해야 하며 내부·중복·역방향 중복 edge는 허용하지 않습니다.
양 끝점이 Dirichlet인 edge는 flux나 h가 0이어도 거절합니다.
한 끝점만 Dirichlet이면 허용하며 consistent edge load 전체를 유지합니다.
서로 다른 side 이름만으로 끝점이 겹치지 않는다고 판단할 수 없습니다.

Dirichlet이 비어 있으면 실제 비어 있지 않은 경계에 양수 h가 있어야 합니다.
h=0은 온도를 고정하지 않습니다. 호환되는 pure Neumann 데이터도 상수 영공간이
남으므로 비호환 데이터와 함께 거절합니다. 임의 pin이나 평균 온도 gauge를
삽입하지 않습니다. 임의·분리 형상, 온도 의존 재료, 과도 flux/Robin,
연성 및 Studio 열 렌더링은 범위 밖입니다.

## 부호·단위·열수지

양수 g는 영역 밖으로 나가는 열입니다. Robin 열은 T가 주변 Ta보다 높으면
외향 양수입니다. q=-k grad(T)일 때 약형은 다음과 같습니다.

```text
q.n = g + h*(T-Ta)
A = K+H
rhs = fQ+B-G
G_i = integral_boundary(g*N_i)
B_i = integral_boundary(h*Ta*N_i)
C = H*T-B
r = (K+H)*T-(fQ+B-G)
reaction = r on Dirichlet nodes, zero on free nodes
total_outward = sum(G+C-reaction)
sum(fQ) = total_outward
```

K와 H의 단위는 W/(m K)입니다. 모든 절점 load, rhs, residual, reaction과
적분 열량률은 면외 깊이당 W/m이며 q는 W/m²입니다.
`load_w_per_m`는 합성 rhs가 아닌 체적 열원 fQ를 유지합니다.
Thermostat 기여만 -sum(reaction)이며 flux나 대류가 있으면 전체 외향 열량과
다릅니다. 과도 storage나 heat-content 양을 추가하지 않습니다.

길이 ell의 직선 edge에서 consistent line 적분은 다음과 같습니다.

```text
H_e = h*ell/6 * [[2,1],[1,2]]
G_e = g*ell/2 * [1,1]
B_e = h*Ta*ell/2 * [1,1]
```

경계 질량을 lump하거나 고정 끝점 load를 버리면 안 됩니다. 엔진의 shifted 평가와
물리 residual·열수지 guard가 기준입니다.

## 계약 예제

단위 정사각형의 선형 정답은 T=300-7x K, qx=14 W/m²입니다.
오른쪽 g=2, h*(T-Ta)=12이고 왼쪽 thermostat은 -14 W/m를 기여합니다.
이는 해석적 기대값이며 측정값이 아닙니다.

```json
{
  "openphysics": "0.2",
  "name": "Steady additive boundary contract",
  "units": {"length": "m", "temperature": "K"},
  "geometry": {"domain": {"xmin": 0, "xmax": 1, "ymin": 0, "ymax": 1}},
  "materials": {},
  "physics": {"heat": {
    "type": "thermal.steady2d",
    "conductivity_w_mk": 2,
    "heat_source_w_m3": 0,
    "dirichlet_temperature_k": {"left": 300},
    "outward_flux_w_m2": {"right": 2},
    "convection": {"right": {"h_w_m2k": 1, "ambient_temperature_k": 281}}
  }},
  "mesh": {"subdivisions": [8, 8]},
  "study": {"type": "single"},
  "results": {"save_fields": true, "plots": false}
}
```

## 버전과 원시 필드 계약

새 매핑 키 중 하나라도 존재하면 빈 객체여도
`thermal.steady2d-result-v2`, `thermal2d-p1-node-cell-boundary-v2`를 선택합니다.
둘 다 없으면 기존 v1 식별자와 배열 9개를 유지합니다. 빈 기본값을 삽입하거나
비어 있지 않은 값으로 버전을 추론하지 마세요. Null은 잘못된 입력입니다.
입력 형식은 0.2를 유지합니다.

기존 배열 9개의 단위와 의미는 유지합니다. V2는 shape (N,), 단위 W/m의
절점 배열 4개를 추가합니다.

| 배열 | 의미 |
| --- | --- |
| `prescribed_outward_load_w_per_m` | G |
| `ambient_load_w_per_m` | B |
| `convective_outward_w_per_m` | C |
| `system_rhs_w_per_m` | fQ+B-G |

Robin만으로 고정하면 두 Dirichlet 배열의 shape은 (0,)이며 node ID는 정수입니다.
전체 residual은 위 A와 rhs를 사용합니다. 소비자는 `allow_pickle=False`로
읽고 format/layout, 단위, shape, 유한한 수치 타입과 metadata를 검사해야 합니다.
누락된 v2 필드에 임의의 0을 채우면 안 됩니다. 이 초안을 완성하기 전에
정확한 공개 result 속성·summary 진단·저장 metadata를 runtime 후보와 대조해야 합니다.

## 형상·수명·검증 한계

유한한 좌표만으로 side를 구분할 수 있다고 보장하지 않습니다. Helper는 축별
절대 좌표와 extent 중 큰 값에 machine eps의 64배를 곱한 tolerance를 사용합니다.
Tolerance가 extent의 절반에 도달하거나 side-edge 분류가 겹치거나 직사각형이
불완전하거나 node/edge tag가 잘못되면 거절합니다. Dirichlet identity는
가까운 내부 절점도 포함할 수 있는 넓은 좌표 mask 대신 검증된 외곽 edge 끝점에서
얻습니다. 큰 원점·아주 짧은 edge는 좌표 정밀도 부족으로 거절할 수 있습니다.
형상 guard를 완화하는 대신 더 작은 좌표 원점을 선택하세요.

Runtime은 저장 metadata를 원래 계산에 결속하고
[새 출력 소유권 계약](thermal_steady2d.md#출력-소유권과-실패)을 유지해야 합니다.
출력 옵션은 실행 전에 정합니다. Fields 비활성 저장도 raw·유한 JSON 검사가
필요하며 원자적 게시·적대적 writer 보호·crash rollback을 뜻하지 않습니다.
정확한 snapshot 강제 여부는 실제 runtime 검토가 남아 있습니다.

n8/16/32/64 마지막 두 구간의 온도 L2 차수 >=1.8, flux 차수 >=0.9,
정규화 residual·열수지 1e-10, SI 상사성 1e-9를 유지합니다. 기존 구적과 독립
음성 대조는 별도 gate입니다. 상수 JSON 경계 데이터로 sine/callback MMS를
직렬화하지 않습니다. 시험 선언·helper 진단·공개 API/CLI·설치 소비자·정확 CI는
서로 다른 근거 단계입니다. Linux 결과로 Windows/macOS 수용을 입증하지 않습니다.
