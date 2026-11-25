# Changed

## English

- Studio: the heated model keeps its runs' maps within the 16.8 MB budget of the optical fields, shared by the tab, File › Save, the project entry and browser recovery: when maps arrive (a result, a recompute, an opened or restored session) the selected run's are kept first, then the pinned runs', then the newest; selecting, pinning or naming a run lets no map go. A run without its maps keeps n_eff, the coupling check and the iteration history; the line beside Run study, Messages, the run list and Results say which runs keep their values only, in the optical words with "maps". Browser recovery of a session over 16 MiB keeps maps in the same order (newest first) instead of the selected and pinned runs' only. The budget and its order are one module shared with the optical model, whose behaviour is unchanged. [Workspace](docs/packages/simcase/workspace.md#keeping-heated-runs-values-and-maps).

## 한국어

- Studio: 가열 모델은 실행의 맵을 광학 필드와 같은 16.8 MB 예산 안에서 보관하며, 이 예산은 탭, File › Save, 프로젝트 항목, 브라우저 복구가 함께 씁니다. 맵이 도착하면(결과, 재계산, 열거나 복원한 세션) 고른 실행의 맵을 먼저, 그다음 고정한 실행, 그다음 최신 실행의 맵을 보관합니다. 실행을 고르거나 고정하거나 이름 지어도 맵을 놓지 않습니다. 맵 없는 실행은 n_eff, 결합 검사, 반복 이력을 보관하고, Run study 옆 줄, Messages, 실행 목록, Results가 어느 실행이 값만 보관하는지 광학 문구에 "maps"를 넣어 말합니다. 16 MiB를 넘는 세션의 브라우저 복구는 고른 실행과 고정한 실행의 맵만이 아니라 같은 순서(최신부터)로 맵을 둡니다. 예산과 순서는 광학 모델과 함께 쓰는 한 모듈이며 광학 모델의 동작은 바뀌지 않습니다. [작업 공간](packages/simcase/workspace.md#가열-실행-보관-값과-맵).
