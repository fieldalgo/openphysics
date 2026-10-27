# 변경 기록

[English](../../../../CHANGELOG.md) | **한국어**

OpenPhysics 배포판 여덟 개(`galerkin`, `galerkin-refsol`, `meshine`, `gmshio`,
`physmat`, `simcase`, `sipi`, 그리고 `openphysics` 메타 배포판)는 하나의 버전 번호로 함께
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

- `galerkin`: PEC 상자 공진기(`solve_cavity_box`)가 JAX나 PyTorch 상자 길이를 받고, 주파수, 고유값, 모서리 계수, 중심 필드를 그 라이브러리로 돌려주며 역방향 미분을 붙입니다. 메시의 축 방향 배율을 거쳐 정확합니다. 축퇴 모드는 NaN 미분과 `DegenerateModeWarning`을 받습니다. NumPy 결과는 바뀌지 않습니다. [문서](packages/galerkin/differentiation.md#상자-공진기-길이에-대한-미분).

- `galerkin`: 도파관 모드(`solve_modes`)가 eps_r, mu_r(스칼라 또는 요소 배열, 실수·복소수)와 k0에 JAX나 PyTorch 값을 받고, n_eff와 두 필드 배열을 그 라이브러리로 돌려주며 고유값과 필드의 역방향 미분을 붙입니다. 축퇴 모드는 NaN 미분과 `DegenerateModeWarning`을 받습니다. NumPy 결과는 바뀌지 않습니다. [문서](packages/galerkin/differentiation.md#도파관-모드-고유값-필드-축퇴-모드).

- `galerkin`: 탄성과 열탄성이 E, nu, alpha, 기준 온도, Dirichlet 변위, 체적력, 견인력에 JAX나 PyTorch 값을 받고 역방향 미분을 돌려줍니다. NumPy 결과는 바뀌지 않습니다. [문서](packages/galerkin/differentiation.md).

- `galerkin`: 과도 열전도가 전도도, 열용량, 열원, Dirichlet 온도, 초기 온도장에 JAX나 PyTorch 값을 받고, 모든 시간 단계를 거치는 역방향 미분을 돌려줍니다. `checkpoint_every`로 재계산과 메모리를 맞바꿀 수 있습니다. NumPy 결과는 바뀌지 않습니다. [문서](packages/galerkin/differentiation.md#과도-열-메모리와-checkpoint).

- `galerkin`: 정상 열전도와 정상 전기 전도가 전도도, 열원, Dirichlet·기준 전위, 경계 데이터에 JAX나 PyTorch 값을 받고, 결과를 그 라이브러리로 미분과 함께 돌려줍니다(adjoint 희소 풀이를 통한 역방향 모드). NumPy 결과는 바뀌지 않습니다. 아직 미분하지 않는 solver는 미분을 조용히 버리지 않고 JAX·PyTorch 값을 거부합니다. [문서](packages/galerkin/differentiation.md).

- 신호·전원 무결성 패키지 `sipi`를 추가합니다. 층 유전체와 직사각형 트레이스로 된 PCB 단면을 준정적(quasi-TEM)으로 풀어 C·L·유전 손실 G 행렬, 단일선 임피던스와 유효 유전율, 결합선 even/odd 모드를 계산합니다. 평행판·동축 정확해, Cohn 스트립라인 정확해, Hammerstad–Jensen 마이크로스트립 식과 비교해 검증했으며 도체 손실은 포함하지 않습니다. `openphysics[sipi]`로 설치합니다. [문서](packages/sipi/overview.md).

- `/workspace`에 실험적 모델 작업공간을 추가합니다. 고정 조건 광학 실행, 모델 편집 이력, 세션 파일과 버전이 있는 지원 범위 계약을 제공하며 기존 광학·열 편집기를 유지합니다.

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

- 전기전도·상수/온도 의존 Joule heating의 직사각형 JSON/CLI, SI 결과 저장과 실패 반복 근거를 추가했다. 기존 솔버를 재사용한다.
