# 패널 정전기: 공개 SI API

[English](../../../../../packages/galerkin/panel_electrostatics.md)

`galerkin.panel_electrostatics`는 galerkin의 균질 2차원 Laplace 경계 패널 계산기의
공개 API다. 다른 공개 모듈과 같은 단위 규칙을 따른다. 유일한 물리량 `box_size`는
`physmat.units` 레지스트리 이름의 keyword-only SI 값이고, 그 자리에 문자열을 주면
`TypeError`가 난다.

이 모듈은 감싸기만 한다. 각 함수는 `box_size`를 읽고 도체 선택 인자의 이름을 바꾼
뒤 같은 수로 내부 계산기를 부른다. 따라서 결과는 내부 계산기의 결과 객체와 비트
단위로 같다. 내부 모듈(`galerkin.laplace_boundary`, `galerkin.laplace_two_ground`,
`galerkin.laplace_open_box`, `galerkin.laplace_corner_*`)은 바뀌지 않으며 내부로
남는다. 이름과 자체 일관 단위를 그대로 유지하고, 호환을 약속하지 않는다.

사용 예제는 영문 문서와 같다. 길이는 m이고 `box_size=(0.008, 0.002)`처럼 (너비, 높이)를
준다. `capacitance_per_permittivity`는 무차원이며, F/m 단위 유전율을 곱하면 F/m 단위
단위 길이당 정전용량 C'가 된다.

## 계산기

| 공개 함수 | 벽 조건 | 내부 계산기(계약과 검증) |
|---|---|---|
| `solve_grounded_rectangle` | 아래 벽 접지, 나머지 벽 법선 전속 0 | [`laplace_boundary`](laplace_boundary.md) |
| `solve_two_ground_rectangle` | 아래·위 접지, 좌우 벽 법선 전속 0 | [`laplace_two_ground`](two-ground.md) |
| `solve_two_ground_rectangle_edges` | 위와 같고 직선 변 전류 포함 | [`laplace_two_ground`](two-ground-edges.md) |
| `solve_two_ground_corner_rectangle_edges` | 위와 같고 코너 멱 밀도, 활성 도체 1–2개 | `laplace_two_ground` |
| `solve_two_ground_linear_corner_rectangle_edges` | 위와 같고 선형 코너 멱 밀도 | `laplace_corner_linear_field` |
| `solve_two_ground_harmonic_corner_three_active_edges` | 위와 같고 활성 도체 3개 | [`laplace_corner_harmonic_field`](laplace_corner_harmonic_field.md) |
| `solve_two_ground_harmonic_corner_guard_edges` | 위와 같고 활성 도체 2개와 전위 0 가드 1개 | [`laplace_corner_harmonic_guard_field`](laplace_corner_harmonic_guard_field.md) |
| `solve_two_ground_harmonic_corner_single_active_edges` | 위와 같고 활성 도체 1개와 가드 2개 | [`laplace_corner_harmonic_single_active_field`](laplace_corner_harmonic_single_active_field.md) |
| `solve_open_rectangle` | 네 벽 모두 법선 전속 0, 접지 도체가 기준 | [`laplace_open_box`](open-box.md) |

허용 기하, 이산화 한계, 기본 개수, 일관성 검사와 그 임계값, 한계는 내부 계산기의
것 그대로이며 링크한 문서에 적혀 있다.

## 인자

| 공개 인자 | 내부 인자 | 뜻 |
|---|---|---|
| `polygons`(위치 인자) | `polygons` | 도체 경계. 각각 꼭짓점 좌표(m)의 (n, 2) 배열이고 엄격히 볼록하며 닫는 중복점이 없다. |
| `box_size`(키워드) | `width`, `height` | 직사각형의 두 변 길이 (너비, 높이), m. 직사각형은 [0, 너비] × [0, 높이]로, `galerkin.cavity`의 3차원 `box_size`처럼 원점에서 시작한다. 양면 접지 계산기에서 높이는 두 접지면 간격이다. |
| `panels_per_edge`, `ground_modes`, `interpolation_degree` | 같음 | 이산화 개수. 기본값은 내부 계산기의 것이다. |
| `ground_indices` | `grounds` | `solve_open_rectangle`: 전위 0으로 묶는 도체의 `polygons` 인덱스. |
| `signal_indices` | `signals` | `solve_two_ground_harmonic_corner_guard_edges`: 활성 도체 두 개의 순서 있는 인덱스. |
| `signal_index` | `signal` | `solve_two_ground_harmonic_corner_single_active_edges`: 활성 도체의 인덱스. |

`box_size`는 유한한 양수 두 개(시퀀스 또는 모양 (2,) 배열)여야 하며, 아니면
`box_size`를 이름으로 든 `ValueError`가 난다. 내부 계산기의 거부 메시지도 공개 인자
이름(`box_size`, `ground_indices`, `signal_indices`, `signal_index`)으로 나온다.

레지스트리에는 직사각형의 너비나 높이 하나를 뜻하는 이름이 없고, `box_size`는 한
꼭짓점이 원점인 축 정렬 상자의 변 길이를 뜻하는 레지스트리 이름이다. 그래서 이름
두 개를 새로 만들지 않고 `box_size`를 쓴다. `polygons`, 개수, 도체 인덱스는 이 모듈로
범위를 한정한 구조명이다(`tests/_support/api_units_structural.json`).

## 결과

네 결과 클래스 `RectangleBoundaryResult`, `TwoGroundRectangleResult`,
`TwoGroundRectangleEdgesResult`(모든 변 전류 계산기), `OpenRectangleResult`는 내부
모듈의 고정 레코드를 그대로 다시 내보낸 것이며, 단위 스캔의 결과 클래스 목록에 있다.
`capacitance_per_permittivity`는 깊이 1 m당 정전용량 행렬을 균질 매질의 절대 유전율로
나눈 값이다. 무차원이며, F/m 단위 유전율을 곱하면 F/m 단위 단위 길이당 정전용량이 된다.
필드 이름은 결과 표면 검사(P3-11)까지 그대로 둔다.

## 검증

`tests/galerkin/test_panel_electrostatics.py`는 빠른 계산기 여섯 개를 같은 입력으로
공개 함수와 내부 계산기에 각각 돌려, 결과의 모든 배열이 바이트 단위로 같아야 한다고
검사한다. 아홉 계산기 모두에 대해서는 내부 계산기가 호출자의 `polygons`, 너비, 높이,
개수를 같은 객체 그대로 받는지와 기본값이 같은지를 검사한다. 조화 코너 계산기 세
개는 허용되는 가장 작은 크기에서도 각각 약 27초가 걸려 이 파일에서는 두 번 돌리지
않는다. 위에 링크한 각자의 시험이 이를 돌린다. 물리 검증은 내부 계산기의 것이며
되풀이하지 않는다.
