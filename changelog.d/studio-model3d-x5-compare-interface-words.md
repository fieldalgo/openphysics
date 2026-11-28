# Fixed

## English

- `simcase`: **Studio 3D Compare reads Tmax and Tmin as the run table does (experimental).**
  - For a run the server holds, Compare's Tmax and Tmin now read like that run's table, for example *363.756 K at the SiO2 / Si (top) interface, (38.5, 163, 510) µm*.
  - A run opened from a file still reads *in <region>*, since its record keeps no region list.

  [3D models](docs/packages/simcase/workspace.md#3d-models-experimental).

## 한국어

- `simcase`: **Studio 3D Compare가 Tmax와 Tmin을 실행 표처럼 읽습니다(실험적).**
  - 서버가 가진 실행에서 Compare의 Tmax와 Tmin은 이제 그 실행 표처럼 읽힙니다. 예: *363.756 K at the SiO2 / Si (top) interface, (38.5, 163, 510) µm*.
  - 파일에서 연 실행은 기록에 영역 목록이 없으므로 여전히 *in <영역>*으로 읽힙니다.

  [3D 모델](packages/simcase/workspace.md#3d-모델실험적).
