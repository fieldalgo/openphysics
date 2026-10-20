# 경계 traction의 독립 수용 검증

[영문 원문](../../../elasticity_traction_independent_validation.md)

조사한 구현은 `8bb3df93c657c4d8e3a3eb496b805da6bf10b936`입니다. 이 검증은 생산
구현·기준해·기존 수용 시험·허용치·의존성·CI 설정을 바꾸지 않습니다. oracle은 명시적
연속체 공식, 독립 Cartesian 다항식 fit, 별도 표면/내부 적분을 사용합니다. 기대값 생성에
엔진의 구성식·변형률·하중·법선·traction 조립 helper나 원래 traction 기준장을 사용하지 않습니다.

## 독립 혼합 경계 해

L0=1 m, X=x/L0, Y=y/L0, a=.002 m, E=17e6 Pa, nu=.23으로 둡니다.

    ux/a = X^2 Y + X Y^2 + X^3/3 + .4 + .2 X - .3 Y
    uy/a = X Y^2 - 2 X^2 Y + Y^3/4 - .25 + .35 X + .1 Y

아래는 공학 변형률에 L0/a를 곱한 값입니다.

    exx:   2XY + Y^2 + X^2 + .2
    eyy:   2XY - 2X^2 + .75Y^2 + .1
    gamma: (X-Y)^2 + .05

sigma_xx=C exx+D eyy, sigma_yy=D exx+C eyy, sigma_xy=G gamma를 사용합니다.

| 평면 | C | D | G |
|---|---|---|---|
| stress | E/(1-nu^2) | E nu/(1-nu^2) | E/[2(1+nu)] |
| strain | E(1-nu)/[(1+nu)(1-2nu)] | E nu/[(1+nu)(1-2nu)] | E/[2(1+nu)] |

조립 잔차 대신 이 응력을 직접 미분하면 N/m^3 단위 힘 밀도를 얻습니다.

    fx = -a/L0^2 [C(2X+2Y) + D(2Y-4X) + G(-2X+2Y)]
    fy = -a/L0^2 [G(2X-2Y) + D(2X+2Y) + C(2X+1.5Y)]

아핀 항은 힘 밀도는 바꾸지 않고 0이 아닌 경계 trace와 상수 응력을 바꿉니다.
경계 밖 내부에서 중심 차분으로 oracle의 변위·응력 미분을 별도 검사합니다.

왼쪽에는 ux만, 아래에는 uy만 처방합니다. 이 trace는 0이 아닙니다. 네 면 모두에
유도한 전역 Cartesian traction을 공급합니다.

    t = (sigma_xx nx + sigma_xy ny, sigma_xy nx + sigma_yy ny).

자유 성분에는 자연 경계 데이터이며, 구속 성분에는 API가 유지하는 외부 하중입니다.
지지 반력은 원래 Ku-load로 계산합니다. 고정 절점/모서리의 외력을 조용히 버리는 대신
겹침을 의도적으로 시험합니다. 두 scalar roller trace가 강체 모드를 억제합니다.
전역 Cartesian 한 성분 구속을 임의 회전 방향인 것처럼 단순 회전하면 안 됩니다.

이 장과 경계 선택은 원래 traction benchmark의 다항식 및 왼쪽 두 성분 동차 clamp와 다릅니다.

## 독립 적분과 고정 기준

두 평면 모델에서 정사각형 mesh 수열 n=6,12,24를 해석 전에 고정했습니다.
별도 Duffy tensor Gauss 차수 5와 7로 삼각형 내부를 적분합니다. 기대 P1 변위 L2와
tensor 변형률/에너지 차수는 2와 1입니다. 모든 오차가 감소하고 마지막 L2 차수는
1.8 이상, 변형률/에너지 차수는 .9 이상이어야 합니다. 차수 5/7은 상대 1e-9로
일치해야 합니다. 매끈한 고정 재료 fixture 기준이며 특이 영역·비압축성 근처의 보편 기준은 아닙니다.

FE 변형률은 각 cell의 Cartesian 아핀 변위를 [1,x,y]에 fit하여 복원합니다.
tensor Frobenius 밀도는 `dexx^2+deyy^2+dgamma^2/2`입니다. 에너지 오차는
생산 재료 helper 없이 변형률 오차의 직접 응력으로 계산합니다.

전체 기대 절점 하중은 독립 적분합니다. 체적 항은 내부 7차, 경계 facet은 알려진
정사각형 법선과 10차 선 구적입니다. 각 조립 절점 성분과 상대 1e-11, 절대 하한
1e-8 N/m로 일치해야 합니다. 이는 합력 0만 검사하는 것보다 강합니다. 대칭 해석
응력의 전체 체적력+표면력 및 모멘트는 0입니다. consistent shape function이
상수·선형 가상 변위를 재현하므로 절점 하중이 이 합력을 보존합니다.

모든 MMS 해석에서 독립 fit 변형률/응력, 전체 힘·모멘트 평형, 아핀 가상 일과
다음을 확인합니다.

    2 U_h = sum_i load_i dot u_i + sum_fixed reaction_i * prescribed_i.

load는 체적력과 traction을 포함하고 U_h는 면외 단위 두께당 J/m입니다.
0이 아닌 처방 변위에서는 지지점 일을 생략할 수 없습니다. 일/평형 허용치는 상대
1e-9입니다. 응력/변형률/변위 절대 하한은 각각 1e-6 Pa, 1e-12, 1e-12 m입니다.
mesh 변환 비교는 상대 1e-10과 힘 하한 1e-8 N/m입니다. 결과를 보기 전에 고정한 값입니다.

## 정확한 선 하중과 아핀 물리 해

단위 오른쪽 에지에 독립 비균일 traction을 사용합니다.

    t(y) = (3+2y^6, -4+y^5) Pa.

전체 에지에서 integral N0*y^p=1/[(p+1)(p+2)], integral N1*y^p=1/(p+2)입니다.
[a,b]에서는 y^p와 y^(p+1)의 정확한 부정적분으로 두 선형 shape 하중을 구합니다.
에지 subdivision 1,3,9에서 각 절점 성분을 비교합니다. 합력은 (3+2/7,-4+1/6),
원점 기준 모멘트는 `-4+1/6-3/2-2/8`입니다. 6차 traction과 선형 shape의 곱은
7차이므로 명시된 4점 Gauss가 정확히 적분해야 합니다. 전체 힘만으로 놓칠 수 있는
선 구적 가중치 오류를 검사합니다.

각 평면에서 수직 단축 인장 P=127 Pa와 전치 전단 tau=91 Pa를 별도 검사합니다.
수직 compliance는 다음과 같습니다.

| 평면 | exx | eyy |
|---|---|---|
| stress | -nu P/E | P/E |
| strain | -nu(1+nu) P/E | (1-nu^2) P/E |

단축 roller 해는 u=(exx*x,eyy*y), sigma=(0,P,0)입니다. 전단은
u=(0,tau*x/G), 왼쪽 두 성분 고정이며 오른쪽/위/아래 traction은 sigma=(0,0,tau)에서
나옵니다. 두 해는 아핀이며 수치 roundoff까지 재현합니다. refsol·엔진 재료 helper
대신 직접 compliance를 사용합니다.

## 법선·압력·겹침·변환·거절

전역 Cartesian callback `t=-P*n`, P>0는 재료를 압축합니다. API에 암시적 scalar
압력 관례는 없고 `+P*n`은 반대 부호입니다. 직사각형과 다각형 annulus에서 양 부호를
시험합니다. annulus 내부 경계의 재료 outward normal은 hole 안으로 향합니다.
기대 facet 법선은 알려진 기하에서 구합니다. 직사각형은 축 법선, 정규 동심 다각형은
정규화한 facet midpoint이며 hole에서 부호를 뒤집습니다. 절점 압력 하중마다
facet 길이 절반×상수 traction과 비교합니다. 순합 0만으로 뒤집힌 법선을 검출할 수 없습니다.

압력 하중 시험은 에지 반전·tag 순서·삼각형 connectivity 반전·임의 절점/요소 순서,
.41 rad 회전, 병진 (1.7,-2.1), 길이 scale 2를 조합해 개별 하중과 반력을 검사합니다.
왼쪽 변위 두 성분을 clamp한 추가 비아핀 MMS도 같은 변환에서 실제 변위·응력 공변성을 검사합니다.

    x' = s Q x+c, u' = s Q u, body' = Q body/s, traction' = Q traction,
    sigma' = Q sigma Q^T, load' = s Q load, reaction' = s Q reaction,
    U' = s^2 U.

두 성분 clamp는 완전 벡터 조건으로 변환할 수 있습니다. 전역 한 성분 roller를
그대로 두고 임의 회전에 공변한다고 주장하지 않습니다.

완전히 처방한 비영 아핀 경계에 추가 비균일 traction을 주면 변위는 같고 반력 변화는
추가 절점 하중의 음수여야 합니다. None과 {}는 모든 결과 배열을 정확히 보존합니다.
거절 사례는 선택 tag 중복, 반전 중복 에지, 내부 에지, 잘못된 shape, 비정수/음수 index,
self edge, node-only tag, callback shape/전치 오류, nonfinite/복소수, 부족한 강체 지지입니다.
생산 검증을 바꾸지 않고 원래 ValueError 계약을 사용합니다.

## 관측한 source 근거

첫 독립 실행은 원 사전 기준 그대로 31통과·실패/skip 0이었습니다. 변위/응력 공변성
2개를 추가하면 새 검사 33개입니다. 원래 traction·탄성·패키지 독립성 검사와 함께
**150통과·실패/skip 0**입니다.

| 평면 | 마지막 L2 차수 | 마지막 변형률 차수 | 마지막 에너지 차수 |
|---|---:|---:|---:|
| stress | 1.9416220 | .9756523 | .9746632 |
| strain | 1.9409472 | .9764219 | .9742340 |

관측 차수는 원 benchmark와 다르며 맞춘 허용치가 아닙니다. 이 범위에서 생산 결함은
관측되지 않았습니다. 한계는 균질 등방 선형 미소변형률 2D, 다각형 hole, 고정 매끈한
장과 지정 재료입니다. 모든 traction regularity·곡면 경계·큰 변형·재료·플랫폼 또는
비압축성 근처 locking-free formulation 검증이 아닙니다.

기존 패키지를 설치한 저장소 루트에서 실행합니다.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
python -m pytest -c pyproject.toml -q -s -ra \
  tests/galerkin/test_traction_independent_validation.py \
  tests/galerkin/test_elasticity_traction.py \
  tests/refsol/test_elasticity_traction_reference.py \
  tests/galerkin/test_elasticity2d.py \
  tests/refsol/test_elasticity_reference.py \
  tests/galerkin/test_independence.py
```

외부 솔버 소스·신규 의존성은 사용하지 않습니다. 설치 wheel 검사, 구현 음성 대조,
전체 시험/CI 결과와 이 source 관측은 구분해야 합니다.
