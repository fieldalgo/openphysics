# Outward flux·Robin 열전도의 독립 수용 검증

[영문 원문](../../../thermal_flux_robin_independent_validation.md)

이 보고서는 초기 후보 `23f528dbcffb42ec4120b762fde840f70d9aeffe`를 다룹니다.
`galerkin/thermal.py` blob은 `20b2f5f0f94583e50775743e1ed9dfaf1c68d97c`,
경계 reference blob은 `6dccfad22c1300a0df698dea502e1643d1a0c153`입니다.
독립 oracle은 이 reference나 생산 조립·법선·하중·flux·열수지 helper를 import하지 않습니다.
이 변경은 전용 oracle/시험/보고와 한국어 문서 추가만 소유합니다. 생산·기존 시험·공유 설정은
그대로입니다. 초기 후보 근거와 후속 최종 후보·release 통합·완전 연성 workflow는 구분합니다.

후속 후보 `f575a7187108800545a3e33903b3a37942df9183`의 solver blob은
`4633e03953d8f6369bdf0e7398d2ebd85b2b4684`입니다. docstring을 제거한 AST 직접
비교에서 실행 solver는 초기 후보와 같았습니다. reference blob
`8f50ada586777e2a2dbac9f4a90275d65d17ad51`은 기존 모든 정의를 유지하고
sine_temperature/sine_flux/sine_source만 추가합니다. 본 oracle은 어느 것도 import하지
않습니다. 최종 독립 branch는 이 후속 후보를 정상 merge하고 초기 이력을 보존하며
관련 source·wheel 소비를 재검증합니다. 이 검증이 생산 코드를 작성·수정하지 않습니다.
최종 후보 관련 source는292통과(독립55+기존 생산/기본/역사 검사237), 최종 wheel
독립 실행은55통과입니다. runtime 음성 대조는 최종 source10/10·그 wheel10/10에서
검출합니다. 이 개수는 아래 초기 후보 개수와 구분합니다.

## 보존식과 독립 복원 연산자

`q=-k*grad(T)`, `div(q)=Q` 및 물리적 outward normal n에서 시작합니다.

```
q.n = g_out + h*(T-T_amb)
K_ij = integral(k*grad(Ni).grad(Nj))
H_ij = integral_boundary(h*Ni*Nj)
rhs = f_Q + f_amb - f_out
f_amb_i = integral_boundary(Ni*h*T_amb)
f_out_i = integral_boundary(Ni*g_out)
reaction = ((K+H)*T-rhs) on prescribed nodes; zero elsewhere.
```

양의 반력은 열 주입입니다. 전역 및 성분별 부호 있는 보존식은
`sum(f_Q+reaction)=sum(f_out+H*T-f_amb)`입니다. 좌표 m, k W/(m K), Q W/m^3,
g_out W/m^2, h W/(m^2 K), T/Tamb K입니다. 절점·적분 열유량은 면외 단위 깊이당
W/m이지 W가 아닙니다. 물리적 깊이를 곱하면 W가 됩니다.

독립 oracle은 raw 삼각형 좌표로 `[1,x,y]` 아핀 기저 계수를 구합니다. 그 gradient로
K를 만들고 자체 Duffy 구적에서 shape function을 보간하여 체적·경계 하중을 별도
적분합니다. 직사각형·정사각형 hole 법선은 해석 기하로 구하며 생산 법선을 기대값에
사용하지 않습니다. 다항식 선 moment도 Gauss sampling과 별도로 계수 곱셈과
`integral(s^j)=1/(j+1)`로 구합니다. 상쇄되는 합계뿐 아니라 모든 절점 항을 검사합니다.

시험 하나는 elimination에 전달한 실제 matrix/RHS를 관측하고 독립 K+H·shifted load와
비교합니다. 관측은 실제값만 공급하며 어떤 생산 routine도 oracle 값을 공급하지 않습니다.
source와 설치 실행은 같은 독립 유도 적분을 기대값으로 사용합니다.

## 폐형식 strip과 별도 manufactured solution

상하 단열인 `[0,L]`에서 상수 k,Q에 대해 다음과 같습니다.

```
T=a+b*x-Q*x*x/(2*k)
q_x=-k*b+Q*x
F_left=k*b; F_right=Q*L-k*b.
```

왼쪽 outward normal은 qx의 부호를 뒤집습니다. 왼쪽 TD/오른쪽 g이면
`a=TD`, `b=(Q*L-g)/k`입니다. 오른쪽 additive Robin이면
`b=[Q*L-g-h*(TD-Ta-Q*L*L/(2*k))]/(k+h*L)`입니다.

Robin-only 양끝에 대해 다음을 정의합니다.

```
B0=h0*Ta0-g0
BL=Q*L-gL+hL*(TaL+Q*L*L/(2*k))
D=k*(h0+hL)+h0*hL*L
a=[B0*(k+hL*L)+k*BL]/D
b=[h0*BL-hL*B0]/D.
```

h로 나누지 않아 한쪽 h=0도 포함합니다. 둘 다 0이면 호환성 `g0+gL=Q*L`을
만족해도 임의 온도 상수가 남습니다. 모든 성분에 Dirichlet 또는 양의 적분 Robin
지지가 필요합니다. 승인 API는 호환/비호환 unanchored 성분을 모두 거절하며 암시적
pin·gauge·pseudoinverse·단위 의존 h cutoff는 없습니다.

생산 benchmark와 다른 매끈한 정사각형 장은 다음과 같습니다.

```
T=310+2*x-3*y+4*x*x+2*x*y+5*y*y+.7*sin(2*pi*x)*cos(pi*y)
grad_x=2+8*x+2*y+1.4*pi*cos(2*pi*x)*cos(pi*y)
grad_y=-3+2*x+10*y-.7*pi*sin(2*pi*x)*sin(pi*y)
Q=k*(-18+3.5*pi*pi*sin(2*pi*x)*cos(pi*y))
q=-k*grad(T)
h=6+2*x+y; g=.8+.3*x-.2*y
T_amb=T-(q.n-g)/h.
```

all-Robin과 왼쪽 Dirichlet/나머지 Robin에서 이 직접 장을 사용합니다.
조립 잔차를 힘 또는 경계 oracle에 맞춰 넣지 않습니다.

## 고정 gate와 weak/raw 경계 열유량 구분

사전 수열은 양 방향 n=8,16,32,64입니다. 마지막 두 구간 16→32·32→64 모두 내부
온도 L2 차수>=1.8, 벡터 flux L2 차수>=.9여야 합니다. 독립 내부/경계 8·10차 구적
검사는 원 기준을 유지합니다. norm 차이는 측정 오차의 1% 미만, 연산자·하중·잔차·반력·
열수지·일 비교는1e-10, 좌표/SI 상사는 비영 물리적 온도차 scale로1e-9입니다.
큰 절대 Kelvin offset으로 온도차 오차를 숨기지 않습니다.

2차 strip 경계량은 두 의미가 다릅니다. variational 반력과 consistent 적분 `G+C`는
내부 FE 오차가 0이 아니어도 연속체 endpoint rate와 이미 roundoff까지 같을 수 있습니다.
이 roundoff 값에 감소하는 비영 오차를 요구하거나 차수를 정의하는 것은 적절하지 않습니다.
정확성 검사<=1e-10을 유지하며 허용치를 완화하지 않습니다.

별도로, 경계 incident cell의 raw P1 구성식 flux와 해석 법선의 내적을 적분합니다.
이는 일반적으로 정확히 보존적이지 않고 비영 이산화 오차가 있습니다. 오차가 감소하고
마지막 두 차수>=.9, 최세밀 비영 2차 경계 상대 오차<=.02여야 합니다. weak 열수지
검사를 대신하지 않습니다. 생산 담당이 보고한 초기 2실패/10통과의 roundoff 단조성
시험 정의 오류는 역사 근거이며 이번 독립 suite에서 새로 관측한 실패가 아닙니다.

관측한 마지막 내부 차수와 최세밀 raw endpoint 상대 오차입니다.

| 장 | 마지막 두 온도 차수 | 마지막 두 flux 차수 | 최세밀 raw 경계 오차 |
|---|---|---|---|
| 혼합 2차 strip | 1.998906 /1.999651 | .999266 /.999779 | .000607705 |
| Robin-only 2차 strip | 1.997677 /1.999269 | .998545 /.999560 | .001527452 |
| 혼합 smooth MMS | 1.989124 /1.997144 | .995127 /.998727 | 2차 endpoint gate 대상 아님 |
| All-Robin smooth MMS | 1.985921 /1.996221 | .994533 /.998544 | 2차 endpoint gate 대상 아님 |

대응 weak endpoint 상대 오차는 최대8.14e-14입니다. 관측 결과이지 맞춘 허용치가
아닙니다. 고정 수열에서 편한 부분집합을 선택하지 않고 실패 구간 정책을 유지합니다.

## Offset·기하·입력 검증과 실제 음성 대조

endpoint 일 항등식은
`theta^T*(K+H)*theta=theta^T*shifted_rhs+theta_D^T*R`입니다.
단위는 W K/m이며 저장 열에너지가 아닙니다. `T=c+theta`이면 shifted RHS에는
`-H*c`가 필요하며 가능하면 `h*(Tamb-c)`를 직접 적분합니다. Dirichlet·ambient 동시
이동은 물리 flux·대류를 보존합니다.2^30 K 이동에는 정확히 표현 가능한 상수 경계
데이터를 사용하여 flux/rate의1e-9 기준을 유지합니다. 반환 절대온도의 부동소수 표현
오차는 따로 허용하며 큰 Kelvin 값을 물리 gate에 넣지 않습니다.

시험은 음수 finite 수학적 Kelvin, h0 ambient 불변성, 임의 cutoff 없는 tiny positive
h1e-12, 성분별 Robin/Dirichlet anchor, 기존 다섯 인수 결과 생성, None/empty 기본값,
비균일 h*Tamb 곱·consistent 선 질량, 회전/병진·절점/요소/local-edge 순서·반전 tag·
hole 안쪽 outward normal도 다룹니다. SI 9조합은 길이 s in{1e-3,1,1e3},
전도율 c in{.1,1,10}, `Q→c/s^2*Q`, `g,h→c/s*(g,h)`입니다. T는 불변,
q는 c/s배와 회전, 단위 깊이 적분 rate는 c배입니다. callback 좌표/법선도 물리 데이터에
맞춰 변환합니다.

거절 검사는 같은 종류 중복·반전 에지, 내부/unknown/empty/self/음수/비정수 에지,
두 endpoint 고정인 자연 에지, 잘못된 scalar/column/vector callback 출력,
음수/nonfinite/bool h, h0에서도 nonfinite ambient, 복소 flux, 호환/비호환 pure Neumann입니다.
한 fixed corner endpoint는 허용합니다. flux+Robin은 의도적 additive입니다.
low-level Dirichlet/ambient Kelvin은 같은 유한실수 수학 정책을 유지하며 음수 K는
물리적 유효성 주장 밖이고 Celsius 추론도 없습니다.

실제 임시 runtime mutation은 outward 부호, H 부호, ambient load, 질량 lumping,
hTamb의 별도 평균, 반력 부호, 전도율 scale, callback 법선, 안정 offset 보정,
Neumann uniqueness의 암시적 pin을 손상시킵니다. 각 경우 기존 독립 assertion을
실행하고 생산 파일은 쓰지 않습니다. 변형 assertion 실패는 대조 검출이지 원 후보
결함이 아닙니다. 기대값은 변형/원래 생산 helper 어느 것도 정답으로 사용하지 않습니다.

## 근거 범위와 재현

첫 독립 source는20통과입니다. 확장53개도 통과했으며 최종 전용 suite는 실제 조립
연산자·tiny anchor를 추가해55개입니다. 마지막 두 개 전의 관련 실행은255통과
(독립53+기존202)였습니다. 최종 관련 실행은257통과(55+202), 설치 독립 실행은55통과입니다.
실제 runtime 음성 대조는 source10/10·설치 wheel10/10에서 각각 예상 assertion 실패
하나로 검출했습니다. 기록한 source 실행에 수치 실패는 없었습니다. 초기 shell 명령은
pytest 전에 잘못된 log redirection으로 실패했으며 실행 오류로 별도 보존했습니다.
확장 로그 하나에는 끝 summary가 없어 완전한 별도53통과 실행을 근거로 사용하고
불완전 로그에서 성공을 추론하지 않았습니다.

기존 의존성을 사용하여 저장소 루트에서 실행합니다.

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
python -m pytest -c pyproject.toml -q -s \
  packages/galerkin/tests/test_thermal_flux_robin_independent_validation.py
```

설치 소비 검사는 checkout 밖 oracle/시험 복사본을
`python -I -m pytest --confcutdir=. -q`로 실행하고 wheel import 경로와 모듈 byte
동일성을 확인합니다. index에서 새로 resolve/install하지 않고 기존 환경 의존성을
재사용합니다. source·설치·전체 회귀·정확 CI 개수는 별도 보고해야 합니다.
공유 호스트 시간은 실행 metadata이며 성능 baseline이 아닙니다. 전체 CI/release gate는
이 초기 후보의 독립 수치 근거와 별도입니다.

추가 한국어 페이지는 해당 영문의 역사 명령·SHA·수식·gate·실패/한계를 바꾸지 않은
번역입니다. 영문 링크는 페이지 기준 상대 경로로 확인합니다. 기존 영문 페이지·생산·
기존 시험·공유 packaging/README 설정은 그대로입니다.

한계는 상수 등방성 정상 2D 열전도, 지정한 매끈한 장과 다각형 기하입니다.
과도 냉각 동역학·복사·비선형 대류/재료·임의 불연속 callback 정확도·구적점 사이
양성·곡선 hole 수렴·온도 출처·headless workflow·열탄성/순차연성 수용을 뜻하지 않습니다.
