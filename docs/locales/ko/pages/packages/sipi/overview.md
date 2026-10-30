# sipi — PCB 단면의 신호·전원 무결성

[English](../../../../../packages/sipi/overview.md) | **한국어**

[문서 홈](../../index.md)

`sipi`는 인쇄회로기판(PCB) 전송선의 단위길이 파라미터를 단면에서 계산합니다. 단면은 유전체 층을
쌓고 직사각형 트레이스를 놓은 것입니다. `sipi`는 이를 [meshine](../meshine/overview.md)으로 메시하고
[galerkin](../galerkin/overview.md) 엔진으로 2차원 정전 문제를 풉니다. 의존성은 numpy, scipy,
galerkin, meshine입니다.

```python
from sipi import CrossSection, Layer, Trace

cs = CrossSection(
    layers=[Layer("FR-4", 0.2e-3, eps_r=4.3, tan_delta=0.02),   # y = 0부터 위로
            Layer("air", 4e-3)],
    traces=[Trace("sig", x=0.0, width=0.35e-3, y=0.2e-3, thickness=35e-6)],
    width=8e-3)                       # x = -4 mm부터 +4 mm까지의 상자
line = cs.analyze()
line.z0, line.eps_eff, line.delay     # ohm, -, s/m
line.C, line.L, line.G(1e9)           # F/m, H/m, S/m 행렬
```

길이는 모두 미터이고 결과는 모두 선로 1 m당 값입니다.
[`examples/sipi/pcb_lines.py`](../../../../../../examples/sipi/pcb_lines.py)는 50 Ω급 마이크로스트립과
가장자리 결합 차동 쌍의 임피던스를 출력합니다.

[템플릿·JSON 문서·목표 임피던스 설계](design.md).

## 계산하는 양

도체는 z 방향으로 뻗고 단면이 파장보다 작으므로 선로는 준TEM(quasi-TEM) 파를 전달합니다. 신호 도체가
N개일 때:

| 양 | 의미 | 계산 |
|---|---|---|
| `C` | Maxwell 정전용량 행렬 (F/m) | 실제 유전체로 정전 해석. `C[i, j]`는 도체 j를 1 V, 나머지를 0 V로 둘 때 도체 i의 전하 |
| `C0` | 같은 행렬의 진공값 (F/m) | 모든 유전체를 진공으로 바꿈 |
| `L` | 인덕턴스 행렬 (H/m) | `L = mu0 eps0 inv(C0)` |
| `C_loss`, `G(f)` | 유전 손실 (F/m), 컨덕턴스 (S/m) | 손실 층은 `eps0 eps_r (1 - j tan_delta)`. 구한 정전용량이 `C - j C_loss`이고 `G = 2 pi f C_loss` |

단일선에서는 `z0 = sqrt(L / C)`, `eps_eff = C / C0`, `phase_velocity`, `delay`(s/m)가 속성이고
`loss_tangent()`는 유효 `C_loss / C`입니다. 두 선로에서는 `even_odd()`가 `z_even`, `z_odd`,
`z_diff = 2 z_odd`, `z_common = z_even / 2`와 두 모드의 `eps_eff`를 줍니다. 거울 대칭이 아닌 메시에서
두 자기 항은 이산화 오차만큼 다르므로 평균을 쓰며, 두 자기 항이 `rtol`(1 %)보다 다르면 거부합니다.
`modes()`는 N 도체 선로의 모드 유효 유전율과 전압 고유벡터를 줍니다.

정전용량 항목은 이산 에너지 `eps0 V_i^T K V_j`이므로 행렬은 대칭이고, 적합 유한요소 해는 정확한 `C`에
위에서 다가갑니다.

## 모델

- `Layer(name, thickness, eps_r=1, tan_delta=0)`: 층은 `y = 0`부터 위로 쌓입니다. `tan_delta`는 주파수와
  무관하므로 `G`는 주파수에 비례합니다.
- `Trace(name, x, width, y, thickness=0, ground=False)`: `x`는 중심, `y`는 아랫면입니다. 두께 0인 트레이스는
  `y` 선 위의 띠이고, 두께가 있으면 메시가 비워 두는 고체 도체입니다. `ground=True`면 0 V 기준 도체가 됩니다
  (예: coplanar 접지).
- `CrossSection(layers, traces, width, bottom="ground", top="open", sides="open")`: 상자 각 면은 접지
  (`"ground"`) 또는 절연 벽(`"open"`, 법선 D = 0)입니다. 트레이스는 상자 안쪽에 엄격히 있어야 하고 서로
  닿으면 안 됩니다.
- 마이크로스트립은 `bottom="ground"`에 기판 층과 공기 층, 스트립라인은 여기에 `top="ground"`를 더합니다.

`analyze()`는 `mesh()`의 메시 옵션을 받습니다:

| 옵션 | 기본값 | 의미 |
|---|---|---|
| `edge_size` | min(가장 작은 치수 / 100, 각 양수 트레이스 두께 / 10) | 장이 특이한 트레이스 모서리에서의 목표 변 길이. 치수는 층 두께, 트레이스 폭, 트레이스 사이 간격입니다. 두께 0은 제한을 추가하지 않으며, 명시적으로 준 값은 이 규칙보다 우선합니다. |
| `grade` | 0.15 | 트레이스에서 멀어질 때 단위 거리당 변 길이 증가율 |
| `far_size` | max(width, height) / 24 | 가장 큰 변 길이 |

`mesh()`는 확인용 `MeshedCrossSection`(galerkin 메시, 삼각형별 `eps_r`·`tan_delta`, 도체 절점 집합)을
돌려줍니다. `line_parameters()`와 `capacitance_matrix()`는 절점 집합을 갖춘 임의의 galerkin 메시를 받으므로,
예를 들어 meshine으로 직접 만든 동축 메시도 쓸 수 있습니다.

## 정확도와 직접 확인할 것

유한 두께 트레이스의 기본값은 도체 옆면을 `두께 / 10` 이하로 분할하면서 선 전체에
`두께 / 100`을 강제하지 않습니다. 오차 추정기가 아닌 메시 규칙이므로 새 형상마다 세분 검사를
해야 합니다. [유한 두께 검증](default-mesh.md)을 참고하세요.

모든 결과에는 오차 두 가지가 남으며, 둘 다 사용자가 확인해야 합니다.

1. **이산화.** `edge_size`, `grade`, `far_size`를 함께 반으로 줄여 비교하세요. 기본 옵션에서 아래 V3–V5
   형상의 임피던스 오차는 0.07–0.44 %였습니다.
2. **상자 절단.** `"open"` 벽은 절연체, `"ground"` 벽은 도체이며 열린 공간의 선로는 둘 사이에 있습니다. 둘 다
   풀거나 벽을 바깥으로 옮기세요. 예제 마이크로스트립에서 상자 폭과 공기 층을 두 배로 하면 `z0`가 0.14 %
   바뀌었고, 열린 벽과 접지 벽의 차이는 0.4 %였습니다.

## 검증

비교는 `tests/sipi/test_sipi_references.py`에 있습니다. 기준은 첫 실행 전에 정했습니다. 측정은 2026-10-26,
Linux, Python 3.12, 고정 환경 `tools/requirements-py312-linux.txt`에서 했습니다.

| 사례 | 기준해 | 판정 기준 | 측정값 |
|---|---|---|---|
| V1 2층 평행판, 절연 옆면, 손실 층 | 직렬 커패시터(P1에서 정확) | C, C_loss, C0, L, `eps_eff`, G 모두 1e-9 이내 | 통과 |
| V2 동축선, `b/a = 3`, `eps_r = 2.2` | `C = 2 pi eps / ln(b/a)` | 가장 고운 메시에서 오차 ≤ 1e-3, 맞춘 차수 ≥ 1.5 | 크기 0.2, 0.1, 0.05 mm에서 +3.9e-3, +1.8e-4, −1.1e-4. 다각형 원과 적합 해가 반대 방향으로 틀려 부호가 바뀌므로, 맞춘 차수(2.5)는 깨끗한 점근 수렴률이 아닙니다 |
| V3 두께 0 스트립라인, `w/b = 0.5`, `eps_r = 4` | Cohn 정확 등각사상, Z0 = 50.216 Ω | 세 메시 중 가장 고운 메시에서 0.5 % 이내, 단조 감소 | −1.0 %, −0.24 %, −0.061 % |
| V4 두께 0 결합 스트립라인, `w/b = 0.4`, `s/b = 0.3`, `eps_r = 3.5` | Cohn 정확 even/odd 사상, 68.591 / 51.077 Ω | 각각 0.5 % 이내 | −0.21 % / −0.35 % |
| V5 두께 0 마이크로스트립, `w/h` 0.5, 1, 2와 `eps_r` 4.3, 9.8 | Hammerstad–Jensen(1980), 명시 정확도 0.01–0.03 %(Z0), 0.2 %(`eps_eff`) | 열린 벽과 접지 벽 각각 Z0·`eps_eff` 1 % 이내, 두 벽 사이 1 % 이내 | Z0 −0.22 %~−0.57 %, `eps_eff` −0.27 %~+0.30 %, 두 벽 차이 0.16–0.33 % |

모든 기준해의 자유공간 임피던스는 `sqrt(mu0 / eps0)` = 376.730 Ω입니다. 교과서 형태의 120 pi = 376.991 Ω은
6.9e-4만큼 커서 위 비교를 그만큼 치우치게 합니다.

참고문헌: S. B. Cohn, "Characteristic impedance of the shielded-strip transmission line," *IRE Trans. MTT*
2(2), 1954; "Shielded coupled-strip transmission line," *IRE Trans. MTT* 3(5), 1955; E. Hammerstad and
Ø. Jensen, "Accurate models for microstrip computer-aided design," *IEEE MTT-S Digest*, 1980.

SIPI는 `meshine.generate(candidate_order="stable")`를 사용하여 반지름이 같은 세분 후보의 입력 순서를 유지합니다. 이전 버전과 동률 메시가 달라질 수 있습니다. native/WebAssembly 차이의 한 원인을 제거하며 모든 수치 라이브러리 버전에서 동일 메시를 보장하지는 않습니다.

## 구현하지 않은 것

- 도체 손실 `R`(표피효과, 표면 거칠기). `R`은 반환하지 않습니다.
- 주파수 의존 유전체(예: Djordjevic–Sarkar). `tan_delta`는 상수입니다.
- 시간 영역 응답과 Touchstone 불러오기. [균일 전송선 S·Touchstone 출력](network.md)은 명시한 RLGC를 받습니다.
- 3D 구조: 비아, 평면 공진, 전원 분배망.
- 레이아웃 가져오기(Gerber, ODB++, IPC-2581), `CrossSection`의 임의 다각형 도체와 Studio 화면. [사다리꼴·평탄 코팅과 JSONv2](manufacturing_sections.md)는 지원합니다.
- 자성 기판: `L`은 모든 곳에서 `mu = mu0`를 가정합니다.
