# Touchstone 입력과 명시적 조건의 네트워크 비교

[English](../../../../../packages/sipi/touchstone.md) | **한국어**

[균일 선로 네트워크](network.md) · [주파수 선로 입력](line_model.md)

`sipi.touchstone.loads_touchstone(text, ports=None, port_names=None)`는 지원하는
single-ended S-파라미터 파일을 기존 불변 `LineNetwork`로 읽습니다. 파일·네트워크
I/O는 없으며 앱이나 브라우저가 텍스트를 전달합니다. 파일명·주석에서 물리적 포트
짝을 추측하지 않습니다. 형식 기준은 [IBIS Touchstone 2.0 규격](https://ibis.org/touchstone_ver2.0/touchstone_ver2_0.pdf)이며 아래 부분집합을 독립 구현했습니다.

```python
from pathlib import Path
from sipi.touchstone import loads_touchstone, compare_networks

# model is a calculated LineNetwork with a known physical port order.
measured = loads_touchstone(Path("coupon.s2p").read_text(encoding="ascii"),
                            ports=2, port_names=model.port_names)
comparison = compare_networks(measured, model)
print(comparison.max_abs_error)  # maximum absolute complex-S difference
```

실제 파일도 지정한 포트 순서를 따라야 합니다. 이름을 붙이는 것은 fixture 배선을
바꾸거나 de-embedding하는 일이 아닙니다. 실행 가능한 [합성 예제](../../../../../../examples/sipi/compare_networks.py)는 외부 측정 파일이 필요 없으며 실측 재료 정확도를 주장하지 않습니다.

## 지원 입력

| 입력 | 동작 |
|---|---|
| 버전 1.0 | 호출자가 양의 정수 `ports`를 지정해야 합니다. 파일명으로 추정하지 않습니다. 1/2포트는 한 행에 한 주파수의 완전한 기록, 더 큰 행렬은 여러 행을 사용할 수 있습니다. |
| 버전 2.0 | 버전·옵션·포트 수·주파수 수·network data·end 표식 필수. 호출자가 포트 수를 주면 일치해야 합니다. 기준 저항은 여러 행에 걸칠 수 있습니다. |
| 네트워크 샘플 | S만 지원. RI, 크기/도 단위 위상, dB/도 단위 위상. Hz/kHz/MHz/GHz. 옵션 기본값은 규격을 따르며 명시한 옵션 종류는 순서가 자유롭습니다. |
| 포트 순서 | 1.0의 2포트는 21_12, 2.0은 21_12 또는 12_21을 명시해야 합니다. 더 큰 full 행렬은 행 우선입니다. |
| 행렬 형태 | Full 또는 2.0 lower/upper 삼각형. 삼각형은 켤레가 아닌 전치로 반사합니다. |
| 기준 임피던스 | 주파수에 무관한 양의 실수 저항. 옵션의 공통 값 또는 2.0의 포트별 값. 암묵적 재정규화 없음. |
| 텍스트 | ASCII, 빈 행과 `!` 주석. 2.0 information 블록은 실행·포트 해석하지 않는 불투명한 텍스트입니다. |
| 이름 | 호출자가 파일 순서대로 고유 이름을 지정하거나 중립적인 `port1`, `port2` 등을 사용합니다. |

결과 주파수는 음이 아닌 유한한 엄격한 증가 배열이며 DC를 허용합니다. 복소 S는
유한해야 합니다. 배열은 복사 후 읽기 전용입니다. 능동·비상호·비인과 네트워크도
파일에 있을 수 있으므로 읽기 성공은 **수동성이나 측정 인증이 아닙니다**.

없는·중복 키워드, 미지원 버전, 잘못된 개수, 행렬 값 누락, 비유한 수, 음의
크기 표현 값·기준 저항, end 이후 내용은 거부합니다. 일반 규격에서 무시할 수 있는
추가 옵션 행도 이 API는 거부합니다. mixed-mode metadata, noise, Y/Z/H/G는
지원하지 않으며 single-ended S로 조용히 해석하지 않습니다. 엄격한 부분집합이며
모든 Touchstone의 범용 importer가 아닙니다. 기존 single-ended Touchstone 2.0
출력은 이름을 명시하면 왕복할 수 있습니다.

## 비교 계약

`compare_networks(measured, model, interpolation='none')`는 두 `LineNetwork`를
받습니다. 포트 이름·순서·basis·기준 임피던스가 정확히 일치해야 합니다. 포트 순열,
교정, 임피던스 재정규화는 호출자가 먼저 해결해야 합니다. `NetworkComparison`에는
주파수가 맞춰진 `measured`, 원래 `model`, 선택한 `interpolation`, 읽기 전용
`delta_s = model.s - measured.s`, 모든 주파수·행렬 원소에 대한 스칼라
`max_abs_error`가 있습니다. factory가 조건을 검증하며 dataclass 직접 생성은 인증이 아닙니다.

기본은 모델의 각 주파수가 측정 grid에 정확히 존재해야 합니다. 측정 샘플의 부분집합은
허용하지만 없는 주파수는 오류입니다. `interpolation='linear'`를 명시하면 측정 범위
**안에서만** Hz 주파수에 대해 S의 실수부·허수부를 선형 보간합니다. 외삽은 없습니다.
물리 모델 fit이나 충분한 샘플링을 보장하지 않으므로 급격한 위상 변화·공진 주변에서는
측정 grid를 세분해야 합니다. 크기·위상 보간이 아닙니다.

잔차는 위상 차이를 포함하므로 크기가 같아도 다를 수 있습니다. 작은 잔차만으로
재료 추정, de-embedding, fixture 제거, 손실 분리, 정확도가 입증되지 않습니다.
별도의 측정과 모델 가정 검증이 필요하며 비교는 두 원본을 바꾸지 않습니다.

## 검증

필수 시험은 `tests/sipi/test_touchstone.py`입니다. 비상호 합성 행렬로 2포트
전치 실수를 드러냅니다. 1/2/3/4포트·두 버전·단위/형식·두 포트 순서·삼각형 대칭·
명시 기준 저항·엄격한 거부·자체 export 왕복을 검사합니다. 형식/참조 기준은 S 절대차
<=1e-12, 주파수 정확 일치, 기준 저항 일치이며 자체 export 왕복은 <=1e-14입니다.

Python 3.12.14, NumPy 2.5.4, SciPy 1.18.1에서 독립 scikit-rf 2.2.0 리더와
버전/형식/행렬 다섯 조합의 S 최대차는 **1.24e-16**으로 1e-12 기준을 통과했습니다.
참조 도구는 BSD-3-Clause 시험 전용이며 배포 코드에서 import하지 않습니다.
새 런타임 의존성은 없습니다. 비교 시험은 grid 부분집합·복소 위상 잔차·해석적인
선형 복소 샘플·이름/basis/reference 불일치·외삽 거부·계산 선로의 출력/입력을 포함합니다.
파일 형식과 수치 비교 시험이며 실측 쿠폰 검증은 아닙니다.
