# Fixed

## English

- `simcase` Studio workspace: **round 11 usability fixes for the next run's inputs, the model tree, restore and small words**. The engine, the result format, the session and document formats and the tolerances are unchanged.
  - **Which inputs the next run uses.** On a viewed run whose inputs differ from the current ones, **Use this run's inputs** (under the Inputs row) loads that run's inputs as the current inputs at once, without a question, since the runs stay; it is one input edit, so Undo takes it back. The title's suffix is shorter, *viewing Run 1 · design A (other inputs)*, and appears on Results and Compare only: on the Model tab the title describes the current inputs alone. The Study settings say which inputs the next run uses, *Next run uses 700 × 300 nm · Silicon · λ 1550 nm · core mesh 30 nm · Modes to find 2*.
  - **Model tree.** A node under the pointer changes its border only, so on Results or Compare, where no node is selected, a hovered node no longer reads as the selected one.
  - **Restore on each model card.** The Heated silicon waveguide card offers its newest browser recovery session, as the Optical waveguide card does; the *Continue where you left off* box lists only the sessions no card offers. A record that is the same as the session file it was saved to names the file's save time, *same as file …json, saved 9:24 PM*, not the record's.
  - **Model back at a run.** The multiphysics sentence reads *No need to run: Run 1 already has these results. Run again to make a copy*; *“Also solve without heater” is ticked again* still follows when it applies.
  - **Smaller items.** Every model's run button reads **Run study**. Add coupling opened for one input lists only the outputs that input can take. A fresh multiphysics template reads *New model · not saved*. Compare opens with the two newest runs, A the older, and on Compare the two run cards end with *· Compare A* and *· Compare B*. The wavelength can be edited in the Study settings as in Physics › Optical modes. A restored multiphysics record that matched its saved or opened file reads *Recovered from this browser · same as file …*. Workspace tools say *Restore … from this browser*.
  - **Run table CSV.** Two columns follow `origin`, so every earlier column keeps its place: `effective_index_imag [1]` (Im n_eff, 0 for a lossless run) and `group_index [1]` (n_g, empty when absent). A run with complex n_eff, which the export refused before, is written.

  [Workspace](docs/packages/simcase/workspace.md).

## 한국어

- `simcase` Studio 작업 공간: **다음 실행의 입력, 모델 트리, 복원, 작은 문구의 11차 사용성 수정**. 엔진, 결과 형식, 세션·문서 형식, 허용오차는 그대로입니다.
  - **다음 실행이 쓰는 입력.** 입력이 현재 입력과 다른 실행을 보고 있으면 **Use this run's inputs**(Inputs 행 아래)가 그 실행의 입력을 묻지 않고 바로 현재 입력으로 불러옵니다. 실행은 그대로 남기 때문입니다. 입력 편집 하나이므로 Undo가 되돌립니다. 제목의 덧붙임은 *viewing Run 1 · design A (other inputs)*로 짧아졌고 Results와 Compare에서만 나옵니다: Model 탭의 제목은 현재 입력만 설명합니다. Study 설정은 다음 실행이 쓸 입력을 밝힙니다: *Next run uses 700 × 300 nm · Silicon · λ 1550 nm · core mesh 30 nm · Modes to find 2*.
  - **모델 트리.** 포인터가 올라간 노드는 테두리만 바뀌므로, 고른 노드가 없는 Results나 Compare에서 포인터 아래 노드가 더는 고른 노드처럼 보이지 않습니다.
  - **모델 카드마다 복원.** Heated silicon waveguide 카드도 Optical waveguide 카드처럼 가장 새 브라우저 복구 세션을 제안하며, *Continue where you left off* 상자는 어느 카드도 제안하지 않는 세션만 나열합니다. 저장했던 세션 파일과 같은 기록은 기록 시각이 아니라 파일 저장 시각을 밝힙니다: *same as file …json, saved 9:24 PM*.
  - **실행과 다시 같아진 모델.** 다중물리 문장은 *No need to run: Run 1 already has these results. Run again to make a copy*이며, 해당하면 *“Also solve without heater” is ticked again*이 여전히 뒤따릅니다.
  - **작은 항목.** 모든 모델의 실행 버튼은 **Run study**입니다. 입력 하나를 위해 연 Add coupling은 그 입력이 받을 수 있는 출력만 나열합니다. 새 다중물리 템플릿은 *New model · not saved*로 읽힙니다. Compare는 가장 새 실행 두 개로 열리고 오래된 쪽이 A이며, Compare에서 두 실행 카드 끝에 *· Compare A*, *· Compare B*가 붙습니다. 파장은 Physics › Optical modes처럼 Study 설정에서도 고칠 수 있습니다. 저장했거나 연 파일과 같았던 다중물리 기록을 복구하면 *Recovered from this browser · same as file …*로 읽힙니다. Workspace tools는 *Restore … from this browser*라고 씁니다.
  - **실행 표 CSV.** 이전 열이 모두 제자리에 있도록 `origin` 뒤에 두 열이 붙습니다: `effective_index_imag [1]`(Im n_eff, 무손실 실행은 0)과 `group_index [1]`(n_g, 없으면 빈칸). 예전에 내보내기가 거부하던 복소 n_eff 실행도 씁니다.

  [작업 공간](packages/simcase/workspace.md).
