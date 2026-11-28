# Changed

## English

- `simcase`: **Studio 3D's results say what their numbers mean (experimental).**
  - One line under the values states the sign of a heat rate: positive into the model, negative out of it.
  - Tmax and Tmin are labelled *(whole model)*, and the colour bar is titled *Surface temperature*, since the surface range can be narrower than the whole model's.
  - On a run this Studio holds, an extreme at a node shared by two regions reads *at the SiO2 / Si (top) interface*: the new HTTP view `GET /api/model3d/runs/{id}/extremes` names the regions around the node. `/values` and the exports are unchanged. The stored run record is unchanged, so a run opened from a file reads *in SiO2* until it is recomputed.

  [3D models](docs/packages/simcase/workspace.md#3d-models-experimental).

## 한국어

- `simcase`: **Studio 3D의 결과가 수의 뜻을 밝힙니다(실험적).**
  - 값 아래 한 줄이 열률의 부호를 밝힙니다: 모델로 들어오면 양수, 나가면 음수.
  - Tmax와 Tmin에는 *(whole model)*이 붙고, 색 막대의 제목은 *Surface temperature*입니다. 면의 범위가 모델 전체보다 좁을 수 있기 때문입니다.
  - 이 Studio가 가진 실행에서 두 영역이 나누는 노드의 극값은 *at the SiO2 / Si (top) interface*로 읽힙니다: 새 HTTP 보기 `GET /api/model3d/runs/{id}/extremes`가 노드 둘레의 영역을 밝힙니다. `/values`와 내보내기는 그대로입니다. 저장된 실행 기록은 그대로이므로, 파일에서 연 실행은 다시 계산할 때까지 *in SiO2*로 읽힙니다.

  [3D 모델](packages/simcase/workspace.md#3d-모델실험적).
