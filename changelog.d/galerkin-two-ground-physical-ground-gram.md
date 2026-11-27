# Fixed

## English

- `galerkin`: **the two-ground panel solver integrates the grounded planes' current Gram in physical space.** The plane charge densities use the closed-form strip Poisson kernel with side-wall images, on x intervals no wider than three times the distance to the nearest singularity, compared at 12 and 16 Gauss points under the unchanged 1e-10 entrywise gate. The cosine sum it replaces left small entries between conductors that barely overlap on a plane by cancellation, so the check of the SIPI layered coupled coplanar stripline failed by rounding (1.1e-10); it now passes at 6e-14, the Gram changes by at most 9e-16 of its largest entry, and each solve takes about 2–4 s more. `ground_modes` is still admitted but no longer changes the Gram. [Two-ground panels](docs/packages/galerkin/two-ground.md).

## 한국어

- `galerkin`: **두 접지 panel 풀이기가 접지판 전류 Gram을 실공간에서 적분합니다.** 판의 전하 밀도를 측벽 영상을 포함한 띠 Poisson 핵의 닫힌 식으로 구하고, 가장 가까운 특이점까지 거리의 3배를 넘지 않는 x 구간에서 12점과 16점 Gauss로 비교하며, 성분별 1e-10 기준은 그대로입니다. 이전의 코사인 합은 판 위에서 거의 겹치지 않는 도체 사이의 작은 성분을 소거로 남겨, SIPI 적층 결합 coplanar stripline의 검사가 반올림 때문에 실패했습니다(1.1e-10). 이제 6e-14로 통과하고, Gram은 최대 성분의 9e-16 이하로 바뀌며, 풀이마다 약 2–4 s가 더 걸립니다. `ground_modes`는 여전히 받지만 Gram을 더는 바꾸지 않습니다. [두 접지 panel](packages/galerkin/two-ground.md).
