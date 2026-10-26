# OpenPhysics

[English](../../../overview.md) | **한국어**

OpenPhysics는 전자기장, 열전도와 고체역학을 위한 Python 시뮬레이션 도구 모음입니다.
유한요소 해석기, 메시 생성, 재료 모델과 독립 해석해를 한 저장소에서 제공합니다.
Python API를 직접 호출하거나, 지원하는 모델을 JSON으로 실행하거나,
로컬 브라우저 Studio에서 2D 광학 모델과 직사각형 열전도 문서를 살펴볼 수 있습니다.

현재 개발 중인 프로젝트입니다. 기능마다 입력·출력 계약과 검증 범위를 명시하며,
이름이 범용 다중물리 완전 연성 해석기의 지원을 뜻하지는 않습니다.

## 여기서 시작: 내 도파관 해석하기

[도파관 튜토리얼](packages/simcase/waveguide_tutorial.md)
([English](../../../packages/simcase/waveguide_tutorial.md))은 제공 예제의
실리콘 strip에서 시작해 내 strip·rib·다각형 단면까지 갑니다. 유효 굴절률, 모드장,
군굴절률을 얻고, 그 값을 믿어도 되는지 알려 주는 창·메시·slab 모드 점검을 함께
익힙니다.

## 해석할 수 있는 문제

| 분야 | 구현 범위 | 안내 |
|---|---|---|
| 전자기 | 2D 스칼라·전체 벡터 도파 모드, 복소 장과 모드 추적을 유지하는 분리 가능한 모드의 파장 sweep | [모델 실행기](packages/simcase/overview.md), [벡터 신뢰성](packages/galerkin/eigenspace_reliability.md) |
| 정전기와 산란 | Python API를 통한 2D 정전 퍼텐셜과 주파수 영역 Helmholtz 산란, 1차 흡수 경계 또는 원통 PML | [galerkin](packages/galerkin/overview.md), [마일스톤 검증](packages/galerkin/milestone_validation.md) |
| 3D 공동 | Python API 또는 단일 JSON study를 통한 직육면체 공동 고유모드: 진공 PEC, 또는 손실 직육면체 재료와 도체 벽(복소 주파수와 Q) | [공동 API](packages/galerkin/cavity_solver.md), [재료 공동](packages/galerkin/material_cavity.md), [JSON 계약](packages/simcase/cavity3d.md) |
| 열전도 | 정상·등방 2D 열전도, Dirichlet·처방 열유속·Robin 경계, 변별 상수 경계 데이터를 받는 직사각형 헤드리스 JSON 경로와 전용 Studio 화면 | [열전도 API](packages/galerkin/thermal_steady2d.md), [열유속·Robin](packages/galerkin/thermal_flux_robin.md), [열전도 JSON](packages/simcase/thermal_steady2d.md), [경계조건 JSON](packages/simcase/thermal_steady_boundary2d.md), [Studio](packages/simcase/thermal_studio.md) |
| 과도 열전도 | 2D Python 엔진과 직사각형 headless JSON/API/CLI/save, 고정 P1·일관 질량·후진 Euler, 상수 등방 물성·명시 시간·표본 Dirichlet/단열, 전용 Studio 시간·장·이력 화면 | [과도 열전도](packages/galerkin/transient_heat.md), [문서](packages/simcase/thermal_transient2d.md), [검증](packages/galerkin/transient_heat_validation.md), [Studio](packages/simcase/thermal_transient_studio.md) |
| 재료 영역 | Python에서 정상·과도 열전도, 탄성, 열팽창, 두 열전도→기계 workflow에 쓰는 2D 메시 이름 영역별 상수·등방 재료, 배경 위에 도형을 놓는 정상·과도 열전도 JSON 문서 | [영역 재료](packages/galerkin/multimaterial.md), [영역 문서](packages/simcase/thermal_regions2d.md) |
| 고체역학 | 정적 2D 선형탄성, 평면응력·평면변형률, 전역 Cartesian 경계 표면하중 | [탄성](packages/galerkin/elasticity2d.md), [표면하중](packages/galerkin/elasticity_traction.md) |
| 열팽창 | 처방 절점 온도장의 기계해석, 선택적 전체 표면하중, 명시적인 동일 메시 정상 열전도→기계 workflow | [처방 온도](packages/galerkin/prescribed_temperature_thermoelasticity.md), [전체 표면하중](packages/galerkin/thermoelastic_traction.md), [workflow](packages/galerkin/thermal_mechanical_workflow.md) |
| Joule heating | 온도독립 또는 온도의존 전기전도도, 요소별 발열 전달과 열 에너지 수지를 검증하는 같은 메시의 명시적 정상 전기→열 Python workflow | [Joule workflow](packages/galerkin/joule_heating.md) |
| 과도 열응력 | 같은 고정 메시에서 저장된 과도 열전도 시간 중 고른 시간마다 준정적 선형 미소변형 기계해석, 명시적인 두 번째 Python 호출 | [과도 열전도→기계](packages/galerkin/transient_thermal_mechanical.md) |

### 기능별 사용 경로

| 기능 | Python API | JSON / CLI | Studio |
|---|---|---|---|
| 2D 도파 모드와 sweep | 지원 | `em.modes2d`(수동 흡수 지원) | 지원 |
| 2D 정전기와 산란 | 지원 | 미지원 | 미지원 |
| 3D 공동: 진공 PEC, 손실 재료와 도체 벽 | 지원 | `em.cavity3d` | 미지원 |
| 정상 전기전도 | 지원 | 균질 직사각형 | 미지원 |
| 정상 열전도 | 지원 | 직사각형 `thermal.steady2d` | 전용 화면 |
| 과도 열전도 | 지원 | 직사각형 `thermal.transient2d` | 전용 화면 |
| 재료 영역이 있는 열전도 | 지원 | 도형이 있는 `thermal.steady2d`, `thermal.transient2d` | 미지원 |
| 탄성·열팽창·열전도→기계 | 지원 | 미지원 | 미지원 |
| 정상 Joule heating | 지원 | 균질 직사각형·상수/σ(T) | 미지원 |

Python 전용 기능이 JSON이나 Studio에도 자동으로 제공되는 것은 아닙니다.

선택 extra `simcase[export]`를 설치하면 저장된 결과를 ParaView용 VTU 파일로 쓸 수 있습니다.
대상은 Dirichlet·단열 변만 쓰는 직사각형 정상 열전도, 직사각형 과도 열전도,
재료 영역이 있는 정상·과도 열전도, 진공 PEC 공동입니다. 과도 열전도는 한 시각 또는
저장된 모든 시각을 `.pvd` 시계열로 내보냅니다.
[ParaView로 보기](packages/simcase/overview.md#paraview로-보기)를 참고하세요.

### 현재 한계

- 열전도→기계 연성은 단방향입니다. 열로 되먹임이 없는 명시적인 두 번째 Python 호출이며,
  열역학적 완전 피드백 연성은 지원하지 않습니다.
- 과도 열전도는 restart·과도 flux/Robin 입력·자동 연성을 제공하지 않습니다.
- 정상 열전도→기계 workflow는 별도 Robin·열유속·표면하중 확장을 아직 받지 않습니다.
- 기계해석(탄성, 열팽창, 열전도→기계)과 2D 정전기·산란은 Python 전용입니다.
- 2D 열전도와 기계해석은 단위 깊이당 평면 모델입니다. JSON 열전도 문서는 계산 영역(domain)의
  바깥 네 변에만 경계조건을 줍니다.
- `em.modes2d`는 수동 흡수를 지원하며 PML·누설·굽힘은 제외합니다. 비선형 역학과 형상 sweep은
  지원하지 않습니다.
- Studio는 3D 모델과 재료 영역이 있는 열전도 문서를 거절하며 기계해석 폼이 없습니다.
- VTU 내보내기는 열유속·대류 변이 있는 직사각형 정상 문서(`boundary-v2`), 손실 공동,
  도파 모드를 거절합니다. 정상 영역 문서의 flux/Robin 하중 배열은 내보냅니다.

## 패키지 구성

모든 구현 소스와 문서를 이 저장소에서 제공합니다. 패키지별로 배포 이름, 버전,
의존성과 라이선스 고지를 관리합니다.

| 패키지 | 역할 |
|---|---|
| [galerkin](packages/galerkin/overview.md) | 유한요소 해석기와 장 후처리 |
| [galerkin-refsol](packages/galerkin-refsol/overview.md) | 독립 해석해와 출판된 benchmark. Python에서는 `refsol`로 import |
| [meshine](packages/meshine/overview.md) | 재료 영역의 2D 삼각형 메시 |
| [gmshio](packages/gmshio/overview.md) | 선택적 Gmsh 실행파일 연동, MSH reader와 메시 adapter |
| [physmat](packages/physmat/overview.md) | 재료 물성, 광학 분산과 Drude–Lorentz fitting |
| [simcase](packages/simcase/overview.md) | JSON 문서, 헤드리스 실행기와 선택적 로컬 Studio |

일곱 번째 배포인 [openphysics](packages/openphysics/overview.md)(`0.0.1`)는
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
python -m simcase validate examples/simcase/slab_te_check.json
python -m simcase run examples/simcase/slab_te_check.json -o slab_results
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
python -m simcase run examples/simcase/thermal_slab.json -o thermal_results
python examples/galerkin/thermal_steady2d.py
python examples/galerkin/elasticity_traction.py
python examples/galerkin/thermoelastic_traction.py
```

다른 문서는 [`examples/simcase`](../../../../examples/simcase),
다른 스크립트는 [`examples/galerkin`](../../../../examples/galerkin)에 있습니다.

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
| 설치 패키지 수용 | Linux·macOS·Windows, Python 3.12 | Linux: sdist에서 만든 일곱 wheel을 extra와 함께 checkout 밖에 설치하고 Python 시험 전체를 실행. 각 OS: 여섯 구현 sdist를 wheel로 만들어 새 환경에서 패키지 바이트, 포함 자산, 공개 API·CLI·저장 동작, 열 저장/I-O 견고성 시험 |

설치 수용 검사는 macOS나 Windows 전체 회귀 시험이 아닙니다. 패키지 metadata는
Python 3.12 이상을 요구하고 CI는 Python 3.12만 시험합니다. `OS Independent` 분류와
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

[2D 정상 전기전도 Python API](packages/galerkin/electric_steady2d.md)는 영역별 전기전도도, 전압·전류·절연 경계, Neumann 기준 전위, V/E/J와 요소별 Joule 발열을 지원합니다. 균질 직사각형의 [JSON/CLI](packages/simcase/electric_joule.md)를 지원하며 Studio는 제외합니다.

[온도 의존 양방향 Joule heating API](packages/galerkin/temperature_joule_heating.md)

전기전도·상수/온도 의존 Joule heating: [JSON/CLI 계약·예제](packages/simcase/electric_joule.md).
