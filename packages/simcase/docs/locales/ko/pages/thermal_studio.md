# Studio 정상 열전도

[English](../../../thermal_studio.md)

## 제공 상태

이 checkout은 Studio의 JSON-first 정상 열전도를 구현합니다. 전용 검증·실행
route, typed SI결과, 실제 결과 메시, 절점 Kelvin과 요소 열유속 표시를 제공합니다.
기존 균질 직사각형/P1 headless solver를 사용하며 상수 등방 k·열원,
변 Dirichlet·단열·상수 외향 flux/Robin조건을 다룹니다. 기존 광학동작과
generic-route 열 guard는 유지합니다. 과도 UI·해석 전 메시 preview·임의 형상·
자동 연성·새 결과저장 endpoint는 이 인터페이스 범위 밖입니다.

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

서버 후보는 다음 전용 route를 구현하며 아직 수용된 main 기능은 아닙니다.

| Route | 후보 동작 |
| --- | --- |
| `GET /api/capabilities` | 버전 있는 정상열 capability·설정 자원 정책 |
| `POST /api/thermal/validate` | 엄격 JSON envelope·공개 문서 검증·preflight |
| `POST /api/thermal/run` | 재검증·용량 예약·입력 캡처·공개 run |
| `GET /api/jobs/{job}` | 제한된 열 상태/log/error·응답 소유 tag |
| `GET /api/jobs/{job}/result` | 성공 후 완전 검증·인코딩된 정상 payload 하나 |

기존 `/api/validate`는 열 `ok=false`를 유지하며 generic `/api/mesh`,
`/api/run`은 열/공진기 실행 거절을 유지합니다. 기존 공진기 schema 검증과
실행은 별개입니다. 열 지원은 generic 광학 guard 제거 대신 전용 route를 사용해야
합니다. 과도 문서·시간/history selector는 미지원입니다. Capability가 없거나
잘못되면 열 동작을 비활성화하되 기존 광학 시작을 막지 않습니다.

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
Job/thread/solver 할당 전에 절점·요소 수를 preflight합니다.
Raw scalar 수는 v1=6N+5M+2D, v2=10N+5M+2D이지만 raw-byte 추정이나
encoded cap으로 Python/solver peak memory를 제한했다고 볼 수 없습니다.
복사·list·희소분해·직렬화·동시 작업의 overhead가 있습니다.
실제 공유호스트 측정은 부하를 공개해야 하며 전용 성능 baseline을 주장하지 않습니다.
전체 배열을 반복 직렬화하는 대신 제한된 encoded 결과를 유지합니다.
새 save/upload/path/overwrite API나 자동 재시도 queue는 없습니다.

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
과거 좁은 Windows 검사는 Windows 전체 물리나 macOS를 인증하지 않습니다.
Universal wheel이 OS 동작을 입증하지 않습니다.
실행할 수 없는 플랫폼은 미검증으로 기록하고 플랫폼 실패를 설명 없는 skip으로
바꾸지 않습니다. 실제 browser 상호작용·자원 실측도 HTTP/Node/설치 검사와 별도입니다.

## 테스트 지도와 근거 상태

| 계층 | 필요한 근거이며 통과 주장이 아님 |
| --- | --- |
| Server | 할당 전 strictJSON/limit; 공개API positive control; v1/v2/D0 metadata; 공개속성 한 번 복사·검사; 모든 terminal 경로 제한 |
| 물리 | 독립 선형/가산·열원/Robin 정답·SI변환·기존수렴·음성대조 |
| Frontend | dirty/revision/sequence/capability/render 결정적 truth-table; stale성공/오류/finally 무시 |
| 표시 | 절점/요소 구별 fixture·절점보간·flatflux/전역부호·상수/음수K |
| 자원 | 용량해제·실패기록보존·byte/count/TTL 경계·별도 peak/직렬화실측 |
| 배포/플랫폼 | 배포자산/import·source/설치소비자·정확필수CI·OS별결과 |
| Browser | 실제 Canvas상호작용; HTTP TestClient·Node시험과별도 |

n8/16/32/64 마지막 두 구간 온도 L2차수>=1.8, flux차수>=0.9,
정규화 residual/열수지1e-10·SI상사성1e-9를 유지합니다.
Studio거절이 물리gate 면제가 아닙니다. 수치·HTTP·Node·설치·browser·플랫폼 수용은 각각 정확 checkout의 실제 실행이
필요합니다. Linux통과가 Windows/macOS
통과를 뜻하지 않으며 시험 정의가 실행·수용·main통합을 뜻하지 않습니다.
