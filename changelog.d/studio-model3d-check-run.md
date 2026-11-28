# Changed

## English

- `simcase`: **the Studio 3D builder's check says whether Run would take the document (experimental).** `POST /api/model3d/check` also answers `run`: the document read as `POST /api/model3d/run` reads it before starting anything (`heat3d_runs.read_document`, now shared by both), `{"ok": true}` or the reader's refusal in its own words and code. A check starts no run, mesh job or process.

  [3D view](docs/packages/simcase/studio_3d.md#what-it-sends-and-answers).

## 한국어

- `simcase`: **Studio 3D 빌더의 검사가 Run이 문서를 받을지 알려 줍니다(실험적).** `POST /api/model3d/check`가 `run`도 답합니다: `POST /api/model3d/run`이 무엇이든 시작하기 전에 읽는 대로 읽은 문서(`heat3d_runs.read_document`, 이제 둘이 함께 씀), `{"ok": true}` 또는 reader의 말과 코드 그대로의 거부. 검사는 실행, 메시 작업, 프로세스를 시작하지 않습니다.

  [3D 보기](packages/simcase/studio_3d.md#보내는-것과-응답).
