# OpenPhysics 문서

[English](../../../README.md) | **한국어**

처음 사용한다면 [도구 개요](overview.md)부터 읽으세요. OpenPhysics가 푸는 문제,
설치, 첫 예제와 현재 한계를 설명합니다. 기여자는 [개발 안내](development.md)(개발 환경,
저장소 구성, 검사, CI와 필수 검사 `tests`)와
[기여 안내](contributing.md)(브랜치·리뷰·릴리스)를 읽으세요.

기본 언어는 영어입니다. README와 기여·보안 진입 문서는 영어로 유지합니다. 영어·한국어
문서는 `docs/` 안에서 제공하며, 영어는
`docs/<이름>.md`, 한국어는 `docs/locales/ko/pages/<이름>.md`에 둡니다. 패키지마다의
문서(개요 포함)는 `docs/packages/<패키지>/`와 `docs/locales/ko/pages/packages/<패키지>/`에
있습니다.
코드 식별자·수식·명령·기록된 출력은 두 언어에서 같은 의미를 유지하며, 번역은 새 수치
결과가 아닙니다.

## 시작하기

| 문서 | English | 한국어 |
|---|---|---|
| 도구 개요·설치 | [Overview](../../../overview.md) | [한국어](overview.md) |
| 튜토리얼: 내 도파관 해석하기 | [Tutorial](../../../packages/simcase/waveguide_tutorial.md) | [한국어](packages/simcase/waveguide_tutorial.md) |
| 구조도와 패키지 관계 | [Architecture](../../../architecture.md) | [한국어](architecture.md) |
| 개발과 검증 | [Development guide](../../../development.md) | [한국어](development.md) |
| 기여 | [Contributing](../../../contributing.md) | [한국어](contributing.md) |
| 보안 | [Security](../../../security.md) | [한국어](security.md) |
| 포함된 이미지·fixture·데이터 | [Asset provenance](../../../assets.md) | [한국어](assets.md) |
| 제3자 소프트웨어·데이터·라이선스 | [Third-party list](../../../third-party.md) | [한국어](third-party.md) |
| 레퍼런스 도구 비교 | [Comparisons](../../../reference-comparisons.md) | [한국어](reference-comparisons.md) |
| 예제 갤러리(그림과 그것을 그리는 스크립트) | [Gallery](../../../gallery.md) | [한국어](gallery.md) |

## 현재 구현의 사용 계약과 검증 근거

계약은 입력·출력·단위·한계를 정의하고, 검증 보고는 독립 기준해·고정 허용치·실측 범위를
기록합니다. 특정 커밋의 결과는 그 커밋의 CI 실행과 artifact에서 확인하세요.

| 주제 | 영어 원문 | 한국어판 상태 |
|---|---|---|
| 과도 열전도 → 준정적 역학 | [저장 index API 및 독립 기준](../../../packages/galerkin/transient_thermal_mechanical.md) | [한국어](packages/galerkin/transient_thermal_mechanical.md) |
| 3D PEC 공동 엔진 | [API·단위·수렴](../../../packages/galerkin/cavity_solver.md) | [한국어](packages/galerkin/cavity_solver.md) |
| 3D PEC 공동 검증 기록(과거) | [계획](../../../packages/galerkin/cavity3d_validation.md), [mesh 재검증](../../../packages/galerkin/cavity3d_alternating_validation.md), [수렴 진단](../../../packages/galerkin/cavity3d_convergence_diagnosis.md) | [한국어](packages/galerkin/cavity3d_validation.md) |
| 손실 재료 공동 | [복소 공진·Q·벽 손실·정답](../../../packages/galerkin/material_cavity.md) | [한국어](packages/galerkin/material_cavity.md) |
| 공동 모델 문서·CLI | [입력·저장 장 계약](../../../packages/simcase/cavity3d.md) | [한국어](packages/simcase/cavity3d.md) |
| 벡터 부분공간 추적 | [선택형 군집 sweep](../../../packages/simcase/vector_subspace_tracking.md) | [한국어](packages/simcase/vector_subspace_tracking.md) |
| 복소 벡터 고유공간 | [보존 방식·한계](../../../packages/galerkin/eigenspace_reliability.md) | [한국어](packages/galerkin/eigenspace_reliability.md) |
| 정적 탄성 | [평면 모델·구속](../../../packages/galerkin/elasticity2d.md) | [한국어](packages/galerkin/elasticity2d.md) |
| 탄성 수용검증 | [독립 연속체 대조](../../../packages/galerkin/elasticity2d_independent_validation.md) | [한국어](packages/galerkin/elasticity2d_independent_validation.md) |
| 경계 표면하중 | [하중·외향 법선](../../../packages/galerkin/elasticity_traction.md) | [한국어](packages/galerkin/elasticity_traction.md) |
| 표면하중 수용검증 | [독립 힘·일·수렴](../../../packages/galerkin/elasticity_traction_independent_validation.md) | [한국어](packages/galerkin/elasticity_traction_independent_validation.md) |
| 정상 열전도 | [Kelvin·열유속·경계 부호](../../../packages/galerkin/thermal_steady2d.md) | [한국어](packages/galerkin/thermal_steady2d.md) |
| 열전도 수용검증 | [독립 source·설치본 근거](../../../packages/galerkin/thermal_independent_validation.md) | [한국어](packages/galerkin/thermal_independent_validation.md) |
| 영역별 재료 | [영역별 열·탄성·열탄성 재료, 층상 정답](../../../packages/galerkin/multimaterial.md) | [한국어](packages/galerkin/multimaterial.md) |
| 처방 온도장 기계단계 | [Snapshot·3D 감소·에너지](../../../packages/galerkin/prescribed_temperature_thermoelasticity.md) | [한국어](packages/galerkin/prescribed_temperature_thermoelasticity.md) |
| 기계단계 수용검증 | [독립 원3D 재료 법칙](../../../packages/galerkin/prescribed_temperature_thermoelasticity_independent_validation.md) | [한국어](packages/galerkin/prescribed_temperature_thermoelasticity_independent_validation.md) |
| 처방 열유속·Robin 경계 | [외향 열유속·대류](../../../packages/galerkin/thermal_flux_robin.md) | [한국어](packages/galerkin/thermal_flux_robin.md) |
| 열유속·Robin 수용검증 | [독립 경계 검사](../../../packages/galerkin/thermal_flux_robin_independent_validation.md) | [한국어](packages/galerkin/thermal_flux_robin_independent_validation.md) |
| 정상 열전도 문서 | [헤드리스 JSON/API/CLI](../../../packages/simcase/thermal_steady2d.md) | [한국어](packages/simcase/thermal_steady2d.md) |
| 열전도 영역 문서 | [정상·과도, 재료 표와 도형](../../../packages/simcase/thermal_regions2d.md) | [한국어](packages/simcase/thermal_regions2d.md) |
| 열전도 문서 수용검증 | [독립 문서 검사](../../../packages/simcase/thermal_simcase_independent_validation.md) | [한국어](packages/simcase/thermal_simcase_independent_validation.md) |
| 정상 경계조건 문서 | [변별 상수 열유속·대류, v1/v2 필드](../../../packages/simcase/thermal_steady_boundary2d.md) | [한국어](packages/simcase/thermal_steady_boundary2d.md) |
| 정상 경계조건 수용검증 | [해석해·요소·수렴 기준](../../../packages/simcase/steady_boundary_independent_validation.md) | [한국어](packages/simcase/steady_boundary_independent_validation.md) |
| 정상 열전도 Studio | [전용 화면·오류·자원 정책](../../../packages/simcase/thermal_studio.md) | [한국어](packages/simcase/thermal_studio.md) |
| 정상 Studio 수용검증 | [독립 Studio 검사](../../../packages/simcase/studio_thermal_independent_validation.md) | [한국어](packages/simcase/studio_thermal_independent_validation.md) |
| 과도 열전도 엔진 | [후진 Euler·Dirichlet·단열](../../../packages/galerkin/transient_heat.md) | [한국어](packages/galerkin/transient_heat.md) |
| 과도 열전도 검증 | [시간·공간 기준](../../../packages/galerkin/transient_heat_validation.md) | [한국어](packages/galerkin/transient_heat_validation.md) |
| 과도 열전도 수용검증 | [독립 기준해](../../../packages/galerkin/transient_heat_independent_validation.md) | [한국어](packages/galerkin/transient_heat_independent_validation.md) |
| 과도 열전도 문서 | [입력·시간축·저장 이력](../../../packages/simcase/thermal_transient2d.md) | [한국어](packages/simcase/thermal_transient2d.md) |
| 과도 열전도 Studio | [시간 index·장·이력 화면](../../../packages/simcase/thermal_transient_studio.md) | [한국어](packages/simcase/thermal_transient_studio.md) |
| 과도 Studio 수용검증 | [독립 Studio 검사](../../../packages/simcase/studio_transient_thermal_independent_validation.md) | [한국어](packages/simcase/studio_transient_thermal_independent_validation.md) |
| 정상 열전도→기계 workflow | [같은 메시 단방향 workflow](../../../packages/galerkin/thermal_mechanical_workflow.md) | [한국어](packages/galerkin/thermal_mechanical_workflow.md) |
| workflow 수용검증 | [독립 workflow 검사](../../../packages/galerkin/thermal_mechanical_independent_validation.md) | [한국어](packages/galerkin/thermal_mechanical_independent_validation.md) |
| 처방 온도장 표면하중 | [열변형률과 전체 표면하중](../../../packages/galerkin/thermoelastic_traction.md) | [한국어](packages/galerkin/thermoelastic_traction.md) |
| 열탄성 표면하중 수용검증 | [독립 하중·에너지](../../../packages/galerkin/thermoelastic_traction_independent_validation.md) | [한국어](packages/galerkin/thermoelastic_traction_independent_validation.md) |

## Benchmark와 자원 관측

| English | 한국어 |
|---|---|
| [Vector waveguide benchmark](../../../benchmark_vector.md) | [한국어](benchmark_vector.md) |
| [Cavity benchmark](../../../benchmark_cavity.md) | [한국어](benchmark_cavity.md) |
| [Transient Studio resource observer](../../../transient_resource_probe.md) | [한국어](transient_resource_probe.md) |

## 패키지 개요

패키지 README는 각각의 의존성·공개 진입점·범위를 설명합니다. 전체 구성은 구현 여섯 개와
이름 예약 배포 하나입니다. `openphysics` 이름 예약 패키지를 설치해도 전체 도구가 설치되지는
않습니다.

| 패키지 | English | 한국어 |
|---|---|---|
| galerkin | [English](../../../packages/galerkin/overview.md) | [한국어](packages/galerkin/overview.md) |
| galerkin-refsol | [English](../../../packages/galerkin-refsol/overview.md) | [한국어](packages/galerkin-refsol/overview.md) |
| meshine | [English](../../../packages/meshine/overview.md) | [한국어](packages/meshine/overview.md) |
| gmshio | [English](../../../packages/gmshio/overview.md) | [한국어](packages/gmshio/overview.md) |
| physmat | [English](../../../packages/physmat/overview.md) | [한국어](packages/physmat/overview.md) |
| simcase | [English](../../../packages/simcase/overview.md) | [한국어](packages/simcase/overview.md) |
| openphysics | [English](../../../packages/openphysics/overview.md) | [한국어](packages/openphysics/overview.md) |
