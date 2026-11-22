# Fixed

## English

- `simcase` Studio workspace: **round 9 usability fixes for run names, recovery, Compare and loss**. The engine, the result format, the session format and the tolerances are unchanged.
  - **Matching words.** The dock note on Results and Compare now reads *Compare matches modes by field overlap*, the same as Compare's own words, instead of saying that modes are not matched between runs.
  - **Recovery entries.** Records with the same inputs and runs count as one session, even when they differ only in the view, the selected run, the Compare choice, the runs' origin, the file link or the save time. The list shows the newest of them and names the session file if any merged record had one. The cause of the duplicates is fixed: opening a session file or recovering one re-marked the origin of every run, so the first save of a new page kept the stored copy of the same runs as a second earlier session. The session that the Optical waveguide card resumes is no longer listed again in the box above it.
  - **Viewed run.** The dock heading, the status bar, the title and the step bar describe the selected run and agree with each other: *Run 1 · design A · current inputs differ from this run* (the status bar adds *Run 2 has them*), and the title adds *viewing Run 1 · design A, which used other inputs* when no input was edited. The run list, the Compare pickers and headings, and the recovery entries name runs by number with their name.
  - **Layout.** The *Inputs* label of the selected run stays on one line. The line under the Results heading names each difference once (*…; unchanged: λ 1550 nm · core mesh 30 nm*). Compare's numbers keep their unit on the same line. The closed matched-modes picker shows the whole pair: *A mode 2 ↔ B mode 2 · overlap 0.98 · TM-like*.
  - **Switch message.** The message shown when the heated model opens over optical runs is one short line, *Optical waveguide runs stay in this tab · Models › Optical waveguide returns to them*. The rest is under **More**.
  - **Loss.** A result with Im n_eff exactly 0 reads *0 dB/cm*. The cell help and the note under the table say this is absorption only, with every material at k = 0. Loss is dB/cm = 20·log10(e)·k0·Im(n_eff)/100, shown to 4 significant digits, with no threshold.
  - **Opened files.** An opened multiphysics result reads *Loaded from file, not recomputed; the file passed its damage check (this does not show who made it).*

  [Workspace](docs/packages/simcase/workspace.md).

## 한국어

- `simcase` Studio 작업 공간: **실행 이름, 복구, Compare, 손실의 9차 사용성 수정**. 엔진, 결과 형식, 세션 형식, 허용오차는 그대로입니다.
  - **짝짓기 문구.** Results와 Compare의 도크 안내는 이제 모드를 실행 사이에서 짝짓지 않는다고 하지 않고, Compare 자신의 문구와 같은 *Compare matches modes by field overlap*을 씁니다.
  - **복구 항목.** 입력과 실행이 같은 기록은 보기, 고른 실행, Compare 선택, 실행의 출처, 파일 연결, 저장 시각만 달라도 한 세션으로 칩니다. 목록은 그중 가장 새 기록을 보여 주고, 합친 기록 중 하나라도 세션 파일을 가리켰으면 그 이름을 붙입니다. 중복의 원인을 고쳤습니다: 세션 파일을 열거나 복구하면 모든 실행의 출처 표시가 바뀌어, 새 페이지의 첫 저장이 같은 실행의 저장된 사본을 또 하나의 이전 세션으로 남겼습니다. Optical waveguide 카드가 이어 여는 세션은 그 위 상자에 다시 나오지 않습니다.
  - **보고 있는 실행.** 도크 제목, 상태 표시줄, 제목 표시줄, 단계 막대가 고른 실행을 설명하고 서로 맞습니다: *Run 1 · design A · current inputs differ from this run*(상태 표시줄은 *Run 2 has them*을 덧붙임). 입력을 편집하지 않았으면 제목 표시줄이 *viewing Run 1 · design A, which used other inputs*를 덧붙입니다. 실행 목록, Compare 선택 목록과 제목, 복구 항목은 실행을 번호와 이름으로 가리킵니다.
  - **배치.** 고른 실행의 *Inputs* 이름표는 한 줄로 남습니다. Results 제목 아래 줄은 다른 부분을 한 번씩만 씁니다(*…; unchanged: λ 1550 nm · core mesh 30 nm*). Compare의 숫자는 단위와 같은 줄에 있습니다. 닫힌 짝지은 모드 선택은 쌍 전체를 보여 줍니다: *A mode 2 ↔ B mode 2 · overlap 0.98 · TM-like*.
  - **전환 메시지.** 광학 실행 위로 가열 모델을 열 때의 메시지는 짧은 한 줄 *Optical waveguide runs stay in this tab · Models › Optical waveguide returns to them*이고, 나머지는 **More** 안에 있습니다.
  - **손실.** Im n_eff가 정확히 0인 결과는 *0 dB/cm*로 읽힙니다. 칸 도움말과 표 아래 안내는 이것이 모든 재료가 k = 0인 흡수만의 값이라고 밝힙니다. 손실은 dB/cm = 20·log10(e)·k0·Im(n_eff)/100이며 유효숫자 4자리로, 문턱값 없이 보입니다.
  - **연 파일.** 연 다중물리 결과는 *Loaded from file, not recomputed; the file passed its damage check (this does not show who made it).*로 읽힙니다.

  [작업 공간](packages/simcase/workspace.md).
