# Fixed

## English

- `simcase` Studio workspace: **round 10 usability fixes for loss words, Compare, recovery and the model tree**. The engine, the result format, the session file format and the tolerances are unchanged.
  - **Absorption loss.** The loss column of the modes table (optical Results and the multiphysics Modes page) and of Compare is *Absorption loss (dB/cm)*. Every cell's help and the note under the table say it counts material absorption (k) only and that leakage and radiation are not computed in a closed window; a lossless run still reads *0 dB/cm*. The formula, the 4 significant digits and the no-threshold rule are unchanged. A multiphysics result with an open boundary (PML), whose Im n_eff includes leakage into the PML, reads *Loss (dB/cm)* with its own help.
  - **Compare.** The matched-modes table has *Absorption loss A (dB/cm)* and *Absorption loss B (dB/cm)* on every row (a matched pair shows the mean of its members) and scrolls inside its box on a narrow screen. The field plots are as tall as the Results plot and Compare opens with their middle, centred on the core, in view; *No point selected.* is under each plot. A run clicked in the run list on Compare is selected and Compare stays, with **Open Run N in Results** under the list.
  - **Session file named.** After a session file is saved or opened, the title names it until the model or a run changes: a page, a selected run, a Compare choice or a field view is no longer a change. A restored notebook whose browser record still matched its file reads *Recovered from this browser · same as file …*, not *not saved to a file*.
  - **Restore.** The Models page says *Restore from this browser* for browser recovery (the card: *Restore from this browser · Optical waveguide · Run 1 · design A, Run 2 · 2:25 PM · same as file …*); **Open session file…** is for files. A restore opens the page that was shown (Model, Results or Compare) with the run that was selected. Browser recovery records gain two optional fields for this, the page and whether the notebook still matched its opened file; older records restore as before.
  - **One selected run.** Exactly one run card reads as selected, and the model tree marks no Study node on Results or Compare (the multiphysics tree marks the results page shown).
  - **Model tree.** The model builder of every model is an ARIA tree, *Model tree*, with tree items, levels, selection and groups that open and close; one tab stop, Up, Down, Home, End, Enter, Space, Left and Right. The multiphysics group *Study 1* is now *Study*, so no two items share a name.
  - **Smaller items.** An opened multiphysics result reads *Loaded from file, not recomputed; integrity check passed (it does not show who made the file).* The heated session's save message says that the tab's Optical waveguide runs are not in its file. *Current inputs differ from this run* in the step bar is in the plain text colour. The multiphysics dock and footer name a named run *Run N · name*, as the optical app does.

  [Workspace](docs/packages/simcase/workspace.md).

## 한국어

- `simcase` Studio 작업 공간: **손실 문구, Compare, 복구, 모델 트리의 10차 사용성 수정**. 엔진, 결과 형식, 세션 파일 형식, 허용오차는 그대로입니다.
  - **흡수 손실.** 모드 표(광 Results와 다중물리 Modes 페이지)와 Compare의 손실 열은 *Absorption loss (dB/cm)*입니다. 모든 칸의 도움말과 표 아래 안내는 재료 흡수(k)만 센다는 것과 닫힌 창에서는 누설과 복사를 계산하지 않는다는 것을 밝히며, 무손실 실행은 여전히 *0 dB/cm*입니다. 식, 유효숫자 4자리, 문턱값 없음은 그대로입니다. Im n_eff가 PML로의 누설을 포함하는 열린 경계(PML) 다중물리 결과는 자기 도움말과 함께 *Loss (dB/cm)*로 읽힙니다.
  - **Compare.** 짝지은 모드 표의 모든 행에 *Absorption loss A (dB/cm)*와 *Absorption loss B (dB/cm)*가 있고(짝지어진 쌍은 두 모드의 평균), 좁은 화면에서는 자기 상자 안에서 스크롤됩니다. 장 그림은 Results 그림과 같은 높이이며, Compare를 열면 코어를 가운데 둔 그림의 가운데가 보입니다. *No point selected.*는 각 그림 아래에 있습니다. Compare에서 실행 목록의 실행을 누르면 그 실행을 고르고 Compare에 남으며, 목록 아래에 **Open Run N in Results**가 있습니다.
  - **세션 파일 이름.** 세션 파일을 저장하거나 연 뒤에는 모델이나 실행이 바뀔 때까지 제목이 그 파일을 밝힙니다: 페이지, 고른 실행, Compare 선택, 장 보기는 더 이상 변경이 아닙니다. 브라우저 기록이 그 파일과 아직 같았던 복구 노트북은 *not saved to a file*이 아니라 *Recovered from this browser · same as file …*로 읽힙니다.
  - **복구.** Models 페이지는 브라우저 복구를 *Restore from this browser*로 부릅니다(카드: *Restore from this browser · Optical waveguide · Run 1 · design A, Run 2 · 2:25 PM · same as file …*). **Open session file…**은 파일에 씁니다. 복구는 보이던 페이지(Model, Results, Compare)를 그때 고른 실행과 함께 엽니다. 이를 위해 브라우저 복구 기록에 선택 필드 두 개, 페이지와 노트북이 연 파일과 아직 같았는지가 생겼으며, 예전 기록은 전과 같이 복구됩니다.
  - **고른 실행 하나.** 고른 것으로 보이는 실행 카드는 정확히 하나이며, 모델 트리는 Results나 Compare에서 Study 노드를 표시하지 않습니다(다중물리 트리는 보이는 결과 페이지를 표시).
  - **모델 트리.** 모든 모델의 모델 빌더는 트리 항목, 수준, 선택, 열고 닫는 그룹을 가진 ARIA 트리 *Model tree*입니다. 탭 정지는 하나이고 Up, Down, Home, End, Enter, Space, Left, Right를 씁니다. 다중물리 그룹 *Study 1*은 이제 *Study*이므로 두 항목이 같은 이름을 갖지 않습니다.
  - **작은 항목.** 연 다중물리 결과는 *Loaded from file, not recomputed; integrity check passed (it does not show who made the file).*로 읽힙니다. 가열 세션의 저장 메시지는 탭의 Optical waveguide 실행이 그 파일에 없다고 밝힙니다. 단계 막대의 *Current inputs differ from this run*은 일반 글자색입니다. 다중물리 도크와 하단은 이름 붙은 실행을 광학 앱처럼 *Run N · 이름*으로 부릅니다.

  [작업 공간](packages/simcase/workspace.md).
