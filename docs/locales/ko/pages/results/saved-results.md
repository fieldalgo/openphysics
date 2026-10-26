# 저장한 장 읽기와 ParaView 내보내기

[English](../../../../results/saved-results.md) | **한국어**

[문서 홈](../index.md)

[두 재료 벽](../packages/simcase/layered_wall_tutorial.md)을 실행해 `out/wall-base/`를 만드세요.
이 안내는 저장된 simcase 해석 결과에 관한 것이며 실험 workspace의 입력·session 형식과 다릅니다.
그림을 내보내는 것만으로 재현 가능한 계산을 저장한 것은 아닙니다.

## 원래 결과 묶음 보존하기

| 파일 | 보존하는 이유 |
|---|---|
| `model.json` | 이번 해석과 함께 저장한 모델 문서 |
| `summary.json` | 결과·layout 버전, 단위, 위치, shape, 영역 배정 |
| `fields.npz` | 수치 장과 layout 메타데이터; `save_fields: true` 필요 |
| `log.txt` | 실행 진단 |
| `view.vtu` | 선택적 보기용 복사본이며 위 파일을 대신하지 않음 |

실행마다 새 폴더 또는 빈 폴더를 별도로 사용합니다. 이 벽 예제에서는 기존 결과 파일을
덮어쓰지 않고 보호합니다. 해석 후 결과 객체의 문서나 메시를 고쳐서 수정한 모델을 푼 것처럼
저장하지 마세요. 입력을 바꿨다면 다시 해석합니다. 이 묶음만으로 전체 Git·의존성 출처가
기록되는 것은 아닙니다. 수치 주장을 재현할 때는 코드 revision, 환경, 외부 데이터 버전을
별도로 함께 기록하세요.

## 배열 위치와 단위를 함께 읽기

벽 예제를 실행한 뒤 저장소 루트에서 다음 블록을 실행합니다.

```python
import json
from pathlib import Path
import numpy as np

folder = Path("out/wall-base")
summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
print(summary["field_layout"])
print(summary["regions"])
with np.load(folder / "fields.npz", allow_pickle=False) as fields:
    print("Temperature (K):", fields["temperature_k"].min(), fields["temperature_k"].max())
    print("Thermostat input (W/m):", fields["reaction_w_per_m"].sum())
    print("Convection out (W/m):", fields["convective_outward_w_per_m"].sum())
```

`temperature_k`는 노드 값이고 `heat_flux_w_m2`는 요소 벡터입니다. `triangle_regions`는
`summary["region_names"]`를 가리키는 요소별 ID이며 재료 ID나 온도가 아닙니다.
해당 영역 항목이 재료를 지정하고 여러 영역이 같은 재료를 쓸 수 있습니다.
범용 reader를 작성하기 전 `field_units`, `field_locations`, `field_shapes`, `field_layout`을
확인하세요. 모든 물리가 같은 배열을 반환하지는 않습니다.

## 보기용 파일 열기

예제의 `--export`는 이미 `view.vtu`를 만듭니다. 재해석 없이 기존 저장 결과를 내보내려면
아직 존재하지 않는 다른 이름을 선택하세요.

```python
from simcase.export import export_fields
export_fields("out/wall-base/fields.npz", "out/wall-base/second-view.vtu")
```

ParaView에서 VTU를 열고 Apply를 누릅니다. point data `temperature_k`로 색칠한 뒤
cell data `triangle_regions`로 바꿔 경계를 확인합니다. 필요하면 메시 모서리도 표시하세요.
열유속은 cell data `heat_flux_w_m2`의 x 성분 또는 크기로 봅니다. cell data를 point data로
바꾸는 것은 표시용 보간이며 솔버 정확도가 좋아지는 것이 아닙니다. 실행을 비교할 때는
같은 색상 범위를 사용하세요. 영역 이름·물성·경계 tag가 모두 VTU에 복사되는 것은 아니므로
NPZ와 summary를 보존합니다.

## 시간 이력

지원되는 과도 열 layout의 저장 결과에서 `export_time_series`는 저장된 시각별 VTU와
PVD 모음을 만듭니다. 보간하거나 다시 해석하지 않습니다. ParaView에서 PVD를 열고 시간
제어를 사용하세요. PVD와 VTU 파일은 함께 이동해야 합니다. 시간은 초이며 frame 번호가
아닙니다. 초기 frame에는 온도·열유속이 있지만 완료 단계의 reaction·residual·storage rate는
없습니다. 전체 명령은 [과도 내보내기 안내](../packages/simcase/overview.md)를 따릅니다.

## 뷰어 선택 전 지원 범위 확인

| 저장 layout 계열 | VTU / PVD |
|---|---|
| Dirichlet·단열 직사각형 정상 열 | VTU |
| flux/convection 직사각형 정상 열 (`boundary-v2`) | 미지원 |
| flux/Robin 필드를 포함한 정상 재료 영역 열 | VTU |
| 직사각형·영역 과도 열 | 한 시각은 VTU, 저장한 전체 시각은 PVD |
| 진공 PEC 공동 | VTU |
| 손실 공동·도파관 모드·전기/Joule 결과 | 이 exporter에서는 미지원 |

영역 경로와 직사각형 boundary-v2 경로는 물리 조건이 비슷해도 layout이 다릅니다.
내보내기 미지원이 해석 실패를 뜻하지는 않습니다. 정확한 범위와 해석은
[영역 내보내기](../packages/simcase/thermal_regions2d.md)와 [결과 신뢰성](index.md)을 읽으세요.
