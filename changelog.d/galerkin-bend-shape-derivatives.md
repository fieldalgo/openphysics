# Added

## English

- `galerkin`: **shape derivatives of bent waveguide modes.** `solve_waveguide_modes(..., pml=ModalPML(...), bend=Bend(...), motion=MeshMotion(design_velocity=W, t=t))` no longer refuses the bend. The window elements may move and their bend factor 1 + (centroid - origin) / radius follows the nodes; the PML elements keep every node in place (as without a bend), so their complex factors stay fixed. The kernel `solve_modes` takes `coordinate_bend=(radius, axis, origin)` with a motion for this. Checked (BD1-BD6, pre-registered): on a radius 2 um bent silicon film the numbers equal the moved-mesh bend solve polished by the same Newton step (residual <= 2e-13); the complex slope matches Richardson differences of moved meshes within 5.7e-11, JAX and PyTorch within 1.3e-15; the film-thickness derivative converges to the Bessel-Hankel pole's (1.6e-4 on the finest mesh, imaginary part 9.4e-3). [Shape derivatives](docs/packages/galerkin/shape_derivative.md#waveguide-modes).

## 한국어

- `galerkin`: **굽은 도파관 모드의 형상 미분.** `solve_waveguide_modes(..., pml=ModalPML(...), bend=Bend(...), motion=MeshMotion(design_velocity=W, t=t))`가 이제 굽힘을 거부하지 않습니다. 창 요소는 움직일 수 있고 그 굽힘 인자 1 + (중심 - origin) / radius가 노드를 따르며, PML 요소는 굽힘이 없을 때처럼 모든 노드를 제자리에 두므로 복소 인자가 그대로입니다. 이를 위해 커널 `solve_modes`가 motion과 함께 `coordinate_bend=(radius, axis, origin)`을 받습니다. 검사(BD1-BD6, 사전 등록): 반지름 2 µm 굽은 실리콘 막에서 수치가 같은 Newton 단계로 다듬은 이동 메시 굽힘 풀이와 같고(잔차 <= 2e-13), 복소 기울기가 이동 메시 Richardson 차분과 5.7e-11, JAX와 PyTorch가 1.3e-15 이내이며, 막 두께 미분이 Bessel-Hankel 극점의 미분으로 수렴합니다(가장 고운 메시 1.6e-4, 허수부 9.4e-3). [형상 미분](packages/galerkin/shape_derivative.md#도파관-모드).
