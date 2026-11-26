# Changed

## English

- Studio: **Run study asks before an open-boundary run whose group index was carried over.** When the group index was already on before the last run completed in the tab (and not turned off since), Run study with an open boundary opens *Group index is still on*: *This open-boundary run with group index takes about 3 min (3 solves).* (the plan line's estimate; *… about three times as long (3 solves).* without one), with **Run with group index**, **Turn off group index and run** (the same run as unticking the box and pressing Run study) and **Cancel** (nothing is run or changed). It does not ask when the group index was turned on after the last completed run, for a closed window or for the multiphysics model, and never together with the slab question. No session, project or recovery format change; no computed value changes. `tests/simcase/studio_round31.cjs` and the workspace browser check cover it. [Workspace](docs/packages/simcase/workspace.md#first-optical-study).

## 한국어

- Studio: **군굴절률이 이어져 켜진 열린 경계 실행 전에 Run study가 묻습니다.** 탭에서 마지막으로 완료된 실행 전부터 군굴절률이 켜져 있었고 그 뒤 끄지 않았으면, 열린 경계의 Run study가 *Group index is still on*을 엽니다: *This open-boundary run with group index takes about 3 min (3 solves).*(계획 줄의 어림값, 없으면 *… about three times as long (3 solves).*)와 **Run with group index**, **Turn off group index and run**(확인란을 끄고 Run study를 누른 것과 같은 실행), **Cancel**(아무것도 실행하거나 바꾸지 않음). 마지막으로 완료된 실행 뒤에 군굴절률을 켰을 때, 닫힌 창, 다중물리 모델에서는 묻지 않으며 슬래브 질문과 함께 나오지 않습니다. 세션, 프로젝트, 복구 형식과 계산 값은 바뀌지 않습니다. `tests/simcase/studio_round31.cjs`와 workspace 브라우저 검사가 확인합니다. [워크스페이스](packages/simcase/workspace.md#첫-광학-해석).
