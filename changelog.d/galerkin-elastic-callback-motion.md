# Added

## English

- `galerkin`: **linear elasticity takes body force and traction callbacks with a motion.** With `motion=`, `solve_elasticity` now accepts a body force `callback(points) -> (Q, 2)` and a traction `callback(points, outward_normals) -> (Q, 2)`; they are called again at the live points of the ordinary rules, so the shape derivative includes their change along the motion (a pressure −p·n follows the turning normal). The thermoelastic solves still take constants only. Checked (EL1–EL7, pre-registered): every field equal to the moved mesh's solve within 1e-12, derivatives equal to Richardson differences within 1e-8, JAX and PyTorch within 1e-12, and the closed-form applied force of a fixed body force and of a traction on a growing side within 1e-10. [Shape derivatives](docs/packages/galerkin/shape_derivative.md#linear-elasticity).

## 한국어

- `galerkin`: **선형 탄성이 motion과 함께 체적력·traction 콜백을 받습니다.** `motion=`에서 `solve_elasticity`가 체적력 `callback(points) -> (Q, 2)`와 traction `callback(points, outward_normals) -> (Q, 2)`을 받습니다. 일반 규칙의 live 점으로 다시 불러, 형상 미분에 motion을 따른 변화가 들어갑니다(압력 −p·n은 돌아가는 법선을 따릅니다). 열탄성 풀이는 여전히 상수만 받습니다. 검사(EL1–EL7, 사전 등록): 모든 필드가 이동 메시 풀이와 1e-12 이내, 미분은 Richardson 차분과 1e-8 이내, JAX와 PyTorch는 1e-12 이내, 고정 체적력과 자라는 변 traction의 닫힌 식 작용력은 1e-10 이내. [형상 미분](packages/galerkin/shape_derivative.md#선형-탄성).
