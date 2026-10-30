# 전자기

[English](../../../../physics/electromagnetics.md) | **한국어**

[문서 홈](../index.md)

도파관 단면에서 시작해 scalar/vector 모드, 파장 sweep 또는 직육면체 공동을 선택합니다. 정전기·산란은 Python 엔진을 사용합니다. PML·누설 모드는 메시와 PML을 독립적으로 검사해야 하는 후보이며, 물리적 pole로 인증된 결과가 아닙니다.

## 실행 경로와 한계

도파관 문서·sweep은 JSON/CLI와 Studio 경로가 있고, 3D 공동은 JSON/CLI만 제공합니다. 각 광학 study의 한계는 모드 계약을 확인하세요.

## 모델 문서와 사용 흐름

- [튜토리얼: 내 도파관 해석하기](../packages/simcase/waveguide_tutorial.md)
- [흡수 도파관 모드](../packages/simcase/lossy_modes.md)
- [PML·누설·일정 반경 모드](../packages/simcase/pml_modes.md)
- [벡터 파장 sweep의 선택형 부분공간 추적](../packages/simcase/vector_subspace_tracking.md)
- [직육면체 공진기 문서와 결과](../packages/simcase/cavity3d.md)


## PCB 전송선(신호·전원 무결성)

- [sipi — 준정적 PCB 단면: C, L, G, 임피던스와 결합선 모드](../packages/sipi/overview.md). Python API와 [균일 전송선 네트워크](../packages/sipi/network.md)가 있으며 명시한 RLGC로 S·Touchstone 출력을 계산합니다. [주파수 선로 입력 모델](../packages/sipi/line_model.md)은 메시 하나로 유전체 분산·고주파 도체 표면 손실·RLGC/S를 연결합니다. [유한 금속 전류 확산](../packages/sipi/conductor_diffusion.md)은 명시적 자기 경계에서 R/L을 추출합니다. 3D 구조는 미지원입니다.

## Python 계약과 수식

- [진공 직육면체 PEC 공동 솔버](../packages/galerkin/cavity_solver.md)
- [재료 충전 직육면체 공동 솔버](../packages/galerkin/material_cavity.md)
- [벡터 고유공간 신뢰성](../packages/galerkin/eigenspace_reliability.md)
- [모드 복소 좌표](../packages/galerkin/modal_coordinates.md)
- [galerkin — OpenPhysics 유한요소 해석 엔진](../packages/galerkin/overview.md)


## 검증 기록

- [galerkin 단계별 검증 결과(2026-09-05)](../packages/galerkin/milestone_validation.md)
- [진공 PEC 직육면체 공진기 독립 검증 계획](../packages/galerkin/cavity3d_validation.md)
- [교대 Kuhn 공진기 mesh의 독립 검증](../packages/galerkin/cavity3d_alternating_validation.md)
- [직육면체 PEC 111 doublet: 부호 있는 평균 수렴 진단](../packages/galerkin/cavity3d_convergence_diagnosis.md)


[모델 구성](../modeling/index.md) · [결과와 신뢰성](../results/index.md) · [전체 물리 문제](index.md)

SIPI는 [단면 템플릿·버전 JSON·목표 임피던스 설계](../packages/sipi/design.md)도 제공합니다.

[SIPI DC·AC 도체 내부 전류 확산](../packages/sipi/conductor_diffusion.md)은 유한 금속 부피와 자기 경계를 명시합니다. 유전체 기하 일치는 별도 계약입니다.

[동일 기하 유한 금속·유전체 DC/AC RLGC와 버전 JSON](../packages/sipi/volume_line.md).

[Touchstone 입력과 명시적 네트워크 비교](../packages/sipi/touchstone.md).

[종단 네트워크 V/I와 주파수 누화](../packages/sipi/termination.md)는 명시 Thevenin 소스·수동 임피던스를 쓰는 Python 전용 API입니다.
