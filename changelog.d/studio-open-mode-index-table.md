# Added

## English

- Studio: **material indices at the run's wavelength.** `workspace-open-boundary.mjs` has `INDEX_TABLE`, the real index of the ten Studio materials from 1400 to 1700 nm every 10 nm (physmat, five decimals), and `indexAt(material, wavelength)`, its linear interpolation, for the guided / leaky notes of open-boundary modes. `tests/simcase/test_studio_index_table.py` checks it against physmat at 301 wavelengths (within 1e-4; 7.5e-6 at most). No page text, document or file changes; `INDEX_1550` is unchanged. [Open boundary in the optical workspace](docs/packages/simcase/workspace.md#open-boundary-in-the-optical-workspace).

## 한국어

- Studio: **실행 파장에서의 재료 굴절률.** `workspace-open-boundary.mjs`에 Studio 재료 10종의 1400–1700 nm, 10 nm 간격 실수 굴절률 표 `INDEX_TABLE`(physmat, 소수 다섯째 자리)과 그 선형 보간 `indexAt(material, wavelength)`이 생겼습니다. 열린 경계 모드의 도파/누설 안내에 씁니다. `tests/simcase/test_studio_index_table.py`가 301개 파장에서 physmat과 비교합니다(1e-4 이내, 최대 7.5e-6). 화면 문구, 문서, 파일은 바뀌지 않으며 `INDEX_1550`도 그대로입니다. [광학 작업 공간의 열린 경계](packages/simcase/workspace.md#광학-작업-공간의-열린-경계).
