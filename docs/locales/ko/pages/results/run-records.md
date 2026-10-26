# 재현 가능한 계산 기록 보관하기

[English](../../../../results/run-records.md) | **한국어**

[문서 홈](../index.md)

저장된 장은 모델·코드·가정을 복원할 수 있어야 유용합니다. 이 예제는 기존
[두 재료 벽](../packages/simcase/layered_wall_tutorial.md) 결과 묶음에 작은 로컬 기록을
추가합니다. simcase 설치 후 저장소 루트에서 새 디렉터리나 빈 디렉터리에 실행합니다.

```sh
python examples/simcase/record_wall_run.py out/wall-recorded
```

[스크립트](../../../../../examples/simcase/record_wall_run.py)는 제공된 벽 모델의 입력을
바꾸지 않고 풉니다. `model.json`·`summary.json`·`fields.npz`·`log.txt` 외에 다음을 씁니다.

| 파일 | 의미 |
|---|---|
| `input.json` | 해석 전에 읽은 원본 JSON 바이트 |
| `run-record.json` | UTC 시작/종료·Git 커밋과 실행 전 dirty 플래그·Python/플랫폼·선택한 설치 패키지 버전·재료 레코드·파일 SHA-256 해시 |

기록 스키마는 이 예제 전용이며 새 simcase 결과 계약이 아닙니다. 해시는 `input.json`을
포함한 저장 파일을 대상으로 하고 기록 파일 자체는 제외합니다. 실행 성공은 수렴
근거가 아니므로 `convergence: not_checked`를 명시합니다. 다음으로 묶음을 확인합니다.

```python
import hashlib
import json
from pathlib import Path

folder = Path("out/wall-recorded")
record = json.loads((folder / "run-record.json").read_text(encoding="utf-8"))
for name, expected in record["sha256"].items():
    actual = hashlib.sha256((folder / name).read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError(f"Changed result file: {name}")
print(record["git_commit"], record["git_dirty_before_run"])
print(record["convergence"])
```

## 기록이 입증하지 않는 것 이해하기

Git 메타데이터는 현재 checkout에 대한 값입니다. 설치 패키지는 다른 checkout이나
wheel에서 왔을 수 있습니다. 문서의 editable 설치를 따르거나 사용한 정확한
wheel·환경 잠금 파일을 보존하세요. 선택된 버전 목록은 전체 의존성 잠금 파일이
아니며 플랫폼·수치 라이브러리 간 비트 단위 재현을 보장하지 않습니다.

Dirty 플래그가 `true`이면 커밋만으로 작업 트리를 복원할 수 없습니다. 관련 변경과
추적되지 않은 소스 입력을 보관하거나 커밋 후 다시 실행하세요. `null`은 Git 정보를
얻지 못했다는 뜻입니다. 실행 중 코드나 입력을 수정하지 마세요. 해시는 이 기록과
비교한 파일 변경을 검출하며 서명·출처 인증·물리적 정확도 증명이 아닙니다.

## 수치적 주장에 필요한 근거 추가하기

서로 다른 실행 폴더 옆에 간단한 비교 표를 보관합니다.

| 항목 | 명시할 내용 |
|---|---|
| 물리적 주장 | 물리량·위치/시간/모드·단위·필요 허용 오차 |
| 재료 데이터 | 출처 레코드와 버전·파장/온도 범위·피팅 계수 |
| 외부 입력 | 메시/데이터 파일과 해시·사용한 데이터베이스 버전 |
| 수치 설정 | 메시/창/시간 간격/PML 설정과 각 실행의 입력 |
| 독립 비교 | 해석식 또는 기준 도구/버전과 관찰 오차 |
| 수렴 | 연속 세분화 값·변화/오차·선택한 합격 기준 |
| 검증 | 정확한 테스트 명령·종료 상태·선택적 skip; 로컬 검사와 CI 구분 |

벽 모델에는 [튜토리얼](../packages/simcase/layered_wall_tutorial.md)의 직렬 열저항 해와
메시 비교를 사용합니다. 도파로는 [슬래브 대조군](../validation/slab-tutorial.md)에서
시작하세요. 다른 예제가 통과했다고 현재 실행을 수렴했다고 표시하지 않습니다.
시각화 내보내기와 함께 원본 묶음을 보관하고, 단위와 데이터 위치는
[저장 장 가이드](saved-results.md)를 따릅니다.
