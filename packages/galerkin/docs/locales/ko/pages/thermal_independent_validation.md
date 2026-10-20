# 정상 열전도 독립 수용 검증

[영문 원문](../../../thermal_independent_validation.md)

아래 실행 수치·실패·미검증 서술은 영문 원문의 해당 후보 시점 기록이며 새 수용 결과를 뜻하지 않습니다.

검증 당시 구현 후보는 `aaf948ae38aa82907ca16ef7cdeed75dfa7484ba`입니다. 이 독립 시험은 구현의 sine 정답 대신 4차 manufactured solution과 혼합 경계 2차 해를 추가합니다. 생산 thermal/refsol 코드, 원래 시험과 허용치는 바뀌지 않았습니다. 매끄러운 해의 메시 단계와 기준은 이 후보가 나오기 전에 기록했습니다. 새 시험은 Mesh와 공개 thermal solver만 import하며 정답 코드는 생산 assembly·gradient·solver·refsol helper를 import하지 않습니다.

## Oracle와 고정 기준

[0,Lx]×[0,Ly]에서 Lx=0.03m, Ly=0.02m, k=12.5W/(m K), T0=293.15K, A=7K로 고정합니다. xi=x/Lx, eta=y/Ly이면 다음과 같습니다.

```text
T = T0 + A*(xi^3-xi + 2*eta^3+eta + xi^2*eta^2)
Tx = A/Lx*(3*xi^2-1 + 2*xi*eta^2)
Ty = A/Ly*(6*eta^2+1 + 2*xi^2*eta)
Q = -k*A*((6*xi+2*eta^2)/Lx^2 + (12*eta+2*xi^2)/Ly^2)
q = -k*(Tx,Ty)
```

네 변 모두에 0이 아니고 비균일한 정확한 경계 온도를 처방합니다. 독립 oracle는 T에 이산 연산자를 적용하지 않고 미분하여 Q를 얻습니다. source 적분은 -k A [11 Ly/(3 Lx)+20 Lx/(3 Ly)]입니다. 유한한 음수 Q는 지원되는 열 흡수원입니다. 서로 다른 두 길이는 좌표·metric 인자의 교환을 검출하고 혼합항은 두 좌표에 실제로 의존하는 변화를 검사합니다.

왼쪽 TL=280K, 오른쪽 TR=315K, 위·아래 단열 조건에서는 다음을 사용합니다.

```text
T = TL + (TR-TL)*x/Lx + Q0*x*(Lx-x)/(2*k)
qx = -k*(TR-TL)/Lx - Q0*Lx/2 + Q0*x; qy = 0
```

Q0=1e5W/m³이면 두 번째 혼합 경계 수렴 시험이고 Q0=0이면 P1으로 정확히 표현 가능한 affine patch입니다. 왼쪽이 더 차갑기 때문에 왼쪽 inward reaction은 음수, 오른쪽은 양수입니다. affine 사례의 전체 합이 0이라는 사실만으로는 충분하지 않아 각 변의 열량을 따로 검사합니다.

변경하지 않은 주 메시 단계는 n=8,16,32,64개의 균일 직사각형 셀이며 각 셀을 같은 대각선으로 나눕니다. 두 manufactured solution 모두 내부 적분 오차가 엄격히 감소하고 **마지막 두 구간 각각에서** 온도 L2 차수 >=1.8, 체적 벡터 flux L2 차수 >=0.9를 만족해야 합니다. 매끄러운 해와 볼록 영역의 P1 근사는 점근 차수 2와 1을 예측합니다. 이 여유값은 해당 fixture에 대한 유한한 기준으로, 거친 해의 보편적 차수 주장이 아닙니다. 양의 norm으로 부호 오차 상쇄를 방지합니다.

## 독립 적분과 보존

Oracle는 좌표 여인수로 barycentric gradient를 계산하고 좌표 항등식을 검사합니다. 8×8 Duffy 구적법으로 상수 k의 요소 stiffness와 Q Ni 하중을 독립 조립하며 생산 source 적분과 다른 Duffy 매개화를 사용합니다. 시험은 내부 구적점에서 P1 T와 반환된 요소 flux를 평가합니다. 구적 차수 6과 8의 오차는 상대 1e-10 이내로 일치해야 합니다. 4차 해에서 온도·gradient 오차 제곱의 차수는 8·6이고 source와 Ni의 곱 차수는 3이므로 이 규칙들은 정확 산술에서 정확합니다. 절점 오차나 centroid 전용 적분으로 이 norm들을 대체하지 않습니다.

원래의 독립 행렬 K와 하중 f를 자유 잔차, 고정 절점 반력을 포함한 결과와 대조하며 다음도 확인합니다.

```text
R = K*T-f; outward boundary heat = -sum(R_fixed)
sum(load)+sum(reaction) = 0
theta^T K theta = theta^T f + theta_fixed^T reaction_fixed
```

theta=T-T0는 수학적 상수 nullspace 등가성을 검사할 때 절대 Kelvin의 상쇄를 피합니다. 보고되는 절대 온도를 복원하면서 생기는 차이도 같은 물리적 변동 scale로 검사합니다. 정규화한 잔차·반력·열수지·약형 항등식의 허용량은 1e-10입니다. 경계 온도와 affine T/flux도 정규화한 1e-10 기준을 사용합니다. 큰 T0로 나눠 변동 오차를 숨기지 않습니다.

하중·반력은 면외 깊이당 W/m, q는 W/m²입니다. 실제 깊이(m)를 곱하면 W를 얻습니다. 2차 weak functional의 단위는 W K/m이며 J 단위의 저장 열에너지가 아닙니다. 원래의 조각별 상수 P1 flux는 H(div) 보존 재구성장이 아닙니다. 비선형 사례의 경계 flux가 반력과 반올림 오차 수준으로 같아야 한다고 요구해서는 안 됩니다. 엄격한 이산 보존에는 반력을 사용하고 물리적 flux 정확도에는 체적 norm과 affine patch를 사용합니다.

## 추가 관측

- 독립 길이 인자 1e-3/1/1e3과 전도도·source 인자로 T'=T0+(d/c)(T-T0), q'=(d/s)q, load'=d load, reaction'=d reaction을 검사합니다.
- 고정 Q와 상수 경계 온도로 전도도에 반비례하는 온도 상승과 변하지 않는 flux를 검사합니다. +11K offset으로 gradient·반력 불변성을 검사합니다.
- 회전·평행이동, 절점·셀 순열과 반사된 대각선으로 scalar/vector 공변성과 문서화된 생성자의 방향 복구를 검사합니다.
- 모든 절점의 Dirichlet 데이터로 Q가 있는 유효한 빈 자유 시스템을 검사합니다. 분리 성분은 독립적인 상수를 가지며 다른 성분에 처방값이 있어도 anchor가 없는 성분은 거절합니다.
- 잘못된 입력 22개는 재료, source callback shape, nonfinite·complex·boolean 입력, 경계 ID·내부 구속과 변이된 메시의 connectivity·방향·중복·미사용·퇴화·nonfinite 절점을 다룹니다.
- 실제 negative control은 잘못된 Q 부호나 다른 k로 풉니다. 각자 자기 방정식을 풀더라도 독립적인 원 K/f 검사가 거절합니다. 반환 flux 반전과 내부 온도 손상도 검출합니다.

변형 관계의 차이는 고정된 정규화 기준 1e-9로 검사합니다. 새 API, 0이 아닌 Neumann/Robin 조건, 가변 k 또는 열탄성 연성은 시험하지 않습니다.

## 실행 근거와 재현

검증 당시 독립 source 및 installed-wheel 시험은 각각 45개입니다. 원래 thermal/refsol 쌍도 별도로 재실행해 84개 통과, 실패·skip 0을 확인했습니다. 이는 구현 담당의 주장을 반복한 수치가 아니라 직접 관측한 결과입니다. 정확한 후보 결과와 범위는 함께 제공되는 manifest에 있습니다.

초기 독립 실행에서는 affine 시험이 차가운 왼쪽 280/315K fixture에 대해 뜨거운 왼쪽의 반력 부호를 기대하여 42개 통과, 1개 실패가 있었습니다. q=-k grad T에 맞게 그 잘못된 기대값만 [1,-1]에서 [-1,1]로 바로잡았으며 생산 코드·허용치는 바꾸지 않았습니다. 상대경로 이동 실패 후 초기 전체 리디렉션 로그를 실수로 덮어썼습니다. 관측한 실패·trace와 명시적으로 보존한 요약에 이 한계를 기록했습니다. 이를 생산 결함으로 보고하거나 조용히 통과 실행으로 대체하지 않습니다.

기존 의존성을 사용해 저장소 루트에서 실행합니다.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python -m pytest -c pyproject.toml -q -s \
  tests/galerkin/test_thermal_independent_validation.py
```

설치 소비 검증에서는 별도 staging 복사본에서 sdist를 만들고 wheel로 빌드한 뒤 기존 NumPy/SciPy를 사용하는 전용 venv에 의존성 설치 없이 설치합니다. 두 독립 test/oracle 파일만 외부 시험 디렉터리로 복사합니다. 그곳에서 `--confcutdir=.`로 pytest를 실행하고 import가 source checkout이나 루트 conftest가 아니라 해당 venv의 site-packages로 해석되는지 확인합니다. 검증한 wheel의 Python 모듈 16개 모두 후보 source와 byte 비교했습니다. 이는 핵심 installed 소비자 검증이며 모든 배포물·플랫폼을 검증한 것은 아닙니다. 이 독립 작업은 공용 MANIFEST나 릴리스 설정을 바꾸지 않았습니다. (문서는 배포물에 포함되지 않습니다.)

Python 3.12.14, NumPy 2.3.5, SciPy 1.17.0, pytest 9.1.1을 사용했고 공유 Linux 호스트의 BLAS/OpenMP/MKL thread는 1입니다. 실행 시간은 성능 기준선이 아닙니다. 로그, source hash, 빌드 산출물과 초기 실패 요약은 별도로 보존합니다. 전체 환경 상태, 생략한 native 필수 조건과 installed-core 결과는 manifest에서 나누어 보고합니다. 이 시험으로 임의 기하, 비정상 해석, 비상수·이방성 전도도, 처방 flux나 연성 물리를 지원한다고 주장하지 않습니다.

## 별도로 보존한 전체 환경 실행

전체 source 실행은 **699 통과, 9 실패, 9 skip**, 하위 시험 9 통과와 FastAPI/Starlette deprecation 경고 1개로 끝났습니다. 그 실행은 앞선 43개 독립 시험 버전을 수집했습니다. 마지막에 추가한 변형 관계 시험 2개는 최종 45개 source·installed 실행에서 별도로 검사했습니다. 실패 7개는 find_gmsh가 None을 반환해도 계속 진행하는 기존 Gmsh 의존 optional-helper 경로입니다. 추가 Gmsh 시험 7개와 로컬 광학 DB 시험 2개는 skip했습니다. native 필수 도구를 설치하거나 이 독립 브랜치에서 해당 helper를 바꾸지 않았습니다. 나머지 실패 2개는 simcase를 import하지 못한 실제 cavity CLI subprocess입니다. 루트 conftest는 부모 프로세스에만 source 경로를 넣지만 이 전용 venv에는 simcase 패키지를 설치하지 않았기 때문입니다. 원래 9개 실패를 보존하며 두 subprocess 사례에 명시적인 candidate-only PYTHONPATH를 적용한 재실행은 manifest에 따로 기록했습니다. 전체 환경 통과를 인증하거나 통합 담당의 정확한 원격 CI를 대체하지 않습니다.

두 cavity CLI 사례는 후보 패키지 경로를 subprocess가 명시적으로 상속하게 하자 2개 통과, 실패·skip 0으로 재실행됐습니다. 이는 제품 변경 없는 환경 수정입니다. 처음 전체 실행의 실패를 지우거나 전체 시험을 다시 실행한 것이 아니며 Gmsh 실패 7개를 해결하지도 않습니다.
