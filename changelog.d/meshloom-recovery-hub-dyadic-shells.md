# Changed

## English

- meshloom: **about a fan's centre, segment recovery rounds split radii down to a dyadic grid common to all its segments** (rc 2^k (1 + j 2^-m), the coarsest grid with a point in the piece's window). Radii that differ by a rounding, such as those of float32 rim points, no longer encroach each other's pieces without end in a thin fan.

## 한국어

- meshloom: **부채꼴 중심 둘레에서 선분 복원은 분할 반지름을 그 중심의 모든 선분에 공통인 이진 격자로 내림합니다**(rc 2^k (1 + j 2^-m), 조각의 허용 구간에 점이 있는 가장 성긴 격자). 그래서 float32 테두리 점처럼 반올림만큼 다른 반지름들이 얇은 부채꼴에서 서로의 조각을 끝없이 침범하지 않습니다.
