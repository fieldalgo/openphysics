# Changed

## English

- meshloom: **an acute vertex's shells hold to 2^-e of the radius, e from the smallest angle θ between its segments** (e = ⌈log2(1/θ²)⌉ + 1, between 24 and 30; a vertex that is not a protected hub also keeps at least 2^-24 of the piece), instead of 2^-30 at every acute vertex. When the window holds no exact double point, one in a window 16 times as wide is taken. A thin fan still gets common shells, and more split points are exact doubles, so needle facets keep their areas (fan readiness input at 3e5 faces: θ = 0.01°, e = 26, no facet over V3(a)).

## 한국어

- meshloom: **예각 꼭짓점의 껍질은 반지름의 2^-e 안에 둡니다. e는 그 선분들 사이 최소각 θ에서 정합니다**(e = ⌈log2(1/θ²)⌉ + 1, 24에서 30 사이. 보호된 hub가 아닌 꼭짓점은 조각의 2^-24도 보장합니다). 이전에는 모든 예각 꼭짓점이 2^-30이었습니다. 창 안에 정확 double 점이 없으면 16배 넓은 창에서 찾습니다. 얇은 부채꼴도 공통 껍질을 얻고, 정확 double 분할점이 늘어 needle facet 면적이 유지됩니다(면 3e5개 fan 사전 점검 입력: θ = 0.01°, e = 26, V3(a)를 넘는 facet 없음).
