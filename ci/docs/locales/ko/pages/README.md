# 검증과 배포 검사

[English original](../../../README.md)

기존 번역 기준은 `7259635a150106a7b98869e7f5a7aa8561ba8028`이며 아래 내용은 현재 검토 후보의 영문 변경과 동기화했습니다.

2026-10-16 오너 승인으로 GitHub Actions를 활성화했습니다. 기존 Linux 패키지·좁은 Windows workflow는 push·pull request·수동 dispatch에서 사용할 수 있습니다. 정확한 실행·종료값·artifact를 확인해야 하며 활성화 자체가 수용을 뜻하지는 않습니다. 과거 Work cloud 결과는 원래 소스·환경·범위의 근거로 유지합니다.

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

한국어 package README 일곱 개와 수신한 전체 한국어 안내는 필수 byte 자산입니다.
독립 외향 열유속/Robin 계약·예제·독립 보고/oracle/시험과 `refsol.thermal_boundary`를
원문 그대로 포함합니다. headless 독립 EN/KO 보고·oracle·시험·stale-state Node도
필수입니다. 현재 필수 byte 목록은 92개입니다. 설치 시험은 기존 consumer 105개를
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

필수 byte 목록은 기존79개에 정확한 traction 구현·참조·안내·예제·producer·독립 자산13개를 더한92개입니다. 원 독립 보고와 시험의 역사적 개수·실패는 그대로 유지합니다. 설치 suite는 기존389개 사례를 보존하고 원래 producer·참조·수렴 파일과 독립90개를 추가합니다. 계획한 합계가 아닌 실제 수집·실행 개수와 실패·선택적 skip을 보고해야 합니다. 원래 `python -I` 전용 consumer4개와 실제 archive 영어 예제는 별도로 실행합니다. 복사한 engine guard가 빈 디렉터리를 scan하면 안 되며 source guard6·설치 origin/module byte 검사는 분리합니다.

새 Python API는 처방 온도장 기계단계에 전체 물리 응력 `sigma*n`을 적용합니다. scalar pressure 전용 키워드·로컬 프레임·follower API는 없지만 고정 기준 형상에서 전역 Pa `-p*normal` callback은 유효합니다. 단방향 heat workflow와 JSON/CLI/Studio는 바뀌지 않습니다. producer 재현 명령은 저장소 루트용이며 풀어 놓은 sdist에는 패키지 내부 `tests/`와 `examples/` 경로가 있습니다. 원 시험 파일과 필요한 oracle·참조 source를 명시적으로 배포합니다.

개별 후보의90/90/전용4/관련208/wrong17 실측이 결합 whole·설치 결과를 입증하지는 않습니다. 독립 보고는 원 whole1385통과/CLI환경7실패/16skip/+하위9와 target7회복을 별개 근거로 보존합니다. 새 결과에는 정확 source·실제 archive·실패·선택적 skip을 명시해야 합니다. GitHub Actions는 활성화돼 있으며 새 workflow 결과와 이 과거 실측은 구분해야 합니다. Linux 결과로 Windows 수용을 입증할 수 없고 core metadata 파싱이 미가용 twine strict 검사를 대체하지 않습니다.

두 workflow는 문서를 포함한 모든 main 대상 PR의 필수 검사입니다. 검사명은
`tests`(항상 실행하는 Linux 완료 job)와 `windows-py312-thermal`입니다.
초록 PR은 GitHub Rebase and merge로 반영하며 새 main SHA를 기록하고
릴리스 전에 main의 필수 검사 성공을 확인합니다. 뒤 push가 main 실행을 취소하지
않으며 기능 브랜치·PR 실행은 대체될 수 있습니다. 태그는 이 workflow를 실행하지
않고 두 workflow 모두 패키지를 게시하지 않습니다.
