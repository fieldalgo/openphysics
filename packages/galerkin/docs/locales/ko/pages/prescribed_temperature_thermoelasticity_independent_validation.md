# 처방 온도장 기계단계의 독립 수용 검증

[영문 원문](../../../prescribed_temperature_thermoelasticity_independent_validation.md)

**한눈에 보기**

- **확인하는 것:** 원래 3차원 연속체 oracle로 `galerkin.thermoelasticity.solve_thermoelasticity`를 독립 수용 검증합니다. 명시적으로 처방한 절점 P1 Kelvin 장을 평면응력·평면변형률에서 다룹니다.
- **고정 기준:** n=8/16/32에서 두 수렴률 모두 변위 L2 ≥ 1.8, 변위 기울기 H1·3D 전체 응력 L2(zz 포함)·에너지 노름 차수 ≥ 0.9가 필요합니다. 정확 장과 에너지·일 항등식은 1e-10, 잔차는 1e-9로 일치해야 합니다.
- **범위:** 기계 단계만 다룹니다. 열전도 솔버, 온도 전달, 출처, 과도 일, 전체 연성 workflow는 검증하지 않습니다. 아래 후보 기록은 그대로 보존하며, 특정 커밋의 결과는 그 커밋의 CI 실행에서 확인하세요.

이 수용은 독립 연속체 oracle과 사전 등록 gate를 사용합니다. 명시적으로 처방한
nodal-P1 Kelvin 장에 대한 기계 응답을 다룹니다. 열 솔버·온도 전달·출처·과도 일 또는
완전 순차연성 workflow를 검증하지 않습니다.

시험 구현은 후보 `9f5ceef5f0aa5394272b25630791576d516924d8`입니다.
최종 후보 `0c9237b2dfcfabd59fa0d14091bbb1e7165eda80`는 그 후보와 develop
`6c38df4eac8db72f8ce3203a122f0ffd6afacc4e`의 정상 merge입니다.
recursive Git tree를 직접 비교했을 때 기존 변경은 `ci/README.md`,
`ci/test_multiphysics_wheel.py` 두 개뿐입니다. 열탄성 전용 module/reference/test/doc/example
6개 blob은 모두 같습니다. 특히 solver blob은
`eb806a1db8f7f8c4102f319771e242bdd10b6ea2`, reference blob은
`6230c95e9e1177e5bad378f7d3d3d56ee2685ff8`입니다. 수치 구현의 동일성을 입증하며,
다른 기능의 통합·release 수용은 별도 결정입니다.

## 원래 3차원 oracle

독립 oracle은 NumPy만 import하고 생산/refsol의 구성식·열하중·구적·장 helper를
호출하지 않습니다. 면내 공학 변형률 `(exx, eyy, gamma_xy)`에서
`exy=gamma_xy/2`를 포함하는 대칭 물리적 3D 변형률 tensor를 만듭니다.
`a=alpha*(T-Tref)`에 대해 다음과 같습니다.

```
mu = E/(2*(1+nu))
lambda = E*nu/((1+nu)*(1-2*nu))
e_elastic = e_total - a*I
sigma = 2*mu*e_elastic + lambda*trace(e_elastic)*I
psi = mu*(e_elastic:e_elastic) + lambda*trace(e_elastic)**2/2
```

평면 변형률은 total `ezz=0`입니다. 평면 응력은 원 방정식 `sigma_zz=0`을 풀어
total ezz를 구하며 ezz=0으로 두거나 z 열변형률을 버리지 않습니다. oracle은 완전한
3D contraction으로 물리 에너지를 계산합니다. 평면 변형률의 자유 면내 팽창은
`(1+nu)*a*(x,y)`, `sigma_zz=-E*a`, 잔여 에너지 밀도는 `E*a*a/2`입니다.
평면 응력의 자유 팽창은 `a*(x,y)`이고 물리 에너지는 0입니다. 완전 구속 균일 가열에서
평면 응력의 면내 법선 응력은 `-E*a/(1-nu)`, 평면 변형률의 세 법선 응력은 모두
`-E*a/(1-2*nu)`입니다. side·corner 반력은 `sigma*n`에서 독립 적분하고 corner의
반 에지 기여도 포함합니다.

각 비균일 해석에서 독립 barycentric gradient로 변위에서 상수 FE total strain을
복원합니다. 별도 tensor-product Duffy 구적으로 snapshot의 P1 온도를 내부 보간하고,
원 법칙으로 구적점마다 z를 포함한 내부 응력·물리 에너지를 구합니다. centroid 표본은
대응 centroid 출력과만 비교합니다. 변위 0의 초기 응력에서 양의 등가 열하중
`g=-integral(grad(N)*sigma_initial)`을 독립 조립합니다. 별도 체적력·내부 절점력
적분으로 전역 평형이나 해 개수만이 아닌 전체 잔차와 반력을 검사합니다.

외부 체적 하중 f와 지지 반력 r에 대해 고정 온도 endpoint 항등식은 다음과 같습니다.

```
uKu = u*(f+g+r)
U = uKu/2 - u*g + C_T
integral(sigma:e_total) = u*f + u_D*r
2U = u*f + u_D*r - u*g + 2*C_T
```

C_T는 면내 변위 0의 원 법칙 에너지를 P1 온도로 적분한 값이며 가열 경로 일이 아닙니다.
0이 아닌 처방 지지 변위가 지지점 일 누락을 검출하게 합니다. centroid `T**2`
근사는 2차 물리 에너지를 재현할 수 없습니다.

## 고정 수렴·정확장 gate

후보를 조사하기 전에 API 이전의 수학 계획·진단을 commit했습니다. 단위 정사각형의
수열 `n=8,16,32`, `E=70e9 Pa`, `nu=.3`, `alpha=12e-6 /K`,
`Tref=293.15 K`를 유지합니다. 인접 두 구간 모두 변위 L2 차수 1.8 이상, 전체
변위 gradient H1·zz 포함 완전 3D 응력 L2·tangent energy norm은 .9 이상이어야 합니다.
비선형 온도 보간은 L2 1.8, H1 .9 이상입니다. 이는 처방 장 보간이지 열 FEM 수렴이 아닙니다.

두 평면 모델에서 서로 다른 세 장을 사용합니다.

- 적합한 선형 온도 `theta=10+20*x`:
  `v=(a0*x+p*(x*x-y*y)/2, a0*y+p*x*y)`, `a0=10*alpha`, `p=20*alpha`.
  PS의 변위는 v, PE는 `(1+nu)*v`입니다. 최소 scalar 지지 3개와 영 total 자연
  traction을 씁니다. 오차에서 질량 가중 additive 강체 운동만 제거하며 변형률·전단·scale·
  아핀 fit은 금지합니다. 정확한 P1 온도·gradient는 `1e-10` 이내로 일치해야 합니다.
- 등록한 sine 장: `theta=20*sin(pi*x)*sin(pi*y)`,
  `u=(1e-4,.6e-4)*sin(pi*x)*sin(pi*y)`, 외곽 두 성분 고정.
- 추가 독립 다항식 장: `theta=8+13*x*x-7*x*y+5*y*y`,
  `ux=1e-4*(x*x*y+x*y*y+x**3/3)`,
  `uy=1e-4*(x*y*y-2*x*x*y+y**3/4)`, 정확한 비영 외곽 변위.

비선형 장의 원 total stress를 직접 미분한 체적력은
`b=-mu*Laplacian(u)-(lambda_eff+mu)*grad(div(u)) + beta*grad(T)`입니다.
PS에서 `lambda_eff=E*nu/(1-nu**2)`, PE에서 원 lambda를 쓰고,
beta는 PS `E*alpha/(1-nu)`, PE `E*alpha/(1-2*nu)`입니다.
oracle에는 명시적으로 미분한 성분 공식이 있습니다.

norm 구적 차수 8과 10은 각 측정 오차의 1% 미만 차이여야 합니다. 기준 물리 에너지의
12·16차 구적은 비영 특성 에너지 scale의 `1e-8` 이내로 일치해야 합니다.
물리 에너지 오차는 refinement마다 감소하고 마지막 정규화 값이 .02 이하여야 합니다.
힘/모멘트·자유 잔차는 `1e-9`, 정확장·에너지/일 항등식은 `1e-10`이며 비영 특성
변형률·응력·힘·에너지로 정규화합니다. 결과를 보고 gate를 바꾸지 않았습니다.
균일 PS의 영 에너지는 0으로 나누지 않고 특성 scale로 정규화합니다.

## 수용 근거와 대조

독립 suite는 37개입니다. 가열/냉각·부호 있는/영 alpha·비영 기계 baseline·T/Tref 이동,
분리 성분·부족한 강체 지지·회전/병진·절점/요소/local vertex/에지 순서, snapshot 복사,
write flag 거절·stale mesh·잘못된 shape·nonfinite/음수 절대온도·단위/metadata·mutable
배열 교체를 다룹니다. checksum 충돌을 강제해도 실제 mesh 배열이 다르면 거절해야 합니다.
재현 FNV-1a64는 checksum이지 암호서명이나 인증된 온도 출처가 아닙니다.
올바르게 표시한 수동 데이터가 열 솔버에서 왔다고 식별하지 않습니다.

source와 설치 wheel에서 독립 37개가 모두 통과했습니다. 수정하지 않은 후보 suite
46개(엔진39·reference7)와 관련 source는 83통과입니다. 최초 source는 26통과와
아핀 온도 gradient norm의 시험 broadcasting 실패 2개였으며 원 traceback을 보존했습니다.
구적 축 수정은 gate나 생산 파일을 바꾸지 않았습니다.

최세밀 mesh의 정규화 물리 에너지 오차(PS/PE)는 선형 온도 .00018018/.00035537,
sine .00180161/.00237582, 다항식 .00048015/.00090519입니다. 선형 온도 변위
차수는 최소 1.8753, sine은 1.9725, 다항식은 1.9992입니다. 등록한 gradient·응력·
tangent energy·온도 보간 gate는 인접 두 refinement에서 모두 통과합니다.

실제 source·설치 검사는 임시 runtime mutation을 거절합니다. 잘못된 PE 면내-alpha
shortcut, 열계수 3배, 열 RHS 부호, 열하중 누락, zz 응력 누락, centroid-only 물리
에너지, 지지 반력/일 누락, mesh binding 우회입니다. 각 변형 실행은 기존 독립 assertion에서
실패합니다. 생산 파일을 편집하거나 완화한 gate로 거절을 만들어내지 않습니다.

저장소 루트에서 실행합니다.

```
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python -m pytest -q \
  packages/galerkin/tests/test_thermoelasticity_independent_validation.py
```

설치 소비 검사는 독립 oracle·시험을 checkout 밖에 복사하고 의존성/index 없이 local
wheel을 설치한 뒤 `python -I -m pytest --confcutdir=. -q`를 실행합니다.
전용 venv에서 기존 환경 의존성을 재사용하므로 clean-room 의존성 설치는 아닙니다.
공유 호스트 시간은 실행 metadata이며 성능 baseline이 아닙니다.

첫 37-case 제출의 로컬 전체 루트 회귀는 657시험·9subtest 통과, optional 환경 skip16,
기존 의존성 폐기예정 경고1이었습니다. 마지막 같은 사례 suite는 명시적 변형률 norm과
모든 비선형 보간 norm의 구적 차수 비교를 추가합니다. 그 초기 개발 실행에서 exact-temperature
assertion이 새 비영 변형률 오차 열을 포함한 오류가 드러났습니다(35통과·시험실패2).
온도·gradient 열만 검사하도록 고쳐 기존 모든 기준을 유지했고, source 재검증은 37통과였습니다.
