# Studio 정상 열전도

[English](../../../thermal_studio.md)

## 제공 상태

**사용자 계약 초안: 구현·검증 대기.** 검토 기준은
`6d6eac56d1dddb8bdfe3f23d6db78d674487a42b`이며 기존 Studio route는
아직 열 문서를 거절합니다. 이 가이드는 예정된 전용 정상열 route/UI를 설명하며
현재 제공 기능이나 시험 통과를 뜻하지 않습니다. 상태를 바꾸기 전에 정확한
server/frontend 후보와 실측 자원 제한을 확인해야 합니다.
Headless 수용이 UI 수용을 입증하지 않습니다.

예정 범위는 JSON-first `thermal.steady2d`입니다. 균질 직사각형/P1,
상수 등방 k·열원, 변 지정온도·단열과 별도로 통합하는 상수 외향 flux/Robin
계약을 사용합니다. 과도 UI·mesh-only preview·새 solver·결과저장 endpoint·
임의 형상·자동 연성은 없습니다. 기존 광학 동작을 유지합니다.
모델 단위와 기존 Python/CLI 흐름은 [headless 정상 가이드](thermal_steady2d.md)에서 시작하세요.

## 시작과 예정 사용자 흐름

저장소 checkout에서 일치하는 패키지와 선택적 Studio 의존성을 설치한 뒤
저장소 루트에서 시작합니다.

```sh
python -m pip install -e "packages/simcase[studio]"
python -m simcase.studio --no-browser
```

출력된 localhost 주소를 엽니다. 기존 시작 명령이 미구현 열 capability를
활성화하지는 않습니다.

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

## 단위와 물리 의미

| 표시/데이터 | 예정 계약 |
| --- | --- |
| 좌표 | raw `nodes_m`는 m; 축은 캡처 문서의 양수 metres-per-length-unit scale로 나눔 |
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

예정 typed payload는 wire format과 headless v1/v2 result/layout ID를 구분합니다.
V1 raw배열은 9개, v2는 13개이며 Robin-only v2의 Dirichlet 절점 수는 0일 수 있습니다.
정확한 허용 버전쌍·단위·위치·shape·유한한 비불리언 배열·유효 CCW 연결 정보를
검사해야 합니다. 알 수 없는 layout·누락 필드·잘못된 payload를 표시하면 안 됩니다.

## Route 경계와 회복

다음 전용 route는 **예정**이며 검토 기준에는 없습니다.

| Route | 예정 동작 |
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

예정 오류는 잘못된 입력400, 논리 검증실패200+`ok=false`, 요청/자원 제한413/429,
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
terminal 보존300 s입니다. 최종 capabilities는 실제 설정 정책을 공개해야 합니다.
필수 정책이 미설정이면 열 run은 비활성 상태를 유지합니다.
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
Studio거절이 물리gate 면제가 아닙니다. 이 초안 작성 중 새 수치·HTTP·Node·
설치·browser·플랫폼시험은 실행하지 않았습니다. Linux통과가 Windows/macOS
통과를 뜻하지 않으며 시험 정의가 실행·수용·main통합을 뜻하지 않습니다.
