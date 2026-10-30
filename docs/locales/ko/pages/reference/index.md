# API·문서 계약

[English](../../../../reference/index.md) | **한국어**

[문서 홈](../index.md)

입력·출력·단위·한계의 기준 문서는 아래 패키지별 페이지입니다. 이 목차는 수기로 작성된
계약을 연결하며, 자동 생성된 전체 API 목록은 아닙니다. 독립 수용 결과는 [검증](../validation/index.md)을 보세요.

## 패키지 개요

- [galerkin — OpenPhysics 유한요소 해석 엔진](../packages/galerkin/overview.md)
- [galerkin-refsol — galerkin 검증용 참조해](../packages/galerkin-refsol/overview.md)
- [gmshio — Gmsh와 링크하지 않고 galerkin에 메시 제공](../packages/gmshio/overview.md)
- [meshine — 여러 재료로 구성된 평면 영역의 소형 품질 삼각형 메시 생성기](../packages/meshine/overview.md)
- [openphysics](../packages/openphysics/overview.md)
- [physmat — 물리 솔버용 재료 물성](../packages/physmat/overview.md)
- [simcase — 모델 문서와 헤드리스 실행기](../packages/simcase/overview.md)
- [sipi — PCB 단면의 신호·전원 무결성](../packages/sipi/overview.md)

## galerkin 계약

- [진공 직육면체 PEC 공동 솔버](../packages/galerkin/cavity_solver.md)
- [벡터 고유공간 신뢰성](../packages/galerkin/eigenspace_reliability.md)
- [2차원 소변형률 탄성](../packages/galerkin/elasticity2d.md)
- [2D 탄성의 직교좌표계 경계 traction](../packages/galerkin/elasticity_traction.md)
- [2D 정상 전기전도](../packages/galerkin/electric_steady2d.md)
- [정상 Joule heating](../packages/galerkin/joule_heating.md)
- [재료 충전 직육면체 공동 솔버](../packages/galerkin/material_cavity.md)
- [모드 복소 좌표](../packages/galerkin/modal_coordinates.md)
- [이름 있는 영역별 구간 상수 재료](../packages/galerkin/multimaterial.md)
- [처방 온도장 열탄성: 2D 기계 단계](../packages/galerkin/prescribed_temperature_thermoelasticity.md)
- [온도 의존 정상 Joule heating](../packages/galerkin/temperature_joule_heating.md)
- [정상 2D 외향 열유속과 대류](../packages/galerkin/thermal_flux_robin.md)
- [명시적인 정상 열전도 → 열탄성 기계단계](../packages/galerkin/thermal_mechanical_workflow.md)
- [정상 2차원 열전도](../packages/galerkin/thermal_steady2d.md)
- [처방 온도 열탄성과 전체 기계 traction](../packages/galerkin/thermoelastic_traction.md)
- [고정 P1 메시의 과도 열전도](../packages/galerkin/transient_heat.md)
- [과도 열전도에서 준정적 역학으로](../packages/galerkin/transient_thermal_mechanical.md)

## simcase 계약

- [직육면체 공진기 문서와 결과](../packages/simcase/cavity3d.md)
- [전기전도·Joule heating 문서](../packages/simcase/electric_joule.md)
- [흡수 도파관 모드](../packages/simcase/lossy_modes.md)
- [PML·누설·일정 반경 모드](../packages/simcase/pml_modes.md)
- [재료 영역이 있는 열전도 문서](../packages/simcase/thermal_regions2d.md)
- [직사각형의 headless 정상 열전도](../packages/simcase/thermal_steady2d.md)
- [정상 외향 열유속·대류 문서](../packages/simcase/thermal_steady_boundary2d.md)
- [Studio 정상 열전도](../packages/simcase/thermal_studio.md)
- [직사각형의 headless 과도 열전도](../packages/simcase/thermal_transient2d.md)
- [Studio 과도 열전도](../packages/simcase/thermal_transient_studio.md)
- [벡터 파장 sweep의 선택형 부분공간 추적](../packages/simcase/vector_subspace_tracking.md)

- [실험적 workspace와 파일 계약](../packages/simcase/workspace.md)

## SIPI 계약

- [단면 템플릿·JSON·목표 임피던스 설계](../packages/sipi/design.md)

- [균일 전송선 RLGC·S·Touchstone](../packages/sipi/network.md)
- [사다리꼴 도체·평탄 코팅 계약과 검증](../packages/sipi/manufacturing_sections.md)
- [주파수 의존 유전체 모델·추출](../packages/sipi/dielectrics.md)

- [DC·AC 도체 부피 메시, 전류 확산과 잔차](../packages/sipi/conductor_diffusion.md)

[동일 기하 유한 금속·유전체 DC/AC RLGC와 버전 JSON](../packages/sipi/volume_line.md).
