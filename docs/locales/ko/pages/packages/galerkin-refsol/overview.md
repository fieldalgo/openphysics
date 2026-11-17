# galerkin-refsol — galerkin 검증용 참조해

[English](../../../../../packages/galerkin-refsol/overview.md) | **한국어**

[전체 문서 색인](https://github.com/fieldalgo/openphysics/blob/main/docs/locales/ko/pages/index.md)

[galerkin](../galerkin/overview.md) FEM 엔진의 정답지로 사용하는 폐형식 해와 출판된 고정밀 벤치마크입니다. 같은 모노레포 안의 별도 패키지이며, 평가자는 평가 대상 코드를 import하지 않습니다. numpy와 scipy에만 의존하며, `refsol.bent_slab`만 호출 시 선택적 `mpmath`가 필요합니다.

수치 솔버는 그럴듯하게 틀릴 수 있는 소프트웨어입니다. 이 패키지는 이산화에 의존하지 않는 부분을 담당합니다.

Python 패키지 이름은 `refsol`입니다(`from refsol import fiber`).

## 구성

| 모듈 | 내용 | 자체 검증 |
|---|---|---|
| `refsol.thermoelasticity` | 주어진 Kelvin 온도장의 균일 자유/구속·적합·사인 장, 면외 응력과 물리적 탄성에너지 | 원래 3차원 법칙, FEM import 없음 |
| `refsol.thermal` | Kelvin 슬랩 및 정상 사인 제조해, 열유속 W/m^2와 열원 W/m^3 | 직접 해석 미분, 엔진 import 없음 |
| `refsol.thermal_boundary` | 처방 내향 열유속·Robin 대류를 갖는 정상 슬랩과 사인 장 | 폐형식, 엔진 import 없음 |
| `refsol.transient_heat` | 균일 단열 가열, 이동 affine 장, 사인 제조해, 소형 dense P1 행렬과 후진 Euler 모드 참조 | 해석식과 dense 고유값 문제, 엔진 import 없음 |
| `refsol.thermal_multilayer` | 층별 상수 전도도와 균일 열원을 갖는 적층 벽의 정상 전도: 직렬 슬랩과 동심 복합 원통, 경계면에서 온도와 수직 열유속 연속 | 열원 없는 경계값과 직렬 열저항, 경계면 연속성, 유한차분으로 확인한 Fourier 법칙과 에너지 균형, 교과서 단일 층; 엔진 import 없음 |
| `refsol.transient_heat_multilayer` | 고유함수 급수로 푼 적층 벽의 과도 전도(`LayeredWall`): 정확한 Pruefer 영점 개수에 대한 이분법으로 고유값을 빠뜨리지 않고 구함; 고정 양끝 온도, 주어진 초기 진폭 또는 열원 구동 시작 | 단일 층 사인 급수, 2층 특성 방정식, 독립적인 조밀 유한요소 고유값, c 가중 직교성과 경계면 조건, PDE·경계·초기 잔차, 정상 장시간 극한; 엔진 import 없음 |
| `refsol.elasticity_multilayer` | 완전 접합된 적층 등방 고체의 평면응력/평면변형률: 자유 면을 갖는 축방향 적층판, 균일 축응력 아래의 직렬 막대(횡방향 변형률이 일치할 때만), 압력과 층별 로그 온도 변화를 받는 동심 복합 원통 | 자유 면의 무표면력과 탄성 법칙, Lamé 단일 셸, Timoshenko 열응력, 균일 가열의 무응력, 경계면·경계 조건을 포함한 평형; 엔진 import 없음 |
| `refsol.thermoelastic_traction` | 원래 3D 법칙에서 얻은 열변형률·표면하중 결합 장, 다항 제조해, `traction_from_stress` | NumPy/표준 라이브러리만 사용, 엔진 import 없음 |
| `refsol.elasticity_traction` | 평면응력/평면변형률 단축·전단 장, Cartesian sigma*n과 다항 표면하중 합력 | 폐형식과 직접 미분, FEM import 없음 |
| `refsol.elasticity` | 균질 등방성 평면응력/평면변형률: 아핀 장, 폐형식 응력, 매끄러운 제조해 | 재료 계수, 공학 전단, 독립적인 힘 미분 |
| `refsol.slab` | 대칭/비대칭 평면 유전체 도파로 TE/TM 모드, TE 장 분포 | 차단식 대비 모드 수, 짝수 모드 방정식, 경계면 연속성 |
| `refsol.lossy_slab` | 복소 유전율 다층 슬랩, 공개 값은 `exp(-i omega t)`(전달행렬은 `exp(+i omega t - i beta z)`로 계산하고 한 번 변환): 전달행렬 특성함수, 무손실 `slab` 근에서 연속 추적한 흡수 결합 모드, 외향 sheet의 기판 누설 모드, 장 분포 | 무손실 극한 = `slab`, 정규화 잔차 ≤ 1e-12, 1차 섭동론(TE 구속률, TM 벡터식)과 O(n''^2) 일치, 유한차분 경계면·층 방정식, exp(-2 k0 gamma gap) 터널링률, 경로 무관 연속 추적 |
| `refsol.fiber` | 계단형 굴절률 광섬유: 스칼라 LP 모드(Gloge), 정확한 벡터 TE/TM/HE/EH 모드, 음함수 미분으로 구한 정확한 벡터 군굴절률(`vector_group_index`, 파장에서 고정한 굴절률), 정확한 벡터 모드 장(`vector_mode_field`, 공개 값은 `exp(-i omega t)`: galerkin 커널 틀에서 계산하고 한 번 변환); 키워드 전용 SI 등록부 이름(코어 반경 `radius`, 쌍 (core, cladding)인 `refractive_index`, `vacuum_wavelength`, `points` (Q,2)), 무손실 | Bessel 차단값 대비 LP 개수, 2.4048의 LP11 차단, 약한 도파에서 HE11 ≈ LP01, LP11 군 축퇴, Rudolph–Neumann 근사; Richardson 외삽한 정밀 근 대비 군굴절률(재료 분산은 테스트의 내부 형식으로), 중심차분 대비 잔차 편미분; 근에서 특이한 장 연속 조건, 경계 조건(E_phi, E_z, n^2 E_r), `+i beta E_z`를 쓴 `div E = 0` |
| `refsol.metallic` | 직사각형 도파로 차단(`rect_waveguide_cutoffs(*, box_size, n_max=5, include_tm=False)`, 단면 (a, b)는 m, L3 커밋 11e부터), 직육면체 공진기 공진, 동축 전위·장(`coax_potential(points, *, position, prescribed_electric_potential)`, L3 커밋 10부터 SI 등록부 이름) | 폐형식 |
| `refsol.electrostatics` | 동축선 깊이 1 m당 정전용량 `2 pi eps0 eps_r / ln(b/a)`와 두 층 평행판 직렬 정전용량(`capacitance_per_depth`), 실수·복소 `relative_permittivity`(`exp(-i omega t)`, 손실 `Im >= 0`); 키워드 전용 SI 등록부 이름(반경은 `position`, 층마다 `thickness`와 `relative_permittivity`, `length`); 동축 전위를 재노출 | 폐형식; 평행판은 P1에서 정확 |
| `refsol.cavity` | 주파수 상한까지의 모든 진공 PEC 상자 모드, 편광·기하 축퇴 포함, SI | 독립 Cartesian 열거, 솔버·메시 없음 |
| `refsol.material_cavity` | 균일 충전 또는 손실 유전·자성 판을 넣은 PEC 상자의 복소 공진과 Q(TE/TM-to-z 초월방정식 근), `exp(+j*omega*t)` | 진공 극한 = 직교 좌표 스펙트럼, 같은 두 층 = 균일 축척, 소손실 Q = 에너지 충전율 |
| `refsol.wall_loss` | 직육면체 공동 모드의 벽별 1차 도체 손실 Q, 축퇴 편광 분리, 균일 충전 | Pozar TE101, 유한차분 curl의 수치 적분, 벽별 가법성, sqrt(sigma) 축척 |
| `refsol.scattering` | 원형 원통의 평면파 산란: PEC(TM/TE)와 유전체, 부분파 급수, 산란 폭(m); 적힌 그대로 `exp(-i omega t)`(변환 없음); `points` 다음 키워드 전용 SI 등록부 이름(`vacuum_angular_wavenumber`, 원통 반경 `radius`, `refractive_index`, `kind`, `terms`) | 1e-9까지 경계조건 만족, 경계면 연속성, 기하광학 극한; 외향 `exp(+i k r)`, `Im n >= 0`이면 흡수 `>= 0` |
| `refsol.bimetal` | Timoshenko (1925) 바이메탈 온도계: 힘·모멘트 평형에서 얻은 곡률, 출판된 폐형식(Timoshenko, Villarceau, 단축 Stoney 극한), 끝면 표면하중을 포함한 정확한 평면응력 띠 장 | 무작위 데이터에서 세 폐형식 일치, Stoney 극한, 단면 힘·모멘트 0, 계면 연속, 유한차분 변형률 |
| `refsol.thermal_convection` | NAFEMS T4 직사각형(뜨거운 변, 단열 변, 대류 변 둘): 변수분리 급수와 출처를 적은 출판 목표값 18.3 °C(`nafems_t4()`·`nafems_t4_target()`가 SI K로 읽음) | 고유값 방정식, 유한차분 Laplace·Fourier, Robin·단열·뜨거운 변 조건, 기하급수 수렴, 선형성 |
| `refsol.joule_slab` | 고정 전위·온도 사이의 `sigma = sigma0 (1 + alpha (T - T0))` 정상 1D Joule 가열: erf/erfi 폐형식(`voltage_driven`), 상수 전도도 극한, 금속형 fold 양쪽의 전류 구동 상태(`current_driven`, `fold_current`), 유계 전도도 모델용 온도 범위 | 적분한 보존 법칙(`J = -sigma V'`, `k (T'(0) - T'(x)) = J (V_a - V(x))`), 모듈 자체 도함수의 수치 적분, 유한차분, 상수 sigma 폐형식으로의 O(alpha) 접근, 대칭·반사, 전력 평형, 1매개변수 대칭 방정식 |
| `refsol.bent_slab` | 복소 차수 Bessel/Hankel 정합(안쪽 `J`, 필름 `J`/`Y`, 외향 `H^(2)`)으로 구한 일정 반경 굽은 슬랩 극점, 안쪽 반경 기준 `n_eff`, 공개 값은 `exp(-i omega t)`(`exp(+i omega t)`로 정합하고 한 번 변환); 호출 시 선택적 `mpmath` 필요 | 잔차 ≤ 1e-12, 1/R 1차의 직선 슬랩 극한(Richardson), 큰 반경에서 초지수적으로 사라지는 손실, 반경이 줄수록 커지는 손실, TM보다 잘 구속되는 TE, mpmath 없이는 ImportError |
| `refsol.thermal3d` | 정상 3D 열전도: 상자의 사인 곱 제조해(온도·열유속·열원)와 z 방향 층상 슬랩의 직렬 전도 | 유한차분 대비 열유속·열원, 직렬 저항 공식 대비 슬랩, NumPy만 |
| `refsol.benchmarks` | Hadley (2002) 리브 도파로 n_eff 표(±3e-6), 유전체 모서리 사례(±1e-8), 완전한 형상 명세; 비공개 모듈에 출판된 그대로 두고 `rib_waveguides()`, `rib_neff(*, thickness)`, `dielectric_corners()`로 SI로 읽음 | — |

## 사용법

주어진 온도장의 기계 단계 참조장에는 `refsol.thermoelasticity`를 명시적으로 import하세요. 좌표/변위는 m, T와 Tref는 절대 K, 부호 있는 alpha는 1/K, E/응력은 Pa, 에너지 밀도는 J/m^3입니다. 원래 3D 탄성법칙이 평면변형률의 면외 응력과 에너지를 보존합니다. 자유 균일 평면변형률 장은 면내 응력이 0이어도 에너지가 0이 아닐 수 있습니다. 이 모듈은 sdist와 wheel에 자동 포함되며 byte 검사를 받습니다. 열 방정식을 풀거나 순차 열–기계 흐름을 인증하지 않습니다.

정상 열전도에는 `refsol.thermal`을 명시적으로 import하세요. `slab`은 m 좌표, Kelvin, 열전도율 W/(m K)에 대한 온도·열유속·열원을 반환합니다. 경계하중 탄성에는 `refsol.elasticity_traction`을 명시적으로 import하세요. 표면하중 벡터는 전역 Cartesian Pa, 적분한 기계 하중은 면외 두께당 N/m입니다. 두 모듈은 Python 코드로 sdist와 wheel에 자동 포함됩니다. 설치 배포 검사는 byte와 공개 import를 검증합니다. 이들은 연성 열탄성 모델을 구현하지 않습니다.

정적 2D 탄성에는 `refsol.elasticity`를 명시적으로 import하세요. 좌표·변위는 m, E·응력은 Pa, 체적력은 N/m^3이며, 변형률 순서는 공학 전단을 쓰는 `(epsilon_xx, epsilon_yy, gamma_xy)`입니다. 예를 들어 평면응력에서 횡방향 표면하중이 자유인 단축 신장은 다음과 같습니다.

```python
from refsol.elasticity import affine

field = affine([[0., 0.], [1., 1.]],
               displacement_gradient=[[1e-3, 0.], [0., -0.3e-3]], displacement=(0., 0.),
               youngs_modulus=70e9, poisson_ratio=0.3, plane="stress")
print(field.displacement)  # metres
print(field.stress)        # [70e6, 0, 0] Pa at each point (up to roundoff)
```

참조 모듈은 sdist와 wheel 모두에 포함되며 FEM 엔진을 import하지 않습니다. 별도의 [엔진 계약](../galerkin/elasticity2d.md)은 경계 구속, 두께당 하중, 잠김 한계를 설명합니다.

```python
from refsol import fiber, slab, lossy_slab, scattering, benchmarks

# exact HE11 effective index of a step-index fiber: core radius 4 um, indices (core, cladding), lengths in m
n_eff = fiber.fundamental_neff(radius=4e-6, refractive_index=(1.45, 1.44), vacuum_wavelength=1.55e-6)

# all guided TE modes of a 220 nm SOI slab: layers (substrate, film, cover), lengths in m
slab.modes(refractive_index=(1.444, 3.48, 1.444), thickness=0.22e-6, vacuum_wavelength=1.55e-6, pol="TE")

# complex TE0 of the same slab with an absorbing film n = 3.48 + 0.01i (exp(-i omega t): Im n_eff > 0)
lossy_slab.three_layer_modes(refractive_index=(1.444, 3.48 + 0.01j, 1.444), thickness=0.22e-6,
                             vacuum_wavelength=1.55e-6, pol="TE")[0]

# substrate-leaky TE0: 0.22 um film over a 0.25 um low-index gap on silicon, outgoing sheet;
# layers (cover, film, gap material, substrate), thickness the pair (film, gap)
lossy_slab.substrate_leaky_mode(refractive_index=(1.444, 3.48, 1.444, 3.48), thickness=(0.22e-6, 0.25e-6),
                                vacuum_wavelength=1.55e-6)

# scattered field of a PEC cylinder of radius 1 um at k0 = 3.14 rad/um, at points (Q, 2) in m
u_s = scattering.scattered(points, vacuum_angular_wavenumber=3.14e6, radius=1e-6, kind="pec_tm")

# published reference: quasi-TE n_eff of the Hadley rib waveguide, slab thickness 0.3 um
benchmarks.rib_neff(thickness=0.3e-6)   # 3.412492
```

`refsol.lossy_slab`은 복소 유전율 평면 다층 구조를 풉니다. 공개 값은 `exp(-i omega t)`를 따릅니다(galerkin 단계, L3 커밋 11c). 수동 재료는 `Im eps >= 0`(굴절률 `n' + i n''`), 감쇠하는 모드는 `Im n_eff > 0`입니다. 전달행렬은 galerkin 모드 커널의 `exp(+i omega t - i beta z)` 규약으로 그대로 계산하고, 각 함수가 복소 입력을 `refsol._conventions.to_kernel`로 한 번 변환하고 결과의 켤레(`to_public`)를 돌려줍니다. 그래서 아래 sheet 규칙은 그 내부 규약으로 적혀 있고, 공개 쪽에서는 `Im`의 부호가 반대입니다. 함수는 키워드 전용 SI 등록부 이름을 받습니다. `relative_permittivity`(층마다), `thickness`(내부 층마다, m), `vacuum_wavelength`(m), `effective_index`, `target_effective_index`, `refractive_index`(`three_layer_modes`와 `substrate_leaky_mode`의 층), `mode_count`, `mode_index`, `subdivision_count`, `relative_tolerance`, `iteration_limit`입니다. 길이는 `k0 d`로만 들어가므로 어떤 일관된 척도든 같은 지수를 줍니다. `characteristic`은 영점이 모드인 해석적 전달행렬 함수이고, `solve`는 초기값을 다듬은 뒤(실수부·허수부에 대한 scipy root, 이어서 복소 Newton) 정규화 잔차가 `1e-12`를 넘는 결과를 거부하며, `continued_root`는 구조 경로를 따라 근을 추적합니다. `three_layer_modes`는 흡수 슬랩의 모든 모드를 무손실 `slab` 근에서 감쇠 sheet(`Im Q <= 0`, 외부 장 감쇠)로 출발시키고, `substrate_leaky_mode`는 고립 슬랩의 결합 모드에서 출발해 고굴절률 기판까지 간격을 줄이며 외향 sheet(`Re Q >= 0`; 누설 모드는 `Im Q_sub > 0`로 횡방향으로 커지는 부적절(improper) 기판 장을 가지며, 복소 좌표 PML 솔버가 수렴하는 극점)에서 풉니다. `field`는 `E_y`(TE) 또는 `H_y`(TM)를 반환합니다. 자체 검증은 무손실 극한을 `slab`과, 소손실 극한을 1차 섭동론과(`n'' = 1e-3`에서 `Im n_eff` 상대오차 2.6e-8, `1e-4`에서 100배 감소), 장을 경계면·층 방정식과, 누설률을 터널링 법칙 `exp(-2 k0 gamma gap)`과 비교합니다. `tests/galerkin/test_lossy_slab_modes.py`는 닫힌 띠(흡수 필름)와 복소 좌표 PML(누설 슬랩)에서 galerkin 스칼라·벡터 솔버를 이 근과 대조합니다. 복소 오차는 2차로(가장 미세한 쌍에서 차수 1.97–2.00) 0.01 um 간격에서 3.9e-4–6.8e-4까지 줄고, `Im n_eff`는 상대적으로 3e-4(TE), 4e-3(TM) 이내로 일치합니다.

`refsol.thermal_boundary`는 처방 내향 열유속과 Robin 경계의 독립 폐형식을 제공합니다. 좌표는 m, 온도는 K, 열전도율은 W/(m K), 내향 열유속은 W/m^2(양수가 몸체로 들어감), 대류 h는 W/(m^2 K)입니다.

galerkin 단계(L2 커밋 6)부터 열 정답(`refsol.thermal`, `thermal3d`, `thermal_boundary`, `thermal_convection`, `thermal_multilayer`, `transient_heat`, `transient_heat_multilayer`, `transient_heat_robin`)은 앞의 `points` 다음에 registry 이름의 키워드 전용 SI 인자를 받고 차원 있는 기본값이 없습니다: `thermal_conductivity`, `prescribed_temperature`(두 끝의 쌍), `heat_source_density`, `inward_heat_flux`, `position`(첫 면을 포함한 층 경계), `time`, `initial_temperature`, `temperature_difference`. 필드도 같은 이름입니다. 문자열 값은 `TypeError`입니다. °C로 출판된 NAFEMS T4 데이터는 비공개 모듈에 출판된 그대로 두고 읽을 때 켈빈으로 바꿉니다.

L2 커밋 8부터 역학 정답(`refsol.elasticity`, `elasticity_traction`, `elasticity_multilayer`, `thermoelasticity`, `thermoelastic_traction`, `bimetal`)도 앞의 `points`(표면하중이면 `normals`까지) 다음에 같은 방식으로 받습니다: `youngs_modulus`, `poisson_ratio`, `plane`, `linear_expansion_coefficient`, `stress_free_temperature`, `temperature`, `temperature_change`, `temperature_gradient`, `displacement`, `displacement_gradient`, `strain`, `stress`, `stress_xx`, `stress_xy`, `strain_xx`, `gauge_pressure`(안/밖 쌍), `position`(첫 면 또는 안쪽 반지름을 포함한 층 경계), `thickness`(층마다 하나), `length`. 이전 기본값은 호출하는 쪽이 적고, 필드는 registry 이름(`stress_zz`, `strain_zz`, `strain_energy_density`, `body_force_density`, `displacement_gradient`, `strain_yy` 등)을 씁니다.

`refsol.transient_heat`는 `uniform_insulated`, `moving_affine`, `sine_manufactured`, 소형 dense `p1_matrices`, `smallest_dirichlet_mode`, `backward_euler_amplitude`를 제공합니다. 좌표·시간·온도는 m/s/K, 열전도율은 W/(m K), 체적열용량은 J/(m³ K), source는 W/m³, flux는 W/m²입니다. Dense 행렬과 mode는 작은 참조 메시용이며 semidiscrete 후진 Euler product는 연속체 PDE 해와 구분합니다. 이 참조는 물리 온도 유효성이나 최대 원리를 인증하지 않습니다. 과도 엔진은 galerkin [과도 열전도 계약](../galerkin/transient_heat.md)에 설명돼 있습니다.

`refsol.thermoelastic_traction`는 원래 3D 구성 법칙의 `uniform_combined`, `polynomial_manufactured`, `parent_state`, `traction_from_stress`를 제공합니다. 좌표·변위는 m, 온도는 K, 응력·전체 표면하중은 Pa, 체적력은 N/m^3, 힘·반력은 N/m, 물리적 에너지는 J/m입니다. 처방 온도장 기계 참조이며 열 해석이나 출처 인증이 아닙니다.

`refsol.bent_slab`(선택적, `python -m pip install mpmath`)은 일정 반경 굽은 슬랩을 풉니다. 클래딩 사이의 필름 `R <= r <= R + d`를 복소 차수 `nu = k0 R n_eff`의 Bessel·Hankel 함수(안쪽 `J`, 필름 `J`/`Y`, `exp(+i omega t)`에서 외향 `H^(2)`)로 정합하므로 `n_eff`는 galerkin 굽힘 솔버처럼 안쪽 반경 `R` 기준입니다. `mode`는 직선 `slab` 근에서 secant 반복을 시작하고 정규화 `residual`이 `1e-12` 이하일 때만 극점을 받아들입니다. `mpmath`는 함수 호출 시 import되며 없으면 그 이름을 담은 `ImportError`를 내므로 `import refsol`과 나머지 패키지는 없이도 동작합니다. `refractive_index`(반경이 커지는 순서의 영역 `(클래딩, 필름, 클래딩)`), `thickness`, `bend_radius`, `vacuum_wavelength`, `effective_index`, `target_effective_index`, `mode_index`, `relative_tolerance`를 받고, 공개 값은 `exp(-i omega t)`를 따릅니다(L3 커밋 11c). 위의 정합은 `exp(+i omega t)`로 하고 결과의 켤레를 한 번 취합니다. 자체 검증은 `mpmath`가 없으면 건너뛰며 잔차, `Im n_eff > 0`, 1/R 1차의 직선 슬랩 극한(R = 40/80 um 값의 Richardson 외삽이 3.9e-3 이동에 대해 5.8e-6까지 직선 근을 회복), 큰 반경에서 초지수적으로 사라지는 손실과 반경이 줄수록 커지는 손실을 확인합니다. 극점은 같은 방정식으로 galerkin 굽힘 솔버를 평가하는 `tests/galerkin/test_pml_modes.py`의 독립 oracle과 일치합니다.

`refsol.joule_slab`은 고정 면 전위·온도를 갖는 슬랩 `0 <= x <= L`에서 결합 정상 방정식 `(sigma(T) V')' = 0`, `k T'' + sigma(T) V'^2 = 0`을 galerkin `ConductivityModel` 콜백이 평가하는 형태의 선형 등방 모델 `sigma = sigma0 (1 + alpha (T - T0))`로 풉니다. 단위는 SI(m, K, V, S/m, W/(m K), A/m^2)입니다. 함수는 레지스트리 이름의 keyword-only 인수를 받습니다: `length`, 면 쌍 `prescribed_electric_potential`과 `prescribed_temperature`, `reference_conductivity`(sigma0), `conductivity_temperature_coefficient`(alpha), `reference_temperature`(T0), `thermal_conductivity`, 그리고 `current_driven`에는 `current_density`와 `prescribed_electric_potential`(V(0), 필수). `str`은 `TypeError`입니다. `alpha > 0`은 온도와 함께 증가하는 전도도, `alpha < 0`은 금속형, `alpha = 0`은 포물선형 상수 전도도 폐형식입니다. `u = sigma/sigma0`으로 열 방정식은 `u'' = -c/u`, `c = alpha J^2/(k sigma0)`이 되고, 그 1차 적분이 축척한 기울기의 `erf`(`alpha > 0`) 또는 `erfi`(`alpha < 0`)로 `u`와 `x`를 폐형식으로 줍니다. 전압 강하가 `J`와 무관하게 양쪽 면 기울기를 정하므로 `voltage_driven`은 명시적이며, 거의 선형인 해가 overflow하지 않도록 `erfcx`/`dawsn`으로 평가합니다. `current_driven`은 주어진 `J`를 흐르게 하는 강하를 찾고, `alpha < 0`에서는 전류–전압 곡선이 `fold_current`에서 접히며 두 가지 모두 얻을 수 있습니다. 각 `JouleSlab`은 입력을 같은 이름으로 담고, x 좌표 `points`에서 `temperature`, `temperature_gradient`, `heat_flux`, `electric_potential`, `electric_field`, `electrical_conductivity`, `joule_power_density`를 계산하며, `current_density`, 비공개 `_joule_power`(면 넓이당, `J (V_a - V_b) = k (T'(0) - T'(L))`; 레지스트리 이름이 없어 규칙 R(2)), 유계 모델이 포함해야 하는 구간 `temperature_range`를 담습니다. `tests/galerkin/test_joule_slab_reference.py`는 1 m x 0.25 m 직사각형에서 `solve_temperature_joule_heat`(Picard, 완화 1)를 평가합니다. 3점 삼각형 공식의 RMS 온도 오차는 2차로(차수 2.00–2.02) 32셀에서 3.5e-4, 4.1e-4 K(`alpha = 0.5` /K, 2 V, 대칭 및 300/304 K 면)와 2.1e-3, 2.0e-3 K(`alpha = -0.004` /K, 5 V)까지 줄고, 소산 전력은 상대 1.9e-4 이내이며, `alpha = 0` 실행은 상수 전도도 폐형식과 일치합니다.

모든 참조 모듈은 sdist와 wheel에 포함됩니다. 어느 모듈도 연성 모델을 구현하지 않으며, 독립 수용 시험은 자체 기대값을 도출합니다.

## 자체 검증 실행

```bash
# From the repository root
python -m pip install pytest -e packages/galerkin-refsol
python -m pytest -q tests/refsol
```

## galerkin에서 사용

```bash
# From the repository root
python -m pip install -e packages/galerkin-refsol
```

벡터 모드 솔버의 권장 검증 순서는 계단형 굴절률 광섬유(정확해이므로 수렴률 측정 가능) → Hadley 유전체 모서리(±1e-8, 구조화 메시로 충분) → Hadley 리브 도파로(±3e-6, 비구조 메시 필요)입니다.

각 모듈은 자기 자신과 비교하는 대신 차단조건·극한·경계조건 등 독립적인 물리와 구현을 대조하는 시험을 포함합니다. 따라서 통과한 참조해를 다른 솔버의 평가자로 신뢰할 수 있습니다.

## 규약

- 시간 의존성은 `exp(-i omega t)`이며 입사 평면파는 +x로 진행합니다.
- 길이는 SI 등록부 이름 아래 미터입니다(galerkin 단계). 도파로와 산란 참조해는 k0와 길이의 곱에만 의존하므로, 다른 일관된 척도로 쓴 문제도 같은 굴절률과 장을 줍니다.
- 유효 굴절률은 `n_eff = beta / k0`입니다.
- `refsol.lossy_slab`과 `refsol.bent_slab`은 galerkin의 공개 모드 함수처럼 `exp(-i omega t)`를 따릅니다(galerkin 단계, L3 커밋 11c): 수동 `Im eps >= 0`, 감쇠 또는 복사하는 모드 `Im n_eff > 0`. 식은 `exp(+i omega t)`로 적혀 있고 `refsol._conventions`에서 한 번 변환합니다. 이를 모드 커널(exp(+i omega t))과 비교하는 galerkin 테스트는 비교할 때 켤레를 한 번 취합니다.
- `refsol.fiber.vector_mode_field`는 `exp(-i omega t)`를 따릅니다(galerkin 단계, L3 커밋 11d): 전방 모드는 `exp(i (beta z - omega t))`로 변하므로 `dEx/dx + dEy/dy + i beta E_z = 0`입니다. 장은 galerkin 커널 틀 `exp(+i omega t - i beta z)`에서 계산하고 `refsol._conventions`에서 한 번 변환합니다. 이를 모드 커널과 비교하는 테스트는 비교할 때 켤레를 한 번 취합니다. 광섬유의 다른 값은 실수입니다.
- `refsol.material_cavity`는 galerkin 공진기 커널처럼 `exp(+i omega t)`를 씁니다: 수동 `Im eps <= 0`, 감쇠 공진 `Im omega > 0`. 변환은 복소 공액입니다.
- `refsol.electrostatics`는 galerkin의 공개 정전기처럼 `exp(-i omega t)`를 따릅니다(galerkin 단계, L3 커밋 10): 수동 `Im eps_r >= 0`이면 `Im C >= 0`입니다. 폐형식은 두 규약에서 같은 식이므로 아무것도 변환하지 않습니다.

## 참고문헌

- D. Gloge, "Weakly guiding fibers," Appl. Opt. 10, 2252 (1971).
- A. W. Snyder and J. D. Love, *Optical Waveguide Theory* (Chapman & Hall, 1983).
- K. Okamoto, *Fundamentals of Optical Waveguides*, 2nd ed. (Academic Press, 2006).
- G. R. Hadley, "High-accuracy finite-difference equations for dielectric waveguide analysis II: dielectric corners," J. Lightwave Technol. 20, 1210 (2002).
- D. Marcuse, *Theory of Dielectric Optical Waveguides* (Academic Press, 1974).
- J. Hu and C. R. Menyuk, "Understanding leaky modes: slab waveguide revisited,"
  Adv. Opt. Photon. 1, 58 (2009).
- W. C. Chew, *Waves and Fields in Inhomogeneous Media* (IEEE Press, 1995).
- D. Marcuse, "Curvature loss formula for optical fibers," J. Opt. Soc. Am. 66, 216 (1976).
- K. R. Hiremath, M. Hammer, R. Stoffer, L. Prkna and J. Čtyroký, "Analytic approach to
  dielectric optical bent slab waveguides," Opt. Quantum Electron. 37, 37 (2005).
- H. S. Carslaw and J. C. Jaeger, *Conduction of Heat in Solids*, 2nd ed. (Oxford, 1959).
- A. C. Fowler, I. Frigaard and S. D. Howison, "Temperature surges in current-limiting
  circuit devices," SIAM J. Appl. Math. 52, 998 (1992).
- 벤치마크 수치는 Hadley의 출판 결과이며 femwell 프로젝트 벤치마크 문서(GPL-3.0)의 같은 표와 교차 확인했습니다. 수치만 재현했으며 NOTICE를 참조하세요.

## 라이선스

Apache License 2.0 — [LICENSE](../../../../../../packages/galerkin-refsol/LICENSE), [NOTICE](../../../../../../packages/galerkin-refsol/NOTICE)를 참조하세요.

Copyright 2026 Yongha Kim (FieldAlgo)

`refsol.benchmarks`가 읽는 벤치마크 수치는 Hadley (2002)가 출판한 수치 결과이고, `refsol.thermal_convection`의 NAFEMS T4 목표값은 출판된 벤치마크 수치입니다. 출처는 [NOTICE](../../../../../../packages/galerkin-refsol/NOTICE)를 참조하세요.
