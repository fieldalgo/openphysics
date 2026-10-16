# Studio 과도 열전도

[English](../../../thermal_transient_studio.md)

## 제공 상태·범위

이 문서는 과도 Studio 통합 계약입니다. 공유 admission/retention기반과
typed 과도 JavaScript모듈은 제출됐지만 검토 checkout의 전용 과도 HTTProute·
배포페이지 연결은 미완료입니다. 정상 Studio와 headless과도 API/JSON/CLI/저장은
기존 인터페이스로 사용합니다. 일치하는 serverroute·page연결·명시capability가
통합되기 전에는 아래 흐름을 실행 가능한 browser경로로 해석하지 마세요.
구현·runtime시험·exactCI·main수용은 별개이며 새로운 runtime·browser·플랫폼·
용량 결과를 주장하지 않습니다.
[Headless 과도 가이드](thermal_transient2d.md)는 기존 입력·저장이력을 정의하며
[정상 Studio](thermal_studio.md)는 별도입니다.

기존 고정 균질 직사각형/P1엔진·일관질량/후진Euler·상수k/c/열원·명시적요청시간을
사용합니다. 초기장은scalar/affine이고변Dirichlet은상수/요청시간표본,나머지는
단열입니다. 초기/BC일치는projection없이검사합니다. 유한한음수K를clamp없이
유지하며DMP/양수성보장은없습니다. 새solver·보간·downsample·과도flux/Robin·
임의형상/재료확장·restart·연성·cancel/delete/save/NPZ endpoint는없습니다.
View변경이solver를다시실행하거나문서를바꾸지않습니다.

## 통합 후 사용자 흐름

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
- Exactsource/installedorigin·archiveasset/byte/link·배포Node·실제browser/HTTP·
  Linux/macOS/Windows결과. Node/HTTP가실제Canvas근거는아니며Linux/
  universalwheel이다른OS통과를입증하지않음.

정확검증명령·artifact는
[검증 가이드](https://github.com/fieldalgo/openphysics/blob/main/ci/docs/README.md)를
참조하세요. 패키지간/root링크는network접근이필요합니다.
없는실행은미검증이며가용하지않은도구/선언fixture/과거steady통과를과도수용으로
바꾸지않습니다.
