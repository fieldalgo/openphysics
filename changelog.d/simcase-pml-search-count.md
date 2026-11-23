# Added

## English

- `simcase`: `physics.<name>.pml.pml_search_mode_count` sets how many open-boundary candidates `em.modes2d` searches before the physical-fraction filter (an integer from 1 to 64 and at least `mode_count`; in a sweep at least the tracker's search count). A wider search finds physical modes that the default search near the target misses. Without the key the search is max(2 `mode_count`, 6) as before and nothing is added to `defaults_applied`, so existing documents give the same results; the result format is unchanged. `physmat` registers the count `pml_search_mode_count`. [PML modes](docs/packages/simcase/pml_modes.md#api-and-results).

## 한국어

- `simcase`: `physics.<name>.pml.pml_search_mode_count`는 `em.modes2d`가 물리 비율 필터를 적용하기 전에 찾는 열린 경계 후보 수를 정합니다(1부터 64까지의 정수, `mode_count` 이상, 스윕에서는 추적기의 검색 수 이상). 검색을 넓히면 목표 근처의 기본 검색이 놓치는 물리 모드를 찾습니다. 키가 없으면 검색 수는 이전처럼 max(2 `mode_count`, 6)이고 `defaults_applied`에 아무것도 더하지 않으므로 기존 문서의 결과는 같습니다. 결과 형식은 바뀌지 않습니다. `physmat`은 개수 `pml_search_mode_count`를 등록합니다. [PML 모드](packages/simcase/pml_modes.md#api와-결과).
