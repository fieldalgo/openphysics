# 도파관 정식화: 모드, 미분, 연성, SI/PI 경로

[English](../../../../../packages/galerkin/waveguide_formulation.md) | **한국어**

[galerkin 개요](overview.md) · [이론·수치 방법](../../theory/index.md) · [전자기 경로](../../physics/electromagnetics.md)

이 문서는 도파관 단면 솔버를 수학으로 읽습니다. 어떤 방정식을 어떤 요소로
이산화하는지, 고유값이 무엇인지, 유효굴절률과 그 미분을 어떻게 복원하는지,
그리고 신호·전원 무결성 패키지 `sipi`가 같은 엔진 위에서 어디서 다른 길을
가는지를 다룹니다. 모든 수식은 코드가 구현한 대로 적고 모듈과 함수를 옆에
둡니다. 부호, 정규화, 분지(branch) 선택은 교과서가 아니라 구현된 것입니다.
규범 계약, 한계, 측정된 검증은 링크된 문서에 남아 있습니다. 이 문서는 새로운
정확도 주장이나 검증 결과를 추가하지 않습니다.

## 1. 문제 설정과 표기

z 방향으로 변하지 않는 도파관은 다음 형태의 장을 전파합니다.

    E(x, y, z, t) = [E_t(x, y) + zhat E_z(x, y)] exp(+i omega t - i beta z)

(`packages/galerkin/src/galerkin/waveguide.py` 모듈 docstring; 같은 phasor를
[흡수 모드](../simcase/lossy_modes.md)와 [모드 복소 좌표](modal_coordinates.md)가
명시합니다). 단면 Omega는 P1 삼각형으로 메시된 2D 영역(`galerkin.mesh.Mesh`)이고,
길이는 메시 길이 단위, `k0`는 그 역단위입니다. 원천 없는 Maxwell 방정식은

    curl ( mu_r^-1 curl E ) - k0^2 eps_r E = 0,     grad = grad_t - i beta zhat

로 줄어듭니다.

| 기호 | 의미 | 코드에서 |
|---|---|---|
| `E_t`, `E_z` | 한 모드의 횡·종방향 전기장 | `et`(`E_t`의 edge 선적분), `ez`와 `E_z = 1j * ez` (`waveguide.py::solve_modes`) |
| `eps_r` | 상대 유전율, 스칼라 또는 삼각형당 하나, 실수 또는 복소수 | `solve_modes`, `assemble_mode_system`의 `eps_r`; simcase의 `eps_tri` |
| `mu_r` | 상대 투자율, 스칼라 또는 삼각형당, 실수 또는 복소수; `1/mu_r`로만 들어감 | `mu_r`(기본 1.0); `waveguide.py::_mode_blocks`의 `inv_mu` |
| `k0 = 2 pi / lambda0` | 진공 파수, 메시 길이의 역단위 | `k0`; simcase는 메시를 파장으로 나누고 `k0 = 2 pi`를 넘김 (`simcase/physics_em_modes2d.py::_solve_vector`) |
| `beta` | z 방향 전파상수 | `beta = k0 * n_eff` |
| `n_eff = beta / k0` | 유효굴절률, 실수 또는 복소수 | `solve_modes`의 첫 반환값 `n_eff` |
| `e_t = beta E_t`, `e_z = -i E_z` | 혼합 정식화의 스케일된 미지수 | pencil 벡터 `x = [beta * et; ez]` |
| `lambda = -beta^2` | pencil `A x = lambda B x`의 고유값 | `waveguide.py::_live_modes`의 `lam0 = -(k0 n_eff)^2` |
| `sigma = -(k0 n_target)^2`, `nu = 1 / (lambda - sigma)` | shift-invert 목표와 ARPACK이 실제로 반환하는 고유값 | `waveguide.py::_solve_modes_numpy`의 `sigma`, `nu` |
| `(s_x, s_y, h)` | 두 횡축의 복소 좌표 늘림과 굽힘 metric, 삼각형당 한 쌍 | `coordinate_factors` (T, 3), `mode_coordinates.py::mode_coordinates`가 생성 |
| `phi` | scalar 근사의 절점(nodal) 모드 함수 | `physics_em_modes2d.solve(formulation="scalar")`의 `fields` |

이 phasor에서 수동(passive)은 `Im eps_r <= 0`, `Im mu_r <= 0`이고, 수동 순방향
모드는 `Im n_eff < 0`입니다(4절). `n + i k`로 쓴 재료표는 solver에 닿기 전에
simcase 문서 runner가 한 번만 공액을 취합니다
(`simcase/runner.py::_solve_in_micrometres`: `np.conjugate(eps)`).

## 2. Scalar P1 모드 고유값 문제

Scalar 근사는 장 성분 하나 `phi(x, y)`와 단면의 Helmholtz 방정식만 남깁니다.

    div_t grad_t phi + (k0^2 eps_r - beta^2) phi = 0.

P1 시험함수 `w`를 곱해 Omega에서 적분하고 Laplacian을 부분적분하면 약형식

    k0^2 int eps_r phi w - int grad phi . grad w = beta^2 int phi w

가 되고, 아무것도 처방하지 않은 곳에서 자연 경계항 `int_Gamma w (d phi / d n)`은
떨어집니다. P1 모자 함수로 `phi = sum_j phi_j N_j`를 쓰면 일반화 고유값 문제

    (k0^2 M_eps - K) phi = beta^2 M phi

가 되며, `packages/simcase/src/simcase/physics_em_modes2d.py::solve`
(`formulation="scalar"`)가 galerkin 조립 함수로 구현합니다.

| 행렬 | 적분 | 조립 |
|---|---|---|
| `K` | `int grad N_i . grad N_j` | `galerkin.assembly.assemble_stiffness(mesh, 1.0)` → `core/kernels.py::p1_stiffness`, 요소 행렬 `(b_i b_j + c_i c_j) / (4 A)` |
| `M` | `int N_i N_j` | `assemble_mass(mesh, 1.0)` → `kernels.p1_mass`, 정확한 `A/12 [[2,1,1],[1,2,1],[1,1,2]]` |
| `M_eps` | `int eps_r N_i N_j` | 삼각형별 유전율로 `assemble_mass(mesh, eps_tri)` |

경계조건은 메시의 이름 있는 변마다 둡니다. `"pec"`는 그 변의 절점을 미지수에서
제거하고(`phi = 0`, TE slab 편광의 전기벽 조건), `"pmc"`는 자유롭게 두어 약형식의
자연 Neumann 조건이 됩니다. Scalar 경로는 그 외를 지원하지 않습니다.

풀이는 자유 절점에 대한 SciPy 일반화 shift-invert Arnoldi입니다. 실수 유전율에는
`eigsh`, 복소수에는 `eigs`를 쓰고, 질량행렬 `M`을 `M` 인자로, 목표는
`sigma = (k0 n_target)^2` 또는 `n_target`이 없으면
`(k0 max sqrt(Re eps_r))^2`, 고유쌍 수는 `k = min(num_modes, free - 2)`입니다. 그 뒤

- `n_eff = sqrt(lambda) / k0`. 실수 문제에서는 음의 `lambda`를 0으로 잘라 제곱근을
  취하고, 복소 문제에서는 NumPy 주제곱근(`Re >= 0`)을 취하며, 모드는 `Re n_eff`
  내림차순으로 정렬합니다.
- `guided = Re n_eff > sqrt(min Re eps_r)`는 가장 낮은 재료 굴절률에 대한 후보
  플래그이며, 구속의 증명이 아닙니다.
- 각 장은 `|phi|`가 가장 큰 절점의 계수로 나누어 그 피크가 정확히 `1`이 되게
  합니다(복소 장은 거기서 임의 위상을 잃습니다). 진폭은 상대값이며 단위 전력이
  아닙니다.

Scalar 방정식은 한 횡축으로 불변인 slab의 TE 편광에서 정확하고, 진짜 2차원
고대비 코어에서는 근사입니다. 거기서는 벡터 모드를 가르지 못합니다
([단계별 검증](milestone_validation.md)의 광섬유 비교는 분해된 TE01/TM01/HE21
세 모드에 대해 LP11 하나를 보여 줍니다). 4절의 저수준 scalar 좌표 솔버
(`galerkin.mode_coordinates.solve_scalar_coordinates`)는 같은 방정식을 늘린
계수로 풉니다.

Scalar 경로에는 자체 고유값 추적이 없습니다. 파장 스윕과 그 overlap/배정 규칙은
simcase에 있으며 [흡수 모드](../simcase/lossy_modes.md)와
[부분공간 추적](../simcase/vector_subspace_tracking.md)에 설명되어 있습니다.
벡터 솔버의 고유공간 규칙은 [고유공간 신뢰성](eigenspace_reliability.md)에 있습니다.

**닫힌 도파관의 차단 문제.** 유전체 도파관 전에, PEC 도파관의 차단 파수
`curl curl E = k_c^2 E`, `n x E = 0`은 edge 요소만으로 `S e = k_c^2 M_t e`로 풉니다
(`examples/galerkin/waveguide_modes.py::solve_nedelec`, 행렬은
`galerkin.edge.assemble_curlcurl`과 `assemble_edge_mass`). 같은 예제는 의도적으로
벡터 P1 절점 요소로도 이산화해 edge 요소가 제거하는 가짜(spurious) 고유값을
보여 줍니다. 기록은 [단계별 검증](milestone_validation.md)에 있습니다.

## 3. Full-vector 혼합 Nédélec/절점 정식화

**공간과 스케일된 미지수.** 유전체 경계면을 가로질러 `E_t`는 접선 성분만
연속이고 `E_z`는 연속이므로, 두 성분은 다른 공간에 둡니다(Lee, Sun, Cendes 1991;
Jin 2014 도파관 장).

- `e_t = beta E_t`는 H(curl)에, 최저차 Nédélec(Whitney) edge 요소
  `W_ij = lambda_i grad lambda_j - lambda_j grad lambda_i`로 두며, 자유도는 방향
  있는 edge를 따른 선적분입니다. 전역 방향은 낮은 절점 번호에서 높은 번호로이고
  삼각형별 부호를 둡니다(`packages/galerkin/src/galerkin/core/spaces.py::EdgeSpace`,
  국소 edge `e`는 절점 `e`의 맞은편, `TRI_LOCAL_EDGES = ((1, 2), (2, 0), (0, 1))`).
- `e_z = -i E_z`는 H1에, 메시의 P1 절점 요소로 둡니다.

`grad = grad_t - i beta zhat`로 ansatz의 curl은

    curl E = zhat curl_t E_t - zhat x (grad_t E_z + i beta E_t)
           = (1/beta) zhat curl_t e_t - i zhat x (grad_t e_z + e_t)

입니다. 스케일링이 횡방향 curl에서 `beta`를 밖으로 빼고, `-i`는 실수 모드에서
종방향 미지수를 실수로 만들어, 결과 pencil은 실수 재료에서 실수 행렬의
전치대칭(transpose-symmetric) pencil이 됩니다.

**약형식과 행렬.** curl-curl 방정식을 같은 두 공간의 `exp(+i beta z)`를 가진
시험장과 짝지으면(실수 재료에서는 에너지 형식, 복소 재료에서는 공액 없는 전치
짝짓기), `beta^2`를 곱해

    [ S(1/mu) - k0^2 Mt(eps) ] e_t + beta^2 [ Mt(1/mu) e_t + G(1/mu) e_z ]           = 0
                                   beta^2 [ G(1/mu)^T e_t + K(1/mu) e_z - k0^2 M(eps) e_z ] = 0,

즉 `x = [e_t; e_z]`에 대해 `A x = -beta^2 B x`,

    A = [ S - k0^2 Mt_eps   0 ]        B = [ Mt_mu   G            ]
        [ 0                 0 ]            [ G^T     K - k0^2 M   ]

입니다. `waveguide.py::assemble_mode_system`이 `waveguide.py::_mode_blocks`로부터
정확히 이 블록을 (`sp.bmat`) 만듭니다.

| 블록 | 적분 | 커널 (`galerkin/core/kernels.py`) | 공개 조립 함수 |
|---|---|---|---|
| `S` | `int (1/mu_r) curl W_e curl W_f` | `nedelec_curlcurl`; `curl W_ij = 2 grad lambda_i x grad lambda_j`는 삼각형에서 상수이므로 적분이 정확 | `galerkin.edge.assemble_curlcurl` |
| `Mt_eps` | `int eps_r W_e . W_f` | `nedelec_mass`, edge 중점 3점 규칙, 2차 피적분함수에 정확 | `assemble_edge_mass` |
| `Mt_mu` | `int (1/mu_r) W_e . W_f` | `nedelec_mass` | `assemble_edge_mass` |
| `G` | `int (1/mu_r) W_e . grad N_n`, 행 edge, 열 절점 | `nedelec_grad`, 닫힌 형식 `(A/3)(grad lambda_j - grad lambda_i) . grad lambda_k` | `assemble_edge_grad` |
| `K` | `int (1/mu_r) grad N_m . grad N_n` | `p1_stiffness` | `galerkin.assembly.assemble_stiffness` |
| `M` | `int eps_r N_m N_n` | `p1_mass` | `assemble_mass` |

두 번째 행에는 `beta^2`가 없는 항이 없으므로 `A`의 `e_z` 블록은 0입니다.
curl-curl 방정식의 약한 종방향 성분은 제약식이고, `beta^2 = 0`은 자유 절점 수
정도의 중복도를 가진 고유값(이산 gradient)입니다. 도파 모드는 그로부터 멀리
`n_clad < Re n_eff < n_core`에 있고, `n_target` 근처의 shift-invert 탐색은 이
무리를 만나지 않습니다. 혼합 쌍이 가짜 모드를 억제하는 방식이 바로 이것입니다.
curl의 핵이 edge 공간에서 정확히 표현되어 `beta^2 = 0`에 모여 있고, 절점 벡터
요소처럼 스펙트럼 전체에 번지지 않습니다
(`examples/galerkin/waveguide_modes.py::solve_nodal`).

`A`와 `B`는 전치대칭입니다. 실수 `eps_r`, `mu_r`에서는 실대칭이고 `B`는
부정부호(indefinite)이며, 복소 재료나 좌표 인자에서는 복소대칭이고 Hermitian이
아닙니다(`waveguide.py` docstring).

**경계조건.** PEC 벽 `n x E = 0`은 두 종류의 자유도를 0으로 고정합니다
(`waveguide.py::_free_dofs`). `pec_nodes`(기본: 모든 이름 있는 경계의 모든 절점)의
`e_z` 값과 `pec_edges`의 `e_t` 선적분입니다. 기본 `pec_edges`는 삼각형 하나만이
소유하고 두 끝점이 모두 `pec_nodes`에 있는 edge입니다
(`core/spaces.py::EdgeSpace.boundary_edge_ids`; 소속은 위상으로 결정하므로 두 경계
절점을 잇는 모서리 대각선은 구속하지 않습니다). 명시적 `pec_edges`로 혼합 벽을
둘 수 있습니다. PEC 모서리 절점을 가진 한 edge짜리 PMC 벽이 그 예입니다. PMC 벽은
자연 조건입니다. 제약이 없고, 약하게 `n x (mu_r^-1 curl E) = 0`을 뜻합니다.
자유 자유도 pencil은 `A[free][:, free]`, `B[free][:, free]`입니다. simcase는
`boundary = {side: "pec" | "pmc"}`를 `mesh.boundary`, `mesh.boundary_edges`로부터
`pec_nodes`와 `pec_edges`로 옮깁니다(`physics_em_modes2d.py::_solve_vector`).

**고유값 풀이.** `B`가 부정부호이므로 양의 준정부호 질량행렬을 요구하는 SciPy
일반화 ARPACK 드라이버는 쓰지 않습니다. 대신 shift-invert 연산자를 만들어 표준
고유값 문제로 넘깁니다(`waveguide.py::_solve_modes_numpy`).

    sigma = -(k0 n_target)^2,    (A - sigma B)의 LU   (scipy.sparse.linalg.splu),
    op(v) = (A - sigma B)^-1 B v,     eigs(op, k=num_modes, which="LM", v0=ones),
    lambda = sigma + 1/nu,    beta^2 = -lambda.

`ncv = min(n, max(4 num_modes, 40))`, `maxiter = 20000`, 재현성을 위한 고정 시작
벡터입니다. 실수 문제에서는 고유값을 실수로 취하고 `beta^2 > 0`만 남겨
`beta^2` 내림차순으로 정렬하며 `beta = sqrt(beta^2)`입니다. `n_eff`는 float64
배열이 됩니다. 복소 분지는 4절에 있습니다.

**반환값과 정규화.** 남긴 각 고유벡터 `v`(ARPACK은 자유 자유도에서 2-노름 1인
벡터를 반환)에 대해

1. 절댓값이 가장 큰 성분으로 위상을 고정합니다. `v <- v conj(p)/|p|`이므로 그
   성분은 실수 양수가 됩니다. 실수 벡터는 음의 pivot을 포함해 정확히 실수로
   남습니다.
2. `x`는 모든 자유도로 되돌린 벡터입니다(PEC 자유도는 0).
3. `et[i] = x[:n_e] / beta`는 `E_t`의 edge 선적분, `ez[i] = x[n_e:]`이고 물리
   `E_z = 1j * ez[i]`입니다.
4. `n_eff[i] = beta / k0`.

두 계수 배열은 실수 pencil에서도 complex128이어서, 축퇴 고유공간에 대해 반환된
복소 기저가 모든 방향을 유지합니다. 고유벡터를 섞거나 실수화하지 않습니다
([고유공간 신뢰성](eigenspace_reliability.md)). 진폭은 임의이며 단위 전력이
아닙니다. 24 x 24 정사각 코어 도파관에서 재구성한 `x = [k0 n_eff et; ez]`는
`||x_free||_2 = 1`(1e-12), 실수 양수 pivot, 자유 자유도 pencil 잔차 1e-15를
보였습니다. 문서의 항등식은 코드가 하는 일 그대로입니다.
`galerkin.edge.eval_edge_field(space, et[i])`는 삼각형 중심에서
`sum_e sign_e et_e W_e(centroid)`로 `E_t`를 평가합니다.

**simcase 래퍼**(`physics_em_modes2d.py::_solve_vector`)는 메시를 파장으로 나누어
`k0 = 2 pi`로 풀고, `n_target`(주어지지 않으면 최대 재료 굴절률)에서
`max(2 num_modes, 6)`개 후보를 요청한 뒤, `n_clad < Re n_eff < n_core`를 남기거나
`n_target`에 가장 가까운 후보를 남깁니다. 둘 다 필터이며 완전성 진술이 아닙니다.
각 모드는 중심점 `|E|` 최댓값이 `1`이 되게 정규화하고, 횡방향 선적분은 파장을
곱해 되돌리며, `E_z = 1j * ez`를 `VectorField`(`simcase/fields.py`)에 저장합니다.
`physics_em_modes2d.vector_pencil_residuals`는 저장된 장에서 자유 자유도의
`||A x + beta^2 B x|| / (||A x|| + |beta^2| ||B x||)`를 다시 계산합니다. 스윕과
PML 계약이 의존하는 진단입니다.

## 4. 복소 재료와 PML

**복소 `eps_r`와 `mu_r`.** 둘 다 같은 여섯 블록에 들어갑니다. `eps_r`는 `Mt_eps`와
`M`에, `1/mu_r`는 `S`, `Mt_mu`, `G`, `K`에 들어갑니다(`_mode_blocks`). 2D edge
커널은 복소 스칼라, 삼각형별, `(T, 2, 2)` 텐서 계수를 받습니다(3D edge 커널은
받지 않음, `kernels._real_coefficient`). 허수부가 하나라도 0이 아니거나 좌표 인자가
주어지면 복소 분지로 전환합니다(`_solve_modes_numpy`의 `complex_problem`). 무손실
입력은 먼저 실수부로 줄여 실수 재료 경로를 그대로 둡니다. `exp(+i omega t)`에서
수동은 `Im eps_r <= 0`, `Im mu_r <= 0`입니다. `solve_modes`는 유한성만 검사하고,
simcase는 `Im eps > 0`을 거부합니다("passive modes use Im eps <= 0"). 이득 매질은
지원하지 않습니다. 채워진 PEC 도파관은 곱 `eps_r mu_r`만 보므로
`tests/galerkin/test_mode_gradients.py::test_complex_mu_matches_the_closed_form`은
이를 이용해 복소 `mu_r` 경로를 복소 `eps_r` 경로와 대조합니다.

**손실 근의 분지와 순서.** `beta^2 = -(sigma + 1/nu)`에서 코드는
`beta = sqrt(beta^2)`를 NumPy 복소 주제곱근으로 취합니다. `Re beta >= 0`이고 분지
절단은 음의 실수축이므로, 음의 실수축 바로 아래의 `beta^2`는 4사분면으로 갑니다.
`beta`가 유한하고 `Re beta > 0`인 후보를 남기고, `Re beta` 내림차순, 같으면
`Im beta` 오름차순으로 정렬합니다(`np.lexsort((beta.imag, -beta.real))`). 수동
순방향 모드에서는 `Im n_eff < 0`이 됩니다. 3절의 정사각 코어 도파관에
`eps_core = 2.25 - 0.01i`를 주면 `Im n_eff = -3.35e-3`이 나오며, 이는 5절의 1차
값 `(d n_eff / d eps_core) Im eps_core`와도 같습니다. 진폭은 `a = -Im beta`로
`exp(-a z)`, 전력은 `exp(-2 a z)`로 감쇠합니다. dB/cm 변환은
[흡수 모드](../simcase/lossy_modes.md)에 있습니다. 좌표 인자가 있으면 모든 후보를
남기고 비유한 또는 0인 근은 오류이므로, 호출자가 모든 후보와 제외 사유를 기록할
수 있습니다.

**복소 좌표 늘림으로서의 PML.** 열린 단면은 횡좌표를 복소 평면으로 늘려
절단합니다(분리장 층은 Bérenger 1994; 여기서 쓰는 늘린 좌표 형식은 Chew,
Weedon 1994). `galerkin.mode_coordinates.mode_coordinates`는 두께가 주어진 최대
네 PML 띠를 가진 직사각 메시에서, 축 `q`와 띠 안 깊이 `d`에 대해

    s_q = 1 - i strength (d / thickness)^order,         order는 {2, 3, 4},
    q~  = q - i sign strength thickness/(order+1) (d / thickness)^(order+1)

를 삼각형 중심에서 정의합니다. 띠 밖에서는 `s_q = 1`, `q~ = q`입니다. 일정 반경
굽힘은 선택한 바깥 축의 metric `h = 1 + (q~_axis - bend_origin) / R`을 더하고
(직선 도파관은 `h = 1`), 전파 거리는 기준 호 길이 `z = R theta`입니다. 인자는
대각 Jacobian `J = diag(s_x, s_y, h)`입니다. `+x`로 나가는 파 `exp(-i k_x x~)`에서
`Im x~ < 0`이면 파가 감쇠하므로 `exp(+i omega t)` phasor와 일관됩니다.

늘린 문제는 재료를 `eps' = eps det(J) J^-1 J^-T`, `mu' = mu det(J) J^-1 J^-T`로
바꾼 원래 문제입니다(Teixeira, Chew 1998). 대각 `J`에서는

    eps'  = eps  diag( s_y h / s_x,  s_x h / s_y,  s_x s_y / h ),
    1/mu' = (1/mu) diag( s_x / (s_y h),  s_y / (s_x h),  h / (s_x s_y) ).

`_mode_blocks`는 횡방향 curl이 요구하는 자리에 이 성분을 둡니다. `S`는
`(1/mu')_zz = (1/mu) h/(s_x s_y)`, `Mt_eps`는 텐서 `(eps'_xx, eps'_yy)`, `Mt_mu`,
`G`, `K`는 텐서 `((1/mu')_yy, (1/mu')_xx)`를 씁니다. `zhat x`가 축을 돌리므로 두
횡성분이 뒤바뀝니다. `M`은 `eps'_zz`를 씁니다. 투자율도 함께 변환하며 흡수
유전율만 쓰는 것이 아닙니다. 반환된 `et`, `ez`는 계산 좌표의 공변 성분입니다.
PML 밖의 물리 종방향 장은 `1j * ez / h`이고, simcase 후보 솔버는 중심점 성분을
`(s_x, s_y, h)`로 나눕니다(`simcase/physics_pml_modes.py::solve`). Scalar 대응
(`mode_coordinates.scalar_coordinate_system`)은

    A = k0^2 M(eps h s_x s_y) - K(diag(h s_y / s_x, h s_x / s_y)),   B = M(s_x s_y / h),   A u = beta^2 B u

이며 `solve_scalar_coordinates`가 shift `(k0 n_target)^2`로 풀어
`n_eff = sqrt(beta^2)/k0`(주제곱근)를 실수부 내림차순으로 정렬합니다.

**흡수 모드 계약.** PML pencil은 복소대칭이며 비Hermitian입니다. 스펙트럼에는
물리 모드 옆에 인공 층 모드가 있고, 유한 창과 shift는 구속도 완전성도 증명하지
않습니다. 따라서 `solve_modes`는 임의 진폭의 후보를 반환합니다. simcase 계약
([PML·누설·굽힘 모드](../simcase/pml_modes.md))은 탐색한 모든 후보를 기록하고,
`Re n_eff > 0`, pencil 잔차 `<= 1e-8`, 양의 L2 진단의 물리 창 비율
`>= min_physical_fraction`(기본 0.1), `Im n_eff <= 1e-10 max(1, |Re n_eff|)`인
후보만 받습니다. 그 문턱 아래의 크기는 `numerically_unresolved`로 표시하며 0으로
자르지 않습니다. PML 바깥 면은 PEC여야 하고, 재료는 층을 관통해 연장해야 하며,
메시·물리 창·두께·강도를 독립적으로 바꿔야 합니다. 단일 실행은
`stability: "not_checked"`를 보고합니다. 전체 감쇠는 흡수와 방사를 합한 것입니다.

`galerkin.pml.radial_pml_coeffs`의 원통 PML은 주파수 영역 산란 솔버(M2.5)에
속하며 나가는 파 `exp(+i k r~)`, 즉 `exp(-i omega t)` phasor로 쓰여
`s = 1 + i sigma(r)/k`입니다(Collino, Monk 1998). 모드 솔버는 쓰지 않습니다. 그
계수를 모드 좌표 인자와 섞지 마세요.

## 5. n_eff와 장의 미분

`solve_modes`는 `eps_r`, `mu_r`, `k0`에 JAX 또는 PyTorch 값을 받습니다
([미분](differentiation.md)). 3절의 NumPy 고유값 풀이가 먼저 숫자로 실행됩니다.
그 뒤 자유 자유도에서 반환된 각 단순 고유쌍 `(lambda0, x0)`,
`lambda0 = -(k0 n_eff)^2`, `x0 = [beta et; ez]`에 대해 `waveguide.py::_live_modes`가
같은 커널로 live 라이브러리에서 `A`, `B`를 다시 만들고(`_live_blocks`,
`_restricted`) `galerkin.core.eigen.refine`을 호출합니다. 정규화 `x^T B x = 1`
(전치, 공액 없음)로 테두리를 친 고유값 문제의 Newton 한 단계입니다.

    [x; lambda] = [x0; lambda0] - J^-1 F,
    J = [[A - lambda0 B, -B x0], [-x0^T B, 0]],   F = [(A - lambda0 B) x0, (1 - x0^T B x0)/2].

`x0`는 먼저 `x0^T B x0 = 1`로 다시 스케일합니다(NumPy 풀이는 `||x0||_2 = 1`로
둡니다). 테두리 시스템은 `galerkin.core.solve`의 adjoint 희소 LU로 풉니다
(JAX `custom_vjp`, PyTorch `autograd.Function`). 값은 NumPy 풀이의 잔차 안에서
그대로이고, 미분은 실수·복소 pencil 모두에서 정확한 암시적 미분입니다
(테두리 고유쌍 미분은 Andrew, Chu, Lancaster 1993).

고유값만 보면 이 단계는 전치대칭 pencil의 단순 고유값에 대한 Hellmann–Feynman
식입니다. 좌고유벡터가 `x` 자신이므로

    d lambda = x^T (dA - lambda dB) x / (x^T B x),

`k0` 고정에서 `n_eff = sqrt(-lambda)/k0`이므로
`d n_eff = -d lambda / (2 k0^2 n_eff)`입니다. 삼각형 집합 `omega`의 유전율에 대해
`dA/d eps = -k0^2 Mt_omega(1)`, `dB/d eps = -k0^2 M_omega(1)`이므로

    d n_eff / d eps_omega = ( e_t^T Mt_omega e_t + beta^2 e_z^T M_omega e_z ) / ( 2 n_eff x^T B x ),

즉 pencil 자체의 정규화(질량 정규화 벡터에서 `x^T B x = 1`)에서 섭동 영역의
`E_t.E_t + E_z.E_z` 적분이라는 익숙한 섭동 공식입니다. 정사각 코어 도파관의 NumPy
풀이에서 계산하면 `solve_modes`의 중심차분과 상대 7e-11로 일치합니다. live 경로는
이 형식에 묶이지 않습니다. 테두리 단계가 장의 미분도 함께 주기 때문입니다.
`k0`에 대해서는 `dA/dk0 = -2 k0 Mt_eps`, `dB/dk0 = -2 k0 M`이고 `k0`로 나누는 것이
`-n_eff/k0`를 더합니다.

단계 후 반환 gauge를 다시 적용합니다. NumPy 풀이가 실수 양수로 남긴 성분을 pivot
`p`로 택해(`waveguide.py::_pivot`, 여러 성분이 같은 크기면 위상이 0인 것)

    x <- x conj(x_p) / ( |x_p| ||x||_2 ),    beta = sqrt(-lambda),    et = x_t / beta,    ez = x_z,

실수 문제에서는 `n_eff = Re beta / k0`, 그 외에는 `beta / k0`입니다. 장의 미분은
이 gauge를 따릅니다. gauge에 무관한 양(overlap 크기, `|E_z|^2/|E_t|^2`, live
`dofs`로 `eval_edge_field`를 통과한 `|E_t|^2`의 가중 비율)은 gauge에 무관한 미분을
가집니다.

중복 고유값은 `J`를 특이하게 만듭니다. `core/eigen.py::degenerate_modes`는 반환된
각 고유값을 다른 반환값과, 그리고 전체 자유 pencil의 가장 가까운 고유값과
비교합니다(`neighbour_gap`: 300 자유도까지는 밀집 `eigvals`, 그 이상은 `lambda0`
근처 두 고유값에 대한 shift-invert Arnoldi). 상대 간격
`<= DEGENERATE_GAP = 1e-8`이면 그 모드는 정확한 값, NaN 미분,
`DegenerateModeWarning`을 받습니다. `n_target`은 모드 선택만 하며 미분이 없습니다.
`coordinate_factors`, 메시 기하, PEC 집합은 구조입니다. `assemble_mode_system`은
live 값을 거부합니다. 검사 목록은 [미분](differentiation.md#검증),
`tests/galerkin/test_mode_gradients.py`에 있습니다.

## 6. 연성: 모드 풀이에서 무엇이 나가는가

`galerkin.coupling`([계약](coupling.md))은 커널 사이에서 `Field`를 옮깁니다. 2D P1
`Mesh`의 절점 또는 삼각형당 실수 float64 값 하나, 기록된 SI 단위, 메시
`MeshSignature`에 결속됩니다. `transfer`는 같은 메시에서 항등이고 `OneWayChain`은
단방향 단계를 순서대로 돌립니다.

모드 결과는 `Field`가 아니며 어댑터도 없습니다.

- `et`는 edge(Nédélec 공간)에 살고, 연성 층은 이를 제외합니다.
- 손실 또는 PML 문제의 `et`, `ez`, `n_eff`는 복소수이고 `Field`는 복소 값을
  거부합니다.
- 진폭이 상대값이어서 기록할 SI 단위가 없습니다.
- JAX·PyTorch 배열은 `Field`가 거부합니다(장이 미분을 끊기 때문).

호출자가 다른 물리에 넘길 수 있는 것은 스스로 유도한 실수 절점·요소 양입니다.
예를 들어 `eval_edge_field`와 `1j * ez`의 중심점 평균에서 삼각형별 `|E|^2`를 만들어
물리 전력으로 스케일하고 `Field(mesh, values, location="element", unit=...)`로
단위와 함께 선언합니다. 열 솔버용 전자기 흡수 열원은 제공하지 않습니다. 기존
단방향 체인은 전기→열, 열→기계입니다. simcase는 모드 장을 3절의 최대 크기
정규화로 자체 `VectorField`에 두고, 복소 NPZ 배열과 실수/허수 JSON 목록으로
저장합니다([흡수 모드](../simcase/lossy_modes.md)).

## 7. SI/PI 경로: `sipi`의 준정적 단면

[`sipi`](../sipi/overview.md)는 같은 엔진으로 PCB 단면을 해석하지만 모드 솔버는
쓰지 않습니다. galerkin에서 쓰는 것은 다음과 같습니다.

| sipi 모듈 | galerkin 구성요소 |
|---|---|
| `sipi/crosssection.py` (`CrossSection.mesh`) | meshine 삼각분할에 대한 `galerkin.Mesh`, `galerkin.from_mesher` |
| `sipi/quasistatic.py::capacitance_matrix` | `galerkin.assemble_stiffness`(실수 또는 복소 `eps_r`의 P1 `K`), `galerkin.solve_dirichlet` |
| `sipi/conductor.py` (표면 임피던스 손실) | 완전도체 외부장에 대한 `assemble_stiffness`, `solve_dirichlet` |
| `sipi/conductor_diffusion.py` (DC/AC 전류 확산) | P1 `A_z` 확산 시스템의 `assemble_stiffness`, `assemble_mass`, `assemble_load` |
| `sipi/plane.py` (전원면 IR drop) | `galerkin.electric.solve_steady_electric` |

edge 요소도, `solve_modes`도, `k0`도 없습니다. 선로를 준-TEM(단면이 파장보다
작음)으로 가정하므로 횡방향 장은 전위의 gradient이고 2차원 문제는 정전 문제입니다
(Paul 2008, 단위 길이당 파라미터).

    div ( eps grad V ) = 0  도체 밖,   V = 1 도체 j,   V = 0 나머지 도체와 접지,

상자의 `"open"` 변은 절연(자연 조건, 법선 D 0), `"ground"` 변은 0 V입니다. 이산
에너지가 Maxwell 정전용량 행렬

    C_ij = eps0 V_i^T K V_j,     C = (C + C^T)/2

를 주며, 이는 각 도체에서 잔차 `K V`로 읽은 전하와 같습니다. `C0`는 모든
`eps_r = 1`로 풀이를 반복하고, `L = mu0 eps0 C0^-1`입니다. 손실 층은
`eps_r (1 - j tan_delta)`로 들어가고(`sipi/quasistatic.py::line_parameters`; 모드
솔버와 같은 `exp(+j omega t)` 의미에서 수동 `Im eps_r <= 0`), 풀린 행렬은
`C - j C_loss`, `G(f) = 2 pi f C_loss`입니다. 유도되는 단위 길이당 양
(`LineParameters`): `z0 = sqrt(L/C)`, `eps_eff = C/C0`, 위상속도
`c/sqrt(eps_eff)`, 지연, `loss_tangent = C_loss/C`, 대칭 쌍의 even/odd 임피던스,
모드 분해 `(L C) v = v/u^2`와 모드별 `eps_eff = (c/u)^2`. 도체 저항은 완전도체 장의
별도 표면 임피던스 섭동([도체 손실](../sipi/conductor.md)) 또는 도체 그룹당
종방향 장 상수 하나를 가진 명시적 P1 `A_z` 확산 풀이
([전류 확산](../sipi/conductor_diffusion.md))입니다.

두 경로가 갈라지는 곳:

- 모드 솔버는 주어진 `k0`에서 full-wave pencil의 고유값으로 `beta`를 찾습니다.
  SI/PI 경로는 정적 행렬에서 준-TEM 모드별 `beta = omega sqrt(L C)`를 취하며,
  차단도 `E_z`도 기하에 의한 분산도 없습니다.
- 모드 솔버의 유전 손실은 한 고유쌍의 `Im n_eff`입니다. SI/PI 경로는 이를 `G`로
  옮기며, 상수 `tan_delta`에서 주파수에 선형입니다.
- PEC 벽은 모드 창을 경계 짓는 모델의 일부이지만, `sipi`의 `"open"` 벽은
  절연체이고 그 절단 오차는 벽을 움직여 확인해야 합니다.
- `sipi`는 `assemble_stiffness`와 `solve_dirichlet`를 통해 NumPy 전용이고 이들은
  live 값을 거부합니다. 5절의 미분 장치는 여기 닿지 않습니다.

공유하는 것: P1 강성 커널 `kernels.p1_stiffness`, 메시 계약과 `from_mesher`, 복소
유전율의 수동 부호.

## 8. 검증 포인터와 한계

측정된 근거는 아래 문서에 있습니다. 이 문서는 그 수치를 되풀이하지 않습니다.

- [단계별 검증](milestone_validation.md): M3-prep 차단과 절점 가짜 모드 시연,
  정확한 벡터 분산 관계에 대한 step-index 광섬유, slab 극한
- [고유공간 신뢰성](eigenspace_reliability.md): 축퇴 쌍, 전기 L2 Gram, 독립
  해석적 장 oracle
- [미분](differentiation.md#검증): `n_eff`, `et`, `ez`의 닫힌 형식·중심차분
  gradient 검사와 축퇴 규칙
- [흡수 모드](../simcase/lossy_modes.md)와 [PML·누설·굽힘 모드](../simcase/pml_modes.md):
  복소 slab 근, 금속 경계면, 나가는 slab과 굽힘 기준해, PML/창 변화
- [모드 복소 좌표](modal_coordinates.md)와 [scikit-fem 비교](../../reference-comparisons.md):
  직선·굽힘 pencil의 독립 조립과 밀집 QZ
- `tests/galerkin/test_fiber_modes.py`, `test_slab_modes.py`,
  `test_pml_modes.py`, `test_crosscheck_skfem_pml_modes.py`,
  `test_eigenspace_reliability.py`, `test_mode_gradients.py`;
  `tests/simcase/test_lossy_modes.py`, `test_pml_contract.py`,
  `test_vector.py`, `test_vector_sweep.py`
- 준정적 경로의 [sipi 검증](../sipi/overview.md#검증)

구현된 정식화의 한계:

- 2차원 단면만 다룹니다. 재료는 삼각형별 등방 스칼라이고, 모드 솔버가 만드는
  유일한 텐서 계수는 대각 PML/굽힘 계수입니다. 비등방 사용자 입력과 이득 매질은
  없습니다.
- 닫힌 도파관 풀이는 모두 PEC 창이 절단하며 그 위치는 모델의 일부입니다. PML
  후보는 메시·창·두께·강도를 바꿔 보기 전까지 heuristic입니다. 감쇠는 전체값이며
  흡수와 방사로 나뉘지 않습니다.
- 장은 상대 진폭입니다. 전력 정규화, 직교성·완전성 보장, 축퇴 쌍 안의 정체성
  배정이 없습니다.
- 미분은 `eps_r`, `mu_r`, `k0`에 대해서만 있습니다. 좌표, PML 파라미터, `n_target`,
  절점 위치, PEC 집합에 대해서는 없고 `Field`를 통과하지도 않습니다.
- Scalar 경로는 불변 축 TE slab 편광에서만 정확합니다.
- `sipi`는 준정적이고 비자성(`L`에서 `mu = mu0`)이며 full-wave 분산이 없고, 단위
  길이당 손실 모델은 모드 솔버의 복소 `n_eff`와 별개입니다.

## 참고문헌

- J.-M. Jin, *The Finite Element Method in Electromagnetics*, 3rd ed.,
  Wiley-IEEE Press, 2014: 벡터 요소, 도파관 고유값 문제, PML의 비등방 매질 형식.
- J.-F. Lee, D.-K. Sun, Z. J. Cendes, "Full-wave analysis of dielectric
  waveguides using tangential vector finite elements," *IEEE Trans. Microwave
  Theory Tech.* 39(8), 1991: `beta` 스케일 횡방향 미지수를 가진 혼합 edge/절점
  정식화.
- J.-C. Nédélec, "Mixed finite elements in R³," *Numer. Math.* 35, 1980;
  A. Bossavit, *Computational Electromagnetism*, Academic Press, 1998: Whitney
  edge 요소와 절점 벡터 요소가 가짜 모드를 만드는 이유.
- J.-P. Bérenger, "A perfectly matched layer for the absorption of
  electromagnetic waves," *J. Comput. Phys.* 114, 1994; W. C. Chew, W. H. Weedon,
  "A 3D perfectly matched medium from modified Maxwell's equations with
  stretched coordinates," *Microwave Opt. Technol. Lett.* 7(13), 1994;
  F. L. Teixeira, W. C. Chew, "General closed-form PML constitutive tensors to
  match arbitrary bianisotropic and dispersive linear media," *IEEE Microwave
  Guided Wave Lett.* 8(6), 1998: 늘린 좌표 PML과 그 재료 텐서.
- F. Collino, P. Monk, "The perfectly matched layer in curvilinear coordinates,"
  *SIAM J. Sci. Comput.* 19(6), 1998: `galerkin.pml`의 원통 PML.
- A. W. Snyder, J. D. Love, *Optical Waveguide Theory*, Chapman and Hall, 1983:
  유효굴절률 섭동 적분과 손실의 부호.
- A. L. Andrew, K.-W. E. Chu, P. Lancaster, "Derivatives of eigenvalues and
  eigenvectors of matrix functions," *SIAM J. Matrix Anal. Appl.* 14(4), 1993:
  고유쌍 미분의 테두리 시스템.
- R. B. Lehoucq, D. C. Sorensen, C. Yang, *ARPACK Users' Guide*, SIAM, 1998:
  `scipy.sparse.linalg.eigs`로 쓰는 shift-invert Arnoldi.
- C. R. Paul, *Analysis of Multiconductor Transmission Lines*, 2nd ed., Wiley,
  2008: 준-TEM 단위 길이당 파라미터.
