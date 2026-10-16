# OpenPhysics 문서

[English](../../../README.md) | **한국어**

[도구 개요·설치 안내](overview.md) · [영어 개요](../../../overview.md)

[구조도와 패키지 관계](architecture.md) · [English architecture](../../../architecture.md)

기본 언어는 영어다. README와 기여·보안 진입 문서는 영어로 유지한다. 영어·한국어 지원은 `docs/` 안에서만 제공하며, 영어는 `docs/<이름>.md`, 한국어는 `docs/locales/ko/pages/<이름>.md`에 둔다. 패키지 개요도 이 구조를 따른다. 수식·API·단위·명령·검증 수치와 한계는 두 언어에서 같은 의미로 유지하며 번역은 새 검증 근거가 아니다.

아래는 이 checkout에 실제 포함된 영어·한국어 구현 계약과 검증 보고다. 번역을 추가한 것과 수치 실험을 실행한 것은 구분한다.

## 현재 구현의 사용 계약과 검증 근거

| 주제 | 영어 원문 | 한국어판 상태 |
|---|---|---|
| 3D PEC 공동 엔진 | [API·단위·수렴](../../../../packages/galerkin/docs/cavity_solver.md) | [한국어](../../../../packages/galerkin/docs/locales/ko/pages/cavity_solver.md) |
| 공동 모델 문서·CLI | [입력·저장 장 계약](../../../../packages/simcase/docs/cavity3d.md) | [한국어](../../../../packages/simcase/docs/locales/ko/pages/cavity3d.md) |
| 복소 벡터 고유공간 | [보존 방식·한계](../../../../packages/galerkin/docs/eigenspace_reliability.md) | [한국어](../../../../packages/galerkin/docs/locales/ko/pages/eigenspace_reliability.md) |
| 정적 탄성 | [평면 모델·구속](../../../../packages/galerkin/docs/elasticity2d.md) | [한국어](../../../../packages/galerkin/docs/locales/ko/pages/elasticity2d.md) |
| 탄성 수용검증 | [독립 연속체 대조](../../../../packages/galerkin/docs/elasticity2d_independent_validation.md) | [한국어](../../../../packages/galerkin/docs/locales/ko/pages/elasticity2d_independent_validation.md) |
| 경계 표면하중 | [하중·외향 법선](../../../../packages/galerkin/docs/elasticity_traction.md) | [한국어](../../../../packages/galerkin/docs/locales/ko/pages/elasticity_traction.md) |
| 표면하중 수용검증 | [독립 힘·일·수렴](../../../../packages/galerkin/docs/elasticity_traction_independent_validation.md) | [한국어](../../../../packages/galerkin/docs/locales/ko/pages/elasticity_traction_independent_validation.md) |
| 정상 열전도 | [Kelvin·열유속·경계 부호](../../../../packages/galerkin/docs/thermal_steady2d.md) | [한국어](../../../../packages/galerkin/docs/locales/ko/pages/thermal_steady2d.md) |
| 열전도 수용검증 | [독립 source·설치본 근거](../../../../packages/galerkin/docs/thermal_independent_validation.md) | [한국어](../../../../packages/galerkin/docs/locales/ko/pages/thermal_independent_validation.md) |
| 처방 온도장 기계단계 | [Snapshot·3D 감소·에너지](../../../../packages/galerkin/docs/prescribed_temperature_thermoelasticity.md) | [한국어](../../../../packages/galerkin/docs/locales/ko/pages/prescribed_temperature_thermoelasticity.md) |
| 기계단계 수용검증 | [독립 원3D 재료 법칙](../../../../packages/galerkin/docs/prescribed_temperature_thermoelasticity_independent_validation.md) | [한국어](../../../../packages/galerkin/docs/locales/ko/pages/prescribed_temperature_thermoelasticity_independent_validation.md) |

패키지 README는 각각의 의존성·공개 진입점·범위를 설명한다. 전체 구성은 구현 여섯 개와 이름 예약 배포 하나다. `openphysics` 이름 예약 패키지를 설치해도 전체 도구가 설치되지는 않는다. [CI 안내](../../../../ci/docs/README.md)는 선언한 메타데이터와 실제 시험 환경, 물리 수용과 설치 소비자 시험을 구분한다.

이 checkout에는 헤드리스 열전도 문서와 독립 API의 처방 열유속·Robin 경계가 있다. 아래 계약과 보고는 각각의 구현과 실측 범위를 설명한다. 헤드리스 JSON은 여전히 flux/Robin 경계를 거부한다. Work cloud Linux 결과·Actions 활성·Windows 검증 미확정 범위는 [검증 안내](../../../../ci/docs/locales/ko/pages/README.md)를 참고한다.

## 패키지 개요: 전체 한국어판

| 패키지 | English | 한국어 |
|---|---|---|
| galerkin | [English](../../../../packages/galerkin/docs/overview.md) | [한국어](../../../../packages/galerkin/docs/locales/ko/pages/overview.md) |
| galerkin-refsol | [English](../../../../packages/galerkin-refsol/docs/overview.md) | [한국어](../../../../packages/galerkin-refsol/docs/locales/ko/pages/overview.md) |
| meshine | [English](../../../../packages/meshine/docs/overview.md) | [한국어](../../../../packages/meshine/docs/locales/ko/pages/overview.md) |
| gmshio | [English](../../../../packages/gmshio/docs/overview.md) | [한국어](../../../../packages/gmshio/docs/locales/ko/pages/overview.md) |
| physmat | [English](../../../../packages/physmat/docs/overview.md) | [한국어](../../../../packages/physmat/docs/locales/ko/pages/overview.md) |
| simcase | [English](../../../../packages/simcase/docs/overview.md) | [한국어](../../../../packages/simcase/docs/locales/ko/pages/overview.md) |
| openphysics | [English](../../../../packages/openphysics/docs/overview.md) | [한국어](../../../../packages/openphysics/docs/locales/ko/pages/overview.md) |

## 헤드리스 열전도 구현 계약

| English | 한국어 | Scope / 범위 |
|---|---|---|
| [Contract](../../../../packages/simcase/docs/thermal_steady2d.md) | [한국어](../../../../packages/simcase/docs/locales/ko/pages/thermal_steady2d.md) | 헤드리스 전용이며 실측 범위와 소유권 한계는 계약·독립 보고를 참고한다 |

## 구현 계약과 검증 보고

| English | 한국어 |
|---|---|
| [thermal_flux_robin](../../../../packages/galerkin/docs/thermal_flux_robin.md) | [한국어](../../../../packages/galerkin/docs/locales/ko/pages/thermal_flux_robin.md) |
| [thermal_flux_robin_independent_validation](../../../../packages/galerkin/docs/thermal_flux_robin_independent_validation.md) | [한국어](../../../../packages/galerkin/docs/locales/ko/pages/thermal_flux_robin_independent_validation.md) |
| [thermal_simcase_independent_validation](../../../../packages/simcase/docs/thermal_simcase_independent_validation.md) | [한국어](../../../../packages/simcase/docs/locales/ko/pages/thermal_simcase_independent_validation.md) |
| [README](../../../../ci/docs/README.md) | [한국어](../../../../ci/docs/locales/ko/pages/README.md) |
| [benchmark_cavity](../../../../ci/docs/benchmark_cavity.md) | [한국어](../../../../ci/docs/locales/ko/pages/benchmark_cavity.md) |
| [benchmark_vector](../../../../ci/docs/benchmark_vector.md) | [한국어](../../../../ci/docs/locales/ko/pages/benchmark_vector.md) |

이 문서들은 이 checkout을 설명합니다. Actions는 활성화돼 있으며 마지막 Windows 실행의 두 실패는 미해결 상태이고 Linux 결과가 Windows 수용을 뜻하지 않습니다. 독립 Robin API와 헤드리스 JSON 계약은 별개입니다.

## 명시적 정상 열전도→기계 workflow

Python 전용 workflow는 같은 메시의 절점 P1 Kelvin 장을 동결한 뒤 기계단계를 실행합니다. 정상·단방향이며 JSON/CLI/Studio·저장·과도 해석 지원 범위를 확대하지 않습니다.

| English | 한국어 |
|---|---|
| [thermal_mechanical_workflow](../../../../packages/galerkin/docs/thermal_mechanical_workflow.md) | [한국어](../../../../packages/galerkin/docs/locales/ko/pages/thermal_mechanical_workflow.md) |
| [thermal_mechanical_independent_validation](../../../../packages/galerkin/docs/thermal_mechanical_independent_validation.md) | [한국어](../../../../packages/galerkin/docs/locales/ko/pages/thermal_mechanical_independent_validation.md) |

## 처방 온도장의 전체 기계 표면하중

Python 기계 API는 처방된 절점 P1 Kelvin 온도와 고정 기준 메시에서 선택적 전역 Cartesian 전체 표면하중 `sigma*n`을 Pa로 받습니다. 체적·표면하중의 합이 외부 하중이며 양의 열 등가 하중은 별도로 유지합니다. 계약은 기존 위치 인자 결과 필드 18개를 유지하고 선택적 하중 필드 두 개를 덧붙입니다. 깊이당 힘은 N/m, 물리 탄성 에너지는 J/m이며 평면변형률의 면외 응력과 지지 일을 포함합니다.

고정 경계의 전역 Pa callback `-p*normal`은 유효하지만 scalar pressure 전용·로컬 프레임·follower API는 추가하지 않습니다. 열→기계 workflow나 JSON/CLI/Studio에 traction을 추가하지 않으며 열전도를 실행하거나 온도·경계 태그의 출처를 인증하지 않습니다.

| English | 한국어 |
|---|---|
| [thermoelastic_traction](../../../../packages/galerkin/docs/thermoelastic_traction.md) | [한국어](../../../../packages/galerkin/docs/locales/ko/pages/thermoelastic_traction.md) |
| [thermoelastic_traction_independent_validation](../../../../packages/galerkin/docs/thermoelastic_traction_independent_validation.md) | [한국어](../../../../packages/galerkin/docs/locales/ko/pages/thermoelastic_traction_independent_validation.md) |

구현 계약, 독립 후보 근거와 결합 배포 검증은 서로 다른 범위입니다. 연결된 보고는 정확한 후보와 원 실패를 보존하며 선별 회복이 이전 전체 실패를 전체 통과로 바꾸지는 않습니다. 완료된 결합 결과에는 해당 최종 명령 exit와 완결 JUnit 근거가 필요합니다. 최종 근거 누락이나 transport 단절만으로 수치 성공이나 단절 원인을 확정할 수 없습니다. Linux 검사가 Windows 수용을 입증하지 않습니다.

소스 snapshot `0bc4419f4cfaf9e1185872d14232f1644639fc72`의 Linux cloud 검증은 source 시험 1536개 통과, 하위검사 9개 통과, skip 16개와 명령 exit0을 기록했습니다. Skip은 optional Gmsh 사례 14개와 로컬 refractiveindex.info database 사례 2개입니다. 별도 sdist→wheel 설치 실행은 541개 사례가 실패·skip 없이 통과했습니다. 원 배포 helper의 16개 명령은 모두 exit0으로 완료됐으며 일곱 sdist→wheel build와 artifact 14개의 strict Twine 검사를 포함합니다. 이 snapshot은 `da811aec95f6695f6d7b9988a7d3e9055736ff97`로 통합됐습니다. 결과는 기록된 Linux 환경에 한정되며 Windows·다른 OS 수용이나 이전 transport 단절의 원인을 입증하지 않습니다. 이전 실패·미확인 실행은 별도 근거로 유지합니다.

## 자산 출처

[포함된 이미지·fixture·데이터](assets.md)에서 도입 이력과 라이선스 범위를 확인할 수 있습니다.

## 기여·보안 안내

| English | 한국어 |
|---|---|
| [Contributing](../../../contributing.md) | [한국어](contributing.md) |
| [Security](../../../security.md) | [한국어](security.md) |

## 과도 열전도 후보: 수용 대기

이 기능 branch 후보에는 명시적 `galerkin.transient_heat.solve_transient_heat` 하위 모듈은 고정 P1 삼각형, 일관 질량과 후진 Euler를 사용하며 상수 등방 열전도율·열용량, 시간변 Dirichlet 값과 단열을 지원합니다. 유한 Kelvin 입력은 물리적 유효성이나 최대 원리를 인증하지 않습니다. JSON/CLI/Studio, 저장 또는 자동 열→기계 연결은 추가하지 않습니다.

| English | 한국어 |
|---|---|
| [transient_heat](../../../../packages/galerkin/docs/transient_heat.md) | [한국어](../../../../packages/galerkin/docs/locales/ko/pages/transient_heat.md) |
| [transient_heat_validation](../../../../packages/galerkin/docs/transient_heat_validation.md) | [한국어](../../../../packages/galerkin/docs/locales/ko/pages/transient_heat_validation.md) |
| [transient_heat_independent_validation](../../../../packages/galerkin/docs/transient_heat_independent_validation.md) | [한국어](../../../../packages/galerkin/docs/locales/ko/pages/transient_heat_independent_validation.md) |

구현과 독립 수용 파일은 제출됐습니다. 생산 담당의 사용/검증 페이지에 소형 source 시험 70개 통과가 기록돼 있으며, 전체 시간/PDE·독립 수용·빌드·설치 검증은 별도 근거가 필요합니다. 이 링크는 후보 checkout을 설명하며 develop에 수용된 지원 기능이나 검증된 릴리스를 뜻하지 않습니다. 검증 페이지는 고정 gate와 관측 결과를 구분합니다.

| English | 한국어 |
|---|---|
| [thermoelastic_traction](../../../../packages/galerkin/docs/thermoelastic_traction.md) | [한국어](../../../../packages/galerkin/docs/locales/ko/pages/thermoelastic_traction.md) |
| [thermoelastic_traction_independent_validation](../../../../packages/galerkin/docs/thermoelastic_traction_independent_validation.md) | [한국어](../../../../packages/galerkin/docs/locales/ko/pages/thermoelastic_traction_independent_validation.md) |
