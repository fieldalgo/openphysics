# Changed

## English

- meshloom: **segment recovery no longer walks the whole star of a vertex with many segments, such as a fan's centre.**
  - Each round re-queues only the segments that the last insertions could have removed.
  - Edges are checked from the end with fewer segments.
  - Reference points are sought among the neighbours of the other end.
  - `neighbours` returns its vertices sorted.

## 한국어

- meshloom: **선분 복원이 부채꼴 중심처럼 선분이 많은 꼭짓점의 star 전체를 더 이상 훑지 않습니다.**
  - 라운드마다 직전 삽입이 지웠을 수 있는 선분만 다시 넣습니다.
  - 변 확인은 선분이 적은 쪽 끝에서 시작합니다.
  - 기준점은 다른 쪽 끝의 이웃에서 찾습니다.
  - `neighbours`는 꼭짓점을 정렬해 돌려줍니다.
