# 3D 솔버가 공유하는 사면체 메시 형식

[English](../../../../../packages/galerkin/mesh3d_format.md) | **한국어**

[galerkin 개요](overview.md)

`galerkin`의 3D 솔버(`solve_cavity`, `solve_material_cavity`,
`thermal3d.solve_steady_heat_3d`, P1·Nédélec 조립)는 한 가지 메시 타입
`galerkin.Mesh3D`만 읽습니다. 다른 곳에서 만든 메시는 `galerkin.from_mesher`를
거치며, 아래 필드를 가진 객체나 dict면 무엇이든 받습니다. `gmshio.FemMesh3D`(별도
프로세스로 실행하는 Gmsh)와 `meshine.TetMesh`(`meshine.extrude`, 순수 NumPy)가 바로
이 필드를 갖습니다. 이 문서는 그 공통 형식의 규범 설명입니다. 인덱스 배열은 0부터
시작합니다.

## 필드

| 필드 | 형상과 타입 | 의미 |
|---|---|---|
| `nodes` | `(N, 3)` float | 좌표. 단위는 호출자의 것이며 각 솔버가 자기 단위를 밝힙니다(공진기·열 솔버는 m). |
| `tetrahedra` | `(T, 4)` int | 각 사면체의 절점 id. `Mesh3D`는 `tets`로 저장하고, 음의 방향을 가진 사면체는 두 정점을 바꿔 모든 부피를 양수로 만듭니다. 메셔가 이미 양의 방향으로 넘길 수도 있습니다(meshine은 정확 산술로 검사). |
| `regions` | `(T,)` int | 각 사면체의 영역 id, `region_names`의 인덱스. |
| `region_names` | `list[str]` | 영역 id마다 하나씩, 중복 없는 이름. |
| `boundary_faces` | `{이름: (F, 3) int}` | 태그가 붙은 외부 면. `Mesh3D`는 `tagged_faces`로 저장합니다. 메서드 `Mesh3D.boundary_faces()`는 예전 의미(모든 외부 면을 정렬된 태그 없는 절점 삼중쌍으로)를 유지합니다. |
| `boundary_nodes` | `{이름: (n,) int}`, 선택 | 태그별 절점 집합. 없으면 면에서 유도하고, 있으면 `unique(boundary_faces[이름])`과 같아야 합니다. `Mesh3D`는 `boundary`로 저장하며 2D식 절점 집합 API(`solve_dirichlet`)가 이를 읽습니다. |
| `interfaces` | `{(a, b): (F, 3) int}`, 선택 | 영역 `a < b` 사이의 면, `a`에서 `b` 방향으로 감김. `Mesh3D.interfaces`에 저장하며 galerkin은 검증하지 않습니다(meshine의 `check`가 검증). |

`Mesh3D`는 면 없이 절점 집합(`boundary`)만 가질 수도 있습니다. 면이 추가되기 전의
`box_mesh`가 그랬고, 표면 physical group이 없는 파일을 읽는 `galerkin.read_msh`가
그렇습니다. 태그로 벽을 고르는 모든 기능(`solve_cavity`, `solve_material_cavity`,
`thermal3d.dirichlet_from_faces`)은 면이 필요합니다.

## 규칙

`Mesh3D.check()`는 모든 위반을 나열한 `MeshCheckError`를 던지고, `validate()`는 그
목록을 반환합니다. `from_mesher`는 면을 가지고 들어오는 모든 메시에 `check()`를
실행합니다. 규칙은 meshine `TetMesh` 계약과 같습니다([meshine 개요](../meshine/overview.md)).

1. **영역.** `regions`는 사면체마다 id 하나를 갖고 모든 id는 `[0, len(region_names))`
   안에 있습니다. 음수 id는 개수를 밝히며 거부합니다. gmshio는 어떤 physical
   volume에도 속하지 않는 사면체에 `-1`을 주므로, 기하의 모든 volume에 태그를 붙이거나
   그 사면체를 제거하세요. `Mesh3D.by_region`도 음수 id를 거부합니다(음수 인덱스는
   조용히 마지막 영역을 골랐을 것입니다).
2. **모든 외부 면은 정확히 한 번 태그됩니다.** 외부 면은 정확히 한 사면체에 속한
   면입니다. 태그 없는 외부 면, 두 이름으로 태그된 면, 외부가 아닌 태그 면을 모두
   보고합니다.
3. **바깥 방향 감김.** 태그 면 `(a, b, c)`의 `(b - a) x (c - a)`는 영역 밖을 향합니다.
   즉 양의 방향 사면체에서 `OUTWARD_FACES`로 읽은 면의 짝 순열입니다.
4. **절점 집합은 면과 일치합니다.** `boundary`는 면과 같은 태그를 갖고 각 집합은 그
   면들의 중복 없는 절점 목록입니다.

벽 위의 변은 절점 소속이 아니라 면에서 유도합니다. 벽 절점 두 개를 잇는 변이 내부를
지날 수 있기 때문입니다.

## 생산자

| 생산자 | 영역 | 면 태그 |
|---|---|---|
| `galerkin.box_mesh`, 공진기 솔버의 교대 상자 | `domain` | `x0`, `x1`, `y0`, `y1`, `z0`, `z1` |
| `meshine.extrude(footprint, z, materials)` | 층마다 준 재료 이름 | `z0`, `z1`(아래, 위), 발자국의 측면 이름(`box_sides`의 `left`, `right`, `bottom`, `top` 또는 임의 namer), 비운 셀과 맞닿은 `void` |
| `gmshio.to_fem3d(generate(geo))` | physical volume 이름, 그 밖은 `-1`(거부) | physical surface 이름, 예: `geo.box_cavity`의 `pec` |
| `galerkin.read_msh`(3D) | 모든 사면체가 physical volume을 가질 때 그 이름 | physical surface 이름을 그대로 |

## 벽 이름

저장소에는 세 가지 체계가 공존합니다.

- **역할 이름**: 전자기 역할 하나에 태그 하나. `geo.box_cavity`는 여섯 벽 전부를
  `pec`, 부피를 `cavity`로 태그합니다.
- **`x0 x1 y0 y1 z0 z1`**: `box_mesh`, 상자 공진기 솔버의 `WALLS`, `extrude`의 `z0`/`z1`.
- **`xmin xmax ymin ymax zmin zmax`**: simcase JSON 공진기 문서. 솔버를 부르기 전에
  `x0..z1`로 바꿉니다.

메시를 받는 솔버는 체계를 강제하지 않습니다. 태그는 임의의 문자열이고, 문제는 메시가
가진 태그로 벽을 지칭합니다. 직접 만드는 메시에는 축 정렬 벽에 `x0..z1`(상자 솔버가
바로 받는 이름이고 `extrude`가 위·아래에 만드는 이름), 그 외에는 역할·부품
이름(`pec`, `port`, `die_top`)을 제안합니다. `xmin..zmax`는 JSON 표기로 남습니다.
이는 제안이며 검사하지 않습니다.

## 예

```python
from meshine import Domain, box_sides, extrude, generate, rectangle
from galerkin import from_mesher

d = Domain(size=0.1)
d.add_region("cavity", rectangle(0, 0, 1.0, 0.8))
tet = extrude(generate(d, box_sides(0, 1.0, 0, 0.8)), [0.0, 0.3, 0.6],
              {"cavity": ["slab", "air"]}, size=0.1)
mesh = from_mesher(tet)           # mesh.check() 실행
mesh.tagged_faces.keys()          # z0, z1, left, right, bottom, top
mesh.by_region({"slab": 2.1, "air": 1.0})
```

소비자는 [공진기 솔버](cavity_solver.md), [재료 공진기](material_cavity.md),
[3D 정상 열전도](thermal3d.md) 문서에 있습니다.
