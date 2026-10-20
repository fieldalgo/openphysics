# 과도 열전도에서 준정적 역학으로

[English](../../../../../packages/galerkin/transient_thermal_mechanical.md)

`galerkin.transient_thermal_mechanical.solve_transient_thermoelasticity`는 고정
기준 mesh에서 기존 온도 snapshot과 선형 소변형 역학을 조합한다. 먼저
`galerkin.transient_heat.solve_transient_heat`를 호출하고 결과와 같은 mesh를
이 함수에 전달한다. [실행 예제](../../../../../../examples/galerkin/transient_thermal_mechanical.py)는
두 공개 호출을 보여준다. 새 열 solver, 관성, 감쇠, 동적 평형, 역학에서 열로의
feedback, 변형 geometry 또는 시간 보간은 없다. E, nu, alpha는 각각 `{영역 이름: 값}`일
수 있고([multimaterial](multimaterial.md)) 그러면 모든 단계가 영역별 기계단계를 호출한다.

## 입력 및 선택

`mesh`는 열 결과와 m 단위 좌표 및 삼각형 연결이 정확히 같아야 하며 노드와
요소 순서도 같아야 한다. 내용이 같은 별도 mesh 객체는 허용한다. 재mesh,
매핑, 단위 변환/추론은 하지 않는다. 필수 `units`는 정확히
`{'length': 'm', 'time': 's', 'temperature': 'K'}`여야 한다.

`heat`는 `TransientHeatResult`여야 한다. 소비하는 시간/geometry/온도 필드를
검사한다. 시간은 유한한 비음수 초 2개 이상, 엄격 증가하고 차이도 유한한 양수이며
온도는 유한 실수 `(Nt,N)` 배열이다. 소비하지 않는 열유속/율/에너지 진단과
solver 출처는 인증하지 않는다. 공개 결과 클래스를 수동 생성할 수 있으므로
구조 검증은 열 계산의 완료나 자료 진위를 증명하지 않는다.

`time_indices=None`은 초기 index0을 포함한 모든 저장 index를 선택한다.
그 외에는 비어 있지 않은 1D list/tuple/array에 엄격 증가 정수를 전달한다.
bool/float/중복/역순/범위 밖 값은 거절한다. 최근접 시간 검색은 없다.
비균일 시간 grid 및 0이 아닌 시작 시각을 지원하며 `time_s[0]`을 그대로
보존한다. 초기 온도는 시간 전진 없이 그 시점의 역학에 사용된다.

선택 온도는 절대 Kelvin>=0이어야 한다. 선택 음수는 clipping 없이 거절한다.
선택하지 않은 유한 음수는 열 API의 수학적 계약과 같이 허용한다.
`reference_temperature_k`는 전체 이력에 고정된 유한 비음수 K scalar,
`thermal_expansion_per_k`는 유한 부호 있는 1/K 값이다. 영/음의 팽창을
지원한다. `young_modulus`는 유한 양수 Pa, `-1<poisson_ratio<0.5`이며, 세 값은 각각
scalar 또는 `{영역 이름: 값}` 매핑이다. `plane`은 명시적으로 `'stress'` 또는 `'strain'`이다.

`mechanical_dirichlet`는 외곽 `(node,component)`에서 고정 scalar 변위 m로의
mapping이다. 성분0은 x, 1은 y다. 각 분리 연결 성분의 세 rigid mode를
제거할 충분한 독립 조건이 필요하다. `body_force`는 일정한 유한 Cartesian
2-vector N/m³이며 기본 `(0.,0.)`이다. 나머지 역학 경계는 **총 물리 traction=0**이다.
열 traction을 따로 빼지 않는다. 시간 변화 지지조건, 체적력 callback 및 외부
traction은 이 최소 adapter 범위 밖이다. 더 넓은 하중 계약은 별도 처방온도
역학 API를 사용한다. 고정 지지/일정 체적력은 두 번째 시간 sampling 규약을
추가하지 않기 위한 범위 선택이다.

## 출력, 소유권 및 실패

frozen aggregate는 `reference_mesh`와 `steps` tuple을 가진다. `time_indices`와
`time_s`는 선택 순서의 tuple이다. 각 step은 원 `time_index`, 정확한 저장
`time_s`, 불변 `temperature_snapshot`, `mechanics` (`ThermoelasticResult`)를
보유한다. 변위는 m, 면내 응력/`sigma_zz`는 Pa, engineering strain 순서는
`(exx,eyy,gamma_xy)`다. 응력과 열변형률 배열은 삼각형 중심에서 평가하며
물리 응력은 일반적으로 P1 요소 내부에서 변한다. 하중/반력/잔차는 두께당
N/m, 물리 탄성 에너지는 J/m이다.

균일 가열의 자유 면내 팽창에서 평면 응력은 `u=alpha*DeltaT*x`, 응력0이다.
평면 변형률은 `u=(1+nu)*alpha*DeltaT*x`, 면내 응력0,
`sigma_zz=-E*alpha*DeltaT`다. z 자유 팽창을 의미하지 않는다.
비압축성에 가까운 P1 locking은 여전히 가능하며 adapter가 해결하지 않는다.

mesh/지지조건/매개변수/소비 온도 이력을 복사한다. 첫 역학 호출 전에 모든
선택 snapshot을 검증·동결한다. caller 입력은 변경하지 않으며 caller도
동시 변경하면 안 된다. snapshot geometry/온도는 immutable bytes를 기반으로
한다. 결과 소유 mesh와 역학 배열은 수정 가능하며 반환 뒤 인증하지 않는다.
이를 수정해도 불변 snapshot은 바뀌지 않는다.

`TransientThermoelasticError`에는 `stage` (`input`, `transfer`, `mechanics`),
`time_index`, `time_s`가 있다. 전역 입력 실패는 index/time이 없고 선택 transfer/
mechanics 실패는 원 저장 index/time 및 `__cause__`를 보존한다. 부분 성공
aggregate는 반환하지 않는다. 뒤 시점 역학 실패 전에 앞 해석이 끝났을 수 있고,
예외 traceback은 해제될 때까지 임시 메모리를 보유할 수 있다.

결과는 선택 snapshot/역학만 보유하고 입력 heat 객체/진단을 보유하지 않는다.
선택 S개, 노드 N개, 요소 M개이면 geometry 복제를 포함하여 O(S*(N+M))다.
caller 전체 열 이력은 별도 O(Nt*(N+M))이며 검증 중 전체 온도 배열의 임시
복사가 생긴다. streaming/메모리 상한 보장이 아니다. 역학은 매번 조립·분해하며
factorization 재사용이나 속도 보장을 주장하지 않는다.

## 독립 검증 및 재현

개발 의존성을 설치한 후 저장소 root에서 실행한다.

```sh
python -m pytest -q tests/galerkin/test_transient_thermal_mechanical.py
python -m pytest -q -s tests/galerkin/test_transient_thermal_mechanical_physics.py
python examples/galerkin/transient_thermal_mechanical.py
python -m pytest -q
```

물리 시험은 원 3D 법칙에서 유도한 NumPy 전용 `refsol.transient_heat` 및
`refsol.thermoelasticity` 독립장을 사용한다. 생산 solver 간 일치는 물리 정답이
아니다. 사전 정의 사례/기준은 다음과 같다.

- 2 s에서 시작하는 비균일 시각의 균일 단열 상수 열원 가열/냉각:
  `T=T0+Q*(t-t0)/c`. 두 plane의 자유 팽창/전 외곽 구속, 음/영 alpha,
  공통 T/Tref 이동. 온도 절대오차<=1e-9 K, 변위<=1e-10*(alpha_scale*20 m),
  응력/반력<=1e-9*(E*alpha_scale*20 Pa), alpha_scale=1e-5/K.
  면외 응력/물리 에너지/적분 지지반력을 독립 확인한다.
- 시간 오차만: 균일 `T=300+t²`, `Q=2ct`, 공간 오차 없는 affine 역학.
  BE 온도 오차=`sum(dt²)`이며 자유 변위/구속 응력 오차는 대응 해석 계수를
  곱한다. 8/16/32 균일 step 차수는 [0.99,1.01], 비균일 grid는 모든 index 검사.
- 공간 오차만 및 정상 한계: `T=310+20x`는 모든 시점에서 열 P1/BE에 정확하다.
  체적력0, `refsol.thermoelasticity.linear_temperature`의 호환 quadratic 팽창장을 전 외곽에
  처방한다. 8/16/32 mesh의 독립 Gauss4 Duffy 적분으로 변위 L2 차수>=1.8,
  gradient/재구성 전체 응력 차수>=0.9, fine 변위오차/(alpha_scale*20 m)<0.01.
  초기/마지막 시점과 두 plane을 모두 검사한다. 이 정상 사례는 공간 비균일
  과도 가열의 수렴을 입증하지 않는다.
- 전용 회귀는 저장 index/time 대응, 정확 mesh 순서, 소비 필드 오류,
  mutation 격리, snapshot backing, 미지원 설정, 지지 부족, 시점별 원자적 실패를 검사한다.

Linux source 전체에 이 시험이 포함되고 전용 preflight는 로그/JUnit에 수치
지표를 남긴다. Linux/macOS/Windows 설치 소비 시험은 공개 조합의 해석해 및
module origin을 확인한다. 배포본에는 문서/시험/예제가 들어가지 않는다. 배포 검사는
checkout에서 추적되는 예제를 checkout 밖으로 복사해 설치된 wheel로 실행한다.
기존 전체 Linux 및 narrow Windows 필수 검사는 유지한다.
설정 자체는 수용 증명이 아니므로 exact 후보 및 main workflow 로그/artifact를
확인해야 한다. 이 문서는 새 플랫폼/성능/자원 보장을 뜻하지 않는다.
