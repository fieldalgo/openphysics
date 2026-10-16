# OpenPhysics

[English](../../../overview.md) | **한국어**

OpenPhysics는 전자기장, 열전도와 고체역학을 위한 Python 시뮬레이션 도구 모음입니다.
유한요소 해석기, 메시 생성, 재료 모델과 독립 해석해를 한 저장소에서 제공합니다.
Python API를 직접 호출하거나, 지원하는 모델을 JSON으로 실행하거나,
로컬 브라우저 Studio에서 2D 광학 모델을 살펴볼 수 있습니다.

현재 개발 중인 프로젝트입니다. 기능마다 입력·출력 계약과 실제 검증 범위를 명시하며,
이름이 범용 다중물리 완전 연성 해석기의 지원을 뜻하지는 않습니다.

## 해석할 수 있는 문제

| 분야 | 구현 범위 | 안내 |
|---|---|---|
| 전자기 | 2D 스칼라·전체 벡터 도파 모드, 복소 장과 모드 추적을 유지하는 분리 가능한 모드의 파장 sweep | [모델 실행기](../../../../packages/simcase/docs/locales/ko/pages/overview.md), [벡터 신뢰성](../../../../packages/galerkin/docs/locales/ko/pages/eigenspace_reliability.md) |
| 3D 공동 | Python API 또는 단일 JSON study를 통한 진공 직육면체 PEC 공동 고유모드 | [공동 API](../../../../packages/galerkin/docs/locales/ko/pages/cavity_solver.md), [JSON 계약](../../../../packages/simcase/docs/locales/ko/pages/cavity3d.md) |
| 열전도 | 정상·상수·등방 2D 열전도, Dirichlet·처방 열유속·Robin 경계, 변별 상수 경계 데이터를 받는 직사각형 헤드리스 JSON 경로 | [열전도 API](../../../../packages/galerkin/docs/locales/ko/pages/thermal_steady2d.md), [열유속·Robin](../../../../packages/galerkin/docs/locales/ko/pages/thermal_flux_robin.md), [열전도 JSON](../../../../packages/simcase/docs/locales/ko/pages/thermal_steady2d.md), [경계조건 JSON](../../../../packages/simcase/docs/locales/ko/pages/thermal_steady_boundary2d.md) |
| 과도 열전도 | 2D Python 엔진과 직사각형 headless JSON/API/CLI/save, 고정 P1·일관 질량·후진 Euler, 상수 등방 물성·명시 시간·표본 Dirichlet/단열 | [과도 열전도](../../../../packages/galerkin/docs/locales/ko/pages/transient_heat.md), [검증](../../../../packages/galerkin/docs/locales/ko/pages/transient_heat_validation.md) |
| 고체역학 | 정적 2D 선형탄성, 평면응력·평면변형률, 전역 Cartesian 경계 표면하중 | [탄성](../../../../packages/galerkin/docs/locales/ko/pages/elasticity2d.md), [표면하중](../../../../packages/galerkin/docs/locales/ko/pages/elasticity_traction.md) |
| 열팽창 | 처방 절점 온도장의 기계해석, 선택적 전체 표면하중, 명시적인 동일 메시 정상 열전도→기계 workflow | [처방 온도](../../../../packages/galerkin/docs/locales/ko/pages/prescribed_temperature_thermoelasticity.md), [전체 표면하중](../../../../packages/galerkin/docs/locales/ko/pages/thermoelastic_traction.md), [workflow](../../../../packages/galerkin/docs/locales/ko/pages/thermal_mechanical_workflow.md) |

JSON 실행기는 무손실 `em.modes2d`, `em.cavity3d`와 문서에 명시한
`thermal.steady2d`와 직사각형 `thermal.transient2d` 범위를 지원합니다. Python 전용 기능이 JSON이나 Studio에도
자동으로 제공되는 것은 아닙니다. Studio는 2D 광학 모델을 지원하고 3D 모델을
거절하며, 열전도 폼·그래프는 없습니다. 과도 열전도는 저장 이력을 갖는 직사각형 headless 문서 경로도 제공하지만,
열 Studio·restart·과도 flux/Robin 입력·자동 연성은 제공하지 않습니다. 비선형 역학, 형상 sweep,
손실 모드 문서 해석과 열역학적 완전 피드백 연성은 현재 통합 범위에 포함하지 않습니다.
정상 열전도→기계 workflow는 별도 Robin·열유속·표면하중 확장을 아직 받지 않습니다.

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
프로젝트 이름을 예약합니다. 엔진을 포함하지 않고 위 패키지들을 설치하지도 않습니다.
저장소 루트 자체도 설치 가능한 배포가 아닙니다.
**아래 소스 설치 방법을 사용하세요. `pip install openphysics`만으로는 시뮬레이션
도구 모음이 설치되지 않습니다.** 저장소 공개와 새로운 PyPI 버전 배포는 별개입니다.

## 소스에서 설치

전체 회귀시험을 실측한 환경은 Ubuntu 24.04의 CPython 3.12.14입니다.
Linux checkout에서는 다음과 같이 설치합니다.

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
재현 가능한 의존성·데이터베이스 버전은 [검증 환경 안내](../../../../ci/docs/locales/ko/pages/README.md)를 따르세요.

## 예제 실행

제공하는 슬래브 도파로 문서를 검사하고 실행합니다.

```bash
python -m simcase validate packages/simcase/examples/slab_te_check.json
python -m simcase run packages/simcase/examples/slab_te_check.json -o slab_results
```

Studio에서 2D 광학 모델을 살펴볼 수 있습니다.

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

저장하는 실행마다 새 출력 디렉터리를 사용하고 저장·정리가 끝날 때까지 독점적으로
관리하세요. 적대적 파일시스템 경쟁과 원자적 rollback은 수용 범위 밖입니다.
단위는 각 계약을 따릅니다. 열전도 API는 Kelvin, 깊이당 열량은 W/m,
깊이당 기계 하중은 N/m, 깊이당 물리 탄성에너지는 J/m입니다.

## 검증과 현재 한계

물리 기능은 독립 해석해, 보존 관계, 음성 대조와 메시 수렴 시험으로 확인합니다.
저장소 루트에서 검사를 실행하세요.

```bash
python -m pytest -q
python -m pytest -q -m "not slow"
python -m pytest -q packages/simcase/tests
```

기록된 Linux snapshot `0bc4419`에서 **source 시험 1,536개와 하위검사 9개가 통과**했고,
**선택 기능 16개를 skip**했습니다. Skip은 Gmsh 부재 14개와 로컬 데이터베이스 부재
2개입니다. 별도의 설치 wheel 실행은 **541개 시험이 skip 없이 통과**했습니다.
일곱 sdist→wheel build와 배포물 14개의 엄격한 metadata 검사도 통과했습니다.
정확한 snapshot과 범위는 [검증 색인](index.md)을 참고하세요.
과거 수치가 이후의 모든 문서 커밋에서 전체 시험을 다시 실행했다는 뜻은 아니며,
일부 시험 통과가 skip한 통합 기능을 검증하지는 않습니다.

패키지 metadata는 Python 3.10 이상을 허용하지만 고정한 Linux 검증 의존성은
Python 3.12용이므로 3.10·3.11에서 그대로 사용할 수 없습니다. 다른 환경은 실측한
전체 회귀시험 범위 밖입니다. Windows 2022 / Python 3.12.10의 좁은 저장 I/O
검증은 `636a23a`에서 설치 API·CLI·저장 36개와 source 기존 대상 보호 3개가
통과했습니다([실행](https://github.com/fieldalgo/openphysics/actions/runs/38858254797)).
과거 교체 실패 두 개를 회복한 범위이며 Windows 전체 회귀·다른 파일시스템·macOS
지원을 입증하지 않습니다. `OS Independent` 분류와 `py3-none-any` wheel은 metadata이며
검증된 플랫폼 목록이 아닙니다. GitHub Actions는 활성화돼 있습니다. 과거 클라우드 결과는 원래 snapshot의 근거이며 새 커밋은 정확한 workflow 결과를 확인해야 합니다.

## 문서와 기여

[문서 색인](index.md)에서 시작하세요. 사용법·검증 안내는
완전한 한국어판을 함께 제공합니다. [자산 출처](assets.md)에는
과거 그림, fixture와 데이터의 출처를 기록했습니다.

기본 브랜치 `main`에는 검토한 통합 변경을 반영합니다. 기능 브랜치에는 검증하지
않은 작업이 있을 수 있습니다. 변경과 재현 가능한 버그 보고는
[기여 안내](contributing.md), 비공개 취약점 신고는 [보안 안내](security.md)를
따르세요. 이 checkout을 사용하는 데 별도의 비공개 저장소는 필요하지 않습니다.

## 라이선스

자체 코드와 문서는 웨이브빗과 같은 **[Apache-2.0](../../../../LICENSE)**입니다.
[NOTICE](../../../../NOTICE)와 각 패키지 고지에 제3자 조건을 보존합니다. 포함된
refractiveindex.info 광학 데이터는 CC0 1.0이고 Gmsh는 자체 라이선스로 별도 설치합니다.
이 저장소의 라이선스가 의존성의 라이선스를 대체하지 않습니다.

과도 headless 입력·초기 일치·시간축·저장 소유권은 [문서 계약](../../../../packages/simcase/docs/locales/ko/pages/thermal_transient2d.md)을 따릅니다. 현재 구현과 정확한 결합 CI 수용은 구분하며 예전 엔진/정상 저장 실측을 새 공개 API 통과로 합산하지 않습니다.
