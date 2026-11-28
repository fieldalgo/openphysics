# Added

## English

- `simcase`: **The Studio 3D view draws, meshes and runs cylinders and spheres in meshloom's builder shapes (experimental).** The display, section and check answers of such a component come from `simcase.display_shapes3d` (each face gains `shape`, a curved face has `axis` and `at` null, the answer gains `display_note`); every other component keeps its answers. The mesh job maps each builder mesh triangle to the display face of its provenance names, and the card `model3d-via-slab-3d.json` (stage 5's E2) runs through `POST /api/model3d/run`. Checks W1(a) (0 mismatches on C1, C4, C5, C11 and the card) and W18 (e_Q = 7.51e-3 against 1e-2 at h = 0.1; Q_h, T and reaction identical by SHA-256 to `build_mesh3d` + `galerkin.solve_steady_heat_3d`). [3D view](docs/packages/simcase/studio_3d.md#cylinders-and-spheres).

## 한국어

- `simcase`: **Studio 3D 보기가 meshloom builder 모양의 원통과 구를 그리고, 메시하고, 풉니다(실험적).** 그런 구성 요소의 표시, 단면, 검사 응답은 `simcase.display_shapes3d`에서 옵니다(면마다 `shape`가 붙고, 곡면은 `axis`와 `at`이 null이며, 응답에 `display_note`가 붙음). 다른 구성 요소의 응답은 그대로입니다. 메시 작업은 builder 메시 삼각형마다 그 출처 이름의 표시 면을 붙이고, 카드 `model3d-via-slab-3d.json`(5단계의 E2)은 `POST /api/model3d/run`으로 풉니다. 검사 W1(a)(C1, C4, C5, C11과 카드에서 불일치 0)와 W18(h = 0.1에서 e_Q = 7.51e-3, 기준 1e-2; Q_h, T, 반작용이 `build_mesh3d` + `galerkin.solve_steady_heat_3d`와 SHA-256으로 같음). [3D 보기](packages/simcase/studio_3d.md#원통과-구).
