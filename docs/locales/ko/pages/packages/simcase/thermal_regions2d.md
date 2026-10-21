# 재료 영역이 있는 열전도 문서

[English original](../../../../../packages/simcase/thermal_regions2d.md)

`geometry`에 `background`나 `shapes`가 있는 `thermal.steady2d`·`thermal.transient2d`
문서는 여러 재료를 기술합니다. 전자기 문서와 같은 기하를 씁니다: 이름 있는 도형마다 재료 이름을 달고,
배경 위에 순서대로 그립니다(나중 도형이 앞 도형을 자릅니다). 열 물성은 `materials` 표에서
옵니다. 메시는 모든 영역 경계를 따릅니다. headless API/CLI 경로이며 Studio는 이 문서를
거부합니다(아래 한계 참고).

`background`/`shapes`가 없는 사각형 문서는 [원래 계약](thermal_steady2d.md)과
[경계 확장](thermal_steady_boundary2d.md)을 그대로 따릅니다.

## 예제

배포 예제 `thermal_regions`(`examples/simcase/thermal_regions.json`,
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
    "steel": {"conductivity_w_mk": 45, "source": "document value"},
    "copper": {"conductivity_w_mk": 400, "source": "document value"},
    "insulation": {"conductivity_w_mk": 0.04, "source": "document value"}
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
simcase validate examples/simcase/thermal_regions.json
simcase run examples/simcase/thermal_regions.json -o heated_plate
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
  도형은 영역 안으로 잘립니다. 영역 밖에 있거나 영역 면적의 1e-12보다 작은 도형은 거부합니다(전자기
  문서는 실행 기록에 아무 말 없이 버림). 나중 도형에 완전히 덮인 도형은 삼각형이 없으며 실행 기록에
  이름이 나옵니다. 자르고 남은 면적 0인 조각(도형이 영역이나 다른 도형에 바깥에서 닿기만 한 곳)은
  메시하지 않습니다.
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

기하와 전역·영역별 메시 크기를 전자기 문서와 같은 십진 비율 환산으로 먼저 마이크로미터로
바꿉니다. meshine이 요청한 최소각으로 제약 Delaunay 세분을 한 뒤, 정규화된 좌표를 문서
단위로 되돌리는 과정 없이 SI 미터로 직접 환산해 열 솔버에 넘깁니다. 모든 도형 경계가 요소 변으로 이어지므로 삼각형마다 한 영역에 속합니다.
곡선 경계는 내접 다각형이라 원의 메시 면적은 pi r^2보다 O(h^2)만큼 작습니다. 메시한 문제는
열전도율과 열원을 영역 이름으로 연결해 `galerkin.thermal.solve_steady_heat`에 넘깁니다
([multimaterial](../galerkin/multimaterial.md)).

뒤 도형과 겹치지 않고(원 안에 통째로 들어간 뒤 도형 포함) 다른 경계와 닿지 않는 원은 절점이 정확한
원 위에 있습니다. 그 밖의 원은 다른 도형처럼 128각형으로 메시하므로 이웃 영역과 경계를 하나로
공유합니다.

**작은 각도 근처의 메시.** 다른 경계에 닿거나 가로지르는 원, 또는 뾰족한 다각형 꼭짓점은
60도보다 작은 입력각을 만들고, 일반 Ruppert 세분은 이런 곳에서 끝나지 않습니다. meshine은 이런
모서리를 따로 처리하고, 그래도 해결하지 못하는 입력은 오류로 거절하며, 잘라내기가 남길 수 있는
분해능 이하의 변은 제거합니다([meshine 개요](../meshine/overview.md#작은-입력각)).
배포 예제의 히터(r = 2 mm)를 놓았을 때 끝없이 돌던 위치는 이제 모두 메시됩니다. Linux에서 다섯 번
실행한 가장 빠른 값:

| 히터가 가로지르는 곳 | 교차 | 시간 | 삼각형 수 | 최소각 |
| --- | --- | --- | --- | --- |
| 아래 변 | 접촉 | 0.51 s | 3030 | 1.41° |
| | 18° | 0.22 s | 2093 | 18.28° |
| | 20° | 0.19 s | 2062 | 21.09° |
| | 25° | 0.20 s | 2018 | 23.91° |
| | 35° | 0.25 s | 1979 | 28.11° |
| | 45° | 0.13 s | 1716 | 28.45° |
| 강판 윗변(위에서) | 접촉 | 0.78 s | 3942 | 1.41° |
| | 18° | 0.51 s | 2554 | 18.28° |
| | 30° | 0.26 s | 2602 | 28.39° |
| | 45° | 0.18 s | 2116 | 28.52° |

히터는 128각형으로 메시하므로 변과 이루는 모서리 각은 접촉일 때 1.41°이고, 그 밖에는 명목 교차
각도와 최대 1.4° 다릅니다(18°에서 18.28°, 20°에서 21.09°). 그 모서리 각이 28° 하한보다 작으면
모서리 안의 삼각형이 그 각을 그대로 가집니다. 28° 미만 삼각형은 모두 접촉점이나 교차점에서
0.03 mm 이내에 있고, 그 점에서 0.1 mm보다 멀리 뻗는 삼각형은 모두 28.0° 이상입니다. 영역 면적은
잘라낸 기하와 1e-12 mm²까지 같습니다. 예외는 45°로, 잘라내기가 6.3e-7 mm(영역 대각선의 1.4e-8)
길이의 변을 남기고 meshine이 이를 제거해 영역 면적이 3.1e-9 mm² 달라집니다. 전에도 메시되던 30,
41, 50, 60도 교차와 아래 변에서 0.001 mm 떨어뜨린 경우는 절점 하나까지 같은 메시를 만듭니다.
두 변 모두에서 1도부터 89도까지 모든 홀수 각도의 교차가 1.1 s 안에 메시됩니다.

남은 한계: 종료는 이 경우들에서 측정한 것이지 증명한 것이 아니고, Linux에서만 측정했습니다.
meshine이 여전히 처리하지 못하는 입력은 계속 돌지 않고 오류로 끝납니다. 점 상한, 반복 한도, 또는
삼각분할이 구분하지 못하는 경계 점이며, 마지막 경우 오류가 그 점을 알려 줍니다(예: 자신이 속하지
않은 변에서 영역 대각선의 약 1e-9~1e-7만큼 떨어진 꼭짓점. 그 변 위로 옮기거나 충분히 떼어
놓으세요). 도형을 다른 경계에서 떼어 두면 여전히 가장 좋은 삼각형을 얻습니다. 전자기 문서도 같은
메시 생성기를 쓰므로 똑같이 동작합니다.

같은 마이크로미터 숫자로 환산되는 입력은 같은 수치 환경에서 mm, m, um, nm 및 사용자 정의
길이 단위에 관계없이 SI 절점·연결·영역·경계 태그와 정상·과도 해석 필드가 동일합니다.
과도 affine 초기 온도장의 영역 원점도 메시와 같은 정규화→SI 경로를 사용합니다. SI 접미어가
있는 재료·하중·온도 값과 해석 시각은 바뀌지 않습니다. 저장 `nodes_m`은 미터이며
`model.json`은 원래 문서 단위를 유지합니다.

환산 후 한 ulp라도 다른 입력이나 서로 다른 라이브러리 버전·플랫폼 사이의 동일성을 보장하지는
않습니다. 정규화로 기존 um 이외 문서의 이산화가 달라질 수 있으며, 해석해 정확도·수렴 기준은
그대로 적용합니다. meshine 자체가 단위에 무관한 절점 위치를 보장하는 것은 아닙니다.

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

`tests/simcase/test_thermal_regions.py`, 비교 전에 고정한 기준:

| 검사 | 기준 |
| --- | --- |
| 층상 벽 문서(10 mm 강철 Q = 2e5 W/m^3, 20 mm 단열재, 400/300 K) 대 `refsol.thermal_multilayer.layered_slab`, 메시 크기 2, 1, 0.5, 0.25 mm | 마지막 두 구간에서 T L2 차수 >= 1.8, 열유속 L2 차수 >= 0.9; 열수지 <= 1e-10 |
| 같은 벽을 mm, m, um, nm으로 | SI 절점·삼각형·T·열유속 동일; 기존 해석해 절대 오차 기준 유지 |
| 배포 예제 대 같은 메시의 `solve_steady_heat` 직접 호출 | 온도·반력 동일; 열원 = Q x 메시 히터 면적(1e-12); 히터 면적이 pi r^2의 1% 이내; 바깥 열 = 열원(1e-10) |
| 저장 필드와 요약 | 형식, `triangle_regions`, 경계 필드, 영역 표, 재료, 전체 면적, 모델 사본 |
| CLI | validate·run 종료 코드 0, 기존 출력이면 1 |
| 잘못된 문서 19개, 덮인 열원 영역, 영역 밖 도형, sliver 한계보다 작은 도형 | `DocumentError`로 거부 |
| 나중 도형에 덮인 도형 | 삼각형 없음, 실행 기록에 이름 |
| 강판 윗변을 가로지르게 옮긴 히터 | 다각형으로 메시(하위 프로세스, 300 s 제한), 열수지 <= 1e-10 |
| 아래 변이나 강판 윗변에 접하거나, 아래 변을 18, 35, 45도로 또는 윗변을 18, 45도로 가로지르는 히터(전에 끝나지 않던 7가지 위치) | 하위 프로세스(120 s 제한)에서 10 s 안에 메시; 태그는 정확히 네 변; 영역 면적이 `resolve_regions`와 1e-9 mm^2(45도는 1e-8)까지 일치; 최소각 >= 입력 모서리 각과 28도 중 작은 값 - 1e-6 |
| 정확한 원 규칙 | 다른 모든 경계와 떨어지고 안에 뒤 도형이 없는 원만 정확한 원으로 메시 |
| 잘랐을 때 다각형과 선 조각이 되는 오목 도형 | 다각형 부분만 메시, 열수지 <= 1e-10, 전자기 문서의 정확한 원 유지 |
| 사각형 문서 | 비어 있지 않은 `materials`는 여전히 거부, 원래 결과 형식 |
| Studio | 영역 문서는 메시·작업자 호출 전에 거부 |

처음 실행했을 때 관측값(메시 크기 2 → 0.25 mm):

| 양 | 값 | 차수 |
| --- | --- | --- |
| T L2 (K m) | 4.07e-6, 1.03e-6, 2.59e-7, 6.42e-8 | 1.98, 2.00, 2.01 |
| 열유속 L2 (W/m) | 0.478, 0.241, 0.121, 0.0603 | 0.99, 1.00, 1.01 |

복합 원통과 경계면 열유량을 포함한 엔진 수준 영역별 검증은
[multimaterial](../galerkin/multimaterial.md)에 있습니다.

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
(`examples/simcase/transient_thermal_regions.json`)입니다.

결과는 `thermal.transient2d-regions-result-v1`, `thermal2d-transient-p1-node-cell-regions-v1`로
사각형 과도 필드에 정적 `triangle_regions`를 더합니다. 요약에는 `region_names`, `regions`,
`materials`, 메시 크기가 더해집니다. `heat_content_j_per_m`는 영역별 열용량을 쓴 `1^T M T`입니다.
전체 이력을 메모리에 둡니다(O(단계 수 x (절점 + 삼각형))). 아래 수렴 연구의 최대 메모리는 약
825 MiB였습니다.

검증(`tests/simcase/test_transient_thermal_regions.py`):

| 검사 | 기준 |
| --- | --- |
| 모든 영역에서 Q_i = r c_i, 단열 변 | 모든 절점·시각에서 T = T0 + r t(300 K의 1e-10), 열유속 1e-9 W/m^2 미만 |
| 긴 시간 극한(500 s 간격, 1e4 s까지) 대 정상 영역 문서 | 같은 메시, 마지막 온도가 온도 상승의 1e-9 이내 |
| 같은 메시의 `solve_transient_heat` 직접 호출 | 온도·열유속·반력·열량 동일 |
| 균일 300 K에서 가열하는 층상 벽(Q 2e5 / 5e4 W/m^3, 양끝 300 K) 대 `refsol.transient_heat_multilayer.LayeredWall.source_driven`, 메시 크기 4, 2, 1, 0.5 mm, dt = 1/64 s, 20 s 관측 | 마지막 두 구간에서 T L2 차수 >= 1.8, 열유속 L2 차수 >= 0.9; 0.5 mm에서 dt를 절반으로 하면 각 오차 변화 <= 5% |
| 한 재료만 쓴 문서 대 사각형 과도 문서 | 열원 1e-12 일치, 최고 온도 2e-3 K 이내 |
| 저장 필드, CLI, 잘못된 문서 11개(하나는 영역 밖 도형), Studio 거부 | 형식·영역·재료, 종료 코드, `DocumentError`, 작업자·메시 호출 없음 |

수렴 기준의 앞선 두 구성은 후진 Euler의 1차 시간 오차가 공간 오차와 분리되지 않아 실패했습니다.

| 구성 | 관측 | 결과 |
| --- | --- | --- |
| dt = 1/4 s, 180 s까지 | 20, 60, 180 s | 마지막 구간 T 차수 0.62, 0.52, 0.88; dt/2에서 T 오차 43%, 44%, 37% 변화(열유속 차수 0.99-1.00은 통과) |
| dt = 1/64 s, 20 s까지 | 5, 10, 20 s | 마지막 구간 T 차수 1.72, 1.86, 1.92; dt/2에서 T 오차 13%, 7.1%, 4.4% 변화 |

남긴 기준은 두 번째 실행에서 분리 기준을 만족한 유일한 시각인 20 s를 관측하며, 이 시각은 실행을
본 뒤 골랐습니다. 관측값(메시 크기 4 → 0.5 mm): T L2 1.81e-4, 4.75e-5, 1.18e-5, 3.11e-6 K m
(차수 1.93, 2.01, 1.92), 열유속 L2 0.942, 0.477, 0.241, 0.121 W/m(차수 0.98, 0.99, 1.00),
dt/2 변화 4.4%(T)와 3e-8(열유속). 이 해상도에서 더 이른 과도 시각은 위의 정확 재현·엔진 일치
검사와 [multimaterial](../galerkin/multimaterial.md)의
엔진 검증으로만 다룹니다.

## 호출자를 위한 메시 상한

서버처럼 직접 쓰지 않은 문서를 실행하는 호출자는 영역 실행이 메시하는 크기를 풀이 전에 제한할 수
있습니다. `simcase.run`은 선택적인 키워드 전용 상한 세 개를 받습니다.

```python
from simcase import MeshLimitError, check_mesh_limits, run

try:
    result = run(doc, max_input_vertices=2048, max_nodes=10201, max_triangles=20000)
except MeshLimitError as exc:
    print(exc.quantity, exc.count, exc.limit)     # for example: input_vertices 2054 2048
```

- `max_input_vertices`는 기하가 meshine에 넘기는 루프 꼭짓점 수(아래)를 제한합니다. 영역을 조립하는
  동안, meshine이 영역을 만들기 전에 검사합니다.
- `max_nodes`는 meshine에 `max_points`로 넘기므로, 이를 넘는 첫 삽입에서 메시가 멈춥니다(meshine의
  `MeshSizeLimitError`). 메시 후에 정확한 절점 수를 한 번 더 비교합니다.
- `max_triangles`는 메시 후 정확한 삼각형 수와 비교합니다.

모든 검사는 풀이 전에 실행됩니다. 각 상한은 양의 `int` 또는 `None`이며 `None`은 검사하지 않습니다.
상한이 없으면 실행은 상한 없는 실행과 정확히 같고, `max_nodes`를 주지 않으면 meshine은 자체 기본
상한인 300,000점을 유지합니다. 상한은 정상·과도 영역 문서에만 적용됩니다. 사각형 열전도 문서나 전자기,
공진기, 전기·줄 가열 문서에 상한을 주면 `ValueError`이고, `bool`, 부동소수점 수, 1보다 작은 값도
마찬가지입니다. 두 열전도 종류는 어떤 문서가 상한을 받는지 물리 등록표(`PhysicsKind.accepts_mesh_limits`)에
선언하고, `run`은 이를 통해 그 실행기에 상한을 넘깁니다. 다른 종류의 실행기는 바뀌지 않습니다.
`max_nodes`에는 `MeshSizeLimitError`가 있는 meshine이 필요합니다. 더 오래된 meshine이 설치되어 있으면 이
상한을 준 실행은 `ImportError`를 발생시키고, 다른 실행은 그대로입니다.

메시 전 작업을 제한하는 것은 `max_input_vertices`뿐입니다. `max_nodes`와 `max_triangles`는 meshine이
영역을 만든 뒤에 작동하는데, 영역 만들기는 모든 루프 꼭짓점을 앞선 모든 꼭짓점과 비교하므로 O(V²)이고,
고립된 원은 그보다 먼저 꼭짓점을 만들거나 0에 가까운 `mesh.size`에서는 만드는 중에 실패합니다.
`max_input_vertices` 없이 영역 크기를 2 mm로 두고 전역 `mesh.size`를 0.004로 한 정상 예제는 `max_nodes`
10,201이 수십 초 뒤에야 거절하고(Linux에서 두 번 측정해 28 s와 45 s), 5e-324에서는 상한이 없을 때처럼
`OverflowError`로 끝납니다. 다른 사람이 쓴 문서에는 `max_input_vertices`도 주세요.

**루프 꼭짓점.** 루프 꼭짓점은 도형의 불리언 연산 후 meshine의 `Domain.add_region`에 넘기는 루프의
항목 하나이며, 바깥 경계와 구멍을 똑같이 셉니다.

- 배경 안의 도형은 자기 경계로 한 번, 배경의 구멍으로 한 번, 두 번 셉니다.
- 나중 도형이 앞 도형을 여러 조각으로 자를 수 있고, 조각마다 루프가 따로 있습니다. 각각 255점인 두
  빗 모양 다각형이 서로 가로지르면 32,776입니다.
- 다른 경계가 닿거나 가로지르는 원, 또는 나중 도형과 겹치는 원은 128각형입니다.
- 정확한 meshine `Circle`로 메시하는 고립된 원은 자기 `mesh_size`가 있어도 **전역** `mesh.size`로
  max(16, int(4πr / `mesh.size`))개를 세고, 둘러싼 영역의 구멍으로 한 번 더 셉니다. 배포된 정상 예제는
  `mesh.size` 0.0246에서 루프 꼭짓점이 2054개이고, 그중 2042개가 히터입니다.

이 수는 meshine 자체의 T자 접합 분할 전에 세므로, meshine이 처리하는 루프는 더 길 수 있습니다.
이 수는 실제로 메시하는 것, 곧 문서의 마이크로미터 사본(메시와 풀이 참고)의 수입니다. 도형의 불리언
연산과 원 규칙은 단위에 의존하지 않으므로 보통 문서 자체의 숫자로 센 수와 같고, 시험이 쓰는 밀리미터
문서 22개에서도 같습니다. 4πr / `mesh.size`가 정수에서 반올림 오차 이내에 있으면 다를 수 있습니다.
영역 크기를 2 mm로 둔 정상 예제는 `mesh.size` 4π·2/20 mm에서 밀리미터로는 루프 꼭짓점이 52개,
메시하는 마이크로미터 사본에서는 50개이며, 세는 수는 50입니다.
`check_mesh_limits(doc, *, max_input_vertices)`는 영역 문서의 이 수를 영역을 만들거나 문서를
바꾸지 않고 반환하거나, `MeshLimitError`를 발생시킵니다. 실행처럼 마이크로미터 사본을 검증하므로 도형의
불리언 연산을 그 검증에서 한 번, 수를 세며 한 번, 두 번 계산합니다. 검증하지 않은 `Document`
(`Document(data)`, `Document.copy()`)에는 아직 해석된 길이 단위가 없으므로, 그 실행이 먼저 검증하듯
검증한 사본으로 세며 불리언 연산을 한 번 더 계산합니다. 자기 수만으로 상한을 넘는 고립된 원은
꼭짓점을 만들기 전에 거절하고 메시지에 그 수의 추정값을(마이크로미터로) 적으므로, `max_input_vertices`를
주면 0에 가까운 `mesh.size`(5e-324)는 나눗셈, 오버플로, 메모리 오류가 아니라 `MeshLimitError`를
발생시킵니다.

**`MeshLimitError`**는 `DocumentError`가 아닌 `ValueError`입니다. 문서는 유효하고, 호출자의 상한이
거절하는 것입니다. `quantity`는 `'input_vertices'`, `'nodes'`, `'triangles'` 중 하나이고, `limit`은
상한, `count`는 정확한 수입니다. 메시가 `max_nodes` 상한에서 멈췄거나 고립된 원 하나만으로
`max_input_vertices`를 넘으면 `count`는 `None`입니다. 메시지는 양, 수, 상한을 명시합니다.

`tests/simcase/test_region_mesh_limits.py`는 변경 전에 정한 기준으로 이를 검사하며, 절점 수와 삼각형
수는 저장하지 않고 시험 안에서 측정합니다. 두 예제의 정확한 절점, 삼각형, 루프 꼭짓점 수를 상한으로
주면 상한 없는 실행과 같은 저장 배열과 요약이 나오고, 하나 적으면 풀이기를 호출하기 전에 거절합니다.
각 상한은 혼자서도 동작하고, 영역이 없는 문서와 잘못된 값은 거절하며, 22개 문서에서 이 수는
meshine이 받는 루프 길이의 합과 같습니다. 상한을 마이크로미터 사본과 물리 등록표로 옮길 때 더한 시험은
미리 정한 기준이 아니며, 이 수가 mm, nm, m 문서와 위에서 단위가 수를 바꾸는 문서에서 각 실행이
meshine에 넘기는 영역의 수와 같은지, 검증하지 않은 문서가 그 실행의 수를 받는지, 상한을 받는 종류만
상한을 받는지 검사합니다.

## 한계

- Studio는 정상·과도 영역 문서를 거부합니다(열 화면이 `mesh.subdivisions`를 읽음). CLI나 Python API를
  쓰십시오.
- 구간 상수 등방 물성, 경계면 완전 접촉.
- 다른 경계에 닿거나 얕게 가로지르는 원, 뾰족한 다각형 꼭짓점 옆의 삼각형은 어느 영역에서든 입력
  모서리만큼, 또는 조금 더 날카로울 수 있습니다(14° 다각형 모서리 옆에서 13.0° 측정). meshine이
  해결하지 못하는 입력은 오류로 끝납니다(메시와 풀이 참고).
- 단위 깊이 평면 기하. 내장 재료의 열 물성 없음.

### 길이 정규화 회귀

`tests/simcase/test_thermal_length_canonical.py`는 원점이 이동된 영역에 직사각형·고립 원·다각형,
배경·도형별 메시 크기를 넣고 mm, m, um, nm 및 사용자 정의 `in_m` 단위를 비교합니다.
정상 열유속·대류 하중과 과도 affine 초기장을 통해 두 풀이 경로를 검사합니다. 모든 수치 저장
배열·영역/재료 배정·경계 태그가 정확히 같아야 하며 원문 모델과 선언 단위를 보존해야 합니다.
기존 층상 벽 해석해 수렴 시험도 계속 필수입니다.

## VTU와 PVD 내보내기

`simcase[export]`(meshio, MIT)를 설치하면 저장한 영역 결과를 ParaView에서 볼 수 있습니다.
`export_fields(fields_npz, output, *, time_index=-1)`는
`thermal2d-p1-node-cell-regions-v1` 및
`thermal2d-transient-p1-node-cell-regions-v1`을 받습니다.
`export_time_series(fields_npz, output_dir, *, name="fields")`는 과도 배치를 받아
저장된 시각마다 VTU를 만들고 정확한 `time_s`(초)를 기록한 PVD 컬렉션으로 연결합니다.
두 함수 모두 솔버를 다시 실행하거나 저장 결과를 바꾸지 않습니다.

```python
from simcase import Document, run
from simcase.export import export_fields, export_time_series

# Run from the repository root, with new output paths.
steady = run(Document.load("examples/simcase/thermal_regions.json"), verbose=False)
steady_dir = steady.save("out/region-steady")
export_fields(steady_dir / "fields.npz", "out/region-steady/view.vtu")
transient = run(Document.load("examples/simcase/transient_thermal_regions.json"), verbose=False)
transient_dir = transient.save("out/region-transient")
export_fields(transient_dir / "fields.npz", "out/region-transient/initial.vtu", time_index=0)
export_time_series(transient_dir / "fields.npz", "out/region-transient/paraview")
```

ParaView에서 `view.vtu` 또는 `paraview/fields.pvd`를 엽니다. **셀** 배열
`triangle_regions`로 색을 지정하면 같은 재료를 쓰는 영역도 구분할 수 있고,
`temperature_k`로 색을 지정하면 절점 온도를 봅니다. ID는 원래
`summary.json["region_names"]`의 0부터 시작하는 인덱스이며,
`summary.json["regions"][name]["material"]`이 재료를 가리킵니다. 같은 summary가 NPZ
메타데이터에도 있습니다. 이름·물성·경계 태그는 VTU에 복사하지 않으므로 의미를 확인하려면
원래 NPZ/summary를 보관하십시오.

| VTU 위치 | 배열과 단위 |
|---|---|
| 점 좌표 | `nodes_m`, z = 0으로 확장; 문서 길이 단위와 무관하게 m |
| 점 데이터 | `temperature_k`(K); 저장된 절점 하중·반력·잔차·저장률(단위 깊이당 W/m) |
| 셀 데이터 | `heat_flux_w_m2`(W/m², z 성분 0); `triangle_regions`(무차원 정수) |

정상 영역 내보내기는 `load_w_per_m`, `reaction_w_per_m`, `residual_w_per_m`,
`prescribed_outward_load_w_per_m`, `ambient_load_w_per_m`, `convective_outward_w_per_m`,
`system_rhs_w_per_m`을 포함합니다. flux/Robin 부호 및 바깥 변 경계조건은 위 설명과 같습니다.
과도 내보내기는 `source_load_w_per_m`을 포함하며 반력·잔차·저장률은 두 번째 저장 시각부터만
존재합니다. 초기 시각의 율을 만들어 넣지 않습니다. 열함량 같은 영역 전체 이력, 경계 절점
부분집합, 이름·단위는 NPZ/summary에 남습니다. 점/셀 보간이나 영역 번호 변경은 없습니다.

기존 VTU는 거부하고 시계열 폴더는 새것이거나 비어 있어야 합니다. 시계열 쓰기에 실패하면
이번 호출이 만든 파일을 정리합니다. `triangle_regions`가 없거나 정수가 아니거나 음수이거나
크기가 맞지 않으면 출력 생성 전에 거부합니다. 유효한 `save()` 결과를 위한 내보내기이며
임의 NPZ의 전체 검증기는 아닙니다. restart·XDMF·과도 flux/Robin 입력 및 별도 직사각형
정상 `boundary-v2` 배치는 지원하지 않습니다.

`tests/simcase/test_export_regions.py`는 내보낸 모든 배열과 NPZ, 모든 저장 시각, 초기율
부재, 재료 ID와 구별되는 영역 ID, 기존 출력 보호와 실패 정리를 검증합니다. 같은 수치 환경에서
위 길이 정규화 조건을 충족하는 mm/m/um/nm/사용자 단위 문제는 정확히 같은 SI 내보내기
배열을 내야 합니다. 이 소비자 시험은 Linux·macOS·Windows 설치 휠에서도 실행합니다.
