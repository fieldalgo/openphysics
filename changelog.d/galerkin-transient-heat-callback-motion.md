# Added

## English

- `galerkin`: **transient heat takes coordinate callbacks with a motion.** With `motion=`, `solve_transient_heat` now accepts the source `callback(position, time)` and the boundary `callback(position, outward_normal)` and `callback(position, outward_normal, time)` for the inward heat flux and the convection h and ambient, Cartesian and axisymmetric. They are called again at the live points of the same rules, at the same times as the ordinary solve, so the shape derivative includes their change along the motion. Coordinate callbacks of the Dirichlet values stay refused. Checked (ET1–ET7, pre-registered): every history equal to the moved mesh's solve within 1e-12, derivatives equal to Richardson differences within 1e-8, JAX and PyTorch within 1e-12, and closed-form rates of a fixed time-dependent source and a field flux within 1e-10. [Shape derivatives](docs/packages/galerkin/shape_derivative.md#transient-heat).

## 한국어

- `galerkin`: **과도 열이 motion과 함께 좌표 콜백을 받습니다.** `motion=`에서 `solve_transient_heat`가 열원 `callback(position, time)`과, 내향 열유속·convection h·ambient의 경계 `callback(position, outward_normal)`·`callback(position, outward_normal, time)`을 Cartesian과 축대칭 모두에서 받습니다. 일반 풀이와 같은 시각에 같은 구적의 live 점으로 다시 불러, 형상 미분에 motion을 따른 변화가 들어갑니다. Dirichlet 값의 좌표 콜백은 계속 거부합니다. 검사(ET1–ET7, 사전 등록): 모든 이력이 이동 메시 풀이와 1e-12 이내, 미분은 Richardson 차분과 1e-8 이내, JAX와 PyTorch는 1e-12 이내, 시간에 따라 바뀌는 고정 열원과 필드 열유속의 닫힌 식 비율은 1e-10 이내. [형상 미분](packages/galerkin/shape_derivative.md#과도-열).
