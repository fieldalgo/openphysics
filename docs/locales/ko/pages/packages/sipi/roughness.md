# 인과적 도체 표면 거칠기

[English](../../../../../packages/sipi/roughness.md) | **한국어**

[표면 추출](conductor.md) · [주파수 선로 JSON](line_model.md)

`sipi.roughness.CausalHuray`는 구형 돌기의 반지름(m)과 구 전체 표면적 비율을
명시합니다. 양도체 반공간의 저항과 리액턴스를 함께 보정합니다. 모든 신호·기준
도체 표면에 같은 모델을 적용하며, 윗면·아랫면별 선택 기능은 아닙니다.

```python
from sipi.roughness import CausalHuray
from sipi.conductor import surface_impedance

roughness = CausalHuray(radii_m=[.5e-6, 1.5e-6], surface_ratios=[1.2, .3])
zs = surface_impedance([1e9, 4e9, 10e9], conductivity=58e6, roughness=roughness)
```

`surface_conductor_loss`도 `roughness=`를 받습니다.
`ConductorLoss.roughness_factor`는 복소 승수가 아니라 기존 의미인
**실수 저항비** `Re(Zrough)/Re(Zsmooth)`입니다. 기존 `roughness_rms`는
Hammerstad 경험식으로 R만 보정합니다. 비영 RMS와 `CausalHuray`를 함께 지정하면 거부합니다.

## 파라미터와 정식화

길이가 같은 1..64개 집단을 받으며 유한 실수 반지름 `a>0`, 면적비 `SR>=0`가 필요합니다.
`SR=N*4*pi*a^2/Aflat`는 투영 원판이 아닌 구 전체 표면적 비율입니다.
기본 matte/flat 면적비는 1로 고정합니다. bool·복소수·null·표현할 수 없는 총 포화값을
거부합니다. 입력 배열은 불변 tuple로 복사하며, 면적비 0인 집단의 기여는 0입니다.
Ra/Rq/Rz나 구 충진 구조로부터 자동 환산하지 않습니다. `factor(skin_depth)`는
비어 있지 않은 양의 유한 실수 1차원 표피 깊이(m) 배열을 받아 순서를 보존합니다.

`exp(+j omega t)`, `s=j*omega`, `mu=mu0*mu_r`에서:

```text
delta = 1/sqrt(pi*f*mu*sigma)
q_i = sqrt(s*mu*sigma*a_i^2) = (1+j)*a_i/delta
H(s) = 1 + sum_i (1.5*SR_i)*q_i/(1+q_i)
Zrough = sqrt(s*mu/sigma)*H(s)
```

제곱근은 주값입니다. 별도로 정의한 실수 손실비는
`1+sum_i 1.5*SR_i/(1+delta/a_i+delta^2/(2*a_i^2))`입니다.
이 **실수** 비율을 매끈한 복소 임피던스 전체에 곱하면 리액턴스를 놓칩니다.
구현은 상쇄를 피하도록 R/X 보정을 따로 계산하고, 반지름·깊이를 정규화한 후
제곱해 overflow를 피합니다. 수학적으로 H의 저주파 극한은 1, 고주파 극한은
`1+1.5*sum(SR)`이며, 추가 저주파 면 인덕턴스의 극한은 `sum(1.5*SR*mu*a)`입니다.

정식화의 출처는 J. Eric Bracken, *A Causal Huray Model for Surface Roughness*,
DesignCon 2012입니다. 복소 승수·구 계수·꺾임 주파수는 Yong Wang/Scott Langdon의
[FDTD Simulation of Multilayer-Coated and Rough Surface Metals Using Surface
Impedance Method](https://zh.remcom.com/hubfs/Blog%20Images/Remcom_ArbitrarilyShapedThinResistiveSheets_Presentation_ACES2019.pdf),
ACES 2019, 슬라이드 6에 명시됩니다. 그 문서의 `omega_i=2/(a_i^2*mu*sigma)`가
위 q를 줍니다. 이 구현은 기본 면적비 1인 경우입니다. 외부 소스 코드·그림·실측 피팅
데이터는 배포하지 않습니다.

## 버전 있는 선로 입력

기존 `sipi.transmission-line/1`은 그대로 유지합니다. Python 생성자나 JSON에서
`schema='sipi.transmission-line/2'`를 명시해야 새 계약을 선택합니다.
버전 2의 최상위 필드·기하·재료·perfect 금속 계약은 같으며 surface 레코드의
`roughness_rms`만 다음 중 하나의 `roughness` 객체로 대체합니다.

| 종류 | 정확한 필수 필드 |
|---|---|
| 매끈한 표면 | `{"kind":"smooth"}` |
| 경험적 Hammerstad | `{"kind":"hammerstad","rms_m":1e-6}` |
| 인과적 Huray | `{"kind":"causal-huray","radii_m":[5e-7,1.5e-6],"surface_ratios":[1.2,0.3]}` |

`rms_m`는 유한 비음수 실수 scalar입니다. conductivity·ground_thickness·
relative_permeability는 여전히 필수입니다. 누락·미지 필드·버전 혼합·중복 키·
유효하지 않은 집단은 메시 생성 전에 거부합니다. `dumps()`는 선택한 버전과
해결된 메시 설정을 보존합니다. 자동 마이그레이션이나 결과 직렬화는 없습니다.
생성자 기본값도 버전 1입니다. 실행 예제:
[`causal_roughness.py`](../../../../../../examples/sipi/causal_roughness.py).

## 검증과 한계

`tests/sipi/test_roughness.py`는 양의 1차 완화 응답을 연속적으로 적분한
다음 표현을 SciPy quadrature로 계산하여 독립 대조합니다.

```text
q/(1+q) = (2/pi) integral_0^(pi/2) z/(z+tan(theta)^2) dtheta
z = s*mu*sigma*a^2
```

같은 닫힌 제곱근 공식을 다시 계산하는 시험이 아닙니다.
`omega*mu*sigma*a^2=1e-6..1e6`에서 복소 상대·절대 기준은 1e-10입니다.
실수 손실식·전도도/투자율/반지름 차원 스케일은 1e-12, 면적비 0의 매끈한 표면 일치,
저·고주파 극한, 극단 유한 입력, strict JSON·입력 격리·메시 전 거부도 확인합니다.

기하 기준은 동축의 정확한 표면계수 `(1/a+1/b)/(2*pi)`입니다.
a=.5 mm, b=2 mm, 방사 셀 64/128/256, 각방향 256에서 거친 R·내부 L 오차가
감소하고 최종 1% 미만이어야 합니다. 결합 마이크로스트립은 edge/far/grade
5 µm/.2 mm/.1에서 2.5 µm/.1 mm/.05로 세분하며 R·내부 L 변화 5% 미만,
적분 전류 오차 5% 미만이 기준입니다. JSON 재실행 RLGC 상대 1e-12/S 절대 1e-10,
개별 표면 API 일치·S 상호성·수동성은 1e-10입니다.
버전 2 smooth/Hammerstad는 버전 1과 정확히 같은 결과를 내야 합니다.

2026-10-30 Linux, Python 3.12.14·NumPy 2.5.4·SciPy 1.18.1에서 신규 55개와
이를 포함한 관련 검사 총 250개가 skip 없이 통과했습니다. 실행 예제의 1/4/10 GHz
저항비는 1.26314496/1.57338324/1.85601051, 표면 전류 오차는 0.03224846입니다.
이는 지정한 예시 입력의 결과이며 실측 동박 피팅이 아닙니다.

이는 정식화와 표면 전류 조립의 검증이며 실측 동박·쿠폰이나 상용 장해석기와의 일치를
뜻하지 않습니다. 기존 BSD-3-Clause SciPy 적분기가 독립 수치 기준이며 새 의존성·바이너리는 없습니다.

양도체·유한 두께·표피 깊이·전류 잔차 기준은 그대로 유지합니다. 통과해도 거칠기 크기가
도체 치수·곡률·간격보다 충분히 작다는 보장은 없으며, 균질 표면 모델과 섭동 가정의
적합성을 확인해야 합니다. 위 저주파 극한은 수학적 검사이며 **표면 API의 DC 사용 허용이 아닙니다**.
유한 금속 확산은 별도의 매끈한 금속 모델로서 거칠기 승수를 적용하지 않습니다.
면별 상이한 거칠기·임의 기본 면적비·재료 추정·3D 실제 요철·시간영역 전파·실측 정확도는
이 계약의 범위 밖입니다. 도체 법칙의 인과성만으로 임의 유전체나 전체 선로의 인과성이 보장되지 않습니다.

```sh
OPENPHYSICS_REQUIRE_CROSSCHECK=1 python -m pytest -q tests/sipi/test_roughness.py tests/sipi/test_conductor.py tests/sipi/test_line_model.py
```
