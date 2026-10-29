# JAX·PyTorch로 미분하기

[English original](../../../../../packages/galerkin/differentiation.md)

[galerkin 개요](overview.md)

정상 열전도(`galerkin.thermal.solve_steady_heat`), 정상 전기 전도
(`galerkin.electric.solve_steady_electric`), 과도 열전도
(`galerkin.transient_heat.solve_transient_heat`), 탄성(`galerkin.elasticity.solve_elasticity`),
열탄성(`galerkin.thermoelasticity.solve_thermoelasticity`), 도파관 모드
(`galerkin.waveguide.solve_modes`), PEC 상자 공진기(`galerkin.cavity.solve_cavity_box`)는
NumPy 숫자 대신 JAX나
PyTorch 값을 받습니다. 그러면 결과 배열도 그 라이브러리의 배열이 되고, 그 입력에 대한 미분이
풀이를 거쳐 흐릅니다. 기본값은 여전히 NumPy이며 계산은 이전과 똑같습니다.
NumPy는 미분하지 않습니다.

배열 라이브러리는 해당 extra로 설치합니다: `pip install "galerkin[jax]"` 또는
`pip install "galerkin[torch]"`. JAX는 배정밀도로 돌려야 합니다
(`jax.config.update("jax_enable_x64", True)`). 단정밀도는 거부합니다.

## 살아 있는 값으로 줄 수 있는 입력

| Solver | JAX·PyTorch 값으로 줄 수 있는 입력 |
|---|---|
| `solve_steady_heat` | `conductivity`(스칼라 또는 `{영역 이름: 값}`); `heat_source`(스칼라, 영역표, 또는 살아 있는 값을 돌려주는 콜백); `dirichlet` 온도; `outward_flux`와 각 `convection` 쌍의 두 값(스칼라 또는 살아 있는 값을 돌려주는 콜백) |
| `solve_steady_electric` | `conductivity`(스칼라 또는 영역표); `dirichlet`와 `reference_potential` 전위(V); `outward_current`(스칼라 또는 살아 있는 값을 돌려주는 콜백) |
| `solve_transient_heat` | `conductivity`와 `volumetric_heat_capacity`(스칼라 또는 영역표); `heat_source`(스칼라, 영역표, 또는 살아 있는 값을 돌려주는 콜백 `(points, time)`); `dirichlet` 온도(스칼라 또는 살아 있는 값을 돌려주는 콜백 `(time)`); `initial_temperature_k` |
| `solve_elasticity` | `young_modulus`와 `poisson_ratio`(스칼라 또는 영역표); `dirichlet` 변위; `body_force`와 `traction`(상수 벡터 또는 살아 있는 값을 돌려주는 콜백) |
| `solve_thermoelasticity` | `solve_elasticity`와 같고, `reference_temperature_k`와 `thermal_expansion_per_k`(스칼라 또는 영역표)를 더함; 온도 스냅숏은 NumPy 기록으로 남음 |
| `solve_modes` | `eps_r`와 `mu_r`(스칼라 또는 요소별 배열, 실수·복소수)와 `k0`; `n_eff`, `et`, `ez`를 그 라이브러리로 돌려줌. `n_target`은 모드를 고르기만 하므로 미분이 없음; `coordinate_factors`는 NumPy여야 함 |
| `solve_cavity_box` | `lengths_m`(세 값의 배열, 또는 숫자와 살아 있는 값을 섞은 시퀀스); 주파수, 고유값, 모서리 계수, 중심 필드는 미분과 함께, 잔차(NumPy 풀이의 진단값)는 미분 없이 그 라이브러리로 돌려줌. `target_frequency_hz`는 모드를 고르기만 함 |

시간 격자 `time_s`는 메시처럼 고정된 구조입니다. 과도 해석의 콜백은 실행 내내 한
라이브러리의 값을 돌려줘야 합니다. 첫 시각에 NumPy 숫자를 돌려주고 나중에 살아 있는
값을 돌려주는 콜백은 거부합니다.

메시 좌표, 연결, 경계 태그, 영역 번호는 고정된 구조입니다. 노드 위치에 대한
미분은 제공하지 않습니다. `ElementHeatSource`와 `ElementConductivity`는 NumPy
값을 담습니다. 콜백은 NumPy 좌표와 법선을 받고, 살아 있는 값을 돌려줄 수
있습니다. 좌표를 식에 쓸 때는 같은 라이브러리로 올리십시오(PyTorch는 텐서와
NumPy 배열을 섞어 계산하지 않습니다).

살아 있는 입력은 모두 한 라이브러리에서 와야 합니다. NumPy 상수는 함께 써도 됩니다.

## 예제

```python
import jax
import jax.numpy as jnp
from galerkin.mesh import rectangle_mesh
from galerkin.thermal import solve_steady_heat

jax.config.update("jax_enable_x64", True)
mesh = rectangle_mesh(1.0, 0.5, 6, 4)
left = [int(i) for i in mesh.boundary["left"]]
right = jnp.asarray(mesh.boundary["right"])


def right_temperature(k, h):
    result = solve_steady_heat(mesh, conductivity=k, dirichlet={i: 350.0 for i in left},
                               convection={"right": (h, 300.0)})
    return result.temperature[right].mean()


dk, dh = jax.grad(right_temperature, argnums=(0, 1))(2.0, 5.0)
# One-dimensional slab, exact for P1: T(L) = 300 + 50 / (h (L/k + 1/h)).
# With L = 1 and R = L/k + 1/h = 0.7:
# dk = 50 L / (k^2 h R^2) = 5.1020, dh = -50 L / (k (h R)^2) = -2.0408,
# in K per W/(m K) and K per W/(m^2 K).
```

같은 함수를 `torch.tensor(..., dtype=torch.float64, requires_grad=True)` 입력으로
쓰면 `.backward()`로 같은 기울기를 얻습니다.

## 미분을 계산하는 방법

정상 열·전기·탄성·열탄성 solver는 연립방정식을 입력의 라이브러리에서 한 번 만들고,
NumPy 입력이든 살아 있는 입력이든 `galerkin.core.solve`로 한 번 풉니다. 과도 열은 매 단계를
먼저 숫자로 풀어 NumPy 실행처럼 보정·검사하고, 풀이 한 번으로 그 해 x0에 미분을 붙입니다:
x = x0 + A⁻¹(b − A x0). 값은 x0와 반올림 수준으로 같습니다. 콜백은 한 번만 부릅니다. 도파관
모드는 고유쌍으로 같은 일을 합니다(다음 절).

조립은 `galerkin.core.kernels`와 `galerkin.core.forms`의 닫힌 식 요소 커널로,
입력의 라이브러리에서 이루어집니다. 희소 연립방정식은 여전히 SciPy 희소 LU로
풉니다. 그 미분은 adjoint(`galerkin.core.solve`)로 공급합니다. 입력이 몇 개든
전치 행렬로 한 번 더 풉니다. JAX는 `jax.custom_vjp`, PyTorch는
`autograd.Function`을 씁니다.

입력 검사, 잔차 허용치, 열·전류·전력 수지 검사는 숫자의 사본으로 돌며, 기준은
NumPy 입력과 같습니다.

## 과도 열: 메모리와 checkpoint

역방향 미분에는 모든 단계의 중간값이 필요합니다. 기본으로는 JAX·PyTorch가 기록하는 대로
전부 보관합니다. 가장 빠르지만 메모리를 가장 많이 씁니다.
`solve_transient_heat(..., checkpoint_every=m)`을 주면 m단계마다의 상태만 보관하고, 그
사이 단계는 역방향 때 `jax.checkpoint`나 `torch.utils.checkpoint`로 다시 계산합니다. 값과
미분은 바뀌지 않고, NumPy 입력에서는 무시되며, 콜백을 다시 부르지 않습니다(값을 보관함).

각 단계는 먼저 NumPy 숫자로 풀고 NumPy 입력과 똑같이 개선·검사합니다. 그 해 x0에
adjoint 보정 x = x0 + A⁻¹(b − A x0)을 붙입니다. 값은 x0와 반올림 수준으로 같고 미분은
정확합니다.

마지막 평균 온도의 미분을 구할 때, 유휴 프로세스 대비 최대 상주 메모리입니다
(`tests/galerkin/test_transient_gradients.py`의 설정을 더 큰 메시로; 2026-10-27, Linux,
JAX 0.12.0.1, PyTorch 2.14.1 CPU). 결과 이력 자체는 O(Nt (N + M))이며 첫 행입니다.

| 경우 | 절점 861, 400단계 | 절점 3321, 200단계 |
|---|---|---|
| 결과 이력(계산한 크기) | 23 MiB | 45 MiB |
| NumPy 실행 | 48 MiB | 99 MiB |
| JAX 미분, 전 단계 보관 | 590 MiB | 786 MiB |
| JAX 미분, `checkpoint_every=20` | 333 MiB | 453 MiB |
| PyTorch 미분, 전 단계 보관 | 363 MiB | 700 MiB |
| PyTorch 미분, `checkpoint_every=20` | 202 MiB | 302 MiB |

한 기계에서 한 번 잰 값이며 한도가 아닙니다. 두 방식 모두 최대 메모리는 단계 수에
비례해 늘어나고, checkpoint는 그 기울기를 낮춥니다.

## 도파관 모드: 고유값, 필드, 축퇴 모드

`solve_modes`는 입력의 숫자로 NumPy 고유값 풀이를 돌립니다. 돌려받은 각 쌍 (λ0, x0)
(λ0 = −(k0 n_eff)², x0 = 자유 자유도 위의 [et β, ez])은 정규화 xᵀ B x = 1을 덧붙인
고유값 문제 A x = λ B x에서 Newton 한 걸음을 밟습니다. 이 연립방정식은 살아 있는 A와
B로 풉니다:

    [x; λ] = [x0; λ0] − J⁻¹ F,   J = [[A − λ0 B, −B x0], [−x0ᵀ B, 0]],
    F = [(A − λ0 B) x0, ½ (1 − x0ᵀ B x0)].

값은 반올림 수준에서 NumPy 풀이와 같고, 미분은 정확한 음함수 미분입니다. 실수 문제와
손실(복소) 문제 모두 같습니다.

필드에는 게이지가 있습니다. 고유벡터는 복소 상수배까지만 정해집니다. solver는 2-노름이
1이고 가장 큰 성분이 양의 실수인 x를 돌려줍니다. 살아 있는 계산은 x에 같은 규칙을 다시
적용하므로 `et`, `ez`와 그 미분은 이 게이지를 따릅니다. 가장 큰 성분이 여럿이면(대칭
모드) NumPy 풀이가 위상 0으로 남긴 성분을 씁니다. 겹침의 크기나 |E_z|²/|E_t|² 비율처럼
게이지에 무관한 양은 미분도 게이지에 무관합니다. 목적함수에는 그런 양을 쓰는 편이
좋습니다.

축퇴 고유값에는 미분이 없습니다. 고유벡터가 그 쌍의 어떤 결합이든 될 수 있기 때문입니다.
돌려준 고유값이 이산 문제의 다른 고유값과 상대 1e-8 이내이면
(`galerkin.waveguide.DEGENERATE_GAP`) 그 모드는 정확한 값과 `DegenerateModeWarning`, NaN
미분을 받습니다. 다른 고유값을 돌려줬는지와 상관없습니다(`num_modes`가 쌍을 자를 수
있습니다). 가장 가까운 다른 고유값은 작은 문제에서는 밀집 행렬로, 그 밖에는 모드마다
shift-invert Arnoldi로 찾으며, 모드마다 분해를 한 번 더 합니다. 그래서 그 모드를 쓰는
역방향 계산은 틀린 숫자 대신 NaN을 냅니다. 목적함수가 쓰지 않는 출력은 아무것도 더하지
않으므로 다른 모드는 미분을 유지합니다. 대칭을 깨거나, 축퇴 부분공간 전체의 양을
쓰십시오.

`solve_material_cavity_box`와 `solve_modes`, `solve_cavity_box`를 뺀 전자기 solver는 아직
미분하지 않습니다.

## 상자 공진기: 길이에 대한 미분

빈 상자에는 바꿀 재료가 없고 입력은 세 길이뿐입니다. 벽을 움직이면 모든 노드가 움직이므로,
일반적으로는 노드 위치에 대한 미분이 필요합니다. 상자 메시는 축 방향으로만 늘어납니다
(x_a → d_a x_a, d_a = L_a / L_a0). 모서리 함수는 이 사상에서 공변으로 변환되므로
curl-curl 행렬과 질량 행렬은 정확히

    K = Σ_a d_a² / (d_x d_y d_z) K_a,   M = (d_x d_y d_z) Σ_a M_a / d_a²

입니다. K_a, M_a는 푼 메시의 성분별 행렬입니다(`galerkin.core.kernels.nedelec3d_components`).
각 모드는 이 살아 있는 K, M으로 도파관과 같은 확장 Newton 한 걸음을 밟습니다. solver의
정규화 xᵀ M x = 1을 이 걸음이 그대로 지키고, 부호 규칙(가장 큰 계수가 양수)은 작은
걸음에서 바뀌지 않으므로, 필드 미분은 따로 게이지를 다시 적용하지 않아도 돌려준 규칙을
따릅니다. 중심 필드는 푼 메시에서 계산하고 성분마다 d_a로 나눕니다.

상자에는 축퇴 모드가 많습니다(두 변의 길이가 같으면 쌍이 생깁니다). 도파관과 같은 규칙을
따릅니다. NaN 미분과 `DegenerateModeWarning`이며, `num_modes`가 쌍을 잘라도 마찬가지입니다.
`result.mesh`와 `result.space`는 푼 기하의 숫자를 담고, 노드 좌표에는 미분이 없습니다.

## 근사하지 않고 거부하는 것

- 이 solver를 감싼 `jax.jit`: 검사에 구체적인 숫자가 필요합니다
  (`galerkin.core.backend.TracedValueError`). `jit` 없이 `jax.grad`와 PyTorch
  autograd는 동작합니다.
- `solve_modes`에 JAX·PyTorch `coordinate_factors`(`TypeError`): PML 늘림이나 굽힘
  좌표에 대한 미분은 제공하지 않습니다.
- forward 모드 미분(`jax.jvp`, `jax.jacfwd`)과 2차 미분.
- `jax_enable_x64`가 꺼진 JAX, 그리고 한 호출에 섞인 JAX와 PyTorch 값.
- 아직 미분하지 않는 solver는 미분을 조용히 끊지 않고 JAX·PyTorch 값을
  `TypeError`로 거부합니다. NumPy 컨테이너인 `ElementHeatSource`, `ElementConductivity`,
  `freeze_temperature`의 `TemperatureSnapshot`, Joule 결합과 열→역학 workflow(열 단계의
  `WorkflowStageError`로 알림), 그리고 살아 있는 열 이력을 받은
  과도 역학(`TransientThermoelasticError`)이 거부합니다. JSON 문서와 명령행은
  NumPy로 돕니다.

## 한계

- 아직 막지 않은 곳: `solve_modes`, `solve_cavity_box`를 뺀 전자기 solver는 입력을 NumPy로
  바꿉니다. 여기에 넘긴 JAX 값은 미분을 잃으므로, 살아 있는 값을 넘기지 마십시오. 낮은 수준
  조립 함수(`galerkin.assembly`, `assembly3d`, `edge`, `edge3d`)는 살아 있는 값을 `TypeError`로
  거부합니다. 값을 살려 두려면 `galerkin.core.kernels`를 `galerkin.core.forms`로 조립하십시오.
- JAX에서 특이한 희소 연립방정식은 풀이의 host callback 안에서 실패합니다. solver가
  `ValueError`를 내기 전에 JAX가 callback의 traceback(`jax.pure_callback failed`)을
  기록합니다. PyTorch는 아무것도 출력하지 않습니다.
- 살아 있는 입력에서는 `joule_power_per_length`와 `supplied_power_per_length`가
  Python float 대신 그 라이브러리의 0차원 배열이며, 결과 배열을 읽기 전용으로
  만들지 않습니다.
- CPU에서만 시험했습니다. 정적 데이터는 CPU 텐서로 올리며, 다른 PyTorch 장치의
  텐서는 지원하지 않습니다.

## 검증

`tests/galerkin/test_steady_gradients.py` (2026-10-26, Linux, NumPy 2.5, JAX 0.12.0.1,
PyTorch 2.14.1 CPU):

- JAX와 PyTorch의 모든 결과 필드가 NumPy 풀이와 상대 1e-12로 맞습니다.
- P1이 정확한 경우의 닫힌 식: Dirichlet–대류 슬래브 오른쪽 온도의 k, h, 두 온도에
  대한 미분과, 직렬 두 도체 Joule 전력의 두 전도도와 두 전압에 대한 미분이 상대
  1e-10으로 맞습니다.
- 살아 있는 입력의 종류마다 NumPy 풀이의 중심차분과 맞습니다. 영역표, 열원·경계
  콜백, 그리고 살아 있는 기준 전위를 쓰는 전류 구동 성분을 포함합니다.

`tests/galerkin/test_transient_gradients.py`(같은 날짜와 버전):

- JAX와 PyTorch의 모든 이력이 NumPy 실행과 상대 1e-12로 맞습니다.
- 단열 물체에 균일한 초기 온도와 열원을 주면 backward Euler가 T0 + Q t / c를 정확히
  재현합니다. 마지막 온도와 그 k, c, Q, T0 미분이 1e-10으로 맞습니다.
- k, c, Q, Dirichlet ramp, 초기 온도장, 그리고 k·c·Q 영역표의 미분이 NumPy 실행의
  중심차분과 맞습니다.
- 4단계에서 `checkpoint_every` 1과 3이 전 단계 보관과 같은 값(1e-14)과 기울기(1e-12)를
  냅니다.

`tests/galerkin/test_mechanics_gradients.py`(같은 날짜와 버전):

- 탄성과 열탄성의 모든 필드가 JAX와 PyTorch에서 NumPy와 1e-12로 맞습니다. 스칼라·영역
  재료, 평면변형률·평면응력 모두입니다.
- P1이 정확히 재현하는 닫힌 식과 1e-10으로 맞습니다. 끝단 견인력을 받는 평면응력 막대
  (u = sigma L / E, 옆 방향 -nu sigma H / E)의 E, nu, sigma 미분과, 자유 열팽창
  (u = alpha (T - Tref) L)의 Tref, alpha, E 미분입니다.
- E, nu, Dirichlet 변위, 체적력·견인력 콜백과 상수, 영역표, 그리고 열탄성의 Tref와
  alpha 미분이 중심차분과 맞습니다.

`tests/galerkin/test_mode_gradients.py`(2026-10-27, Linux, NumPy 2.5, JAX 0.12.0.1,
PyTorch 2.14.1 CPU):

- JAX와 PyTorch의 `n_eff`, `et`, `ez`가 NumPy와 1e-12로 맞습니다. 실수 도파관, 손실
  코어, 복소 좌표 인자(늘린 4분의 1 영역과 굽힘 같은 h) 모두입니다.
- 균일하게 채운 PEC 도파관에서는 이산화가 (k0 n_eff)² = k0² ε μ − kc²를 지키고 kc는
  메시로만 정해집니다(1e-11로 확인). 세 모드의 ε, μ, k0 미분이 μ/(2 n_eff),
  ε/(2 n_eff), kc²/(k0³ n_eff)와 1e-9로 맞습니다.
- n_eff(실수부·허수부), 게이지에 무관한 비율 |ez|²/|et|², 돌려준 게이지의 `ez` 성분
  하나가 코어·클래딩 굴절률, μ, k0, 코어 손실에 대해 NumPy 풀이의 중심차분과 맞습니다.
  요소별 ε·μ 배열은 방향 차분과 비교합니다.
- 정사각형 대칭을 가진 메시 위 정사각 도파관: 축퇴한 기본 모드 쌍은 경고와 NaN 미분을
  내고, 같은 호출의 축퇴하지 않은 모드는 중심차분과 맞습니다. 쌍의 한쪽만 돌려주는
  `num_modes=1`에서도 그 모드는 경고와 NaN을 냅니다.

`tests/galerkin/test_cavity_gradients.py`(같은 날짜와 버전):

- JAX와 PyTorch의 주파수, 고유값, 모서리 계수, 중심 필드, 잔차가 NumPy와 1e-12로 맞습니다.
  밀집(자유 모서리 43개)과 반복(291개) 고유값 풀이 경로 모두입니다.
- 이산화가 정확히 지키는 항등식 Σ_a L_a ∂λ/∂L_a = −2λ(주파수는 −f)가 네 모드에서
  1e-12로 맞습니다.
- 고유값, 주파수, 모서리 계수, 필드 양의 세 길이에 대한 미분이 두 경로 모두에서 NumPy
  풀이의 중심차분과 맞습니다. 숫자 둘 옆에 살아 있는 길이 하나를 준 경우도 맞습니다.
- 단면이 정사각형인 상자: 축퇴 쌍은 경고와 NaN을 내고, 단순한 기본 모드는 중심차분과
  맞으며, `num_modes=1`로 잘린 쌍도 경고와 NaN을 냅니다.

adjoint 풀이 자체는 `tests/galerkin/test_core_solve.py`에서 각 라이브러리가 밀집
`linalg.solve`를 자동미분한 값과, 중심차분과 비교합니다.
