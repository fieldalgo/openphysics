# Fixed

## English

- `simcase` Studio workspace: **usability fixes after a restart, in recovery and in Results**. Session files, the solver and tolerances are unchanged.
  - **Restart.** While the tab holds no optical runs and browser recovery holds an optical session, the Optical waveguide card offers it first: *Resume Optical waveguide · design A, design B · 2:25 PM (this browser)*, next to **Start new**. The Messages line shown when the heated model opens over optical runs now says the tab holds them until it is closed or reloaded, then how to get them back from browser recovery or the session file.
  - **Recovery lists.** Each stored session is listed once, newest first, and names the session file it came from. The cause of the duplicates is fixed: the start page's last-session entry was read once at page load and never refreshed, and an unchanged session saved again after a move between models kept its earlier copy. Browser recovery now stores a session text once.
  - **Older run viewed.** Results and the selected run's settings say *Current inputs differ from this run: this run 600 × 300 nm · Silicon, current 700 × 300 nm · Silicon* instead of *your edits are kept*. The step bar's Results step describes the run shown.
  - **Opened file.** A tab click no longer drops *Opened …json* from the title of a multiphysics model.
  - **Results layout.** Optical Results show the modes table before the field plot.
  - **Template.** The heated silicon waveguide template asks for two modes, so it shows a TE-like and a TM-like mode. The first mode's n_eff, coupled and without heater, is unchanged bit for bit on Linux.
  - **Freshness.** An edit marks out of date only the solve steps whose inputs it changed: removing only the coupling leaves Heat 1 current.
  - **TM-like cells.** They name the dominant share: *TM-like · 96.9 % TM (3.1 % TE)*.

  [Workspace](docs/packages/simcase/workspace.md).

## 한국어

- `simcase` Studio 작업 공간: **다시 켠 뒤, 복구, Results의 사용성 수정**. 세션 파일, 솔버, 허용오차는 그대로입니다.
  - **다시 켠 뒤.** 탭에 광학 실행이 없고 브라우저 복구에 광학 세션이 있으면 Optical waveguide 카드가 그것을 **Start new** 옆에 먼저 제안합니다: *Resume Optical waveguide · design A, design B · 2:25 PM (this browser)*. 광학 실행 위로 가열 모델을 열 때의 Messages는 이제 탭이 그 실행을 닫거나 새로고침할 때까지 가진다고 밝히고, 그 뒤 브라우저 복구나 세션 파일에서 되찾는 방법을 알려 줍니다.
  - **복구 목록.** 저장된 세션은 최신순으로 한 번씩만 나오고, 온 세션 파일의 이름을 밝힙니다. 중복의 원인을 고쳤습니다: 시작 화면의 마지막 세션 항목은 페이지를 열 때 한 번 읽고 새로 고치지 않았고, 모델 사이를 오간 뒤 바뀌지 않은 세션을 다시 저장하면 이전 사본이 남았습니다. 이제 브라우저 복구는 세션 글을 한 번만 저장합니다.
  - **이전 실행 보기.** Results와 고른 실행의 설정은 *your edits are kept* 대신 *Current inputs differ from this run: this run 600 × 300 nm · Silicon, current 700 × 300 nm · Silicon*이라고 씁니다. 단계 막대의 Results 단계는 보고 있는 실행을 설명합니다.
  - **연 파일.** 탭을 눌러도 다중물리 모델 제목에서 *Opened …json*이 사라지지 않습니다.
  - **Results 배치.** 광 Results는 모드 표를 장 그림보다 먼저 보여 줍니다.
  - **템플릿.** 가열 실리콘 도파로 템플릿은 두 모드를 요청하므로 TE-like와 TM-like 모드를 보여 줍니다. 첫 모드의 결합·히터 없음 n_eff는 Linux에서 비트까지 같습니다.
  - **최신 여부.** 편집은 입력이 바뀐 풀이 단계만 out of date로 표시합니다. 결합만 지우면 Heat 1은 최신으로 남습니다.
  - **TM-like 칸.** 주된 비율을 먼저 밝힙니다: *TM-like · 96.9 % TM (3.1 % TE)*.

  [작업 공간](packages/simcase/workspace.md).
