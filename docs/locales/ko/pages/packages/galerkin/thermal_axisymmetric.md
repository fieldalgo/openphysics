# 축대칭 정상 열전도

[English](../../../../../packages/galerkin/thermal_axisymmetric.md) | **한국어**

`solve_steady_heat(..., coordinate_system="axisymmetric")`는 좌표가 **미터 단위
(r,z)**인 P1 삼각형 메시에서 정상 열전도를 풉니다. 기본값 `"cartesian"`은 기존
단위 두께당 계산을 유지합니다.

```python
from galerkin.mesh import rectangle_mesh
from galerkin.thermal import solve_steady_heat

R, L, k, Q, Tb = .003, .001, 1.114, 1e5, 293.15
mesh = rectangle_mesh(R, L, 64, 32)
result = solve_steady_heat(
    mesh, conductivity=k, heat_source=Q,
    dirichlet={int(i): Tb for i in mesh.boundary["right"]},
    coordinate_system="axisymmetric",
)
assert result.nodal_heat_rate_unit == "W"
absorbed_W = result.load.sum()
outward_W = -result.reaction.sum()
```

## 적분과 경계조건

체적 측도는 `2*pi*r dr dz`, 경계 측도는 `2*pi*r ds`입니다. 전체 회전량이며 라디안당
또는 두께당 값이 아닙니다. 기존 [정상 열](thermal_steady2d.md)의 상수/영역별 전도도,
좌표 callback, ElementHeatSource, Dirichlet·flux·Robin 입력을 재사용합니다.

`core.measure.ScalarMeasure`가 기존 커널·forms·하중 구적에 정적 기하 가중치를
제공합니다. P1·요소별 일정 전도도의 강성 적분은 정확합니다. 일정 요소 Q도
`Q N_i 2*pi*r`로 적분하므로 요소 전력을 세 절점에 똑같이 나누는 방법과 다릅니다.
경계는 기존 Gauss 점에서 가중합니다. 별도 열 솔버를 복제하지 않았습니다.

r은 음수가 될 수 없습니다. r=0에서는 유한 P1 함수와 가중 약형식으로 자연 정칙성을
처리하며 1/r을 계산하지 않습니다. 축 edge의 비영 flux 또는 convection h를 거부합니다.
축에만 속한 절점의 Dirichlet도 거부합니다. 실제 끝면에 속하는 축 끝점은 그 끝면의
Dirichlet 온도를 가질 수 있습니다. r>0인 환형 영역도 허용합니다. 선택하지 않은
실제 경계는 단열이며, 연결 성분마다 Dirichlet 또는 양의 Robin 지지가 필요합니다.
순수 Neumann 문제는 지원하지 않습니다.

## 단위와 결합

온도는 K, 열유속 `(q_r,q_z)`는 W/m²입니다. 적분한 절점량(load·reaction·residual·경계
하중·system_rhs)은 W입니다. 결과의 `coordinate_system`과 `nodal_heat_rate_unit`이
이를 기록합니다. Cartesian은 `"cartesian"`·`"W/m"`입니다. 수지는
`sum(load + reaction - prescribed_outward_load - convective_outward) = 0`입니다.

[Field](coupling.md)의 Q W/m³는 여전히 체적 밀도입니다. 요소 체적은
`2*pi*mean(r_vertices)*area`입니다. Field는 메시·단위만 저장하므로 **축대칭 좌표·측도는
호출자의 실행 기록에 별도로 보존**해야 합니다. transfer는 이를 추론하지 않습니다.
simcase JSON·Studio·격자 투영은 추가하지 않습니다. 기존 Cartesian 결과 식별자로
축대칭 W 결과를 저장하면 안 됩니다.

계수·경계 입력은 기존 JAX/PyTorch 역방향 미분을 유지합니다. 기하는 정적이며 물리 간
Field는 NumPy 전용입니다. 기하 미분·Field 전달 미분을 지원한다고 주장하지 않습니다.

## 검증과 한계

`test_thermal_axisymmetric.py`에서 원통 해 `T-Tb=Q(R²-r²)/(4k)`, 전력
`Q*pi*R²*L` 및 반력 수지(상대 1e-10)를 확인합니다. 원통·곡면 제조해의
nr16/32/64/128 가중 L2 차수는 1.8–2.2, H1은 0.9–1.2, 최종 L2는 0.5% 이하를
요구합니다. 곡면 제조해의 경사면은 단열이 아니라 `q_out=Q*r*n_r/2`입니다.
축 방향 선형 온도의 flux/Robin, Robin만 있는 원통, 네 열원 형식, 영가열, 축 입력 거부,
두 배열 라이브러리의 Q/k 해석 기울기(상대 1e-6)를 검사합니다. 일정 열원의 정확한
형상함수 모멘트, 환형 영역의 로그 해, 길이 변경 시 전체 전력의 스케일도 검사합니다.

처음 점별 온도 검사는 nr32에서 0.02444K>0.02K, Robin 검사는 nr64에서
0.00007059K>0.00006K로 실패했습니다. nr64/nr128로 세분해 **같은 허용오차**를
통과했습니다. 거친 메시가 정확하다는 뜻은 아닙니다. 로컬 관련 시험은 213개 통과했고
Linux Python3.12.14·NumPy2.3.5·SciPy1.17.0·JAX0.12.0.1·PyTorch2.15.0+cpu를
사용했습니다. PyTorch의 asarray 기본값 경고는 남았습니다. 필수 CI·다른 OS 검증과
이 로컬 결과는 구분합니다. 추가 열/Joule/Field/forms 회귀는 261개 통과, 최종 축대칭
시험 파일만은 21개 통과했습니다. 서로 겹치는 실행이므로 수를 합산하지 않습니다.

정상 스칼라 축대칭 열만 지원합니다. 각도 모드·구조변형·과도 열·광학·열복사는 없습니다.
