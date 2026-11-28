# Fixed

## English

- meshloom: **segment recovery picks a split point about an acute vertex within 2^-24 of its distance, not 2^-30**; only a protected hub (a thin fan's centre) keeps 2^-30. The narrower window left few exact double points, and the rounded points on needle facets' long edges moved their sub-areas past V3(a)'s bound (needle readiness input at 1e5 faces: 163 failing facets back to 2; small-angle row G:needle:0.01:0.25 passes KC1 again).

## 한국어

- meshloom: **선분 복원은 예각 꼭짓점 둘레의 분할점을 거리의 2^-30이 아니라 2^-24 안에서 고릅니다.** 보호된 hub(얇은 부채꼴 중심)만 2^-30을 유지합니다. 좁은 창에는 정확 double 점이 드물어, needle facet 긴 변의 반올림된 점이 부분 면적을 V3(a) 한계 밖으로 옮겼습니다(면 1e5개 needle 사전 점검 입력: 실패 facet 163개 → 2개, 작은 각 행 G:needle:0.01:0.25 KC1 다시 통과).
