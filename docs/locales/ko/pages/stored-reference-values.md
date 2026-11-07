# 저장 레퍼런스 값

[English](../../../stored-reference-values.md) | **한국어**

저장 결과를 읽으면 독립 도구를 설치하거나 실행하지 않고 비교할 수 있습니다. 코드 간 비교
근거이며 해석해 수용 기준이나 메시 수렴 근거를 대신하지 않습니다. 첫 물리 값 기록은 SOI strip modesolver 비교
`tests/simcase/reference_values/modesolver/soi_strip_modes.json`입니다.

## 배치와 사용

기록 위치는 `tests/<import>/reference_values/<tool>/<case>.json`입니다. pip만으로 재현할 수 있는
생성기는 해시 고정 requirements와 함께 옆에 둡니다(VCS는 전체 커밋 고정). 그 외 생성기의 공개
위치는 문자 그대로 `private research repository`입니다. 수치 출력과 출처만 두며 도구 코드나
제3자 데이터는 넣지 않습니다.

배포하지 않는 `tests/_support/reference_loader.py`는 루트 pytest `pythonpath`로 찾습니다.
`tests/conftest.py`를 만들면 미설치 `refsol` 대신 `tests/refsol`이 잡힐 수 있으므로 만들지 않습니다.
`test_reference_*.py`와 `test_crosscheck_*.py`만 로더를 import합니다. 배포·플랫폼 검사기의 평면
복사 목록에는 이 파일을 넣지 않습니다. 전체 설치 시험은 로더·기록·루트 설정을 함께 복사합니다.

시험은 자기 저장소 상대 경로를 `consumers`에 적고 기록 파일명 문자열을 포함하는 표현식으로
`load_reference`를 호출합니다. `ref.inputs`로 사례를 만들고 읽기 전용 `ref.arrays`를 비교합니다.
판정 기준은 시험이 소유하며 데이터에 저장하지 않습니다. `tests/galerkin/crosscheck.py`의
`make_record(..., stored=ref)`에 정확한 도구와 기록의 `tool_discretization`을 전달합니다.
사례·물리도 일치해야 합니다. 도구의 설치 메타데이터는 조회하지 않습니다. 출력은
`wall_time_s.reference = null`이며 과거 생성 비용과 해시를 `stored_reference`에 남깁니다.
지금 도구를 실행했다고 주장하지 않습니다. 다른 이산화 비교는 보고만 하며 기존 해석해·같은
이산화 기준은 바꾸지 않습니다.

## 형식 v1

스키마는 `openphysics.reference-values/1`입니다. Wavebit은 다른 이름공간에 같은 해시 규칙을 씁니다.

| 필드 | 내용 |
|---|---|
| `case`, `physics`, `comparison`, `role` | 식별자. comparison: `same-discretization`, `different-discretization`, `structure-oracle` |
| `references` | 도구별 목록: `tool`, 정확한 `version`, `build`, `modified` (`value`, `description`), 목록과 같은 SPDX `license`, `source`, `install` (`kind`, `command`, `lock`), `settings`, `discretization`, `arrays` 이름 glob, `execution`, `independence` |
| 독립성 | execution: `separate-process`, `in-process`, `unknown`; independence: `product_loaded`, `inputs_from_product` |
| `generator` | `path`, LF 정규화 `sha256`, `command`, `product_commit`, `clean` |
| `generated_utc`, `environment` | UTC 시각. 환경: `python`, `numpy`, `os`, `cpu`, `dtype`, `backend/device` |
| `cost` | `compile_s`, `compute_s`, `wall_time_s`, `peak_rss_mb`, `threads`, `not_measured` |
| `inputs` | 사례를 재구성하는 입력 |
| `matched`, `not_matched`, `reference_self_check`, `failed_or_discarded`, `not_run` | 일치·불일치·자체 점검·실패·미실행 목록 |
| `values` 또는 `payload` | 아래 표현 중 정확히 하나 |
| `values_sha256`, `content_sha256` | 수치와 입력/내용 해시 |
| `consumers` | 이 기록을 명시적으로 읽는 추적 시험 경로 목록 |
| `provenance_status`, `not_recorded` | `complete` 또는 `reconstructed`; 모든 null 필드의 점 경로(목록은 `[0]`)를 이유·확인한 출처에 연결하는 객체 |
| `regeneration` | `date`, `mode`, `reason`, `previous_content_sha256`, `content_sha256`, `tool_version`, `review`, `approval` 목록 |

인라인 `values`는 `{name, unit, dtype, shape, data}` 목록입니다. dtype은 `<f8`처럼 명시합니다.
복소수는 `<c16`과 `real`, `imag` 목록을 쓰며 `data`를 대체합니다. 유한한 숫자만 허용하고 각 배열은
정확히 한 도구의 glob에 속해야 합니다. `metadata`는 예약 이름입니다. payload는 기록에 상대적인
`file`, `format` (`npz`/`json`), `file_sha256`, `arrays` 이름 목록입니다. JSON은 인라인 목록 형식이며
NPZ는 숫자 배열만 담고 pickle 없이 읽습니다.

기록 1 MiB, payload(압축 해제 포함)·전체 배열 바이트 512 KiB, 저장소 합계 10 MiB가 한도입니다.
경로가 디렉터리를 벗어나면 실패합니다. 절대·홈·드라이브 경로, 비공개 조정 경로, 세션 URL,
비공개 연구 저장소 이름은 문자열에 넣지 않습니다. 대신 `private research repository`라고 씁니다.
어느 깊이든 `gate`, `tolerance` 키는 금지합니다. AGPL 도구는 수정하지 않은 것만 허용합니다.
모르는 메타데이터는 null과 `not_recorded` 설명을 남기지만 모르는 버전·수치는 검증값으로 삼지 않습니다.

## 해시와 갱신

`values_sha256`은 이름순 배열(`metadata` 제외)의 UTF-8 이름, NUL, `dtype.str`, NUL,
`repr(shape)`, NUL, C 순서 바이트를 SHA-256에 넣습니다. `content_sha256`은
`{"inputs": inputs, "values_sha256": values_sha256}`를 `sort_keys=True`,
`separators=(",", ":")`, `allow_nan=False`, `ensure_ascii=False`로 직렬화한 UTF-8의 SHA-256입니다.
파일 해시는 바이트 기준이며 텍스트의 CRLF/CR은 LF로 정규화합니다.

공유 벡터 `x=[0.1,0.2]` (`<f8`), `z=[1+2j]` (`<c16`)의 해시는
`5b1e6695fa1d3df431519ed94c7096a82b5d1ca875872559f67e1cab86e1ce2e`입니다.
입력 `{"eps":{"real":4.0,"imag":-0.04},"modes":2}`를 넣은 내용 해시는
`63ad3eaeaed8bee68b8cc4ff62997c2fddd92f443327e07d926189d5fde7dea0`입니다.

생성기의 기본은 compare입니다. 임시 위치에 쓰고 배열별 차이를 출력하며 차이가 있으면 실패하고
tests에는 쓰지 않습니다. `--restamp --reason`은 값·입력/내용 해시를 유지하는 출처 수정만 허용합니다.
`--rebaseline --reason`은 고정 도구 버전과 키별 차이를 보여주는 검토 변경이 필요합니다. 실패를
통과시키려고 재생성하지 않습니다. 이력에는 이전·결과 내용 해시를 모두 적고 인접 이력과 마지막
현재 해시가 이어져야 합니다. 승인은 관리자·날짜 설명으로 적으며 비공개 링크를 넣지 않습니다.
로더는 생성기나 재생성 명령을 제공하지 않습니다.

## 감사

`python -m pytest -q tools/tests/test_reference_values.py`는 추적 파일, 목록의 라이선스, 생성기,
소비 시험, 고아 payload, 복사 경계, 공유 벡터와 손상 변이를 확인합니다. 설치 시험에서는 tools 없이
로더가 형식·유한값·크기·해시를 다시 확인합니다. 목록의 `external_tools`는 `spdx`, `url`,
`reference` (`mode`, `execution`, `modules`, `imported_by`, `values`, `generators`, `light`)를
기록하며 의존성을 설치하거나 허용하지 않습니다. NGSolve는 사례 63초·1.8 GB 때문에 저장 방식이며
검토된 기록이 들어올 때까지 값 목록은 비어 있습니다. 새 도구는 기록과 함께 반영합니다.
도구 import 구역 전체 검사는 별도 작업이며 이 감사는 로더와 평면 복사 경계만 검사합니다.
