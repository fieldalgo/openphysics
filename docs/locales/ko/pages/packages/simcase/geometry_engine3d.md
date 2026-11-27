# meshloom을 거치는 3D 상자와 판 층(5단계, 실험 단계)

[English](../../../../../packages/simcase/geometry_engine3d.md) | **한국어**

[문서 홈](../../index.md)

**상태: 실험 단계.** meshloom 자체가 수용되기 전까지입니다([meshloom](../meshloom/overview.md)).
`simcase.geometry_engine3d`는 [형상 문서 계약](geometry_document.md) 5단계의 슬라이스 1입니다. 계약의
[5단계 컴파일 조건](geometry_document.md#5단계-컴파일-조건2026-11-27-보완)에 따라 `3d` 구성 요소의 `box`
피처와 판 층으로 3D 영역 구성을 만들고 `meshloom.generate3d`로 메시합니다. 아직 이를 읽는 물리 러너는
없습니다.

## 사용

```python
import simcase

result = simcase.build_mesh3d(document)        # 형식 0.3 문서(dict 또는 simcase.Document)
mesh = result.mesh                             # galerkin.Mesh3D, 미터 단위
mesh.tagged_faces                              # {"x0": (F, 3), ..., "void": (F, 3)}
result.provenance_faces["cap.z1"]              # 그 이름을 가진 모든 면의 (F, 3) 면
result.selections["joint"]                     # ("boundary", (F, 3) 면) 또는 ("region", 사면체)
result.selection_nodes["joint"]                # 선택의 노드 번호
result.complex                                 # 3D 영역 구성(셀, 면, 출처)
```

`build_mesh3d(document, component=None)`은 버전 1 형상 블록이 있는 문서와 그 `mesh` 블록을 받습니다
(구성 요소가 하나이면 이름을 생략할 수 있습니다).

| 키 | 뜻 |
|---|---|
| `mesh.element_size` | 크기를 주지 않은 모든 영역의 크기 |
| 피처나 배경의 `element_size` | 그 피처나 배경 영역의 크기 |
| `mesh.controls` `{"select": <영역 선택>, "element_size": h}` | 선택한 영역의 크기. 나중 항목이 이김 |
| `mesh.element_count_limit` | 기본값 600000. 메시하기 전에 T = 6.3 Σ V_r / h_r³와 비교하고, meshloom에는 점 상한으로 넘김 |

영역은 셀들의 가장 작은 크기를 씁니다. 추정값은 사면체당 0.4–0.6 ms로 본 예상 메시 시간과 함께
`result.diagnostics`에 `I-MESH-ESTIMATE`(정보)로 알립니다. 한도를 넘으면 추정값과 함께 문서를 거부합니다
(`E-MESH-ESTIMATE`). 경계 선택에 거는 크기, 거리 등급(`near`, `far`, `refinement_distance`),
`z_divisions`는 3D 구성 요소에서 이름을 밝혀 거부합니다.

`simcase.geometry_engine3d.evaluate3d(model, component=None)`은 `simcase.geometry_document.parse`로 읽은
모델의 영역 구성만 돌려줍니다. 압출 경로로 메시되는, `layers` 피처 하나만 가진 구성 요소는 거부합니다. 표시용(Studio)
`simcase.geometry_engine3d.display_complex3d(model, component=None)`은 그런 구성 요소를 포함해 슬라이스 1이 받는 모든
`3d` 구성 요소의 정확한 영역 구성, 곧 meshloom 경로가 만들 구성을 돌려줍니다. 아무것도 메시하지 않으며
`build_mesh3d`가 하거나 거부하는 것을 바꾸지 않습니다.

## 만드는 것

- **프리즘.** 모든 `box`와 모든 판 층(`material`이 있고 `footprint`가 없는 층)은 수직 프리즘입니다. 판
  층은 정확한 z 높이 사이에서 도메인 x–y 범위를 덮으며, 셀 이름은 압출 경로처럼 `region`, 없으면 재료
  이름입니다.
- **나중 피처가 이김.** 모든 프리즘의 발자국을 경계를 모두 남긴 채 [2단계 엔진](geometry_engine.md)에
  한 번 넣습니다. 그래서 잘게 나뉜 2D 셀마다 그 셀을 품는 프리즘의 정확한 집합이 붙습니다. 구성 요소를
  서로 다른 모든 z 높이에서 자르면, 판 구간 안에서 셀의 영역은 그 셀을 품는 마지막 활성 프리즘의 것이고,
  없으면 배경입니다. 이는 계약의 판 구간별 규칙, 곧 그 판 구간에서 활성인 프리즘을 2단계 엔진으로 푼 "나중
  피처가 이김" 배열과 같습니다. 셀은 2D 셀 하나 × 판 구간
  하나이며, `material: null`이면 빈 공간입니다.
- **면.** 수평면은 위아래 영역이 다르거나 한쪽이 도메인 밖인 곳에, 수직면은 2D 곡선 양쪽의 영역이 다른
  곳에 있습니다. 빈 공간 셀 둘 사이, 빈 공간 셀과 바깥 사이의 면은 메시하지 않고 목록에도 없습니다.
  양쪽과 출처가 같은 면은 평면 안에서, 그리고 판 구간을 건너 합칩니다. 경계가 꼭짓점에서 자기와 만나는
  수평면은 사각형으로 나눠, meshloom이 받는 모든 루프가 단순하게 합니다.
- **출처.** 면은 그 면을 품는 표면의 모든 부분을 가집니다. 그 피처가 이웃 셀을 가졌는지와 상관없습니다.
  `<box>.x0` … `<box>.z1`, `domain.x0` … `domain.z1`, 판 층은 `<id>.<layer>.bottom`,
  `<id>.<layer>.top`, 옆면 `<id>.<layer>.domain.x0` … `<id>.<layer>.domain.y1`입니다. 이는 계약의
  `<id>.<layer>.domain.<side>`에 3D 도메인 면 이름을 쓴 것으로, 2D 이름은 층 뚜껑(`<id>.<layer>.bottom`,
  `.top`)과 겹치기 때문입니다. `meshine.extrude`는 출처를 내지 않으므로 두 경로가 이 이름을 다르게 쓸 수
  없습니다. 수직면은 그 판
  구간에서 활성인 프리즘의 부분만 가집니다.
- **태그.** 도메인 면 위의 외부 면은 `x0`–`z1`, 그 밖의 외부 면(빈 공간 셀과 맞닿은 면)은 `void`입니다.
  `boundary_tags`가 이름을 바꾸며, 먼저 맞는 항목이 이깁니다.
- **선택**은 계약의 [선택자 규칙](geometry_document.md#선택자-규칙동결)을 따릅니다. `{"boundary": "z0"}`(태그),
  `{"boundary": "domain.z0"}`와 `{"boundary": "cap.z1"}`(출처 이름), `{"boundary": "cap"}`(출처가 그 피처를
  가리키는 모든 면), `{"boundary": {"between": [a, b]}}`, `{"boundary": {"of": a}}`, `{"region": name}`,
  `{"region": {"feature": id}}`, `{"region": {"material": m}}`. 아무것도 고르지 않는 이름 있는 선택은
  `optional`이 아니면 거부합니다.

## meshloom에 넘기기

- **좌표(규칙 H1).** pm 값 k마다 `float(Fraction(k, 10**12))` 미터가 되며 한 번만 반올림합니다. 그래서
  축에 정렬된 평면의 점들은 double 하나를 공유하고 평면은 정확하게 남습니다. 한 축의 서로 다른 두 값이
  같은 double로 반올림되면 둘 다 밝혀 거부합니다.
- **패싯.** 면 하나가 평면 패싯 하나이며, 바깥 루프가 먼저입니다. 패싯의 변 위에 놓인 구성의 모든 점을
  그 변에 넣으므로, 두 패싯은 온전한 변이나 점에서만 만나고 직선을 따라 일부만 겹치지 않습니다. 패싯마다
  고유 태그(`f<i>`)가 있고, 결과는 그것을 태그와 출처로 되돌립니다.
- **영역.** 유계 성분마다 정확한 내부 점 하나를 영역 이름과 함께 줍니다. 닫힌 빈 공간은 `None`이며
  메시하지 않습니다. 도메인 경계에 닿는 빈 공간은 메시 바깥입니다.
- **크기.** `h`는 크기 하나이거나 영역마다 하나입니다.
- **메시 면.** 외부 면은 패싯 태그에서 옵니다. 내부 면은 meshloom의 `interfaces`에서 오며, 축 정렬 평면의
  정확한 일치로, 한 평면에 패싯이 여럿이면 면 중심을 각 패싯 다각형에 정확히 판정해 패싯에 배정합니다.
  `mesh.interfaces`의 키는 정렬된 영역 이름 쌍이며, 첫째에서 둘째로 감깁니다.
- **오류.** meshloom 오류(`InvalidPLC`, `RecoveryError`, `RoundingError`, `RegionError`, `RefineError`,
  `MeshError`)는 오류가 가리키는 패싯의 출처 이름과 피처를 붙여 `simcase.geometry_engine3d.Mesh3DError`로
  다시 알립니다(`.cause`, `.facets`, `.provenance`).

메시는 galerkin이 받는 double에서 meshloom의 보장을 지닙니다. 모든 사면체의 정확한 `orient3d > 0`과
[3D 검증 계획](../meshine/validation3d.md)의 출력 계약입니다.

## 거부하는 것

코드 `E-3D-COMBINATION`, 피처의 `features[i]`에서, 계약의 메시지 줄기로(메시지는 영어로 나옵니다):

- `extrude`, `cylinder`, `sphere`: `<type> '<name>' is not taken yet in a 3d component; boxes and slab
  layers are`(원통과 구는 슬라이스 3이 받음)
- 다른 피처와 함께 쓴 발자국 `layers`: `layers '<name>' has footprint layers; with other features a 3d
  component takes slab layers only, until a later slice`
- 같은 double로 반올림되는 두 값: `<a>.<part> and <b>.<part> round to the same coordinate <x> m`
- `mesh.controls`의 `circle_segment_count`: `mesh.controls: circle_segments on '<select>' is not taken for
  3d surfaces yet; use size`(`mesh.controls[i]`에서)

`layers` 피처 하나만 가진 구성 요소는 `meshine.extrude` 경로(`simcase.geometry_document.layer_stack`,
그대로)를 유지하며 `build_mesh3d`는 이를 거부합니다(`E-CONTRACT`). `em.cavity3d` 문서는 자기 경로와 결과를
유지합니다.

## 검증

사전 등록된 검사이며 `tests/simcase/test_geometry_engine3d.py`가 실행합니다.

| ID | 사례 | 지표 | 기준 | 측정(Linux, 2026-11-27) |
|---|---|---|---|---|
| G1 | 4 × 3 × 2 격자(mm)에 상자 8개 이하를 놓은 시드 고정 "나중 피처가 이김" 집합 200개(닿음, 중첩, 공유 평면, 도메인 밖 상자, 빈 공간 포함), h = 0.25 격자 단위; 전수 오라클(점을 품는 마지막 상자) | (a) 정확한 중심을 오라클이 다른 영역에 두는 사면체 수; (b) 영역 부피 상대 오차 | (a) 0; (b) ≤ 1e-12 | 200개 모두: (a) 0; (b) 최대 2.8e-16(메시한 집합 199개, 사면체 496–12,664개; 시드 69는 빈 공간 배경 위의 빈 공간 상자 하나라 메시할 것이 없어 이름을 밝혀 거부) |
| G2 | G1 집합과 E1 | 출처 이름 아래 면 중 그 부분의 정확한 표면 밖에 있는 것; 부분 표면 위에 있는데 그 부분을 적지 않은 구성 면; 이름별 메시 넓이와 정확한 면 넓이(1e-12); 정확히 한 태그에 들지 않는 외부 면 | 0 | 0 |
| G3 | 테스트 파일의 모든 메시 | [validation3d](../meshine/validation3d.md)의 V1(출력 double에서 정확한 orient3d ≤ 0)과 V2 | 0; 모두 성립 | 0; 모두 성립 |
| G4 | m, mm, µm, nm로 쓴 E1, h = 0.8 mm | 정규 메시 배열의 SHA-256 | 같음 | 같음 |
| G5 | E1, h = 0.8 mm, 새 프로세스 3개 | SHA-256 | 같음 | 같음 |
| G6 | 위 거부마다 문서 하나 | 코드, 경로, 메시지 안의 이름 | 100% | 100% |
| P1 | meshloom과 `meshine.extrude`를 거친 E1, `refsol.thermal3d.layered_slab`(P1에서 정확)과 비교 | 노드 최대 \|T_h − T\|; 윗면 열 비율 상대 오차 | ≤ 1e-10; ≤ 1e-9 | 아래 |

E1은 두께 1, 0.5, 1 mm(z 높이 0, 1, 1.5, 2.5 mm)인 판 층 셋으로, k = 1, 0.01, 1 W/(m K)이고 도메인은
10 × 10 mm입니다. `z0`에서 T = 0, `z1`에서 T = 1, 옆면은 단열이며 `galerkin.solve_steady_heat_3d`로
풉니다.

P1 측정값:

| 경로 | h (mm) | 사면체 | 최대 \|T_h − T\| | 윗면 열 비율 |
|---|---|---|---|---|
| meshloom | 0.8 | 4,891 | 1.6e-15 | 1.7e-15 |
| meshloom | 0.4 | 28,284 | 2.3e-15 | 1.4e-14 |
| `meshine.extrude` | 0.8 | 7,680 | 4.8e-15 | 8.8e-14 |
| `meshine.extrude` | 0.4 | 49,152 | 9.4e-15 | 5.0e-15 |

풀 리퀘스트는 소스 시험 부분에서 G1을 200개 가운데 고정 시드 25개(여덟 번째마다)로 돌립니다.
`OPENPHYSICS_GEOMETRY3D_FULL=1`이면 200개를 모두 돌리며, CI job `geometry3d-full`이 main push와 수동 dispatch에서
그렇게 합니다([CI가 돌리는 것](../../development.md#ci가-돌리는-것)).

## 한계

- 실험 단계: meshloom은 아직 수용되지 않았고, 메시 품질은 meshloom의 것입니다.
- 상자와 판 층만 받습니다. 발자국 층은 혼자이면 압출 경로를 쓰고, 다른 피처와 함께이면 뒤 슬라이스까지
  거부합니다.
  원통과 구는 슬라이스 3에서 옵니다.
- 영역마다 크기 하나입니다. 등급 크기나 표면 크기는 아직 없습니다.
- 면과 셀은 2D 셀과 판 구간마다 나열합니다. 구성은 메모리 안의 진단 구조이며 저장 형식이 아닙니다.
- Python: 구성은 정확한 정수로 순수 Python에서 만듭니다. 상자가 많은 구성 요소는 서로 다른 평면 수에
  따라 커지는 배열을 만듭니다.
