# OpenPhysics 문서

[English](../../../README.md) | **한국어**

[도구 개요·설치 안내](../../../../README.ko.md) · [영어 개요](../../../../README.md)

영어 원문은 기존 패키지 경로에 유지한다. 완전한 한국어판은 각 패키지의 `docs/locales/ko/pages/<같은파일명>.md`, 패키지 개요는 `README.ko.md`에 둔다. 수식·API·단위·부호·실행 명령·검증 수치와 한계는 두 언어에서 같은 의미로 유지한다. 번역을 추가한 것은 수치 실험을 새로 실행하거나 새 합격 근거를 얻었다는 뜻이 아니다.

아래 한국어판은 현재 작성 중이다. 실제 파일의 번역·원문 대조·링크 확인이 끝난 뒤 해당 페이지를 연결한다. 준비 중인 번역을 완료된 문서로 표시하지 않는다.

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

패키지 README는 각각의 의존성·공개 진입점·범위를 설명한다. 전체 구성은 구현 여섯 개와 이름 예약 배포 하나다. `openphysics` 이름 예약 패키지를 설치해도 전체 도구가 설치되지는 않는다. [CI 안내](../../../../ci/README.md)는 선언한 메타데이터와 실제 시험 환경, 물리 수용과 설치 소비자 시험을 구분한다.

화면 없는 열전도 문서 연결과 처방 열유속·Robin 경계는 별도의 개발 후보다. 검토·통합을 마친 뒤 실제 구현 범위에 맞는 사용·검증 문서를 두 언어로 연결한다. 번역 계획만으로 기능이 지원된다고 해석하지 않는다.

## 패키지 개요: 전체 한국어판

| 패키지 | English | 한국어 |
|---|---|---|
| galerkin | [English](../../../../packages/galerkin/README.md) | [한국어](../../../../packages/galerkin/README.ko.md) |
| galerkin-refsol | [English](../../../../packages/galerkin-refsol/README.md) | [한국어](../../../../packages/galerkin-refsol/README.ko.md) |
| meshine | [English](../../../../packages/meshine/README.md) | [한국어](../../../../packages/meshine/README.ko.md) |
| gmshio | [English](../../../../packages/gmshio/README.md) | [한국어](../../../../packages/gmshio/README.ko.md) |
| physmat | [English](../../../../packages/physmat/README.md) | [한국어](../../../../packages/physmat/README.ko.md) |
| simcase | [English](../../../../packages/simcase/README.md) | [한국어](../../../../packages/simcase/README.ko.md) |
| openphysics | [English](../../../../packages/openphysics/README.md) | [한국어](../../../../packages/openphysics/README.ko.md) |

## Headless thermal review candidate / 헤드리스 열전도 검토 후보

| English | 한국어 | Scope / 범위 |
|---|---|---|
| [Contract](../../../../packages/simcase/docs/thermal_steady2d.md) | [한국어](../../../../packages/simcase/docs/locales/ko/pages/thermal_steady2d.md) | Headless only; Windows save/independent acceptance remain separate gates / 헤드리스 전용·Windows 저장 및 독립수용은 별도 gate |

## 검토 후보와 개발 검증 안내

| English | 한국어 |
|---|---|
| [thermal_flux_robin](../../../../packages/galerkin/docs/thermal_flux_robin.md) | [한국어](../../../../packages/galerkin/docs/locales/ko/pages/thermal_flux_robin.md) |
| [thermal_flux_robin_independent_validation](../../../../packages/galerkin/docs/thermal_flux_robin_independent_validation.md) | [한국어](../../../../packages/galerkin/docs/locales/ko/pages/thermal_flux_robin_independent_validation.md) |
| [thermal_simcase_independent_validation](../../../../packages/simcase/docs/thermal_simcase_independent_validation.md) | [한국어](../../../../packages/simcase/docs/locales/ko/pages/thermal_simcase_independent_validation.md) |
| [README](../../../../ci/README.md) | [한국어](../../../../ci/locales/ko/pages/README.md) |
| [benchmark_cavity](../../../../ci/benchmark_cavity.md) | [한국어](../../../../ci/locales/ko/pages/benchmark_cavity.md) |
| [benchmark_vector](../../../../ci/benchmark_vector.md) | [한국어](../../../../ci/locales/ko/pages/benchmark_vector.md) |

이 문서들은 현재 검토 후보에 실제 포함됩니다. develop 최종 수용을 뜻하지 않습니다. Actions는 비활성화돼 있고 Windows 두 실패는 미확정입니다.
