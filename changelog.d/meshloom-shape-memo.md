# Changed

## English

- `meshloom`: **mesh improvement uses far less memory, and a tetrahedron's shape no longer depends on its vertex order.** The flips no longer keep a memo of every tetrahedron's shape (it held about 60% of peak memory) and compute the shape on the sorted vertices, so the result no longer depends on which vertex order was asked first; where only the quality q is needed, the six dihedral angles are skipped. Some meshes change in their last flips: 2 of 59 recorded comparison inputs and 5 of V26's nine cases (C1–C9 at h = 0.1), with the same tetrahedron counts; every quality gate of the meshloom tests still passes. On V14's graded 1M-tetrahedron cube peak memory falls from 2.12 to 0.77 GiB (within the 1 GiB bound) and time from 255 to 175 s (the 60 s bound is still not met). [meshloom limits](docs/packages/meshloom/overview.md#limits).

## 한국어

- `meshloom`: **메시 개선이 메모리를 훨씬 적게 쓰고, 사면체의 shape가 꼭짓점 순서에 따라 달라지지 않습니다.** flip 단계가 모든 사면체의 shape memo(peak 메모리의 약 60%)를 더는 들고 있지 않습니다. shape는 정렬한 꼭짓점에서 계산하므로, 어떤 꼭짓점 순서로 먼저 물었는지에 따라 결과가 달라지지 않습니다. 품질 q만 필요한 곳에서는 이면각 여섯 개를 계산하지 않습니다. 일부 메시는 마지막 flip에서 바뀝니다. 기록된 비교 입력 59개 중 2개, V26 아홉 사례(C1–C9, h = 0.1) 중 5개이며, 사면체 수는 같습니다. meshloom 시험의 품질 게이트는 모두 그대로 통과합니다. V14의 graded 1M 사면체 정육면체에서 peak 메모리는 2.12 GiB에서 0.77 GiB로 줄어 1 GiB 한도 안이고, 시간은 255 s에서 175 s로 줄었습니다(60 s 한도는 아직 못 맞춤). [meshloom 한계](packages/meshloom/overview.md#한계).
