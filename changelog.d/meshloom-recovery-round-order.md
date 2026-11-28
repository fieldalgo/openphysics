# Fixed

## English

- meshloom: **segment recovery orders a round's split points by coordinates before inserting them in BRIO order.** The order came from segment numbers, so renumbering an input's points (as a mesh file loader does) could change the mesh where the first Delaunay tetrahedralization did not: the 1e5-face needle readiness input had 2 facets over V3(a)'s area bound in one numbering and 6 in the other. Meshes change.

## 한국어

- meshloom: **선분 복원이 한 라운드의 분할점을 BRIO 순서로 넣기 전에 좌표로 정렬합니다.** 그동안은 순서가 선분 번호에서 나왔습니다. 그래서 입력 점의 번호만 바꿔도(메시 파일 로더처럼) 첫 Delaunay 분할은 그대로인데 메시가 바뀔 수 있었습니다. 면 1e5개짜리 needle 사전 점검 입력은 한 번호에서 V3(a) 면적 한계를 넘는 facet이 2개, 다른 번호에서 6개였습니다. 메시가 바뀝니다.
