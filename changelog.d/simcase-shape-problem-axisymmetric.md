# Added

## English

- `simcase`: **`shape_problem` takes axisymmetric heat documents.** A `thermal.steady2d` or `thermal.transient2d` document on an `axisymmetric` component gives its shape derivative with `coordinate_system="axisymmetric"`, as `run` solves it. Nodes on the symmetry axis keep a zero radial velocity: the radial component is extended again with them held at 0. A design that moves a point of the axis off it is refused by name; an axisymmetric component of another physics stays refused. Checked (SA1-SA6, pre-registered): a two-layer hollow cylinder's inner-layer thickness converges to the closed-form series rate at order 2.0 (2.5e-4 on the finest mesh); on a solid cylinder the axis nodes keep W_r = 0 exactly; steady and transient derivatives match same-mesh central differences within 1.9e-9 and 3.0e-9; the solve at t = 0 equals `run` within 1e-12. [Design velocity](docs/packages/simcase/geometry_engine.md#design-velocity-stage-4).

## 한국어

- `simcase`: **`shape_problem`이 축대칭 열 문서를 받습니다.** `axisymmetric` 성분의 `thermal.steady2d`·`thermal.transient2d` 문서는 `run`처럼 `coordinate_system="axisymmetric"`으로 형상 미분을 줍니다. 대칭축 위 노드는 반지름 속도 0을 유지합니다. 반지름 성분을 그 노드들을 0으로 둔 채 다시 확장합니다. 축 위의 점을 축 밖으로 움직이는 설계는 이름을 밝혀 거부하며, 다른 물리의 축대칭 성분은 계속 거부합니다. 검사(SA1-SA6, 사전 등록): 두 층 속 빈 원통의 안쪽 층 두께 미분이 닫힌 직렬 열량으로 차수 2.0으로 수렴하고(가장 고운 메시 2.5e-4), 속 찬 원통에서 축 노드의 W_r이 정확히 0이며, 정상·과도 미분이 같은 메시 중앙 차분과 1.9e-9, 3.0e-9 이내이고, t = 0 풀이가 `run`과 1e-12 이내로 같습니다. [설계 속도](packages/simcase/geometry_engine.md#설계-속도-4단계).
