# Added

## English

- `simcase` mode results: **the effective area of each mode**. `em.modes2d` results without PML save `effective_area` (points × modes, m², the existing registry quantity) in `fields.npz` and the summary's `mode_postprocessing`. For vector results it is A_eff = (Σ A_T |E|²)² / Σ A_T |E|⁴ on the saved centroid field over every triangle of the window with all three components, so any reader of the samples reproduces it; it is the common mode-solver form, not the vectorial nonlinear area of Afshar and Monro. It converges to the Whitney/P1 kernel's value (2.5e-4 and 6.7e-5 relative for the SOI strip's two modes at 20 nm) and gives π w0² for a Gaussian to 1.7e-6. Scalar results save `scalar_effective_area` of the nodal field. The key is additive: `field_layout` and every other key are unchanged; PML and bend results get none. [Result format](docs/packages/simcase/overview.md#mode-post-processing).

## 한국어

- `simcase` 모드 결과: **모드마다 유효 면적**. PML이 없는 `em.modes2d` 결과는 `fields.npz`와 summary의 `mode_postprocessing`에 `effective_area`(점 × 모드, m², 기존 레지스트리 양)를 저장합니다. 벡터 결과에서는 저장된 중심 장에서 창의 모든 삼각형에 대해 세 성분을 모두 쓴 A_eff = (Σ A_T |E|²)² / Σ A_T |E|⁴이므로 샘플을 읽는 누구나 같은 값을 얻습니다. 흔한 모드 솔버 형식이며 Afshar와 Monro의 벡터 비선형 면적이 아닙니다. Whitney/P1 커널 값으로 수렴하고(SOI 스트립의 두 모드에서 20 nm일 때 상대 2.5e-4와 6.7e-5) 가우스 장에서 π w0²를 1.7e-6까지 맞춥니다. 스칼라 결과는 노드 장의 `scalar_effective_area`를 저장합니다. 이 키는 추가일 뿐이어서 `field_layout`과 다른 모든 키는 그대로이고, PML·굽힘 결과에는 없습니다. [결과 형식](packages/simcase/overview.md).
