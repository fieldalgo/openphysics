# Fixed

## English

- Studio: **restoring both models of a project no longer stops browser recovery.** The second restore of the pair could continue a stored record this tab had replaced while the server checked the model; every later save then read as another tab's change (*browser recovery changed in another tab*, with one tab open) and automatic recovery stopped. A restore now writes this tab's pending recovery save first and continues the record that is stored; a change made by another tab is still detected. [Workspace](docs/packages/simcase/workspace.md).

## 한국어

- Studio: **프로젝트의 두 모델을 복원해도 브라우저 복구가 더는 멈추지 않습니다.** 한 쌍의 두 번째 복원이 서버가 모델을 확인하는 동안 이 탭이 바꾼 저장 기록을 이어 갈 수 있었고, 그러면 이후의 모든 저장이 다른 탭의 변경으로 읽혀(탭이 하나뿐인데도 *browser recovery changed in another tab*) 자동 복구가 멈췄습니다. 이제 복원은 이 탭의 대기 중인 복구 저장을 먼저 쓰고 저장된 기록을 이어 갑니다. 다른 탭이 한 변경은 그대로 감지합니다. [워크스페이스](packages/simcase/workspace.md).
