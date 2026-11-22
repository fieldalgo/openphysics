# Added

## English

- Studio: the optical document builder can open edges of the window (adapter `optical-shapes-v9`, `/api/workspace/capabilities/v9`; no control on the page yet). Each open edge gets a 1–2 µm PML outside the 3 × 2.4 µm window with a PEC outer wall; shapes along an open edge continue through it. The PML settings are fixed (strength 3, order 2, physical fraction 0.5, a search of 16 candidates), and the search target defaults to (n_max + n_SiO2) / 2 (2.46 for a silicon core). With every edge closed the document is the `optical-shapes-v8` one byte for byte, and capabilities v1–v8 are unchanged. The server refuses another PML in a workspace request. [Open boundary document](docs/packages/simcase/workspace.md#open-boundary-document-optical-shapes-v9).

## 한국어

- Studio: 광학 문서 작성기가 계산창의 변을 열 수 있습니다(어댑터 `optical-shapes-v9`, `/api/workspace/capabilities/v9`. 페이지의 조작은 아직 없음). 열린 변마다 3 × 2.4 µm 계산창 바깥에 1–2 µm PML과 PEC 바깥 벽이 놓이고, 열린 변에 놓인 형상은 그 층을 지나 이어집니다. PML 설정은 고정이며(세기 3, 차수 2, 물리 비율 0.5, 후보 16개 검색), 검색 목표의 기본값은 (n_max + n_SiO2) / 2입니다(실리콘 코어는 2.46). 모든 변이 닫히면 문서는 `optical-shapes-v8` 문서와 바이트 단위로 같고 capability v1–v8은 바뀌지 않습니다. 서버는 작업공간 요청의 다른 PML을 거부합니다. [열린 경계 문서](packages/simcase/workspace.md#열린-경계-문서optical-shapes-v9).
