# 이론·수치 방법

[English](../../../../theory/index.md) | **한국어**

[문서 홈](../index.md)

수식과 수치 방법은 현재 구현 계약 안에 설명되어 있습니다. 아래 경로에서 해당 설명을
읽고, 독립 검증 근거는 [검증 목차](../validation/index.md)에서 확인하세요. 이 목차 자체가
추가 정확도나 수렴을 보장하지는 않습니다.

## 전자기 모드와 좌표

- [진공 직육면체 PEC 공동 솔버](../packages/galerkin/cavity_solver.md)
- [재료 충전 직육면체 공동 솔버](../packages/galerkin/material_cavity.md)
- [벡터 고유공간 신뢰성](../packages/galerkin/eigenspace_reliability.md)
- [모드 복소 좌표](../packages/galerkin/modal_coordinates.md)

## 열·전기전도

- [정상 2차원 열전도](../packages/galerkin/thermal_steady2d.md)
- [정상 2D 외향 열유속과 대류](../packages/galerkin/thermal_flux_robin.md)
- [고정 P1 메시의 과도 열전도](../packages/galerkin/transient_heat.md)
- [2D 정상 전기전도](../packages/galerkin/electric_steady2d.md)
- [정상 Joule heating](../packages/galerkin/joule_heating.md)
- [온도 의존 정상 Joule heating](../packages/galerkin/temperature_joule_heating.md)

## 역학·재료·연계

- [2차원 소변형률 탄성](../packages/galerkin/elasticity2d.md)
- [2D 탄성의 직교좌표계 경계 traction](../packages/galerkin/elasticity_traction.md)
- [이름 있는 영역별 구간 상수 재료](../packages/galerkin/multimaterial.md)
- [처방 온도장 열탄성: 2D 기계 단계](../packages/galerkin/prescribed_temperature_thermoelasticity.md)
- [처방 온도 열탄성과 전체 기계 traction](../packages/galerkin/thermoelastic_traction.md)
- [명시적인 정상 열전도 → 열탄성 기계단계](../packages/galerkin/thermal_mechanical_workflow.md)
- [과도 열전도에서 준정적 역학으로](../packages/galerkin/transient_thermal_mechanical.md)

## 독립 기준해 구현

- [galerkin-refsol — galerkin 검증용 참조해](../packages/galerkin-refsol/overview.md)
