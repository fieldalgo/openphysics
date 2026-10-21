# 정상 2차원 열전도

[English original](../../../../../packages/galerkin/thermal_steady2d.md)

명시적 import는 `galerkin.thermal`과 `refsol.thermal`입니다. 이 모듈은 적합 P1
삼각형 mesh에서 균질·등방성 정상 열전도를 풉니다.

```text
-div(k grad T) = Q,       q = -k grad T
T = prescribed value on Dirichlet nodes
q.n = 0 on unselected natural edges (insulation by default)
```

`Mesh`, 스칼라 P1 강성 조립, 상수 하중 조립, 기존 Dirichlet 선형 solver와 요소
포텐셜 gradient 복구를 재사용합니다. 전자기 edge 공간이나 탄성 solver는 사용하지 않습니다.

## API와 SI 단위

```python
from galerkin.thermal import solve_steady_heat

result = solve_steady_heat(
    mesh,
    conductivity=12.0,
    dirichlet={0: 350.0, 1: 300.0},  # Example node IDs; select actual boundary nodes.
    heat_source=0.0,
)
```

| 입력 | 계약/단위 |
| --- | --- |
| mesh | `galerkin.mesh.Mesh`, 기준 좌표 `(N,2)` m, 정수 삼각형 `(M,3)` |
| conductivity | 필수 유한 실수 스칼라 k>0, W/(m K), 또는 `mesh.region_names` 위 구간 상수 `{영역 이름: k}`([multimaterial](multimaterial.md)). tensor·영역 안에서 변하는 k 없음 |
| dirichlet | 외부 정수 절점 ID→유한 스칼라 온도 K 매핑 |
| heat_source | 유한 실수 스칼라 Q, `{영역 이름: Q}` 또는 `(Qpoints,2)` m 좌표→정확히 `(Qpoints,)` W/m^3 콜백 또는 메시 사본에 결합한 요소별 `(M,)` W/m^3의 `ElementHeatSource(mesh, values)`. 기본값 0 |

기본 단열 경계에서는 연결 성분마다 적어도 하나의 처방 온도가 필요하며, 선택적 Robin
확장도 성분을 고정할 수 있습니다. 절점을 몰래 pin하지 않고 spring이나 최소제곱
정규화를 넣지 않으며 순수 Neumann 문제는 API 범위 밖입니다. Dirichlet 데이터는 내부
절점이나 신뢰한 tag만이 아닌 실제 위상적 외부 경계에 있어야 합니다. 선택하지 않은
자연 edge는 단열입니다. 경계 절점 tag로 Dirichlet 매핑을 만들 수 있습니다. 선택적
처방 외향 flux·Robin edge-tag 입력, 추가 결과 필드와 바뀐 열수지 방정식은 소스 트리의
`docs/packages/galerkin/thermal_flux_robin.md`를 보십시오. 해당 가이드·예제는 배포본에
포함되지 않습니다. 한국어 설명은 [flux·Robin 가이드](thermal_flux_robin.md)에 있습니다.
아래 방정식은 그 입력들을 생략한 기본 경우를 설명합니다.

온도는 K로 지정하며 Celsius 변환이나 기준 온도 차감을 입력에서 추론하지 않습니다.
유한 음수 열원은 열 흡수입니다. 상수 계수 선형 PDE는 재료 유효 온도 범위, 열역학적
비선형성 또는 계산 온도의 양성을 강제하지 않습니다. 물리적으로 의미 있는 SI 데이터를
제공해야 합니다.

`SteadyHeatResult`는 다음을 포함합니다.

| 필드 | shape | 단위/위치 |
| --- | --- | --- |
| temperature | `(N,)` | mesh 절점 K |
| heat_flux | `(M,2)` | 각 P1 삼각형에서 일정한 벡터, W/m^2 |
| load | `(N,)` | 면외 두께당 W/m, 적분 체적 열원 |
| reaction | `(N,)` | 두께당 W/m, 고정 절점의 경계 열 입력. 자유 절점에서 정확히 0 |
| residual | `(N,)` | 두께당 W/m, 모든 절점의 K*T-load |

2D 약형은 **면외 단위 두께당**입니다. `load`와 `reaction`은 총 W가 아닙니다.
총량이 필요하면 명시적 외부 계산에서 실제 두께(m)를 곱합니다. 암묵적인 두께 인자나
스케일링은 없습니다.

## 조립, 경계 부호와 품질

스칼라 P1 shape function N_i에 대해 다음과 같습니다.

```text
K_ij = integral k grad(N_i).grad(N_j) dA
f_i  = integral Q N_i dA
K_FF T_F = f_F - K_FD T_D
r = K*T-f
reaction_D = r_D, reaction_F = 0
sum(load + reaction) = 0
outward integrated boundary heat = -reaction
```

양의 반력은 영역 안으로 열을 주입합니다. 왼쪽이 뜨겁고 오른쪽이 찬 slab에서 왼쪽
반력은 양수, 오른쪽 반력은 음수입니다. 양의 균일 발열·같은 낮은 경계 온도에서는
총 외향 열량이 양수이며 Q의 적분과 같습니다. 적분 반력은 절점 약형 경계량이지
점별 경계 flux 밀도가 아닙니다.

`galerkin.thermal`에서 `ElementHeatSource`를 import합니다. 열원 값과 정확한
좌표·삼각형 순서·영역 대응의 사본을 유지하며 소비 시 불일치를 거절합니다.
각 요소의 상수 Q는 꼭짓점마다 Q*area/3을 기여합니다. 일반 요소 배열을 그대로
넣는 입력은 지원하지 않습니다. [Joule 발열 전달](joule_heating.md#요소-열원-api)을 보십시오.

상수 Q는 기존 정확한 상수원 하중을 사용합니다. 콜백 Q는 원래 6x6 Gauss-Legendre
Duffy 삼각형 규칙으로 **Q*N_i**를 적분하며, centroid Q의 면적/3을 각 절점에 주는
방식이 아닙니다. 상수·선형 열원 모멘트는 정확합니다. 매끄러운 비다항식 열원은 근사하며
불연속·고진동 열원은 별도의 해상도·구적 연구가 필요합니다. 콜백은 좌표마다 정확히
하나의 유한 실수를 반환해야 합니다. 스칼라, `(Qpoints,1)`, complex·비유한 반환은 거부합니다.

수치 안정성을 위해 성분의 첫 처방 온도를 상수 offset으로 사용합니다. 기존 solver가
온도 증분을 풀고 절대 K를 복원합니다. 정확한 성분별 상수 nullspace 성질로 offset을
더하기 전에 flux·잔차를 평가합니다. 수학적으로 잔차는 여전히 K*T-load입니다.
보고된 절대온도로 독립 희소행렬 계산을 하면 반올림 상쇄오차 차이가 날 수 있습니다.
극단적인 온도 동적 범위나 악조건 기하가 단지 이 shift로 정확해지는 것은 아닙니다.

solver는 유한하지 않은 조립계·해·flux를 거부합니다. 자유 잔차의 무한대 norm은
`max(norm(abs(K)*abs(increment)+abs(load), infinity), tiny)`의 1e-10 이하여야
합니다. 전역 열 불균형 절댓값도
`max(sum(abs(load))+sum(abs(reaction)), tiny)`의 1e-10 이하여야 합니다.
이는 대수·열수지 검사이지 이산화 오차 추정이 아닙니다. P1 열 flux는 요소별 상수이며
H(div) 적합 국소 보존 복원이 아닙니다. 자연 단열은 약형으로 적용합니다. 전역 열수지만으로
국소 flux 정확도나 mesh 수렴을 보장하지 않습니다.

## 기하 검증과 오류

유한 실수 `(N,2)` 좌표, 범위 내 정수 삼각형 연결, 모두 사용되고 서로 다른 절점,
중복 없는 삼각형과 양의 해상 가능한 방향·면적이 필요합니다. 퇴화 삼각형, 비다양체
edge·vertex, 점으로만 이어진 hinge, 내부 중첩과 hanging node를 거부합니다.
국소 상대 기하 허용치를 씁니다. determinant는 edge 길이 척도 제곱의 1e-14보다 커야
하며, 교차·hanging-node 허용치는 국소 길이의 1e-12입니다. 부동소수점 기하 해상도보다
작은 형상은 계약 밖입니다. 내부 중첩 검사는 두 삼각형의 무게중심 거리가 두 무게중심
반경(무게중심-꼭짓점 최대 거리) 중 큰 값의 두 배 이내일 때만 그 쌍을 살피고, 중첩하는
쌍은 모두 이 조건을 만족하므로 비용은 가장 큰 삼각형이 아니라 국소 mesh 크기 변화를
따릅니다.

`Mesh`는 보통 생성 시 방향을 고치지만 배열은 변경할 수 있습니다. solver는 호출 시
실제 데이터를 검증하며 시계 방향 삼각형을 거부합니다. `Mesh`는 생성 시 연결 인덱스를
정수로 바꾸므로 소수 인덱스를 자르기 전에 검증하는 용도로 의존하지 마십시오.
solve·콜백 실행 중 mesh 데이터를 바꾸지 마십시오. 경계 index·shape, bool 수치,
complex·비유한 입력, 잘못된 재료, 누락된 성분 구속은 `ValueError`입니다.
특이·비유한 해 또는 잔차·열수지 실패도 오류이며 조용히 수용한 결과가 아닙니다.

## 재현

기존 패키지가 설치된 환경에서 저장소 루트로부터 실행합니다.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python examples/galerkin/thermal_steady2d.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest -q -s \
  tests/galerkin/test_thermal_steady2d.py \
  tests/galerkin/test_mesh_overlap_candidates.py \
  tests/refsol/test_thermal_reference.py
```

예제는 2 m×0.7 m slab, k=12 W/(m K), 왼쪽 350 K·오른쪽 300 K,
상하 자연 단열·Q=0을 사용합니다. `q=(300,0) W/m^2`, 왼쪽 주입 `210 W/m`,
오른쪽 주입 `-210 W/m`을 얻습니다. 명시적 submodule import를 쓰며 공용 package
export 변경은 필요하지 않습니다.

## 독립 정답과 고정 수용 기준

`refsol.thermal.slab`은 `T=TL+(TR-TL)x/L`, `q=(-k(TR-TL)/L,0)`, `Q=0`을
직접 계산합니다. `refsol.thermal.sine_manufactured`는 다음을 직접 미분합니다.

```text
T = T0 + A sin(pi*x/Lx) sin(pi*y/Ly)
Q = k*pi^2*(Lx^-2+Ly^-2)*(T-T0)
q_x = -k*A*(pi/Lx)*cos(pi*x/Lx)*sin(pi*y/Ly)
q_y = -k*A*(pi/Ly)*sin(pi*x/Lx)*cos(pi*y/Ly)
```

정답은 engine·solver·assembly를 import하지 않습니다. 기본 sine은 T0=300 K,
A=1 K이며 네 측면에 T0를 처방합니다. 정확한 Q는 `-k Laplacian(T)`, 정확한 flux는
직접 미분으로 구하고 이산 연산자를 쓰지 않습니다. 정답 미분 시험이 부호를 독립 검사합니다.

원래 구현 전 수용 기준을 유지합니다.

- slab 온도·flux 정규화 오차 <=1e-10. 전역 열률이 0이라는 사실과 독립적으로 측면 반력을 검사합니다.
- 단위 정사각형 n=8,16,32,64 P1 mesh, k=2.5 sine: **마지막 두 구간 모두**
  온도 L2 차수 >=1.8, flux L2 차수 >=0.9. 오차는 절점값·centroid만이 아닌 독립
  8x8 내부 삼각형 구적으로 측정합니다.
- 정규화 자유 잔차와 반력 기반 열 불균형 <=1e-10.
- SI 길이 인자 1e-3/1/1e3, 독립 열전도율·열원 인자 0.1/1/10에서 장 상사성 <=1e-9.
  x'=s*x, k'=c*k, Q'(x')=d*Q(x'/s)/s^2이면 같은 이산 기하에서
  `T'=300+(d/c)(T-300)`, `q'=(d/s)q`, load'=d*load, reaction'=d*reaction입니다.
- 독립 선형 열원 shape-function 모멘트, 성분 nullspace, finite/shape/material/boundary
  오류와 잘못된 기하를 검사합니다.

초기 source 구현의 가용 환경에서 마지막 두 온도 차수 1.99349/1.99836, flux 차수
0.99725/0.99931을 관측했습니다. 이는 고정 gate의 보조 증거이며 수치 잔차가 물리적
수렴을 대신하지 않습니다. 정확한 후보 revision의 전체 source·설치 배포 증거는 별도로 기록합니다.

## 한계

비정상 열용량, 복사 입력, 영역 안에서 변하는 열전도율(영역별 구간 상수는
[multimaterial](multimaterial.md)), 이방성 열전도율, 3D, 열탄성 연성, simcase·Studio
지원을 포함하지 않습니다. 기존 NumPy/SciPy와 직접 유도한 수식만 사용합니다. 외부
solver 소스나 새 runtime 의존성을 추가하지 않습니다. 문서·예제는 저장소에만
있고 배포본에 포함되지 않습니다.
