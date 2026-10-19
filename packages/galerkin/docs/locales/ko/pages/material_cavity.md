# 재료 충전 직육면체 공동 솔버

[영문 원문](../../../material_cavity.md)

```python
from galerkin import CavityMaterialRegion, solve_material_cavity_box

slab = CavityMaterialRegion(
    bounds_m=((0.0, 1.0), (0.0, 0.8), (0.0, 0.3)),
    relative_permittivity=4.0 - 0.04j,      # eps' (1 - j tan_delta), tan_delta = 0.01
)
result = solve_material_cavity_box(
    lengths_m=(1.0, 0.8, 0.6),
    subdivisions=(8, 8, 8),
    regions=[slab],
    num_modes=4,
    target_frequency_hz=150e6,
)
print(result.resonant_frequencies_hz, result.quality_factors)
```

이 API는 [진공 PEC 상자 솔버](cavity_solver.md)에 축 정렬 직육면체 영역별로 일정한
(손실이 있을 수 있는) 비유전율과 비투자율을 더합니다. 복소 공진 주파수와 Q를
반환합니다. 벽은 유한 전도도를 주지 않으면 완전 전기 도체이고, 주면 Leontovich 표면
임피던스 조건을 씁니다([유한 전도도 벽](#유한-전도도-벽) 참조). 열린 경계, 이방성·분산
재료, 임의 형상은 포함하지 않습니다. `solve_cavity_box`와 그 계약은 바뀌지 않습니다.

## 규약

시간 의존성은 **`exp(+j*omega*t)`**입니다. 수동(passive) 재료는

    eps_r = eps' - j*eps'',  eps'' >= 0,    mu_r = mu' - j*mu'',  mu'' >= 0

이므로 손실 탄젠트 `tan_delta`인 유전체는 `eps' * (1 - 1j*tan_delta)`입니다. 실수부가
양수가 아니거나 허수부가 양수(이득)인 입력은 거부합니다. 감쇠하는 공진은
`Im(omega) > 0`이며 Q는

    Q = Re(omega) / (2 * Im(omega)) = Re(f) / (2 * Im(f))

로, 위상 변화율과 에너지 감쇠율의 비입니다. 모든 재료가 무손실이면 무한대입니다.
`eps' (1 - j tan_delta)`와 실수 `mu_r`로 균일하게 채운 공동은
`Q = (1 + sqrt(1 + tan_delta**2)) / (2 tan_delta)`, 약 `1/tan_delta`입니다.

PEC 벽에서 `curl(mu_r^-1 curl E) = k0^2 eps_r E`의 약형식은 복소 대칭(비에르미트)
일반화 고유값 문제

    S(1/mu_r) q = k0^2 M(eps_r) q

가 되며 `k0^2`는 복소수입니다. `frequencies_hz = c0 * sqrt(k0^2) / (2*pi)`는 주
제곱근을 써서 `Re f > 0`입니다.

## 인수

`solve_material_cavity_box(lengths_m, subdivisions, *, regions=(), num_modes=6,
target_frequency_hz, wall_conductivity_s_per_m=None)`는 `MaterialCavityResult`를 반환합니다. `lengths_m`,
`subdivisions`, `num_modes`, `target_frequency_hz`의 의미와 검증은 진공 솔버와 같고
mesh도 같은 교대 Kuhn mesh입니다.

`regions`는 `CavityMaterialRegion(bounds_m, relative_permittivity=1,
relative_permeability=1)`의 시퀀스입니다. `bounds_m`은 상자 원점 기준 m 단위
`((x0, x1), (y0, y1), (z0, z1))`입니다. 어느 영역에도 속하지 않는 공간은 진공이고,
영역이 겹치면 뒤의 영역이 우선합니다. 각 사면체는 무게중심이 속한 재료를 가집니다.

모든 경계값은 mesh 격자 평면, 즉 그 축의 `length/subdivisions` 배수여야 합니다(한
cell의 상대 허용치 `1e-9`). 따라서 재료 경계면이 mesh 면과 일치합니다. 그렇지 않으면
`ValueError`가 해당 경계값과 격자 간격을 알려 줍니다. 계단 근사에 기대지 말고
subdivisions를 바꾸세요.

## 결과

K는 요청 모드 수, E는 에지 수, T는 사면체 수입니다.

| 속성 | 형태 / 의미 | 단위 |
| --- | --- | --- |
| `frequencies_hz` | `(K,)` 복소수, 손실이 있으면 `Im > 0` | Hz |
| `resonant_frequencies_hz` | `(K,)` `Re(frequencies_hz)`, 오름차순 | Hz |
| `quality_factors` | `(K,)` `Re f / (2 Im f)`; 무손실이면 `inf` | 무차원 |
| `eigenvalues_m2` | `(K,)` 복소 `k0^2` | m^-2 |
| `edge_coefficients` | `(E,K)` 복소수, PEC 에지는 정확히 0 | m^-1/2 |
| `electric_field` | `(K,T,3)` 복소수, 사면체 무게중심 | m^-3/2 |
| `relative_residuals` | `(K,)` 자유 에지 방정식 | 무차원 |
| `pec_edge_ids`, `mesh`, `space` | 진공 솔버와 같음 | |
| `tet_relative_permittivity`, `tet_relative_permeability` | `(T,)` 사면체별 복소수 | 무차원 |
| `lossless` | 모든 재료 상수가 실수이고 모든 벽이 PEC인지 여부 | bool |
| `time_convention` | `"exp(+j*omega*t)"` | 메타데이터 |
| `wall_conductivity_s_per_m` | `WALLS`별 dict; `None`은 PEC | S/m |
| `fixed_point_iterations` | `(K,)`; 유한 전도도 벽이 없으면 0 | 횟수 |

`search`, `cluster_completeness`, `mode_count_policy`는 진공 솔버와 같은 값과 의미입니다.
`lossless`가 참이어도 계산은 복소수로 하며, 반환 고유값이
`|Im k0^2| <= 1e-9 |k0^2|`임을 확인한 뒤 허수부를 0으로 둡니다.

각 모드는 반환된 SI mesh의 에르미트 **진공** 에지 질량 `M0`로 `q^H M0 q = 1`이 되게
정규화하고, 크기가 가장 큰 계수를 양의 실수로 맞춥니다. 이는 임의의 수학적 정규화이며
볼트, V/m, 에너지, 전력이 아닙니다. 서로 다른 공진은 `M0` 직교가 아니라 켤레 없는
쌍선형형식 `q_i^T M(eps_r) q_j = 0`으로 쌍직교합니다.

## 수치 방법과 실패 정책

S와 M은 서로 다른 재료마다 실수 지시함수 가중 조립에 복소 상수 `1/mu_r`, `eps_r`를
곱해 더합니다. 기울기 핵(`(nx-1)(ny-1)(nz-1)`개 내부 절점 기울기)에 대해 C를 내부
절점 전위에서 자유 에지 순환으로의 사상으로 두고, 켤레 없는 전치로
`P = I - C (C^T M C)^-1 C^T M`을 씁니다.

- 자유 에지 256개 이하: 조밀 `scipy.linalg.eig(S, M)`과 정확한 핵 개수 검사.
- 그 외: **표준** 문제 `T = P (S - sigma M)^-1 M P`에 ARPACK `which="LM"`을 적용하고,
  `sigma = (2*pi*f_target*L/c0)^2`, `k0^2 = sigma + 1/nu`로 되돌립니다. ARPACK의 일반화
  모드는 에르미트 양정치 M을 요구하므로 쓰지 않습니다. T는 기울기를 소거하고(`nu = 0`,
  제외) 물리 고유값을 보존합니다. 후보 수, `ncv`, 허용치 `1e-10`, 반복 한도, seed는 진공
  솔버를 따릅니다. 희소 LU는 대칭 희소 구조에 맞는 `MMD_AT_PLUS_A` 순서를 씁니다.

물리 후보는 `|k0^2|`가 해석적 진공 기본 모드 값을 `max|eps_r mu_r|`로 나눈 값의
`1e-8`배보다 큰 것입니다. 목표와의 `|k0^2 - sigma|`가 가장 작은 요청 개수를 실수 주파수
오름차순으로 반환합니다. 반환 집합은 모두 다음을 통과해야 합니다.

- 상대 잔차 `||S q - k0^2 M q|| / (||S q|| + |k0^2| ||M q||) <= 1e-8`;
- 기울기 성분(M 기반 투영)의 `M0` 노름 `<= 1e-9`;
- `M0` Gram 행렬의 최소 고유값 `>= 1e-6`(중복 벡터 없음);
- 상대 간격이 `1e-6`보다 큰 공진 쌍은
  `|q_i^T M q_j| <= 1e-7 * sqrt((|q_i|^T |M| |q_i|)(|q_j|^T |M| |q_j|))`;
- `Im k0^2 < -1e-9 |k0^2|`(이득) 또는 `Re k0^2 <= 0`인 물리 후보가 없을 것.

실패는 부분 결과 없이 `RuntimeError`, 잘못된 인수는 `ValueError`를 냅니다.

## 검증

저장소 루트에서:

```bash
python -m pytest -c pyproject.toml -q packages/galerkin/tests/test_material_cavity.py \
  packages/galerkin/tests/test_cavity_wall_loss.py \
  packages/galerkin-refsol/tests/test_material_cavity_reference.py \
  packages/galerkin-refsol/tests/test_wall_loss_reference.py
```

정답은 `refsol.material_cavity`와 `refsol.wall_loss`에 있으며 mesh나 FEM 코드를 쓰지 않습니다.

**균일 충전.** 균질 공동은 진공 장을 그대로 가지고 `k0^2 = k_vac^2 / (eps_r mu_r)`가
정확하며, 이산 문제도 똑같이 축척됩니다. 시험은 재료 솔버를 진공 솔버에 이 인자를 곱한
값과 상대 `1e-11`로 비교하고(n = 2, 4; 손실 유전·자성, 무손실 유전, 손실 자성), 반환된
모든 Q를 닫힌 식과 `1e-9`로 비교합니다. `tan_delta = 1e-3`에서 `Q = 1/tan_delta`가
`1e-6` 이내입니다.

**유전체 판 충전.** `a x b x c` 상자의 단면 전체를 `0 <= z <= d`로 채운 판은
`kx = m pi/a`, `ky = n pi/b`, `kz_i^2 = eps_i mu_i k0^2 - kx^2 - ky^2`인 TE-to-z(`Ez = 0`)와
TM-to-z(`Hz = 0`) 모드로 분리됩니다. `z = d`에서 접선 장을 맞추면
`S_i = sin(kz_i L_i)/kz_i`, `C_i = cos(kz_i L_i)`, `L_1 = d`, `L_2 = c - d`로

    TE-to-z:  C_1 S_2 / mu_1 + S_1 C_2 / mu_2 = 0
    TM-to-z:  kz_1^2 S_1 C_2 / eps_1 + kz_2^2 S_2 C_1 / eps_2 = 0

입니다. 두 식은 `k0^2`의 정함수이므로 `kz_i = 0`에서 가짜 근이 없습니다. 무손실 근을
실수 주사로 구간화해 이분법으로 구한 뒤, 복소 secant 반복으로 16단계 homotopy를 거쳐
복소 재료로 연속시킵니다. 정답 자체 검사: `eps = 1`이면 `(1, 0.8, 0.6) m`에서 500 MHz
이하 진공 모드 15개를 `1e-13`으로 재현하고, 두 층이 같은 손실 재료면 균일 축척을
`1e-12`로 재현하며, `tan_delta = 1e-4`에서 계산한 `1/Q`가 독립 무손실 근에서 얻은 전기
충전율 `-(eps'/k0^2) dk0^2/deps'`과 `tan_delta`의 곱과 상대 `2e-3` 이내로 같습니다.

고정 수렴 연구는 상자 `(1, 0.8, 0.6) m`, 판 `0 <= z <= 0.3 m`, 모든 방향 `n = 4, 8, 16`,
목표 50 MHz(기본 모드 아래), 실수부 오름차순 최저 6개 모드를 씁니다.

경우 `eps = 4 - 0.04j`, `mu = 1` (z 기준 TM11, TE10, TE01, TE11, TM21, TE20):

| 양 | TM11 | TE10 | TE01 | TE11 | TM21 | TE20 |
| --- | --- | --- | --- | --- | --- | --- |
| 정답 f (MHz) | 155.763+0.605j | 175.160+0.780j | 186.637+0.839j | 205.021+0.935j | 207.719+0.947j | 228.145+1.057j |
| 정답 Q | 128.676 | 112.238 | 111.187 | 109.625 | 109.635 | 107.904 |
| `|dk0^2|/|k0^2|`, n=16 | 6.9e-4 | 8.9e-4 | 3.5e-3 | 2.9e-4 | 2.9e-3 | 2.4e-4 |
| 차수 8→16 | 1.949 | 2.035 | 1.999 | 1.539 | 1.934 | -0.576 |
| Q 상대 오차, n=16 | 4.2e-4 | 3.3e-4 | 2.3e-4 | 2.9e-4 | 1.19e-3 | 5.9e-4 |

경우 `eps = 2.5 - 0.1j`, `mu = 1.2 - 0.02j` (z 기준 TM11, TE10, TE01, TM21, TE11, TM12):

| 양 | TM11 | TE10 | TE01 | TM21 | TE11 | TM12 |
| --- | --- | --- | --- | --- | --- | --- |
| 정답 f (MHz) | 170.767+3.662j | 202.255+4.386j | 215.658+4.763j | 234.327+5.944j | 237.134+5.388j | 261.535+6.849j |
| 정답 Q | 23.313 | 23.055 | 22.637 | 19.711 | 22.004 | 19.094 |
| `|dk0^2|/|k0^2|`, n=16 | 5.8e-4 | 9.9e-4 | 3.6e-3 | 2.4e-3 | 1.5e-4 | 1.2e-3 |
| 차수 8→16 | 1.943 | 2.033 | 1.998 | 1.918 | 0.867 | 1.758 |
| Q 상대 오차, n=16 | 4.6e-5 | 3.9e-4 | 6.3e-5 | 1.10e-3 | 1.5e-4 | 1.41e-3 |

기준(두 경우 모두): 최저 3개 모드의 복소 고유값 오차가 매 단계 감소하고 마지막 차수가
**1.8**을 넘을 것; n = 16에서 6개 모두 `|dk0^2|/|k0^2| < 4e-3`, Q 상대 오차 `< 1.5e-3`;
모든 Q 오차가 n = 8에서 16으로 감소할 것. TE11 모드의 실수부 오차는 두 경우 모두
n = 4와 8 사이에서 부호가 바뀌므로(첫 경우는 TE20도) 이 고정 수열에서 관측 차수는
상쇄를 반영하며 기준으로 쓰지 않습니다. 그 절대 오차는 가장 작은 편입니다. 대응은
실수부 오름차순이며, n = 16에서 모든 오차는 이웃 정답 모드 간격보다 훨씬 작습니다.

기타 시험: 손실 유전·자성 판에서 n = 2, 4, 6의 목표 근처 선택이 완전한 조밀 복소
스펙트럼(정확한 `(n-1)^3` 핵 포함)과 같음; 독립적인 재료별 조립으로 잔차 재계산; 빈
`regions`가 `solve_cavity_box`를 `1e-10`으로 재현; 축을 바꾼 상자에서 x에 수직인 판이
z 적층 정답과 일치(n = 8에서 고유값 1.5%, Q 0.3% 이내); 영역 우선순위와 무게중심 배정;
격자 밖 경계, 이득, 양수가 아닌 실수부, 잘못된 경계 형식과 타입의 거부.

## 유한 전도도 벽

`wall_conductivity_s_per_m`는 `None`(여섯 벽 모두 PEC), 모든 벽에 같은 양의 전도도 하나,
또는 `galerkin.material_cavity.WALLS`(`"x0", "x1", "y0", "y1", "z0", "z1"`, 각 축의 낮은
쪽·높은 쪽 벽)를 키로 하는 dict입니다. 없거나 `None`인 항목은 PEC입니다. 값은 유한한
양의 S/m이어야 하며 0, 음수, 무한대, bool, 알 수 없는 벽 이름은 `ValueError`입니다.

유한 전도도 벽은 Leontovich 조건 `E_t = Zs H x n`(n은 공동 밖을 향함)과 양도체 임피던스

    Zs = sqrt(j omega mu0 / sigma) = (1 + j) Rs,   Rs = sqrt(omega mu0 / (2 sigma))

를 씁니다. `curl(mu_r^-1 curl E)`를 부분적분하면 `-j omega mu0 int (n x H) . v dS`가
남고 `n x H = -E_t / Zs`이므로 약형식에 벽 항

    j k0 (eta0 / Zs) int_wall E_t . v_t dS = sqrt(j k0 eta0 sigma) B_wall

이 더해집니다. `eta0 = mu0 c0`, `mu0 = 1.25663706212e-6 H/m`, `B_wall`은 그 벽 삼각형의
정확한 접선 Whitney 에지 질량입니다. PEC 벽의 에지는 구속을 유지하고, 유한 전도도 벽의
에지는 미지수가 됩니다. 내부 절점 기울기가 여전히 정확한 핵이므로 투영과 핵 개수는
바뀌지 않습니다. 벽 계수가 `k0^(1/2)`로 변하므로

    T(k0^2) q = [S + sum_w sqrt(j k0 eta0 sigma_w) B_w - k0^2 M] q = 0

은 비선형 고유값 문제이며 다음과 같이 풉니다.

1. 목표에서 벽 계수를 계산한 선형 문제를 풀어 평소처럼 모드를 고릅니다.
2. 고른 모드마다 그 모드의 시작값에서 `T`를 LU 분해 한 번만 하고 잔차 역반복
   (Neumaier 1985)을 씁니다. 각 단계는 스칼라 방정식 `x^T T(k0^2) x = 0`을 Newton으로 풀고
   `x <- x - P T0^-1 P^T T(k0^2) x`로 보정합니다. 상대 비선형 잔차 `<= 1e-10`이고 고유값
   변화가 `<= 1e-12`이면 멈추며, 최대 50단계입니다.
3. 상대 `1e-8` 안에서 축퇴한 모드들(예: 정육면체의 011/101/110 삼중 모드)은 평균에서 계산한
   벽 계수 하나를 공유하고, 같은 정지 규칙으로 반복 shift 고유값 풀이로 다듬습니다.

수렴하지 않으면 `RuntimeError`입니다. 보고하는 잔차는 선형 잔차와, 각 모드의 최종 `k0`로
`Zs`를 계산한 비선형 잔차 중 큰 값이며 같은 `<= 1e-8` 기준을 통과해야 합니다. 유한 전도도
벽에서는 모드마다 자기 연산자를 풀기 때문에 M-쌍직교 검사를 하지 않습니다. 나머지
기준은 모두 적용합니다. 임피던스 조건은 표피 깊이가 벽 곡률과 cell 크기보다 충분히 작아
`|Zs| << eta0`일 때만 유효합니다. 표면 거칠기, 코팅, 주파수 의존 전도도는 모델링하지
않습니다.

### 벽 손실 정답과 검증

`refsol.wall_loss`는 표준 1차(섭동) 도체 Q

    Q_c = omega W / P_c,   W = (mu/2) int |H|^2 dV,   P_c = (Rs/2) sum_w int_w |H_t|^2 dS

를 PEC 정재파 `Ex = Ax cos(kx x) sin(ky y) sin(kz z)`(및 순환 치환)로 계산합니다. 모든
적분은 `sin^2`, `cos^2`의 닫힌 식 곱입니다. 세 지수가 모두 양수면 두 편광이 축퇴합니다.
이때 벽 손실은 진폭 평면의 이차형식이고, 그 고유벡터가 두 Q 값을 줍니다. Leontovich
리액턴스는 손실이 허수부를 올리는 만큼 실수 주파수를 낮춥니다:
`omega = omega0 (1 + (j - 1)/(2 Q_c))`. 무시한 항의 상대 크기는 `1/Q_c`입니다.

정답 자체 검사: TE101이 Pozar 닫힌 식(*Microwave Engineering*, 4판, 식 6.46)과 `1e-12`로
같습니다. `(1, 0.8, 0.6) m`의 400 MHz 이하 모든 모드(분리된 111 이중 모드 포함)가 유한차분
curl의 Gauss 적분과 `1e-6`로 같습니다. 벽별 손실의 합이 전체와 같습니다. `Q`는
`sqrt(sigma)`로 축척됩니다. 균일 충전은 `Q -> Q mu_r (eps_r mu_r)^(-1/4)`입니다. 정육면체
축퇴가 보존됩니다.

FEM 시험은 상자 `(1, 0.45, 0.8) m`(최저 4개 모드에 우연 축퇴 없음)와 구리
`sigma = 5.8e7 S/m`를 씁니다.

| 모드 | f (MHz) | 정답 Q_c | Q 오차 n=4 | n=8 | n=16 | 차수 8→16 |
| --- | --- | --- | --- | --- | --- | --- |
| 101 | 239.951 | 51776.8 | -4.74% | -1.25% | -0.314% | 1.988 |
| 201 | 353.530 | 65216.0 | -13.9% | -2.77% | -0.714% | 1.958 |
| 110 | 365.276 | 54744.4 | +6.12% | +0.715% | +0.184% | 1.958 |
| 011 | 382.185 | 59436.8 | +8.28% | +2.37% | +0.616% | 1.945 |

고정 slow 기준: Q 오차가 매 단계 감소하고 마지막 차수 **> 1.8**, n=16 Q 오차 `< 8e-3`,
복소 주파수 오차 `< 4e-3`(관측 최대 `3.5e-3`). 모든 모드가 비선형 반복 4회를 썼습니다.

기타 벽 시험:

- n=8의 TE101이 Pozar와 1.5% 이내입니다.
- `j k0 eta0 / Zs`로 `T(k0)`를 독립적으로 SI 재조립하면 비선형 잔차가 `< 1e-7`입니다.
- 벽 질량이 모든 균일 장의 접선 부분을 정확히 적분합니다(`1e-12`).
- n=8의 단일 벽 Q가 정답과 6.7% 이내입니다.
- 1차 가법성: 여섯 단일 벽 `1/Q`의 합이 모든 벽 `1/Q`와 `3.1e-4` 이내입니다.
- `sigma = 1e18`이 PEC 솔버를 `7.7e-11`로 재현합니다.
- 손실 유전체 충전과 구리 벽을 함께 쓰면 `1/Q = 1/Q_walls + 1/Q_d`가 `5e-6` 이내입니다. 충전 공동의 벽 Q는 n=8에서 정답과 2.8% 이내입니다.
- 정육면체 삼중 모드는 정확히 축퇴(폭 `9e-16`)를 유지하고, 서로 독립인 세 모드이며, n=4에서 Q가 정답과 3.8% 이내입니다.
- 조밀 n=2 경우에 혼합 벽을 씁니다.
- 잘못된 전도도를 거부합니다.

## 레퍼런스 도구 비교

scikit-fem 12.0.2(`BSD-3-Clause`, 시험 extra `galerkin[crosscheck]`)와 같은 이산화 비교:
`tests/test_crosscheck_skfem_lossy_cavity.py`가 galerkin 메시에서 손실 판과 임피던스 벽 연산자를 다시
조립하고 고유값 차이를 `1e-9`로 검사합니다(관측 `4.1e-15`, `6.8e-13`).
[레퍼런스 비교](https://github.com/fieldalgo/openphysics/blob/main/docs/locales/ko/pages/reference-comparisons.md)를 참조하세요.

### 고차 비교 (NGSolve)

이 비교는 위의 해석해 pass/fail 기준과 별개이며, 그것을 대신하거나 수렴 증거로 쓰지 않습니다.

**도구와 설정.**

- NGSolve 6.2.2608과 netgen-mesher 6.2.2608(둘 다 `LGPL-2.1-only`). PyPI 휠로 별도
  Python 3.12 환경에 설치해 별도 프로세스로 실행했습니다. OpenPhysics의 의존성이 아니며
  NGSolve 코드를 복사하지 않았습니다.
- 재현 스크립트와 원자료 JSON은 비공개 lab 저장소에 있습니다.

**맞춘 조건:**

- 기하: 상자 `(1, 0.8, 0.6) m`와 판 `z <= 0.3 m`, 그리고 상자 `(1, 0.45, 0.8) m`;
- 재료: `eps = 4 - 0.04j`, 그리고 `eps = 2.5 - 0.1j`와 `mu = 1.2 - 0.02j`;
- PEC 벽, 또는 구리 Leontovich 벽(`sigma = 5.8e7 S/m`, 같은 약형식 항과 `mu0`);
- 시간 규약, Q 정의, 실수부 기준 최저 모드;
- 모드별 `k0` 고정점.

**맞추지 않은 조건:**

- 메시: 비구조 Netgen 사면체와 구조 교대 Kuhn 메시;
- 요소 차수: NGSolve 4차(`maxh = 0.15 m`, 복소 미지수 27.5k–47.3k, 도구 자체 확인용
  3차 `maxh = 0.2 m` 실행 포함)와 최저차 galerkin n = 16;
- 고유값 풀이: 목표에 shift를 둔 NGSolve Arnoldi.

Arnoldi 벡터 14개로는 `eps = 4 - 0.04j` 경우의 4차 실행에서 여섯째 값이 수렴하지 않았습니다
(908.5 MHz, Q 음수). 벡터 26개로 다시 돌리자 여섯 모드가 모두 수렴했습니다. 수렴한 재실행만
쓰고, 실패 값은 원자료에 남겼습니다.

여섯 모드(판) 또는 네 모드(구리) 중 가장 큰 상대 차이:

| 경우 | NGSolve p4 vs 해석해: f / Q | NGSolve p3 vs p4: f / Q | galerkin n=16 vs NGSolve p4: f / Q | galerkin n=16 vs 해석해: Q |
| --- | --- | --- | --- | --- |
| 판 `eps 2.5-0.1j`, `mu 1.2-0.02j` | 7.8e-6 / 1.2e-4 | 1.4e-4 / 3.6e-4 | 1.8e-3 / 1.5e-3 | 1.4e-3 |
| 판 `eps 4-0.04j` | 1.6e-7 / 1.3e-7 | 3.3e-4 / 1.3e-3 | 1.8e-3 / 1.2e-3 | 1.2e-3 |
| 구리 벽 | 6.2e-7 / 1.3e-5 | 1.9e-3 / 1.4e-2 | 3.5e-3 / 7.1e-3 | 7.1e-3 |

고차 NGSolve 결과는 독립 해석 정답과 주파수에서 `1.6e-7`–`7.8e-6`로 일치합니다. 구리 벽 Q의
`1.3e-5` 차이는 1차 섭동 정답의 `O(1/Q)` 항 안에 있습니다. 여기서 Q는 `Re f / (2 Im f)`이며
`omega0 W / P`와 1/2만큼 다릅니다. galerkin과 NGSolve의 차이는 galerkin과 해석해의 차이와 같으며,
이미 위에서 기준을 둔 galerkin 자체의 메시 오차입니다.

| 실행 | 시간 / 메모리 (1코어) |
| --- | --- |
| NGSolve 4차 | 경우별 29 s, 25 s(벡터 26개로 42 s), 63 s; 최대 RSS 1.8 GB |
| galerkin n=16 | 9.6 s, 9.2 s, 34 s |

이 시간은 서로 다른 이산화의 결과이며 성능 비교가 아닙니다.

**지원 판단:** 바뀌지 않습니다. 이 기능은 해석해 기준을 근거로 지원합니다. 비교에서 galerkin의
문서화된 메시 오차와 정답의 1차 항을 넘는 불일치는 없었습니다.

## 한계

- 유한 전도도 벽은 상자 벽 전체에 적용하는 국소 Leontovich 임피던스이며 정답은 1차
  섭동식입니다. 거칠기, 코팅, 벽 일부 패치는 없습니다.
- 일정하고 등방적이며 주파수 무관한 `eps_r`, `mu_r`만 지원합니다. 분산 재료도 문제를
  비선형으로 만듭니다.
- 영역은 격자 평면에 맞춘 직육면체입니다. 계단 근사나 곡면 경계는 없습니다.
- 검색·군집·개수 정책은 진공 솔버와 같습니다.
