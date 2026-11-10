# physmat.units — 물리량 등록부와 정확한 단위 변환기

[English](../../../../../packages/physmat/units.md) | **한국어**

[문서 홈](../../index.md)

상태: **OpenPhysics 단위·이름 규칙의 첫 단계와, 문서 리더에 필요한 등록부 항목과 변환 함수.**
`physmat.units`는 물리량 등록부와,
사람이 쓴 단위를 SI로 바꾸는 단 하나의 변환기를 담습니다. **지금은 `simcase`의 형식 0.3 읽기만
이 모듈을 부르며**([문서 형식 0.3](../simcase/document_format.md)), 아직 어떤 물리 종류도 그 형식을
읽지 않습니다. 모델 문서, `simcase` 실행기, `galerkin`, `sipi`, Studio는 지금의 키 이름과 단위를 그대로
쓰고, physmat의 다른 함수도 지금의 인수(파장은 마이크로미터, 온도는 켈빈, Ciddor 공기 모델만
섭씨 `temperature_c`)를 그대로 받습니다. 이후 단계에서 한꺼번에 바뀝니다. 이 모듈은 Python 표준
라이브러리만 씁니다.

```python
from physmat.units import q, q_array, convert, convert_array, convert_complex

q("200 GPa", "youngs_modulus")                   # 200000000000.0  (Pa)
q("200000 MPa", "youngs_modulus")                # the same double
q("25 degC", "ambient_temperature")              # 298.15  (K)
q("12 ppm/K", "linear_expansion_coefficient")    # 1.2e-05  (1/K)
q("220 ㎚", "length")                             # 2.2e-07  (m)
q(0.3, "poisson_ratio")                          # a bare number: dimensionless quantities only
q_array({"unit": "nm", "values": [1500, 1550]}, "vacuum_wavelength")   # [1.5e-06, 1.55e-06]
q("1550 THz", "vacuum_wavelength")               # UnitError E-UNIT-DIMENSION: Did you mean frequency?

q("10 mPa", "gauge_pressure")                    # UnitError E-UNIT-NOT-ACCEPTED: millipascal
convert("10 mPa", "gauge_pressure").error        # the same diagnostic, returned instead of raised
convert("30 deg", "minimum_angle").number_text   # "30": the number as written, beside the SI value

convert_array({"unit": "nm", "values": [1500, -1]}, "vacuum_wavelength")    # every entry's diagnostics
convert_complex({"re": 4.0, "im": 0.04}, "relative_permittivity").value     # (4+0.04j), exp(-i omega t)
convert_complex({"n": 3.48, "k": -0.002}, "refractive_index").error         # E-GAIN: k >= 0 is loss
```

## 값의 규칙

- **차원 있는 숫자는 단위를 함께 씁니다.** 데이터시트처럼 `"10 MPa"`, `"1550 nm"`,
  `"25 degC"`, `"12 ppm/K"`로 씁니다. 맨 숫자는 무차원 물리량과 개수에만 받으며,
  `youngs_modulus`에 `200000`을 쓰면 `E-UNIT-MISSING`입니다. 0도 예외가 아니어서 `"0 V"`로
  씁니다. 각도는 항상 `deg` 또는 `rad`를 붙입니다.
- **물리량마다 받는 단위 목록(메뉴)이 닫혀 있습니다.** 헷갈리는 단위는 넣지 않습니다.
  탄성 계수나 하중에는 `mPa`가 없고 도체에는 `mS/m`가 없습니다. 대소문자만 다른 두 표기를
  같은 메뉴에 두지 않으므로 `MPa` 자리에 쓴 `mPa` 같은 대소문자 실수는 읽히지 않고 항상
  이름을 밝혀 거부됩니다.
- **`degC`는 섭씨 눈금 위의 한 점입니다.** 절대 온도 값의 단위 전체로만 받습니다. 온도차,
  허용오차, 모든 복합 단위에는 `K`나 `mK`를 씁니다: `"1 mK"`, `"W/(m K)"`, `"ppm/K"`.
- **모든 값은 물리량의 정식 단위로 한 번, 정확하게 바뀝니다.** 정식 단위는 일관 SI이며
  `propagation_loss`(dB/m)와 `bend_loss`(dB/(90 deg))만 예외입니다.
- **`fix`는 값을 바꾸지 않고, `suggestion`은 바꿀 수 있습니다.** fix는 모든 SI 값을 그대로
  두므로 도구가 묻지 않고 적용해도 됩니다. suggestion은 뜻이 바뀌므로 바뀌기 전후의 SI 값을
  보여 주고 사람이 확인해야만 적용합니다.

## 물리량 문자열

```
quantity = number 1*SP unit            ; "25 degC", "1.2e-3 1/K"
         / number ("%" / "°C" / "°")   ; "40%", "25°C", "8°" are read as "40 %", "25 degC", "8 deg"
number   = ["+" / "-"] 1*DIGIT ["." 1*DIGIT] [("e" / "E") ["+" / "-"] 1*DIGIT]
unit     = one entry of the spelling table
```

- 숫자는 숫자로 시작해야 합니다(`.5`가 아니라 `0.5`). 소수점 쉼표와 천 단위 구분자는 없습니다.
- 숫자와 단위 사이에는 공백 하나가 필요합니다. `"2eV"`와 `"25K"`는 거부되고 fix로 `"2 eV"`,
  `"25 K"`를 줍니다. 잘못 읽힐 수 없는 위의 세 붙임 형태만 받습니다. `"25℃"`는 fix
  `"25 degC"`와 함께 거부하고, `"25 ℃"`는 받습니다.
- 여기서 받는 값의 형태: 물리량 문자열, 맨 숫자(JSON 숫자, `int`, `float`, `Decimal`,
  `Fraction`, numpy 스칼라), 단위 붙은 배열 `{"unit": "nm", "values": [...]}`(중첩 목록은
  모양을 유지. 어떤 시퀀스든, numpy 배열처럼 `tolist()`가 있는 배열도 됨), 무차원 배열
  `{"values": [...]}`, 물리량 문자열 3개 이하의 짧은 벡터(`["0 MPa", "-5 MPa"]`).
  `"unit": "1"`은 쓰지 않습니다. 무차원 값은 맨 숫자입니다.
- 숫자만 담은 문자열(`"0.3"`, `"2"`)은 맨 숫자가 아닙니다. 무차원 물리량이나 개수에서는 JSON
  숫자를 fix로 주는 `E-UNIT-UNKNOWN`(`0.3`, `2`)이고, 차원 있는 물리량에서는 `E-UNIT-MISSING`입니다.
- Python float는 가장 짧은 `repr`로 읽습니다. 따라서 `0.1`은 JSON 텍스트 `0.1`처럼 10진수
  0.1을 뜻합니다. numpy `float32`는 그 정확한 double(`0.30000001192092896`)로 읽습니다. numpy를
  가져오지는 않습니다.
- 개수(`mode_count`, `pml_order` 등)는 정수 리터럴입니다. `2.0`이 아니라 `2`입니다. `2.0`,
  `Decimal("2E+1")`, `Fraction(2)`는 정수를 fix로 주는 `E-DOMAIN`입니다.
- `Conversion.number_text`는 쓴 그대로의 숫자이고 `Conversion.unit_text`는 문자 대응표를 거친
  뒤 쓴 그대로의 단위입니다(`"28.5 °"`: `"28.5"`와 `"deg"`. `"148 W/m/K"`: `"W/m/K"`이고
  `text`는 `"148 W/(m K)"`). 도(degree)를 받는 메셔처럼 쓴 숫자가 필요한 쪽은 여기서 읽습니다.
  `math.degrees(q("30 deg", "minimum_angle"))`은 정확히 30이 아닙니다.
- `is_quantity_text(s)`는 숫자, 공백 하나, 두 표 가운데 하나에 있는 단위로 이루어진 문자열
  (`"0.5 um"`, `"10 mPa"`, `"40%"`)이면 True, 식(`"w/2"`, `"220 nm + gap"`)이나 맨 숫자면
  False입니다. 문서 리더가 단위 붙은 값과 식을 가릴 때 씁니다.

## 배열과 복소수 값

`convert_array(values, quantity, path=...)`는 위의 배열 형태를 받아 `ArrayConversion`을
돌려줍니다. 쓴 모양 그대로의 SI 값(실패한 항목은 `None`), 항목마다의 `Conversion`, 모든
진단을 담으며, 진단은 배열 자체의 것(모르는 키, 빠진 `values`, 거부된 단위)이 먼저이고 그다음
항목의 것이 차례로 옵니다. 잘못된 값에 예외를 일으키지 않습니다. 단위 붙은 배열 안의 문자열이나
bool, 문자열 4개 이상의 목록, 배열이 아닌 객체는 그 경로의 `E-VALUE-FORM`입니다. `q_array`는
예외를 일으키는 `convert_array`입니다. 형태가 틀리면 `TypeError`, 첫 오류는 `UnitError`,
경고는 각각 `UnitWarning`입니다.

`convert_complex(value, quantity, path=..., allow_gain=False)`는 복소 물리량을 하나뿐인 시간
규약 exp(−iωt)로 읽습니다.

| 형태 | 물리량 | 예 |
|---|---|---|
| `convert`가 받는 실수 값 | 모두 | `1.45`, `4`, `"50 Ohm"` |
| 맨 숫자의 `{"re": .., "im": ..}` | `refractive_index`가 아닌 무차원 복소 물리량(`relative_permittivity`, `relative_permeability`) | `{"re": 4.0, "im": 0.04}` |
| 맨 숫자의 `{"n": .., "k": ..}` | `refractive_index`만 | `{"n": 3.48, "k": 0.01}` |

실수부(`re`, `n`)는 물리량의 허용 범위와 타당 범위로 검사하고(`"n": 0`은 `E-DOMAIN`),
허수부는 맨 숫자로서 범위만 검사합니다. 수동 재료 물리량(`refractive_index`,
`relative_permittivity`, `relative_permeability`)에서 허수부나 `k`가 음수이면 그 부분 경로의
`E-GAIN`이며, "출처가 exp(+jωt)를 쓴다면 허수부의 부호를 바꾸라"는 안내와 부호를 바꾼 숫자를
suggestion으로 줍니다(fix는 아님). `allow_gain=True`면 받습니다. `[re, im]` 쌍,
`refractive_index`의 `{"re", "im"}`, 다른 물리량의 `{"n", "k"}`, 실수 물리량이나 차원 있는
물리량의 객체는 `E-VALUE-FORM`이고, 빠지거나 모르는 키는 `E-KEY-MISSING`이나
`E-KEY-UNKNOWN`입니다. 결과 `ComplexConversion`은 복소 SI 값, 정확한 실수부·허수부, 읽은 형태
(`"real"`, `"re_im"`, `"n_k"`), 진단을 담습니다.

## 정확한 변환

숫자는 10진 텍스트에서 `fractions.Fraction`으로 읽고, 단위의 정확한 유리수 계수를 곱하고
(`degC`면 오프셋 273.15를 더하고), 정식 단위의 계수로 나눈 뒤 double로 **한 번만** 반올림합니다.

- `"200 GPa"`, `"200000 MPa"`, `"2e11 Pa"`는 비트까지 같은 double이 됩니다.
  `"25 degC"`는 298.15에 가장 가까운 double입니다.
- 계수는 정확합니다: `in` = 0.0254 m, `mil` = 25.4 µm,
  `psi` = 44482216152605/6451600000 Pa, `atm` = 101325 Pa, `eV` = 1.602176634e-19 J.
  `deg`는 40자리로 한 번 반올림한 π로 만든 π/180이므로 `"180 deg"`는 `math.pi`입니다.
  `dB/(180 deg)`는 정확히 `dB/(90 deg)`의 절반입니다.
- **범위.** 바꾼 값이 유한하지 않거나, 0이 아니면서 크기가 1e-300보다 작으면(double로 비정규
  수나 0.0) `E-DOMAIN`입니다: `"1e400 Pa"`, `"1e-330 m"`. 10진 지수가 ±1000을 넘는 숫자(지수를
  텍스트에서 읽으므로 `"1e999999999999999999999 Pa"`도)와 1100비트를 넘는 정수나 분수는 계산하기
  전에 거부합니다.
- 메시지와 `format()`은 숫자를 자릿수에서 직접 만들므로 호출한 쪽의 `decimal` 컨텍스트(정밀도,
  트랩)는 영향을 주지 않습니다.

## 단위 문자열을 읽는 방법

실행 중에는 단위 문법이 없습니다. 변환기는 네 단계를 거칩니다.

1. **문자 대응표.** 정해진 별칭 대응표를 문자열 전체에 적용합니다. 유니코드 정규화(NFC, NFKC)는
   하지 않습니다. NFKC는 `m²`를 `m2`로 바꾸기 때문입니다.

   | 쓴 것 | 읽는 것 |
   |---|---|
   | `µ`(U+00B5), `μ`(U+03BC) | `u` |
   | `Ω`(U+03A9), `Ω`(U+2126) | `Ohm` |
   | `Å`(U+00C5), `Å`(U+212B) | `Angstrom` |
   | `K`(켈빈 기호 U+212A) | `K` |
   | `°C`, `℃`(U+2103) | `degC` |
   | 단독 `°` | `deg` |
   | `㎚ ㎛ ㎜ ㎝ ㎞ ㎟ ㎠ ㎡`(U+339A–U+33A1, 한글 입력기와 PDF 복사에서 생김) | `nm um mm cm km mm^2 cm^2 m^2` |
   | 위 첨자 `⁰`–`⁹`와 `⁻` | `^`와 ASCII: `m⁻³` → `m^-3` |
   | `−`(U+2212) | `-`(숫자와 지수 모두) |
   | `·`, `⋅` | 공백 |
   | 줄바꿈 없는 공백과 얇은 공백(U+00A0, U+2007, U+2009, U+200A, U+202F) | 공백. 연속 공백은 하나로 |

   따라서 `"220 ㎚"`, `"25 ℃"`, `"3 µΩ·cm"`, `"148 W/(m·K)"`는 쓴 그대로 받습니다.
2. **철자 조회.** 단위 텍스트 전체를 고정된 철자표에서 찾습니다. 철자표는 받는 모든 철자를
   정식 단위 하나에 대응시킵니다: `W/(m K)`, `W/(m*K)`, `W/m/K`, `W m^-1 K^-1`,
   `W/(K m)`는 모두 `W/(m K)`입니다. 받지 않는 철자는 알려진 거부 목록에서 찾습니다. 둘 다에
   없으면 `E-UNIT-UNKNOWN`이며, "혹시" 후보는 대소문자를 무시했을 때 같은 메뉴 철자
   (`Mpa` → `MPa`)이고 suggestion으로 줍니다. 메뉴 밖의 철자도 대소문자를 무시하면 같을 때는
   메시지가 모든 읽기를 값과 함께 밝힙니다: `"1 ms/m"`은 `MS/m`(1e6 S/m, 메뉴에 있음)과
   `mS/m`(0.001 S/m, `electrical_conductivity` 메뉴에 없음)에 해당합니다.
3. **차원, 종류, 메뉴.** 단위는 물리량의 차원을 가져야 하고(`E-UNIT-DIMENSION`), `degC` 규칙을
   지켜야 하며(`E-DEGC-NOT-ABSOLUTE`), 물리량의 메뉴에 있어야 합니다(`E-UNIT-NOT-ACCEPTED`,
   메뉴를 보여 줌). 차원 오류는 그 단위를 메뉴에 가진 물리량을 밝히고, 그 차원의 대표 물리량을
   "Did you mean"으로 묻습니다(`MS/m`면 `electrical_conductivity`, `mm`면 `length`). 분광 키끼리는
   서로를 먼저 밝힙니다(`vacuum_wavelength`에 `"1550 THz"`: "Did you mean frequency?"). 모델
   파라미터(`lower_corner_frequency`, `plasma_energy` 등)와 `air_wavelength`는 밝히지 않습니다.
   거부 철자는 같은 차원의 물리량만 밝힙니다(`"MW"`는 megawatt, "which has the dimension of
   heat_rate"). 각도도 따지므로 `dB`를 `bend_loss`의 단위라고 하지 않습니다.
4. **변환**은 위와 같고, 이어서 허용 범위(`E-DOMAIN`)와 타당 범위(`W-MAGNITUDE`)를 봅니다.

**철자표.** 빌드 시점 생성기가 작은 문법으로 씁니다. 인수는 공백 하나나 `*`로 나누고, 분모는
`/x`, `/(x y)`, `/x/y`로 쓰며, 음의 거듭제곱을 한 줄로 쓰고, 인수의 모든 순서를 씁니다.
붙여 쓴 형태(`W/mK`, `Nm`)와 괄호 없는 `a/b c` 형태(`W/m K`)는 절대 쓰지 않습니다. 도구가 쓰는
정식 형태는 ASCII이며 인수를 공백 하나로 나누고, `/`는 많아야 하나, 인수가 둘 이상인 분모는
괄호로 묶고, 지수는 `^n`으로 씁니다: `W/(m K)`, `J/(kg K)`, `kg/m^3`, `S/m`, `1/K`,
`Ohm m`, `dB/m`. 출력에만 쓰는 두 단위는 지수가 반정수이며 괄호 안에 씁니다: `1/m^(1/2)`,
`1/m^(3/2)`(`m^(-1/2)`, `m^(-3/2)`로도 읽음). 어느 입력 메뉴에도 없습니다.

**알려진 거부 목록.** 같은 생성기가 알아보지만 거부하는 철자를 코드와 읽는 법과 함께 씁니다.

| 철자 | 코드 | 메시지 내용 예 |
|---|---|---|
| 닫힌 기호 목록에 없는 SI 접두 기호(`mPa`, `Mm`, `MW`, `MV`, `MOhm`, `dam`, `Tm` 등) | `E-UNIT-NOT-ACCEPTED` | "`mPa`는 millipascal". suggestion으로 `"10 MPa"`와 메뉴 단위로 쓴 같은 값 |
| 복합 단위 안의 `degC`(`W/(m degC)`, `ppm/degC`, `1/degC`, `degC/m`) | `E-DEGC-NOT-ABSOLUTE` | fix: 같은 숫자에 `K`(`"12 ppm/K"`) |
| 붙여 쓴 형태나 `a/b c` 형태 안의 `degC`(`J/kg°C`, `W/m°C`, `W/m degC`) | `E-UNIT-AMBIGUOUS` | `K`로 쓴 읽기(`J/(kg K)`)와 "write K". fix는 없음 |
| 메뉴 복합 단위의 대소문자 닮은꼴(`mW/(m K)` 자리의 `MW/(m K)`, `MOhm/mm`, `W/Mm^2`) | `E-UNIT-NOT-ACCEPTED` | "`MW/(m K)` is megawatt per metre kelvin" |
| 입력 메뉴의 복합 단위에서 인수 하나의 접두어만 흔한 다른 접두어(`p n u m k M G`, 미터에는 `c`도. 켈빈 인수는 제외)로 바꾼 것: `MW/m^3`, `mW/(m^2 K)`, `kW/m^3`, `V/cm`, `mS/cm`, `1/mm`, `km^2` | `E-UNIT-NOT-ACCEPTED` | "`MW/m^3` is megawatt per cubic metre. As written it is 5e6 W/m^3". suggestion으로 메뉴 단위로 쓴 같은 값 |
| 외래 단위(`degF`, `Mpsi`, `R`, `Np`, `Np/m`, `Btu`, `kgf/mm^2`, `oz`, `ft`, `lb`, `lbf`, `Torr`, `mmHg`, `cal`, `micron` 등) | `E-UNIT-NOT-ACCEPTED` | 정확한 환산(있으면 suggestion으로) |
| `^` 없는 거듭제곱(`m2`, `m3`, `um2`, `W/m2`) | `E-UNIT-NOT-ACCEPTED` | fix: `m^2` |
| 단위 `1` | `E-UNIT-NOT-ACCEPTED` | 무차원 값은 맨 숫자 |
| 붙여 쓴 형태와 `a/b c` 형태(`W/mK`, `J/kgK`, `Ohmm`, `Nm`, `kWh`, `W/m K`, `W/m^2 K`) | `E-UNIT-AMBIGUOUS` | 가능한 모든 읽기(`W/mK`: W/(m K) 또는 와트 매 밀리켈빈). fix는 없음 |

`bara`와 `psia`는 `absolute_pressure`에서 받고, `gauge_pressure`에서는
`E-ABSOLUTE-AS-LOAD`입니다. `barg`와 `psig`는 `absolute_pressure` 메뉴에 없고, 게이지·절대
표시가 붙은 값은 다른 단위로 바꿔 쓰자고 제안하지 않습니다. 절대 압력 = 게이지 압력 + 주변
압력이기 때문입니다. 두 목록 어디에도 없으면서 `degC`를 담은 단위 텍스트(`kW/(m degC)`)는
`E-UNIT-UNKNOWN`이며, 메시지가 복합 단위 안에는 `degC`를 쓰지 않는다고 알려 줍니다.

**닫힌 기호 목록.** 접두 기호는 하나씩 나열하며 생성하지 않습니다.

| 갈래 | 기호 |
|---|---|
| 길이 | `pm nm Angstrom um mm cm m km in mil` |
| 질량 | `mg g kg` |
| 시간 | `fs ps ns us ms s min h` |
| 온도 | `mK K degC`(오프셋 273.15, 절대 온도에만) |
| 전류 | `uA mA A kA` |
| 각도 | `urad mrad rad deg` |
| 주파수 | `Hz kHz MHz GHz THz` |
| 힘 | `mN N kN` |
| 압력, 응력 | `Pa kPa hPa MPa GPa bar mbar atm psi ksi`. 게이지 표시 `barg psig`, 절대 표시 `bara psia` |
| 에너지 | `meV eV mJ J kJ MJ` |
| 전력 | `pW nW uW mW W kW` |
| 전위 | `uV mV V kV` |
| 저항 | `nOhm uOhm mOhm Ohm kOhm` |
| 컨덕턴스 | `uS mS S kS MS` |
| 정전용량, 인덕턴스, 전하 | `fF pF nF uF F`; `pH nH uH mH H`; `pC nC uC mC C` |
| 물질량, 자기(예약) | `mol`; `mT T Wb` |
| 비, 로그 | `1 % ppm dB`(`dB`는 항상 전력비의 10·log₁₀) |

`MS`(메가지멘스)는 `electrical_conductivity` 메뉴(`MS/m`)에만, `mS`는 컨덕턴스 메뉴에만
있으므로 둘은 만나지 않습니다.

## 진단

진단은 `{code, severity, path, message, fix, suggestions, acknowledged}`이며
`<severity> <CODE> at <path>` 다음에 무엇이 잘못되었는지, 물리적으로 무슨 뜻인지, 그대로 쓸 수
있는 fix나 suggestion을 출력합니다(메시지는 영어).

```
error E-UNIT-NOT-ACCEPTED at physics.solid.conditions.bore.gauge_pressure
  "10 mPa": "mPa" is millipascal. As written it is 0.01 Pa. It is not accepted for gauge_pressure. Accepted: Pa kPa MPa GPa bar mbar psi ksi barg psig.
  Suggestion (not applied automatically): "10 MPa" (1e7 Pa; as written 0.01 Pa)
  Suggestion (not applied automatically): "0.01 Pa" (0.01 Pa)
```

값 하나에는 오류가 많아야 하나이며, 먼저 맞는 규칙이 이깁니다.

1. (나중의 문서 리더) 그 자리에서 거부되는 키
2. 모르는 키(여기서는 모르는 물리량 이름 `E-KEY-UNKNOWN`. 등록부의 기호와 거부 별칭으로 "혹시"를
   줌: `E` → `youngs_modulus`)
3. 차원 있는 자리의 맨 숫자: `E-UNIT-MISSING`
4. 문자 대응표 다음 조회. 두 목록 어디에도 없음: `E-UNIT-UNKNOWN`
5. 여러 뜻으로 읽히는 철자: `E-UNIT-AMBIGUOUS`
6. 다른 차원의 단위: `E-UNIT-DIMENSION`(`thermal_conductivity`에 `"58 MS/m"`: "a unit of
   electrical_conductivity")
7. 온도차나 복합 단위 안의 `degC`: `E-DEGC-NOT-ABSOLUTE`(복합 단위는 fix, 온도차는 suggestion만)
8. 그 밖의 알려진 거부 철자: 그 코드(읽는 법을 밝힌 `E-UNIT-NOT-ACCEPTED`, 게이지 자리의
   `bara`/`psia`는 `E-ABSOLUTE-AS-LOAD`)
9. 차원은 맞지만 메뉴에 없는 받는 철자: 메뉴를 보여 주는 `E-UNIT-NOT-ACCEPTED`
   (`vacuum_angular_wavenumber`에 `"6451.6 1/cm"`: "1/cm is a unit of vacuum_wavenumber")
10. 정확한 변환과 범위 검사: `E-DOMAIN`
11. 허용 범위: `E-DOMAIN`
12. 타당 범위: `W-MAGNITUDE`. 그럴듯한 접두 실수를 suggestion으로 줌(강철의 `"210000 Pa"`,
    1/K 숫자를 `ppm/K`로 쓴 `"1.2e-5 ppm/K"`)

90–110 kPa의 `gauge_pressure`는 `W-GAUGE-ATMOSPHERIC`도 냅니다. `q()`는 오류면 `UnitError`를
일으키고 경고는 각각 `UnitWarning`으로 냅니다. `convert()`는 둘 다 돌려줍니다. 등록부는 규칙의
진단 코드 66개 모두를 영어·한국어 한 줄 제목과 함께 담습니다(`DIAGNOSTIC_CODES`). 설계의 58개와
문서 리더를 위한 8개(`E-FORMAT`, `E-JSON`, `E-VALUE-FORM`, `E-MATERIAL-UNKNOWN`, `E-CONTRACT`,
`W-SHAPE-DROPPED`, `W-PIECE-DROPPED`, `I-MESH-CONTROL-RAISED`)입니다. 이 모듈은 그중 16개를
냅니다(`E-VALUE-FORM`과 `E-GAIN`은 `convert_array`와 `convert_complex`에서).

**fix**는 닫힌 목록에서만 나옵니다: 복합 단위 안의 `degC`를 `K`로, 빠진 공백
(`"2eV"` → `"2 eV"`, `"25℃"` → `"25 degC"`), `^` 없는 거듭제곱(`m2` → `m^2`), 무차원 물리량이나
개수에 쓴 숫자만 담은 문자열(`"0.3"` → `0.3`), 정수로 쓰지 않은 정수 개수(`2.0` → `2`). 붙임 형태, 문자 별칭, 정식이 아닌
철자는 쓴 그대로 받으며 `Conversion.text`가 정규화한 텍스트를 담습니다(`"148 W/m/K"`면
`"148 W/(m K)"`). 나머지는 모두 **suggestion**입니다: 대소문자·접두 후보(`"10 mPa"`에
`"10 MPa"`), 더 읽기 쉬운 메뉴 단위로 쓴 같은 값(`"2 MW"`에 `"2000 kW"`), `degC` 온도차의 같은
숫자를 `K`로, 타당 범위를 벗어난 그럴듯한 실수. 다른 단위로 바꿔 쓴 값은 정확히 같은 double로
되돌아오는 가장 짧은 숫자로 씁니다.

## 등록부

JSON 파일 두 개가 모듈 옆에 패키지 데이터로 들어갑니다.

- `physmat/quantities.json`: 검토하는 원본. 물리량마다 차원, 정식 단위, 닫힌 메뉴(`"1"`은
  맨 숫자), 종류(`ordinary`, `absolute`, `difference`, `fraction`, `count`), 계수(rank), 허용
  범위, 타당 범위, 쓰이는 곳, 허용 이름 수식어, "혹시"에 쓰는 기호와 거부 별칭, 차원 오류의
  힌트 표시(`hint`: 그 차원의 대표 물리량이면 true, 밝히지 않을 물리량이면 false. `family`:
  `spectral`), 영어·한국어 설명을 줍니다. 해당하는 곳에는 이름마다의 부호 문장 `sign`
  (`inward_heat_flux`: "positive enters the body"), `statistic_definitions`(`maximum_stress`),
  기반 항목과 다른 이름의 계수 `name_rank`(`inward_heat_flux`는 스칼라인 법선 성분), 모델
  파라미터가 속한 모델 `scope`도 줍니다. 정확한 계수를 가진 닫힌 기호 목록(`barg psig bara psia`의
  `gauge`/`absolute` 표시 포함), 접두어, 외래 단위, 문자 대응표, 진단 코드, 출력 전용 수식어
  낱말, 표시 묶음도 담습니다.
- `physmat/unit_tables.json`: 원본에서 생성합니다. 차원·정확한 계수·각도 지수·이름을 가진
  정식 단위, 받는 모든 철자, 알려진 거부 목록, 쓸 수 있는 모든 물리량 이름, 기반 항목과 다른
  이름의 쓰이는 곳과 계수, 표시 묶음마다의 구성원.

```bash
python -m physmat.units --check                    # exit 1 if unit_tables.json is stale
python -m physmat.units --write                    # regenerate it (deterministic, sorted)
python -m physmat.units youngs_modulus             # describe a quantity
python -m physmat._unit_tables --write             # regenerate without reading unit_tables.json
```

생성기는 패키지 안에 들어 있어 R3 검사가 설치한 휠에서도 돕니다. `unit_tables.json`을 읽을 수
없으면(예: 병합 충돌 뒤) `physmat.units`를 가져올 수 없습니다. `python -m physmat._unit_tables
--write`는 `quantities.json`만 읽으므로 이 파일을 복구합니다.

**이름.** 물리량 이름은 기호나 단위가 아닌 ISO식 전체 이름이며 `lower_snake_case`입니다:
`thermal_conductivity`, `electrical_conductivity`, `youngs_modulus`,
`linear_expansion_coefficient`, `thermo_optic_coefficient`. 생성된 이름은 등록부가 허용하는
곳에서 앞에 방향·역할·통계 낱말 하나까지, 뒤에 성분 낱말 하나를 붙입니다:
`ambient_temperature`, `stress_free_temperature`, `maximum_temperature`, `inward_heat_flux`,
`outward_heat_rate_per_depth`, `stress_xy`, `displacement_x`, `minimum_overlap`,
`prescribed_temperature`, `outward_reaction_heat_rate_per_depth`. `_per_depth` 물리량은 따로
등록한 항목입니다. 출력 전용 역할 낱말(`evaluation`, `unnormalized`, `mass_normalized`)이 붙은
이름은 출력이어서 쓰이는 곳이 `api`와 `result`뿐이므로, `evaluation_temperature`는 문서에서 읽지
않습니다. 단위를 바꾸는 역할 낱말은 `reference_conductivity`처럼 따로 기반 항목을 만듭니다
(`unnormalized_electric_field`는 단위가 없고, `mass_normalized_electric_field`는 1/m^(3/2)).
등록부에는 항목 242개와 이름 367개가 있습니다(`physmat.units.names()`).

메뉴 일부:

| 물리량 | 정식 단위 | 메뉴 |
|---|---|---|
| `length`, `depth`, `element_size` 등 | m | `pm nm Angstrom um mm cm m km in mil` |
| `temperature`(+ `ambient_`, `reference_`, `initial_`, `stress_free_`, `prescribed_`, 출력 `evaluation_`) | K | `K mK degC` |
| `temperature_difference`, `temperature_tolerance` | K | `K mK` |
| `thermal_conductivity` | W/(m K) | `W/(m K) mW/(m K) W/(cm K)` |
| `electrical_conductivity` | S/m | `S/m kS/m MS/m S/cm` |
| `youngs_modulus` | Pa | `Pa kPa MPa GPa psi ksi` |
| `gauge_pressure` | Pa | `Pa kPa MPa GPa bar mbar psi ksi barg psig` |
| `absolute_pressure` | Pa | `Pa kPa hPa bar mbar atm bara psia` |
| `linear_expansion_coefficient` | 1/K | `1/K ppm/K um/(m K)` |
| `vacuum_wavelength` | m | `nm um m` |
| `vacuum_wavenumber`(1/λ₀) | 1/m | `1/cm 1/m` |
| `vacuum_angular_wavenumber`(2π/λ₀) | rad/m | `rad/m rad/um` |
| `propagation_loss` | dB/m | `dB/m dB/cm dB/mm` |
| `relative_humidity` | 1 | 맨 숫자, `%` |

다른 메뉴는 `physmat.units.menu(name)`으로 봅니다. 데이터에 관한 메모:

- 모든 메뉴는 정식 단위를 담습니다(검사함). 시작 표가 접두 단위만 적은 곳에는 정식 단위를
  더했습니다: `capacitance_per_length`에 `F/m`, `inductance_per_length`에 `H/m`,
  `huray_sphere_radius`·`rms_roughness`·`air_wavelength`에 `m`, `photon_energy`와
  Drude–Lorentz 에너지에 `J`. 같은 까닭으로 닫힌 기호 목록에 `F`를 더했습니다(시작 목록에는
  `fF pF nF uF`만 있음). 나머지 메뉴는 모두 시작 표와 같습니다(항목마다 시험함).
- `overlap`은 결과 통계 낱말을 받으므로 `minimum_overlap`, `maximum_overlap`, `mean_overlap`이
  이름입니다. 입력 경계는 `overlap_threshold`입니다.
- 각도는 SI처럼 무차원이지만 단위마다 각도 지수를 기록하므로 suggestion이 `1/cm`를 `rad/m`로
  바꾸는 일은 없습니다. `vacuum_angular_wavenumber`의 정식 단위는 `rad/m`(1/m과 같은 숫자)로
  써서 메뉴에 들어가고 `vacuum_wavenumber`와 겹치지 않게 했습니다.
- `dB`는 따로 차원을 두어, 로그 값이 보통의 비로 바뀌거나 그 반대가 되지 않게 했습니다
  (`vacuum_wavenumber`에 `"2 dB/m"`은 차원 오류).
- 닫힌 목록의 모든 기호는 메뉴에 쓰이지 않아도 아는 단위이므로 `"5 mg"`는 모르는 단위가 아니라
  차원으로 거부됩니다.
- 타당 범위는 항목마다 정한 대로 |값|이나 부호 있는 범위에 적용합니다. 정확히 0인 값은 |값|의
  아래 경계에서 면제됩니다. 벡터의 노름과 텐서의 고유값은 문서 리더의 몫이고, 여기서는 숫자
  하나하나를 따로 보며 복소수는 실수부를 검사합니다.
- **부호 문장**(`Quantity.sign`, 영어·한국어)은 방향 낱말이 붙은 모든 이름, 열·전류·힘의 절점
  반력·하중·균형 항, `heat_flux`, `gauge_pressure`, `traction`, 그리고 복소 물리량에 있습니다:
  `refractive_index`(k ≥ 0이 손실), `relative_permittivity`와 `effective_index`(Im ≥ 0이 손실),
  `resonant_frequency`(Im < 0이면 감쇠), `propagation_loss`, `bend_loss`. 반력은 "구속이 물체에
  가하는" 뜻을 지키고, `ambient_convective_heat_rate`(대류 하중의 주변 항)는 "물체로 들어감"입니다.
  경계에서 합한 보고 값은 모두 `outward_`입니다.
- **통계 정의.** `maximum_displacement`는 절점 변위의 유클리드 노름 가운데 가장 큰 값,
  `maximum_stress`는 요소들에 걸친 면내 직교 응력 성분의 절댓값 가운데 가장 큰 값이며
  (`Quantity.definition`), 둘 다 스칼라입니다.
- **셀마이어 파라미터** `constant`(A, 타당 범위 ≥ 1), `strength`(Bᵢ ≥ 0),
  `resonance_wavelength`(`nm um m`), `resonance_wavelength_squared`(Cᵢ, `nm^2 um^2 m^2`)는
  `scope`가 `refractive_index` 모델 `sellmeier`이며 차원 힌트에서 밝히지 않습니다.
- 균형 결손(`heat_rate_imbalance`, `current_imbalance`, `electric_power_imbalance`,
  `force_imbalance`), 절점 전류와 힘, `stiffness_energy_functional`(전체 변형률의 ½ uᵀKu. 저장된
  탄성 에너지가 아님), `minimum_triangle_angle`(rad), 모드 추적 설정과 근거, 정규화하지 않은
  모드 필드와 질량 정규화한 모드 필드의 출력 항목이 있습니다. `target_frequency`는 > 0이고,
  `subdivision_count`는 벡터(개수 2개 또는 3개)이며, 결과 요약이 되풀이하는 입력은 모두
  `result`에도 둡니다(`heat_transfer_coefficient`, `body_force_density`, `traction`,
  `gauge_pressure`, `target_frequency`, `mode_count`, `pml_` 설정, 추적 문턱값,
  `beam_waist_radius`, `position`).
- **표시 묶음**(`display_groups()`): `length`는 모든 길이 물리량 이름과 맨 형상 숫자를 담고,
  단위는 `LENGTH_UNITS` 가운데 하나입니다. 문서의 `display_units`는 묶음이나 물리량을 지정합니다.
- **라이브러리 기준 온도.** 내장 재료마다 광학 데이터의 온도를 `Material.datum_temperature`(K)로
  밝히고, 출처가 밝히지 않으면 `datum_assumed`입니다([physmat 개요](overview.md#내장-재료)).

## 형상 피코미터 격자

`length_to_pm(value, length_unit)`은 형상 길이를 부호 있는 int64 피코미터 격자에 올립니다.
맨 형상 숫자는 `length_unit`(`pm nm Angstrom um mm cm m in mil`, 모두 pm의 정수배)로 읽고,
자기 단위가 붙은 물리량 문자열(`"0.5 nm"`)은 그 단위로 읽습니다. 정확한 값을 짝수 쪽으로 한
번 반올림합니다. 1e-3 pm 미만의 이동은 `I-PM-ROUNDING`(`0.30000000000000004` 같은 이진 잡음),
그 이상은 `W-PM-ROUNDING`이며 둘 다 쓴 값, 저장한 값, 이동량을 밝힙니다. `pm_to_m(k)`는
`float(Fraction(k, 10**12))`이므로 `mm` 구성 요소에 `100`으로 쓴 꼭짓점은 정확히 `0.1`이
됩니다. 약 ±9.2e6 m를 넘는 값은 `E-DOMAIN`입니다.

## Python API

| 이름 | 쓰임 |
|---|---|
| `q(value, quantity)` | SI float. `UnitError`를 일으키고 `UnitWarning`을 냄 |
| `q_array(values, quantity)` | 단위 붙은 배열, 무차원 배열, 물리량 문자열 목록의 SI 목록 |
| `convert(value, quantity, path=...)` | `value`, `exact`(Fraction), `unit`, `text`, `diagnostics`, `number_text`, `unit_text`를 가진 `Conversion`. 잘못된 값에 예외를 일으키지 않음 |
| `convert_array(values, quantity, path=...)` | `values`, 항목마다의 `Conversion`, 모든 진단을 가진 `ArrayConversion`. 잘못된 값에 예외를 일으키지 않음 |
| `convert_complex(value, quantity, path=..., allow_gain=False)` | exp(−iωt)의 `ComplexConversion`: 실수 값, `{re, im}`, `{n, k}`. 수동 재료에는 `E-GAIN` |
| `is_quantity_text(s)` | 숫자, 공백, 두 표 가운데 하나의 단위 |
| `format(value, quantity, unit)` | 정확히 `value`로 되돌아오는 가장 짧은 숫자로 쓴 물리량 문자열 |
| `quantity(name)`, `menu(name)`, `names()` | 등록부 조회. `Quantity` 객체는 읽기 전용이며 그 이름의 `rank`, `places`, `sign`, `definition`, `scope`를 줌 |
| `display_groups()` | 표시 묶음(읽기 전용) |
| `normalize(text)` | 문자 대응표, 붙임 형태, 공백 규칙 |
| `length_to_pm(value, length_unit)`, `pm_to_m(k)` | 형상 격자 |
| `generate_tables()` | `quantities.json`에서 만든 `unit_tables.json` 텍스트 |
| `Diagnostic`, `Fix`, `Suggestion`, `DIAGNOSTIC_CODES` | 진단. `Fix.patch(pointer)`는 JSON Patch 연산 하나 |

`format`과 `names`는 `__all__`에 없으므로 `from physmat.units import *`가 내장 `format`이나
`physmat.names`를 가리지 않습니다. `units.format(...)`, `units.names()`처럼 모듈 이름을 붙여
부릅니다. `pm_to_m`은 정수(`int`나 numpy 정수)만 받습니다.

`import physmat.units`는 표준 라이브러리만 있으면 됩니다. 이제 `physmat`은 다른 하위 모듈과
이름을 처음 쓸 때 읽으므로 numpy와 scipy는 재료 모듈만 가져옵니다.

## 검사

`tests/physmat/test_units.py`는 구현 전에 정한 검사를, 등록부와 따로 쓴 정확한 SI 계수 표에
대해 구현합니다.

| 검사 | 시험 |
|---|---|
| R1 모든 메뉴의 모든 단위가 표본 10진수를 `float(Fraction(text) × factor)`(+ `degC` 오프셋)와 비트까지 같게 바꿈. `"200 GPa"`, `"200000 MPa"`, `"2e11 Pa"`가 같고 `"25 degC"` == 298.15 | `test_r1_*` |
| R2 `str.casefold()`로 같은 두 철자를 가진 메뉴가 없음 | `test_r2_*` |
| R3 고정 표가 생성기 출력과 바이트까지 같고, 해시 시드가 달라도 같음 | `test_r3_*` |
| R4 문자 대응표의 모든 항목, 위 첨자, 공백을 표로 시험. NFKC 없음 | `test_r4_*` |
| R5 알려진 거부 목록의 모든 항목이 그 코드와 읽는 법을 냄. 설계가 이름을 든 철자는 모두 고정해 시험 | `test_r5_*` |
| R6 복합 단위 안의 `degC`는 값을 지키는 K fix와 함께 거부, 온도차는 suggestion만이고 fix는 없음 | `test_r6_*` |
| R7 `thermal_conductivity`의 `"58 MS/m"`가 `electrical_conductivity`를 밝힘. 힌트를 정확히 시험 | `test_r7_*` |
| R8 `"1e400 Pa"`와 `"1e-330 m"`는 `E-DOMAIN` | `test_r8_*` |
| R9 numpy와 scipy를 막아도 표준 라이브러리만으로 동작 | `test_r9_*` |
| R10 `q()`는 float, `q_array()`는 목록. 맨 숫자는 무차원 물리량에만 | `test_r10_*` |
| R11 정식 단위가 메뉴에 있고, 메뉴의 모든 단위가 물리량의 차원을 가짐. 모든 메뉴가 시작 표와 같음 | `test_r11_*` |
| R12 기존 physmat 시험이 바뀌지 않고 통과함 | `test_r12_*` |
| 문서 리더를 위한 등록부 추가: 새 이름마다 단위와 쓰이는 곳, 리더의 코드, 방향 낱말이 붙은 모든 이름의 부호 문장, 통계 정의와 계수, 반정수 지수의 출력 단위, `length` 표시 묶음, 접두어를 바꾼 입력 복합 단위를 읽는 법과 함께 거부(모르는 단위가 되지 않음), `convert_array`, `convert_complex`와 `E-GAIN`, 라이브러리 기준 온도, 잘못된 이름 필드를 생성기가 거부 | `test_p2_*` |

이 파일에는 우선순위 규칙마다, 내는 코드마다 시험이 하나씩 있으며 fix, suggestion(모든
suggestion이 보여 준 SI 값으로 되돌아옴), 메시지, 타당 범위, pm 격자, numpy 입력, 호출한 쪽의
decimal 컨텍스트, 모든 메뉴 단위의 `format` 왕복, 깨진 `unit_tables.json`의 복구도 검사합니다.

```bash
python -m pytest -q tests/physmat
```

## 아직 하지 않은 것

- 변환기는 `simcase`의 형식 0.3 읽기만 부르며(슬롯 표, 10진수를 보존하는 JSON 읽기·쓰기, 성분
  객체, 범위, 모델 계수, `accept`를 가진 주석 값과 함께;
  [문서 형식 0.3](../simcase/document_format.md)), 아직 어떤 문서 종류도 그 형식을 읽지 않습니다.
  `galerkin`, `sipi`, Studio는 부르지 않습니다. JSON Schema, 표, 임피던스, 생성 문서 표는 아직
  하지 않았습니다.
- 값 여러 개가 필요한 검사(음속, 섭씨를 켈빈으로 쓴 값, 메시 추정 등)와 `E-SPECTRAL`,
  `E-BASIS`는 여기에 없습니다.
- `result`에 둔 되풀이 입력 목록은 2단계 명세가 대응시킨 오늘의 결과 요약에서 왔습니다. 문서
  종류마다의 단계가 바꾼 결과와 대조합니다.
- 메시지는 영어입니다. 등록부는 모든 코드에 영어·한국어 제목을 둡니다. 유니코드 표시
  형태(`µm`, `°C`, `W/(m·K)`)와 표시 프로필은 여기에 없습니다.
- 물리 상수, 같은 단위 쌍 목록, 결합 표는 아직 등록부에 없고, 항목에 `display`,
  `depth_exponent`, `not_to_be_confused_with` 필드도 아직 없습니다(표시 형태와 적분 기준은 나중에
  옵니다).
- 등록부에서 뺀 것: `design_velocity`(단위가 파라미터에 따라 다름), `huray_populations`(거칠기
  항목의 목록), 공진기 커널 계수(내부용).
