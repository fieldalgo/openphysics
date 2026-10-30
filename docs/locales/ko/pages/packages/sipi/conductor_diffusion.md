# DC·AC 도체 내부 전류 확산

[English](../../../../../packages/sipi/conductor_diffusion.md) | **한국어**

[단면](overview.md) · [균일 선로 네트워크](network.md)

`sipi.conductor_diffusion.conductor_impedance`는 유한한 금속 내부의 종방향
전류와 주변 자기장을 풀어 직렬 임피던스 Z, 저항 R, 금속 내부를 포함하는
**전체** 인덕턴스 L을 추출합니다. DC와 메시로 해상한 표피·근접 효과의
전류 재분포를 지원하며 고주파 표면 저항을 DC로 외삽하지 않습니다.

## 금속 부피 메시 구성

```python
from sipi import microstrip
from sipi.conductor_mesh import mesh_conductor_section

section = microstrip(width=.4e-3, substrate_height=.5e-3, thickness=.1e-3,
                     eps_r=4, air_height=.5e-3, box_width=2e-3)
volume = mesh_conductor_section(section, ground_thickness=.1e-3, padding=2e-3,
                               metal_size=25e-6, far_size=.25e-3, grade=.1)
series = volume.impedance([0, 1e3, 1e5], conductivity=58e6, keep_fields=True)
print(series.R[:, 0, 0])  # ohm/m
print(series.L[:, 0, 0])  # H/m, including internal inductance
```

실행 가능한 [예제](../../../../../../examples/sipi/conductor_diffusion.py)는
해상도와 보존 잔차도 출력합니다. 길이는 m, 주파수는 Hz, 전도도는 S/m입니다.
`relative_permeability=1`은 비전도 영역까지 **전 영역에 균일하게** 적용됩니다.

`mesh_conductor_section`은 두께가 양수인 직사각형 또는 중심 사다리꼴 trace의
`CrossSection`을 받으며 신호 이름과 순서를 보존합니다. 모든 ground trace와
상자 접지를 하나의 공통 귀환 그룹으로 묶습니다.

- 아래·위 접지는 폭 `section.width`의 유한 판으로 바꾸며 유전체 상자 바깥으로
  `ground_thickness`만큼 확장합니다.
- 측면 접지는 같은 두께로 바깥쪽에 놓이며 수평 판과 면적 중복 없이 연결합니다.
- 이 전체 구성에서 사방으로 `padding`만큼 확장한 자기 상자 외곽에서 Az=0입니다.
  비전도 영역과 금속 내부 모두 정합 P1 삼각형으로 채웁니다. 유전율은 사용하지 않습니다.
- `metal_size`, `far_size`, `grade`는 목표 메시 크기이며 실제 변 길이나 정확도
  추정치가 아닙니다. `0 < min_angle < 34`, `far_size >= metal_size > 0`,
  `grade >= 0`, 양의 두께·padding이 필요합니다.

기존 유전체 전용 `CrossSection.mesh()`는 도체를 구멍으로 두므로 금속 부피
메시로 전달할 수 없습니다. 기존 상자 경계와 위의 유한 판은 물리 경계 계약이
다릅니다. 기존 JSON v1/v2는 단면만 저장합니다. **이 API에는 금속 부피 메시
JSON 계약이나 동일 기하의 유전체·도체 자동 통합 추출이 없습니다.**

## 직접 메시 입력과 수식

`conductor_impedance(mesh, frequency, signals=..., ground=...,
conductivity=..., magnetic_boundary=...)`는 galerkin 삼각형 메시를 받습니다.
`signals`는 신호 이름에서 금속 부피의 **삼각형 인덱스**로 가는 매핑이며
`ground`는 또 다른 삼각형 집합입니다. 서로 다른 그룹은 겹치거나 노드에서
접촉할 수 없습니다. 분리된 귀환 도체 조각도 하나의 종방향 전기장 상수를
공유합니다. `magnetic_boundary`는 Az=0인 외곽 **노드 인덱스**입니다.
그 외 외곽 변에는 자연 자기 플럭스 0 조건이 적용됩니다. 경계를 명시적으로
선택하고 계산 영역 확대를 검증해야 합니다.

exp(+jωt), 금속 내 균일한 양의 전도도 σ(밖에서는 0), 전 영역 균일 µ,
P1 기저 φ에 대해 다음 계를 조립합니다.

```text
Kij = integral grad(phi_i).grad(phi_j)/mu
Mij = integral sigma*phi_i*phi_j
Qig = integral sigma*chi_g*phi_i
Dgg = sigma*area_g
(K + j*omega*M) A - Q E = 0
D E - j*omega*Q.T A = I
```

신호 N개에 대한 전류 행렬 S는 신호의 단위행렬 행들과 공통 귀환의 −1 행으로
구성됩니다. 각 열은 한 신호에 +1 A, 귀환에 −1 A를 가하며 다른 신호의 순전류는
0입니다. 자기장 풀이 후 작은 전류 제약 Schur 계를 풀며 Z=S.T E입니다.
R=Re Z, L=Im Z/ω입니다. DC에서는 E=D⁻¹S, K A=Q E, L=A.T K A로 에너지
극한을 계산하며 0으로 나누지 않습니다. DC 저항은 실제 다각형 면적에 대해
`diag(1/(sigma*signal_area)) + 1/(sigma*ground_area)`와 일치합니다.

주파수는 음수가 아니며 엄격히 증가해야 합니다. 모든 양의 주파수에서
σ/(ωε₀) >= 1000 및 **실제 모든 금속 삼각형 변 <= 표피 깊이**
δ=sqrt(2/(ωµσ))를 요구합니다. 이는 필요한 해상도 조건이며 수렴 보증이
아닙니다. 고주파에서는 많은 삼각형이 필요할 수 있습니다. 표면·부피 모델의
자동 전환이나 미검증 보간은 없습니다.

## 결과와 전파

주파수 F개, 신호 N개, 도체 그룹 G=N+1개에 대해:

| 필드 | 형태와 단위 |
|---|---|
| `Z`, `R`, `L` | (F,N,N); ohm/m, ohm/m, H/m |
| `voltage_gradient` | (F,G,N), 단위 전류에 대한 V/m |
| `current_integrals` | (F,G,N), A; S와 비교 |
| `skin_depth`, `max_edge_over_skin_depth` | (F,), m과 무차원; DC는 무한대와 0 |
| `current_error`, `power_error`, `magnetic_energy_error` | (F,), 최대 전류 잔차 A 및 상대 에너지 잔차 |
| `vector_potential` | 선택적 (F,nodes,N), Wb/m |
| `current_density` | 선택적 (F,triangles,N), A/m²; **요소 중심** Jz이며 금속 밖은 0, 피크 전류가 아님 |

`keep_fields=True`일 때 두 장 배열을 보존하며 아니면 None입니다. 결과는
배열을 복사하고 쓰기를 막습니다. 결과 dataclass 직접 생성은 검증 인증이
아닙니다. 풀이에서는 전류 잔차 <=1e-10 A, Joule/임피던스 및 자기 에너지/L
상대 잔차 <=1e-9, 임피던스 상호성 <=1e-10을 검사합니다. 국소 P1 일관 질량
적분으로 Joule 손실을 계산하여 큰 전역 전기장 항의 상쇄를 피합니다.

`series.network(C=..., G=..., length=..., z_ref=50)`는 이 R과 **전체 L을
한 번만** 사용합니다. 호출자는 동일한 도체 기하·귀환 순서 및 적절한 전기
경계의 C/G를 제공해야 합니다. 외부 L을 다시 더하거나 유한 판과 무한 상자
접지를 조용히 섞으면 안 됩니다. 일반 전파 시험에서 제공하는 명시적 C/G는
이 부피에 대한 독립 유전체 추출이 아닙니다.

## 검증과 제한

필수 시험은 `tests/sipi/test_conductor_diffusion.py`와
`tests/sipi/test_conductor_mesh.py`입니다. 측정 환경은 Python 3.12,
NumPy 2.5.4, SciPy 1.18.1, scikit-fem 12.0.2이며 마지막 도구는 시험 전용입니다.
새 런타임 의존성은 없습니다.

| 사례 | 수락 기준 | 측정 |
|---|---|---|
| 동축 중심 a=.5 mm, 귀환 관 b=1.5/c=2 mm, σ=58 MS/m; 100 Hz–1 MHz | 독립 원통 Bessel 해; 오차 감소, 최종 R/L/Z 1% 이내 | 반경 분할 16/32/64, 각도 256에서 1 MHz R 오차 1.7341% → .44448% → .11380%; 최종 L 오차 .01542% |
| 같은 동축 DC | 원→다각형 R 오차 <.1%; L과 100 Hz 차이 1% 이내 | R 오차 .01004%; L 통과 |
| 직사각 신호 2개와 귀환, DC | 실제 다각형 면적 저항 행렬 relative1e-10 | 통과; AC 전류 재분포·상호성·네트워크 수동성도 검사 |
| 독립 scikit-fem P1 조립과 직접 augmented 풀이, 10 kHz 동축 | 같은 메시 Z 상대 차이 <1e-9 | 9.40e-15; 메시 수렴을 뜻하지 않음 |
| 예제 microstrip, 금속 크기 50→25 µm 및 외부 세분, 100 kHz | R/L 메시 변화 <1% | R .51886357→.51887859 ohm/m; L 485.2423→489.1627 nH/m |
| 같은 fine microstrip, padding 2→4 mm | L 변화 <2% | 489.1627→495.2537 nH/m; 경계 오차는 별도 |
| 직사각/사다리꼴 및 위/아래/측면/coplanar 접지 | 금속 면적과 DC R relative1e-10 | 통과 |

Bessel 기준은 k=sqrt(jωµσ), 중심 도체의 I0/I1, 귀환 관의 I/K 수정 Bessel
해에 H(b)=I/(2πb), H(c)=0을 적용하고 외부 jωµ ln(b/a)/(2π)를 더합니다.
금속 내부 표피 깊이를 해상하며 독립 조립 비교는 같은 메시의 대수를 검증합니다.
서로 다른 근거이며 모든 PCB 기하의 정확도를 보장하지 않습니다.

2D 종방향 자기준정적 모델입니다. 금속 변위전류, 방사, 거칠기, 온도 의존 또는
서로 다른 도체 전도도, 비균일·비선형 자기 매질, 3D 전이는 구현하지 않았습니다.
새 기하·주파수 범위마다 금속·외부 메시를 세분하고 자기 경계를 확대해야 합니다.

동일한 유한 상자 유전체 추출과 부피 JSON은 별도 [부피 선로 모델](volume_line.md)을 사용합니다.
