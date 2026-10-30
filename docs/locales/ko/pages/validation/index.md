# 검증·벤치마크

[English](../../../../validation/index.md) | **한국어**

[문서 홈](../index.md)

검증 기록은 기준해·고정 허용치·측정 범위에 대한 근거입니다. 특정 커밋의 통과 여부는
해당 커밋의 CI 로그와 artifact에서 확인하세요. 과거 기록이나 실행 계획은 현재 코드의
통과를 뜻하지 않으며, 자원 관측은 성능 보장이 아닙니다.

## galerkin 수용 검증·기준해

- [2D 탄성의 독립 수용 검증](../packages/galerkin/elasticity2d_independent_validation.md)
- [경계 traction의 독립 수용 검증](../packages/galerkin/elasticity_traction_independent_validation.md)
- [처방 온도장 기계단계의 독립 수용 검증](../packages/galerkin/prescribed_temperature_thermoelasticity_independent_validation.md)
- [공개 기준값 벤치마크: 바이메탈 띠와 NAFEMS T4](../packages/galerkin/public_benchmarks.md)
- [Outward flux·Robin 열전도의 독립 수용 검증](../packages/galerkin/thermal_flux_robin_independent_validation.md)
- [정상 열전도 독립 수용 검증](../packages/galerkin/thermal_independent_validation.md)
- [정상 열전도 → 기계 workflow 독립 수용](../packages/galerkin/thermal_mechanical_independent_validation.md)
- [처방 온도 열탄성 traction 독립 수용](../packages/galerkin/thermoelastic_traction_independent_validation.md)
- [비정상 열전도 독립 수용 검증](../packages/galerkin/transient_heat_independent_validation.md)
- [과도 열전도 검증 계약](../packages/galerkin/transient_heat_validation.md)

## simcase 수용 검증·기준해

- [정상 열전도 경계 headless 독립 수용](../packages/simcase/steady_boundary_independent_validation.md)
- [정상열 Studio 독립 검증](../packages/simcase/studio_thermal_independent_validation.md)
- [과도 Studio 독립 수용](../packages/simcase/studio_transient_thermal_independent_validation.md)
- [Headless 열전도 문서의 독립 검증](../packages/simcase/thermal_simcase_independent_validation.md)

## 최근 계약에 포함된 검증 근거

- [2D 정상 전기전도](../packages/galerkin/electric_steady2d.md)
- [정상 Joule heating](../packages/galerkin/joule_heating.md)
- [온도 의존 정상 Joule heating](../packages/galerkin/temperature_joule_heating.md)
- [모드 복소 좌표](../packages/galerkin/modal_coordinates.md)
- [흡수 도파관 모드](../packages/simcase/lossy_modes.md)
- [PML·누설·일정 반경 모드](../packages/simcase/pml_modes.md)

## 메시 생성 계획

- [사전 등록 검증 계획: 3D 사면체 메시 생성](../packages/meshine/validation3d.md)

## 과거 공동·단계별 기록

- [진공 PEC 직육면체 공진기 독립 검증 계획](../packages/galerkin/cavity3d_validation.md)
- [교대 Kuhn 공진기 mesh의 독립 검증](../packages/galerkin/cavity3d_alternating_validation.md)
- [직육면체 PEC 111 doublet: 부호 있는 평균 수렴 진단](../packages/galerkin/cavity3d_convergence_diagnosis.md)
- [galerkin 단계별 검증 결과(2026-09-05)](../packages/galerkin/milestone_validation.md)

## 외부 기준해와 저장값

- [레퍼런스 도구 비교](../reference-comparisons.md)
- [저장 레퍼런스 값](../stored-reference-values.md)

## 벤치마크와 자원 관측

- [벡터 모드 성능 측정](../benchmark_vector.md)
- [3D PEC 공진기의 시간·메모리 측정](../benchmark_cavity.md)
- [Transient Studio 자원 관측기](../transient_resource_probe.md)
- [영역 Studio 자원 관측](../region_resource_probe.md)

## 내 모델로 확장하기

- [인과적 거칠기: 독립 스펙트럼 적분·R/L 수렴](../packages/sipi/roughness.md#검증과-한계)

- [내 계산의 수렴 확인하기](convergence.md)

- [슬래브 해석해로 도파로 검증하기](slab-tutorial.md)

- [전송선 네트워크 해석식·독립 도구 검증](../packages/sipi/network_validation.md)
- [사다리꼴 도체·평탄 코팅 계약과 검증](../packages/sipi/manufacturing_sections.md)
- [분산 유전체: 해석식·독립 도구·메시 검증](../packages/sipi/dielectrics.md#검증과-재현)

- [도체 확산: Bessel/DC 해, 메시·영역 수렴, 독립 조립](../packages/sipi/conductor_diffusion.md#검증과-제한)

[동일 기하 유한 금속·유전체 DC/AC RLGC와 버전 JSON](../packages/sipi/volume_line.md).
