# Python·JSON/CLI·Studio 실행 경로 선택

[English](../../../../guide/execution-paths.md) | **한국어**

[문서 홈](../index.md)

먼저 물리 문제와 필요한 제어 항목을 정합니다. OpenPhysics 인터페이스는 엔진을
공유하지만 노출하는 기능이 같지는 않습니다.

| 경로 | 선택할 상황 | 범위 |
|---|---|---|
| Python 패키지 API 직접 호출 | 역학·명시적 열 → 역학 연성·세부 수치 제어가 필요할 때 | 지원되는 메시·계수·경계 객체를 직접 조합 |
| Python `Document` + `run` | 지원되는 simcase 모델을 Python으로 자동화할 때 | JSON/CLI와 같은 문서 계약 사용 |
| JSON/CLI | 재현 가능한 모델 검증·일괄 실행·결과 저장이 필요할 때 | 문서당 지원되는 물리 항목 하나이며, 임의 다중물리 그래프는 아님 |
| 기존 Studio `/` | 2D 광학 또는 직사각형이거나 재료 영역이 있는 정상/과도 열 모델을 브라우저에서 편집할 때 | 공동·전기/Joule·역학 편집기 없음; 재료 영역이 있는 열 문서는 Studio 영역 한도 안에서만 |
| 실험적 workspace `/workspace` | 제한된 광학 워크플로와 세션 노트북을 사용할 때 | 고정 광학 어댑터이며 가열 도파로 화면은 설정 미리보기 |

## 물리 문제에 맞는 경로 찾기

[지원 문서 표](../packages/simcase/overview.md#지원하는-문서)에서 JSON/CLI의
도파로·직사각형 공동·영역별 재료를 포함한 직사각형 정상/과도 열·지원되는 전기/Joule
모델을 확인합니다. 경계조건·study·계수 제한은 각 모델 계약에 정의되어 있습니다.
Python 엔진에 기능이 있다고 JSON 필드나 Studio 제어 항목이 자동으로 생기지는 않습니다.

열 → 열탄성에는 [Python 역학 직접 호출](../packages/galerkin/thermal_mechanical_workflow.md)을
사용합니다. 명시적 비선형 제어는
[온도 의존 Joule 튜토리얼](../packages/galerkin/temperature_joule_tutorial.md)을 따릅니다.
다중 재료 열 모델을 headless로 실행하려면
[두 재료 벽](../packages/simcase/layered_wall_tutorial.md)부터 시작하세요.

## 문서 검증과 실행

[simcase 설치](../packages/simcase/overview.md) 후 저장소 루트에서 제공된 벽 모델을
실행합니다.

```sh
python -m simcase validate examples/simcase/layered_wall.json
python -m simcase run examples/simcase/layered_wall.json -o out/wall-cli
```

새 디렉터리나 빈 출력 디렉터리를 사용하세요. 문서 검증은 문서 규칙을 검사하며,
메시 수렴·보존·물리적 타당성을 입증하지는 않습니다.
[저장 결과](../results/saved-results.md)를 확인하고 해당
[수렴 검사](../validation/convergence.md)를 수행합니다.

## 브라우저 워크플로 구분하기

기존 Studio와 실험적 workspace는 `simcase-studio`가 제공하지만 저장 파일의 계약이
다릅니다. 기존 편집기는 지원되는 simcase 모델 문서를 사용합니다. Workspace의
입력/세션 JSON은 별도 형식이며, 결과가 담길 수 있는 세션 파일은 headless solver
문서가 아닙니다. 고정된 형상·파장·재료 선택·내보내기·복원 제한은
[workspace 가이드](../packages/simcase/workspace.md)를 따릅니다.

가열 도파로 workspace 미리보기는 열–광학 연성 결과를 계산하지 않습니다. 어댑터
범위 밖의 제어가 필요하면 지원되는 문서나 Python 워크플로를 사용하세요. 내보낸
이미지와 함께 모델·실행 설정을 보관합니다. 이미지만으로는 계산을 재현할 수 없습니다.
