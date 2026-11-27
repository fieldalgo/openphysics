# Added

## English

- `simcase`: **extrudes of rect, trapezoid and polygon profiles in a `3d` component mesh through meshloom** (stage 5, slice 2; experimental until meshloom's acceptance), mixed freely with boxes and slab layers, later wins. Derived points (trapezoid corners, intersections of sloped edges) stay exact rationals until the hand-off, where each is rounded once (rule H1); a sloped side is one vertical quad per 2D edge piece, so no point is put into a sloped edge after rounding. Part names follow contract A4: `<id>.bottom` and `<id>.top` on the caps, `left`, `right`, `y0` and `y1` on a rect or trapezoid's sides, `e1` … `eN` or the `edges` names on a polygon's. An extruded circle (a cylinder) is refused by name until slice 3; the refusal of cylinders and spheres now lists extrudes among what is taken. `build_mesh3d`, `display_complex3d` and `thermal.steady3d` take extrudes with no change of their own; boxes-only and slab-only components give byte-identical complexes and meshes. [3D boxes, slab layers and extrudes](docs/packages/simcase/geometry_engine3d.md).

## 한국어

- `simcase`: **`3d` 구성 요소의 사각형·사다리꼴·다각형 프로파일 압출을 meshloom으로 메시**(5단계 슬라이스 2, meshloom 수용 전까지 실험 단계). 상자, 판 층과 자유롭게 섞으며 나중 피처가 이깁니다. 유도된 점(사다리꼴 꼭짓점, 기울어진 변의 교점)은 넘기기 전까지 정확한 유리수로 남고, 넘길 때 한 번만 반올림합니다(규칙 H1). 기울어진 옆면은 2D 변 조각마다 수직 사각형 하나이므로 반올림한 뒤 기울어진 변 안에 점을 넣지 않습니다. 부분 이름은 계약 A4를 따릅니다. 뚜껑은 `<id>.bottom`과 `<id>.top`, 사각형·사다리꼴 옆면은 `left`, `right`, `y0`, `y1`, 다각형 옆면은 `e1` … `eN` 또는 `edges` 이름입니다. 원의 압출(원통)은 슬라이스 3까지 이름을 밝혀 거부하며, 원통과 구의 거부 메시지가 받는 것에 압출을 더합니다. `build_mesh3d`, `display_complex3d`, `thermal.steady3d`는 따로 바뀌지 않고 압출을 받으며, 상자만 또는 판 층만 있는 구성 요소의 구성과 메시는 바이트까지 같습니다. [3D 상자, 판 층, 압출](packages/simcase/geometry_engine3d.md).
