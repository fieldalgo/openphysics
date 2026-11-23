# Changed

## English

- Studio server: a workspace request with an open boundary may carry PML strength 6 as well as 3; 6 is the second solve of Studio's optional PML check, and `/api/workspace/capabilities/v9` lists it as `pml_check_strength`. Every other strength is still refused with the open boundary's message (P1 refused 6). [Open boundary in the optical workspace](docs/packages/simcase/workspace.md#open-boundary-in-the-optical-workspace).

## 한국어

- Studio 서버: 열린 경계가 있는 작업 공간 요청은 PML 강도 3과 함께 6도 담을 수 있습니다. 6은 Studio의 선택적 PML 점검에서 하는 두 번째 풀이이며 `/api/workspace/capabilities/v9`가 `pml_check_strength`로 나열합니다. 다른 강도는 여전히 열린 경계 문구로 거부합니다(P1은 6을 거부했습니다). [광학 작업 공간의 열린 경계](packages/simcase/workspace.md#광학-작업-공간의-열린-경계).
