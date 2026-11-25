# Fixed

## English

- `meshloom`: **in parity mode an open surface whose points all lie in one plane is `NotClosed`, with its type-6 witness.** Before, boundary recovery failed on it first and raised `RecoveryError` without a witness: one triangle, for example. Parity mode now asks whether the surface is closed from the input check, before recovery. The witness is an elementary segment (no input point inside it) on the boundary of an odd number of facets. Closed inputs and regions mode are unchanged. [meshloom overview](docs/packages/meshloom/overview.md).

## 한국어

- `meshloom`: **parity 모드에서 모든 점이 한 평면에 놓인 열린 표면은 이제 유형 6 근거가 붙은 `NotClosed`입니다.** 전에는 경계 복원이 먼저 실패해 근거 없는 `RecoveryError`를 냈습니다(예: 삼각형 하나). 이제 parity 모드는 복원 전에 입력 검사로 표면이 닫혔는지 판정합니다. 근거는 홀수 개 면의 경계에 놓인 기본 선분(안에 입력 점이 없음)입니다. 닫힌 입력과 regions 모드는 그대로입니다. [meshloom 개요](packages/meshloom/overview.md).
