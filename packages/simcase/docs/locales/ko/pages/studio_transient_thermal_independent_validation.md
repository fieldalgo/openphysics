# 과도 Studio 독립 수용

[English](../../../studio_transient_thermal_independent_validation.md)

## 근거 수준
전용 과도 Studio API가 포함된 통합 checkout을 위한 독립 시험 정의다.
test-only branch는 서버를 구현하지 않는다. 수집·HTTP 수치 실행·설치·플랫폼/
브라우저 결과는 정확 통합 commit별로 보고해야 하며 여기서 통과를 주장하지 않는다.
기존 engine/headless 수치·수렴 시험은 계속 필수다. 합성 wire나 손상 producer actor는
물리 solve 성공을 의미하지 않는다.

구성된 시험 환경의 저장소 루트에서 실행한다.

```sh
python -m pytest -q -s packages/simcase/tests/test_studio_transient_thermal_acceptance.py
```

성공 case의 studio_transient_independent_exact JSON은 정확 요청 시간,
필드별 최대 절대오차 및 원 H/V 이력을 기록한다. JUnit·명령 exit·환경·source/module
hash와 함께 보존한다. -s가 없으면 성공 출력이 capture되어 숫자가 누락될 수 있다.
이때 다른 API/commit 실측을 차용하지 말고 누락으로 보고한다.
archive 시험과 독립 oracle 의존파일을 source checkout 밖의 isolated 설치 환경에서
실행하는 것은 별도 수용 단계다.

## 물리 정답과 불변 gate
studio_transient_independent_fixtures.py는 기존
transient_headless_independent_oracle.py 및 transient_headless_independent_cases.py를
import한다. 독립 P1 geometry/mass/stiffness action과 analytic state가 정답이며
생산 행렬·reduced helper·refsol·summary totals를 정답으로 사용하지 않는다.
독립 물리 수용 이후 별도 public Document/run 이력과 동일성을 대조한다.
이는 일관성 검사이며 oracle이 아니다.

rectangle .002x.001m,k=2.5 W/(m K),c=4 J/(m³ K),
비균일 저장 시간[2,2.03,2.1,2.4,3]s다. 각 case를 m/mm/um에서 정의한다.

| case | 독립 기대 |
|---|---|
|shift uniform heating|initial300K,Q8W/m³,T=300+2(t-2),q=0|
|absolute uniform heating|initial304K,Q8,T=300+2t, 시간 원점 혼동 금지|
|signed cooling|initial300K,Q=-1600,T=300-400(t-2),최종-100K/clamp 없음|
|sampled exterior ramp|initial290K,Q12,모든 변290+3(t-2),uniform exact P1|
|all-fixed support|n1,initial290K,Q2,같은 ramp,내향 reaction20e-6W/m|
|affine|T=290+5000x,left290/right300,q=(-12500,0)W/m²,H=.00236J/m,V=.3481333333333333JK/m|

H=1^TMT와 V=.5T^TMT의 단위·의미는 다르다. storage=M deltaT/dt,
원 residual=storage+KT-fQ다. 고정절점 reaction은 내향이며 외향=-sum(reaction).
rate는 Nt-1 interval에 있고 초기 zero row가 아니다.
초기 projection·negative-K clamp·시간 보간·다운샘플 금지다.
원 normalized1e-10/SI1e-9/좌표1e-12 및 per-field scale을 유지한다.
기존 transient engine --suite all·원 temporal/spatial 수열·모든 구간 threshold·
5% companion-error 분리는 별도 필수 회귀다. BE/P1 exact HTTP control은
기존 PDE 수렴을 대체하거나 재정의하지 않는다.

## transport와 독립 음성 대조
13개 public field 전부 검증한다. manifest static 배열은
nodes_m/triangles/dirichlet_node_ids이며 time_s는 정확 top-level 축이다.
descriptor의 shape/unit/location/time axis/initial availability를 확인한다.
기본 frame은 Nt-1이다. 모든 동적 field를 전 저장 frame에서 재구성하여 history와
대조한 뒤 독립 기대 배열과 검사한다. T는 nodal, 공급 q는 cell-centered이며 절점
평균을 만들지 않는다. H/V frame은 shape[]인 숫자 scalar이지 길이1 vector가 아니다.
Nt2는 단 하나의 interval을 확인하고 실제 Nt17 H/V page[0,16)/[16,17)은
마지막 partial page와 17행 요청 거절을 확인한다. 조용한 truncation은 금지다.

manifest/frame/history의 result/layout pair,job/result identity,
원 client_revision/request_seq와 별도 view frame_seq를 확인한다.
frame/history query에는 result_id가 필수다. 정수 i는 state rowi,
rate i>=1은 rowi-1 및[t[i-1],t[i]],i0 rate는422다.
frame_seq를 포함한 동일 전체 frame query는 byte가 같아야 한다.
다른 view sequence 간 byte동일성이나 encoded cache는 요구하지 않는다.
query/raw JSON에서 duplicate/unknown/missing,bool/fractional/range,
stale identity,잘못된 시간/단위·초기BC불일치를 검사한다.

producer 음성8종은 실제 public result를 먼저 얻은 뒤 layout/unit/shape/nonfinite/
bool/index/time/rate axis를 손상시킨다. job error와 result 미게시를 요구한다.
frozen result subclass는 명시 구성하며 생산 객체를 수정하지 않는다.
수치 음성7종은 H/V·storage·source/flux/support 부호·시간원점·초기 rate 축을
손상시켜 독립 수학의 거절을 요구한다. 숫자는 시험 정의이며 관측 pass 수가 아니다.

reset/TTL대기/가짜 양성solver/skip/xfail/허용치완화로 capacity를 우회하지 않는다.
case를 순차 실행하며 다음 job이 회수하기 전에 현재 result를 완전히 읽는다.
60초 bounded 비동기 poll은 시험 관측 한도이며 solver 취소나 생산 timeout이 아니다.
shared admission/pinned-response accounting·실브라우저 Canvas/current-frame minmax·
플랫폼별 자원 실측은 별도 suite다. 본시험만으로 capacity/RSS/browser/3OS를 보장하지 않는다.
