# Changed

## English

- meshloom: **segment recovery chooses each split point on the mesh as it is when the point goes in**, still taking a round's missing pieces in BRIO order of their middles. Points chosen on the round's starting mesh had stale reference points; on the needle readiness input at 3e5 faces they cost 45% more segment points and made the subfacet stage fifteen times slower.

## 한국어

- meshloom: **선분 복원은 각 분할점을 그 점을 넣는 때의 메시에서 고릅니다.** 한 라운드의 빠진 조각은 여전히 가운데 점의 BRIO 순서로 다룹니다. 라운드 시작 메시에서 고른 점은 기준점이 낡아서, 면 3e5개의 needle 사전 점검 입력에서 선분 점이 45% 늘고 subfacet 단계가 15배 느려졌습니다.
