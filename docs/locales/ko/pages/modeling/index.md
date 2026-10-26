# 모델 구성: 형상·재료·메시

[English](../../../../modeling/index.md) | **한국어**

[문서 홈](../index.md)

하나의 해석은 형상·재료·메시·경계조건·study로 구성됩니다. `simcase`는 지원되는 조합을
JSON 문서로 묶고, Python 경로에서는 각 패키지 API를 직접 조합합니다.

| 단계 | 담당과 확인할 내용 |
|---|---|
| 형상·영역 | `simcase` 모델의 영역과 도형, 또는 mesher 입력을 정합니다. |
| 재료 | 광학 물성·분산은 `physmat`; 열·전기·역학 물성은 해당 solver/document 계약을 따릅니다. |
| 메시 | `meshine`의 2D 삼각형 또는 선택적 `gmshio` 경로를 사용합니다. 영역 이름과 경계를 보존합니다. |
| 물리·경계·단위 | `galerkin`의 모델별 부호·단위·경계조건을 확인합니다. |
| study·실행 | 지원되는 `simcase` single/sweep/시간 해석 또는 명시적 Python 호출을 선택합니다. |

패키지를 같은 저장소에서 제공한다는 사실만으로 임의 재료·메시·물리 조합이 지원되지는 않습니다.
특히 광학 분산 모델을 열전도율이나 전기전도도로 해석하지 마세요.

## 형상과 메시

- [meshine — 여러 재료로 구성된 평면 영역의 소형 품질 삼각형 메시 생성기](../packages/meshine/overview.md)
- [gmshio — Gmsh와 링크하지 않고 galerkin에 메시 제공](../packages/gmshio/overview.md)
- [튜토리얼: 내 도파관 해석하기](../packages/simcase/waveguide_tutorial.md)


## 물성과 영역 배정

- [physmat — 물리 솔버용 재료 물성](../packages/physmat/overview.md)
- [이름 있는 영역별 구간 상수 재료](../packages/galerkin/multimaterial.md)
- [재료 영역이 있는 열전도 문서](../packages/simcase/thermal_regions2d.md)


## 문서와 패키지 경계

- [simcase — 모델 문서와 헤드리스 실행기](../packages/simcase/overview.md)
- [OpenPhysics 구조](../architecture.md)
- [물리 문제별 안내](../physics/index.md)
