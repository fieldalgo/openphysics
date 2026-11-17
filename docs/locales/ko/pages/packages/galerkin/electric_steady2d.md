# 2D 정상 전기전도

[English](../../../../../packages/galerkin/electric_steady2d.md)

## 연성 계약 (버전 1)

명시적 Python 진입점은
`galerkin.electric.solve_steady_electric(mesh, *, electrical_conductivity,
prescribed_electric_potential, inward_current_density=None,
reference_electric_potential=None, motion=None)`입니다. 모든 물리량은 레지스트리
이름의 keyword-only SI 값이며 `str`을 주면 `TypeError`입니다(문자열은 먼저
`physmat.units.q` 등으로 변환합니다). 적합 P1 삼각형에서 `div(J)=0`, `E=-grad(V)`, `J=sigma*E`를 풉니다.
체적 전류원은 없습니다. 전기전도도는 유한한 양의 스칼라 또는 모든 영역 이름과
정확히 일치하는 `{region_name: scalar}` 표이며 단위는 S/m입니다. 재료 경계는
요소 변과 일치해야 합니다. 전위는 연속이며 법선 전류는 약한 형식으로 보존합니다.
온도 의존성·접촉저항·이방성·3D·UI는 범위 밖입니다.

`prescribed_electric_potential`은 외부 경계 절점 번호를 스칼라 전압(V)에
대응시킵니다. `inward_current_density`는 외부 변 태그를 물체로 들어오는 법선
전류밀도 `-J.n`(A/m²)에 대응시키며 양수는 **내향**입니다. 스칼라 또는
`(position, outward_normal) -> (Q,)` 콜백(위치는 m)을 받고 변마다 Gauss 점
4개로 적분합니다. galerkin은 이 값을 `0.0 - x`로 한 번 부호 반전해 외향 형식으로
조립합니다. 미지정 변과 명시적 0은 절연입니다. 변 순서가 뒤집혀도 법선은
기하학적 외향입니다. 중복 선택 변·내부 변·두 끝점 모두 전압 지정인 변에 자연
경계를 주면 거절합니다. 인접 전압/전류 변은 끝점 하나를 공유할 수 있습니다.

전압 조건이 없는 각 연결 성분은 전류 적분이 0이어야 합니다.
`integral(abs(J.n))` 대비 상대 허용오차는 `1e-12`이고 절대 전류 하한은 없습니다.
적합성은 게이지를 추가하기 **전에** 검사합니다. `reference_electric_potential`은 이러한
각 성분에 정확히 하나의 절점→전압을 지정하는 사전이며 내부 절점도 가능합니다.
누락·중복·불필요한 게이지는 거절합니다. 이는 상수 자유도만 고정하며 물리적 전류를
공급하거나 전극 반력에 포함되지 않습니다. 분리 성분 사이의 전류 상쇄는 허용하지 않습니다.

반환되는 `SteadyElectricResult`는 아래 SI 필드를 레지스트리 이름으로 담는 평면
결과입니다. 절점 전류와 적분량은 깊이 1 m당 값입니다(`_per_depth`). `.units`는
각 물리량 필드의 단위를 주고, 총량 이름(`joule_power`)을 물으면 깊이당 필드를
알려 주는 `AttributeError`가 납니다. 결과는 frozen입니다. 배열과 복사된 메시
배열은 입력과 독립적인 읽기 전용 스냅샷입니다. 재메시 없이 절점·삼각형 순서와
영역 번호를 유지합니다.

| 필드 | 모양 | 단위 / 의미 |
|---|---|---|
| `mesh` | `Mesh` | 입력 토폴로지·m 좌표·경계/영역 식별자의 복사본 |
| `electric_potential` | `(N,)` | V, 지정 게이지를 포함한 P1 절점 전위 |
| `electric_field` | `(M,2)` | V/m, 요소별 상수, Cartesian x/y |
| `current_density` | `(M,2)` | A/m², 요소별 상수 |
| `electrical_conductivity` | `(M,)` | S/m, 전개한 재료 표 |
| `joule_power_density` | `(M,)` | W/m³, 음이 아닌 `J·E = sigma*abs(E)**2` |
| `generated_heat_rate_per_depth` | `(N,)` | W/m, 각 요소가 절점마다 `Q*A/3`을 더한 일관 P1 Joule 하중 |
| `joule_power_per_depth` | 스칼라 | W/m, `sum(Q*A) = sum(generated_heat_rate_per_depth)` |
| `reaction_current_per_depth` | `(N,)` | A/m, 전압 전극이 주입한 전류; 나머지는 0 |
| `outward_prescribed_current_per_depth` | `(N,)` | A/m, 물체에서 나가는 지정 전류의 형상함수 적분 |
| `residual_current_per_depth` | `(N,)` | A/m, 오프셋 복원 전 계산한 `K*V + outward_prescribed_current_per_depth` |
| `inward_electric_power_per_depth` | 스칼라 | W/m, 전극·전류원이 공급한 전력 |

열 소비자는 절점/요소 순서가 동일한 **같은 메시**를 사용해야 합니다.
`joule_power_density`를 명시적인 요소별 체적 열원으로, 또는
`generated_heat_rate_per_depth`를 조립된 하중으로 전달합니다. 요소 배열을
스칼라/영역 전용 `heat_source_density`에 그대로 넣거나, 영역/절점 평균·경계 너머
보간을 하거나, 전기전도도를 다시 곱하면 안 됩니다.
`sum(Q*A) == sum(generated_heat_rate_per_depth)`를 반올림 오차 내에서 확인합니다. 전기 모듈은 기존
열 솔버를 변경하지 않습니다. 열전도도와 열 경계조건은 소비자 소관입니다.
실제 깊이가 `d` m이면 단위 깊이당 전류·전력에 `d`를 곱해 A·W를 얻습니다.
Q는 W/m³ 그대로이며 암묵적 두께·단위 변환은 없습니다.

전극 외향 전류는 해당 전극의 중복 없는 절점에서 `-sum(reaction_current_per_depth)`입니다.
각 성분은 `sum(reaction_current_per_depth) = sum(outward_prescribed_current_per_depth)`를
만족해야 합니다. 절점을 공유하는 전극 집합의 반력을 중복 합산하면 안 됩니다.
공급 전력은 `V·reaction_current_per_depth - V·outward_prescribed_current_per_depth`이며
수치 안정성을 위해
성분별 전위 오프셋을 빼고 계산합니다. 이산 해의 Joule 전력과 같습니다.
P1 요소 기울기는 H(div) 평형 유속이 아닙니다. 직접 경계 `J.n` 적분과 요소 간
점프는 메시 수렴으로 평가해야 하며 조립 전극 반력을 대신할 수 없습니다.

## 예제

```python
from galerkin.mesh import rectangle_mesh
from galerkin.electric import solve_steady_electric

mesh = rectangle_mesh(2., 1., 8, 4)  # metres
volts = {int(i): 2. for i in mesh.boundary['left']}
volts.update({int(i): 0. for i in mesh.boundary['right']})
r = solve_steady_electric(mesh, electrical_conductivity=3., prescribed_electric_potential=volts)
# V=2-x, E=(1,0) V/m, J=(3,0) A/m², Q=3 W/m³, power=6 W/m.
print(round(r.joule_power_per_depth, 10))  # 6.0

# Same current with pure Neumann data (3 A/m² enters on the left); a reference is required.
n = solve_steady_electric(mesh, electrical_conductivity=3., prescribed_electric_potential={},
                          inward_current_density={'left': 3., 'right': -3.},
                          reference_electric_potential={0: 2.})
```

실행 가능한 [두 재료 예제](../../../../../../examples/galerkin/electric_steady2d.py)는
Joule/공급 전력 0.026666667 W/m, 주입 전류 0.133333333 A/m를 출력합니다.
이 서브모듈을 명시적으로 import합니다. `galerkin` 최상위에서 재노출하지 않습니다.

## 검증과 한계

시험·crosscheck 의존성을 설치한 뒤 저장소 루트에서 실행합니다.

```sh
python -m pytest -q tests/galerkin/test_electric_steady2d.py
OPENPHYSICS_REQUIRE_CROSSCHECK=1 python -m pytest -q -s tests/galerkin/test_crosscheck_skfem_electric.py
python examples/galerkin/electric_steady2d.py
```

기준은 선형 평판·직렬/병렬 재료 경계 해석해(상대 `1e-10`), 성분별 전류·이산
전력 수지(`1e-10`), 단위 정사각형 조화 전위
`V=sin(pi*x)*sinh(pi*y)/sinh(pi)`의 내부 L2 수렴 차수(전위 >1.8, E 및 J >0.9)입니다.
로컬 Linux에서 변당 4/8/16/32 분할의 전위 오차는
0.02113/0.005517/0.001396/0.0003501 V, E 오차는
0.4790/0.2454/0.1235/0.06184 V/m, 마지막 차수는 1.996/0.998이었습니다.
총 Joule 전력을 정확한 `sigma*pi*coth(pi)/2`와도 비교합니다.
부호·뒤집힌 변·분리 성분·게이지 누락/불필요 지정·아주 작은 부적합 전류·영 전류·
전위 오프셋/부호/전압 제곱 비례를 검사합니다. 메시와 영역 순서도 보존합니다.

독립 scikit-fem 12.0.2(BSD-3-Clause) 시험은 기하 입력만 공유하고 약한 형식·
경계 하중·구속·Joule 하중을 별도로 조립합니다. 이종 재료 전압 전용, 이종 재료
혼합 경계, 순수 Neumann에서 V/E/J/Q/하중/전력과 실제 전극 반력을 상대 `1e-10`으로
비교합니다. 로컬 최대 차이는 각각 3.69e-15/4.89e-14/1.42e-14였습니다
(Python 3.12, NumPy 2.5.4, SciPy 1.18.1). 같은 프로세스의 코드 대 코드 비교이며
수렴 검증을 대신하지 않습니다. [비교 기록 도구](../../reference-comparisons.md)가
JSON을 남깁니다. 기존 소스·설치 휠 CI가 새 시험 모듈을 모두 수집하며 필수 CI는
레퍼런스 도구가 없으면 실패합니다. 로컬 통과로 CI·macOS/Windows 수용을 주장하지
않습니다. 해당 커밋의 워크플로 결과를 확인해야 합니다.

P1 장의 점별 법선 전류 연속성이나 국소 평형 유속은 보장하지 않습니다.
경계 콜백은 변당 4점으로 샘플링하므로 빠른 변화는 메시로 해상해야 합니다.
극단적 물성 대비·조건이 나쁜 메시에 보편적 정확도 보장은 없습니다. 비유한 계·
자유 잔차·전류·전력 검사는 발견한 실패를 거절합니다. 비적합 메시·전도도 0인 영역·
비선형 재료는 지원하지 않습니다.

명시적 메시 결합 요소 전도도 및 온도 피드백은
[온도 의존 Joule heating](temperature_joule_heating.md)을 참조한다. 원시 배열은 계속 거부한다.

[균질 직사각형 JSON/CLI 입력·저장 계약](../simcase/electric_joule.md). Python API 전체 범위를 JSON에 노출하지는 않습니다.

JAX·PyTorch 입력과 그 미분은 [JAX·PyTorch로 미분하기](differentiation.md)에 있습니다.
