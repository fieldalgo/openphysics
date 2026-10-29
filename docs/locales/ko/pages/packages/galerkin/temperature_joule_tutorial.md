# 온도 의존 Joule 튜토리얼: 되먹임과 수렴

[English](../../../../../packages/galerkin/temperature_joule_tutorial.md) | **한국어**

먼저 [상수 물성 Joule 튜토리얼](joule_tutorial.md)을 읽으세요. 이전 예제는 전기를 한 번만
풀지만 이번에는 온도에 따라 전기전도도가 달라져 정상 전기·열 문제를 반복해서 풉니다.
이 반복은 **시간 단계가 아닙니다.**

## 1. 전류로 구동하는 모델 정의하기

Python 3.12 이상과 활성화한 가상환경을 사용하고 저장소 루트에서 실행합니다.

```sh
python -m pip install -e packages/galerkin
python examples/galerkin/temperature_joule_heating.py
```

[예제](../../../../../../examples/galerkin/temperature_joule_heating.py)는
1 m × 0.25 m 직사각형을 16 × 4개 셀로 나눕니다. 왼쪽 전위는 0 V, 오른쪽 외향 전류밀도는
1 A/m²이며 나머지 전기 자연 경계는 절연입니다. 열 경계는 양 끝 300 K, 위·아래 단열이고
k=1 W/(m K)입니다. 전류밀도와 총전류는 다릅니다. 오른쪽 변의 전류는 돌출 깊이당 0.25 A/m입니다.

설명용 비저항 법칙은 `rho(T)=1+0.5*(T-300)` ohm m이므로 `sigma(T)=1/rho(T)` S/m입니다.
`ConductivityModel`은 유효 범위를 [300,400] K로 선언합니다. 결정적인 callback은 1차원
온도 배열을 받고 같은 shape의 유한한 양의 전도도 배열을 반환합니다. 솔버는 노드 온도 범위를
확인하고 삼각형의 평균 노드 온도에서 전도도를 평가합니다. 각 노드에서 평가한 전도도 세 개를
평균하지 않습니다. 해를 범위 안에 강제로 넣기 위한 clipping이나 외삽도 하지 않습니다.

## 2. 수렴한 계산 읽기

예제의 `relaxation=1.`로 실행한 결과는 대략 다음과 같습니다.

```text
Maximum temperature: 300.131806613 K
Joule power: 0.260917862 W/m
Iterations: 8
Unrelaxed defect: 1.049e-10 K
Nonlinear heat residual: 6.216e-12
```

끝자리와 반복 횟수는 수치 실행 환경에 따라 달라질 수 있습니다. 일정 전류에서는 비저항이
늘면 `Q=J²*rho`가 커지고 온도가 올라 비저항에 다시 영향을 줍니다. 일정 전압과는 다르므로
이전 튜토리얼의 전압 제곱 비례 규칙을 이 문제에 그대로 적용하지 마세요.

이 1차원 연속체 thermistor의 기준식은
`T=300+(cos(beta*(x-L/2))/cos(beta*L/2)-1)/alpha`이며
`beta²=J²*rho0*alpha/k`, L=1 m, alpha=0.5 /K입니다. 유한 메시 해는 이를 근사합니다.
독립 메시 세분화 근거는 [계약의 검증](temperature_joule_heating.md)에 기록되어 있습니다.
반복이 성공했다는 사실 자체가 그 검증을 대신하지는 않습니다.

## 3. 종료 검사 이해하기

각 Picard 단계는 T에서 평가한 전도도로 시험 온도 H(T)를 구한 다음
`T_next=T+relaxation*(H(T)-T)`로 갱신합니다.

- 온도 defect는 **완화 전 H(T)−T**를 K 단위로 측정합니다.
- 별도의 상대 전도도 defect 검사도 통과해야 합니다.
- 전기 해석을 갱신해 무차원 비선형 열 잔차를 확인합니다.
- 하위 해석의 전류·전력·열 보존 검사도 유지됩니다.

아주 작은 완화계수로 갱신량만 줄여 가짜 수렴을 만들 수는 없습니다.
`result.history`에는 스칼라 진단 이력이, `result.coupled`에는 수용한 전기·열 결과가 있습니다.
평가 온도 snapshot과 반환된 시험 온도는 수용 조건 범위 안에서 차이가 있으며,
정확한 비선형 근이라고 주장하지 않습니다.

## 4. 통제된 변경과 실패 실험

스크립트를 `packages/` 밖으로 복사하고 한 번에 한 설정씩 바꾸세요.

| 변경 | 확인할 내용 |
|---|---|
| `relaxation=.5` | 허용치 안에서 같은 해; 로컬 실행에서는 8회 대신 33회 반복 |
| 솔버 호출의 `method='picard'`를 `method='newton'`으로 변경 | 허용치 안에서 같은 해를 8회 대신 3개 상태로([Newton 방법](temperature_joule_heating.md#newton-방법)) |
| `.5*(t-300)`를 `0.*(t-300)`로 교체 | 상수 sigma=1 S/m: 최고 300.125 K, 전력 0.25 W/m |
| 솔버 호출에 `max_iterations=1` 추가 | 예산 부족으로 `JouleConvergenceError`; 완료한 이력 1개 보존 |
| 모델 범위를 `(300., 300.05)`로 변경 | 시험 온도가 재료 범위를 초과하며 성공한 부분 결과를 반환하지 않음 |

진단하려면 `galerkin.temperature_joule_heating`에서 `JouleConvergenceError`를 import하고
해석 호출을 감싸서 잡습니다. `reason`, `history`, `last_temperature`를 확인하세요.
이는 수용한 연계 해가 아니라 실패 진단입니다. 좁은 범위 실험에서는 이력 한 개가
완료되기도 전에 첫 시험이 실패할 수 있습니다.

실패를 숨기려고 수용 허용치를 느슨하게 하거나 재료 범위를 넓히지 마세요.
물리적으로 타당한 입력을 사용하고 필요에 따라 초기 온도·완화계수·반복 예산을 조정하거나 `method='newton'`을 씁니다.
이 해법의 실패만으로 물리적 열폭주를 단정하거나 과도 궤적을 얻을 수는 없습니다.

## 5. 범위와 다음 문서

고정 2D 메시, 일정 열전도율, 제한된 온도 의존 전기 법칙을 사용하는 정상 DC 문제입니다.
임의 입력에 대해 해의 유일성이나 반복 수렴을 보장하지 않습니다. 정의와 실패 정책은
[규범적 계약](temperature_joule_heating.md)을 읽으세요.

별도 [JSON/CLI 계약](../simcase/electric_joule.md)은 균질 직사각형과 선언된 선형 비저항
모델을 제공하며 임의 Python callback은 받지 않습니다. 두 경로 모두 온도 의존 Joule의
Studio 화면은 제공하지 않습니다.
