# 재현 가능한 주파수별 선로 모델

[English](../../../../../packages/sipi/line_model.md) | **한국어**

[형상 JSON](design.md) · [유전체](dielectrics.md) · [도체 손실](conductor.md) · [네트워크](network.md)

`sipi.line_model.TransmissionLineDocument`는 형상·층별 재료·명시한 도체 모델·주파수·선로 길이·
포트 기준값을 입력 스냅샷 하나로 묶습니다. `analyze()`는 메시를 **한 번** 만들고 같은 형상·
도체 순서로 유전체 C/G, 도체 R·내부 L, 균일 선로 S를 계산합니다. 표면 도체에서는 진공 C0 해석도
공유합니다. 다른 단면에서 얻은 행렬을 실수로 섞지 않도록 합니다.

```python
from sipi import CrossSectionDocument, coupled_microstrip
from sipi.dielectric import WidebandDielectric
from sipi.line_model import TransmissionLineDocument

geometry = CrossSectionDocument(
    coupled_microstrip(width=.5e-3, gap=.3e-3, substrate_height=1e-3,
                       thickness=50e-6, eps_r=4),
    mesh=dict(edge_size=5e-6, far_size=.2e-3, grade=.1))
model = TransmissionLineDocument(
    geometry, [1e9, 4e9, 10e9],
    materials={'substrate': WidebandDielectric(4, .02, 1e9)},
    conductor=dict(kind='surface', conductivity=58e6, ground_thickness=35e-6,
                   relative_permeability=1, roughness_rms=1e-6),
    length=.03, z_ref=50)
saved = model.dumps()
result = TransmissionLineDocument.loads(saved).analyze()
result.R, result.L, result.G, result.C
result.network.s, result.network.mixed_mode().s
touchstone = result.network.touchstone()
```

실측 재료·구리 보정값이 아닌 사용 예입니다. 실행 예제:
[`frequency_line.py`](../../../../../../examples/sipi/frequency_line.py).
파일 쓰기는 호출자가 결정하며 `dumps()`는 문자열만 반환합니다.

## 입력 스키마

`sipi.transmission-line/1`은 아래 필드가 **정확히 모두** 필요합니다.

| 필드 | 계약 |
|---|---|
| `schema` | `sipi.transmission-line/1` |
| `cross_section` | 기존 엄격한 `sipi.cross-section/1` 또는 `/2`, 길이는 m |
| `frequency_hz` | 비어 있지 않고 엄격히 증가하는 유한 실수 배열, 0 이상; surface는 0 초과 |
| `materials` | 기존 층 이름별 엄격한 `sipi.dielectric/1`; 생략한 층은 기존 상수값 |
| `conductor` | 아래 perfect 또는 surface를 명시, 기본 도체 없음 |
| `length_m` | 유한 실수 길이, 0 이상 |
| `reference_ohms` | 모든 single-ended 포트의 공통 양의 유한 실수 기준값 |

완전도체는 정확히 `{"kind":"perfect"}`로 R·내부 L을 0으로 둡니다. surface에는
`kind="surface"`, `conductivity`(S/m), `ground_thickness`(m), `relative_permeability`,
`roughness_rms`(m)가 **모두** 필요하며 1과 0도 명시합니다. 기존 도체 모델의 표피 깊이·양도체·
유한 두께·flux 제한을 유지합니다. DC에서 다른 모델로 자동 전환하지 않습니다.
경험적 거칠기는 R을 보정하며 인과적 리액턴스 모델이 아닙니다.

알 수 없는 버전/필드, 누락, 모든 깊이의 JSON 중복 키, 비유한값·bool, 잘못된 재료 표와
유효하지 않은 주파수/표피 깊이 조합은 메시 전에 거부합니다. `materials={}`는 층의 상수값을
유지하는 명시적 선택입니다. 모든 요청 주파수에서 재료값을 먼저 확인합니다.

생성 시 입력을 복사하며 `to_dict()`·`.cross_section`은 새 객체를 반환합니다.
반환값을 바꿔도 저장 입력은 변하지 않습니다. 형상 메시 기본값을 `edge_size`·`far_size`·
`grade`·`min_angle` 숫자로 확정해 저장합니다. 요청 설정을 고정하는 것이지 향후 솔버/수치
라이브러리 버전까지 같은 결과를 보장하는 것은 아닙니다. 설치 환경 사이 재현에는 계산 보고서에
엔진 revision·환경도 함께 보관하세요. 이 스키마는 입력 전용이며 기존 형상 JSON을 바꾸지 않습니다.

버전 2(`sipi.transmission-line/2`)는 위 최상위 필드를 유지하며 surface의
`roughness_rms`만 명시적 smooth/Hammerstad/causal-Huray 객체로 대체합니다.
[거칠기 입력 계약](roughness.md#버전-있는-선로-입력)에 정확한 필드를 정의합니다.
버전 1과 생성자 기본값은 유지하고 저장한 버전도 보존합니다.

## 결과

`TransmissionLineResult`에는 `.input_json`, 읽기 전용 `.mesh_settings`, `.dielectric`,
`.conductor`(perfect이면 None), `.network`가 남습니다. `.frequency`·`.names`가 주파수/도체
순서를 정합니다. R/L/G/C는 `(F,N,N)` 읽기 전용 행렬이며 각각 Ω/m·H/m·S/m·F/m입니다.
L은 외부·내부 성분을 한 번씩 합칩니다. 추출 객체에 층별 복소 유전율, 표면 전류 오차와 표피
깊이도 남습니다. 네트워크의 near→far 포트 순서, mixed-mode 및 single-ended Touchstone 계약은 유지합니다.

기존 재료·표면 알고리즘을 내부 메시 함수로 공유하며 독립 추출 API도 유지합니다.
입력 모델이 형상·메시·순서 일치를 보장하지만 메시 수렴·상자 독립성·재료 정확도·표면 섭동 오차·
준TEM 유효성을 자동으로 확립하지는 않습니다. 직접 만든 결과 객체는 검증 수행의 증거가 아닙니다.

## 검증

`tests/sipi/test_line_model.py`의 기준:

- JSON roundtrip RLGC 상대차 1e-12·S 절대차 1e-10, 사다리꼴 v2 보존, 입력 복사·메시 설정 확정.
- 독립 호출한 유전체/도체 공개 API 조합과 RLGC 상대차 1e-10·S 절대차 1e-10, C0·도체 순서 일치.
- 두 추출에 메시 생성 1회, 완전도체 DC 연결, 독립 스칼라 ABCD·S 상호성/수동성 1e-10.
- 잘못된 형식·중복·비유한값·표 범위 밖·무효 도체를 메시 전에 거부, 도체 선택 필수.

Linux, Python 3.12.14, NumPy 2.5.4, SciPy 1.18.1(2026-10-30)에서 신규 23개와
유전체·도체 56개가 함께 통과했으며 독립 도구를 필수로 실행했습니다.
검토 중 발견한 직사각형 v2 입력의 v1 자동 변경을 수정한 뒤 입력 모델 24개도 통과했습니다.
각 추출 문서가 해석식·외부 기준의 근거를 설명합니다. 이 조합은 새로운 물리 정확도 주장·
런타임 의존성·브라우저/EXE 배포를 추가하지 않습니다.

```sh
OPENPHYSICS_REQUIRE_CROSSCHECK=1 python -m pytest -q tests/sipi/test_line_model.py tests/sipi/test_dielectric.py tests/sipi/test_conductor.py
```
