# 직사각형의 headless 과도 열전도

[English](../../../../../packages/simcase/thermal_transient2d.md)

**한눈에 보기**

- **하는 일:** `thermal.transient2d`는 과도 열전도 엔진을 `simcase` 문서 API·CLI·버전 JSON/NPZ 이력에 연결합니다. 고정된 균질 직사각형 하나, P1 삼각형, 일관 질량과 후진 Euler, 초 단위 명시 시간, 균일 또는 affine 초기 Kelvin, 변 상수 또는 표본 Dirichlet 값과 나머지 단열이며, 깊이당 계산입니다.
- **한계:** 과도 열유속·Robin·복사, 가변 또는 영역별 k/c, 적응 시간 간격, Crank–Nicolson, 자동 연성, restart가 없습니다. 초기값을 projection하지 않고 유한한 음의 Kelvin을 clamp하지 않습니다.
- **검증:** 엔진 수치 기준은 galerkin 과도 열전도 검증 계약(아래 링크, 변경 없음)에 있고, 이 페이지는 문서·adapter·설치·저장 검사를 따로 나열합니다. 특정 커밋의 결과는 그 커밋의 CI 실행에서 확인하세요.

## 범위와 근거

`thermal.transient2d`는 기존 과도 열전도 엔진을 `simcase` 문서 API·CLI와
버전이 있는 JSON/NPZ 출력에 연결합니다. 고정된 균질 2D 직사각형에서
`c*dT/dt - div(k*grad T) = Q`를 적합 P1 삼각형·일관 질량·후진 Euler로 풉니다.
형상은 m로 변환하고 요청 시간은 명시적 초입니다. 계산은 단위 면외 깊이당 값입니다. `geometry`에
`background`나 `shapes`가 있는 문서는 대신 [영역 문서 계약](thermal_regions2d.md)을 따릅니다.

이 페이지는 headless 인터페이스를 설명합니다. Generic 광학 Studio route의
열 guard는 유지하며 전용 [정상 Studio](thermal_studio.md)는 별도입니다.
[과도 Studio 통합 가이드](thermal_transient_studio.md)에서 capability·시간view·
구현/검증 상태를 구분합니다. Schema수용만으로 browserroute·renderer가
활성화되지 않습니다.

구현·source 시험·설치 consumer·정확 CI·main 통합은 서로 다른 근거 단계입니다.
코드는 아래 계약을 정의하며 새 시험 결과가 아닙니다. 보고된 source 부분집합
41개는 공개 API·설치 배포·전체 수치 gate·플랫폼 수용을 인증하지 않습니다.
정확한 결합 후보의 명령 종료값·원 로그·artifact를 확인하세요.
엔진만의 통과를 headless 저장·CLI 통과로 승계하지 마세요.

## 엄격한 입력 문서

형식 `"openphysics": "0.2"`와 명시적 `units.length`,
`units.temperature: "K"`, `units.time: "s"`를 사용합니다.
`m`, `mm`, `um` 같은 길이 기호는 네 형상 경계에 적용됩니다.
고정 SI 접미사 값은 형상 길이 단위로 변환하지 않습니다.

| 절 / 필드 | 수용 계약 |
|---|---|
| geometry.domain | 유한 xmin/xmax/ymin/ymax만; SI 변환 전후 표현 가능한 양의 길이 |
| materials | 빈 object; 광학 재료·영역별 계수 없음 |
| mesh.subdivisions | 정확히 [nx,ny], 양의 비boolean JSON 정수; 4.0은 정수 개수가 아님 |
| physics | 이름 있는 thermal.transient2d 항목 정확히 하나; 이름은 identifier |
| conductivity_w_mk | 필수 유한 양의 상수, W/(m K) |
| volumetric_heat_capacity_j_m3k | 필수 유한 양의 상수, J/(m³ K) |
| heat_source_w_m3 | 유한 부호 있는 상수 Q, W/m³; 기본값 0 |
| initial_temperature_k | 필수 유한 scalar K 또는 아래 affine object |
| dirichlet_temperature_k | 필수 변 매핑; 빈 object는 완전 단열 |
| study | type="transient"와 time_s만 |
| study.time_s | 유한한 음이 아닌 실수 초 최소 두 개; 유한 양의 차이로 엄격히 증가; 0이 아닌 시작 허용 |
| results | Boolean save_fields·plots; 기본값 true·false; plots=true 거절 |

알 수 없는 키·숫자로 쓰인 bool·비유한/복소 값·공간변 열원·tagged quantity·
shape·sweep·혼합 physics는 거절합니다. 문서 loader는 기본값을 적용하지만
누락한 단위·재료 상수·초기 데이터·시간 표본을 대신 만들지 않습니다.

Scalar 초기 온도는 균일합니다. 구조화된 초기장은 다음 affine object만 받습니다.

```json
{
  "type": "affine",
  "origin_temperature_k": 300.0,
  "gradient_k_per_m": [5.0, 0.0]
}
```

이는 `T0(x,y)=origin_temperature_k + gx*(x-xmin_m) + gy*(y-ymin_m)`입니다.
원점은 전역 (0,0)이 아니라 SI 영역의 왼쪽 아래 꼭짓점입니다.
형상이 mm·um여도 두 gradient는 K/m입니다. 초기값은 가정한 절점 순서가 아니라
실제 메시 좌표에서 평가합니다. 임의 절점 배열·수식·직렬화 Python callback은
이 문서 형식에 포함되지 않습니다.

### 경계 표본과 초기 일치

`left`, `right`, `bottom`, `top`만 허용합니다. 선택한 변은 외곽 전체를
덮고 공간적으로 일정한 값을 받습니다. 값은 모든 요청 시간에 반복하는 유한 scalar K,
또는 `study.time_s`마다 정확히 하나의 값을 갖는 `{"values_k":[...]}`입니다.
요청 시간 표본이며 보간·외삽하지 않습니다. 선택하지 않은 변은 단열입니다.
완전 단열은 질량/시간 항이 과도 계를 well-posed하게 하므로 인공 Dirichlet anchor가
필요하지 않습니다.

인접 처방 변은 꼭짓점 절점을 공유합니다. 전체 표본 수열이 정확히 같아야 하며
동일 선택은 매핑 순서와 무관하게 중복 제거합니다. 각 선택 절점의 초기 온도와
첫 경계 표본은 다음을 만족해야 합니다.

```text
abs(initial_i - d_i(t0)) <= 32*eps*max(1 K, abs(initial_i), abs(d_i(t0)))
```

수용한 초기값은 정확히 보존하며 projection·덮어쓰기·clamp가 없습니다.
시간 불변 변 값도 t0에서 일치해야 합니다. 처방 변을 따라 변하는 affine 초기장은
일치 조건을 만족하지 않으면 하나의 변 상수 경계로 표현할 수 없습니다.

선형 수학 모델은 유한한 음의 초기·경계·계산 K를 허용합니다.
물리적 재료 유효성을 인증하지 않습니다. 일관 질량은 양수성이나
discrete maximum principle을 약속하지 않습니다. 부호 있는 Q는 가열·냉각을 허용합니다.
별도 열→기계 전달은 계속 음의 K를 거절하며 이 adapter는 이를 바꾸지 않습니다.

## 완전한 최소 JSON

제공하는 `transient_thermal_uniform` 예제입니다.

```json
{
  "openphysics": "0.2",
  "name": "Insulated constant-source transient heat",
  "units": {"length": "m", "temperature": "K", "time": "s"},
  "geometry": {"domain": {"xmin": 0, "xmax": 1, "ymin": 0, "ymax": 1}},
  "materials": {},
  "physics": {
    "heat1": {
      "type": "thermal.transient2d",
      "conductivity_w_mk": 2.5,
      "volumetric_heat_capacity_j_m3k": 4.0,
      "initial_temperature_k": 300.0,
      "dirichlet_temperature_k": {},
      "heat_source_w_m3": 8.0
    }
  },
  "mesh": {"subdivisions": [4, 4]},
  "study": {"type": "transient", "time_s": [0.0, 0.1, 0.3]},
  "results": {"save_fields": true, "plots": false}
}
```

독립 수학 기대값은 `T=300+(8/4)*t` K, 영 flux와 영 thermostat 반력입니다.
해석적 기대값이며 이 페이지에서 관측한 출력이 아닙니다.

시간변 변 데이터는 나머지 조건이 호환되는 모델에서
`"left": {"values_k": [300.0, 300.2, 300.6]}`으로 지정할 수 있습니다.
각 표본은 해당 요청 시간에 대응하며 두 번째 인접 변을 선택하려면 공유 꼭짓점에서
같은 수열이 필요합니다.

## Python API와 이식 가능한 CLI 재현

패키지 설치 후 저장소 루트에서 다음 Python snippet을 실행합니다.
자체 임시 부모를 만들고 UTF-8 JSON을 쓰며 새롭고 서로 다른 출력 경로를 사용합니다.
공개 API와 CLI를 모두 보여주는 예시이며 어느 OS에서 이 명령이 실행됐다는 기록이 아닙니다.

```python
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[name] = "1"

from simcase import Document, TransientThermalRunResult, examples, run

work = Path(tempfile.mkdtemp(prefix="openphysics-transient-"))
model = copy.deepcopy(examples.TRANSIENT_THERMAL_UNIFORM)
model_path = work / "model.json"
model_path.write_text(json.dumps(model, ensure_ascii=False), encoding="utf-8")
doc = Document.load(model_path)
result = run(doc, verbose=False)
assert isinstance(result, TransientThermalRunResult)
summary = result.summary()
result.save(work / "api-results")
subprocess.run([sys.executable, "-m", "simcase", "validate", str(model_path)],
               check=True)
subprocess.run([sys.executable, "-m", "simcase", "run", str(model_path),
                "-q", "-o", str(work / "cli-results")], check=True)
print(work)
```

동등한 CLI 진입점은
`python -m simcase example transient_thermal_uniform`,
`python -m simcase validate model.json`,
`python -m simcase run model.json -q -o fresh_results`입니다.
`-o`가 없으면 모델 옆의 `<model-stem>_results`가 출력 기본값입니다.
필드를 저장하지 않더라도 새 경로를 사용하세요.
처리된 문서·JSON·파일 누락 load 오류는 CLI exit2,
처리된 run/save/fresh-output 오류는 exit1, 성공은 exit0입니다.
종료 코드는 정확한 실제 실행에서 관측한 경우에만 실측 근거입니다.

`run(Document, verbose=False)`는 문서를 검증·복사한 뒤 SI 직사각형을 만들고
직렬화 초기·경계 데이터를 표본화해 기존 과도 엔진을 한 번 호출합니다.
`TransientThermalRunResult`는 `doc`, `solution`, `timings`, `log`와
아래 장 배열을 노출합니다. `mesh_nodes_m`·`mesh_triangles`는 해의 형상 alias입니다.
Run snapshot은 호출자의 원 문서 변경과 격리됩니다. Run 뒤 `result.doc`의 값이
하나라도 바뀌면 name·results 옵션을 포함해 summary/save가 결과를 거절합니다.
모든 옵션은 run 전에 설정하세요. 매핑 순서만 바뀌는 것은 문서 의미 변경이 아닙니다.
직렬화 전에 raw 배열과 metadata를 재검증하며 적대적 코드에 대한 불변성·인증은 아닙니다.
EM 전용 `build_mesh`·`solve_point`는 이 physics를 거절하므로 `run`을 사용하세요.

## Raw 이력과 단위

`result_format="thermal.transient2d-result-v1"`,
`field_layout="thermal2d-transient-p1-node-cell-v1"`은 입력 형식 0.2 및 정상 결과
형식과 별개입니다. N은 절점, M은 삼각형, Nt는 요청 시간,
D는 정렬된 고유 Dirichlet 절점 수입니다.

| 수치 NPZ 키 | Shape | 위치 / 시간축 | 단위 |
|---|---|---|---|
| nodes_m | (N,2) | nodes / static | m |
| triangles | (M,3) | CCW integer connectivity / static | 1 |
| time_s | (Nt,) | requested_times / time_s | s |
| temperature_k | (Nt,N) | nodes / time_s | K |
| heat_flux_w_m2 | (Nt,M,2) | triangle_centroids / time_s | W/m² |
| source_load_w_per_m | (Nt,N) | nodes / time_s | W/m |
| reaction_w_per_m | (Nt-1,N) | nodes / time_s[1:] | W/m |
| residual_w_per_m | (Nt-1,N) | nodes / time_s[1:] | W/m |
| storage_rate_w_per_m | (Nt-1,N) | nodes / time_s[1:] | W/m |
| heat_content_j_per_m | (Nt,) | domain / time_s | J/m |
| quadratic_functional_jk_per_m | (Nt,) | domain / time_s | J K/m |
| dirichlet_node_ids | (D,) | dirichlet_nodes / static | 1 |
| dirichlet_temperatures_k | (Nt,D) | dirichlet_nodes / time_s | K |

초기 frame에는 정확히 수용한 T0·그 flux·진단용 f0가 있습니다.
초기 반력·step 잔차·storage rate는 없으며 Nt-1 배열은
`rate_time_s=time_s[1:]`에 대응합니다. 빈 Dirichlet 매핑에서는 D=0이며
처방 온도 이력은 (Nt,0)입니다.

양의 고정 절점 반력은 열을 주입하고 자유 절점 반력은 0입니다.
외향 열은 Dirichlet thermostat 기여이며 별도로 복원한 경계 flux 적분이 아닙니다.

```text
storage_n = M*(T_n-T_n-1)/dt_n
residual_n = storage_n + K*T_n - source_load_n
reaction_n = residual_n on fixed DOFs; zero on free DOFs
(H_n-H_n-1)/dt_n = sum(source_load_n) + sum(reaction_n)
outward_D,n = -sum(reaction_n)
H_n = 1^T*M*T_n                  [J/m]
V_n = .5*T_n^T*M*T_n             [J K/m; not stored heat]
```

Rate와 H는 면외 깊이당 값이며 실제 두께 m를 곱하면 W와 J입니다.
온도·flux에는 두께를 곱하지 않습니다. H는 상수 열용량의 현열량에 대해 0K를 선택한
기준이며 보편적 절대 enthalpy 모델이 아닙니다. 일반적 H/V 단조성을 주장하거나
직접 요소 flux 적분을 유한 메시의 약형 반력과 같다고 해서는 안 됩니다.

## Summary와 저장 파일

`summary()`는 다음과 같은 JSON 유한 metadata를 반환합니다.

- `name`, `physics_name`, `physics_type`, 결과/layout 식별자,
  선언 `units`, `mesh_length_unit="m"`, `mesh`, `study`, k/c/Q.
- 모든 수치 배열의 `field_units`, `field_locations`, `field_time_axes`,
  `field_shapes`; 선언 형상 단위가 SI raw 장을 바꾸지 않습니다.
- Nt 시간 전체의 `temperature_min_k`, `temperature_max_k`,
  `source_heat_w_per_m`, H·V.
- Nt-1 step의 `storage_heat_w_per_m`, `outward_heat_w_per_m`,
  `heat_balance_defect_w_per_m`, `rate_time_s`.
  Balance defect는 sum(storage)-sum(source at step end)-sum(reaction)입니다.
- `dirichlet_nodes`, `save_fields`, `timings_s`, 정의 문자열
  `reaction_sign`, `balance_equation`, `heat_content_definition`,
  `quadratic_functional_definition`.

시간 측정은 adapter 메시/준비와 solver 호출을 구분하며 전용 호스트 성능 기준선이나
이식 가능한 시간 보장이 아닙니다. Summary 생성은 배열 유한성·차원/인덱스/CCW 형상·
시간 유효성과 문서/재료/시간 일치를 검사합니다. 검증이지 출처 인증이나 독립 물리
증명은 아닙니다.

저장은 UTF-8 `model.json`, `log.txt`, 선택적 `fields.npz`를 쓰고
`summary.json`을 마지막에 씁니다. 임시 `.incomplete` 표시는 보존된 미완료 출력에
남으며 성공하면 제거됩니다. `save_fields=false`이면 JSON/log/summary는 있지만
NPZ는 없습니다. 해석은 계속 전체 이력을 보존하고 summary/save도 배열을 복사·검증합니다.
필드 비활성화는 streaming이나 메모리 상한이 아닙니다. Plot을 생성하지 않습니다.

NPZ에는 수치 장과 비객체 scalar 문자열 `result_format`, `field_layout`,
`mesh_length_unit`, `metadata_json`이 있습니다. 마지막 항목에는 같은 인코딩 summary
metadata가 들어갑니다. Pickle 없이 읽으세요.

```python
import json
import numpy as np

with np.load(work / "api-results" / "fields.npz", allow_pickle=False) as fields:
    times = fields["time_s"]
    temperature = fields["temperature_k"]
    rates = fields["storage_rate_w_per_m"]
    metadata = json.loads(str(fields["metadata_json"]))
    assert temperature.shape[0] == len(times)
    assert rates.shape[0] == len(times) - 1
```

저장한 모델과 이력은 조사에 사용할 수 있지만 이 출력에서 solver를 restart/resume하는
loader는 없습니다.

## 출력 소유권·실패·메모리

출력 경로는 존재하면 안 됩니다. 파일·빈/비어 있지 않은 디렉터리·끊어진 symlink를
덮어쓰지 않고 거절합니다. CLI는 해석 전에 새 경로인지 검사하고 save는 공유 정상 저장
소유권 구현으로 자신의 디렉터리를 확보합니다. 저장·정리가 반환될 때까지 호출자가
출력과 임시 인접 pin 경로를 독점해야 합니다. 관측한 외부 파일·디렉터리/파일 교체는
소유 출력으로 오인해 삭제하지 않고 보존합니다. 일반 실패에서는 알려진 소유 데이터만
정리합니다. 앞선 실패 뒤에는 완료 summary를 쓰지 않으며 log나 미완료 파일만으로
성공을 입증할 수 없습니다.

소유권 검사와 사용 사이에 적대적 외부 writer가 경로를 바꾸는 상황의 원자적 보호나
crash rollback은 아닙니다. Windows 저장에는 같은 볼륨 hard-link 지원과 공유 native
resource 수명 계약이 필요하며 미지원 파일시스템은 명시적으로 실패합니다.
실제 플랫폼에서 native rename/replace/cleanup 성공을 측정해야 합니다.
Linux 통과·classifier·universal wheel은 Windows/macOS 수용을 인증하지 않습니다.

Adapter는 초기 데이터 projection·온도 clamp·경계 표본 보간·이력 downsample·
solver gate 변경을 하지 않습니다. 엔진 step 오류는 physics 이름이 붙은 adapter 오류의
chained cause에 시간 context를 보존하며 실패 시 부분 결과를 반환하지 않습니다.
Run 뒤 문서 값 변경은 거절하고 배열·metadata는 직렬화 전에 재검증하며 호출자의
동시 변경은 지원하지 않습니다.

전체 이력은 O(Nt*(N+M)) 메모리와 sparse factor·임시 메모리를 사용합니다.
Save·summary에는 추가 검증 복사본·압축 buffer가 필요합니다. 큰 요청은 할당에 실패할
수 있으며 숨은 restart·streaming 보장은 없습니다.

## 한계와 검증 단계

과도 flux/Robin/복사·가변/영역별 k/c·임의 메시/절점/수식 직렬화·adaptive time step·
Crank–Nicolson·열 Studio 렌더링·자동 연성·restart는 추가하지 않습니다.
별도 정상 flux/Robin이나 열→기계 문서 계약의 범위를 넓히지 않습니다.

기존 [엔진 수치 gate](../galerkin/transient_heat_validation.md)는
불변입니다.
Schema 검증·source adapter 시험·독립 직렬화 해석/단위/이력/음성 대조·
격리 설치 consumer·정확한 sdist/wheel 내용과 byte·Studio 거부/stale-state 검사·
native 저장 회귀를 각각 기록하세요. 구현이나 정적 개수는 관측한 통과가
아닙니다. 최종 공개 API 수용에는 정확한 통합 source와 설치/CI 근거가 필요하며
릴리스에는 결과 main 커밋의 검사 성공도 필요합니다.
