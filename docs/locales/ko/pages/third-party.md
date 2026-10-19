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
| optional | 시험이 아닌 extra(`simcase[studio]`, `simcase[export]`, `physmat[rii]`, 그림 extra). 그 안의 Python 라이브러리는 이 저장소에서 runtime 조건을 따름. extra가 설치하는 GPL 프로그램(`gmshio[gmsh]`)은 대신 external process로 다룸 |
| test | 시험 전용 extra(`test`, 레퍼런스 도구 비교용 `crosscheck`)나 시험 전용 도구. 사용자에게는 필요 없음 |
| tool | CI 빌드·패키징·업로드 도구. 패키지 코드가 import하지 않음 |
| external process | 따로 설치한 프로그램을 별도 프로세스로 실행하고 출력 파일만 읽음. 그 프로그램에 Python 모듈이 있어도 패키지 코드는 import하지 않음 |
| bundled | 제3자 휠을 올린 쪽이 그 휠 안에 넣어 배포하는 네이티브 라이브러리, 정적으로 링크된 코드, 글꼴, 런타임 파일 |
| data | 저장소에 옮겨 적거나 내려받는 수치·기록 |

## 라이선스 정책

프로젝트 정책이며 법률 자문이 아닙니다. 라이선스 조건은 세 층으로 판단합니다.

1. **이 저장소가 만들고·복사하고·빌드하고·링크하고·배포하는 것**: 소스 트리, 패키지의
   sdist·wheel, CI 산출물. 모두 Apache-2.0인 자체 저작물입니다. 저장소에 복사해 넣은 제3자
   소스 코드는 없고, 컴파일된 코드를 담은 패키지도 없으며, 배포판은 의존성을 선언만 하고
   담지 않습니다.
2. **의존성 하나하나, 그 배포판이 스스로 선언한 라이선스로**: 기본 의존성, extra, 시험·도구
   의존성, 전이 의존성 포함.
   - 허용형 라이선스가 기본입니다.
   - 약한 copyleft(LGPL·MPL·CeCILL-C)는 많아야 선택 extra, 시험 extra, 도구까지 허용하며,
     수정하지 않은 채 따로 설치되게 합니다. 기본 의존성으로는 쓰지 않고, OpenPhysics는 그것을
     수정·복사·정적 링크하지 않으며 자체 코드에서 직접 로드하지도 않습니다(ctypes, cffi, 컴파일된
     확장). 이 저장소는 지금 이보다 엄격합니다. runtime·optional 의존성은 모두 허용형이고
     [자동 검사](#자동-검사)가 그렇게 유지하며, 시험 extra `crosscheck`는 허용형 레퍼런스 도구만
     설치합니다.
   - GPL 프로그램은 별도 프로세스로만 씁니다. 외부 레퍼런스 도구로 돌리거나, 선택 extra의
     백엔드(`gmshio[gmsh]`)로 돌립니다. import·링크·번들하지 않고 소스를 읽거나 복사하지
     않습니다.
   - AGPL과 다른 네트워크 copyleft 라이선스(SSPL, EUPL, OSL 등)는 패키지, 그 CI, 호스팅
     서비스 어디에도 쓰지 않습니다. 쓰더라도 비공개 연구 저장소에서 따로 실행하는 레퍼런스
     도구로만 씁니다.
   - 런타임 예외가 붙은 라이선스(`GPL-3.0-or-later WITH GCC-exception-3.1` 등)는 예외 문구의
     조건으로 판단하고 그 조건을 기록합니다. 이중 라이선스는 기대는 쪽을 기록합니다(FreeType:
     FreeType License, FTL).
3. **따로 설치되는 제3자 휠 안에 묶인 구성 요소**: 휠을 올린 쪽이 휠 안에 넣은 네이티브
   라이브러리, 정적으로 링크된 코드, 글꼴, 재배포용 런타임. 그쪽 배포물의 일부이고 그쪽 고지가
   다룹니다. 금지하지 않고 [묶인 구성 요소](#묶인-구성-요소)에 기록·검토합니다. OpenPhysics는
   이들을 수정·다시 빌드·다시 링크·복사·재배포하지 않고, 패키지 코드는 그 구성 요소를 가진
   패키지의 공개 Python API로만 닿습니다. 기록된 예외는 CI 진단 도구
   `ci/tools/report_numeric_runtime.py` 하나입니다. 이 도구는 작업 로그에 커널 이름을 남기려고
   numpy에 묶인 OpenBLAS를 ctypes로 로드합니다(Linux에서는 묶인 GCC 런타임과 libquadmath도 함께
   로드됨). 패키지 코드가 아니고, 텍스트 보고서만 CI 결과와 함께 남깁니다. 묶인 copyleft
   라이브러리의 API를
   노출하는 것이 주된 목적인 휠(얇은 바인딩)은 OpenPhysics가 그 라이브러리에 직접 의존하는
   것으로 보고 검토합니다.

서버에서 소프트웨어를 실행하는 것은 배포가 아니지만, 브라우저로 보내는 JavaScript, CSS, 글꼴,
WebAssembly는 배포입니다. OpenPhysics는 제3자 바이너리를 배포하지 않습니다. 제3자 바이너리를
담은 것(컨테이너·가상 머신 이미지, 설치본, frozen 앱, wheelhouse나 휠 미러, 브라우저 기반
Python 사이트, 고객 납품물)을 배포하기 전에는 재배포 체크리스트와 법률 검토가 필요합니다.
라이선스 전문과 고지, LGPL·GPL 구성 요소의 대응 소스나 서면 제공 약속, 바꿔 끼울 수 있는 LGPL
라이브러리, 수정과 디버깅용 역설계를 허용하는 이용 조건을 갖춰야 합니다.

## Python 배포판

버전 범위는 패키지 요구 조건입니다. CI의 정확한 버전은
`ci/requirements-py312-linux.txt`(Linux)와
`ci/requirements-py312-windows-thermal.txt`(설치 플랫폼 검사)에 고정합니다.

### Runtime

| 배포판 | 요구하는 패키지(범위) | SPDX | 비고 |
|---|---|---|---|
| `numpy` | openphysics 외 전부(`>=1.24`) | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | 휠에 OpenBLAS와 GCC 런타임 라이브러리가 들어 있고, 그 가운데 libquadmath는 LGPL-2.1-or-later(GCC 예외 대상 아님). Linux와 macOS 14 미만에서는 별도 공유 라이브러리, macOS 14 이상에서는 없음(Apple Accelerate 사용), Windows에서는 GCC 런타임이 정적으로 링크된 OpenBLAS DLL과 `msvcp140.dll`. [묶인 구성 요소](#묶인-구성-요소) 참고 |
| `scipy` | galerkin, galerkin-refsol, meshine, physmat, simcase(`>=1.10`) | BSD-3-Clause | 휠에 libquadmath(LGPL-2.1-or-later)를 포함한 GCC 런타임 라이브러리가 Linux와 모든 macOS에서 공유 라이브러리로 들어 있고, macOS 14 이상을 빼면 OpenBLAS도 들어 있음. Windows에서는 GCC 런타임이 OpenBLAS DLL과 확장 모듈 하나에 정적으로 들어 있음. Qhull은 정적 링크. [묶인 구성 요소](#묶인-구성-요소) 참고 |
| `shapely` | simcase(`>=2.0`) | BSD-3-Clause | 휠에 GEOS(LGPL-2.1)가 Linux·macOS·Windows 모두 별도 공유 라이브러리로 들어 있고 shapely 자신의 확장 모듈이 동적으로 로드함. Windows 휠에는 `msvcp140.dll`도 있음. OpenPhysics는 shapely의 Python API만 부르고 어느 것도 재배포하지 않음. [묶인 구성 요소](#묶인-구성-요소) 참고 |
| `matplotlib` | simcase(범위 없음), 그림 extra(`>=3.7`) | LicenseRef-Matplotlib | PSF 기반 허용형 라이선스. 확장 모듈에 FreeType(FTL OR GPL-2.0-or-later, FTL로 사용), HarfBuzz, libraqm, SheenBidi, Qhull이 정적으로 들어 있고, 데이터 파일에 OFL-1.1·BaKoMa·Bitstream Vera 조건의 글꼴이 있음 |
| `contourpy`, `cycler`, `kiwisolver` | matplotlib | BSD-3-Clause | |
| `fonttools`, `pyparsing`, `six` | matplotlib | MIT | |
| `pillow` | matplotlib | MIT-CMU | 허용형 조건의 이미지·글꼴·압축 라이브러리를 포함함(FreeType: FTL OR GPL-2.0-or-later, FTL로 사용). Linux·macOS에서는 공유 라이브러리, Windows에서는 정적 링크 |
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
| `meshio` | `simcase[export]`(`>=5.3,<6`) | MIT |
| `rich`, `markdown-it-py`, `mdurl` (and `pygments`, BSD-2-Clause) | meshio | MIT |

`pydantic-core`는 MIT, Apache-2.0, Unlicense OR MIT, Unicode-3.0(icu_normalizer) 조건의 Rust
crate를 정적으로 링크하며, 휠에는 자기 MIT 라이선스만 들어 있습니다. `pyyaml`은 libyaml(MIT)을
정적으로 포함합니다.

### 시험

| 배포판 | 경로 | SPDX | 비고 |
|---|---|---|---|
| `pytest`, `iniconfig`, `pluggy` | `test` extra | MIT | |
| `pygments` | pytest | BSD-2-Clause | |
| `colorama` | pytest, click(Windows만) | BSD-3-Clause | |
| `httpx`, `httpcore` | `simcase[test]` | BSD-3-Clause | |
| `certifi` | httpx, requests | MPL-2.0 | CA 묶음을 수정 없이 사용(certifi의 묶음 자체가 Mozilla 묶음에서 파생된 것). 시험·도구 전용 |
| `scikit-fem` | `galerkin[crosscheck]`(`>=12,<13`) | BSD-3-Clause | [솔버 비교](reference-comparisons.md)용 레퍼런스 도구. 순수 Python이며 numpy와 scipy만 필요 |

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

pip는 certifi의 CA 묶음(MPL-2.0) 사본을 자기 안에 넣어 두고 수정 없이 씁니다.

## 묶인 구성 요소

CI에 고정한 제3자 휠이 자기 안에 넣어 배포하는 것입니다(정책 3층). 조사 기준:
`ci/requirements-py312-linux.txt`에 고정한 버전의 CPython 3.12 휠, CI가 시험하는 플랫폼(manylinux
x86_64, macOS 14 arm64, Windows amd64). macOS 14 미만용 numpy·scipy 휠과 numpy·scipy·shapely·
matplotlib·pillow의 macOS x86_64 휠도 목록을 확인했습니다. 정적 링크 여부는 Linux, macOS arm64,
Windows 바이너리를 실행하지 않고 읽어 확인했습니다. 다른 플랫폼, Python 버전, 패키지 버전의 휠은
다를 수 있습니다.

조사하지 않은 것: Linux aarch64, musllinux, Windows arm64, CPython 3.10·3.11·3.13(패키지는
Python 3.10 이상을 받음), 선언한 범위 안의 고정 버전 외 버전.

| 휠 | 구성 요소 | 라이선스(SPDX) | 플랫폼과 링크 방식 |
|---|---|---|---|
| `numpy` | OpenBLAS(LAPACK 포함) | BSD-3-Clause, BSD-3-Clause-Open-MPI | Linux(`numpy.libs/`)와 macOS 14 미만(`numpy/.dylibs/`)은 공유 라이브러리, Windows는 DLL(`numpy.libs/`). macOS 14 이상은 Apple Accelerate를 써서 들어 있지 않음 |
| | GCC 런타임: libgfortran, macOS에서는 libgcc_s도 | GPL-3.0-or-later WITH GCC-exception-3.1 | Linux와 macOS 14 미만은 공유 라이브러리. Windows는 휠 고지대로 OpenBLAS DLL에 정적으로 링크 |
| | libquadmath | LGPL-2.1-or-later. GCC 예외 대상 아님 | Linux와 macOS 14 미만은 공유 라이브러리. 휠 고지는 라이선스 이름과 URL만 적고 LGPL 전문은 없음. Windows에서는 strip된 DLL에서 찾지 못했으나 확정할 수 없음 |
| | winpthreads | MIT AND BSD-3-Clause | Windows: OpenBLAS DLL에 정적으로 링크. 휠 고지에 없음 |
| | Microsoft C++ 런타임 `msvcp140.dll` | Microsoft 재배포 조건 | Windows: 별도 DLL. 휠에 고지 없음 |
| `scipy` | OpenBLAS(LAPACK 포함) | BSD-3-Clause, BSD-3-Clause-Open-MPI | Linux(`scipy.libs/`)와 macOS 14 미만(`scipy/.dylibs/`)은 공유 라이브러리, Windows는 DLL. macOS 14 이상은 들어 있지 않음(Apple Accelerate) |
| | GCC 런타임: libgfortran, macOS에서는 libgcc_s도 | GPL-3.0-or-later WITH GCC-exception-3.1 | Linux(libgfortran 빌드 두 개)와 모든 macOS는 공유 라이브러리. Windows는 OpenBLAS DLL과 확장 모듈 `scipy/odr/__odrpack`에 정적으로 링크. 고지는 DLL만 언급 |
| | libquadmath | LGPL-2.1-or-later | Linux(사본 두 개)와 모든 macOS는 공유 라이브러리. Windows는 `scipy/odr/__odrpack`에 정적으로 들어 있을 가능성이 높음(바이트 일치, 심볼로 확인하지는 못함). 고지에 없음 |
| | winpthreads | MIT AND BSD-3-Clause | Windows: OpenBLAS DLL과 여러 확장 모듈에 정적으로 링크 |
| | Qhull | Qhull | 모든 플랫폼: `scipy/spatial`에 정적으로 링크 |
| `shapely` | GEOS | LGPL-2.1(고지에 "or later" 선택지가 적혀 있지 않음) | Linux(`shapely.libs/`), macOS(`shapely/.dylibs/`), Windows(`shapely.libs/`) 모두 별도 공유 라이브러리 `geos`·`geos_c`이고 shapely 확장 모듈이 로드함. shapely가 상류 릴리스를 패치 없이 빌드하며, 휠 정리 도구가 파일 이름과 라이브러리 경로를 바꿈. `LICENSE_GEOS`에 LGPL-2.1 전문은 있으나 GEOS 저작권 줄은 없음 |
| | `msvcp140.dll` | Microsoft 재배포 조건 | Windows: 별도 DLL, 고지는 `LICENSE_win32` |
| `matplotlib` | FreeType | FTL OR GPL-2.0-or-later. FTL로 사용 | 모든 플랫폼: `ft2font`에 정적으로 링크 |
| | HarfBuzz, libraqm, SheenBidi | MIT-Modern-Variant, MIT, Apache-2.0 | 모든 플랫폼: `ft2font`에 정적으로 링크 |
| | Qhull | Qhull | 모든 플랫폼: `_qhull`에 정적으로 링크 |
| | 글꼴과 글꼴 메트릭 | OFL-1.1(STIX, Last Resort), BaKoMa Fonts Licence, Bitstream Vera 조건(DejaVu), Adobe 조건(AFM 파일) | 데이터 파일 |
| `pillow` | libjpeg-turbo, libpng, libtiff, libwebp(sharpyuv·mux·demux 포함), OpenJPEG, Little CMS, libavif(aom·dav1d·libyuv 포함), Brotli, liblzma, zstd(Linux) 또는 zlib-ng(macOS), FreeType, HarfBuzz, libxcb, libXau | 휠 고지에 따르면 허용형. FreeType은 FTL OR GPL-2.0-or-later이고 FTL로 사용 | Linux(`pillow.libs/`)와 macOS(`PIL/.dylibs/`)는 공유 라이브러리 18개, Windows는 정적 링크. xz 항목의 LGPL·GPL 문구는 들어 있지 않은 명령줄 도구에 해당함. FriBiDi(LGPL)는 들어 있지 않고, 시스템에 있을 때만 Pillow가 실행 중에 로드함 |
| `pydantic-core` | Rust crate(pyo3, regex, serde_json, icu_normalizer 등) | MIT, Apache-2.0, Unlicense OR MIT, Unicode-3.0 | 정적 링크. 휠에는 pydantic-core 자신의 라이선스만 있음 |
| `pyyaml` | libyaml | MIT | `_yaml`에 정적으로 링크 |
| `pip` | certifi CA 묶음 | MPL-2.0 | 함께 넣어 둔 데이터 파일, 수정 없이 사용 |
| `gmsh` | libgmsh(OpenCASCADE, FLTK 등 포함) | GPL-2.0-or-later, Gmsh 예외 포함 | 환경의 `lib/` 디렉터리에 설치되는 공유 라이브러리. 별도 `gmsh` 프로세스 안에서 Gmsh 자신의 Python 모듈만 로드함([외부 프로그램](#외부-프로그램) 참고) |

위에 적은 상류 고지의 빈틈(LGPL 전문 없는 libquadmath, numpy `msvcp140.dll`과 winpthreads의
고지 없음, scipy Windows 확장 모듈 안의 정적 GCC 런타임·libquadmath, GEOS 저작권 줄 없음)은
OpenPhysics가 이 휠들을 재배포하지 않는 동안에는 OpenPhysics의 의무를 만들지 않습니다. 이 휠들을
재배포하는 쪽에는 중요합니다.

고정 버전이 바뀔 때, CI에 플랫폼·휠 태그·Python 버전이 추가될 때, 의존성이 추가될 때, 패키지에
컴파일된 코드가 생길 때, OpenPhysics 코드가 묶인 라이브러리를 직접 로드하려 할 때는 이 절을 CI
세 플랫폼에서 다시 확인합니다.

## 외부 프로그램

| 프로그램 | 라이선스 | 쓰는 방식 |
|---|---|---|
| Gmsh(`gmshio[gmsh]`와 CI의 pip 배포판 `gmsh`, 또는 사용자가 설치한 [`gmsh`](https://gmsh.info) 실행 파일) | GPL-2.0-or-later. Gmsh를 Netgen, METIS, OpenCASCADE, ParaView와 결합하도록 허용하는 예외 포함(Gmsh `LICENSE.txt`) | `gmshio`가 `.geo` 스크립트를 쓰고 `gmsh`를 별도 프로세스로 실행한 뒤, 공개된 형식 설명으로 새로 작성한 파서로 `.msh` 파일을 읽음. pip 배포판의 `gmsh` 명령은 그 별도 프로세스 안에서 Gmsh 자신의 Python 모듈과 `libgmsh`를 로드하는 실행 스크립트임. 패키지 코드는 `gmsh`를 import하지 않고(검사함) 아무것도 번들하지 않음. [gmshio NOTICE](../../../../packages/gmshio/NOTICE) 참고 |
| NGSolve와 Netgen(pip 배포판 `ngsolve`, `netgen-mesher`) | LGPL-2.1-only(패키지 메타데이터 기준) | [재료 공동 비교](../../../../packages/galerkin/docs/locales/ko/pages/material_cavity.md#레퍼런스-도구-비교)의 레퍼런스 도구. PyPI 휠로 별도 환경에 설치하고 별도 프로세스로 실행함. 의존성이 아니고 이 저장소의 CI가 설치하지 않음. 수치 결과만 보고하고 코드는 복사하지 않음. 그 휠은 `netgen-occt`(분류자 기준 LGPL)와 macOS 외에서 `ngsolve-openblas`(BSD-3-Clause)도 설치함 |
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
일치한다는 사실을 수렴 근거로 쓰지 않습니다. 시험 전용 `crosscheck` extra로는 정한 대로
허용형 도구만 설치하고 위 목록에 적습니다. 기록 형식과 현재 사례는
[레퍼런스 비교](reference-comparisons.md)에 있습니다. 약한 copyleft 도구([외부 프로그램](#외부-프로그램)의
NGSolve)와 GPL 도구는 이 저장소가 import하거나 설치하지 않습니다. 쓰더라도 따로 설치한 수정 없는
프로그램을 자기 환경과 프로세스에서 돌리며, 소스는 읽거나 복사하지 않고 수치 결과만 보고합니다.
AGPL 도구는 여기서 쓰지 않습니다.

## 자동 검사

```bash
python ci/check_licenses.py --report .validation/licenses.json
```

설치된 메타데이터를 `importlib.metadata`로 읽으므로 라이선스 검사 도구를 따로 설치하지
않습니다. 다음 경우에 실패합니다.

- 설치된 배포판에 검토된 목록 항목이 없을 때
- 설치된 메타데이터가 다른 SPDX 식을 선언하거나, 항목에 없는 copyleft 라이선스를
  언급할 때(항목에 이유를 적은 경우 제외)
- 자체 패키지의 runtime·optional 의존성이 허용형이 아닐 때(external process는 대신 아래 GPL
  규칙으로 검사)
- 약한 copyleft 시험·도구 의존성에 `test_only` 표시가 없을 때
- GPL 배포판이 external process 항목이 아니거나, 기본 runtime 의존성이거나, 자체 코드가
  import할 때
- AGPL이나 SSPL이 어디에든 있을 때
- 자체 패키지가 Apache-2.0을 선언하지 않을 때
- 이 문서나 영어 원문이 목록의 항목을 모두 나열하지 않을 때

CI는 고정된 Linux 환경, 설치한 휠만 담은 새 환경, 그리고 Linux·macOS·Windows 설치 플랫폼
검사에서 이 검사를 돌립니다. 제3자 휠 안에 묶인 구성 요소(shapely의 GEOS 등)는 메타데이터에
드러나지 않으므로 직접 검토해 [묶인 구성 요소](#묶인-구성-요소)에 기록합니다.

의존성을 추가할 때: upstream 저장소의 LICENSE 파일로 라이선스를 확인하고, SPDX 식과 출처
URL을 목록에 항목으로 추가하고, CI 플랫폼마다 그 휠에 묶인 것을 확인해 적고, 이 문서와 영어
원문에 행을 추가하며, 번들하거나 복사하면 패키지 NOTICE에도 적습니다.
