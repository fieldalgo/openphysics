# 비정상 열전도 독립 수용 검증

[English](../../../transient_heat_independent_validation.md)

## 현재 checkout과 근거

이 페이지는 현재 checkout의 구현을 설명합니다. 명시된 과거 snapshot의 결과와 한계는 해당 버전에 적용됩니다. 다른 커밋의 검증 상태는 그 커밋의 CI 로그와 artifact에서 확인합니다.

## 과거 등록과 현재 재현

2026-10-16. 이 보고서는 정확한 초기 생산 후보
`d21e083d9723eec71ab5e32777ecd331d75cd981`을 대상으로 한다.
`galerkin/transient_heat.py`의 Git blob은
`426015f84e2c43db964f3063c734d47aca41a9fa`이다.
독립 수용 브랜치 `codex/openphysics-transient-heat-independent-validation`은
이 정확한 후보에서 생성했다. 초기 코드 체크포인트는
`55afd565b9f6feea38896dc567eef574adf21371`이다.
그 과거 제출은 생산 코드·생산 담당 시험·refsol·기존 시험·공용 release 설정을 변경하지 않았습니다.

**과거 제출 근거:** 원 d21 독립 수용 제출에서는 Python parse/compile·collection·NumPy 진단·source/설치 시험·runtime 음성대조·PDE 수렴·전체 회귀·Windows 시험을 실행하지 않았습니다. 통과 수·측정 차수·artifact hash·clean-whole 주장은 없었습니다. 이는 과거 한계이며 현재 실행 제한이 아닙니다. Actions는 활성화돼 있고 현재 checkout 결과는 정확한 CI 근거가 필요합니다.

신규 생산 모듈을 읽기 전에 독립 사전등록
`d42b43360bcaff9fe1d98c44105b15ab74ceec90`에서 수치 계약을 고정했다.
oracle blob `69238292eb72c58c3d3385cc0a60a1db8c7fcd2b`는
생산/refsol에서 변형한 것이 아니라 **바이트 그대로** 복사했다.
모든 사전 gate를 유지한다. 이전 작은 n3 248확인/41이름과 생산 담당 자체시험은
이 독립 수용 결과가 아니다. 기존 열탄성 traction/전체시험 이력은 별도 범위다.

## 소유 범위와 파일

실행 파일은 모두 `packages/galerkin/tests/`에 있다.

| 파일 | 역할 |
|---|---|
| transient_heat_independent_oracle.py | 변경하지 않은 NumPy/stdlib 수학 정답 |
| transient_heat_independent_cases.py | public API adapter와 unittest 수용 클래스 |
| test_transient_heat_independent_validation.py | pytest 발견 wrapper만 담당 |
| transient_heat_independent_consumer.py | stdlib 격리 설치모듈 loader/origin/hash 검사 |

영어 보고서와 이 완전한 한국어판이 나머지 두 추가 파일이다.
생산 담당 시험이나 허용치를 편집하지 않는다. 현재 원문에는 test 메서드17개가
선언되어 있다. 이는 정적 문자열 개수이며 **collection 또는 통과 횟수가 아니다**.
unittest subtest와 후속 pytest/subtest 개수는 실제 관측값으로 따로 보고해야 한다.

## 독립 유도와 scale

scalar SI 문제는 c*Tdot-div(k*gradT)=Q이며, 외부 고정 노드의 온도를 처방하고
나머지 변은 단열이다. 좌표는 m, k는 W/(m K), c는 J/(m^3 K), Q는 W/m^3,
T는 Kelvin이다. 원 barycentric geometry에서 다음을 얻는다.

```text
M_e = c*A/12 * [[2,1,1],[1,2,1],[1,1,2]]
K_e,ij = k*A*(grad N_i dot grad N_j)
f_e,i(t) = integral N_i*Q(x,t) dA
q_e = -k*sum_i T_i*grad N_i
```

oracle은 결정적인 CCW 정사각형/분리 메시를 직접 만들고 맞은편 변 gradient와
Duffy tensor-Gauss 적분을 사용한다. 생산 geometry/assembly/load/solver/
postprocess/refsol 함수를 정답으로 호출하지 않는다. Public Mesh는 입력 adapter다.
wrong-runtime actor는 생산 helper를 관측하거나 patch할 수 있지만 그 반환값은
reference solution이 아니다.

C는 처방 노드, F는 자유 노드, h=t_n-t_old일 때 다음과 같다.

```text
(M_FF/h+K_FF)*T_F,n =
 f_F,n + M_FF*T_F,old/h - K_FC*d_n
 + M_FC*T_C,old/h - M_FC*d_n/h
r = M*(T_n-T_old)/h + K*T_n - f_n
reaction_C=r_C; reaction_F=0
H=1^T*M*T                         [J/m]
V=.5*T^T*M*T                      [J K/m]
(H_n-H_old)/h=sum(f_n)+sum(reaction_n)
outward_D=-sum(reaction_n)
(V_n-V_old)/h + .5*deltaT^T*M*deltaT/h + T_n^T*K*T_n
 = T_n dot (f_n+reaction_n)
```

첫 old 처방 상태는 **허용된 실제 초기 장**이며, 허용 불일치 내의 sampled d0와
반드시 같지는 않다. 이후 old 처방 상태는 이전에 푼 BC 값이다.
양의 반력은 내향 열이고 transient 외향률은 source에서 storage를 뺀 값이다.
V는 저장 열이 아니다. 회복 셀 flux가 유한 메시에서 약한 thermostat 수지를
재현할 필요는 없다. 성분별 수지를 독립 감사하며 단열에는 steady의 anchor
규칙을 적용하지 않는다.

원 M/K 작용, source load, storage, 전체 잔차, 반력, H/V, 열·functional 항등식,
shift 및 정확 control은 정규화 <=1e-10, 명시 SI 변환은 <=1e-9를 사용한다.
Tscale=max(1K,amplitude/change), mass scale c*area,
Hscale=c*area*Tscale, flux scale=k*Tscale/L이다.
rate scale은 source+reaction+storage의 절대 크기와 양의 단위 floor를 사용하며,
상쇄되는 순 source를 쓰지 않는다. W K/m functional 항등식은 절대 항 크기를
사용하고 절대온도와 rate의 곱을 포함한다. 직접 V 차이와 대수적으로 안정화한
V 차이를 모두 감사한다. 관측 결과로 허용치를 선택하지 않는다.

## 고정 수치해 계열과 오차 분리

| 계열 | 고정 정의와 gate |
|---|---|
| 균일 단열 | T0+Q*(t-t0)/c; Q8,-1600; 불규칙[0,.03,.1,.4,1]s; 단일/분리 영역과 성분별 다른 초기 상수; 정확 절점 T, 영 q/r, 성분 H |
| 이동 affine | n8; T=290+5x+3*(t-t0), Q=3c, 외부 전체 정확 BC, 시작0/2s; 정확 T/q와 원 약한 반력 |
| 허용 초기 불일치 | n3, 영 baseline, 고정노드1 초기16eps, d0=0, h1e-12; 초기 비트 보존과 독립 비영 storage;64eps 거절 |
| 이산 열원 우단점 | T=300+2t+7t^2; lookup Q_n=c*[2+7*(t_n+t_old)], Q0=2c; 연속미분이 아닌 우단점 BE control |
| 시간 고유모드 | n8 최소 양의 일반화 Dirichlet 모드,max(abs(phi))=1;300K baseline+1K 모드,Q0; tau1/lambda,step8/16/32/64; 마지막 두 종점 mass-norm 차수 .9–1.1; 전체 history BE-product<=1e-10 |
| PDE sine | n8/16/32/64,dt1/256,종료1s,관측 .25/.5/1s; 각 시간 마지막 두 구간 T L2>=1.8,flux L2>=.9 |
| 시간 companion | n64 dt1/512; 모든 관측 시간의 두 norm에서 abs(E_half-E_primary)/E_primary<=5% |
| 독립 적분 | Gauss8/10 내부 norm 차이<=각 비영 측정 오차의1% |

k=2.5,c=4,A1K,gamma=.7/s,L1m에서 PDE 정답은 다음과 같다.

```text
T = 300+(1+.7t)*sin(pi*x)*sin(pi*y)
Q = [c*.7+2*k*pi^2*(1+.7t)]*sin(pi*x)*sin(pi*y)
q = -k*(1+.7t)*grad(sin(pi*x)*sin(pi*y))
```

초기는 정확한 절점 값이고 외부는 T300이다. oracle은 물리 내부 구적에서
P1 온도와 셀 flux를 계산한다. 절점/centroid만의 오차나 생산 요약을
정답으로 쓰지 않는다. 모든 메시의 대각선은 같은 결정 규칙을 사용한다.
dense 대수는 작은 control/n8 고유모드에만 사용하고 n64 감사는
원소 텐서/scatter 작용으로 한다. 연속체의 시간함수가 affine이라고 해서
반이산 시간오차가0이라고 할 수 없다. 5% gate 실패는 실패로 보존하며
dt나 허용치를 재조정하지 않는다. roundoff 수준의 정확한 affine/uniform은
정확성으로 검사하고 가짜 수렴률을 만들지 않는다.

오차를 네 범위로 나누어 보고한다: 원 전체계 대수 잔차, 지수해 대비
고정 메시 시간오차와 이산 BE product, 고정 기본/companion dt에서 연속체
T/flux 오차, 독립 구적 오차. 실행하면 raw 오차/차수와 모든 companion
비율을 출력한다.

## Gate 변경 없이 B 계약 검토 반영

구현 전 검토 `420bd73ea202eef65354b65ee0042598934cb0c2`의
review blob `114a828d5d3b74cb66801c017000b36170e9812d`를 읽었다.
R2 actual initial/old M_FC는 영 baseline에서 작은 허용 불일치와 유한한 작은 h로
검사한다. 온도 허용치만으로는 놓칠 수 있어 원래 scale을 완화하지 않고 storage로
비영 witness를 드러낸다. 초기 projection actor는 실제 solve를 호출하며,
생산 출력을 정답으로 삼지 않고 독립 storage 정답과 비교한다.

R5는 callback 전 copy, 후속 입력 변형, 혼합 bool, 잘못된 callback/배열 shape,
used nodes 및 유도 overflow를 검사한다. 현재 메시의 실제 배열을 검증하며,
이미 casting한 Mesh 생성자가 지운 원래 입력 이력을 복원하지 않는다.
R6는 전체 이산 열원 lookup을 먼저 정의한다. 잘못된 좌단점/평균/고정 lookup
actor는 같은 함수/history에 적용한다. 이차식의 연속 미분을 평균하여 우연히
같아지는 경우를 음성 검출로 사용하지 않는다.

R1의 실제 캡처 접근자는 nodes_m/triangles이다.
R3은 요청 시간별 샘플과 같은 sampled-point 합계를 확인하며,
임의의 Python 호출1회나 배치 순서를 강요하지 않는다.
R4는 time_index/time_s와 비어 있지 않은 chained cause를 갖는
TransientHeatStepError를 요구한다. R7 정규화 및5% 오차비 해석은 원 사전계획과
같다. 이것으로 생산 수치 계약 준수를 추정하지 않는다.

## 계약과 wrong-runtime 범위

adapter는 정확한 Nt/Nt-1 shape, 초기 flux/source f0,
가짜 초기 reaction/rate 부재, 빈 BC history, 캡처 좌표·연결성,
읽기전용 배열, 불변 result 속성 및 mutable caller alias 부재를 검사한다.
통제된 callback 변형은 copy 시점 진단이지 동시 변형 보장이 아니다.
순수·결정적 callback이 전제이며 외부 부수효과를 rollback하지 않는다.

유한 음수 initial/BC/computed Kelvin은 수학적으로 허용한다.
이는 물리적 유효성을 인증하거나 별도 역학 transfer gate를 바꾸지 않는다.
bool/complex/nonfinite/잘못된 값, 잘못된 BC ID, used-node 위반,
잘못된 시간 수열 및 유도 수치 overflow를 거절한다.
진화에 f0를 쓰지 않더라도 잘못된 t0 source는 거절한다.
후속 source/BC sentinel 오류는 정확한 step/cause를 보존하며
성공한 부분 결과를 반환하지 않아야 한다.

frame 회전·평행이동에서는 flux를 벡터로 변환한다.
노드/셀 순열과 명시 mm→m 표현을 같은 물리 문제에 비교한다.
T/BC/initial의 공통 상수 shift는 q/storage/reaction을 보존하고
H를 선형으로 바꾼다. 단위/출처 인증이나 DMP를 약속하지 않는다.

| Actor 범주 | 작성된 검출 기준; 실행은 정확한 CI로 확인 |
|---|---|
| Runtime 질량 조립 변형 | row-sum lumped M은 독립 n8 BE-product 비교에서 실패해야 함; 자체 일관 wrong residual만으로 충분하지 않음 |
| Runtime 잘못된 reduced solve | 독립 old/new/both M_FC 누락 자유해를 splu actor로 주입; 원 전체계 자유잔차 거절과 예상 step/cause 확인 |
| 실제 solve, 잘못된 source 입력 | 좌단점/평균/고정 deterministic lookup을 이산 우단점 정답과 비교 |
| 실제 solve, 조용한 초기 projection | R2의 비영 독립 첫 storage |
| 반환 result 변형 | storage 누락,storage 없는 residual,반력 부호반전,V를 H로 오표기; 예상 assertion label 요구 |
| 독립 행렬 대안 | 독립 BE의 old/new/both M_FC 누락; runtime 주입과 명확히 구분 |

actor는 생산 파일을 편집하지 않는다. 예상 밖 import/fixture/type 오류나
무관한 예외는 잘못된 물리 검출 성공이 **아니다**.
실행 시 원 실패와 이름 붙인 물리 witness를 보존해야 한다.
clamp/f0 누락/copy 누락/anchor 부재 거절/stale dt/부호·storage 오류도
고정 positive/control/계약 시험으로 구분한다. 고정 lab에는 추가 행렬 actor가 있다.

## 재현 대기열, source와 설치 근거

아래 명령은 재현 절차이며 측정 결과가 아닙니다. 기존 의존성을 갖춘 격리 환경의 저장소 루트에서 실행하고 정확한 source·환경 근거를 기록합니다. 첫 예시는 이식 가능한 Python이고 artifact/consumer 명령은 명시적으로 POSIX 셸용입니다. 수치 thread는 1로 설정합니다.

```python
import os
from pathlib import Path
import subprocess
import sys

root = Path.cwd()  # Run this script from the repository root.
env = os.environ.copy()
for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
             "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS"):
    env[name] = "1"
subprocess.run([sys.executable, "-m", "pytest", "-c", "pyproject.toml", "-q", "-s",
                "packages/galerkin/tests/test_transient_heat_independent_validation.py"],
               cwd=root, env=env, check=True)
```

정확한 checkout commit, dirty/비승인 파일 감사, host/OS/Python, 버전/module origin,
stdout/stderr/종료값과 최초 실패/skip을 보존한다. 과거 checkout에 남은 파일로
정확한 artifact라고 주장하지 않는다. source oracle은 동결 blob을 유지해야 한다.
선언/collection/통과 시험 수를 각각 기록한다.

실제 sdist를 만들고 그 sdist에서 wheel을 만든다.
ACCEPTANCE_RECORDS와 ACCEPTANCE_SDIST에는 본인 records 경로를 지정하고,
출처를 모르는 기존 wheel을 사용하지 않는다.

```bash
python -m build --no-isolation --sdist --outdir "$ACCEPTANCE_RECORDS/artifacts" packages/galerkin
python -m pip wheel --no-deps --no-build-isolation --no-index --no-cache-dir --wheel-dir "$ACCEPTANCE_RECORDS/wheels" "$ACCEPTANCE_SDIST"
```

이미 있는 의존성을 사용하는 별도의 본인 venv에 설치한다.
source/sdist/wheel/installed의 runtime 파일 이름·바이트, 특히 정확한
transient_heat.py를 hash 대조한다. Git blob을 SHA256으로 쓰지 말고
실제 hash를 기록한다. oracle/cases/consumer는 checkout 밖의 본인 consumer
디렉터리에 복사하고 source checkout을 PYTHONPATH에 추가하지 않는다.
관측한 설치에서 ACCEPTANCE_INSTALLED_PYTHON, ACCEPTANCE_INSTALLED_ROOT,
ACCEPTANCE_MODULE_SHA256 및 ACCEPTANCE_CONSUMER_DIR를 정한다.

```bash
"$ACCEPTANCE_INSTALLED_PYTHON" -I "$ACCEPTANCE_CONSUMER_DIR/transient_heat_independent_consumer.py" --expected-installed-root "$ACCEPTANCE_INSTALLED_ROOT" --expected-module-sha256 "$ACCEPTANCE_MODULE_SHA256" --suite all
```

격리 consumer는 pytest 대신 stdlib unittest와 기존 NumPy 및 설치 solver를 쓴다.
자신의 외부 oracle/cases만 명시적으로 load하며 설치 root/module SHA256을
검사한다. module origin/isolated flag/oracle·cases hash와 실제 횟수를 출력한다.
기본 all은 변경하지 않은 네 메시 PDE gate를 포함한다.
core는 PDE를 제외한 명시적 진단이며 전체 수용을 대신할 수 없다.

관련 실행이 성공하고 승인된 경우에만 관련 회귀 및 최종 전체 root 실행1회를
따로 기록한다.

```bash
python -m pytest -q
```

현재 manifest·문서 색인·배포 helper는 이 보고서, 원 oracle/cases/wrapper/consumer·runtime 모듈·예제를 archive/byte/origin 검사에 연결합니다. Helper는 격리 archive consumer를 `--suite all`로 실행하고 전체 수렴 예제를 실행합니다. 이는 구현된 검증이며 artifact 실행 성공 근거는 아닙니다. 정확한 CI 종료값과 artifact를 확인해야 합니다.
후속 생산 SHA는 원 blob 비교와 영향별 재검증이 필요하며,
동일 코드라는 이유로 전체 시험을 자동 반복하지 않는다.

## 과거 d21 근거의 한계

| 범위 | 원 d21 제출 결과 |
|---|---|
| 후보 API/source 읽기 | 완료; 정확한 모듈 blob 기록 |
| 수용 oracle/cases/consumer 및 EN/KO 보고 | 작성; 정적검토만 수행 |
| 동결 oracle/gate | 보존; producer/refsol 정답 의존 없음 |
| Python syntax/pytest collection/NumPy/source/installed/runtime 음성 | 미실행; 통과 주장 없음 |
| 시간/PDE/5% 분리·구적 gate | 미실행 |
| 전체회귀/artifact/build/배포/Windows | 미실행 |
| Actions | 조회·실행·활성화 없음 |

원 수치 실패를 통과로 바꾸지 않습니다. 표는 과거 source-only 제출을 기록하며 현재 checkout의 CI 상태가 아닙니다. 최초 실패와 정확한 근거를 보존하고 main 통합·릴리스 전에 현재 source·설치·독립·플랫폼 결과를 각각 평가해야 합니다.
