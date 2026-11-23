# Fixed

## English

- `simcase` Studio workspace: **round 12 usability fixes for the Compare table, the group index option and the page tabs**. The engine, the result format, the session and document formats and the tolerances are unchanged.
  - **Compare table that fits.** The table of modes matched by field overlap keeps every column and value but has short headers grouped as A | B (*Polarization*, *n_eff*, *A_eff (µm²)*, *Absorption loss (dB/cm)* and *n_g* each over an A and a B column), a line above it naming run A and run B, and row headers *1 ↔ 1* whose accessible name is the full *A mode 1 ↔ B mode 1* (the title adds the overlap and Δn_eff). The first column stays in view while the others scroll sideways inside the table's box, at 1440 × 900 and at 390 × 844.
  - **Group index option.** Its note says what it does in plain words, *Also solves at λ ± 1 nm and takes n_g from the change (about 3× slower). Off: one solve, no n_g.* The box is also in **Physics › Optical modes**, next to Wavelength and Modes to find, and is the same option as in Study. Ticking or clearing it says in Messages what the next run does, the Study settings read *Next run uses … · group index on* while it is on, and an n_g header shows *Off · turn on in Study or Optical modes* when no run shown computed n_g.
  - **Smaller items.** The start page's tab is **Library** (it was *Models*, one letter from **Model**), and the messages that name it say *Library › Optical waveguide*. The page tabs are a tab list for assistive technology, with the shown page's tab selected, one Tab stop and Left, Right, Home and End moving between them. *Also solve without heater* reads *(about 1 s more)*.

  [Workspace](docs/packages/simcase/workspace.md).

## 한국어

- `simcase` Studio 작업 공간: **Compare 표, 군굴절률 선택, 페이지 탭의 12차 사용성 수정**. 엔진, 결과 형식, 세션·문서 형식, 허용오차는 그대로입니다.
  - **화면에 맞는 Compare 표.** 장 겹침으로 짝지은 모드 표는 모든 열과 값을 그대로 두고, 머리글을 A | B로 묶어 짧게 씁니다(*Polarization*, *n_eff*, *A_eff (µm²)*, *Absorption loss (dB/cm)*, *n_g*가 각각 A 열과 B 열 위). 표 위 줄이 실행 A와 B를 밝히고, 행 머리글은 *1 ↔ 1*이며 접근 가능한 이름은 전체 *A mode 1 ↔ B mode 1*입니다(제목은 겹침과 Δn_eff를 덧붙임). 1440 × 900과 390 × 844에서 첫 열은 그대로 보이고 나머지 열은 표 상자 안에서 옆으로 스크롤됩니다.
  - **군굴절률 선택.** 설명이 하는 일을 쉬운 말로 밝힙니다: *Also solves at λ ± 1 nm and takes n_g from the change (about 3× slower). Off: one solve, no n_g.* 상자는 **Physics › Optical modes**에도 Wavelength, Modes to find 옆에 있으며 Study의 것과 같은 선택입니다. 켜거나 끄면 Messages가 다음 실행이 하는 일을 알리고, 켜져 있는 동안 Study 설정은 *Next run uses … · group index on*으로 읽히며, 보이는 실행 중 n_g를 계산한 것이 없으면 n_g 머리글에 *Off · turn on in Study or Optical modes*가 보입니다.
  - **작은 항목.** 시작 화면의 탭 이름은 **Library**입니다(전에는 **Model**과 한 글자 차이인 *Models*). 이 탭을 가리키는 메시지도 *Library › Optical waveguide*로 씁니다. 페이지 탭은 보조 기술에 탭 목록으로 보이며, 보이는 페이지의 탭이 선택되어 Tab 정지점 하나가 되고 왼쪽·오른쪽 화살표와 Home, End로 옮겨 다닙니다. *Also solve without heater*는 *(about 1 s more)*로 읽힙니다.

  [작업 공간](packages/simcase/workspace.md).
