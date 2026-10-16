# galerkin-refsol — galerkin 검증용 참조해

[English](../../../overview.md) | **한국어**

## 현재 checkout과 근거

이 페이지는 현재 checkout의 구현과 재현 계약을 설명합니다. 아래 d21/b2/e79의 과거 관측은 명시한 snapshot에만 적용됩니다. 현재 checkout의 source·독립 수치·배포·설치 gate는 정확한 CI 실행·명령 종료값·artifact로 확인해야 하며, 여기서는 전체 CI 성공을 주장하지 않습니다. GitHub Actions는 활성화돼 있습니다. 모든 변경은 main 대상 PR과 필수 검사를 거쳐 GitHub Rebase and merge로 반영하며, 릴리스에는 결과 main 커밋의 검사 성공도 필요합니다.

[영어·한국어 문서와 번역 상태](https://github.com/fieldalgo/openphysics/blob/main/docs/locales/ko/pages/index.md)

[galerkin](https://github.com/fieldalgo/openphysics/blob/2efbc413df5d3d36bcc4c9879b34ed88213b9217/packages/galerkin/README.md) FEM 엔진의 정답지로 사용하는 폐형식 해와 출판된 고정밀 벤치마크입니다. 같은 모노레포 안의 별도 패키지이며, 평가자는 평가 대상 코드를 import하지 않습니다. numpy와 scipy에만 의존합니다.

수치 솔버는 그럴듯하게 틀릴 수 있는 소프트웨어입니다. 이 패키지는 이산화에 의존하지 않는 부분을 담당합니다.

Python 패키지 이름은 `refsol`입니다(`from refsol import fiber`).

## 구성

| 모듈 | 내용 | 자체 검증 |
|---|---|---|
| `refsol.thermoelasticity` | 주어진 Kelvin 온도장의 균일 자유/구속·적합·사인 장, 면외 응력과 물리적 탄성에너지 | 원래 3차원 법칙, FEM import 없음 |
| `refsol.thermal` | Kelvin 슬랩 및 정상 사인 제조해, 열유속 W/m^2와 열원 W/m^3 | 직접 해석 미분, 엔진 import 없음 |
| `refsol.elasticity_traction` | 평면응력/평면변형률 단축·전단 장, Cartesian sigma*n과 다항 표면하중 합력 | 폐형식과 직접 미분, FEM import 없음 |
| `refsol.elasticity` | 균질 등방성 평면응력/평면변형률: 아핀 장, 폐형식 응력, 매끄러운 제조해 | 재료 계수, 공학 전단, 독립적인 힘 미분 |
| `refsol.slab` | 대칭/비대칭 평면 유전체 도파로 TE/TM 모드, TE 장 분포 | 차단식 대비 모드 수, 짝수 모드 방정식, 경계면 연속성 |
| `refsol.fiber` | 계단형 굴절률 광섬유: 스칼라 LP 모드(Gloge), 정확한 벡터 TE/TM/HE/EH 모드 | Bessel 차단값 대비 LP 개수, 2.4048의 LP11 차단, 약한 도파에서 HE11 ≈ LP01, LP11 군 축퇴, Rudolph–Neumann 근사 |
| `refsol.metallic` | 직사각형 도파로 차단, 직육면체 공진기 공진, 동축 전위·장 | 폐형식 |
| `refsol.scattering` | 원형 원통의 평면파 산란: PEC(TM/TE)와 유전체, 부분파 급수, 산란 폭 | 1e-9까지 경계조건 만족, 경계면 연속성, 기하광학 극한 |
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

참조 모듈은 sdist와 wheel 모두에 포함되며 FEM 엔진을 import하지 않습니다. 별도의 [엔진 계약](https://github.com/fieldalgo/openphysics/blob/a292ae15707b3713f0464b4d126be765b4c205ae/packages/galerkin/docs/elasticity2d.md)은 경계 구속, 두께당 하중, 잠김 한계를 설명합니다. 이 저장소 링크에는 네트워크 연결과 저장소 접근 권한이 필요합니다.

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

## 자체 검증 실행

```bash
# From the repository root
python -m pip install pytest -e packages/galerkin-refsol
python -m pytest -q packages/galerkin-refsol/tests
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

Apache License 2.0 — [LICENSE](../../../../LICENSE), [NOTICE](../../../../NOTICE)를 참조하세요.

Copyright 2026 Yongha Kim (FieldAlgo)

`refsol.benchmarks`의 벤치마크 수치는 Hadley (2002)가 출판한 수치 결과입니다. 출처는 [NOTICE](../../../../NOTICE)를 참조하세요.


`refsol.thermal_boundary`는 처방 외향 열유속과 Robin 경계의 독립 폐형식을 제공합니다. 좌표는 m, 온도는 K, 열전도율은 W/(m K), 외향 열유속은 W/m^2, 대류 h는 W/(m^2 K)입니다. 두 배포 아카이브에 포함되며 이 독립 참조 모듈이 헤드리스 JSON schema를 확장하지는 않습니다.

`refsol.thermoelastic_traction`는 원래3D 구성 법칙의 `uniform_combined`, `polynomial_manufactured`, `parent_state`, `traction_from_stress`를 NumPy/표준 라이브러리만으로 제공하며 engine을 import하지 않습니다. 좌표·변위는 m, 온도는 K, 응력·전체 표면하중은 Pa, 체적력은 N/m^3, 힘·반력은 N/m, 물리적 에너지는 J/m입니다. 처방 온도장 기계 참조이며 열 해석이나 출처 인증이 아닙니다.

## 과도 열전도 참조

`refsol.transient_heat`를 명시적으로 import해 `uniform_insulated`, `moving_affine`, `sine_manufactured`, 소형 dense `p1_matrices`, `smallest_dirichlet_mode`, `backward_euler_amplitude`를 사용합니다. 이 모듈은 engine import 없이 NumPy/표준 라이브러리를 사용합니다. 좌표·시간·온도는 m/s/K, 열전도율은 W/(m K), 체적열용량은 J/(m³ K), source는 W/m³, flux는 W/m²입니다. Dense 행렬과 mode는 작은 참조 메시용이며 semidiscrete BE product는 연속체 PDE 해와 구분합니다. 이 참조는 물리 온도 유효성이나 최대 원리를 인증하지 않으며 독립 수용은 자체 정답을 도출해야 합니다.

상수 등방 재료, 시간변 Dirichlet 값과 단열을 사용하는 고정 P1·일관 질량·후진 Euler 엔진 API는 다음 문서에 설명돼 있습니다.

[사용법](../../../../../galerkin/docs/locales/ko/pages/transient_heat.md) ([English](../../../../../galerkin/docs/transient_heat.md)) · [생산 검증 계약](../../../../../galerkin/docs/locales/ko/pages/transient_heat_validation.md) ([English](../../../../../galerkin/docs/transient_heat_validation.md)) · [독립 검증 보고](../../../../../galerkin/docs/locales/ko/pages/transient_heat_independent_validation.md) ([English](../../../../../galerkin/docs/transient_heat_independent_validation.md))

과거 b2 snapshot의 소형 source 70개 통과와 현재 checkout의 수용은 별개입니다. 현재 manifest/helper에는 문서·원 시험·독립 consumer·runtime byte 검사가 연결돼 있습니다. 실제 전체 시간/PDE·독립·배포·설치 성공은 정확한 현재 CI의 종료값과 artifact로 확인해야 합니다. 구현이나 gate 연결만으로 릴리스·통합 수용을 뜻하지 않습니다. JSON/CLI/Studio·저장·자동 열→기계 연결은 제공하지 않습니다.
