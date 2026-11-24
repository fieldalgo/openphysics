# 개발과 검증

[English](../../../development.md) | **한국어**

개발 환경을 만들고, CI가 돌리는 검사를 직접 실행하고, CI 결과를 읽는 방법입니다.
브랜치·리뷰·릴리스 흐름은 [기여 안내](contributing.md)에 있습니다. 기능별 수용 기준과
근거는 각 기능의 계약·검증 문서에 있으며 [문서 색인](index.md)에서 찾을 수 있습니다.

## 환경

CI는 Ubuntu 24.04에서 Python 3.12.14와 Node.js 24.19.0을 고정해 사용합니다. 저장소
루트에서 Python 3.12 가상환경을 켠 상태로:

```bash
rustup toolchain install 1.97.0 --profile minimal --component rust-src
python -m pip install -r tools/requirements-py312-linux.txt
python -m pip install --no-deps --no-build-isolation \
  -e packages/galerkin -e packages/galerkin-refsol -e packages/meshine \
  -e packages/meshloom \
  -e packages/gmshio -e packages/physmat -e packages/simcase -e packages/sipi
python -m pip check
```

컴파일된 코드를 가진 패키지는 `meshloom` 하나입니다. editable 설치는 요구 사항 파일에 고정한
maturin과 `packages/meshloom/rust-toolchain.toml`의 도구 모음으로 Rust 커널을 빌드하고, 시험이
import하는 소스 옆에 확장 모듈을 둡니다. 빌드하지 않으면 `tests/meshloom`은 건너뜁니다.
`Cargo.lock`이나 도구 모음을 바꾸면 `python tools/build_meshloom_notices.py`로 라이선스 고지를 다시
만드세요. CI는 `--check`로 확인합니다.

`tools/requirements-py312-linux.txt`는 검증 도구와 그 하위 의존성을 고정한 것이며,
패키지의 실행 의존성이 아닙니다. 고정 버전은 리뷰를 거친 변경에서 의도적으로 바꾸고,
소스 검사와 배포 검사를 다시 실행합니다. 패키지 메타데이터는 Python >=3.12를
선언하고, CI는 Python 3.12만 시험합니다. 하한 numpy 1.26, scipy 1.11.2, shapely 2.0.2,
matplotlib 3.8은 Python 3.12 휠이 있는 첫 릴리스입니다. 정확히 그 버전들로 slow가 아닌
시험 전체를 손으로 한 번 통과시켰고(2026-10-21, Linux, Python 3.12), CI는 고정 버전만
시험합니다.

`galerkin[jax]`와 `galerkin[torch]`용 선택 배열 라이브러리는 따로 고정합니다. PyPI의 Linux torch
휠은 CUDA 패키지를 끌어오므로 CI는 torch CPU 빌드를 먼저 설치합니다.

```bash
python -m pip install --index-url https://download.pytorch.org/whl/cpu torch==2.14.1+cpu
python -m pip install -r tools/requirements-py312-linux-backends.txt
```

이것이 없으면 백엔드 시험의 JAX·PyTorch 경우가 skip됩니다. Linux CI 작업은 전체 시험 전에 둘 다
import되는지 확인하고, 설치 휠 실행은 skip이 하나라도 있으면 실패합니다. array-api-compat 하한
1.15는 `tests/galerkin/test_core_backend.py`로 손으로 한 번 확인했습니다(2026-10-26, Linux,
NumPy·JAX).

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
  사용합니다. 찾지 못하면 검사가 실패하며, 건너뛰지 않습니다. workspace, multiphysics,
  multiphysics session, project 스크립트는 `tools/studio_browser/browser_launch.mjs`로 브라우저를 띄웁니다. DevTools
  엔드포인트가 페이지를 나열하기까지 최대 60초 기다리고, 응답이 없으면 그 브라우저를 멈추고 새 포트와 새
  프로필 디렉터리로 한 번 더 띄웁니다. 실패한 시도는 모두 `report.json`(`browserLaunch`: 명령줄, 종료 코드나
  신호, stderr 마지막 4000자)에 기록되며, 두 번째 실패는 검사를 실패시킵니다. 다시 시도하는 것은 실행
  단계뿐이고 Studio 단계는 다시 하지 않습니다. `tests/simcase/studio_browser_launch.cjs`가 가짜 브라우저로
  이를 확인합니다. 네 스크립트는 끝에서 자기가 띄운 프로세스를 멈추고(SIGTERM, 10초 뒤 SIGKILL) 마지막 줄을
  찍은 뒤 자기 상태로 끝납니다. 그래서 스크립트보다 오래 남거나 출력 파이프를 쥔 브라우저 프로세스가 끝난
  검사를 계속 돌게 하지 못합니다(2026-11-24 macOS에서 project 스크립트가 통과한 뒤 작업 한도까지 돌았습니다).
  같은 시험이 SIGTERM을 무시하는 자식과 파이프를 열어 둔 자식으로 이를 확인합니다.

소스 Studio Node 단계는 실험적 작업공간을 포함한 `tests/simcase/*.cjs` 계약을
모두 실행합니다. 배포 검증은 `studio_workspace_*.cjs` 시험도 복사하여 검증된
설치 정적 파일에 대해 실행합니다.

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
| `packages/meshloom` | `src/meshloom/`(Python), `rust/`(커널) | `tests/meshloom/` | — |
| `packages/gmshio` | `src/gmshio/` | `tests/gmshio/`. `.geo`/`.msh` fixture는 `tests/gmshio/data/` | `examples/gmshio/` |
| `packages/physmat` | `src/physmat/` | `tests/physmat/` | `examples/physmat/` |
| `packages/sipi` | `src/sipi/` | `tests/sipi/` | `examples/sipi/` |
| `packages/simcase` | `src/simcase/`. Studio 정적 파일은 `src/simcase/studio/static/` | `tests/simcase/`. Studio JavaScript 검사(`*.cjs`) 포함 | `examples/simcase/`(JSON 문서와 `docs/gallery/`를 그리는 `gallery.py`) |

패키지마다의 문서(계약과 검증 보고서)는 `docs/packages/<name>/`에, 한국어 문서는
`docs/locales/ko/pages/packages/<name>/`에 있습니다. `tools/`에는 저장소 검사, 고정한 검증
환경, 검토한 라이선스 목록, 관리용 스크립트가 있습니다. 예를 들어 `tools/build_physmat_tables.py`는
physmat의 내장 표를 다시 만듭니다. 그중 필수 CI가 무엇을 돌리는지는 [tools/README.md](../../../../tools/README.md)에
있습니다. `physmat/unit_tables.json`은 `python -m physmat.units --write`로
`physmat/quantities.json`에서 생성합니다(`--check`는 비교). 생성기가 패키지 안에 들어 있어
`tests/physmat/test_units.py`(R3)가 설치한 휠에서도 이 파일을 검사합니다. [benchmarks/](../../../../benchmarks/README.md)에는 시간 측정 벤치마크가,
[studies/](../../../../studies/README.md)에는 진단 스크립트가 있습니다. 사람이 돌리며 필수 CI는 돌리지
않습니다. `openphysics` 메타 배포판에는 코드·시험·예제가 없고, 일곱 패키지(`studio`·`export` extra를 포함한 `simcase`, `rii`를 포함한 `physmat`)를 요구하며 Studio를 여는 `openphysics` 명령을 제공합니다. 루트에서 `python -m pytest`를
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

**API 단위 검사.** `tests/galerkin`, `tests/refsol`, `tests/physmat`은 각각
`test_api_units_scan_<package>.py`를 돌려, 공개 API(공개 모듈의 `__all__`)의 모든 매개변수를
단위 규칙에 비추어 봅니다. 매개변수는 `api` 자리가 있는 `physmat.units` 등록부 이름이면서
키워드 전용이고 차원 있는 기본값이 없거나, 구조 이름이어야 하며, 어떤 이름도 단위 토큰으로 끝나지
않아야 합니다. 공개 메서드에는 `__call__`도 들어가며, solver가 돌려주는 결과 클래스의 생성자는
검사하지 않습니다. 공통 논리와 데이터는 `tests/_support/`에 있습니다. `api_scan.py`, 공개·내부
모듈 목록, 닫힌 구조 이름 목록과 결과 클래스 목록, 제거된 이름 목록입니다. 그 밖의 모듈은 모두 내부 모듈이며
docstring에 "Internal module, consistent units"라고 적습니다. 패키지마다의
`api_units_allowlist.json`은 비어 있고 늘어날 수 없습니다. 새 위반은 실패합니다. 그래서 모든 공개 모듈이
깨끗합니다. 제거된 이름 목록의 모든 이름이 없는지 확인하고, 공개 물리량 매개변수에 `str`을 주면
반드시 `TypeError`가 나야 합니다. 범위(scope)와 그 까닭을 적은 메모가 붙은 제거된 이름은 그 모듈에서만 없는지
확인합니다. `refsol.bent_slab`은 더는 `radius`를 받지 않고(이제 `bend_radius`), `refsol.fiber`는 등록부 이름
`radius`를 받습니다. `galerkin.kernels`와 `physmat.kernels`는 simcase와 sipi를 위해 일관 단위의
커널을 다시 내보내는 내부 이름공간입니다. 어떤 공개 이름도 그 이름과 같지 않고, 그 객체도 아닙니다. 목록을 닫은 뒤 더한 구조 이름에는 검토 메모가 붙고, "deferred to the
materials step" 범주(`datum_temperature` 같은 physmat 레코드 인수)는 그 항목을 끝낼 조건도 적습니다.

**복소 규약.** galerkin과 refsol의 공개 복소 값은 exp(−iωt)를 따릅니다. exp(+iωt)로 계산하는 커널은
패키지의 비공개 모듈 `_conventions`의 `to_kernel`과 `to_public`으로만 변환합니다.
`tests/galerkin/test_conventions.py`는 galerkin, refsol, simcase의 패키지 코드를 읽고(sipi와 시험은
읽지 않음) 켤레(`conj`, `conjugate`, 또는 `0.0 - x.imag`와 `-x.imag`)를 거기와 simcase의 경계 함수,
수학적 켤레의 닫힌 목록 `tests/galerkin/conventions_allowlist.json`에서만 허용합니다. 목록 항목마다
함수, 원본 줄, 이유를 적으며, 더는 맞지 않는 항목도 실패합니다. 이 시험은 변환된 출력마다(지금은
정전기) 수동 매질의 부호를 확인하고, JAX와 PyTorch 기울기가 변환을 지나는지도 확인합니다.

## 검사 실행

```bash
export MPLBACKEND=Agg OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python -m pytest -q -ra                    # 전체 소스 시험
node --test tests/simcase/*.cjs            # Studio JavaScript 검사
python tools/check_distributions.py        # 모든 패키지 빌드·검사·설치
python tools/run_installed_tests.py        # 설치된 wheel로 tests/의 Python 시험 전체 실행
python tools/check_licenses.py             # 설치된 라이선스를 검토 목록과 대조
python tools/check_markdown_links.py       # 모든 Markdown 파일의 상대 링크와 #앵커
python tools/check_release_version.py      # 배포판 아홉 개의 버전이 하나인지
python tools/changelog.py --check          # changelog.d/의 변경 기록 조각
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

마지막 단계인 설치된 Studio 작업 공간 브라우저 점검에는 `PATH`에 Node 22 이상과 미리 설치된
Chrome, Chromium 또는 Edge가 필요합니다(흔한 위치에서 찾거나 `CHROME_PATH`로 지정). 없으면
건너뛰지 않고 실패합니다.

requirements 파일 이름은 예전 이름이며 Windows 전용이라는 뜻이 아닙니다.

## CI가 돌리는 것

`Validate packages` 워크플로(`.github/workflows/validate.yml`)는 main push, Ready PR,
수동 실행에서 돕니다. 브랜치 push와 draft PR에서는 돌지 않습니다. 다섯 부분이 병렬로
실행됩니다.

| Job | 플랫폼 | 검사 내용 |
|---|---|---|
| `linux-py312` | Ubuntu 24.04 | 라이선스·release 버전·변경 기록 조각·meshloom 커널·Markdown 링크 검사; 빠른 사전 검사 묶음; 배포물 아홉 개; Studio Node 검사; 정상·과도·영역 Studio 자원 관측 각 1회 |
| `linux-py312-tests` | Ubuntu 24.04, job 여덟 개 | 고정 RII 데이터베이스로 전체 소스 시험을 시간이 고르게 나뉜 여덟 부분으로 동시에 실행 |
| `installed-tests` | Ubuntu 24.04, job 여덟 개 | sdist에서 빌드한 wheel 아홉 개를 모든 extra와 함께 checkout 밖에 설치하고 `tests/`의 Python 시험 전체를 시간이 고르게 나뉜 여덟 부분으로 동시에 실행 |
| `blas-kernels` | Ubuntu 24.04, job 두 개 | 수치에 민감한 추적·고유공간·재료 공진기(복소 조밀·희소 고유값 풀이)·광섬유 기준·길이 단위 독립성 시험을 OpenBLAS 커널 두 개로 강제해 실행 |
| `installed-platforms` | Ubuntu 24.04, macOS 15, Windows 2022 | 패키지 여덟 개를 sdist에서 wheel로 빌드해 checkout 밖 새 환경에서 시험 |

필수 검사는 **`tests`** 하나입니다. 다섯 부분이(나뉜 부분의 job 여덟 개씩 모두 포함) 모두 성공해야 통과하며, 하나라도
실패·취소·건너뜀이면 실패합니다. 문서만 바꾼 변경도 이 검사가 필요합니다.

**Linux job.** 라이선스 검사 뒤 `tools/check_release_version.py`가 배포판 아홉 개의 버전이
하나인지 확인하고([배포](#배포pypi) 참고) `tools/changelog.py --check`가 [변경 기록 조각](#변경-기록-조각)을 확인한 뒤, Markdown 링크 검사가 돕니다. 저장소에서 추적하는 Markdown 파일의 모든 상대
링크와 `#앵커`가 풀려야 합니다(외부 URL은 가져오지 않습니다. 조각의 링크는 조각 검사가 풉니다). 사전 검사 묶음(정상 경계, 과도 문서, 정상·과도 Studio, 과도 열-역학)을
이어서 돌려서 계약이 깨지면 몇 분 안에 실패합니다. 그 뒤 배포 검사, Studio Node 검사,
자원 관측이 돕니다. 소스 시험을 뺀 이 job은 2026-11-20에 8~11분 걸렸습니다. 45분 제한은
멈춘 실행을 끊기 위한 것이며, 호스트 러너 속도가 실행마다 다르기 때문에 여유를 둡니다.

**소스 시험** (`linux-py312-tests`). 루트 설정의 `python -m pytest` 전체(`tests/`와
`tools/tests/`의 모든 시험)를 job 여덟 개에서 동시에 돌립니다. 각 job은 전체를 수집한 뒤
`tools/shards/openphysics_shard.py`가 자기 부분에 배정한 시험 파일만 남깁니다. 파일은 통째로,
큰 것부터, 그때까지 시간이 가장 적은 부분에 배정하며, 시간은
`tools/shards/durations.json`의 파일별 초를 씁니다(표에 없는 파일은 중앙값으로 셉니다).
모든 부분이 같은 수집 결과에서 같은 배정을 계산하므로, 여덟 부분을 합치면 수집한 시험을
빠짐없이 정확히 한 번씩 돌립니다. 이름으로 고르는 시험은 없습니다. 각 로그 끝에 그 부분의
파일 수, 시험 수, 예상 시간이 나옵니다. job 하나로 돌리던 때 전체 시험은 2026-11-20에 러너
CPU에 따라 44~70분, 네 부분으로는 2026-11-21에 10~21분 걸렸습니다. 여덟 부분의 한 부분은 표
기준 시험 약 5.5분과 준비 약 3분이며, 45분 제한은 멈춘 실행을 끊기 위한 것입니다. 파일을
통째로 배정하므로 가장 큰 파일이 한 부분의 바닥입니다(`tools/tests/test_examples_smoke.py`
5.7분, 예제를 파일 안에서 정한 순서로 돌림). 같은 이유로 5.5분짜리 M3 판 세밀화 연구는 자기
파일(`tests/galerkin/test_cavity_mesh_slab_refinement.py`)에 둡니다. 로컬에서 한 부분만
돌리려면:

```bash
PYTHONPATH=tools/shards python -m pytest -q -p openphysics_shard --shard 2/8
```

시험 시간의 균형이 어긋나면, 한 번의 완전한 실행에서 나온 JUnit 파일(artifact
`source-tests-<k>-of-8` 여덟 개를 한 폴더에 푼 것)로 저장소 루트에서 표를 다시 만듭니다.

```bash
python tools/shards/openphysics_shard.py --update source-tests-*.xml --source "Validate packages run <id> (main <sha>)"
```

**배포 검사** (`tools/check_distributions.py`). 패키지 아홉 개(`openphysics` 메타
배포판 포함)를 고정 빌드 도구로 빌드하며, 각 wheel은 자기 sdist에서 빌드합니다.
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
Studio 브라우저 검사는 Chrome에서 작은 실제 모델을 돌립니다. 정상·과도 직사각형 문서에 이어 배포 정상·과도 영역 예제(영역 색, 범례, 영역 표, 커서 표시)를 확인합니다. 마지막으로
`tools/audit_distribution_artifacts.py`가 보관된 압축본의 체크섬과 sdist·wheel의 정확한
내용을 다시 확인합니다.

**설치 시험** (`tools/run_installed_tests.py`). 모든 패키지를 빌드하고(각 wheel은 자기
sdist에서), 압축본을 배포 검사와 같은 규칙으로 확인합니다. wheel 아홉 개를 각 metadata가
선언한 모든 extra와 함께 checkout 밖 임시 디렉터리의 새 환경에 설치합니다. 그 옆에는
`tests/`, `examples/`, `docs/` 아래의 추적 파일, 단위 배치의 고정 문서(`tools/units_batch/fixtures/`,
시험이 읽는 JSON 데이터)와 루트 `pyproject.toml`만 복사하고 `packages/` 아래와 `tools/`의 다른
파일은 복사하지 않습니다. 복사한 파일의 해시는
`suite-file-hashes.json`에 기록합니다. 이어서 `tests/`의 Python 시험 전체를 `python -I -m pytest`로
실행하며, 이름으로 고르는 시험은 없습니다. 시험이 실패하는 경우 말고도, 이 저장소 패키지의
모듈이 설치된 환경에서 로드되지 않거나, 건너뛰거나 xfail된 시험이 하나라도 있거나, 결과가
없는 시험 파일(`test_*.py`, `*_test.py`)이 있으면 실패합니다. 설치된 환경은 `tools/check_licenses.py`도
통과해야 합니다. 이 job은 고정 requirements, Gmsh, 고정 RII 데이터베이스, 필수 레퍼런스
교차 검사(`OPENPHYSICS_REQUIRE_CROSSCHECK=1`)를 사용합니다. 로컬에서 돌리려면 Gmsh와
`PHYSMAT_RII_PATH`가 필요합니다. 없으면 그 시험이 건너뛰어지고, 건너뛴 시험이 있으면
실패하기 때문입니다. Linux에서만 확인했습니다. 소스 시험은 `linux-py312-tests`에서 돕니다.

CI에서는 이 job을 `--shard K/8`로 여덟 부분, `installed-tests (1/8)`~`(8/8)`로 돌립니다.
각 부분은 자기 wheel을 빌드·설치하고(약 2분), 복사한 시험 파일 전체에서
`tools/shards/openphysics_shard.py`가 소스 시험과 같은 표로 자기에게 배정한 시험 파일을 pytest에
넘깁니다. 결과 검사는 그 파일마다 결과가 있는지 확인합니다. 여덟 부분을 합치면 모든 시험 파일을
한 번씩 돌리며, 각 부분은 자기 파일과 예상 시간을 `shard.json`에 남깁니다. job 하나로 돌리던 때는
2026-11-20에 러너 CPU에 따라 39~71분 걸렸고, 63분 실행을 여덟으로 나누면 부분마다 7.1~10.9분이며
가장 긴 부분은 M3 판 세밀화 연구 하나입니다.
45분 제한은 멈춘 실행을 끊기 위한 것입니다. 로컬처럼 `--shard` 없이 실행하면 모든 시험 파일을
돌립니다.

**라이선스** (`tools/check_licenses.py`). 시험 전에 고정 검증 환경을, 이후 새로 설치한
환경마다 `tools/third_party_licenses.json`의 검토 목록과 대조합니다. 선언된 라이선스와, 제3자 휠이
설치한 공유 라이브러리를 OS마다 파일 하나하나 확인합니다. 정책과 전체 목록은
[제3자 소프트웨어](third-party.md)에 있습니다.

**설치 플랫폼** (`tools/check_platform_install.py`). OS마다 설치된 라이선스, 패키지 바이트, 설치된
모듈 위치, 포함 자산, 공개 API·CLI·저장 간단 시험, 열 저장/I-O 견고성 시험(부분 실패
정리, 동시 저장, 기존 대상 보호), source 대상 보호 fixture 두 개와 export extra를 설치한
영역 VTU/PVD 소비자 시험(`tests/simcase/test_export_regions.py`)을 확인합니다.
복사해 실행하는 wheel 소비자는 `test_thermal_simcase_wheel.py`,
`test_electric_joule_wheel.py`, `test_transient_thermomechanical_wheel.py`,
`test_cavity_wheel.py`(Studio 검사는 `check_distributions.py`에서 돌리므로 제외),
`test_sipi_wheel.py`(스트립라인·마이크로스트립·JSON 문서·DC 평면을
거친 메시에서 Cohn, Hammerstad–Jensen, 정확한 저항과 명시한 허용치로 비교)와
`test_vector_modes_wheel.py`(완전 벡터 슬래브 모드를 `refsol.slab`과, PML 누설 슬래브를
외향 근 분산식과 비교하고, `vector_slab` 예제를 PML 유무로 `simcase` CLI에서 실행)입니다.
나머지 `test_*_wheel.py` 소비자는 배포 검사에서 Linux에서만 돕니다. 2026-11-02에 추가한
소비자 세 개는 Linux에서 확인했으며, macOS와 Windows의 첫 실행은 CI 작업 자체입니다.
설치 수용 검사이며 macOS나 Windows 전체 회귀 시험은 아닙니다.
2026-11-24 main에서 플랫폼마다 28–30분이 걸렸습니다. 60분 제한은 멈춘 실행을 끊기 위한 것이며,
호스트 러너 속도가 실행마다 다르기 때문에 여유를 둡니다.
Studio extra의 고정 버전(`tools/requirements-py312-studio.txt`, 리눅스와 같은 버전)도 설치하고,
러너의 브라우저에서 설치된 작업 공간을 점검합니다(`tools/studio_browser/studio_workspace_browser.mjs`):
설계 두 개, Compare, Save session, 페이지를 연 채 서버 재시작, 시작 화면에서 복구, 설계 두 개를 더 만든
Compare의 모드 짝짓기(500 → 450 nm: 두 모드가 겹침 0.95 이상으로 짝지어지고 선택 목록이 짝지어진 쌍을 나열), 모드 수(Optical
modes와 Study의 Modes to find가 0, 9, 2.5를 거부하며 Run을 막고 1과 8을 받음, 8을 요청한 템플릿이 *Found 3 of 8 modes above
n = 1.45*와 세 행을 보임, 모드 8개인 2000 × 400 nm 코어 두 개가 쌍마다 짝지어지고 템플릿과 비교하면 *no match*, 선택 목록이
모든 쌍을 나열하며 1440 × 900과 390 × 844에 들어맞음, 엔진 값을 가진 버전 9 세션 저장과 열기, 16 MiB를 넘는 모드 8개 실행
여섯 개에서 먼저 묻고 Cancel은 아무것도 쓰지 않으며 보존한 파일은 장 없는 실행을 엶), 그다음 Joule 가열
애플리케이션: 기본 띠를 Picard와 Newton으로(반복 횟수, 수지, 온도·전위 범위, 두 방법의 1e-6 K 이내 일치. 영역
메시가 macOS arm64와 다른 플랫폼에서 달라서 메시에 따라 달라지는 값은 이산화 오차 안에서 확인),
수렴하지 않는 Newton 실행의 거부 문장 표시, 상수 재료(`joule.steady2d`, 균일한 띠의 정확한 전력 20 W/m).
잡히지 않은 페이지 예외와 `console.error` 호출이 있으면 검사가 실패합니다(그 밖의 브라우저 로그 항목은 모으지 않습니다).
또 모델 빌더를 키보드만으로 쓰는 ARIA 트리로 확인하고(하나뿐인 탭 정지로 Tab, Up, Down, Home, End, Enter,
Space, Left, Right), 광학과 Joule 가열 트리의 모든 노드를 브라우저 접근성 트리에서 역할과 접근 가능한 이름으로 찾으며,
Compare의 흡수 손실 열, 1440 × 900과 1280 × 800에서 코어에 맞춰진 그림과 그 아래의 probe 줄, Compare에서 누른 실행이
Compare에 남고 **Open in Results**를 제안함, 고른 것으로 보이는 실행 카드 하나, 페이지·실행·모드를 골라도 복구 뒤에도
이름이 남는 세션 파일, 보이던 페이지를 여는 복구를 확인합니다. 11차부터는 Results나 Compare에서 고른 트리 노드가 없고
포인터가 올라간 노드도 일반 배경을 유지함, 짧은 *(other inputs)*가 Results와 Compare에서만 제목에 붙음, 묻지 않는
**Use this run's inputs**와 그것을 되돌리는 Undo, 다음 실행의 입력을 밝히고 파장을 고치는 Study 설정(1300 nm는
Optical modes에서처럼 거부), 파일 저장 시각을 밝히는 복구 카드도 확인합니다. 모델과 함께 저장되는 study
설정도 확인합니다: Modes to find 변경, 군굴절률 상자 변경, 모드 수와 상자가 다른 실행의 **Use this run's
inputs**에 대한 Undo와 Redo, 모드 2개에 상자가 꺼져 있으면 **File › Export › Model file…**(`optical-waveguide.json`)이 버전 7을 쓰고(설정 키를
뺀 버전 8 파일과 같은 바이트. 템플릿의 파일은 `tests/simcase/studio_project_study.cjs`가
`tests/simcase/studio_session_fixtures/inputs-v7-optical.json`과 비교) `modeCount` 4나
`groupIndex` true이면 버전 8을 쓰며 각 파일을 다시 열면 그 설정이 되는지, 버전 8 입력의 세션이 버전 9로
저장되는지 확인합니다. 12차부터는 *Pages*라는 탭 목록인 페이지 탭(Library가 처음, 선택된 탭과 Tab 정지점은
하나, 오른쪽·왼쪽 화살표와 Home, End가 다음·이전·처음·마지막 페이지를 엶. 13차부터는 모든 탭이 제어하고 키마다 고른 탭의
이름을 따르는 `role=tabpanel` 페이지 패널 하나), 1440 × 900과 390 × 844에서 Compare 표의
두 머리글 줄(짧은 이름, 이어서 A | B), 표 위 줄의 실행 이름, 접근 가능한 이름이 전체 짝인 *1 ↔ 1* 행 머리글, 나머지 열이
표 상자 안에서 스크롤되는 동안 고정된 첫 열, 그 안에서 닿는 모든 열과 한 줄인 머리글·행 머리글, 그리고 군굴절률 상자의
쉬운 설명, Physics › Optical modes에도 있어 Study와 양쪽으로, Undo로도 맞춰지는 같은 상자, 켜고 끌 때마다의
Messages 줄, 다음 실행 입력의 *· group index on*, 보이는 실행이 n_g를 계산하지 않았을 때의
*Off · turn on in Study or Optical modes* 안내(15차부터는 Compare처럼 모드 표 위 줄에 있고 n_g 머리글은 *n_g*뿐)도
확인합니다. 13차부터는 Compare 표가 1440 × 900에 들어가는지
확인합니다(사전 등록): 500 → 450 nm 표와 8모드 표 두 개에서, Settings 창이 열린 채로(Compare는 모델 트리를
숨김) 상자의 clientWidth가 표 너비보다 24 px 이상 크고(Linux에서 42–44 px 측정) scrollWidth를 넘지 않으며,
잘리거나 칸 밖으로 나간 머리글·칸 글자가 없고, 모든 칸이 상자 안에 있으며, Polarization 칸은 두 줄이고 n_g
안내는 표 위 줄에 있습니다. 390 × 844에서는 표가 상자 안에서 스크롤되며 *Scroll sideways for all 14 columns ›*
줄과 오른쪽 끝에 닿으면 사라지는 오른쪽 가장자리 그림자가 나옵니다.
슬라이스 P2부터는 별도의 브라우저 컨텍스트에서 광학 열린 경계를 확인합니다(OB 단계): Outer boundary 라디오,
Search near n_eff, PML 점검 상자, *Close this edge* 스위치를 역할과 이름으로 찾고, 그림의 PML 띠, PML 점검을 켠
모든 변 열린 템플릿 실행(찾은 개수 줄, *< 0.01 dB/cm* 칸, 다른 후보 30개, 두 모드 모두 *no leakage resolved*), 작업 공간 세션이 버전 10인 프로젝트 파일, 닫힌 실행과의
Compare(짝짓기 꺼짐, 쪽마다의 손실 머리글과 안내, 1440 × 900에서 24 px 여유), Geometry에서 만든 누설 사례(문서가
P1의 기판 위 스트립과 같고 *29.15 dB/cm*와 *1006 dB/cm*, 모드별 점검에서 둘 다 손실 변화 2 % 미만으로 PML에 무관, 그 프로젝트 파일을 저장·열기·다시 저장하면 V-P1 (a)와 (b)를 따르고 실행이 같게 읽힘, Search near n_eff 1.600에서 클래딩 굴절률 근처 모드)를
확인하며, 1440 × 900과 390 × 844에서 가로 넘침이 없는지 봅니다
([열린 경계](packages/simcase/workspace.md#광학-작업-공간의-열린-경계)).
File 메뉴가 생긴 뒤로는 접근성 트리에서 역할과 이름으로, 그리고 키보드로(Export와 Browser copy 하위
메뉴와 Edit 메뉴를 지나는 Enter, Up, Down, Home, End, Right, Left, 한 단계씩 닫고 초점을 돌려주는
Escape) 메뉴를 확인하고, 보이는 단축키와 `aria-keyshortcuts`, 1440 × 900과 390 × 844에서 페이지 안에
들어가는 열린 메뉴, 두 크기에서 복구 제안이 있든 없든 Library 맨 위 한 곳의 **Open session file…**도
확인합니다. 헤드리스 실행에서는 브라우저의 실제 저장 대화상자에 답할 수 없으므로 스크립트는 문서 시작 시
`window.showSaveFilePicker`를 지우고, Save는 Studio의 이름 대화상자를 거칩니다(Download는 제안 이름을
유지하므로 파일 이름과 바이트를 전처럼 확인). 이어서 Chromium처럼 닫을 때만 파일이 바뀌는 대역(stub)을 그
경계에 넣어 Save As(대화상자 옵션: 제안 이름, JSON 형식 하나, `id` `openphysics-project`, 파일을 고르기
전에는 `startIn` 없음, 그다음엔 현재 파일), 같은 상태의 다운로드와 같은 바이트, 대화상자를 다시 부르지 않고 같은
파일에 쓰는 Save, 아무것도 쓰지 않는 취소, 중단되어 이전 내용이 온전한 실패한 쓰기, `NotAllowedError`를
던지는 대화상자에서 이름 대화상자로 넘어가는 것을 확인합니다. 헤드리스 브라우저는 `navigator.webdriver`를 알리며, 이때 Studio는 저장 대화상자를 부르지 않습니다
(부르면 예외를 던질 대역이 불리지 않고 Save As가 입력한 이름으로 내려받음). 대화상자 점검은 그 경계에서
`navigator.webdriver`를 false로 둡니다. 이름 대화상자에 입력한 이름은 정리됩니다
(`my run/<x>?`은 `my runx.json`으로 내려받음). 13차부터는 다운로드 경로에서 모델의 현재 파일 이름도
확인합니다: Save As *design-a-ng*, Width 편집 뒤 Save와 Ctrl+S가 이름 대화상자 없이 `design-a-ng.json`으로
다시 내려받음(바이트에 새 폭, Messages에 “ (1)” 안내와 함께 *Downloaded design-a-ng.json again*), 파일
이름을 밝히는 헤더(14차부터 *design-a-ng.json · downloaded …*와 *· changed since downloaded*, 그리고 picker
경로에는 없는 title 텍스트 *Your browser may have added “ (1)” to the file name.*, Save As 대화상자의 줄
*Later saves download again under this name; your browser may add “ (1)”.*), 그 이름으로 채워진
Save As, 그 파일을 **File › Open…**으로 열면 이름이 그 파일이 됨(*Opened design-a-ng.json*, 이어서
*· changed since opened*, Save가 이름을 유지), **Reset design**이 이름을 버려 Save가 모델 기반 이름으로
묻는 것, 그리고 **File › Open…**으로 연 64 KiB 넘는 모델 파일이 *Model file exceeds 64 KiB*로 거부되는
것입니다. 다른 흐름에서도 연 파일 뒤의 저장은 그 이름을 유지합니다. 데스크톱 Chrome의 실제 저장 대화상자는 어떤 점검도
조작하지 않습니다.
14차부터는 도크 제목과 상태 표시줄이 두 기하를 모두 밝히는지(*Run 1 · design A 600 × 300 nm · current inputs
700 × 300 nm*), **Use this run's inputs**의 변경 목록이 실행 패널의 버튼 자리에 남는지(Messages와 같은 문구,
페이지를 바꿔도 남고 다음 입력 편집에서 사라짐), 현재 입력의 실행이 없을 때 저장 알림이 *Current inputs
(650 × 400 nm) have no run yet.*이라고 하는지(실행이 있으면 말하지 않음)도 확인합니다. 500, 450 nm 실행에서
실행 배너도 확인합니다(사전 등록): 1440 × 900과 390 × 844에서 트리, 설정 창, 작업 영역의 상자가 배너 전,
배너가 보이는 동안(실행 중과 *Optical run complete…*), 편집으로 배너가 사라진 뒤 모두 정확히 같고, 배너가
보이는 동안 모든 탭, 리본 버튼, File 메뉴 버튼, 트리의 첫 항목이 그 중심점의 요소이며, 배너 밖의 보이는
컨트롤이 배너와 겹치지 않고 배너의 버튼은 누를 수 있습니다. Compare에서 실행 목록의 *Compare A*, *Compare B*는
레이블 뒤의 테두리 있는 배지이고, 버튼의 접근 가능한 이름은 여전히 *· Compare A*, *· Compare B*로 끝납니다.
15차부터(사전 등록) 배너는 보기 제목 줄의 일부입니다: 두 크기에서 실행 중과 완료 때 배너를 화면 안으로 스크롤한
상태로, 배너가 어떤 패널 제목(보기 제목과 설명, 창 제목, 보기와 설정의 제목과 표 캡션)과도 겹치지 않고, 각 제목이
그 중심점의 요소이며, 보기 제목이 보이고, 제목 줄, 보기 제목, 보기의 상자가 배너가 있을 때와 없을 때 같은지
확인합니다. 입력이 없으면 완료 배너는 나타난 뒤 5.9–6.6초에 사라지고(1440 × 900, 페이지 안에서 측정), 실제 마우스
누름이 있으면 300 ms 안에 사라집니다(390 × 844).
15차부터 hybrid Polarization 문구(*hybrid · x % TE / y % TM*)도 확인합니다.
15차부터 재료 분산에 대한 군굴절률 설명과 Optical modes의 *Material data*도 확인합니다.
15차부터 단계 막대의 파장이 접근성 트리에서 *Wavelength 1550 nm, edit*라는 이름의 버튼인지도 확인하고, 다중물리
검사는 트리 경고 배지가 *Modes 1: Temperature input has no source: …*라는 이름의 이미지인지, 세션 검사는 Library
카드마다의 *Open model*(16차부터, 이전에는 *Open (runs stay in this tab)*), *Runs stay in this tab until you close it.*로
끝나는 카드 설명, 카드 제안의 *Start new (no runs)*를 읽습니다.
16차부터 Save As 안내 *This browser cannot write to the file, so later saves download again under this name and may add
“ (1)”.*(15차는 *Chrome and Edge save to the same file.*을 확인했으며 이제 사용 안내에만 있음), 파일 이름에서 온 프로젝트
이름이 Save As를 따라가는지(*chosen*, 그다음 *design-a-ng*), 누설 사례의 기판을 T16 순서(Left x −1500, Bottom y −1200,
Width 3000, Height 700)로 한 글자씩 입력하면 (−1500, −1200)에 놓인 3000 × 700 nm 사각형이 되고 *Width set to 3000 nm.
Left x kept at −1500 nm: centred, the shape would leave the window.*가 나오는지도 확인합니다.
17차부터(사전 등록) 자체 브라우저 컨텍스트의 단계로 끝납니다: 작업 공간 안내와 닫힌 Study 패널이 바깥 경계는 *Physics ›
Optical modes*에서 고른다고 말하는지, 선택을 켜면 Run study 옆에 군굴절률이 나오고(*Closed window · group index on (3 solves) · …*, 18차의 말) 끄면 빠지는지,
템플릿 실행 일곱 개(코어 메시 30~42 nm)가 Run 7부터 Run 2로 나열되고 *Run 1 (500 × 220 nm · 2 modes) was dropped: up to
six runs are kept; pin a run to keep it.*가 나오며 상태 표시줄이 Run 7인지, Run 5와 Run 6에 이름을 붙여 비교한 뒤 여덟 번째
실행이 Run 2를 내보내고 *Run 8 is newer than this pair · Compare Run 8 with B*가 나오는지, Compare 선택 목록이 접근성
트리에서 *Run A*, *Run B*이고 전체 이름을 제목으로 가지며 1440 × 900과 390 × 844에서 실행 번호와 이름이 보이는 너비에
들어가는지, 닫힌 창에서 T18 기판((−1500, −1200)의 3000 × 700 nm)으로 모드 1과 2 아래에 안내 행(*Mode 1 is mostly in
Substrate (… % of |E|²), which touches the window edge; …*, 50 % 초과)이 나오는지, 파장 편집 뒤 상태 표시줄이 *Run 9 ·
Core 500 × 220 + Substrate 3000 × 700 nm …*인지, 템플릿 코어와 기판 실행을 Compare에서 비교하면 B의 안내, 짝이 없는 행마다
*best x (< 0.8, not matched)*, 1440 × 900에서 O2의 24 px가 나오는지 봅니다.
18차부터(사전 등록) 자체 브라우저 컨텍스트의 단계가 하나 더 Run study 옆 상자를 확인합니다: 실행 전 *Closed window*(20차 문구; 19차에는 *no timed run in this tab yet*, 그 전에는 *no earlier
run*), *… · group index on (3 solves)*와 *Open boundary · 2 searches · group index on (3 solves)*, 그때
Messages에 자기 색으로 나오는 경고 *Group index is on: open-boundary runs with it take about three times as long.*, 실행 뒤
*last such run m:ss*; 모든 문구와 내보냄 줄에서 1440 × 900과 390 × 844의 Compute 그룹 높이, Run study 상자, 상자 크기가
0.5 px 안에서 같은지; Search near n_eff 도움말이 *(n_core + 1.444)/2.*로 끝나는지; 편집으로 Run 1의 입력에 돌아오면
**Show Run 1**과 함께 *No need to run: Run 1 already has these results. …*가 나오고(Run study는 그대로 켜짐) 실행 목록이
*Run 1 · closed · 500 × 220 nm …*인지; Run 2 뒤 Run 1을 보면 상태 표시줄이 *… · current inputs from Run 2*인지; 실행 여섯 개에서
*If you run: drops Run 1 (500 × 220 nm · 2 modes) · pin it to keep it*(20차 문구)와 **Pin Run 1**이 나오고 누르면 고정되며 줄이 Run 2로
옮겨 가는지; 기판 실행의 안내 아래 **Use Open boundary**와 **Search near 2.46 · 4 modes**(C2; C0에서는 *Set Modes to find to 4*, 그 전에는 *Find 4 modes*)가 각각 입력을 정하고 아무것도 실행하지 않는지;
Compare의 선택 목록과 제목이 *closed*를 담고 O2의 24 px가 나오는지; 두 크기 모두 가로 넘침이 없는지 봅니다.
19차부터(사전 등록) 자체 브라우저 컨텍스트의 단계가 하나 더 확인합니다: 형상 속성의 *Name*과 *Material* 칸이 그 낱말 하나뿐인
레이블을 하나씩 가지는지(감싸지 않고 `for`로); 실행 여섯 개 뒤 Run study가 *Running drops Run 1 (500 × 220 nm · 2 modes).*와
*Up to six runs are kept; a pinned run is never dropped.*, **Pin Run 1 and run**, **Run**, **Cancel**(첫째에 포커스)을 담은 대화
상자를 열고 1440 × 900과 390 × 844에서 가로 넘침이 없는지; Escape가 아무것도 실행하지 않고 닫으며 포커스가 Run study로 가는지;
Pin Run 1 and run이 Run 1을 고정하고 Run 2에 대해 다시 묻는지; Cancel이 아무것도 실행하지 않는지; 그다음 Run이 Run 7을 만들고
Run 2를 내보내며 Run study 옆 줄은 남는지; 실행 하나의 두 번째 세션 뒤 Library 상자가 *Restore newest from this browser:
Optical waveguide · 1 run · Run 1 · saved …*(카드가 제안하는 기록)로 시작하고 실행 여섯 개 세션은 *… · older · saved …*인지;
그 오래된 세션을 복원하면 상자가 숨고, 더 새 세션은 곧바로 마지막 세션으로, 이 탭의 기록이 쓰인 뒤에는 Workspace tools의
이전 세션으로 제안되며, 복원한 세션은 다시 나오지 않는지. 실행 여섯 개를 넘기는 단계는 대화 상자에 Run으로 답하고, Library의
첫 화면 검사는 이제 카드 위 상자의 가장 새 제안을 봅니다. 20차부터(사전 등록) 대화 상자 단계는 질문이 열려 있는 동안 Run study
옆의 *Waiting for your answer: pin, run or cancel*(내보냄 줄은 숨음), 상태 표시줄의 *Run study is waiting for your answer*,
그대로 *Run study*인 버튼, 비어 있는 숨은 작업 메시지, 대화 상자 안의 포커스를, Escape 뒤에는 전의 계획 줄과 상태를 읽습니다.
자체 브라우저 컨텍스트의 단계가 하나 더 실행 전 *Closed window*, 어느 경계에서든 범위 안내의 *3 × 2.4 µm window, closed (PEC
edges) or with an open boundary (PML 1 µm outside the open edges, PEC on the closed ones)*를 확인하고, 실행 둘(Modes to find
2와 3), 새로고침, 복원 뒤 Modes to find를 2로, 그다음 3으로 바꾸면 **Show Run 2**와 함께 *Modes to find set to 3. No need to
run: Run 2 already has these results. Run study adds a copy with the same values.*, 상태 표시줄 *Run 2 · recovered from this
browser, not recomputed · has the results of the current inputs*가 나오고, 어떤 실행에도 없는 4는 *… Run explicitly to
compute new results.*를 그대로 두는지; 1440 × 900과 390 × 844에서 가로 넘침이 없는지 봅니다.
광학 트리의 Results 그룹(사전 등록)은 실행 둘에서 역할과 이름으로(*Results · run 1*은 수준 1, 고른 *Runs · 2 of 6*과
*Compare*는 수준 2, 탭 정지는 Runs), 키보드로(Up으로 그룹, End로 Compare, Enter로 Compare 열기, Runs에서 Enter로
보이는 실행의 Results 열기) 확인하며, 11차의 표시 검사는 이제 Results에서 Runs만, Compare에서 Compare만 고른 것으로 봅니다.
이어서 두 번째 스크립트(`tools/studio_browser/studio_multiphysics_browser.mjs`)가 다중물리 모델을
조작합니다. Heated silicon waveguide 템플릿, 포트 선택기로 결합을 지웠다 다시 추가하기, 재료 문제와
한 번에 고치기, 결합된 n_eff가 같은 문서의 엔진 실행과 정확히 같아야 하는 Run, 결합 검사, 실행과 함께 푼 히터 없는
열과 엔진 두 실행의 차이와 같은 Δn_eff, 편집으로 out of date가 되고 내용이 같으면 다시 현재가 되는
실행(두 번째 실행에서도 열이 유효), 결합만 지웠을 때 광 단계만 out of date가 됨, 템플릿의 두 모드(TE-like, 이어서 TM 비율을
밝히는 TM-like 칸), 지운 결합의 경고와 Undo, 1440 × 900과 390 px 폭에서 가로 넘침이 없음, 키보드만으로 쓰고 역할과 이름으로 찾는
다중물리 모델 트리, Results에서 트리가 결과 페이지를 표시함을 확인합니다. 11차부터는 새 템플릿의 *New model · not
saved*, 온도 입력을 위해 추가하는 결합의 From 목록에 온도만 있음, *No need to run: Run 1 already has these
results*도 확인합니다.
세 번째 스크립트(`tools/studio_browser/studio_multiphysics_session_browser.mjs`)는 다중물리 세션 파일(버전 8)을
확인합니다. 모든 모델의 Save session과 Open session 하나씩, 템플릿·0.12 µm 메시·실행 두 개 세션을 저장하고 열고 다시
저장(두 번째 파일은 바이트 단위로 같고, 저장된 모든 배열은 따로 받은 서버 응답과 Float64 비트까지 같음), 0.08 µm 메시
실행 여섯 개로 16 MiB 한도의 질문과 거부, 손상되거나 더 새로운 파일의 거부, 다시 읽기 뒤 브라우저 복구, 이전 세션 세 개,
두 탭의 충돌, 그리고 다시 켜기입니다: 광학 실행 두 개, 그 위로 가열 세션 파일 열기, 새로고침, 같은 파일 다시 열기. 그 뒤
제목은 탭을 눌러도 *Opened …*를 유지하고, 복구 목록은 세션마다 한 번씩만 보여 주며, Optical waveguide 카드가 광학
실행을 제안하고 그 실행은 같은 n_eff로 돌아옵니다. 또 도크와 하단의 이름 붙은 실행(*Run 1 · Heater 2e14 · …*)과,
가열 세션의 저장 메시지가 그 파일에 없는 광학 실행을 밝히는지 확인합니다. 11차부터는 새로고침 뒤 Heated silicon
waveguide 카드가 자기 가장 새 기록을 복원하고(19차부터 위 상자는 가장 새 기록인 그 기록으로 시작) 세션 파일의 저장 시각을 밝히는지,
복원된 제목이 *same as file …*인지, Workspace tools가 *Restore earlier session from this browser*라고 하는지 확인합니다. 13차부터는 Save As 이름
뒤의 Save가 대화상자 없이 그 이름으로 다시 내려받는지(*Downloaded heated-design.json again*, 바닥글
“ (1)” title 텍스트와 함께 *heated-design.json · downloaded …*), 연 모델 파일이나 세션 파일 뒤의 Save가 그 파일 이름을
유지하는지도 확인합니다. 14차부터 두 스크립트는 제목이 *same as file X*인 복원이 X를 현재 파일로 삼는지(Save As가
X를 제안함) 확인하고, workspace 스크립트는 입력 편집 뒤와 실행 이름을 바꾼 뒤 *X · changed since restored*를 확인하며, session 스크립트는 파일에서 연 실행이 *Loaded from file, not
recomputed. Results match the file's checksum.*으로 표시되고 출처 주의 문구가 그 문장의 title 텍스트인지 확인합니다.
네 번째 스크립트(`tools/studio_browser/studio_project_browser.mjs`)는 [프로젝트
파일](packages/simcase/workspace.md#프로젝트-파일)을 확인합니다. 1440 × 900과 390 × 844에서, 역할과 접근 가능한
이름으로, 어느 단계에서도 가로 넘침 없이: 광학 실행 두 번(하나는 Modes to find 4)과 히터 없는 결과가 있는 가열
실행, 프로젝트 이름 *Heater study*와 제안 이름 `heater-study.json`으로 Save As, 기억한 이름으로 다시 Save, 그다음 서버 재시작과 새 브라우저 프로필, File ›
Open, 두 모델이 실행 없이 같은 값 문자열을 다시 읽음. 저장, 열기, 다시 저장(저장 시각과 광학 실행의 출처 말고는
같고, 그다음은 저장 시각 말고는 바이트까지 같음), 손상되거나 더 새로운 파일을 탭 그대로 거부, 경계에서 바꾼
`window.showSaveFilePicker`로 Save As, Save, 취소, 실패한 쓰기. `--old-python <python>`을 주면 이전 Studio에서
파일을 여는 것도 봅니다(손으로만, CI는 주지 않음). 16차부터(사전 등록) 이어서 새 프로필에서 1440 × 900으로 그 파일을
엽니다: Library › Heated silicon waveguide는 그 Results로, Library › Optical waveguide는 마지막으로 본 실행의 Results로
돌아가고, *Design A*, *Design B*로 이름 붙인 Run 1과 Run 2는 세 번째 실행이 생겨도 Compare에 남으며(*Run 3 is newer than
this pair · Compare Run 3 with B*), `design-ab.json`으로 Save As해도 이름 *Heater study*와 그 쌍이 유지되고, 새로고침 뒤
두 카드 제안 모두 *same as file design-ab.json*을 말하며(저장할 때 가열 모델은 보이지 않았음), 광학 제안을 복원하면
헤더가 *Heater study · design-ab.json · saved …*이고 Save As가 `design-ab.json`을 제안하며, 다시 연 파일은 Design A와
Design B를 비교합니다. 17차부터(사전 등록) Compare에 두고 떠난 광학 모델은 실행 하나가 눌린 Results로 돌아오고, 바꿔 연
모델은 스크롤해 두었어도 페이지 맨 위(scrollTop 0)에서 시작하며, 새 프로필에서 광학 모델만으로 내려받아 저장한 프로젝트에
가열 모델을 더하면 **Save**가 `u8-optical.json`을 채운 Save As 대화상자와 *This project now holds Optical waveguide and
Heated silicon waveguide; u8-optical.json holds Optical waveguide. Save under this name or another.*를 보이고, Cancel은
아무것도 내려받지 않으며, 두 모델로 저장한 뒤의 Save는 바로 내려받습니다. 18차부터(사전 등록) 같은 프로필에서 Save As 줄
*The file will hold Optical waveguide (no runs).*와 Save가 물을 때의 *… and Heated silicon waveguide (no runs).*, 가열
모델이 합류한 뒤 상태 표시줄 *Heated silicon waveguide · in project u8-optical.json · not saved since it joined · …*와 두
모델로 저장한 뒤의 *… · downloaded …*(제목 표시줄의 말과 함께), 두 카드의 *Return to Optical waveguide*와 *Return to Heated silicon waveguide*(20차 문구)를 확인합니다. 16차의 다시 불러오기
단계에서도 두 카드의 제안이 다른 모델을 *· also in this project: … (restored separately)*로 밝힙니다. 19차부터(사전 등록)
새 프로필이 `heater-study.json`을 열고 광 모델을 다시 실행한 뒤 새로고침하여 복원하면 헤더가 *Untitled project · recovered from a
copy of heater-study.json · not saved to a file · …*이고 상태 표시줄은 *Recovered from this browser (opened from heater-study.json;
changed since)*인지, `r19-saved.json`으로 저장하고 다시 실행해 복원하면 *r19-saved · r19-saved.json · changed since saved …*인지
봅니다. session 스크립트는 히터 없는 풀이 레이블을 마우스 이벤트로(글자에, 그다음 *(about 1 s more)*에) 눌러 상자가 꺼졌다
켜지는지 보고, 가열 실행 여섯 개 뒤 Run study가 세 답과 함께 *Running drops Run 1 (run at …).*라고 묻고 Cancel은 아무것도
실행하지 않으며 Run은 Run 1을 내보내고 Run 7을 만드는지 봅니다. P3부터 **File › Save**가 프로젝트 파일을 쓰므로 workspace와
session 스크립트는 세션을 **File › Export › Model with runs (session file)…**로 저장합니다. 20차부터(사전 등록) project
스크립트는 새 프로필에서 `heater-study.json`을 열고 두 모델을 보인 뒤 가열 기록이 쓰이고 1분 뒤 `r20-both.json`으로 저장하고
새로고침합니다: 상자가 *Restore newest from this browser: Optical waveguide (2 runs) and Heated silicon waveguide (1 run) · same
as file r20-both.json · saved …*로 시작하고, 가열 기록은 상자와 카드에서 같은 시각(파일의 저장 시각)을 밝히는지; 한 번의
클릭이 둘 다 복원하여 *Restored Optical waveguide (2 runs) and Heated silicon waveguide (1 run) from this browser, not
recomputed. …*, 헤더 *Heater study · r20-both.json · saved …*, 광 모델의 Results가 나오고, Library에는 복원 제안이 남지 않으며
*Return to Optical waveguide (2 runs)*와 *Return to Heated silicon waveguide (1 run)*로 읽히는지; 1440 × 900과 390 × 844에서
가로 넘침이 없는지 봅니다. session 스크립트의 가열 모델 내보내기 질문은 열려 있는 동안 Run study 아래에 *Waiting for your
answer: pin, run or cancel*, 상태 표시줄에 *Run study is waiting for your answer*를 보이고 Cancel 뒤에는 둘 다 없으며, 파일에서
연 실행의 상태 표시줄은 *… · has the results of the current model*, 그 카드는 *Return to Heated silicon waveguide (2 runs)*입니다.

**자원 관측.** Linux 실행이 통과하면 정상·과도 Studio 서버와 열전도 영역 문서를 받는 Studio를
고정 작업량으로 한 번 측정합니다. 관측값이며 성능 기준이 아닙니다. 영역 관측은 작업의 결과
코드가 정해 둔 것과 다르거나 단계가 실패할 때만 실패합니다. 관측 도구는
`tools/studio_resources/`에 있고, 과도 관측 도구는 [과도 자원 관측 안내](transient_resource_probe.md)가,
영역 관측은 [영역 자원 관측](region_resource_probe.md)이 설명합니다. 솔버 시간 측정과 프로파일링 명령은
[벡터](benchmark_vector.md)·[공동](benchmark_cavity.md)·[열전도](benchmark_thermal.md)·
[탄성](benchmark_elasticity.md)·[전기](benchmark_electric.md)·[미분](benchmark_derivatives.md)
벤치마크 안내에 있습니다.

**단위 배치 동등성(수동 실행 전용).** `units-batch-equivalence` job은
`OPENPHYSICS_BATCH_BASELINE`을 `main`과의 merge base로, `OPENPHYSICS_BATCH_PHASE`를 `3`으로 두고
`tests/simcase/test_units_batch_equivalence.py`를 Ubuntu 24.04, macOS 15, Windows 2022에서
한 플랫폼씩 실행합니다. `examples/simcase`의 모든 문서와 고정 fixture를 같은 문서 그대로 기준
커밋과 실행한 커밋에서 각각 기록해, 저장 바이트가 같은지, 그리고 solver·mesher 입력이
[단위 배치 비교 도구](../../../../tools/units_batch/README.md#phase-3-the-galerkin-step)의 규칙
항목 아래에서 매개변수 이름별로 같은지 봅니다(galerkin 단계의 점검 P3-1). 비교 도구의 phase 2,
즉 단위 배치 자체의 점검은 그 배치의 기준 커밋이 필요하므로 로컬에서 실행합니다. 수동
실행(`gh workflow run validate.yml --ref <branch>`)에서만 돌고 push와 pull request에서는
건너뜁니다. `tests`에 들어 있지 않으므로 플랫폼마다 결과를 따로, 주장하는 커밋의 실행에서
읽습니다.

**대기열.** main 실행은 워크플로마다 하나의 동시성 그룹을 `queue: max`로 공유하며,
새 push가 와도 취소되지 않습니다. 다른 ref는 `queue: single`이라 새 push가 이전
실행을 대체합니다.

### 최신 의존성 카나리

`Latest dependencies` 워크플로(`.github/workflows/latest-deps.yml`)는 하루 한 번(21:47 UTC)과
수동 실행에서 돕니다. 필수 검사 `tests`에 **들어가지 않으며** PR이나 `main`을 막지 않습니다.
고정 환경이 제공하는 extra(`galerkin[test,figures,jax,torch,crosscheck]`, `galerkin-refsol[test]`,
`meshine[test,plot]`, `meshloom[test]`, `gmshio[test,gmsh,plot]`, `physmat[test,rii,plot]`,
`simcase[test,studio,export]`, `sipi[test]`)와 함께 패키지 여덟 개를 고정 requirements 없이,
`--no-deps` 없이 editable로 설치하므로 pip이 `pyproject.toml` 범위 안에서 가장 새 버전을
고릅니다. PyTorch CPU 인덱스는 버전 고정 없이 추가 인덱스로 쓰며, 설치된 torch가 `+cpu`
빌드인지 확인합니다. meshloom은 pyproject가 허용하는 가장 새 maturin으로 빌드하되 Rust
crate는 `Cargo.lock`에 고정합니다(`--locked`). 이어서 `python -m pip check`, 라이선스 검사(검토
목록에 없는 새 전이 의존성이 있으면 실패하며, 그것이 이 검사의 목적 중 하나입니다), Linux
job과 같은 사전 검사 묶음, 고정 RII 데이터베이스와 필수 레퍼런스 교차 검사를 포함한
non-slow 시험, `blas-kernels` 파일 목록을 강제 OpenBLAS 커널 두 개로 돌립니다. 설치가
성공하면 앞 단계가 실패해도 각 검사는 그대로 돌아서 한 실패가 다른 실패를 가리지
않습니다. `pip freeze`는 step summary에 적고, 라이선스 보고서·JUnit 파일과 함께
`latest-deps-results` 아티팩트로 올립니다. 돌리지 않는 것: Studio Node 검사(Node는 워크플로가
고정하고 pip이 고르지 않으므로 여기서 바뀔 수 없음), 배포물 빌드, meshloom의 Cargo 시험과
notices, slow 연구.

예약 실행이나 수동 실행이 실패하면 **Latest dependencies canary failed** 이슈를 열고, 이미
열려 있으면 그 이슈에 댓글을 남깁니다. 본문에는 실행 URL과 주요 패키지의 해석된 버전을
고정 버전과 나란히 적습니다. 통과한 실행은 그 이슈를 닫습니다. 취소된 실행(90분 제한에
걸려 멈춘 실행 포함)은 보고하지 않습니다. 카나리는 미리 알리는 신호이지 커밋에 대한
판정이 아닙니다. `tools/requirements-py312-linux*.txt`의 고정 버전은 여전히 소스·배포 검사를
다시 돌리는 검토된 변경에서 의도적으로 올립니다.

## 결과 읽기

각 job은 실패해도 artifact를 올립니다.

- Linux: `distributions-and-test-results`. 사전 검사 묶음별 JUnit XML, 배포물 체크섬과 보고서,
  `numeric-runtime.json`이 든 `.validation/` 디렉터리입니다.
- 소스 시험: 부분마다 `source-tests-<k>-of-8`. `source-tests-<k>.xml`, 교차 검사 기록,
  `numeric-runtime.json`이 든 `.validation/` 디렉터리입니다.
- 설치 시험: 부분마다 `installed-test-results-<k>-of-8`. 빌드한 배포물, `installed-tests.xml`,
  `shard.json`, `installed-origins.json`, `suite-file-hashes.json`, 라이선스 보고서, 교차 검사
  기록이 든 `.validation/` 디렉터리입니다.
- 설치 플랫폼: `installed-packages-<os>-<run_id>`. 모든 명령의 종료 코드와 로그,
  환경 정보, 체크섬, 설치 위치, JUnit XML, `numeric-runtime.json`이 들어 있습니다.
- 단위 배치 동등성(수동 실행 전용): `units-batch-equivalence-<os>-<run_id>`. 비교
  보고서(문서와 배열마다의 SHA-256 표와 적용한 규칙 항목), 문서 목록, 양쪽 기록의 manifest가
  들어 있습니다.

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

`Release` 워크플로(`.github/workflows/release.yml`)는 GitHub 릴리스가 게시되면 배포판
아홉 개를 PyPI에 올립니다. 태그만 push해서는 아무것도 올라가지 않고, 검증 워크플로가 이
워크플로를 시작하지도 않습니다. 작업은 순서대로 돕니다.

1. **gate**: 릴리스 커밋에서 `validate.yml`이 이미 성공했는지 봅니다. 시험을 다시 돌리지는
   않습니다. 그 전에 릴리스를 게시하면 여기서 실패하고 아무것도 올리지 않습니다. 검증이
   성공한 뒤 워크플로를 다시 실행하세요.
2. **build**: `tools/check_release_version.py --tag <tag>`, 이어서
   `OPENPHYSICS_DOCS_REF`를 그 태그로 두고 `tools/check_distributions.py --build-only`.
   **kernel**과 **assemble**: meshloom의 wheel을 그 sdist에서 릴리스 플랫폼마다(manylinux 2.17
   x86_64·aarch64, macOS 11 x86_64·arm64, Windows x64) 고정한 도구 모음과 maturin으로 빌드하고,
   `check_distributions.py --assemble`이 로컬 meshloom wheel을 이것들로 바꾼 뒤 하나씩 확인하고
   `SHA256SUMS`를 씁니다.
3. **install**: Linux·macOS·Windows에서 Python 3.12와 3.15로
   `tools/check_release_install.py --wheels`를 실행하며, 제3자 의존성은 PyPI에서 해석합니다.
   설치된 패키지의 smoke 검사이며 시험 전체가 아닙니다.
4. **publish**: `v*` 태그만 받는 GitHub 환경 `pypi`에서 PyPI trusted publishing(OIDC, 저장한
   토큰 없음)으로 올립니다. 의존 대상을 먼저, `openphysics`를 마지막에 올립니다. 각 PyPI
   프로젝트에는 owner `fieldalgo`, repository `openphysics`, workflow `release.yml`,
   environment `pypi`로 publisher가 등록돼 있어야 합니다.
5. **verify**: PyPI의 파일이 빌드한 파일과 SHA-256이 같아야 하고, PyPI에서 설치해도 같은
   플랫폼에서 3단계를 다시 통과해야 합니다.

손으로 실행하면(Actions → Release → Run workflow) dry run입니다. 고른 브랜치의 커밋에서
1–3단계만 돌고, 설명의 링크는 그 커밋을 가리키며, 아무것도 올리지 않습니다. 릴리스 순서:
버전 변경을 반영하고, 그 `main` 커밋의 검증을 기다리고, `main`에서 dry run을 돌린 뒤, 그
커밋에 `vX.Y.Z` 태그를 달고 그 태그로 GitHub 릴리스를 게시합니다.

각 패키지는 `packages/<name>`에서 빌드합니다. 저장소 루트는 배포물이 아니며,
`packages/openphysics`는 나머지 여덟 개 중 일곱 개를 (Studio·export·RII extra와 함께) 요구하고 `openphysics` 명령을 제공하는 메타 배포판입니다. `meshloom`은 아직 포함하지 않습니다. 패키지 하나만 빌드해
확인하려면:

```bash
python -m build --no-isolation --outdir .validation/simcase packages/simcase
python -m twine check --strict .validation/simcase/*
```

배포판 아홉 개는 하나의 버전으로 함께 릴리스합니다. 버전을 바꿀 때는 모든
`packages/<name>/pyproject.toml`과 각 import 패키지의 `__version__`, meshloom의 `Cargo.toml`을 바꾸고, 우리 배포판
사이의 의존성은 그 마이너 계열 안(0.0.2라면 `>=0.0.2,<0.1`, 0.1.x라면 `>=0.1.0,<0.2`)으로 두되 `simcase`는 내부
`physmat.kernels`와 `galerkin.kernels`를 부르므로 `physmat`과 `galerkin`을, `sipi`는 내부 `galerkin.kernels`를
부르므로 `galerkin`을 정확한 버전(`physmat==0.0.2`, `galerkin==0.0.2`)으로 고정하고,
`python tools/changelog.py --assemble`로 [변경 기록 조각](#변경-기록-조각)을 합친 뒤
[변경 기록](changelog.md)의 `[Unreleased]` 절을 `[X.Y.Z] - YYYY-MM-DD`로 바꿉니다.
릴리스에서는 `python tools/check_release_version.py --tag vX.Y.Z`가 이것을 모두 확인합니다
(`changelog.d/`에 조각이 남아 있으면 태그를 거부합니다).
또 패키지 README와 문서 페이지(변경 기록 제외)에 "아직 PyPI에 없다"는 문구가 남아 있으면
거부합니다. 패키지 README가 그대로 PyPI 설명이 되기 때문입니다. 필수 CI처럼 `--tag` 없이
돌리면 `[Unreleased]` 절과 그 문구를 받아들입니다. 0.x에서 안정적으로
유지하는 것도 변경 기록에 있습니다.

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
`tools/tests/test_readme_links.py`는 여덟 `setup.py`가 같은지, 패키지 설명에 상대 링크가 남지
않았는지 검사합니다. `meshloom`은 `setup.py`를 실행하지 않는 maturin으로 빌드하므로 README에
절대 링크만 쓰며, 같은 시험이 이를 확인합니다.

### 변경 기록 조각

변경은 `CHANGELOG.md`를 직접 고치지 않습니다. 커밋마다 변경 기록 항목을 조각 하나,
`changelog.d/<slug>.md`로 담아서 동시에 열린 PR이 `[Unreleased]` 맨 위에서 충돌하지 않게 합니다.
slug는 영문 소문자·숫자·하이픈으로 된 짧은 이름입니다(PR 번호는 필요 없습니다). `#` 제목은
Keep a Changelog 분류 하나(`Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`)이고,
두 절에는 [영어 변경 기록](../../../../CHANGELOG.md)과 [한국어 변경 기록](changelog.md)에 들어갈
그대로의 영어·한국어 항목을 쓰며, 링크는 그 페이지 기준 상대 경로입니다:

```markdown
# Fixed

## English

- `galerkin`: what changed and why, with the checks. [Shape derivatives](docs/packages/galerkin/shape_derivative.md).

## 한국어

- `galerkin`: 바뀐 내용과 이유, 검사. [형상 미분](packages/galerkin/shape_derivative.md).
```

`python tools/changelog.py --check`(CI에서 실행)가 이름, 분류, 두 절, 링크를 확인합니다.
버전 변경 PR은 `python tools/changelog.py --assemble`을 돌립니다. 이 명령은 분류마다 항목을
slug 순서로 두 페이지 `[Unreleased]`의 해당 `###` 하위 절 맨 위에 넣고(하위 절이 없으면 만들고)
조각을 지웁니다. `[Unreleased]`에 이미 있는 줄은 첫 `###` 하위 절 위에 분류 없이 놓인 항목을
포함해 그 자리에 그대로 둡니다. `changelog.d/`에는 조각만 둡니다.

## 저장값 시험 지원

`tests/_support/`는 배포하지 않는 모듈만 담습니다(하위 폴더 없음). 루트 pytest `pythonpath`로
[저장값 로더](stored-reference-values.md)를 찾으며 `tests/conftest.py`는 만들지 않습니다.
설치 시험은 루트 설정과 지원 모듈을 함께 복사하므로 도구 설치 없이 동일하게 검증합니다.

<a id="reference-import-checks"></a>

## 레퍼런스 import 검사

`tools/check_reference_zones.py`는 `git ls-files -z` 경로만 검사합니다. 새 파일은
검사 전에 stage해야 하며 추적하지 않는 가상환경은 제외됩니다. 모든 추적 `.py`는
packages·examples·tools·tests·studies·benchmarks 중 하나에 속해야 합니다.
모든 conftest와 시험 도우미는 항상 불러오는 구역이며 `test_*.py`/`*_test.py`만
시험 모듈입니다. 저장값 생성기는 `tests/<import>/reference_values/<tool>/generate_*.py`입니다.

import 문, 리터럴 `__import__`·`importlib.import_module`·`pytest.importorskip`·
`require_tool` 및 import 별칭을 인식합니다. 모듈 수준 try/if/class, 함수 기본값과
데코레이터는 즉시 실행입니다. 함수 본문과 정확한 `if __name__ == "__main__":` 본문은
늦은 실행으로 봅니다. 기본 로드 파일은 비허용형 도구를 즉시 불러오는 모듈을
즉시 import할 수 없습니다(저장소 루트·호출 파일 폴더에서 한 단계 해석).
각 레퍼런스 사용 파일은 목록의 `reference.imported_by` glob과 일치해야 합니다.

예를 들어 등록된 시험은 fixture 안에서 `require_tool("scikit-fem")`을 호출할 수
있습니다. 향후 제한 도구도 같은 늦은 호출을 따라야 하며 공용 fixture 모듈 또는
모듈 수준 try에 import를 넣으면 실패합니다. 검사기가 새 도구를 설치하지는 않습니다.
리터럴 구문 검사이므로 동적 이름 생성·별칭 재대입·함수 호출 실행·한 단계보다 긴
간접 연결은 해석하지 않으며 수동 검토가 필요합니다. 설치된 솔버 소스는 읽지 않습니다.

비시험 의존성·extra는 자사 패키지 의존 경로를 통해 시험 extra나 레퍼런스 도구에
도달할 수 없습니다. 비허용형 레퍼런스는 시험 extra를 포함한 모든 배포 의존성에서
금지됩니다. 환경 marker는 지원 환경 중 하나에서 도달 가능하다고 보수적으로 봅니다.
제3자 전이 의존 라이선스는 설치 메타데이터 검사로 계속 확인합니다. 메타 배포판은
Gmsh에 도달할 수 없습니다. 이 정적 검사는 Linux 소스 CI에서 필수이며 플랫폼 설치
job의 기존 라이선스 스캔 실행 조건은 유지됩니다.

이는 소스 정책 API이며 물리 솔버 API가 아니므로 물리 단위·경계조건은 없습니다.
저장 수치 단위와 비교 경계는 [저장 레퍼런스 값](stored-reference-values.md)을 따릅니다.
