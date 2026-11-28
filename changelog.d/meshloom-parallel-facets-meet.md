# Fixed

## English

- meshloom: **two facets one rounding apart from one plane that share an edge no longer make refinement run without end.** Refinement read their planes, parallel in doubles, as not meeting, so the small-angle rule did not apply and points on each facet split the other's subfacets until the point cap, which took hours. They now meet along the shared edge at an angle near 0° (or 180°), measured about that edge. A seeded assembly from the 3D geometry engine (fuzz seed 55) that hung now meshes in about 25 s; every recorded mesh is unchanged. [meshloom refinement](docs/packages/meshloom/overview.md#kernel-building-blocks).

## 한국어

- meshloom: **한 평면에서 반올림 한 번만큼 벗어나고 변을 공유하는 두 facet 때문에 세분화가 끝나지 않던 문제를 고쳤습니다.** 세분화는 doubles로 평행한 두 평면을 만나지 않는 것으로 읽었습니다. 그래서 작은 각 규칙이 적용되지 않았고, 각 facet의 점이 상대 facet의 subfacet을 점 상한까지 나누느라 몇 시간이 걸렸습니다. 이제 두 facet은 공유 변을 따라 0°(또는 180°)에 가까운 각으로 만나며, 각은 그 변을 축으로 잽니다. 3D 형상 엔진의 seed 조립(fuzz seed 55)은 멈추던 입력인데 이제 약 25 s에 메시됩니다. 기록된 메시는 모두 같습니다. [meshloom 세분화](packages/meshloom/overview.md#커널-구성-요소).
