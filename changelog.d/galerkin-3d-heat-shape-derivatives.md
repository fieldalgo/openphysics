# Added

## English

- `galerkin`: **shape derivatives of 3D steady heat.** `solve_steady_heat_3d(mesh3d, ..., motion=MeshMotion(design_velocity=W, t=t))` with an (N, 3) design velocity gives the temperatures, heat flux and nodal rates with their derivative with respect to the JAX or PyTorch t; the inputs stay a region or scalar conductivity and source and Dirichlet values attached to their nodes (a source callback is refused). `galerkin.shape.admissible_interval` takes a `Mesh3D` (each tetrahedron volume is a cubic in t; its polished real roots bound the interval), and `extend_velocity` extends known node velocities harmonically in 3D. Checked (T1-T10, pre-registered): the numbers equal the moved-mesh solve (5.7e-14); the derivative matches Richardson differences of moved meshes within 1.2e-10 of max |dT/dt|, JAX and PyTorch within 2.3e-16; rigid motions give zero; a two-layer box matches the analytic dQ/dL1 within 4.7e-15; a hollow cylinder's inner-radius derivative converges to the analytic value at order 2.0 (5.9e-4 on the finest mesh). [Shape derivatives](docs/packages/galerkin/shape_derivative.md#3d-steady-heat).

## 한국어

- `galerkin`: **3D 정상 열의 형상 미분.** (N, 3) 설계 속도를 준 `solve_steady_heat_3d(mesh3d, ..., motion=MeshMotion(design_velocity=W, t=t))`가 온도, 열유속, 노드 비율과 JAX·PyTorch t에 대한 미분을 줍니다. 입력은 영역 또는 스칼라 전도도와 열원, 노드에 붙은 Dirichlet 값 그대로이며 열원 콜백은 거부합니다. `galerkin.shape.admissible_interval`이 `Mesh3D`를 받고(사면체 부피는 t의 3차식이며 다듬은 실근이 구간을 정함), `extend_velocity`가 3D에서 알려진 노드 속도를 조화 확장합니다. 검사(T1-T10, 사전 등록): 수치가 이동 메시 풀이와 같고(5.7e-14), 미분이 이동 메시 Richardson 차분과 max |dT/dt|의 1.2e-10 이내, JAX와 PyTorch가 2.3e-16 이내이며, 강체 운동은 0을, 두 층 상자는 해석 dQ/dL1과 4.7e-15 이내를 주고, 속 빈 원통의 안쪽 반지름 미분은 해석값으로 차수 2.0으로 수렴합니다(가장 고운 메시 5.9e-4). [형상 미분](packages/galerkin/shape_derivative.md#3d-정상-열).
