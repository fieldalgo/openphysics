# 구속된 3D 고체의 강제진동

[English](../../../../../packages/galerkin/structural_harmonic3d.md)

`galerkin.structural_harmonic3d.solve_structural_harmonic_3d`는 정현파 하중을 받는 구조물의 정상 주기 변위와 탄성 응력을 계산한다. 주파수마다 사면체 메시에서 선형 연립방정식을 푼다.

```python
import numpy as np
from galerkin.mesh3d import box_mesh
from galerkin.structural_harmonic3d import solve_structural_harmonic_3d

mesh = box_mesh(.12, .018, .012, 32, 4, 4)
clamp = {(n, a): 0.0 for n in mesh.boundary["x0"] for a in range(3)}
response = solve_structural_harmonic_3d(
    mesh, youngs_modulus=70e9, poisson_ratio=0., mass_density=2700.,
    prescribed_displacement=clamp, frequency=[0., 500., 700., 900.],
    traction={"x1": (0., 0., 1000.)}, stiffness_proportional_damping_coefficient=1e-5,
)
tip = response.displacement[:, mesh.boundary["x1"], 2].mean(axis=1)
print(np.abs(tip) * 1e6, np.angle(tip, deg=True))  # micrometres and degrees
```

길이 단위는 m이다. 영률(Pa), 푸아송비, 질량 밀도(kg/m³)를 스칼라 또는 재료 영역 이름별 사전으로 주고 지지점의 구속 변위를 0으로 준다. 분리된 고체마다 강체 운동을 구속한다. `frequency`는 0 이상의 Hz를 담은 1차원 배열이며 입력 순서대로 결과를 반환한다. 균일한 직교 성분 체적력 밀도(N/m³)와 이름을 붙인 외부 면의 일정한 표면력(Pa)에 복소 진폭을 줄 수 있다. 이 하중은 주파수 전체에 적용된다. 각 하중 성분은 $f(t)=\operatorname{Re}(\hat f e^{-i\omega t})$ 규약의 최대 진폭이다.

$\omega=2\pi f$에서 $[K-\omega^2 M-i\omega C]\hat u=\hat F$를 푼다. 레일리 감쇠행렬은 $C=\alpha M+\beta K$이다. 0 이상인 `mass_proportional_damping_coefficient`($\alpha$, s⁻¹)와 `stiffness_proportional_damping_coefficient`($\beta$, s)를 생략하거나 `None`을 주면 해당 감쇠 기여는 0이다. 0 Hz에서는 정적 탄성 해석으로 환원된다. 무감쇠 고유진동수에서는 정상 응답이 유일하게 정해지지 않는다. 유한한 공진 응답을 구할 때는 물리적 감쇠를 입력한다.

| 결과 | 배열 형태 | 의미 |
|---|---|---|
| `frequency` | (F,) | 입력 순서의 주파수(Hz) |
| `displacement` | (F,N,3) | 절점 복소 변위(m) |
| `stress` | (F,T,3,3) | 대칭 복소 탄성 응력(Pa), 인장이 양수 |
| `reaction_force` | (F,N,3) | 동적 지지 반력(N), 자유 성분은 0 |
| `relative_residual` | (F,) | 자유 성분 평형의 무차원 상대 잔차 |

F, N, T는 각각 주파수, 절점, 사면체 개수이다. 응력은 탄성 변형률에서 계산한다. 동적 지지 반력에는 관성과 레일리 감쇠의 기여도 들어간다. 양의 실수 하중을 기준으로 비교할 때 이 시간 규약에서 양의 변위 위상은 응답의 시간 지연을 뜻한다. 각 주파수에서 감쇠 가중치를 포함한 강성항, 관성항, 외력항의 노름 합으로 자유 성분의 잔차를 나눈다. 상대 잔차가 1e−6을 넘으면 오류를 반환한다. 모델은 초기 응력이 없는 고체의 소변형 선형 응답을 가정한다.

실행 예제에서는 120 × 18 × 12 mm 외팔보 끝면에 아래쪽으로 총 1 N을 가한다. 사면체 10,368개의 메시에서 첫 굽힘 고유진동수는 719.92 Hz이다. 이 모드의 감쇠비를 2%로 설정하면 끝면 평균 변위의 진폭은 0 Hz에서 2.855 µm, 첫 고유진동수에서 69.197 µm이며 이때 변위가 하중보다 89.92° 늦는다. 메시를 사면체 34,992개로 세분화하면 첫 고유진동수는 698.76 Hz, 정적 진폭은 3.033 µm, 해당 고유진동수에서 진폭은 73.518 µm이다. 검증 시험에서는 봉의 메시를 세분화하며 축방향 파동의 해석해에 수렴하는지 확인하고, 두 재료로 만든 고체의 변위·탄성 응력·지지 반력을 scikit-fem으로 독립 조립한 모드 중첩 해와 비교한다.

[외팔보 주파수 스윕 예제](../../../../../../examples/galerkin/cantilever_frequency_response_3d.py) · [해석해 비교](../../../../../../tests/galerkin/test_structural_harmonic3d.py) · [독립 유한요소 비교](../../../../../../tests/galerkin/test_crosscheck_skfem_structural_harmonic3d.py) · [고유진동수와 모드 형상](structural_modes3d.md)
