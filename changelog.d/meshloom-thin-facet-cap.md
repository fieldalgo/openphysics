# Fixed

## English

- meshloom: **refinement refuses a facet too thin for the point cap before it starts**, with a `RefineError` that names the facet, its two input edges and their distance, instead of reaching the cap point by point, which took hours. Two input edges of one facet that share no end point and lie d apart over a length L need about L/(2d) points there; when that estimate is above the cap (`max_points` or its default), refinement ends at once. Inputs from the 3D geometry engine with two edges 0.4 pm to 862 pm apart (fuzz seeds 42 and 46, and two boxes 6e-8 of the diagonal apart side by side and face to face) now end in 0.01 s; every recorded mesh is unchanged. [meshloom limits](docs/packages/meshloom/overview.md#limits).

## 한국어

- meshloom: **점 상한에 비해 너무 얇은 facet은 세분화를 시작하기 전에 거부합니다.** 거부할 때 facet, 그 두 입력 변, 둘 사이 거리를 대는 `RefineError`를 냅니다. 예전에는 상한에 닿을 때까지 점을 하나씩 넣느라 몇 시간이 걸렸습니다. 끝점을 공유하지 않는 한 facet의 두 입력 변이 길이 L에 걸쳐 거리 d로 떨어져 있으면 그곳에 점이 약 L/(2d)개 필요합니다. 이 어림이 상한(`max_points` 또는 기본값)을 넘으면 세분화가 곧바로 끝납니다. 3D 형상 엔진이 만든 입력 가운데 두 변이 0.4 pm–862 pm 떨어진 것(fuzz seed 42와 46, 대각선의 6e-8만큼 떨어져 나란히 놓이거나 마주 보는 상자 둘)은 이제 0.01 s에 끝납니다. 기록된 메시는 모두 같습니다. [meshloom 한계](packages/meshloom/overview.md#한계).
