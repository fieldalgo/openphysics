# JAX·PyTorch로 미분하기

[English original](../../../../../packages/galerkin/differentiation.md)

[galerkin 개요](overview.md)

정상 열전도(`galerkin.thermal.solve_steady_heat`)와 정상 전기 전도
(`galerkin.electric.solve_steady_electric`)는 NumPy 숫자 대신 JAX나 PyTorch 값을
받습니다. 그러면 결과 배열도 그 라이브러리의 배열이 되고, 그 입력에 대한 미분이
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

조립은 `galerkin.core.kernels`와 `galerkin.core.forms`의 닫힌 식 요소 커널로,
입력의 라이브러리에서 이루어집니다. 희소 연립방정식은 여전히 SciPy 희소 LU로
풉니다. 그 미분은 adjoint(`galerkin.core.solve`)로 공급합니다. 입력이 몇 개든
전치 행렬로 한 번 더 풉니다. JAX는 `jax.custom_vjp`, PyTorch는
`autograd.Function`을 씁니다.

입력 검사, 잔차 허용치, 열·전류·전력 수지 검사는 숫자의 사본으로 돌며, 기준은
NumPy 입력과 같습니다.

## 근사하지 않고 거부하는 것

- 이 solver를 감싼 `jax.jit`: 검사에 구체적인 숫자가 필요합니다
  (`galerkin.core.backend.TracedValueError`). `jit` 없이 `jax.grad`와 PyTorch
  autograd는 동작합니다.
- forward 모드 미분(`jax.jvp`, `jax.jacfwd`)과 2차 미분.
- `jax_enable_x64`가 꺼진 JAX, 그리고 한 호출에 섞인 JAX와 PyTorch 값.
- 아직 미분하지 않는 solver는 미분을 조용히 끊지 않고 JAX·PyTorch 값을
  `TypeError`로 거부합니다. 과도 열, 탄성, 열탄성은 입력 검사에서,
  `ElementHeatSource`와 `ElementConductivity`, 그리고 Joule 결합과
  열→역학 workflow가 거부합니다(열→역학 workflow는 열 단계의
  `WorkflowStageError`로 알립니다). JSON 문서와 명령행은 NumPy로 돕니다.

## 한계

- 아직 막지 않은 곳: 낮은 수준 조립 함수(`galerkin.assembly`, `assembly3d`,
  `edge`, `edge3d`)와 전자기 solver는 입력을 NumPy로 바꿉니다. 여기에 넘긴 JAX
  값은 미분을 잃으므로, 살아 있는 값을 넘기지 마십시오.
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

adjoint 풀이 자체는 `tests/galerkin/test_core_solve.py`에서 각 라이브러리가 밀집
`linalg.solve`를 자동미분한 값과, 중심차분과 비교합니다.
