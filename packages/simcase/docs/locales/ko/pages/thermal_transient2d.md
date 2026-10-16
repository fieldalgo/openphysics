# 과도 열전도: Python과 문서 인터페이스의 경계

[English](../../../thermal_transient2d.md)

## 구현 경계

소스 snapshot `d5d2f0886e49df0e1a96731270602340329f9192`에서
과도 열전도는 명시적 Python 엔진 API
`galerkin.transient_heat.solve_transient_heat`로 사용할 수 있습니다.
문서 실행기는 `em.modes2d`, `em.cavity3d`, `thermal.steady2d`를 받으며
아직 과도 열전도 문서를 받지 않습니다. Python 엔진 결과는 문서 실행기의
결과나 지원되는 저장 문서 형식이 아닙니다.

이 페이지는 과도 문서 adapter가 보존해야 할 경계를 기록합니다.
수용된 JSON schema, 공개 adapter 결과 클래스, CLI 예제 이름이나 저장 형식
식별자를 정의하지 않습니다. 문서 인터페이스를 사용하기 전에 구현과 정확한
검증 근거를 확인하세요. 이 문서로 수치·설치 배포·플랫폼 통과가 성립하지 않습니다.

| 인터페이스 | 명시한 snapshot에서 사용 가능 | 경계 |
|---|---|---|
| 명시적 과도 Python 엔진 | 고정 적합 P1 삼각형, 일관 질량, 후진 Euler | 상수 균질 등방 열전도율·체적열용량, 명시적 요청 시간 |
| Headless JSON / API / CLI | 정상 직사각형 열전도 문서만 | 과도 solver import가 실행기의 과도 study를 활성화하지 않음 |
| 저장된 열전도 문서 | 기존 정상 결과 계약 | 정상 온도 배열을 시간 이력으로 해석하지 않음 |
| Studio | 열 editor·renderer 없음 | 광학 화면이 열 이력을 광학 결과로 표시하면 안 됨 |
| 열–기계 workflow | 별도의 정상 단방향 계약 | 자동 과도 연성 없음 |

엔진의 [사용 계약](https://github.com/fieldalgo/openphysics/blob/main/packages/galerkin/docs/locales/ko/pages/transient_heat.md),
[생산 검증](https://github.com/fieldalgo/openphysics/blob/main/packages/galerkin/docs/locales/ko/pages/transient_heat_validation.md),
[독립 수용](https://github.com/fieldalgo/openphysics/blob/main/packages/galerkin/docs/locales/ko/pages/transient_heat_independent_validation.md)은
별도 패키지에 있어 네트워크 접근이 필요합니다. 과거 제출 근거와 후속 정확 커밋
검증을 구분해 보존합니다. 기존 [정상 문서 계약](thermal_steady2d.md)은 과도 schema가 아닙니다.

## 단위와 수치 불변조건

독립 엔진은 명시적 SI 값을 사용합니다. 문서 adapter는 지원하는 입력 단위 변환을
메시 생성 전에 선언·검증해야 하며 숫자 크기나 파일 이름으로 단위를 추론하면 안 됩니다.

| 양 | 엔진 계약 |
|---|---|
| 좌표 | m |
| 요청 시간과 시간 증분 | s; 유한하고 엄격히 증가하는 시간, 유한한 양의 증분 |
| 초기·처방 온도 | K; 유한 실수 값 |
| 열전도율 | 양의 상수 k, W/(m K) |
| 체적열용량 | 양의 상수 c, J/(m³ K) |
| 체적 열원 | Q, W/m³; 부호 있는 가열·냉각 |
| 요소 열유속 | q=-k grad T, W/m² |
| 절점 source load·storage rate·잔차·반력 | 면외 깊이당 W/m |
| 열량 | H=1ᵀMT, J/m |
| 이차 functional | V=.5TᵀMT, J K/m; 저장 열량이 아님 |

선형 수학 엔진은 유한한 음의 Kelvin을 허용하며 계산값을 clamp하거나
discrete maximum principle을 약속하지 않습니다. 물리적 재료 유효성 인증은 아닙니다.
별도 열→기계 전달은 계속 음의 Kelvin을 거절합니다. Adapter는 자체 입력 정책을
명시해야 하며 엔진 해를 조용히 바꾸면 안 됩니다.

초기값과 첫 처방 경계 표본은 엔진의 일치 허용치를 만족해야 합니다.
수용한 초기값은 정확히 유지하며 projection이나 덮어쓰기는 없습니다.
완전 단열 과도 성분은 질량/시간 항으로 well-posed하므로 정상 solver의
Dirichlet anchor 요구를 가져오면 안 됩니다.

## 초기 frame과 step 이력

N은 절점 수, M은 삼각형 수, Nt는 요청 시간 수입니다.
Adapter는 모든 요청 시간의 값과 Nt-1 진화 step의 rate를 구분해야 합니다.

| 엔진 배열 | Shape | 해석 |
|---|---|---|
| time_s | (Nt,) | 초기 시간을 포함한 요청 시간 |
| temperature_k | (Nt,N) | 정확한 초기 frame을 포함한 절점 온도 |
| heat_flux_w_m2 | (Nt,M,2) | 초기 frame을 포함한 요소 flux |
| source_load_w_per_m | (Nt,N) | 조립 source; 초기 f0는 진단용 |
| reaction_w_per_m / residual_w_per_m / storage_rate_w_per_m | (Nt-1,N) | Step 양; 초기 반력·rate를 만들지 않음 |
| heat_content_j_per_m / quadratic_functional_jk_per_m | (Nt,) | 서로 다른 H·V 이력 |
| nodes_m / triangles | (N,2) / (M,3) | 장의 위치를 식별하는 형상·연결성 |

양의 처방 온도 반력은 열을 주입합니다. 각 진화 step의 외향 thermostat 열률은
반력 합의 음수입니다.

```text
(H_n-H_n-1)/dt_n = sum(source_load_n) + sum(reaction_n)
outward_D,n = -sum(reaction_n)
           = sum(source_load_n) - sum(storage_rate_n)
```

약형 절점 thermostat rate는 복원한 요소 flux의 직접 법선 적분과 다릅니다.
깊이당 rate와 H에 실제 두께 m를 곱하면 W와 J이며 온도와 flux에는 곱하지 않습니다.

## 실행·저장·근거

활성 환경의 Python interpreter로 엔진 예제를 실행하세요.
다음 Python snippet은 저장소 루트에서 실행합니다.

```python
import os
from pathlib import Path
import subprocess
import sys

env = os.environ.copy()
for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    env[name] = "1"
subprocess.run(
    [sys.executable, "packages/galerkin/examples/transient_heat_convergence.py"],
    cwd=Path.cwd(), env=env, check=True)
```

기존 엔진의 전체 수렴 예제를 실행하는 명령이며 과도 headless CLI가 아닙니다.
상당한 메모리·계산이 필요할 수 있습니다. 재현 명령은 어느 플랫폼에서 실행됐다는
근거가 아닙니다.

엔진은 O(Nt*(N+M))의 전체 이력과 sparse factor·임시 배열·최종 복사본을 보존합니다.
문서 직렬화에는 추가 메모리가 필요할 수 있으며 streaming·restart·메모리 상한을
추론하면 안 됩니다.

저장 문서 인터페이스는 field layout·단위·JSON 유한 값·비객체 배열·pickle 없는
안전한 읽기를 명시하고 검증해야 합니다. Fresh-output 소유권·교체 보호·정리는
실제 adapter에서 검증해야 합니다. 기존 정상 저장 근거는 새 과도 저장 구현의
증명이 아닙니다. 저장·정리가 끝날 때까지 소유 출력 경로를 독점 제어해야 하며
적대적 파일시스템 경쟁과 원자적 rollback은 기존 소유권 계약 밖입니다.

## 범위와 검증 경계

직사각형 문서 부분집합이 임의 메시 직렬화·과도 flux/Robin·복사·변경/온도의존 재료·
adaptive stepping·열 renderer·solver 영속 저장/restart·자동 연성을 뜻하면 안 됩니다.
새 문서 검증은 엔진의 고정 시간·공간·구적·분리 gate를 보존해야 합니다.

Source 검사·격리 설치 consumer·archive byte/링크·수치 gate·OS 민감 저장 시험을
각각 기록하고 실제 종료값·실패·skip을 사용해야 합니다. Linux 통과·metadata 분류·
universal wheel은 Windows/macOS 수용이 아닙니다. Manifest 포함은 구현한 포장 규칙이며
생성 archive나 설치 consumer의 통과 증명이 아닙니다.
