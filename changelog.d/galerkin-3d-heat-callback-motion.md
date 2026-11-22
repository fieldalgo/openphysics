# Added

## English

- `galerkin`: **3D steady heat takes a heat source callback with a motion.** With `motion=`, `solve_steady_heat_3d` now accepts the source `callback(centroids) -> (T,)`; it is called again at the live tetrahedron centroids (the ordinary centroid rule), so the shape derivative includes its change along the motion, and the result's `heat_source_density` carries the derivative too. Checked (E3D1–E3D6, pre-registered): every field equal to the moved mesh's solve within 1e-12, the derivative equal to Richardson differences within 1e-8, JAX and PyTorch within 1e-12, and the closed-form heat rate of a fixed linear source within 1e-10. [Shape derivatives](docs/packages/galerkin/shape_derivative.md#3d-steady-heat).

## 한국어

- `galerkin`: **3D 정상 열이 motion과 함께 열원 콜백을 받습니다.** `motion=`에서 `solve_steady_heat_3d`가 열원 `callback(centroids) -> (T,)`을 받습니다. live 사면체 중심(일반 중심 규칙)에서 다시 불러 형상 미분에 motion을 따른 변화가 들어가고, 결과의 `heat_source_density`도 미분을 나릅니다. 검사(E3D1–E3D6, 사전 등록): 모든 필드가 이동 메시 풀이와 1e-12 이내, 미분은 Richardson 차분과 1e-8 이내, JAX와 PyTorch는 1e-12 이내, 고정 일차 열원의 닫힌 식 열 비율은 1e-10 이내. [형상 미분](packages/galerkin/shape_derivative.md#3d-정상-열).
