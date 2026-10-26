# 결과·내보내기·신뢰성

[English](../../../../results/index.md) | **한국어**

[문서 홈](../index.md)

해석이 종료되었다는 사실과 물리 결과를 신뢰할 수 있다는 판단은 다릅니다. 저장된 모델과
설정, 단위, 보존 관계, 독립 기준해와 수렴을 함께 확인하세요.

1. **실행 기록:** 원래 모델, 해석 설정과 요약을 해당 저장 형식으로 보존합니다.
2. **장과 좌표:** 복소 모드 계수, 물리 좌표와 PML 좌표, 시간 index의 의미를 확인합니다.
3. **물리 검사:** 전류·에너지 보존이나 독립 기준해 등 해당 계약의 검사를 확인합니다.
4. **수렴:** 메시·시간 간격·PML 조건 등 모델에 맞는 축을 독립적으로 바꿉니다.
5. **근거 범위:** 과거 검증 기록과 현재 커밋의 CI 결과를 구분합니다.

## 저장과 내보내기

JSON/CLI의 저장 파일과 export 지원은 모델마다 다릅니다. `simcase[export]`를 설치해도
모든 결과가 VTU/PVD로 변환되는 것은 아닙니다. 정확한 지원 범위는 simcase 개요와
해당 물리 계약을 확인하세요.

## 결과 형식과 해석

- [simcase — 모델 문서와 헤드리스 실행기](../packages/simcase/overview.md)
- [전기전도·Joule heating 문서](../packages/simcase/electric_joule.md)
- [벡터 고유공간 신뢰성](../packages/galerkin/eigenspace_reliability.md)
- [모드 복소 좌표](../packages/galerkin/modal_coordinates.md)
- [직사각형의 headless 과도 열전도](../packages/simcase/thermal_transient2d.md)


## 독립 근거와 재현성

- [검증·벤치마크](../validation/index.md)
- [저장 레퍼런스 값](../stored-reference-values.md)
- [레퍼런스 도구 비교](../reference-comparisons.md)
- [개발과 검증](../development.md)

## 내 모델로 확장하기

- [저장한 장 읽기와 ParaView 내보내기](saved-results.md)
- [내 계산의 수렴 확인하기](../validation/convergence.md)
- [모델·솔버·결과 오류 진단하기](../guide/troubleshooting.md)

- [도파로 모드와 손실 해석](waveguide-modes.md)

- [열팽창·응력·반력 해석하기](thermoelastic-controls.md)
- [재현 가능한 계산 기록 보관하기](run-records.md)
