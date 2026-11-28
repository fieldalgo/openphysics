# Changed

## English

- `galerkin`: **the two-ground panel solver integrates the smooth kernel directly on plane-scaled boxes with fewer panels than the interpolation degree.** Such a box uses `degree` Gauss points per panel, fewer than the degree² interpolation grid; the degree−2 comparison (1e-10) and the explicit degree are unchanged, and the docs no longer say that the smooth part is only interpolated. With the reciprocal box pairs, the three SIPI layered coplanar stripline sections take 4.4–7.4 s instead of 11.1–14.2 s; capacitance and current Gram change by at most 1.1e-15 and 1.6e-14 of their largest entries, no more than the change from degree 14 to 16. [Two-ground panels](docs/packages/galerkin/two-ground.md).

## 한국어

- `galerkin`: **두 접지 panel 풀이기가 패널 수가 보간 차수보다 적은 평면 비례 상자에서 매끄러운 핵을 직접 적분합니다.** 이런 상자는 패널마다 `degree`점 Gauss를 써서 차수² 보간 격자보다 점이 적습니다. 차수−2 비교(1e-10)와 명시 차수는 그대로이며, 문서는 매끄러운 부분을 보간만 한다고 더는 쓰지 않습니다. 상반 상자 쌍과 함께 SIPI 적층 coplanar stripline 세 단면은 11.1–14.2 s 대신 4.4–7.4 s가 걸리고, 정전용량과 전류 Gram은 최대 성분의 1.1e-15, 1.6e-14 이하로 바뀌어 차수 14→16 변화보다 크지 않습니다. [두 접지 panel](packages/galerkin/two-ground.md).
