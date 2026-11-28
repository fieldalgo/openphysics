# Changed

## English

- meshloom: **segment recovery protects a fan's centre with its whole set of shells at once** (radii rc 2^k and one point just short of each segment's far end, on a dyadic grid common to the hub's segments), and rounds later split points on those segments to the same grid. A 36,000-segment fan with float32 rim points now converges (83 rounds) instead of doubling its missing pieces each round.

## 한국어

- meshloom: **선분 복원은 부채꼴 중심을 보호할 때 껍질 전체를 한 번에 넣습니다**(반지름 rc 2^k의 점과, 각 선분의 먼 끝 바로 앞의 점 하나. 뒤의 점은 hub 선분들이 공유하는 이진 격자 위에 둡니다). 그 뒤 이 선분들의 분할점도 같은 격자로 내림합니다. 그래서 테두리 점이 float32인 선분 36,000개짜리 부채꼴이 라운드마다 빠진 조각이 두 배가 되지 않고 83라운드에 수렴합니다.
