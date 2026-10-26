# 온도 의존 정상 Joule heating

[English (기준 계약)](../../../../../packages/galerkin/temperature_joule_heating.md) | **한국어**

고정 2D P1 메시·DC·등방성 σ(T)·온도 독립 양수 열전도도만 포함한다.
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
σ(H(T))와 σ(T)의 각 요소별 상대 차의 최댓값도 상대 기준을 만족해야 성공한다.
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
독립 검증 계획은 기준 계약의 Validation plan을 따른다. 신규 및 관련 회귀·독립 scikit-fem 비교를 로컬에서 통과했다. 플랫폼 전체 근거는 CI에서 확인한다.


H(T)에서 전기를 한 번 더 풀고 `r_heat + load(T) - load(H(T))`의 열 자유 절점
무한노름을 두 Joule 하중 및 열 반력·처방 유출·대류 하중의 가장 큰 무한노름(machine tiny 하한)으로 나눈다.
이 무차원 `nonlinear_heat_residual`도 1e-8 이하여야 성공한다. 선형 해석 잔차와 구별한다.

## 예제·한계

저장소 루트에서 galerkin 설치 후 실행한다:

```bash
python examples/galerkin/temperature_joule_heating.py
```

[실행 예제](../../../../../../examples/galerkin/temperature_joule_heating.py)는 오른쪽
유출 전류 1 A/m², 왼쪽 V=0, 양끝 T=300 K, k=1 W/(m K),
σ=1/(1+0.5*(T-300)) S/m, 유효 범위 [300,400] K를 사용한다.
온도·단위 깊이 전력·반복 횟수·결함을 출력한다.
`galerkin.electric.ElementConductivity(mesh, values)`는 명시적인 양수·유한
요소별 `(M,)` S/m 사본을 받으며 메시 기하·순서·영역 일치를 검사한다.
원시 배열은 여전히 거부한다. 열전도도 입력 계약은 변하지 않는다.

전류 구동 양의 저항률 피드백은 정상해 상실에 접근할 수 있다. 반복 실패를 과도
궤적이나 물리적 불안정성 증거로 단정하지 않는다. 초기값·완화·반복 예산을
물리적 근거로 선택해야 하며 수용 허용오차나 물성 범위를 완화해서는 안 된다.
경계 콜백도 결정적이어야 한다. 수렴·유일해·모든 재료의 안정성은 보장하지 않는다.

검증: 신규 기능 시험 28개. scikit-fem 최대 상대차 1.04e-12 (<1e-9).
연속 온도 RMS L2 오차는 n=8/16/32에서 1.52995e-3, 3.83592e-4, 9.59884e-5 K
(마지막 차수 1.999)였다. 강한 피드백 alpha=7은 완화 1/0.5에서
59/128회에 수렴했다. 실패 이력 보존도 시험한다.

[균질 직사각형 JSON/CLI 입력·저장 계약](../simcase/electric_joule.md). Python API 전체 범위를 JSON에 노출하지는 않습니다.
