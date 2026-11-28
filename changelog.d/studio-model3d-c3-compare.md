# Added

## English

- `simcase`: **Studio 3D compares two runs of the same 3D model (experimental).** With a 3D model shown, the Compare tab sets two kept runs side by side, Run A and Run B (the two newest at first).
  - A values table shows Tmax, Tmin, each fixed temperature's heat rate, the total source, the balance residual and the mesh, with B − A.
  - *Inputs that differ* lists the changed document fields in the tree's words.
  - On a shared mesh the view colours the surface temperature difference B − A, with its own legend. Runs share a mesh when their records have the same geometry+mesh digest and the same node and tetrahedron counts.
  - On different meshes a notice says the values are compared but the surface temperature is not compared point by point.

  Everything is read from the two run records. The pair is view state, and the project and session formats are unchanged. As an analytical reference, raising every fixed temperature of card 2 by 10 K shifts the field by 10 K to 9.1e-13 K.

  [3D models](docs/packages/simcase/workspace.md#3d-models-experimental).

## 한국어

- `simcase`: **Studio 3D가 같은 3D 모델의 두 실행을 비교합니다(실험적).** 3D 모델이 보일 때 Compare 탭은 보관한 실행 둘, Run A와 Run B를 나란히 놓습니다(처음에는 가장 새로운 둘).
  - 값 표는 Tmax, Tmin, 고정 온도마다의 열률, 전체 열원, 수지 잔차, 메시를 B − A와 함께 보입니다.
  - *Inputs that differ*는 바뀐 문서 칸을 트리의 말로 나열합니다.
  - 메시를 공유하면 보기는 면 온도 차 B − A를 자기 범례와 함께 칠합니다. 두 실행은 기록의 geometry+mesh 다이제스트와 노드·사면체 수가 같으면 메시를 공유합니다.
  - 메시가 다르면 값은 비교하지만 면 온도는 점마다 비교하지 않는다는 알림이 보입니다.

  모든 것은 두 실행 기록에서 읽습니다. 짝은 보기 상태이며, 프로젝트와 세션 형식은 바뀌지 않습니다. 해석적 기준으로, 카드 2의 모든 고정 온도를 10 K 올리면 장이 9.1e-13 K 안에서 10 K 이동합니다.

  [3D 모델](packages/simcase/workspace.md#3d-모델실험적).
