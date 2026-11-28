# Changed

## English

- meshloom: **a protected hub's shells hold to 2^-e of the radius, e from the smallest angle θ between its segments** (e = ⌈log2(1/θ²)⌉ + 1, between 24 and 30), instead of always 2^-30. A thin fan still gets common shells, and the wider window lets split points be exact doubles, so the fan's needle facets keep their areas (fan readiness input at 3e5 faces: θ = 0.01°, e = 26).

## 한국어

- meshloom: **보호된 hub의 껍질은 반지름의 2^-e 안에 둡니다. e는 그 선분들 사이 최소각 θ에서 정합니다**(e = ⌈log2(1/θ²)⌉ + 1, 24에서 30 사이). 이전에는 항상 2^-30이었습니다. 얇은 부채꼴도 공통 껍질을 얻고, 넓어진 창 덕분에 분할점이 정확 double이 되어 부채꼴의 needle facet 면적이 유지됩니다(면 3e5개 fan 사전 점검 입력: θ = 0.01°, e = 26).
