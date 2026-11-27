# Added

## English

- `simcase`: **`thermal.steady3d` takes cylinders and spheres in meshloom's builder shapes** (stage 5, slice 4b; experimental), on a third mesh route, `"builder"`: `prescribed_temperature` names a tag, an exterior part (`via.bottom`, `sa.surface`) or a feature id; a fixed temperature on an interior part (`via.side`) is refused by name. The result's `mesh_route` is `"builder"` and its diagnostics carry `I-MESH-ESTIMATE` and `I-SURFACE-SAMPLED`. Validated on the direct path (`build_mesh3d` + `galerkin.solve_steady_heat_3d`): a via through a slab against parallel conduction (E2, slope 1.99, 2.7e-3 at h = 0.05) and spherical shells against 16π/3 (E3, slope 1.99, 2.1e-3), whose heat rate equals the discrete energy uᵀKu on the same mesh to 4e-14; the kind gives the same temperatures and heat rates as the direct path. [Steady heat on a 3D component](docs/packages/simcase/thermal_steady3d.md#validation).

## 한국어

- `simcase`: **`thermal.steady3d`가 meshloom builder 모양의 원통과 구를 받음**(5단계 슬라이스 4b, 실험 단계). 세 번째 메시 경로 `"builder"`에서 `prescribed_temperature`는 태그, 외부 부분(`via.bottom`, `sa.surface`), 피처 id를 이름으로 받고, 내부 부분(`via.side`)에 거는 고정 온도는 이름을 밝혀 거부합니다. 결과의 `mesh_route`는 `"builder"`이며 진단에 `I-MESH-ESTIMATE`와 `I-SURFACE-SAMPLED`가 담깁니다. 직접 경로(`build_mesh3d` + `galerkin.solve_steady_heat_3d`)에서 검증했습니다. 판을 지나는 비아를 병렬 전도와(E2, 기울기 1.99, h = 0.05에서 2.7e-3), 구 껍질을 16π/3와(E3, 기울기 1.99, 2.1e-3) 비교했고, 열 비율은 같은 메시의 이산 에너지 uᵀKu와 4e-14까지 같습니다. 이 종류는 직접 경로와 같은 온도와 열 비율을 냅니다. [3D 구성 요소의 정상 열](packages/simcase/thermal_steady3d.md#검증).
