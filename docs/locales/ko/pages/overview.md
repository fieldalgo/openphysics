# OpenPhysics

[English](../../../overview.md) | **한국어**

OpenPhysics는 전자기장, 열전도와 고체역학을 위한 Python 시뮬레이션 도구 모음입니다.
유한요소 해석기, 메시 생성, 재료 모델과 독립 해석해를 한 저장소에서 제공합니다.
Python API를 직접 호출하거나, 지원하는 모델을 JSON으로 실행하거나,
로컬 브라우저 Studio에서 2D 광학 모델과 직사각형 열전도 문서를 살펴볼 수 있습니다.

현재 개발 중인 프로젝트입니다. 기능마다 입력·출력 계약과 검증 범위를 명시하며,
이름이 범용 다중물리 완전 연성 해석기의 지원을 뜻하지는 않습니다.

## 해석할 수 있는 문제

| 분야 | 구현 범위 | 안내 |
|---|---|---|
| 전자기 | 2D 스칼라·전체 벡터 도파 모드, 복소 장과 모드 추적을 유지하는 분리 가능한 모드의 파장 sweep | [모델 실행기](../../../../packages/simcase/docs/locales/ko/pages/overview.md), [벡터 신뢰성](../../../../packages/galerkin/docs/locales/ko/pages/eigenspace_reliability.md) |
| 3D 공동 | Python API 또는 단일 JSON study를 통한 직육면체 공동 고유모드: 진공 PEC, 또는 손실 직육면체 재료와 도체 벽(복소 주파수와 Q) | [공동 API](../../../../packages/galerkin/docs/locales/ko/pages/cavity_solver.md), [재료 공동](../../../../packages/galerkin/docs/locales/ko/pages/material_cavity.md), [JSON 계약](../../../../packages/simcase/docs/locales/ko/pages/cavity3d.md) |
| 열전도 | 정상·상수·등방 2D 열전도, Dirichlet·처방 열유속·Robin 경계, 변별 상수 경계 데이터를 받는 직사각형 헤드리스 JSON 경로와 전용 Studio 화면 | [열전도 API](../../../../packages/galerkin/docs/locales/ko/pages/thermal_steady2d.md), [열유속·Robin](../../../../packages/galerkin/docs/locales/ko/pages/thermal_flux_robin.md), [열전도 JSON](../../../../packages/simcase/docs/locales/ko/pages/thermal_steady2d.md), [경계조건 JSON](../../../../packages/simcase/docs/locales/ko/pages/thermal_steady_boundary2d.md), [Studio](../../../../packages/simcase/docs/locales/ko/pages/thermal_studio.md) |
| 과도 열전도 | 2D Python 엔진과 직사각형 headless JSON/API/CLI/save, 고정 P1·일관 질량·후진 Euler, 상수 등방 물성·명시 시간·표본 Dirichlet/단열, 전용 Studio 시간·장·이력 화면 | [과도 열전도](../../../../packages/galerkin/docs/locales/ko/pages/transient_heat.md), [문서](../../../../packages/simcase/docs/locales/ko/pages/thermal_transient2d.md), [검증](../../../../packages/galerkin/docs/locales/ko/pages/transient_heat_validation.md), [Studio](../../../../packages/simcase/docs/locales/ko/pages/thermal_transient_studio.md) |
| 고체역학 | 정적 2D 선형탄성, 평면응력·평면변형률, 전역 Cartesian 경계 표면하중 | [탄성](../../../../packages/galerkin/docs/locales/ko/pages/elasticity2d.md), [표면하중](../../../../packages/galerkin/docs/locales/ko/pages/elasticity_traction.md) |
| 열팽창 | 처방 절점 온도장의 기계해석, 선택적 전체 표면하중, 명시적인 동일 메시 정상 열전도→기계 workflow | [처방 온도](../../../../packages/galerkin/docs/locales/ko/pages/prescribed_temperature_thermoelasticity.md), [전체 표면하중](../../../../packages/galerkin/docs/locales/ko/pages/thermoelastic_traction.md), [workflow](../../../../packages/galerkin/docs/locales/ko/pages/thermal_mechanical_workflow.md) |
| 과도 열응력 | 같은 고정 메시에서 저장된 과도 열전도 시간 중 고른 시간마다 준정적 선형 미소변형 기계해석, 명시적인 두 번째 Python 호출 | [과도 열전도→기계](../../../../packages/galerkin/docs/locales/ko/pages/transient_thermal_mechanical.md) |

### 기능별 사용 경로

| 기능 | Python API | JSON / CLI | Studio |
|---|---|---|---|
| 2D 도파 모드와 sweep | 지원 | `em.modes2d`(무손실) | 지원 |
| 3D PEC 공동 | 지원 | `em.cavity3d` | 미지원 |
| 정상 열전도 | 지원 | 직사각형 `thermal.steady2d` | 전용 화면 |
| 과도 열전도 | 지원 | 직사각형 `thermal.transient2d` | 전용 화면 |
| 탄성·열팽창·열전도→기계 | 지원 | 미지원 | 미지원 |

Python 전용 기능이 JSON이나 Studio에도 자동으로 제공되는 것은 아닙니다.

### 현재 한계

- 열전도→기계 연성은 단방향입니다. 열로 되먹임이 없는 명시적인 두 번째 Python 호출이며,
  열역학적 완전 피드백 연성은 지원하지 않습니다.
- 과도 열전도는 restart·과도 flux/Robin 입력·자동 연성을 제공하지 않습니다.
- 정상 열전도→기계 workflow는 별도 Robin·열유속·표면하중 확장을 아직 받지 않습니다.
- 비선형 역학, 형상 sweep, 손실 모드 문서 해석은 지원하지 않습니다.
- Studio는 3D 모델을 거절하며 기계해석 폼이 없습니다.

## 패키지 구성

모든 구현 소스와 문서를 이 저장소에서 제공합니다. 패키지별로 배포 이름, 버전,
의존성과 라이선스 고지를 관리합니다.

| 패키지 | 역할 |
|---|---|
| [galerkin](../../../../packages/galerkin/docs/locales/ko/pages/overview.md) | 유한요소 해석기와 장 후처리 |
| [galerkin-refsol](../../../../packages/galerkin-refsol/docs/locales/ko/pages/overview.md) | 독립 해석해와 출판된 benchmark. Python에서는 `refsol`로 import |
| [meshine](../../../../packages/meshine/docs/locales/ko/pages/overview.md) | 재료 영역의 2D 삼각형 메시 |
| [gmshio](../../../../packages/gmshio/docs/locales/ko/pages/overview.md) | 선택적 Gmsh 실행파일 연동, MSH reader와 메시 adapter |
| [physmat](../../../../packages/physmat/docs/locales/ko/pages/overview.md) | 재료 물성, 광학 분산과 Drude–Lorentz fitting |
| [simcase](../../../../packages/simcase/docs/locales/ko/pages/overview.md) | JSON 문서, 헤드리스 실행기와 선택적 로컬 Studio |

일곱 번째 배포인 [openphysics](../../../../packages/openphysics/docs/locales/ko/pages/overview.md)(`0.0.1`)는
프로젝트 이름만 예약합니다. 엔진을 포함하지 않고 위 패키지들을 설치하지도 않습니다.
저장소 루트 자체도 설치 가능한 배포가 아닙니다.
**아래 소스 설치 방법을 사용하세요. `pip install openphysics`만으로는 시뮬레이션
도구 모음이 설치되지 않습니다.**

## 소스에서 설치

CI는 Ubuntu 24.04의 CPython 3.12에서 전체 회귀 시험을 돌립니다. Linux checkout에서는
다음과 같이 설치합니다.

```bash
git clone https://github.com/fieldalgo/openphysics.git
cd openphysics
python -m venv .venv
source .venv/bin/activate
python -m pip install -e packages/galerkin -e packages/galerkin-refsol -e packages/meshine -e packages/gmshio -e "packages/physmat[rii]" -e "packages/simcase[studio,test]"
```

명령은 저장소 루트에서 실행하세요. `packages/` 내부에서 Python을 실행하면
같은 이름의 디렉터리가 설치된 모듈을 가릴 수 있습니다.

Gmsh는 선택 도구로 별도 설치합니다. 메시 생성에는 PATH의 `gmsh` 또는
`GMSH_EXECUTABLE`이 필요하지만, 기존 MSH 파일을 읽는 데에는 필요하지 않습니다.
내장 광학 재료는 전체 refractiveindex.info 데이터베이스를 내려받지 않아도 동작합니다.
고정된 의존성·데이터베이스 버전은 [개발 안내](development.md)를 따르세요.

## 예제 실행

제공하는 슬래브 도파로 문서를 검사하고 실행합니다.

```bash
python -m simcase validate packages/simcase/examples/slab_te_check.json
python -m simcase run packages/simcase/examples/slab_te_check.json -o slab_results
```

Studio에서 2D 광학 모델과 직사각형 열전도 문서를 살펴볼 수 있습니다.

```bash
python -m simcase.studio --no-browser
```

`http://127.0.0.1:8765`에 접속하세요. Studio는 로컬 도구이며 인증된 다중 사용자
서비스가 아닙니다. 신뢰할 수 없는 네트워크에 노출하지 마세요. CLI 진입점은
`simcase`, `simcase-run`, `simcase-studio`이고 문서 형식의 버전 필드는
기존 `"openphysics": "0.2"`를 유지합니다.

헤드리스 열전도 문서나 독립 Python 예제를 실행할 수도 있습니다.

```bash
python -m simcase run packages/simcase/examples/thermal_slab.json -o thermal_results
python packages/galerkin/examples/thermal_steady2d.py
python packages/galerkin/examples/elasticity_traction.py
python packages/galerkin/examples/thermoelastic_traction.py
```

다른 문서는 [`packages/simcase/examples`](../../../../packages/simcase/examples),
다른 스크립트는 [`packages/galerkin/examples`](../../../../packages/galerkin/examples)에 있습니다.

저장하는 실행마다 새 출력 디렉터리를 사용하고 저장·정리가 끝날 때까지 독점적으로
관리하세요. 적대적 파일시스템 경쟁과 원자적 rollback은 수용 범위 밖입니다.
단위는 각 계약을 따릅니다. 열전도 API는 Kelvin, 깊이당 열량은 W/m,
깊이당 기계 하중은 N/m, 깊이당 물리 탄성에너지는 J/m입니다.

## 검증과 플랫폼 지원

물리 기능은 독립 해석해, 보존 관계, 음성 대조와 메시 수렴 시험으로 확인합니다.
기능별 기준과 한계는 [문서 색인](index.md)에 연결된 각 계약·검증 문서에 있습니다.
저장소 루트에서 전체 소스 시험을 실행하세요.

```bash
python -m pytest -q
```

| 범위 | 플랫폼 | 확인하는 것 |
|---|---|---|
| 전체 소스 회귀 | Linux, Python 3.12 | 전체 소스 시험, Studio JavaScript 검사, 일곱 배포의 build·설치, 강제한 두 BLAS kernel에서 수치에 민감한 시험 |
| 설치 패키지 수용 | Linux·macOS·Windows, Python 3.12 | 여섯 구현 sdist를 wheel로 만들어 새 환경에서 시험: 패키지 바이트, 포함 자산, 공개 API·CLI·저장 동작, 열 저장/I-O 견고성 |

설치 수용 검사는 macOS나 Windows 전체 회귀 시험이 아닙니다. 패키지 metadata는
Python 3.10 이상을 허용하지만 CI는 Python 3.12만 시험합니다. `OS Independent` 분류와
`py3-none-any` wheel은 metadata이며 검증된 플랫폼 목록이 아닙니다. 커밋별 결과는
GitHub Actions의 필수 검사 `tests`에서 확인하세요. 검사와 명령은
[개발 안내](development.md)에 있습니다.

## 문서

| 문서 | 내용 |
|---|---|
| [문서 색인](index.md) | 모든 기능 계약과 검증 보고, 영어·한국어 |
| [구조도](architecture.md) | 패키지 관계와 진입점 |
| [개발 안내](development.md) | 개발 환경, 저장소 구성, 검사, CI와 결과 |
| [자산 출처](assets.md) | 포함된 그림, fixture와 데이터의 출처 |

## 기여와 보안

변경, 버그 보고와 질문은 [기여 안내](contributing.md), 비공개 취약점 신고는
[보안 안내](security.md)를 따르세요. 기본 브랜치 `main`에는 검토한 변경을 반영하며,
기능 브랜치에는 검증하지 않은 작업이 있을 수 있습니다.

## 라이선스

자체 코드와 문서는 **[Apache-2.0](../../../../LICENSE)**입니다.
[NOTICE](../../../../NOTICE)와 각 패키지 고지에 제3자 조건을 보존합니다. 포함된
refractiveindex.info 광학 데이터는 CC0 1.0이고 Gmsh는 자체 라이선스로 별도 설치합니다.
이 저장소의 라이선스가 의존성의 라이선스를 대체하지 않습니다.

모든 의존성, 외부 프로그램, 데이터, 출판 자료의 라이선스와 쓰는 방식은
[제3자 소프트웨어](third-party.md)에 있습니다.
