# OpenPhysics

[English](README.md) | **한국어**

하나의 저장소에 여섯 구현 패키지를 모은 시뮬레이션 도구다. 패키지마다 배포 이름, 버전, 의존성을 별도로 관리한다. [한국어 문서 색인](docs/locales/ko/pages/index.md)에서 사용법·검증 문서의 언어별 경로와 번역 상태를 확인할 수 있다.

| 패키지 | 현재 역할 |
|---|---|
| [galerkin](packages/galerkin/README.ko.md) | 2D 전자기 FEM, 벡터 도파로 모드, 정상 열전도, 정적 2D 탄성, 3D PEC 직육면체 공동 해석 |
| [galerkin-refsol](packages/galerkin-refsol/README.ko.md) | 독립 해석해와 발표된 벤치마크. Python에서는 `refsol`로 import |
| [meshine](packages/meshine/README.ko.md) | 재료 영역을 위한 2D 삼각형 메시 생성 |
| [gmshio](packages/gmshio/README.ko.md) | 외부 Gmsh 실행, MSH 4.1 ASCII 읽기, FEM 메시 어댑터 |
| [physmat](packages/physmat/README.ko.md) | 광학 분산·재료 데이터와 Drude–Lorentz 피팅 |
| [simcase](packages/simcase/README.ko.md) | JSON 모델 문서, 화면 없는 실행기, 선택 설치하는 브라우저 Studio |

일곱 번째 배포인 [openphysics](packages/openphysics/README.ko.md)는 이름 예약용 `0.0.1`이다. 해석 엔진을 포함하지 않으며 전체 도구를 설치하지도 않는다. 저장소 루트 자체는 설치할 수 있는 배포 패키지가 아니다. 일곱 패키지의 완전한 한국어 README를 제공한다. 개별 사용·검증 안내의 번역 상태는 문서 색인에서 구분한다.

## 이 checkout에서 설치하기

패키지 메타데이터는 Python 3.10 이상을 허용한다. 전체 자동 회귀 범위는 Ubuntu 24.04의 CPython 3.12.14다. 별도 Windows 2022 / Python 3.12.10 gate는 설치된 헤드리스 열전도 API/CLI와 선택한 저장 I/O만 다룬다. Windows 전체 회귀나 Gmsh 검증이 아니며 다른 환경은 이 실측 범위에 포함되지 않는다. Windows 저장·정리 수용검증은 미완료이며 좁은 GitHub runner 검증은 중단 상태다. Linux 결과가 Windows 지원을 입증하지 않는다. `OS Independent` 분류와 `py3-none-any` wheel은 패키지 메타데이터이며 시험한 플랫폼 목록을 뜻하지 않는다. [CI 안내](ci/README.md)의 고정 검증 환경은 Linux/Python 3.12용으로, 그 의존성 버전을 Python 3.10/3.11에 그대로 재사용할 수 없다.

가상환경을 만들고 저장소 루트에서 실행한다.

```bash
python -m pip install -e packages/galerkin -e packages/galerkin-refsol -e packages/meshine -e packages/gmshio -e "packages/physmat[rii]" -e "packages/simcase[studio,test]"
```

로컬 구현과 해당 의존성을 함께 설치한다. Gmsh는 선택적인 외부 실행 파일이다. 메시 생성 시험에는 PATH의 `gmsh` 또는 실행 파일을 가리키는 `GMSH_EXECUTABLE`이 필요하지만, 기존 MSH 파일을 읽을 때는 필요 없다. refractiveindex.info 전체 데이터베이스도 선택 사항이다. 기본 내장 재료와 작은 fixture를 사용하는 읽기 시험은 다운로드 없이 동작한다.

## 모델 실행하기

설치 후 저장소 루트에서 실행한다.

```bash
python -m simcase validate packages/simcase/examples/slab_te_check.json
python -m simcase run packages/simcase/examples/slab_te_check.json -o slab_results
python -m simcase.studio --no-browser
```

Studio 주소는 `http://127.0.0.1:8765`다. CLI 명령은 `simcase`, `simcase-run`, `simcase-studio`이고 Python import 이름은 `simcase`다. JSON 형식의 버전 필드는 계속 `"openphysics": "0.2"`를 사용한다.

2D 문서 실행기는 손실 없는 `em.modes2d` 문제 하나를 PEC/PMC 경계에서 푼다. 스칼라 해석은 물리 매개변수 sweep을 지원한다. 전체 벡터 해석은 단일 해석과 분리된 모드의 파장 sweep, 명시적 외부 도파 기준, 복소 장 저장과 Studio 성분 표시를 지원한다. Sweep은 전기장 overlap으로 모드 가지를 추적한다. group index를 내기 전에 모드 누락, 모호한 대응, 근접 축퇴 대응을 거절한다. `vector_slab`, `vector_fiber`, `vector_slab_sweep` 예제와 [추적 계약](packages/simcase/README.md#tracked-vector-wavelength-sweeps)을 참고한다.

같은 문서 실행기로 여섯 면이 PEC인 진공 직육면체를 단일 `em.cavity3d` 해석할 수 있다.

```bash
python -m simcase validate packages/simcase/examples/cavity_box.json
python -m simcase run packages/simcase/examples/cavity_box.json -o cavity_results
```

공동 해석마다 새 출력 디렉터리를 사용한다. JSON/NPZ 결과에는 Hz 주파수, SI 메시 좌표, 질량 정규화된 에지 계수와 요소 중심 장이 들어간다. 필수 주파수 target은 그 주변의 유한 후보 집합을 선택한다. 전체 최저 스펙트럼이나 모든 축퇴 짝을 찾았다고 보증하지 않는다. Studio는 2D 모델만 지원하며 3D 메시·실행 요청을 명시적으로 거절한다. [공동 문서 계약](packages/simcase/docs/locales/ko/pages/cavity3d.md)과 재사용 가능한 [Python 공동 API](packages/galerkin/docs/cavity_solver.md)를 참고한다.

문서 실행기에는 다중물리 연성, 형상 sweep, 손실 모드 해석을 구현하지 않았다.

## 독립 열전도·탄성 API와 벡터 장

상수 등방 재료의 정상 2D 열전도는 `galerkin.thermal`과 독립 해석해 `refsol.thermal`을 사용한다. [Kelvin·열유속 계약](packages/galerkin/docs/thermal_steady2d.md)을 참고한다. 정적 탄성은 [전역 Cartesian 경계 표면하중](packages/galerkin/docs/elasticity_traction.md)을 지원하며 [독립 표면하중 검증](packages/galerkin/docs/elasticity_traction_independent_validation.md)이 있다. 설치 후 루트에서 예제를 실행한다.

```bash
python packages/galerkin/examples/thermal_steady2d.py
python packages/galerkin/examples/elasticity_traction.py
```

영어 출력의 두 예제는 galerkin sdist에도 포함된다. 열 하중·반력은 면 밖 두께당 W/m, 기계 하중·반력은 두께당 N/m이다. 이 두 API 자체에는 비정상 열전도, 열팽창, 연성 모델을 추가하지 않았다.

별도의 [처방 온도장 기계단계](packages/galerkin/docs/prescribed_temperature_thermoelasticity.md)는 `galerkin.thermoelasticity`, `refsol.thermoelasticity`와 명시적으로 제공한 같은 메시의 불변 nodal-P1 Kelvin 온도장을 사용한다. 설치 후 [실행 예제](packages/galerkin/examples/prescribed_temperature_thermoelasticity.py)를 실행할 수 있다. 평면변형률의 면 밖 기여를 포함해 실제 3D 탄성에너지를 두께당 J/m으로 보고한다. 이 단계는 열전도를 풀거나 열 결과를 자동 연결하지 않는다. 온도장의 출처를 인증하지 않으며 simcase/Studio 지원도 추가하지 않는다.

독립 정적 2D 탄성은 `galerkin.elasticity`와 `refsol.elasticity` submodule을 사용한다. [탄성 계약](packages/galerkin/docs/elasticity2d.md)은 평면응력·평면변형률, SI 단위, 구속, 거의 비압축성인 경우의 한계를 설명한다. 설치 후 루트에서 실행한다.

```bash
python packages/galerkin/examples/elasticity2d.py
```

계약과 [영어 출력 예제](packages/galerkin/examples/elasticity2d.py)는 galerkin sdist에도 포함된다. 이 API에는 simcase/Studio나 열 연성 연결이 없다. [벡터 고유공간 설명](packages/galerkin/docs/eigenspace_reliability.md)은 복소 장 보존과 축퇴 기저 신뢰성의 한계를 설명한다.

## 헤드리스 정상 열전도 문서

별도 [thermal.steady2d 계약](packages/simcase/docs/locales/ko/pages/thermal_steady2d.md)은 명시적 길이 단위·절대 Kelvin·SI 계수를 갖는 직사각형 정상 열전도를 설명한다. [슬랩](packages/simcase/examples/thermal_slab.json)과 [혼합 열원](packages/simcase/examples/thermal_mixed.json) JSON 예제를 제공한다. 열 Studio UI·그림·Robin 경계·자동 열탄성 연성을 추가하지 않는다. 새 출력 경로 소유권과 불완전 출력 판별·플랫폼 한계는 계약을 참고한다. Windows2022/Python3.12.10의 별도 gate는 설치된 헤드리스 API/CLI와 선택된 저장 I/O만 검사한다. Windows 전체 회귀나 Gmsh 지원으로 해석하지 않는다.

## Checkout 검증하기

재현 가능한 Linux 검증, 고정 광학 데이터, 설치한 wheel/sdist 산출물 검사는 [CI 안내](ci/README.md)에 설명한다.

```bash
python -m pytest -q
python -m pytest -q -m "not slow"
python -m pytest -q packages/simcase/tests
```

루트의 `conftest.py`는 worktree에서도 현재 checkout의 패키지를 import한다. Python은 저장소 루트에서 실행한다. `packages/` 내부에서 실행하면 같은 이름의 디렉터리가 설치된 모듈을 가릴 수 있다.

시험은 해석해, 메시 위상·스케일, FEM 수렴, 재료 모델, 문서 실행과 Studio HTTP API를 포함한다. 선택 도구나 데이터가 없으면 일부 통합 시험은 skip한다. 부분 시험 통과만으로 그 통합을 실제 시험했다고 볼 수 없다. 브라우저 상호작용과 패키지 릴리스 절차는 별도로 확인한다.

패키지 README의 과거 수치 측정은 원래 명시한 날짜의 기록이다. 이 한국어판을 추가했다는 사실이 새로운 시험 실행이나 새로운 수치 합격을 뜻하지 않는다.

저장과 정리가 끝날 때까지 호출자가 출력 경로를 독점해야 합니다. 정리 전에 관측한
교체에 대한 보호는 시험하지만, 소유권 검사와 unlink 사이의 외부 교체는 안전을
보장하지 않습니다. 적대적 파일시스템 경쟁과 원자적 rollback은 수용 범위 밖입니다.
이 구간에는 다른 writer가 출력을 변경하면 안 됩니다. Windows 저장 검증은 두 실패의
원인이 미확정인 상태로 중단됐으며 Linux 결과로 Windows 수용을 대신하지 않습니다.
GitHub Actions는 비활성화돼 있으며 dispatch와 재실행을 하지 않습니다.

이 checkout에는 독립 API의 외향 열유속·Robin 열 경계가 포함됩니다. [계약](packages/galerkin/docs/locales/ko/pages/thermal_flux_robin.md)과 [독립 수용검증](packages/galerkin/docs/locales/ko/pages/thermal_flux_robin_independent_validation.md)을 참고하세요. 헤드리스 JSON은 이 경계를 받지 않습니다. 계약과 검증 보고는 구현 범위와 실측 범위를 구분합니다.

명시적 Python 전용 [정상 열전도→기계 workflow](packages/galerkin/docs/locales/ko/pages/thermal_mechanical_workflow.md)는 같은 메시 열전도와 처방 온도 기계단계를 불변 nodal-P1 Kelvin 복사로 연결합니다. [독립 보고](packages/galerkin/docs/locales/ko/pages/thermal_mechanical_independent_validation.md)는 실측 수용과 구현 범위를 구분합니다. JSON/CLI/Studio 연결·저장·Robin/flux/traction workflow·과도 피드백·열역학적 완전 연성을 추가하지 않습니다.

standalone [과도 열전도 Python API](packages/galerkin/docs/locales/ko/pages/transient_heat.md)는 고정 P1 삼각형·일관 질량·후진 Euler를 사용합니다. [생산 검증 계약](packages/galerkin/docs/locales/ko/pages/transient_heat_validation.md)과 [독립 보고](packages/galerkin/docs/locales/ko/pages/transient_heat_independent_validation.md)는 작성된 gate와 실측 근거를 구분합니다. 배포 검사는 전체 archive 수렴 예제와 독립 `--suite all`을 소비하도록 설정하며 설정은 실행 결과가 아닙니다. 과도 JSON/CLI/Studio, Robin/flux 입력, 저장 또는 자동 열→기계 연결은 추가하지 않습니다.
