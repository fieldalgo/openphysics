# 종단 네트워크와 주파수 누화

[English](../../../../../packages/sipi/termination.md) | **한국어**

[개요](overview.md) · [선로 네트워크](network.md)

`sipi.termination`의 `terminate_network`는 `LineNetwork`에 이름으로 명시한
Thevenin 소스와 유한 수동 소스/부하 임피던스를 연결해 단자 전압·전류를 풉니다.
`loaded_crosstalk`는 같은 해로 주파수별 NEXT/FEXT를 계산합니다.
Python API이며 UI·JSON 연결을 뜻하지 않습니다.

```python
from sipi import rlgc_network
from sipi.termination import terminate_network

network = rlgc_network([0, 1e6, 1e9], R=[[10]], L=[[400e-9]],
                       G=[[0]], C=[[100e-12]], length=1)
response = terminate_network(network, source_voltages={'near:1': 1},
                             terminations={'near:1': 50, 'far:1': 100})
```

DC에서는 선로 10 Ω, 소스 50 Ω, 부하 100 Ω의 직렬 회로입니다.
`voltage[0]=[110/160, 100/160]` V, `current[0]=[1/160, -1/160]` A입니다.
양 끝 전류 모두 네트워크로 들어가는 방향입니다.

## 입력·출력 계약

- 유한 S와 양의 실수·주파수 불변 기준 임피던스를 가진 네트워크를 받습니다.
  single-ended와 mixed-mode 모두 가능하나 종단은 입력 basis에서 독립입니다.
  모드 종단이 물리 단자 부하로 자동 변환되지는 않습니다.
- `source_voltages`: 비어 있지 않은 포트 이름→유한 복소 스칼라 또는 길이 F 배열,
  단위 V. 다중 소스를 지원하며 미지정 소스는 0입니다. 영 입력도 유효합니다.
- `terminations`: 포트 이름→유한 복소 스칼라 또는 길이 F 배열, 단위 Ω.
  실수부 >=0이며 미지정 포트는 소스 포트까지 각자의 `z_ref`를 사용합니다.
  0은 단락/이상적 전압원입니다. 무한대·개방, 음의 저항, 결합 부하 행렬은 미지원입니다.
- bool·문자열 수치, 미등록 이름, 잘못된 배열 모양·비유한 입력은 거부합니다.
  주파수와 순서는 네트워크에서 가져옵니다.
- 입력·네트워크는 복사한 읽기 전용 스냅샷입니다. `a`, `b`, `voltage`, `current`,
  `source_voltages`, `terminations`는 `(F, ports)`, `condition_number`,
  `kvl_residual`, `wave_residual`은 `(F,)`입니다.
  `frequency`, `port_names`, `basis`로 계산한 네트워크를 식별합니다.
- exp(+j omega t), peak phasor이며 전류는 네트워크 안쪽 방향입니다.
  DC의 복소 값은 상수 진폭이며 물리적인 DC 입력에는 실수를 사용합니다.
  평균 전력은 DC에서 Re(V I*), 양의 주파수에서 Re(V I*)/2입니다.
  DC 저항 손실을 절반으로 줄이지 않습니다.
- `network_power`, `termination_power`, `source_power`는 읽기 전용 `(F,)` W입니다.
  소스 전력=네트워크 유입 전력+모든 소스/부하 임피던스 손실입니다.
  무효 전력은 반환하지 않습니다. 외부 S가 능동이면 네트워크 전력이 음수일 수
  있으며 이를 자르거나 수동성 증거로 삼지 않습니다. 전력 overflow는 해당
  property에 접근할 때 `ValueError`로 거부합니다.

## 방정식과 실패 검사

실수 기준 R에서 b=S a, V=sqrt(R)(a+b), I=(a-b)/sqrt(R), Vs=V+Zt I입니다.
따라서 다음 회로를 주파수별로 풉니다.

```text
Gamma = (Zt-R)/(Zt+R)
a_source = sqrt(R) Vs/(Zt+R)
(I - diag(Gamma) S) a = a_source
```

2-norm 조건수는 <=1e12여야 합니다. 특이·과도한 조건수·비유한 회로는
`ValueError`이며 부분 결과를 반환하지 않습니다. Vs-V-Zt I 및
 a-Gamma b-a_source 잔차를 각 항의 infinity norm 중 최댓값으로 정규화해
<=1e-10을 요구합니다. 영 입력의 잔차는 0입니다. 작은 잔차는 backward error
검사이며 한계에 가까운 조건수의 forward 정확도를 보장하지 않습니다.
아주 큰 임피던스는 상쇄 오차로 거부될 수 있으며 개방 회로 API가 아닙니다.

## 명시적인 NEXT/FEXT

`loaded_crosstalk(network, aggressor=..., near_victim=..., far_victim=...,
terminations=...)`의 세 포트 이름은 서로 달라야 합니다. 위치·형상을 추론하지
않으므로 물리적 의미는 호출자가 지정합니다. aggressor 한 포트만 1 V peak
Thevenin 소스로 구동하며 전체 해는 `Crosstalk.response`입니다.

`next_ratio`, `fext_ratio`는 피해 단자 전압 / 실제 aggressor 입사 전압
`sqrt(R_aggressor)*a_aggressor`입니다. 무차원 복소 읽기 전용 F 배열이며
소스 개방 전압이나 aggressor 총전압으로 나누지 않습니다.
입사 전압 크기 <=1e-14 V는 거부합니다. 모든 포트가 정합이고 기준이 같으면
해당 S 원소와 같습니다. 기준이 다르면 sqrt(R_victim/R_aggressor)가 포함되고,
부정합이면 모든 반사가 반영됩니다. 진폭 dB는 `20*log10(abs(ratio))`이며
0에서 -infinity입니다. 시간영역 peak·상승시간별 누화·eye diagram이 아닙니다.

## 검증과 재현

```sh
OPENPHYSICS_REQUIRE_CROSSCHECK=1 python -m pytest -q tests/sipi/test_termination.py
python examples/sipi/loaded_crosstalk.py
```

| 검사 | 독립 기준 | 기준값 |
|---|---|---|
| DC V/I·손실 전력 | 10 Ω 선로, 50 Ω 소스, 100 Ω 부하 해석해 | 상대 1e-10 |
| 복소 소스/부하, 1 kHz–5 GHz | scalar hyperbolic ABCD | 상대 1e-10, 절대 floor 1e-14 V / 1e-16 A |
| 정합 결합선 NEXT/FEXT | 독립 짝/홀 scalar ABCD 모드 | 절대 1e-10 |
| 비상호 2/4포트·불균등 기준·다중 소스 | scikit-rf 2.2.0 s2z 후 독립 임피던스 회로 | V/I 상대 infinity-norm <=1e-10 |
| 전력·잔차 | 소스=네트워크+종단 손실, 회로 보존 | 상대 1e-10 |

참조 도구는 BSD-3-Clause로 시험에서만 지연 import하며 새 runtime 의존성이
아닙니다. 2026-10-30 Linux/Python 3.12.14, NumPy 2.5.4, SciPy 1.18.1에서
합성 2/4포트 V/I 상대 차이 최댓값은 4.23e-16이었습니다.
회로 산술 검증이며 재료 추출 정확도·실측 일치·유효 대역·공간 이산화 검증이
아닙니다. 입력 네트워크의 메시/외곽/재료 한계를 유지합니다. 개방·결합 종단,
시간영역 변환, 비선형 드라이버·via는 미구현입니다.
[실행 가능한 결합선 예제](../../../../../../examples/sipi/loaded_crosstalk.py)를 참고하세요.
