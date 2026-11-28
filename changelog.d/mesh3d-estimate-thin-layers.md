# Fixed

## English

- `simcase`: the meshloom-route 3D estimate (`estimate_mesh3d`, and the `E-MESH-ESTIMATE` check `build_mesh3d` makes before meshing) counts thin layers and gaps: T = 6.3 ∫ dV / s³ with s = min(h, 1.2 lfs), the local feature size along the grid lines of the component. A thin layer, which meshloom meshes to about area / t² tetrahedra whatever h is, was undercounted up to 45× (Studio card 1 at t_ox 2 µm, h 40 µm) and could pass the limit and then mesh far above it; card 1 at t_ox 2–10 µm and h 15–40 µm is now within 0.73–0.86 of the built count. Thick documents keep 6.3 Σ V/h³; the builder and extrude routes are unchanged. The message reads "(T = 6.3 sum(V/s^3), s the element size, smaller in thin layers and gaps)". [3D boxes, slab layers, cylinders and spheres](docs/packages/simcase/geometry_engine3d.md#use).

## 한국어

- `simcase`: meshloom 경로의 3D 추정(`estimate_mesh3d`, `build_mesh3d`가 메시하기 전에 하는 `E-MESH-ESTIMATE` 검사)이 얇은 층과 틈을 셉니다. T = 6.3 ∫ dV / s³이며 s = min(h, 1.2 lfs), lfs는 구성 요소의 격자선을 따른 국소 형상 크기입니다. meshloom이 h와 상관없이 약 면적 / t²개의 사면체로 메시하는 얇은 층을 최대 45배 적게 세어(Studio 카드 1, t_ox 2 µm, h 40 µm) 한도를 통과한 뒤 훨씬 넘게 메시될 수 있었습니다. 이제 카드 1의 t_ox 2–10 µm, h 15–40 µm에서 만든 수의 0.73–0.86 안에 듭니다. 두꺼운 문서는 6.3 Σ V/h³를 그대로 쓰고, builder 경로와 압출 경로는 바뀌지 않습니다. 메시지는 "(T = 6.3 sum(V/s^3), s the element size, smaller in thin layers and gaps)"입니다. [3D 상자, 판 층, 원통, 구](packages/simcase/geometry_engine3d.md#사용).
