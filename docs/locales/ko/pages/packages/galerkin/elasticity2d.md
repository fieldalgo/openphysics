# 2차원 소변형률 탄성

[English original](../../../../../packages/galerkin/elasticity2d.md)

`galerkin.elasticity`와 `refsol.elasticity`를 명시적으로 import합니다. 이 첫 구현은
적합 `galerkin.mesh.Mesh` P1 삼각형에서 균질·등방성·선형·정적 변위 정식화를 씁니다.
절점당 변위 자유도는 두 개이며 스칼라·전자기 edge 공간은 사용하지 않습니다.
E와 nu는 이름 있는 메시 영역마다 구간 상수 `{영역 이름: 값}`으로 줄 수도 있으며,
그 확장과 정답·기준은 [multimaterial](multimaterial.md)에 있습니다. 따로 적지 않으면
아래 내용은 균질 재료 하나를 설명합니다.

## 방정식과 관례

면내 변위 u=(u_x,u_y)에 대해 다음과 같습니다.

    -div(sigma) = b,
    epsilon = (grad(u) + grad(u).T)/2,
    sigma = 2*mu*epsilon + lambda_eff*trace(epsilon)*I.

공학 변형률 벡터는 `(epsilon_xx, epsilon_yy, gamma_xy)`이며,
**gamma_xy = 2*epsilon_xy = du_x/dy + du_y/dx**입니다. 면내 응력 벡터는
`(sigma_xx, sigma_yy, sigma_xy)`입니다. 따라서 전단 행렬 성분은 2*mu가 아닌 mu이며
응력의 일은 `stress @ strain`입니다.

    mu = E / (2*(1+nu))
    D = [[lambda_eff+2*mu, lambda_eff,      0],
         [lambda_eff,      lambda_eff+2*mu,0],
         [0,               0,             mu]]

필수 인자 `plane`은 서로 다른 두 모델 중 하나를 선택합니다.

| plane | 면외 조건 | lambda_eff | 반환하지 않는 면외량 |
|---|---|---|---|
| `"stress"` | sigma_zz=sigma_xz=sigma_yz=0 | E*nu/(1-nu^2) | epsilon_zz=-nu*(epsilon_xx+epsilon_yy)/(1-nu) |
| `"strain"` | epsilon_zz=epsilon_xz=epsilon_yz=0 | E*nu/((1+nu)*(1-2*nu)) | sigma_zz=lambda_eff*(epsilon_xx+epsilon_yy) |

모델을 자동 선택하지 않습니다. 두 모델 모두 안정한 3차원 모재 영역인 유한 스칼라
**E>0, -1<nu<0.5**를 사용합니다. auxetic nu<0도 허용합니다. 측면이 자유인 단축
인장에서도 두 모델의 횡변형률·축강성은 서로 다릅니다.

shape-function gradient와 교차 배치한 국소 DOF를 사용합니다.

    B = [[N0,x, 0,    N1,x, 0,    N2,x, 0],
         [0,    N0,y, 0,    N1,y, 0,    N2,y],
         [N0,y, N0,x, N1,y, N1,x, N2,y, N2,x]]
    K_e = area * B.T @ D @ B
    f_e = integral_over_triangle(N_vector.T @ b) dA

전역 DOF `2*i`는 절점 i의 x 변위, `2*i+1`은 y 변위입니다. 요소 변형률·응력은
각 삼각형에서 일정합니다. 체적력은 6x6 Gauss-Legendre Duffy 규칙으로 적분하며
상수 체적력에 정확합니다. 매끄러운 비다항식 하중은 근사합니다. 불연속·고진동 하중은
이 gate 범위 밖의 mesh·구적 연구가 필요합니다.

## 입력·출력 단위

2차원 약형은 **면외 단위 두께당**입니다. 두께 인자를 받지 않아 하중 속에 길이 인자가
숨지 않게 합니다.

| 물리량 | shape/관례 | SI 단위 |
|---|---|---|
| Mesh 좌표 | `(N,2)` | m |
| E, stress | 스칼라 E 또는 `{영역 이름: E}`; stress `(T,3)` | Pa = N/m^2 |
| nu, strain | 스칼라 nu 또는 `{영역 이름: nu}`; strain `(T,3)`, 공학 전단 | 무차원 |
| 처방·결과 변위 | `(node,component)`마다 스칼라; 결과 `(N,2)` | m |
| body_force | 상수 `(2,)` 또는 콜백 `(Q,2)->(Q,2)` | N/m^3 |
| 내부 강성행렬 | `(2N,2N)` | N/m^2 |
| result.load | consistent 체적·경계 절점 하중의 합 `(N,2)` | 두께당 N/m |
| result.reaction | 물체에 작용하는 지지력 `(N,2)` | 두께당 N/m |
| result.residual | 모든 DOF의 `K*u-load`, `(N,2)` | 두께당 N/m |
| 복원한 `0.5*u.T*K*u` | 두께당 에너지 | J/m = N |

실제 두께 t(m)를 하중·반력·에너지에 곱하면 N·N·J를 얻습니다. **두께 1 m**에서만
수치가 총량과 같습니다. 1 mm 판에는 0.001을 곱해야 합니다. 균일한 두께 스케일링에서
변위·변형률·응력은 바뀌지 않습니다. 체적력은 체적 밀도이며 총 절점력이나 edge 선하중이 아닙니다.

## API와 경계 조건

```python
from galerkin.mesh import rectangle_mesh
from galerkin.elasticity import solve_elasticity

mesh = rectangle_mesh(.1, .02, 20, 4)  # coordinates in metres
bc = {(int(i), c): 0. for i in mesh.boundary["left"] for c in (0, 1)}
r = solve_elasticity(mesh, young_modulus=70e9, poisson_ratio=.3,
                     plane="stress", dirichlet=bc,
                     body_force=(0., -2700*9.81))
print(r.displacement[:, 1].min())
print(r.load.sum(axis=0), r.reaction.sum(axis=0))
```

`dirichlet`는 `{(node_index, component): value_in_metres}` 매핑입니다. 성분 0은 x,
1은 y이며 0이 아닌 처방도 지원합니다. 인덱스는 bool이 아닌 정수여야 하고 절점은 구멍
경계를 포함한 실제 기하 경계에 있어야 합니다. `mesh.boundary` 이름에 의존하지 않으며
절점 tag는 매핑 생성의 편의 수단일 뿐입니다. traction 매핑이 없으면 구속되지 않은
경계 성분의 traction은 모두 0입니다. x만 처방하면 경계 하중이 없는 한 y traction은
0으로 남습니다. 선택적 `traction` 매핑으로 0이 아닌 전역 Cartesian 경계 traction을
지원합니다. tag·콜백 법선·consistent 적분·처방 DOF의 하중은
[traction 가이드](../../../../../packages/galerkin/elasticity_traction.md)를 보십시오. 점하중·주기 구속·다점
구속은 지원하지 않습니다. 이 첫 API는 내부 처방 변위를 거부합니다.

체적력 콜백은 모든 구적 좌표를 실수 `(Q,2)` 배열로 받고 정확히 같은 shape의 유한
실수 배열을 반환해야 합니다. 콜백은 한 번 평가하며 상태를 가진 콜백은 권장하지 않습니다.
상수 힘은 정확히 `(2,)`여야 합니다. 절점별·요소별 하중 배열을 암묵적으로 해석하지 않습니다.

`ElasticityResult`는 `displacement`, `strain`, `stress`, `load`, `reaction`,
`residual`과 명시적 `plane` 문자열을 포함합니다. 반력은 처방 DOF에서 `K*u-load`,
자유 DOF에서 0입니다. 자유 DOF 잔차는 작아야 하며 처방 위치의 잔차는 물리 반력이지
수렴 실패가 아닙니다. 적용 traction이 0이면 반올림 범위에서
`sum(reaction)+sum(load)=0`입니다. 반력은 구속 소거 전 원래 계를 사용합니다.

예제는 본인 환경에 기존 패키지를 설치하고 저장소 루트에서 실행합니다.

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python examples/galerkin/elasticity2d.py
python -m pytest -q -s tests/galerkin/test_elasticity2d.py \
  tests/galerkin/test_mesh_overlap_candidates.py \
  tests/refsol/test_elasticity_reference.py
python -m pytest -q
```

## 독립 정답과 고정 수용 gate

`refsol.elasticity`는 FEM engine·solver를 import하지 않습니다. `affine`은
`u=gradient*x+offset`을 계산하고, `stress_from_strain`은 plane별 폐형식 응력 방정식을
쓰며, `sine_manufactured`는 해석적 Navier 방정식을 직접 미분합니다. 모두 면외 성분
없이 공학 변형률·면내 응력을 반환합니다. FEM 구현은 정답을 import하지 않습니다.

단위 정사각형의 비자명한 manufactured case는 다음과 같습니다.

    u = 1e-3*sin(pi*x)*sin(pi*y)*(1, 0.6)
    s = sin(pi*x)*sin(pi*y), c = cos(pi*x)*cos(pi*y)
    b_x = pi^2*((lambda_eff+3*mu)*1e-3*s-(lambda_eff+mu)*0.6e-3*c)
    b_y = pi^2*((lambda_eff+3*mu)*0.6e-3*s-(lambda_eff+mu)*1e-3*c)

E=70000 Pa, nu=0.3입니다. 전체 경계에 두 성분을 처방합니다. 이 정확해에서 변위가
0이라고 traction이 0인 것은 **아닙니다**. 구조 mesh는 방향별 n=8,16,32 분할을
사용합니다. 변위 L2 오차와 tensor 변형률 Frobenius 오차는 독립 8x8 Duffy 규칙으로
적분합니다. 에너지 오차는 1/2 인자 없이
`sqrt(integral((epsilon_h-epsilon):D:(epsilon_h-epsilon)) dA)`입니다.
변형률 norm은 `exx^2+eyy^2+gamma_xy^2/2`를 사용합니다.

다음 gate는 구현 실행 전에 기록되었습니다.

| 검사 | 고정 gate |
|---|---|
| affine 변위·상수 변형률·응력 patch, 두 plane | 상대오차 <=1e-10, 작은 절대 반올림 하한 |
| 강체 병진+미소 회전 | 변형률 절대값 <=1e-12 |
| 측면 traction 자유인 성분별 단축 인장 | plane별 해석적 횡변위·응력, 상대 <=1e-10 |
| 매끄러운 manufactured 변위, 두 plane | 오차 감소, 마지막 L2 차수 >=1.8 |
| 같은 manufactured 변형률·에너지 | 오차 감소, 마지막 차수 >=0.9 |
| 전역 하중·반력 평형 | 상대 불균형 <=1e-9 |
| 고정된 체적력 사각형 모멘트 평형 | 상대 scaled 불균형 <=1e-9 |
| 잘못된 재료·힘·기하·index·강체 mode | 명시적 ValueError |

Python 3.12.14, NumPy 2.3.5, SciPy 1.17.0의 초기 클라우드 결과입니다.

| Plane | n=8 L2 / n=16 L2 / n=32 L2 (m^2) | 마지막 L2 차수 | 마지막 변형률 차수 | 마지막 에너지 차수 |
|---|---|---|---|---|
| stress | 1.95006e-5 / 4.94136e-6 / 1.23990e-6 | 1.99469 | 0.99808 | 0.99817 |
| strain | 1.88764e-5 / 4.79193e-6 / 1.20324e-6 | 1.99368 | 0.99816 | 0.99820 |

2D 영역에서 적분 변위 L2 norm의 단위는 m^2이며 점별 변위가 아닙니다. 변형률 L2는 m,
에너지 norm은 sqrt(J/m)입니다. 정확도 검사이며 시간 성능 기준선이 아닙니다.
정답 시험도 조립계와 독립적으로 알려진 응력 계수와 유한차분 음의 응력 발산을 검사합니다.

## 거부 조건과 한계

solver는 유한 실수 좌표·힘, shape, 정수 연결·index, 미사용·동일 위치 절점, 중복·수치적
퇴화 삼각형, edge/vertex 비다양체 위상, 내부 중첩과 hanging node를 검사합니다.
잘못된 연결은 solver 전에 mesh 생성에서 오류가 날 수 있습니다. `Mesh`는 연결 입력을
정수로 바꾸므로 소수 인덱스를 조용히 자르는 용도로 사용하지 마십시오. solver는 호출 시
Mesh에 있는 실제 배열을 검증합니다. 위상 검사는 국소 기하 허용치 1e-12를 쓰며
삼각형 determinant가 edge 길이 척도 제곱의 1e-14 이하이면 거부합니다. 부동소수점
기하 해상도보다 작은 형상은 계약 밖입니다. 내부 중첩 검사는 두 삼각형의 무게중심
거리가 두 무게중심 반경(무게중심-꼭짓점 최대 거리) 중 큰 값의 두 배 이내일 때만 그
쌍을 살피고, 중첩하는 쌍은 모두 이 조건을 만족하므로 비용은 가장 큰 삼각형이 아니라
국소 mesh 크기 변화를 따릅니다.

분리 성분마다 x/y 병진과 면내 회전을 독립 제거해야 합니다. 처방 DOF에 제한한 이 세
강체 mode의 rank는 3이어야 합니다(무차원 rank 허용치 1e-10). 아니면 성분 번호와 함께
오류를 내며 절점 pin·spring·암묵적 정규화·최소제곱 변위를 쓰지 않습니다. 수치적으로
불분명한 거의 일직선 지지는 거부될 수 있습니다. 이 기하 검사 뒤 희소 직접 풀이와
backward 잔차 검사를 수행합니다.

**거의 비압축성인 경우:** 표준 변위 전용 P1 삼각형은 plane strain에서 nu가 0.5에
접근하면 체적 locking을 보입니다. 대수 잔차가 작아도 변위를 크게 과소평가할 수 있습니다.
nu=0.5는 거부하며 엄격한 nu<0.5 입력 검사를 통과해도 정확도를 보장하지 않습니다.
거의 비압축성 재료에는 검증된 mixed 정식화가 필요하지만 여기에는 없습니다. 보고된
수렴은 그 영역이 아닌 nu=0.3에 해당합니다. 얇고 굽힘이 지배적인 구조도 성긴 P1 mesh에서
과도하게 뻣뻣할 수 있습니다. 매우 작은 변형률과 큰 병진을 함께 쓰면 부동소수점 정확도를
잃을 수 있습니다.

비선형 구성 법칙, 대변형, 접촉, 동역학, 3D, 열팽창, 다중물리 연성, simcase·Studio
연결은 포함하지 않습니다. 소변형률·미소 회전은 모델 가정이지 자동으로 강제하는 진폭
한계가 아닙니다. 시험의 강체 회전은 유한 회전이 아닌 미소 회전장입니다.

기존 NumPy/SciPy 의존성과 직접 유도한 식만 사용하며 외부 solver 구현을 복사하지
않습니다. 예제·문서는 소스 트리에 있고 배포본에 포함되지 않습니다. 설치 검사는
checkout의 예제를 복사해 설치된 wheel로 실행합니다.
