# 2D 탄성의 직교좌표계 경계 traction

[영문 원문](../../../elasticity_traction.md)

아래 실행 수치·실패·미검증 서술은 영문 원문의 해당 후보 시점 기록이며 새 수용 결과를 뜻하지 않습니다.

기존 P1 벡터 절점 변위 공간의 `galerkin.elasticity.solve_elasticity`에 선택적 경계 traction을 추가합니다. 서브모듈을 명시적으로 import하며, 최상위 export나 simcase 통합은 추가하지 않습니다. [초기 안내서](../../../elasticity2d.md)의 정식화, plane 선택, engineering shear, 재료 범위와 locking 한계는 계속 적용됩니다. 0이 아닌 traction을 지원하지 않는다는 초기 안내서의 이전 설명은 이 문서로 대체합니다.

## API와 단위

```python
from galerkin.mesh import rectangle_mesh
from galerkin.elasticity import solve_elasticity

mesh = rectangle_mesh(1.2, .7, 12, 7)  # metres
bc = {(int(i), 0): 0. for i in mesh.boundary["left"]}
bc.update({(int(i), 1): 0. for i in mesh.boundary["bottom"]})
r = solve_elasticity(mesh, young_modulus=70000., poisson_ratio=.3,
                     plane="stress", dirichlet=bc,
                     traction={"right": (123., 0.)})
print(r.load.sum(axis=0), r.reaction.sum(axis=0))  # N/m of thickness
```

기본값 `traction=None` 또는 `{}`는 기존 zero-traction 동작을 유지합니다. 기존 `body_force`와 성분별 Dirichlet 매핑은 바뀌지 않습니다. 선택하지 않은 경계의 구속되지 않은 성분에는 가해진 traction이 0입니다. E와 nu는 균일하며 plane은 `"stress"` 또는 `"strain"`으로 명시해야 합니다.

| 물리량 | 정의 | SI 단위 |
|---|---|---|
| 좌표 / 처방 및 반환 변위 | 기존 Mesh / 절점 u | m |
| Traction | 전역 직교좌표계 벡터 t=sigma*n | Pa = N/m^2 |
| 변 적분 측도 | ds | m |
| 일관 경계 절점 하중 | integral(N_i*t)ds | 두께당 N/m |
| 체적력 | 기존 체적 밀도 b | N/m^3 |
| result.load | **체적력과 경계 하중의 합**인 `(N,2)` 절점 하중 | 두께당 N/m |
| result.reaction / residual | 원 K*u-load, 반력은 처방 DOF에만 존재 | 두께당 N/m |
| 면내 한 점에 대한 모멘트 | sum(r_x*f_y-r_y*f_x) | N = 두께당 (N*m)/m |
| 탄성 변형에너지 / 외력 일 | 두께당 값 | J/m = N |

하중·반력에 실제 두께(m)를 곱하면 총힘 N, 모멘트·에너지에 두께를 곱하면 N*m와 J를 얻습니다. 두께 1m에서는 수치가 총량과 같고, 두께 1mm에서는 0.001을 곱해야 합니다. 암시적 두께 매개변수나 절점 힘 입력은 추가하지 않습니다.

## 태그, 변, 법선과 입력 자료

`traction`은 `{tag: vector_or_callable}` 매핑입니다. 태그에는 비어 있지 않은 정수 `(E,2)` 절점 쌍 배열인 `mesh.boundary_edges[tag]`가 명시되어 있어야 합니다. `mesh.boundary` 절점 집합만으로는 traction 경계를 정의하지 못합니다. 일부만 선택하려면 원하는 메시 변을 정확히 포함하는 새 boundary_edges 태그를 정의해야 합니다. 경계 절점 번호를 단순히 순서대로 연결하면 유효하지 않은 변 선택이 생길 수 있습니다.

선택한 각 변은 정확히 한 삼각형에 속해야 합니다. 내부 변, 메시 변이 아닌 선분, 길이 0인 변, 잘못된 인덱스·shape·type, 반복된 변은 ValueError로 거절합니다. 같은 기하학적 변을 한 태그 안에서 또는 선택한 여러 태그 사이에서 두 번 선택할 수 없으며, 겹친 태그를 암시적으로 더하지 않습니다. 인접 변의 공유 꼭짓점은 허용합니다. 선택하지 않은 태그 정의는 사용하지 않습니다. 초기 API처럼 Mesh 생성자는 입력 connectivity를 정수로 변환하므로 호출자는 잘림 변환에 의존하지 않고 정수 connectivity를 공급해야 합니다. 검사는 Mesh에 실제 저장된 배열을 대상으로 합니다.

태그 변의 접선 방향은 임의입니다. 단위 법선은 **그 변을 유일하게 소유하는 삼각형에서 멀어지는** 수직 방향입니다. 외곽 경계에서는 영역 바깥, 구멍의 내부 경계에서는 구멍 안쪽을 향합니다. 태그의 절점 쌍 방향, 변 순서나 삼각형 방향을 뒤집어도 물리적 법선은 뒤집히지 않습니다. traction 적분 전에 기존 전체 기하·manifold 검사를 수행합니다.

지원하는 장의 형식은 다음과 같습니다.

- 정확히 `(2,)` shape인 유한 실수 상수 배열, 예: `(123.,0.)`. 성분은 Pa 단위의 전역 x/y traction입니다.
- callable `field(points, normals)`. 두 인자 모두 `(Q,2)`이며 points는 m 좌표, normals는 무차원 외향 단위 법선입니다. 반환값은 정확히 `(Q,2)`인 유한 실수 배열(Pa)이어야 합니다. 선택한 태그마다 그 태그의 모든 구적점에 대해 callback을 한 번 호출합니다. 기하에 의존하고 부작용이 없는 callback을 권장하며 전체 점의 정렬 순서는 공개 계약에 포함되지 않습니다.

다음과 같은 비균일 전역 직교좌표계 장을 사용할 수 있습니다.

```python
import numpy as np

def traction_xy(points, normals):
    y = points[:, 1]  # metres
    return np.column_stack([100. + 20.*y, -30. + 10.*y*y])  # Pa
```

식의 상수에는 결과가 Pa가 되도록 필요한 단위가 있어야 합니다. 스칼라는 거절합니다. **압력 API**, 스칼라 법선 하중, 국소 법선/접선 좌표 모드, follower load 또는 미지 변위에 의존하는 하중은 없습니다. 해석적 응력장은 주어진 법선으로 sigma*n을 명시적으로 반환할 수 있습니다. callable은 법선을 접선처럼 취급하거나 태그 방향으로 법선 부호를 결정해서는 안 됩니다.

## 일관 적분과 Dirichlet 중첩 정책

a에서 b로 향하는 변에 대해 q(s)=(1-s)*p_a+s*p_b, 0<=s<=1이면 다음과 같습니다.

    f_a = length * integral_0^1 ((1-s)*t(q(s),n)) ds
    f_b = length * integral_0^1 (s*t(q(s),n)) ds.

고정된 4점 Gauss-Legendre 구적법을 사용합니다. 상수 traction은 양 끝 DOF에 균등 분배합니다. 선형 traction은 비균일한 일관 가중치를 가지므로 단순 균등 분배는 잘못입니다. 직선 변에서 shape function과 차수 <=6인 다항 traction의 곱을 정확히 적분합니다. 일반적인 매끄러운 하중은 메시·구적 검증이 필요하며, 진동하거나 불연속인 하중이 자동으로 정확히 적분되지는 않습니다. callable traction에 절점 보간을 가정하지 않습니다.

**처방 변위 성분에 가해지는 하중을 허용하고 유지합니다.** 해당 DOF에 가해지는 외력으로 해석합니다. 그 성분의 변위는 여전히 처방값으로 결정하며 지지 반력은 원 시스템의 `reaction=(K*u-load)`로 계산합니다. 구속된 성분에 별도의 독립 응력 경계조건을 추가로 부과하지 않습니다. 하중을 조용히 버리거나 Dirichlet 값을 덮어쓰는 데 쓰지 않습니다. 공유 모서리 절점과 완전히 처방된 변에도 같은 정책을 적용합니다. 고정 DOF의 하중을 늘리면 반력이 바뀌며, 영향을 받는 모든 DOF가 고정되어 있으면 변위는 바뀌지 않을 수 있습니다.

`result.load`는 구속 DOF의 하중까지 포함한 체적력·경계 하중의 합입니다. `result.reaction`은 자유 DOF에서 0입니다. `result.residual`은 모든 DOF의 K*u-load를 유지하며 처방 DOF 값은 물리적 반력입니다. 힘·모멘트 평형에는 어느 한 항만이 아니라 **load plus reaction**을 사용합니다.

분리된 각 연결 성분에서 세 강체 모드를 모두 제거해야 합니다. 평형을 이루는 순수 traction만으로는 변위해가 유일하지 않으며, 처방 변위 구속이 부족하면 거절합니다. 자동 절점 고정, 약한 스프링, penalty 정칙화나 최소제곱 해를 추가하지 않습니다.

균일 선형탄성에서 하중과 처방 변위를 0부터 비례적으로 증가시키면 다음이 성립합니다.

    U = .5 * integral(epsilon:sigma) dA
      = .5 * sum(u * (load + reaction)) = W_external.

이 에너지와 일은 두께당 값입니다. 처방 변위가 0이면 지지부의 일은 0입니다. 0이 아닌 처방 변위에서 반력의 일을 무시하면 평형식이 틀립니다. 이 등식은 임의의 하중 이력이나 최종 힘과 변위의 임의 곱을 뜻하지 않으며 계수 1/2는 비례적 선형 증가를 가정합니다.

## 독립 해석해 검증

`refsol.elasticity_traction`은 FEM 엔진을 import하지 않으며 다음을 제공합니다.

- `uniaxial`: sigma=(P,0,0). 평면응력 변형률은 `(P/E,-nu*P/E,0)`, 평면변형률 변형률은 `((1-nu^2)*P/E,-nu*(1+nu)*P/E,0)`입니다.
- `shear`: 두 plane 선택 모두 sigma=(0,0,tau), u=(tau/mu*y,0)입니다.
- `polynomial_manufactured`, `polynomial_traction`: 직접 미분한 3차 변위, 2차 응력·traction, 1차 체적력입니다.
- `polynomial_resultants`: 체적력과 세 벽면의 힘·모멘트에 대한 닫힌식입니다.
- `traction_from_stress`: 직교좌표계 응력 텐서와 법선의 직접 곱입니다.

단위 정사각형 manufactured 사례는 기준 길이 L0=1m, 진폭 A=1e-3m, E=70000Pa, nu=0.3을 사용합니다. 무차원 좌표 X=x/L0, Y=y/L0에 대해 다음과 같습니다.

    u_x = A*(X^2+X*Y+X*Y^2)
    u_y = A*(.6*X^2*Y+.2*X*Y^2+.3*X^3)
    exx = A/L0*(2*X+Y+Y^2)
    eyy = A/L0*(.6*X^2+.4*X*Y)
    gamma_xy = A/L0*(X+3.2*X*Y+.2*Y^2+.9*X^2)
    sigma_xx = (lambda+2*mu)*exx + lambda*eyy
    sigma_yy = lambda*exx + (lambda+2*mu)*eyy
    sigma_xy = mu*gamma_xy
    b_x = -A/L0^2*(2*(lambda+2*mu)+2*mu*X+(lambda+mu)*(1.2*X+.4*Y))
    b_y = -A/L0^2*(mu*(1.2*Y+1.8*X)+.4*X*(lambda+2*mu)+(lambda+mu)*(1+2*Y))

참조해는 고정 영역의 m 좌표를 받으며 단위 변환 도구가 아닙니다. 명시적 A/L0와 A/L0^2 인자로 변형률은 무차원, b는 Pa/m = N/m^3가 됩니다. SI에서 L0의 수치는 1입니다. Lambda는 초기 안내서처럼 명시적으로 선택한 plane의 유효값입니다. x=0에서 두 변위 성분을 0으로 고정하고 나머지 세 벽에는 zero traction 대신 해석적 sigma*n을 가합니다. 계산된 FEM 해로 oracle를 만들지 않습니다.

왼쪽 벽 지지를 제외한 가해진 하중의 정확한 합력·모멘트는 다음과 같습니다.

    F = A*(5*(lambda+2*mu)/6, mu/15)
    M_origin = -7*A*L0*(lambda+2*mu)/12.

고정된 단위 m 영역에서 왼쪽 벽 traction 적분의 음수이며 각각 N/m와 N 단위입니다. 전체 경계 부호와 체적·변 적분을 독립적으로 검사합니다. 참조해 시험은 변위 운동학과 응력 발산의 음수를 유한차분하고, plane별 알려진 단축 해와 텐서-법선 정답과도 대조합니다.

다음 기준과 메시는 수치 결과 전에 고정했습니다.

| 검사 | 기준 |
|---|---|
| 균일 P=123Pa 단축 및 tau=87Pa 전단, 두 plane | affine 변위·변형률·응력 상대 오차 <=1e-10, 반올림 하한 적용 |
| 일관 선형·6차 변 가중치 / 합력 / 모멘트 | scale로 정규화한 오차 <=1e-12 |
| 다항 MMS, 각 방향 n=8,16,32, 두 plane | L2·변형률·에너지 오차 감소; 최종 L2 차수 >=1.8, 변형률·에너지 차수 >=0.9 |
| 총힘 / 모멘트 평형 | 상대 오차 <=1e-9 |
| 비례 외력 일과 변형에너지 | 상대 오차 <=1e-10 |
| 동차 Dirichlet Galerkin 항등식 2*(U_exact-U_h)=energy_error^2 | defect / U_exact <=1e-8 |
| 변·태그 방향, 강체 좌표 회전·이동과 크기 변환 | 상대 오차 <=1e-10 |
| 구멍 법선 방향, 고정 DOF 하중 유지, 잘못된 입력과 강체 모드 | 명시적 검사 / ValueError |

독립 내부 8x8 Duffy 구적법으로 변위 L2, 텐서 변형률 L2(engineering shear는 gamma_xy^2/2로 기여), 에너지 오차 `sqrt(integral(delta_epsilon:delta_sigma)dA)`를 측정합니다. 각 단위는 m^2, m, sqrt(J/m)입니다. U_exact는 해석적 장을 적분하며 미세 메시에서 solver를 호출해 얻지 않습니다.

| Plane | n=8 / n=16 / n=32 변위 L2 | 마지막 L2 차수 | 마지막 변형률 차수 | 마지막 에너지 차수 |
|---|---|---:|---:|---:|
| stress | 3.2716170e-5 / 8.5427956e-6 / 2.1627088e-6 | 1.98187 | 0.99567 | 0.99546 |
| strain | 3.3961009e-5 / 8.9269633e-6 / 2.2655929e-6 | 1.97828 | 0.99624 | 0.99523 |

이는 수치 정확도 결과이며 성능 기준선이 아닙니다. 기존 zero-traction 시험과 정답은 바뀌지 않았습니다. 기존 sine MMS와 새 혼합 경계 다항 사례는 서로 별개의 회귀 기준입니다.

## 재현과 한계

로컬 패키지를 설치한 환경에서 저장소 루트에서 실행합니다.

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python packages/galerkin/examples/elasticity_traction.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest -q -s packages/galerkin/tests/test_elasticity_traction.py packages/galerkin-refsol/tests/test_elasticity_traction_reference.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest -q
```

근접 비압축성 평면변형률 P1 locking, 거친 메시의 굽힘 강성, 소변형 가정과 부동소수점 메시 한계는 그대로입니다. 작은 대수 잔차 통과만으로 nu=0.5 근처의 정확도가 보증되지는 않습니다. 압력 모델, 열팽창, 비선형 재료, 대변형, 접촉, 동적, 3D, simcase나 Studio 기능을 추가하지 않습니다. 의존성을 추가하거나 외부 solver 구현을 복사하지 않습니다. 안내서·예제는 source-tree 자산이며 sdist 포함은 공용 패키징 통합 담당 범위입니다.
