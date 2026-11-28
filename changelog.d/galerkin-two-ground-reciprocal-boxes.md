# Changed

## English

- `galerkin`: **the two-ground panel solver computes each distant pair of plane-scaled interpolation boxes once.** The smooth kernel is reciprocal, so a block between boxes more than one apart is filled by transposition; diagonal blocks and both orders of neighbouring boxes are still computed, so the raw 1e-10 reciprocity check keeps comparing independently interpolated entries where boxes are closest. The three SIPI layered coplanar stripline sections take 6.3–10.1 s instead of 9.6–14.1 s; capacitance and current Gram change by at most 6e-16 and 2e-14 of their largest entries, below the change from interpolation degree 14 to 16. [Two-ground panels](docs/packages/galerkin/two-ground.md).

## 한국어

- `galerkin`: **두 접지 panel 풀이기가 멀리 떨어진 평면 비례 보간 상자 쌍을 한 번만 계산합니다.** 매끄러운 핵이 상반적이므로 한 칸보다 멀리 떨어진 상자 사이 블록은 전치로 채웁니다. 대각 블록과 이웃 상자의 두 방향은 여전히 계산하므로, raw 상반성 검사(1e-10)는 상자가 가장 가까운 곳에서 독립적으로 보간한 성분을 계속 비교합니다. SIPI 적층 coplanar stripline 세 단면은 9.6–14.1 s 대신 6.3–10.1 s가 걸리고, 정전용량과 전류 Gram은 최대 성분의 6e-16, 2e-14 이하로 바뀌어 보간 차수 14→16 변화보다 작습니다. [두 접지 panel](packages/galerkin/two-ground.md).
