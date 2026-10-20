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

| 이름 | 모델 | 출처(모두 refractiveindex.info 경유, CC0) |
|---|---|---|
| vacuum / air | n = 1 | 정의 |
| SiO2 (실리카, 용융 실리카) | Sellmeier 0.21–6.7 µm | Malitson 1965 |
| Si (실리콘) | Sellmeier 1.357–11.04 µm | Salzberg & Villa 1957 |
| Si_visible | n,k 표 0.25–1.45 µm | Green 2008 |
| Si3N4 (질화규소) | Sellmeier 0.31–5.5 µm | Luke et al. 2015 |
| GaAs, InP, Ge | Sellmeier | Skauli 2003, Pettit & Turner 1965, Burnett 2016 |
| Al2O3 (사파이어), MgF2, CaF2, LiNbO3, TiO2 | Sellmeier / 식 4 | Malitson & Dodge 1972, Dodge 1984, Malitson 1963, Zelmon 1997, DeVore 1951 |
| Au, Ag, Cu | n,k 표 0.19–1.94 µm | Johnson & Christy 1972 |
| Al | n,k 표 0.2–12 µm | Rakić 1995 |
| H2O (물) | n,k 표 0.2–200 µm | Hale & Querry 1973 |

Si, SiO2, Si3N4 및 금속에는 실온 밀도, 열전도율, 비열, Young 계수, Poisson 비, 열팽창계수, 열광학계수가 편람 수준의 시작값으로 붙어 있습니다. 각 값은 `source` 문자열을 갖습니다. 실제로 의존하기 전에 확인하세요.

## 모델 (`physmat.dispersion`)

`Constant`, `Sellmeier`, `Tabulated`(선형 보간), `Composite`(한 모델에서 n, 다른 모델에서 k), `Drude`, `DrudeLorentz`(Rakić 형식, 에너지는 eV), refractiveindex.info의 아홉 분산식을 저장된 그대로 구현한 `RIIFormula`가 있습니다. 모두 `index`, `n`, `k`, `eps`, `group_index`와 유효 범위를 제공합니다.

## 데이터 라이선스

refractiveindex.info 데이터베이스는 퍼블릭 도메인(CC0 1.0)으로 제공됩니다. 관리자는 다음 인용을 요청합니다.
M. N. Polyanskiy, "Refractiveindex.info database of optical constants",
*Sci. Data* **11**, 94 (2024). 내장 레코드는 각각 원 측정 출처도 명시합니다. `tools/build_physmat_tables.py`는 로컬 데이터베이스 사본에서 내장 표를 다시 생성합니다.

## 자체 검증

```bash
# From the repository root
python -m pip install pytest -e "packages/physmat[rii]"
python -m pytest -q tests/physmat
```

출판된 값(용융 실리카 n_d = 1.4585, Si n(1.55) = 3.4777, 사파이어/MgF2/CaF2 n_d, 금 ε(800 nm) ≈ −24 + 1.5i), 물리 제약(Im ε ≥ 0, ω_p에서 Drude 영점 교차, ε → ε∞), 손으로 계산한 식 2–9와 대조합니다. 합성 Drude–Lorentz 적합을 1e-3까지 복원하고, 400–1000 nm의 금 적합은 5 % 이내여야 합니다. 로컬 데이터베이스 사본이 있으면 3500개가 넘는 모든 레코드를 읽고 내장 값과 일치하는지도 검사합니다.

## 라이선스

Apache License 2.0 — [LICENSE](../../../../../../packages/physmat/LICENSE), [NOTICE](../../../../../../packages/physmat/NOTICE)를 참조하세요.

Copyright 2026 Yongha Kim (FieldAlgo)

내장 광학 데이터에는 이 라이선스 부여가 적용되지 않습니다. 해당 데이터는 refractiveindex.info 데이터베이스에서 왔고 CC0 1.0(퍼블릭 도메인)입니다. 위 [데이터 라이선스](#데이터-라이선스)와 [NOTICE](../../../../../../packages/physmat/NOTICE)를 참조하세요. Apache-2.0 라이선스는 코드에 적용됩니다.

