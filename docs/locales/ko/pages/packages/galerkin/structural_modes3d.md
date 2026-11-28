# 구속된 3D 고체의 고유진동수

[English](../../../../../packages/galerkin/structural_modes3d.md)

Python 함수 `solve_structural_modes_3d`는 초기 응력이 없는 고체의 미소 무감쇠 자유진동을 계산한다. 낮은 고유진동수부터 지정한 개수만큼 주파수와 절점 모드 형상을 돌려준다.

```python
from galerkin.mesh3d import box_mesh
from galerkin.structural_modes3d import solve_structural_modes_3d

mesh = box_mesh(0.12, 0.018, 0.012, 48, 6, 6)
clamp = {(n, a): 0.0 for n in mesh.boundary["x0"] for a in range(3)}
modes = solve_structural_modes_3d(
    mesh, youngs_modulus=70e9, poisson_ratio=0.0, mass_density=2700.0,
    prescribed_displacement=clamp, mode_count=2,
)
tip_shapes = modes.mass_normalized_displacement[:, mesh.boundary["x1"], :]
print(modes.frequency)
```

좌표 단위가 m인 정합 선형 사면체 메시를 사용한다. 영률(Pa), 푸아송비, 질량 밀도(kg/m³)는 각각 스칼라 또는 모든 재료 영역 이름에 대응하는 사전으로 준다. 변위 성분 번호와 구속 조건은 [정적 탄성](elasticity3d.md)과 같다. 지지점의 구속 변위를 0으로 주고 분리된 고체마다 강체 운동 6개를 제거한다. 나머지 표면의 표면력은 0이다. `mode_count`는 자유 변위 성분 수 이하의 양의 정수이며 기본값은 1이다.

등방 탄성 강성행렬과 일관 질량행렬에서 구속된 성분을 제거한 뒤 $K u = (2\pi f)^2 M u$를 푼다. `frequency`는 Hz 단위의 실수 고유진동수를 오름차순으로 담는다. `mass_normalized_displacement`는 (모드, 절점, xyz) 배열이며 단위는 kg⁻¹ᐟ²이다. 각 모드를 열로 모은 $U$는 $U^T M U = I$를 만족한다. 모드 진폭은 이 정규화로 정해지며 부호는 임의다. 반복 고유진동수에서는 해당 모드 부분공간이 정해진다. `relative_residual`은 모드별 자유 성분에서 계산한 $\|Ku-\lambda Mu\|/(\|Ku\|+\|\lambda Mu\|)$이며 1e−6을 넘으면 오류를 낸다. 강제 응답, 초기 응력, 감쇠는 별도 모델이 필요하다.

## 외팔보 검증

패키지가 설치된 환경에서 저장소 루트의 `python examples/galerkin/cantilever_modes_3d.py`를 실행한다. 직사각형 외팔보의 치수는 120 × 18 × 12 mm이며 $E=70$ GPa, $\rho=2700$ kg/m³, $\nu=0$이다. 낮은 두 모드는 각각 두께 방향과 폭 방향으로 굽힌다.

| 사면체 수 | 1차 모드 (Hz) | 2차 모드 (Hz) |
|---:|---:|---:|
| 1,296 | 819.54 | 1,172.97 |
| 10,368 | 719.92 | 1,055.19 |
| 34,992 | 698.76 | 1,032.13 |
| 오일러–베르누이 세장보 근사 | 685.43 | 1,028.15 |

가장 세밀한 메시에서 보 이론과의 차이는 1.94%, 0.39%이다. 3D 고체 모델은 전단 변형과 회전 관성을 포함한다. 이 예제에서는 성긴 선형 사면체 메시가 굽힘 강성을 크게 평가한다. 별도의 두 재료 시험에서는 같은 메시로 scikit-fem이 독립적으로 조립한 첫 다섯 주파수와 모드 형상을 대조하고, 질량 직교성과 자유 성분의 평형 잔차를 확인한다.

[실행 예제](../../../../../../examples/galerkin/cantilever_modes_3d.py) · [독립 비교 시험](../../../../../../tests/galerkin/test_crosscheck_skfem_structural_modes3d.py)
