# Fixed

## English

- Studio: **a running job is waited for as long as the server says it runs.** The optical job monitor stopped after three minutes even while the server answered *running*, so 12–16 min open-boundary solves needed Resume three or four times. The three-minute limit now counts only time without an answer (failed status requests are retried every 0.7 s), then the job detaches with *The server has not answered for three minutes. Resume to check this job again.* The panel shows the elapsed time as m:ss and what the run solves from its record (*Open boundary · 2 modes · PML check (up to 2 more solves)*, *PML check · mode 1 of 2*); no stage, as the server reports none. Unit tests with a fake clock: a 12 min job, polls failing past three minutes, Resume afterwards. [Workspace](docs/packages/simcase/workspace.md).

## 한국어

- Studio: **서버가 실행 중이라고 답하는 동안 작업을 계속 기다립니다.** 광학 작업 감시는 서버가 *running*이라고 답해도 3분 뒤 멈춰, 12–16분 걸리는 열린 경계 계산에 Resume을 서너 번 눌러야 했습니다. 이제 3분 제한은 답이 없는 시간만 세고(실패한 상태 요청은 0.7초마다 다시 시도) 그 뒤 *The server has not answered for three minutes. Resume to check this job again.*으로 분리합니다. 패널은 경과 시간을 m:ss로, 실행이 푸는 것을 기록에서 보여 줍니다(*Open boundary · 2 modes · PML check (up to 2 more solves)*, *PML check · mode 1 of 2*). 서버가 단계를 보고하지 않으므로 단계는 없습니다. 가짜 시계로 한 단위 테스트: 12분 작업, 3분 넘게 실패하는 조회, 그 뒤 Resume. [워크스페이스](packages/simcase/workspace.md).
