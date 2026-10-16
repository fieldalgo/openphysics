# 직사각형의 headless 정상 열전도

[English](../../../thermal_steady2d.md)

`thermal.steady2d`는 면외 방향 단위 두께를 갖는 단일 균질 2D 직사각형에서
`-div(k grad T) = Q`를 풉니다. 기존 P1 열전도 엔진을 사용합니다. 이 문서는
headless API와 CLI를 설명합니다. Studio는 이 모델을 거절하고 이전 광학 결과를
지웁니다. 이 버전에는 열전도용 Studio 편집기나 렌더러가 없습니다.

## 입력

문서 형식은 `"openphysics": "0.2"`입니다. `units.length`(예: `m`, `mm`, `um`)와
`units.temperature: "K"`를 선언합니다. 형상 경계 좌표는 선언한 길이 단위를
사용하며, adapter가 메시 생성과 조립 전에 미터로 변환합니다. 다음 고정 접미사
필드는 문서 길이 단위와 관계없이 SI 의미를 갖습니다.

- `conductivity_w_mk`: 유한한 양의 상수, W/(m K).
- `heat_source_w_m3`: 부호를 가질 수 있는 유한한 상수, W/m³. 기본값은 0입니다.
- `dirichlet_temperature_k`: `left`, `right`, `bottom`, `top` 중 하나 이상을 유한한
  비음수 켈빈 온도에 대응시키는 비어 있지 않은 매핑입니다. 지정하지 않은 외벽은 단열입니다.

서로 인접한 지정 경계는 모서리 절점을 공유합니다. 같은 온도는 중복을 제거하고,
상충하는 온도는 매핑 순서와 관계없이 거절합니다. 0 K도 유효한 지정값입니다.
직사각형은 연결되어 있으며 비어 있지 않은 Dirichlet 집합이 상수 영공간을 제거합니다.
하위 엔진도 연결 성분별 구속을 검사합니다. 임의의 분리된 메시는 이 문서 형식의
범위 밖입니다.

`mesh`에는 `subdivisions: [nx, ny]`만 들어갑니다. 각 값은 불리언이 아닌 양의
JSON 정수여야 합니다. `4`는 허용하지만 `4.0`, `true`, 0과 음수는 거절합니다.
`geometry`에는 유한하고 엄격히 순서가 맞는 네 `domain` 경계값만 들어갑니다.
`materials`는 비어 있어야 하며 physics는 정확히 하나, `study`는
`{"type":"single"}`이어야 합니다. `results`는 불리언 `save_fields`와 `plots`를
받으며 `plots`는 기본값인 false만 허용합니다. 광학 재료·분산·파장 키, shapes,
sweep, 추가 키, 영역별 k, Neumann/Robin, 시간 의존, 결합 해석, 3D 요청은 거절합니다.

완전한 예제를 생성하고 실행합니다.

```sh
simcase example thermal_slab > slab.json
simcase validate slab.json
simcase run slab.json -o slab_results
simcase example thermal_mixed > mixed.json
simcase run mixed.json -o mixed_results
```

예제는 L=0.03 m, H=0.02 m, k=12.5 W/(m K), TL=280 K, TR=315 K를 사용합니다.
위·아래 경계는 단열입니다. `thermal_slab`은 Q=0, `thermal_mixed`는
Q=100000 W/m³입니다. 독립 정답은 다음과 같습니다.

`T(x) = TL + (TR-TL)x/L + Q x(L-x)/(2k)` 및
`qx(x) = -k(TR-TL)/L - Q(L-2x)/2`, `qy = 0`.

혼합 열원 예제의 부호 있는 순 외향 열량은 면외 깊이당 QLH=60 W/m입니다.
각 경계의 열량은 서로 반대 부호일 수 있습니다. 같은 물리적 직사각형을 유지하며
경계값의 단위를 mm에서 um으로 바꾸면 모든 SI 결과가 같아야 합니다.

## API와 원시 결과

```python
from simcase import Document, ThermalRunResult, run
result = run(Document.load("mixed.json"), verbose=False)
assert isinstance(result, ThermalRunResult)
result.save("fresh_results")
```

`result_format`은 `thermal.steady2d-result-v1`, `field_layout`은
`thermal2d-p1-node-cell-v1`입니다. 이 값은 입력 형식 0.2 및 광학·공진기 결과
형식과 독립적으로 열전도 출력을 식별합니다. 온도에 neff, 파장, 모드 정규화를
붙이지 않습니다.

| NPZ 키 | Shape | 위치 | 단위 |
| --- | --- | --- | --- |
| `nodes_m` | (N,2) | 절점의 SI 좌표 | m |
| `triangles` | (M,3) | 정수 절점 연결 정보, CCW | 1 |
| `temperature_k` | (N,) | 절점 | K |
| `heat_flux_w_m2` | (M,2) | 삼각형 중심, q=-k grad T | W/m² |
| `load_w_per_m` | (N,) | 절점에 조립된 열원 | W/m |
| `reaction_w_per_m` | (N,) | 절점의 내향 구속 반력 | W/m |
| `residual_w_per_m` | (N,) | 전체 조립 잔차 K T - load | W/m |
| `dirichlet_node_ids` | (D,) | 정렬되고 중복이 없는 지정 절점 인덱스 | 1 |
| `dirichlet_temperature_k` | (D,) | 대응하는 지정 온도 | K |

결과 속성은 `mesh_nodes_m`, `mesh_triangles` 및 위 표의 물리량·Dirichlet 배열
이름 7개입니다. 지정 절점의 반력은 `K T - load`이며 자유 절점 반력은 0입니다.
전체 residual은 지정 절점 반력과 반올림 오차 수준의 자유 절점 잔차를 모두
보존합니다. 순 외향 열량은 중복 없는 지정 절점 반력 합의 **음수**입니다.
절점 W/m 양은 단위 깊이당 적분값이고 flux는 W/m²입니다. 요소 flux는 요소 경계에서
불연속이며 절점장이 아닙니다. flux와 residual은 엔진의 동치 연결 성분 offset
좌표에서 평가합니다.

`summary.json`에는 format/layout ID, 원래 문서 단위, SI 메시 단위, 배열 9개의
단위·위치·shape, 지정 절점 수, 온도, 열원·외향 열량·열수지 진단, 시간이 기록됩니다.
수치는 유한해야 합니다. `fields.npz`에는 object 배열 없이 Unicode 스칼라 식별자와
`metadata_json`도 들어갑니다. 소비자는 `numpy.load(path, allow_pickle=False)`를
사용하고 식별자를 검사한 뒤 배열을 해석해야 합니다. `save_fields=false`이면
NPZ 전체를 생략하고 summary, model, log는 남깁니다. 이때도 원시 배열의 수치·shape
검사와 유한한 JSON 검증은 수행합니다. 저장 좌표는 문서 단위가 아닌 SI입니다.

## 출력 소유권과 실패

대상 경로는 존재하지 않아야 합니다. 빈 디렉터리, 기존 파일, 끊어진 symlink도
거절합니다. CLI는 해석 전에 검사하며, save는 배타적 mkdir로 새 대상을 확보합니다.
동시에 새 저장을 시도하는 mkdir claim 중 하나만 성공하고 패자는 승자의 데이터를
정리하지 않습니다. 이것은 다른 writer가 출력 안에 들어와도 된다는 뜻이 아닙니다.
Caller는 **실패 cleanup을 포함한 save 전체가 끝날 때까지** 외부 writer가 출력
디렉터리나 그 항목을 바꾸지 못하게 해야 합니다. 수용 범위는 비적대적인 caller-exclusive
fresh-output 계약입니다.

소유 writer는 `.incomplete`, model/log 및 선택적 NPZ를 쓴 뒤 `summary.json`을
마지막에 씁니다. Marker 제거 전에 finish가 기록한 artifact의 존재와 관측 identity를
검사하며, 누락을 관측하면 완료하지 않습니다. 생성자의 handle 확보가 실패하면 관측상
같은 빈 target만 제거를 시도하고 원래 예외를 유지합니다.

Cleanup은 관측한 소유권을 검사하며 디렉터리를 재귀적으로 삭제하지 않습니다.
검사 전에 관측한 외부·교체 파일이나 대상은 보존합니다. **검사와 뒤따르는 open/unlink는
별개 연산**이므로 check/use 사이 교체에 대한 원자적 보호는 없습니다. 외부 writer가
경합하면 바뀐 target에 쓰거나 cleanup 중 교체 파일을 삭제할 수 있습니다. Inode pin은
재사용을 identity로 오인하는 문제를 막지만 이 race를 제거하지 않습니다. 정리를 마치지
못하면 미완료 출력이 남을 수 있습니다. 소비자는 같은 배타적 사용 전제에서 summary가
있고 `.incomplete`가 없는지 모두 확인해야 합니다. 원자적 다중 파일 게시·적대적 race
보호·crash rollback 보장이 아닙니다. 독립 source/설치본의 실제 반례가 check/use 한계를
보여줍니다. [독립 보고서](https://github.com/fieldalgo/openphysics/blob/e9183fc8f5444422c7a5e167c878d2d5804a6611/packages/simcase/docs/locales/ko/pages/thermal_simcase_independent_validation.md)를 참고하세요.
이 한계는 과거 Windows fixture-operation 두 실패와 별개이며 그 원인을
입증하지 않습니다.
소유권 고정에는 POSIX 파일 descriptor와 좁은 Windows adapter를 사용합니다.
Windows 파일 identity는 쓰기 후 유지하는 파일 handle 대신, 독점 생성한 인접 임시
디렉터리의 hard link로 고정합니다. 출력 이름이 교체돼도 원래 파일의 할당을 유지합니다.
파일시스템이 동일 볼륨 hard link를 지원해야 하며, 지원하지 않으면 identity 검사를
조용히 약화하지 않고 원인을 chain한 `OSError`로 저장에 실패합니다. 출력 부모에
쓰기 권한이 필요하며 저장·정리가 끝날 때까지 이 임시 인접 경로도 호출자가 독점해야 합니다.
관측한 자기 link와 빈 디렉터리만 제거하고 예상 밖 내용은 보존합니다. crash 시 pin
디렉터리가 남을 수 있으며 crash rollback을 제공하지 않습니다.
디렉터리 handle은 여전히 표준 라이브러리 ctypes와
`FILE_FLAG_BACKUP_SEMANTICS`를 사용하며 모든 native 파일 열기는 read/write/delete를
공유를 요청합니다. 실제 연산 가능 여부는 caller-exclusive 계약 아래 별도로
확인해야 합니다. 새 파일에는 `CREATE_NEW`를
사용합니다. 플랫폼별 실제 실행 근거는 별도로 확인해야 합니다. Windows API 계약은
Microsoft의 [CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)와
[directory handles](https://learn.microsoft.com/en-us/windows/win32/fileio/obtaining-a-handle-to-a-directory)에 설명되어 있습니다.
Microsoft의 [FILE_RENAME_INFORMATION](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/ns-ntifs-_file_rename_information)은
열린 대상 파일 교체와 열린 파일을 포함한 디렉터리 이름 변경의 제한도 설명합니다.
delete 공유만으로 이 제한이 사라진다고 가정하면 안 됩니다.

CLI 종료 코드는 성공 0, 잘못된 입력 2, solver/save 실패 1입니다. 유한하지 않은
JSON 거절도 1입니다. 예상된 실패는 traceback 없이 오류를 출력합니다.
기존 EM/cavity 출력 동작은 유지합니다.

## 수용 근거와 한계

전용 시험은 엔진과 adapter의 일치만 보는 대신 affine slab, 혼합 열원 닫힌형 정답,
반력 부호를 독립적으로 비교합니다. 고정 분할수 8/16/32/64에서 마지막 두 구간의
온도 L2 차수는 1.8 이상, flux 차수는 0.9 이상이어야 하며, 혼합 예제의 열원·외향
열량은 60 W/m입니다. SI 불변성은 1e-9, 정규화된 배열·반력 검사는 1e-10입니다.
모서리 상충, 엄격한 입력 타입, raw 유한성·shape·연결 정보·CCW, no-pickle 소비자,
fields 비활성 저장, 기존 대상, 부분 실패, 파일·디렉터리 교체, 동시 writer,
CLI 오류와 Studio 지연 응답을 시험합니다.
이 gate는 전체 패키지·설치본 회귀 검사를 대체하지 않습니다. 열전도 plot, 성능
기준선, 지원하지 않는 경계·재료 모델을 제공한다고 주장하지 않습니다.

실패 주입 검사는 OS errno/winerror/message와 fixture 단계를 기록합니다.
교체가 완료된 뒤 의도한 NPZ 이후 주입 오류에 도달해야 합니다. OS가 rename/replace를
거부하면 fixture 사전조건 실패이며 cleanup 소유 보호의 성공이나 cleanup이 교체 파일을
지웠다는 증거로 해석하지 않습니다.

열린 파일 handle을 유지하지 않는 pin 후보 `d89ce964b71ac3c47cd1bed47118653374967fbb`는
Windows Server 2022 / CPython 3.12.10의 좁은 설치 API·CLI·저장 gate에서
36개 통과·62개 deselect, 별도 source 기존 대상 보호 3개 통과·14개 deselect를 기록했습니다.
원래 다섯 fault 단계는 바꾸지 않았고 이전에 거부된 rename/replace 두 연산도 포함합니다.
추가 link-pin 사례 일곱 개도 포함됩니다. [정확한 실행](https://github.com/fieldalgo/openphysics/actions/runs/38857948286)을
참조하세요. Windows 전체 회귀·macOS 수용이나 hard link 미지원 파일시스템을 보장하지 않습니다.
이전 실패는 역사적 근거로 보존합니다.

