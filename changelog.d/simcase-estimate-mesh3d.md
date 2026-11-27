# Added

## English

- `simcase`: **`simcase.estimate_mesh3d(document, component=None)` gives the `I-MESH-ESTIMATE` of a `3d` component without meshing it (experimental).** It runs exactly what `build_mesh3d` runs before meshloom, so the estimate T = 6.3 Σ V_r / h_r³, the diagnostic and every refusal that blocks meshing (`E-MESH-ESTIMATE` above `mesh.element_count_limit`, `E-CONTRACT`, `E-3D-COMBINATION`) are `build_mesh3d`'s, in the same words. The result, `Mesh3DEstimate`, holds the component, T as an integer, the limit, the expected seconds at 0.6 ms per tetrahedron and the diagnostic. [3D boxes and slab layers](docs/packages/simcase/geometry_engine3d.md#use).

## 한국어

- `simcase`: **`simcase.estimate_mesh3d(document, component=None)`가 `3d` 구성 요소를 메시하지 않고 `I-MESH-ESTIMATE`를 줍니다(실험적).** `build_mesh3d`가 meshloom 전에 돌리는 것을 그대로 돌리므로, 추정 T = 6.3 Σ V_r / h_r³, 진단, 메시를 막는 모든 거부(`mesh.element_count_limit`를 넘을 때의 `E-MESH-ESTIMATE`, `E-CONTRACT`, `E-3D-COMBINATION`)가 같은 문구로 `build_mesh3d`의 것과 같습니다. 결과 `Mesh3DEstimate`는 구성 요소, 정수 T, 한도, 사면체당 0.6 ms로 본 예상 초, 진단을 담습니다. [3D 상자와 판 층](packages/simcase/geometry_engine3d.md#사용).
