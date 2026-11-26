# Added

## English

- `galerkin`: **`galerkin.panel_electrostatics`, a public SI API for the boundary-panel solvers.** Nine solvers (`solve_grounded_rectangle`, the two-ground solvers including the corner-power ones, and `solve_open_rectangle`) take the rectangle as `box_size=(width, height)` in m, keyword-only, and refuse text with `TypeError`; the open box takes `ground_indices` and the harmonic guard solvers `signal_indices` or `signal_index`. Each calls the internal solver with the same numbers, so its result (one of four re-exported result classes) equals the internal one bit for bit. The internal `galerkin.laplace_*` modules, their names and their behaviour are unchanged and stay internal. [Panel electrostatics](docs/packages/galerkin/panel_electrostatics.md).

## 한국어

- `galerkin`: **경계 패널 계산기의 공개 SI API `galerkin.panel_electrostatics`.** 계산기 아홉 개(`solve_grounded_rectangle`, 코너 멱 계산기를 포함한 양면 접지 계산기, `solve_open_rectangle`)가 직사각형을 keyword-only `box_size=(너비, 높이)`(m)로 받고, 문자열은 `TypeError`로 거부합니다. open box는 `ground_indices`, 조화 가드 계산기는 `signal_indices`나 `signal_index`를 받습니다. 각 함수는 같은 수로 내부 계산기를 부르므로 결과(다시 내보낸 결과 클래스 네 개 중 하나)가 내부 결과와 비트 단위로 같습니다. 내부 `galerkin.laplace_*` 모듈의 이름과 동작은 그대로이고 내부로 남습니다. [패널 정전기](packages/galerkin/panel_electrostatics.md).
