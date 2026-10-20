# 2D 탄성의 독립 수용 검증

[영문 원문](../../../elasticity2d_independent_validation.md)

이 검증은 `galerkin.elasticity`, `refsol.elasticity`와 기존 시험을 바꾸지 않고
독립 다항식 장과 시험을 추가합니다. 조사한 구현은 commit
`52ede82a5e1390c3a14b41be0b7fa70d4f035c08`입니다. 균질 등방성 미소변형률 P1
삼각형, 단위 면외 두께, 명시적인 두 평면 모델, 성분별 Dirichlet 조건과 기존
자연 영 traction 경계를 다룹니다. 0이 아닌 표면 traction, 불균질 재료, 비선형
탄성 또는 비압축성 근처의 locking-free 거동을 검증하지 않습니다.

## 재료와 힘의 직접 공식

길이는 m, 응력은 Pa, 힘 밀도는 N/m^3입니다. E=17e6, nu=.23, a=.002로 둡니다.
oracle은 공학 변형률 (exx, eyy, gamma), gamma=ux,y+uy,x를 사용하며, 엔진/refsol의
구성식·응력·gradient·하중 helper를 import하지 않습니다.

sigma_xx=A exx+B eyy, sigma_yy=B exx+A eyy, sigma_xy=G gamma로 두고 직접 계산합니다.

| 모델 | A | B | G |
|---|---|---|---|
| 평면 응력 | E/(1-nu^2) | E nu/(1-nu^2) | E/[2(1+nu)] |
| 평면 변형률 | E(1-nu)/[(1+nu)(1-2nu)] | E nu/[(1+nu)(1-2nu)] | E/[2(1+nu)] |

각각 3D 등방성 응력 법칙에서 sigma_zz=0 또는 epsilon_zz=0로 유도합니다.
솔버는 면외 변형률/응력을 반환하지 않으며, 이를 면내 공학 전단 관례와 혼동하지 않습니다.

## 3차 벡터 manufactured solution

단위 정사각형에서 기존 sine benchmark와 다른, 경계에서 0이 아닌 장을 선택합니다.

    ux = a (x^2 y + x y^2 + x^3/3)
    uy = a (x y^2 - 2 x^2 y + y^3/4)

미분하면 다음과 같습니다.

    exx   = a (2xy + y^2 + x^2)
    eyy   = a (2xy - 2x^2 + 3y^2/4)
    gamma = a (x-y)^2

force=-div(sigma)를 직접 적용하면 다음을 얻습니다.

    fx = -a [A(2y+2x) + B(2y-4x) + G(-2x+2y)]
    fy = -a [G(2x-2y) + B(2x+2y) + A(2x+3y/2)]

모든 경계 절점에서 변위 두 성분을 처방합니다. 경계 traction은 일반적으로 0이
아닙니다. 하중은 솔버 잔차에 맞춰 만들지 않고 내부 구적점에서 평가합니다.
중심 차분으로 변위 미분과 해석 응력의 발산을 독립 검사합니다. 힘의 부호 반전,
공학 전단의 절반 적용, 반대 평면 모델은 비교에 실패해야 하는 음성 대조입니다.
이는 oracle 일관성 대조이며 모든 구현 결함을 mutation 시험으로 다뤘다는 뜻은 아닙니다.

## 2차 혼합 성분·영 traction 해

k=B/A, M=A-B^2/A로 두면 별도 폐형식은 다음과 같습니다.

    ux = a (x^2 + k y^2),    uy = -2 a k x y
    exx = 2ax,              eyy = -2akx,    gamma = 0
    sigma_xx = 2aMx,        sigma_yy = sigma_xy = 0
    body force = (-2aM, 0)

평면 응력에서는 k=nu, M=E이고, 평면 변형률에서는 k=nu/(1-nu), M=E/(1-nu^2)입니다.
좌우에서 ux, 아래에서 uy=0을 처방합니다. 구속하지 않은 위쪽 traction은 정확히 0입니다.
좌우의 자유 y 성분과 아래의 자유 x 성분에도 traction이 없습니다. 이는 절점 정확성을
가정한 것이 아닌 비아핀 혼합 경계 문제입니다. 별도 미분으로 해석 장과 응력을 검사합니다.

단위 두께당 정확한 연속체 에너지는 다음과 같습니다.

    U = (1/2) integral sigma:epsilon dA = 2 a^2 M / 3.

상수 fx=-2aM에서 전체 체적력은 (-2aM,0), 원점 기준 모멘트는 +aM입니다.
경계 반력은 이 합력을 평형시킵니다. 1.3 by .7 직사각형에서 전치한 수직 아핀
신장도 정확한 성분 구속과 위쪽 합반력 1.3*a*M을 확인합니다.

## 첫 실행 전 고정한 내부 적분과 검사

두 해와 두 평면 모델 모두 단위 정사각형에서 n=6,12,24를 사용합니다.
별도 Duffy tensor Gauss 차수 5와 7로 삼각형 내부를 적분합니다. 오차는 다음과 같습니다.

- 변위 L2: integral |u_h-u|^2의 제곱근
- tensor 변형률 L2: integral (dexx^2+deyy^2+dgamma^2/2)의 제곱근
- 에너지 norm: 직접 평가한 oracle 응력 법칙으로 integral delta_epsilon:delta_sigma의 제곱근

모든 오차가 감소하고 마지막 변위 차수는 1.8 이상, 변형률/에너지 차수는 .9
이상이어야 합니다. 구적 차수 5/7은 상대 1e-9 이내로 일치해야 합니다. 두 차수 모두
이 다항식을 정확히 적분하기에 충분합니다. 기대 P1 차수는 2와 1입니다. 이는 매끈한
고정 재료·규칙적 fixture의 기준이지 특이점이나 임의 mesh에 대한 주장이 아닙니다.
수치 기준은 아래 결과를 계산하기 전에 고정했습니다.

각 FE 요소 변형률은 [1,x,y]의 아핀 Cartesian 변위 계수를 풀고 그 fit을 미분하여
독립 복원합니다. 생산 B 행렬을 재사용하지 않고 공학 전단을 명시적으로 검사합니다.

모든 수렴 mesh에서 조립 하중·모멘트를 직접 힘 적분과 비교하고(상대 1e-10),
load+reaction의 힘/모멘트 평형(1e-9), 자유 DOF 반력 0, 독립 변형률/응력과
다음 이산 일 항등식(1e-9)을 확인합니다.

    2 U_h = sum_i body_load_i dot u_i + sum_fixed reaction_i * prescribed_i.

0이 아닌 처방 변위에는 지지점 일이 필수입니다. 독립 아핀 가상 변위로
integral sigma:epsilon(v)와 sum_i (load_i+reaction_i) dot v_i도 비교합니다.
평형 항등식만으로 물리적 정확성을 입증할 수 없으므로 다항식 수렴·직접 응력 검사는 별도입니다.

변형된 해에 강체 병진/미소 회전을 더하면 변위만 그 운동만큼 바뀌고 변형률·응력·반력은
유지되어야 합니다. 정확히 세 독립 성분 구속으로 순수 강체 운동도 복원하고, 세 번째
지지를 제거하면 강체 nullspace를 거절해야 합니다. .37 rad 회전, scale 2,
병진 (2.3,-1.7), 절점/요소 순열, connectivity 반전을 조합하여 다음 변환을 검사합니다.

    x' = s Q x + c, u' = s Q u, f' = Q f / s,
    sigma' = Q sigma Q^T, load' = s Q load, reaction' = s Q reaction.

비교 허용치는 상대 1e-9, 변위/변형률 절대 1e-12, 응력 절대 1e-6 Pa,
힘 절대 1e-9 N/m입니다. mesh 좌표 공변성 검사이며, 혼합 경계 지지의 임의
성분별 회전을 의미하지 않습니다.

## 관측한 source 결과

첫 등록 실행은 기준 변경 없이 독립 10개가 통과했습니다. 별도 혼합 oracle/최소
강체 검사를 더하면 독립 12개입니다. 기존 탄성·패키지 독립성 시험은 그대로이며,
관련 합동 실행은 84통과·실패/skip 0입니다.

| 해 | 평면 | 마지막 L2 차수 | 마지막 변형률 차수 | 마지막 에너지 차수 |
|---|---|---:|---:|---:|
| 3차 | stress | 1.9996468 | .9995067 | .9994900 |
| 3차 | strain | 1.9996468 | .9995067 | .9994846 |
| 혼합 2차 | stress | 1.9886895 | .9988464 | .9978539 |
| 혼합 2차 | strain | 1.9856805 | .9983809 | .9966891 |

혼합 수치 에너지는 폐형식에 아래쪽에서 접근합니다.
stress는 45.01863,45.25394,45.31342 대 45.33333,
strain은 47.53282,47.78104,47.84421 대 약 47.86541 J/m입니다.
관측 결과이며 새로 맞춘 수용 경계가 아닙니다.

기존 패키지를 설치한 저장소 루트에서 실행합니다.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
python -m pytest -c pyproject.toml -q -s -ra \
  tests/galerkin/test_elasticity2d_independent_validation.py \
  tests/galerkin/test_elasticity2d.py \
  tests/refsol/test_elasticity_reference.py \
  tests/galerkin/test_independence.py
```

신규 의존성이나 외부 솔버 구현을 사용하지 않습니다. 다항식/연속체 항등식은 여기서
유도하며 기존 NumPy/SciPy가 산술·선형해를 수행합니다. source와 설치 wheel 결과,
전체 시험의 환경 실패, 미실행 배포 gate는 구분해서 보고해야 합니다. 이 시험만으로
모든 패키징·플랫폼·물리 모델을 인증하지 않습니다.

## 설치 artifact와 음성 대조

기존 build 도구로 sdist에서 만든 galerkin wheel의 `elasticity.py`는 조사 source와
byte-identical입니다. source 밖에서 `python -I`로 새 독립 12개를 실행하면 이 wheel의
galerkin을 import하며 **12통과·실패/skip 0**입니다. 환경은 이미 설치된 NumPy/SciPy/pytest
도구를 재사용하므로 clean dependency resolver나 플랫폼 간 호환 인증이 아닙니다.

별도 격리 프로세스 세 개는 source/wheel bytes를 유지하면서 설치 모듈을 메모리에서
의도적으로 손상시킵니다. 동일 허용치의 원래 `polynomial-stress` 수렴 사례를 실행합니다.

| 주입한 구현 오류 | 관측한 거절 |
|---|---|
| 전단 구성 계수에 .5를 곱함 | 독립 응력 비교 실패; 전단 상대 불일치 .5 |
| 평면 응력/변형률 선택을 교환 | 독립 응력 비교의 법선 성분 실패 |
| 공급 체적력에 -1을 곱함 | 전체 하중이 직접 힘 적분과 상대 2만큼 다름 |

각 프로세스는 예상한 assertion 실패 하나로 종료합니다. 이는 음성 대조이며 수정하지 않은
후보의 결함이 아닙니다. 주입 wrapper가 결함 변형을 만들 때 원래 routine을 호출할 수
있지만, 기대값 oracle은 그 routine을 호출하지 않습니다.

전체 source 실행은 **564통과·7실패·9skip**, subtest 9통과와 기존 FastAPI/Starlette
폐기예정 경고 1개입니다. 실패 7개는 Gmsh 실행 파일 부재가 필요한 사례입니다
(unstructured cavity, mesh interop, mesh 파일 생성). skip은 Gmsh 통합 7개와
로컬 refractiveindex.info 데이터베이스 부재 2개입니다. 전체 green 주장과 다릅니다.
원래 후보의 원격 CI 결과는 별도 검증입니다. 환경 실패를 없애기 위해 Gmsh skip helper,
기존 물리 허용치, 패키징 설정 또는 생산/refsol 구현을 바꾸지 않았습니다.
엄격한 다중 패키지 배포/metadata 검증은 여기서 재실행하지 않았으며, 위 wheel 검사는
이 독립 수용 범위를 다룹니다.
