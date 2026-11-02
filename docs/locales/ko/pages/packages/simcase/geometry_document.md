# 형상 문서: 0단계 계약(초안)

[English](../../../../../packages/simcase/geometry_document.md) | **한국어**

[문서 홈](../../index.md)

상태: **초안 계약입니다. 구현되지 않았고 아직 승인되지 않았습니다.** 이 형식을 읽는 코드는 없으며,
이 문서는 현재의 어떤 문서·메시 생성기·솔버 동작도 바꾸지 않습니다. 저장소 사실은 `main` `015a6d8`에서
확인했습니다.

이 문서의 구성은 다음과 같습니다.
- **동결** 표시 절은 승인 시 고정됩니다. SHA-256을 기록하며, 그 뒤에는 날짜가 있는 보완으로만
  바뀝니다.
- **예약** 표시 키워드는 뒤 단계에서 정의합니다. 그때까지 모든 리더가 이름을 밝혀 거부합니다.
- JSON 문서 계약을 바꾸는 일(봉투 버전 문자열, `"openphysics": "0.2"` 문서 이전)은 따로 결정합니다.
  그 결정 전까지 0.2 문서는 그대로 동작합니다(`packages/simcase/src/simcase/schema.py:51,100-101`).

## 목적과 범위

OpenPhysics의 모든 물리는 하나의 형상 문서를 참조해야 합니다. 지금은 형상을 여러 방식으로 따로 씁니다.
- simcase 도형(`packages/simcase/src/simcase/geometry.py:107-142`)
- 손으로 만드는 meshine `Domain`(`packages/meshine/src/meshine/geometry.py:118-208`)
- `meshine.extrude`(`packages/meshine/src/meshine/extrude.py:33-60`)
- gmshio `.geo` 텍스트(`packages/gmshio/src/gmshio/geo.py:42-126`)
- sipi 단면, 도체 단면 메시, 전원면
  (`packages/sipi/src/sipi/crosssection.py:175-206`,
  `packages/sipi/src/sipi/conductor_mesh.py:59-164`,
  `packages/sipi/src/sipi/plane.py:181-218`)
- 공동 상자(`packages/simcase/src/simcase/cavity.py:104-145`)
- galerkin 구조 격자 생성기(`packages/galerkin/src/galerkin/mesh.py:81-260`,
  `packages/galerkin/src/galerkin/mesh3d.py:124-161`)
- Studio 작업공간 파일(`packages/simcase/src/simcase/studio/static/workspace-project.mjs:21-70`)

이 문서는 이 모두가 옮겨질 하나의 형상 블록을 정의합니다.

**승인 시 동결하는 것:**
- 최상위 구조
- 단위와 고정 1 pm 내부 격자
- 길이·비율 파라미터
- 2D·2.5D·상자 피처
- "나중 피처가 이김" 규칙과 선택적 `imprint` 마무리
- 영역 구성과 출처 이름
- 메시 태그와 선택자
- 물리·재료·메시 제어·스터디가 형상을 참조하는 방식
- 현재 표현 대응표

**정의하지만 뒤 단계 전에는 소비자가 없는 것:** FEM의 `path`·`segment`(2단계),
`cylinder`·`sphere`(5단계).

**예약:**
- 구성 요소·피처 키워드: `periodic`, `ellipse`, `rotation`, `"z"`가 아닌 `axis`, `offset`,
  `surface`, 층 `below`/`above`
- 파라미터 종류 `angle`·`count`
- 선택자 키 `inside`·`kind`·`all`·`except`·`covered_by`
- 3D `imprint`
- 메시 필드 `node_feature`·`node_param`
- 영역 구성을 저장하는 형식

**여기서 정하지 않는 것:**
- JSON 계약 변경 자체
- 2단계 정확 2D 엔진이나 그 밖의 코드
- 메시 변형과 adjoint(galerkin 소관)
- 상자 규칙을 넘는 3D 배열
- 메시 생성기·galerkin의 주기 경계
- Wavebit 어댑터([3단계 미리보기](#3단계-미리보기-wavebit-동결-아님) 참고)
- ECAD·STEP 가져오기, 곡면 B-rep·NURBS
- Studio 편집기

## 평가기의 위치

평가기는 형상 블록을 읽고, 불리언을 풀고, 영역 구성을 만듭니다. 평가기는 simcase 안에 두며,
정확한 정수·유리수 산술을 쓰는 순수 Python입니다. meshloom 밖에는 컴파일 코드를 더하지 않습니다.

평가기는 shapely 없이 동작해야 합니다. shapely 휠에는 GEOS(LGPL-2.1)가 들어 있어서 sipi 브라우저
계산기가 이를 브라우저로 보내게 되고, 2단계 정확 2D 엔진이 어차피 shapely를 대체합니다. 평가기 모듈
자체는 표준 라이브러리와 NumPy만 import합니다.

scipy는 제한하지 않습니다. sipi·galerkin·meshine이 이미 의존하고(`packages/sipi/pyproject.toml:26`),
BSD-3-Clause입니다. `import simcase`가 솔버 묶음을 불러오는 것(`packages/simcase/src/simcase/__init__.py:26-40`)을
지연 import로 바꾸는 일은 선택적인 정리이며 이 계약의 요구가 아닙니다.

## 최상위 구조(동결)

```json
"units": {"length": "m"},
"geometry": {
  "version": 1,
  "parameters": {"<param>": {"value": <number|expression>, "kind": "length" | "ratio", "range": [lo, hi]}},
  "components": {
    "<component>": {
      "dimension": "2d" | "axisymmetric" | "3d",
      "domain": {...},
      "background": {"material": <name|null>, "mesh_size": <length>},
      "features": [{"id": "...", "name": "...", "type": "...", ...}, ...],
      "finalize": "later_wins" | "imprint",
      "selections": {"<selection>": <selector>},
      "boundary_tags": [{"tag": "<mesh tag>", "select": <selector>}, ...]
    }
  }
}
```

봉투의 다른 키(`units`, `materials`, `physics`, `mesh`, `study`)는 의미가 그대로입니다
(`packages/simcase/src/simcase/schema.py:51-69`). `version`이 없는 `geometry` 블록은 0.2 형식이며,
어댑터가 읽습니다([대응표](#현재-표현-대응표동결) 참고).

### 버전

`version`은 정수입니다. 형상 블록에 속하며 봉투의 `openphysics` 문자열을 대신하지 않습니다.
봉투를 `"0.3"`으로 올릴지는 JSON 계약 결정에 맡깁니다.

### 단위

형상 숫자는 문서의 `units.length` 단위입니다.

**선언 필수.** 버전 1 형상 블록이 있는 문서는 `units.length`를 선언해야 하며, 선언하지 않은
길이는 거부합니다. `units.resolve`는 없는 차원을 SI로 다루지만
(`packages/simcase/src/simcase/units.py:103-104`), 형상을 읽는 모든 종류가 이미 선언하지 않은
길이를 거부합니다.
- `em.modes2d`: `packages/simcase/src/simcase/schema.py:55,333-341`
- `thermal.steady2d`: `packages/simcase/src/simcase/thermal.py:63-65`
- 영역 열: `packages/simcase/src/simcase/thermal_regions.py:229-231`
- `em.cavity3d`: `packages/simcase/src/simcase/cavity.py:169-170`

**새 문서의 기본값.** Studio와 API가 새로 쓰는 문서는 `"m"`를 선언합니다.

**바뀌지 않는 규칙:**
- 단위 기호와 `{"in_m": x}` 탈출구(`packages/simcase/src/simcase/units.py:35-37,124-146`)
- 태그 `[value, "unit"]` 쌍 거부(`packages/simcase/src/simcase/schema.py:110-118`)

**각도 없음.** 버전 1에는 각도 양이 없습니다.

### 내부 격자: 1 pm(동결)

정확 형상 계산은 **1 pm**(10⁻¹² m) 정수 위에서 합니다. 문서 단위는 따로 고릅니다. 격자는 고정이며
문서가 바꿀 수 없습니다.

1. **읽기.** JSON 숫자는 파싱한 double을 왕복 재현하는 가장 짧은 십진수로 읽습니다. 지금의 단위 변환도
   이렇게 읽습니다(`packages/simcase/src/simcase/units.py:322-325`). 따라서 유효숫자가 17자리를
   넘는 리터럴은 그 double 값으로 읽힙니다.
2. **계산.** 식은 정확한 유리수 산술로 계산합니다.
3. **배율.** 결과에 문서 길이 단위와 1 pm의 정확한 비를 곱합니다. 십진 단위(nm, um, mm, m 등
   `packages/simcase/src/simcase/units.py:35-37`)에서는 문서 단위의 정수 값이 정수 pm가 됩니다.
4. **한 번만 반올림.** 정수가 아닌 결과는 읽을 때 한 번만 가장 가까운 pm로 반올림합니다(동률이면
   짝수 쪽). 반올림마다 JSON 경로, 쓴 값, 이동량을 보고합니다. 그 뒤에는 다시 반올림하지 않습니다.

**정의 값**은 식을 계산한 뒤의 피처 자체 필드입니다. 예:
- rect `x, y, w, h`, circle `cx, cy, r`, polygon `points`
- trapezoid `cx, y, w, w_top, h`
- 상자 경계, 층 `z0`와 두께, 도메인 경계

**유도점은 양자화하지 않습니다.** 유도점은 정의 값에서 계산한 점입니다.
- rect의 먼 꼭짓점 `x + w`
- trapezoid의 꼭짓점 `cx ± w/2`
- 직선·곡선 교점
- 층 경계가 기울어진 사다리꼴 변을 나누는 점

이 점들은 정확한 유리수(곡선 교점은 2단계에서 정확한 구성)로 두며, 나온 곡선의 출처를 기록합니다.
양자화하면 곧은 면이 꺾입니다(`packages/sipi/src/sipi/crosssection.py:294-326`).

**범위.** 좌표는 |k| < 2⁶³ pm(약 9.2 × 10⁶ m)이어야 합니다. 넘는 구성 요소는 범위를 밝혀 거부합니다.

**격자가 주는 것.** 문서가 어떤 단위를 선언하든 맞닿음은 맞닿음으로 남습니다. 지금은 미터로 쓴 8 × 8
맞닿은 사각형 격자는 교차 4개, 그 마이크로미터 사본은 0개로 셉니다
(`packages/simcase/src/simcase/complexity.py:74-80`).

**격자가 해결하지 않는 것.** 넘긴 뒤에는 메시 생성기의 상대 허용오차가 그대로 적용됩니다. 경계 상자
대각선의 `MERGE_EPS = 1e-9`와 `SNAP_EPS = 3e-8`입니다
(`packages/meshine/src/meshine/geometry.py:33,57`). 10 cm 도메인 안의 1 nm 피처(비 10⁻⁸)는
`SNAP_EPS`보다 작습니다. 그래서 검증 단계는 넘기기 전에, 컴포넌트 경계 상자 대각선에 대한 크기 비가 받는
메시 생성기의 허용오차보다 작은 피처를 거부하고 피처 이름·크기·비를 밝힙니다. 조용히 사라지는 피처는
없습니다. 이런 다중 스케일 형상을 제대로 메시하는 일은 장기 과제이며 0–6단계 일정에 넣지 않습니다.

**meshine에 넘기기.** meshine은 마이크로미터 double을 받습니다. k pm 좌표는 k/10⁶ µm로 바꾸며 한 번만
반올림합니다. 꼭짓점은 이 한 번의 반올림 전에 정확히 계산하므로, 메시가 지금의 0.2 메시와 반올림
수준에서 다를 수 있습니다.

예: `examples/simcase/pml_leaky_slab.json`(µm)의 substrate는 `y = 0.47`, `h = 2.0`입니다. 지금 윗변은
부동소수점 합 0.47 + 2.0 = 2.4699999999999998입니다
(`packages/simcase/src/simcase/geometry.py:43-44`; `packages/simcase/src/simcase/runner.py:130-135`).
이 계약에서는 2.47입니다.

지금 메시와 비트 단위로 같은지는 수용 기준이 아닙니다. 해석해, 독립 기준, 저장값 검사는 지금 기준
그대로 통과해야 합니다.

**meshloom에 넘기기(meshloom 3D 작업에 대한 제안이며 여기서 정하지 않음).** meshloom은 정수 pm 개수를
double로(|k| ≤ 2⁵³, 약 9 km까지 정확) 받고 배율을 따로 받습니다. 어떤 형태를 고르든
`docs/packages/meshine/validation3d.md:44`의 출력 보장은 galerkin이 최종으로 받는 좌표에서 성립해야
합니다. 여기에는 출력 double에서 정확한 `orient3d > 0`이 포함됩니다.

### 파라미터(동결)

`parameters`는 이름을 `{"value": <숫자 | 식>, "kind": ..., "range": [lo, hi]}`에 대응시킵니다.

- **이름**은 `^[A-Za-z_][A-Za-z0-9_]*$`를 따릅니다.
- **종류.** `kind`는 `length`(기본, 문서 길이 단위) 또는 `ratio`(무차원)입니다. `angle`·`count`
  종류는 예약입니다.
- **식**에는 십진 리터럴, 파라미터 이름, `+ - * /`, 단항 음수, 괄호만 씁니다. 그 밖에는 허용하지
  않습니다(`min`·`max`·`sqrt`·삼각함수 없음). 식은 정확한 유리수 산술로 계산합니다.
- **종류 규칙:**
  - `+`·`-`는 같은 종류끼리만
  - 길이 × 비율은 길이
  - 길이 ÷ 길이는 비율
  - 길이 × 길이는 거부
- **오류.** 순환이나 0으로 나누기는 파라미터 이름을 밝힌 오류입니다.
- **범위.** 선택 필드 `range`는 파라미터의 범위를 정합니다. 스윕, 미분, 정적 경계 상자가 필요한
  소비자가 씁니다.

숫자 형상 필드는 모두 식이 될 수 있습니다. 도메인 경계, 피처 필드, 층 두께, `mesh_size`,
`mesh.controls`가 포함됩니다. 물리 필드는 형상이 아니며, 이 문서는 물리 필드에 식을 주지 않습니다.

### 구성 요소(동결)

구성 요소는 차원이 하나인 형상 모델입니다.

- **`2d`**: x–y 좌표. `domain`은 `{xmin, xmax, ymin, ymax}`이며 지금처럼 자르기 상자입니다
  (`packages/simcase/src/simcase/geometry.py:110-111`).
- **`axisymmetric`**: 같은 2D 피처를 (r, z)로 읽습니다.
  - `xmin ≥ 0`이어야 하며, r < 0으로 넘어가는 피처는 거부합니다.
  - r = 0의 도메인 변은 `xmin == 0`일 때만 `axis`라 부르고, 아니면 `left`입니다.
  - `main` `015a6d8`에는 축대칭 러너가 없습니다. 브랜치 `codex/axisymmetric-thermal-lens` `2c58b05`는
    확인하지 않았습니다. 그 브랜치가 들어오면 태그 이름을 이 규칙에 맞춥니다.
- **`3d`**: `domain`은 공동처럼 `{xmin, xmax, ymin, ymax, zmin, zmax}`입니다
  (`packages/simcase/src/simcase/cavity.py:104-145`).

**`background`**는 도메인의 나머지를 채우는 영역입니다. 이름은 `background`이고 예약 이름으로
남습니다(`packages/simcase/src/simcase/geometry.py:133-136`;
`packages/simcase/src/simcase/schema.py:283-284`). `material`은 세 가지 형태입니다.
- 재료 이름
- `null`: 나머지가 빈 공간입니다. 메시하지 않으며 그 경계는 외부 경계입니다.
- **`material` 키 없음**: 물리가 물성을 주는 균질체입니다. 피처가 없는 구성 요소에서, 균질 물성을
  받는 물리 종류에서만 씁니다. 지금의 사각형 문서가 그렇고, 예를 들어 `thermal.steady2d`는
  `materials == {}`를 요구합니다(`packages/simcase/src/simcase/thermal.py:93-94`).

**구성 요소 지정.** 물리 항목은 `"component": "<name>"`으로 구성 요소를 지정합니다. 발자국으로 쓰이지
않는 구성 요소가 정확히 하나이면 생략할 수 있습니다.

`periodic`은 예약입니다.

### 피처(동결)

`features`는 순서 있는 목록이고 순서에 의미가 있습니다. 나중 피처가 이깁니다
([불리언 규칙](#불리언-규칙동결) 참고). 각 피처의 필드는 다음과 같습니다.

**`name`**은 영역 이름입니다. 비어 있지 않은 문자열이며 구성 요소의 피처 사이에서 유일합니다.
- 지금 역할을 그대로 가집니다. 재료 표, 물리 키, 결과 키가 이 이름을 씁니다
  (`packages/simcase/src/simcase/thermal_regions.py:189-199,405-414`).
- 지금 허용되는 문자열은 `background`를 빼고 모두 그대로 유효합니다.
- MSH 쓰기는 따옴표나 줄바꿈이 든 이름을 거부합니다(`packages/meshine/src/meshine/mesh3d.py:329-333`).
  이는 쓰기의 한계이지 문서 규칙이 아닙니다.

**`id`**는 출처 이름과 선택자에 쓰는 식별자입니다.
- `^[A-Za-z_][A-Za-z0-9_-]{0,63}$`를 따르고 구성 요소 안에서 유일합니다.
- `name`이 이 문법에 맞고 예약어가 아니면 기본값은 `name`이고, 아니면 필수입니다.
- 예약 id는 대소문자를 구분하지 않고 비교합니다(Studio도 이미 그렇게 비교함,
  `packages/simcase/src/simcase/studio/static/workspace-shapes.mjs:58`): `background`, `domain`,
  `exterior`, `outer`, `void`, `axis`, `left`, `right`, `bottom`, `top`, `x0`–`z1`, `xmin`–`zmax`.

**`region`**(선택, 기본값 `name`)은 여러 피처를 한 영역으로 묶습니다. meshine과 gmshio는 이미 이름이
같은 조각을 합칩니다(`packages/meshine/src/meshine/refine.py:691-696`;
`packages/gmshio/src/gmshio/geo.py:113-115`). 다음 두 경우는 거부합니다.
- 재료가 다른 피처를 묶는 경우
- `region` 값이 그 영역 밖 피처의 `name`과 같은 경우

**`material`**은 재료 이름이거나, 빈 공간이면 `null`입니다.

**`mesh_size`**는 선택이며 의미는 지금과 같습니다.

**하위 이름.** 출처 부분이 되는 이름(층 이름, 다각형 `edges`, 경로 구간 이름, 발자국 부분)은 모두
부분 문법 `[A-Za-z0-9_-]+`를 따릅니다.

### 마무리(동결)

`finalize`는 나중 피처가 덮은 경계를 평가가 어떻게 다룰지 고릅니다.

| 방식 | 영역과 재료 | 덮인 경계 |
|---|---|---|
| `later_wins`(기본) | 지금과 같음 | 지움 |
| `imprint`(2D) | 지금과 같음(재료는 여전히 마지막으로 덮은 피처) | 출처를 가진 내부 곡선으로 남김 |

`imprint`는 경계면을 남기는 선택 방식입니다. 합집합이 아니어서 영역을 합치지 않고 재료도 바꾸지 않습니다.

**1단계 구현.** 1단계는 영역을 영역 이름이 같은 조각으로 나눕니다. meshine은 이런 조각을 합치고 공유
구간을 제약으로 유지하지만 경계면으로 보고하지는 않습니다
(`packages/meshine/src/meshine/refine.py:690-707`). 그래서 1단계는 이 곡선을 새 필드
`provenance_edges`에 적습니다([메시 태그](#메시-태그동결) 참고).

3D `imprint`는 예약입니다.

## 피처 어휘(따로 표시하지 않으면 동결)

피처 종류마다 필드와 **부분**이 정해져 있습니다. 부분은 피처 경계 가운데 이름이 있는 조각이며,
출처 이름은 부분으로 만듭니다.

### 2D와 축대칭

| `type` | 필드 | 부분 | 소비자 |
|---|---|---|---|
| `rect` | `x, y, w, h`(왼쪽 아래 꼭짓점과 크기, `w, h > 0`) | `left, right, bottom, top` | 모든 2D |
| `circle` | `cx, cy, r` | `boundary` | 모든 2D |
| `polygon` | `points`(3개 이상, 암묵적으로 닫힘, 단순); 선택 `edges`(변마다 부분 이름 하나) | `e1..eN`(점 i에서 점 i+1로 가는 변) 또는 `edges` 이름 | 모든 2D |
| `trapezoid` | `cx`(중심), `y`(아랫변), `w`(아랫변 폭), `h > 0`; 선택 `w_top`(기본 `w`) | `bottom, top, left, right` | sipi 어댑터; FEM 2D |
| `segment` | `points`(열린 꺾은선); `material` 없음 | `line` | 지금은 sipi 어댑터; FEM은 2단계부터 |
| `path` | `start: [x, y]`, `segments: [{"line": [x, y]} \| {"arc": {"center": [cx, cy], "to": [x, y], "ccw": bool}}]`, `start`로 닫힘; 선택 구간별 `name` | `s1..sN` 또는 구간 이름 | 2단계 전에는 없음 |

규칙:
- **`rect`와 `trapezoid`는 `polygon`과 다른 종류로 유지합니다.** 어떤 어댑터도 이들을 다각형으로
  바꾸지 않습니다.
- **`segment`는 넓이가 없습니다.** 그것을 품은 영역에 새겨지는 여차원 1 곡선이며, sipi의 두께 0
  스트립과 같습니다(`packages/sipi/src/sipi/crosssection.py:314-320,348-352`). 나중 면적 피처는 자기가
  덮는 부분을 지웁니다. meshine `Domain`은 영역 루프만 받으므로
  (`packages/meshine/src/meshine/geometry.py:118-121`) FEM은 2단계부터 `segment`를 받습니다.
- **`path`의 원호.** 반지름은 현재 점에서 `center`까지의 거리입니다. 끝점은 `center`에서 `to`를 지나는
  반직선이 원과 만나는 점입니다. 이 끝점은 유도점이며, `to`가 원 위에 있으면 `to`와 같습니다. 길이가
  0인 원호나 `to`가 `center`와 같은 원호는 거부합니다.

### 2.5D(`3d` 구성 요소 안)

| `type` | 필드 | 부분 |
|---|---|---|
| `extrude` | `profile`(`id` 없는 인라인 2D 피처 하나), `zmin, zmax`; `axis: "z"` | `bottom, top`; 옆면은 프로파일 부분 이름(`pad.left`, `via.boundary`) |
| `layers` | `z0`(바닥); `layers: [{name, thickness, material \| footprint + map, region?}]` | 아래 참고 |

`layers` 규칙:
- **판 층.** `material`이 있고 `footprint`가 없는 층은 도메인 x–y 범위 전체에 걸친 판입니다.
- **발자국 층.** `footprint`가 있는 층은 2D 구성 요소를 가리킵니다. 그 구성 요소의 도메인 x–y 범위는
  이 구성 요소의 것과 같아야 합니다.
- **`map`.** `map`은 발자국 영역 이름마다 재료 이름, `null`(빈 공간), `{"material": ..., "region": ...}`
  가운데 하나를 줍니다. `map`이 없으면 발자국 영역의 재료를 그대로 씁니다. 이는 `meshine.extrude`가 받는
  표와 같으며, 함수는 표 항목으로 풀어 씁니다(`packages/meshine/src/meshine/extrude.py:13-18,36-41`).
- **층 셀의 영역 이름.** 명시한 `region`이 있으면 그것이고, 없으면 재료 이름입니다. 이는
  `meshine.extrude`의 규칙입니다. 그래서 같은 재료로 대응한 두 발자국 영역은 지금처럼 합쳐집니다.
  나누려면 `region`을 줍니다.
- **z 높이**는 두께의 정확한 누적합입니다. 압출기처럼 두께에 대해 아핀입니다.
- **출처 이름:**
  - 층 셀: `<id>.<layer>`
  - 수평면: `<id>.<layer>.bottom`과 `<id>.<layer>.top`
  - 옆면: `<id>.<layer>.<발자국 피처 id>.<part>`, 발자국 도메인 변 위이면
    `<id>.<layer>.domain.<side>`
- `below`·`above`(반무한 매질)는 예약입니다.

### 3D

| `type` | 필드 | 부분 | 소비자 |
|---|---|---|---|
| `box` | `xmin, xmax, ymin, ymax, zmin, zmax`(공동 형식) | `x0, x1, y0, y1, z0, z1` | 지금 `em.cavity3d`; 5단계부터 meshloom |
| `cylinder` | `cx, cy, r, zmin, zmax`; `axis: "z"` | `side, bottom, top` | 5단계 전에는 없음 |
| `sphere` | `cx, cy, cz, r` | `surface` | 5단계 전에는 없음 |

`docs/packages/meshine/validation3d.md:76-95`가 사전 등록된 3D 사례를 나열하며, 이 사례들은 상자·원통·구를
씁니다.

**5단계 컴파일 조건 제안(동결 아님).** meshloom 3D 계획과의 합의가 아직 필요합니다.
- 상자는 겹칠 수 있고 나중 상자가 이깁니다.
- 원통은 z 방향입니다. 각 뚜껑은 층 평면, 도메인 z 면, 또는 한 영역 안에 놓입니다. 상자 면을 가로지르는
  곳에서는 뚜껑이 그 면 안에 완전히 들어가야 합니다.
- 구는 아무것과도 닿지 않습니다. 단독이거나 엄격히 중첩됩니다.
- 그 밖의 형상은 별도 프로세스 gmshio로 보냅니다. 이는 새 작업이며, 그 경로가 생기기 전에는 피처 이름을
  밝혀 거부합니다.

**meshloom API 입력으로 남는 것.** 원시 조각선형 복합체, 퍼즈 입력, 임의 double 가져오기 곡면
(`docs/packages/meshine/validation3d.md:76-95`의 C7, C10, C13, C14)은 형상 문서가 아닙니다. 격자로
반올림하면 이 사례들이 시험하는 것이 망가집니다.

## 불리언 규칙(동결)

기본은 지금 규칙인 "나중 피처가 이김"입니다(`packages/simcase/src/simcase/geometry.py:107-142`).
- **자르기.** 모든 피처는 도메인으로 자릅니다.
- **영역.** 피처 i의 영역은 clip(i)에서 모든 나중 피처 j > i의 clip(j) 합집합을 뺀 것입니다.
- **배경.** `background`는 도메인에서 모든 피처를 뺀 것입니다.
- **재료로 합치지 않음.** 재료가 같다는 이유로 피처를 합치지 않습니다. 재료가 같은 두 맞닿은 피처는
  경계면을 사이에 둔 두 영역으로 남습니다. 피처를 합치는 것은 `region`뿐입니다.
- **덮인 피처.** 나중 피처들이 완전히 덮은 피처는 영역을 만들지 않습니다. 그 피처를 가리키는 선택이
  어떻게 되는지는 [선택자 규칙](#선택자-규칙동결)이 정합니다.
- **떨어진 조각.** 한 영역이 지금의 MultiPolygon처럼 서로 떨어진 여러 면일 수 있습니다
  (`packages/simcase/src/simcase/geometry.py:213-216`).
- **슬리버.** 지금의 상대 규칙을 그대로 씁니다. 정확한 넓이가 `AREA_EPS = 1e-12` × 도메인 넓이보다
  작은 조각은 슬리버입니다(`packages/simcase/src/simcase/geometry.py:27-38`). 대응은 지금처럼 물리에
  따라 다릅니다. EM은 메모, 영역 열은 거부입니다
  (`packages/simcase/src/simcase/thermal_regions.py:139-157`).
- **3D.** 같은 규칙을 5단계 조합 안에서 씁니다. 공동은 구조 격자 중심점 규칙
  (`packages/galerkin/src/galerkin/material_cavity.py:342-346`)과 격자면 검사
  (`packages/simcase/src/simcase/cavity.py:130-141`)를 유지합니다. 둘 다 형상이 아니라 메시·물리 검사입니다.

영역이 겹치면 meshine은 혼자서는 그 넓이를 **앞** 영역에 줍니다
(`packages/meshine/src/meshine/refine.py:430-436`). 그래서 평가는 넘기기 전에 불리언을 풀고, 겹치는 피처를
`Domain`에 넘기지 않습니다.

## 출력: 영역 구성(동결)

구성 요소를 평가하면 메모리 안의 영역 구성이 나옵니다. 버전 1에는 이를 저장하는 형식이 없습니다. 진단용
덤프는 계약이 아닙니다.

**셀**은 2D에서는 면, 3D에서는 부피입니다. 각 셀은 영역 이름, 재료, 피처 출처를 가집니다.

**곡선(2D)과 곡면(3D)**은 각각 다음을 가집니다.
- `kind`: 2D는 `line`·`arc`·`circle`, 3D는 `plane`·`cylinder`·`sphere`
- 정확한 매개변수: 끝점, 중심, 반지름, 축
- **출처 집합**: 원래 곡선이나 곡면이 그 개체를 포함하는 모든 피처 부분(도메인 변 포함). 그 피처가
  인접 셀을 소유하는지와 상관없습니다. 예: 스택 바닥 평면 위에 놓인 비아 아래 뚜껑은 `via3.bottom`과
  `stack.sub.bottom`을 함께 가집니다.
- 양쪽의 셀, 또는 `exterior`

**꼭짓점**은 격자점이거나 유도 구성입니다.

출처 문법:

```text
provenance := id "." part ( "." part )*
id         := 피처 id, "domain" 또는 "background"
part       := [A-Za-z0-9_-]+
```

예: `via3.side`, `core.top`, `stack.sub.bottom`, `stack.top.die.left`, `domain.bottom`.

2D 도메인 변은 `domain.left`, `domain.right`, `domain.bottom`, `domain.top`이며, 축대칭에서는
`domain.axis`도 있습니다. 3D 도메인 면은 `domain.x0`부터 `domain.z1`까지입니다.

### 메시 태그(동결)

공유 메시 형식은 바뀌지 않습니다. `nodes`, 셀, `regions`, `region_names`, `boundary_edges` /
`boundary_faces`, `boundary_nodes`, 선택 `interfaces`입니다
(`packages/galerkin/src/galerkin/interop.py:55-111`;
`docs/packages/meshine/validation3d.md:38-54`). 모든 외부 변이나 면은 정확히 한 태그를 가집니다.

**기본 태그**는 소비자마다 지금 내는 태그와 정확히 같습니다. 기존 태그는 하나도 바뀌지 않습니다.

| 소비자 | 기본 외부 태그 |
|---|---|
| meshine을 거치는 2D | `box_sides`의 `left, right, bottom, top`; 그 밖의 변은 `outer`(`packages/meshine/src/meshine/geometry.py:297-318`) |
| 축대칭 | 같음. `xmin == 0`이면 `left` 대신 `axis` |
| `meshine.extrude`를 거치는 2.5D | `z0`, `z1`, 발자국 자체의 변 태그, `void`(`packages/meshine/src/meshine/extrude.py:33-60`) |
| `em.cavity3d` | `x0`–`z1`, 별칭 `xmin`–`zmax`(`packages/simcase/src/simcase/cavity.py:46`) |

**`boundary_tags`**는 `{"tag": ..., "select": <경계 선택자>}`의 순서 있는 선택 목록입니다.
- 외부 개체는 그것을 포함하는 첫 항목의 태그를 받습니다. 어느 항목에도 없으면 기본 태그를 유지합니다.
- 태그는 영역 이름과 같을 수 없습니다. gmshio가 한 이름을 두 차원에 쓰는 것을 거부하기 때문입니다
  (`packages/gmshio/src/gmshio/mesh.py:101-102`).
- 태그에는 따옴표나 줄바꿈이 들어갈 수 없습니다.

`boundary_tags`는 지금 코드가 읽는 태그를 재현합니다.
- sipi의 상수 `outer`(`packages/sipi/src/sipi/conductor_mesh.py:157,163`;
  `packages/sipi/src/sipi/crosssection.py:380`)와 galerkin의 `outer`
  (`packages/galerkin/src/galerkin/solver.py:33`)
- 전원면의 단자 태그, `outline`, `cutout`(`packages/sipi/src/sipi/plane.py:220-285`)
- 고리형 메시의 `inner`·`outer`(`packages/galerkin/src/galerkin/mesh.py:118-148`)

**새 선택 필드(추가만 함).** `provenance_edges`(2D)와 `provenance_faces`(3D)는 출처 이름마다 그 이름을
가진 `(E, 2)` / `(F, 3)` 메시 개체를 대응시킵니다.
- 출처 이름이 여럿인 개체는 각 이름 아래에 모두 나옵니다.
- `imprint`가 남긴 내부 곡선도 여기에 나옵니다.
- 선택자는 이 필드에서 풀리므로 선택이 변 태그의 일부만 덮을 수 있습니다. 예: `left`의 일부에 있는 단자.
- galerkin은 아직 이 필드를 읽지 않습니다. `interfaces`도 무시하고, 3D에서는 경계 노드 집합만 남깁니다
  (`packages/galerkin/src/galerkin/interop.py:100-111`). 새 필드를 쓰는 소비자는 그 작업을 기다립니다.

**그대로인 것.** 경계면은 정렬된 영역 쌍 키를 유지합니다
(`packages/meshine/src/meshine/refine.py:704-707`; `packages/meshine/src/meshine/mesh3d.py:43-55`).

**정확한 원.** 원이나 원호는 곡선 정체성을 하나만 가집니다. 그것에 닿는 모든 영역이 같은
`meshine.Circle` 객체를 받습니다. 이는 두 가지 어림 규칙, 곧 구멍의 5 % 넓이 맞춤과 `round(·, 12)` 키를
대신합니다(`packages/simcase/src/simcase/geometry.py:187,223-227`). meshine은 아직 완전한 원만
있으므로(`packages/meshine/src/meshine/geometry.py:60-81`) 메시의 원호는 2단계를 기다립니다.

## 선택자 규칙(동결)

선택자는 `{"region": <식>}` 또는 `{"boundary": <식>}`이며, 선택적으로 `"optional": true`를 붙입니다.
식은 문자열이거나 키가 정확히 하나인 객체입니다.

**문자열 해석**은 개체 종류에 따라 다릅니다. region 문자열은 경계로 풀리지 않고, boundary 문자열은
영역으로 풀리지 않습니다.

`region` 문자열은 다음 순서로 풉니다.
1. 영역 종류의 이름 있는 선택
2. 영역 이름
3. 피처 id(그 피처가 소유한 영역)

2와 3이 같은 피처를 가리키면(기본 `id` = `name`) 한 번 맞은 것으로 봅니다. 서로 다른 개체에 맞는
문자열은 거부합니다.

`boundary` 문자열은 다음 순서로 풉니다.
1. 경계 종류의 이름 있는 선택
2. 메시 태그: 위 표의 기본 태그나 선언한 `boundary_tags` 태그. 그 태그를 가진 개체를 정확히 고릅니다.
3. 출처 이름(점이 들어 있음)
4. 피처 id(출처가 그 피처를 가리키는 모든 곡선이나 곡면)

이렇게 나누므로 0.2에서 유효한 `top`이라는 영역 이름이 변 `top`과 부딪히지 않습니다. 선택 이름은 `id`
문법과 그 예약 목록을 따르며, 영역 이름이나 메시 태그와 같을 수 없습니다.

**객체 키:**

| 키 | 뜻 |
|---|---|
| `{"feature": "via3"}` | 그 피처가 소유한 영역. `boundary`에서는 출처가 그 피처를 가리키는 모든 개체 |
| `{"provenance": "via3.side"}` | 그 출처 이름을 가진 개체 |
| `{"material": "Cu"}` | 그 재료의 영역. `boundary`에서는 그 바깥 경계 |
| `{"between": [A, B]}` | 경계만: 한쪽에 A의 셀, 다른 쪽에 B의 셀 또는 `"exterior"`가 있는 개체 |
| `{"of": A}` | 경계만: 영역 집합 A의 경계 |
| `{"any": [...]}` | 나열한 선택자들의 합집합 |

`inside`·`kind`·`all`·`except`·`covered_by` 키는 예약입니다.

**빈 결과:**
- **이름 있는 선택.** `selections`나 `boundary_tags`의 선택이 아무것도 고르지 못하면 평가 시 그 선택
  이름을 밝힌 오류입니다. `"optional": true`이면 오류가 아닙니다. 스윕에서는 그 오류가 일어난 스윕 점의
  오류입니다.
- **영역을 가리키는 물리 키**는 종류별로 지금 동작을 유지합니다.
  - 검증은 나중 도형이 완전히 덮은 도형 이름을 받아들입니다
    (`packages/simcase/src/simcase/thermal_regions.py:139-146,189-199`).
  - 실행 시 영역 열은 살아남지 못한 영역의 열원을 거부합니다
    (`packages/simcase/src/simcase/thermal_regions.py:330-336`).
  - EM은 덮인 도형을 받아들입니다.

**원시 ID 없음.** 선택자에는 노드·변·면·셀·커널 ID가 들어가지 않습니다. 다각형 변 부분 `e1..eN`은 엔진
개체가 아니라 작성자의 점 순서를 가리킵니다.

**안정성.** `feature`·`provenance`·`material`·`between`·`of`·`any`와 이들로 풀리는 이름은, 위상이
유지되는 파라미터 변화에서 뜻이 바뀌지 않습니다.

## 문서의 다른 부분이 형상을 참조하는 방식(동결)

**물리.** 기존 키는 모양이 그대로입니다.
- 변을 가리키는 키는 boundary 문자열이므로 `boundary: {left: pec}`는 그대로 검증됩니다
  (`packages/simcase/src/simcase/schema.py:316-318`).
- 영역을 가리키는 키는 region 문자열이므로 `heat_source_w_m3: {heater: ...}`는 그대로 검증됩니다
  (`packages/simcase/src/simcase/thermal_regions.py:189-199`).
- `heater_top` 같은 다른 경계 이름은 이 계약이 허용하지만, 아직 받는 러너가 없습니다. 지금 영역 열은
  변이 아닌 태그를 모두 거부하고(`packages/simcase/src/simcase/thermal_regions.py:285-288`), EM은 정확히
  네 변을 요구합니다.

**재료**는 피처마다 `material`로 정하고, 지금처럼 `materials`와 physmat을 거쳐 풉니다.

**메시.** 다음은 그대로입니다.
- `mesh.size`, `min_angle`, `grading`(`packages/simcase/src/simcase/schema.py:351-355`)
- 피처 `mesh_size`
- `mesh.subdivisions`(메시 설정으로 남음)

새 선택 목록 `mesh.controls`는 다음 형태의 항목을 가집니다.
- `{"select": <name>, "size": h}`: 선택 위의 균일 크기
- `{"select": <name>, "circle_segments": n}`: 원 꼭짓점 수. 지금은
  `n = max(16, int(2πr/(size/2)))`(`packages/simcase/src/simcase/geometry.py:198`)이고, sipi 전원면은
  `n = 32`(`packages/sipi/src/sipi/plane.py:42`)입니다.
- `{"select": <name>, "z_divisions": n}`: 층 분할 수
- `{"select": <name>, "near": h0, "far": h1, "distance": d}`: 선택에서 멀어질수록 선형으로 커지는 크기.
  gmshio Threshold 필드에 해당합니다(`packages/gmshio/src/gmshio/geo.py:254-258`).

**스터디.** 스윕은 `geometry.parameters.<p>.value`를 가리킬 수 있습니다. 메시를 한 번만 만드는 러너는
점마다 다시 메시할 때까지 이를 계속 거부합니다(`packages/simcase/src/simcase/schema.py:367-371`).

## 파라미터, 스윕, 미분(동결)

- **스윕.** 스윕 점마다 파라미터로 형상을 다시 평가합니다. 점 사이에 위상이 바뀔 수 있으며, 바뀌면
  보고합니다.
- **설계 속도.** 길이 파라미터 p마다 평가는 정의 값, 유도점, 곡선 매개변수에 대해 V = ∂x/∂p를 줍니다.
  V는 반올림하지 않은 정확한 식에서 구합니다. 메시 노드 이동과 adjoint는 galerkin 소관입니다.
- **위상 변화.** p에서 위상이 바뀌면 미분을 거부하고 관련 피처를 밝힙니다. 엔진은 위상 변화를 넘어
  조용히 미분하지 않습니다. 정확한 탐침(간격과 퇴화 판정)은 4단계 보완이 정합니다.

## 소비자

모든 소비자는 받을 수 없는 것을 거부하며, 거부할 때 피처나 키워드를 밝힙니다.

| 소비자 | 받는 것 | 거부하는 것 |
|---|---|---|
| FEM 2D(meshine) | `2d` 구성 요소(러너가 생기면 `axisymmetric`도); `rect`, `circle`, `polygon`, `trapezoid` | 2단계 전 `path`·`segment`; 예약 키워드 |
| FEM 2.5D(`meshine.extrude`) | `layers`, z 방향 `extrude` | 기울거나 휜 옆면. 압출기는 수직 프리즘만 만듦(`packages/meshine/src/meshine/extrude.py:4-19`) |
| `em.cavity3d` | 격자면 규칙을 지키는 `box` | 다른 3D 피처 |
| FEM 3D(meshloom, 5단계) | 5단계 조합 | 그 밖의 모든 것(gmshio 경로가 생길 때까지) |
| sipi | 어댑터를 거친 `2d` 구성 요소. 어댑터는 sipi의 겹침 거부를 유지(`packages/sipi/src/sipi/crosssection.py:216-239`) | — |
| Wavebit RCWA·FDTD | 3단계 보완이 정의 | — |

## 예시

### 파라미터와 선택이 있는 2D 열광학 단면

```json
{
  "openphysics": "0.2",
  "name": "Heated SOI strip",
  "units": {"length": "nm", "temperature": "K"},
  "geometry": {
    "version": 1,
    "parameters": {"w": {"value": 500}, "t": {"value": 220}, "gap": {"value": 1000, "range": [500, 2000]}},
    "components": {
      "xs": {
        "dimension": "2d",
        "domain": {"xmin": -3000, "xmax": 3000, "ymin": -2000, "ymax": 3000},
        "background": {"material": "SiO2"},
        "features": [
          {"name": "core", "type": "rect", "x": "-w/2", "y": 0, "w": "w", "h": "t", "material": "Si", "mesh_size": 20},
          {"name": "heater", "type": "rect", "x": -1000, "y": "t + gap", "w": 2000, "h": 100, "material": "heater_metal"}
        ],
        "finalize": "later_wins",
        "selections": {
          "heater_top": {"boundary": "heater.top"},
          "core_wall": {"boundary": {"between": ["core", "background"]}}
        }
      }
    }
  }
}
```

`physics`·`materials`·`mesh` 블록은 생략했으며 지금처럼 동작합니다.
`dirichlet_temperature_k: {"bottom": 300}`의 `bottom`은 메시 태그로, `heat_source_w_m3: {"heater": 1e15}`의
`heater`는 영역으로 풀립니다. `w = 501`인 스윕 점에서는 `x = -250.5` nm, 곧 −250500 pm이므로 격자
위에 있습니다.

### 사다리꼴 트레이스가 있는 sipi 마이크로스트립

상자 폭 4 mm, h = 0.2 mm, 구리 두께 35 µm, 문서 단위 `m`입니다.

```json
"features": [
  {"name": "substrate", "type": "rect", "x": -0.002, "y": 0, "w": 0.004, "h": 0.0002, "material": "substrate"},
  {"name": "air", "type": "rect", "x": -0.002, "y": 0.0002, "w": 0.004, "h": 0.002035, "material": "air"},
  {"name": "signal", "type": "trapezoid", "cx": 0, "y": 0.0002, "w": 0.0003, "w_top": 0.00028, "h": 0.000035, "material": "conductor"}
],
"boundary_tags": [{"tag": "outer", "select": {"boundary": {"between": [{"any": ["substrate", "air"]}, "exterior"]}}}]
```

sipi에서 옮기는 방식:
- **재료.** 층의 `eps_r`·`tan_delta`는 `substrate`·`air`라는 `materials` 항목이 됩니다.
- **물리**는 도체를 밝힙니다:
  `"conductors": {"signals": ["signal"], "reference": {"boundary": "bottom"}}`.
- **순서.** 층을 아래부터 먼저 두고 트레이스를 뒤에 둡니다. 이는 도체가 유전체를 자른다는 sipi 규칙을
  재현합니다(`packages/sipi/src/sipi/crosssection.py:294-326,354-368`).
- **두 메시 역할.** 정전 소비자는 도체가 아닌 영역만 메시하므로 도체는 지금처럼 구멍입니다. 도체 단면
  소비자는 도체를 금속으로 메시합니다(`packages/sipi/src/sipi/conductor_mesh.py:59-164`).

### 비아가 있는 2.5D 패키지 스택

```json
"components": {
  "plan": {"dimension": "2d", "domain": {"xmin": 0, "xmax": 10000, "ymin": 0, "ymax": 10000},
           "background": {"material": "mold"},
           "features": [
             {"name": "die", "type": "rect", "x": 3000, "y": 3000, "w": 4000, "h": 4000, "material": "Si"},
             {"name": "via3", "type": "circle", "cx": 1500, "cy": 1500, "r": 150, "material": "Cu"}]},
  "pkg": {"dimension": "3d", "domain": {"xmin": 0, "xmax": 10000, "ymin": 0, "ymax": 10000, "zmin": 0, "zmax": 2500},
          "background": {"material": null},
          "features": [
            {"name": "stack", "type": "layers", "z0": 0, "layers": [
              {"name": "sub", "thickness": 1000, "footprint": "plan", "map": {"die": "FR4", "via3": "Cu", "background": "FR4"}},
              {"name": "top", "thickness": 1500, "footprint": "plan", "map": {"die": "Si", "via3": "mold", "background": "mold"}}]}
          ],
          "selections": {"via_wall": {"boundary": "stack.sub.via3.boundary"}, "sink": {"boundary": "stack.sub.bottom"}}}
}
```

층 셀은 압출 규칙에 따라 `FR4`·`Cu`·`Si`·`mold`라는 이름을 가집니다. `meshine.extrude`는 지금도 이
스택을 받을 수 있습니다. 기본 태그는 `z0`, `z1`, 발자국의 변, `void`입니다.

## 현재 표현 대응표(동결)

표에 쓰는 용어:
- **손실**: 이 계약이 담을 수 없는 정보
- **이름 변경**: 이름이 바뀌며 그 사실을 보고함
- **반올림**: 값을 한 번 1 pm 격자로 옮기며 보고함
- **동작**: 형상을 잃지 않는 검증 변화

| 현재 표현 | 출처 | 표현 방식 | 손실과 변화 |
|---|---|---|---|
| simcase 0.2 `geometry.domain/background/shapes`(`rect`, `circle`, `polygon`, `name`, `material`, `mesh_size`) | `packages/simcase/src/simcase/schema.py:278-292`; `packages/simcase/src/simcase/geometry.py:41-49` | `finalize: later_wins`인 `2d` 구성 요소 하나. 도형은 피처가 되고 `name`은 영역 이름으로 남음. `id`는 문법에 맞고 예약어가 아니면 `name`, 아니면 `s<i>`(목록 위치). 물리 키와 결과 키는 그대로 | 손실 없음. 반올림: 1 pm 격자를 벗어난 값은 반올림(`examples/simcase`에는 없음, 부록 참고). 동작: (1) 검증기 하나가 약한 EM 검증기(`packages/simcase/src/simcase/schema.py:278-292`)와 영역 열 검증기(`packages/simcase/src/simcase/thermal_regions.py:44-75`)를 대신하므로, 자기 교차 다각형이나 유한하지 않은 수가 든 EM 문서는 거부됨. (2) 꼭짓점을 정확히 계산한 뒤 한 번 반올림하므로 메시는 지금과 반올림 수준에서 다름 |
| 단독 정확 원; 구멍 어림 규칙 | `packages/simcase/src/simcase/geometry.py:71-104,216-229` | 구성 안의 `circle` 종류, 곡선 정체성 하나를 공유 | 없음. 어림 규칙은 사라짐 |
| 가려진 원(128각형) | `packages/simcase/src/simcase/geometry.py:46` | `circle`. 불리언 뒤의 원호는 2단계에서 | 문서에서는 없음. 2단계 전까지 메시는 여전히 다각형을 씀 |
| MultiPolygon 영역; 슬리버 규칙 | `packages/simcase/src/simcase/geometry.py:27-38,213-216` | 면이 여럿인 영역 하나; 같은 `AREA_EPS` 규칙 | 없음 |
| 사각형 문서(열, 전기, 줄, 균일 과도) | `packages/simcase/src/simcase/thermal.py:80-99`; `packages/simcase/src/simcase/steady_boundary_contract.py:59-71`; `packages/simcase/src/simcase/electric_joule.py:27-37` | 도메인만 있고 피처가 없으며 배경에 `material` 키가 없는 `2d` 구성 요소. `mesh.subdivisions`는 `mesh`에 남음 | 없음. 키 유무로 가르던 것(`packages/simcase/src/simcase/thermal_regions.py:30-36`)은 JSON 결정에서 명시 필드로 바뀜 |
| `em.cavity3d` 상자와 벽 키 | `packages/simcase/src/simcase/cavity.py:46,104-145` | `box` 피처와 나중 피처 우선 규칙을 쓰는 `3d` 구성 요소. 기본 태그 `x0`–`z1`, 별칭 `xmin`–`zmax`. 격자면·중심점 규칙은 메시 검사로 남음 | 이름 변경: `background`라는 상자(지금은 허용, `packages/simcase/src/simcase/cavity.py:121-124`)는 이름이 바뀜. 이득: 상자 이름이 이제 영역 구성까지 감(지금은 경계와 재료만 솔버에 전달, `packages/simcase/src/simcase/cavity.py:400-406`) |
| PML 두께, 굽힘, 등급 중심 | `packages/simcase/src/simcase/pml_contract.py:18-41`; `packages/simcase/src/simcase/schema.py:351-355` | 그대로인 물리·메시 필드 | 없음 |
| 영역 복잡도 검사; Studio 한도 | `packages/simcase/src/simcase/complexity.py:46-93`; `packages/simcase/src/simcase/studio/thermal_regions_api.py:47-60` | 그대로, 피처 기준으로 셈 | 없음 |
| 기존 Studio | `packages/simcase/src/simcase/studio/static/index.html:750` | 지금처럼 문서를 편집 | 없음 |
| Studio 작업공간 프로젝트·세션 v1–v5; 기능 엔드포인트 | `packages/simcase/src/simcase/studio/static/workspace-project.mjs:21-70`; `packages/simcase/src/simcase/studio/static/workspace-notebook.mjs:9-23`; `packages/simcase/src/simcase/studio/server.py:80-135` | 형상 v1로 컴파일되는 응용 형식이며 자체 형상 의미는 없음. 도형은 피처가 됨: `name`은 표시 이름, 이름에 공백이 있으면 `id`를 생성. 창은 `domain`, 열판은 사각형 문서 | 초안에 한한 손실: 재료가 없는(`''`) 도형. 반올림: Studio는 값을 10⁻⁶ nm까지 유지(`packages/simcase/src/simcase/studio/static/workspace-shapes.mjs:15-16`)하고 이동은 그 정리를 거치지 않음(`packages/simcase/src/simcase/studio/static/workspace-shape-editor.mjs:9-16`). 1 pm 아래는 반올림. 이 형식의 폐기 여부는 JSON 결정에 맡김 |
| Studio 광학 솔버 문서(`s1..sN`, 사각형을 다각형으로 씀) | `packages/simcase/src/simcase/studio/static/workspace-shapes.mjs:91-98` | 첫 행과 같은 0.2 문서 | 그 문서는 프로젝트보다 이미 손실이 있음. 계약은 그 문서가 아니라 프로젝트에서 받음 |
| sipi `CrossSection`: 층, 트레이스(직사각형, 사다리꼴, 두께 0), 상자 변 플래그, 접지 플래그 | `packages/sipi/src/sipi/crosssection.py:42-206` | `2d` 구성 요소: 전폭 층 `rect`를 아래부터, 그 뒤 트레이스를 트레이스 순서로 `rect`·`trapezoid`·`segment`. `eps_r`·`tan_delta`는 층 이름의 `materials` 항목. 물리는 `conductors`(순서 있는 `signals`, 접지 트레이스와 접지 변을 담은 `reference` 선택)를 가짐. 변 플래그는 변 태그 위의 물리. `outer`는 `boundary_tags`에서 | 형상 손실 없음. 이름 변경: 층과 트레이스의 이름이 같으면(지금은 목록을 따로 검사하므로 허용, `packages/sipi/src/sipi/crosssection.py:195-200`) 영역으로 합쳐지므로 하나의 이름을 바꿈. 반올림: `(w+gap)/2`(`packages/sipi/src/sipi/templates.py:65`) 같은 템플릿 산술은 0.00015000000000000001 m 같은 값을 내며 격자에서 약 10⁻⁸ pm 벗어남. 동작: 사각형 경로의 정확한 부동소수점 일치(`packages/sipi/src/sipi/crosssection.py:319,348-353`)가 바뀔 수 있고, 동일성 시험 `tests/sipi/test_manufacturing_sections.py:19`가 이를 감지함(열린 질문). 겹침·맞닿음 거부(`packages/sipi/src/sipi/crosssection.py:216-239`)는 어댑터에 남으므로 나중 피처 우선 규칙이 sipi 겹침을 풀지 않음. 허용오차 기반 도체 노드 고르기(`packages/sipi/src/sipi/crosssection.py:389-410`)는 선택으로 바뀜 |
| sipi JSON `sipi.cross-section/1,/2`과 선로·부피 감싸개 | `packages/sipi/src/sipi/document.py:13-161`; `packages/sipi/src/sipi/line_model.py`; `packages/sipi/src/sipi/volume_line.py` | 형상 v1로 컴파일되는 응용 형식. 스키마 버전(/1, /2)은 sipi 형식의 속성 | 없음. 템플릿 파라미터는 지금도 저장하지 않음 |
| sipi 도체 단면 메시(`signal-<i>`, `reference`, `_bottom`/`_top`/`_side`, `ground_thickness`) | `packages/sipi/src/sipi/conductor_mesh.py:59-164` | 그 소비자가 같은 형상과 자기 메시 옵션으로 만듦 | 없음. 합성 이름은 그 소비자의 메시 세부 사항이 됨 |
| sipi `PowerPlane`: 외곽선, 구멍, 세 종류의 단자 | `packages/sipi/src/sipi/plane.py:42-71,181-286` | 외곽선은 영역 `copper`인 `polygon` 또는 `circle`. 구멍은 `material: null`인 나중 피처. 루프 전체 단자는 `{"boundary": {"feature": <id>}}`, 변 단자는 이름 붙인 다각형 `edges`의 `any`. `boundary_tags`가 단자 이름, `outline`, `cutout`을 재현. 두께는 물리로, 원 `n`은 `circle_segments`로 | 없음. 어댑터는 겹치는 구멍과 외곽선 밖 구멍을 거부함(지금은 `packages/sipi/src/sipi/plane.py:282-285`에서 실패) |
| 직접 만든 meshine `Domain`(영역 타일링, 같은 이름 병합, `Circle`) | `packages/meshine/src/meshine/geometry.py:104-208` | 피처, 병합에는 `region`. `domain`은 모든 루프의 경계 상자, `background`는 `null`. `box_sides`는 기본 태그, 상수 이름은 `boundary_tags` 항목 하나, 루프별 이름은 피처별 항목 | 손실: `boundary_names`의 임의 좌표 콜백 |
| `meshine.shapes` 리브와 광섬유 | `packages/meshine/src/meshine/shapes.py:11-49` | 피처. 광섬유의 `outer`는 `boundary_tags`에서 | 없음 |
| `meshine.extrude`(영역 × 층 → 재료 또는 None, z 높이, `z0`/`z1`/`void`) | `packages/meshine/src/meshine/extrude.py:33-60` | `footprint`와 `map`이 있는 `layers`. 함수는 표로, 분할은 `z_divisions`로, 사용자 지정 `bottom`/`top`/`void` 이름은 압출 소비자의 메시 옵션으로 | 손실: 완성된 `TriMesh`로만 주어진 발자국은 형상이 아니며 메시 수준 API로 남음 |
| gmshio `Geo` 다각형; 미리 만든 리브·광섬유·상자 공동 | `packages/gmshio/src/gmshio/geo.py:42-126,227-302` | 피처. `pec`는 상자의 모든 면을 덮는 `boundary_tags` 항목. Threshold 필드는 거리 등급 `mesh.controls` 항목 | 손실: `raw()` `.geo` 텍스트와 Gmsh 필드 문법 |
| galerkin 구조 격자 생성기: 사각형, 고리(`inner`/`outer`), 원판과 층 사각형(`layer0..`), 상자(`x0`–`z1`) | `packages/galerkin/src/galerkin/mesh.py:81-260`; `packages/galerkin/src/galerkin/mesh3d.py:124-161` | 도메인만; 안쪽에 빈 원이 있는 원(태그는 `boundary_tags`에서); 이름이 `layer<i>`인 중첩 원이나 사각형; 3D 도메인. 구조 격자 메시는 메시 옵션으로 남음 | 없음 |
| meshloom 점 집합 | `packages/meshloom/src/meshloom/_core.py:60-77` | 형상이 아님 | — |
| meshloom 빌더(계획)와 원시 double 입력 | `packages/meshloom/src/meshloom/__init__.py:41-46`; `docs/packages/meshine/validation3d.md:76-95` | 빌더는 5단계 피처가 됨 | 원시 PLC, 퍼즈, 가져오기 곡면 입력은 meshloom API 입력으로 남으며 범위 밖 |
| Wavebit RCWA·FDTD 장면 | Wavebit API | 3단계 보완 | 이 동결 대응표에 들어가지 않음 |

## 부록: 현재 예제 점검(일부)

**확인한 것:**
- `examples/simcase/*.json` 25개는 모두 `units.length`를 선언합니다.
- 그 `geometry` 블록 안의 숫자 값(202개)은 모두 정수 nm이므로 정수 pm입니다. 반올림이 필요 없습니다.
- 반올림 수준의 꼭짓점 변화가 하나 알려져 있습니다: `pml_leaky_slab.json`([내부 격자](#내부-격자-1-pm동결)
  참고).

**아직 점검하지 않은 것.** 승인 전에 반드시 점검해야 합니다.
- `packages/simcase/src/simcase/examples.py`와 `thermal_examples.py`의 내장 예제
- 문서와 시험 안의 sipi 문서
- 저장된 Studio 프로젝트
- `examples/meshine/extrude_chip.py`, `examples/meshine/compare_with_gmsh.py`
- `examples/gmshio/hadley_rib_mesh.py`
- galerkin 생성기 예제

## 3단계 미리보기: Wavebit (동결 아님)

이 절은 규범이 아닙니다. 3단계 보완이 더해야 할 것을 적습니다. 그 바탕의 Wavebit 사실은 이름 있는
커밋의 Wavebit 체크아웃과 대조하지 않았습니다. 보완은 공개 Wavebit 저장소의 특정 SHA를 인용해야
합니다.

- **주기 셀:** 격자 벡터 둘을 정확히 저장합니다. 비스듬한 셀과 육각 셀을 포함하며, 그러려면
  `(a, b, angle)` 형식이나 식 안의 `√`가 필요합니다.
- **주기 의미:** 피처는 잘리는 대신 감기고, 격자 셀이 기본 영역이 됩니다.
- **새 피처:** `ellipse` 종류, 자유 `rotation`과 그 각도 단위, x·y 방향 압출, 회전한 3D 상자
- **층:** 반무한 매질(`below` / `above`)이 있는 z 불변 층
- **변환 규칙:** 압출한 원은 프리즘이 아니라 원통이 됩니다.
- **범위 밖:** 래스터 유전율 층은 형상이 아니라 재료 데이터입니다.

## 정한 질문 (2026-11-02)

1. 메시 생성기의 상대 허용오차보다 작은 피처는 검증 단계에서 이름·크기·비를 밝혀 거부합니다. 이를
   지원하는 일은 장기 과제입니다.
2. sipi 사각형 한계 동일성 시험은 1단계 어댑터가 생길 때까지 그대로 둡니다. 그 뒤 노드 동일성을 해석
   또는 저장 기준값과 기존 허용오차로 비교하는 시험으로 바꾸려면 별도 결정이 필요합니다. 허용오차는
   완화하지 않습니다.
3. 평가기는 simcase 안에 둡니다. shapely 없이 동작해야 하고, scipy는 제한하지 않습니다
   ([평가기의 위치](#평가기의-위치) 참고).
4. sipi JSON과 Studio 프로젝트는 자기 형식을 유지하고 1단계 어댑터로 읽습니다. 폐기 여부는 JSON 계약
   결정에서 정합니다. 새 형상 기능은 버전 1에 먼저 넣습니다.
5. Wavebit 변환(주기 셀, 타원, 회전, 각도, x·y 방향 압출)은 3단계 보완으로 미룹니다.
   [3단계 미리보기](#3단계-미리보기-wavebit-동결-아님)는 계속 비규범입니다.

## 열린 질문

1. 점 선택자(기준 노드, 탐침)는 정의하지 않았습니다. 어느 단계에서 더할까요?
