# 3D 정상 직류 전기전도

[English](../../../../../packages/galerkin/electric_steady3d.md) | **한국어**

`galerkin.electric3d.solve_steady_electric_3d`는 적합 선형 사면체에서
∇·J = 0, J = σE, E = −∇V를 SI 단위로 풉니다. 좌표가 m 단위이고 외부 면
태그가 있는 [Mesh3D](mesh3d_format.md)를 전달합니다. 전기전도도는 S/m 단위의
유한한 양의 스칼라 또는 모든 `mesh.region_names`에 해당하는 유한한 양의
스칼라를 담은 매핑입니다. 각 요소 안에서 전도도는 일정합니다.

`{외부_면_태그: 전압}`으로 단자 전위를 지정합니다. 단자끼리 노드를 공유할
수 없으며 각 연결 성분에는 단자가 필요합니다. 나머지 외부 면에는 법선
전류가 0인 자연 경계조건을 적용합니다. 이 API는 등방성 재료와 전위 경계에서
NumPy와 SciPy를 사용합니다.

```python
from galerkin import box_mesh
from galerkin.electric3d import solve_steady_electric_3d
from galerkin.thermal3d import solve_steady_heat_3d

mesh = box_mesh(0.4, 0.2, 0.3, 4, 2, 2)
electric = solve_steady_electric_3d(
    mesh, electrical_conductivity=8.0,
    prescribed_electric_potential={"x0": 6.0, "x1": 1.0},
)
thermal = solve_steady_heat_3d(
    mesh, thermal_conductivity=4.0,
    prescribed_temperature={int(i): 300.0 for i in mesh.boundary["x0"]},
    heat_source_density=lambda centroids: electric.joule_power_density,
)
```

| 결과 | 배열 형상·SI 단위 |
|---|---|
| `electric_potential` | 노드 순서의 (N,) V |
| `electric_field`, `current_density` | (T, 3) V/m와 A/m² |
| `electrical_conductivity`, `joule_power_density` | (T,) S/m와 W/m³ |
| `terminal_current` | 면 태그별 A, 도체 안으로 흐르면 양수 |
| `joule_power`, `inward_electric_power` | 체적 발열 적분과 단자 공급 전력, 각각 W |

조립한 강성 행렬에서 단자별 노드 반력을 합산해 전류를 얻습니다. 공급
전력은 Σ Vₖ Iₖ이며, 공통 전압 이동에 따른 상쇄를 줄이기 위해 연결 성분마다
기준 전압을 뺀 값으로 계산합니다. 사면체마다 J·E를 하나씩 반환하며 모든
요소 배열은 입력 `mesh.tets` 순서를 따릅니다. J·E에 사면체 부피를 곱해
합하면 `joule_power`입니다. 위 열원 콜백은 같은 메시에서 이 배열을 그대로
반환합니다. 형상이나 요소 순서가 바뀌면 전기 해를 다시 구합니다.

## 검증

- 0.4 m × 0.2 m × 0.3 m 균질 도체에 σ = 8 S/m, ΔV = 5 V를 적용하면
  R = L/(σA) = 5/6 Ω, 전류 6 A, 발열 30 W입니다. 세 메시 해상도에서
  선형 전위와 일정한 E, J, J·E를 확인합니다.
- 길이 0.1 m·0.3 m, 전도도 2·8 S/m인 직렬 재료에서 구간별 선형 전위와
  연속인 법선 전류를 확인합니다. 사면체 순서를 뒤집어 열 솔버가 같은
  순서의 J·E를 소비하고 단자 전력과 같은 발열을 얻는지 검사합니다.
- 0~1 m 구간에서 σ(x) = 2 + x인 도체의 로그 저항 해에 대해 전류 수렴을
  검사합니다. 각 층의 중간점 전도도를 쓰고 층 수를 두 배로 늘리면
  2차 수렴을 보입니다.
- scikit-fem으로 같은 사면체에서 횡방향 전기장이 있는 두 재료 교차 배치를
  독립적으로 조립하고 풉니다. 영역과 단자 노드는 좌표로 별도 판정합니다.
  V, E, J, J·E, 양쪽 단자 전류와 두 적분 전력의 전체 상대 차이 허용치는
  10⁻¹⁰입니다.
