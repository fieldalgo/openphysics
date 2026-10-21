# 개발과 검증

[English](../../../development.md) | **한국어**

개발 환경을 만들고, CI가 돌리는 검사를 직접 실행하고, CI 결과를 읽는 방법입니다.
브랜치·리뷰·릴리스 흐름은 [기여 안내](contributing.md)에 있습니다. 기능별 수용 기준과
근거는 각 기능의 계약·검증 문서에 있으며 [문서 색인](index.md)에서 찾을 수 있습니다.

## 환경

CI는 Ubuntu 24.04에서 Python 3.12.14와 Node.js 24.19.0을 고정해 사용합니다. 저장소
루트에서 Python 3.12 가상환경을 켠 상태로:

```bash
python -m pip install -r tools/requirements-py312-linux.txt
python -m pip install --no-deps --no-build-isolation \
  -e packages/galerkin -e packages/galerkin-refsol -e packages/meshine \
  -e packages/gmshio -e packages/physmat -e packages/simcase
python -m pip check
```

`tools/requirements-py312-linux.txt`는 검증 도구와 그 하위 의존성을 고정한 것이며,
패키지의 실행 의존성이 아닙니다. 고정 버전은 리뷰를 거친 변경에서 의도적으로 바꾸고,
소스 검사와 배포 검사를 다시 실행합니다. 패키지 메타데이터는 Python >=3.10을
선언하지만 Python 3.10·3.11은 CI에서 시험하지 않습니다.

항상 저장소 루트에서 실행합니다. `packages/`나 `tests/` 안에서 Python을 실행하면 같은 이름의
디렉터리가 설치된 모듈을 가릴 수 있습니다.

선택 도구와 데이터:

- **Gmsh**: 메시 생성에는 PATH의 `gmsh`가 필요합니다(Linux는 워크플로가 설치하는
  시스템 라이브러리도 필요). 별도 프로세스이며 배포물에 포함하지 않습니다.
- **refractiveindex.info 데이터베이스**: `tools/rii-revision.txt`가
  [polyanskiy/refractiveindex.info-database](https://github.com/polyanskiy/refractiveindex.info-database)의
  전체 커밋 ID를 고정합니다. `python tools/fetch_rii.py <dir>`는 정확히 그 커밋을 받고,
  수정됐거나 다른 커밋인 캐시는 거부합니다. `PHYSMAT_RII_PATH=<dir>/database`를
  설정합니다. 명시적으로 설정한 경로가 잘못되면 두 데이터베이스 시험은 건너뛰지 않고
  실패합니다. 데이터는 CC0 1.0이며 소스 트리 밖에 두고 배포하지 않습니다. 인용:
  M. N. Polyanskiy, *Refractiveindex.info database of optical constants*,
  Scientific Data **11**, 94 (2024), https://doi.org/10.1038/s41597-023-02898-2.
- **Chrome 또는 Chromium**: 설치 Studio 브라우저 검사는 이미 설치된 브라우저를
  사용합니다. 찾지 못하면 검사가 실패하며, 건너뛰지 않습니다.

## 저장소 구성

`packages/<name>/`에는 배포판 `<name>`이 싣는 것만 있습니다. `pyproject.toml`,
`setup.py`, `README.md`, `LICENSE`, `NOTICE`, 그리고 src 구성을 따르는 import 패키지
`packages/<name>/src/<import 이름>/`입니다. 시험·예제·패키지 문서·도구는 저장소 루트에
두므로, 이들이 쓰는 것은 배포물에 들어갈 수 없습니다.

| 패키지 | 코드 | 시험 | 예제 |
|---|---|---|---|
| `packages/galerkin` | `src/galerkin/` | `tests/galerkin/` | `examples/galerkin/` |
| `packages/galerkin-refsol` | `src/refsol/` | `tests/refsol/` | `examples/galerkin-refsol/` |
| `packages/meshine` | `src/meshine/` | `tests/meshine/` | `examples/meshine/` |
| `packages/gmshio` | `src/gmshio/` | `tests/gmshio/`. `.geo`/`.msh` fixture는 `tests/gmshio/data/` | `examples/gmshio/` |
| `packages/physmat` | `src/physmat/` | `tests/physmat/` | `examples/physmat/` |
| `packages/simcase` | `src/simcase/`. Studio 정적 파일은 `src/simcase/studio/static/` | `tests/simcase/`. Studio JavaScript 검사(`*.cjs`) 포함 | `examples/simcase/`(JSON 문서와 `docs/gallery/`를 그리는 `gallery.py`) |

패키지마다의 문서(계약과 검증 보고서)는 `docs/packages/<name>/`에, 한국어 문서는
`docs/locales/ko/pages/packages/<name>/`에 있습니다. `tools/`에는 저장소 검사, 고정한 검증
환경, 검토한 라이선스 목록, 관리용 스크립트가 있습니다. 예를 들어 `tools/build_physmat_tables.py`는
physmat의 내장 표를 다시 만듭니다. 그중 필수 CI가 무엇을 돌리는지는 [tools/README.md](../../../../tools/README.md)에
있습니다. [benchmarks/](../../../../benchmarks/README.md)에는 시간 측정 벤치마크가,
[studies/](../../../../studies/README.md)에는 진단 스크립트가 있습니다. 사람이 돌리며 필수 CI는 돌리지
않습니다. 빈 `openphysics` 이름 예약에는 코드·시험·예제가 없습니다. 루트에서 `python -m pytest`를
실행하면 루트 `pyproject.toml`의 `testpaths`에 따라 `tests/`와 도구의 시험인 `tools/tests/`를 모읍니다. `slow`
표시도 이 파일에서 선언합니다. 루트 `conftest.py`는 각 패키지의 `src/` 폴더를 import 경로
맨 앞에 두므로, 시험은 이 checkout의 코드를 사용합니다.

패키지 하나의 시험만 돌리려면 저장소 루트에서:

```bash
python -m pytest -q tests/galerkin                 # 패키지 하나
python -m pytest -q tests/galerkin -m "not slow"   # 수렴 연구 제외
python -m pytest -q tests/gmshio/test_msh.py       # 파일 하나
node --test tests/simcase/*.cjs                    # Studio JavaScript 검사
```

## 검사 실행

```bash
export MPLBACKEND=Agg OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python -m pytest -q -ra                    # 전체 소스 시험
node --test tests/simcase/*.cjs            # Studio JavaScript 검사
python tools/check_distributions.py        # 모든 패키지 빌드·검사·설치
python tools/run_installed_tests.py        # 설치된 wheel로 tests/의 Python 시험 전체 실행
python tools/check_licenses.py             # 설치된 라이선스를 검토 목록과 대조
python tools/check_markdown_links.py       # 모든 Markdown 파일의 상대 링크와 #앵커
```

빠르게 반복할 때는 바꾼 부분과 관련된 시험만 돌리고 전체 시험은 CI에 맡깁니다.
`slow` 표시 시험(메시 수렴 연구)은 전체 실행에 포함되며, 로컬에서는
`-m "not slow"`로 뺄 수 있습니다. 일부만 통과한 결과가 CI를 대신하지는 않습니다.

CI 스크립트의 출력 디렉터리는 새것이거나 비어 있어야 하므로, 이전 실행의 결과가
섞이지 않습니다. `--output`으로 다른 디렉터리를 주지 않으면 `check_distributions.py`는
`.validation/dist/`에, `run_installed_tests.py`는 `.validation/installed/`에 씁니다.

설치 패키지 검사는 깨끗한 Python 3.12 환경이면 어느 OS에서나 실행됩니다.

```bash
python -m pip install -r tools/requirements-py312-windows-thermal.txt
python -X utf8 tools/check_platform_install.py
```

requirements 파일 이름은 예전 이름이며 Windows 전용이라는 뜻이 아닙니다.

## CI가 돌리는 것

`Validate packages` 워크플로(`.github/workflows/validate.yml`)는 main push, Ready PR,
수동 실행에서 돕니다. 브랜치 push와 draft PR에서는 돌지 않습니다. 네 부분이 병렬로
실행됩니다.

| Job | 플랫폼 | 검사 내용 |
|---|---|---|
| `linux-py312` | Ubuntu 24.04 | Markdown 링크 검사와 빠른 사전 검사 묶음 뒤 고정 RII 데이터베이스로 전체 소스 시험; 배포물 일곱 개; Studio Node 검사; Studio 자원 관측 1회 |
| `installed-tests` | Ubuntu 24.04 | sdist에서 빌드한 wheel 일곱 개를 모든 extra와 함께 checkout 밖에 설치하고 `tests/`의 Python 시험 전체를 실행 |
| `blas-kernels` | Ubuntu 24.04, job 두 개 | 수치에 민감한 추적·고유공간·재료 공진기(복소 조밀·희소 고유값 풀이)·광섬유 기준·길이 단위 독립성 시험을 OpenBLAS 커널 두 개로 강제해 실행 |
| `installed-platforms` | Ubuntu 24.04, macOS 14, Windows 2022 | 패키지 여섯 개를 sdist에서 wheel로 빌드해 checkout 밖 새 환경에서 시험 |

필수 검사는 **`tests`** 하나입니다. 네 부분이 모두 성공해야 통과하며, 하나라도
실패·취소·건너뜀이면 실패합니다. 문서만 바꾼 변경도 이 검사가 필요합니다.

**Linux job.** 라이선스 검사 뒤 Markdown 링크 검사가 돕니다. 저장소에서 추적하는 Markdown 파일의 모든 상대
링크와 `#앵커`가 풀려야 합니다(외부 URL은 가져오지 않습니다). 사전 검사 묶음(정상 경계, 과도 문서, 정상·과도 Studio, 과도 열-역학)을
이어서 돌려서 계약이 깨지면 몇 분 안에 실패합니다. 그다음 전체 시험이 모든 것을 다시
돌립니다. 소스 시험이 실패해도 배포 검사와 Node 검사는 근거를 남기려고 계속 돌지만,
job은 실패로 남습니다. 보통 16~22분 걸립니다. 45분 제한은 멈춘 실행을 끊기 위한
것이며, 호스트 러너 속도가 실행마다 다르기 때문에 여유를 둡니다.

**배포 검사** (`tools/check_distributions.py`). 패키지 일곱 개(빈 `openphysics` 이름
예약 포함)를 고정 빌드 도구로 빌드하며, 각 wheel은 자기 sdist에서 빌드합니다.
`twine check --strict`로 메타데이터를 확인합니다. 배포물에는 패키지 코드만 들어갑니다.
sdist에는 `src/` 아래의 import 패키지, `README.md`, `LICENSE`, `NOTICE`, 빌드 파일(`pyproject.toml`,
`setup.py`, 빌드가 만드는 `PKG-INFO`, `setup.cfg`, egg-info)만 있고,
wheel에는 최상위에 둔 import 패키지와 dist-info만 있으며 `LICENSE`와 `NOTICE`는
`.dist-info/licenses/`에 들어갑니다. 시험·문서·예제·도구는 `packages/` 밖에 있으므로
어느 패키지도 `MANIFEST.in`이 필요 없습니다. 들어가야 할 내용은 손으로 적은 목록이
아니라 `packages/<name>/`에서 Git이 추적하는 파일로 정합니다. `src/` 아래의 추적 파일 전부(sdist에서는 `src/<import 이름>/…`,
wheel에서는 `<import 이름>/…`)와, sdist에서는 위에 적은 최상위 파일 중 Git이 추적하는 것이
모두 있어야 하고 checkout과 바이트가 같아야 합니다(`LICENSE`, `NOTICE` 포함). 그 밖의
파일이 압축본에 있거나, `packages/<name>/`에 그 밖의 파일이나 폴더(위 파일과 `src/` 말고는
`.gitignore`만 허용. 예: `tests/`나 `docs/` 폴더) 또는 `src/` 안에 import 패키지가 아닌 것을
Git이 추적하고 있으면 실패합니다.

이어서 wheel을 checkout 밖 새 환경에 설치합니다. 배포된 모든 모듈(`__main__` 제외)과
Studio 정적 파일은 그 환경에서 checkout과 같은 바이트로 로드돼야 합니다. 이 검사는
`tests/`의 pytest 시험을 돌리지 않으며, 그 시험은 `installed-tests`가 돌립니다. 이 검사는
공개 API·CLI·저장 파일을 확인하는 wheel 전용 소비자(`tools/wheel_consumers/test_*_wheel.py`),
고른 galerkin과 simcase 예제, 독립 수용 소비자를 돌립니다. 이들은 checkout이 추적하는 파일을 checkout 밖
임시 디렉터리로 복사해(해시는 `consumer-file-hashes.json`에 기록) 설치된 wheel을 대상으로
`python -I`로 실행하므로 checkout이 섞이지 않습니다. 설치된 환경은
`tools/check_licenses.py`를 통과해야 합니다. Studio Node 검사는 설치된 Studio 파일로 돌고,
Studio 브라우저 검사는 Chrome에서 작은 실제 모델을 돌립니다. 마지막으로
`tools/audit_distribution_artifacts.py`가 보관된 압축본의 체크섬과 sdist·wheel의 정확한
내용을 다시 확인합니다.

**설치 시험** (`tools/run_installed_tests.py`). 모든 패키지를 빌드하고(각 wheel은 자기
sdist에서), 압축본을 배포 검사와 같은 규칙으로 확인합니다. wheel 일곱 개를 각 metadata가
선언한 모든 extra와 함께 checkout 밖 임시 디렉터리의 새 환경에 설치합니다. 그 옆에는
`tests/`, `examples/`, `docs/` 아래의 추적 파일과 루트 `pyproject.toml`만 복사하고
`packages/` 아래는 복사하지 않습니다. 복사한 파일의 해시는
`suite-file-hashes.json`에 기록합니다. 이어서 `tests/`의 Python 시험 전체를 `python -I -m pytest`로
실행하며, 이름으로 고르는 시험은 없습니다. 시험이 실패하는 경우 말고도, 이 저장소 패키지의
모듈이 설치된 환경에서 로드되지 않거나, 건너뛰거나 xfail된 시험이 하나라도 있거나, 결과가
없는 시험 파일(`test_*.py`, `*_test.py`)이 있으면 실패합니다. 설치된 환경은 `tools/check_licenses.py`도
통과해야 합니다. 이 job은 고정 requirements, Gmsh, 고정 RII 데이터베이스, 필수 레퍼런스
교차 검사(`OPENPHYSICS_REQUIRE_CROSSCHECK=1`)를 사용합니다. 로컬 Linux 실행에서 25분쯤
걸렸고, 50분 제한은 멈춘 실행을 끊기 위한 것입니다. 로컬에서 돌리려면 Gmsh와
`PHYSMAT_RII_PATH`가 필요합니다. 없으면 그 시험이 건너뛰어지고, 건너뛴 시험이 있으면
실패하기 때문입니다. Linux에서만 확인했습니다. 소스 시험은 계속 `linux-py312`에서 돕니다.

**라이선스** (`tools/check_licenses.py`). 시험 전에 고정 검증 환경을, 이후 새로 설치한
환경마다 `tools/third_party_licenses.json`의 검토 목록과 대조합니다. 선언된 라이선스와, 제3자 휠이
설치한 공유 라이브러리를 OS마다 파일 하나하나 확인합니다. 정책과 전체 목록은
[제3자 소프트웨어](third-party.md)에 있습니다.

**설치 플랫폼** (`tools/check_platform_install.py`). OS마다 설치된 라이선스, 패키지 바이트, 설치된
모듈 위치, 포함 자산, 공개 API·CLI·저장 간단 시험, 열 저장/I-O 견고성 시험(부분 실패
정리, 동시 저장, 기존 대상 보호), source 대상 보호 fixture 두 개를 확인합니다. 설치
수용 검사이며 macOS나 Windows 전체 회귀 시험은 아닙니다.

**자원 관측.** Linux 실행이 통과하면 정상·과도 Studio 서버를 고정 작업량으로 한 번
측정합니다. 관측값이며 성능 기준이 아닙니다. 관측 도구는 `tools/studio_resources/`에 있고,
과도 관측 도구는 [과도 자원 관측 안내](transient_resource_probe.md)가 설명합니다. 솔버 시간 측정과 프로파일링 명령은
[벡터](benchmark_vector.md)·[공동](benchmark_cavity.md) 벤치마크 안내에 있습니다.

**대기열.** main 실행은 워크플로마다 하나의 동시성 그룹을 `queue: max`로 공유하며,
새 push가 와도 취소되지 않습니다. 다른 ref는 `queue: single`이라 새 push가 이전
실행을 대체합니다.

## 결과 읽기

각 job은 실패해도 artifact를 올립니다.

- Linux: `distributions-and-test-results`. 단계별 JUnit XML, 배포물 체크섬과 보고서,
  `numeric-runtime.json`이 든 `.validation/` 디렉터리입니다.
- 설치 시험: `installed-test-results`. 빌드한 배포물, `installed-tests.xml`,
  `installed-origins.json`, `suite-file-hashes.json`, 라이선스 보고서, 교차 검사 기록이 든
  `.validation/` 디렉터리입니다.
- 설치 플랫폼: `installed-packages-<os>-<run_id>`. 모든 명령의 종료 코드와 로그,
  환경 정보, 체크섬, 설치 위치, JUnit XML, `numeric-runtime.json`이 들어 있습니다.

일부 단계는 통과한 시험의 stdout도 JUnit `system-out`에 남깁니다
(`-o junit_logging=all -o junit_log_passing_tests=true`). 통과한 시험이 출력한 수치
진단을 보존하기 위해서입니다.

설정되어 있다는 것은 근거가 아닙니다. 어떤 커밋이 통과했다고 말하기 전에 그 커밋
자신의 실행, 개수, 건너뜀, artifact를 확인합니다. 한 OS의 결과는 다른 OS에 대해 아무것도
말해 주지 않습니다.

## 수치 재현성

호스트 러너는 매번 새로 만든 가상 머신이라 실행마다 CPU 기종이 바뀝니다. numpy에
포함된 OpenBLAS는 CPU를 보고 커널을 고르므로, 같은 커밋·고정 버전·시드에 스레드를
하나로 해도 마지막 비트가 달라질 수 있습니다.

- `tools/report_numeric_runtime.py`가 job마다 CPU 기종, OpenBLAS 커널,
  `numpy.show_runtime()`을 기록합니다(`numeric-runtime.json`). macOS arm64는
  Accelerate를 쓰므로 OpenBLAS 커널이 표시되지 않습니다.
- `blas-kernels`는 `OPENBLAS_CORETYPE=Haswell`(AVX2, AMD Zen에서도 쓰는 커널)과
  `Sandybridge`(AVX)를 강제합니다. 먼저 강제한 커널이 실제로 쓰이는지 확인하므로,
  다른 커널로 넘어가 조용히 통과할 수 없습니다. 이 job은 `OPENBLAS_L2_SIZE=2048`도
  설정합니다. 그러지 않으면 OpenBLAS 0.3.34가 AVX-512 AMD 러너(Zen 4/5)에서 커널을
  강제해도 GEMM 블로킹을 키워 Haswell 커널이 죽습니다
  ([OpenMathLib/OpenBLAS#6021](https://github.com/OpenMathLib/OpenBLAS/issues/6021)).
  고정한 numpy에 수정된 OpenBLAS가 들어오면 지웁니다
  ([#78](https://github.com/fieldalgo/openphysics/issues/78)). 로컬 재현:

  ```bash
  OPENBLAS_CORETYPE=Sandybridge python -m pytest -q -m "not slow" <test files>
  ```

시험은 마지막 비트 반올림에 기대지 않게 씁니다. 반올림 오차보다 충분히 큰 명시적
허용치로 비교하고, 반올림이 닿을 수 있는 경계에서 정확히 비교하지 않습니다.
정확한 비교는 한 기계에서 같은 코드에 같은 입력이 들어간다는 데서 나올 때만 타당합니다.
`tests/simcase/test_length_canonical.py`(nm, um, m 문서가 메시 생성기에 같은 입력을 줌)가
그 예이며, 근거를 시험에 적습니다.

## 배포(PyPI)

PyPI에 올리는 워크플로는 없고, 태그도 아무것도 실행하지 않습니다. 릴리스 전에 패키지와
버전을 정하고, 그 버전이 PyPI에 이미 있는지 확인하고, 정확한 main 커밋을 검증하고, 그
PyPI 프로젝트의 trusted publisher를 리뷰를 거친 배포 워크플로와 GitHub environment에
맞춰 설정합니다. 각 패키지는 `packages/<name>`에서 빌드합니다. 저장소 루트는 배포물이
아니며 `openphysics` 이름 예약은 전체 설치 패키지가 아닙니다. 패키지 하나만 빌드해
확인하려면:

```bash
python -m build --no-isolation --outdir .validation/simcase packages/simcase
python -m twine check --strict .validation/simcase/*
```

README는 PyPI 설명으로도 쓰이지만, 링크가 패키지 디렉터리 기준 상대 경로라 PyPI에서는
깨집니다. 그래서 각 패키지의 `setup.py`는 링크를 한 리비전에 고정한 GitHub 주소로 바꾼
README 사본을 메타데이터에 저장합니다(링크는 `blob/<ref>/…`, 이미지는 raw 파일).
`README.md` 자체는 바뀌지 않습니다. 리비전은 `OPENPHYSICS_DOCS_REF`가 있으면 그 값,
없으면 checkout의 커밋입니다. 릴리스 때는 push할 태그로 빌드해야 설명이 릴리스된 파일을
가리킵니다.

```bash
OPENPHYSICS_DOCS_REF=v0.2.0 python -m build --no-isolation --outdir .validation/simcase packages/simcase
```

풀어 놓은 sdist에서 만드는 wheel은 sdist의 설명을 그대로 씁니다.
`tools/tests/test_readme_links.py`는 일곱 `setup.py`가 같은지, 패키지 설명에 상대 링크가 남지
않았는지 검사합니다.
