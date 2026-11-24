# Added

## English

- Studio: optical session files of version 12 keep each run's number (`number`, after `job`, inside the run's check value), so Run 7 stays Run 7 after File › Open, Open project and Restore. Version 12 is written only when a run's number is not its place in the list (a run was dropped); a session numbered 1, 2, 3 … is still written as version 11, 10, 9 or 7, byte for byte. The reader refuses a missing, invalid, repeated or out-of-order number by name. A Studio before this one refuses a version 12 file as newer than it reads, and does not take over a browser-recovery record that holds one. Browser-recovery records may also keep the project's name (`project`), which earlier Studios ignore. [Workspace](docs/packages/simcase/workspace.md).

## 한국어

- Studio: 버전 12 광학 세션 파일은 각 실행의 번호(`number`, `job` 다음, 실행의 검사값 안)를 담으므로 File › Open, Open project, Restore 뒤에도 Run 7은 Run 7입니다. 버전 12는 실행 번호가 목록 안 자리와 다를 때(실행 하나가 빠졌을 때)만 쓰고, 1, 2, 3 … 으로 번호가 매겨진 세션은 지금처럼 버전 11, 10, 9, 7로 바이트 그대로 씁니다. 읽는 쪽은 없거나, 잘못되었거나, 겹치거나, 순서가 어긋난 번호를 이름을 들어 거부합니다. 이전 Studio는 버전 12 파일을 읽을 수 있는 것보다 새 파일로 거부하고, 그런 파일을 담은 브라우저 복구 기록을 넘겨받지 않습니다. 브라우저 복구 기록은 프로젝트 이름(`project`)도 담을 수 있으며 이전 Studio는 이를 무시합니다. [작업 공간](packages/simcase/workspace.md).
