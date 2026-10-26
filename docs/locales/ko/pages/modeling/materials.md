# 재료 데이터와 유효 범위 선택

[English](../../../../modeling/materials.md) | **한국어**

[문서 홈](../index.md)

관심 있는 물리량·파장·온도에 맞는 재료 레코드를 선택합니다. 재료 이름만으로
OpenPhysics 해석에 필요한 모든 계수가 정해지지는 않습니다. 이 가이드는
[physmat API](../packages/physmat/overview.md)와
[영역별 재료 모델](../packages/galerkin/multimaterial.md)을 연결합니다.

## 사용 전에 레코드 확인하기

```python
import physmat

si = physmat.get("Si")
wavelength_um = 1.55
print(si.source)
print(si.range_um)
print(si.index(wavelength_um))

conductivity = si.properties["thermal_conductivity"]
print(conductivity.unit, conductivity.source)
k_w_mk = si.get("thermal_conductivity", T=300.0)
print(k_w_mk)
```

`physmat` 광학 호출의 파장 단위는 항상 **마이크로미터**이며, `simcase` 문서의
형상 단위와 무관합니다. 내장 Si 레코드의 범위는 1.357–11.04 µm이고 1.55 µm는
그 안에 있습니다. 기본 strict 검사에서는 범위를 벗어나면 `physmat.OutOfRange`가
발생합니다. 범위 검사를 끄더라도 외삽의 타당성이 확보되지는 않습니다.
선택한 레코드의 출처와 범위를 확인하세요. 같은 물질이라도 시편이나 측정 조건이
다른 레코드가 존재할 수 있습니다.

위 Si 열전도율은 300 K의 핸드북 값인 148 W/(m K)입니다. 출처는 광학 모델의
출처와 별도로 각 물성에 붙어 있습니다. 상수 `Property`에 다른 `T`를 전달해도
동일한 상수를 반환합니다. 온도 의존 법칙이나 유효 온도 구간이 생기지 않습니다.
함수형 물성도 표현할 수 있지만, 허용하는 계수 형태는 각 solver가 결정합니다.

## 물리량 구분하기

| 입력 | 의미와 단위 | 확인할 내용 |
|---|---|---|
| 광학 `n`, `k` | 굴절률과 소광계수, 무차원 | 파장 범위·분산·흡수 부호 규약 |
| 열전도율 | W/(m K) | 시편·온도·등방성/이방성 가정 |
| 밀도·비열 | kg/m³·J/(kg K) | 곱은 체적 열용량 J/(m³ K) |
| 전기전도율 | S/m | 전기 모델과 명시적 온도 의존 법칙 |
| Young 탄성계수·Poisson 비·열팽창계수 | Pa·무차원·1/K | 역학 가정과 무응력 기준 온도 |

광학 소광계수 `k`는 열전도율이 아니며, 광학 유전율이 DC 전기전도율을 제공하지도
않습니다. `physmat`에는 일부 비광학 핸드북 물성이 있지만 열·Joule·역학 모델을
자동으로 채우지 않습니다. 선택한 API나 문서 계약에 필요한 값만 단위와 출처를
명시해 옮기세요. 없는 물성은 `KeyError`를 발생시키며, 관련 없는 광학 값으로
대체하면 안 됩니다.

## 모델에 배정하기

광학 JSON에서는 내장 재료 이름 또는 지원되는 사용자 정의 상수 `n`/`k`, Sellmeier
정의를 사용합니다. 문서의 파장·Sellmeier 길이 입력은
[simcase 단위 계약](../packages/simcase/overview.md)을 따르고, `physmat` 직접 호출은
여전히 µm를 사용합니다. 두 인터페이스의 길이 규약을 섞지 마세요.

열 모델에서는 [영역 열 계약](../packages/simcase/thermal_regions2d.md)의 명시적인
열전도율·열용량 필드를 사용합니다. 각 도형과 배경의 재료, 도형이 덮지 않은 공간,
겹치는 도형의 우선순위를 확인하세요.
[두 재료 벽 튜토리얼](../packages/simcase/layered_wall_tutorial.md)에서 저장된 영역
배정과 열유속을 확인할 수 있습니다.

온도 의존 Joule 발열에는 [Joule 계약](../packages/simcase/electric_joule.md)이나
[Python 워크플로](../packages/galerkin/temperature_joule_tutorial.md)가 지원하는 법칙을
입력합니다. 광학 열광학 계수가 있다고 자동 연성 해석이 활성화되지는 않습니다.

## 선택을 재현할 정보 보존하기

재료 출처·선택한 레코드·계수·단위·파장 또는 온도 구간·피팅 설정을 모델과 함께
보관합니다. Drude–Lorentz 피팅 오차는 피팅 표본에 대한 값이므로 실제 사용할 대역을
따로 확인하세요. 메시 수렴으로 부적절한 재료 모델을 고칠 수는 없습니다. 불확실한
재료 계수의 변화는 [수치 수렴 검사](../validation/convergence.md)와 구분해 수행합니다.
