# 검증과 배포 검사

[English original](../../../README.md)

번역 기준은 `7259635a150106a7b98869e7f5a7aa8561ba8028`의 영문 문서입니다.

루트 `validate.yml` workflow는 push·pull request·수동 dispatch에서 실행됩니다.
Ubuntu 24.04의 CPython 3.12.14와 Node.js 24.19.0을 시험합니다. Python 3.10/3.11과
다른 운영체제는 이 CI 검증 범위 밖이며 패키지 metadata는 여전히 Python >=3.10을
선언합니다. `requirements-py312-linux.txt`는 패키지 runtime 요구가 아니라 검증 도구와
전이 의존성을 고정합니다. pin을 의도적으로 검토·갱신하고 source·wheel 검사를 모두
다시 실행합니다.

반복 가능한 벡터 시간·메모리·profiling 명령은
[benchmark_vector.md](benchmark_vector.md)에 있습니다. 성능 측정은 수치 검사를
보완하며 CI 시간 gate가 아닙니다.

Python 3.12 가상환경을 활성화한 뒤 저장소 루트에서 실행합니다.

```bash
python -m pip install -r ci/requirements-py312-linux.txt
python -m pip install --no-deps --no-build-isolation \
  -e packages/galerkin -e packages/galerkin-refsol -e packages/meshine \
  -e packages/gmshio -e packages/physmat -e packages/simcase
python -m pip check
export MPLBACKEND=Agg OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python ci/fetch_rii.py /tmp/openphysics-rii
export PHYSMAT_RII_PATH=/tmp/openphysics-rii/database
gmsh --version
python -m pytest -q -ra
node --test packages/simcase/tests/studio_vector.cjs
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
링크는 알려진 통합 revision의 명시적 repository URL을 사용하며, 저장소가 private인
동안 network 접근과 repository 권한이 필요합니다. 검사 통과가 완전한 오프라인 문서를
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
이 package 결합의 여섯 thermal 구현·reference·문서·예제·원래 시험 blob은 검사한 후보와
동일합니다. 따라서 바뀌지 않은 열 구현의 수용 증거를 보존하며 최종 결합 CI가 상호작용을
별도 검사합니다. 과거 전체 환경 run의 699 passed / 9 failed / 9 skipped를 통과로
다시 분류하지 않습니다. 독립 보고된 설치 45개와 원래 쌍 84개 결과의 범위는 해당
manifest에 각각 따로 있습니다.
