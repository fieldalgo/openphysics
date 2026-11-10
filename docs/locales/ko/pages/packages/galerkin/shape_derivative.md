# 형상 미분: 설계 변수로 메시 움직이기

[English original](../../../../../packages/galerkin/shape_derivative.md)

[galerkin 개요](overview.md) · [JAX·PyTorch로 미분하기](differentiation.md)

`galerkin.shape`는 층 두께나 구멍 반지름처럼 메시를 움직이는 설계 변수에 대한 미분을 줍니다. 정상 Cartesian 열
(`galerkin.thermal.solve_steady_heat`, 2026-11-09), 정상 전기 전도(`galerkin.electric.solve_steady_electric`, 2026-11-10),
선형 탄성(`galerkin.elasticity.solve_elasticity`, 2026-11-10), 열탄성(`galerkin.thermoelasticity.solve_thermoelasticity`와
`galerkin.thermal_mechanical.solve_steady_thermoelasticity`, 2026-11-10)을 다룹니다. 다른 솔버는 같은 틀로 뒤에 잇습니다.

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

## 정상 전기 전도

`solve_steady_electric(mesh, ..., motion=MeshMotion(W, t))`도 같은 방식입니다.
- 옮겨진 메시에서 일반 풀이가 돌고, 잔차·전류 수지·전력 수지 검사를 그대로 거칩니다.
- live 풀이 한 번이 X₀ + t·W로 시스템을 다시 조립합니다: 영역 전도도를 쓴 P1 강성, 움직이는 변의 outward current.
- 모든 필드가 d/dt를 나릅니다: `potential`·`electric_field`·`current_density`·`joule_heating`·`joule_load`·
  `joule_power_per_length`·`reaction`·`prescribed_outward_load`·`residual`·`supplied_power_per_length`.
  `result.mesh`는 옮겨진 메시의 NumPy 스냅샷이라, 그 좌표에는 미분이 없습니다.
- Dirichlet 전압과 `reference_potential` 게이지(전류 자료만 있는 성분)를 모두 받습니다. 게이지 성분에서는 이동이 알짜
  주입 전류를 0으로 유지해야 합니다(예: 전류가 흐르는 변의 길이를 유지). 그렇지 않으면 t 근처에 해가 없으므로 거부합니다.
- 솔버처럼 전압을 각 성분의 오프셋에 대한 값으로 다루므로, 큰 공통 전압이 전력이나 그 미분에 섞이지 않습니다.
- 이산 전력 항등식(Joule 전력 = 공급 전력)이 미분에서도 성립합니다(검증 E5).

## 선형 탄성

`solve_elasticity(mesh, ..., motion=MeshMotion(W, t))`는 plane stress·plane strain, 스칼라 또는 영역별 영률·푸아송비,
일정 체적력, 경계 태그의 일정 traction(변과 함께 움직임), Dirichlet 변위 `{(node, component): value}`를 받습니다. 변위·변형률·
응력·부하·반력·잔차가 d/dt를 나릅니다.
- Dirichlet 값은 노드에 붙어 노드와 함께 움직입니다.
- 큰 강체 변위 오프셋(탄성 변형보다 훨씬 큰 Dirichlet 값)은 솔버 자체에서처럼 결과와 그 미분의 정밀도를 떨어뜨립니다.

## 열탄성

`motion=`을 받는 경로는 둘이고, 온도장이 메시와 함께 움직이는 방식이 다릅니다.
- **정해진 온도**, `solve_thermoelasticity(mesh, snapshot, ..., motion=MeshMotion(W, t))`:
  - 스냅샷은 주어진 메시(X₀)의 것이며, motion이 없을 때처럼 그 메시에 대해 검사합니다.
  - 노드 온도는 Dirichlet 변위처럼 노드에 붙어 함께 움직입니다. 그래서 미분은 기하(변형률 행렬·요소 넓이·하중 변
    길이)에서만 옵니다.
  - 선형 탄성이 받는 것에 더해 스칼라 또는 영역별 열팽창 계수와 기준 온도를 받습니다.
- **열 뒤 기계 워크플로**, `solve_steady_thermoelasticity(..., motion=MeshMotion(W, t))`:
  - 일반 워크플로를 옮겨진 메시에서 한 번 돌려 모든 단계 검사와 manifest를 얻습니다.
  - 그 뒤 열 단계를 움직이는 메시에서 다시 풀고(위 정상 열과 같음), 그 live 온도로 live 기계 단계를 풉니다. 그래서
    미분에 온도장의 변화가 들어갑니다.
  - `result.heat`와 `result.mechanics` 모두 d/dt를 나릅니다.
  - `result.reference_mesh`, `result.temperature_snapshot`, manifest는 옮겨진 메시를 기술하며 미분을 나르지 않습니다.
- 두 경로 모두 변위, 세 변형률, 응력, σzz, εzz, 외부·열 하중, 반력, 잔차, 물리 탄성 에너지가 d/dt를 나릅니다.
  `result.temperature_snapshot`은 옮겨진 메시의 스냅샷입니다.
- 공간에 고정된 온도장을 움직이는 노드에서 다시 샘플링하는 방식은 제공하지 않습니다. 좌표 콜백이 필요하기 때문입니다(아래
  거부).

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
- 열원·outward flux·convection·outward current·체적력·traction의 좌표 콜백(convection 쌍 안의 것 포함),
  `ElementHeatSource`와 `ElementConductivity`: 표본점이 메시와 함께 움직입니다.
- motion과 함께 쓰는 live 전도도·열원·경계값·Dirichlet·기준 전위·탄성 상수·열팽창 계수·기준 온도·체적력·traction 값:
  그런 호출에서 live 입력은 t 하나입니다.
- 다른 메시(옮겨진 메시 포함)의 온도 스냅샷: 스냅샷은 주어진 메시의 것입니다.
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

`tests/galerkin/test_shape_derivative_electric.py`에 정상 전기 전도의 검사 E1–E8이 있습니다. 2026-11-10에 사전 등록하고 같은 날
같은 버전으로 측정했습니다.

| 검사 | 기준 | 결과 |
|---|---|---|
| E1 이산 일관성 | 영역 전도도와 움직이는 변의 outward current가 있는 문제에서, 탐침 전위·단자 전류·Joule 전력의 미분 vs 옮긴 메시 중심차분(h = 1e-4); 상대 1e-6, JAX·PyTorch | 7.2e-10, 1.9e-9, 1.2e-9 |
| E2 두 층 저항 | dR/dL₁ = (1/σ₁ − 1/σ₂)/H, 상대 1e-10 | 통과 |
| E3 동축 도체 | 형상 엔진 노드 속도로 안 반지름; dI/da = 2πσΔV/(a ln²(b/a)); 관측 차수 ≥ 1.5, 최세 1e-3 이내 | 크기 0.8·0.4·0.2에서 8.1e-3, 2.1e-3, 5.8e-4 |
| E4 강체 이동 | dJ/dt = 0, 1e-12 · \|J\| 이내(전력, 전위 합) | 통과 |
| E5 전력 항등식 | d(Joule 전력)/dt = d(공급 전력)/dt, 상대 1e-10 | 9e-14(JAX), 5e-14(PyTorch) |
| E6 무변경 | `motion` 없이 결과가 이전 코드와 같음 | 결과 배열 sha256이 main `a0a432b`과 같음(측정); `motion=None`과 키워드 없음이 같음(시험) |
| E7 게이지 성분 | 전류 자료와 `reference_potential`만 있는 성분: E1 기준 | 통과 |
| E8 거부 | 위 목록대로 | 통과 |

그 뒤 독립 검토가 회귀 시험을 더했습니다: 1e9 V까지의 공통 전압(E5 기준), 전류만 있는 성분의 수지를 바꾸는 이동(거부).

`tests/galerkin/test_shape_derivative_elasticity.py`에 선형 탄성의 검사 M1–M8이 있습니다. 2026-11-10에 사전 등록하고 같은 날
같은 버전으로 측정했습니다.

| 검사 | 기준 | 결과 |
|---|---|---|
| M1 이산 일관성 | 두 재료·중력·움직이는 변의 traction이 있는 문제에서, 끝 변위·고정변 반력·변형 에너지의 미분 vs 옮긴 메시 중심차분(h = 1e-4), plane stress·plane strain; 상대 1e-6, JAX·PyTorch | 2.6e-10 ~ 9.6e-9 |
| M2 일축 봉 | dδ/dL = σ/E, 상대 1e-10 | 통과 |
| M3 직렬 두 재료(ν = 0) | dδ/dL₁ = σ(1/E₁ − 1/E₂), 상대 1e-10 | 통과 |
| M4 두꺼운 원통(plane strain) | 형상 엔진 노드 속도로 안 반지름, 그 위에 반지름 방향 변위 U₀, 바깥 자유; Lamé 해의 dF/da와 비교; 관측 차수 ≥ 1.0, 최세 1e-2 이내 | 크기 0.4·0.2·0.1에서 4.4e-2, 1.0e-2, 2.6e-3(차수 약 2) |
| M5 강체 이동 | dJ/dt = 0, 1e-12 · \|J\| 이내(변형 에너지, 변위 합) | 통과 |
| M6 에너지 항등식 | d(½∫σ:ε)/dt = d(½ load · u)/dt, 상대 1e-10 | 통과 |
| M7 무변경 | `motion` 없이 결과가 이전 코드와 같음 | 결과 배열 sha256이 main `6f80a73`과 같음(측정); `motion=None`과 키워드 없음이 같음(시험) |
| M8 거부 | 위 목록대로 | 통과 |

`tests/galerkin/test_shape_derivative_thermoelastic.py`에 열탄성의 검사 T1–T8이 있습니다(경로 1: 정해진 스냅샷, 경로 2:
워크플로). 2026-11-10에 T3의 메시 크기까지 사전 등록하고 같은 날 같은 버전으로 측정했습니다.

| 검사 | 기준 | 결과 |
|---|---|---|
| T1 이산 일관성 | 두 재료·불균일 온도·중력·(경로 1) 움직이는 변의 traction이 있는 문제에서, 끝 변위·고정변 반력 합·물리 탄성 에너지(경로 2는 평균 온도도)의 미분 vs 옮긴 메시 중심차분(h = 1e-4), plane stress·plane strain; 상대 1e-6, JAX·PyTorch | 경로 1: 1.9e-9 ~ 4.9e-8; 경로 2: 2.6e-10 ~ 2.0e-8, plane strain 반력 합은 예외(아래) |
| T2 자유 열팽창 | dδ/dL = αΔT(plane stress), (1+ν)αΔT(plane strain), 상대 1e-10 | 통과 |
| T3 두꺼운 원통, 열 연쇄(경로 2) | 형상 엔진 노드 속도로 안 반지름; 두 면 사이 로그 정상 온도, 안쪽 고정, 바깥 자유, plane strain; 안쪽 반지름 방향 반력의 dF/da를 닫힌 해와 비교; 크기 0.4·0.2·0.1; 관측 차수 ≥ 1.0, 최세 1e-2 이내 | 1.4e-1, 3.4e-2, 8.8e-3(차수 2.1, 1.9) |
| T4 양끝 고정 두 재료 봉(ν = 0) | σ = −ΔT(α₁L₁ + α₂L₂)/(L₁/E₁ + L₂/E₂)의 dσ/dL₁, 상대 1e-10 | 통과 |
| T5 강체 이동 | dJ/dt = 0, 1e-12 · \|J\| 이내(에너지, 변위 합), 두 경로 | 통과 |
| T6 온도 변화 없음 | T = T_ref이면 미분이 선형 탄성과 같음, 상대 1e-12 | 통과 |
| T7 무변경 | `motion` 없이 두 경로 결과가 이전 코드와 같음 | 결과 배열(과 manifest) sha256이 main `e9bb438`과 같음(측정); `motion=None`과 키워드 없음이 같음(시험) |
| T8 거부 | 위 목록대로 | 통과 |

T1 경로 2에서 고정변 반력 합은 10 800 N/m(체적력 × 넓이)이지만, 더하는 반력 하나하나는 약 1e7 N/m입니다. 일반 워크플로
자체의 반올림이 t = 0과 t = 1e-12의 두 풀이 사이에서 이 값을 약 2e-6 N/m 움직이고, 미분은 t 단위당 약 1.2e3 N/m입니다.
그래서 사전 등록한 h = 1e-4에서는 plane strain 중심차분이 미분과 4.2e-6 달라 1e-6을 넘습니다(plane stress: 2.0e-8).
h를 키우면 차이가 줄고(h = 1e-2: 4.8e-9), 미분은 평형값 d(ΣR_y)/dt = −f_y dA/dt와 1.2e-10 ~ 4.5e-10으로 같습니다. 그래서
시험은 이 합의 중심차분을 두 평면 모두 h = 1e-2에서 잡고 평형 검사를 더합니다. 사전 등록한 스텝과 다른 점이며, 여기와 HQ
기록에 적었습니다. 사전 등록하지 않은 모멘트 검사도 같게 다루고(h = 1e-4에서 plane strain 7.0e-6, plane stress 4.5e-7),
평형값(f_y × Σ 넓이 · 무게중심 x의 미분)과도 비교합니다.

사전 등록은 M4의 기준을 정했고 메시 크기는 정하지 않았습니다. 크기 0.8·0.4·0.2로 처음 돌리면 1.6e-1, 4.4e-2, 1.016e-2로 차수는 약
2지만 최세가 1e-2를 조금 넘었습니다. 시험은 한 단계 더 고운 세 크기를 쓰며, 기준은 그대로입니다.
