# 형상 미분: 설계 변수로 메시 움직이기

[English original](../../../../../packages/galerkin/shape_derivative.md)

[galerkin 개요](overview.md) · [JAX·PyTorch로 미분하기](differentiation.md)

`galerkin.shape`는 층 두께나 구멍 반지름처럼 메시를 움직이는 설계 변수에 대한 미분을 줍니다. 이번 첫 조각은 정상
Cartesian 열(`galerkin.thermal.solve_steady_heat`)을 다룹니다. 다른 솔버는 같은 틀로 뒤에 잇습니다.

## 무엇을 미분하나

설계 변수 t가 모든 노드를 움직입니다: **X(t) = X₀ + t·W**.
- **W**는 (N, 2) 모양의 고정된 NumPy 메시 속도입니다. t 한 단위당 노드가 메시 길이 단위로 움직이는 양입니다.
- **t**만 live 값입니다(JAX·PyTorch 스칼라). 그 수치는 풀이가 이루어지는 스텝이며, 보통 0(주어진 메시)입니다.
- 연결·태그·영역은 고정입니다.

미분은 그 움직이는 메시 위 이산 해의 정확한 미분입니다. 노드를 ±h·W만큼 옮겨 다시 풀면 유한차분 절단 오차 안에서 같은
값이 나옵니다.

풀이는 옮겨진 메시에서 일반 솔버로 한 번 돌기 때문에, 모든 입력 검사·잔차 허용치·열수지가 그대로 적용됩니다. 그다음
live 풀이 한 번이 미분을 붙입니다: T = T₀ + A(t)⁻¹ (b(t) − A(t) T₀). A(t)와 b(t)는 X₀ + t·W로 live 라이브러리에서 조립하며
(P1 강성, 영역 열원, 움직이는 변의 flux·Robin 항), T는 반올림 안에서 T₀와 같습니다. `temperature`·`heat_flux`·`load`·
`reaction`·`residual`이 미분을 나릅니다.

```python
import jax
import jax.numpy as jnp
from galerkin.shape import MeshMotion, admissible_interval, extend_velocity
from galerkin.thermal import solve_steady_heat

jax.config.update("jax_enable_x64", True)
W = extend_velocity(mesh, boundary_velocity, on_curve)   # (N, 2)
lo, hi = admissible_interval(mesh, W)                    # lo < t < hi에서 뒤집히는 요소 없음


def heat_in(t):
    r = solve_steady_heat(mesh, conductivity=k, dirichlet=dirichlet, motion=MeshMotion(W, t))
    return jnp.sum(r.reaction[hot])


dQ = jax.grad(heat_in)(jnp.asarray(0.0))
```

PyTorch는 `torch.tensor(0.0, dtype=torch.float64, requires_grad=True)`를 넘기고 `.backward()`를 부릅니다.

## 메시 속도

형상의 곡선 위 노드는 설계가 움직이는 대로 움직입니다. 버전 1 형상 문서라면 `simcase.geometry_velocity.design_velocity(document,
p).node_velocity(meshine_mesh)`가 그 값을 줍니다([설계 속도](../simcase/geometry_engine.md#설계-속도-4단계)). 그 `values`는 무차원이므로
(∂x/∂p, x와 p 모두 문서 단위), 이때 t는 메시 길이 단위로 나타낸 파라미터 변화입니다. `galerkin.interop.from_mesher`는 meshine
노드 순서를 유지합니다.

`extend_velocity(mesh, values, known, method="harmonic")`가 나머지 노드를 움직입니다. 같은 메시에서 성분별 라플라스 문제를
풀며, known 노드의 값이 Dirichlet 자료입니다.
- `"harmonic"`(기본)은 확산계수 1을 씁니다. 아핀 이동을 정확히 재현합니다.
- `"stiffened"`는 확산계수를 요소 넓이로 나눠, 작은 요소가 더 강체처럼 움직이게 합니다.

이 선택은 이산 미분을 이산화 수준에서만 바꾸며, 그 차이는 메시를 세분하면 사라집니다(아래 검증 S4). 주로 요소가 뒤집히기
전까지 스텝이 얼마나 갈 수 있는지를 정합니다.

## 요소 뒤집힘과 재메시

X₀ + t·W에서 각 요소의 부호 넓이는 t의 이차식입니다. `admissible_interval(mesh, W)`는 모든 요소에서 양쪽으로 가장 가까운
근을 돌려줍니다. 그 열린 구간 안에서는 어떤 요소도 뒤집히지 않습니다. 구간 밖 스텝에서 풀면 구간을 밝히는
`galerkin.shape.ElementInversion`이 납니다. t = 0의 미분은 언제나 정의됩니다.

galerkin은 재메시하지 않습니다. 미분은 그것을 계산한 메시에 속합니다. 호출자가 새 파라미터 값에서 형상으로부터 메시를 다시
만듭니다. 권장 기준은 스텝이 허용 구간의 절반을 넘거나, 최소각이 메셔의 `min_angle` 아래로 떨어질 때입니다. 재메시를 건너면
범함수와 그 미분이 이산화 수준, 즉 아래 수렴 오차 정도만큼 바뀝니다.

## 거부

각 거부는 이유를 밝힙니다.
- NumPy `t`(`TypeError`): NumPy는 미분하지 않습니다. 옮겨진 메시에서 풀려면 노드를 옮겨 그 메시를 푸십시오.
- live 메시 속도; 모양이 틀리거나 유한하지 않은 속도.
- 허용 구간 밖 스텝(`ElementInversion`).
- 열원·outward flux·convection의 좌표 콜백과 `ElementHeatSource`: 표본점이 메시와 함께 움직입니다.
- motion과 함께 쓰는 live 전도도·열원·경계값·Dirichlet 값: 그런 호출에서 live 입력은 t 하나입니다.
- `coordinate_system="axisymmetric"`.
- 다른 솔버의 `motion=`: 그 솔버에는 이 키워드가 없습니다.
- 2차 미분: 모든 galerkin 풀이처럼 JAX 전진 모드와 PyTorch `create_graph=True`는 오류를 냅니다
  ([거부 목록](differentiation.md#근사하지-않고-거부하는-것)).

## 검증

`tests/galerkin/test_shape_derivative.py`에 구현 전에 사전 등록한 검사 S1–S8이 있습니다. 2026-11-09에 Linux, JAX 0.12.0.1,
PyTorch 2.14.1+cpu로 측정했습니다.

| 검사 | 기준 | 결과 |
|---|---|---|
| S1 이산 일관성 | 움직이는 변에 열원·convection·flux가 있는 문제에서, 탐침 온도·Dirichlet 열량·평균 온도의 미분 vs 옮긴 메시 중심차분(h = 1e-4); 상대 1e-6, JAX·PyTorch | 1.7e-9, 9.2e-10, 4.1e-9 |
| S2 두 층 평판 | dR/dL₁ = 1/k₁ − 1/k₂, 상대 1e-10 | 약 1e-14까지 정확 |
| S3 환형 | 형상 엔진 노드 속도로 안 반지름; dQ/da = 2πk/(a ln²(b/a)); 관측 차수 ≥ 1.5, 최세 1e-3 이내 | 크기 0.8·0.4·0.2에서 8.1e-3, 2.1e-3, 5.8e-4; 차수 1.97·1.84 |
| S4 확장 무관성 | 조화 vs 강화 미분 차이: 차수 ≥ 1, 최세 1e-3 이내 | 2.4e-4, 5.4e-5, 1.6e-5; 차수 2.1·1.8 |
| S5 강체 이동 | dJ/dt = 0, 1e-12 · \|J\| 이내 | 통과 |
| S6 뒤집힘 한계 | 구간이 정확한 근과 같음; 넘는 스텝은 거부 | 통과 |
| S7 무변경 | `motion` 없이 결과가 이전 코드와 같음 | 결과 배열 sha256이 main `627eb28`과 같음(측정); `motion=None`과 키워드 없음이 같음(시험) |
| S8 거부 | 위 목록대로 | 통과 |
