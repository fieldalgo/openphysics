# 3D 정상 직류 전기전도

[English](../../../../../packages/galerkin/electric_steady3d.md) | **한국어**

`galerkin.electric3d.solve_steady_electric_3d`는 적합 선형 사면체에서
∇·J = 0, J = σE, E = −∇V를 SI 단위로 풉니다. 좌표가 m 단위이고 외부 면
태그가 있는 [Mesh3D](mesh3d_format.md)를 전달합니다. 전기전도도는 S/m 단위의
유한한 양의 값으로, 스칼라, 모든 `mesh.region_names`를 포함하는 스칼라 매핑,
또는 `mesh.tets` 순서의 (T,) 배열을 사용합니다. 각 요소 안에서 전도도는 일정합니다.

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
    heat_source_density=electric.joule_power_density,
)
```

| 결과 | 배열 형상·SI 단위 |
|---|---|
| `electric_potential` | 노드 순서의 (N,) V |
| `electric_field`, `current_density` | (T, 3) V/m와 A/m² |
| `electrical_conductivity`, `joule_power_density` | (T,) S/m와 W/m³ |
| `inward_current` | 면 태그별 A, 도체 안으로 흐르면 양수 |
| `joule_power`, `inward_electric_power` | 체적 발열 적분과 단자 공급 전력, 각각 W |

조립한 강성 행렬에서 단자별 노드 반력을 합산해 전류를 얻습니다. 공급
전력은 Σ Vₖ Iₖ이며, 공통 전압 이동에 따른 상쇄를 줄이기 위해 연결 성분마다
기준 전압을 뺀 값으로 계산합니다. 사면체마다 J·E를 하나씩 반환하며 모든
요소 배열은 입력 `mesh.tets` 순서를 따릅니다. J·E에 사면체 부피를 곱해
합하면 `joule_power`입니다. 같은 메시의 열 솔버에 이 배열을 바로 넘깁니다.
형상이나 요소 순서가 바뀌면 전기 해를 다시 구합니다.
[3D 줄 발열 예제](../../../../../../examples/galerkin/joule_heating_3d.py)는 한쪽 단자의
대류 냉각까지 실행합니다. 전기전도도가 온도에 따라 변하지 않는 단방향 연성입니다.

## 온도 의존 재료 평가

결합 솔버는 기존
`galerkin.temperature_joule_heating.ConductivityModel`을 단독으로 쓰거나,
이름 있는 영역 매핑에서 상수 전도도와 섞어 사용할 수 있습니다. 각 모델이
적용되는 사면체의 모든 절점 온도는 해당 모델의 유효 범위(K, 양 끝 포함)에
있어야 합니다. 콜백은 사면체의 네 절점 온도를 산술 평균한 값들을 받아
각 평균에 대해 유한한 양의 전도도(S/m)를 반환합니다.

정상 DC 풀이는 한 전압 상태에서 이렇게 얻은 전도도 배열을 사용합니다.
전압과 온도의 평가 시각은 과도 결합 솔버가 정합니다. 같은 전압을 인가한
도체의 전체 저항이 높아지면 총 줄 발열은 감소합니다. 단자 전류는 도체
안쪽이 양수이며, 요소별 줄 발열원 J·E(W/m³)는 0 이상입니다.


## 검증

- [3D 연성 시험](../../../../../../tests/galerkin/test_joule_heating_3d_coupling.py)은
  단면 10 × 10 mm, 길이 20 mm인 도체를 길이가 같은 두 층으로 나눕니다.
  전기전도도는 각각 1·3 S/m, 열전도율은 1·2 W/(m K)입니다. 2 V를 가하면
  전류는 15 mA이고 발열은 0.030 W입니다. 한쪽 끝에서 300 K 주변으로 대류
  냉각(h = 100 W/(m² K))할 때 반대편 단열 끝의 이론 최고 온도는 305.4375 K입니다.
  두 층의 국소 열원, 냉각 면의 독립 열량 적분, 세 단계 메시의 노드·요소 중심 온도를 검사합니다.
- [scikit-fem 연성 비교](../../../../../../tests/galerkin/test_crosscheck_skfem_joule_heating_3d.py)에서는
  한쪽 끝 면의 절반만 전극으로 덮습니다. 두 솔버가 각각 전위, 발열밀도, 온도 상승을
  구합니다. 이 세 필드와 단자 전력, 체적 발열, 대류 방출의 상대 허용오차는 10⁻⁹입니다.

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

- 온도 의존 히터와 상수 전도도 리드를 직렬로 이은 정전압 도체를 세 온도와 세 메시에서 검증했습니다. 총 저항, 구간별 전위, 요소별 J·E를 기준해와 비교했습니다.
