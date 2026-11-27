# Changed

## English

- `simcase`: **the Studio 3D builder's check answers the mesh estimate (experimental).** `POST /api/model3d/check` now also calls `simcase.estimate_mesh3d` and answers under `mesh` the estimate and the mesh job's reuse key, or the refusal that blocks meshing (E-MESH-ESTIMATE, a below-tolerance E-CONTRACT, two values rounding to one coordinate) with its code, path and `features[i]`. The shape is formed either way, so the answer stays `ok`. Checks: W5 extended to these three stems (3/3) and W9 through the check (3/3: no job started by a check, 1.5 times the limit refused, the estimate equal to `/api/model3d/mesh/estimate`).

  [3D view](docs/packages/simcase/studio_3d.md#what-it-sends-and-answers).

## 한국어

- `simcase`: **Studio 3D 빌더의 검사가 메시 추정을 답합니다(실험적).** `POST /api/model3d/check`가 이제 `simcase.estimate_mesh3d`도 불러, `mesh` 아래에 추정과 메시 작업의 재사용 키, 또는 메시를 막는 거부(E-MESH-ESTIMATE, 허용 오차 아래의 E-CONTRACT, 한 좌표로 반올림되는 두 값)를 코드, 경로, `features[i]`와 함께 답합니다. 어느 쪽이든 형상은 만들어지므로 응답은 `ok`로 남습니다. 검사: 이 세 줄기로 넓힌 W5(3/3)와 검사를 거친 W9(3/3: 검사는 작업을 시작하지 않음, 한도의 1.5배는 거부, 추정이 `/api/model3d/mesh/estimate`와 같음).

  [3D 보기](packages/simcase/studio_3d.md#보내는-것과-응답).
