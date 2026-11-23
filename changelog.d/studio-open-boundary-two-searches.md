# Changed

## English

- Studio: an open run also searches 16 candidates near (Search near n_eff + n_SiO2) / 2 to two decimals (1.95 for the default 2.46), so a strip over a substrate shows its mode near the cladding index when enough modes are asked for; modes are listed by descending Re n_eff. Physics › Optical modes shows the second target as text, Study reads *searches near 2.46 and 1.95*, the found line and the job panel name both targets, and the other candidates gain a Search column and a count of the candidates both searches found. Below a target of 1.466 a run searches once. The PML check still searches once per mode. `optical-shapes-v9` documents gain `pml.pml_additional_searches`; closed documents are unchanged byte for byte. The server accepts exactly that second search, and asks a page loaded before this update to reload. Version 10 files written before keep their values and words. [Open boundary document](docs/packages/simcase/workspace.md#open-boundary-document-optical-shapes-v9).

## 한국어

- Studio: 열린 실행은 (Search near n_eff + n_SiO2) / 2(소수 둘째 자리, 기본 2.46이면 1.95) 근처 후보 16개도 검색하므로, 모드를 충분히 요청하면 기판 위 스트립의 클래딩 굴절률 근처 모드가 보입니다. 모드는 Re n_eff 내림차순으로 나열합니다. Physics › Optical modes는 두 번째 목표를 글로 보이고, Study는 *searches near 2.46 and 1.95*로 읽히며, 찾은 개수 줄과 작업 패널은 두 목표를 모두 적고, 다른 후보 표에는 Search 열과 두 검색이 모두 찾은 후보의 개수가 더해집니다. 목표가 1.466 미만이면 한 번만 검색합니다. PML 점검은 여전히 모드마다 한 번 검색합니다. `optical-shapes-v9` 문서에 `pml.pml_additional_searches`가 더해지며 닫힌 문서는 바이트 그대로입니다. 서버는 그 두 번째 검색만 받아들이고, 이 갱신 전에 열린 페이지에는 새로 고치라고 안내합니다. 이전에 쓴 버전 10 파일은 값과 문구를 그대로 유지합니다. [열린 경계 문서](packages/simcase/workspace.md#열린-경계-문서optical-shapes-v9).
