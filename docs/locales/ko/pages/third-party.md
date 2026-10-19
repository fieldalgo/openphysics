# 제3자 소프트웨어·데이터·참고 자료

[English](../../../third-party.md) | **한국어**

OpenPhysics의 코드와 문서는 Apache-2.0입니다([LICENSE](../../../../LICENSE),
[NOTICE](../../../../NOTICE)). 이 문서는 저장소가 쓰는 제3자 구성 요소를 모두 나열하고,
각각을 어떻게 쓰는지와 어떤 조건인지 적습니다. Apache-2.0은 이들의 라이선스를 바꾸지
않습니다.

기계가 읽는 목록은 [`ci/third_party_licenses.json`](../../../../ci/third_party_licenses.json)입니다.
`ci/check_licenses.py`가 검증 환경마다 설치된 메타데이터와 이 목록을 대조합니다
([자동 검사](#자동-검사) 참고).

## 쓰는 방식

| 방식 | 뜻 |
|---|---|
| runtime | 패키지의 기본 의존성. 실행 중 import함. pip로 따로 설치되며 함께 묶어 배포하지 않음 |
| optional | 시험이 아닌 extra(`simcase[studio]`, `physmat[rii]`, 그림 extra). runtime과 같은 조건 |
| test | 시험 전용 extra(`test`, 레퍼런스 도구 비교용 `crosscheck`)나 시험 전용 도구. 사용자에게는 필요 없음 |
| tool | CI 빌드·패키징·업로드 도구. 패키지 코드가 import하지 않음 |
| external process | 따로 설치한 프로그램을 별도 프로세스로 실행하고 출력 파일만 읽음 |
| data | 저장소에 옮겨 적거나 내려받는 수치·기록 |

정책: runtime·optional 구성 요소는 허용형 라이선스만 씁니다. LGPL·MPL은 수정 없이 따로
설치되는 시험·도구 구성 요소에만 허용합니다. GPL 프로그램은 별도 프로세스로만 쓰며
import·링크·번들하지 않고 소스를 복사하지 않습니다. AGPL은 쓰지 않습니다. 저장소에
복사해 넣은 제3자 소스 코드는 없습니다.

## Python 배포판

버전 범위는 패키지 요구 조건입니다. CI의 정확한 버전은
`ci/requirements-py312-linux.txt`(Linux)와
`ci/requirements-py312-windows-thermal.txt`(설치 플랫폼 검사)에 고정합니다.

### Runtime

| 배포판 | 요구하는 패키지(범위) | SPDX | 비고 |
|---|---|---|---|
| `numpy` | openphysics 외 전부(`>=1.24`) | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | 휠에 OpenBLAS(BSD-3-Clause)와 Linux·Windows에서 GCC Fortran 런타임(GPL-3.0-or-later WITH GCC-exception-3.1, 이 사용을 허용함)이 들어 있음 |
| `scipy` | galerkin, galerkin-refsol, meshine, physmat, simcase(`>=1.10`) | BSD-3-Clause | numpy와 같은 번들 라이브러리 |
| `shapely` | simcase(`>=2.0`) | BSD-3-Clause | 휠에 GEOS 공유 라이브러리(LGPL-2.1-only)가 들어 있고 수정 없이 동적으로 로드됨. OpenPhysics는 이를 재배포하지 않음 |
| `matplotlib` | simcase(범위 없음), 그림 extra(`>=3.7`) | LicenseRef-Matplotlib | PSF 기반 허용형 라이선스 |
| `contourpy`, `cycler`, `kiwisolver` | matplotlib | BSD-3-Clause | |
| `fonttools`, `pyparsing`, `six` | matplotlib | MIT | |
| `pillow` | matplotlib | MIT-CMU | 허용형 조건의 이미지 코덱을 포함함 |
| `packaging` | matplotlib | Apache-2.0 OR BSD-2-Clause | |
| `python-dateutil` | matplotlib | Apache-2.0 AND BSD-3-Clause | |

### 선택 extra

| 배포판 | Extra | SPDX |
|---|---|---|
| `fastapi` | `simcase[studio]`(`>=0.100`) | MIT |
| `uvicorn` | `simcase[studio]`(`>=0.20`) | BSD-3-Clause |
| `starlette`, `idna` | fastapi | BSD-3-Clause |
| `click` | uvicorn | BSD-3-Clause |
| `pydantic`, `pydantic-core`, `annotated-types`, `annotated-doc`, `typing-inspection`, `anyio`, `h11` | fastapi, uvicorn | MIT |
| `typing-extensions` | fastapi, pydantic | PSF-2.0 |
| `opentelemetry-api` | fastapi | Apache-2.0 |
| `pyyaml` | `physmat[rii]` | MIT |

### 시험

| 배포판 | 경로 | SPDX | 비고 |
|---|---|---|---|
| `pytest`, `iniconfig`, `pluggy` | `test` extra | MIT | |
| `pygments` | pytest | BSD-2-Clause | |
| `colorama` | pytest, click(Windows만) | BSD-3-Clause | |
| `httpx`, `httpcore` | `simcase[test]` | BSD-3-Clause | |
| `certifi` | httpx, requests | MPL-2.0 | 수정하지 않은 CA 묶음. 시험·도구 전용 |

자체 패키지의 test extra는 `galerkin-refsol`, `meshine`, `gmshio`도 요구합니다. 모두 이
저장소의 Apache-2.0 패키지입니다.

### CI 도구

| 배포판 | 용도 | SPDX |
|---|---|---|
| `build`, `pyproject-hooks`, `wheel`, `setuptools`, `pip` | 배포판 빌드·설치 | MIT |
| `twine`, `id`, `readme-renderer`, `requests`, `requests-toolbelt`, `rfc3986` | `twine check --strict` | Apache-2.0 |
| `docutils` | twine의 README 렌더링 | LicenseRef-Public-Domain AND BSD-2-Clause AND 0BSD(GPL 분류자는 휠에 없는 파일을 가리킴) |
| `nh3`, `rich`, `markdown-it-py`, `mdurl`, `keyring`, `jaraco-classes`, `jaraco-context`, `jaraco-functools`, `more-itertools`, `jeepney`, `urllib3`, `charset-normalizer` | twine 의존성 | MIT |
| `cffi` | cryptography | MIT-0 |
| `cryptography` | secretstorage | Apache-2.0 OR BSD-3-Clause |
| `secretstorage`, `pycparser` | keyring, cffi | BSD-3-Clause |

## 외부 프로그램

| 프로그램 | 라이선스 | 쓰는 방식 |
|---|---|---|
| Gmsh([`gmsh`](https://gmsh.info) 실행 파일, `gmshio[gmsh]`와 CI의 pip 배포판 `gmsh`) | GPL-2.0-or-later | `gmshio`가 `.geo` 스크립트를 쓰고 `gmsh`를 별도 프로세스로 실행한 뒤, 공개된 형식 설명으로 새로 작성한 파서로 `.msh` 파일을 읽음. import·번들하지 않음. [gmshio NOTICE](../../../../packages/gmshio/NOTICE) 참고 |
| Node.js | MIT | CI에서 Studio JavaScript 검사 실행 |
| Chrome 또는 Chromium | Chrome 약관 / BSD-3-Clause | CI Studio 브라우저 검사에 이미 설치된 브라우저 사용 |
| GitHub Actions `actions/checkout`, `actions/setup-python`, `actions/setup-node`, `actions/upload-artifact` | MIT | CI 전용. 커밋으로 고정 |

## 데이터와 출판 수치

| 출처 | 조건 | 쓰는 방식 |
|---|---|---|
| [refractiveindex.info 데이터베이스](https://github.com/polyanskiy/refractiveindex.info-database) | CC0-1.0 | 일부 표와 분산 계수를 physmat(`physmat/_tables.py`, `physmat/library.py`)에 포함. CI는 `ci/rii-revision.txt`에 고정한 커밋을 내려받으며 그 사본은 배포하지 않음. 인용과 기록별 출처: [physmat NOTICE](../../../../packages/physmat/NOTICE) |
| G. R. Hadley, J. Lightwave Technol. 20(7), 1210 (2002) | 출판된 사실 | `galerkin-refsol`의 benchmark 값. femwell(GPL-3.0)과 함께 공개된 표와 대조했고 숫자만 옮겼으며 코드·글은 옮기지 않음. [galerkin-refsol NOTICE](../../../../packages/galerkin-refsol/NOTICE) 참고 |
| handbook 유형의 열·기계 상수 | 근사 예제 입력 | 인증된 측정값이 아님. [자산 출처](assets.md) 참고 |

## 비교용 레퍼런스 도구

다른 유한요소 도구를 돌린 비교 결과는 해석해 수용 기준과 따로 기록합니다. 두 도구가
일치한다는 사실을 수렴 근거로 쓰지 않습니다. 허용형 도구는 시험 전용 extra로 설치해 위
목록에 적습니다. GPL 도구는 쓰더라도 이 저장소 밖에서 따로 설치한 수정 없는 실행 파일로만
돌리며, 소스는 읽거나 복사하지 않고 수치 결과만 보고합니다.

## 자동 검사

```bash
python ci/check_licenses.py --report .validation/licenses.json
```

설치된 메타데이터를 `importlib.metadata`로 읽으므로 라이선스 검사 도구를 따로 설치하지
않습니다. 다음 경우에 실패합니다.

- 설치된 배포판에 검토된 목록 항목이 없을 때
- 설치된 메타데이터가 다른 SPDX 식을 선언하거나, 항목에 없는 copyleft 라이선스를
  언급할 때(항목에 이유를 적은 경우 제외)
- 자체 패키지의 runtime·optional 의존성이 허용형이 아닐 때
- 약한 copyleft 시험·도구 의존성에 `test_only` 표시가 없을 때
- GPL 배포판이 external process 항목이 아니거나, 기본 runtime 의존성이거나, 자체 코드가
  import할 때
- AGPL이나 SSPL이 어디에든 있을 때
- 자체 패키지가 Apache-2.0을 선언하지 않을 때
- 이 문서나 영어 원문이 목록의 항목을 모두 나열하지 않을 때

CI는 고정된 Linux 환경, 설치한 휠만 담은 새 환경, 그리고 Linux·macOS·Windows 설치 플랫폼
검사에서 이 검사를 돌립니다. 제3자 휠 안에 묶인 네이티브 라이브러리(shapely의 GEOS 등)는
메타데이터에 드러나지 않으므로 위 비고에서 직접 검토합니다.

의존성을 추가할 때: upstream 저장소의 LICENSE 파일로 라이선스를 확인하고, SPDX 식과 출처
URL을 목록에 항목으로 추가하고, 이 문서와 영어 원문에 행을 추가하며, 번들하거나 복사하면
패키지 NOTICE에도 적습니다.
