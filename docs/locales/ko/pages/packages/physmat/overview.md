# physmat — 물리 솔버용 재료 물성

[English](../../../../../packages/physmat/overview.md) | **한국어**

[영어·한국어 문서와 번역 상태](https://github.com/fieldalgo/openphysics/blob/main/docs/locales/ko/pages/index.md)

우선 광학 분산(파장에 따른 복소 굴절률 및 유전율)을 제공하며, 향후 다중물리 솔버에 필요한 열·기계 상수를 담을 자리도 갖추고 있습니다. 솔버와 독립적입니다. numpy + scipy를 사용하며 refractiveindex.info 데이터베이스를 읽을 때는 PyYAML도 사용합니다.

```python
import numpy as np, physmat

si = physmat.get("Si")            # aliases work too: "silicon", "c-Si"
si.n(1.55)                        # 3.4777  — wavelength in micrometres
si.eps(1.55)                      # (n + i k)^2, exp(-i w t) convention: Im eps >= 0 is loss
si.source                         # 'C. D. Salzberg and J. J. Villa, J. Opt. Soc. Am. 47, 244 (1957) ...'
si.range_um                       # (1.357, 11.04): evaluating outside raises OutOfRange
si.get("thermal_conductivity")    # 148.0  (W/(m K)); the multiphysics slot
physmat.get("Cu").get("thermal_conductivity", 77.0)   # 544: Hust & Lankford 1984 equation, RRR 100

au = physmat.get("Au")            # Johnson & Christy 1972 table
au.index(0.8)                     # 0.154 + 4.908j

# fit a table to Drude + Lorentz poles for time-domain or broadband solvers
fit = physmat.fit_drude_lorentz(au.optical, np.linspace(0.4, 1.0, 60), n_lorentz=2)
fit.model.eps(0.8), fit.rms_eps, fit.max_rel_index    # passive by construction

# the full refractiveindex.info database (3500+ records, CC0 1.0)
db = physmat.rii.Database("/path/to/refractiveindex.info-database")   # or Database.download()
db.search("silicon nitride")                  # -> entries (shelf, book, page, name)
rec = db.load("main/Si3N4/Luke")
rec.dispersion.n(1.55), rec.references

# your own material
glass = physmat.constant(1.5, name="my glass")
custom = physmat.Material("doped SiO2", physmat.Sellmeier(B=[...], C=[...], range_um=(0.3, 2.0)))
```

## 내장 재료

| 이름 | 모델 | 출처 |
|---|---|---|
| vacuum / air | n = 1 | 정의 |
| standard_air (standard air, Ciddor air) | Ciddor 식 0.3–1.69 µm; 지정한 온도·압력·습도·CO2에서의 n(λ) | Ciddor 1996, 출판된 식으로 계산(저장 데이터 없음) |
| SiO2 (실리카, 용융 실리카) | Sellmeier 0.21–6.7 µm | Malitson 1965, refractiveindex.info 경유(CC0) |
| Si (실리콘) | Sellmeier 1.357–11.04 µm | Salzberg & Villa 1957, refractiveindex.info 경유(CC0) |
| Si_visible | n,k 표 0.25–1.45 µm | Green 2008, refractiveindex.info 경유(CC0) |
| Si3N4 (질화규소) | Sellmeier 0.31–5.5 µm | Luke et al. 2015, refractiveindex.info 경유(CC0) |
| GaAs, InP, Ge | Sellmeier | Skauli 2003, Pettit & Turner 1965, Burnett 2016, refractiveindex.info 경유(CC0) |
| Al2O3 (사파이어), MgF2, CaF2, LiNbO3, TiO2 | Sellmeier / 식 4 | Malitson & Dodge 1972, Dodge 1984, Malitson 1963, Zelmon 1997, DeVore 1951, refractiveindex.info 경유(CC0) |
| Au, Ag, Cu | n,k 표 0.19–1.94 µm | Johnson & Christy 1972, refractiveindex.info 경유(CC0); Cu 열전도율 λ(T): Hust & Lankford 1984, RRR 100 |
| Al | n,k 표 0.2–12 µm | Rakić 1995, refractiveindex.info 경유(CC0); 열전도율 λ(T): Hust & Lankford 1984, RRR 100 |
| H2O (물) | n,k 표 0.2–200 µm | Hale & Querry 1973, refractiveindex.info 경유(CC0) |

Si, SiO2, Si3N4 및 금속에는 실온 밀도, 열전도율, 비열, Young 계수, Poisson 비, 열팽창계수, 열광학계수가 편람 수준의 시작값으로 붙어 있습니다. 각 값은 `source` 문자열을 갖습니다. 실제로 의존하기 전에 확인하세요. 예외는 Cu와 Al의 열전도율로, 출판된 식에서 계산한 온도의 함수입니다([아래](#금속-열전도율의-온도-의존성-hust--lankford-1984)).

## 공기 (Ciddor 1996)

`air`는 진공(n = 1)입니다. `standard_air`는 P. E. Ciddor, "Refractive index of air: new equations for the visible and near infrared", *Appl. Opt.* **35**, 1566–1573 (1996)의 습한 공기 모델로, 출판된 식에서 구현했습니다. 표준 건조 공기의 분산과 CO2 보정, 수증기의 분산, BIPM 1981/91 습공기 밀도(포화 수증기압, 증강 계수, 압축률 Z), 밀도비 혼합 규칙으로 이루어집니다.

```python
std = physmat.get("standard_air")                     # 15 °C, 101325 Pa, 0 % RH, 450 ppm CO2
std.n(0.633)                                          # 1.00027653
lab = physmat.standard_air(20.0, 101325.0, humidity=0.5, co2_ppm=450.0)   # RH as a fraction
lab.n(0.633), lab.optical.refractivity(0.633)         # n and n − 1 at full precision
lab.optical.at(temperature_c=25.0).n(0.633)           # same model, other conditions
lab.get("density", 293.15)                            # kg/m³, BIPM 1981/91 (Property, T in kelvin)
physmat.air.refractive_index(0.633, temperature_c=np.linspace(-40, 100, 5), pressure_pa=90e3)
```

조건은 온도(°C), 압력(Pa), 상대습도(분수; 또는 수증기 분압 `vapour_pressure_pa`), CO2(ppm, µmol/mol)입니다. Ciddor는 0.3–1.69 µm, −40~+100 °C, 80–120 kPa, RH 0–100 %, CO2 0–2000 ppm에서 식을 제시하며, 실험실 조건에서 n의 불확도는 2–5e-8입니다(NIST 추정은 k = 2에서 약 2e-8, 극한 조건에서 최대 1e-7). 범위 밖 파장은 `n(wl, strict=False)`가 아니면 `OutOfRange`를 일으키고, 범위 밖 조건은 재료를 만들 때 `strict=False`가 아니면 예외를 일으킵니다(`strict=False`는 식을 외삽합니다). 밀도 `Property`는 재료의 압력·습도·CO2에서 켈빈 온도의 함수로 BIPM 식을 계산합니다. 습도 모델은 Ciddor가 쓴 Davis(1992)의 물 위 포화 수증기압을 사용합니다. 0 °C 아래에서 NIST는 얼음 위 식을 따로 쓰므로 영하의 습한 공기는 1e-9 수준에서 다릅니다.

## 금속 열전도율의 온도 의존성 (Hust & Lankford 1984)

Cu와 Al의 `thermal_conductivity` 속성과 W용 `physmat.thermal`은 J. G. Hust, A. B. Lankford, *Thermal conductivity of aluminum, copper, iron, and tungsten for temperatures from 1 K to the melting point*, NBSIR 84-3007, National Bureau of Standards (1984), [doi:10.6028/NBS.IR.84-3007](https://doi.org/10.6028/NBS.IR.84-3007)의 식을 계산합니다. 금속마다 식 하나이며, 순도 매개변수는 잔류저항비 RRR = ρ(273 K)/ρ(0 K)입니다(보고서 식 1.1.3–1.1.6, 1.2.2; T는 K, λ는 W/(m K)).

```
λ    = 1 / (W0 + Wi + Wi0)
W0   = β / T,            β = ρ0 / L0,   ρ0 = ρi,273 / (RRR − 1),   L0 = 2.443e-8 V²/K²
Wi   = P1 T^P2 / (1 + P1 P3 T^(P2+P4) exp(−(P5/T)^P6)) + Wc(T)
Wi0  = P7 Wi W0 / (Wi + W0)
```

W0는 전자–결함(잔류) 열저항, Wi는 고유 전자–포논 열저항, Wi0는 둘의 상호작용 항, Wc는 작은 경험적 보정입니다. 매개변수 P1–P7과 Wc는 보고서의 값(2.1, 3.1, 5.1절; 구리는 P7 = 0.838/βr^0.1661, βr = β/0.0003)이고, ρi,273은 Cu, Al, W에 대해 15.4, 24.8, 48.4 nΩ m입니다(1.5절). 보고서의 표는 저장하지 않습니다.

```python
cu = physmat.get("Cu")
cu.get("thermal_conductivity", np.array([4.0, 20.0, 77.0, 300.0]))   # 628, 2420, 544, 397  (RRR 100)
physmat.HustLankford("Cu", rrr=300)(20.0)                            # 5073: purer copper
physmat.HustLankford("Al", rrr=1000).range_k                         # (1.0, 933.47): 1 K to the melting point
physmat.thermal.thermal_conductivity("W", 300.0)                     # 175.6  (RRR 100)
physmat.thermal.conductivity_property("W", rrr=50)                   # a Property for your own Material("W", ...)
```

- **기본 RRR 100**(세 금속 공통): 보고서 자체 표의 열이고, NIST 극저온 적합식의 OFHC 구리 등급이며(Hust & Lankford는 상용 구리선을 RRR 50–500으로 봄), 대체한 편람 300 K 상수와 2 % 이내입니다(Cu 397 대 401, Al 234 대 237, W 176 대 174 W/(m K)). 다른 순도는 `rrr=`로 지정합니다. 약 100 K 아래에서는 값이 순도에 크게 좌우됩니다(Cu 20 K: RRR 30, 100, 300에서 843, 2408, 5054 W/(m K)).
- **유효 범위**: 1 K부터 녹는점까지(Cu 1357.77 K, Al 933.47 K, W 3695 K), 어닐링한 벌크 시편. 보고서는 1차 데이터를 약 ±15 %(Cu; 어닐링하지 않은 시편은 20 %), RRR 경향 없는 무작위 편차(Al), ±7 %(W)로 표현하며, 구리 적합식은 RRR 20 아래에서 점차 타당성을 잃는다고 적습니다. 범위 밖 온도는 `strict=False`가 아니면 `OutOfRange`를 일으킵니다. RRR은 1보다 커야 하고(`ValueError`), 적합 데이터의 RRR 범위(Cu 20–1800, Al 13–16800, W 30–170) 밖이면 `strict=False`로 만들지 않는 한 `OutOfRange`를 일으킵니다(`strict=False`는 외삽; 보고서 자체 표는 RRR 3000, 10000, 300까지 있음).
- **검증**(`tests/physmat/test_conductivity_temperature.py`, 사전 등록 기준): 보고서의 표 2.4.1(Cu)과 3.4.1(Al)을 1.5 % 이내로 재현합니다(Al의 한 항목, RRR 100의 700 K 값 229 W/(m K)는 더 순수한 열보다 큰 오식이라 제외). Cu RRR 100은 NIST Cryogenic Material Properties의 OFHC 적합식(RRR 100; 데이터는 NIST Monograph 177)과 4, 20, 77, 150, 300 K에서 2.3 % 이내(RRR 50과 300은 3.0 %와 0.6 %), Ho, Powell & Liley(1972) 권장값과 100–1300 K에서 4.3 % 이내로 일치합니다. Al과 W는 Ho, Powell & Liley와 각각 3.8 %(150–900 K), 4.0 %(100–3000 K) 이내이고, 그 시편의 순도에서 100 K 값은 2 % 이내입니다. 텅스텐은 보고서에 인쇄된 매개변수가 표 5.4.1을 2 % 이내로 재현하지만, 더 순수한 열의 열전도율 최대값 부근에서는 표가 식보다 최대 3.5 %(RRR 100, 14–50 K), 7.2 %(RRR 300, 9–50 K) 높습니다. 매개변수는 스캔을 고해상도로 다시 읽어 인쇄된 그대로임을 확인했으므로 이는 원전 자체의 불일치이며, 기록만 하고 고치지 않았습니다. Cu와 W는 최대값이 하나이고(RRR 100에서 22 K, 2447과 786 W/(m K)) 300 K까지 단조 감소합니다. Al(24 K, 1630 W/(m K))은 242 K 부근의 얕은 최소값까지 감소한 뒤 300 K까지 0.5 % 오르며, 보고서 표와 Ho, Powell & Liley도 같습니다.
- **출처**: 보고서는 미국 정부 저작물로 미국 안에서는 저작권 대상이 아닙니다(17 U.S.C. 105). 미국 밖에서의 지위는 그 법률이 정하지 않으므로 패키지 `NOTICE`와 [제3자 소프트웨어](../../third-party.md#데이터와-출판-수치)에 사실만 적고 판단하지 않습니다. 텅스텐은 아직 내장 재료가 아니므로(광학 모델이 없음) `physmat.thermal` 함수를 직접 사용하세요.

## 모델 (`physmat.dispersion`)

`Constant`, `Sellmeier`, `Tabulated`(선형 보간), `Composite`(한 모델에서 n, 다른 모델에서 k), `Drude`, `DrudeLorentz`(Rakić 형식, 에너지는 eV), refractiveindex.info의 아홉 분산식을 저장된 그대로 구현한 `RIIFormula`가 있습니다. 모두 `index`, `n`, `k`, `eps`, `group_index`와 유효 범위를 제공합니다.

## 데이터 라이선스

refractiveindex.info 데이터베이스는 퍼블릭 도메인(CC0 1.0)으로 제공됩니다. 관리자는 다음 인용을 요청합니다.
M. N. Polyanskiy, "Refractiveindex.info database of optical constants",
*Sci. Data* **11**, 94 (2024). 내장 레코드는 각각 원 측정 출처도 명시합니다. `tools/build_physmat_tables.py`는 로컬 데이터베이스 사본에서 내장 표를 다시 생성합니다. Ciddor 공기 모델과 Hust & Lankford 열전도율 모델은 데이터베이스 데이터를 담지 않고 출판된 식과 상수를 계산합니다.

## 자체 검증

```bash
# From the repository root
python -m pip install pytest -e "packages/physmat[rii]"
python -m pytest -q tests/physmat
```

출판된 값(용융 실리카 n_d = 1.4585, Si n(1.55) = 3.4777, 사파이어/MgF2/CaF2 n_d, 금 ε(800 nm) ≈ −24 + 1.5i), 물리 제약(Im ε ≥ 0, ω_p에서 Drude 영점 교차, ε → ε∞), 손으로 계산한 식 2–9와 대조합니다. 합성 Drude–Lorentz 적합을 1e-3까지 복원하고, 400–1000 nm의 금 적합은 5 % 이내여야 합니다. 로컬 데이터베이스 사본이 있으면 3500개가 넘는 모든 레코드를 읽고 내장 값과 일치하는지도 검사합니다. Ciddor 공기 모델은 NIST Engineering Metrology Toolbox 표(Stone & Zimmerman; 300–1700 nm, −40~50 °C, 60–120 kPa, RH 0–100 %)의 값 14개를 1.5e-9 이내로 재현하고(측정 최대 0.75e-9, 표의 반올림 수준), 독립적으로 구현한 Birch & Downs 1994 수정 Edlén 식과 상온 조건에서 1.5e-8 이내로 일치하며(측정 최대 5.7e-9), Ciddor가 출판한 Z_a = 0.9995922115와 ρ_ws = 0.00985938 kg/m³를 재현하고, 극한 거동(p → 0에서 n → 1, 압력에 단조, 온도에 감소, 정상 분산)을 만족합니다. 열전도율 검증 기준은 [위 절](#금속-열전도율의-온도-의존성-hust--lankford-1984)에 있습니다.

## 라이선스

Apache License 2.0 — [LICENSE](../../../../../../packages/physmat/LICENSE), [NOTICE](../../../../../../packages/physmat/NOTICE)를 참조하세요.

Copyright 2026 Yongha Kim (FieldAlgo)

내장 광학 데이터에는 이 라이선스 부여가 적용되지 않습니다. 해당 데이터는 refractiveindex.info 데이터베이스에서 왔고 CC0 1.0(퍼블릭 도메인)입니다. 위 [데이터 라이선스](#데이터-라이선스)와 [NOTICE](../../../../../../packages/physmat/NOTICE)를 참조하세요. Apache-2.0 라이선스는 코드에 적용됩니다.

