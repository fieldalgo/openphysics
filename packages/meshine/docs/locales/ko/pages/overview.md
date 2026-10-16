# meshine — 여러 재료로 구성된 평면 영역의 소형 품질 삼각형 메시 생성기

[English](../../../overview.md) | **한국어**

[영어·한국어 문서와 번역 상태](https://github.com/fieldalgo/openphysics/blob/main/docs/locales/ko/pages/index.md)

scipy Delaunay를 바탕으로 Python으로 작성한 제약 Delaunay 세분화(Ruppert 알고리즘)입니다. 영역을 빈틈없이 채우는 다각형과 원을 이름 있는 재료 영역으로 기술하면, 구멍도 허용하면서 최소각을 보장하는 적합 삼각형 메시를 반환합니다. 영역별 크기 제어, 삼각형별 영역 ID, 이름별 경계 변을 제공합니다.

numpy와 scipy에만 의존합니다. 외부 메시 생성기나 GPL 코드는 사용하지 않습니다.

```python
from meshine import Domain, Circle, generate, box_sides, rectangle

d = Domain(size=0.3)
d.add_region("core", rectangle(-1, 0, 1, 0.5), size=0.05)
d.add_region("clad", [(-3, -2), (3, -2), (3, 0.5), (1, 0.5), (1, 0), (-1, 0), (-1, 0.5), (-3, 0.5)])
d.add_region("clad", rectangle(-3, 0.5, 3, 2))
mesh = generate(d, box_sides(-3, 3, -2, 2), min_angle=28)

mesh.nodes            # (N, 2)
mesh.triangles        # (T, 3) counter-clockwise
mesh.regions          # (T,) index into mesh.region_names == ["core", "clad"]
mesh.boundary_edges   # {"left": (E, 2), "right": ..., "top": ..., "bottom": ...}
mesh.interfaces       # {("clad", "core"): (E, 2)}  edges between materials
mesh.min_angle(), mesh.quality(), mesh.region_area("core")
```

영역 사이의 공유 변과 T자 접합을 자동으로 처리합니다. 원은 정확하게 다룹니다. 세분화 중 원 경계에 삽입한 노드는 실제 원 위로 투영되므로 광섬유 코어가 실제로 둥글게 유지됩니다.

메시 생성기는 길이 단위를 알지 못하며 패키지 어디에도 절대 길이 상수가 없습니다. 점 병합과 경계 분류는 영역 경계 상자 대각선의 무차원 비율을 쓰고, 퇴화 검사는 삼각형 면적을 자체 변 길이와 비교합니다. 따라서 같은 단면을 마이크로미터 또는 킬로미터로 적어도 같은 형상을 생성합니다. 세분화의 반올림 차이 때문에 척도별 삼각형 수는 조금 달라도 되지만, 영역 면적, 각도 하한, 경계 이름은 유지됩니다.

```python
from meshine import shapes
d, namer = shapes.rib_waveguide(slab_thickness=0.3, size_core=0.1, size_far=0.5)   # Hadley 2002
mesh = generate(d, namer, size_fn=shapes.size_graded(0.1, 0.5, dist_max=3.0, center=(0, 0.5)))
mesh = generate(shapes.circular_fiber(core_radius=4.0, domain_radius=20.0, size_core=0.4))

d = Domain(size=0.3)                                  # PEC cylinder in a circular air domain
d.add_region("air", Circle((0, 0), 4.0), holes=[Circle((0, 0), 1.0)])
mesh = generate(d, lambda mid: "pec" if abs(complex(*mid)) < 2 else "abc")
```

## 동작 방식

각 반복에서 모든 점을 삼각분할(Qhull)합니다. 삼각분할에 없거나 지름을 기준으로 한 원 안에 다른 꼭짓점이 있는 입력 선분을 나눕니다. 다음으로 영역 내부에서 너무 가늘거나(각도 < `min_angle`) 너무 큰(외접반지름 > `size_factor * h`) 삼각형의 외심을 삽입합니다. 외심이 선분을 침범하면 대신 선분을 나눕니다. 나쁜 요소가 없어질 때까지 반복합니다. Ruppert 규칙에 따라 합리적인 입력(직각 형상에서는 약 30°까지)에 대해 요청한 각도 하한을 만족하며 종료합니다. 마지막 Laplacian 단계는 접한 삼각형을 악화시키지 않는 경우에만 내부 노드를 이동합니다.

점은 간격 필터를 적용해 묶어서 삽입하고, 매 반복 전체 점을 다시 삼각분할하므로 코드가 약 300줄로 유지됩니다. 10k개 삼각형의 리브 단면은 약 1초가 걸립니다.

## 자체 검증

```bash
# From the repository root
python -m pip install pytest -e packages/meshine
python -m pytest -q packages/meshine/tests
```

검사하는 특성은 다음과 같습니다. 다각형 영역 면적을 1e-9까지 재현하고 모든 삼각형 방향이 양수이며, 태그 경계가 정확히 하나의 삼각형에서만 쓰이는 변의 집합과 일치해야 합니다(빈틈이나 겹침 없이 닫힘). 재료 경계 변은 해당 두 재료의 삼각형이 하나씩 공유해야 합니다. 요청한 최소각이 유지되고, 변 길이는 영역별 크기 및 크기 함수를 따라야 합니다. 광섬유 경계 노드는 실제 원 위에 1e-12 이내로 놓이고 면적은 2차 수렴해야 합니다. 구멍은 비어 있어야 하며, 의도적으로 불규칙한 메시에서 매끄러운 함수의 변 중점 구적은 2차 수렴해야 합니다.

척도는 별도로 검사합니다. 열두 자릿수 범위의 다섯 길이 척도로 같은 장치를 기술했을 때 영역 면적 비율, 각도 하한, 경계 이름이 같아야 합니다. 척도 비율이 1.0이면 무의미한 비교로 판단해 각 비교를 실패시킵니다. 빈 메시가 나오면 `generate`는 0인 개수와 두 원인 중 어느 원인인지를 명시해 거절합니다. 빈 메시를 반환해 뒤쪽 축약 연산에서 뒤늦게 실패하도록 두지 않습니다.

`examples/compare_with_gmsh.py`는 같은 리브 도파로를 여기서 생성한 메시와 Gmsh(`gmshio` 경유) 메시로 나란히 그립니다. Gmsh Frontal-Delaunay가 여전히 더 높은 평균 품질(반지름비 0.98 대 0.93)과 매끄러운 크기 변화를 제공합니다. meshine이 보장하는 것은 각도 하한입니다.

## 한계

- 2D 전용입니다. 사면체 메시 생성은 다른 문제이므로 3D에는 `gmshio`를 통한 Gmsh를 사용하세요.
- 선분 사이 입력각이 약 60°보다 작으면 높은 `min_angle`에 도달하지 못할 수 있습니다. 하한을 낮추세요(Ruppert 증명이 다루는 값은 20.7°).
- 곡선 경계: 원은 내장되어 있습니다. 다른 곡선은 폴리라인으로 추가하거나 루프 객체에 `project` 메서드를 추가할 수 있습니다.

## 라이선스

Apache License 2.0 — [LICENSE](../../../../LICENSE), [NOTICE](../../../../NOTICE)를 참조하세요.

Copyright 2026 Yongha Kim (FieldAlgo)

