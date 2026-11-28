# Added

## English

- `simcase`: **`simcase.display_shapes3d(model, component=None)`** returns a `Display3D`, the display shape of a `3d` component whose cylinders or spheres are in a meshloom builder shape (C4, C5, C1, C11; experimental). Each face's name set is the mesh's provenance names of the triangles it stands for; planar faces are exact, cylinder rings, discs and annuli use the inscribed n-gon (n = min(256, max(48, ⌈2πr/ℓ⌉)), ℓ = diagonal / 200), spheres an icosahedral geodesic grid (f = min(64, max(8, ⌈1.05 r/ℓ⌉))); regions carry exact volumes and `section(axis, at_pm)` exact outlines. What no builder takes is refused in the builder's words; `display_complex3d`, `evaluate3d` and `build_mesh3d` are unchanged. Checks W1(b) (0 off-plane vertices) and W2 (display areas within their pre-registered bounds). [Display shape](docs/packages/simcase/geometry_engine3d.md#display-shape).

## 한국어

- `simcase`: **`simcase.display_shapes3d(model, component=None)`**는 원통이나 구가 meshloom builder 모양(C4, C5, C1, C11)인 `3d` 구성 요소의 표시 모양 `Display3D`를 돌려줍니다(실험적). 면마다 이름 집합은 그 면이 대신하는 메시 삼각형의 출처 이름입니다. 평면은 정확하고, 원통 고리·원판·고리 모양 면은 내접 n각형(n = min(256, max(48, ⌈2πr/ℓ⌉)), ℓ = 대각선 / 200), 구는 정이십면체 측지 격자(f = min(64, max(8, ⌈1.05 r/ℓ⌉)))입니다. 영역은 정확한 부피를, `section(axis, at_pm)`은 정확한 윤곽을 줍니다. 어느 builder도 받지 않는 것은 builder의 문구로 거부하며, `display_complex3d`, `evaluate3d`, `build_mesh3d`는 그대로입니다. 검사 W1(b)(평면 밖 꼭짓점 0)와 W2(표시 넓이가 미리 정한 한계 안). [표시 모양](packages/simcase/geometry_engine3d.md#표시-모양).
