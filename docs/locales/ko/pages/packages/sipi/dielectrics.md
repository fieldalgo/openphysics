# 주파수 의존 유전체 추출

[English](../../../../../packages/sipi/dielectrics.md) | **한국어**

[단면](overview.md) · [균일 전송선 네트워크](network.md)

`sipi.dielectric`은 요청한 각 주파수에서 재료를 평가하고, 같은 메시 위에서
층별 복소 정전문제를 다시 풉니다. 주파수별 정전용량과 유전체 컨덕턴스를
계산하며, 이질 단면을 하나의 유효 유전율로 대체하지 않습니다.

```python
import json
import numpy as np
from sipi import microstrip
from sipi.dielectric import WidebandDielectric, dispersive_line, dielectric_to_dict

section = microstrip(width=.5e-3, substrate_height=1e-3, eps_r=4)
material = WidebandDielectric(eps_ref=4, tan_delta_ref=.02, reference_hz=1e9)
sweep = dispersive_line(section, [1e6, 1e8, 1e9, 1e10],
                        materials={'substrate': material})
network = sweep.network(length=.1, R=np.zeros((1, 1)), z_ref=50)
material_json = json.dumps(dielectric_to_dict(material), allow_nan=False)
```

R=0은 완전도체를 명시적으로 가정합니다. 직접 비교에는 동일한 확정 메시를
사용하고, 대상 주파수 범위의 메시 세분과 상자 절단 오차를 따로 확인합니다.
[실행 예제](../../../../../../examples/sipi/dispersive_line.py)는 재료값·C·G·전달을 출력합니다.

## 재료 계약

시간 규약은 exp(+jωt), 상대 유전율은 εr=ε′−jε″입니다. 주파수는 Hz이며
유전율과 완화 강도는 무차원입니다. bool·복소 입력·비유한 값·잘못된 부호를
거부합니다. `permittivity`는 비음수 실수 스칼라 또는 비어 있지 않은 1차원
주파수 배열을 받습니다. 재료 평가 배열은 정렬이 필요 없지만 단면 추출은
엄격히 증가해야 합니다. 이 모델들의 실수 상대 유전율은 1 이상입니다.

| 모델 | 입력과 동작 |
|---|---|
| `ConstantDielectric(eps_r, tan_delta=0)` | εr=eps_r(1−j tan_delta). 기존 상수 손실탄젠트 계약을 보존합니다. 비영 상수 tanδ에 광대역 인과성을 주장하지 않습니다. |
| `DebyeDielectric(eps_inf, strengths, relaxation_hz)` | εr=eps_inf+Σ strength_k/(1+j f/f_k). 비어 있지 않은 동일 길이 배열, strength>=0, f_k>0, eps_inf>=1. DC는 eps_inf+Σstrength, 무한주파수 극한은 eps_inf입니다. |
| `WidebandDielectric(eps_ref, tan_delta_ref, reference_hz, low_hz=1e3, high_hz=1e12)` | 유한 완화 대역의 로그 모델. 기준점에서 ε′·tanδ를 재현합니다. low<high, low<=reference<=high이며 교정 결과 eps_inf>=1이어야 합니다. 손실 0이면 상수 유전체입니다. |
| `TabulatedDielectric(frequency, eps_r, tan_delta)` | 최소 두 개의 양수·증가 주파수와 동일 길이 값 배열. log(f)에 대해 ε′와 ε″=eps_r·tan_delta를 각각 선형 보간하고 끝점을 포함합니다. 외삽·DC 평가는 거부합니다. 표본 수동성이 인과성을 보장하지 않습니다. |

광대역 모델은 `D(f)=log((high+j*f)/(low+j*f))`,
`strength=eps_ref*tan_delta_ref/(-Im D(reference))`,
`eps_inf=eps_ref-strength*Re D(reference)`,
`εr(f)=eps_inf+strength*D(f)`입니다. 비음수 Debye 완화 강도의 연속 분포이며,
완화 대역 경계는 점근 거동을 결정할 뿐 **실측 재료의 유효 대역이 아닙니다**.
공통 주파수 정규화와 로그 크기 평가로 불필요한 overflow를 피합니다.
극단적인 유한 입력의 수치 안정성은 해당 주파수에서의 물리적 유효성 주장이
아닙니다. DC 전도도·자성 분산은 포함하지 않습니다.

## 엄격한 재료 JSON

`dielectric_to_dict(model)`과 `dielectric_from_dict(value)`는 정확히 다음 구조를 씁니다.

```json
{
  "schema": "sipi.dielectric/1",
  "kind": "wideband",
  "parameters": {
    "eps_ref": 4.0,
    "tan_delta_ref": 0.02,
    "reference_hz": 1000000000.0,
    "low_hz": 1000.0,
    "high_hz": 1000000000000.0
  }
}
```

kind는 `constant`, `debye`, `wideband`, `table`입니다. parameters에는 기본값을
포함한 생성자의 모든 필드를 넣으며 추가 필드는 허용하지 않습니다. 배열은 JSON
배열입니다. 알 수 없는 버전·kind·키와 누락 필드를 거부합니다. 이 계약은 재료
입력이며 기존 `sipi.cross-section/1`, `/2`의 확장이 아닙니다. 호출자가 형상과
층 이름별 재료 문서를 함께 저장해야 하며, 브라우저 UI는 아직 새 재료 스키마를
불러오지 않습니다.

## 단면 추출과 네트워크

`dispersive_line(section, frequency, materials=..., **mesh_options)`의 materials는
기존 층 이름과 위 모델의 매핑입니다. 지정하지 않은 층은 기존 상수 eps_r·tan_delta를
유지합니다. 알 수 없는 층·미지원 모델·잘못된 주파수·표 범위 이탈은 메시 생성 전에
거부합니다. 메시와 진공 C0는 각각 한 번 만들고, 매 주파수에 실제 요소별 복소
유전율을 넣어 다시 풀므로 이질 재료의 전기장 재분포와 유전체 손실을 반영합니다.

`DielectricSweep`은 복사한 읽기 전용 frequency, 신호 names, `(F,N,N)`형
C_complex, `(N,N)`형 C0와 외부 `L=mu0*eps0*inv(C0)`, 읽기 전용 매핑의 실제
layer_permittivity 표본을 기록합니다. C는 실수부(F/m),
`G=-2*pi*f*Im(C_complex)`는 S/m입니다. `network(length=..., R=..., z_ref=50)`는
기존 전체 RLGC 행렬 해석기에 연결됩니다. R은 필수이며, 비대칭 쌍을 대칭 평균하거나
진공 L에 재료 유전율을 곱하지 않습니다.

이 해석은 준TEM 근사이며 전파장 분산 해석기가 아닙니다. 도체 저항·표피/근접
효과·구리 거칠기·도체 내부 인덕턴스·복사를 추출하지 않습니다. 인과적인 재료식만으로
유한 표본 네트워크의 시간영역 인과성이나 실제 적층재 특성을 인증하지 않습니다.
재료 피팅과 실측 검증은 별도입니다. mixed-mode·Touchstone은
[네트워크 계약](network.md)을 따릅니다.

## 검증과 재현

```sh
python -m pytest -q -s tests/sipi/test_dielectric.py
```

- 단일/다중 Debye 해석값·DC/고주파 극한·광대역 기준점·표 끝점/보간·입력/스키마
  거부 기준: 1e-12.
- 기존 상수 C/L/G 재현과 균일 재료 `C_complex=εr(f)*C0`: 상대 1e-10.
  균일 복소TEM의 독립 스칼라 ABCD, 상호성·수동성: 절대 1e-10.
- scikit-rf 2.2.0의 `MLine.analyse_dielectric`와 복소 유전율 비교: 상대 1e-12,
  DC와 1 Hz~1 PHz 표본에서 관측 최대 1.82e-16. 수식 비교이며 이 범위 전체에
  PCB 준TEM의 물리적 유효성을 주장하지 않습니다.
- scikit-fem 12.0.2의 독립 복소 P1 조립/풀이: 동일 메시의 층별 비대칭 두 도체,
  1 MHz·100 MHz·10 GHz에서 복소 C 상대 기준 1e-9, 관측 최대 5.75e-15.
  동일 메시 일치와 이산화 수렴은 다릅니다.
- 유한 두께·이질 결합 microstrip, 1 MHz·1 GHz·100 GHz에서 edge/far/grade를
  절반으로 했을 때 복소 C 변화 0.498%, 사전 기준 1% 이내. 메시 민감도 검사이며
  전파장 정확도·유한 상자 크기 수렴의 증거는 아닙니다.

기준 도구는 시험 전용이며 제품이 import하거나 번들하지 않습니다.
`openphysics.crosscheck/1` 기록은 `OPENPHYSICS_CROSSCHECK_DIR`로 저장할 수
있습니다. 기존 기준·골든은 바꾸지 않았습니다. 추가 극한 시험에서 hypot overflow를
발견했고 제곱 전 정규화·로그 크기 분해로 동일 기준을 통과했습니다. Windows/macOS와
설치 휠 지원은 해당 정확 버전의 필수 CI를 통과해야 확정됩니다.

출처: C. Svensson, G. E. Dermer, *Time domain modeling of lossy interconnects*,
IEEE Transactions on Advanced Packaging 24(2), 191–196 (2001);
A. R. Djordjevic 외, *Wideband frequency-domain characterization of FR-4 and
time-domain causality*, IEEE Transactions on EMC 43(4), 662–667 (2001).
독립 수식은 [scikit-rf MLine 구현](https://github.com/scikit-rf/scikit-rf/blob/v2.2.0/skrf/media/mline.py)에도 나옵니다.
