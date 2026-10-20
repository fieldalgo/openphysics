# 정상열 Studio 독립 검증

[English](../../../../../packages/simcase/studio_thermal_independent_validation.md)

**한눈에 보기**

- **확인하는 것:** 실제 공개 솔버로 정상 열전도 Studio HTTP route(`/api/capabilities`, `/api/thermal/validate`, `/api/thermal/run`, 작업 상태·결과)를 검사합니다. 반환 배열은 생산 조립이나 refsol helper가 아닌 독립 요소 자산으로 감사합니다.
- **고정 기준:** 2차 열원 사례를 8/16/32/64에서 돌려 온도 L2 차수 ≥ 1.8, 요소 열유속 L2 차수 ≥ 0.9, Gauss 8/10 오차 차이 < 1%, 최세 메시 상대 영역 열유속 L2 ≤ 2%, 대수·보존 1e-10, SI 불변성 1e-9가 필요합니다.
- **범위:** 과도 UI, 메시 전용 미리보기, 새 솔버, 연성, 재료 확장, 저장 endpoint는 범위 밖입니다. 특정 커밋의 결과는 그 커밋의 CI 실행에서 확인하세요.

## 현재 범위와 근거

이 checkout에는 JSON-first 정상열 검증·실행, typed HTTP 결과와 독립 수용시험이
구현돼 있다. 본문은 검사 항목과 유지해야 할 수치 기준을 설명한다.
실제 source·설치본·브라우저·자원·플랫폼 결과는 정확한 checkout의 CI 로그와
원자료로 확인한다. 시험 정의와 preflight 부분집합만으로 전체 수용이나
릴리스를 입증할 수 없다.

사용법은 [Studio 가이드](thermal_studio.md), 환경·배포 요구사항은
[개발 안내](https://github.com/fieldalgo/openphysics/blob/main/docs/locales/ko/pages/development.md)를 따른다.
중간 구현 검토는 과거 이력이며 현재 runtime이나 수용 상태를 정의하지 않는다.

## HTTP suite의 검사 범위

`test_studio_thermal_acceptance.py`는 공개
`Document`, `run`, `ThermalRunResult`와 실제 HTTP 앱을 소비한다.
`/api/capabilities`, `/api/thermal/validate`, `/api/thermal/run`,
기존 job status/result 경로를 검사한다.
일반 광학 동작과 일반 validate/mesh/run의 heat 거절은 보존한다.
과도 UI, 열 mesh-only 미리보기, 새 solver, 연성, 재료 확장,
저장 endpoint는 범위 밖이다.

HTTP 양성은 실제 공개 solver를 사용하고 기존 독립
`Elements/model/audit/slab`으로 반환 배열을 감사한다.
이 자산은 생산 assembly나 refsol helper를 정답으로 쓰지 않고
삼각형 기울기·원 stiffness 작용·consistent 외곽 변 적분을 도출한다.
summary metadata는 일관성을 검사하지만 그 총량으로 기대 물리를 만들지 않는다.

## Analytic 사례와 보존된 gate

- **선형 가산 냉각:** 단위 정사각형, k=2 W/(m K), Q=0,
  left300 K, right g=2 W/m², h=4 W/(m² K), ambient290 K.
  왼쪽 경계 상대 x에서 T=300−7x K, q=(14,0) W/m²이다.
  적분 지정 외향 G=2, 대류 C=12, thermostat 내향 반력14 W/m이므로
  오른쪽 외향14, 왼쪽 thermostat 외향−14, 총 외향0이다.
- **이차 source:** L=.03 m, H=.02 m, k=12.5 W/(m K),
  Q=100000 W/m³, a=300 K, right g=100, h=20, ambient290.
  T=a+bx−Qx²/(2k),
  b=(QL−g−h(a−Ta)+hQL²/(2k))/(k+hL)이다.
  적분 source는 깊이당60 W/m이다.
- **Robin-only와 h=0 대조:** 독립 slab 계열은 좌우 외향 flux에서
  ambient를 도출한다. 양수 Robin anchor가 있는 v2의 빈 Dirichlet 배열은
  유효하며, 한쪽 h=0에서도 반대편 양수 anchor를 유지한다.
  숨은 고정 절점을 넣지 않는다.
- **SI 동등성:** m/mm/um 문서는 원점(.1,.2)m를 포함한 동일 물리
  직사각형이다. 좌표는 metre이고 표시 길이 단위로 field 단위를 바꾸지 않는다.

oracle은 K,H,fQ,G,B를 재구성하고
`rhs=fQ+B−G`, `C=HT−B`, `residual=(K+H)T−rhs`,
고정 반력=residual, 자유 반력0 및
`sum(G+C−reaction)=sum(fQ)`를 검사한다.
`load_w_per_m`은 source-only이다. 열량률은 깊이당 W/m이며 W나 기계 N/m가 아니다.

이차 HTTP 사례는 분할 **8/16/32/64를 순차 실행**한다.
마지막 두 구간 온도 L2 차수는 **>=1.8**, cell-flux L2 차수는 **>=.9**이다.
독립 Gauss8/10 오차 차이는 **<1%**, 최종 영역 상대 flux L2는 **<=2%**다.
대수·보존 normalized gate **1e-10**, SI 불변 **1e-9**를 유지한다.
gate와 fixture는 바꾸지 않았다. 영역 flux L2와 경계 normal-gradient 측정은 다르다.

## Typed wire와 음성 대조

wire는 `payload_format="studio-thermal-steady-v1"`,
`kind="thermal.steady2d"`, 쌍을 이룬 headless result/layout ID,
top-level `display_length_in_m`, `arrays`, `summary` 및
`job/result_id/client_revision/request_seq` identity를 사용한다.
중첩 `coordinates` metadata는 허용하지 않는다.
표시 factor는 finite 양수이며 선언 길이와 일치해야 한다.
`run_enabled=true`는 설정 정책·공개 API 가용을 뜻하며 성능 보장이 아니다.

v1은 node, triangle, temperature, cell flux, source load, reaction,
residual, Dirichlet ID와 prescribed temperature의 정확9 raw 수량이다.
v2는 `prescribed_outward_load_w_per_m`, `ambient_load_w_per_m`,
`convective_outward_w_per_m`, `system_rhs_w_per_m`을 더해13개다.
새 경계 키 부재는 v1, 빈 mapping이라도 새 키 하나의 존재는 v2를 선택한다.
빈 D는 버전·물리 계약이 허용할 때만 유효하다.

consumer는 정확 field 집합·shape·unit·location을 검사한다.
temperature(N,), flux(M,2), nodes(N,2), triangles(M,3), fixed arrays(D,)이다.
수치는 finite real nonbool, 연결·fixed ID는 범위 내 safe integer이며
fixed ID는 sorted unique이다. metadata 차원은 정확 integer list이며
동등한 float/bool로 대신하지 않는다.
응답 identity는 타입을 검사하고 승인된 요청과 대조한다.

20개 malformed-wire 대조는 layout/unit/shape, NaN/Inf/bool,
잘못된·fractional index, 필드 누락·추가, 표시 scale·선언,
폐기된 coordinates, metadata·identity 타입을 포함한다.
독립 N5/M4 fixture는 parser 구별용이며 solver 결과가 아니다.
별도6개 actor는 실제 공개 결과의 layout, unit, shape, finite 값,
dtype 또는 index를 포착한 공개 property로 변형한다.
주입점은 worker의 공개 `server.run`이다.
요구 결과는 job error, `has_result=false`, result 요청409이며
malformed payload를 게시하지 않는다. actor는 대체 solver가 아니다.

전용 route는 unsupported optical/transient 문서와 duplicate key,
nonfinite JSON, unknown key, 잘못된 counter 등 malformed envelope를 거절한다.
공개 export AST 검사는 Studio consumer의 private 수치 import와
`_raw_arrays` 호출을 거절한다.

## 재현과 결과 해석

설정된 검증 환경에서 저장소 루트 기준:

```sh
python -m pytest -q tests/simcase/test_studio_thermal_acceptance.py
```

별도 shipped-script/page-handler Node 검사는 다음과 같다.

```sh
node --test tests/simcase/studio_steady_thermal.cjs
```

HTTP 시험은 실제 비동기 job을 시간제한 polling한다.
각 현재 결과를 완전히 수신·감사한 뒤 다음 run을 제출한다.
admission/publication은 가장 오래된 released terminal done/error를 회수할 수 있다.
300s TTL은 최대 보관시간이며 active·optical은 보존하고 evicted ID는404다.
store reset, TTL 소진 대기, mesh 축소, 자원 거절 skip을 하지 않는다.
짧은 상태 polling 대기는 보관정책 우회가 아니다.

정확 commit·명령/exit·환경·실패/skip·원 수렴 JSON·source/installed origin/hash를
기록한다. 중복 전체 suite 대신 조율된 exact CI를 감사하며
기존 정상경계·과도·일반 Studio gate를 유지한다.

최종 수용에는 완료된 exact source·격리 설치 결과, 모든 물리·음성 대조,
배포·origin 감사, 자원·수명 근거와 지원 플랫폼 검사가 아직 필요하다.
frontend revision/render 소유권, 실제 Canvas 동작, 자원·직렬화 상한 실측은
별도 근거이며 이 물리 suite만으로 인증하지 않는다.
universal wheel이나 다른 OS pass는 플랫폼 검증이 아니다.
기존 headless 정상경계 수용이 Studio HTTP·렌더링 수용을 의미하지 않는다.
