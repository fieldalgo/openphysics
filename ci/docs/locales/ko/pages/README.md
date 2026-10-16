# 검증과 배포 검사

[English original](../../../README.md)

## main 검증 대기열

각 검증 워크플로의 `main` 실행은 workflow/ref별로 고정된 동시성 그룹을 사용하며
`queue: max`, `cancel-in-progress: false`로 설정됩니다. 같은 그룹에서는 한 번에
하나씩 실행하고, 새 push가 기존 대기를 교체하지 않도록 최대 100개 pending 실행을
보존합니다. 큐가 가득 차면 추가 실행은 취소될 수 있습니다. 처리 순서는 큐 진입
순서에 따르며 커밋 또는 push 순서를 보장하지 않습니다.

다른 ref는 `queue: single`을 사용하며 같은 ref의 새 실행이 이전 실행을 대체합니다.
서로 다른 검증 워크플로와 레포는 실행기 용량 내에서 병렬 실행할 수 있습니다.
이 설정이 슬롯을 예약하거나 PR의 실행 우선순위를 보장하지는 않습니다. 기존 실행은
시작할 때의 워크플로 설정을 유지합니다. 테스트 선택, 수치 기준, 필수 검사와 릴리스
검증은 바뀌지 않으며, 릴리스에는 정확한 대상 커밋의 검증 성공이 필요합니다.
이는 CI 실행 대기열이며 PR 병합 대기열과는 다릅니다.

## CI 정책과 설치 플랫폼 검증표

검증은 main push, Ready PR(`opened`, `synchronize`, `reopened`,
`ready_for_review`), 명시적 수동 dispatch에서 실행합니다. 기능 브랜치 push는
CI를 실행하지 않으며 Linux 집계 작업을 포함한 모든 검증 작업이 draft PR을
제외합니다. 변경 검토와 관련 검사를 마친 Ready PR은 자동 Rebase and merge를
사용할 수 있습니다. 필수 검사는 모두 유지합니다. main은 고정 workflow/ref
그룹과 `queue: max`, 취소 비활성화를 사용합니다. 다른 ref는 `queue: single`로
이전 실행을 대체합니다. 이것은 workflow 대기열이며 PR 병합 큐가 아닙니다.

| Workflow | 플랫폼 | 검증 범위 |
|---|---|---|
| `validate.yml` | Ubuntu 24.04, Python 3.12.14 | 전체 소스 시험, 일곱 배포판, 엄격한 archive/문서 검사, 설치 소비자와 Studio Node 검사 |
| `thermal-windows.yml` | Windows 2022, Python 3.12.10 | 기존 설치 열전도와 저장 소유권 회귀 시험 |
| `platform-install.yml` | Ubuntu 24.04, macOS 14, Windows 2022; Python 3.12.10 | 여섯 구현 sdist에서 wheel 재빌드; 새 격리 소비자 환경; 패키지 바이트·모듈 출처·번들 자산 및 공개 API/CLI/저장 smoke |

설치 검증표는 `ci/requirements-py312-windows-thermal.txt`의 기존 이식 가능한
정확 pin을 재사용합니다. 이 과거 파일명이 검증표를 Windows로 한정하지 않습니다.
system site packages 없는 새 venv에 의존성을 설치하고 직접 만든 wheel만
`--no-index --no-deps`로 설치한 뒤 checkout 밖에서 `python -I`로 실행합니다.
기존 열전도 폐형식·단위·저장 소비자, scalar slab/reference, Gmsh parser 시험의
수치 허용치를 유지합니다. 소비자 시험·예제·MSH fixture는 정확 checkout에서
복사하고 별도 hash를 기록합니다. 각 sdist에 시험 fixture가 포함된다는 주장은 아닙니다. 별도 공개 mesh smoke는 양의 요소 면적과 전체 단위
면적을 확인합니다. 이 검증표는 외부 Gmsh 실행, macOS/Windows 전체 회귀,
RII 다운로드, 브라우저 runtime을 검증했다고 주장하지 않으며 전체 Linux 수용을 보완합니다.

각 OS는 명령 종료값/로그, 환경 정보, archive checksum 12개, 패키지 바이트와
소비자 시험 hash, 설치 출처와 pytest JUnit을
`installed-packages-<os>-<run_id>` artifact로 올립니다. 로컬 또는 다른 실행기에서:

```bash
python -m pip install -r ci/requirements-py312-windows-thermal.txt
python -X utf8 ci/tools/check_platform_install.py
```

출력 디렉터리는 새 경로여야 합니다. 설정만으로 통과를 입증하지 않습니다.
수용을 주장하기 전에 정확 커밋의 세 OS 작업과 artifact를 확인합니다.
패키지 metadata 최소 버전과 별개로 Python 3.10/3.11은 이 CI 검증표 범위 밖입니다.

`platform-install.yml`은 `validate.yml`이 호출하는 재사용 workflow입니다.
기존 필수 `tests` 집계가 전체 Linux 수용과 설치 플랫폼의 모든 작업을 기다리며,
플랫폼 하나가 실패하거나 skip되면 집계도 통과하지 않습니다. 기존 보호 규칙의
검사 이름을 유지하면서 플랫폼 검사가 병합에 필수로 작용합니다. 명시적 수동
dispatch도 지원하지만 독립 수동 실행은 PR 검증을 대체하지 않습니다.

## 현재 checkout과 근거

이 페이지는 현재 checkout의 구현을 설명합니다. 명시된 과거 snapshot의 결과와 한계는 해당 버전에 적용됩니다. 다른 커밋의 검증 상태는 그 커밋의 CI 로그와 artifact에서 확인합니다.

기존 번역 기준은 `7259635a150106a7b98869e7f5a7aa8561ba8028`이며 아래 내용은 현재 검토 후보의 영문 변경과 동기화했습니다.

GitHub Actions의 Linux 패키지·좁은 Windows·설치 플랫폼 workflow는 main push·Ready PR·명시적 수동 dispatch에서 실행합니다. 정확한 실행·종료값·artifact를 확인해야 하며 활성화 자체가 수용을 뜻하지는 않습니다. 과거 Work cloud 결과는 원래 소스·환경·범위의 근거로 유지합니다.

루트 `validate.yml` workflow는 main push·Ready PR·수동 dispatch에서 실행됩니다.
Ubuntu 24.04의 CPython 3.12.14와 Node.js 24.19.0을 시험합니다. Python 3.10/3.11은 이 CI 검증 범위 밖이며
별도 설치 검증표가 세 운영체제를 다룹니다. 패키지 metadata는 여전히 Python >=3.10을
선언합니다. `requirements-py312-linux.txt`는 패키지 runtime 요구가 아니라 검증 도구와
전이 의존성을 고정합니다. pin을 의도적으로 검토·갱신하고 source·wheel 검사를 모두
다시 실행합니다.

반복 가능한 벡터 시간·메모리·profiling 명령은
[benchmark_vector.md](benchmark_vector.md)에 있습니다. 성능 측정은 수치 검사를
보완하며 CI 시간 gate가 아닙니다.

Python 3.12 가상환경을 활성화한 뒤 저장소 루트에서 실행하는 POSIX 셸용 Linux 검증 명령입니다. 이 Linux 의존성이 이식 가능한 플랫폼 검증표를 뜻하지는 않습니다.

```bash
python -m pip install -r ci/requirements-py312-linux.txt
python -m pip install --no-deps --no-build-isolation \
  -e packages/galerkin -e packages/galerkin-refsol -e packages/meshine \
  -e packages/gmshio -e packages/physmat -e packages/simcase
python -m pip check
export MPLBACKEND=Agg OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python ci/fetch_rii.py .validation-rii
export PHYSMAT_RII_PATH="$PWD/.validation-rii/database"
gmsh --version
python -m pytest -q -ra
node --test packages/simcase/tests/studio_vector.cjs packages/simcase/tests/studio_thermal.cjs packages/simcase/tests/thermal_simcase_independent_stale.cjs
python ci/check_distributions.py
```

Linux Gmsh에는 workflow가 설치하는 system library도 필요합니다. Gmsh 실행파일은
별도 프로세스이며 우리 배포판에 포함하지 않습니다.

## 고정 광학 데이터베이스

`rii-revision.txt`는
[polyanskiy/refractiveindex.info-database](https://github.com/polyanskiy/refractiveindex.info-database)의
전체 commit ID입니다. `fetch_rii.py`는 정확히 그 commit을 가져오고 dirty 상태나
다른 revision의 cache checkout을 거부합니다. pin은 검토된 변경에서 바꾸고, 갱신을
수용하기 전에 DB 시험 두 개를 모두 실행합니다. 데이터는 CC0 1.0 dedication이며
`LICENSE`를 참조합니다. 인용: M. N. Polyanskiy, *Refractiveindex.info database of optical constants*,
Scientific Data **11**, 94 (2024), https://doi.org/10.1038/s41597-023-02898-2.
데이터는 소스 트리 밖에 두고 release artifact에 포함하지 않습니다.

시험은 `PHYSMAT_RII_PATH`를 따릅니다. 명시적으로 설정했으나 유효하지 않은 경로이면
두 DB 시험이 실패하므로 CI가 조용히 skip하지 못합니다. 명시적 경로가 없으면 로컬
시험은 선택적 cached DB 동작을 유지합니다.

## 배포 검증

`check_distributions.py`는 빈 `openphysics` 이름 예약을 포함해 일곱 패키지를
각각 build합니다. 각 wheel은 고정 build 도구(`--no-isolation`)로 sdist에서
build합니다. `twine check --strict`로 metadata, LICENSE/NOTICE와 Studio 자산을
검사하고 artifact SHA256 checksum을 씁니다. sdist의 LICENSE/NOTICE·README·build
metadata·Studio 페이지도 검사하며, 일곱 wheel의 식별자·버전은 sdist와 같아야 합니다.
galerkin cavity solver 문서와 simcase cavity 문서·JSON 예제도 sdist에 존재하고
checkout 파일과 byte가 같아야 합니다. 누락되거나 오래된 문서·예제는 설치 wheel
시험 전에 검증을 실패시킵니다. simcase README가 연결하는 screenshot 두 개도
sdist에 있고 byte가 같아야 합니다. 이 사용자 문서들은 runtime wheel 자산이 아닙니다.
galerkin eigenspace 계약, 정적 탄성 계약 두 개와 영문 탄성 예제도 sdist에서 byte가
같아야 합니다. reference 모듈도 refsol sdist에서 byte 단위로 동일해야 합니다.
자동으로 패키징되는 Python 코드이므로 추가 refsol manifest 항목은 필요하지 않습니다.
독립 탄성 시험과 helper, eigenspace 시험 helper도 sdist에서 checkout과 같아야 합니다.
Setuptools가 시험 파일은 이미 포함하며 manifest는 원래 누락되는 helper 모듈을
명시적으로 포함합니다. 이들은 source 검증 자산이며 runtime wheel 모듈이 아닙니다.
포함된 모든 Markdown의 inline 상대 link/image 대상을 percent-decoded 경로와
fragment를 포함해 archive의 일반 파일과 대조합니다. 현재 package 문서는 공백 없는
inline target을 사용합니다. reference-style link, 그 문법을 넘는 Markdown parsing,
fragment anchor의 존재와 외부 URL 도달성은 이 검사 범위 밖입니다. package 간·root
링크는 알려진 통합 revision의 명시적 repository URL을 사용하며 network 접근이
필요합니다. 검사 통과가 완전한 오프라인 문서를
인증하지는 않습니다. wheel이나 단일 sdist는 monorepo checkout이 아니므로 editable
`packages/...` 설치 명령에는 저장소 루트가 필요합니다.

이후 checkout 밖의 임시 가상환경에 해당 wheel과 선언된 의존성만 고정 버전으로
설치하며, 선택적 Studio·test·RII·Gmsh extra도 포함합니다. import 위치, editable 설치
부재, 모든 CLI entry point, scalar slab run·저장 결과, 기존 Studio API·Gmsh 연결
시험을 검사합니다. 소스 `conftest.py`는 복사하지 않습니다. 전용
`test_cavity_wheel.py`는 cavity 기능을 갖춘 galerkin·simcase 후보도 요구합니다.
설치 wheel에서 공개 API 예제와 `cavity_box` CLI workflow를 재현하고,
`allow_pickle=False`로 JSON/NPZ SI metadata·field 복원, spectral-only 출력,
재사용한 출력 디렉터리·미지원 plotting의 안전한 거부를 검사하며 Studio가 3D 모델을
숨기고 거부하는지도 확인합니다. cavity API가 없으면 이 gate는 skip하지 않고 실패합니다.
이 consumer 검사는 수치 mesh 수렴이나 완전 cluster 수용 기준을 인증하지 않습니다.
그 기준은 별도 source·독립 검증 gate입니다. cavity 후보가 통합될 때까지 이 확장은
후보들과 이 CI 변경을 결합한 checkout에서 시험해야 합니다. 전체 source suite를
보완하지만 모든 physics 시험을 wheel에서 다시 실행하거나 browser layout을 검증하지는
않습니다.

추가 `test_multiphysics_wheel.py` consumer에는 설치된 `galerkin.elasticity`와
`refsol.elasticity`가 필요합니다. 직접 구한 단축 폐형식과 plane stress·plane strain을
대조하고, 구속하지 않은 강체 mode를 거부하며, 검증한 sdist에서 읽은 실제 영문 예제를
격리된 Python import로 실행합니다. 결정적인 비실수 위상 대조를 포함해 복소 벡터 solver
출력과 정확한 NPZ/JSON 보존도 검사합니다. 수렴·완전성 주장을 추가하거나 기존 수용
임계값을 바꾸지 않습니다. 모듈·예제가 없으면 skip하지 않고 실패합니다. 이 gate의 정적
탄성에는 simcase/Studio나 열 연성 연결이 없습니다.

artifact 기본 경로는 `.validation/dist/`입니다. 다른 위치는
`--output /absolute/empty/directory`로 지정합니다. 오래된 파일을 피하도록 비어 있지
않은 출력 경로는 거부합니다. CI는 실패한 뒤에도 artifact와 JUnit 보고서를 업로드합니다.
이는 검증 자산이지 공개 release가 아닙니다. 여기서 build 재현성은 입력 고정과 반복
가능한 검사를 뜻하며 머신 간 archive byte 동일성을 뜻하지 않습니다. source 시험이
시작됐고 job이 취소되지 않았다면 source 시험 단계가 실패해도 배포·Node 단계는 실행됩니다.
source 실패는 여전히 job 실패이며, 별도 package 증거로 실패한 physics gate를 숨겨서는
안 됩니다.

## Release 준비

오래된 중첩 standalone-repository publish workflow는 제거했습니다. GitHub는 루트
`.github/workflows/`의 workflow만 찾습니다. 여기의 workflow는 PyPI에 업로드하지
않고 release tag로 publication을 시작하지도 않습니다.

배포 전에 package·version을 선택하고 해당 version의 PyPI 존재 여부를 확인한 뒤,
clean checkout에서 검증합니다. 명시적으로 검토한 root publishing workflow·GitHub
환경을 위해 해당 PyPI 프로젝트의 trusted publisher를 설정해야 합니다. 각 패키지는
`packages/<name>`에서 build하며 저장소 루트는 배포판이 아닙니다. 이름 예약은
umbrella installer가 아닙니다.

고정 build 도구를 설치한 환경에서 단일 패키지 build-only 검사는 다음과 같습니다.

```bash
python -m build --no-isolation --outdir .validation/simcase packages/simcase
python -m twine check --strict .validation/simcase/*
```

version 변경, 소유권 확인, trusted-publisher 등록과 실제 publication은 별도 release
업무입니다. 검증 workflow는 repository contents 읽기 권한만 필요하며 OIDC upload
토큰을 요청하지 않습니다.

archive의 탄성 예제는 출력 반력·불균형 검사에 0이 아닌 적용 하중 벡터 norm을 힘
척도로 사용합니다. 총 평형 허용치는 상대 1e-9이고 성분 비교는 상대 1e-9와 무차원
1e-12의 영 성분 하한을 사용합니다. 따라서 수평 합력이 0일 때의 반올림을 절대 N/m
정확도 약속으로 다루지 않습니다. source 수렴·잔차와 독립 힘/모멘트/에너지 수용 gate는
별도로 유지합니다.

## 설치본의 처방 온도 기계 단계

`test_thermoelasticity_wheel.py`는 기존 설치 consumer 58개를 보완합니다. checker는
처방 온도 계약·영문 예제를 galerkin sdist에 포함하고, 자동 포함되는
`refsol/thermoelasticity.py`의 byte가 source와 같도록 요구합니다. 검증한 archive 예제를
checkout 밖에서 `python -I`로 실행합니다.

추가 consumer는 E=70 GPa, nu=0.3, alpha=12e-6/K, delta T=20 K에서 독립 작성한
원래 등방성 3D 법칙을 사용합니다. 자유 plane stress는 u=alpha*deltaT*(x,y),
응력 0·물리 에너지 0입니다. 자유 plane strain은 u=(1+nu)*alpha*deltaT*(x,y),
면내 응력 0, sigma_zz=-16.8 MPa이며 한 제곱미터 영역에서 물리 탄성 에너지는
2016 J/m입니다. 완전 구속한 균일 장으로 consistent 경계 반력·물리 에너지를 독립
검사합니다. 냉각, 음수·0 alpha, 0이 아닌 지지부의 일, 기준 온도 shift, 복사한 불변
snapshot, 오래된 기하·단위 metadata, 잘못된 Kelvin 데이터와 강체 mode도 추가 검사합니다.
오차 정규화에는 0이 아닌 eigenstrain이나 기계적 응력/힘/에너지 척도를 사용하며,
절대 Kelvin 온도나 계산한 영 에너지 답을 사용하지 않습니다.

이는 설치·계약 consumer이며 독립 수렴 수용이나 완전한 열→기계 workflow 검증이
아닙니다. API는 주어진 같은 mesh의 절점 P1 Kelvin 장을 받으며 열을 풀거나 열 결과를
자동 연결하거나 출처를 인증하거나 simcase/Studio를 추가하지 않습니다. 전용 독립
수용은 별도 gate입니다. 전용 독립 수용 문서·NumPy oracle·시험은 원문 그대로 포함하고
galerkin sdist에서 byte 단위로 같아야 합니다. 과거 후보·harness 실패 기록은 바꾸지
않습니다. 여섯 전용 구현/reference/test/doc/example blob은 원래 후보·제품 merge·이
release 결합에서 동일하며, 최종 결합 source CI는 통합 tree를 별도로 검증합니다.

## 설치본 정상 열전도·경계 traction (기존 gate)

무차원 힘 비교를 포함한 기존 consumer 37개는 바꾸지 않습니다.
`test_thermal_traction_wheel.py`는 설치 consumer 21개를 추가합니다. checker는
기존 탄성 예제와 함께 byte 검증한 sdist의 새 영문 예제 두 개를 복사하고 checkout 밖에서
`python -I`로 실행합니다. 새 계약·예제·독립 수용 helper/시험은 galerkin sdist에서
checkout과 byte가 같아야 합니다. 새 refsol 모듈 두 개도 refsol sdist와 같고 설치
환경에서 import되어야 합니다.

열 consumer는 Kelvin과 직접 slab/상수원 혼합 단열 폐형식을 사용합니다. q의 W/m^2,
열 하중·반력의 두께당 W/m, 외향 열량=-reaction, 상수·콜백 열원 일치, 상수 온도 offset,
잘못된 입력·nullspace의 명시적 거부를 검사합니다. 작은 8-to-16 mesh 구간 하나에서
독립 적분한 이차 폐형식과 대조해 기존 정칙해 P1 차수 여유를 검사합니다. 독립적인
여러 구간 source 수렴·구적 수용을 대체하지 않습니다. 열수지의 분모는 0일 수 있는
부호 포함 합이 아니라 하중·반력 절댓값의 합입니다. 척도가 0인 조건은 따로 검사합니다.

traction consumer는 두 plane 모델을 직접 단축·전단 식과 대조하고, consistent 선형
edge 하중, edge 반전에서 외향 콜백 법선, 처방 DOF에도 남는 적용 하중, 중복·내부 edge
거부와 None/빈 매핑 회귀를 검사합니다. 기계 평형에는 0이 아닌 힘 norm을, 에너지·work
비교에는 자체의 0이 아닌 에너지 척도를 사용합니다. 이 비교는 단위 변경 전반에 걸친
절대 N/m·W/m 정확도 하한을 약속하지 않습니다. 독립 source의 힘/모멘트/work·수렴·오류
주입 gate는 별도 요구로 남습니다. 이 배포 검사는 새 플랫폼 matrix·의존성·publication을
도입하지 않습니다.

독립 열 문서, JSON 수용 manifest, oracle와 시험도 필수 sdist 자산입니다. manifest는
후보 `aaf948ae38aa82907ca16ef7cdeed75dfa7484ba`의 과거 기록이며 후보·환경·실패 필드를
원문 그대로 유지합니다. recovery `3102c32874e89c300f21647291db57626c000982`와
과거 통합 `0a44797f73cf67bab14429c982144f0e0e4338aa` /
`6cdfa6ca40ac7b7313d3768e3b7ac59c71338e9f` tree의 여섯 thermal 구현·reference·문서·예제·원래 시험 blob만
검사한 후보와 동일합니다. 이후 열 확장은 별도 독립 수용과 Dirichlet 회귀가 필요하며
역사적 manifest는 바뀐 구현 blob을 인증하지 않습니다. 최종 결합 검증은 상호작용을 별도로
검사합니다. 과거 전체 환경 run의 699 passed / 9 failed / 9 skipped를 통과로
다시 분류하지 않습니다. 독립 보고된 설치 45개와 원래 쌍 84개는 각각의 범위입니다.

## 좁은 Windows 헤드리스 열전도 gate

`thermal-windows.yml`은 GitHub-hosted windows-2022의 Python 3.12.10을 정의합니다.
네 로컬 wheel(galerkin, meshine, physmat, simcase)을 빌드하고 index·의존성 해석 없이
consumer venv에 설치합니다. checkout 밖 `python -I`로 전용 열 문서 consumer와
선택된 저장 I/O 시험을 실행하도록 정의했습니다. API/CLI 저장, 수치 raw 출력,
기존 파일·디렉터리·끊어진 링크, 부분 실패, 파일·디렉터리 교체와 동시 소유권을 다룹니다.
실패는 skip하지 않습니다. consumer venv는 system-site-packages로 고정 job 의존성을
재사용하므로 clean-room 의존성 설치가 아닙니다.

Windows 요구는 Linux exact version의 최소 부분집합입니다. pytest/build 전이 의존성
`colorama==0.4.6`은 별도 pin이며 upstream tag의 pyproject와 LICENSE.txt에서
BSD-3-Clause를 확인했습니다. runtime 요구나 패키지 버전은 바꾸지 않았습니다.
Windows 전체 회귀·광학/Gmsh·다른 OS/Python 지원을 인증하지 않습니다.
hard-link 파일 pin 후보 `636a23a`는 같은 runner에서 설치 API·CLI·저장 36개와
source 기존 대상 보호 3개가 통과했습니다([실행](https://github.com/fieldalgo/openphysics/actions/runs/38858254797)).
기존 교체 fixture를 바꾸지 않고 통과했으며 이전 실패는 역사적 근거로 보존합니다.
Windows 전체·macOS 지원은 아닙니다. Windows 저장은 동일 볼륨 hard link를 지원하는
파일시스템과 임시 인접 pin 디렉터리에 대한 호출자의 독점 제어가 필요하며 미지원 시
명시적으로 실패합니다. [저장 계약](../../../../../packages/simcase/docs/locales/ko/pages/thermal_steady2d.md)을 참고하세요. Windows log/JUnit/
환경·네 wheel checksum은 별도 `windows-thermal-installed-and-io-<run_id>` artifact입니다.
Linux 전체 source, 일곱 sdist→wheel/strict/metadata/byte/link와 기존 88 consumer는
유지되며 Node는 shipped `studio_thermal.cjs`도 실행하도록 정의했습니다.

새 headless consumer는 독립 SI slab·부호 있는 혼합 열원 폐형식, 모서리 구속,
수치 version/units/shape와 검증 archive JSON 예제를 검사합니다. 유한요소 smoke의
오차 범위는 해석적 열원 곡률과 cell 크기에서 정하며 summary 자기비교가 아닙니다.
독립 수렴·소유권 수용을 대체하지 않습니다. 플랫폼 검증과 실패는 실제 exact 후보의
실행 근거로 판단해야 하며 workflow 존재만으로 추정하지 않습니다.

저장과 정리가 끝날 때까지 호출자가 출력 경로를 독점해야 합니다. 정리 전에 관측한
교체 보호는 시험하지만 소유권 검사와 unlink 사이의 외부 교체는 안전을 보장하지 않습니다.
적대적 파일시스템 경쟁과 원자적 rollback은 수용 범위 밖입니다. 이 동안 다른 writer가
출력을 바꾸면 안 됩니다. Windows 교체 fixture는 위 `636a23a` 좁은 gate에서 회복됐지만 소유권 계약이나 전체 플랫폼 지원 범위가 넓어진 것은 아닙니다. Actions는 활성화돼 있으며 후보마다 해당 실행 근거를 확인해야 합니다.

## 배포본의 독립 수용

docs/ 안의 패키지 개요 EN/KO 일곱 쌍과 수신한 한국어 안내는 필수 byte 자산입니다. 진입점 README는 영어로 유지합니다.
독립 외향 열유속/Robin 계약·예제·독립 보고/oracle/시험과 `refsol.thermal_boundary`를
원문 그대로 포함합니다. headless 독립 EN/KO 보고·oracle·시험·stale-state Node도
필수입니다. 현재 필수 byte 목록은 136개이며 headless 과도 추가 항목은 아래에서
설명합니다. 설치 시험은 기존 consumer 105개를
유지하고 원래 headless·Robin 독립 Python 수용 파일을 허용치 수정 없이 추가합니다.
각 실행의 실제 개수와 skip을 보고합니다. Node 명령은 기존 vector 8 + thermal guard 6 +
독립 stale guard 8 = 22개이며 서로 다른 범위를 물리 인증 숫자 하나로 합치지 않습니다.

현재 Robin 구현과 열 계약은 aaf에서 변경됐으므로 여섯 blob 동일성은 과거 0a/6cdf에만
해당합니다. 역사적 JSON과 동결 영어 수용 문서는 불변입니다. Robin은 별도 독립 수용과
Dirichlet 회귀가 연결됩니다. headless JSON은 여전히 flux/Robin을 거부하고 열 Studio UI나
자동 연성을 추가하지 않습니다. 배포 검증이 릴리스를 게시하거나 플랫폼 지원을 확대하지는 않습니다.

Work cloud는 현재 가용 Linux/Python 3.12.14, numpy 2.3.5, scipy 1.17.0으로 검증하며
보존 pinned CI 환경이 아닙니다. Gmsh와 명시적 RII database가 없으므로 실제 skip을
기록합니다. twine이 없어 strict 검사는 기존 도구가 가용해지지 않는 한 미실행입니다.
Linux 결과로 Windows 수용을 추정하지 않습니다. Actions는 활성화돼 있으므로 정확한 workflow 결과를 확인합니다.

## 명시적 workflow의 source 재현 자산

정상 열전도→기계단계 workflow 모듈·EN/KO 안내·영어 예제와 원 producer 시험
`test_thermal_mechanical_workflow.py`, `test_thermal_mechanical_workflow_physics.py`,
helper `thermal_mechanical_workflow_oracle.py`를 명시적 byte 검사 sdist 자산으로
포함합니다. 안내의 `packages/galerkin/...` 물리 명령은 저장소 루트용입니다. 풀어 놓은
galerkin sdist는 `tests/`와 `examples/`가 있는 패키지 루트이며 모노레포의
`packages/galerkin/` 구조가 아닙니다. helper 포함은 원시험의 import를 보존하지만
포함 자체가 새 시험 결과는 아닙니다.

설치 검증은 원 독립 수용 suite와 검증한 archive의 영어 예제를 사용합니다. 중복 물리
oracle을 추가하거나 모든 producer 사례를 반복하지 않습니다. source의 engine 의존성
guard는 패키지 tree 밖으로 무조건 복사하지 않습니다. `ENGINE` 경로가 실제 engine
모듈을 가리키지 않으면 빈 디렉터리 scan이 내용 없이 통과할 수 있습니다. source guard
실행·명시적 installed-ENGINE 확인·wheel module byte 검사는 서로 다른 범위입니다.

명시적 workflow의 독립 EN/KO 보고·원 oracle·시험은 원문 그대로 필수 source 자산입니다.
설치 검사는 기존 299개 사례를 유지하고 원래 90개 독립 workflow suite를 추가하며
물리 공식을 복제한 시험이나 gate 변경을 하지 않습니다. 실제 실행의 개수·실패·선택적
skip을 보고해야 합니다. 검증한 sdist의 영어 workflow 예제도 checkout 밖에서 설치
wheel의 `python -I`로 실행합니다. guard는 source에 두어 6개 시험이 실제 engine
파일을 scan합니다. 설치 module origin과 wheel module byte는 별도로 확인합니다.
이 배포 검사가 schema/CLI/Studio 지원이나 열역학적 완전 연성을 인증하지는 않습니다.

## 처방 온도 전체 표면하중의 배포 계약

공개 전 traction snapshot의 필수 byte 목록은 이전79개에 정확한 traction 구현·참조·안내·예제·producer·독립 자산13개를 더한92개였습니다. 공개 준비에서 한국어 README 일곱 개를 docs 개요 EN/KO 열네 페이지로 바꿔99개가 됐으며 과도 구현에서15개를 추가합니다. 원 독립 보고와 시험의 역사적 개수·실패는 그대로 유지합니다. 설치 suite는 기존389개 사례를 보존하고 원래 producer·참조·수렴 파일과 독립90개를 추가합니다. 계획한 합계가 아닌 실제 수집·실행 개수와 실패·선택적 skip을 보고해야 합니다. 원래 `python -I` 전용 consumer4개와 실제 archive 영어 예제는 별도로 실행합니다. 복사한 engine guard가 빈 디렉터리를 scan하면 안 되며 source guard6·설치 origin/module byte 검사는 분리합니다.

새 Python API는 처방 온도장 기계단계에 전체 물리 응력 `sigma*n`을 적용합니다. scalar pressure 전용 키워드·로컬 프레임·follower API는 없지만 고정 기준 형상에서 전역 Pa `-p*normal` callback은 유효합니다. 단방향 heat workflow와 JSON/CLI/Studio는 바뀌지 않습니다. producer 재현 명령은 저장소 루트용이며 풀어 놓은 sdist에는 패키지 내부 `tests/`와 `examples/` 경로가 있습니다. 원 시험 파일과 필요한 oracle·참조 source를 명시적으로 배포합니다.

개별 후보의90/90/전용4/관련208/wrong17 실측이 결합 whole·설치 결과를 입증하지는 않습니다. 독립 보고는 원 whole1385통과/CLI환경7실패/16skip/+하위9와 target7회복을 별개 근거로 보존합니다. 새 결과에는 정확 source·실제 archive·실패·선택적 skip을 명시해야 합니다. GitHub Actions는 활성화돼 있으며 새 workflow 결과와 이 과거 실측은 구분해야 합니다. Linux 결과로 Windows 수용을 입증할 수 없고 core metadata 파싱이 미가용 twine strict 검사를 대체하지 않습니다.

두 workflow는 문서를 포함한 모든 main 대상 PR의 필수 검사입니다. 검사명은
`tests`(항상 실행하는 Linux 완료 job)와 `windows-py312-thermal`입니다.
초록 PR은 GitHub Rebase and merge로 반영하며 새 main SHA를 기록하고
릴리스 전에 main의 필수 검사 성공을 확인합니다. 뒤 push가 main 실행을 취소하지
않으며 기능 브랜치·PR 실행은 대체될 수 있습니다. 태그는 이 workflow를 실행하지
않고 두 workflow 모두 패키지를 게시하지 않습니다.
## 과도 열전도 배포 검사

이 checkout에는 과도 열전도 구현과 검증 gate가 있습니다. 전체 물리·독립·배포
수용에는 정확한 현재 CI 근거가 필요하며 구현만으로 검증된 릴리스가 되지 않습니다.
[구현 계약](../../../../../packages/galerkin/docs/locales/ko/pages/transient_heat.md)과
[독립 보고](../../../../../packages/galerkin/docs/locales/ko/pages/transient_heat_independent_validation.md)는
생산 담당의 소형 source70개 기록과 남은 gate를 구분합니다.

엔진만 추가한 단계의 필수 byte 목록114개는 공개 baseline99개와 과도15개였습니다. EN/KO여섯 페이지,
영어 수렴 예제, 새 runtime모듈 두 개, 원생산/참조시험과 독립
oracle/cases/pytest-wrapper/consumer 네 파일을 포함합니다. 기존 metadata/license,
archive링크·역사JSON·traction수용 검사는 유지합니다. 새 runtime두모듈은 wheelbyte도
같아야 합니다. 격리 설치 preflight가 venvorigin·sourceSHA256을 확인하고
artifact곁에 `transient-module-origins.json`을 기록합니다.

기존 설치pytest파일은 바꾸지 않고 과도 원생산/참조시험 두 파일을 추가합니다.
독립 발견wrapper는 source재현자산으로 보존하며 설치pytest에 중복복사하지 않습니다.
대신 검증sdist에서 원standaloneconsumer·oracle/cases를 읽어 `--suite all`로 한 번
실행하고 동결 PDE·companion·구적gate를 포함합니다. 이어 archive의 전체 영어 수렴
프로그램을 `python -I`로 실행합니다. `core`나 짧은 smoke로 이를 대체하지 않습니다.
모든 단계는 순차이며 실패 뒤 단계는 미실행으로 두고 원 exit/log를 보존합니다.

```python
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path.cwd()  # Run this script from the repository root.
env = os.environ.copy()
for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
             "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS"):
    env[name] = "1"
output = Path(tempfile.mkdtemp(prefix="openphysics-transient-")) / "distributions"
print("Validation output:", output)
subprocess.run([sys.executable, "ci/check_distributions.py", "--output", str(output)], cwd=root, env=env, check=True)
```

비어 있는 본인 출력경로와 문서의 검증 의존성을 사용합니다. 이는 재현명령이며 후보
build나통과 근거가 아닙니다. pytestJUnit·독립unittest사례/subtest·archive프로그램
결과·nativeprerequisite를 별도 보고합니다. 기존 traction541사례와 전용consumer4는
baseline근거이며 새 과도 count가 아닙니다. 엔진만 추가한 단계에는 과도JSON/CLI와
저장이 없었습니다. 현재 headless API·JSON/CLI·저장 이력은 아래에서 설명합니다.
과도 Studio·Robin/flux입력·자동열–기계연결은 아직 지원하지 않습니다. 수용 전에 CI와 cloud실험의
정확source근거가 필요하며 Linux결과가 Windows지원을 입증하지 않습니다.

## Headless 과도 배포 검증

Linux job은 작은 영역·일반 상태 엔진 회귀, 과도 문서·실행·독립 수용·Studio 거부·이식 가능한 저장 시험을
먼저 실행하며 `transient-preflight.xml`에 JUnit 결과를 남깁니다. 실패하면
비용이 큰 전체 시험 전에 해당 job을 실패로 끝냅니다. 부분 시험 통과나 수용
요건을 건너뛴 성공으로 처리하지 않습니다. 성공하면 아래의 전체 source·설치
시험과 기존 수치 gate를 모두 이어서 실행합니다.

helper는 기존 engine 독립 `--suite all` PDE와 archive의 전체 수렴 예제를 유지합니다.
추가로 simcase 원문 자산20개(runtime/dispatch·소유권 모듈, 사용안내 두 페이지,
JSON 예제, 생산/계약/Studio/Windows 시험, 독립 수용 파일 네 개)와 원래의
작은 영역·일반 상태 엔진 회귀 파일 두 개를 요구하여 현재 필수 자산은136개입니다.
두 회귀 파일은 검증된 sdist에서 가져와 설치 pytest에서도 실행합니다.
이는 포함 gate이며 실측 통과 수가 아닙니다.

새 runtime 두 모듈과 기존 dispatch/schema/소유권 모듈은 wheel byte를 대조하고
checkout 밖에서 `python -I`로 import합니다. `installed-module-hashes.json`과
`transient-module-origins.json`에 기대 hash와 실제 설치 origin을 기록합니다.
원 계약·runtime·Studio·저장 시험은 검증된 simcase sdist에서 설치 pytest로
추출합니다. 원 독립 headless consumer와 oracle/cases는 별도로 추출하고
`--expected-installed-root` 및 `--expected-module-hashes`로 실행합니다.
그 unittest 개수는 설치 pytest 및 engine 독립17개와 분리합니다.
검증된 JSON 예제는 격리 CLI validate/run으로 소비하며 새 출력 경로를 사용합니다.
source 시험은 저장소 루트의 전체 pytest 명령에 포함됩니다.

좁은 Windows job은 기존 설치 선택에 `test_transient_headless_windows.py`의
12개를 모두 추가하고, 기존 steady 설치 및 source 대상보호 시험을 유지합니다.
소비자 전에 명시적인 설치 모듈 origin/hash를 기록합니다. 이 검사는 전체
Windows 과도 PDE나 macOS 수용이 아니며 정확 run의 실패·skip·개수·artifact를 확인해야 합니다.

build/consumer 성공 뒤 Linux workflow는 소비자를 반복하지 않고 보존 archive bytes를
독립적으로 감사합니다.

```text
python ci/tools/audit_distribution_artifacts.py --artifacts .validation/dist --report .validation/distribution-audit.json
```

보고 경로는 기존에 없어야 합니다. 이 감사는 checkout의 필수 자산/link 검사를 재사용하고
14개 checksum 및 지정 runtime wheel bytes를 확인합니다. twine strict·설치 실행·
독립 물리 또는 정확 source commit 검증을 대체하지 않습니다. 구성된 명령이나
과거 baseline을 새 후보의 통과로 표시하지 않습니다.

## 정상 열경계 계약·독립 배포 gate

게시된 경계 helper·원시험, 사용안내와 독립보고의 EN/KO 페이지, 원 독립 수용
네 파일을 필수 byte 자산으로 요구합니다. 독립 설치 소비자가 정확한 identity를
요구하므로 기존 steady engine 모듈도 필수 자산과 wheel byte 검사에 추가합니다.
현재 명세는153개로, P1기존136+경계계약2+문서/독립자산8+steady원문1+schema/runtime/예제/platform자산6입니다.
이는 구성 개수이며 통과 수가 아닙니다.

별도 정상 열경계 preflight는 원 계약·schema·runtime·독립·저장/platform·Studio source entry point를 기존 P1 preflight와
전체 suite 전에 실행합니다. 실패하면 job이 실패하고 뒤 단계는 미실행입니다.
preflight 성공이 전체 suite를 대체하지 않습니다. 필수 완료 검사와 main 실행
보존 규칙은 그대로입니다.

정상 열경계 선행 검사는 기존 `test_thermal.py`와
`test_thermal_simcase_independent_validation.py` 소비자도 실행합니다. 저장 시험의
이름과 `save_fields`는 해석 전에 설정합니다. 완료된 결과의 문서를 바꾸면 해석 시
포착한 입력과 달라져 거절되기 때문입니다. 동시 저장 시험의 단일 승자·완결된 파일
검사는 유지하며, 비유한 metadata 시험은 무관한 문서 변경이 아니라 비유한 값 때문에
실패하는지 확인합니다.

원 독립 oracle/cases/consumer는 검증한 simcase sdist에서 추출해 checkout 밖에서
`python -I`, `--expected-installed-root`, `--expected-module-hashes`로 실행합니다.
원 계약·schema·runtime·저장/platform·Studio 시험도 설치 pytest로 소비합니다. hash 명세에는 steady consumer가 요구하는
여섯 identity가 모두 있으며, 기존 transient·dispatch를 포함한 runtime 모듈은13개입니다.
standalone unittest·설치 pytest·preflight·전체 source 개수는 분리합니다.
기존 transient 독립17/headless9/전체 archive 수렴과 Windows 회귀는 유지합니다.

이 연결에는 경계 기능을 갖춘 결합 schema/runtime 후보가 필요합니다. 게시된 문서
초안이나 정의된 시험이 현재 API/CLI·build·설치·플랫폼 성공을 인증하지 않습니다.
schema/runtime 시험·thermal_boundary.json·platform 시험은 정확 게시 경로를 읽고 연결했으며
미게시 경로를 요구하지 않습니다. 검증 JSON 예제는 격리 설치 CLI validate/run으로 새 출력에 소비합니다. 정확 결합 CI와 artifact를 확인해야 합니다.
위 보존 artifact 감사 명령은 수치 소비자를 반복하지 않고 이 명세에도 적용됩니다.
패키지 게시는 하지 않습니다.

Node source gate에는 `studio_steady_boundary.cjs`도 추가하며 원문 byte를 simcase sdist에서
요구합니다. 이는 source UI 검증이며 별도 설치 Node 실행을 주장하지 않습니다.
Windows 설치 선택에는 기존 모든 선택 사례와 함께 standalone
`test_steady_boundary_platform.py` 전체를 포함합니다. 기존 Windows origin probe에
steady 경계 identity 두 개를 추가하여 총11모듈을 확인합니다.
별도 source 대상보호 단계는 동일 platform 파일의 기존 대상보호 세 사례를 소비합니다.
기존 source 보호 단계도 유지하며 새 로그/JUnit은
`windows-steady-boundary-source-target.log`,
`windows-steady-boundary-source-target-tests.xml`로 분리합니다.
실제 개수와 skip은 정확 CI에서 확인해야 하며 새 의존성이나 플랫폼 지원을 뜻하지 않습니다.

## 정상열 Studio 배포·브라우저 검사

checker는 simcase sdist에 정확한 Studio adapter, 페이지/thermal JavaScript,
원 HTTP·수용·lifecycle 시험 세 파일, 독립 fixture, Node script와 사용법·독립보고
EN/KO 두 쌍을 요구합니다. Python module과 static resource는 wheel에서 source와
byte가 같아야 하며 설치 module hash와 `studio-resource-origins.json`은 격리 venv도
검사합니다. 원시험은 검증한 archive에서 source conftest 없이 추출합니다. 독립
fixture가 사용하는 P2 steady-boundary cases/oracle 원문도 같은 archive에 있어야
합니다. 수용 전 해당 기능과 결합해야 하며 배포 전용 branch가 생산 의존성을
제공하는 것은 아닙니다. 기존 engine all17·전체 수렴·headless·Windows gate를
제거하지 않습니다.

Linux preflight는 `studio-thermal-preflight.xml`을 기록하며 실패는 전체 수용 전의
실패입니다. source Node에는 실제 `studio_steady_thermal.cjs`를 추가합니다.
브라우저 수용은 별도입니다. 검증한 wheel 환경 안에서
`ci/tools/studio_thermal_browser.mjs`가 본인 격리 uvicorn 서버를 시작하고,
which/version으로 찾은 기존 Chrome/Chromium에 Node24 내장 WebSocket/fetch
CDP를 사용합니다. npm/Python/browser 다운로드를 추가하지 않습니다. 작은 실제
모델로 Apply JSON·Validate·Run·온도/flux·Results/Mesh·dirty 입력의 stale run
거절을 조작합니다. 보이는 canvas CSS/backing 크기, console 예외, PNG, origin,
환경과 본인 subprocess exit는 `dist/studio-browser/`에 남깁니다. 브라우저 부재는
unavailable과 nonzero exit로 기록하며 passing mock이나 skip으로 숨기지 않습니다.

dirty 입력 검사는 폐기된 크기 0 canvas backing store를 빈 상태로 인정하며
빈 영역에 getImageData를 호출하지 않습니다. 숨겨진 동안과 보이는 Results 탭으로
돌아온 뒤 모두 결과·hover 소유권 부재, 열 제어 숨김, Run 비활성화를 검사합니다.
검사 도구가 canvas를 직접 비우거나 크기를 바꾸지 않으며 dirty-results.png에
복귀 상태를 남깁니다. 정상 결과 표시 단계는 계속 양수 크기와 실제 픽셀을 요구합니다.

검증 성공 뒤 Linux source 서버 관측을 한 번 수행합니다.

```text
python ci/tools/profile_studio_thermal.py --source-root "$GITHUB_WORKSPACE" --expected-commit "$GITHUB_SHA" --output .validation/studio-resource-observation
```

각각 새 본인 서버 process에서 n2/32/100 공개 API·실제 HTTP 구간, 실제
capture_result/encode_json hooks, result 열 번 읽기, encoded bytes, tracemalloc과
RSS, 추가 job admission/oldest terminal 회수, 서버 종료를 측정합니다. hook 시간은
중첩되므로 합산하지 않습니다. TTL300s는 최대 보관이며 최소 보장이 아닙니다.
회수/만료 job은 자동 재실행 없이404입니다. run_enabled는 설정된 공개 API 가용성이고
candidate-unmeasured 자원 정책과 별개입니다. 고정 workload와 공유 runner 측정은
관측이며 용량·성능 인증이 아닙니다. 가짜 물리나 limit patch를 사용하지 않습니다.
기존 always-upload 단계가 partial 보고도 보존합니다. 설정된 명령은 exact 실행의
완료 근거가 아니므로 실제 CI exit·count·artifact를 보고해야 합니다. 브라우저,
수치 독립 수용, source 자원 관측, Windows는 별도 수용 범위입니다.


## 과도 Studio 배포 및 수치 원자료

과도 Studio preflight는 게시된 producer HTTP·독립수용·수명 시험을 전체 source
앞에서 실행합니다. preflight 실패는 job 실패이며, 실행되지 않은 후속 단계를
수용 근거로 취급하지 않습니다. 독립 fixture와 기존 headless cases/oracle은
byte 검산한 simcase sdist에서 격리 설치 pytest 전에 추출합니다. SHA256은
`dist/transient-studio-consumer-assets.json`에 보존합니다. shipped 과도 CJS는
기존 source Node 스크립트들과 실행하고, byte 검산한 설치 static을 대상으로
steady CJS와 함께 실행합니다. Node fixture는 물리·설치 Python·실제 브라우저
수용을 대신하지 않습니다.

시험이 출력한 성공 수치 진단 JSON도 실패 출력뿐 아니라 실제로 남겨야 합니다.
과도 preflight와 기존 설치 pytest 호출 모두 다음 옵션을 사용하며, 같은 시험을
두 번 실행하지 않습니다.

```text
-o junit_logging=all -o junit_log_passing_tests=true
```

always-upload되는 `studio-transient-preflight.xml`과 `dist/wheel-tests.xml`은
성공 testcase의 captured stdout을 `system-out`에 보존하며 해당하는 log/stderr도
남깁니다. 원 XML과 hash를 보존하고 JSON 수치를 반올림하거나 허용치를 바꾸지
않고 읽습니다. 실제 testcase·subtest·suite 보고 수를 구분하고 failure/error/skip
요소를 검사합니다. 설정만으로 수치 case의 실행·통과를 주장하지 않습니다.
전체 source·기존 installed·독립 all-suite/full-convergence·필수 플랫폼 gate는
그대로 유지합니다.


설치 browser 검사는 검산한 archive의 `transient_thermal_uniform.json`도 실제
shipped 과도 페이지에서 소비합니다. 저장된 최종/최초/비균일 중간 index, T와
qx/qy/magnitude의 현재 frame raw 범위, 명시적 유계 H/V page의 표시 원값·단위,
Mesh/Results 가시성을 검사합니다. 실제 진행 중 frame 요청은 비동기 성공/finally가
게시되기 전에 dirty JSON으로 무효화합니다. 사용자가 명시적으로 두 번째 실행한
뒤 browser 내부 offline 음성 대조로 늦은 transport error/finally도 검사하며 응답
본문이나 물리를 합성하지 않습니다. offline 상태는 finally에서 복구합니다. 이
음성 대조를 성공한 실제 HTTP solve/read 근거와 구분해 보고합니다.
`browser-report.json`은 과도 frame/history/raw label·transport 실패·hidden/visible
무효화와 기존 소유 process 정리를 보존합니다. `transient-dirty-results.png`와
`transient-error-dirty-results.png`는 각각 늦은 read 뒤 빈 visible 결과를 남깁니다.
기존 steady browser 검사도 필수로 유지합니다. 설정된 시나리오는 exact CI에서
실행해야 하며 구문 검사나 Node fixture가 native-browser 수용은 아닙니다.


## 과도 Studio 자원 workload 산출물

기존 steady 자원 관측이 성공한 뒤, Linux는 같은 job-success 조건으로 정확한
과도 wrapper를 한 번 실행합니다.

```text
python ci/tools/run_transient_resource_workloads.py --source-root "$GITHUB_WORKSPACE" --expected-commit "$GITHUB_SHA" --output .validation/transient-resource-observation
```

기존 `.validation/` always-upload가
`transient-resource-observation/workload-summary.json`, 각 workload stdout/stderr,
생성 입력 문서와 각 `*-observation/instrumented-report.json` 및 원 HTTP 근거를
보존합니다. small·medium·near-raw-candidate workload는 각각 새 process를 사용합니다.
near workload는 over-budget actor도 전달하여 solve 전 413 거절을 요구하고,
완료 capture에서는 공개 getter 13개를 각각 정확히 한 번 읽었는지 검사합니다.
실패·부분 단계와 원 exit를 보존하고, 앞선 실패 뒤 없는 단계를 성공 측정으로
취급하지 않습니다. 이는 계측 workload 관측이며 물리 수용·최대 용량·RSS 상한·
누수 증명·전용 성능 기준선이 아닙니다. 정확 source commit·세 exit·getter 횟수·
원응답·계상 보고를 source/설치/browser/플랫폼 gate와 구분해 검토합니다.
이 step은 별도 CI 실행을 만들지 않으며 기존 steady 관측을 그대로 보존합니다.

과도 dirty 수용은 늦은 성공·transport 오류 read 이후 hidden/visible 복귀 네 경로에서 status가 정확히 `validate current transient JSON`인지도 요구합니다. 픽셀이 비워져도 이전 reading/result-ready 상태가 남아 있으면 실패합니다.
