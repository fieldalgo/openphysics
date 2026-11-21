# 다중물리 문서: 한 형상 위의 여러 물리와 결합

[English](../../../../../packages/simcase/multiphysics_document.md) | **한국어**

[문서 홈](../../index.md) · [simcase 개요](overview.md) ·
[문서 형식 0.3](document_format.md) · [물리 공급자](providers.md)

*다중물리 문서*는 한 형상 위의 여러 물리 항목, 그 사이의 결합, 받아들인 반복 설정을 담습니다.
문서 하나로 모두 실행합니다. `simcase validate`는 무엇이든 실행하기 전에 항목과 결합을 모두
검사하고, `simcase run`은 결합이 정하는 순서로 물리를 풀고 물리마다 결과 폴더를 하나씩 씁니다.
구현은 [`simcase.multiphysics`](../../../../../../packages/simcase/src/simcase/multiphysics.py)에 있습니다.

이 릴리스의 첫 결합은 정상 상태 온도를 광 모드로 넘깁니다.
`thermal.steady2d` → n(T) → `em.modes2d`.

```json
{
  "openphysics": "0.3/multiphysics.1",
  "name": "Heated slab waveguide",
  "geometry": {"version": 1, "components": {"xs": {"dimension": "2d", "length_unit": "um", "depth": null,
    "domain": {"xmin": -0.5, "xmax": 0.5, "ymin": -1.2, "ymax": 1.2},
    "background": {"material": "clad"},
    "features": [{"name": "core", "type": "rect", "x": -0.5, "y": 0.0, "w": 1.0, "h": 0.22, "material": "core"}]}}},
  "materials": {
    "core": {"refractive_index": 3.48, "thermal_conductivity": "148 W/(m K)",
             "thermo_optic_coefficient": "1.8e-4 1/K", "reference_temperature": "300 K"},
    "clad": {"refractive_index": 1.444, "thermal_conductivity": "1.38 W/(m K)",
             "thermo_optic_coefficient": "1.0e-5 1/K", "reference_temperature": "300 K"}},
  "physics": {
    "heat1": {"type": "thermal.steady2d", "prescribed_temperature": {"bottom": "300 K", "top": "330 K"}},
    "modes1": {"type": "em.modes2d", "formulation": "scalar", "vacuum_wavelength": "1.55 um", "mode_count": 1,
               "boundary": {"left": "pmc", "right": "pmc", "top": "pec", "bottom": "pec"}}},
  "couplings": {
    "heat_to_optics": {"from": "heat1.temperature", "to": "modes1.temperature", "transfer": "same_mesh"}},
  "mesh": {"element_size": "0.02 um"}
}
```

함께 배포하는 예제는 [`multiphysics_heated_slab.json`](../../../../../../examples/simcase/multiphysics_heated_slab.json)입니다.

```sh
python -m simcase validate examples/simcase/multiphysics_heated_slab.json
python -m simcase run examples/simcase/multiphysics_heated_slab.json -o heated_slab_results
```

## envelope

`couplings`가 있거나 물리 항목이 둘 이상의 종류에 속하는 문서는 다중물리 envelope
`"openphysics": "0.3/multiphysics.1"`을 밝힙니다. 이 envelope는 형식 0.3 위에 놓입니다. 모든 값은
[형식 0.3 규칙](document_format.md)을 따릅니다(차원이 있는 값마다 단위, 등록부 키 이름, `units`
블록 없음). 이 envelope를 모르는 읽기는 형식 검사에서 문서를 거부하므로(`openphysics`에서
`E-FORMAT`) 결합이 소리 없이 버려지지 않습니다.

- `couplings`가 있거나 두 종류의 항목이 있는 `"0.3"` 문서는 `openphysics`에서 `E-FORMAT`이며 써야
  할 envelope를 밝힙니다.
- 한 종류의 항목만 있고 결합이 없는 envelope 문서도 `E-FORMAT`입니다. 이런 문서는 단일 물리 형식
  `"0.3"`으로 씁니다. 문서마다 쓰는 방법은 하나입니다.
- 단일 물리 문서는 바뀌지 않습니다. 계속 `"0.3"`이고 읽기, 슬롯 표, 검증, 결과가 모두 같습니다.

envelope는 바탕 형식과 자기 버전을 밝힙니다. 다중물리 envelope를 나중에 바꾸면 `"0.3/multiphysics.2"`,
바탕 형식이 바뀐 뒤의 envelope는 `"0.4/multiphysics.1"`이 됩니다.

최상위 키: `openphysics name display_units geometry materials physics mesh study results
couplings`. 형상은 버전 1 블록입니다([형상 문서](geometry_document.md)). 물리들은 그 영역과 메시
하나를 함께 씁니다. `results`는 `save_fields`(기본값 true)와 `plots`(기본값 false)를 받고,
`study.type`은 `"single"`(기본값)이나 `"sweep"`입니다.

## 물리 항목마다 그 종류가 검증합니다

`physics.<이름>` 항목은 그 유형을 맡은 종류가 단일 물리 문서를 읽을 때와 똑같이 읽습니다. 읽기는
항목마다 *뷰*를 만듭니다. 뷰는 공유하는 `geometry`, `mesh`, `results`와 그 항목 하나, `study`(sweep은
그 값을 바꾸는 물리의 뷰에만), 그 종류가 읽는 것만 남긴 재료 기록으로 이루어진 `"0.3"` 문서입니다.
다른 물리가 읽는 물성은 뷰에서 뺍니다(그 물리가 검사합니다). 어떤 물리도 읽지 않는 물성은
남겨서 값을 검사하고 쓰이지 않는다고 알립니다(`I-UNUSED-PROPERTY`). 진단은 문서 경로를 그대로
쓰고, 두 뷰가 공유 블록에 대해 같은 진단을 내면 한 번만 알립니다.

물리 이름은 식별자(문자, 숫자, `_`)입니다. 이 릴리스의 다중물리 문서는 결합 훅이 있는 종류
`thermal.steady2d`와 `em.modes2d`를 받습니다. 다른 유형은 `physics.<이름>.type`에서
`E-CONTRACT`("is not coupled in this release")입니다. 복합 종류(`joule.temperature2d`,
`mechanics.thermoelastic2d`)는 자체 반복을 가진 단일 물리 문서로 남습니다.

## 결합

```json
"couplings": {"heat_to_optics": {"from": "heat1.temperature", "to": "modes1.temperature", "transfer": "same_mesh"}}
```

- `from`은 `<물리 이름>.<출력 포트>`, `to`는 `<물리 이름>.<입력 포트>`이며 포트는 종류의
  [manifest](providers.md#내장-종류와-포트)에 있는 것입니다. 결합 하나는 물리량 하나를 한 방향으로
  나릅니다. 양방향 교환은 결합 둘입니다.
- 두 포트의 `quantity`와 `unit` 문자열이 같아야 합니다. 결합은 단위를 바꾸지 않습니다(다르면
  `E-COUPLING-PAIR`).
- 절점 출력은 절점 입력이나 요소 입력으로, 요소 출력은 요소 입력으로 갑니다. 절점 필드가 요소
  입력으로 가면 받는 종류가 삼각형마다 세 절점 값의 평균(P1 평균)을 씁니다.
- `transfer`는 `"same_mesh"`입니다. 한 메시 위의 항등 전달(`galerkin.coupling.transfer`)이며, 절점과
  삼각형의 `MeshSignature`가 정확히 같고 삼각형마다 영역도 같아야 합니다. 서로 다른 메시 사이의
  투영은 나중에 따로 승인할 전달입니다.
- `combine: "single"` 입력은 결합을 많아야 하나 받고, `"sum"`은 들어오는 결합의 필드를 모두 더합니다.
- 물리는 자기 자신과 결합하지 않습니다.

### 실행 전 검증

`simcase validate`는 실행 전에 다음을 모두 알리고, 결합이나 물리의 이름과 바꿀 것을 밝힙니다.

| 문제 | 코드와 경로 |
|---|---|
| 문서에 없는 물리 이름이나 포트 이름 | `couplings.<이름>.from` / `.to`에서 `E-CONTRACT`, 있는 물리나 포트를 나열 |
| `from`에 입력, `to`에 출력 | `couplings.<이름>.from` / `.to`에서 `E-CONTRACT` |
| 종류가 저장하지만 이 릴리스에서 결합하지 않는 출력(`thermal.steady2d`는 `heat_flux`가 아니라 `temperature`를 결합) | `couplings.<이름>.from`에서 `E-CONTRACT` |
| 물리량, 단위, 위치가 맞지 않음 | `couplings.<이름>`에서 `E-COUPLING-PAIR` |
| `single` 입력으로 들어오는 두 번째 결합 | `couplings.<이름>.to`에서 `E-CONTRACT`, 이미 있는 결합을 밝힘 |
| 자기 결합 | `couplings.<이름>`에서 `E-CONTRACT` |
| `same_mesh`가 아닌 전달 | `couplings.<이름>.transfer`에서 `E-CONTRACT` |
| 두 물리가 서로 다른 메시를 만들 `same_mesh` 결합 | `couplings.<이름>.transfer`에서 `E-CONTRACT`, 한 물리가 읽지 않는 `mesh` 키를 밝힘 |
| 받아들인 반복이 없는 순환 | `study.loops`에서 `E-COUPLING-CYCLE`, 제안하는 반복 항목과 함께 |
| `temperature` 입력이 결합됐는데 열광학 모델이 없는 광학 재료 | `materials.<이름>`(라이브러리 재료는 `physics.<이름>`)에서 `E-PROPERTY-MISSING` |

두 메시는 만들어진 뒤 한 번 더 비교합니다. `simcase run`은 메시가 다른 결합을
거부하고(`couplings.<이름>: same_mesh needs one mesh, …`) 보간하지 않습니다. 지금
`thermal.steady2d`와 `em.modes2d`는 같은 형상과 `mesh` 블록에서 똑같은 메시를 만듭니다. 단
`mesh.grading`(`em.modes2d`의 방사형 등급)은 열 종류가 읽지 않습니다. 그래서 둘 사이의 `same_mesh`
결합은 `mesh.grading`을 거부하고, 둘 다 읽는 `mesh.controls`로 메시를 조절합니다.

## 열 → n(T) → 광 모드

`em.modes2d` 입력 `temperature`(K, 요소, `single`)는 `thermal.steady2d` 항목의 절점 온도(출력
`temperature`, K, 절점)를 받습니다. 모드 종류는 삼각형마다 세 절점 온도의 P1 평균 T를 구하고

n = n₀(λ) + (dn/dT) (T − T_ref)

를 씁니다. n₀(λ)는 재료의 굴절률(상수, n + i k, Sellmeier 모델)입니다. 실수부만 바뀌고 소광 계수
k는 그대로입니다. 굴절률 변화가 정확히 0인 삼각형은 재료의 유전율을 비트 단위로 그대로 씁니다.

결합된 항목의 광학 재료에는 모두 열광학 모델이 있어야 합니다.

- 로컬 기록은 `thermo_optic_coefficient`(dn/dT, 예: `"1.8e-4 1/K"`)와
  `reference_temperature`(T_ref, 예: `"300 K"`)를 함께 씁니다. 하나만 쓰면 `E-KEY-MISSING`입니다.
- `physmat:Si`와 `physmat:SiO2`에는 모델이 있습니다. dn/dT는 physmat의 `thermo_optic_dn_dT`(1.8e-4,
  1.0e-5 1/K)이고 T_ref는 300 K입니다. 다른 라이브러리 재료에는 없습니다.

두 키는 다중물리 문서에서만 재료 키입니다. 단일 물리 문서에서는 계속 알 수 없는 키
(`E-KEY-UNKNOWN`)입니다. 결합된 온도 입력이 없으면 검사하고 쓰이지 않는다고 알립니다.

이 결합의 한계:

- 열 → 모드 문서는 `physmat:Si`와 `physmat:SiO2`를 쓸 수 있습니다. 정상 열전도는 그 300 K 핸드북
  상숫값 `thermal_conductivity`(148, 1.38 W/(m K); [열 영역](thermal_regions2d.md))를, 모드 종류는 그
  열광학 모델을 읽습니다. 전도도는 온도를 따라 바뀌지 않으므로 온도 상승이 크면 로컬 기록을 쓰십시오.
- physmat의 Sellmeier 자료는 293.15 K(SiO2)와 299.15 K(Si) 기준입니다. 열광학 변화는 300 K에서 재고,
  n₀는 실행 파장의 Sellmeier 값입니다.
- 열광학 모델은 T에 선형입니다. 열팽창이나 응력 광학 효과는 없습니다.

## 풀이 순서와 반복

풀이 순서는 저장하지 않고 유도합니다. 실행기는 결합 그래프로 물리의 순서를 정합니다. 강하게 연결된
묶음을 찾고 위상 순서로 늘어놓습니다. 준비된 묶음 가운데 첫 물리가 `physics` 블록에서 앞선 묶음이
먼저이고, 묶음 안의 물리도 그 순서를 지킵니다. 물리가 둘 이상인 묶음이 순환입니다.

순환은 받아들인 반복이 있어야만 실행합니다. 그 묶음과 정확히 같은 `study.loops` 항목입니다.

```json
"study": {"type": "single", "loops": [
  {"physics": ["a", "b"], "method": "fixed_point",
   "tolerance": {"port": "a.y", "norm": "max_abs", "value": "1e-6 K"},
   "max_iterations": 30, "relaxation": 0.5}]}
```

반복이 없는 순환은 `study.loops`에서 `E-COUPLING-CYCLE`입니다. 메시지는 묶음과 그 결합을 밝히고 위
항목을 제안으로 줍니다(기본값: `fixed_point`, 순환 안에서 첫 물리의 첫 출력에 `max_abs`와 그 포트
단위의 `1e-6`, 30회, relaxation 0.5). 반복 항목은 다음을 검사합니다. 물리가 정확히 순환 하나이고,
순환마다 항목 하나, `method`는 `"fixed_point"`, tolerance 포트는 그 반복의 출력이며 값은 그 포트
단위의 양수, `norm`은 `"max_abs"`, `max_iterations`는 2 이상의 정수, `relaxation`은 (0, 1]입니다.
tolerance 포트는 반복 안 결합의 출발점이고, 그 값은 변화량입니다. 온도 tolerance는 온도 차이입니다
(`"1e-6 K"`나 mK. `degC`는 모호하므로 거부합니다).

받아들인 반복은 순환 안 결합의 필드에 대한 완화 고정점 반복 x ← (1 − w) x + w G(x)로 실행합니다.
반복마다 구성 물리를 그 순서대로 풀고, 반복 안 결합의 필드는 w로 완화해 다음 풀이에 넣습니다(첫
반복은 보낸 그대로). 반복의 잔차는 tolerance 포트가 보내는 필드의 고정점 잔차 |G(x) − x|입니다. 그
포트가 지금 보내는 값과 이번 반복에 넣은 완화 필드의 가장 큰 차이(`max_abs`, 그 포트 단위)입니다. 완화가
작아도 줄지 않으므로 작은 w로 반복이 일찍 끝나지 않습니다. 첫 잔차는 두 번째 반복에서 잽니다. 잔차가
tolerance 이하이면 수렴이고, 결과에 잔차를 모두 적습니다. `max_iterations`에
닿은 반복은 `study.loops`에서 잔차 이력과 함께 `E-LOOP-DIVERGED`로 실패합니다. 마지막 반복값을
결과로 돌려주지 않으며 아무것도 쓰지 않습니다.

내장 종류의 쌍 가운데 아직 순환을 이루는 것은 없습니다. 반복은 시험 전용 종류로만 시험합니다.

## 결과: `multiphysics-run-v1`

```
<out>/
  summary.json    result "multiphysics-run-v1", format, name, diagnostics, defaults_applied,
                  solve_order, physics, couplings, loops, timing
  model.json      읽은 그대로의 문서
  log.txt
  heat1/          열 결과, 그 자체 식별자와 함께(summary.json, fields.npz, log.txt;
                  results.plots가 true이고 그 종류가 그림을 그리면 results.png)
  modes1/         모드 결과, 그 자체 식별자와 함께
```

- `solve_order`는 실제로 쓴 순서이며 묶음의 목록입니다(`[["heat1"], ["modes1"]]`).
- `physics.<이름>`은 유형, 그 물리 자체 결과의 식별자, 폴더를 줍니다. 폴더마다 그 종류의 평소 결과
  파일이 있고 결합된 입력으로 계산한 것입니다. 단일 물리 결과는 식별자를 그대로 씁니다. 물리마다의
  `model.json`은 없습니다. 물리를 풀 때 쓴 뷰는 사용자가 쓴 문서가 아니고, 결합 입력 없이는 그 결과를
  내지 않기 때문입니다.
- `couplings.<이름>`은 `from`, `to`, `quantity`, `unit`, `transfer`, 필드 `location`,
  `mesh_signature`(`"match"`), `max_abs_difference`(전달이 만든 가장 큰 변화, `same_mesh`에서는
  `{"value": 0.0, "unit": "K"}`, 0이 아니면 실행 실패)를 적습니다. `conservation_residual`은 일률
  물리량(W, W/m, W/m², W/m³; 요소 필드는 값 × 넓이, 절점 필드는 집중 P1 적분)에서
  |Σ 보냄 − Σ 받음| / |Σ 보냄|이고, 온도를 비롯한 다른 물리량에서는 null입니다.
- `loops`는 실행한 반복마다 `physics`, `method`, `tolerance`, `relaxation`, `iterations`,
  `converged`, `residuals`(첫 반복 다음부터 반복마다 `{"value", "unit"}` 하나)를 적습니다. 순환이
  없는 문서에서는 비어 있습니다.
- 모드 폴더의 `fields.npz`에는 결합 입력이 더해집니다. `temperature`(K, 삼각형마다 값 하나, 쓴 P1
  평균)와 `refractive_index`(연구 지점마다 행 하나, 삼각형마다 값 하나, 손실이 있으면 exp(−iωt)의
  n + i k)입니다.

## Python

```python
from simcase import Document, multiphysics, run

doc = Document.load("examples/simcase/multiphysics_heated_slab.json")
doc.views["modes1"]                       # 항목 하나의 단일 물리 뷰
result = run(doc, verbose=False)          # multiphysics.MultiphysicsRunResult
result.solve_order                        # [['heat1'], ['modes1']]
result.results["modes1"].effective_index  # 결합된 온도로 계산한 모드 결과
result.couplings["heat_to_optics"]        # 결합 기록
result.save("heated_slab_results")
```

`multiphysics.run(doc, on_event=callback)`은 진행 표시를 위해 단계마다 JSON 데이터 dict 하나로
`callback`을 순서대로 부릅니다. 물리마다 `physics_started`와 `physics_finished`(`seconds` 포함),
받아들인 반복에서는 `loop_started`, 잰 잔차마다 `loop_iteration`(`iteration`, `residual`, `unit`),
`loop_finished`(`iterations`)입니다.

## 결합 훅은 내부용입니다

종류는 결합 훅(`PhysicsKind.coupling`, `multiphysics.CouplingHook`)으로 다중물리 문서에 참여합니다.
이 릴리스에서 훅은 simcase 내부용이며 [공급자 프로토콜](providers.md)의 일부가 아닙니다. 그래서 다른
공급자의 종류는 아직 결합에 참여할 수 없습니다. 그 manifest에는 입력 포트를 이미 밝힐 수 있습니다.

## 검증

구현 전에 미리 등록했습니다. 예제의 형상에서 검사합니다(n₀ 3.48, dn/dT 1.8e-4 1/K인 0.22 µm 코어가
n₀ 1.444, dn/dT 1.0e-5 1/K인 클래딩으로 된 2.4 µm 창의 폭 1.0 µm 전체를 가로지름, T_ref 300 K,
λ 1.55 µm, 스칼라 정식화, 왼쪽·오른쪽 PMC, 위·아래 PEC). 옆면이 PMC이면 모드가 x에 의존하지 않으므로
2D 문제는 PEC 벽 사이의 1D TE 슬랩입니다. 시험은
[`tests/simcase/test_multiphysics_heat_optics.py`](../../../../../../tests/simcase/test_multiphysics_heat_optics.py)와
[`tests/simcase/test_multiphysics_document.py`](../../../../../../tests/simcase/test_multiphysics_document.py)입니다.

| 검사 | 독립 기준 | 기준값 |
|---|---|---|
| V1 균일 ΔT = 10 K(위·아래 310 K, 옆면 단열) | PEC로 둘러싼 슬랩의 정확한 분산 관계 kd = atan(γ coth(γ t_s)/κ) + atan(γ coth(γ t_c)/κ): n_eff 2.851738985 → 2.853529512, 변화 1.79053e-3 | h = 0.04 µm: n_eff 3e-3, 변화 5e-3 상대; h = 0.02 µm: 1e-3과 2e-3 |
| V1 일관성(스칼라와 벡터) | 독립 아님: 올린 굴절률을 직접 쓴 실행 | \|Δn_eff\| ≤ 1e-12 |
| V2a 300 K / 400 K, 옆면 단열 | 직렬 층 열전도의 닫힌 해(y에 대해 조각별 선형) | 모든 절점에서 1e-8 K 이내(h = 0.02 µm) |
| V2b 결합 n_eff, h = 0.04, 0.02, 0.01 µm | 정확한 n(y)를 쓴 TE 방정식의 1D P1 FEM, 요소 48 000개: 2.86159710 | 관측 차수 [1.8, 2.2]; 가장 고운 메시의 오차가 Richardson 추정의 0.5–2배; 외삽값 상대 1e-5 이내; 가장 고운 메시 2.5e-4 이내 |
| V3a V2a의 열에서 dn/dT = 0(스칼라와 벡터) | 결합하지 않은 단일 물리 문서 | 비트 단위로 같음: n_eff, 필드, 메시 배열, 후처리, summary 값 |
| V3b 모든 면 300 K, 열원 없음 | 결합하지 않은 단일 물리 문서 | V3a처럼 비트 단위로 같음 |
| V4 단일 물리는 그대로 | 배포한 모든 예제의 변경 전후 | validate 출력, fields.npz 배열, 시간을 뺀 summary와 metadata, model.json, results.png가 같음 |

## 이 릴리스에 없는 것

- 다중물리 sweep의 실행. `study.type: "sweep"`과 그 매개변수 경로(물리 항목 하나의 값,
  `physics.<이름>.…`)는 검증하고, `simcase run`은 sweep을 `study.type`에서 `E-CONTRACT`("a multiphysics
  sweep is validated but not run in this release")로 거부합니다.
- `same_mesh`가 아닌 전달.
- Studio: 아직 다중물리 문서를 편집하거나 보여 주지 않습니다.
- 결합에 참여하는 다른 공급자의 종류(훅은 내부용입니다).
