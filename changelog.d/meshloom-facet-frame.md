# Fixed

## English

- `meshloom`: **a polygon facet whose first loop points lie on a long edge now refines.** Refinement places a facet point as a + s (b − a) + r (c − a) on a frame triple a, b, c of the facet, solving s and r in doubles. The frame was the first three loop points that are not exactly collinear; three points along one slanted edge, off a line by rounding only, qualified, and the system was then singular. Facet points missed their facet: `RefineError` (no frame for the facet, or the point cap). Such a triple (squared sine of its angle at most 1e-8) is now replaced by a well-spread one: the loop point farthest from the first, then the point farthest from their line. Other frames are unchanged. A 15° wedge whose top loop starts on its slanted edge reached the 5000-point cap before and now meshes in 0.4 s with the exact volume. New test in `tests/meshloom/test_triangle_surface.py`. [meshloom](docs/packages/meshloom/overview.md#limits).

## 한국어

- `meshloom`: **바깥 고리의 첫 점들이 긴 변 위에 놓인 다각형 facet도 이제 세분화됩니다.** 세분화는 facet의 기준 틀 세 점 a, b, c로 facet 점을 a + s (b − a) + r (c − a)에 놓고, s와 r을 double로 풉니다. 기준 틀은 정확히는 한 직선 위에 있지 않은 첫 세 고리 점이었습니다. 그래서 비스듬한 한 변 위에서 반올림만큼만 직선을 벗어난 세 점이 뽑힐 수 있었고, 그러면 연립식이 특이해졌습니다. facet 점이 facet을 벗어났고 `RefineError`(facet의 기준 틀 없음, 또는 점 상한)가 났습니다. 이제 이런 세 점(각의 사인 제곱이 1e-8 이하)은 넓게 퍼진 세 점으로 바꿉니다. 첫 점에서 가장 먼 고리 점, 그리고 두 점을 잇는 직선에서 가장 먼 점입니다. 다른 기준 틀은 바뀌지 않습니다. 윗면 고리가 비스듬한 변에서 시작하는 15° 쐐기는 전에는 점 상한 5000에 닿았고, 이제 0.4초에 정확한 부피로 메시가 됩니다. 새 시험은 `tests/meshloom/test_triangle_surface.py`에 있습니다. [meshloom](packages/meshloom/overview.md#한계).
