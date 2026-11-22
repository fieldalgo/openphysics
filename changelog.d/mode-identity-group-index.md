# Added

## English

- `simcase` mode results: **the group index of a single study**. An `em.modes2d` single study with `results.group_index = {"wavelength_step": "1 nm"}` (the default step; 1 pm to λ0/20) also solves the same mesh at λ0 ∓ Δλ, with each material evaluated at each wavelength, matches each mode with the sweep's resolved-mode tracker tests (`electric-l2-assignment-v1`, scalar `scalar-l2-assignment-v1`) and saves the existing `group_index` n_g = n_eff − λ0 dn_eff/dλ0 by the central difference. A mode the tracker cannot match is `null` with a reason, and the run succeeds. The summary adds `group_index_method` (method, step, tracker, reasons). The key is refused for sweeps (a wavelength sweep already gives n_g), PML, bend, lossy materials and multiphysics documents; the registry gains `wavelength_step`. Results without the key are unchanged. The slab case is within 2.3e-4 of the analytic central difference; a dispersive fibre's TE01 is within 1.2e-4 relative of the exact value. [Group index of a single study](docs/packages/simcase/group_index.md).

## 한국어

- `simcase` 모드 결과: **단일 study의 군굴절률**. `results.group_index = {"wavelength_step": "1 nm"}`(기본 간격, 1 pm~λ0/20)를 준 `em.modes2d` 단일 study는 같은 메시를 λ0 ∓ Δλ에서도 풀고(재료는 파장마다 값을 구함), sweep의 분해 모드 추적기 검사(`electric-l2-assignment-v1`, 스칼라는 `scalar-l2-assignment-v1`)로 모드를 대응시킨 뒤, 기존 `group_index` n_g = n_eff − λ0 dn_eff/dλ0를 중앙 차분으로 저장합니다. 추적기가 대응시키지 못한 모드는 이유와 함께 `null`이며 실행은 성공합니다. summary에는 `group_index_method`(방법, 간격, 추적기, 이유)가 더해집니다. sweep(파장 sweep은 이미 n_g를 줌), PML, 굽힘, 손실 재료, 다중물리 문서에서는 이 키를 거절하며, 레지스트리에 `wavelength_step`이 더해집니다. 이 키가 없는 결과는 그대로입니다. 슬래브는 해석적 중앙 차분과 2.3e-4 이내, 분산 광섬유의 TE01은 정확한 값과 상대 1.2e-4 이내입니다. [단일 study의 군굴절률](packages/simcase/group_index.md).
