# Changed

## English

- Studio browser checks: **the browser launch is retried once.** The workspace, multiphysics and multiphysics session scripts wait up to 60 s (was 30 s) for the browser's DevTools endpoint and, when it does not answer, start the browser once more on a new port with a new profile; `report.json` records each failed attempt's command line, exit code and stderr tail, and a second failure still fails the check. Only the launch is retried. Two `windows-2022` platform-install runs had failed with *Browser DevTools endpoint unavailable* before any Studio stage. [Development guide](docs/development.md#environment).

## 한국어

- Studio 브라우저 검사: **브라우저 실행을 한 번 다시 시도합니다.** workspace, multiphysics, multiphysics session 스크립트는 브라우저의 DevTools 엔드포인트를 최대 60초(이전 30초) 기다리고, 응답이 없으면 새 포트와 새 프로필로 한 번 더 띄웁니다. `report.json`은 실패한 시도마다 명령줄, 종료 코드, stderr 끝부분을 기록하며, 두 번째 실패는 여전히 검사를 실패시킵니다. 다시 시도하는 것은 실행뿐입니다. `windows-2022` platform-install 실행 두 번이 Studio 단계 전에 *Browser DevTools endpoint unavailable*로 실패했습니다. [개발 안내](development.md#환경).
