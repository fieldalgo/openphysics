# 사면체 메시의 정상 열전도

[English](../../../../../packages/galerkin/thermal3d.md) | **한국어**

명시적 import는 `galerkin.thermal3d`와 `refsol.thermal3d`입니다. 이 모듈은
[사면체 메시 형식](mesh3d_format.md)의 어떤 메시에서든 P1 사면체로 등방성 정상
열전도를 풉니다.

```text
-div(k grad T) = Q,       q = -k grad T
T = prescribed value on Dirichlet nodes
q.n = 0 on every other face (insulation, the natural condition)
```

`Mesh3D`, P1 사면체 강성 `assemble_stiffness_3d`, Dirichlet 솔버를 재사용하고 열원
하중은 모듈 안에서 조립합니다. 열유속·Robin 확장이 없는 [정상 2D 열전도](thermal_steady2d.md)의
3D 대응이며, `meshine.extrude`의 층상 전도 검사가 쓰는 솔버입니다.

## API와 SI 단위

```python
from meshine import Domain, box_sides, extrude, generate, rectangle
from galerkin import from_mesher
from galerkin.thermal3d import dirichlet_from_faces, solve_steady_heat_3d

d = Domain(size=0.1)
d.add_region("chip", rectangle(0, 0, 1.0, 0.8))
mesh = from_mesher(extrude(generate(d, box_sides(0, 1.0, 0, 0.8)), [0.0, 0.2, 0.3, 0.6],
                           {"chip": ["substrate", "die", "mold"]}, size=0.1))
result = solve_steady_heat_3d(
    mesh,
    conductivity={"substrate": 1.0, "die": 0.01, "mold": 0.5},
    dirichlet=dirichlet_from_faces(mesh, {"z0": 320.0, "z1": 300.0}),
    heat_source={"substrate": 0.0, "die": 2e5, "mold": 0.0},
)
```

| 입력 | 계약 / 단위 |
| --- | --- |
| mesh | m 단위 `galerkin.Mesh3D`: meshine·gmshio 메시의 `from_mesher` 또는 `box_mesh`. 면 태그는 `dirichlet_from_faces`에만 필요합니다. |
| conductivity | 유한한 k > 0, W/(m K), 또는 `mesh.region_names`와 정확히 같은 항목의 `{영역 이름: k}` |
| dirichlet | `{절점 인덱스: 온도 K}`; 모든 절점은 외부 경계 위에 있고 메시의 모든 연결 성분에 하나 이상 |
| heat_source | Q W/m^3, `{영역 이름: Q}`, 또는 읽기 전용 `(T, 3)` 사면체 중심 좌표를 받아 `(T,)` 값을 돌려주는 callable; 기본 0 |

`dirichlet_from_faces(mesh, {면 태그: T})`는 태그를 절점 맵으로 바꾸고, 두 태그가 다른
온도로 두려는 절점을 거부합니다.

| 결과 필드 | 의미와 단위 |
| --- | --- |
| `temperature` | `(N,)` K |
| `heat_flux` | `(T, 3)` W/m^2, 사면체별 `-k grad T` |
| `load` | `(N,)` W, 열원 하중: 사면체마다 절점당 `Q V / 4` |
| `reaction` | `(N,)` W, Dirichlet 절점의 `K T - load`, 그 외 0; 양수가 열을 넣음 |
| `residual` | `(N,)` W, 모든 절점의 `K T - load` |
| `conductivity`, `heat_source` | 사용한 `(T,)` 값 |
| `balance_error` | 절점 열량 절대합에 대한 `abs(sum(load) + sum(reaction))` |
| `dirichlet_nodes` | 고정한 절점 인덱스(정렬) |

절점 열량은 깊이당이 아닌 W입니다. 자유 잔차가 계 규모의 `1e-10`을 넘거나 열수지가
`1e-10`을 넘으면 `ValueError`를 던지므로, 반환된 결과는 둘을 통과한 것입니다. NumPy
전용: JAX·PyTorch 값은 `TypeError`이며 미분 경로는 없습니다.

## 검증

`refsol.thermal3d`는 독립 폐형식 둘을 제공합니다.

- `sine_product(points, lengths, conductivity, reference_temperature, amplitude)`:
  `T = T0 + A sin(pi x/Lx) sin(pi y/Ly) sin(pi z/Lz)`와 그 열유속·열원
  `Q = k pi^2 (1/Lx^2 + 1/Ly^2 + 1/Lz^2) (T - T0)`, 여섯 면에서 `T = T0`.
- `layered_slab(points, interfaces, conductivities, bottom_temperature, top_temperature)`:
  열원 없는 z 방향 직렬 전도. 구간 선형 온도와 균일 열유속
  `(T_bottom - T_top) / sum(d_i / k_i)`. 층 경계가 절점 평면이면 P1에서 정확.

`tests/galerkin/test_thermal3d.py`는 1.0 x 0.8 x 0.6 m 상자의 비정형 발자국을
`meshine.extrude`로 쌓은 메시(Gmsh 없음)에서 3D 개방의 사전 등록 gate로 솔버를
채점합니다.

| 검사 | Gate | 측정(Linux, 이 변경) |
| --- | --- | --- |
| 사인 곱, k = 2.5, 크기 0.2, 0.1, 0.05 m, 중심점 열원 | L2 차수 >= 1.8, H1 차수 >= 0.9(세 메시의 최소제곱 기울기) | L2 오차 6.12e-2, 1.70e-2, 4.46e-3(차수 1.889); H1 오차 8.17e-1, 4.30e-1, 2.20e-1(차수 0.946) |
| 3층 슬랩 0.2 / 0.1 / 0.3 m, k = 1, 0.01, 0.5, 320 K → 300 K, 크기 0.15 m | 20 K 낙차 대비 온도 오차 <= 1e-10; 열유속 <= 1e-9; 뜨거운 면 반력 = 열유속 x 면적 | 통과(roundoff) |
| 모든 풀이 | `balance_error <= 1e-10` | 솔버가 강제 |

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
