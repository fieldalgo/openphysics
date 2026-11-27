# Changed

## English

- `galerkin`: **the two-ground panel solver skips lateral images that cannot change a result.** An image is skipped when twice a bound on its magnitude over the whole target–source block is below 2⁻⁵⁴ of the block's smallest entry, so every result stays bit for bit that of the full image sum; wide, low rectangles such as the layered coplanar striplines of the SIPI catalog run about ten times faster. The degree−2 comparison never tested image truncation there, and the documentation now says so. [Two-ground panels](docs/packages/galerkin/two-ground.md).

## 한국어

- `galerkin`: **두 접지 panel 풀이기가 결과를 바꿀 수 없는 측벽 영상을 건너뜁니다.** 대상–원천 블록 전체에서 구한 영상 크기 상한의 두 배가 블록의 가장 작은 성분의 2⁻⁵⁴배보다 작으면 건너뛰므로, 모든 결과가 영상을 모두 더한 합과 비트 단위로 같습니다. SIPI 목록의 적층 coplanar stripline 같은 넓고 낮은 직사각형은 약 10배 빨라집니다. 그런 경우 차수−2 비교가 영상 절단을 검사하지 못했다는 점도 문서에 적었습니다. [두 접지 panel](packages/galerkin/two-ground.md).
