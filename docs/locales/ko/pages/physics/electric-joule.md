# 전기전도·Joule 발열

[English](../../../../physics/electric-joule.md) | **한국어**

[문서 홈](../index.md)

DC 전기 해석, 전기에서 열로의 단방향 전달, 온도 의존 전도도 반복을 구분합니다. 각각 입력과 수렴 조건이 다르며, 온도 의존 반복이 범용 다중물리 연계 기능을 의미하지는 않습니다.

## 첫 Python 해석 튜토리얼

- [첫 Joule 발열 해석: 전력을 열로 전달하기](../packages/galerkin/joule_tutorial.md)

- [온도 의존 Joule 튜토리얼: 되먹임과 수렴](../packages/galerkin/temperature_joule_tutorial.md)

## 실행 경로와 한계

Python 전기 API는 영역 전도도와 명시적 Neumann gauge를 지원합니다. JSON/CLI는 균질 직사각형과 문서에 명시된 전도도 모델로 제한되며 shapes·sweep·plot·Studio 실행을 지원하지 않습니다. 온도 의존 JSON은 지정된 선형 비저항 모델을 쓰며 임의 Python callback을 실행하지 않고, 항상 Picard 반복을 씁니다. Newton 방법(`method="newton"`)은 Python에서만 씁니다.

## 모델 문서와 사용 흐름

- [전기전도·Joule heating 문서](../packages/simcase/electric_joule.md)


## Python 계약과 수식

- [2D 정상 전기전도](../packages/galerkin/electric_steady2d.md)
- [정상 Joule heating](../packages/galerkin/joule_heating.md)
- [온도 의존 정상 Joule heating](../packages/galerkin/temperature_joule_heating.md)
- [PCB 전원면 DC 전압강하: sipi.PowerPlane](../packages/sipi/overview.md#전원면-dc-전압강하ir-drop), 위 정상 2D 전도 위에서 계산


## 검증 근거

위 세 Python 계약과 JSON/CLI 계약에 독립 기준해·보존 검사·반복 수용 조건이 기록되어 있습니다. 허용치는 해당 원문을 따릅니다.

[모델 구성](../modeling/index.md) · [결과와 신뢰성](../results/index.md) · [전체 물리 문제](index.md)
