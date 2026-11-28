# Added

## English

- `simcase`: **Studio's card 2 shows the expected heat rate beside the run's (experimental).** On Copper via through a slab, a run's values now show *Expected heat rate 31.99 W (parallel formula)* next to *Heat rate through z0*. The formula is Q = ΔT/L · (k_v·πr² + k_s·(A − πr²)), computed from the run's document. The line appears only where the formula applies: one cylinder through the whole slab height, fixed temperatures on exactly `z0` and `z1`, and no heat source. Otherwise there is no line. The run's own values are unchanged.

  [3D models](docs/packages/simcase/workspace.md#3d-models-experimental).

## 한국어

- `simcase`: **Studio의 카드 2가 실행의 열률 옆에 예상 열률을 보입니다(실험적).** Copper via through a slab에서 실행의 값이 이제 *Heat rate through z0* 옆에 *Expected heat rate 31.99 W (parallel formula)*를 보입니다. 식은 Q = ΔT/L · (k_v·πr² + k_s·(A − πr²))이며 실행의 문서에서 계산합니다. 이 줄은 식이 맞는 경우에만 보입니다: 슬래브 높이 전체를 지나는 원기둥 하나, 정확히 `z0`과 `z1`의 고정 온도, 열원 없음. 아니면 줄이 없습니다. 실행 자신의 값은 그대로입니다.

  [3D 모델](packages/simcase/workspace.md#3d-모델실험적).
