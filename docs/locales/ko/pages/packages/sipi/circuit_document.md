# 회로 계산 입력 저장

[English](../../../../../packages/sipi/circuit_document.md) | **한국어**

[개요](overview.md) · [종단 회로](termination.md) · [Touchstone](touchstone.md)

`sipi.circuit_document.CircuitDocument`는 네트워크 정의·구동 조건·명시한 소스와
부하 임피던스를 strict `sipi.circuit/1` JSON으로 저장합니다. 기존 선로·종단
엔진을 실행하며 새 재료 모델·파일 I/O·네트워크 접속·UI를 추가하지 않습니다.

```python
from sipi.circuit_document import CircuitDocument

network = dict(kind='rlgc', frequency_hz=[0, 1e6, 1e9],
    R=[[10]], L=[[400e-9]], G=[[0]], C=[[100e-12]],
    length_m=1, reference_ohms=50, names=['signal'])
doc = CircuitDocument(network,
    excitation={'kind': 'sources', 'voltages': {'near:signal': 1}},
    terminations={'near:signal': 50, 'far:signal': 100})
restored = CircuitDocument.loads(doc.dumps())
result = restored.analyze()
```

DC에서는 1 V 소스와 총 160 Ω 직렬 회로입니다. 단자 전압은 `[0.6875, 0.625]` V,
네트워크 안쪽 방향 전류는 `[0.00625, -0.00625]` A,
`network_power[0]`은 0.000390625 W입니다.

## 스키마

최상위 필드는 정확히 `schema`, `network`, `excitation`, `terminations`입니다.
`schema`는 `"sipi.circuit/1"`입니다. 알 수 없는/누락된 필드, JSON 중복 키,
NaN/Infinity를 거부합니다. `from_dict`는 JSON 값만 받으며 Python complex,
NumPy 배열, 문자열이 아닌 객체 키는 거부합니다. 문자열 실행은 없습니다.
생성 시 입력을 스냅샷으로 복사하고 `to_dict()`는 새 복사본을 반환합니다.

`network`는 다음 중 하나이며 나머지 필드는 모두 필수입니다.

| `kind` | 나머지 필드 | 의미 |
|---|---|---|
| `rlgc` | `frequency_hz`, `R`, `L`, `G`, `C`, `length_m`, `reference_ohms`, `names` | 기존 균일 선로 API, 명시 도체 이름 배열, SI RLGC와 공통 실수 기준 임피던스 |
| `touchstone` | `text`, `ports`, `port_names` | 지원하는 single-ended S 본문, 양의 정수 포트 수와 파일 순서의 명시 이름 배열 |
| `transmission-line` | `document` | 스키마까지 포함한 [공유 메시 선로 문서](line_model.md), perfect/surface 도체 선택 명시 |
| `volume-line` | `document` | 스키마와 전체 메시 설정을 포함한 [동일 기하 금속·유전체 문서](volume_line.md) |

앞 두 종류는 주어진 네트워크 데이터입니다. 뒤 두 종류는 형상·재료·주파수·길이·
기준 임피던스를 보존하고 `analyze()`에서 RLGC/S를 추출합니다. 기존 문서가
해결한 기본값을 저장합니다. 소스/부하 이름과 주파수 길이는 **메시 생성 전에**
검사하고 실제 추출된 포트 순서·주파수와도 일치해야 합니다.
입력 수락이 이후 물리 해석의 성공을 보장하지는 않습니다.

`excitation`은 정확히 두 형식 중 하나입니다.

- `{"kind":"sources", "voltages":{...}}`: 포트 이름→Thevenin peak 전압 V의
  비어 있지 않은 맵. 여러 소스와 영 입력을 지원합니다.
- `{"kind":"crosstalk", "aggressor":"...", "near_victim":"...", "far_victim":"..."}`:
  서로 다른 세 포트를 명시합니다. aggressor에 1 V peak 소스를 적용하며
  종단 계약의 실제 입사 전압 기준 NEXT/FEXT를 사용합니다.

`terminations`는 포트 이름→유한 수동 임피던스 Ω의 맵으로 빈 맵도 가능합니다.
미지정 포트는 각자의 기준 임피던스, 미지정 소스는 0입니다. 임피던스 0은
지원하지만 개방/무한대, 음의 저항, 결합 부하 행렬, 비선형 구동기, 물리적
포트 위치 추론은 미지원입니다.

각 값은 유한 실수 스칼라/길이 F 배열 또는 `{"real":..., "imag":...}`입니다.
후자의 두 성분은 모두 스칼라 또는 같은 길이 F 배열이어야 합니다.
bool·문자열·null은 수치가 아닙니다. 스칼라는 모든 주파수에 적용됩니다.
정규 저장 형식은 모든 값을 명시 real/imag 객체로 쓰며 언어별 복소 구문을
저장하지 않습니다.

## 실행과 출력

`from_dict(data)`와 `loads(text)`는 입력을 검사합니다. `dumps()`는 키를
정렬한 결정적 JSON, `to_dict()`는 복사본입니다. `analyze()`는 `CircuitResult`를
반환합니다.

- `input_json`: 계산에 사용한 정확한 정규 입력.
- `response`: `TerminatedNetwork`의 단자 V/I·파동·소스/부하·전력·잔차.
  기존 peak/DC 전력 정의를 유지합니다.
- `network`: response가 보존한 네트워크 스냅샷.
- `crosstalk`: 해당 구동 종류의 `Crosstalk`, 아니면 `None`.
- `extraction`: 두 형상 기반 종류의 선로 결과(RLGC·기존 진단 포함), 아니면 `None`.

메시·재료·표피 해상도·조건수·잔차 실패를 그대로 전달합니다. 부분 성공,
외삽·자동 모델 변경을 하지 않습니다. 이 계약은 **입력** 스키마이며 결과 저장
형식이 아닙니다. 같은 입력도 다른 엔진 버전에서 bitwise 동일하다는 보장은 없습니다.

## 검증과 재현

```sh
OPENPHYSICS_REQUIRE_CROSSCHECK=1 python -m pytest -q tests/sipi/test_circuit_document.py
python examples/sipi/circuit_document.py
```

DC 예제는 독립 직렬 저항 해석해와 상대 1e-10으로 비교합니다.
네 가지 경로의 JSON 복원 결과를 직접 API와 비교해 S 절대 차이 <=1e-12,
단자 V/I 상대 1e-10을 요구합니다. 비상호 4포트·불균등 기준 fixture의 NEXT/FEXT는
절대 차이 <=1e-12입니다. 복소 배열·다중 소스·복사 독립성·중복/미등록 필드·
메시 전 포트 검사·유한 금속 표피 해상도 거부 전파를 검사합니다.

직접 API 대조는 조합·직렬화 검증이며 독립 물리 정확도 검증이 아닙니다.
형상·주파수 한계와 해석해/참조 도구 검증은 연결된 각 엔진 계약을 따릅니다.
실측 일치·브라우저·portable 실행 검증을 뜻하지 않습니다.
[실행 예제](../../../../../../examples/sipi/circuit_document.py).
