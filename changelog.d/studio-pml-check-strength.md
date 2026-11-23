# Changed

## English

- Studio server: a workspace request with an open boundary may carry PML strength 6 with a search of 16 as well as strength 3 with 32; these are the per-mode solves of Studio's optional PML check, and `/api/workspace/capabilities/v9` lists them as `pml_check_strength` and `pml_check_search_mode_count`. Any other strength or search, or 6 with 32 and 3 with 16, is refused by name (P1 refused strength 6 and other searches). [Open boundary in the optical workspace](docs/packages/simcase/workspace.md#open-boundary-in-the-optical-workspace).

## 한국어

- Studio 서버: 열린 경계가 있는 작업 공간 요청은 PML 강도 3과 후보 32개 외에 강도 6과 후보 16개도 담을 수 있습니다. 이는 Studio의 선택적 PML 점검에서 모드마다 하는 풀이이며 `/api/workspace/capabilities/v9`가 `pml_check_strength`와 `pml_check_search_mode_count`로 나열합니다. 다른 강도나 후보 수, 그리고 6과 32, 3과 16의 조합은 이름을 밝혀 거부합니다(P1은 강도 6과 다른 후보 수를 거부했습니다). [광학 작업 공간의 열린 경계](packages/simcase/workspace.md#광학-작업-공간의-열린-경계).
