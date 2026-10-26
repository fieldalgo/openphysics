# 도파로 모드와 손실 해석

[English](../../../../results/waveguide-modes.md) | **한국어**

[문서 홈](../index.md)

이 가이드는 `em.modes2d` 도파로 결과를 다룹니다. 공동의 복소 주파수와 Q는 별도의
[공동 계약](../packages/simcase/cavity3d.md)을 사용합니다. 반환된 고유쌍은 수치적
후보입니다. 관심 있는 물리 모드로 판단하기 전에 장 분포·수렴·선택 설정을 확인하세요.

## 유효굴절률과 감쇠

도파로 장의 규약은 `exp(+iωt − iβz)`이며 `β = 2π n_eff / λ₀`입니다.
따라서 순방향 수동 감쇠에서는 `Im(n_eff) < 0`입니다. JSON 재료 소광계수 `k`와
`physmat`은 흡수에 양의 `k`를 쓰는 `n + ik` 규약입니다. 문서 runner가 solver
경계에서 변환하므로 JSON 입력을 직접 켤레 변환하지 마세요. 저수준 유전율 직접
호출은 solver 규약을 사용합니다. [흡수 모드](../packages/simcase/lossy_modes.md)를
참고하세요.

simcase 설치 후 작은 흡수 슬래브를 실행합니다.

```python
import copy
import numpy as np
from simcase import Document, examples, run

data = copy.deepcopy(examples.VECTOR_SLAB)
data["materials"]["film"] = {"n": 3.48, "k": 0.01}
data["study"] = {"type": "single"}
result = run(Document.from_dict(data), verbose=False)
neff = np.asarray(result.neff)
loss_db_cm = result.propagation_loss_db_cm()
print(neff)
print(loss_db_cm)

wavelength_m = 1.55e-6
beta_per_m = 2 * np.pi * neff / wavelength_m
power_decay_per_m = -2 * beta_per_m.imag
expected_db_cm = 10 * power_decay_per_m / (100 * np.log(10))
np.testing.assert_allclose(loss_db_cm, expected_db_cm)
```

전파 거리 `z`의 단위가 m일 때 장 진폭은 `exp(−a z)`로 감소하며 `a = −Im(β)`입니다.
전력은 `exp(−2a z)`로 감소합니다. 위 변환은 전력 감쇠계수를 사용하며 단위는 dB/m가
아닌 **dB/cm**입니다. 슬래브의 반환 굴절률은 유한 창과 메시에 의존합니다. 위 검사는
단위·부호 변환을 확인하며 고유값 solver의 독립적인 정확도 검증은 아닙니다.

## 장에 임의의 전력 척도 부여하지 않기

스칼라 모드는 계수의 최댓값, 벡터 모드는 삼각형 중심 전기장 크기의 최댓값으로
정규화합니다. 상대적인 장이며 보정된 V/m나 1 W 모드가 아닙니다. 전체 복소 위상은
임의적입니다. 위상을 고려해 장 패턴을 비교하고, 독립적으로 정규화한 모드 그림의
같은 색을 같은 광학 전력으로 해석하지 마세요.

저수준 벡터 종방향 좌표에는 문서에 정의된 `Ez = i*ez` 변환이 필요합니다. 상위 API의
물리 전기장 배열은 이미 해당 장 표현을 따릅니다. 계수를 변환하기 전에
[모드 좌표](../packages/galerkin/modal_coordinates.md)를 확인하세요. 저장 PNG sweep 곡선은 유효굴절률과 군굴절률의 실수부를
표시하고 JSON/NPZ는 복소 정보를 보존합니다. 버전 2 summary의 `neff`와 `neff_imag`는
별도 배열이므로 `neff`만 읽으면 흡수 정보가 빠집니다. NPZ의 `neff`는 복소 배열입니다.

## 실행 간 같은 모드 찾기

명시적 target이 없을 때 적용되는 유전체 후보 필터와 실수 굴절률 내림차순 정렬은
구속성이나 완전성을 입증하지 않습니다. 스칼라 TE 슬래브 해는 유용한 대조군이지만,
스칼라 근사는 일반적인 고굴절률 대비 2D 벡터 도파로를 표현하지 못합니다. 유전율
실수부가 양수가 아닌 문제에는 문서에 정의된 명시적 target과 적절한 정식화가 필요합니다.

Sweep에서는 지원되는 추적 메타데이터를 사용해 overlap·배정 margin·스펙트럼 분리를
확인합니다. 후보의 배열 인덱스가 보편적인 모드 가지 식별자는 아닙니다. 흡수 sweep의
양의 켤레 L2 overlap은 전력 직교성이 아닙니다. 복소 `n_g = n_eff − λ d(n_eff)/dλ`는
스펙트럼 미분이며 자동으로 에너지 속도나 신호 속도가 되지 않습니다. 메시와 함께
파장 간격도 줄여 확인하세요. [추적](../packages/simcase/lossy_modes.md)과
[벡터 부분공간 추적 제한](../packages/simcase/vector_subspace_tracking.md)을 참고하세요.

## PML 손실의 수렴 확인하기

PML·일정 반경 결과에는 한 번의 실행으로 안정성이 확인되지 않은 `not_checked` 후보가
포함됩니다. 같은 물리 모드 가지를 따라 메시·물리 창·PML 두께·스트레칭 설정을 각각
변화시키세요. PML 영역의 장에는 인공 좌표가 적용되므로 물리 창 안의 물리 장을
해석합니다. 진단용 PML overlap은 저장된 물리 에너지가 아닙니다.

흡수와 방사가 함께 있으면 보고되는 전파 손실은 총손실입니다. 서로 다른 실행의
결과를 빼도 두 메커니즘이 유일하게 분리되지는 않습니다.
[PML 계약](../packages/simcase/pml_modes.md)은 물리 창·target 요구사항·굽힘 손실 변환을
정의합니다. 설정을 [저장 결과](saved-results.md)와 함께 보관하고 보고할 물리량의
[수렴 근거](../validation/convergence.md)를 기록하세요.
