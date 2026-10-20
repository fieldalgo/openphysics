# 정상 열전도 경계 headless 독립 수용

[English](../../../steady_boundary_independent_validation.md)

## 상태와 범위

수용 코드는 경계 확장 통합 전 main
`6d6eac56d1dddb8bdfe3f23d6db78d674487a42b`에서 준비했다.
고정 기대값, 이후 정확한 원문 결합 검토와 보충 직접 경로 실측을 아래에서
구분해 기록한다. 이는 범위가 한정된 근거 기록이며 실시간 CI 상태 보고가 아니다.
전체 source·설치본·플랫폼 결과는 정확한 checkout의 CI 로그와 산출물을 확인한다.

시험은 경계 계약을 요구하며 가짜 구현, skip 또는 허용치 완화로 대신하지 않는다.
최초 준비 환경에서는 Python 구문 분석, pytest, solver와 설치 consumer를
실행할 수 없었다. 이후 직접 경로 실측이 최초 suite 전체를 실행한 근거로
소급 적용되지는 않는다. 기존 과도·독립 Robin 엔진 시험과 허용치는 그대로다.

## 독립 수학

`q=-k grad(T)`, 외향 `q.n=g+h(T-Ta)`에서
`A=K+H`, `rhs=fQ+B-G`, `r=A T-rhs`, `C=H T-B`이다.
반력은 고정 절점 잔차이며 자유 절점에서는 0이다.
부호 있는 총 외향 열량은 `sum(G+C-reaction)=sum(fQ)`, 깊이당 W/m이다.

NumPy 전용 oracle은 좌표와 연결로 삼각형 면적/P1 기울기를 직접 도출하고
원소 stiffness 작용 및 source 적분을 구성한다. 외곽 변은 생산 boundary tag가
아니라 한 삼각형만 소유한 변으로 찾는다. 길이 ell 변에서
`H_e=h ell [[2,1],[1,2]]/6`, `G_e=g ell [1,1]/2`,
`B_e=h Ta ell [1,1]/2`를 독립 사용한다.
생산/refsol assembly, summary 또는 해로 기대값을 만들지 않는다.
반환 geometry를 물리 직사각형과 감사하나 임의 topology 인증은 아니다.

## 고정 정확해와 gate

- 선형: 단위 정사각형, k=2,Q=0,left300 K,right g=2 W/m²,
  h=4 W/(m² K),Ta=290 K. T=300-7x K,qx=14 W/m².
  오른쪽 제거14 W/m, 왼쪽 thermostat 외향 -14 W/m, 총0.
- 이차: L=.03 m,H=.02 m,k=12.5,Q=100000 W/m³,a=300 K,
  g=100,h=20,Ta=290. T=a+b x-Q x²/(2k),
  b=(QL-g-h(a-Ta)+h QL²/(2k))/(k+hL). source 적분60 W/m.
- Robin-only: 같은 geometry/k/Q,a=300,b=-10. 독립 좌우 외향
  k b 및 QL-kb로 ambient를 정한다. 빈 고정 배열은 유효하다.
  왼쪽 h=0과 일치 g에서도 오른쪽 양수 h가 anchor이다.
- m/mm/um은 (.1,.2)m의 비영 원점을 포함한 동일 SI 직사각형이다.

mesh 분할8,16,32,64, 마지막 두 구간 온도 L2 차수≥1.8,
원소 flux L2 차수≥.9, 최종 상대 flux 오차≤2%이다.
독립 Duffy-product 삼각형 구적8/10 차이는 오차의1% 미만이다.
정확 선형/대수 normalized1e-10, SI 불변1e-9이다.
생산 결과에 맞춰 기준을 바꾸지 않는다. 약형 적분 열량은 roundoff로 정확할
수 있어 무의미한 단조 수렴 대신 대수로 검사한다.

## 공개 adapter와 저장 consumer

공개 Document/run/save와 별도 CLI subprocess를 검사한다.
argv/python-I/외부 임시 cwd/UTF-8을 사용하고,
np.load(...,allow_pickle=False) 및 context manager로 수치 필드를 읽는다.

기존9필드 의미를 유지하고 v2는 prescribed_outward_load_w_per_m,
ambient_load_w_per_m, convective_outward_w_per_m, system_rhs_w_per_m을 추가한다.
단위/shape/location/metadata 식별자를 검사한다.
load_w_per_m은 rhs가 아닌 fQ이다. 새 키가 없으면 v1, 빈 mapping이라도
새 키 하나가 존재하면 v2이다. caller 문서 수정은 복사된 계산을 바꾸지 않으며
result.doc 수정은 summary/save를 거절해야 한다. fields=false는 NPZ를 생략한다.

엄격 입력은 malformed/새 키, bool/nonfinite, 음수 h/ambient,
h0의 잘못된 ambient, Robin 필수멤버 누락, compatible/incompatible pure
Neumann, zero-h-only anchor, side 이름이 달라도 양 끝 고정인 실제 변 overlap을
포함한다. 한 고정 corner에서는 전체 변 하중을 보존한다.
CLI 출력 재사용은 거절하면서 기존 bytes를 보존해야 한다.

잘못된 물리 진단은 비상수 변 probe로 sign(G), H 누락/음수, B 누락,
consistent/lumped H를 구별한다. 저장 결과 actor는 load=rhs, B 누락,
G 부호 및 geometry 단위 오류를 겨냥한다. 준비된 대조일 뿐 실행 전
runtime 거절을 주장하지 않는다. 정확 후보에서 추가 metadata/summary 및
음성 대조를 고정 oracle gate 변경 없이 검토한다.

## 재현과 남은 검증

정확 구현 결합 후 저장소 루트에서:

```sh
python -m pytest -q packages/simcase/tests/test_steady_boundary_independent_validation.py
python -I /external/steady_boundary_independent_consumer.py --expected-installed-root /wheel/venv --expected-module-hashes /external/source-hashes.json
```

외부 경로는 고정 머신 경로가 아닌 예시이다. oracle/cases/consumer는 checkout의
추적 파일에서 checkout 밖 디렉터리로 복사한다. 비어 있지 않은 UTF-8 hash mapping은
simcase.schema, simcase.steady_boundary_contract, simcase.thermal,
simcase.runner, simcase.cli, galerkin.thermal을 필수 포함한다.
consumer는 설치 루트 밖 origin/byte 불일치를 거절하고 identity/count를
출력하며 skip이 있으면 실패한다.

새 범위 source/isolatedinstalled, exact CI, Windows/macOS, 전체 회귀 및
main 통합은 모두 미검증이다.
배포 총괄이 CI 연결과 전체 회귀 일정을 소유한다.

준비된 suite는 현재11개 시험 메서드를 선언한다(수집/통과 수가 아님).
reference offset 누락, 고정 corner 하중 제거, thermostat-only 총 외향량,
저장 format/layout/unit/object/nonfinite actor도 포함한다.
원문 검토만으로 이러한 대조를 실제 실행했다고 주장하지 않는다.

## 정확 구현 연결 정적 검토

schema/contract 4bd15626fe37c306eb6265f1db1b308c6b580460 및
runtime56238cd76ab09e422344ef54e89d68f5a1aa579e 원문을 읽었다.
병렬 제출이며 실행된 결합 checkout이 아니다.
수치 엔진 thermal.py blob4633e03953d8f6369bdf0e7398d2ebd85b2b4684는 그대로다.

관측한 이름은 독립 consumer와 일치한다. runtime thermal.py539–598은
문서를 검증·복사하고 다섯 경계 keyword를 연결하며 solve 전 입력을 포착한 뒤
반환 경계4배열을 확인한다. 600–619는 source/지정외향/convection/thermostat을
분리하며 총 외향에 세 경계 기여를 모두 넣는다. 430–472는 v2의 빈 고정
indices와13개 finite 수치 필드를 허용한다. 352–386은 이후 검증 전에 복사한
canonical data를 포착하며 default 복원으로 편집이 숨겨지기 전에 거절한다.
498–529는 승인된 v2 metadata와 원 model snapshot을 저장한다.
이 원문 검토에서 확정 생산 blocker는 발견하지 못했다.

contract는 새 키 부재/빈 mapping 존재, h0/양수 Robin anchor, 한 고정 끝점/
완전 고정 자연 경계 변을 구분한다. 경계 identity는 여섯 side 쌍 교집합을 모두
검사하고 Dirichlet 절점을 실제 외곽 변 끝점에서 구한다.

엔진은 rhs=fQ+B-G, 안정적인 shifted Robin offset,
C=H*increment-shifted_B, 원 고정절점 반력과 두 normalized1e-10 guard를
직접 유지한다. 독립 oracle은 helper를 정답으로 호출하지 않고 원 절대온도
수학식과 analytic 해를 사용한다. 원문 검토로 부동소수 정확도를 입증하지 않는다.

초기 snapshot 시험의 API 오류를 수정했다. Document에는 항목 대입이 없어
doc.data["name"] 및 result.doc.data["name"]로 변경했다.
원 기대와 모든 gate는 그대로다. 수치 재현/source·installed 통과/CLI 실행을
주장하지 않는다. 실제 결합 후보 CI와 원 진단 배열이 아직 필요하다.

## 추가 direct-path 실측

schema4bd15626fe37c306eb6265f1db1b308c6b580460,
runtime56238cd76ab09e422344ef54e89d68f5a1aa579e 및 기존 독립Robin oracle를
결합한 별도 source를 Python3.12.14/NumPy2.3.5/SciPy1.17.0에서 실행한 근거다.
실제Document.from_dict와 directrun_thermal을 사용했으나 package root
initializer는 우회했다. 새 Elements/11시험 공식suite나 공개root-runner/
CLI/설치 수용이 아니다.

10logicalgroup은 n2선형,상수Robin-only빈D,legacy/명시빈v2,mm/um저장,
이차mesh8/16/32/64이다. 첫실행은10solve를모두끝낸뒤 NumPybool JSON보고에서
exit1로실패했다. 직렬화만수정한최종10group은3.050654208999731s/exit0/
stderr없음이다. 앞probe포함21solve이며21독립시험이아니다.

C가원archive/14source SHA256·Gitblob/eight저장artifact hash를감사한뒤
새solve없이 수치NPZ를독립해독·재적분했다. 원배열선형G2/C12/R14 W/m이므로
오른쪽외향14/왼쪽thermostat외향-14/총약0이다. 이차각rawsource는60W/m,
최종총외향결손은약1.04e-11 W/m이다. rhs=fQ+B-G가각성분일치한다.

보고마지막2차수는 T1.9988550488612653/1.999656433643703,
flux.9994821862440284/.9998446426372463이다. 별도원배열구적은
T1.9988550488799535/1.9996564337200657,
flux.9994821862440356/.9998446426372037로둘다고정1.8/.9충족한다.
Gauss8/10최대relative는보고8.650446906980553e-11,
독립재적분1.3590626820738625e-11로모두<.01이다.
최종차원있는영역fluxL2는.3314417618241207,정확analyticfluxnorm
35.166282766624136으로나눈relative는.009424987111196404<.02이다.
영역상대L2이며경계gradient실측이아니다. 추가 normalized진단
5.6282662146672146e-14는명시된constituent합scale을사용하며공식gate를대체하지않는다.

이근거는10direct-path group만지지한다. 원점은이suite의(.1,.2)m가아닌0,
선형/단위n8대신n2,Robin-only는추가비영source/h0계열이아닌상수이다.
snapshot은caller-name격리/result-name거절만확인했고모든값변형이아니다.
새wrongactor/fieldsfalse/CLI/publicrunner/isolatedinstalled/플랫폼수용은
도출하지않는다. 정확결합후보의원suite/CI가여전히필요하다. gate변경없다.
