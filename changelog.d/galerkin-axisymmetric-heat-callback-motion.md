# Added

## English

- `galerkin`: **axisymmetric steady heat takes coordinate callbacks with a motion.** With `motion=` and `coordinate_system="axisymmetric"`, `solve_steady_heat` now accepts the heat source, inward heat flux and convection h and ambient callbacks, as the Cartesian solve does: they are called again at the live points of the same rules, weighted by 2πr there. Checked (EA1–EA7, pre-registered): numbers equal to the moved mesh's solve within 1e-12, derivatives equal to Richardson differences within 1e-8, JAX and PyTorch within 1e-12, and the closed-form reaction of a hollow cylinder and its derivatives in length and outer radius within 1e-10. [Shape derivatives](docs/packages/galerkin/shape_derivative.md#coordinate-callbacks-in-steady-heat).

## 한국어

- `galerkin`: **축대칭 정상 열이 motion과 함께 좌표 콜백을 받습니다.** `motion=`과 `coordinate_system="axisymmetric"`에서 `solve_steady_heat`가 Cartesian 풀이처럼 열원, 내향 열유속, convection의 h와 ambient 콜백을 받습니다. 같은 구적의 live 점에서 다시 부르고, 그 점의 2πr로 가중합니다. 검사(EA1–EA7, 사전 등록): 수치는 이동 메시 풀이와 1e-12 이내, 미분은 Richardson 차분과 1e-8 이내, JAX와 PyTorch는 1e-12 이내, 속이 빈 원통의 닫힌 식 반력과 길이·바깥 반지름 미분은 1e-10 이내. [형상 미분](packages/galerkin/shape_derivative.md#정상-열의-좌표-콜백).
