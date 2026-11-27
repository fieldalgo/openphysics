# 3D 구성 요소의 정상 열(`thermal.steady3d`)

[English](../../../../../packages/simcase/thermal_steady3d.md) | **한국어**

[문서 홈](../../index.md)

`thermal.steady3d`는 형식 0.3 문서에서 버전 1 형상 블록([형상 문서](geometry_document.md))의 `3d` 구성 요소
하나에 대해 정상 열전도 −∇·(k∇T) = Q를 풉니다. 얇은 종류입니다. [영역의 `thermal.steady2d`](thermal_regions2d.md)
키 가운데 3D에 맞는 것을 받고, 구성 요소를 5단계 경로 가운데 하나로 메시한 뒤 `galerkin.solve_steady_heat_3d`로
풉니다. Studio는 아직 이 종류를 열지 않습니다.

```json
{
  "openphysics": "0.3",
  "name": "three-layer slab",
  "geometry": {"version": 1, "components": {"pkg": {
    "dimension": "3d", "length_unit": "mm",
    "domain": {"xmin": 0, "xmax": 10, "ymin": 0, "ymax": 10, "zmin": 0, "zmax": 2.5},
    "background": {"material": null},
    "features": [{"name": "stack", "type": "layers", "z0": 0, "layers": [
      {"name": "a", "thickness": 1, "material": "lower"},
      {"name": "b", "thickness": 0.5, "material": "core"},
      {"name": "c", "thickness": 1, "material": "upper"}]}]}}},
  "materials": {"lower": {"thermal_conductivity": "1 W/(m K)"},
                "core": {"thermal_conductivity": "0.01 W/(m K)"},
                "upper": {"thermal_conductivity": "1 W/(m K)"}},
  "physics": {"heat": {"type": "thermal.steady3d",
                       "prescribed_temperature": {"z0": "300 K", "z1": "301 K"}}},
  "mesh": {"element_size": "0.4 mm"}
}
```

```python
from simcase import Document, run
result = run(Document.load("slab3d.json"))
result.temperature, result.reaction_heat_rate     # 노드마다, K와 W
result.save("out/")                               # summary.json, fields.npz, model.json, log.txt
```

## 메시 경로

경로는 계약의 [메시 생성기 경로](geometry_document.md#5단계-컴파일-조건2026-11-27-보완)를 따릅니다.

| 구성 요소 | 경로 | 외부 태그 |
|---|---|---|
| 판 층으로 된 `layers` 피처 하나 | `meshine.extrude`: 도메인 사각형을 요소 크기로 meshine이 메시하고, 그 두께 이하의 하위 층으로 층 높이를 따라 압출 | `z0`, `z1`, 발자국 옆면 `left`, `right`, `bottom`, `top` |
| 슬라이스 1이 받는 [상자와 판 층](geometry_engine3d.md)의 그 밖의 조합 | meshloom을 거치는 `simcase.build_mesh3d`(**실험 단계**) | 도메인 면에 `x0`–`z1`, 그 밖에 `void`, 또는 `boundary_tags` |

결과의 `route`(요약의 `mesh_route`)가 어느 경로였는지 알려 줍니다. 발자국 층이 있는 단독 `layers` 피처는 아직
받지 않습니다. 압출 경로의 면은 태그만 가지므로 그 경로에서는 `selections`와 `boundary_tags`를 거부합니다.

## 키

| 키 | 뜻 |
|---|---|
| `physics.<name>.prescribed_temperature` | `{경계 이름: 온도}`. meshloom 경로에서는 [선택자 규칙](geometry_document.md#선택자-규칙동결)으로 이름을 풉니다. 태그, 이름 있는 경계 선택, 출처 이름(`domain.z0`, `via.x1`, `stack.c.top`), 피처 id입니다. 압출 경로에서는 위의 태그 가운데 하나입니다. 하나 이상 필요합니다. |
| `physics.<name>.heat_source_density` | 값 하나, 또는 메시되는 영역에 대한 `{영역: 값}`. 없으면 열원 없음 |
| `materials.<m>.thermal_conductivity` | 재료가 `m`인 모든 영역의 열전도율 |
| `mesh.element_size` | 필수. meshloom 경로에서는 [build_mesh3d](geometry_engine3d.md#사용)처럼 `mesh.element_count_limit`과 `mesh.controls` `element_size`도 받음 |

`prescribed_temperature`가 이름 짓지 않은 외부 면은 모두 단열입니다. 이름 없이 남은 기본 태그마다
`I-DEFAULT-BOUNDARY`를 한 번 알립니다. 두 이름이 고정하는 노드는 온도가 하나여야 합니다.

이름을 밝혀 거부하는 것:
- 내부 면에 거는 고정 온도(`E-CONTRACT`): `Fixed temperature needs an outer face; <name> is inside`. galerkin은
  외부 노드만 고정합니다.
- 아무 면도 고르지 않는 이름, 메시되지 않는 영역의 열원(`E-SELECTION-UNKNOWN`)
- `inward_heat_flux`, `convection`과 2D 종류의 그 밖의 키(`E-KEY-UNKNOWN`), 물리 항목의 `thermal_conductivity`
  (`materials`에서 받음)
- `thermal_conductivity`가 없는 재료(`E-PROPERTY-MISSING`)
- `2d`나 축대칭 구성 요소, 구성 요소 둘 이상
- `mesh.subdivision_count`, `minimum_angle`, `grading`
- `{"type": "single"}`이 아닌 스터디와 `results.plots`

## 결과

`summary.json`의 `result_format`은 `thermal.steady3d-result-v1`, `field_layout`은
`thermal3d-p1-node-tet-regions-v1`입니다. 형식 0.3 결과가 공유하는 봉투(진단, 기본값, 해석된 입력, 범위, 시간)와
`mesh_route`, 영역(재료, 사면체, 부피), 재료, 지정 온도, `reaction_heat_rate_by_boundary`(`prescribed_temperature`
이름마다 W, 두 이름이 고정하는 노드는 앞 이름에 셈), `generated_heat_rate`, `outward_reaction_heat_rate`,
`heat_rate_imbalance`, `relative_conservation_residual`, 온도와 열전도율의 최솟값·최댓값, 메시 개수와 태그를
담습니다. 열 비율은 W 단위 합이며 깊이가 없으므로 깊이 없는 이름을 씁니다.

`fields.npz`에 담기는 것:

| 배열 | 모양 | 단위 | 위치 |
|---|---|---|---|
| `node_coordinates` | (N, 3) | m | 노드 |
| `tetrahedra` | (T, 4) | — | 사면체 연결 |
| `tetrahedron_regions` | (T,) | — | `region_names`의 번호 |
| `temperature` | (N,) | K | 노드 |
| `heat_flux` | (T, 3) | W/m² | 사면체 중심 |
| `generated_heat_rate`, `reaction_heat_rate`, `residual_heat_rate` | (N,) | W | 노드 |
| `prescribed_node_ids`, `prescribed_temperature` | (P,) | —, K | 지정 노드 |

`simcase export`는 아직 이 배치를 받지 않습니다. `fields.npz`를 읽으세요.

## 검증

Linux(2026-11-27)에서 `tests/simcase/test_thermal_steady3d.py`로 측정했습니다.

| 검사 | 사례 | 기준 | 측정 |
|---|---|---|---|
| 종류를 거친 P1 | 위 문서(E1), h = 0.8, 0.4 mm, `refsol.thermal3d.layered_slab`과 비교 | 노드 최대 \|T_h − T\| ≤ 1e-10; 윗면 열 비율(`z1`의 반력) 상대 오차 ≤ 1e-9 | 1.4e-12와 3.4e-12; 2.5e-11과 4.8e-12(사면체 7,680개와 49,152개, T는 300 K 근처) |
| 비트 일치, 압출 경로 | E1을 `meshine.extrude` + `solve_steady_heat_3d` 직접 호출과 비교 | 노드, 사면체, 온도, 반력 열 비율의 SHA-256이 같음 | 같음 |
| 비트 일치, meshloom 경로 | 코어 층에 구리 상자를 넣은 E1을 `build_mesh3d` + `solve_steady_heat_3d`와 비교 | SHA-256이 같음 | 같음 |

## 한계

- 지정 온도와 체적 열원만 있는 정상 열전도입니다. 열유속, 대류, 과도, 결합은 아직 없습니다. Studio는 이 종류를
  열지 않습니다.
- meshloom 경로는 meshloom 수용 전까지 실험 단계이며 상자와 판 층을 받습니다([3D 상자와 판 층](geometry_engine3d.md)).
  압출 경로는 판 층으로 된 단독 스택을 받습니다.
- `simcase export`는 이 배치를 지원하지 않는 배치로 거부합니다.
