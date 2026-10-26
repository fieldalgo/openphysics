# 온도 의존 정상 Joule heating

[English (기준 계약)](../../../../../packages/galerkin/temperature_joule_heating.md) | **한국어**

현재는 구현 전 계약이다. 고정 2D P1 메시·DC·등방성 σ(T)·온도 독립 양수 열전도도만 포함한다.
전기 및 단방향 열 해석을 재사용한다. 3D·과도·Studio·메시 변경·릴리스는 제외한다.

재료는 `ConductivityModel(evaluate, temperature_range)` 또는 정확한 영역 이름 표이다.
콜백은 1차원 K 배열을 받아 같은 모양의 S/m 배열을 반환한다. 유효 범위는 유한한
`0 <= T_min < T_max`이며 양끝을 포함한다. 모든 요소 절점의 온도를 범위 검사하고,
세 절점 온도의 산술평균에서 σ를 평가한다. 경계 절점은 인접한 각 재료의 범위를 만족해야 한다.
σ는 실수·유한·양수여야 한다. 클리핑·외삽·섭씨 변환은 없다. 콜백은 순수하고 결정적이어야 한다.

`solve_temperature_joule_heat`는 명시적 초기 K 스칼라 또는 `(N,)` 배열을 받으며
열 Dirichlet 값을 먼저 적용한다. `relaxation=0.5`, `temperature_atol=1e-8 K`,
`relative_tolerance=1e-10`, `max_iterations=100`이 기본값이다.
T→σ→전기→열 H(T)를 계산하고 `T += relaxation*(H(T)-T)`로 갱신한다.
완화 전 무한노름 결함이 절대+상대 온도 기준을 만족하고,
σ(H(T))와 σ(T)의 상대 무한노름 차도 상대 기준을 만족해야 성공한다.
작은 완화값으로 거짓 수렴할 수 없다. 열 후보·완화 상태 모두 유효 범위를 검사한다.
자동 재시도·완화 조절·유일해 보장은 없다.

결과의 `coupled`는 기존 전기/열 결과이며 `evaluated_temperature`는 물성을 평가한 T다.
반환 열 온도 H(T)와 T는 위 두 허용오차로 제한되며 정확한 비선형 근으로 주장하지 않는다.
`history`에는 반복 번호, 온도 결함 K, 물성 상대 결함, 온도 최소/최대 K,
전기/열 자유 절점 잔차 A/m·W/m, 전류 수지 A/m, 공급/발열/유출 및 수지 오차 W/m가 담긴다.
기존 해석기의 1e-10 정규화 잔차·성분별 보존·전력/열 수지 기준은 그대로 유지한다.
온도 사본은 읽기 전용이다. 단위 깊이 W/m에 깊이 m를 곱하면 W다.

잘못된 옵션은 ValueError다. 범위·물성·해석 실패나 최대 반복은 `JouleConvergenceError`이며
`reason`, 완료된 `history`, `last_temperature`, 원인 예외를 보존한다. 부분 결과를 성공 반환하지 않는다.
독립 검증 계획은 기준 계약의 Validation plan을 따른다. 아직 실행 통과를 주장하지 않는다.
