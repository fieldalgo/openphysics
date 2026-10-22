# galerkin-refsol — galerkin 검증용 참조해

[English](../../../../../packages/galerkin-refsol/overview.md) | **한국어**

[전체 문서 색인](https://github.com/fieldalgo/openphysics/blob/main/docs/locales/ko/pages/index.md)

[galerkin](../galerkin/overview.md) FEM 엔진의 정답지로 사용하는 폐형식 해와 출판된 고정밀 벤치마크입니다. 같은 모노레포 안의 별도 패키지이며, 평가자는 평가 대상 코드를 import하지 않습니다. numpy와 scipy에만 의존합니다.

수치 솔버는 그럴듯하게 틀릴 수 있는 소프트웨어입니다. 이 패키지는 이산화에 의존하지 않는 부분을 담당합니다.

Python 패키지 이름은 `refsol`입니다(`from refsol import fiber`).

## 구성

| 모듈 | 내용 | 자체 검증 |
|---|---|---|
| `refsol.thermoelasticity` | 주어진 Kelvin 온도장의 균일 자유/구속·적합·사인 장, 면외 응력과 물리적 탄성에너지 | 원래 3차원 법칙, FEM import 없음 |
| `refsol.thermal` | Kelvin 슬랩 및 정상 사인 제조해, 열유속 W/m^2와 열원 W/m^3 | 직접 해석 미분, 엔진 import 없음 |
| `refsol.thermal_boundary` | 처방 외향 열유속·Robin 대류를 갖는 정상 슬랩과 사인 장 | 폐형식, 엔진 import 없음 |
| `refsol.transient_heat` | 균일 단열 가열, 이동 affine 장, 사인 제조해, 소형 dense P1 행렬과 후진 Euler 모드 참조 | 해석식과 dense 고유값 문제, 엔진 import 없음 |
| `refsol.thermoelastic_traction` | 원래 3D 법칙에서 얻은 열변형률·표면하중 결합 장, 다항 제조해, `traction_from_stress` | NumPy/표준 라이브러리만 사용, 엔진 import 없음 |
| `refsol.elasticity_traction` | 평면응력/평면변형률 단축·전단 장, Cartesian sigma*n과 다항 표면하중 합력 | 폐형식과 직접 미분, FEM import 없음 |
| `refsol.elasticity` | 균질 등방성 평면응력/평면변형률: 아핀 장, 폐형식 응력, 매끄러운 제조해 | 재료 계수, 공학 전단, 독립적인 힘 미분 |
| `refsol.slab` | 대칭/비대칭 평면 유전체 도파로 TE/TM 모드, TE 장 분포 | 차단식 대비 모드 수, 짝수 모드 방정식, 경계면 연속성 |
| `refsol.fiber` | 계단형 굴절률 광섬유: 스칼라 LP 모드(Gloge), 정확한 벡터 TE/TM/HE/EH 모드, 음함수 미분으로 구한 정확한 벡터 군굴절률(`vector_group_index`, 재료 분산 선택), 정확한 벡터 모드 장(`vector_mode_field`) | Bessel 차단값 대비 LP 개수, 2.4048의 LP11 차단, 약한 도파에서 HE11 ≈ LP01, LP11 군 축퇴, Rudolph–Neumann 근사; Richardson 외삽한 정밀 근 대비 군굴절률, 중심차분 대비 잔차 편미분; 근에서 특이한 장 연속 조건, 경계 조건(E_phi, E_z, n^2 E_r) |
| `refsol.metallic` | 직사각형 도파로 차단, 직육면체 공진기 공진, 동축 전위·장 | 폐형식 |
| `refsol.cavity` | 주파수 상한까지의 모든 진공 PEC 상자 모드, 편광·기하 축퇴 포함, SI | 독립 Cartesian 열거, 솔버·메시 없음 |
| `refsol.material_cavity` | 균일 충전 또는 손실 유전·자성 판을 넣은 PEC 상자의 복소 공진과 Q(TE/TM-to-z 초월방정식 근), `exp(+j*omega*t)` | 진공 극한 = 직교 좌표 스펙트럼, 같은 두 층 = 균일 축척, 소손실 Q = 에너지 충전율 |
| `refsol.wall_loss` | 직육면체 공동 모드의 벽별 1차 도체 손실 Q, 축퇴 편광 분리, 균일 충전 | Pozar TE101, 유한차분 curl의 수치 적분, 벽별 가법성, sqrt(sigma) 축척 |
| `refsol.scattering` | 원형 원통의 평면파 산란: PEC(TM/TE)와 유전체, 부분파 급수, 산란 폭 | 1e-9까지 경계조건 만족, 경계면 연속성, 기하광학 극한 |
| `refsol.bimetal` | Timoshenko (1925) 바이메탈 온도계: 힘·모멘트 평형에서 얻은 곡률, 출판된 폐형식(Timoshenko, Villarceau, 단축 Stoney 극한), 끝면 표면하중을 포함한 정확한 평면응력 띠 장 | 무작위 데이터에서 세 폐형식 일치, Stoney 극한, 단면 힘·모멘트 0, 계면 연속, 유한차분 변형률 |
| `refsol.thermal_convection` | NAFEMS T4 직사각형(뜨거운 변, 단열 변, 대류 변 둘): 변수분리 급수와 출처를 적은 출판 목표값 18.3 °C | 고유값 방정식, 유한차분 Laplace·Fourier, Robin·단열·뜨거운 변 조건, 기하급수 수렴, 선형성 |
| `refsol.benchmarks` | Hadley (2002) 리브 도파로 n_eff 표(±3e-6), 유전체 모서리 사례(±1e-8), 완전한 형상 명세 | — |

## 사용법

주어진 온도장의 기계 단계 참조장에는 `refsol.thermoelasticity`를 명시적으로 import하세요. 좌표/변위는 m, T와 Tref는 절대 K, 부호 있는 alpha는 1/K, E/응력은 Pa, 에너지 밀도는 J/m^3입니다. 원래 3D 탄성법칙이 평면변형률의 면외 응력과 에너지를 보존합니다. 자유 균일 평면변형률 장은 면내 응력이 0이어도 에너지가 0이 아닐 수 있습니다. 이 모듈은 sdist와 wheel에 자동 포함되며 byte 검사를 받습니다. 열 방정식을 풀거나 순차 열–기계 흐름을 인증하지 않습니다.

정상 열전도에는 `refsol.thermal`을 명시적으로 import하세요. `slab`은 m 좌표, Kelvin, 열전도율 W/(m K)에 대한 온도·열유속·열원을 반환합니다. 경계하중 탄성에는 `refsol.elasticity_traction`을 명시적으로 import하세요. 표면하중 벡터는 전역 Cartesian Pa, 적분한 기계 하중은 면외 두께당 N/m입니다. 두 모듈은 Python 코드로 sdist와 wheel에 자동 포함됩니다. 설치 배포 검사는 byte와 공개 import를 검증합니다. 이들은 연성 열탄성 모델을 구현하지 않습니다.

정적 2D 탄성에는 `refsol.elasticity`를 명시적으로 import하세요. 좌표·변위는 m, E·응력은 Pa, 체적력은 N/m^3이며, 변형률 순서는 공학 전단을 쓰는 `(epsilon_xx, epsilon_yy, gamma_xy)`입니다. 예를 들어 평면응력에서 횡방향 표면하중이 자유인 단축 신장은 다음과 같습니다.

```python
from refsol.elasticity import affine

field = affine([[0., 0.], [1., 1.]], [[1e-3, 0.], [0., -0.3e-3]],
               young_modulus=70e9, poisson_ratio=0.3, plane="stress")
print(field.displacement)  # metres
print(field.stress)        # [70e6, 0, 0] Pa at each point (up to roundoff)
```

참조 모듈은 sdist와 wheel 모두에 포함되며 FEM 엔진을 import하지 않습니다. 별도의 [엔진 계약](../galerkin/elasticity2d.md)은 경계 구속, 두께당 하중, 잠김 한계를 설명합니다.

```python
from refsol import fiber, slab, scattering, benchmarks

# exact HE11 effective index of a step-index fiber
n_eff = fiber.fundamental_neff(a=4.0, n1=1.45, n2=1.44, wavelength=1.55)

# all guided TE modes of a 220 nm SOI slab
slab.modes(n_f=3.48, n_s=1.444, n_c=1.444, d=0.22, wavelength=1.55, pol="TE")

# scattered field of a PEC cylinder, radius a, wavenumber k, at points (x, y)
u_s = scattering.scattered(x, y, k=3.14, a=1.0, kind="pec_tm")

# published reference: quasi-TE n_eff of the Hadley rib waveguide, slab 0.3 um
benchmarks.rib_neff(0.3)   # 3.412492
```

`refsol.thermal_boundary`는 처방 외향 열유속과 Robin 경계의 독립 폐형식을 제공합니다. 좌표는 m, 온도는 K, 열전도율은 W/(m K), 외향 열유속은 W/m^2, 대류 h는 W/(m^2 K)입니다.

`refsol.transient_heat`는 `uniform_insulated`, `moving_affine`, `sine_manufactured`, 소형 dense `p1_matrices`, `smallest_dirichlet_mode`, `backward_euler_amplitude`를 제공합니다. 좌표·시간·온도는 m/s/K, 열전도율은 W/(m K), 체적열용량은 J/(m³ K), source는 W/m³, flux는 W/m²입니다. Dense 행렬과 mode는 작은 참조 메시용이며 semidiscrete 후진 Euler product는 연속체 PDE 해와 구분합니다. 이 참조는 물리 온도 유효성이나 최대 원리를 인증하지 않습니다. 과도 엔진은 galerkin [과도 열전도 계약](../galerkin/transient_heat.md)에 설명돼 있습니다.

`refsol.thermoelastic_traction`는 원래 3D 구성 법칙의 `uniform_combined`, `polynomial_manufactured`, `parent_state`, `traction_from_stress`를 제공합니다. 좌표·변위는 m, 온도는 K, 응력·전체 표면하중은 Pa, 체적력은 N/m^3, 힘·반력은 N/m, 물리적 에너지는 J/m입니다. 처방 온도장 기계 참조이며 열 해석이나 출처 인증이 아닙니다.

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
- 길이는 일관된 어떤 단위든 사용할 수 있습니다(파장이 척도를 정함).
- 유효 굴절률은 `n_eff = beta / k0`입니다.

## 참고문헌

- D. Gloge, "Weakly guiding fibers," Appl. Opt. 10, 2252 (1971).
- A. W. Snyder and J. D. Love, *Optical Waveguide Theory* (Chapman & Hall, 1983).
- K. Okamoto, *Fundamentals of Optical Waveguides*, 2nd ed. (Academic Press, 2006).
- G. R. Hadley, "High-accuracy finite-difference equations for dielectric waveguide analysis II: dielectric corners," J. Lightwave Technol. 20, 1210 (2002).
- 벤치마크 수치는 Hadley의 출판 결과이며 femwell 프로젝트 벤치마크 문서(GPL-3.0)의 같은 표와 교차 확인했습니다. 수치만 재현했으며 NOTICE를 참조하세요.

## 라이선스

Apache License 2.0 — [LICENSE](../../../../../../packages/galerkin-refsol/LICENSE), [NOTICE](../../../../../../packages/galerkin-refsol/NOTICE)를 참조하세요.

Copyright 2026 Yongha Kim (FieldAlgo)

`refsol.benchmarks`의 벤치마크 수치는 Hadley (2002)가 출판한 수치 결과이고, `refsol.thermal_convection`의 NAFEMS T4 목표값은 출판된 벤치마크 수치입니다. 출처는 [NOTICE](../../../../../../packages/galerkin-refsol/NOTICE)를 참조하세요.
