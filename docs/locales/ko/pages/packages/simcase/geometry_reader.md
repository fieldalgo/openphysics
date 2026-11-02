# 버전 1 형상 읽기 (1단계)

[English](../../../../../packages/simcase/geometry_reader.md) | **한국어**

[문서 홈](../../index.md)

`simcase.geometry_document`는 [형상 문서 계약](geometry_document.md)이 정한 버전 1 `geometry` 블록을
읽습니다. 계약의 1단계로, 파싱·검증·양자화를 하고 형상을 기존 생성기에 넘깁니다.

## 문서 안에서

문서는 `"openphysics": "0.2"`를 그대로 두고, `geometry` 블록만 `"version": 1`을 가집니다. `Document.from_dict`와
`Document.load`는 이런 블록을 `parse`로 읽고 `to_v02`로 컴파일해 실행기에 0.2 형식을 넘깁니다. 그래서 모든 실행기가
바뀌지 않은 채 동작하고, 받을 수 없는 형상은 거부합니다. `version`이 없는 블록은 지금처럼 읽습니다.

- `doc.data`에는 컴파일된 0.2 형상이 들어 있습니다. 문서를 기록하는 결과 파일은 실제로 계산한 이 형식을 기록합니다.
- `doc.geometry_source`에는 쓴 그대로의 버전 1 블록이 들어 있고, `doc.save`·`doc.to_dict`·`doc.copy`가 이를 유지합니다.
- 1 pm 격자로 옮긴 값은 `doc.geometry_roundings`에 남고 `doc.notes`로 보고됩니다.

```python
from simcase.geometry_document import parse, to_v02, from_v02, layer_stack

model = parse({"units": {"length": "nm"}, "geometry": {
    "version": 1,
    "parameters": {"w": {"value": 500}, "t": {"value": 220}},
    "components": {"xs": {
        "dimension": "2d",
        "domain": {"xmin": -1500, "xmax": 1500, "ymin": -1200, "ymax": 1200},
        "background": {"material": "SiO2"},
        "features": [{"name": "core", "type": "rect", "x": "-w/2", "y": 0,
                      "w": "w", "h": "t", "material": "Si"}]}}}})
model.components["xs"].features[0].data   # {'x': -250000, 'y': 0, 'w': 500000, 'h': 220000} (pm)
model.roundings                          # [] : 모든 값이 이미 1 pm 격자 위
to_v02(model)                            # nm 단위의 0.2 geometry 블록
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
- **0.2 문서.** `from_v02`는 0.2 `geometry` 블록을 버전 1로 쓰고, `to_v02`는 2D 컴포넌트나 상자만 있는
  3D 컴포넌트를 다시 0.2로 컴파일합니다. 나중 도형 우선 불리언은 여전히 0.2 생성기가 shapely로 풀며,
  2단계의 정확한 2D 엔진이 이를 대체합니다. 사다리꼴은 정확한 꼭짓점의 다각형이 됩니다.
- **층 쌓기.** `layer_stack`은 `layers` 피처를 z 높이(pm)와 `meshine.extrude`가 받는 영역 × 층 표로
  바꿉니다. 셀 이름은 지정한 `region`, 없으면 재료 이름입니다.

```python
stack = layer_stack(model, "pkg")
mesh = meshine.extrude(footprint, [model.to_unit(z) for z in stack.levels],
                       stack.table_for(footprint.region_names), size=0.4)
```

## 아직 하지 않는 일

- 선택자 해석, 영역 구성 만들기, 메시에 출처 이름 쓰기(2단계 엔진이 필요합니다).
- `path`·`segment` 피처, 병합 영역, 축대칭 컴포넌트, 원통, 구, `extrude` 피처의 메시. 파싱은 하고,
  컴파일러가 이름을 밝혀 거부합니다.
- 설계 속도 제공(4단계).

`simcase.geometry_document`를 import해도 scipy와 shapely는 불러오지 않습니다. `import simcase`는
`simcase.Document` 같은 공개 이름을 처음 쓸 때 실행기 묶음을 불러옵니다.

## 검증

`tests/simcase/test_geometry_document.py`:
- 현재 simcase 문서 45개(내장 예제와 `examples/simcase/*.json`)가 0.2에서 버전 1로, 다시 0.2로 반올림
  없이 그대로 돌아오고, 각각을 버전 1 형상으로 쓴 문서가 같은 `Document.data`로 읽힙니다. 영역 열전도 예제는
  같은 온도를 냅니다.
- 1 pm 격자, half-to-even 반올림, 범위 한계, 단위 선언.
- 식의 종류, 순환, 0으로 나누기, 거부되는 토큰.
- `examples/meshine/extrude_chip.py`를 층 형태로 쓴 메시가 직접 `extrude`를 부른 메시와 노드 하나까지
  같습니다.
- 해석 열유속: 두 고정 온도 사이의 3층 직렬 스택과 공극 안의 원형 비아가 ΔT·A/Σ(tᵢ/kᵢ)와 σ·A·ΔT/L에
  상대 10⁻⁹ 이내로 맞습니다(측정값 약 2 × 10⁻¹⁴). 비아의 A는 메시된 정32각형이며 원 면적보다 0.64 % 작습니다.
