# 연성 층과 커널 인터페이스

[English](../../../../../packages/galerkin/coupling.md) | **한국어**

`galerkin.coupling`은 한 물리의 값을 다음 물리로 넘깁니다. 한 물리를 푸는 솔버(*커널*)가
다른 커널이 결과를 받아 쓰도록 무엇을 내놓아야 하는지 정합니다. 이 패키지의 유한요소 엔진이
이 계약 뒤에 놓인 첫 커널입니다. API는 0.x 동안 바뀔 수 있습니다
([안정성](../../changelog.md#0x의-안정성)).

```python
import numpy as np
from galerkin.coupling import Field, OneWayChain, transfer
from galerkin.mesh import rectangle_mesh

mesh = rectangle_mesh(.02, .01, 4, 2)  # metres
temperature = Field(mesh, np.full(mesh.num_nodes, 300.), location="node", unit="K")
same = transfer(temperature, mesh)     # identity on the same mesh
```

## 메시 계약

커널은 `galerkin.mesh.Mesh`에서 동작합니다. 2D 선형(P1) 삼각형이고 좌표는 SI 미터입니다.
`MeshSignature`가 일치하면 두 메시는 연성에서 같은 메시입니다.

- 절점 좌표가 허용오차 없이 정확히 같습니다.
- 삼각형 연결이 같습니다. 삼각형 순서와 각 삼각형 안의 절점 순서도 같아야 합니다.
- 기본으로 삼각형 영역 번호와 영역 이름도 같아야 합니다. `regions=False`는 기하와 연결만 비교합니다.

경계 태그는 signature에 들어가지 않습니다. 각 물리는 공유 메시 위에 자기 경계조건을 둡니다.
메시를 정확히 같게 복사한 것은 일치합니다. 그 밖의 메시는 다른 메시입니다.

## Field 계약

`Field`는 만들 때 쓴 메시의 signature에 묶입니다.

| 항목 | 계약 |
|---|---|
| `location` | `"node"`: 메시 절점마다 값 하나, 모양 (N,). `"element"`: 삼각형마다 그 위에서 일정한 값 하나, 모양 (M,). |
| `values` | 읽기 전용 float64 사본이며 유한한 실수입니다. 불리언·복소수·비수치·비유한·범위 초과 값은 `ValueError`를 냅니다. |
| `unit` | 비어 있지 않은 SI 단위 문자열입니다. 예: `"K"`, `"W/m^3"`. 기록만 하고 변환하거나 추정하지 않습니다. |
| 배열 라이브러리 | NumPy만 받습니다. JAX·PyTorch 배열은 `TypeError`를 냅니다. 물리 사이의 field가 미분을 끊기 때문입니다. |

선택 인자 `name`은 이 오류 메시지에서 값을 부르는 이름입니다. `Field.on_mesh(mesh)`는 signature를
확인한 뒤 값을 돌려주고, 메시가 다르면 호출한 쪽의 메시지로 `ValueError`를 냅니다.

## 전달

`transfer(field, mesh)`는 값·location·단위가 같고 `mesh`에 묶인 field를 돌려줍니다. 같은 메시에서는
항등입니다. 다른 메시는 `ValueError`를 냅니다. 메시 사이의 보간·평균·투영은 없습니다. 격자와 메시
사이의 보존 투영은 둘째 커널과 함께 계획되어 있고 아직 없습니다.

## 한 방향 체인

`OneWayChain(error)`는 한 방향 workflow의 단계를 차례로 실행합니다.

```python
chain = OneWayChain(lambda stage, exc, **context: RuntimeError(f"[{stage}] {exc}"))
with chain.stage("heat"):
    ...
with chain.stage("mechanics", time_index=3):
    ...
chain.completed  # ("heat", "mechanics")
```

실패한 단계는 `error(stage, exc, **context)`가 만든 예외를 원래 원인에 연결해 냅니다. 끝난 단계는
순서대로 기록됩니다. 체인에는 반복이나 되먹임이 없습니다. 고정점 연성(예:
[온도 의존 Joule 가열](temperature_joule_heating.md))은 자기 반복을 그대로 갖습니다.

## 한계

- 2D P1 삼각형 메시만 다룹니다. 3D 메시(`Mesh3D`)와 변(Nédélec) 장은 이 층의 field가 아닙니다.
- 같은 메시만 다룹니다. 메시↔메시, 격자↔메시 전달은 없습니다.
- NumPy만 다룹니다. 미분은 field를 건너가지 않습니다.
- 한 방향만 다룹니다. 일반 고정점 드라이버는 없습니다.

기존 workflow([Joule heating](joule_heating.md),
[온도 의존 Joule heating](temperature_joule_heating.md),
[정상 열→역학](thermal_mechanical_workflow.md),
[과도 열→역학](transient_thermal_mechanical.md))는 각자의 계약을 유지합니다.
