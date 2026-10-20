# 처방 온도 열탄성과 전체 기계 traction

[English](../../../thermoelastic_traction.md)

이 기능은 적합한 평면 P1 삼각형 메시에서 명시적으로 동결한 절점 Kelvin 장과
일정한 등방성 3D 재료를 사용하는 선형 정적 기계 해석입니다. 열 솔버를 실행하거나
온도의 출처를 인증하지 않습니다. `plane="stress"`와 `plane="strain"` 중 하나를
명시적으로 선택해야 합니다.

## API와 실행 예제

```python
from galerkin.thermoelasticity import freeze_temperature, solve_thermoelasticity
snapshot = freeze_temperature(mesh, temperature_k)
result = solve_thermoelasticity(
    mesh, snapshot, reference_temperature_k=293.15,
    thermal_expansion_per_k=12e-6, young_modulus=70e9,
    poisson_ratio=.3, plane="strain", dirichlet=constraints,
    body_force=(0., 0.), traction={"right": (8e6, 3e6)})
```

`dirichlet`는 `(node_id, component)`를 m 단위 변위로 매핑합니다. component 0/1은
Cartesian x/y입니다. `body_force`는 유한 실수 상수 `(2,)` N/m³ 또는 순수
`callback(points_m)->(Q,2)` N/m³입니다. `traction`은 `None`, `{}`, 또는
`mesh.boundary_edges` 태그를 전역 Cartesian 유한 실수 `(2,)` Pa 벡터나 순수
`callback(points_m, outward_normals)->(Q,2)` Pa로 매핑합니다. 좌표와 단위 법선의
shape는 `(Q,2)`입니다. 스칼라 pressure 전용 키워드·로컬 법선/접선 프레임 API·follower 형상 하중은 없습니다.
그러나 고정 기준 경계에서 Pa 단위 스칼라 p에 대해
`lambda points_m, normals: -p * normals` 같은 전역 Cartesian Pa callback은 유효합니다.
벡터 `(8e6,3e6)`는 에지 각도와 관계없이 x/y 성분입니다.
Callback은 결정적이어야 하며 메시/snapshot/입력을 변경하면 안 됩니다.
평가 순서와 batch 분할은 공개 계약이 아닙니다. 동시 입력 변경은 지원하지 않습니다.
Callback 예외는 전파되며 잘못된 값은 `ValueError`입니다. 실패 뒤 부분 성공 결과를
반환하지 않습니다.

패키지를 사용할 수 있는 checkout 루트에서 실행합니다.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python packages/galerkin/examples/thermoelastic_traction.py
python -m pytest -q tests/galerkin/test_thermoelastic_traction.py tests/refsol/test_thermoelastic_traction_reference.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python -m pytest -q -s tests/galerkin/test_thermoelastic_traction_convergence.py
```

예제는 균일 313.15 K, Tref293.15 K, 1m 정사각형, E70GPa, nu.3,
alpha12e-6/K, 목표 응력 `[[8e6,3e6],[3e6,-2e6]]` Pa와 0이 아닌 강체 병진
`(2e-5,-1e-5)` m를 설정합니다. 왼쪽 변위를 지정하고 나머지 세 에지에 전체 물리
응력 traction을 가합니다. 변위 오차, 외력/지지 반력의 개별 합력, 지지 일, 물리 U와
zz를 출력합니다. 처방 온도 기계 예제이며 열 workflow가 아닙니다.

## 전체 traction, 부호와 단위

 a=alpha*(T-Tref), e=(exx,eyy,gamma_xy), gamma_xy=2exy, m=(1,1,0)라 두면
원래 3D 법칙은 다음과 같습니다.

```text
mu = E/[2(1+nu)]
lambda = E*nu/[(1+nu)(1-2nu)]
sigma = 2*mu*(epsilon-a*I) + lambda*tr(epsilon-a*I)*I
-div(sigma) = body_force
sigma*n = traction
K*u = load_body + load_traction + load_thermal
load_external = load_body + load_traction
load_total = load_external + load_thermal
residual = K*u - load_external - load_thermal
```

Traction은 **전체 물리 sigma*n**입니다. 이미 전체인 traction에 열 q*n을 더하거나
빼지 않습니다. 양의 열 등가 RHS `g=integral B.T*q*m`은 유지됩니다.
PS의 q=E*a/(1-nu), PE의 q=E*a/(1-2nu)입니다. 일정 T는 gradient가 0이지만
일반적으로 g는 0이 아닙니다. 열 효과를 grad(T)에 비례하는 body 항으로만 처리하면
경계 물리를 잃습니다.

| 물리량 | 단위 / 위치 |
|---|---|
| 좌표, 변위 | m / 절점 |
| T, Tref; alpha | K / 절점 P1; K; 1/K |
| E, 응력, traction | Pa=N/m² |
| body force | N/m³ |
| body/traction/thermal load, residual, reaction | 두께당 N/m / 절점 `(N,2)` |
| 두께당 기계 모멘트 | N |
| 물리 탄성 에너지, 끝점 일 | J/m |

m 단위 실제 두께 h를 곱하면 힘은 N, 에너지는 J입니다. 열률 W/m는 다른 물리량이며
기계 N/m에 더할 수 없습니다. 단위를 추론하지 않습니다. 해석 전에 형상/변위/재료/하중을
SI로 변환하세요. T와 Tref는 유한한 음이 아닌 절대 K입니다. 냉각은 허용하며 alpha는
부호가 있거나 0일 수 있습니다. E>0과 -1<nu<.5가 필요합니다.
거의 비압축성인 plane-strain P1 locking은 여전히 한계입니다.

## 선택 에지 검증과 구속 성분 중첩

선택 태그는 존재해야 하며 비어 있지 않은 정수 `(E,2)` 범위 내 끝점 인덱스를 가져야
합니다. 순서를 무시한 각 에지는 길이가 0이 아닌 삼각형 외곽 에지이며 owner가 정확히
하나여야 합니다. 선택 태그 내부/사이 중복, 내부/존재하지 않는 에지, 퇴화 끝점,
잘못된 인덱스를 거절합니다. 모서리를 공유하는 서로 다른 에지는 각각 한 번 더합니다.
선택하지 않은 태그를 전역적으로 중복 제거하지 않습니다. 경계 절점 태그만으로 선하중
에지를 정의할 수 없습니다. 전체 선택 에지 검증을 traction callback보다 먼저 수행합니다.
메시는 적합하고 겹치지 않는 manifold여야 합니다. 임의 CAD 형상을 복구하지 않습니다.

법선은 유일한 owner 삼각형 바깥을 향하며 끝점 순서와 무관합니다. 내부 구멍 법선은
빈 공간을 향합니다. 도메인 중심을 기준으로 정하면 잘못됩니다. 4점 Gauss 에지 구적은
끝점 lumping이 아닌 일관 P1 하중을 만듭니다. 길이 L에서 선형 끝점 traction t0,t1은
다음과 같습니다.

```text
f0 = L*(2*t0+t1)/6
f1 = L*(t0+2*t1)/6
```

지정 변위 성분의 하중도 포함됩니다. Dirichlet는 변위를 고정하지만 적용 traction을
지우지 않습니다. Reaction은 원래 소거 전 계의 고정 DOF residual이며 자유 DOF에서는
0입니다. 모서리가 공유되므로 태그별 지지 반력은 유일하게 정의되지 않습니다.
평형을 만족하는 순수 Neumann 하중도 각 연결 성분에서 충분한 강체 구속이 필요합니다.

## 결과, 기존 생성 방식과 snapshot

기존 `ThermoelasticResult`의 위치 인자 18개는 순서와 의미를 유지합니다.
displacement, total_strain, thermal_strain, elastic_strain, stress,
sigma_zz, epsilon_zz, load_external, load_thermal, reaction, residual,
physical_elastic_energy, temperature_snapshot, reference_temperature_k,
thermal_expansion_per_k, young_modulus, poisson_ratio, plane입니다.
끝에 `load_body=None`, `load_traction=None` 두 필드가 추가됩니다. 정상 솔버 결과는
둘 다 `(N,2)` 배열로 채웁니다. 기존 18인자로 직접 생성한 결과는 새 필드가 `None`일 수
있으므로 소비자는 이를 허용해야 합니다. `load_total`은 계산된 합으로 유지됩니다.
`traction=None/{}`는 이전 수치 결과를 유지합니다.

변위는 절점 값이며 total_strain은 요소별 상수입니다. thermal_strain,
elastic_strain, stress, sigma_zz, epsilon_zz는 중심점 표본입니다. 응력 벡터 순서는
`(sxx,syy,sxy)`, 변형률 벡터 순서는 `(exx,eyy,gamma_xy)`입니다. P1 T에서는 셀 내부
물리 응력이 선형입니다. 적분할 때 상수 변형률과 보간 T로 복원해야 합니다. 중심 응력을
셀 전체 상수 응력으로 취급하면 안 됩니다. 물리 에너지는 온도의 이차 항을 적분합니다.

PS는 sigma_zz=0에서 ezz를 소거합니다. PE의 전체 ezz=0이며
sigma_zz=lambda*(exx+eyy)-q입니다. 균일 S=0인 자유 면내 팽창에서 PE의 두 수직
변형률은 (1+nu)*a, sigma_zz=-E*a, 에너지 밀도 .5*E*a²입니다. PS의 변형률은 a이며
응력/에너지는 0입니다. 평면 환원에서도 3D 물리를 버리지 않습니다.

Snapshot은 SI 형상, 연결/순서와 절점 T를 불변 복사합니다. 원래 입력 배열을 바꿔도
snapshot은 변하지 않습니다. 내용이 동일한 다른 메시 객체를 사용할 수 있지만 오래된
스케일/좌표/절점·셀 순서/온도 metadata는 fingerprint와 정확한 배열 비교로 거절합니다.
경계 태그는 snapshot hash로 **인증되지 않습니다**. 매 해석마다 현재 선택 에지를
별도로 검증합니다. Fingerprint는 식별자이며 서명이나 열 솔버 출처 증명이 아닙니다.
결과와 하중 배열은 변경 가능하며 반환 후 무결성을 보장하지 않습니다.

## 물리 끝점 에너지와 지지 일

고정 온도에서 C_T를 면내 변형률 0인 물리 에너지라 합니다.
F=load_external, g=load_thermal, r=reaction이면 다음과 같습니다.

```text
uKu = u·(F+g+r)
U = .5*uKu - u·g + C_T
integral sigma:epsilon_inplane = u·F + u_D·r
2U = u·F + u_D·r - u·g + 2*C_T
```

물리 U는 전체 3D 탄성 변형률을 사용합니다. .5*uKu와 .5*u·F는 물리 열탄성 에너지가
아닙니다. 0이 아닌 지지 변위에서는 일반적으로 지지 일 u_D·r을 생략할 수 없습니다.
이전 연속체 진단의 왼쪽 전단과 ux가 0인 경우는 uy가 0이 아니어도 지지 일이 정확히
0이었습니다. 유효한 상쇄를 대조로 보존합니다. 고정 병진을 더하면 변형률, 응력, body,
traction이나 gate를 바꾸지 않고 생략된 지지 일을 검출할 수 있습니다.
이는 고정 온도의 끝점 항등식이며 가열 경로의 일이나 전체 열역학 에너지 보존 주장이
아닙니다. 물리 힘/모멘트 평형은 F+r을 사용합니다. g는 별도로 합력/모멘트가 0이며
또 다른 물리 외력이 아닙니다.

## 해석 정답과 고정 검증 기준

`refsol.thermoelastic_traction`은 NumPy와 표준 라이브러리만 import하며 engine이나
기존 reference helper를 import하지 않습니다. `uniform_combined`,
`polynomial_manufactured`, `parent_state`, `traction_from_stress`를 제공합니다.
단위 정사각형 다항식은 c=1e-4와 다음 병진 장을 사용합니다.

```text
u = c*(x^3+2*x*y^2+x*y, 2*x^2*y+y^3+x^2) + (2e-5,-1e-5) m
T-Tref = 12+9*x-4*y+6*x*y+3*y^2 K
linear control: T-Tref = 12+9*x-4*y K
```

정확한 body는 전체 물리 응력을 미분하며 오른쪽/위/아래에 정확한 전체 sigma*n을,
왼쪽 두 성분에 정확한 u를 지정합니다. 이차 해석 T를 절점에 표본화하므로 T 보간 오차는
기계 일관성 연구의 일부이며 열 FEM 오차가 아닙니다. 선형 대조의 T는 P1에서 정확합니다.
Affine fitting이나 변형률 재스케일을 하지 않습니다.

양 plane에서 n8/16/32/64를 고정합니다. **마지막 두** 인접 구간 각각에서 u L2 차수>=1.8,
전체 gradient, 변형률 텐서, zz를 포함한 full3D 응력과 tangent-energy norm 차수>=.9가
필요합니다. 이차 T의 L2/H1 차수는 >=1.8/.9입니다. 특성 스케일은 c*L,
max(c,alpha*20), E*strain, stress*L, stress*L², E*strain²*L²이며 상쇄되는 순하중이나
Tref로 정규화하지 않습니다. Norm 구적8/10은 측정된 0이 아닌 오차의1% 이내로 일치하고
정확한 기준 에너지 구적12/16 차이는 특성 에너지의1e-8 이하입니다. 물리 에너지 오차는
매 세분화에서 감소하며 최종<=.02입니다. 균일 장, 독립 하중/일/에너지/복원 정규화 오차
<=1e-10, 자유 residual과 힘/모멘트<=1e-9입니다. 선형 일관 에지와 회전한 ring/구멍/순서
검사는 정확성 gate를 유지합니다. 실제 helper mutation이 열 경계 traction을 더하거나
빼고 g를 생략/역전하면 물리 patch assertion이 실패해야 합니다. Reference 미분 검사와
invalid/callback/중복/stale 대조는 수렴과 별개입니다. 카운트나 연속체 진단만으로 설치본,
전체 회귀, 독립 수용 또는 플랫폼 지원을 입증하지 않습니다.

열/workflow 확장, pressure 전용·로컬 프레임·follower API, traction 저장,
schema/CLI/Studio, feedback, transient,
비선형, 큰 변형, 일반 3D 또는 locking 개선은 추가하지 않습니다.
Windows와 release 통합에는 각각 실제 근거가 필요합니다.
