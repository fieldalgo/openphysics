# 정상 2D 외향 열유속과 대류

[English original](../../../thermal_flux_robin.md)

`galerkin.thermal.solve_steady_heat`를 명시적으로 import합니다. 균질·등방성·상수
열전도율 P1 삼각형 모델은 SI 좌표와 면외 단위 깊이에서
`-div(k grad T)=Q`를 풉니다. 독립 정답은 `refsol.thermal_boundary`에 있습니다.

## API와 단위

```python
result = solve_steady_heat(
    mesh, conductivity=2.5, dirichlet=prescribed_node_temperatures,
    heat_source=5.0,
    outward_flux={"right": 0.7},
    convection={"right": (10.0, 300.0)},
)
```

새 선택 키워드 두 개의 기본값은 `None`입니다. 기존 인자와 원래 다섯 결과 필드는
의미를 유지합니다. 선택하지 않은 자연 경계는 단열입니다. 위 오른쪽 경계에는
두 조건이 의도적으로 더해집니다.

`q.n = g_out + h*(T-T_amb)`, `q=-k grad T`.

| 입력 | 계약 |
| --- | --- |
| outward_flux | 외부 경계 edge tag→g_out 매핑, W/m². 양수는 열을 제거 |
| convection | tag→(h, T_amb) 쌍 매핑, h는 W/(m² K), 주변 온도는 K |
| 경계 상수 | 유한한 실수 스칼라. bool/complex 제외, h>=0 |
| 경계 콜백 | `(points_m, outward_normals)->values`. 두 인자는 `(Q,2)`, 반환은 정확히 `(Q,)`인 유한 실수. 스칼라·열·벡터 broadcasting 없음 |

세 경계량 모두 콜백일 수 있습니다. 외향 법선은 단위 길이이며 실제 인접 삼각형으로
계산하므로 tag 방향과 무관합니다. 구멍에서는 구멍 안을 향합니다. 콜백 배치는 절점이
아닌 구적점입니다. 콜백은 mesh를 변경하지 않아야 하며 결정적 동작을 권장합니다.
음수 g는 처방 열 주입입니다. T<T_amb에서 음수 대류는 주변으로부터의 가열입니다.
h=0은 허용하지만 절대온도를 고정하지 않으며, 이때도 주변 온도를 검증합니다.
h<0 또는 유한하지 않은 데이터는 거부합니다.

Dirichlet와 주변 온도에는 기존 저수준의 유한 실수 수학적 Kelvin 정책을 동일하게
적용합니다. 변환·clamping이나 주변 온도만의 양수 제약은 없습니다. 음수 절대 K는
물리적 유효성 주장 범위 밖입니다. 별도 문서 입력·열탄성 인터페이스는 더 엄격한
물리적 범위를 요구할 수 있습니다.

## 경계 검증과 유일성

선택한 `mesh.boundary_edges` tag는 존재하며 비어 있지 않아야 합니다. 선택한 정수
절점 쌍은 인접 삼각형이 정확히 하나인 실제 edge여야 합니다. 없는·빈 tag, 잘못된
shape/type/index, 길이 0, 고립·내부·비다양체 edge는 거부합니다. 정규화한 절점 쌍
식별자로 방향 반전을 포함한 중복을 같은 종류의 조건에서 tag 내부·사이에 걸쳐 거부합니다.
flux 한 개와 convection 한 개는 같은 edge에 더할 수 있습니다. 두 끝점이 모두
Dirichlet인 edge의 자연 조건 선언은 값이 0이어도 거부합니다. 혼합 경계 모서리에서
끝점 하나만 고정하는 것은 허용하며 해당 shape-function 하중을 버리거나 재정규화하지 않습니다.

연결 성분마다 Dirichlet 데이터 또는 양의 이산 적분 Robin 지지가 필요합니다. h=0은
고정 조건이 아닙니다. 순수 Neumann 호환성, 즉 열원과 처방 외향 열률의 일치만으로
상수 nullspace가 없어지지 않습니다. 호환·비호환 여부와 관계없이 고정되지 않은 성분은
거부합니다. 숨겨진 pin·gauge·의사역행렬·단위 의존 h cutoff는 없습니다. 샘플에서 양수인
h는 이산 증거일 뿐 샘플 사이의 콜백 동작을 보장하지 않습니다. 매우 작은 h는 악조건일 수
있습니다. 절점 Dirichlet는 이산계를 고정하지만, 고립된 점 구속만으로 연속체의 양의
경계 측도 조건을 충족한다고 주장하지 않습니다.

`Mesh`는 생성 시 연결 인덱스를 정수로 변환합니다. solver는 호출 시 실제 배열을
검증하며 이미 잘린 인덱스의 출처를 판별하지 않습니다. 기하에는
[기존 가이드](thermal_steady2d.md)의 적합·비중첩 요구가 유지됩니다.

## 약형의 부호, 결과와 열수지

P1 스칼라 shape function에 대해 다음과 같습니다.

```text
K_ij = integral_Omega k grad(N_i).grad(N_j) dA
H_ij = integral_Gamma h N_i N_j ds
fQ_i = integral_Omega Q N_i dA
G_i  = integral_Gamma g_out N_i ds
B_i  = integral_Gamma h T_amb N_i ds
A = K+H; system_rhs = fQ+B-G
r = A*T-system_rhs
reaction = r at fixed nodes, zero at free nodes
C = H*T-B
sum(fQ+reaction) = sum(G+C)   (also separately on every component)
```

| 결과 필드 | shape | 의미/단위 |
| --- | --- | --- |
| temperature | `(N,)` | 절점 T, K |
| heat_flux | `(M,2)` | 요소별 -k grad T, W/m² |
| load | `(N,)` | 기존 체적원 fQ, W/m |
| reaction | `(N,)` | 고정 절점의 열 주입, W/m |
| residual | `(N,)` | r의 모든 행, W/m |
| prescribed_outward_load | `(N,)` | G, W/m |
| ambient_load | `(N,)` | B, W/m |
| convective_outward | `(N,)` | C, W/m |
| system_rhs | `(N,)` | fQ+B-G, W/m |

thermostat의 외향 열률은 **-reaction**이며, 전체 외향 열률은 G+C-reaction입니다.
절점 적분량은 W가 아닌 깊이당 W/m입니다. W를 얻으려면 API 밖에서 실제 깊이(m)를
명시적으로 곱합니다. `load`를 경계·system 하중의 합으로 바꾸지 않습니다.
`SteadyHeatResult`를 기존처럼 다섯 위치 인자로 만들 수 있습니다. 추가 네 필드는
기본값 `None`이며 실제 solver 결과에는 아홉 배열이 모두 채워집니다.

4점 선 Gauss가 consistent 경계 행렬과 h*T_amb의 곱을 적분합니다. 길이 ell에서
상수 h이면 `H=h*ell/6*[[2,1],[1,2]]`입니다. 행렬을 lump하지 않으며 주변 하중을
별도 평균의 곱으로 적분하지 않습니다. 불연속·고진동 콜백은 별도의 구적·해상도 연구가
필요합니다. 체적 콜백은 기존 6x6 Duffy 규칙을 유지합니다.

수치 안정성을 위해 성분별 T=offset+increment를 사용합니다. K는 상수를 소거하지만
H는 그렇지 않으므로 이동된 주변 하중은 **h*(T_amb-offset)**을 적분합니다.
큰 절대 Kelvin offset을 복원하기 전에 대류·잔차·flux를 평가합니다. Dirichlet와 주변
온도를 함께 이동하면 flux가 보존되지만 고정된 주변 온도에서 T만 이동하는 것은 null
mode가 아닙니다. 보고된 절대 RHS·ambient 필드에는 내부 이동계보다 큰 상쇄오차가
있을 수 있습니다.

자유 잔차의 무한대 norm은
`max(norm(abs(A)@abs(increment)+abs(shifted_rhs), inf), tiny)`의 1e-10 이하여야 합니다.
성분별 열 불균형은 체적·반력·처방·대류 열률의 절댓값 합(또는 tiny)의 1e-10 이하여야
합니다. 유한하지 않은 조립·해 또는 품질 실패는 `ValueError`입니다. 이 검사는 FEM
이산화 오차를 추정하지 않습니다. 요소 gradient는 H(div) flux 복원이 아니므로 점별
경계 gradient가 약형 Robin trace와 정확히 같을 필요는 없습니다.

정상 변분 함수는
`0.5 integral k|grad T|² + 0.5 integral h(T-T_amb)² - integral QT + integral g_out T`입니다.
단위는 W K/m이며 저장된 열에너지가 아닙니다. work 항등식에는 처방 절점에서 0인
허용 시험 함수를 사용합니다.

## 독립 검증과 재현

기존 의존성과 패키지가 설치된 환경에서 저장소 루트로부터 실행합니다.

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python packages/galerkin/examples/thermal_flux_robin.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest -c pyproject.toml -q -s \
 packages/galerkin/tests/test_thermal_boundary.py \
 packages/galerkin/tests/test_thermal_boundary_convergence.py \
 packages/galerkin-refsol/tests/test_thermal_boundary_reference.py
```

예제는 상수 Q slab을 독립 다항식 `T=a+b*x-Q*x²/(2*k)`와 직접 비교합니다.
끝점 외향 flux는 k*b와 Q*L-k*b입니다. 정답은 왼쪽 Dirichlet/오른쪽 flux 또는 Robin,
양끝 Robin(한쪽 h=0 포함)을 다루며 FEM engine·assembly·solver를 import하지 않습니다.
직접 미분과 끝점 방정식으로 열원·경계 부호를 독립 확인합니다.

고정 gate는 기존 Dirichlet 시험을 모두 유지하며 다음을 추가합니다.

- 선형 patch의 온도·flux·측면 열률과 정규화 잔차·열수지 <=1e-10.
  양의 온도에서 냉각·주변 가열을 확인합니다.
- 상수 Q slab(flux/mixed/Robin-only)과 sine MMS(all-Robin/mixed),
  n8/16/32/64에서 마지막 두 구간 온도 L2 차수 >=1.8, flux 차수 >=0.9.
  독립 내부 8/10점 Duffy·경계 8/10점 norm 적분 차이는 측정 오차의 1% 미만입니다.
  0이 아닌 이차해 경계 flux trace는 수렴하고 최종 상대오차 <=2%여야 합니다.
  적분 대류는 이미 반올림 수준으로 정확할 수 있으므로 수치 잡음의 차수를 매기지 않고
  별도로 1e-10에서 검사합니다.
- sine MMS는 T=300+sin(pi*x)sin(pi*y)를 직접 미분합니다. 측면 법선 정답은
  명시적 사각형 기하이며 주변 온도는 T-(q.n-g)/h입니다. 기대값 구성에 생산 normal
  helper를 사용하지 않습니다.
- SI 길이 s=1e-3/1/1e3, 계수 c=.1/1/10: k'=c*k, Q'=c*Q/s²,
  g'=c*g/s, h'=c*h/s. T는 같고 flux는 c/s, 단위 깊이 열률은 c배이며
  정규화 일치 <=1e-9입니다. Kelvin 공동 offset 1e8과 h0 불변성도 검사합니다.
- 독립 consistent affine 선 모멘트와 실제 runtime mutation: 처방 부호 오류, 음의 H,
  주변 항·offset 보정 누락, lumped mass, 곱의 분리 평균, 법선 반전이 실패해야 합니다.
- 잘못된 값·shape·위상·겹침, 구멍, 분리 성분, 순수 Neumann 호환성과 유일성 구분을
  검사합니다. gate를 낮추려는 의도는 없습니다.

비정상, 복사, 가변·이방성 k, 온도 의존 h, 3D, 새 연성 workflow, simcase/Studio 또는
export 연결은 추가하지 않습니다. 기존 NumPy/SciPy만 사용하며 새 runtime 의존성이나
외부 solver 소스는 없습니다. 문서·예제는 배포본에 포함되지 않습니다.
