# 사면체 메시의 정상 열전도

[English](../../../../../packages/galerkin/thermal3d.md) | **한국어**

명시적 import는 `galerkin.thermal3d`와 `refsol.thermal3d`입니다. 이 모듈은
[사면체 메시 형식](mesh3d_format.md)의 어떤 메시에서든 P1 사면체로 등방성 정상
열전도를 풉니다.

```text
-div(k grad T) = Q,       q = -k grad T
T = prescribed value on Dirichlet nodes
q.n = h (T - T_ambient) - inward_heat_flux on specified natural faces
q.n = 0 on the remaining faces
```

`Mesh3D`, P1 사면체 강성 `assemble_stiffness_3d`, Dirichlet 솔버를 재사용하고 열원
하중은 모듈 안에서 조립합니다. [정상 2D 열전도](thermal_steady2d.md)의
3D 대응이며, `meshine.extrude`의 층상 전도 검사가 쓰는 솔버입니다.

## API와 SI 단위

```python
from meshine import Domain, box_sides, extrude, generate, rectangle
from galerkin import from_mesher
from galerkin.kernels import dirichlet_from_faces
from galerkin.thermal3d import solve_steady_heat_3d

d = Domain(size=0.1)
d.add_region("chip", rectangle(0, 0, 1.0, 0.8))
mesh = from_mesher(extrude(generate(d, box_sides(0, 1.0, 0, 0.8)), [0.0, 0.2, 0.3, 0.6],
                           {"chip": ["substrate", "die", "mold"]}, size=0.1))
result = solve_steady_heat_3d(
    mesh,
    thermal_conductivity={"substrate": 1.0, "die": 0.01, "mold": 0.5},
    prescribed_temperature=dirichlet_from_faces(mesh, {"z0": 320.0, "z1": 300.0}),
    heat_source_density={"substrate": 0.0, "die": 2e5, "mold": 0.0},
)
```

| 입력 | 계약 / 단위 |
| --- | --- |
| mesh | m 단위 `galerkin.Mesh3D`: meshine·gmshio 메시의 `from_mesher` 또는 `box_mesh`. 자연 경계 맵은 `mesh.tagged_faces`를 사용합니다. |
| thermal_conductivity | 유한한 k > 0, W/(m K), 또는 `mesh.region_names`와 정확히 같은 항목의 `{영역 이름: k}` |
| prescribed_temperature | `{절점 인덱스: 온도 K}`; 모든 절점은 외부 경계 위에 있고 각 연결 성분에는 고정 절점 또는 h가 양수인 면이 필요합니다 |
| heat_source_density | Q W/m^3, `{영역 이름: Q}`, `mesh.tets` 순서의 유한한 실수 `(T,)` 배열, 또는 읽기 전용 `(T, 3)` 사면체 중심 좌표를 받아 `(T,)` 값을 돌려주는 callable; 기본 `None`(열원 없음) |
| inward_heat_flux | `{면 태그: 열유속}`, W/m^2, 안쪽으로 향하는 값이 양수 |
| convection | `{면 태그: (h, T_ambient)}`, h >= 0의 단위는 W/(m^2 K), 주위 온도는 K |

각 태그에 지정한 값은 그 태그의 모든 면에서 일정합니다. 같은 삼각형의 열유속과 대류는
합산합니다. 알 수 없거나 비어 있거나 외부가 아닌 면, 같은 조건에서 중복 지정한 면, 절점이 모두
고정된 삼각형의 자연 경계는 `ValueError`를 냅니다. 자연 경계 입력은 정적 메시에서 지원합니다.
요소별 줄 발열을 적용하려면 같은 메시의 1차원 J·E 배열을 `heat_source_density`로 전달합니다.
총 발열은 `density @ mesh.volumes()`로 계산하며 단위는 W입니다.

`dirichlet_from_faces(mesh, {면 태그: T})`는 태그를 절점 맵으로 바꾸고, 두 태그가 다른
온도로 두려는 절점을 거부합니다. 공개 API가 아니라 내부 `galerkin.kernels`의 도우미입니다(일관 단위: 여기서는 켈빈).

| 결과 필드(`SteadyHeat3DResult`, frozen) | 의미와 단위 |
| --- | --- |
| `temperature` | `(N,)` K |
| `heat_flux` | `(T, 3)` W/m^2, 사면체별 `-k grad T` |
| `generated_heat_rate` | `(N,)` W, 열원 하중: 사면체마다 절점당 `Q V / 4` |
| `reaction_heat_rate` | `(N,)` W, Dirichlet 절점의 전체 계 잔차, 그 외 0; 양수가 열을 넣음 |
| `residual_heat_rate` | `(N,)` W, 자연 경계 항을 포함한 모든 절점의 전체 계 잔차 |
| `thermal_conductivity`, `heat_source_density` | 사용한 `(T,)` 값 |
| `outward_prescribed_heat_rate` | `(N,)` W, 지정 안쪽 열유속에 음의 부호를 붙인 절점별 적분 |
| `outward_convective_heat_rate` | `(N,)` W, h (T - T_ambient)의 절점별 적분 |
| `relative_conservation_residual` | 체적 발열과 반력 열률을 더하고 두 외향 열률을 뺀 합의 절댓값을 절점별 열률 절댓값의 합으로 나눈 값 |
| `prescribed_node_ids` | 고정한 절점 인덱스(정렬) |

절점 열량은 깊이당이 아닌 W이므로 필드에 `_per_depth`가 없습니다(물으면 이유를 말하는
`AttributeError`). `.units`가 각 물리량 필드의 SI 단위를 줍니다. 자유 잔차가 계 규모의 `1e-10`을 넘거나 열수지가
`1e-10`을 넘으면 `ValueError`를 던지므로, 반환된 결과는 둘을 통과한 것입니다.
JAX·PyTorch 값은 `TypeError`이며, 미분 경로는 JAX·PyTorch t를 준 형상 미분 `motion=MeshMotion(...)` 하나뿐입니다([형상 미분](shape_derivative.md#3d-정상-열)).

## 검증

`tests/galerkin/test_thermal3d_boundaries.py`는 세 메시 해상도의 균질 슬래브를
직접 구한 선형 해와 독립 `refsol.thermal_boundary` 해에 비교합니다. 면 적분 열률,
부호를 고려한 열수지와 요소별 체적열원의 총 발열을 검사합니다. 균일 체적 발열과 같은 면의 두 자연 경계 항을
함께 적용하고 SciPy `solve_bvp`의 독립 배치법 해와 비교한 결과, 절점 온도의 RMS 오차는
2.18차, 요소 중심 축 방향 열유속의 부피 가중 RMS 오차는 0.975차로 수렴했습니다.

`refsol.thermal3d`는 독립 폐형식 둘을 제공합니다.

- `sine_product(points, *, length, thermal_conductivity, reference_temperature, temperature_difference)`:
  `T = T0 + A sin(pi x/Lx) sin(pi y/Ly) sin(pi z/Lz)`와 그 열유속·열원
  `Q = k pi^2 (1/Lx^2 + 1/Ly^2 + 1/Lz^2) (T - T0)`, 여섯 면에서 `T = T0`.
- `layered_slab(points, *, position, thermal_conductivity, prescribed_temperature)`:
  열원 없는 z 방향 직렬 전도(`position`은 아랫면부터의 층 경계, `prescribed_temperature`는
  (아래, 위) 쌍). 구간 선형 온도와 균일 열유속
  `(T_bottom - T_top) / sum(d_i / k_i)`. 층 경계가 절점 평면이면 P1에서 정확.

`tests/galerkin/test_thermal3d.py`는 1.0 x 0.8 x 0.6 m 상자의 비정형 발자국을
`meshine.extrude`로 쌓은 메시(Gmsh 없음)에서 3D 개방의 사전 등록 gate로 솔버를
채점합니다.

| 검사 | Gate | 측정(Linux, 이 변경) |
| --- | --- | --- |
| 사인 곱, k = 2.5, 크기 0.2, 0.1, 0.05 m, 중심점 열원 | L2 차수 >= 1.8, H1 차수 >= 0.9(세 메시의 최소제곱 기울기) | L2 오차 6.12e-2, 1.70e-2, 4.46e-3(차수 1.889); H1 오차 8.17e-1, 4.30e-1, 2.20e-1(차수 0.946) |
| 3층 슬랩 0.2 / 0.1 / 0.3 m, k = 1, 0.01, 0.5, 320 K → 300 K, 크기 0.15 m | 20 K 낙차 대비 온도 오차 <= 1e-10; 열유속 <= 1e-9; 뜨거운 면 반력 = 열유속 x 면적 | 통과(roundoff) |
| 모든 풀이 | `relative_conservation_residual <= 1e-10` | 솔버가 강제 |

`tests/refsol/test_thermal3d_reference.py`는 기준해 자체를 검사합니다. 유한차분 대비
열유속·열원, 직렬 공식 대비 슬랩, 모듈이 NumPy만 import하는지.

저장소 루트에서 실행합니다.

```sh
python -m pytest -q tests/galerkin/test_thermal3d.py tests/refsol/test_thermal3d_reference.py
```

## 한계

- 등방성·온도 무관·영역 내 상수 열전도율. 텐서, 열유속, Robin, 과도, 역학 연성은
  없습니다. 2D 모듈에는 있지만 여기서 3D로 옮기지 않았습니다.
- callable 열원은 사면체마다 한 번(중심점) 표본화합니다. 위의 P1 차수는 유지되지만
  변하는 열원의 정확한 적분은 아닙니다.
- Dirichlet 절점은 외부 경계 위에 있어야 하며 내부 절점은 거부합니다.
