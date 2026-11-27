# Changed

## English

- meshloom: **an S point whose exact coordinates are doubles goes straight to the exact double predicates** (its cached interval is that point, decided once when it is added). Mixed orient3d and insphere then skip the filters and big integers for it, with the same signs. Segment recovery at 3e5 faces: needle 32.0 to 28.5 s, coplanar 26.5 to 24.6 s; the six readiness digests are unchanged.

## 한국어

- meshloom: **정확 좌표가 double인 S점은 바로 정확 double 술어로 보냅니다**(점을 넣을 때 한 번 판정해 캐시 구간을 그 점으로 둡니다). 혼합 orient3d와 insphere는 이런 점에 필터와 큰 정수를 쓰지 않고 같은 부호를 냅니다. 면 3e5개에서 선분 복원은 needle 32.0 → 28.5 s, coplanar 26.5 → 24.6 s이고, 사전 점검 digest 6개는 그대로입니다.
