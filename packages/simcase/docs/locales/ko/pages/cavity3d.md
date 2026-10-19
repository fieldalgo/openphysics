# 직육면체 공진기 문서와 결과

[English](../../../cavity3d.md)

제품 계약은 하나의 `em.cavity3d` study를 지원합니다. 진공 직육면체의 여섯 면에
모두 완전 전기 도체(PEC) 조건을 적용합니다. 공개 API 계약은 아래와 같습니다.
실제 엔진 통합 검사는 CLI 실행, 단위 변환, 저장된 장 복원을 다루며, 엔진의 수치
수렴 수용 검사와는 별개입니다.

## 입력

예제는 `examples/cavity_box.json`이며 `python -m simcase example cavity_box`로도
얻을 수 있습니다. 의도한 headless 실행 흐름은 다음과 같습니다.

```bash
python -m simcase example cavity_box > cavity.json
python -m simcase validate cavity.json
# Requires the matching galerkin cavity API:
python -m simcase run cavity.json -o cavity_results
```

입력은 `"openphysics": "0.2"`를 유지합니다. 단위가 `"m"`여도 `units.length`를
명시적으로 선언합니다. `geometry.domain`의 여섯 좌표 `xmin`, `xmax`, `ymin`,
`ymax`, `zmin`, `zmax`는 선언한 길이 단위를 사용합니다. 각 최댓값은 최솟값보다
커야 하며 원점이 0이 아니어도 됩니다. `geometry.background`는
`{"material": "vacuum"}`, `geometry.shapes`와 `materials`는 비어 있어야 합니다.
직육면체 재료, 채워진 배경, 유한 전도도 벽은 [재료와 도체 벽](#재료와-도체-벽)에서 설명합니다. 임의 형상과 다른 경계 종류는 지원하지 않습니다.

이름이 있는 physics 항목이 정확히 하나여야 합니다.

```json
{
  "physics": {
    "em1": {
      "type": "em.cavity3d",
      "boundary": "pec",
      "search": "near_target",
      "target_frequency_hz": 250000000.0,
      "num_modes": 5
    }
  },
  "mesh": {"subdivisions": [6, 6, 6]},
  "study": {"type": "single"},
  "results": {"save_fields": true, "plots": false}
}
```

physics 필드 다섯 개를 모두 명시합니다. 목표 주파수는 `units.time`과 관계없이
항상 Hz이며 `_hz` 접미사는 고정 SI 필드입니다. 분할수와 모드 수는 양의 정수여야
하며 불리언은 거절합니다. 구조화 메시에는 `6 * nx * ny * nz`개의 사면체가 있습니다.
`mesh.size`, grading, 파장, 2D formulation, sweep, 알 수 없는 cavity 설정은
거절하므로 지원하지 않는 요청이 문제를 조용히 바꾸지 않습니다.

기본값은 빈 shapes/materials, 진공 background, single study 및
`save_fields=true`, `plots=false`인 `results`만 제공합니다. cavity 입력은 2D의
파장·mesh-size·formulation 기본값을 상속하지 않습니다. Plotting과 Studio 3D
렌더러는 제공하지 않으며 명시적인 `plots=true`는 거절합니다. Studio는 이 예제를
목록에 넣지 않고 cavity mesh/run 요청을 거절합니다. `build_mesh`와 `solve_point`는
2D 단계로 유지되며 cavity 진입점은 `run`입니다.

## 검색과 실패 의미

요청한 모드는 지정한 목표 부근에서 찾은 양의 Maxwell 모드입니다. 엔진 계약은
주파수 제곱의 거리(진공 파수 제곱의 거리와 동치)로 후보를 순위화하고, 선택한
모드를 주파수 오름차순으로 반환합니다. 이는 유한한 후보 검색이며 최저 모드들이나
완전한 스펙트럼 구간을 보장하지 않습니다. 특히 기본 주파수보다 훨씬 높은 목표는
그 아래의 모든 모드를 요청한다는 뜻이 아닙니다.

영모드·gradient 모드는 제외합니다. 축퇴 고유벡터는 주파수 중복 제거 없이 별도
모드로 유지하며 `num_modes`는 서로 다른 주파수 값이 아니라 벡터 수를 셉니다.
요청 개수 때문에 축퇴 cluster가 잘릴 수 있습니다. 축퇴 부분공간 안의 개별 벡터와
그 부호는 안정적인 label이 아닙니다. 메시 세분화가 연속체의 축퇴를 갈라놓을 수도
있습니다. 정확한 주파수 일치를 고유한 모드 식별로 가정하지 말고 cluster 중복도와
수렴을 확인해야 합니다.

잘못된 문서는 검증에 실패합니다. Solver 비수렴, 양의 후보 부족, 수치 잔차 검사
실패는 부분 성공 결과를 쓰는 대신 실행을 실패시켜야 합니다. CLI 문서 오류는 종료
코드 2, solver 오류는 1입니다. 해석 실패 시 출력 디렉터리를 만들지 않습니다.

## 결과 파일과 배열 단위

`run(doc)`가 성공하면 2D `RunResult`와 구별되는 `CavityRunResult`를 반환합니다.
`result.frequencies_hz`는 주파수 벡터이며 `result.cavity`에는 재사용할 수 있는
galerkin 결과가 들어 있습니다. `result.save(directory)`는 다음 파일을 씁니다.

- `model.json`: 검증한 문서이며 선언한 입력 단위를 유지합니다.
- `summary.json`: 주파수·고유값·잔차 벡터, 명시적 배열 단위, 메시 개수, 검색 목표,
  요청·반환 모드 수, 초 단위 시간입니다.
- `log.txt`: 문서 요약과 주파수입니다.
- `fields.npz`: `save_fields=true`인 경우에만 아래 배열을 저장하며
  `numpy.load(path, allow_pickle=False)`로 읽을 수 있습니다.

`results.png`는 없습니다. CLI는 results 설정으로 활성화한 파일 이름만 출력합니다.
문서의 단위 선언은 `summary.units`에 보존하지만 **모든 cavity 결과 좌표와 차원이
있는 배열은 SI**입니다. 좌표를 해석할 때 출력의 `mesh_length_unit="m"`를 사용해야 합니다.

| NPZ 키 | Shape | 의미 / 단위 |
| --- | --- | --- |
| `nodes` | `(N, 3)` | 문서 원점을 포함한 미터 단위 좌표 |
| `tetrahedra` | `(T, 4)` | 0부터 시작하는 절점 인덱스 |
| `edges` | `(E, 2)` | 작은 절점 인덱스에서 큰 인덱스로 향하는 전역 에지 |
| `tet_edges` | `(T, 6)` | 지역 에지의 전역 에지 인덱스 |
| `edge_signs` | `(T, 6)` | 지역·전역 에지 방향 사이의 부호 |
| `pec_edge_ids` | `(P,)` | `edges`에서 구속한 에지의 인덱스 |
| `frequencies_hz` | `(K,)` | Hz 단위 공진 주파수 |
| `eigenvalues_m2` | `(K,)` | 진공 파수 제곱, m^-2 |
| `relative_residuals` | `(K,)` | 무차원 대수 잔차 |
| `edge_coefficients` | `(E, K)` | SI 질량 정규화된 에지 적분, m^-1/2 |
| `electric_field` | `(K, T, 3)` | 사면체 중심의 전기장, m^-3/2 |

배열과 함께 스칼라 문자열·수치 metadata를 저장합니다. field layout은
`cavity3d-edge-v1`이며 `mesh_length_unit`, `frequency_unit`, `eigenvalue_unit`,
`edge_coefficient_unit`, `electric_field_unit`, 정규화
`electric_mass_orthonormal_si`, `search`, `target_frequency_hz`,
`requested_modes`, `returned_modes`, `edge_orientation="low_node_index_to_high_node_index"`,
`electric_field_location="tetrahedron_centroid"`,
`cluster_completeness="not_certified"`,
`mode_count_policy="exact_count_may_split_cluster"`를 포함합니다.
지역 에지 6개는 galerkin의 사면체 순서 `(0,1)`, `(0,2)`, `(0,3)`, `(1,2)`,
`(1,3)`, `(2,3)`를 따릅니다. 부호는 이 지역 방향을 저장된 전역 방향으로 대응시킵니다.
Cavity 출력에는 `neff`나 삼각형·절점 스칼라 배열이 없습니다.

정규화는 진공 전기 질량 행렬에 대해 `q.T @ M_SI @ q = I`입니다. 따라서 장의
진폭은 임의 정규화 값이며 **V/m가 아닙니다**. 원시 에지 적분과 중심 장은 서로 다른
배열이며 단위도 다릅니다. 어느 쪽도 절점값으로 해석하면 안 됩니다. 잔차는 PEC로
축소한 일반화 고유문제의 자유 에지에 대해
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
주파수, 고유값, 잔차, 정규화, SI 단위, 목표, 요청·반환 개수, cluster/count 정책
두 필드가 남습니다.

동등한 길이 단위 선언을 사용하려면 모든 domain 좌표를 변환해야 합니다. 예를 들어
미터 단위 정육면체는 `"mm"`에서 최댓값 `1000`으로 나타내고 같은 분할수와 Hz 목표를
사용할 수 있습니다. 그러면 물리적인 SI 출력이 같아야 합니다. 목표를 유지한 채
물리적 크기를 바꾸면 스펙트럼뿐 아니라 검색 문제도 바뀝니다. 기하학적으로 닮은 모드
집합을 비교할 때에는 크기에 반비례하도록 목표를 조정합니다.

## 재료와 도체 벽

같은 `em.cavity3d` study는 축 정렬 직육면체 안의 일정하고 등방적인(손실이 있을 수 있는)
재료와 유한 전도도 벽을 받습니다. 이런 문서는 `galerkin.solve_material_cavity_box`를
실행하고 아래 복소 배치로 저장합니다. 배경이 진공이고 shape·material이 없으며
`"boundary": "pec"`인 문서는 원래 솔버와 위의 진공 배치를 그대로 씁니다. 예제는
`examples/cavity_lossy_slab.json`(`python -m simcase example cavity_lossy_slab`)입니다.

```json
{
  "geometry": {
    "domain": {"xmin": 0, "xmax": 1, "ymin": 0, "ymax": 0.8, "zmin": 0, "zmax": 0.6},
    "background": {"material": "vacuum"},
    "shapes": [{"type": "box", "name": "slab", "material": "lossy_dielectric",
                "xmin": 0, "xmax": 1, "ymin": 0, "ymax": 0.8, "zmin": 0, "zmax": 0.3}]
  },
  "materials": {"lossy_dielectric": {"relative_permittivity": [4.0, -0.04]}},
  "physics": {"em1": {"type": "em.cavity3d",
                      "boundary": {"conductivity_s_per_m": 58000000.0},
                      "search": "near_target", "target_frequency_hz": 150000000.0,
                      "num_modes": 3}},
  "mesh": {"subdivisions": [8, 8, 8]}
}
```

**시간 규약**은 `exp(+j*omega*t)`입니다. 복소 상수는 실수 하나 또는 `[실수부, 허수부]` 쌍이며
`실수부 > 0`, `허수부 <= 0`(수동)이어야 합니다. 손실 탄젠트 `t`인 유전체는 `[eps', -eps' * t]`입니다.

- `materials.<이름>`: `relative_permittivity`(필수)와 `relative_permeability`(기본 1).
  이름 `vacuum`은 예약되어 있고, 2D의 `n`, `k`, `sellmeier`를 포함한 다른 키는 거부합니다.
- `geometry.background.material`: `"vacuum"` 또는 상자 전체를 채우는 정의된 재료.
- `geometry.shapes`: 선언한 길이 단위와 문서 좌표계의 상자
  `{"type": "box", "name", "material", "xmin", ..., "zmax"}`. 이름은 서로 달라야 합니다. 각
  상자는 domain 안에 있어야 하고, 모든 면은 mesh 격자 평면, 즉 domain 최솟값에서
  `extent / subdivisions`의 배수에 있어야 합니다(한 cell의 상대 허용치 `1e-9`). 아니면 검증이
  실패하며 간격을 알려 줍니다. 뒤의 상자가 앞의 상자보다 우선하고, 각 사면체는 무게중심의
  재료를 가집니다.
- `physics.<이름>.boundary`: `"pec"`, 여섯 벽 모두에 대한 `{"conductivity_s_per_m": sigma}`,
  또는 키 `xmin, xmax, ymin, ymax, zmin, zmax`를 쓰는
  `{"conductivity_s_per_m": {"zmax": sigma, ...}}`. 지정하지 않은 벽은 PEC입니다. 전도도는
  `units`와 무관하게 항상 S/m입니다. 벽은 Leontovich 표면 임피던스
  `Zs = sqrt(j omega mu0 / sigma)`를 쓰며 각 모드를 고정점 반복으로 수렴시킵니다.

수치 방법, 기준, 검증은 엔진의
[재료 공진기 계약](https://github.com/fieldalgo/openphysics/blob/main/packages/galerkin/docs/locales/ko/pages/material_cavity.md)에 있습니다.

### 복소 결과

이런 study의 `result.frequencies_hz`는 복소수입니다. `summary.json`에는 JSON에 안전한 실수
배열을 저장합니다.

- `resonant_frequencies_hz`(Re f)와 `frequencies_hz_imag`(Im f, 손실이 있으면 양수);
- `quality_factors`, 즉 `Q = Re f / (2 Im f)`. 무손실 모드는 `null`;
- `eigenvalues_m2_real`와 `eigenvalues_m2_imag`;
- `relative_residuals`;
- `fixed_point_iterations`;
- `lossless`, `time_convention`, 문서의 `boundary`, `background`, `materials`;
- 문서 벽 이름별 `wall_conductivity_s_per_m`(PEC는 `null`).

`fields.npz`는 `field_layout="cavity3d-edge-complex-v1"`을 씁니다. 진공 배치의 mesh·위상·방향
키와 메타데이터 문자열을 유지하고, 다음 키를 더하거나 바꿉니다.

| NPZ 키 | 형태 | 의미 / 단위 |
|---|---|---|
| `frequencies_hz` | `(K,)` 복소수 | 복소 주파수, Hz |
| `eigenvalues_m2` | `(K,)` 복소수 | `k0^2`, m^-2 |
| `quality_factors` | `(K,)` | 무차원; 무손실이면 `inf` |
| `edge_coefficients` | `(E, K)` 복소수 | m^-1/2 |
| `electric_field` | `(K, T, 3)` 복소수 | 무게중심, m^-3/2 |
| `tet_relative_permittivity`, `tet_relative_permeability` | `(T,)` 복소수 | 사면체별 재료 |
| `wall_names`, `wall_conductivity_s_per_m` | `(6,)` | `xmin..zmax`; S/m, PEC는 `nan` |
| `fixed_point_iterations` | `(K,)` | 횟수 |

여기서 `pec_edge_ids`는 PEC 벽의 에지만 나열하며, 도체 벽의 에지는 미지수입니다. 정규화는
`vacuum_mass_hermitian_unit_si`입니다. 진공 에지 질량 `M0`로 `q^H M0 q = 1`이고, 각 모드에서
크기가 가장 큰 계수는 양의 실수입니다. 진폭은 임의이며 **V/m가 아닙니다**. 배열은
`numpy.load(path, allow_pickle=False)`로 읽습니다.

`packages/simcase/tests/test_cavity3d_materials.py`의 시험이 확인하는 것:

- 새 필드 각각의 검증;
- 문서 실행이 엔진 직접 호출과 같음;
- 원점을 옮긴 mm 문서가 같은 SI 결과를 냄;
- 단일 벽이 엔진 벽과 PEC 에지에 대응됨;
- 채운 배경이 진공 스펙트럼을 `eps_r`로 나눈 값과 같음;
- 복소 NPZ·JSON 출력이 pickle 없이 읽힘;
- 무손실 study의 Q가 `null`임;
- 진공 PEC 문서가 원래 솔버를 씀;
- CLI 실행, 엔진 API 누락, Studio 거부.

Studio는 이 study를 나열하거나 실행하지 않습니다. 그림 출력은 여전히 지원하지 않습니다.

## 통합 검증과 수치적 한계

Cavity를 지원하는 galerkin 구현이 있는 저장소 루트에서 실행합니다.

```bash
python -m pytest -q packages/simcase/tests/test_cavity3d_integration.py
```

통합 사례 7개는 simcase revision `ba1c8a7`과 galerkin revision `a660233` 조합에서
통과했습니다. 이전에는 `cd4071a`와 `3b850a8` 조합에서도 통과했습니다. 이는 해당
revision의 과거 검증 기록입니다. 사례는 평행 이동한 정육면체, 처음 두 개의 완전한
reference cluster에 대한 기준 주파수 smoke 검사, m/mm/um/nm 표현, fields 유무에
따른 실제 CLI 실행, `allow_pickle=False`로 읽은 NPZ 복원을 다룹니다. 재조립한 위상
정보, 중심 장, PEC 계수, 자유 에지 잔차, 질량 직교성을 검사합니다. 성긴 메시의
기준 주파수 검사는 메시 수렴 수용 gate가 아닙니다.

이전 galerkin revision `3b850a8`에서는 고정 직육면체 111-cluster 평균 수렴 gate가
실패했습니다. 마지막 관측 차수는 약 1.2284로 요구값 1.8보다 낮았습니다.
Revision `a660233`은 반사 방향을 균형 있게 하는 cavity 메시로 바꿨으며 제품 통합
사례도 이 메시에서 통과했습니다. 문서 실행과 파일 복원이 메시 수렴이나 전체 기능
수용을 독립적으로 인증하는 것은 아닙니다. 수치 검증 근거는
[엔진 검증 기록](https://github.com/fieldalgo/openphysics/blob/2efbc413df5d3d36bcc4c9879b34ed88213b9217/packages/galerkin/docs/cavity_solver.md)을 확인하세요.
