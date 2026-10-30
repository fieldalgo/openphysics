# 균일 전송선 네트워크

[English](../../../../../packages/sipi/network.md) | **한국어**

[고주파 도체 표면 손실](conductor.md)은 별도 추출 API이며 외부·내부 L을 합쳐 네트워크에 전달합니다.

[단면 개요](overview.md) · [검증](network_validation.md)

`rlgc_network`는 주어진 단위길이 RLGC를 균일 전송선의 주파수별 S 행렬로 변환합니다.
`quasistatic_network`는 기존 단면 추출 결과를 연결합니다. 도체 손실, 거칠기, 표피 효과,
내부 인덕턴스, 주파수 의존 유전체 모델을 추출하는 API는 아닙니다.

```python
import numpy as np
from sipi import stripline, quasistatic_network

parameters = stripline(width=0.5e-3, plane_spacing=1e-3,
                      eps_r=4, tan_delta=0.02).analyze()
network = quasistatic_network(parameters, [1e6, 1e8, 1e9],
                             length=0.1, R=np.zeros((1, 1)), z_ref=50)
# R=0 explicitly selects perfect conductors; dielectric loss remains present.
s21 = network.s[:, 1, 0]
insertion_loss_db = -20*np.log10(np.abs(s21))
text = network.touchstone()  # save this text as line.s2p; no implicit file writes
```

## 입력과 결과 계약

- 주파수: 비어 있지 않고 엄격히 증가하는 1차원 Hz 배열, 0 이상. DC에서는 입력한 R/G를
  사용합니다. 상수 손실탄젠트의 G는 DC에서 0이며, DC 누설이나 광대역 인과성을 모델링하지 않습니다.
- R/L/G/C: 실수 대칭 `(N,N)` 상수 또는 `(F,N,N)` 표본. 단위는 Ω/m, H/m, S/m, F/m입니다.
  단일선도 스칼라 대신 행렬을 입력합니다. L/C는 양의 정부호, R/G는 양의 준정부호여야 합니다.
  대칭성과 준정부호 판정에 최대 절대 원소의 1e-12만큼 반올림 차이를 허용합니다.
  작은 비대칭은 평균하지만 고윳값을 잘라내지 않습니다. 부정부호·복소·비유한 수·불리언은 거부합니다.
- `length`: 유한한 0 이상 m. `z_ref`: 모든 입력 포트에 공통인 유한한 양의 실수 Ω.
  복소수 또는 주파수별 기준 임피던스는 지원하지 않습니다.
- 선택적 `names`: 도체마다 고유한 한 줄 이름.
- `LineNetwork.frequency`, `.s`, `.z_ref`는 복사한 읽기 전용 배열입니다. S의 크기는
  `(F,2N,2N)`, 포트 순서는 `.port_names`입니다. 직접 구성한 `LineNetwork`는 크기와 유한성을
  검사하며 수동성·인과성을 보증하지 않습니다.
- `quasistatic_network(parameters, frequency, length=..., R=..., z_ref=50)`는
  C/L을 재사용하고 G(f)=2*pi*f*C_loss를 계산합니다. R은 필수이며 0 행렬은 완전도체라는
  명시적 가정입니다. 추출한 저항으로 표시하면 안 됩니다.

시간 규약은 exp(+j*omega*t)입니다. 포트 순서는 `near:1 ... near:N`, `far:1 ... far:N`이며
양쪽 모두 포트 전류가 네트워크 안쪽을 향합니다. `S[i,j]`는 j에 입사할 때 i의 출사파입니다.
정합 무손실 선로의 S21은 exp(-j*beta*length)로 위상이 감소합니다. 길이 0은 반사나 순서 변경 없이
각 near 포트를 같은 도체의 far 포트에 연결합니다.

## 계산

진행 방향 도체 전류 I에 대해 `dV/dz = -(R+j*omega*L) I`, `dI/dz = -(G+j*omega*C) V`입니다.
V를 sqrt(Zref)로 나누고 I에 sqrt(Zref)를 곱해 정규화합니다. 짧은 구간의 행렬 지수를 S로
변환한 뒤 산란 연결로 길이를 반복해서 두 배로 늘립니다. 큰 감쇠에서 쌍곡함수 전달행렬 원소가
넘치는 문제를 피하며, 모드 대칭이나 행렬의 동시 대각화를 가정하지 않습니다.

길이를 곱한 정규화 생성행렬의 norm은 유한하고 2^50 이하여야 하며 아니면 `ValueError`입니다.
이는 overflow 방어로 그 한계 부근의 정확도 보증이 아닙니다. 매우 나쁜 조건수와 긴 전기 길이는
독립 오차 평가가 필요합니다. 이 균일 선로 전파 단계는 공간 메시를 쓰지 않습니다.
단면 메시·영역 절단·재료 모델·준TEM 유효성 오차는 별도입니다.

## 차동·공통 모드

**두 도체**에서 `.mixed_mode()`는 near+/near-/far+/far-를
`d_near, d_far, c_near, c_far`로 바꿉니다. 같은 기준 임피던스의 single-ended 포트 4개가 필요합니다.
차동 전압 V+ - V-, 차동 전류 (I+ - I-)/2, 공통 전압 (V+ + V-)/2, 공통 전류 I+ + I-입니다.
기준 임피던스는 `2*Zref, 2*Zref, Zref/2, Zref/2`입니다. 전력파의 직교 변환이므로 전력을 보존합니다.
서로 다른 기준 임피던스는 거부하며, 도체 쌍의 형상 대칭은 가정하지 않습니다.

## Touchstone 출력

`.touchstone()`은 포트·주파수 수와 포트별 실수 기준 임피던스를 명시한 Touchstone **2.0**
텍스트(Hz, S, 실수/허수, 전체 행렬)를 반환합니다. 2포트는 S11,S21,S12,S22 (`21_12`),
N>=3은 행 우선 순서입니다. 포트 수 N에 맞게 `.sNp`로 저장합니다. 이름은 ASCII 안전 주석입니다.
독립 읽기 시험에 비상호 데이터를 넣어 전치 오류를 검출합니다.

single-ended 내보내기만 지원합니다. mixed-mode 파일 출력,
시간영역 변환, 일반 회로 해석기는 미구현입니다. 이 Python API가 웹 화면을 추가하거나 기존
단면 JSON 스키마를 변경하지는 않습니다.

층별 주파수 분산 추출은 [유전체 모델](dielectrics.md)을 사용합니다.

[Touchstone 입력·조건을 명시한 측정 비교](touchstone.md)는 별도 API로 지원합니다.
