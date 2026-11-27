# Changed

## English

- `simcase`: **`build_mesh3d` refuses pieces of a 3d component's arrangement below the mesher tolerance before the hand-off to meshloom**, as the parser already refuses whole features: the contract's "What the grid does not fix" (`MESHER_RELATIVE_TOLERANCE` = 3e-8 of the bounding-box diagonal). The pieces are the distance from a 2D vertex to a fine curve that does not end there (a short curve or a thin neck), the height of a slab that a meshed side spans, and the width of a meshed horizontal face. Code `E-CONTRACT` at `geometry.components.<name>`, with the parser's sentence and the later feature whose part bounds the piece. Documents without such pieces mesh as before. New limit noted: pieces just above the tolerance (about 1e-7 of the diagonal and thinner) can make meshloom not return. [3D boxes and slab layers](docs/packages/simcase/geometry_engine3d.md#what-it-refuses).

## 한국어

- `simcase`: **`build_mesh3d`가 메시 생성기 허용 오차 아래인 `3d` 구성 요소의 배열 조각을 meshloom에 넘기기 전에 거부**합니다. 파서가 피처 전체를 이미 거부하는 것과 같은 계약 규칙("격자가 해결하지 않는 것", 경계 상자 대각선의 `MESHER_RELATIVE_TOLERANCE` = 3e-8)입니다. 조각은 2D 꼭짓점에서 그 점에서 끝나지 않는 곡선까지의 거리(짧은 곡선이나 얇은 목), 메시되는 옆면이 걸친 판 구간의 높이, 메시되는 수평면의 폭입니다. `geometry.components.<name>`에서 코드 `E-CONTRACT`로, 파서와 같은 문장과 조각을 이루는 부분의 나중 피처 이름을 냅니다. 그런 조각이 없는 문서는 전처럼 메시합니다. 새 한계: 허용 오차를 조금 넘는 조각(대각선의 약 1e-7 이하)은 meshloom이 돌아오지 않게 할 수 있습니다. [3D 상자와 판 층](packages/simcase/geometry_engine3d.md#거부하는-것).
