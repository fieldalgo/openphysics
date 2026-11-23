# Added

## English

- `simcase`: a vector `em.modes2d` result with an open boundary (PML, no bend) now saves `te_polarization_fraction` and `effective_area`, computed over its physical window (the triangles whose centroid lies inside `physical_bounds`, the PML excluded), with `integration_region: "physical_window"` in `mode_postprocessing`. Power, confinement, overlaps and coupling stay absent for PML results; bend and scalar PML results and every closed result are unchanged, byte for byte. `results.group_index` is accepted with `pml` (still refused with `bend`): n_g is then complex, `{"re", "im"}`, by the same three solves, matched with physical weights. At the default mesh of the leaky slab check n_g is 5.2e-3 low in Re, almost all of it the error of n_eff itself; it shrinks on refinement. [PML modes](docs/packages/simcase/pml_modes.md#api-and-results), [group index](docs/packages/simcase/group_index.md).

## 한국어

- `simcase`: 열린 경계(PML, 굽힘 없음)가 있는 벡터 `em.modes2d` 결과는 이제 `te_polarization_fraction`과 `effective_area`를 물리 창(중심이 `physical_bounds` 안에 있는 삼각형, PML 제외)에서 계산해 저장하고, `mode_postprocessing`에 `integration_region: "physical_window"`를 적습니다. PML 결과의 전력, 가둠, 겹침, 결합은 여전히 없습니다. 굽힘·스칼라 PML 결과와 모든 닫힌 결과는 바이트 그대로입니다. `results.group_index`는 `pml`과 함께 받습니다(`bend`와는 여전히 거절). 이때 n_g는 같은 세 풀이로 물리 가중치로 짝지은 복소수 `{"re", "im"}`입니다. 누설 슬래브 점검의 기본 메시에서 n_g의 Re는 5.2e-3 낮으며, 거의 모두 n_eff 자체의 오차이고 메시를 세밀하게 하면 줄어듭니다. [PML 모드](packages/simcase/pml_modes.md#api와-결과), [군굴절률](packages/simcase/group_index.md).
