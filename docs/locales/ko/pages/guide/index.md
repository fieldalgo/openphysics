# 사용 안내

[English](../../../../guide/index.md) | **한국어**

[문서 홈](../index.md)

수행하려는 해석에 따라 읽으세요. 각 링크는 지원 입력과 저장 결과를 설명하는 원문입니다.
Python에서 제공하는 기능이 JSON/CLI나 Studio에도 자동으로 제공되는 것은 아닙니다.

## 실행 인터페이스 선택

[모델 구성](../modeling/index.md)과 [물리 문제](../physics/index.md)를 먼저 정한 뒤 선택하세요.

| 경로 | 쓰는 경우 |
|---|---|
| Python | 저수준 엔진, 역학, 명시적 연계와 모델별 수치 제어 |
| JSON/CLI | simcase가 정의한 모델의 검증·실행·저장 |
| Studio | 지원되는 광학·직사각형 열 모델의 브라우저 편집과 시각화 |

실행 후에는 [결과·내보내기·신뢰성](../results/index.md)을 확인하세요.

## 모델 문서와 결과

- [simcase — 모델 문서와 헤드리스 실행기](../packages/simcase/overview.md)
- [튜토리얼: 내 도파관 해석하기](../packages/simcase/waveguide_tutorial.md)

## 도파관과 공동

- [흡수 도파관 모드](../packages/simcase/lossy_modes.md)
- [PML·누설·일정 반경 모드](../packages/simcase/pml_modes.md)
- [벡터 파장 sweep의 선택형 부분공간 추적](../packages/simcase/vector_subspace_tracking.md)
- [직육면체 공진기 문서와 결과](../packages/simcase/cavity3d.md)

## 열전도와 재료 영역

- [직사각형의 headless 정상 열전도](../packages/simcase/thermal_steady2d.md)
- [정상 외향 열유속·대류 문서](../packages/simcase/thermal_steady_boundary2d.md)
- [직사각형의 headless 과도 열전도](../packages/simcase/thermal_transient2d.md)
- [재료 영역이 있는 열전도 문서](../packages/simcase/thermal_regions2d.md)

## 전기전도와 Joule 발열

- [전기전도·Joule heating 문서](../packages/simcase/electric_joule.md)

## Studio

- [Studio 정상 열전도](../packages/simcase/thermal_studio.md)
- [Studio 과도 열전도](../packages/simcase/thermal_transient_studio.md)

## Python 역학·연계 해석

- [2차원 소변형률 탄성](../packages/galerkin/elasticity2d.md)
- [2D 탄성의 직교좌표계 경계 traction](../packages/galerkin/elasticity_traction.md)
- [처방 온도장 열탄성: 2D 기계 단계](../packages/galerkin/prescribed_temperature_thermoelasticity.md)
- [처방 온도 열탄성과 전체 기계 traction](../packages/galerkin/thermoelastic_traction.md)
- [명시적인 정상 열전도 → 열탄성 기계단계](../packages/galerkin/thermal_mechanical_workflow.md)
- [과도 열전도에서 준정적 역학으로](../packages/galerkin/transient_thermal_mechanical.md)
- [정상 Joule heating](../packages/galerkin/joule_heating.md)
- [온도 의존 정상 Joule heating](../packages/galerkin/temperature_joule_heating.md)
