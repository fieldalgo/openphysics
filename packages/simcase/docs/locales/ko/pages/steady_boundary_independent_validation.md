# 정상 열전도 경계 headless 독립 수용

[English](../../../steady_boundary_independent_validation.md)

## 상태와 범위

main `6d6eac56d1dddb8bdfe3f23d6db78d674487a42b`에서 수용 코드를 준비했다.
이 문서는 고정 기대값이며 통과 실측 보고가 아니다. 경계 확장 schema/runtime의
정확 결합 후보와 아직 연결하지 않았다. 현재 기반은 기존 Dirichlet 전용 정상
문서만 지원한다. 새 시험은 승인된 경계 계약을 요구하며 가짜 구현, skip 또는
허용치 완화로 구현을 대신하지 않는다.

준비 중 Python 구문 분석, pytest, solver, 설치 consumer, 플랫폼 실행은
불가능했다. 원문 검토는 수치 수용이 아니다. 기존 과도 및 독립 Robin 엔진
시험과 허용치는 변경하지 않는다.

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

외부 경로는 고정 머신 경로가 아닌 예시이다. 검증된 source archive에서
oracle/cases/consumer를 복사한다. 비어 있지 않은 UTF-8 hash mapping은
simcase.schema, simcase.steady_boundary_contract, simcase.thermal,
simcase.runner, simcase.cli, galerkin.thermal을 필수 포함한다.
consumer는 설치 루트 밖 origin/byte 불일치를 거절하고 identity/count를
출력하며 skip이 있으면 실패한다.

새 범위 source/isolatedinstalled, exact CI, Windows/macOS, 전체 회귀,
source archive 포함 및 main 통합은 모두 미검증이다.
배포 총괄이 archive/CI 연결과 전체 회귀 일정을 소유한다.

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
