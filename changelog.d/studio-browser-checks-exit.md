# Fixed

## English

- CI: **the Studio browser checks exit when they finish.** The workspace, multiphysics, multiphysics session and project scripts now stop the processes they started (SIGTERM, then SIGKILL after 10 s), print their last line and exit with their status. On 2026-11-24 the project script passed on macOS and then kept running, with a Chrome process left, until the job's time limit cancelled it. `tests/simcase/studio_browser_launch.cjs` checks a child that ignores SIGTERM and one that leaves the output pipe open. [Development guide](docs/development.md#environment).

## 한국어

- CI: **Studio 브라우저 검사가 끝나면 종료합니다.** workspace, multiphysics, multiphysics session, project 스크립트가 이제 자기가 띄운 프로세스를 멈추고(SIGTERM, 10초 뒤 SIGKILL) 마지막 줄을 찍은 뒤 자기 상태로 끝납니다. 2026-11-24 macOS에서 project 스크립트가 통과한 뒤 Chrome 프로세스가 남은 채 작업 시간 한도에 취소될 때까지 돌았습니다. `tests/simcase/studio_browser_launch.cjs`가 SIGTERM을 무시하는 자식과 출력 파이프를 열어 둔 자식으로 확인합니다. [개발 안내](development.md#환경).
