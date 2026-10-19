# 고정 P1 메시의 과도 열전도

[English](../../../transient_heat.md) · [검증](transient_heat_validation.md)

**한눈에 보기**

- **하는 일:** `galerkin.transient_heat.solve_transient_heat`는 고정된 적합 P1 삼각형 메시에서 일관 질량과 후진 Euler로 2D 열전도 c·dT/dt − div(k·grad T) = Q를 시간 진행합니다. 입력은 상수 등방 k[W/(m K)]와 c[J/(m³ K)], 열원 Q[W/m³], 명시 시간[s], 초기 온도장[K], 시간에 따라 온도가 바뀌는 고정 Dirichlet 절점이며 나머지 경계는 단열입니다.
- **한계:** 처방 열유속·Robin 경계, restart, 자동 열전도→기계 연성이 없습니다. 유한한 음의 Kelvin을 clamp하지 않으며 이산 최대 원리를 약속하지 않습니다.
- **검증:** [검증 계약](transient_heat_validation.md)과 [독립 수용 검증](transient_heat_independent_validation.md)은 정확한 이산 고유모드 곱 대비 후진 Euler 차수 0.9–1.1, 사인 제조해에서 온도 L2 차수 ≥ 1.8과 열유속 L2 차수 ≥ 0.9를 고정합니다. 아래 과거 기록은 그대로 보존하며, 특정 커밋의 결과는 그 커밋의 CI 실행에서 확인하세요.

## 현재 checkout과 근거

이 페이지는 현재 checkout의 구현을 설명합니다. 명시된 과거 snapshot의 결과와 한계는 해당 버전에 적용됩니다. 다른 커밋의 검증 상태는 그 커밋의 CI 로그와 artifact에서 확인합니다.

**과거 최초 제출(d21): source와 정적 검토만 완료한 상태였습니다.** 당시 Python
parse/import/compile과 collection은 미실행이었습니다. 그 역사적 상태를 보존하며
이전 수치 통과를 추론하지 않습니다.

**2026-10-16 제한 후속 검증:** exact code snapshot
d21e083d9723eec71ab5e32777ecd331d75cd981과
b2f420f4d540503ad3711bdab996e12dcbce9e9d에서 각각 새 Python 5파일 compile과
engine/reference 하위 모듈 import가 성공했습니다. 대상 collect-only는 snapshot마다
동일한 node ID 70개(producer 58개, reference 12개)를 수집했습니다.
**Collected는 passed가 아니며 시험 본문은 하나도 실행하지 않았습니다.**
Git blob을 확인한 새 38파일 source 부분 복원본과 새 venv에서 기존 runtime 패키지인
Python3.12.14, pytest9.1.1, NumPy2.5.4, SciPy1.18.1을 사용했습니다.
Import 출처는 해당 exact source snapshot이며 설치 wheel 증명이 아닙니다.
기존 checkout·venv·역사적 실행 기록을 복구한 것이 아닙니다.

**2026-10-16 실제 소형 본문 후속 검증:** exact
b2f420f4d540503ad3711bdab996e12dcbce9e9d의 대상 두 파일을 한 번 실행해
**70 passed(producer 58 + reference 12), exit0, 실패/error/skip0**를 확인했습니다.
이전 70 collected와 구분합니다. 원래 stdout·stderr·JUnit 바이트, 해시, 자원 사전값과
모듈 출처를 보존했습니다. 동일한 Python3.12.14/pytest9.1.1/NumPy2.5.4/SciPy1.18.1
source 환경에서 BLAS/OMP/MKL1을 사용했으며 시험 수나 허용치를 줄이지 않았습니다.
솔버 수정이나 시험 재실행은 필요하지 않았습니다. d21 snapshot의 시험 본문을 별도로
실행한 것은 아닙니다.

그 과거 체크포인트에서는 고정 시간/PDE 공간/5% 분리 gate, 완전한 source 회귀,
설치 sdist/wheel 증명, 독립 수용과 플랫폼 시험이 미실행이었습니다. 소형 대조 70개는
완전한 물리 수용이 아닙니다. 현재 checkout은 정확한 현재 CI 근거로 평가해야 하며,
아래 명령은 재현 절차이지 새 통과 결과가 아닙니다.

## 명시적 하위 모듈과 최소 사용법

```python
import numpy as np
from galerkin.mesh import rectangle_mesh
from galerkin.transient_heat import solve_transient_heat

mesh = rectangle_mesh(1., 1., 4, 4)  # metres
result = solve_transient_heat(
    mesh, conductivity=2.5, volumetric_heat_capacity=4.0,
    time_s=np.array([0., .1, .3]),
    initial_temperature_k=np.full(mesh.num_nodes, 300.),
    dirichlet={}, heat_source=8.0)
outward_dirichlet_w_per_m = -result.reaction_w_per_m.sum(axis=1)
```

이 단열·상수 source 예제의 수학적 목표는 T=300+(8/4)*t K이며 flux와 thermostat
reaction은 0입니다. 이는 정확한 기준 기대값이며 **관측한 실행 결과가 아닙니다**.

정확한 keyword-only API는 다음과 같습니다.

```text
solve_transient_heat(
    mesh, *, conductivity, volumetric_heat_capacity,
    time_s, initial_temperature_k, dirichlet, heat_source=0.0)
```

하위 모듈을 명시적으로 import합니다. 자동 최상위 export는 추가하지 않습니다.
모델은 c*dT/dt-div(k*grad T)=Q이며 상수·등방성 k>0, c>0(재료 하나, 또는
[multimaterial](multimaterial.md)의 이름 있는 영역별 구간 상수. 이 문서의 기준은 재료 하나를 씁니다), 고정 적합 CCW
scalar P1 삼각형, consistent mass와 backward Euler를 사용합니다. 선택하지 않은
자연 경계는 단열입니다. 완전 단열 또는 분리된 성분에도 Dirichlet anchor가 필요하지
않습니다. 유효한 사용 절점 형상에서 M/dt+K는 양의 정부호입니다. 정상 해석의 필수
anchor 규칙을 가져오면 안 됩니다.

## 입력과 단위

| 입력 | 계약 |
|---|---|
| mesh | galerkin Mesh, 유한한 m 좌표; 사용 절점·적합·비중첩 manifold CCW 삼각형 |
| conductivity | 유한한 양의 scalar k, W/(m K) |
| volumetric_heat_capacity | 유한한 양의 scalar c, J/(m³ K) |
| time_s | 유한 실수 1D 초, 최소 두 개, 음이 아니며 유한 양의 차이로 엄격히 증가 |
| initial_temperature_k | time_s[0]의 유한 실수 정확히 (N,) K |
| dirichlet | 고정 외곽 정수 절점 -> scalar K 또는 callback(time_s)->scalar K |
| heat_source | 유한 scalar W/m³ 또는 callback(points_m,time_s)->정확히 (Q,) W/m³ |

Source callback은 (Q,2) m 좌표와 한 scalar 초 값을 받습니다. Callback 출력의
scalar broadcasting은 없습니다. bool·complex·비유한 값, 잘못된 shape와
bool/비정수/내부/범위 밖 Dirichlet ID를 거절합니다. 혼합 Python sequence는 dtype
변환 전에 bool을 검사합니다. 이미 변환된 float 배열에서는 생성 이력을 알 수 없습니다.
좌표·시간·섭씨·재료 단위를 추론하지 않습니다.

상수 열용량의 **선형 수학 API**에서는 standalone 정상 열전도처럼 유한한 음의 K도
허용합니다. 물리 온도·재료 유효성 인증이 아닙니다. 부호 있는 source/sink를 허용합니다.
Consistent mass 진화가 음이 아닌 절점 값을 보존하지 않을 수 있습니다. clamp, mass
lumping 또는 discrete maximum principle을 약속하지 않습니다. 별도 열→기계
snapshot 정책은 계속 음의 K를 거절하며 이 모듈은 전달 API를 바꾸지 않습니다.

Robin/outward-flux/복사 입력, 가변 재료, 변경 메시, adaptive time step,
Crank–Nicolson, mechanics, schema/CLI/Studio, 저장 또는 restart API는 없습니다.
예상하지 않은 keyword를 조용히 무시하지 않습니다.

## 초기 일치와 callback 수명

각 지정 절점에서 초기값과 t0 경계 표본은 다음 범위 안에서 일치해야 합니다.

```text
32*eps*max(1 K, abs(initial_i), abs(d_i))
```

허용 반올림 범위 안에서도 초기값을 projection하거나 덮어쓰지 않습니다. 첫 old-state
mass 항은 실제 초기 장을 사용합니다. 0이 아닌 시작 시간도 허용하며 초기 데이터는
첫 제공 시간에 속합니다.

Source와 경계 callback은 순수하고 결정적이어야 합니다. Source는 t0에서 검증하고
f0 진단용으로 보존합니다. 이후 각 요청 시간마다 한 번 표본화하며 BE는 **오른쪽 끝**
하중을 사용합니다. 각 지정 경계 callback도 시간마다 한 번 표본화합니다. 점 batch나
절점 평가 순서는 보장하지 않습니다. 초기 rate 또는 reaction을 만들지 않습니다.

형상/연결, 시간, 초기 데이터, scalar 입력과 고정 Dirichlet 선택은 callback 전에
복사/캡처합니다. 캡처·해석 중 caller의 동시 변경을 지원하지 않습니다. Callback 좌표는
복사본입니다. 이후 caller의 변경은 반환 history나 캡처 형상을 바꾸지 않습니다.

해석은 eager all-or-error입니다. 구조적 입력 오류는 ValueError입니다. 준비·표본화·
해석·파생 history·최종 복사 실패는 time_index와 time_s를 갖는 ValueError 하위 클래스
TransientHeatStepError로 chaining합니다. __cause__는 원래 예외를 보존합니다.
준비 실패는 index0, 최종 복사 실패는 마지막 index/time입니다. 부분 성공 결과를
반환하지 않으며 실패한 trial로 이전 수용 내부 상태를 바꾸지 않습니다. 외부 callback의
부작용은 rollback하지 않습니다.

## 이산화와 이동 온도

```text
M_e = c*A/12 * [[2,1,1],[1,2,1],[1,1,2]]
K_ij = integral k*grad(N_i).grad(N_j)
f_i(t) = integral N_i*Q(x,t)
r_n = M*(T_n-T_n-1)/h_n + K*T_n - f_n

(M_FF/h_n+K_FF)*T_F,n =
    f_F,n + M_FF*T_F,n-1/h_n
    - K_FC*d_n - M_FC*(d_n-d_n-1)/h_n
```

Old와 new M_FC 항이 모두 필요합니다. 구현은 전체 old M*T를 포함하고 전체 new
A_FC*d를 뺍니다. 정상 문제의 반복 해석이 아닙니다. 정상 열전도의 4점 경계/Robin
구적을 여기서 사용하지 않습니다. 공간 source 적분은 기존 6x6 Duffy 규칙입니다.

각 형상 성분은 전체 실행에서 하나의 **시간에 무관한** 초기 offset을 사용해
차분/미분합니다. Stiffness image는 수학적으로 0이고 mass 미분도 0입니다. 시간마다
offset을 재설정하지 않습니다. 각 요청 dt마다 sparse factorization을 다시 계산하며
dt와 무관한 재사용이나 성능을 주장하지 않습니다. 파생 부동소수점 overflow나
residual/balance 검사 실패는 잘못된 성공 history 대신 예외를 발생시킵니다.

## 결과 배열, 수명과 메모리

TransientHeatResult는 다음 배열을 소유하며 read-only 복사본으로 보존합니다.
N은 절점, M은 삼각형, Nt는 요청 시간, D는 정렬된 고유 지정 절점 수입니다.

| 필드 | Shape | 의미 / 단위 |
|---|---|---|
| time_s | (Nt,) | 요청 초 |
| temperature_k | (Nt,N) | 절점 K, 정확한 초기 복사 장 포함 |
| heat_flux_w_m2 | (Nt,M,2) | 요소 q=-k*grad(P1 T), W/m², t0 포함 |
| source_load_w_per_m | (Nt,N) | 절점 f, W/m; f0는 진단용만 |
| reaction_w_per_m | (Nt-1,N) | 고정 절점의 원래 residual, 자유 절점은 0, W/m |
| residual_w_per_m | (Nt-1,N) | 모든 절점의 원래 전체 BE residual, W/m |
| storage_rate_w_per_m | (Nt-1,N) | M*(T_n-T_n-1)/h_n, W/m |
| heat_content_j_per_m | (Nt,) | H=1ᵀ M T, J/m |
| quadratic_functional_jk_per_m | (Nt,) | V=.5 Tᵀ M T, J K/m |
| dirichlet_node_ids | (D,) | 정렬된 고유 고정 절점 인덱스 |
| dirichlet_temperatures_k | (Nt,D) | 표본화한 지정 K |
| nodes_m / triangles | (N,2) / (M,3) | 복사한 SI 형상/연결/순서 |

두 metadata 필드 conductivity_w_mk와 volumetric_heat_capacity_j_m3k는
제공한 상수를 기록합니다(float, 또는 영역별 입력이면 `{영역 이름: float}` 사본). 단위·provenance·hash·source 출처 인증을 주장하지 않습니다.
Read-only 배열과 frozen container는 적대적 코드에 대한 암호학적 보호가 아닙니다.

History만 O(Nt*(N+M)) 메모리를 사용하며 sparse system/factor와 임시 복사본이
추가됩니다. 최종 결과 생성에도 복사 메모리가 필요합니다. 숨은 downsampling,
streaming, restart는 없습니다. 큰 요청은 할당에 실패할 수 있으며 부분 성공 history를
반환하지 않습니다.

## 열량 회계와 이차 functional

모든 절점 rate는 단위 면외 깊이당 W/m이며 전체 W가 아닙니다. 실제 m 두께를 rate와
H에 곱하면 W와 J입니다. 온도나 flux에는 곱하지 않습니다. 기계 N/m는 열률이 아닙니다.

```text
H_n = 1^T*M*T_n                         [J/m]
V_n = .5*T_n^T*M*T_n                   [J K/m]
storage_n = M*(T_n-T_n-1)/h_n           [W/m]
reaction_n = residual_n on fixed DOFs  [W/m]
outward_D,n = -sum(reaction_n)
(H_n-H_n-1)/h_n = sum(f_n)+sum(reaction_n)
outward_D,n = sum(f_n)-sum(storage_n)
```

양의 reaction은 열을 주입합니다. H는 0K를 선택한 기준으로 삼는 선형 상수 열용량의
현열량이며 보편적 절대 enthalpy 모델이 아닙니다. V는 이차 functional이지 **저장 열량이
아닙니다**. 균질한 0 Dirichlet 또는 완전 단열 무강제 진화에서는 BE 이차 항등식이
V 비증가를 뜻합니다. Source나 0이 아닌/이동 경계 온도가 있으면 H/V 단조성이나
maximum principle을 주장하면 안 됩니다. 복원한 셀 flux는 H(div)-conforming이
아닙니다. 직접 경계 법선 적분은 일반적으로 유한 메시의 약형 thermostat reaction과
다르므로 별도로 보고해야 합니다.

고정 gate, 독립 대수/reference 경계와 재현은
[검증 가이드](transient_heat_validation.md)를 보세요.

## 별도의 headless 문서 adapter

직사각형 `thermal.transient2d` JSON/API/CLI와 저장 이력은 별도 simcase adapter가 제공합니다. [입력·결과·저장 계약](https://github.com/fieldalgo/openphysics/blob/main/packages/simcase/docs/locales/ko/pages/thermal_transient2d.md)은 다른 패키지의 온라인 문서로 네트워크 접근이 필요합니다. 이 engine 함수의 임의 callback/메시 범위가 문서 직렬화 범위인 것은 아닙니다. 문서는 균일/affine 초기장과 변 상수/요청 시간별 표본을 사용하며 초기 일치·무projection·finite K/no clamp를 유지합니다. Studio·restart·과도 flux/Robin·자동 연성은 추가하지 않습니다. 엔진 수용과 headless source/설치/저장/CI 수용은 구분합니다.
## 제한된 공간 잔차 보정

초기 성분 상태 offset은 전체 해석에서 고정합니다. 강성과 기울기를 평가할 때만
각 성분의 현재 대표 절점값을 뺍니다. 온도, 이력 또는 질량 미분을 재정의하지 않습니다.
성분 상수 E에 대해 정확한 산술에서는 K E=0이므로 원래 backward-Euler 방정식과
old/new 경계 질량항을 모두 유지합니다. 반올림된 조립 K에서는 비트 단위 K E=0이
아닐 수 있으며, 반올림된 행렬이 불변이라고 주장하지 않습니다.

자유 DOF가 있는 각 단계는 원래 행렬과 LU를 유지하고 물리 잔차 평가 6회와 같은 LU를 사용하는
자유 DOF 보정 5회를 수행합니다. 지정 절점의 보정은 0입니다. 물리 잔차가 가장 작은
반복값을 선택한 뒤 원래 자유 잔차·성분 평형 검사를 허용치 변경 없이 적용합니다.
해석적 평균 대입, projection 또는 새 수용 기준이 아닙니다. 최종 검사 실패는
여전히 오류입니다. 추가 분해 없이 단계당 삼각 풀이 최대 5회와 추가 행렬-벡터
평가가 필요하며 수렴이나 성능을 보장하지 않습니다.

새 제작자 시험 `test_transient_heat_tiny_domain.py`와
`test_transient_heat_general_state.py`는 작은 균일장·ramp 및 비균일장, 이동 경계,
전체 고정, 분리·재정렬 상태를 독립 dense consistent-mass 재구성과 함께 다룹니다.
파일 추가는 실행이 아닙니다. 선택한 소스의 좁은 네 사례 진단은 성공 반환했지만
전체 source·설치·공개 headless·플랫폼 수용은 아닙니다. 원래 실패 근거와 모든 고정
수치 기준을 계속 보존합니다.
