# 정상 Joule heating

명시적 단방향 workflow `galerkin.joule_heating.solve_steady_joule_heat`는
`galerkin.electric.solve_steady_electric`의 `SteadyElectricResult`를 받아
요소별 발열을 기존 정상 열 솔버에 전달합니다. 전기 결과의 기준 계약은
[정상 전기전도](electric_steady2d.md)에 정의되어 있습니다.

```python
from galerkin.electric import solve_steady_electric
from galerkin.joule_heating import solve_steady_joule_heat
from galerkin.mesh import rectangle_mesh

mesh = rectangle_mesh(.02, .01, 16, 8)  # metres
voltage = {int(i): 0. for i in mesh.boundary['left']}
voltage.update({int(i): 2. for i in mesh.boundary['right']})
electric = solve_steady_electric(mesh, conductivity=3., dirichlet=voltage)
temperature = {i: 300. for i in voltage}
result = solve_steady_joule_heat(
    mesh, electrical_result=electric, conductivity=5., dirichlet=temperature)
print(result.thermal.temperature.max())
print(result.source_power_per_length)  # W/m, not W
```

전기 해석은 사용자가 명시적으로 한 번 실행합니다. 전기전도도(S/m)와
열전도도(W/(m K))는 양의 스칼라 또는 영역별 상수이며 온도에 무관합니다.
비선형 연성 반복은 없습니다. 두 해석은 SI 좌표, 절점·삼각형 순서와 영역
식별자가 정확히 같은 메시를 사용합니다. 동일 사본은 허용하며 좌표·순서가
다르면 `ValueError`를 냅니다.

요소별 `Q=J·E`는 W/m³입니다. 보간·영역 평균·AC의 1/2 계수 없이 각 절점에
`Q*area/3`을 조립합니다. 전기 결과의 절점 부하·적분 전력을 열 조립 결과와
독립 비교합니다. `source_power_per_length`, `outward_heat_per_length`는
W/m이며 실제 두께(m)를 명시적으로 곱해야 W입니다. 반환 전기·열 결과는
입력과 독립적인 배열을 소유합니다. 추가 열원을 암묵적으로 더하지 않습니다.

`dirichlet`은 외부 절점→K입니다. `outward_flux`, `convection`은
[정상 열 경계 규약](thermal_flux_robin.md)의 외향 `q·n=g+h(T-Tambient)`를
따릅니다. 유속은 W/m², h는 W/(m² K)입니다. 미지정 변은 절연이며 독립 성분마다
고정 온도 또는 양의 Robin 지지가 필요합니다. 총 유출은 Dirichlet reaction의
음수에 지정 외향·대류 부하를 더한 값입니다. 양의 reaction은 열을 주입합니다.

## 요소 열원 API

`galerkin.thermal.ElementHeatSource(mesh, values)`는 유한 실수 `(M,)` 배열
(W/m³)을 메시 좌표·연결·영역 순서 사본에 결합합니다.
`solve_steady_heat(..., heat_source=source)`로 사용합니다. 일반 열 해석의
음수 냉각은 허용하지만 Joule workflow는 음수 Q를 거절합니다. 기존 스칼라·
영역 사전·좌표 함수 입력의 의미는 그대로이며 일반 배열은 거절합니다.
열 문제의 경계 태그는 달라도 되지만 메시 좌표·순서·영역 대응은 같아야 합니다.

## 검증과 한계

요소 전달 시험은 국소 부하·전력 보존·메시/순서 불일치·사본 소유·잘못된 값·
음수 냉각·영 열원을 확인합니다. 해석적 전기장을 사용한 준비 검증에서 온도는
약 2차, 열유속은 약 1차 수렴했습니다. 이는 실제 전기→열 API 검증이 아닙니다.
실제 공개 API 시험은 균질·두 재료 막대, 전압 부호·제곱 비례·영전압,
순수 Neumann 전기 경계, 열 Robin/지정 유속, 메시 불일치·입력 변경·결과 손상을
확인합니다. 0.02 m × 0.01 m에서 V=5000(x²-y²), sigma=3 S/m, k=5 W/(m K)이고
정확한 경계 온도 T=300+sigma*5000²/(3k)*(0.02⁴+0.01⁴-x⁴-y⁴)를 주면
8/16/32 분할의 마지막 온도/열유속 내부 L2 차수는 1.99897/0.99884로 기준
>1.8/>0.9를 통과했습니다. 전력 9.9609375/9.990234375/9.99755859375 W/m는
정확한 10 W/m로 수렴합니다. 독립 scikit-fem 12.0.2의 전기·열 조립으로
두 재료·전압/전류·열 혼합 경계를 비교한 최대 상대 차이는 1.54e-12(기준1e-9)입니다.
Linux Python3.12.14/NumPy2.3.5/SciPy1.17.0 결과이며 다른 OS 수용을 뜻하지 않습니다.

시험·crosscheck 의존성을 설치하고 저장소 루트에서 실행합니다.

```sh
python -m pytest -q tests/galerkin/test_element_heat_source.py tests/galerkin/test_joule_heating.py
OPENPHYSICS_REQUIRE_CROSSCHECK=1 python -m pytest -q tests/galerkin/test_crosscheck_skfem_joule.py
python examples/galerkin/joule_heating.py
```

[실행 예제](../../../../../../examples/galerkin/joule_heating.py)는 최고 온도
300.300000 K와 발열·유출 각각 6.000000 W/m를 출력합니다. 기존 소스 및 설치 휠
CI가 세 시험 모듈을 모두 수집하며 필수 crosscheck 설정은 도구 누락 시 실패합니다.
온도의존 물성·피드백 반복·과도 연성·다른 메시 전달·3D·UI는 범위 밖입니다.
2D 양은 두께당 값이며 P1 원시 경계 유속은 정확한 평형 유속이 아니므로
이산 에너지 수지는 조립 reaction으로 평가합니다.

[온도 의존 양방향 연성](temperature_joule_heating.md)은 별도 Python workflow다.

[균질 직사각형 JSON/CLI 입력·저장 계약](../simcase/electric_joule.md). Python API 전체 범위를 JSON에 노출하지는 않습니다.
