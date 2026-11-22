# Added

## English

- Studio optical application: **the group index of each mode**. **Also compute group index (3 solves)** in Study (off by default) adds `results.group_index = {"wavelength_step": "1 nm"}` to the run's document. With the box off, the document is the `optical-shapes-v8` document as before, byte for byte; the adapter and the run settings are unchanged. The modes table gains an **n_g** column (4 decimals). It reads “—” when the run did not compute n_g, with the help “Turn on Also compute group index in Study”, and “—” with the engine's reason for a mode the engine could not match. Compare gains **n_g A** and **n_g B**. A version 9 session keeps the values in the `group_index` and `group_index_method` slots; the reasons are not kept in session files. The multiphysics table has no n_g column. The single-page Studio now shows every mode's n_g of such a run, and “—” for a null value. [Workspace](docs/packages/simcase/workspace.md#modes-table).

## 한국어

- Studio 광 애플리케이션: **모드마다 군굴절률**. Study의 **Also compute group index (3 solves)**(기본값 꺼짐)는 실행 문서에 `results.group_index = {"wavelength_step": "1 nm"}`를 더합니다. 꺼져 있으면 문서는 이전과 같은 `optical-shapes-v8` 문서이며 바이트 단위로 같고, 어댑터와 실행 settings도 그대로입니다. 모드 표에는 **n_g** 열(소수 4자리)이 더해집니다. 실행이 n_g를 계산하지 않았으면 “Turn on Also compute group index in Study” 도움말과 함께 “—”이고, 엔진이 대응시키지 못한 모드는 엔진의 이유와 함께 “—”입니다. Compare에는 **n_g A**와 **n_g B**가 더해집니다. 버전 9 세션은 값을 `group_index`와 `group_index_method` 칸에 보관하며, 이유는 세션 파일에 남지 않습니다. 다중물리 표에는 n_g 열이 없습니다. 단일 페이지 Studio는 이제 그런 실행의 모든 모드 n_g를 보이고 null 값은 “—”로 보입니다. [작업 공간](packages/simcase/workspace.md#모드-표).
