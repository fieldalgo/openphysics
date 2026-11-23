# Fixed

## English

- Studio: **a Width that would push a rectangle out of the window keeps its left edge.** Typing Left x −1500 and then Width 3000 was refused, because the centred 3000 nm shape left the window, and retyping Left x did not clear the error. A Width now keeps the centre when that fits, else the left edge (*Width set to 3000 nm. Left x kept at −1500 nm: centred, the shape would leave the window.*), computed from the shape when the field took focus; a refused value is tried again when another value of the same shape changes. T16's entry order (Name, Left x −1500, Bottom y −1200, Width 3000, Height 700) gives a 3000 × 700 nm rectangle at (−1500, −1200), in a unit test and typed key by key in the browser check. [Workspace](docs/packages/simcase/workspace.md).

## 한국어

- Studio: **사각형을 계산창 밖으로 밀어낼 Width는 왼쪽 변을 지킵니다.** Left x −1500 다음 Width 3000을 입력하면 가운데를 지킨 3000 nm 형상이 창을 벗어나 거부되었고, Left x를 다시 입력해도 오류가 남았습니다. 이제 Width는 들어가면 가운데를, 아니면 왼쪽 변을 지키며(*Width set to 3000 nm. Left x kept at −1500 nm: centred, the shape would leave the window.*), 입력란에 포커스가 들어왔을 때의 형상에서 계산합니다. 거부된 값은 같은 형상의 다른 값이 바뀔 때 다시 시도합니다. T16 입력 순서(Name, Left x −1500, Bottom y −1200, Width 3000, Height 700)는 단위 테스트와 브라우저 검사의 한 글자씩 입력 모두에서 (−1500, −1200)에 놓인 3000 × 700 nm 사각형이 됩니다. [워크스페이스](packages/simcase/workspace.md).
