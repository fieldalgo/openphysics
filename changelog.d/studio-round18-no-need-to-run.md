# Changed

## English

- Studio: **the optical model says "No need to run" when the inputs equal a run's.** After an edit, Undo or Redo that leaves the inputs and study settings (geometry, materials, wavelength, mesh, Modes to find, group index, boundary and search targets) equal to an existing run's, Messages adds the heated model's sentence, *No need to run: Run 5 already has these results. Run study adds a copy with the same values.*, with **Show Run 5**. Run study still runs if pressed; an open run with the group index took about 3.5 minutes to recompute. [Workspace](docs/packages/simcase/workspace.md).

## 한국어

- Studio: **광학 모델도 입력이 어떤 실행과 같으면 "No need to run"이라고 알립니다.** 편집, Undo나 Redo 뒤에 입력과 스터디 설정(기하, 재료, 파장, 메시, Modes to find, 군굴절률, 경계와 검색 목표)이 기존 실행과 같으면 Messages가 가열 모델의 문장 *No need to run: Run 5 already has these results. Run study adds a copy with the same values.*와 **Show Run 5**를 붙입니다. Run study는 눌리면 그래도 실행합니다. 군굴절률을 켠 열린 실행은 다시 계산하는 데 약 3.5분이 걸렸습니다. [워크스페이스](packages/simcase/workspace.md).
