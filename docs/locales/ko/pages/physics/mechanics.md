# 역학·열탄성 연계

[English](../../../../physics/mechanics.md) | **한국어**

[문서 홈](../index.md)

평면 응력·평면 변형률을 고르고 변위 구속과 하중을 정의합니다. 처방 온도 역학, 정상 열→역학, 선택한 과도 열 시간의 역학은 같은 메시를 사용하는 서로 다른 명시적 흐름입니다.

## 첫 Python 해석 튜토리얼

- [첫 열탄성 해석: 열전도에서 역학으로](../packages/galerkin/thermoelastic_tutorial.md)

## 실행 경로와 한계

Python 전용이며 역학 JSON/CLI와 Studio 양식은 없습니다. 선형 소변형률 역학이고 열→역학은 열로 되먹임 없는 단방향입니다. 정상 연계 흐름이 별도 flux/Robin/traction 확장을 자동으로 지원하지는 않습니다. 과도 열 snapshot의 역학은 준정적이며 구조 동역학이 아닙니다.

## Python 계약과 수식

- [2차원 소변형률 탄성](../packages/galerkin/elasticity2d.md)
- [2D 탄성의 직교좌표계 경계 traction](../packages/galerkin/elasticity_traction.md)
- [처방 온도장 열탄성: 2D 기계 단계](../packages/galerkin/prescribed_temperature_thermoelasticity.md)
- [처방 온도 열탄성과 전체 기계 traction](../packages/galerkin/thermoelastic_traction.md)
- [명시적인 정상 열전도 → 열탄성 기계단계](../packages/galerkin/thermal_mechanical_workflow.md)
- [과도 열전도에서 준정적 역학으로](../packages/galerkin/transient_thermal_mechanical.md)
- [이름 있는 영역별 구간 상수 재료](../packages/galerkin/multimaterial.md)


## 검증 기록

- [2D 탄성의 독립 수용 검증](../packages/galerkin/elasticity2d_independent_validation.md)
- [경계 traction의 독립 수용 검증](../packages/galerkin/elasticity_traction_independent_validation.md)
- [처방 온도장 기계단계의 독립 수용 검증](../packages/galerkin/prescribed_temperature_thermoelasticity_independent_validation.md)
- [처방 온도 열탄성 traction 독립 수용](../packages/galerkin/thermoelastic_traction_independent_validation.md)
- [정상 열전도 → 기계 workflow 독립 수용](../packages/galerkin/thermal_mechanical_independent_validation.md)
- [공개 기준값 벤치마크: 바이메탈 띠와 NAFEMS T4](../packages/galerkin/public_benchmarks.md)


[모델 구성](../modeling/index.md) · [결과와 신뢰성](../results/index.md) · [전체 물리 문제](index.md)
