# 정상열 Studio 독립 수용

[English](../../../studio_thermal_independent_validation.md)

## 근거 수준

main `6d6eac56d1dddb8bdfe3f23d6db78d674487a42b`를 기준으로 준비했다.
이 기반은 일반 Studio endpoint에서 열을 거절하며 전용 정상열 endpoint가 없다.
본문은 사전 수용 정의이며 구현 완료나 통과 실측이 아니다. 별도 정상열 경계
독립 자산은 기능 결합 시 필요하고 여기서 복제하거나 대체하지 않는다.

준비 중 Pythonparse/compile,수집,HTTP,solver,source/installed suite,
browser/Node/플랫폼 실행은 없었다. 최상위10시험 함수와 parameter 사례는 정의뿐이다.
합성 wire fixture/TestClient 정의는 렌더링·설치·플랫폼 지원 증명이 아니다.

## 범위와 보존 경계

대상은 추가 JSON-first 정상열 검증/실행 후 실제 결과 mesh,
절점 P1 온도K 및 삼각형상수 fluxW/m²이다. 채택설계는 capabilities와 전용
/api/thermal/validate,/api/thermal/run,기존job/status/result 및 엄격typed
정상열결과를 사용한다. 일반광학동작과 일반endpoint의heat거절은 보존한다.
과도UI/열mesh-only미리보기/새solver/저장endpoint/연성/재료확장은 제외한다.

시험은 공개Document/run/ThermalRunResult와HTTP를 사용한다.
생산assembly/private rawarray/refsolhelper를 정답으로 쓰지 않는다.
기존 독립 정상경계 Elements/model/audit/slab을 참조하며
수치oracle와 고정허용치는 바꾸지 않는다.

## 물리 기대값

선형 단위정사각형은 k2/source0/left300 K/right외향g2 W/m²,
h4 W/(m² K)/ambient290 K이다. T=300-7x,q=(14,0).
적분G2/C12/thermostat내향반력14 W/m에서 총외향0이다.
좌표에비영원점이가능하고 식의x는왼쪽경계상대값이다.
m/mm/um문서는 동일한 실제SI배열을 유지한다.

이차slab은 L.03m/H.02m/k12.5/Q100000 W/m³/left300 K,
rightg100/h20/ambient290이다. T=a+bx-Qx²/(2k),
b=(QL-g-h(a-Ta)+hQL²/(2k))/(k+hL),source60 W/m깊이당이다.
비영source Robin-only 및h0+반대양수anchor계열은
좌우외향flux/ambient를 독립유도한다. Robin-only v2의 빈D는 유효하고
숨은고정절점을 넣지 않는다.

좌표/외곽변incidence에서 원소작용으로 K/H/fQ/G/B를재구성한다.
반환계약은 rhs=fQ+B-G,C=HT-B,residual=(K+H)T-rhs,
고정반력=residual/자유반력0,총외향sum(G+C-reaction)=sum(fQ)이다.
load_w_per_m은source뿐이며 metadata/summary총량이 정답을 정의하지 않는다.

고정분할8/16/32/64,마지막2구간온도L2차수≥1.8,
cellfluxL2차수≥.9,Gauss8/10오차차이<1%,최종영역상대fluxL2≤2%이다.
대수normalized1e-10/SI불변1e-9를 사용한다.
원gate이며Studio편의허용치가 아니다. 자원거절은보고하고mesh축소/skip로바꾸지않는다.

## Wire 계약과 음성 대조

초안binding은 studio-thermal-steady-v1/thermal.steady2d,
쌍을이룬headless result/layout ID,job/result/revision/sequence echo,
arrays mapping과복사summary metadata를요구한다.
실행전 명시된exact서버후보와필드binding을대조해야하며
특정구현이이미이키를쓴다는근거가아니다.

v1은정확9raw물리/geometry수량,v2는13개이다.
scalar는finite real nonbool,연결/fixedID는safeinteger/range와
필요한sortedunique를충족한다. shape/unit/location은정확해야한다.
온도(N,),flux(M,2),좌표(N,2),삼각형(M,3)이다.
독립N5/M4합성fixture는node/cell혼동검출용이며solver시험이아니다.

음성payload는layout/W/m단위/fluxshape/NaN·Inf/bool온도/
잘못된·fractionalindex/v2필드누락/추가time을변경한다.
consumer감사는수치비교전에거절해야한다.
두번째그룹은실제공개result를공개property만포착한의도적subclass actor로
변형한다. 서버는joberror/has_result=false/결과없음을반환해야한다.
malformedresult주입이며대체수치구현이아니다.
실제서버원문검토후공개producer호출에runhook을연결해야한다.

새headless경계키부재는v1,빈mapping이라도새키존재는v2이며
동일물리인경우배열의물리의미는같다.
전용route는optical/transient/malformedenvelope를거절하고
일반validate/mesh/run은heat거절을보존한다.
무관한기존광학시험은그대로유효하다.
duplicate/NaN/unknown/counter엄격거절은headless물리유효성과별개다.

공개export AST시험은Studio Pythonconsumer에서simcase import가__all__에있고
galerkin/refsol/private simcase수치import나_raw_arrays호출이없는지검사한다.
자원보존/peak실측과frontend revision/render truth-table은별도필수근거이며
이물리suite가인증하지않는다.

## 실행과 남은 일

exactserver/adapter binding·기능결합후저장소루트에서:

```sh
python -m pytest -q packages/simcase/tests/test_studio_thermal_acceptance.py
```

HTTP양성은실제공개solver/시간제한polling/반환배열독립감사를사용한다.
summary로물리기대값을만들지않는다.
저장소전체시험은중복하지않고정확CI에서기존정상경계/과도/일반Studio gate를보존한다.

미검증: exactwire이름/producer주입위치,실행·수집,malformedresult거절,
물리HTTP수렴,설치origin/archive소비,실제Canvas,Windows/macOS/최종통합.
기존정상경계C11/CLI/installed수용은별도기능결과이며exactCI원로그로확인해야한다.

## 초기 exact 서버 binding

원문검토로 시험을 server/adapter commit
533c5e8c3f50d05f52323588e81b4997500e00e5에 연결했다.
worker가공개server.run을호출하므로 malformed공개결과주입점이확인됐다.
wire는top-level display_length_in_m/arrays/summary 및
kind/job/result_id/client_revision/request_seq identity를사용한다.
중첩coordinates metadata는폐기됐고독립consumer가거절한다.

consumer는finite양수표시scale을선언m/mm/um또는명시in_m길이와대조하고,
정확metadata필드집합·status/result echo를검사한다.
bool/zero/nonfinite scale·선언scale불일치음성을추가했다.
malformed-layout actor는공개field_layout property뿐아니라
summary.field_layout도바꾼다. earlyadapter가summary pair를읽어
property만바꾸면의도한거절에도달하지않기때문이다.
시험정의정정이며producer보호/물리gate는변경하지않았다.
binding중새UNITS참조의누락import는실행전정적발견해정정했다.

요구자원정책은admission/publication압박때가장오래된terminal done/error를
회수하고active/optical을보존하며evictedID는404이다.
300s TTL은최대보관시간이다. 원mesh8/16/32/64를순차실행하고
store reset/mesh축소/TTL대기/skip을하지않는다.
기존짧은polling대기는실제비동기상태관측용이지보관정책우회가아니다.
run_enabled=true는유효설정정책/공개API가용을뜻하고실측성능인증이아니다.

early533에는run_enabled가아직없고terminal2보관뒤TTL만료전admission을
거절하므로생산후속수정이예정돼있다.
이초기자원동작을수용하거나시험으로숨기지않는다.
본단계exactHTTP/물리/설치/CI는모두미실행이다.
후속생산변경은별도source delta검토·정확결합CI가필요하다.
별도writer fixture수정은이branch에포함하지않는다.

## 후속 exact binding 판정

f8506b7490b52105c37a55e656dc8f23baa98647 정적검토가위의early533
자원미완료관측을대체한다. 서버는blob6c750aa452ae78a21f5a470bc0c1d6fb5aaeee0b
그대로이고adapter는blob4fd5633340ca945aff9c3fb878aeb40a2f6c106e이다.

adapter는공개result_format/field_layout을포착해summary pair와일치를
요구하며동일top-level표시factor/arrays/summary/identity를유지한다.
복사전배열shape/dtype/finite/크기를확인하고엄격encoding된결과만게시한다.
기존layout/unit/shape/nonfinite/bool/index actor는실제소비값을겨냥한다.

capabilities는검증된자원설정하에공개result API가용으로run_enabled를
명시한다. admission/publication은가장오래된released done/error를회수하며
active lease는제외한다. thermal기록은optical과분리되고TTL은최대보관시간,
evicted ID는404이다. reset/TTL대기/mesh수열축소/skip없이
초기terminal2이후admission문제가정적으로해소됐다.

이sourcebinding에추가독립시험/물리gate변경은필요없었다.
확정binding blocker미발견으로정적범위를승인한다.
실제HTTP/source/installed/음성거절/자원동작은정확결합CI가필요하다.
실측성능/browser/플랫폼수용은아니다.

## 정상경계 main 반영 후 Studio 재개 검토

main49ff59874af3c5140d0e8126b1feb18964953e7e의정상경계독립oracle와cases는
각각blob8957c5663e4dfacb62331c46c215f5872732c6bc,
963e6850099c1b5ffe458c9bd31b373327546f04로기존검토수학/fixture/gate와같다.
참조import는이제미게시의존이아닌반영된base에존재한다.

server/adapter c762c4e5fdb9700978a24f639e694630477b8679를검토했다.
server는blob6c750aa452ae78a21f5a470bc0c1d6fb5aaeee0b유지,
adapter는blob6ecec32a623d7f92ba6f4543d46b3fb1d3bd8170이다.
강화된log/error status byte계산은물리payload필드나공개runhook을바꾸지않는다.

순차HTTPmesh loop는각현재result를완전히수신/감사한뒤다음job을제출한다.
따라서이전terminal eviction은기대배열을바꾸거나과거jobID재조회를요구하지않는다.
n64는4225node/8192cell로설정10201/20000이내이고,
이차leftD65인v2 rawscalar는83340개이다.
정적크기사실이며encoding용량/peakmemory실측보장이아니다.
admission/publication압박으로300s전released done/error를회수할수있고
active/optical은별도보존한다. reset/TTLsleep/skip/mesh축소는추가하지않았다.

독립consumer정적틈을찾았다. Python동등비교에서metadata차원5.0이정수5와
같게통과할수있었다. 이제shape는list이며각항목정확int/nonbool을요구하고,
mapping형식/unit키/safeinteger·비어있지않은responseidentity도검사한다.
float/bool차원과float/bool/emptyidentity음성5개를추가했다.
이전15wire음성과6malformed공개result actor는그대로이며
물리기대값/4mesh/모든수치허용치는변경하지않았다.

조건부정적승인: main49ff/Fc762 binding의확정blocker미발견.
metadata틈은독립consumer시험정의문제이며확정생산결함이아니다.
Pythonparse/pytest/HTTP/solver/installed/browser/플랫폼실행은없었다.
실제반복run과전음성을포함한정확결합Studio source/installedCI가여전히필요하다.

## 최신main 검토와 다른 담당 시험 blocker

main6e9be99a10fba77d329063da973401f26d4ed0b5는검토된P2oracle
blob8957c5663e4dfacb62331c46c215f5872732c6bc와cases
blob963e6850099c1b5ffe458c9bd31b373327546f04를유지한다.
main49ff이후변경은검증/플랫폼기반·공개지침이며수치oracle가아니다.
이base에독립HTTP/엄격metadata fixture나원물리gate의추가코드수정은불필요하다.
공개지침과Linux/macOS/Windows설치검사는정확통합검증에계속포함된다.

F c762c4e5fdb9700978a24f639e694630477b8679의wire/resource소스는
원8/16/32/64순차실행과맞는다. 현재payload를수신·감사한뒤다음admission이
이전terminal을회수하므로소유중인현재기대배열을바꾸지않는다.
새반복실행실측이아닌소스수준판정이다.
store reset/보관대기sleep/skip/허용치변경은추가하지않았다.

별도B767cc8dbaeccd4a7cf85c828971d5324abdbd863에서확정시험정의
blocker를발견했다. tests/studio_steady_thermal.cjs307행의즉시실행함수는
load("p3JS")/load("p3NodeTests")를호출하지만파일에load선언/import가없다.
통상Node에서HTTP mock문자열구성중ReferenceError가발생해
검증/실행동작에도달하지못한다.
14–18행기존cap()로JSON.stringify(cap())를사용하면동일capability를제공한다.
이는타담당최소정정권고이며생산UI/수치계약/본독립suite변경이아니다.

이finding에Node/HTTP/수치실행은없었다.
원B소스를보존하고정정된exact후보의조율된Node실행이필요하다.
전체통합수용은이정정과정확독립source/installed/물리/metadata결과대기이다.
추가전체CI나수동dispatch는시작하지않았다.
