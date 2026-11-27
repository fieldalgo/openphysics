# Added

## English

- `simcase`: **the Studio 3D builder's server check (experimental).**
  - `POST /api/model3d/check` answers per feature its coverage, computed exactly from the complex: "covered in part by 2 (via)" or "covered by 2 (b), 3 (c); adds no region". It also gives the parameters with their SI values and the fields that use them, the selections, and the display answer.
  - A refusal carries the engine's message as written, its code, path and `features[i]`.
  - `POST /api/model3d/selection` turns a picked face into a new selection named by the one provenance name that selects it alone.
  - The card document "Via in a layer stack (3D heat)" ships with Studio.
  - Checks: W4 server part (10 listed faces, the written selection and the hand-typed one resolve through `build_mesh3d` to the picked face's mesh faces, 10/10) and W5 server part (every E-3D-COMBINATION stem the check can raise).

  [3D view](docs/packages/simcase/studio_3d.md#what-it-sends-and-answers).

## 한국어

- `simcase`: **Studio 3D 빌더의 서버 검사(실험적).**
  - `POST /api/model3d/check`는 기능마다 복합체로 정확히 계산한 덮임 상태("covered in part by 2 (via)", "covered by 2 (b), 3 (c); adds no region")를 답합니다. SI 값과 쓰는 필드를 함께 준 파라미터, 선택, 표시 응답도 줍니다.
  - 거부에는 엔진 메시지 그대로와 코드, 경로, `features[i]`가 실립니다.
  - `POST /api/model3d/selection`은 고른 면을 그 면만 고르는 출처 이름으로 된 새 선택으로 바꿉니다.
  - 카드 문서 "Via in a layer stack (3D heat)"가 Studio에 들어 있습니다.
  - 검사: W4 서버 부분(나열한 면 10개에서 만든 선택과 손으로 적은 선택이 `build_mesh3d`로 고른 면의 메시 면과 같음, 10/10), W5 서버 부분(검사가 낼 수 있는 E-3D-COMBINATION 문구 전부).

  [3D 보기](packages/simcase/studio_3d.md#보내는-것과-응답).
