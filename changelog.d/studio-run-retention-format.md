# Changed

## English

- Studio: the optical model keeps up to 20 runs (it kept six). A session of more than six runs is written as optical session version 13, whose runs are those of version 12; a session of six runs or fewer is still written as version 12, 11, 10, 9 or 7, byte for byte. File › Open, Open project, Restore and Add runs from file read up to 20 runs; a version 12 or earlier file still holds at most six. A Studio before this one refuses a version 13 file as newer than it reads, alone or in a project file, and does not take over a browser-recovery record that holds one. [Workspace](docs/packages/simcase/workspace.md).

## 한국어

- Studio: 광학 모델은 실행을 최대 20개까지 보관합니다(이전에는 6개). 실행이 6개를 넘는 세션은 광학 세션 버전 13으로 쓰며, 그 실행 기록은 버전 12와 같습니다. 실행이 6개 이하인 세션은 지금처럼 버전 12, 11, 10, 9, 7로 바이트 그대로 씁니다. File › Open, Open project, Restore, Add runs from file은 실행을 최대 20개까지 읽고, 버전 12 이하 파일은 여전히 최대 6개를 담습니다. 이전 Studio는 버전 13 파일을 단독으로든 프로젝트 파일 안에서든 읽을 수 있는 것보다 새 파일로 거부하고, 그런 파일을 담은 브라우저 복구 기록을 넘겨받지 않습니다. [작업 공간](packages/simcase/workspace.md).
