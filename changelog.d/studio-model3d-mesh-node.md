# Added

## English

- `simcase`: **Mesh 1 in the Studio workspace's 3D model (experimental).** The 3D model's tree gains Mesh 1 with the server's estimate ("size 40 µm · Estimate 2,400 tetrahedra · about 1 s"). Its page edits the mesh block's `element_size`, and Mesh runs Studio's cancellable mesh job (the steps, the elapsed time, Cancel meshing, then the mesh view coloured by region) through the existing mesh routes. A refusal before meshing (E-MESH-ESTIMATE, below tolerance, rounding) is shown in Messages with its code, marks the feature or Mesh 1 and disables Mesh with its words, without greying the shape. Run's reason is now "Heat comes in a later step of the 3D model.". The mesh is not kept in Undo or files. Checks: W5 3/3 before meshing, W9 3/3 through the workspace, W12 for the mesh view at 1440 × 900 and 390 × 844, and W13 by keyboard with mesh, cancel and mesh again (0 pointer events).

  [3D models](docs/packages/simcase/workspace.md#3d-models-experimental).

## 한국어

- `simcase`: **Studio 작업 공간 3D 모델의 Mesh 1(실험적).** 3D 모델 트리에 서버 추정("size 40 µm · Estimate 2,400 tetrahedra · about 1 s")이 붙은 Mesh 1이 더해집니다. 그 페이지는 mesh 블록의 `element_size`를 편집하고, Mesh는 기존 메시 경로로 Studio의 취소할 수 있는 메시 작업(단계, 경과 시간, Cancel meshing, 그다음 영역별 색의 메시 보기)을 실행합니다. 메시 전 거부(E-MESH-ESTIMATE, 허용 오차 아래, 반올림)는 Messages에 코드와 함께 보이고, 특징이나 Mesh 1을 표시하며, 형상을 흐리게 하지 않고 그 말로 Mesh를 끕니다. Run의 이유는 이제 "Heat comes in a later step of the 3D model."입니다. 메시는 Undo와 파일에 남지 않습니다. 검사: 메시 전 W5 3/3, 작업 공간을 거친 W9 3/3, 1440 × 900과 390 × 844에서 메시 보기의 W12, 메시·취소·다시 메시를 키보드로 하는 W13(포인터 이벤트 0).

  [3D 모델](packages/simcase/workspace.md#3d-모델실험적).
