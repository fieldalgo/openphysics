# Added

## English

- `galerkin`: **Cartesian steady heat takes coordinate callbacks with a motion.** With `motion=`, `solve_steady_heat` now accepts a heat source `callback(points)`, an inward heat flux `callback(points, normals)` and convection h and ambient `callback(points, normals)`. The callback is a field fixed in space; it is called once more with the live JAX or PyTorch points and normals of the same quadrature rules, so the shape derivative includes its change along the motion. A callback that computes with NumPy only is refused by name with a `TypeError`. Axisymmetric, transient, electric, elastic and 3D coordinate callbacks and callable coefficients stay refused. Checked (E1–E7, pre-registered): numbers equal to the moved mesh's solve within 1e-12, derivatives equal to Richardson differences within 1e-8, JAX and PyTorch within 1e-12, and the analytic dQ/dL of a fixed linear source within 1e-10. [Shape derivatives](docs/packages/galerkin/shape_derivative.md#coordinate-callbacks-in-steady-heat).

## 한국어

- `galerkin`: **Cartesian 정상 열이 motion과 함께 좌표 콜백을 받습니다.** `motion=`에서 `solve_steady_heat`가 열원 `callback(points)`, 내향 열유속 `callback(points, normals)`, convection의 h와 ambient `callback(points, normals)`을 받습니다. 콜백은 공간에 고정된 장이며, 같은 구적의 live JAX·PyTorch 점과 법선으로 한 번 더 불러 형상 미분에 motion을 따른 콜백의 변화가 들어갑니다. NumPy로만 계산하는 콜백은 이름을 밝힌 `TypeError`로 거부합니다. 축대칭·과도·전기·탄성·3D 좌표 콜백과 콜백 계수는 계속 거부합니다. 검사(E1–E7, 사전 등록): 수치는 이동 메시 풀이와 1e-12 이내, 미분은 Richardson 차분과 1e-8 이내, JAX와 PyTorch는 1e-12 이내, 고정 선형 열원의 해석 dQ/dL과 1e-10 이내. [형상 미분](packages/galerkin/shape_derivative.md#정상-열의-좌표-콜백).
