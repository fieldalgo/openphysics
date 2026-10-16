# Transient Studio 자원 관측기
[English](../../../transient_resource_probe.md)

stdlib 도구 `ci/tools/probe_transient_studio_resources.py`는 이미 실행 중인 명시적 loopback 서버를 관측한다. 서버설치/시작·solver import·수치수용·용량인증을 하지 않는다. 시도마다 새 evidence 디렉터리를 사용한다.

```sh
python ci/tools/probe_transient_studio_resources.py --plan --output records/transient-shapes
python ci/tools/probe_transient_studio_resources.py --base-url http://127.0.0.1:8000 --document input.json --source-commit FULL_SERVER_SHA --output records/transient-http
```

input은 envelope가 아닌 document다. HTTP모드는 capabilities→validate→solve정확1회제출(재시도없음)→유계poll→manifest/마지막Tframe→동일전체query10회(최초1+반복10=frame GET총11회)→최대16행Hpage를 기록한다. 동일query의status/bytes/hash를 비교하되 transient 요청별encode는 허용되므로 hash만으로 getter/solve0을 증명하지 않는다. 429/거절/오류/timeout은 capacity성공이 아니고 timeout도 server solve취소가 아니다.

operator입력SHA(실제source검증아님),환경/inputhash/HTTP경로·status·bytes·hash·시간/선택raw/실패/exit를 저장한다. redirect/proxy/credentials/비literal·비loopback주소는 제외한다. request<=1MiB,read<=4MiB(status128KiB),전체요청<=160,framecache없음. 원문서/응답에 사용자모델데이터가 있으므로 적절한 records경로를 쓴다. 기존output은 덮어쓰지 않는다.

## Workload와계수
plan은 배열할당·물리실행없는정수산식이다. N=(n+1)^2,M=2n^2,Nt,D에대해13배열scalar수
`S=2N+3M+D+Nt*(2N+2M+D+3)+3*(Nt-1)*N`.
8S는8byte가정이고실제는dtype별itemsize*size합이다. 유일한D를완전경계검증으로증명하기전D=N상계를쓴다. BC입력/metadata/summary복사/예약/listJSONworkspace/native/transport는별도다.

small n2/Nt3,medium n16/Nt8은준비shape. 16MiB raw후보바로아래/위의보수적D산식을탐색한다. 물리fixture·실제preflight·cap+1·실측용량이아니다. exact구현의사전검사와독립유효문서로실행하고거절도보존한다. 수용을위해D/BC/입력을낮추거나rescale하지않는다.

동반계측필수: 실제shape/dtype/rawbytes와사전예측, ingress-before-buffer/BC/metadata, sharedraw+manifest+예약+pins합과allocationID, 결정적ASGIsend대기중eviction·새admission, encoded응답도최종참조까지계수, slice/list전readslot획득·send-finally까지보유·초과429·예외정확해제, capture후getter/solve0과steadybytecache보존, ingress1/solver1독립·crossroute/failure후다음성공요청, servercurrentRSS/누적highwater/tracedlive·peak/native범위와중첩시간, exactsource/origin/계측patchhash. socketbackpressure만으로slowreader/pin을증명하지않는다.

도구는private store/추측metricsendpoint를읽지않는다. 내부memory/lease/counter는명시적미측정이다. 향후계측runner는생산원문/수치gate/steady계약을보존해야하며독립물리·수명·플랫폼CI와구분한다.

## 별도 fresh-process 계측 companion
`ci/tools/profile_transient_studio_resources.py`는 실제 source Studio 서버를 새 child에 띄우고 HTTP client는 parent에둔다. `instrumented-report.json`, 선택응답원문, `child.stderr`를저장한다. opt-in이며steadyCI중복실행에자동연결하지않는다.

```sh
python ci/tools/profile_transient_studio_resources.py --source-root . --expected-commit FULL_CHECKOUT_SHA --document small-valid-transient.json --output records/transient-instrumented-small
python ci/tools/profile_transient_studio_resources.py --source-root . --expected-commit FULL_CHECKOUT_SHA --document near-valid-transient.json --reject-document over-budget-transient.json --output records/transient-instrumented-near
```

HEAD정확일치/추적package무변경을검사한다. 기존declareddeps만사용,import/start실패는원문보존하고설치/재시도없음. 호출별freshprocess/실제solve1회다. 독립유효small/medium/near문서를각각실행한다. 선택over문서는413·추가solve0을기대하며429는그actor의실패로보존하고capacity성공으로세지않는다.

실제publicrun/capture/공개forwardedgetter/strict·viewencode/pin/reserve/readpublish/release를원함수그대로호출하며계수한다. producer구현module을import하지않고실제Studio전송store만계측한다. 첫phase는publicobserver(frame11GET+Hpage1),별도phase는동일frame11GET이며run/capture/getter증가0·허용viewencode11을확인한다. 전체count를단일11회workload로혼동하지않는다.

실제frame ASGIsendbody를최대30초hold하고두번째frame429→hold해제→다음read200·pin/workspace해제를검사한다. solver/응답bytes는변경하지않는다. 결정적transporthold이며socket속도시험이아니다. hold중eviction/disconnect/send실패/TTL/모든수명actor는별도미검증이다.

artifact `transient-instrumented-resource-v1`: child_start(PID/환경/version/baseline/originSHA256),requests(부모HTTP시간/status/bytes/hash/raw),phases(서버memory/store/counter전후·delta/hold거절),store(active/pending/reserved/retained/workspace/live/retired/snapshot/pins/raw·manifestbytes/allocationID목록),cleanup(stop상태/최종snapshot/originafter),failure/exit_code/child_exit/forced_stop. allocationID는프로세스로컬값이다. 강제종료는수용실패이며harness정리이지서버cancelendpoint가아니다.

Linux /proc currentRSS, Linux/macOS정규화ru_maxrss누적highwater를분리한다. 다른플랫폼RSS는미지원값으로남긴다. tracemalloc은import/serverstartup후시작하며native일부누락. native6thread변수1,hook중첩시간/계측overhead/최대256events와계속누적counter를구분한다. encoded/retained/RSS는서로다르고32MiB는RAM보증아님. originhash를exactGit/packagebytes와별도대조해야한다. 수치/최대capacity수용주장없음.
