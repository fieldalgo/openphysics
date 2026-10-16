# 정상 외향 열유속·대류 문서

[English](../../../thermal_steady_boundary2d.md)

## 구현과 검증 상태

이 checkout은 기존 열 엔진을 이용해 `thermal.steady2d` 경계 확장을
`Document.from_dict`, JSON 읽기, 검증, 문서 summary, `run(Document)`,
`ThermalRunResult`, CLI와 JSON/NPZ 저장에 연결합니다.
[기존 가이드](thermal_steady2d.md)는 원래 v1 계약을 보존합니다.
같은 checkout에서 만든 서로 일치하는 패키지를 사용하세요.

[독립 검증 보고서](steady_boundary_independent_validation.md)는 고정 수용 기준,
원문 검토와 제한된 직접 경로 실측을 구분합니다. 전체 source·설치본·플랫폼 수용은
정확한 커밋의 CI 로그와 산출물에서 확인해야 합니다. 시험 정의만으로 통과를
뜻하지는 않습니다. 아래 예제는 재현 절차와 해석적 기대값이며 실측 검증 범위를
넓히지 않습니다.

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
내장 `thermal_boundary` 예제는 h=4 W/(m² K), Ta=290 K입니다.
오른쪽 T=293 K, g=2, h*(T-Ta)=12이고 왼쪽 thermostat은 -14 W/m를 기여합니다.
이는 해석적 기대값이며 측정값이 아닙니다.

```json
{
  "openphysics": "0.2",
  "name": "Steady additive outward flux and convection",
  "units": {"length": "m", "temperature": "K"},
  "geometry": {"domain": {"xmin": 0, "xmax": 1, "ymin": 0, "ymax": 1}},
  "materials": {},
  "physics": {"heat1": {
    "type": "thermal.steady2d",
    "conductivity_w_mk": 2,
    "heat_source_w_m3": 0,
    "dirichlet_temperature_k": {"left": 300},
    "outward_flux_w_m2": {"right": 2},
    "convection": {"right": {"h_w_m2k": 4, "ambient_temperature_k": 290}}
  }},
  "mesh": {"subdivisions": [8, 8]},
  "study": {"type": "single"},
  "results": {"save_fields": true, "plots": false}
}
```

## API·CLI·출력 파일

결합 checkout의 일치하는 패키지를 설치한 뒤 저장소 루트에서 다음 portable
Python 예제를 실행합니다. CLI subprocess에도 같은 interpreter를 사용하고,
UTF-8을 명시하며 새 임시 경로를 선택합니다. 재현 절차이며 이 문서 작성 중
실행하지 않았습니다.

```python
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from simcase import Document, ThermalRunResult, run

env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    env[key] = "1"
with tempfile.TemporaryDirectory(prefix="steady-boundary-") as directory:
    root = Path(directory)
    model = root / "thermal_boundary.json"
    example = subprocess.run(
        [sys.executable, "-m", "simcase", "example", "thermal_boundary"],
        check=True, capture_output=True, text=True, encoding="utf-8", env=env,
    )
    model.write_text(example.stdout, encoding="utf-8")
    subprocess.run(
        [sys.executable, "-m", "simcase", "validate", str(model)],
        check=True, env=env,
    )
    subprocess.run(
        [sys.executable, "-m", "simcase", "run", str(model),
         "-o", str(root / "cli_results")],
        check=True, env=env,
    )
    document = Document.load(model)
    result = run(document, verbose=False)
    assert isinstance(result, ThermalRunResult)
    summary = result.summary()
    result.save(root / "api_results")
    assert summary["result_format"] == "thermal.steady2d-result-v2"
    json.dumps(summary, allow_nan=False)
```

Context가 끝나면 임시 출력을 제거합니다. 결과를 보존하려면 호출자가 소유하고
아직 존재하지 않는 영구 경로를 선택하세요. CLI 종료 코드는 성공 0,
잘못된 입력 2, solver/save 또는 기존 대상 실패 1입니다.
열 PNG를 생성하지 않습니다. Studio는 열 문서를 거절하고 오래된 광학 상태를
지우며 headless 지원이 Studio 지원을 뜻하지 않습니다.

`summary()`는 JSON-safe dictionary를 반환합니다. `result_format`,
`field_layout`, `boundary_enabled`는 캡처한 layout을 식별합니다.
공개 배열 속성 이름은 아래와 같지만 `nodes_m`는 `mesh_nodes_m`,
`triangles`는 `mesh_triangles`입니다. `dirichlet_node_ids`,
`dirichlet_temperature_k`는 공개 result attribute입니다.
온도에 광학 유효굴절률이나 모드 정규화를 붙이지 않습니다.

## 버전과 원시 필드 계약

새 매핑 키 중 하나라도 존재하면 빈 객체여도
`thermal.steady2d-result-v2`, `thermal2d-p1-node-cell-boundary-v2`를 선택합니다.
둘 다 없으면 기존 v1 식별자와 배열 9개를 유지합니다. 빈 기본값을 삽입하거나
비어 있지 않은 값으로 버전을 추론하지 마세요. Null은 잘못된 입력입니다.
입력 형식은 0.2를 유지합니다.

| NPZ 배열 | Shape | 위치 / 의미 | 단위 |
| --- | --- | --- | --- |
| `nodes_m` | (N,2) | 절점, SI 좌표 | m |
| `triangles` | (M,3) | 정수 CCW 연결 정보 | 1 |
| `temperature_k` | (N,) | 절점 | K |
| `heat_flux_w_m2` | (M,2) | 삼각형 중심, -k grad(T) | W/m² |
| `load_w_per_m` | (N,) | 절점, 열원 fQ만 | W/m |
| `reaction_w_per_m` | (N,) | 절점, 내향 thermostat 반력 | W/m |
| `residual_w_per_m` | (N,) | 절점, A*T-rhs | W/m |
| `dirichlet_node_ids` | (D,) | 정렬·중복 없는 지정 정수 ID | 1 |
| `dirichlet_temperature_k` | (D,) | 대응하는 지정값 | K |
| `prescribed_outward_load_w_per_m` | (N,) | 절점, G; v2만 | W/m |
| `ambient_load_w_per_m` | (N,) | 절점, B; v2만 | W/m |
| `convective_outward_w_per_m` | (N,) | 절점, C; v2만 | W/m |
| `system_rhs_w_per_m` | (N,) | 절점, fQ+B-G; v2만 | W/m |

Robin만으로 고정하면 두 Dirichlet 배열의 shape은 (0,)이며 node ID는 정수입니다.
전체 residual은 위 A와 rhs를 사용합니다. 소비자는 `allow_pickle=False`로
읽고 format/layout, 단위, shape, 유한한 수치 타입과 metadata를 검사해야 합니다.
누락된 v2 필드에 임의의 0을 채우면 안 됩니다. Summary metadata에는 `field_units`, `field_locations`, `field_shapes`,
`mesh_length_unit="m"`, 원래 문서 단위, 경계 매핑, 고정 절점 수,
온도 극값과 mesh/solve 시간이 있습니다. NPZ에는 Unicode scalar
`result_format`, `field_layout`, `mesh_length_unit`, `metadata_json`도
저장하며 metadata JSON은 summary와 같습니다. Python object 배열은 없습니다.

V2 진단은 `source_heat_w_per_m`, `prescribed_outward_heat_w_per_m`,
`convective_outward_heat_w_per_m`, `thermostat_outward_heat_w_per_m`,
`outward_heat_w_per_m`, `heat_balance_defect_w_per_m`,
`normalized_heat_balance_defect`, `free_residual_max_w_per_m`입니다.
부호 있는 defect는 전체 외향 열량에서 열원을 뺀 값입니다.
정규화 defect는 그 절댓값을 절점 열원·반력·G·C 기여의 절댓값 합으로 나누며
양의 부동소수점 하한을 사용합니다. 자유 residual 최대값은 W/m 차원량이며
자유 절점이 없으면 0입니다. V2에는 v1의 `normalized_free_residual` 진단을
게시하지 않습니다. K만 사용하는 정규화는 Robin 엔진의 guard가 아닙니다.
Summary 검사가 엔진의 원래 물리 residual·열수지 guard나 독립 수용을
대체하지 않습니다. 검토한 구현은 v2 차원량 자유 residual과 기존 정규화를
분리해 유지합니다.

## 형상·수명·검증 한계

유한한 좌표만으로 side를 구분할 수 있다고 보장하지 않습니다. Helper는 축별
절대 좌표와 extent 중 큰 값에 machine eps의 64배를 곱한 tolerance를 사용합니다.
Tolerance가 extent의 절반에 도달하거나 side-edge 분류가 겹치거나 직사각형이
불완전하거나 node/edge tag가 잘못되면 거절합니다. Dirichlet identity는
가까운 내부 절점도 포함할 수 있는 넓은 좌표 mask 대신 검증된 외곽 edge 끝점에서
얻습니다. 큰 원점·아주 짧은 edge는 좌표 정밀도 부족으로 거절할 수 있습니다.
형상 guard를 완화하는 대신 더 작은 좌표 원점을 선택하세요.

Runtime은 입력 문서를 복사·검증해 선언된 단위 scale을 즉시 복구하고,
canonical JSON, 메시 절점·삼각형과 지정 데이터를 캡처합니다.
Summary/save는 검증 전에 문서 값을 비교하고 정규화 후 다시 검사합니다.
기본 필드를 삭제한 변경을 검증 과정의 기본값 복원으로 숨길 수 없습니다.
Name/results 변경은 거절하며 키 순서만 바뀐 것은 무관합니다.
메시·지정 배열은 캡처한 값·dtype과 같아야 합니다. 출력 옵션은 실행 전에
정하세요. 저장 model은 해당 계산을 설명하며 caller 원래 문서 변경은 격리됩니다.

Raw 실수 수치·유한성 검사는 문서·메시 snapshot 검사보다 먼저 수행합니다.
따라서 다른 입력도 변경됐더라도 비유한 raw 값 자체를 먼저 거절합니다.
Fields 비활성화 시에도 snapshot 검사가 raw 검증을 우회하지 않습니다.
이는 일관성 검사이며 암호학적 인증·권한 검증이 아닙니다.
노출된 모든 result 객체를 동결하거나 caller가 바꾼 유한 해를 독립적으로
다시 풀어 인증하지 않습니다. Run/capture/save 중 동시 변경은 지원하지 않습니다.

저장은 [새 출력 소유권 계약](thermal_steady2d.md#출력-소유권과-실패)을
유지합니다. 새 대상에 `.incomplete`, `model.json`, UTF-8 `log.txt`,
선택적 `fields.npz`를 쓰고 `summary.json`을 마지막에 씁니다.
`save_fields=false`는 NPZ만 생략하며 raw 유한성·shape·연결 정보·CCW와
유한 JSON 검사를 생략하지 않습니다. 전체 해는 메모리에 유지됩니다.
비유한 reduction/JSON은 NaN/Infinity로 내보내지 않고 거절합니다.
저장·정리 전체에 caller 독점이 필요하며 check/use 교체 race,
원자적 게시·crash rollback은 보장 밖입니다. Windows hard-link 기능과
실제 Windows/macOS 실행은 별도로 평가해야 합니다. 기존 소유권 실패도
근거로 보존합니다.

n8/16/32/64 마지막 두 구간의 온도 L2 차수 >=1.8, flux 차수 >=0.9,
정규화 residual·열수지 1e-10, SI 상사성 1e-9를 유지합니다. 기존 구적과 독립
음성 대조는 별도 gate입니다. 상수 JSON 경계 데이터로 sine/callback MMS를
직렬화하지 않습니다. 시험 선언·helper 진단·공개 API/CLI·설치 소비자·정확 CI는
서로 다른 근거 단계입니다. Linux 결과로 Windows/macOS 수용을 입증하지 않습니다.
