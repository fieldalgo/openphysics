# Studio 과도 열전도

[English](../../../../../packages/simcase/thermal_transient_studio.md)

**한눈에 보기**

- **하는 일:** 직사각형 `thermal.transient2d` 문서를 위한 Studio 화면으로, 전용 capability·검증·실행·manifest/frame/history route를 씁니다. 정확한 요청 시간(기본값은 마지막)을 골라 절점 Kelvin과 요소 열유속을 보고, 열량 H[J/m]와 이차 범함수 V[J K/m] 이력을 페이지 단위로 봅니다. 재료 영역이 있는 과도 열전도 문서도 Studio의 영역 한도 안에서 같은 방식으로 검증·실행·표시하며 영역 색, 경계, 범례, 영역 표를 보여 줍니다([영역 문서](#영역-문서) 참고).
- **한계:** 새 솔버, 보간, downsample, 과도 열유속·Robin, restart, 연성, 취소·삭제·저장·NPZ endpoint가 없으며, 화면을 바꿔도 솔버를 다시 돌리지 않습니다. 설정한 한도는 `candidate-unmeasured`이며 용량 보장이 아닙니다.
- **검증:** [과도 Studio 독립 수용 검증](studio_transient_thermal_independent_validation.md)을 참고하세요. 특정 커밋의 결과는 그 커밋의 CI 실행에서 확인하세요.

## 제공 상태·범위

이 checkout은 전용 capability·HTTP 검증/실행·manifest/frame/history route와
배포 페이지의 시간/field/H/V control을 갖춘 과도 Studio 인터페이스를 구현합니다.
Capability는 지원하는 format·view·route와 설정된 제한을 알립니다.
`run_enabled`는 runtime 가용성과 유효한 제한 설정을 나타내며 실측 용량이나
성능 보장이 아닙니다. 구현과 검증은 별개입니다. 실제 실행·설치·browser·자원 및
플랫폼별 검증 범위는 정확한 checkout의 CI 결과와 artifact에서 확인하세요.
설정된 제한은 계속 `candidate-unmeasured`이며 이 설명은 새로운 통과 수치나
release를 주장하지 않습니다.
[Headless 과도 가이드](thermal_transient2d.md)는 기존 입력·저장이력을 정의하며
[정상 Studio](thermal_studio.md)는 별도입니다.

기존 고정 균질 직사각형/P1엔진·일관질량/후진Euler·상수k/c/열원·명시적요청시간을
사용합니다. 초기장은scalar/affine이고변Dirichlet은상수/요청시간표본,나머지는
단열입니다. 초기/BC일치는projection없이검사합니다. 유한한음수K를clamp없이
유지하며DMP/양수성보장은없습니다. 새solver·보간·downsample·과도flux/Robin·
아래 영역 문서를 넘는 임의형상/재료확장·restart·연성·cancel/delete/save/NPZ endpoint는없습니다.
View변경이solver를다시실행하거나문서를바꾸지않습니다.
재료 영역이 있는 과도 문서는 같은 route에서 별도 경로를 따르며
[영역 문서](#영역-문서)에서 설명합니다.

## 사용자 흐름

일치하는runtime패키지와선택적Studio extra설치뒤저장소루트에서시작합니다.

```sh
python -m pip install -e "packages/simcase[studio]"
python -m simcase.studio --no-browser
```

출력된localhost주소를엽니다. 시작만으로누락·미지원과도capability가활성화되지는
않습니다.

1. 완전한과도JSON을열거나붙여넣고명시적으로적용합니다. 엄격중복키/유한JSON검사를
   위해원문을유지합니다. 길이/K/s·양수k/c·초기장·BC·증가하는비음수time_s를
   선언합니다. 0아닌첫시간도유효하며dirty/invalid텍스트는old검증·결과를무효화합니다.
2. 전용과도capability로현재입력을검증합니다. HTTP200도bodyok=true여야유효합니다.
   Run은재검증·snapshot캡처·공개simcaseAPI를사용하며광학mesh-only preview는없습니다.
3. 명시적으로실행합니다. 완료후실제staticmesh·정확요청시간·descriptor를가진typed
   manifest를수용합니다. 기본선택은time0/반올림시간조회가아닌마지막정수index Nt-1.
4. 정확time_s[i]의온도K·요소qx/qy/크기를고릅니다. 현재frame min/max·단위를
   표시합니다. 시간이다르면같은색이같은절대값을뜻하지않을수있습니다.
   Globalextrema scan/API를추가하지않습니다.
5. 최대16행H/Vhistorypage를명시적으로엽니다. Page는정수halfopen[start,stop)이며
   자동다음page조회·조용한clip없음. 시간/field선택은데이터조회이며재해석하지않습니다.
6. 현재view오류는wrongtimefield/hover/label을지우고명시적retry를표시합니다.
   새solve는명시적새run이필요합니다. 편집/import/newrun/type변경이oldview를
   무효화하며stalesuccess/error/finally는현재상태를바꾸지못합니다.

초기UI는T/q/HV만노출하며rate공간장·rate표는없습니다.
독립소비자를위한원rateAPI의미는보존합니다. Animation·임의substep·nearest
외삽을뜻하지않습니다.

## 시간축·단위·물리 의미

N절점,M삼각형,Nt요청시간,D중복없는지정절점입니다.

| 양 | Shape | 축 / 단위 |
|---|---|---|
| nodes_m, triangles | (N,2), (M,3) | static / m, 정수CCW연결 |
| time_s | (Nt,) | 요청시간 / s |
| temperature_k | (Nt,N) | time_s / 절점K |
| heat_flux_w_m2 | (Nt,M,2) | time_s / 요소중심W/m² |
| source_load_w_per_m | (Nt,N) | time_s / 깊이당절점W/m |
| reaction_w_per_m, residual_w_per_m, storage_rate_w_per_m | (Nt-1,N) | time_s[1:] / 절점W/m |
| heat_content_j_per_m | (Nt,) | time_s / H[J/m] |
| quadratic_functional_jk_per_m | (Nt,) | time_s / V[J K/m] |
| dirichlet_node_ids | (D,) | static / 정렬중복없는정수ID |
| dirichlet_temperatures_k | (Nt,D) | time_s / K; D0는(Nt,0) |

Index0에는T/flux/진단열원f0가있고reaction/residual-step/storage rate는없습니다.
i>=1의rate행은i-1이고구간[time_s[i-1],time_s[i]]입니다.
초기rateAPI는0을만들지않고422를반환합니다.
[2,2.03,2.1,2.4,3]에서기본i4는정확3s,i2는2.1s입니다.
포맷label이같은인접시간도서로다른index입니다.

```text
q = -k grad(T)
storage_n = M*(T_n-T_(n-1))/dt_n
residual_n = storage_n + K*T_n - source_n
reaction_n = residual_n on fixed nodes; zero on free nodes
(H_n-H_(n-1))/dt_n = sum(source_n)+sum(reaction_n)
outward_D,n = -sum(reaction_n)
H_n = 1^T*M*T_n            [J/m]
V_n = .5*T_n^T*M*T_n       [J K/m; not stored heat]
```

Reaction은내향열주입,outward_D는thermostat기여이며요소flux직접적분이아닙니다.
H는상수c·0K기준sensiblecontent이며보편enthalpy가아닙니다.
V는저장열·기계에너지가아니며일반H/V단조성도보장하지않습니다.
H/rate에실제깊이m를곱하면J/W지만깊이변환은이UI범위밖입니다.
Raw좌표는m이며축은최상위display_length_in_m·문서길이선언을사용합니다.
온도는절점선형P1,flux는요소상수·전역+y위쪽이고화살표는viewscale입니다.
파생overflow는view거절입니다.

## Typed 조회·응답 소유권

과도result/layoutID는thermal.transient2d-result-v1과
thermal2d-transient-p1-node-cell-v1입니다. Manifest/frame/history는별도wireID
studio-thermal-transient-v1,studio-thermal-transient-frame-v1,
studio-thermal-transient-history-v1를사용합니다. 광학/정상layoutfallback없음.

Manifest에는staticmesh·최상위time_s·immutable summary·기본마지막index·
13개fielddescriptor(fullshape/unit/location/axis/available_views/initial_available/
ui_supported)가있습니다. 초기UIfield는T/q/HV만입니다.
Frame은캡처행하나,H/Vframe은scalarshape[],page는[rows],vectorpage는[rows,M,2].
Staticmesh를매frame복제하지않습니다.

Frame/history는result_id와정확정수index/range가필수입니다.
Run counterclient_revision/request_seq와view frame_seq는별개입니다.
Job/result/revision/runsequence/field/index-or-range/frame_seq가맞을때만commit합니다.
ManifestURLtemplate는상대sameorigin수용job경로여야하고안전한query대입을사용하며
scheme/host/fragment/traversal을금지합니다.
Frame_seq를포함한동일전체query는데이터/bytes가같습니다.
과도조회는immutable캡처행을on-demandencoding할수있지만producergetter재조회·
resolve·encodedframecache없음. 기존정상immutableencoded응답동작은불변입니다.

## 영역 문서

`geometry`에 `shapes`나 `background`가 있는 `thermal.transient2d` 문서는
`/api/thermal/transient/validate`와 `/api/thermal/transient/run`에서 Studio의 영역
경로를 따르며, 그 밖의 문서는 바뀌지 않은 직사각형 경로를 따릅니다. 형상 한도,
summary 하한, worker thread 검증, job 단계의 절점·요소 한도는 정상 영역 문서와
같습니다([정상 Studio, 영역 문서](thermal_studio.md#영역-문서)). 요청 시간 검사는
직사각형 것과 같으며 코드와 메시지도 같습니다.

| 항목 | 영역 manifest |
| --- | --- |
| Result·layout ID | `thermal.transient2d-regions-result-v1`, `thermal2d-transient-p1-node-cell-regions-v1` |
| Manifest | `payload_format = "studio-thermal-transient-regions-v1"`, 같은 최상위 필드 16개 |
| `arrays` | `nodes_m`, `triangles`, `dirichlet_node_ids`, `triangle_regions`(삼각형마다 영역 번호 하나) |
| Descriptor | 직사각형 descriptor 13개와 `triangle_regions`: shape `[M]`, 단위 `1`, 위치 `triangles`, 축 `static`, view 없음, `ui_supported=false` |
| Frame·history page | 직사각형 ID `studio-thermal-transient-frame-v1`·`-history-v1`에 job이 저장한 영역 쌍을 붙임; `triangle_regions`는 frame·history 필드가 아님(400 `invalid_query`) |
| Capability | 과도 블록 안의 중첩 `regions` 키: 영역 쌍, 위 payload 형식 세 개, 영역 `limits` 다섯 개 |

영역 job의 raw 이력은 16 MiB raw 한도 안에 영역 번호(삼각형마다 8 byte)도
담습니다. 그래서 절점·요소 한도는 요청 시간 수 nt로 정합니다.

```text
n_cap = min(10201, floor((16 MiB/8 - 3 nt) / (10 nt + 8)))
m_cap = min(20000, 2 n_cap)
```

D <= N이고 M <= m_cap이면 raw 이력은 많아야 (10 nt + 8) n_cap + 3 nt개 scalar이므로
해석 전에 한도 안에 들어갑니다. 절점 한도는 nt <= 19에서 10201, nt = 64에서 3236,
nt = 128에서 1627입니다. nt가 정한 절점·요소 한도를 넘는 메시는 job 오류
`history_limit_exceeded`로 끝나며 메시지는 그 한도와 시간 수를 밝힙니다. nt가 정하지
않은 한도를 넘으면 `mesh_limit_exceeded`입니다. 예를 들어 시간이 20개이면 nt가 절점
한도(10082)를 정하지만 요소 한도는 일반 20000 그대로입니다. 이 한도는 D = N, M = 2N을
가정하므로 실제 이력은 들어가는 메시도 거절할 수 있습니다. 예를 들어 배포 과도 영역
예제를 메시 크기 0.5 mm, 시간 128개로 돌리면 절점이 1649개로 1627을 넘습니다.

페이지는 영역 manifest를 정상 영역 결과와 같은 방식으로 보여 줍니다([정상 Studio,
화면](thermal_studio.md#화면) 참고). 메시에 영역 색과 경계를, 모든 frame에 경계를
그리고, 범례와 커서 줄의 "; region 이름 (재료)", 체적 열용량 ρc를 더한 영역 표를
보여 줍니다. 정상 페이지처럼 검증할 때 문서 종류를 고정합니다.

## 동시성·메모리·회복

| 제한 | 계약 |
|---|---|
| 공유thermal ingress1 | 정상+과도validate/run이bodybuffer/Documentcopy전획득;초과429/무대기 |
| 공유solver1 | 별도admission;client편집이active해석을취소하지않음 |
| 공유과도read1 | Frame·history/HV가slice/list/JSON전획득;초과429/send-finally까지점유 |
| 보존 | 공유terminal2/retained32MiB/oldestreleased done/error회수;active/optical보존·TTL최대300s |
| 후보byte/time상한 | request1MiB/raw16MiB/manifest4MiB/framepage4MiB/Nt128/N10201/M20000/page16 |

상한은candidate-unmeasured정책이며실측용량/RSS/시간보장이아닙니다.
Sharedingress로동시정상요청도명시적거절할수있고opticalroute는불변입니다.
Permit은성공/schema·streamerror/disconnect/cancellation/모든예외에해제하며
old중복해제가나중owner를해제하지않습니다. 숨은retryqueue·가짜solver취소없음.
영역 문서의 검증은 worker thread에서 돌고, 그 permit은 연결이 끊기거나 요청이
취소되어도 thread가 끝날 때에만 해제됩니다. 따라서 취소된 영역 요청도 검증이
끝날 때까지 다른 열 요청을 429로 거절할 수 있습니다.

Reader는send종료까지immutablerawbacking/encodedresponse를pin합니다.
논리eviction뒤에도slowclient참조가남으면계상을유지합니다.
같은할당참조는중복하지않고별도copy는계산합니다.
Read출력/workspace예약은retained논리데이터와별개입니다.
Pinned+retained+reservation이안맞으면oversubscribe대신429입니다.
전체solver이력/희소factor/decodedDocument/summary·capturecopy/HTTPbuffer는
추가메모리이며boundedframe전송이streaming은아닙니다.

| 오류 | 사용자 의미/회복 |
|---|---|
| validate200okfalse/run400 | 현재문서invalid;수정필요·oldsnapshotrun없음 |
| malformed400/media415 | JSON/envelope/application/json교정;job없음 |
| resource413/429 | 요청/ingress/solver/read/budget명시거절;자동retry/mesh·time축소없음 |
| pending409/stale409 | 미완료/잘못된resultidentity;다른결과로조용히대체금지 |
| range/initialrate422 | 잘못된index/range/초기rate없음;반올림/가짜데이터없음 |
| 회수/만료/미지404 | TTL전에도불가할수있음;명시적새run만 |
| unexpected500/invalidpayload | 현재연산실패;부분성공이력/광학fallback없음 |

Errorecho는검증safe counter·권위acceptedidentity만사용합니다.
UntrustedstaleID가acceptedID를대체하지않고unknown404는이를만들지않습니다.
오류는제한plaintext입니다. 만료/viewretry/clientabort가globaljob삭제나
다중사용자인증/격리권한을주지않습니다.
Headless저장은별도:옵션실행전/document snapshot결속/새caller소유경로/
incomplete marker·summary마지막/적대적race·crashrollback보장없음.
Headless가이드를참조하며Studio저장API는추가하지않습니다.

## 재현·검증 체크리스트

이는필요검사이며이문서에서얻은결과가아닙니다.
구현·실제시험·exact통합CI·main반영·release를구분합니다.

- 균일headlesscontrol k2.5/c4/Q8/T0=300,t0=0은300+2t기대.
  t0=2/T0=300은300+2*(t-2)이며global300+2t에는T0=304필요.
- Nt2/비균일·0아닌시간/첫·끝/D0/affine·sampledBC/초기32eps무projection/
  signedK무clamp/정확descriptor·ID·timeaxis.
- 독립public수치/oracle·원n8/16/32/64마지막두온도L2차수>=1.8/flux>=.9/
  정규화residual·열수지1e-10/SI1e-9·원시간/구적/음성control유지.
- Dirty/duplicateJSON·validate200실패/run400·역순frame/page·같은index retry/
  field변경/hiddentab/stalesuccess-error-finally/명시429회복/
  실수solverrerun·globaljob삭제없음.
- N/M구별syntheticindexfixture는표시·축검사이며PDE/browser/resource/
  full13field수용이아님.
- Crossrouteheldstreamingress·모든실패해제·slowsend/disconnectpin·
  eviction/byte계상/정상cachedbyte보존.
- Exactsource/installedorigin·sdist/wheel내용·byte·배포Node·실제browser/HTTP·
  Linux/macOS/Windows결과. Node/HTTP가실제Canvas근거는아니며Linux/
  universalwheel이다른OS통과를입증하지않음.

정확검증명령·artifact는
[개발 안내](../../development.md)를
참조하세요.
없는실행은미검증이며가용하지않은도구/선언fixture/과거steady통과를과도수용으로
바꾸지않습니다.
