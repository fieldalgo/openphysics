# 재료 영역이 있는 열전도 문서

[English original](../../../thermal_regions2d.md)

`geometry`에 `background`나 `shapes`가 있는 `thermal.steady2d`·`thermal.transient2d`
문서는 여러 재료를 기술합니다. 전자기 문서와 같은 기하를 씁니다: 이름 있는 도형마다 재료 이름을 달고,
배경 위에 순서대로 그립니다(나중 도형이 앞 도형을 자릅니다). 열 물성은 `materials` 표에서
옵니다. 메시는 모든 영역 경계를 따릅니다. headless API/CLI 경로이며 Studio는 이 문서를
거부합니다(아래 한계 참고).

`background`/`shapes`가 없는 사각형 문서는 [원래 계약](thermal_steady2d.md)과
[경계 확장](thermal_steady_boundary2d.md)을 그대로 따릅니다.

## 예제

배포 예제 `thermal_regions`(`examples/thermal_regions.json`,
`simcase example thermal_regions`)는 단열재 안의 강판에 구리 히터가 박혀 있고, 아랫면은
고정 온도, 윗면은 대류로 식는 문제입니다.

```json
{
  "openphysics": "0.2",
  "name": "Heated steel plate in insulation",
  "units": {"length": "mm", "temperature": "K"},
  "geometry": {
    "domain": {"xmin": 0, "xmax": 40, "ymin": 0, "ymax": 20},
    "background": {"material": "insulation"},
    "shapes": [
      {"name": "plate", "type": "rect", "x": 5, "y": 5, "w": 30, "h": 6, "material": "steel"},
      {"name": "heater", "type": "circle", "cx": 20, "cy": 8, "r": 2, "material": "copper", "mesh_size": 0.5}
    ]
  },
  "materials": {
    "steel": {"conductivity_w_mk": 45},
    "copper": {"conductivity_w_mk": 400},
    "insulation": {"conductivity_w_mk": 0.04}
  },
  "physics": {"heat1": {
    "type": "thermal.steady2d",
    "heat_source_w_m3": {"heater": 5e6},
    "dirichlet_temperature_k": {"bottom": 300},
    "convection": {"top": {"h_w_m2k": 10, "ambient_temperature_k": 295}}
  }},
  "mesh": {"size": 2, "min_angle": 28},
  "study": {"type": "single"},
  "results": {"save_fields": true, "plots": false}
}
```

```bash
simcase validate packages/simcase/examples/thermal_regions.json
simcase run packages/simcase/examples/thermal_regions.json -o heated_plate
```

## 입력

- `units`: 사각형 문서처럼 `length`와 `temperature: "K"`를 명시합니다. 기하·도형 크기·
  메시 크기는 길이 단위를 쓰고, SI 접미어(`_w_mk`, `_w_m3`, `_w_m2`, `_w_m2k`, `_k`)가
  붙은 물성은 SI입니다.
- `geometry.domain`: 사각형. 네 변이 경계 태그 `left`, `right`, `bottom`, `top`입니다.
- `geometry.background`: `material`과 선택 `mesh_size`. 배경 영역 이름은 `background`입니다.
- `geometry.shapes`: `rect`(`x`, `y`, `w`, `h`), `circle`(`cx`, `cy`, `r`), `polygon`
  (`points`, `[x, y]` 세 개 이상, 자기 교차 없음)의 목록. 각각 고유한 비어 있지 않은
  `name`(`background` 제외), `material`, 선택 `mesh_size`를 가지며 다른 키는 받지 않습니다.
  도형은 영역 안으로 잘리고, 영역 면적의 1e-12보다 작게 남은 영역은 전자기 문서처럼 버립니다.
- `materials`: `{재료 이름: {...}}`. 사용하는 모든 재료에 `conductivity_w_mk` > 0(필수),
  선택 `volumetric_heat_capacity_j_m3k` > 0(정상 열전도는 쓰지 않음), 선택 `source` 메모.
  열 물성은 내장 광학 재료에서 가져오지 않으므로 사용하는 재료는 모두 여기 정의해야 합니다.
  쓰지 않는 재료는 허용합니다.
- `physics.<name>`: `type`, `heat_source_w_m3`(숫자 하나, 또는 `{영역 이름: 숫자}`이며
  적지 않은 영역은 0), 사각형 문서와 같은 변 규칙의 `dirichlet_temperature_k`,
  `outward_flux_w_m2`, `convection`(모서리 충돌 거부, Dirichlet 변이나 양의 Robin 고정 필요,
  Dirichlet 변에 자연 조건 금지). 여기의 `conductivity_w_mk`는 거부합니다(`materials`에서 옴).
- `mesh`: `size` > 0(길이 단위, 필수), `min_angle`(도, 기본 28, 최대 33).
  `subdivisions`와 `grading`은 거부합니다.
- `study` `{"type": "single"}`; `results.plots`는 false여야 합니다.

메시 후 남지 않은 영역(나중 도형에 완전히 덮임)의 이름으로 준 열원은 실행할 때 거부합니다.

## 메시와 풀이

기하는 문서 단위로 meshine이 메시하고(요청한 최소각의 제약 Delaunay 세분), 미터로 정확히
배율 변환합니다. 모든 도형 경계가 요소 변으로 이어지므로 삼각형마다 한 영역에 속합니다.
곡선 경계는 내접 다각형이라 원의 메시 면적은 pi r^2보다 O(h^2)만큼 작습니다. 메시한 문제는
열전도율과 열원을 영역 이름으로 연결해 `galerkin.thermal.solve_steady_heat`에 넘깁니다
([multimaterial](https://github.com/fieldalgo/openphysics/blob/main/packages/galerkin/docs/locales/ko/pages/multimaterial.md)).

meshine은 같은 기하를 다른 길이 단위로 쓰면 같은 절점 위치를 만들지 않습니다. 그래서 mm,
m, um 결과는 절점 단위가 아니라 이산화 오차 수준에서 일치합니다. 어댑터의 단위 변환 자체는
정확한 곱셈입니다.

## 결과

`result_format`은 `thermal.steady2d-regions-result-v1`, `field_layout`은
`thermal2d-p1-node-cell-regions-v1`입니다. 저장 필드는 경계 v2 배치(`nodes_m`, `triangles`,
`temperature_k`, `heat_flux_w_m2`, `load_w_per_m`, `reaction_w_per_m`, `residual_w_per_m`,
`dirichlet_node_ids`, `dirichlet_temperature_k`, `prescribed_outward_load_w_per_m`,
`ambient_load_w_per_m`, `convective_outward_w_per_m`, `system_rhs_w_per_m`)에
`triangle_regions`(삼각형별 정수 영역 번호)를 더한 것입니다. 경계 필드는 항상 있습니다(자연
조건이 없으면 0). 요약에는 `region_names`(`triangle_regions`의 번호 순서), `regions`(영역별
재료, 삼각형 수, m^2 단위 메시 면적), `materials` 표, `conductivity_range_w_mk`, 메시 크기,
달성한 최소각이 더해집니다. 부호와 단위는 경계 계약과 같습니다: 반력은 안쪽으로 들어오는
thermostat 열, 전체 바깥 열은 `sum(prescribed_outward_load + convective_outward - reaction)`,
절점 열량은 모두 깊이당 W/m입니다.

## 검증

`packages/simcase/tests/test_thermal_regions.py`, 비교 전에 고정한 기준:

| 검사 | 기준 |
| --- | --- |
| 층상 벽 문서(10 mm 강철 Q = 2e5 W/m^3, 20 mm 단열재, 400/300 K) 대 `refsol.thermal_multilayer.layered_slab`, 메시 크기 2, 1, 0.5, 0.25 mm | 마지막 두 구간에서 T L2 차수 >= 1.8, 열유속 L2 차수 >= 0.9; 열수지 <= 1e-10 |
| 같은 벽을 mm, m, um으로 | 어댑터 절점 = meshine 절점 x 단위 배율(정확히); 정확한 벽 대비 T·열유속 오차가 5% 이내로 일치 |
| 배포 예제 대 같은 메시의 `solve_steady_heat` 직접 호출 | 온도·반력 동일; 열원 = Q x 메시 히터 면적(1e-12); 히터 면적이 pi r^2의 1% 이내; 바깥 열 = 열원(1e-10) |
| 저장 필드와 요약 | 형식, `triangle_regions`, 경계 필드, 영역 표, 재료, 전체 면적, 모델 사본 |
| CLI | validate·run 종료 코드 0, 기존 출력이면 1 |
| 잘못된 문서 19개와 덮인 열원 영역 | `DocumentError`로 거부 |
| 사각형 문서 | 비어 있지 않은 `materials`는 여전히 거부, 원래 결과 형식 |
| Studio | 영역 문서는 메시·작업자 호출 전에 거부 |

처음 실행했을 때 관측값(메시 크기 2 → 0.25 mm):

| 양 | 값 | 차수 |
| --- | --- | --- |
| T L2 (K m) | 4.07e-6, 1.03e-6, 2.59e-7, 6.42e-8 | 1.98, 2.00, 2.01 |
| 열유속 L2 (W/m) | 0.478, 0.241, 0.121, 0.0603 | 0.99, 1.00, 1.01 |

복합 원통과 경계면 열유량을 포함한 엔진 수준 영역별 검증은
[multimaterial](https://github.com/fieldalgo/openphysics/blob/main/packages/galerkin/docs/locales/ko/pages/multimaterial.md)에 있습니다.

## 과도 문서

`background`/`shapes`가 있는 `thermal.transient2d` 문서는 정상 영역 문서와 같은 기하,
`materials` 표, `mesh`(`size`, `min_angle`)를 쓰고, 시간 규칙은
[thermal_transient2d](thermal_transient2d.md)와 같습니다: `units.time: "s"`, 증가하는 명시적
초의 `study: {"type": "transient", "time_s": [...]}`, `initial_temperature_k`(균일 숫자 또는
`affine` 객체), 변별 `dirichlet_temperature_k`(상수 또는 요청 시각마다의 `{"values_k": [...]}`,
t0에서 초기장과 일치). 사용하는 모든 재료에 `conductivity_w_mk`와
`volumetric_heat_capacity_j_m3k`가 필요하고, `heat_source_w_m3`는 숫자 또는
`{영역 이름: 숫자}`입니다. physics 수준의 `conductivity_w_mk`나
`volumetric_heat_capacity_j_m3k`는 거부합니다. 배포 예제는 `transient_thermal_regions`
(`examples/transient_thermal_regions.json`)입니다.

결과는 `thermal.transient2d-regions-result-v1`, `thermal2d-transient-p1-node-cell-regions-v1`로
사각형 과도 필드에 정적 `triangle_regions`를 더합니다. 요약에는 `region_names`, `regions`,
`materials`, 메시 크기가 더해집니다. `heat_content_j_per_m`는 영역별 열용량을 쓴 `1^T M T`입니다.
전체 이력을 메모리에 둡니다(O(단계 수 x (절점 + 삼각형))). 아래 수렴 연구의 최대 메모리는 약
825 MiB였습니다.

검증(`packages/simcase/tests/test_transient_thermal_regions.py`):

| 검사 | 기준 |
| --- | --- |
| 모든 영역에서 Q_i = r c_i, 단열 변 | 모든 절점·시각에서 T = T0 + r t(300 K의 1e-10), 열유속 1e-9 W/m^2 미만 |
| 긴 시간 극한(500 s 간격, 1e4 s까지) 대 정상 영역 문서 | 같은 메시, 마지막 온도가 온도 상승의 1e-9 이내 |
| 같은 메시의 `solve_transient_heat` 직접 호출 | 온도·열유속·반력·열량 동일 |
| 균일 300 K에서 가열하는 층상 벽(Q 2e5 / 5e4 W/m^3, 양끝 300 K) 대 `refsol.transient_heat_multilayer.LayeredWall.source_driven`, 메시 크기 4, 2, 1, 0.5 mm, dt = 1/64 s, 20 s 관측 | 마지막 두 구간에서 T L2 차수 >= 1.8, 열유속 L2 차수 >= 0.9; 0.5 mm에서 dt를 절반으로 하면 각 오차 변화 <= 5% |
| 한 재료만 쓴 문서 대 사각형 과도 문서 | 열원 1e-12 일치, 최고 온도 2e-3 K 이내 |
| 저장 필드, CLI, 잘못된 문서 10개, Studio 거부 | 형식·영역·재료, 종료 코드, `DocumentError`, 작업자·메시 호출 없음 |

수렴 기준의 앞선 두 구성은 후진 Euler의 1차 시간 오차가 공간 오차와 분리되지 않아 실패했습니다.

| 구성 | 관측 | 결과 |
| --- | --- | --- |
| dt = 1/4 s, 180 s까지 | 20, 60, 180 s | 마지막 구간 T 차수 0.62, 0.52, 0.88; dt/2에서 T 오차 43%, 44%, 37% 변화(열유속 차수 0.99-1.00은 통과) |
| dt = 1/64 s, 20 s까지 | 5, 10, 20 s | 마지막 구간 T 차수 1.72, 1.86, 1.92; dt/2에서 T 오차 13%, 7.1%, 4.4% 변화 |

남긴 기준은 두 번째 실행에서 분리 기준을 만족한 유일한 시각인 20 s를 관측하며, 이 시각은 실행을
본 뒤 골랐습니다. 관측값(메시 크기 4 → 0.5 mm): T L2 1.81e-4, 4.75e-5, 1.18e-5, 3.11e-6 K m
(차수 1.93, 2.01, 1.92), 열유속 L2 0.942, 0.477, 0.241, 0.121 W/m(차수 0.98, 0.99, 1.00),
dt/2 변화 4.4%(T)와 3e-8(열유속). 이 해상도에서 더 이른 과도 시각은 위의 정확 재현·엔진 일치
검사와 [multimaterial](https://github.com/fieldalgo/openphysics/blob/main/packages/galerkin/docs/locales/ko/pages/multimaterial.md)의
엔진 검증으로만 다룹니다.

## 한계

- Studio는 정상·과도 영역 문서를 거부합니다(열 화면이 `mesh.subdivisions`를 읽음). CLI나 Python API를
  쓰십시오.
- 구간 상수 등방 물성, 경계면 완전 접촉.
- 단위 깊이 평면 기하. 내장 재료의 열 물성 없음.
