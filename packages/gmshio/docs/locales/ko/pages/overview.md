# gmshio — Gmsh와 링크하지 않고 galerkin에 메시 제공

[English](../../../overview.md) | **한국어**

[영어·한국어 문서와 번역 상태](https://github.com/fieldalgo/openphysics/blob/main/docs/locales/ko/pages/index.md)

`.geo` 스크립트를 작성하고 `gmsh` 명령행 프로그램을 별도 프로세스로 실행한 뒤, 생성된 MSH 4.1 파일을 유한요소 코드에서 바로 사용할 수 있는 numpy 배열로 읽습니다. 노드 좌표, 일관된 방향의 요소, 요소별 영역 ID, 이름별 경계 면을 제공합니다.

Gmsh는 GPL입니다. 이 패키지는 Gmsh Python API를 import하거나 라이브러리에 링크하지 않습니다. 프로그램을 실행하고 출력만 해석하므로 `gmshio`를 사용하는 솔버는 자체 라이선스를 유지합니다. `gmshio` 자체 의존성은 numpy뿐입니다.

## 설치

```bash
# From the repository root
python -m pip install -e packages/gmshio
# plus a gmsh executable, one of:
pip install gmsh            # PyPI wheel ships the program
# or a system package / download from https://gmsh.info, or set GMSH_EXECUTABLE
```

## 사용법

```python
from gmshio import geo, generate, to_fem2d, to_fem3d, read_msh

# 1. a ready-made benchmark geometry -> .geo text -> gmsh -> Mesh -> FEM arrays
mesh = generate(geo.rib_waveguide(slab_thickness=0.3, lc_core=0.1), dim=2)
fem = to_fem2d(mesh)
fem.nodes            # (N, 2)
fem.triangles        # (T, 3) counter-clockwise
fem.regions          # (T,) index into fem.region_names == ["core", "box", "clad"]
fem.boundary_edges   # {"left": (E, 2), "right": ..., "top": ..., "bottom": ...}
fem.region_area("core")   # 7.5 exactly (polygonal regions are reproduced exactly)

# 2. your own planar geometry: list material regions as polygons that tile the domain
g = geo.Geo()
g.add_region("core", [(-1, 0), (1, 0), (1, 0.5), (-1, 0.5)], lc=0.05)
g.add_region("clad", [(-3, -2), (3, -2), (3, 0.5), (1, 0.5), (1, 0), (-1, 0), (-1, 0.5), (-3, 0.5)], lc=0.3)
g.add_region("clad", [(-3, 0.5), (3, 0.5), (3, 2), (-3, 2)], lc=0.3)
fem = to_fem2d(generate(g.render(geo.box_sides(-3, 3, -2, 2)), dim=2))
# shared edges and T-junctions between polygons are resolved automatically

# 3. 3D
fem3 = to_fem3d(generate(geo.box_cavity(1.0, 0.5, 0.75, lc=0.1), dim=3))
fem3.tetrahedra, fem3.boundary_faces["pec"]

# 4. read a .msh you produced yourself (MSH 4.1 ASCII)
mesh = read_msh("model.msh")
mesh.cells("triangle"), mesh.physical_tags("triangle"), mesh.cells_in("pec", "line")
```

`.geo` 스크립트는 작성자가 선택한 단위를 사용하므로 `gmshio`에는 절대 길이 상수가 없습니다. `Geo`의 점 병합과 T자 접합 분할은 해당 형상의 경계 상자 대각선에 대한 무차원 비율을 사용합니다. `to_fem2d`도 메시 자체의 평면 내 크기로 평면성을 판단하므로, 같은 형상을 마이크로미터 또는 킬로미터로 적어도 같은 위상을 얻습니다.

`gmshio.geo`의 기본 형상:

| 함수 | 형상 | 영역 / 경계 |
|---|---|---|
| `rib_waveguide(...)` | Hadley (2002) 리브 도파로 단면: 3 µm × 1 µm 리브, 0–0.7 µm 슬랩, 폭 18 µm 영역, 10 µm 기판, 3 µm 클래딩 | `core`, `box`, `clad` / `left right top bottom` |
| `circular_fiber(a, R, lc_core)` | 계단형 굴절률 광섬유: 원형 클래딩 내부 원형 코어, 정확한 원호 | `core`, `clad` / `outer` |
| `box_cavity(a, b, d, lc)` | 직육면체 공진기 | `cavity` / `pec` |

## 자체 검증

```bash
# From the repository root
python -m pip install pytest -e packages/gmshio
python -m pytest -q tests/gmshio
```

판독기 출력을 자기 자신과 비교하는 대신 솔버가 의존하는 특성을 검사합니다. 다각형 영역의 면적과 상자 부피가 정확히 재현되고, 모든 요소 방향이 양수이며, 태그 경계가 정확히 한 요소에서만 쓰이는 변(면)의 집합과 일치하는지 확인합니다. 광섬유 경계 노드는 실제 원에 1e-9 이내로 놓이고, 원의 다각형 면적 오차는 2차로 감소합니다. 실행 파일이 필요한 시험은 실행 파일이 없으면 skip됩니다.

## 범위와 한계

- MSH 4.1 ASCII만 지원합니다(`gmsh -format msh41`). 바이너리와 이전 버전은 명확한 오류로 거절합니다.
- `to_fem2d` / `to_fem3d`는 1차 삼각형 / 사면체를 받습니다. 원시 `Mesh`는 Gmsh가 생성한 모든 요소 유형을 보존합니다.
- `Geo`는 직선 변의 다각형을 처리합니다. 곡선은 직접 작성하거나(`circular_fiber` 참조), `Geo.raw` / 자체 `.geo`를 통해 Gmsh OpenCASCADE 커널로 작성합니다.

## 라이선스

Apache License 2.0 — [LICENSE](../../../../LICENSE), [NOTICE](../../../../NOTICE)를 참조하세요.

Copyright 2026 Yongha Kim (FieldAlgo)

Gmsh는 GPL-2.0-or-later의 별도 프로그램입니다. 이 패키지에 배포되거나 링크되지 않습니다. `gmshio`는 `.geo` 스크립트를 작성하고 `gmsh` 실행 파일을 자식 프로세스로 실행한 뒤 `.msh` 파일을 읽습니다. 따라서 GPL은 `gmshio` 또는 이를 사용하는 코드로 확장되지 않습니다. Gmsh는 자체 라이선스에 따라 별도로 설치하세요.

이 프로젝트는 Gmsh 프로젝트와 제휴하지 않으며, 그 프로젝트의 보증이나 지원을 받지 않습니다.

