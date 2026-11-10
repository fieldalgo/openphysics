# 직육면체 공진기 문서와 결과

[English](../../../../../packages/simcase/cavity3d.md)

`em.cavity3d` 문서는 직육면체 study 하나를 담습니다. 먼저 설명하는 경우는 여섯 면에
모두 완전 전기 도체(PEC) 조건을 적용한 진공 상자입니다. [재료와 도체 벽](#재료와-도체-벽)은
축 정렬 직육면체 안의 일정하고 손실이 있을 수 있는 재료, 채워진 배경, 유한 전도도 벽을
더합니다. 엔진 통합 검사는 CLI 실행, 단위 변환, 저장된 장 복원을 다루며, 엔진의 수치
수렴 수용 검사와는 별개입니다.

## 입력

예제는 `examples/simcase/cavity_box.json`이며 `python -m simcase example cavity_box`로도
얻을 수 있습니다. headless 실행 흐름은 다음과 같습니다.

```bash
python -m simcase example cavity_box > cavity.json
python -m simcase validate cavity.json
python -m simcase run cavity.json -o cavity_results
```

문서는 [형식 0.3](document_format.md)입니다. 모든 값이 단위를 함께 적고(`"250 MHz"`,
`"58 MS/m"`) 키는 레지스트리 물리량 이름입니다. 형식 0.2 공진기 문서는 이름을 밝혀
거부합니다(`E-FORMAT`). 0.2의 `units` 블록, `target_frequency_hz`, `num_modes`,
`conductivity_s_per_m`, `mesh.subdivisions`는 알 수 없는 키이며 메시지가 새 키를 알려 줍니다.
`geometry.length_unit`은 `"m"`여도 반드시 적습니다(메뉴 `pm nm Angstrom um mm cm m in mil`).
`geometry.domain`의 여섯 경계 `xmin`, `xmax`, `ymin`, `ymax`, `zmin`, `zmax`는 그 단위의 일반
숫자입니다. 각 값은 정수 피코미터 격자에 한 번 놓이고, 각 최댓값은 최솟값보다 커야 하며
원점이 0이 아니어도 됩니다. 3D domain에는 `depth`가 없습니다(`E-KEY-UNKNOWN`). 진공 PEC
경우에는 `geometry.background`가 `{"material": "physmat:vacuum"}`(필수이며, 없으면
`E-KEY-MISSING`)이고 `geometry.shapes`와 `materials`는 비어 있습니다. 상자만 담은
[버전 1](geometry_document.md) `3d` component는 이 평면 블록으로 읽습니다.
직육면체 재료, 채워진 배경, 유한 전도도 벽은 [재료와 도체 벽](#재료와-도체-벽)에서 설명합니다.
임의 형상과 다른 경계 종류는 지원하지 않습니다.

이름이 있는 physics 항목이 정확히 하나여야 합니다.

```json
{
  "physics": {
    "em1": {
      "type": "em.cavity3d",
      "boundary": "pec",
      "search": "near_target",
      "target_frequency": "250 MHz",
      "mode_count": 5
    }
  },
  "mesh": {"subdivision_count": [6, 6, 6]},
  "study": {"type": "single"},
  "results": {"save_fields": true, "plots": false}
}
```

| 키 | 값 |
|---|---|
| `type`, `search` | `"em.cavity3d"`, `"near_target"`(둘 다 필수) |
| `target_frequency` | 필수, > 0(메뉴 `Hz kHz MHz GHz THz`; `"250 mHz"`는 밀리헤르츠라서 거부하고, 단위 없는 숫자는 `E-UNIT-MISSING`) |
| `mode_count` | 필수, 1 이상인 JSON 정수(`2.0`과 불리언은 거부) |
| `boundary` | 필수: `"pec"` 또는 `{"electrical_conductivity": ...}`([도체 벽](#재료와-도체-벽)) |
| `mesh.subdivision_count` | 필수, 양의 정수 `[nx, ny, nz]` |

구조화 메시에는 `6 * nx * ny * nz`개의 사면체가 있습니다. `mesh.element_size`,
`minimum_angle`, grading, 파장, 2D formulation, sweep, 알 수 없는 cavity 설정은 거부하므로
지원하지 않는 요청이 문제를 조용히 바꾸지 않습니다. 공진기에는 단위를 단 길이가 없으므로
규모 검사는 `W-CAVITY-SCALE`입니다. domain의 가장 긴 변에 `target_frequency / c`를 곱한 값이
0.1~100 밖이면 경고합니다(예제의 1 m 정육면체와 250 MHz는 0.834, 같은 숫자를 `mm`로
선언하면 8.3e-4). 이 값은 `validate`와 log의 `extent` 줄에 나옵니다.

기본값은 빈 `materials`, single study, `save_fields=true`, `plots=false`인 `results`만
제공하며 각각 `defaults_applied`에 기록합니다. cavity 입력은 2D의 파장·mesh-size·formulation
기본값을 상속하지 않습니다. Plotting과 Studio 3D 렌더러는 제공하지 않으며 명시적인
`plots=true`는 거부합니다. Studio는 이 예제를 목록에 넣지 않고 cavity mesh/run 요청을
거절합니다. `build_mesh`와 `solve_point`는 2D 단계로 유지되며 cavity 진입점은 `run`입니다.

## 검색과 실패 의미

요청한 모드는 지정한 목표 부근에서 찾은 양의 Maxwell 모드입니다. 엔진 계약은
주파수 제곱의 거리(진공 파수 제곱의 거리와 동치)로 후보를 순위화하고, 선택한
모드를 주파수 오름차순으로 반환합니다. 이는 유한한 후보 검색이며 최저 모드들이나
완전한 스펙트럼 구간을 보장하지 않습니다. 특히 기본 주파수보다 훨씬 높은 목표는
그 아래의 모든 모드를 요청한다는 뜻이 아닙니다.

영모드·gradient 모드는 제외합니다. 축퇴 고유벡터는 주파수 중복 제거 없이 별도
모드로 유지하며 `mode_count`는 서로 다른 주파수 값이 아니라 벡터 수를 셉니다.
요청 개수 때문에 축퇴 cluster가 잘릴 수 있습니다. 축퇴 부분공간 안의 개별 벡터와
그 부호는 안정적인 label이 아닙니다. 메시 세분화가 연속체의 축퇴를 갈라놓을 수도
있습니다. 정확한 주파수 일치를 고유한 모드 식별로 가정하지 말고 cluster 중복도와
수렴을 확인해야 합니다.

잘못된 문서는 코드와 경로를 밝혀 검증에 실패합니다. Solver 비수렴, 양의 후보 부족,
수치 잔차 검사 실패는 부분 성공 결과를 쓰는 대신 실행을 실패시켜야 합니다. CLI 문서
오류는 종료 코드 2, solver 오류는 1입니다. 해석 실패 시 출력 디렉터리를 만들지 않습니다.

## 결과 파일과 배열 단위

`run(doc)`가 성공하면 2D `RunResult`와 구별되는 `CavityRunResult`를 반환합니다.
`result.resonant_frequency`는 Hz 단위 주파수 벡터이고,
`result.mass_normalized_electric_field`와
`result.mass_normalized_electric_field_line_integral`은 저장되는 장이며,
`result.cavity`에는 galerkin 결과(솔버 자체 규약)가 들어 있습니다.
`result.save(directory)`는 다음 파일을 씁니다.

- `model.json`: 작성한 문서(파일에서 읽었다면 그 바이트 그대로).
- `summary.json`: `{"value", "unit"}` 객체와 단위 배열(`{"unit", "values"}`)로 쓴 결과, 메시
  개수, 검색 목표와 모드 수, 공통 블록 `diagnostics`, `defaults_applied`, `resolved_inputs`,
  `extent`, `timing.wall_time.mesh_and_solve`(초).
- `log.txt`: extent 줄, 문서 요약, 주파수, 모든 진단.
- `fields.npz`: `save_fields=true`인 경우에만 아래 배열과 `metadata_json`(summary의 메타데이터를
  담은 JSON 문자열)을 저장하며 `numpy.load(path, allow_pickle=False)`로 읽을 수 있습니다.

`results.png`는 없습니다. CLI는 results 설정으로 활성화한 파일 이름만 출력합니다.
**모든 cavity 결과 좌표와 차원이 있는 배열은 SI**이며, `field_units`, `field_locations`,
`field_shapes`, `field_components`가 각 배열의 단위, 위치, 형태, 성분을 밝힙니다. 단위 접미사가
붙은 키나 `*_unit` 키는 없습니다.

| NPZ 키 | Shape | 의미 / 단위 |
| --- | --- | --- |
| `node_coordinates` | `(N, 3)` | 문서 원점을 포함한 좌표, m |
| `tetrahedra` | `(T, 4)` | 0부터 시작하는 절점 인덱스 |
| `edges` | `(E, 2)` | 작은 절점 인덱스에서 큰 인덱스로 향하는 전역 에지 |
| `tet_edges` | `(T, 6)` | 지역 에지의 전역 에지 인덱스 |
| `edge_signs` | `(T, 6)` | 지역·전역 에지 방향 사이의 부호 |
| `pec_edge_ids` | `(P,)` | `edges`에서 구속한 에지의 인덱스 |
| `resonant_frequency` | `(K,)` | 공진 주파수, Hz |
| `wavenumber_squared` | `(K,)` | 진공 파수 제곱, 1/m^2 |
| `relative_residual` | `(K,)` | 무차원 대수 잔차 |
| `mass_normalized_electric_field_line_integral` | `(E, K)` | SI 질량 정규화된 에지 적분, 1/m^(1/2) |
| `mass_normalized_electric_field` | `(K, T, 3)` | 사면체 중심의 전기장, 1/m^(3/2) |

배열과 함께 문자열 스칼라를 저장합니다. field layout `cavity3d-edge-v2`, 정규화
`electric_mass_orthonormal_si`, `search`, `edge_orientation="low_node_index_to_high_node_index"`,
`electric_field_location="tetrahedron_centroid"`,
`cluster_completeness="not_certified"`,
`mode_count_policy="exact_count_may_split_cluster"`입니다. 목표(`target_frequency`, Hz)와
모드 수(`mode_count`, `returned_mode_count`)는 summary와 `metadata_json`에 있습니다.
지역 에지 6개는 galerkin의 사면체 순서 `(0,1)`, `(0,2)`, `(0,3)`, `(1,2)`,
`(1,3)`, `(2,3)`를 따릅니다. 부호는 이 지역 방향을 저장된 전역 방향으로 대응시킵니다.
Cavity 출력에는 유효 굴절률이나 삼각형·절점 스칼라 배열이 없습니다. 단위·이름 일괄 변경
이전에 저장한 결과(`cavity3d-edge-v1`, `cavity3d-edge-complex-v1`)는 `simcase.export`가
이름을 밝혀 거부합니다. 문서를 다시 실행하세요.

정규화는 진공 전기 질량 행렬에 대해 `q.T @ M_SI @ q = I`입니다. 따라서 장의
진폭은 임의 정규화 값이며 **V/m가 아닙니다**(summary의 `amplitude`가 이를 밝힙니다).
원시 에지 적분과 중심 장은 서로 다른 배열이며 단위도 다릅니다. 어느 쪽도 절점값으로
해석하면 안 됩니다. 잔차는 PEC로 축소한 일반화 고유문제의 자유 에지에 대해
`||S q - lambda M q||_2 / (||S q||_2 + |lambda| ||M q||_2)`이며 실패 한계는
`1e-8`입니다. 선택한 모드의 질량 직교성 최대 절대 오차는 `1e-7` 이하여야 합니다.
작은 수치 kernel 고유값은 정규화된 직육면체 좌표의 해석적 기본 파수 제곱에 대한
`1e-8` 배 기준으로 걸러내며, 이 기준은 목표 주파수와 독립적입니다.

각 cavity 실행은 새 출력 디렉터리를 사용합니다. 파일을 쓰기 전에 `save()`는
`summary.json`, `model.json`, `log.txt`, `fields.npz`, `results.png` 중 하나라도
포함된 디렉터리를 거절합니다. 그 이름에 디렉터리나 끊어진 symlink가 있는 경우도
포함합니다. `FileExistsError`를 발생시키며 CLI는 오류를 보고하고 종료 코드 1을
반환합니다. 기본 `<model>_results` 경로에도 적용되므로 반복 실행에는
`-o another_directory`를 사용합니다. 기존 결과와 무관한 사용자 파일은 보존합니다.
무관한 파일만 들어 있는 디렉터리는 허용합니다. 같은 디렉터리에 동시에 실행하지 마세요.

`save_fields=false`이면 NPZ 파일 전체를 생략합니다. 이때도 `summary.json`에는
주파수, 파수, 잔차, 정규화, SI 단위, 목표, 두 개수, cluster/count 정책 두 필드가 남습니다.

형상 숫자는 어떤 `length_unit`에서도 같은 상자를 뜻합니다. 미터 단위 정육면체를 `"mm"`에서
최댓값 `1000`으로 적으면 피코미터 경계가 같으므로 솔버가 같은 double을 받고 저장 결과도
비트 단위로 같습니다. 목표를 유지한 채 물리적 크기를 바꾸면 스펙트럼뿐 아니라 검색 문제도
바뀝니다. 기하학적으로 닮은 모드 집합을 비교할 때에는 크기에 반비례하도록 목표를 조정합니다.

## 재료와 도체 벽

같은 `em.cavity3d` study는 축 정렬 직육면체 안의 일정하고 등방적인(손실이 있을 수 있는)
재료와 유한 전도도 벽을 받습니다. 이런 문서는 `galerkin.solve_material_cavity_box`를
실행하고 아래 복소 배치로 저장합니다. 배경이 `physmat:vacuum`이고 shape가 없으며
`"boundary": "pec"`인 문서는 원래 솔버와 위의 진공 배치를 그대로 씁니다. 예제는
`examples/simcase/cavity_lossy_slab.json`(`python -m simcase example cavity_lossy_slab`)입니다.

```json
{
  "geometry": {
    "length_unit": "m",
    "domain": {"xmin": 0, "xmax": 1, "ymin": 0, "ymax": 0.8, "zmin": 0, "zmax": 0.6},
    "background": {"material": "physmat:vacuum"},
    "shapes": [{"type": "box", "name": "slab", "material": "lossy_dielectric",
                "xmin": 0, "xmax": 1, "ymin": 0, "ymax": 0.8, "zmin": 0, "zmax": 0.3}]
  },
  "materials": {"lossy_dielectric": {"relative_permittivity": {"re": 4.0, "im": 0.04}}},
  "physics": {"em1": {"type": "em.cavity3d",
                      "boundary": {"electrical_conductivity": "58 MS/m"},
                      "search": "near_target", "target_frequency": "150 MHz",
                      "mode_count": 3}},
  "mesh": {"subdivision_count": [8, 8, 8]}
}
```

**시간 규약**은 형식 0.3 문서와 결과의 모든 복소값과 같은 `exp(-i omega t)`입니다. 복소
상수는 숫자 하나 또는 `{"re": .., "im": ..}`이며 `re > 0`, `im >= 0`이어야 합니다. 양의
허수부가 손실이고, 손실 탄젠트 `t`인 유전체는 `{"re": eps', "im": eps' * t}`입니다. 음의
허수부는 이득이므로 거부합니다(`E-GAIN`. 메시지는 exp(+j omega t)로 적은 값을 바꾸는 법,
즉 허수부의 부호를 바꾸라고 알려 줍니다). 형식 0.2의 `[re, im]` 쌍은 `{"re": re, "im": -im}`이며
쌍 자체는 거부합니다(`E-VALUE-FORM`). 공진기 솔버는 수동 매질만 다루므로 `allow_gain`은
이름을 밝혀 거부합니다.

- `materials.<이름>`: `relative_permittivity`(필수)와 `relative_permeability`(기본 1,
  `defaults_applied`에 기록). 다른 형식 0.3 문서와 같이 레코드의 다른 레지스트리 물성
  (예: `refractive_index`)은 검사한 뒤 읽지 않는다고 보고합니다(`I-UNUSED-PROPERTY`).
  `loss_tangent`는 거부하고, 0.2 키 `n`, `k`, `sellmeier`는 알 수 없는 키입니다. 지역 재료의
  이름을 `vacuum`으로 지을 수 있지만 평범한 레코드일 뿐이므로(라이브러리 진공은
  `physmat:vacuum`) 다른 이름이 더 분명합니다.
- `geometry.background.material`: `"physmat:vacuum"` 또는 상자 전체를 채우는 지역 재료.
  다른 라이브러리 이름은 거부합니다(`E-CONTRACT`: 공진기는 일정한 `relative_permittivity`만 받습니다).
- `geometry.shapes`: `length_unit`과 문서 좌표계의 상자
  `{"type": "box", "name", "material", "xmin", ..., "zmax"}`이며 각각 지역 재료를 씁니다
  (`physmat:vacuum`은 배경 전용). 이름은 서로 달라야 합니다. 각 상자는 domain 안에 있어야 하고,
  모든 면은 mesh 격자 평면, 즉 domain 최솟값에서 `extent / subdivisions`의 배수에 있어야 합니다
  (한 cell의 상대 허용치 `1e-9`, 피코미터 값으로 평가). 아니면 검증이 실패하며 간격을 알려 줍니다.
  뒤의 상자가 앞의 상자보다 우선하고, 각 사면체는 무게중심의 재료를 가집니다.
- `physics.<이름>.boundary`: `"pec"`, 여섯 벽 모두에 대한 `{"electrical_conductivity": "58 MS/m"}`,
  또는 키 `xmin, xmax, ymin, ymax, zmin, zmax`를 쓰는
  `{"electrical_conductivity": {"zmax": "58 MS/m", ...}}`. 지정하지 않은 벽은 PEC입니다(메뉴
  `S/m kS/m MS/m S/cm`; 값은 > 0). 벽은 Leontovich 표면 임피던스를 쓰며 각 모드를 고정점
  반복으로 수렴시킵니다.

수치 방법, 기준, 검증은 엔진의
[재료 공진기 계약](../galerkin/material_cavity.md)에 있습니다. 엔진은 exp(+j omega t)로
계산합니다. simcase는 경계에서 각 복소값을 한 번 켤레로 바꾸므로(들어가는 재료 값과 나오는
결과) 솔버는 단위 일괄 변경 이전과 같은 double을 받고, 저장되는 복소 배열은 모두 엔진 값의
켤레입니다.

### 복소 결과

이런 study의 `result.resonant_frequency`는 복소수이며 감쇠하는 모드는 `Im f < 0`입니다.
`summary.json`에는 최상위 `time_convention: "exp(-i omega t)"`가 있고, 모든 복소 항목은
`{"re": [...], "im": [...], "unit", "time_convention"}`입니다.

- `resonant_frequency`(Hz)와 `wavenumber_squared`(1/m^2), 복소수;
- `quality_factor`, 즉 `Q = Re f / (-2 Im f)`(손실이 있으면 `> 0`). 무손실 모드는 `null`;
- `relative_residual`과 `iteration_count`(모드별 고정점 반복 횟수);
- `lossless`, 문서의 `boundary`, `background`, `materials`(복소값은 복소 객체);
- 문서 벽 이름별 `electrical_conductivity`(`{"value", "unit": "S/m"}`, PEC는 `null`).

`fields.npz`는 `field_layout="cavity3d-edge-complex-v2"`를 씁니다. 진공 배치의 mesh·위상·방향
키와 문자열 스칼라를 유지하고, 다음 키를 더하거나 바꿉니다.

| NPZ 키 | 형태 | 의미 / 단위 |
|---|---|---|
| `resonant_frequency` | `(K,)` 복소수 | 복소 주파수, Hz |
| `wavenumber_squared` | `(K,)` 복소수 | `k0^2`, 1/m^2 |
| `quality_factor` | `(K,)` | 무차원; 무손실이면 `inf` |
| `mass_normalized_electric_field_line_integral` | `(E, K)` 복소수 | 1/m^(1/2) |
| `mass_normalized_electric_field` | `(K, T, 3)` 복소수 | 무게중심, 1/m^(3/2) |
| `relative_permittivity`, `relative_permeability` | `(T,)` 복소수 | 사면체별 재료 |
| `wall_names`, `electrical_conductivity` | `(6,)` | `xmin..zmax`; S/m, PEC는 `nan` |
| `iteration_count` | `(K,)` | 횟수 |

여기서 `pec_edge_ids`는 PEC 벽의 에지만 나열하며, 도체 벽의 에지는 미지수입니다. 정규화는
`vacuum_mass_hermitian_unit_si`입니다. 진공 에지 질량 `M0`로 `q^H M0 q = 1`이고, 각 모드에서
크기가 가장 큰 계수는 양의 실수입니다. 진폭은 임의이며 **V/m가 아닙니다**. 배열은
`numpy.load(path, allow_pickle=False)`로 읽습니다. `simcase.export.export_fields`는 이 배치를
VTU로 쓸 때 복소 모드마다 셀 데이터 `mass_normalized_electric_field_mode_<k>_real`과
`..._imag`(같은 정규화와 `exp(-i omega t)` 규약이므로
`real*cos(omega*t) + imag*sin(omega*t)`가 순시 장)를, 재료 배열은 `_real`/`_imag` 쌍으로
씁니다. VTU FieldData 블록이 각 배열의 단위와 시간 규약을 밝힙니다.
[ParaView로 보기](overview.md#paraview로-보기)를 참고하세요.

`tests/simcase/test_cavity3d_materials.py`의 시험이 확인하는 것:

- 각 필드의 검증과 각 거부의 코드·경로;
- 문서 실행이 엔진 직접 호출과 같고 공개 값이 그 켤레임;
- 원점을 옮긴 mm 문서가 같은 SI 결과를 냄;
- 단일 벽이 엔진 벽과 PEC 에지에 대응됨;
- 채운 배경이 진공 스펙트럼을 비유전율로 나눈 값과 같음;
- 복소 NPZ·JSON 출력이 pickle 없이 읽힘;
- 무손실 study의 Q가 `null`임;
- 진공 PEC 문서가 원래 솔버를 씀;
- 이름이 `vacuum`인 지역 재료가 평범한 레코드임;
- CLI 실행, 엔진 API 누락, Studio 거부.

`tests/simcase/test_units_cavity.py`는 이 종류의 단위·이름 규칙을 확인합니다. 같은 값을 어떤
단위 표기나 `length_unit`으로 적어도 솔버 입력과 저장 배열이 같고, `W-CAVITY-SCALE`, 거부의
코드와 경로, 모든 출력의 진단, 결과 이름과 단위, 복소 규약, 내보내기를 검사합니다.

Studio는 이 study를 나열하거나 실행하지 않습니다. 그림 출력은 여전히 지원하지 않습니다.

## 통합 검증과 수치적 한계

Cavity를 지원하는 galerkin 구현이 있는 저장소 루트에서 실행합니다.

```bash
python -m pytest -q tests/simcase/test_cavity3d_integration.py
```

통합 사례 7개는 simcase revision `ba1c8a7`과 galerkin revision `a660233` 조합에서
통과했습니다. 이전에는 `cd4071a`와 `3b850a8` 조합에서도 통과했습니다. 이는 해당
revision과 그때의 형식 0.2 문서에 대한 과거 검증 기록입니다. 사례는 평행 이동한 정육면체,
처음 두 개의 완전한 reference cluster에 대한 기준 주파수 smoke 검사, m/mm/um/nm 표현,
fields 유무에 따른 실제 CLI 실행, `allow_pickle=False`로 읽은 NPZ 복원을 다룹니다. 재조립한
위상 정보, 중심 장, PEC 계수, 자유 에지 잔차, 질량 직교성을 검사합니다. 성긴 메시의
기준 주파수 검사는 메시 수렴 수용 gate가 아닙니다. 단위 일괄 변경 이후 같은 사례는 형식
0.3 문서를 읽고, m/mm/um/nm 표현을 비트 단위로 비교합니다.

이전 galerkin revision `3b850a8`에서는 고정 직육면체 111-cluster 평균 수렴 gate가
실패했습니다. 마지막 관측 차수는 약 1.2284로 요구값 1.8보다 낮았습니다.
Revision `a660233`은 반사 방향을 균형 있게 하는 cavity 메시로 바꿨으며 제품 통합
사례도 이 메시에서 통과했습니다. 문서 실행과 파일 복원이 메시 수렴이나 전체 기능
수용을 독립적으로 인증하는 것은 아닙니다. 수치 검증 근거는
[엔진 검증 기록](https://github.com/fieldalgo/openphysics/blob/2efbc413df5d3d36bcc4c9879b34ed88213b9217/packages/galerkin/docs/cavity_solver.md)을 확인하세요.
