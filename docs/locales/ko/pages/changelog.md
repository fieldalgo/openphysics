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

- Scalar/full-vector 모드 PML·일정 반경 굽힘: 복소 후보 진단, 물리창 추적, 총 감쇠, Studio 입력 및 독립 slab/원통 기준 검증.

구현 패키지 여섯 개와 `openphysics` 메타 배포판의 첫 PyPI 릴리스이며, 0.1.0으로
계획돼 있습니다.

### Added

- 수동 복소 scalar/full-vector 도파관 모드, 복소 분리 모드 sweep, dB/cm 손실과 Studio/JSON/NPZ 출력. [부호와 한계](packages/simcase/lossy_modes.md).

- 정확한 정답과 대조하는 공개 기준값 벤치마크를 추가했습니다: Timoshenko (1925) 바이메탈
  띠(`refsol.bimetal`)와 NAFEMS T4 대류 열전달(`refsol.thermal_convection`, 출판 목표값
  18.3 °C 포함). 메시 수렴 기준, 그림 스크립트, 검증 문서
  `docs/packages/galerkin/public_benchmarks.md`가 함께 들어갔고 엔진 코드는 바뀌지 않았습니다.

- 같은 메시의 명시적 정상 전기→열 연성과 메시 사본에 결합한 요소별 열원 입력을
  추가했습니다. 해석해 수렴·에너지 수지·독립 도구 비교로 검증했습니다.

### Changed

- `openphysics`는 메타 배포판입니다. 코드가 없고 여섯 구현 패키지를 의존성으로 요구합니다.
  extra `studio`, `export`, `rii`는 `simcase[studio]`, `simcase[export]`,
  `physmat[rii]`를 설치합니다. 어떤 extra도 Gmsh를 설치하지 않습니다. 이전의
  `openphysics` 0.0.1은 다른 여섯 이름의 0.0.1과 마찬가지로 빈 이름 예약이었습니다.
- 모든 패키지가 Python 3.12 이상을 요구합니다. numpy·scipy·shapely·matplotlib의 최소 버전은
  Python 3.12 휠이 있는 첫 릴리스인 1.26, 1.11.2, 2.0.2, 3.8로 올렸습니다.
- 패키지 사이의 의존성은 0.1 계열(`>=0.1.0,<0.2`)로 제한됩니다.

- 온도 의존 2D 정상 Joule heating: 유효 범위 물성, 완화 Picard 반복, 실패 이력 및 독립 검증 추가.
