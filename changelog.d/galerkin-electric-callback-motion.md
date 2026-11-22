# Added

## English

- `galerkin`: **steady electric conduction takes current-density callbacks with a motion.** With `motion=`, `solve_steady_electric` now accepts an inward current density `callback(position, outward_normal)`; it is called again at the live points and normals of the ordinary edge rule, so the shape derivative includes its change along the motion. On a component without prescribed volts a callback current stays refused by name. Checked (EE1–EE7, pre-registered): every field equal to the moved mesh's solve within 1e-12, the power derivative equal to Richardson differences within 1e-8, JAX and PyTorch within 1e-12, and the closed-form reaction of a current on a growing side within 1e-10. [Shape derivatives](docs/packages/galerkin/shape_derivative.md#steady-electric-conduction).

## 한국어

- `galerkin`: **정상 전기 전도가 motion과 함께 전류 밀도 콜백을 받습니다.** `motion=`에서 `solve_steady_electric`가 내향 전류 밀도 `callback(position, outward_normal)`을 받습니다. 일반 변 규칙의 live 점과 법선으로 다시 불러, 형상 미분에 motion을 따른 변화가 들어갑니다. 지정 전압이 없는 성분의 콜백 전류는 계속 이름을 밝혀 거부합니다. 검사(EE1–EE7, 사전 등록): 모든 필드가 이동 메시 풀이와 1e-12 이내, 전력 미분은 Richardson 차분과 1e-8 이내, JAX와 PyTorch는 1e-12 이내, 자라는 변 전류의 닫힌 식 반력은 1e-10 이내. [형상 미분](packages/galerkin/shape_derivative.md#정상-전기-전도).
