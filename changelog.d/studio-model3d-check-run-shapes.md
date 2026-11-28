# Fixed

## English

- `simcase`: **the Studio 3D builder's check answers `run` for cylinders and spheres too (experimental).** For a component in a builder shape, `POST /api/model3d/check` now answers `run` the same way it does for boxes and layers. The answer is `{"ok": true}`, or the reader's refusal in its own words and code, such as *Fixed temperature needs an outer face; via.side is inside* (E-CONTRACT). Before this, that answer had no `run` key.

  [3D view](docs/packages/simcase/studio_3d.md#what-it-sends-and-answers).

## 한국어

- `simcase`: **Studio 3D 빌더의 검사가 원기둥과 구에도 `run`을 답합니다(실험적).** builder 형상의 구성 요소에도 `POST /api/model3d/check`가 상자와 층에서처럼 `run`을 답합니다. 답은 `{"ok": true}`이거나 reader의 말과 코드 그대로의 거부입니다(예: *Fixed temperature needs an outer face; via.side is inside*, E-CONTRACT). 이전에는 그 답에 `run` 키가 없었습니다.

  [3D 보기](packages/simcase/studio_3d.md#보내는-것과-응답).
