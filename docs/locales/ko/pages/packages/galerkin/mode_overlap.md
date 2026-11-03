# 모드 전력, 중첩과 결합

[English](../../../../../packages/galerkin/mode_overlap.md) | **한국어**

[galerkin 개요](overview.md) · [고유공간 신뢰성](eigenspace_reliability.md) · [미분](differentiation.md)

`galerkin.mode_overlap`은 `galerkin.waveguide.solve_modes`의 모드(전체 벡터, edge `et`와
절점 `ez`)와 `Mesh` 위의 스칼라 P1 모드 함수를 후처리합니다: 도파 전력, 장 중첩,
정규화, 결합 효율, 구속 계수, 유효 면적. 모든 적분은 유한요소 계수의 정확한 질량·결합
행렬 곱이며, 유효 면적의 `int |E|^4`만 대칭 삼각형 구적 규칙으로 정확히 적분합니다.
함수가 그렇게 명시한 곳 외에는 요소 중심에서 표본을 뽑지 않습니다. 이
페이지는 계약이자 검증 기록입니다. 식은 사전 등록된 것이고, 아래 측정값은 고정된
Linux 환경에서 `tests/galerkin/test_mode_overlap.py`가 낸 값입니다(2026-11-02).

## 관례

- 페이저는 solver와 같이 `exp(+i omega t - i beta z)`입니다. `et[i]`는 `E_t`의 edge
  선적분(전역 방향: 낮은 절점 번호에서 높은 번호로), `ez[i]`는 `E_z = 1j * ez[i]`인
  절점 값이며 진폭과 위상은 임의입니다([고유공간 신뢰성](eigenspace_reliability.md)).
  스칼라 모드는 절점 `phi`입니다.
- `k0`와 `n_eff`는 solver의 것입니다: `beta = k0 n_eff`, `k0`는 메시 길이의 역수
  단위, `n_eff`는 실수 또는 복소수.
- `mu_r`(기본 1)과 `eps_r`는 solver와 같이 스칼라 또는 삼각형당 한 값입니다. 아래
  함수들은 Poynting 적분에 `conj(1/mu_r)`을, 에너지 가중치에 `Re(eps_r)`을 씁니다.
- **단위.** 메시가 미터, `E`가 V/m이면 `vector_power`는 와트입니다. 메시가 다른
  단위 `L`(메시 단위당 미터)이고 `k0`가 그 역수 단위이면, `E`가 메시 단위당 볼트일
  때 결과가 와트이고, `E`가 V/m이면 `L^2`을 곱합니다. 모드 진폭이 임의이므로
  정규화 전의 "전력"은 (장 단위)^2당 와트입니다. 장 중첩은 (장 단위)^2 (메시
  단위)^2를 가지며, 효율과 구속 계수는 무차원입니다. 스칼라 "전력"은
  `int |phi|^2 dA`이고 물리적 전력이 아닙니다.

## 식

**전기장에서 자기장.** 위 페이저와 `grad = grad_t - i beta zhat`로 Faraday 법칙은
모드의 횡 자기장을 `E`만으로 줍니다(solver는 `H`를 만들지 않습니다):

    H_t = (beta / (omega mu)) zhat x E_t + (1 / (i omega mu)) zhat x grad_t E_z.

**전력과 교차 전력.** 횡 벡터 `a`, `b`에 대해 `(a x (zhat x b)) . zhat = a . b`이므로,
모드 `a`의 전기장과 모드 `b`의 자기장의 복소 Poynting 적분은

    P_ab = 1/2 int (E_a x H_b^*) . zhat dA
         = (1 / (2 omega mu0)) int conj(1/mu_r) [ conj(beta_b) E_ta . E_tb^* + i E_ta . grad_t E_zb^* ] dA,

이고 `P = P_aa`입니다. `Re P`는 `+z` 방향 시간 평균 전력이며 무손실 모드에서 `P`는
실수입니다. `E_t = sum_e et_e W_e`(Whitney edge 함수), `E_z = i sum_n ez_n phi_n`(P1
모자 함수)을 넣으면 두 적분은 edge 질량 `M_e(c) = int c W_e . W_f`
(`assemble_edge_mass`, 정확)와 edge-절점 결합 `G(c) = int c W_e . grad phi_n`
(`assemble_edge_grad`, 정확)입니다:

    P_ab = (1 / (2 omega mu0)) [ conj(beta_b) et_b^H M_e(c) et_a + ez_b^H G(c)^T et_a ],    c = conj(1/mu_r),

여기서 `omega mu0 = k0 c mu0`(`scipy.constants`)입니다. `G` 항의 부호와 방향은
`i int c E_t . conj(grad_t E_z)`의 무차별 요소 중심 적분(조각별 선형 피적분함수에
정확)과 비교했습니다: `conj(ez) @ (G.T @ et)`가 반올림 오차 안에서 재현하고,
`et^H G ez`는 그 공액이며 실수부가 같습니다.

**정확한 이산 전력 직교성.** 실수 pencil `A x = -beta^2 B x`, `x = [beta et; ez]`에서
둘째 블록 행은 `G^T et = -(K - k0^2 M) ez / beta`입니다. 이를 서로 다른 고유값의 두
고유벡터의 `B`-직교성 `x_b^T B x_a = 0`에 대입하면
`beta_a [ beta_b et_b^T M_t et_a + ez_b^T G^T et_a ] = 2 omega mu0 beta_a P_ab`가 남습니다.
따라서 서로 다른 무손실 이산 모드의 교차 전력은 극한에서만이 아니라 정확히 0이며,
아래 측정이 반올림 수준에서 이를 확인합니다.

**장 중첩, 결합 효율, 구속.**

    <E_a, E_b> = int E_a^* . E_b dA = et_a^H M_e(1) et_b + ez_a^H M(1) ez_b        (M(1): P1 질량, 정확)
    eta        = |<E_m, E_in>|^2 / (<E_m, E_m> <E_in, E_in>)
    Gamma_R    = int_R Re(eps_r) |E|^2 dA / int Re(eps_r) |E|^2 dA

모드가 여럿(퇴화 쌍)이면 `eta`는 그 생성 공간 안의 입력 비율
`||P E_in||^2 / ||E_in||^2`로, 장 중첩의 직교 사영을 모드의 Gram 행렬로 계산합니다.
횡 입력(`ez_in` 생략)은 모드의 `E_t`와만 비교하므로 종방향 성분은 입력에 그것이 있을
때만 `eta`에 들어갑니다. `Gamma_R`는 계수를 삼각형 집합 `R`로 제한합니다. 스칼라
함수는 `M(1)`만 씁니다.

**유효 면적.**

    A_eff = (int |E|^2 dA)^2 / int |E|^4 dA

기본은 `|E|^2 = |E_t|^2`(통상의 횡 정의)이고 `include_longitudinal=True`면
`|E_t|^2 + |E_z|^2`입니다. 스칼라 모드는 `|E|` 대신 `|phi|`를 씁니다. 분자는 모드 자신과의
장 중첩(edge·P1 질량 행렬, 정확)입니다. 분모는 질량 행렬 형태가 없으므로 Dunavant의
6점 4차 대칭 삼각형 규칙(`galerkin.core.quadrature.triangle_symmetric_rule(4)`)으로
Whitney/P1 보간을 규칙의 점에서 평가해 적분합니다. `E_t`(Whitney)와 `E_z`, `phi`(P1)는
삼각형마다 선형이므로 `(|E|^2)^2`은 거기서 4차 다항식이고 규칙은 근사가 아니라
정확합니다. 아래 기준 F3이 12점 6차 규칙과 36점 Gauss–Duffy 곱 규칙에 대해 이를
확인합니다. `A_eff`는 척도에 무관하고 (메시 단위)^2를 가지며, 높이 `h`의 띠 위 y-불변
장에서는 `h` 곱하기 유효 폭 `(int |E|^2 dx)^2 / int |E|^4 dx`입니다.

**주어진 장의 보간.** `interpolate_vector_field(space, field)`는 함수
`field(x, y) -> (N, 2 또는 3)`을 `(et, ez)`로 보냅니다: `et_e`는 edge `e`를 따른 접선
선적분을 2점 Gauss 구적으로(최저차 Nédélec 보간; edge 방향 3차 변화까지 정확),
`ez = -1j * E_z(절점)`입니다. 요소 중심에서만 아는 장 `(T, 2)`는 edge 자유도로 보낼 수
없습니다: 한 삼각형의 세 Whitney 함수는 중심에서 선형 종속이어서(상수 curl 거품이
거기서 0) 중심 평가 사상은 흔한 구조 메시에서 핵을 가지며 최소제곱 맞춤이 유일하지
않습니다. 그런 사영은 제공하지 않습니다. 장을 함수로 표본화하거나
`centroid_field`로 중심 장을 직접 비교하십시오.

## API

모든 함수는 NumPy 전용입니다. JAX·PyTorch 값은 `TypeError`를 냅니다
(`galerkin.core.checks.refuse_live`). `space`는 `solve_modes`가 돌려준 `EdgeSpace`이고,
모양을 검사하며 비유한 값을 거부합니다.

| 함수 | 반환 |
|---|---|
| `vector_power(space, et, ez, n_eff, k0, mu_r=1.0)` | 한 모드의 복소 `P`; `Re P`가 +z 전력, 무손실 모드에서 실수 |
| `vector_cross_power(space, et_a, ez_a, et_b, ez_b, n_eff_b, k0, mu_r=1.0)` | `P_ab`; `a`가 `E`, `b`가 `H^*`와 그 `n_eff_b` |
| `vector_field_overlap(space, et_a, ez_a, et_b, ez_b, include_longitudinal=True)` | `<E_a, E_b>`; `False`면 `E_t`만(`ez`는 None 가능) |
| `overlap_matrix(space, et, ez, kind="field" \| "power", n_eff=None, k0=None, mu_r=1.0)` | `(m, n_e)`, `(m, n_n)`으로 쌓은 모드들의 `<E_a, E_b>` 또는 `P_ab` `(m, m)` 행렬 |
| `normalize_vector(space, et, ez, n_eff=None, k0=None, mu_r=1.0, convention="power" \| "mass" \| "peak")` | `Re P = 1`, `int |E|^2 = 1`, 또는 최대 중심 `|E| = 1`(simcase 벡터 관례)인 `(et, ez)`; 위상 유지; `"power"`는 `Re P > 0` 필요 |
| `coupling_efficiency(space, et_mode, ez_mode, et_in, ez_in=None)` | `eta`; `et_mode`는 `(n_e,)` 또는 여러 모드의 생성 공간을 위한 `(m, n_e)` |
| `confinement_factor(space, et, ez, eps_r, triangles)` | `Gamma_R`; `triangles`는 불 마스크 `(T,)` 또는 인덱스 배열 |
| `centroid_field(space, et, ez=None)` | 요소 중심의 복소 `E` `(T, 3)`(`eval_edge_field`와 절점 `ez` 평균의 `1j *`) |
| `interpolate_vector_field(space, field)` | 함수의 `(et, ez)`; 2성분 장이면 `ez`는 None |
| `effective_area(space, et, ez, include_longitudinal=False)` | (메시 단위)^2의 `A_eff`; 기본은 `E_t`만(`ez`는 None 가능), `True`면 `E_t`와 `E_z` |
| `scalar_power(mesh, phi)` | `int |phi|^2 dA` |
| `scalar_overlap(mesh, a, b)` | `int a^* b dA` |
| `normalize_scalar(mesh, phi, convention="power" \| "peak")` | 단위 `int |phi|^2`(위상 유지) 또는 `|phi|`가 최대인 절점에서 정확히 1(simcase 스칼라 관례, 임의 위상을 제거) |
| `scalar_coupling_efficiency(mesh, mode, field)` | P1 질량의 `eta`; `mode`는 `(n_n,)` 또는 `(m, n_n)` |
| `scalar_confinement_factor(mesh, phi, triangles)` | `int_R |phi|^2 / int |phi|^2` |
| `scalar_effective_area(mesh, phi)` | `(int |phi|^2 dA)^2 / int |phi|^4 dA` |

공개 이름은 `galerkin`에서도 내보냅니다. 벡터 전력 함수는 `beta`가 `H_t`에 들어가므로
`n_eff`를 명시적으로 받습니다. `solve_modes`가 `(n_eff, space, et, ez)`를 돌려주므로
`vector_power(space, et[i], ez[i], n_eff[i], k0)`입니다.

```python
import numpy as np
from galerkin import rectangle_mesh, solve_modes
from galerkin.mode_overlap import normalize_vector, coupling_efficiency, confinement_factor, interpolate_vector_field

n_eff, space, et, ez = solve_modes(mesh, eps_r, k0, n_target=n_core, num_modes=4)
et0, ez0 = normalize_vector(space, et[0], ez[0], n_eff[0], k0)           # Re P = 1
gamma = confinement_factor(space, et0, ez0, eps_r, mesh.regions == 0)   # 영역 0의 에너지
et_in, _ = interpolate_vector_field(space, lambda x, y: np.stack([np.exp(-(x**2 + y**2) / w0**2),
                                                                  np.zeros_like(x)], axis=-1))
eta = coupling_efficiency(space, et[:2], ez[:2], et_in)                 # 퇴화 쌍으로의 Gaussian 결합
```

## 검증

참조는 모듈을 쓰지 않습니다: `refsol.slab.field_te`와 `refsol.fiber.vector_mode_field`를
`scipy.integrate.quad` 또는 코어 반경에서 나눈 조밀한 극좌표 격자로 적분하고, 테스트
안에서 조립한 edge 질량 곱과 무차별 요소 중심 합을 씁니다. 기준은 측정 전에 고정했고
쓰인 대로 유지합니다. 충족하지 않은 기준은 완화하지 않고 보고합니다. 테스트는 모든
값을 출력하며 파일은 약 12초에 돕니다.

**A. 스칼라 TE slab** (d = 0.22 µm, n_f = 3.48, n_s = n_c = 1.444, λ = 1.55 µm; simcase
스칼라 solver와 같은 P1 일반화 고유문제 `(k0^2 M_eps - K) phi = beta^2 M phi`를 테스트
안에서 구성; ±1.21 µm에 PEC 먼 벽; h = 0.044, 0.022, 0.011 µm의 세 메시, 정사각 셀 한
줄). 단위 높이 셀 한 줄의 띠를 먼저 시험했는데 장 오차가 O(h)였습니다(2.2e-2, 1.0e-2,
5.1e-3, 차수 1.0): 대각선이 한 방향인 구조 메시에서 P1 질량의 Neumann 행은 1D 질량의
제한이 아니어서 y-불변 벡터가 이산 고유벡터가 아니고, 고유함수가 y 방향으로 O(h_y)만큼
변합니다. 정사각 셀이 이 효과를 없앱니다. 전체 직선에서 `int E^2 dx = 1`로 정규화한
정확한 분포에 `sqrt(height)`를 곱해 비교합니다.

| 기준 | 측정(h = 0.044, 0.022, 0.011 µm) | 차수 | 결과 |
|---|---|---|---|
| A1 단위 전력 TE0 장의 정확한 분포 대비 상대 L2 오차, 차수 ≥ 1.8, 최세밀 ≤ 1e-3 | 6.17e-3, 1.48e-3, 3.64e-4 | 2.06, 2.03 | 통과 |
| A2 `1 - eta(수치 TE0, 절점의 정확한 장)`, 차수 ≥ 1.8 | 7.63e-6, 3.02e-7, 1.34e-8 | 4.66, 4.49 | 통과 |
| A3 `eta(TE0, 다음 모드)` ≤ 1e-10(이산 질량 직교성) | 0, 1.2e-34, 2.2e-34 | — | 통과 |
| A4 필름 구속 계수 대 |x| ≤ d/2에서 `E^2`의 `quad`, 차수 ≥ 1.8, 최세밀 ≤ 1e-3 | 6.86e-3, 1.76e-3, 4.46e-4 | 1.96, 1.98 | 통과 |
| A5 Gaussian 입력 `exp(-x^2/w0^2)`, w0 = d: `eta` 대 `quad` 중첩, 최세밀 ≤ 1e-3 | 1.19e-3, 3.14e-4, 8.00e-5 | 1.91, 1.98 | 통과 |

유효굴절률도 함께 수렴합니다(상대 오차 3.1e-3, 7.9e-4, 2.0e-4).

**B. 벡터 slab** (`tests/galerkin/test_slab_modes.py`의 두 셀 폭 띠에 `solve_modes`,
scale 1, 2, 4; TE는 PEC 옆벽, TM은 자기 옆벽).

| 기준 | 측정(scale 1, 2, 4) | 차수 | 결과 |
|---|---|---|---|
| B1 TM: `vector_power`(Faraday 경로) 대 eps 가중 edge 질량의 Ampère 경로 `(omega eps0 / 2 beta) int eps_r |E_t|^2`, 상대 차이, 차수 ≥ 1.8, 최세밀 ≤ 2e-3 | 1.47e-6, 1.12e-7, 7.37e-9 | 3.72, 3.92 | 통과 |
| B1 TE: `grad E_z` 항이 0이므로 두 경로가 ≤ 1e-12로 일치 | 전력 중 `G` 항의 비율 3.61e-9, 1.55e-10, 8.83e-12 | 4.54, 4.13 | **미충족**(최세밀 메시에서 8.8e-12 > 1e-12) |
| B2 서로 다른 모드 `|P_ab| / sqrt(P_a P_b)`, 차수 ≥ 1.8, 최세밀 ≤ 1e-4 | TE 9.8e-17, 5.4e-17, 7.4e-17; TM 1.4e-16, 3.5e-16, 1.8e-15 | 측정 불가(반올림) | 한계는 통과; 아래 참조 |

B1 TE에 대해: 이산 TE 모드는 작지만 0이 아닌 `ez`를 가집니다. x-불변 `E_x`의 Whitney
보간이 정확히 x-불변이 아니고, 둘째 블록 행이 `ez = -(K - k0^2 M)^{-1} G^T et != 0`을 주기
때문입니다. 이 항은 차수 4~4.5로 수렴하는 이산화 양으로 고유값 solver 잡음보다 훨씬
크며, 사용한 최세밀 메시에서 사전 등록된 1e-12 한계에 이르지 못합니다. 테스트는
사후 기준임을 명시하고 항이 수렴한다는 것(차수 ≥ 1.8)만 단언합니다. Ampère 식 자체는
TE에 적용되지 않습니다(`H_z != 0`): Faraday 경로와의 측정 차이 0.2552, 0.2557, 0.2558은
출력하되 기준으로 삼지 않습니다. B2에 대해: 식 절의 항등식에 따라 교차 전력이 정확히
0이므로 한계는 모든 메시에서 충족되고 측정할 수렴 차수가 없습니다. 두 무손실 전력의
허수부는 상대 1e-12 안에서 0입니다.

**C. 계단형 광섬유 HE11** (a = 4 µm, n1 = 1.45, n2 = 1.44, λ = 1.55 µm,
`tests/galerkin/test_fiber_modes.py`의 scale 2 메시, R = 6a; 수치 HE11 쌍은 1e-9까지 퇴화).

| 기준 | 측정 | 결과 |
|---|---|---|
| C1 수치 쌍의 생성 공간으로의 정확한 HE11 장의 `eta` ≥ 1 − 5e-3 | 중심 비교(중심의 정확한 장 대 `centroid_field`, 면적 가중, Gram 사영) 0.998843(1 − eta = 1.16e-3); 보간한 장(`interpolate_vector_field` 뒤 쌍과 `coupling_efficiency`) 0.999987(1 − eta = 1.29e-5); 쌍의 한 구성원만으로는 최대 0.9116 | 통과 |
| C2 코어 구속 계수 대 `eps_r |E|^2`의 조밀 적분(Gamma = 0.874409, 격자 수렴 1e-8) | 0.873395, 차이 1.01e-3(≤ 5e-3) | 통과 |

**D. Gaussian → HE11** (x 편광 `exp(-r^2/w0^2)`, w0 = a, edge 자유도로 보간; 쌍으로의
`eta` 대 두 정확한 편광에 대한 조밀 극좌표 적분): 0.997946 대 0.997924, 차이
2.15e-5(≤ 5e-3), 통과. scale 1과 3에서 차이는 8.2e-5, 1.3e-5였습니다.

**F. 유효 면적.**

| 기준 | 측정 | 차수 | 결과 |
|---|---|---|---|
| F1 x 편광 Gaussian `exp(-r^2/w0^2)`를 `interpolate_vector_field`로 반경 4 w0의 원판 메시(`disk_mesh`, 반경 방향 16, 32, 64 × 방위각 24, 48, 96 분할)에 보간: `effective_area` 대 `pi w0^2`, 상대 오차, 차수 ≥ 1.8, 최세밀 ≤ 1e-3 | 1.33e-2, 3.31e-3, 8.26e-4 | 2.00, 2.00 | 통과 |
| F2 A의 스칼라 slab TE0: `scalar_effective_area / height` 대 `field_te`를 `quad`로 적분한 유효 폭 `(int E^2 dx)^2 / int E^4 dx`(0.299304 µm), 상대 오차, 차수 ≥ 1.8, 최세밀 ≤ 1e-3 | 1.20e-2, 3.07e-3, 7.72e-4 | 1.97, 1.99 | 통과 |
| F3 4차 규칙의 `int |E|^4` 대 6차 규칙, 상대, 한 메시에서 ≤ 1e-12(scale 1 TM slab 모드, `E_t`만과 `E_z` 포함; A의 h = 0.044 µm P1 TE0 장) | 4.3e-15, 6.9e-15, 2.7e-15; 36점 곱 규칙 대비 6.7e-16, 4.7e-15, 4.0e-15 | — | 통과(정확) |
| F4 JAX·PyTorch 값 거부(`TypeError`), 모양 오류, 비유한·영 장(`ValueError`); 척도 불변; 상수 스칼라 장의 `A_eff`는 영역 면적 | 명시대로 | — | 통과 |

보간한 Gaussian의 F1 오차는 Whitney 보간 자체가 `L2`에서 1차인데도 2차로 수렴합니다.
매끄러운 장의 주 보간 오차는 각 삼각형에서 평균이 0이어서 `A_eff`의 두 적분이 모두
`O(h^2)`로만 보기 때문입니다. F3은 두 규칙이 단위 삼각형에서 각자의 차수까지의 모든
단항식을 1e-13 안에서 적분하는지도 확인합니다.

단위 테스트는 세 벡터·두 스칼라 정규화 관례(왕복, 위상 유지), 생성 공간 사영(구성원은
1, 쌍의 선형 결합, 종속 모드 거부), 구속 영역의 마스크·인덱스 형태, 보간이 Whitney
함수와 모자 함수를 정확히 재현함, 모양 오류, JAX·PyTorch 값 거부(라이브러리가 없으면
건너뛰며 backend CI job이 실행)를 다룹니다.

## 한계

- NumPy 전용: 이 적분을 통한 미분은 없고 살아 있는 값은 `TypeError`를 냅니다. 쓰이는
  커널(`assemble_edge_mass`, `assemble_edge_grad`, `assemble_mass`)도 NumPy입니다.
- 전력은 무손실 도파관 정의, 즉 주어진 장의 복소 Poynting 적분의 `Re`입니다. 손실·누설
  모드에서도 그 장의 `+z` 전력이지만 모드가 전력 직교하지 않고 `P`에 무효 허수부가
  생기며 `conj(1/mu_r)`이 중요합니다. 여기서는 PML 후보를 인증하지 않습니다
  ([모드 복소 좌표](modal_coordinates.md)).
- 좌표 인자(PML, 굽힘)를 가진 모드는 계산 좌표의 공변 성분이며, 여기 적분은 늘림을
  되돌리지 않습니다.
- 군속도·에너지 속도 전력, 가져온 측정 장과의 중첩, 중심→edge 사영은 없습니다. 유효
  면적은 위의 `|E|^2`/`|E|^4` 정의이며 비선형 계수 가중(영역별 `n_2`, `chi^(3)`)은
  제공하지 않습니다.
- simcase는 닫힌 창 `em.modes2d` 결과마다 `vector_power`/`scalar_power`,
  `confinement_factor`, `overlap_matrix`와 선택적 Gaussian `coupling_efficiency`를
  저장합니다([모드 후처리](../simcase/overview.md#모드-후처리)). Studio에는 노출되지
  않습니다. simcase 정규화(`"peak"`)는 비교를 위해 재현했을 뿐입니다.
