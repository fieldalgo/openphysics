# 개발과 검증

[English](../../../development.md) | **한국어**

개발 환경을 만들고, CI가 돌리는 검사를 직접 실행하고, CI 결과를 읽는 방법입니다.
브랜치·리뷰·릴리스 흐름은 [기여 안내](contributing.md)에 있습니다. 기능별 수용 기준과
근거는 각 기능의 계약·검증 문서에 있으며 [문서 색인](index.md)에서 찾을 수 있습니다.

## 환경

CI는 Ubuntu 24.04에서 Python 3.12.14와 Node.js 24.19.0을 고정해 사용합니다. 저장소
루트에서 Python 3.12 가상환경을 켠 상태로:

```bash
python -m pip install -r ci/requirements-py312-linux.txt
python -m pip install --no-deps --no-build-isolation \
  -e packages/galerkin -e packages/galerkin-refsol -e packages/meshine \
  -e packages/gmshio -e packages/physmat -e packages/simcase
python -m pip check
```

`ci/requirements-py312-linux.txt`는 검증 도구와 그 하위 의존성을 고정한 것이며,
패키지의 실행 의존성이 아닙니다. 고정 버전은 리뷰를 거친 변경에서 의도적으로 바꾸고,
소스 검사와 배포 검사를 다시 실행합니다. 패키지 메타데이터는 Python >=3.10을
선언하지만 Python 3.10·3.11은 CI에서 시험하지 않습니다.

항상 저장소 루트에서 실행합니다. `packages/` 안에서 Python을 실행하면 같은 이름의
디렉터리가 설치된 모듈을 가릴 수 있습니다.

선택 도구와 데이터:

- **Gmsh**: 메시 생성에는 PATH의 `gmsh`가 필요합니다(Linux는 워크플로가 설치하는
  시스템 라이브러리도 필요). 별도 프로세스이며 배포물에 포함하지 않습니다.
- **refractiveindex.info 데이터베이스**: `ci/rii-revision.txt`가
  [polyanskiy/refractiveindex.info-database](https://github.com/polyanskiy/refractiveindex.info-database)의
  전체 커밋 ID를 고정합니다. `python ci/fetch_rii.py <dir>`는 정확히 그 커밋을 받고,
  수정됐거나 다른 커밋인 캐시는 거부합니다. `PHYSMAT_RII_PATH=<dir>/database`를
  설정합니다. 명시적으로 설정한 경로가 잘못되면 두 데이터베이스 시험은 건너뛰지 않고
  실패합니다. 데이터는 CC0 1.0이며 소스 트리 밖에 두고 배포하지 않습니다. 인용:
  M. N. Polyanskiy, *Refractiveindex.info database of optical constants*,
  Scientific Data **11**, 94 (2024), https://doi.org/10.1038/s41597-023-02898-2.
- **Chrome 또는 Chromium**: 설치 Studio 브라우저 검사는 이미 설치된 브라우저를
  사용합니다. 찾지 못하면 검사가 실패하며, 건너뛰지 않습니다.

## 검사 실행

```bash
export MPLBACKEND=Agg OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python -m pytest -q -ra                    # 전체 소스 시험
node --test packages/simcase/tests/*.cjs   # Studio JavaScript 검사
python ci/check_distributions.py           # 모든 패키지 빌드·검사·설치
python ci/check_licenses.py                # 설치된 라이선스를 검토 목록과 대조
python ci/check_markdown_links.py          # 모든 Markdown 파일의 상대 링크와 #앵커
```

빠르게 반복할 때는 바꾼 부분과 관련된 시험만 돌리고 전체 시험은 CI에 맡깁니다.
`slow` 표시 시험(메시 수렴 연구)은 전체 실행에 포함되며, 로컬에서는
`-m "not slow"`로 뺄 수 있습니다. 일부만 통과한 결과가 CI를 대신하지는 않습니다.

CI 스크립트의 출력 디렉터리는 새것이거나 비어 있어야 하므로, 이전 실행의 결과가
섞이지 않습니다. `check_distributions.py`는 `--output`으로 다른 디렉터리를 주지 않으면
`.validation/dist/`에 씁니다.

설치 패키지 검사는 깨끗한 Python 3.12 환경이면 어느 OS에서나 실행됩니다.

```bash
python -m pip install -r ci/requirements-py312-windows-thermal.txt
python -X utf8 ci/tools/check_platform_install.py
```

requirements 파일 이름은 예전 이름이며 Windows 전용이라는 뜻이 아닙니다.

## CI가 돌리는 것

`Validate packages` 워크플로(`.github/workflows/validate.yml`)는 main push, Ready PR,
수동 실행에서 돕니다. 브랜치 push와 draft PR에서는 돌지 않습니다. 세 부분이 병렬로
실행됩니다.

| Job | 플랫폼 | 검사 내용 |
|---|---|---|
| `linux-py312` | Ubuntu 24.04 | Markdown 링크 검사와 빠른 사전 검사 묶음 뒤 고정 RII 데이터베이스로 전체 소스 시험; 배포물 일곱 개; Studio Node 검사; Studio 자원 관측 1회 |
| `blas-kernels` | Ubuntu 24.04, job 두 개 | 수치에 민감한 추적·고유공간·광섬유 기준 시험을 OpenBLAS 커널 두 개로 강제해 실행 |
| `installed-platforms` | Ubuntu 24.04, macOS 14, Windows 2022 | 패키지 여섯 개를 sdist에서 wheel로 빌드해 checkout 밖 새 환경에서 시험 |

필수 검사는 **`tests`** 하나입니다. 세 부분이 모두 성공해야 통과하며, 하나라도
실패·취소·건너뜀이면 실패합니다. 문서만 바꾼 변경도 이 검사가 필요합니다.

**Linux job.** 라이선스 검사 뒤 Markdown 링크 검사가 돕니다. 저장소에서 추적하는 Markdown 파일의 모든 상대
링크와 `#앵커`가 풀려야 합니다(외부 URL은 가져오지 않습니다). 사전 검사 묶음(정상 경계, 과도 문서, 정상·과도 Studio, 과도 열-역학)을
이어서 돌려서 계약이 깨지면 몇 분 안에 실패합니다. 그다음 전체 시험이 모든 것을 다시
돌립니다. 소스 시험이 실패해도 배포 검사와 Node 검사는 근거를 남기려고 계속 돌지만,
job은 실패로 남습니다. 보통 16~22분 걸립니다. 45분 제한은 멈춘 실행을 끊기 위한
것이며, 호스트 러너 속도가 실행마다 다르기 때문에 여유를 둡니다.

**배포 검사** (`ci/check_distributions.py`). 패키지 일곱 개(빈 `openphysics` 이름
예약 포함)를 고정 빌드 도구로 빌드하며, 각 wheel은 자기 sdist에서 빌드합니다.
`twine check --strict`로 메타데이터를 확인하고, 모든 sdist·wheel에 패키지의 LICENSE와 NOTICE가 그대로 들어 있는지, Studio 자산, 검사기의
필수 목록에 있는 모든 파일이 sdist에 있고 바이트가 같은지 확인합니다. 압축본 안의
상대 Markdown 링크는 실제 파일을 가리켜야 하며, 외부 URL은 열어 보지 않습니다.
이어서 wheel을 checkout 밖 새 환경에 설치하고 공개 API·CLI·저장 파일, 포함된 예제,
독립 수용 소비자 시험으로 확인합니다. `python -I`로 실행해 checkout이 섞이지 않게
합니다. 설치된 환경은 `ci/check_licenses.py`를 통과해야 합니다. Studio 브라우저 검사는 Chrome에서 작은 실제 모델을 돌립니다. 마지막으로
`ci/tools/audit_distribution_artifacts.py`가 보관된 압축본의 체크섬과 wheel 바이트를
다시 확인합니다.

**라이선스** (`ci/check_licenses.py`). 시험 전에 고정 검증 환경을, 이후 새로 설치한
환경마다 `ci/third_party_licenses.json`의 검토 목록과 대조합니다. 정책과 전체 목록은
[제3자 소프트웨어](third-party.md)에 있습니다.

**설치 플랫폼** (`ci/tools/check_platform_install.py`). OS마다 설치된 라이선스, 패키지 바이트, 설치된
모듈 위치, 포함 자산, 공개 API·CLI·저장 간단 시험, 열 저장/I-O 견고성 시험(부분 실패
정리, 동시 저장, 기존 대상 보호), source 대상 보호 fixture 두 개를 확인합니다. 설치
수용 검사이며 macOS나 Windows 전체 회귀 시험은 아닙니다.

**자원 관측.** Linux 실행이 통과하면 정상·과도 Studio 서버를 고정 작업량으로 한 번
측정합니다. 관측값이며 성능 기준이 아닙니다. 솔버 시간 측정과 프로파일링 명령은
[벡터](benchmark_vector.md)·[공동](benchmark_cavity.md) 벤치마크 안내에 있습니다.

**대기열.** main 실행은 워크플로마다 하나의 동시성 그룹을 `queue: max`로 공유하며,
새 push가 와도 취소되지 않습니다. 다른 ref는 `queue: single`이라 새 push가 이전
실행을 대체합니다.

## 결과 읽기

각 job은 실패해도 artifact를 올립니다.

- Linux: `distributions-and-test-results`. 단계별 JUnit XML, 배포물 체크섬과 보고서,
  `numeric-runtime.json`이 든 `.validation/` 디렉터리입니다.
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

- `ci/tools/report_numeric_runtime.py`가 job마다 CPU 기종, OpenBLAS 커널,
  `numpy.show_runtime()`을 기록합니다(`numeric-runtime.json`). macOS arm64는
  Accelerate를 쓰므로 OpenBLAS 커널이 표시되지 않습니다.
- `blas-kernels`는 `OPENBLAS_CORETYPE=Haswell`(AVX2, AMD Zen에서도 쓰는 커널)과
  `Sandybridge`(AVX)를 강제합니다. 먼저 강제한 커널이 실제로 쓰이는지 확인하므로,
  다른 커널로 넘어가 조용히 통과할 수 없습니다. 로컬 재현:

  ```bash
  OPENBLAS_CORETYPE=Sandybridge python -m pytest -q -m "not slow" <test files>
  ```

시험은 마지막 비트 반올림에 기대지 않게 씁니다. 반올림 오차보다 충분히 큰 명시적
허용치로 비교하고, 반올림이 닿을 수 있는 경계에서 정확히 비교하지 않습니다.

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
`ci/test_readme_links.py`는 일곱 `setup.py`가 같은지, 패키지 설명에 상대 링크가 남지
않았는지 검사합니다.
