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
| Au, Ag, Cu | n,k 표 0.19–1.94 µm | Johnson & Christy 1972, refractiveindex.info 경유(CC0) |
| Al | n,k 표 0.2–12 µm | Rakić 1995, refractiveindex.info 경유(CC0) |
| H2O (물) | n,k 표 0.2–200 µm | Hale & Querry 1973, refractiveindex.info 경유(CC0) |

Si, SiO2, Si3N4 및 금속에는 실온 밀도, 열전도율, 비열, Young 계수, Poisson 비, 열팽창계수, 열광학계수가 편람 수준의 시작값으로 붙어 있습니다. 각 값은 `source` 문자열을 갖습니다. 실제로 의존하기 전에 확인하세요.

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

## 모델 (`physmat.dispersion`)

`Constant`, `Sellmeier`, `Tabulated`(선형 보간), `Composite`(한 모델에서 n, 다른 모델에서 k), `Drude`, `DrudeLorentz`(Rakić 형식, 에너지는 eV), refractiveindex.info의 아홉 분산식을 저장된 그대로 구현한 `RIIFormula`가 있습니다. 모두 `index`, `n`, `k`, `eps`, `group_index`와 유효 범위를 제공합니다.

## 데이터 라이선스

refractiveindex.info 데이터베이스는 퍼블릭 도메인(CC0 1.0)으로 제공됩니다. 관리자는 다음 인용을 요청합니다.
M. N. Polyanskiy, "Refractiveindex.info database of optical constants",
*Sci. Data* **11**, 94 (2024). 내장 레코드는 각각 원 측정 출처도 명시합니다. `tools/build_physmat_tables.py`는 로컬 데이터베이스 사본에서 내장 표를 다시 생성합니다. Ciddor 공기 모델은 데이터베이스 데이터를 담지 않고 출판된 식과 상수를 계산합니다.

## 자체 검증

```bash
# From the repository root
python -m pip install pytest -e "packages/physmat[rii]"
python -m pytest -q tests/physmat
```

출판된 값(용융 실리카 n_d = 1.4585, Si n(1.55) = 3.4777, 사파이어/MgF2/CaF2 n_d, 금 ε(800 nm) ≈ −24 + 1.5i), 물리 제약(Im ε ≥ 0, ω_p에서 Drude 영점 교차, ε → ε∞), 손으로 계산한 식 2–9와 대조합니다. 합성 Drude–Lorentz 적합을 1e-3까지 복원하고, 400–1000 nm의 금 적합은 5 % 이내여야 합니다. 로컬 데이터베이스 사본이 있으면 3500개가 넘는 모든 레코드를 읽고 내장 값과 일치하는지도 검사합니다. Ciddor 공기 모델은 NIST Engineering Metrology Toolbox 표(Stone & Zimmerman; 300–1700 nm, −40~50 °C, 60–120 kPa, RH 0–100 %)의 값 14개를 1.5e-9 이내로 재현하고(측정 최대 0.75e-9, 표의 반올림 수준), 독립적으로 구현한 Birch & Downs 1994 수정 Edlén 식과 상온 조건에서 1.5e-8 이내로 일치하며(측정 최대 5.7e-9), Ciddor가 출판한 Z_a = 0.9995922115와 ρ_ws = 0.00985938 kg/m³를 재현하고, 극한 거동(p → 0에서 n → 1, 압력에 단조, 온도에 감소, 정상 분산)을 만족합니다.

## 라이선스

Apache License 2.0 — [LICENSE](../../../../../../packages/physmat/LICENSE), [NOTICE](../../../../../../packages/physmat/NOTICE)를 참조하세요.

Copyright 2026 Yongha Kim (FieldAlgo)

내장 광학 데이터에는 이 라이선스 부여가 적용되지 않습니다. 해당 데이터는 refractiveindex.info 데이터베이스에서 왔고 CC0 1.0(퍼블릭 도메인)입니다. 위 [데이터 라이선스](#데이터-라이선스)와 [NOTICE](../../../../../../packages/physmat/NOTICE)를 참조하세요. Apache-2.0 라이선스는 코드에 적용됩니다.

