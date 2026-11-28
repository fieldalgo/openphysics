# Changed

## English

- meshloom: **a new point on a segment finds its piece of the segment by bisection** instead of testing every piece with exact predicates, so each insertion no longer takes time in proportion to the points already on that segment. On an input whose refinement puts tens of thousands of points on one segment, 60 s of refinement inserts 74,000 points instead of 28,000; every recorded mesh is unchanged (the 59 comparison inputs, V26's nine cases, the CDT inputs and the 21 locked surfaces, bit for bit).

## 한국어

- meshloom: **선분 위 새 점은 선분의 어느 조각에 있는지 이분 탐색으로 찾습니다.** 예전에는 모든 조각을 정확 술어로 시험했으므로, 삽입 한 번의 시간이 그 선분에 이미 있는 점 수에 비례했습니다. 세분화가 선분 하나에 점 수만 개를 넣는 입력에서 60 s 동안 넣는 점이 28,000개에서 74,000개로 늘었습니다. 기록된 메시는 모두 같습니다(비교 입력 59개, V26의 아홉 사례, CDT 입력, 잠금 표면 21개, 비트 단위).
