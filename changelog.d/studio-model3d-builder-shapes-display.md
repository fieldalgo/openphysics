# Added

## English

- `simcase`: **Studio's 3D view draws cylinders and spheres in meshloom's builder shapes (experimental).** `simcase.display_shapes3d(model, component)` draws a component the exact complex does not take yet by a display rule that is not the mesh: planar faces exactly, circles as inscribed n-gons (n = min(256, max(48, ⌈2πr/ℓ⌉)), ℓ = diagonal/200), a cylinder side as their prism and a sphere as a geodesic grid of frequency min(64, max(8, ⌈1.05 r/ℓ⌉)), with the mesh's face names and tags, exact areas and volumes and exact axis-plane sections. The display, section and check answers take such components (curved faces with `axis` and `at` null, `shape` on every face, `display_note`); Mesh and Run take them too, the mesh view mapping each mesh triangle to the face of its name set. Card 2, `via-slab-3d` (E2 of stage 5), is served beside card 1. Checks W1 and W2 for the shapes and W18 (card 2 through the run route: e_Q 7.51e-3, bit-identical to the direct path) pass. [3D view, cylinders and spheres](docs/packages/simcase/studio_3d.md#cylinders-and-spheres).

## 한국어

- `simcase`: **Studio 3D 보기가 meshloom builder 모양의 원통과 구를 그립니다(실험적).** `simcase.display_shapes3d(model, component)`가 정확한 구성이 아직 받지 않는 구성 요소를 메시가 아닌 표시 규칙으로 그립니다. 평면 면은 정확히, 원은 내접 n각형(n = min(256, max(48, ⌈2πr/ℓ⌉)), ℓ = 대각선/200), 원통 옆면은 그 각기둥, 구는 주파수 min(64, max(8, ⌈1.05 r/ℓ⌉))의 측지 격자이며, 면 이름과 태그는 메시의 것, 넓이와 부피와 축 평면 단면은 정확합니다. 표시, 단면, 확인 응답이 그런 구성 요소를 받고(곡면은 `axis`와 `at`이 null, 모든 면에 `shape`, `display_note`), Mesh와 Run도 받으며 메시 보기는 메시 삼각형마다 이름 집합이 같은 면을 줍니다. 카드 2 `via-slab-3d`(5단계 E2)를 카드 1 옆에 둡니다. 모양의 W1, W2와 W18(실행 경로를 거친 카드 2: e_Q 7.51e-3, 직접 경로와 비트까지 같음)이 통과합니다. [3D 보기, 원통과 구](packages/simcase/studio_3d.md#원통과-구).
