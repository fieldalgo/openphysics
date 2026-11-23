# Added

## English

- `simcase`: `physics.<name>.pml.pml_additional_searches` lists 1 to 3 further open-boundary searches (`target_effective_index` and `pml_search_mode_count` each) beside the primary one, so `em.modes2d` finds modes far from one target, such as the mode near the cladding index of a strip over a substrate. The searches share one mesh and pencil; a candidate that repeats an earlier one (index within 1e-9 and transverse-field overlap at least 0.99) is recorded as `duplicate_candidate` and never selected, and the eligible candidates with the highest Re n_eff are returned. The record is `openphysics.pml-candidates/3` and the summary's `selection` is `pml_heuristic_descending_real_index`. Vector formulation and single studies only; without the key results are unchanged. [PML modes](docs/packages/simcase/pml_modes.md#further-searches).

## 한국어

- `simcase`: `physics.<name>.pml.pml_additional_searches`는 주 검색 외의 열린 경계 추가 검색 1~3개(각각 `target_effective_index`와 `pml_search_mode_count`)를 나열합니다. 그래서 `em.modes2d`가 기판 위 스트립의 클래딩 굴절률 근처 모드처럼 목표 하나에서 먼 모드도 찾습니다. 검색들은 메시와 pencil을 함께 쓰고, 앞 후보를 되풀이하는 후보(굴절률 차 1e-9 이내, 횡방향 모드장 겹침 0.99 이상)는 `duplicate_candidate`로 기록하고 선택하지 않으며, Re n_eff가 가장 큰 적격 후보를 반환합니다. 기록은 `openphysics.pml-candidates/3`이고 요약의 `selection`은 `pml_heuristic_descending_real_index`입니다. 벡터 정식화와 단일 study만 해당하며, 키가 없으면 결과는 바뀌지 않습니다. [PML 모드](packages/simcase/pml_modes.md#추가-검색).
