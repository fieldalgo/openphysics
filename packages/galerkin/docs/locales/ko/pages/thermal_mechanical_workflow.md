# 명시적인 정상 열전도 → 열탄성 기계단계

[English](../../../thermal_mechanical_workflow.md)

이 Python 전용 workflow는 기존 열 solver를 호출하고 절점 Kelvin 장을 고정한 뒤,
격리된 기준 메시 하나에서 기존 처방 온도 기계단계를 호출합니다. 정상·one-way·소변형
모델이며 열역학적으로 결합된 solver나 과도 solver가 아닙니다. Submodule을 명시적으로
import합니다. Top-level export, 모델 schema, CLI, Studio, 저장, Robin, flux,
기계 traction, 재메시, 온도 의존 재료나 3D 기능은 추가하지 않습니다. k, E, nu, alpha와
상수 열원은 각각 스칼라 하나 또는 `{영역 이름: 값}` 매핑일 수 있습니다. 영역별 계약,
manifest 기록(열원은 `{'kind': 'per_region', ...}`, 재료는 정렬된 사전)과 연성 복합 원통
검증은 [multimaterial](multimaterial.md)에 있습니다.

## API와 SI 경계

```python
from galerkin.mesh import rectangle_mesh
from galerkin.thermal_mechanical import solve_steady_thermoelasticity

n = 8
mesh = rectangle_mesh(1., 1., n, n)
thermal = {int(i): 303.15 for i in mesh.boundary['left']}
thermal.update({int(i): 323.15 for i in mesh.boundary['right']})
result = solve_steady_thermoelasticity(
    mesh, units={'length': 'm', 'temperature': 'K'},
    conductivity=10., thermal_dirichlet=thermal, heat_source=0.,
    young_modulus=70e9, poisson_ratio=.3, plane='strain',
    thermal_expansion_per_k=12e-6, reference_temperature_k=293.15,
    mechanical_dirichlet={(0, 0): 0., (0, 1): 0., (n, 1): 0.},
    body_force=(0., 0.))
```

전체 signature는 다음과 같습니다.

```python
solve_steady_thermoelasticity(
    mesh, *, units, conductivity, thermal_dirichlet, heat_source=0.0,
    young_modulus, poisson_ratio, plane, thermal_expansion_per_k,
    reference_temperature_k, mechanical_dirichlet, body_force=(0., 0.))
```

| 입력 | 의미와 검증 |
| --- | --- |
| mesh | galerkin Mesh, nodes (N,2) m, 정수 triangles (M,3); 기준 형상 |
| units | 정확히 `{'length':'m','temperature':'K'}`; 추가 키·자동 변환 없음 |
| conductivity | 유한한 상수 k>0, W/(m K), 또는 `mesh.region_names` 전체에 대한 `{영역 이름: k}` |
| thermal_dirichlet | 외벽 정수 절점 → 유한한 절대 K; 나머지 단열 |
| heat_source | 유한한 부호 있는 scalar, `{영역 이름: Q}`, 또는 (Q,2) 미터 좌표 → (Q,) W/m³ callback |
| young_modulus / poisson_ratio | 유한한 E>0 Pa / -1<nu<0.5; 각각 scalar 또는 `{영역 이름: 값}` |
| plane | 명시적인 `stress` 또는 `strain` |
| thermal_expansion_per_k | 유한한 부호 있는 **선팽창** alpha, 1/K; 0·음수 허용; scalar 또는 `{영역 이름: alpha}` |
| reference_temperature_k | 필수 유한 비음수 절대 K; 자동 기준값 없음 |
| mechanical_dirichlet | 외벽 (node,component) → 변위 m; component0=x,1=y |
| body_force | 유한한 (2,) 또는 (Q,2) 미터 좌표 → (Q,2) N/m³ callback |

열 연결 성분마다 Dirichlet anchor가 필요하고 기계 성분마다 독립적인 강체 구속3개가
필요합니다. 나머지 기계 성분에는 탄성 성분만의 traction 0이 아닌 **전체 열탄성 자연
traction 0**을 적용합니다. 열 태그가 기계 고정을 뜻하지 않습니다. Spring이나 fallback
구속을 넣지 않습니다. 기존 형상·재료·잔차·구속 검사를 유지합니다. 거의 비압축성인
plane-strain P1 locking은 한계로 남습니다.

Caller는 mm/um 표현을 진입 전에 m로 변환해야 하며 body force 좌표와 처방 변위도
포함합니다. 다른 수치 입력은 위의 고정 SI 단위를 유지합니다. 잘못된 m/K 표시는
배열에서 알아낼 수 없습니다. 입력한20은20K이며 자동 Celsius 변환이 아닙니다.
Caller 측 Mesh 생성자가 이미 소수 인덱스를 변환하거나 방향을 보정했다면 소실 이력을
복원할 수 없습니다. Workflow는 자신의 생성자가 인덱스를 변환하거나 삼각형 방향을
뒤집기 전에 복사한 raw 배열을 검사합니다. 소수·불리언 연결 정보, 유한하지 않은 좌표,
양수가 아닌 방향은 보정하지 않고 거절합니다. 이후 기존 component validator가
비적합 메시·겹침·부적절한 구속을 거절합니다.

## 격리·전달·수명

절점·연결·경계 배열·영역 metadata·상수 재료·상수 body force·구속 map을 복사합니다.
두 단계는 절점·요소 순서와 변형 전 좌표를 보존하는 **같은 내부 소유 Mesh 객체**를
사용합니다. 실행 중 내부 mesh/boundary/region 변경을 탐지하면 해당 단계가 실패합니다.
Callback에서 caller 원래 배열을 바꿔도 이 복사본은 바뀌지 않습니다. Callback 자체는
외부 가변 코드입니다. 동작·부작용을 인증·복사하거나 순수 함수·thread-safe로 만들지 않습니다.

열해석이 성공하면 온도는 유한한 실수 (N,) 배열이어야 합니다. 음수 Kelvin은 최솟값·절점을
표시하는 명시적인 `transfer` 오류입니다. 유한하지 않은 값은 절점을, shape/type 오류는
기대 계약을 표시합니다. 열 solver는 수학적으로 음수 온도를 허용하지만 이 workflow의
snapshot 도메인은 허용하지 않습니다. Clamp·절댓값·숨은 offset·Tref 이동·허용 오차
예외를 사용하지 않습니다. Heat/transfer 실패 뒤 mechanics를 호출하지 않습니다.

Snapshot은 canonical little-endian float64/int64, immutable bytes backing,
schema1, m/K와 재현 가능한 framed FNV-1a64 checksum을 가진 정확한 nodal-P1 복사본입니다.
정확한 좌표·연결·절점·요소 순서에 연결됩니다. 같은 배열을 복사한 메시는 허용하지만
재정렬·스케일 변경·재메시는 허용하지 않습니다. 보간이나 자동 순열은 없습니다.
Boundary/configuration은 snapshot 메시 checksum으로 인증하지 않고 manifest에 별도로 기록합니다.

반환 후 `heat.temperature`를 바꿔도 이미 고정한 snapshot은 바뀌지 않습니다. 다시 freeze하는
것은 명시적인 새 전달입니다. Component 결과 배열과 내부 소유 기준 Mesh는 기존의 가변성을
유지합니다. Aggregate는 속성을 읽을 때마다 이들을 재검증하지 않습니다. 완료된 실행 manifest는
**반환 이후 무결성 인증이 아닙니다**. 불변 snapshot은 원래 입력보다 오래 살아남을 수 있습니다.
나중에 바꾼 메시를 기계 API에 넘기면 해당 API가 검사하지만, 반환 Mesh를 수정하는 것만으로
완료된 실행이 소급 변경되거나 다시 인증되지는 않습니다.

## Aggregate와 canonical manifest

`SteadyThermoelasticResult`는 다음 멤버를 갖습니다.

| 멤버 | 계약 |
| --- | --- |
| reference_mesh | 격리된 소유 Mesh; SI 기준 절점, 반환 후 가변 |
| heat | 기존 SteadyHeatResult; temperature/flux/load/reaction/residual |
| temperature_snapshot | 실제 기계단계에 전달한 불변 TemperatureSnapshot |
| mechanics | 기존 ThermoelasticResult; 장·분리된 하중·반력·물리 에너지 |
| manifest_json | 불변 canonical JSON 문자열 |
| manifest | 접근할 때마다 새로 decode하는 dictionary |

```python
metadata = result.manifest
metadata['units']['length'] = 'mm'
assert result.manifest['units']['length'] == 'm'
assert result.mechanics.temperature_snapshot is result.temperature_snapshot
```

JSON은 정렬된 키·compact separator·유한한 수치를 사용합니다. Schema는
`galerkin-steady-thermoelasticity-v1`입니다. 선언한 SI 단위, 재료(float, 또는 키를 정렬한
`{영역 이름: float}` 사전), 기준온도·plane, 정렬된 구속, 열원·body force(`{'kind': 'constant',
'value': ...}`, 영역 열원은 `{'kind': 'per_region', 'value': {...}}`, 또는 callable label), 메시 개수·boundary·region
metadata, 메시·온도·snapshot hash, 정확 복사 전달 정책, 완료 단계 상태, 물리량 단위를
기록합니다. 이동하는 Git revision을 전체 runtime 버전이라고 주장하지 않습니다.
정확한 source manifest는 외부 검증 근거에 속합니다.

Origin은 `workflow_owned_heat_call`로 이 호출이 heat component를 실행했다는 뜻입니다.
Authentication은 `not_certified`입니다. Callable 입력은 `caller_provided`,
`fingerprinted: false`로 표시하며 repr/address나 만들어낸 코드 fingerprint를 쓰지 않습니다.
Checksum은 재현 식별자이며 서명·물리 단위·외부 출처·callback 순수성의 증명이 아닙니다.
이 workflow는 수동 heat-result shortcut을 받지 않으며 외부장을 인증된 열 출처로 승격하지
않습니다. 반환 후 가변 배열이 더는 기록한 hash와 일치하지 않을 수 있습니다.

## 단계 오류와 실패 경계

`WorkflowStageError`는 `.stage`와 `.__cause__`의 원래 예외를 가진 ValueError입니다.
단계는 `input`, `heat`, `transfer`, `mechanics`, `manifest`입니다. 입력 검사·복사는 heat
전에 수행합니다. Component 열 검증·해석 실패는 heat, freeze/domain 실패는 transfer,
component 기계 검증·해석 실패는 mechanics, canonical 직렬화 실패는 manifest입니다.
내부 메시 변경은 관측한 component 경계의 단계로 표시합니다.

```python
from galerkin.thermal_mechanical import WorkflowStageError
try:
    solve_steady_thermoelasticity(mesh, **parameters)
except WorkflowStageError as error:
    print(error.stage, str(error), type(error.__cause__).__name__)
```

여기서 `parameters`는 signature의 완전한 인자 dictionary를 뜻합니다. 어느 단계든
실패하면 성공 aggregate를 반환하지 않습니다. 부분 결과·저장·cleanup·영속화 계약을
추가하지 않습니다. 필수 인자 누락·알 수 없는 인자 같은 일반적인 Python 호출 binding 오류는
pipeline 실행 전에 발생하며 KeyboardInterrupt/SystemExit는 workflow 오류로 변환하지 않습니다.

## 물리와 분리된 회계

열해석은 `-div(k grad T)=Q`, q=-k grad T입니다. 지정 절점의 열 반력이 rT이면
`sum(load)+sum(reaction)=0`, 부호 있는 순 외향 열량=-sum(reaction)입니다.
열 절점 load/reaction/residual은 깊이당 W/m이며 flux는 W/m²입니다.

기계단계에서 a=alpha(T-Tref), e=(exx,eyy,gamma_xy), gamma_xy=2epsilon_xy,
m=(1,1,0), mu=E/[2(1+nu)], lambda=E nu/[(1+nu)(1-2nu)]입니다. 원래3D 법칙은
sigma=2mu(epsilon-aI)+lambda tr(epsilon-aI)I입니다. 면내 응력은 D e-q m이며
q는 PS에서 E a/(1-nu), PE에서 E a/(1-2nu)입니다. PS는 sigma_zz=0과
`epsilon_zz=((1+nu)a-nu(exx+eyy))/(1-nu)`, PE는 epsilon_zz=0과
`sigma_zz=lambda(exx+eyy)-E a/(1-2nu)`입니다.

열 약형식 하중은 양의 `g=integral B^T q m dA`이며 물리적인 외부 body force가 아닙니다.
Body-force-only 대체는 경계항과 균일 자유 팽창을 빠뜨립니다. 물리적 열변형률은 z를
포함한3D에서 여전히 aI이며, PE의 유효 (1+nu)a는 축약 하중 표현일 뿐입니다.

전체 변형률은 요소별 상수입니다. thermal/elastic strain, stress, sigma_zz와 epsilon_zz는
중심 표본입니다. T가 P1이므로 응력은 일반적으로 요소 안에서 선형입니다. Snapshot의 P1 T와
요소 변위 변형률로 점별 응력을 복원해야 하며 중심값을 전체 상수 장으로 해석하면 안 됩니다.
Plane stress는 국소 축약이며 복원한3D warping이 아닙니다.

기계 external load·thermal-equivalent load·reaction·residual은 분리된 깊이당 N/m입니다.
`load_total`은 external+thermal입니다. 반력은 고정 성분에서 Ku-f-g, 자유 성분에서0이며
전체 residual은 모든 성분을 유지합니다. 물리적 탄성 에너지 U는 원래3D 탄성 에너지에서
구하는 J/m입니다.

```text
PS: psi=.5(e-a m)^T Dps(e-a m)
PE: psi=.5(e-(1+nu)a m)^T Dpe(e-(1+nu)a m)+.5 E a²
U=.5 u^T K u-u^T g+CT
u^T K u=u^T(f+g+r)
2U=u^T f+u_D^T r_D-u^T g+2CT
```

CT는 PS에서 integral E a²/(1-nu) dA, PE에서1.5 E a²/(1-2nu) dA입니다.
P1 온도에는 중심 T를 제곱하는 대신2차 정확 에너지 구적이 필요합니다. 비영 처방 변위에는
support work를 포함해야 합니다. 이들은 고정 T에서의 endpoint 기계 항등식이며 전체
열역학 수지나 가열 경로의 일이 아닙니다. `T^T KT T`는 W K/m이며 탄성 에너지나 저장 열이
아닙니다. 깊이당 힘·에너지에 물리적 두께를 곱하는 것은 명시적인 외부 연산에서만 수행합니다.

## 재현과 사전 수치 gate

기존 의존성이 준비된 정확한 source checkout 루트에서 실행합니다.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
PYTHONPATH=packages/galerkin \
python packages/galerkin/examples/thermal_mechanical_workflow.py

OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
python -m pytest -q packages/galerkin/tests/test_thermal_mechanical_workflow.py \
  packages/galerkin/tests/test_thermal_mechanical_workflow_physics.py
```

예제는1m 정사각형에서 선형 열전도 T=Tref+10+20x, Q=0, k=10을 사용합니다.
적합한 연속체 자유 팽창은 vx=alpha10x+.5alpha20(x²-y²), vy=alpha10y+alpha20xy이며
PS는 u=v, PE는 u=(1+nu)v입니다. 이차 변위에는 FE 오차가 있으며 선형 열해는 P1-exact입니다.
균일20K 가열이면 PS u=a(x,y), 응력/U=0이고 PE u=(1+nu)a(x,y), sigma_zz=-Ea,
U=.5 E a² area입니다. 대신 외벽 전체를 고정하면 E70GPa, nu.3, alpha12e-6/K에서
PS -24MPa, PE -42MPa의 법선 응력이 생깁니다.

Producer 수치 시험은 위 사례와1m 정사각형의 sine MMS
T=Tref+20sin(pi x)sin(pi y), u=(1e-4,.6e-4)sin(pi x)sin(pi y),
k10/E70GPa/nu.3/alpha12e-6을 사용합니다. 열원은 -k Laplacian(T), 기계 body force는
-div(total analytic stress)에서 유도하며 sine에서는 외벽의 두 변위 성분을 모두 지정합니다.
생산 constitutive/assembly helper나 refsol import 없이 원래3D tensor 법칙과 독립 구적을 씁니다.

고정 n=8/16/32/64, **인접한 세 구간 모두**, 양 plane에서 다음을 검사합니다.

- L2 온도·변위 차수>=1.8, gradient·strain·sigma_zz를 포함한 full3D stress·기계
  energy-norm 차수>=.9. 정확히0인 선형 열해·전달에는 만들어낸 차수가 아닌 exact 검사를 씁니다.
- 수치 열해 T_h, 해석적 절점 I_h T, u_h[T_h], u_h[I_h T]를 해석장과 각각 비교합니다.
  Snapshot 절점 전달은 정확한 배열 동일성입니다. 열로 인한 기계 변화는 탄성 dual-norm
  bound를 만족해야 하며 벡터 오차를 분해할 수 있어도 norm 크기를 scalar처럼 더하지 않습니다.
- 균일 정규화 장·경계별 반력·물리 U<=1e-10, 독립 약형식 하중·원래3D stress/U·support-work
  감사<=1e-10, 열수지<=1e-10, 기계 힘·모멘트<=1e-9입니다. 올바르게 변환한 단위는<=1e-9로 일치합니다.
- Norm 구적8x8/10x10 차이<측정 오차의1%, 해석적 물리 U12x12/16x16 차이<=고정 에너지 scale의
  1e-8입니다. 정규화 물리 U 오차는 단조 감소해 최종<=.02이어야 하며 raw-energy2차 gate를 만들지 않습니다.

매끄러운 볼록 정사각형의 P1 이론이 gradient1차·L2 2차 수렴의 근거이며, 관측 후 문턱을
맞추지 않습니다. Component gate를 유지하며 copy/stale/invalid/component supports,
냉각·음수·0 alpha, 공동 기준온도 이동, 경계별 반력, 비영 support work, 잘못된 PE·중심
에너지의 실제 직접 수학 음성 대조도 포함합니다. 이 producer 검사는 독립 수용과
release·설치 근거와 별개입니다. 가이드나 예제가 Windows·Actions·배포 포함·성능 성공을
뜻하지 않습니다. 공유 release manifest는 별도 검토 대상입니다.
