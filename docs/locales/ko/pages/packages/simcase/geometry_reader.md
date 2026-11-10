# 버전 1 형상 읽기 (1단계)

[English](../../../../../packages/simcase/geometry_reader.md) | **한국어**

[문서 홈](../../index.md)

`simcase.geometry_document`는 [형상 문서 계약](geometry_document.md)이 정한 버전 1 `geometry` 블록을
읽습니다. 계약의 1단계로, 파싱·검증·양자화를 하고 형상을 기존 생성기에 넘깁니다. [2단계 엔진](geometry_engine.md)은
이 리더가 파싱한 것으로 영역 복합체를 만듭니다.

## 문서 안에서

[형식 0.3](document_format.md) 문서(`"openphysics": "0.3"`)는 `geometry` 블록에 `"version": 1`을 두고, 구성
요소마다 `length_unit`을(`2d` 구성 요소는 `depth`도) 선언합니다. `Document.from_dict`와 `Document.load`는 이런
블록을 `parse`로 읽습니다. 문서는 블록을 쓴 그대로 둡니다(`doc.data`). 2D 영역 구성 요소는 접근자
`doc.domain`·`doc.background`·`doc.regions()`로 읽고, 균질 사각형이나 상자만 있는 3D 구성 요소는 `to_v02`로 그
종류가 읽는 평면 블록으로 컴파일됩니다(`doc.geometry_flat`). 메시는 파싱한 모델(`doc.geometry_model`)을 들고
있는 [2단계 엔진](geometry_engine.md)이 만듭니다. `version`이 없는 블록은 형식 0.3의 평면 형태 가운데
하나입니다. `parse`는 다른 형식의 문서를 `Document.from_dict`처럼 이름을 밝혀 거부합니다(`openphysics`에서
`E-FORMAT`). 형식 0.2는 읽지 않습니다.

- `doc.geometry_source`에는 쓴 그대로의 버전 1 블록이 들어 있고, `doc.save`·`doc.to_dict`·`doc.copy`가 이를 유지합니다.
- 1 pm 격자로 옮긴 값은 그 경로의 코드 붙은 진단이 되고(옮긴 양이 10⁻³ pm 미만이면 `I-PM-ROUNDING`, 이상이면
  `W-PM-ROUNDING`), `model.roundings`에도 남습니다.

```python
from simcase.geometry_document import parse, from_v02, layer_stack

model = parse({"openphysics": "0.3", "geometry": {
    "version": 1,
    "parameters": {"w": {"value": "500 nm"}, "t": {"value": "220 nm"}},
    "components": {"xs": {
        "dimension": "2d", "length_unit": "nm", "depth": None,
        "domain": {"xmin": -1500, "xmax": 1500, "ymin": -1200, "ymax": 1200},
        "background": {"material": "SiO2"},
        "features": [{"name": "core", "type": "rect", "x": "-w/2", "y": 0,
                      "w": "w", "h": "t", "material": "Si"}]}}}})
model.components["xs"].features[0].data   # {'x': -250000, 'y': 0, 'w': 500000, 'h': 220000} (pm)
model.roundings                          # [] : 모든 값이 이미 1 pm 격자 위
```

## 하는 일

- **검증.** 이름, id, 예약된 id와 키워드, 중복 이름, 재료가 다른 영역 병합, 단순 다각형, 양의 크기,
  선택자 문법. 모든 거부는 JSON 경로를 밝힌 `GeometryError`입니다.
- **식.** 파라미터 값과 형상 필드에 `+ - * /`, 괄호, 십진 리터럴, 파라미터 이름으로 된 식을 쓸 수 있습니다.
  계약의 종류 규칙에 따라 정확한 유리수 산술로 계산합니다.
- **1 pm 격자.** 모든 정의 값은 정수 pm이 됩니다. 격자 위에 있지 않은 값은 한 번 half-to-even으로
  반올림하고, 경로·원래 값·변위와 함께 `model.roundings`에 남깁니다.
- **작은 피처.** 메시 생성기의 상대 허용오차(컴포넌트 경계 상자 대각선의 3 × 10⁻⁸)보다 작은 피처는
  메시에서 사라지는 대신 이름을 밝혀 거부합니다. 이런 다중 스케일 형상의 메시는 지원하지 않습니다.
- **평면 블록.** `from_v02`는 평면 `geometry` 블록(`length_unit`·`depth` 포함)을 버전 1로 쓰고, `to_v02`는
  2D 컴포넌트나 상자만 있는 3D 컴포넌트를 다시 평면 블록으로(요소 크기 없이) 컴파일합니다. 사다리꼴은 정확한
  꼭짓점의 다각형이 됩니다.
- **층 쌓기.** `layer_stack`은 `layers` 피처를 z 높이(pm)와 `meshine.extrude`가 받는 영역 × 층 표로
  바꿉니다. 셀 이름은 지정한 `region`, 없으면 재료 이름입니다.

```python
stack = layer_stack(model, "pkg")
mesh = meshine.extrude(footprint, [model.components["pkg"].to_unit(z) for z in stack.levels],
                       stack.table_for(footprint.region_names), size=0.4)
```

## sipi와 meshine 어댑터

두 패키지는 자기 형상을 버전 1 블록으로 씁니다. 결과는 단순한 사전이며 simcase에 의존하지 않고, `parse`가
그 결과를 검사합니다. 두 어댑터는 길이 단위를 아직 형식 0.2 방식으로 `units` 블록에 선언합니다(meshine
피처는 단위 없는 `mesh_size`도 씀). 형식 0.3 문서는 그 단위를 구성 요소마다 `length_unit`으로(`depth`와 함께)
두고, 메시 크기는 단위를 붙인 `element_size`로 둡니다. `tests/simcase/test_geometry_adapters.py`가 그렇게 합니다.

```python
from sipi import geometry_v1 as sipi_v1
out = sipi_v1.to_geometry_v1(section)          # sipi CrossSection, 미터 단위
geometry = out["geometry"]
for comp in geometry["components"].values():
    comp.update(length_unit=out["units"]["length"], depth=None)
model = parse({"openphysics": "0.3", "geometry": geometry})
out["materials"], out["conductors"], out["boundaries"], out["renamed"]

from meshine import geometry_v1 as meshine_v1
out = meshine_v1.to_geometry_v1(domain, length_unit="um")   # build() 전의 Domain
out["mesh_size"], out["mesh_controls"]         # 기본 크기, Circle 꼭짓점 수
```

- **sipi:** 층을 아래부터, 그다음 국소 유전체 영역, 그다음 트레이스를 트레이스 순서로 둡니다. 그래서 나중
  피처 우선 규칙이 sipi 자체의 자르기와 같아집니다. 사각형 트레이스는 `rect`, 사다리꼴은 `trapezoid`, 두께 0은
  `segment`, `PolygonTrace`는 `polygon`입니다. 층이나 영역과 이름이 같은 트레이스는 `<name>-trace`로 바꾸고
  `renamed`에 남깁니다. 유도 좌표(트레이스 왼쪽 아래 꼭짓점, 층 경계)는 정확하게 씁니다.
- **meshine:** 영역을 포함 순서로 둡니다. 어떤 영역으로도 정확히 채워지지 않는 구멍은 빈 공간 피처가 되고,
  그 안의 영역은 여전히 뒤에 와서 이깁니다. 같은 이름의 루프는 `region`으로 합칩니다. `Domain`에는 단위와 재료가
  없으므로 `length_unit`이 필수이고, `materials`로 정하지 않으면 영역 재료는 영역 이름입니다. 경계 이름 함수는
  옮길 수 없습니다.

`examples/simcase/geometry_v1_imprint_rib.json`은 슬랩과 리브가 같은 실리콘인 리브 도파관으로, `finalize: "imprint"`가 식각선을 남기고
선택이 그 선과 리브 벽을 이름 짓습니다. `examples/simcase/geometry_v1_soi_strip.json`은 SOI 스트립 예제를 버전 1 형상과 파라미터로 쓴 것입니다.

## 아직 하지 않는 일

- 선택자 해석과 영역 구성 만들기. [2단계 엔진](geometry_engine.md)이 그 일을 하고 문서를 메시합니다.
- 원통·구·`extrude` 피처를 `Document`로 읽는 것. 그 종류들은 평면 컴파일을 읽는데 거기에는 이들의 형식이 없으므로
  `to_v02`가 이름을 밝혀 거부합니다. 2D 영역 구성 요소(`path`·병합 영역·빈 공간·`imprint`·`segment` 포함)는 쓴
  그대로 문서에 남아 `doc.domain`·`doc.background`·`doc.regions()`로 읽힙니다. 축대칭 구성 요소는 정상 영역 열에서만
  실행됩니다. 균질 사각형과 상자만 있는 3D 구성 요소는 평면 블록으로 컴파일됩니다.
- 설계 속도 제공(4단계).

`simcase.geometry_document`를 import해도 scipy와 shapely는 불러오지 않습니다. `import simcase`는
`simcase.Document` 같은 공개 이름을 처음 쓸 때 실행기 묶음을 불러옵니다.

## 검증

`tests/simcase/test_geometry_adapters.py`: sipi 단면 8가지(마이크로스트립, 스트립라인, 결합, 코플래너, 표면 마스크,
사다리꼴, 두께 0, 국소 영역이 있는 다각형 도체)가 영역마다 sipi 자체 형상의 넓이와 상대 10⁻¹² 이내로 맞고(측정
4 × 10⁻¹⁶), 반올림은 입력 잔차(최대 2 × 10⁻⁷ pm)에서만 일어납니다. meshine 리브·발자국·구멍 도메인은 루프 넓이와
맞고, 광섬유는 정확한 원을 유지합니다. 버전 1 SOI 스트립 예제는 `soi_strip.json`과 같은 `Document.data`로 읽힙니다.


`tests/simcase/test_geometry_document.py`:
- 현재 simcase 문서 51개(내장 예제와 `examples/simcase/*.json`)의 평면 형상 블록이 버전 1로 갔다가 반올림
  없이 그대로(요소 크기 제외) 돌아옵니다. 공진기 문서를 버전 1 형태로 쓰면 솔버에 같은 입력을 넘기고, 영역
  열전도 예제를 버전 1 형태로 쓰면 평면 원본과 온도 상승의 2 × 10⁻³ 이내로 맞습니다(엔진이 다른 꼭짓점
  순서로 메시함).
- 1 pm 격자, half-to-even 반올림, 범위 한계, `length_unit` 선언.
- 식의 종류, 순환, 0으로 나누기, 거부되는 토큰.
- `examples/meshine/extrude_chip.py`를 층 형태로 쓴 메시가 직접 `extrude`를 부른 메시와 노드 하나까지
  같습니다.
- 해석 열유속: 두 고정 온도 사이의 3층 직렬 스택과 공극 안의 원형 비아가 ΔT·A/Σ(tᵢ/kᵢ)와 σ·A·ΔT/L에
  상대 10⁻⁹ 이내로 맞습니다(측정값 약 2 × 10⁻¹⁴). 비아의 A는 메시된 정32각형이며 원 면적보다 0.64 % 작습니다.
