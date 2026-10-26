# 열전도

[English](../../../../physics/heat.md) | **한국어**

[문서 홈](../index.md)

정상·과도 열전도를 고른 뒤 직사각형 또는 재료 영역 형상을 선택합니다. 경계 부호, Kelvin 온도, 시간 표본과 단위 깊이당 물리량이 모델 계약의 일부입니다.

## 실행 경로와 한계

Python과 JSON/CLI는 직사각형·영역 모델을 지원하지만 Studio는 직사각형 열전도만 지원합니다. 과도 열전도는 flux/Robin 입력과 restart를 제공하지 않습니다. 후속 역학 해석은 아래의 명시적 연계 경로를 사용하세요.

## 모델 문서와 사용 흐름

- [직사각형의 headless 정상 열전도](../packages/simcase/thermal_steady2d.md)
- [정상 외향 열유속·대류 문서](../packages/simcase/thermal_steady_boundary2d.md)
- [직사각형의 headless 과도 열전도](../packages/simcase/thermal_transient2d.md)
- [재료 영역이 있는 열전도 문서](../packages/simcase/thermal_regions2d.md)
- [Studio 정상 열전도](../packages/simcase/thermal_studio.md)
- [Studio 과도 열전도](../packages/simcase/thermal_transient_studio.md)


## Python 계약과 수식

- [정상 2차원 열전도](../packages/galerkin/thermal_steady2d.md)
- [정상 2D 외향 열유속과 대류](../packages/galerkin/thermal_flux_robin.md)
- [고정 P1 메시의 과도 열전도](../packages/galerkin/transient_heat.md)
- [이름 있는 영역별 구간 상수 재료](../packages/galerkin/multimaterial.md)


## 검증 기록

- [정상 열전도 독립 수용 검증](../packages/galerkin/thermal_independent_validation.md)
- [Outward flux·Robin 열전도의 독립 수용 검증](../packages/galerkin/thermal_flux_robin_independent_validation.md)
- [과도 열전도 검증 계약](../packages/galerkin/transient_heat_validation.md)
- [비정상 열전도 독립 수용 검증](../packages/galerkin/transient_heat_independent_validation.md)
- [Headless 열전도 문서의 독립 검증](../packages/simcase/thermal_simcase_independent_validation.md)
- [정상 열전도 경계 headless 독립 수용](../packages/simcase/steady_boundary_independent_validation.md)
- [정상열 Studio 독립 검증](../packages/simcase/studio_thermal_independent_validation.md)
- [과도 Studio 독립 수용](../packages/simcase/studio_transient_thermal_independent_validation.md)


[모델 구성](../modeling/index.md) · [결과와 신뢰성](../results/index.md) · [전체 물리 문제](index.md)

[열→역학 연계](mechanics.md)
