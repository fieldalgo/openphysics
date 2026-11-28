# Changed

## English

- `meshloom` documentation: **a mesh depends on how the input is numbered**, now stated in the overview's limits. The same arrays give the same mesh, bit for bit (V26), but the same points and facets numbered differently can give a different, equally valid mesh: Delaunay ties are broken by point index, and boundary recovery follows the numbering. Counts taken on the mesh, such as V3 bound failures, can differ with it, so results are compared on the same arrays; C14 measures the loader's canonical arrays. [meshloom limits](docs/packages/meshloom/overview.md#limits).

## 한국어

- `meshloom` 문서: **메시가 입력의 번호 매김에 의존한다는 점**을 개요의 한계에 적었습니다.
  - 같은 배열은 비트 단위로 같은 메시를 냅니다(V26).
  - 같은 점과 facet이라도 번호가 다르면 다른 메시가 나올 수 있고, 그 메시도 똑같이 유효합니다. Delaunay 동점을 점 번호로 가르고, 경계 복원이 번호를 따르기 때문입니다.
  - 그래서 V3 한도 초과 수처럼 메시에서 센 값도 달라질 수 있으니, 결과는 같은 배열끼리 비교합니다. C14는 로더의 정준 배열을 잽니다. [meshloom 한계](packages/meshloom/overview.md#한계).
