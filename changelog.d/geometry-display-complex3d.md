# Added

## English

- `simcase`: **`simcase.geometry_engine3d.display_complex3d(model, component=None)`**, the exact 3D complex of any `3d` component the boxes-and-slab-layers slice takes, for display: `evaluate3d`'s complex, and for a lone slab `layers` component (meshed on the `meshine.extrude` route) the complex the meshloom route would build. It meshes nothing; `build_mesh3d` is unchanged and still refuses a lone `layers` component for the extrude route. Checked: on the three-layer slab it returns the same cells and faces as the meshloom-route evaluation. [3D boxes and slab layers](docs/packages/simcase/geometry_engine3d.md#use).

## 한국어

- `simcase`: **`simcase.geometry_engine3d.display_complex3d(model, component=None)`** — 상자·판 층 슬라이스가 받는 모든 `3d` 구성 요소의 정확한 3D 영역 구성을 표시용으로 돌려줍니다. `evaluate3d`의 구성이며, 단독 판 `layers` 구성 요소(`meshine.extrude` 경로로 메시)에는 meshloom 경로가 만들 구성을 줍니다. 아무것도 메시하지 않고, `build_mesh3d`는 그대로여서 단독 `layers` 구성 요소를 압출 경로로 계속 거부합니다. 검사: 세 층 판에서 meshloom 경로 평가와 같은 셀과 면을 돌려줍니다. [3D 상자와 판 층](packages/simcase/geometry_engine3d.md#사용).
