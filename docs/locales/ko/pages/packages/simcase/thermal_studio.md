# Studio 정상 열전도

[English](../../../../../packages/simcase/thermal_studio.md)

**한눈에 보기**

- **하는 일:** 직사각형 `thermal.steady2d` 문서(균질 직사각형, P1, 상수 등방 k와 열원, 변 Dirichlet, 단열, 상수 외향 열유속·Robin)를 위한 JSON 우선 전용 Studio 화면입니다. 전용 route로 검증·실행하고 결과 메시, 절점 Kelvin, 요소 열유속을 보여 줍니다. 재료 영역이 있는 정상 열전도 문서도 Studio의 영역 한도 안에서 같은 방식으로 검증·실행·표시하며 영역 색, 경계, 범례, 영역 표를 보여 줍니다([영역 문서](#영역-문서) 참고).
- **한계:** 과도 문서(별도 과도 Studio 안내 참고), 해석 전 메시 미리보기, 영역 문서를 넘는 임의 형상, 연성, 결과 저장 endpoint가 없습니다. 설정한 자원 한도는 `candidate-unmeasured`이며 용량 보장이 아닙니다. Studio는 로컬 도구이며 다중 사용자 서비스가 아닙니다.
- **검증:** [정상 Studio 독립 검증](studio_thermal_independent_validation.md)을 참고하세요. 특정 커밋의 결과는 그 커밋의 CI 실행에서 확인하세요.

## 제공 상태

이 checkout은 Studio의 JSON-first 정상 열전도를 구현합니다. 전용 검증·실행
route, typed SI결과, 실제 결과 메시, 절점 Kelvin과 요소 열유속 표시를 제공합니다.
기존 균질 직사각형/P1 headless solver를 사용하며 상수 등방 k·열원,
변 Dirichlet·단열·상수 외향 flux/Robin조건을 다룹니다. 기존 광학동작과
generic-route 열 guard는 유지합니다. 이 정상열 인터페이스는 과도 문서와 시간/history
선택을 제외하며 별도 [과도 Studio 가이드](thermal_transient_studio.md)를 참조하세요.
해석 전 메시 preview·아래 영역 문서를 넘는 임의 형상·자동 연성·새 결과저장 endpoint는
범위 밖입니다.
재료 영역이 있는 정상 문서(`geometry.shapes` 또는 `geometry.background`)는 같은
route에서 별도 경로를 따르며 [영역 문서](#영역-문서)에서 설명합니다.

구현과 검증·release상태는 별개입니다. Source·설치 플랫폼·browser·자원 근거는
정확한 checkout의 CI결과·artifact에서 확인하세요. 이 페이지는 새로운 통과나
release를 주장하지 않습니다. `run_enabled=true`는 유효한 설정 limits와 공개API
가용성을 뜻하며 성능실측완료가 아닙니다. 자원정책은 `candidate-unmeasured`를
유지하며 설정 제한은 용량·성능 보장이 아닙니다. 모델 단위와 Python/CLI 사용법은
[headless 정상 가이드](thermal_steady2d.md)를 참조하세요.

## 시작과 사용자 흐름

저장소 checkout에서 일치하는 패키지와 선택적 Studio 의존성을 설치한 뒤
저장소 루트에서 시작합니다.

```sh
python -m pip install -e "packages/simcase[studio]"
python -m simcase.studio --no-browser
```

출력된 localhost 주소를 엽니다. 시작 명령이 capability검사나 설정 자원 제한을
우회하지는 않습니다.

1. 완전한 정상열 JSON 문서를 열거나 JSON editor에 붙여 넣고 명시적으로 적용합니다.
   열 재료·경계 전용 폼은 범위 밖이며 generic 광학 예제는 광학용으로 유지합니다.
2. 전용 열 동작으로 현재 적용한 JSON을 검증합니다. 잘못된 JSON·미지원 physics·
   제한 거절을 이전 유효 문서 실행 권한으로 삼지 않습니다. 편집·import 즉시 이전
   검증·메시·결과 소유권을 무효화하며 파싱 성공 전에도 적용합니다.
3. 서버가 일치하는 capability·설정 제한을 알릴 때 현재 검증된 정상 문서만
   실행합니다. Run은 독립적으로 재검증합니다. 제한에 맞추려고 메시를 조용히
   거칠게 바꾸지 않습니다.
4. 성공 후 **실제 결과 메시**를 봅니다. 해석 전 열 Mesh 동작은 비활성 상태입니다.
   광학 meshing을 사용하거나 preview만을 위해 solver를 실행하지 않습니다.
5. 재실행 없이 온도·요소 열유속 성분/크기를 선택합니다. 모델 편집은 새 검증·실행이
   필요하며 view 변경은 result 문서를 바꾸지 않습니다.
6. 오류 시 현재 입력을 수정하거나 현재 연산을 명시적으로 재시도합니다. 오래된 비동기
   성공·오류·finalization callback이 현재 control·메시지·mesh·field·colorbar를
   덮지 않아야 합니다.

Editor는 중복키 검출을 포함한 엄격 검증을 위해 원래 JSON텍스트를 보존하며
정규화 모델 데이터는 별도 snapshot입니다. 성공 후 summary표는 raw온도범위·
결과 절점/요소 수·서버의 명명된 source/outward/balance양을 표시합니다.
**Full result metadata**를 펼치면 전체 summary를 볼 수 있으나 독립 물리정답은
아닙니다. 숨겨진 tab은 layout크기0으로 rasterize하지 않습니다.
보이는 Mesh/Results tab으로 전환하면 재해석 없이 현재 수용된 결과를 다시 그립니다.

## 단위와 물리 의미

| 표시/데이터 | 계약 |
| --- | --- |
| 좌표 | raw `arrays.nodes_m`는 m; 축은 최상위 `display_length_in_m`(캡처 문서의 양수 metres-per-document-length-unit scale)로 나눔 |
| 온도 | `temperature_k`, 절점 P1, K; 선형 보간·단위 colorbar |
| Flux | `heat_flux_w_m2`, 삼각형별 상수, W/m²; 전역 qx/qy 또는 크기 |
| 화살표 | 실제 요소 중심·전역 방향; 명시한 view gain이며 물리값 재조정 아님 |
| 열원/반력/rate | 면외 깊이당 절점 W/m이며 W/m² flux와 구분 |

```text
q = -k grad(T)
q.n = g_out + h*(T-T_ambient)
rhs = fQ+B-G
total_outward = sum(G+C-reaction)
thermostat_outward = -sum(reaction)
```

양수 지정 flux는 외향입니다. Flux·대류가 있으면 thermostat 열을 전체 외향 열로
대체하지 않습니다. 문서 계약의 지정/주변 입력 K는 유한한 비음수입니다.
유한한 음수 계산 K는 clamp·광학모드 정규화 없이 표시합니다. 이 선형 수학 해가
그 온도에서 재료의 물리적 유효성을 입증하지는 않습니다. 상수 온도는 0으로 나누는
대신 상수 범위로 표시합니다. 요소 flux를 절점장으로 평균하지 않습니다.
변환 좌표·파생 flux 크기 overflow는 view 오류이며 raw값 변경 허가가 아닙니다.

Typed payload는 wire format과 headless v1/v2 result/layout ID를 구분합니다.
V1 raw배열은 9개, v2는 13개이며 Robin-only v2의 Dirichlet 절점 수는 0일 수 있습니다.
정확한 허용 버전쌍·단위·위치·shape·유한한 비불리언 배열·유효 CCW 연결 정보를
검사해야 합니다. 알 수 없는 layout·누락 필드·잘못된 payload를 표시하면 안 됩니다.

## 고정 wire envelope

```text
payload_format = "studio-thermal-steady-v1"
kind = "thermal.steady2d"
job, result_id, client_revision, request_seq
result_format, field_layout
display_length_in_m
summary
arrays
```

모두 최상위 필드이며 **중첩 coordinates 객체는 없습니다**.
`arrays`는 정확히 v1의 9개 또는 v2의 13개 headless 배열을 포함합니다.
`summary`는 일치하는 단위·위치·shape를 포함합니다.
좌표는 미터(`summary.mesh_length_unit="m"`)이며 `summary.units.length`는
문서 표시 단위 선언입니다. Run identity는 kind/job/result_id와 비음수
safe-integer counter 두 개입니다. Status는 status/log/error/has_result를
추가합니다. 요청은 정확히 doc/client_revision/request_seq를 포함하고 UTF-8
application/json을 사용합니다. 중복키·비유한 JSON·잘못된 envelope·미지원
physics를 거절합니다. 열 status/result route에는 field/time selector를
허용하지 않습니다. Arrays·summary·identity는 이 단일 계약을 사용합니다.

## Route 경계와 회복

이 checkout은 다음 전용 정상열 route를 구현합니다. 위에서 설명한 대로 구현과
정확한 checkout의 검증은 별개입니다.

| Route | 정상열 동작 |
| --- | --- |
| `GET /api/capabilities` | 버전 있는 정상열 capability·설정 자원 정책 |
| `POST /api/thermal/validate` | 엄격 JSON envelope·공개 문서 검증·preflight |
| `POST /api/thermal/run` | 재검증·용량 예약·입력 캡처·공개 run |
| `GET /api/jobs/{job}` | 제한된 열 상태/log/error·응답 소유 tag |
| `GET /api/jobs/{job}/result` | 성공 후 완전 검증·인코딩된 정상 payload 하나 |

기존 `/api/validate`는 열 `ok=false`를 유지하며 generic `/api/mesh`,
`/api/run`은 열/공진기 실행 거절을 유지합니다. 기존 공진기 schema 검증과
실행은 별개입니다. 열 지원은 generic 광학 guard 제거 대신 전용 route를 사용해야
합니다. 이 정상열 endpoint는 과도 문서·시간/history selector를 거절하며,
별도 [과도 Studio 인터페이스](thermal_transient_studio.md)가 해당 전용 route와
view를 정의합니다. 정상열 capability가 없거나 잘못되면 정상열 동작을 비활성화하되
기존 광학 시작을 막지 않습니다.

오류는 잘못된 입력400, 논리 검증실패200+`ok=false`, 요청/자원 제한413/429,
만료/알 수 없는 결과404, 아직 제공할 수 없는 running/error결과409를 구분합니다.
HTTP200만으로 검증 성공이 아닙니다. Network/non-JSON 오류는 현재 연산의
명시적 재시도가 필요하며 만료가 자동 재해석을 유발하면 안 됩니다.
실패 작업 후 부분 결과나 이전 광학 fallback을 게시하지 않습니다.
오류 문자열은 plain text로 표시합니다.

Revision/sequence/job/result tag는 현재 view를 갱신할 응답을 선택하며 인증이
아닙니다. 같은 revision 재시도·field-render 변경도 연산 소유권이 필요합니다.
오래된 응답 무시는 서버 해석 취소나 다른 작업 삭제 권한을 뜻하지 않습니다.
Localhost/auth/CORS 동작이 다중 사용자 격리 서비스로 강화되는 것은 아닙니다.

## 자원 정책과 한계

모든 값은 **후보 설정이며 실측 용량이 아닙니다**.
요청1 MiB, N<=10201절점, M<=20000요소, 인코딩결과16 MiB,
활성 열 작업1개, terminal 열 기록 최대2개·합계32 MiB,
terminal 최대 보존300 s입니다. Log상한64 KiB·error4 KiB·summary metadata64 KiB·
status encoding128 KiB도 적용합니다. 최종 capabilities는 실제 설정 정책을 공개해야 합니다.
필수 정책이 미설정이면 열 run은 비활성 상태를 유지합니다.
신규 admission/publication에 count/byte 공간이 필요하면 가장 오래된 terminal
기록(done **또는** error)을 회수하며 활성 열 작업과 모든 광학 작업은 보존합니다.
TTL300 s는 최대 보관이며 **최소 제공시간 보장이 아닙니다**.
결과가 더 일찍 회수될 수 있으며 회수/만료된 status·result는404를 반환하고
자동 재실행하지 않습니다. 매 세 번째 실행을 5분 차단하는 정책은 없습니다.
UI무효화로 global job을 삭제하지 않습니다.
성공·실패 terminal metadata/log/error 모두 제한하며 성공과 모든 실패
(thread-start·encoding·publication 포함) 후 용량을 해제해야 합니다.
활성/광학 작업은 축출하지 않습니다.

Content-Length를 신뢰하지 않고 전체 파싱 전에 stream 요청 byte를 제한합니다.
직사각형 문서는 job/thread/solver 할당 전에 정확한 절점·요소 수를 preflight합니다.
영역 문서는 raw 형상 한도와 루프 꼭짓점 수를 job 전에, 정확한 절점·요소 수를
메시 생성 뒤 해석 전에 검사합니다([영역 문서](#영역-문서) 참고).
Raw scalar 수는 v1=6N+5M+2D, v2=10N+5M+2D, 영역 10N+6M+2D이지만 raw-byte 추정이나
encoded cap으로 Python/solver peak memory를 제한했다고 볼 수 없습니다.
복사·list·희소분해·직렬화·동시 작업의 overhead가 있습니다.
실제 공유호스트 측정은 부하를 공개해야 하며 전용 성능 baseline을 주장하지 않습니다.
전체 배열을 반복 직렬화하는 대신 제한된 encoded 결과를 유지합니다.
새 save/upload/path/overwrite API나 자동 재시도 queue는 없습니다.

## 영역 문서

`geometry`에 `shapes`나 `background`가 있는 `thermal.steady2d` 문서는(엔진과 같은
규칙, [재료 영역이 있는 열전도 문서](thermal_regions2d.md) 참고)
`/api/thermal/validate`와 `/api/thermal/run`에서 Studio의 영역 경로를 따릅니다.
그 밖의 문서는 직사각형 경로를 따르며 그 코드·byte·오류는 바뀌지 않습니다.
`tests/simcase/test_studio_rectangle_invariants.py`가 이를 고정합니다.
`mesh.subdivisions`가 있는 영역 문서는 거절합니다(`invalid_document`, 경로
`mesh.subdivisions`). `geometry.shapes` 키가 남은 직사각형 문서도 그 키 때문에 영역
문서가 되므로 같은 이유로 거절합니다.

### Wire 형식

| 항목 | 영역 결과 |
| --- | --- |
| Result·layout ID | `thermal.steady2d-regions-result-v1`, `thermal2d-p1-node-cell-regions-v1` |
| Payload | `payload_format = "studio-thermal-steady-regions-v1"`, 직사각형 payload와 같은 최상위 필드 11개 |
| `arrays` | v2 배열 13개와 `triangle_regions`(삼각형마다 영역 번호 하나, 단위 `1`, 위치 `triangles`, shape `[M]`); D=0 허용(Robin만으로 고정) |
| `summary` | 생산자 summary 그대로이며 `region_names`(번호 순서), `regions`(이름마다 `material`, `triangles`, `area_m2`), 전체 `materials` 표, `heat_source_w_m3`, `conductivity_range_w_mk`, `mesh`(`nodes`, `triangles`, `size`, `min_angle_deg`, `size_unit`)를 포함 |
| Capability | 정상 블록 안의 중첩 `regions` 키: `supported`, `run_enabled`, `result_formats`, `field_layouts`, `payload_formats`와 아래 `limits` 다섯 개 |

영역 쌍은 직사각형 client가 읽는 블록 바깥 `result_formats`에 넣지 않습니다.
따라서 영역을 지원하지 않는 페이지는 중첩 블록을 무시하고, 영역 payload는
job이 끝난 뒤 거절합니다(형식과 쌍이 새것이므로).
페이지는 문서를 검증할 때 그 종류(직사각형 또는 영역)를 고정합니다. 서버가 유효한
`regions` 블록을 알리지 않으면 요청을 보내기 전에 영역 문서를 거절하고, 그 블록의
`run_enabled`가 true일 때만 실행하며, 다른 종류의 결과는 거절합니다.

게시 전에 capture는 배열을 읽기 전에 쌍을 확인하고, 공개 속성을 한 번씩 읽고,
복사 전에 shape와 절점·요소 한도를 검사한 뒤 영역을 검사합니다. 이름은 1~65개의
서로 다른 비어 있지 않은 문자열이며 summary와 같아야 하고, 번호는 범위 안이어야
합니다. 영역별 삼각형 수, 캡처한 메시에서 생산자와 같은 식으로 더한 영역별 면적
(같은 수에 같은 식이므로 정확히 같음), 영역 면적의 합과 도메인 면적(1e-9), 문서가 지정한
영역별 재료, 문서와 같은 summary 재료·열원을 확인합니다. 하나라도 어긋나면 job
오류 `invalid_result`이며 아무것도 게시하지 않습니다.

### 한도와 적용 위치

| 단계 | 검사 | 거절 |
| --- | --- | --- |
| Event loop, JSON 크기에 선형인 비용 | `thermal.steady2d` 항목 하나; `mesh.subdivisions` 없음 | `unsupported_physics`(400); `invalid_document`(validate는 200·`ok=false`, run은 400) |
| Event loop | 정상 경계(v2) 결과 runtime이 설치되어 있음(영역 결과는 항상 경계 배열을 담으므로) | `unsupported_result_format`(400) |
| Event loop, run만 | 영역 실행용 공개 결과 API를 쓸 수 있음(블록의 `run_enabled`) | `unsupported_public_api`(400) |
| Worker thread, `Document.from_dict` 전 | 도형 64개, 원 16개, 다각형 점 합계 512개 이하, 다음으로 경계 교차 1024개 이하(`simcase.region_complexity`) | `geometry_limit_exceeded`(413), 경로 `geometry.shapes` |
| Worker thread | `Document.from_dict` | `invalid_document` |
| Worker thread | 도형 boolean 뒤 루프 꼭짓점 2048개 이하(`simcase.check_mesh_limits`) | `geometry_limit_exceeded`(413), 경로 `geometry.shapes` |
| Worker thread | 문서의 이름·단위·재료·열원이 64 KiB(`metadata_bytes`) 안에 인코딩됨; summary가 이들을 복사함 | `payload_limit_exceeded`(413), 경로 `materials` |
| Job, 해석 전 | 메시 생성은 절점 10201개(`max_nodes`)를 넘으면 멈추고, 이어서 정확한 절점·요소 수를 10201·20000과 비교 | Job 오류 `mesh_limit_exceeded` |
| Job | 메시 생성 뒤 드러나는 문서 오류(예: 뒤 도형이 완전히 덮은 도형의 열원) | Job 오류 `invalid_document` |
| Job | 그 밖의 실행 실패(예: meshine이 풀지 못하는 형상, meshine의 80 round 안에 수렴하지 않는 세분) | Job 오류 `solver_failed` |

형상 한도 네 개와 루프 꼭짓점 한도는 capability의 `limits`(`max_shapes`,
`max_circles`, `max_polygon_points`, `max_boundary_crossings`,
`max_input_vertices`)이고, 절점·요소 한도는 정상 블록의 `max_nodes`와
`max_triangles`입니다. 모든 거절 메시지는 개수와 한도를 밝힙니다. 메시 생성이 절점
한도에서 멈추면 개수를 알 수 없으므로 메시지는 "more than"이라고 씁니다. 모든 값은
후보입니다(`candidate-unmeasured`).

- **경계 교차**는 서로 다른 도형의 경계 선분 쌍 가운데 내부가 정확히 한 점에서
  만나는 쌍입니다(사각형은 선분 4개, 원은 엔진이 만드는 128각형, 다각형은 그 변).
  맞닿음과 같은 직선 위 겹침은 세지 않습니다. 교차는 뒤 도형이 덮어도 검증 시간을
  쓰므로 검증 전에 raw JSON에서 셉니다.
- **루프 꼭짓점**은 boolean 뒤 메시 생성기에 넘기는 루프의 점 하나입니다. 배경 안의
  도형은 자기 자신과 배경의 구멍으로 두 번 세고, 다른 경계에 닿거나 교차하는 원은
  128각형이므로 그런 원은 2048 안에 최대 7개까지 들어갑니다. 다른 경계와 떨어진 원은
  자체 `mesh_size`가 있어도 전역 `mesh.size`로 정한 max(16, 4πr/`mesh.size`)개 점의
  정확한 원으로 메시하므로, 아주 작은 전역 크기는 여기서 거절됩니다.

Studio가 쓰는 엔진 함수는 [호출자를 위한 메시 상한](thermal_regions2d.md#호출자를-위한-메시-상한)을,
이 한도 안팎의 고정 작업에서 잰 검증·job 시간과 메모리는
[영역 자원 관측](../../region_resource_probe.md)을 참고하세요.

### 검증 thread와 동시성

영역 검증(raw 개수, `Document.from_dict`, 루프 꼭짓점 수, run이면 실행용 복사)은
worker thread에서 돌므로 긴 형상 계산이 event loop를 막지 않습니다. 다만 GIL을
잡는 Python 수준 shapely·numpy 호출은 잠깐 지연시킬 수 있고 job thread도 마찬가지입니다
(로컬 실행에서 다른 요청이 검증 중에는 최대 약 0.06 s, job이 도는 동안에는 0.2~0.5 s 기다렸습니다.
[영역 자원 관측](../../region_resource_probe.md) 참고). 요청은 그 thread가
끝날 때까지 공유 열 ingress permit을 쥐고 있으며, client 연결이 끊기거나 요청이
취소되어도 마찬가지입니다. 따라서 영역 검증은 한 번에 하나만 돌고 그동안 다른 열
요청은 429를 받습니다. 취소된 요청은 그 뒤 job을 시작하지 않고 끝납니다. Run은 같은
방식으로 다시 검증한 뒤 단일 job 자리를 예약합니다.

루프 꼭짓점 수는 실행이 메시하는 마이크로미터 사본에서 세고, `check_mesh_limits`는 실행처럼
그 사본을 검증합니다. 그래서 검증은 도형의 불리언 연산을 `Document.from_dict`, 사본 검증, 수 세기에서
세 번 계산합니다. 로컬 실행에서 수 세기는 `Document.from_dict`의 약 두 배가 걸렸습니다. 교차 한도에
맞춘 덮인 교차에서 약 0.6 s 대 0.3 s였습니다.

### 화면

- **Mesh 탭:** 각 삼각형을 영역 색(Okabe-Ito 여덟 색을 영역 번호 순으로 반복)으로
  메시 선 아래에 칠하고, 영역 경계는 굵은 선으로 그립니다. 범례는 모든 영역을
  "이름 — 재료"로 나열하고, 메시 줄은 "N nodes, M cells, R regions"로 씁니다.
- **Results 탭:** 온도·열유속 화면에도 영역 경계를 그립니다. 커서를 올리면 값 줄에
  "; region 이름 (재료)"가 붙습니다.
- **요약 패널:** 양(quantity) 행에서 영역·재료·열원 표를 뺍니다(영역 이름은 양이
  아님). 전체 metadata는 **Full result metadata**에 그대로 있고, 그 뒤에 색·영역·재료·
  k·Q·요소 수·면적·재료 `source` 문구를 담은 영역 표가 이어집니다.
- 영역 이름과 재료 문구는 HTML이 아니라 텍스트로만 표시합니다.

### 알려진 한계

- 너무 촘촘한 메시는 검증이 아니라 job에서, 메시 생성 뒤 해석 전에 실패합니다.
  검증은 형상, summary 하한, 과도 문서의 이력 길이만 보고 거절합니다. 그동안 job
  자리를 차지하며, 로컬 실행들에서 이런 거절 전 메시 생성에 최대 약 5 s(최근 실행에서는 최대
  2.9 s)가 걸렸습니다.
- 절점 한도에 닿기 전에 meshine의 80 round 안에 수렴하지 않는 세분도 job에서
  `solver_failed`로 실패하며, 도는 동안 job 자리를 차지합니다. 로컬 실행에서는 약
  6~13 s였습니다.
- 고립된 원의 점 수는 전역 `mesh.size`로 정합니다(위 참고).
- 루프 꼭짓점 수는 메시 생성기가 T자 접점에서 루프를 나누기 전에 세므로, 생성기는
  센 것보다 조금 더 많은 점을 처리할 수 있습니다.
- 영역 결과에는 항상 배열 14개가 있으며 D=0도 유효합니다.
- Summary는 쓰지 않는 재료와 그 `source` 문구까지 재료 표 전체를 복사하며 64 KiB 안에
  들어가야 합니다. 확실한 초과는 검증에서 거절하고 나머지는 job 오류로 끝납니다.
- meshine은 예각 별 모양 다각형, 경계가 거의 겹치는 교차 다각형, 끝 각이 1도인 톱니 같은 입력에서
  "cannot resolve"로 안전하게 실패할 수 있습니다(`solver_failed`). 이 톱니는 simcase가 메시하는
  마이크로미터 사본에서만 실패하고, 밀리미터나 다른 배율에서는 대신 절점 한도에 닿습니다
  ([영역 자원 관측](../../region_resource_probe.md) 참고).
- 영역이 여덟 개를 넘으면 색이 반복됩니다. 범례·경계·표·커서 표시는 여전히 모든 영역의
  이름을 밝힙니다.
- 영역 지원 전에 캐시한 페이지는 job이 끝난 뒤 영역 결과를 거절합니다(`/static`에
  `Cache-Control`이 없음). 페이지를 다시 읽으세요.
- 일반 route가 열전도 문서를 거절하므로 영역 예제는 `/api/examples`에 나오지 않습니다.
- 이 checkout보다 오래된 meshine(`MeshSizeLimitError` 없음)에서는 `run_enabled`가
  true인 채로 영역 실행이 `solver_failed`로 끝납니다.
- 측정은 Linux에서만 했으며 macOS와 Windows는 검증하지 않았습니다.

## 기여·검증 수명주기

문서를 포함한 모든 변경에 같은 main/PR 검증 정책을 적용합니다.
작업은 Draft PR로 열며 Draft PR과 기능 branch push에는 검증 CI를 실행하지
않습니다. 허용된 개발 환경에서 관련 검사를 통과한 뒤 검토한 후보를 Ready로
전환합니다. 사용자 PC에서 수치 작업을 실행하지 않습니다.
실행하지 못한 검사는 통과가 아닌 명시적 공백입니다. Ready PR·main 검증은
과학 gate와 필수 검사를 유지해야 합니다.
검토된 Ready PR은 필수 검사 후 자동 **Rebase and merge**를 사용하며
자동 반영이 검토·병합 후 근거 확인을 대체하지 않습니다.
제출 commit과 달라질 수 있는 실제 landed main SHA를 기록합니다.

Main 검증은 workflow/ref 고정 concurrency key,
`cancel-in-progress: false`, `queue: max`를 사용합니다.
Non-main/PR은 `queue: single`로 오래된 실행을 대체·취소합니다.
Main pending 한도는100이며 대기열 진입 순서는 commit 순서·무한 보존·
용량 예약·배포 보장이 아닙니다. Green PR과 green landed main을 구분합니다.
해당 green main commit에서만 release하며 검증은 패키지를 게시하지 않습니다.

Linux 전체 과학 수용과 Linux·macOS·Windows 설치 배포 검증은 별도 요구입니다.
Matrix 설정이 실제3OS 통과는 아닙니다. 정확 job별 환경·import origin·
archive/wheel identity·실패·skip·artifact를 확인하세요.
좁은 Windows 검사는 Windows 전체 물리나 macOS를 인증하지 않습니다.
Universal wheel이 OS 동작을 입증하지 않습니다.
실행할 수 없는 플랫폼은 미검증으로 기록하고 플랫폼 실패를 설명 없는 skip으로
바꾸지 않습니다. 실제 browser 상호작용·자원 실측도 HTTP/Node/설치 검사와 별도입니다.

## 테스트 지도와 근거 상태

| 계층 | 필요한 근거이며 통과 주장이 아님 |
| --- | --- |
| Server | 할당 전 strictJSON/limit; 공개API positive control; v1/v2/D0 metadata; 공개속성 한 번 복사·검사; 모든 terminal 경로 제한; 영역 지원 전 고정한 직사각형 byte·오류(`test_studio_rectangle_invariants.py`); 영역 한도·거절·worker thread·취소·capture 결함(`test_studio_region_http.py`) |
| 물리 | 독립 선형/가산·열원/Robin 정답·SI변환·기존수렴·음성대조; wire를 거친 영역 문서(`test_studio_region_acceptance.py`) |
| Frontend | dirty/revision/sequence/capability/render 결정적 truth-table; stale성공/오류/finally 무시; 중첩 영역 capability·문서 종류 고정·영역 payload 검사(`studio_steady_thermal.cjs`, `studio_transient_thermal.cjs`) |
| 표시 | 절점/요소 구별 fixture·절점보간·flatflux/전역부호·상수/음수K |
| 자원 | 용량해제·실패기록보존·byte/count/TTL 경계·별도 peak/직렬화실측 |
| 배포/플랫폼 | 배포자산/import·source/설치소비자·정확필수CI·OS별결과 |
| Browser | 실제 Canvas상호작용; HTTP TestClient·Node시험과별도 |

n8/16/32/64 마지막 두 구간 온도 L2차수>=1.8, flux차수>=0.9,
정규화 residual/열수지1e-10·SI상사성1e-9를 유지합니다.
Studio거절이 물리gate 면제가 아닙니다. 수치·HTTP·Node·설치·browser·플랫폼 수용은 각각 정확 checkout의 실제 실행이
필요합니다. Linux통과가 Windows/macOS
통과를 뜻하지 않으며 시험 정의가 실행·수용·main통합을 뜻하지 않습니다.
