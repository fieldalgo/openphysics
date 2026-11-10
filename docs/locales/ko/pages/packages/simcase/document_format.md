# 문서 형식 0.3: 정확한 읽기, 슬롯 표, 진단

[English](../../../../../packages/simcase/document_format.md) | **한국어**

[문서 홈](../../index.md) · [simcase 개요](overview.md) ·
[physmat.units](../physmat/units.md)

상태: **형식 0.3의 공용 읽기가 들어왔고, 아직 어떤 물리 종류도 형식 0.3을 읽지 않습니다.**
제공 예제와 오늘 쓰는 문서는 모두 `"openphysics": "0.2"` 형식이며 예전과 똑같이 읽힙니다.
envelope가 JSON 문자열 `"0.3"`인 문서만 여기 적은 읽기를 거칩니다. 단위·이름 배치에서 각 종류의
단계가 그 종류의 물리 슬롯을 줄 때까지, 그 종류의 0.3 문서는 `E-CONTRACT`("documents are not
read in format 0.3 yet")로 거부됩니다. 종류는 하나씩 옮겨 갑니다(열, 전기·Joule, 역학,
`em.modes2d`, `em.cavity3d`). 마지막 종류가 옮겨 간 뒤 0.2 읽기를 없앱니다.

형식 0.3은 오늘의 문서 뼈대(`geometry`, `materials`, `physics.<이름>`, `mesh`, `study`,
`results`)를 그대로 두고 단위·이름 규칙이 요구하는 것만 바꿉니다.

- **차원이 있는 값은 모두 단위를 함께 씁니다.** 데이터시트처럼 `"200 GPa"`, `"25 degC"`,
  `"0.25 um"`로 씁니다. 차원이 있는 자리의 맨 숫자는 0도 포함해 `E-UNIT-MISSING`입니다
  (`"0 V"`). 무차원 값과 개수는 맨 숫자로 남습니다(`0.3`, `2`).
- **키는 등록부의 전체 물리량 이름입니다.** `thermal_conductivity`, `youngs_modulus`,
  `element_size`, `minimum_angle`. 단위 접미사와 기호는 쓰지 않습니다.
- **`units` 블록이 없습니다.** 형상 구성 요소마다 `length_unit`을 밝히고 그 맨 형상 숫자는 이
  단위로 읽습니다. 평면 구성 요소는 `depth`도 밝힙니다.
- **진단에는 코드가 붙고 버려지지 않습니다.** 진단 하나는 `{code, severity, path, message, fix,
  suggestions, acknowledged}`이며 `simcase validate`와 `simcase run`이 출력합니다.

단위, 메뉴, 코드, 정확한 변환은 [`physmat.units`](../physmat/units.md)의 것이고, 이 문서는
문서가 그것을 어떻게 쓰는지 적습니다.

## 읽기: 정확한 JSON

`simcase.reader`가 문서 텍스트를 읽습니다.

| 입력 | 결과 |
|---|---|
| 소수점이나 지수가 있는 숫자 | 그 텍스트의 `decimal.Decimal`(`0.1000000000000000000001`은 그 10진수 그대로) |
| 정수 | `int` |
| `NaN`, `Infinity`, 잘못된 JSON, 해독할 수 없는 바이트 | `E-JSON` |
| UTF-16이나 UTF-32 텍스트 | `E-JSON`("UTF-8로 저장하세요") |
| 맨 앞의 UTF-8 바이트 순서 표시 | 받아들이고 버림 |
| 어느 깊이에서든 중복 키 | 그 객체 경로의 `E-KEY-DUPLICATE` |
| 1000자를 넘는 숫자 리터럴 | 어떤 계산보다 먼저 그 경로의 `E-DOMAIN` |
| `-0`, `-0.0` | 해석한 트리에서 +0.0 |

`Document.from_dict`는 Python 객체를 같은 방식으로 읽습니다. float은 가장 짧은 `repr`로 읽고
(`0.1`은 10진수 0.1), 유한하지 않은 float이나 문자열이 아닌 키는 `E-JSON`입니다.
`reader.dumps`는 같은 인수로 `json.dumps`가 쓰는 것을 쓰고, `Decimal`은 그 텍스트대로 씁니다.
`Decimal`이 없는 트리에서는 바이트가 같습니다.

## envelope

`"openphysics"`는 JSON **문자열** `"0.3"`이어야 합니다. 키가 없거나, 숫자 `0.3`이거나,
`"0.2"`나 다른 값이면 `openphysics`에서 `E-FORMAT`이고 읽기를 멈춥니다. 이 읽기는 형식 0.2
문서를 읽지 않습니다. 문서의 물리 유형이 오늘처럼 종류를 고르며, 아직 형식 0.3을 읽지 않는
종류는 `physics.<이름>.type`에서 `E-CONTRACT`로 거부합니다.

최상위 키: `openphysics name geometry materials physics mesh study results display_units`.
`units`는 "units travel with each value"와 함께 `E-KEY-UNKNOWN`입니다. `display_units`(선택)는
물리량 이름이나 표시 묶음 `length`를 그 메뉴의 단위에 대응시킵니다. 어떤 값도 바꾸지 않고
표시(extent 줄)에만 씁니다.

## 슬롯 표

`simcase.slots`는 문서의 경로마다 슬롯 하나를 대응시킵니다. 구조 객체나 목록, 등록부 물리량(문서
자리나 재료 자리), 형상 숫자, `length_unit`, `depth`, 열거값, 이름, 재료 참조, 선택자, 참·거짓,
문자열, study 경로, 개수 목록, 확인(acknowledgement), 거부된 키 가운데 하나입니다. 공용 슬롯
(envelope, 세 가지 형상 형태, 재료, 메시, study, 결과)은 `simcase.slots`에 있고, 물리 종류마다
`physics.<이름>` 항목의 슬롯을 데이터로 가져옵니다(`PhysicsKind.slots`). 패턴 문법: 점으로 나눈
마디, 맵 키 하나는 `*`, 목록 항목 하나는 `[]`, 글자 그대로의 키는 `["a.b"]`, `physics.*` 뒤의
`{type}`은 그 유형의 항목, `geometry` 뒤의 `<rect>`, `<regions>`, `<v1>`은 그 형상 형태입니다.

```bash
python -m simcase.slots --check      # exit 1 when slot_table.json differs from the generator
python -m simcase.slots --write      # regenerate it (deterministic, sorted)
```

`slot_table.json`은 생성해 고정한 뒤 함께 배포하며, `tests/simcase/test_slots.py`가 `--check`를
돌립니다. 지금은 공용 슬롯만 있고 종류는 없습니다.

**훑기.** 작성된 경로마다 문서 순서대로 슬롯 하나가 정확히 맞아야 하며, 먼저 해당하는 규칙이 그
경로의 오류 하나를 정합니다.

1. 거부된 키는 그 키의 코드와 메시지(`units`; 재료 기록의 `base`; 하중 자리의
   `absolute_pressure`는 `E-ABSOLUTE-AS-LOAD`).
2. 알 수 없는 키는 그 경로의 `E-KEY-UNKNOWN`. 형제 이름, 형제 물리량의 등록부 기호와 거부 별칭
   (`E`는 `youngs_modulus`를 권함), 0.2 이름의 닫힌 표(`mesh.size`는 `element_size`를,
   `outward_flux_w_m2`는 `inward_heat_flux`를 알리고 값의 부호가 바뀐다는 것을 메시지로만
   알리며 fix로 주지 않음)에서 "did you mean"을 찾습니다.
3. 값의 형태: `E-VALUE-FORM`(숫자 자리의 참·거짓, 물리량 문자열 자리의 객체, 문자열 넷 이상의
   목록, `{"in_m": ...}`).
4. 값 자체는 `physmat.units`로 한 번 변환하며, 단위·메뉴·범위·타당 범위 코드를 그쪽이 냅니다.

그다음 필수 키(빠진 경로의 `E-KEY-MISSING`)와 아래 기본값을 봅니다.

## 값의 형태

| 형태 | 예 | 자리 |
|---|---|---|
| 물리량 문자열 | `"0.25 um"`, `"45 W/(m K)"` | 차원이 있는 스칼라 |
| 태그 배열 | `{"unit": "s", "values": [0, 0.1, 0.3]}` | 계열(`study.time`, sweep 값) |
| 물리량 문자열 3개 이하의 짧은 목록 | `["0 um", "0.11 um"]` | 벡터(`position`, `traction`) |
| 성분 객체 | `{"x": "0 mm"}` | 변위 성분 |
| 주석 값 | `{"value": "4 J/(m^3 K)", "accept": {"W-MAGNITUDE": "manufactured solution"}}` | 모든 물리량 자리 |
| 맨 숫자 | `0.3`; 개수는 `2`(`2.0`은 안 됨) | 무차원 값과 개수 |
| 복소수 | `{"re": 4.0, "im": 0.04}`; `refractive_index` 안에서는 `{"n": 3.48, "k": 0.01}` | exp(−iωt) 규약; 허수부가 음수면 `E-GAIN` |

주석 값은 경고를 확인합니다. 경고는 그대로 출력·저장되며 그 이유와 함께 `acknowledged`로
표시됩니다. 오류는 확인할 수 없습니다.

## 형상: 세 형태, 각각 `length_unit` 하나

| 형태 | 알아보는 법 | `length_unit` | `depth` |
|---|---|---|---|
| 평면 직사각형 | `geometry: {length_unit, depth, domain}` | `geometry.length_unit` | `geometry.depth` |
| 평면 영역 | `background`나 `shapes` 키 | `geometry.length_unit` | `geometry.depth`(2D); `zmin`/`zmax`가 있는 3D `domain`이면 `E-KEY-UNKNOWN` |
| 버전 1 구성 요소 | `"version": 1` | `geometry.components.<c>.length_unit` | `2d` 구성 요소의 `geometry.components.<c>.depth`; `axisymmetric`과 `3d`에서는 `E-KEY-UNKNOWN` |

- `length_unit`은 필수이며 `pm nm Angstrom um mm cm m in mil` 가운데 하나입니다. `µm`와 `Å`는
  문자 대응표로 읽습니다. `km`는 `E-UNIT-NOT-ACCEPTED`, `{"in_m": x}`는 `E-VALUE-FORM`입니다.
  구성 요소 형태에서 `geometry.length_unit`과 `geometry.depth`는 `E-KEY-UNKNOWN`입니다.
- `depth`는 길이(`"40 mm"`, `> 0`)이거나 깊이 1 m당을 뜻하는 `null`입니다.
- **형상 숫자**는 구성 요소 단위의 맨 숫자이며 1 pm 정수 격자에 한 번 올립니다
  (`physmat.units.length_to_pm`). 옮겨진 값은 `I-PM-ROUNDING`(1e-3 pm 미만)이나
  `W-PM-ROUNDING`입니다. 해석한 트리에서 형상 숫자는 그 pm 개수의 `pm_to_m`입니다.
- **버전 1 블록**([형상 문서](geometry_document.md))은 문법을 그대로 두고 구성 요소마다 읽습니다.
  각 구성 요소의 숫자와 식 안의 리터럴은 그 구성 요소의 `length_unit`이므로 두 구성 요소가 다른
  단위를 쓸 수 있습니다. 형상 `parameters`는 모든 구성 요소 밖에 있고 단위를 함께 씁니다. 길이
  파라미터의 `value`와 `range`는 물리량 문자열(`"0.5 um"`)이나 다른 파라미터의 식입니다. 맨
  길이 값은 `E-UNIT-MISSING`, 단위처럼 읽히는 파라미터 이름(`nm`, `h`, `bar`)은 `E-ID-CLASH`, 식
  안의 단위(`"220 nm + gap"`)는 `E-EXPRESSION-KIND`("declare a parameter"), 파라미터 식에서
  길이에 더한 맨 숫자는 `E-UNIT-MISSING`입니다. 파라미터 값은 정확한 피코미터이므로 설계 속도
  V = dx/dp는 0.2와 같은 수입니다.
- **요소 크기**는 식이 아닌 물리량 문자열입니다. 배경, 도형, 형상 요소, `mesh`, 메시 제어의
  `element_size`(오늘의 `mesh_size`와 `size`)입니다.
- 형상 수준의 경고는 평면 블록이나 구성 요소의 `accept`(`{"W-GEOMETRY-SCALE": "<이유>"}`)로
  확인합니다.

## 재료

`materials: {<이름>: <기록>}`은 오늘과 같습니다. 로컬 이름은 `:`이 없는 비어 있지 않은 문자열입니다
(`E-ID-CLASH`). 기록의 키는 등록부 물성 이름(`thermal_conductivity`,
`volumetric_heat_capacity`, `electrical_conductivity`, `youngs_modulus`, `poisson_ratio`,
`linear_expansion_coefficient`, `mass_density`, `refractive_index`,
`relative_permittivity`, `relative_permeability`)과 `source`입니다. 있는 물성은 모두 변환·검사하며,
실행의 어떤 물리도 읽지 않는 물성은 `I-UNUSED-PROPERTY`입니다. 이번 릴리스가 읽지 않는 등록부
물성(`shear_modulus`, `bulk_modulus`, `elasticity_tensor`, `mean_linear_expansion_coefficient`,
`volumetric_expansion_coefficient`, `specific_heat_capacity`, `loss_tangent`,
`reference_resistivity`)은 `E-CONTRACT`, `base`와 `description`은 `E-KEY-UNKNOWN`입니다.
`refractive_index`는 셀마이어 모델 형태 `{"model": "sellmeier", "constant", "terms":
[{"strength", "resonance_wavelength_squared"}], "valid": {"vacuum_wavelength": [lo 또는 null,
hi]}, "reference_medium": "vacuum"}`도 받습니다.

**재료 참조**는 로컬 이름이거나(자기 기록으로만 풀리며, 없으면 `E-MATERIAL-UNKNOWN`이고 라이브러리
이름이면 `"physmat:<Name>"`을 권함) `physmat:<Name>`입니다. 후자는 대소문자 접기나 별칭 없이
`physmat.names()`와 정확히 맞춥니다(`E-LIBRARY-UNKNOWN`과 "did you mean": `physmat:sio2` →
`physmat:SiO2`). 어떤 라이브러리 참조를 쓸 수 있는지는 종류마다 정합니다(도파 모드: 모두; 공진기:
`physmat:vacuum`; 열·전기·Joule·역학: 없음, `E-CONTRACT`). 출처가 온도를 밝히지 않은 라이브러리
기록은 그 참조에서 `I-DATUM-ASSUMED`입니다.

## 기본값

차원이 있는 값에는 기본값이 없습니다. 읽기는 아래 기본값만 적용하고 각각을 `defaults_applied`에
`{path, value, reason}`으로 남기며, 작성된 트리는 바꾸지 않습니다.

| 경로 | 기본값 |
|---|---|
| `materials` | `{}` |
| `geometry.shapes`(평면 영역) | `[]` |
| `mesh.minimum_angle`(`mesh.element_size`가 있을 때) | `"28 deg"`; 최대 `"33 deg"` |
| `mesh.element_count_limit`(`mesh.element_size`가 있을 때) | `600000` |
| `materials.*.refractive_index.constant` | `1` |
| 종류마다의 기본값(`name`, `study`, `results`, 개수, 경계 조건) | 그 종류와 함께 |

## 교차 검사와 extent 줄

메시를 만들기 전에 형상 구성 요소마다 그 숫자가 무엇을 뜻하는지 말하는 **extent 줄**이 하나씩
나옵니다.

```text
geometry (length_unit mm): 40 mm x 20 mm = 0.04 m x 0.02 m; depth per metre (null); element_size 2 mm, about 760 triangles
```

직사각형은 `subdivision_count 32 x 16 = 1024 triangles`로, 공진기는
`cavity size x f/c = ...`로 끝납니다. 그다음 검사는 다음과 같습니다.

| 코드 | 조건 |
|---|---|
| `E-MESH-ESTIMATE` | 추정 삼각형 수(영역의 2A/h², 자기 크기를 가진 도형·형상 요소·제어마다 같은 값, 반경 grading)가 `mesh.element_count_limit`를 넘음. 메시지는 적당한 수를 주는 `length_unit`을 알림 |
| `W-GEOMETRY-SCALE` | 추정이 10 미만; 또는 `length_unit`이 `m`이고 형상 숫자가 모두 정수이며 대각선이 10 m를 넘음(밀리미터를 미터로 씀); 또는 진공 파장이 있을 때 가장 작은 형상이 파장의 1e-3..1e3 밖이거나 영역이 1e4를 넘음 |
| `W-CAVITY-SCALE` | 공진기 크기 × 목표 주파수 / c가 0.1..100 밖 |
| `W-DEPTH-RATIO` | 깊이와 면내 대각선의 비가 1e-6..1e6 밖 |
| `W-CELSIUS-AS-KELVIN` | 다른 절대 온도가 250 K 이상인데 K나 mK로 쓴 절대 온도가 150 K 미만 |

아직 검사하지 않는 것: `W-TIME-SCALE`, `W-WIEDEMANN-FRANZ`, `W-SOUND-SPEED`,
`W-STRAIN-LARGE`, `W-DATUM-FAR`, `W-LIBRARY-RATIO`, `W-TEMPERATURE-RANGE`,
`W-EFFECTIVE-INDEX-RANGE`, `W-ANISOTROPY-MISSING`, `E-TEMPERATURE-NONPOSITIVE`,
`I-VERTEX-SNAPPED`, `E-SCALE-MISMATCH`. 직사각형 문서에는 태그된 길이가 없으므로 잘못 밝힌
직사각형은 extent 줄과 밀리미터를 미터로 쓴 유형으로만 드러납니다.

## 진단

문서의 진단은 덧붙이기만 하는 목록 하나(`doc.diagnostics`)입니다. 어떤 단계도 항목을 지우거나
바꾸지 않으며, 문서를 다시 검증하면 새 항목만 덧붙습니다. 코드는 physmat의 닫힌 목록입니다.
**fix**는 모든 SI 값을 지키며 묻지 않고 적용해도 됩니다(`"25K"` → `"25 K"`, `"12 ppm/degC"` →
`"12 ppm/K"`, 개수의 `2.0` → `2`, 문자 별칭 `"1 µm"` → `"1 um"`). **suggestion**은 뜻을 바꿀 수
있어(`"10 mPa"` → `"10 MPa"`) 사람만 적용합니다.

심각도: 오류는 문서를 거부하고, 경고는 출력하며, 정보는 나열합니다. 명령줄의 종료 코드는 **0**
유효(실행도 성공), **1** 실행 실패, **2** 문서 오류(읽을 수 없는 JSON과 없는 파일 포함), **3**
`--strict` 때문에만 거부(확인하지 않은 경고나 `I-DATUM-ASSUMED`)입니다.

`DocumentError`와 `GeometryError`는 `(message, *, path=None, code="E-CONTRACT",
diagnostics=())`를 받습니다. 모든 종류의 거부처럼 메시지 하나로 낸 거부는 그 메시지를 그대로
출력하고 `E-CONTRACT` 진단 하나로(메시지가 시작하는 경로에) 기록됩니다. 읽기의 거부는 오류마다
한 줄을 출력합니다. `E-CONTRACT` 줄은 그 메시지, 다른 코드는 `<path>: <message> (<code>)`입니다.
경고와 정보는 `str()`이 아니라 `.diagnostics`에 있습니다.

## 명령줄

```bash
python -m simcase validate model.json [--json] [--strict]
python -m simcase run model.json [-o out] [-q] [--strict]
python -m simcase explain model.json [--json]
python -m simcase fix model.json [--in-place]
```

- `validate`는 extent 줄, 요약, 모든 진단을 출력합니다. `--json`은
  `{"valid", "extent", "diagnostics", "defaults_applied", "resolved_inputs"}`를 출력합니다.
- `run`은 메시를 만들기 전에 extent 줄과 진단을 출력하고 `validate`처럼 거부합니다. `log.txt`도
  같은 줄로 시작합니다.
- `explain`은 입력마다 한 줄을 냅니다. 경로, 작성한 텍스트, SI 값, 정식 단위, 형상 숫자의
  `length_unit`, 그리고 각 기본값과 그 이유입니다.
- `fix`는 fix마다 그 경로의 JSON 문자열이나 숫자 토큰만 바꿔 적용하므로 다른 바이트(공백, 키 순서,
  줄바꿈, 바이트 순서 표시)는 그대로입니다. suggestion은 적용하지 않고, 한 일을 나열하며, 문서가
  전에 해석한 SI 값이 하나라도 비트 단위로 달라지면 쓰지 않습니다. `--in-place`가 없으면 결과를
  출력합니다.

형식 0.2 문서에서 `validate`와 `run`은 예전과 같고, `explain`과 `fix`는 거부합니다.

## Python

```python
from simcase import Document
from simcase import reader

doc = Document.load("model.json")       # .loads(text), .from_dict(obj); DocumentError on any error
doc, diagnostics = reader.check(text)    # without raising: for validate, explain, fix
```

| 멤버 | 뜻 |
|---|---|
| `doc.data` | 바뀌지 않는 작성된 트리(숫자가 `Decimal`이므로 `json.dumps`는 거부함) |
| `doc.si` | 해석한 SI 트리. `data`의 키에서 `accept`를 뺀 것이며, 물리량 문자열은 SI float, 태그 배열과 짧은 목록은 목록, 복소 값은 `complex`, 개수는 `int`, 형상 숫자는 미터 |
| `doc.exact(path)`, `doc.pm(path)`, `doc.um(path)` | 정확한 유리수 SI 값; 형상 숫자의 pm 개수; 정확한 값에서 얻은 마이크로미터(`si / 1e-6`은 쓰지 않음) |
| `doc.degrees(path)` | 메셔가 받는 각도 숫자. `deg`로 썼으면 작성한 숫자 |
| `doc.authored(path)`, `doc.resolved_inputs()` | 작성한 토큰; `{path: {authored, value, unit[, length_unit]}}` |
| `doc.defaults_applied`, `doc.diagnostics`, `doc.extent_lines()` | 위와 같음 |
| `doc.canonical_json(separators=(",", ":"))` | `data`를 정렬하고 10진수를 보존한 JSON. 0.2 문서에서는 `json.dumps(data, sort_keys=True, ...)`가 주던 바이트이며 결과 스냅샷 보호에 씀 |
| `doc.source_bytes`, `doc.save(path)` | 읽은 바이트; 0.3 문서는 읽은 그대로 저장 |
| `doc.with_value(path, si, exact)` | 해석한 값 하나를 바꾼 사본(sweep 지점) |

`simcase.quantities`는 등록부 함수(`q`, `convert`, `menu`, `quantity`, `names`, `format`)를
다시 내보냅니다. `simcase.results_common`은 모든 0.3 결과가 함께 쓰는 것을 담습니다. 값 객체
`{"value", "unit"}`, 태그 배열, exp(−iωt) 규약의 복소 값, `field_*` 맵, 요약 envelope
(`diagnostics`, `defaults_applied`, `resolved_inputs`, `extent`, `timing.wall_time`),
`metadata_json`, `model.json`(작성한 바이트), `log.txt` 머리말입니다.
`simcase.export.inject_field_data`는 VTU 단위 메타데이터를 넣습니다. ASCII `UInt8` 배열 두 개
`units`와 `conventions`를 담은 `<FieldData>` 블록이며, 각 배열은 JSON 객체의 UTF-8 바이트입니다
(`String`은 meshio 5.3이 다시 읽지 못하고, meshio는 VTU를 쓸 때 field data를 버립니다). layout이
`export.RETIRED_LAYOUTS`에 있는 `fields.npz`는 이름을 밝혀 거부합니다. 각 종류의 단계가 식별자를
바꿀 때 이 표를 채웁니다.

## 검사

| 검사 | 시험 |
|---|---|
| 정확한 읽기: `"200 GPa"`, `"200000 MPa"`, `"2e11 Pa"`는 같은 double; `"25 degC"`는 298.15에 가장 가까운 double; 긴 리터럴은 그 텍스트에서; 마이크로미터와 각도는 정확한 값과 작성한 값에서 넘김; `model.json`은 읽은 바이트와 같음; Python dict는 그 JSON 텍스트처럼 해석; BOM과 UTF-16; `-0`; 제공 문서에 음의 0이 없음; `doc.data`에 `json.dumps`를 부르지 않음; 거부의 `str()` | `tests/simcase/test_reader.py` |
| `canonical_json()`이 모든 예제, 내장 예제, 비교 도구 fixture에서 `json.dumps`의 바이트를 줌 | `tests/simcase/test_reader.py` |
| 고정한 슬롯 표가 생성기와 같음; 물리량 슬롯은 문서나 재료 자리에 둔 등록부 물리량을 가리킴; 변환한 모든 예제와 fixture에서 `physics`, `study.tracking`, `results.mode_overlap`(종류의 슬롯) 밖의 경로가 슬롯 하나에 정확히 맞음; 어느 슬롯에도 없는 경로는 `E-KEY-UNKNOWN` | `tests/simcase/test_slots.py` |
| `validate`, `run`, `explain`, `fix`와 종료 코드; 결과 도우미; `xml.etree`와 meshio로 다시 읽은 VTU 메타데이터; 은퇴한 layout | `tests/simcase/test_cli_units.py` |
| 0.3의 버전 1 형상: 0.2로 쓴 같은 형상과 같은 pm 모델, 설계 속도, 요약, 형상 실험실 화면; 코드와 경로를 가진 거부 | `tests/simcase/test_geometry_units.py` |

아직 내장 종류가 형식 0.3을 읽지 않으므로 이 시험들은 시험 전용 종류
(`tests/simcase/units_toy_kind.py`)에서 돕니다.

## 아직 하지 않은 것

- 각 종류(열, 전기·Joule, 역학, `em.modes2d`, `em.cavity3d`)의 물리 슬롯, 예제, 결과, Studio
  부분은 종류마다의 단계에서 합니다. 등록부 이름의 결과, Studio의 원시 바이트 읽기와 물리량
  엔드포인트, 그다음 0.2 읽기와 `simcase.units`, `simcase.unit_vocabulary`의 은퇴가 뒤따릅니다.
- `I-DEFAULT-BOUNDARY`, `E-SPECTRAL`, `E-OUTSIDE-VALID`는 그것이 필요한 종류가 그 단계에서 냅니다.
- 슬롯의 JSON Schema와 생성 문서 표.
