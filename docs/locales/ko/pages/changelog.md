# 변경 기록

[English](../../../../CHANGELOG.md) | **한국어**

OpenPhysics 배포판 일곱 개(`galerkin`, `galerkin-refsol`, `meshine`, `gmshio`,
`physmat`, `simcase`, 그리고 `openphysics` 메타 배포판)는 하나의 버전 번호로 함께
릴리스됩니다. 이 문서는 릴리스마다 바뀐 점을 기록합니다. 형식은
[Keep a Changelog](https://keepachangelog.com/ko/1.1.0/)를 따릅니다. 기준 문서는 영어판
`CHANGELOG.md`입니다.

## 0.x의 안정성

0.x 릴리스는 알파입니다.

- 모든 패키지의 Python API는 마이너 릴리스(0.1에서 0.2)마다 바뀔 수 있습니다. 패치
  릴리스(0.1.x)는 버그를 고치며 API를 바꾸려는 것이 아닙니다.
- JSON 모델 문서 형식 `"openphysics": "0.2"`는 계약입니다. 이 형식으로 유효한 문서는 계속
  유효하고 뜻도 그대로입니다. 이를 깨는 변경에는 새 형식 버전을 붙입니다.
- 저장 결과의 형식·필드 layout 식별자(예: `thermal.steady2d-result-v1`,
  `cavity3d-edge-v1`)는 계약입니다. 어떤 식별자가 붙은 파일은 그 layout을 유지합니다.
  layout이 바뀌면 새 식별자를 붙입니다.

각 패키지가 구현하는 범위와 한계는 [개요](overview.md)에 있습니다.

## [Unreleased]

구현 패키지 여섯 개와 `openphysics` 메타 배포판의 첫 PyPI 릴리스이며, 0.1.0으로
계획돼 있습니다.

### Changed

- `openphysics`는 메타 배포판입니다. 코드가 없고 여섯 구현 패키지를 의존성으로 요구합니다.
  extra `studio`, `export`, `rii`는 `simcase[studio]`, `simcase[export]`,
  `physmat[rii]`를 설치합니다. 어떤 extra도 Gmsh를 설치하지 않습니다. 이전의
  `openphysics` 0.0.1은 다른 여섯 이름의 0.0.1과 마찬가지로 빈 이름 예약이었습니다.
- 모든 패키지가 Python 3.12 이상을 요구합니다.
- 패키지 사이의 의존성은 0.1 계열(`>=0.1.0,<0.2`)로 제한됩니다.
