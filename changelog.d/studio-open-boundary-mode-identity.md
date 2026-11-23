# Changed

## English

- Studio: an open run's modes table shows Polarization and A_eff over the 3 × 2.4 µm window with the PML excluded, and Re n_g; **Also compute group index** works with an open boundary (its help states the measured mesh error of n_g). Compare matches an open run with a closed or open one on the intersection of their physical windows. Runs saved by the previous version get their TE fraction and A_eff from their stored field and are written as they were; new open runs keep the engine's values and a complex `group_index` `{"re", "im"}` in version 10 files. Closed runs and files of versions 6, 7 and 9 are written byte for byte as before. [Mode identity with an open boundary](docs/packages/simcase/workspace.md#mode-identity-with-an-open-boundary).

## 한국어

- Studio: 열린 실행의 모드 표는 PML을 뺀 3 × 2.4 µm 창에서 구한 Polarization과 A_eff, 그리고 Re n_g를 보입니다. **Also compute group index**는 열린 경계에서도 동작하며 도움말에 측정한 n_g의 메시 오차를 적습니다. Compare는 열린 실행을 닫힌 실행이나 다른 열린 실행과 두 물리 창이 겹치는 영역에서 짝짓습니다. 이전 버전이 저장한 실행은 저장된 장으로 TE 비율과 A_eff를 얻고 그대로 씁니다. 새 열린 실행은 버전 10 파일에 엔진 값과 복소 `group_index` `{"re", "im"}`를 보존합니다. 닫힌 실행과 버전 6, 7, 9 파일은 이전처럼 바이트 그대로 씁니다. [열린 경계의 모드 식별](packages/simcase/workspace.md#열린-경계의-모드-식별).
