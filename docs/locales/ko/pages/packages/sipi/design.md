# 단면 템플릿·문서·목표 임피던스 설계

[English](../../../../../packages/sipi/design.md) | **한국어**

[SIPI 개요](overview.md)

기존 준정적 엔진에 입력 재현성과 제한 있는 탐색을 더합니다. 새로운 물리 모델은 아닙니다.
모든 길이는 m, 임피던스와 잔차 허용값은 Ω입니다. 물리적 한계는 개요를 참조하세요.

## 템플릿

각 함수는 `CrossSection`을 반환하고 필수 인자는 키워드로 받습니다.

| 함수 | 필수 입력 | 형상 |
|---|---|---|
| `microstrip` | `width`, `substrate_height`, `eps_r` | 아래 접지면 위 표면 신호선 |
| `stripline` | `width`, `plane_spacing`, `eps_r` | 균일 유전체 안 두 접지면 중앙의 신호선 |
| `coupled_microstrip` | `width`, `gap`, `substrate_height`, `eps_r` | 같은 폭의 표면 신호선 쌍; `gap`은 가장자리 사이 거리 |
| `grounded_coplanar` | `width`, `gap`, `ground_width`, `substrate_height`, `eps_r` | 유한 폭의 양옆 접지와 아래 접지면을 가진 표면 신호선 |

모두 `thickness=0`, `tan_delta=0`, `box_width=None`을 받습니다. 표면 템플릿은
`air_height=None`도 받으며 기본값은 `10 * substrate_height + thickness`입니다.
스트립라인의 접지면 간격에는 도체 두께가 포함됩니다. 옆벽은 모두 open(법선 전기변위 0),
스트립라인 위벽은 ground, 나머지 위벽은 open입니다. 기본 상자 폭은 마이크로스트립
`max(20*h, 4*w)`, 스트립라인 `max(12*b, 4*w)`, 결합 쌍 `max(20*h, 4*(2*w+gap))`,
공면 구조 `max(20*h, 4*w, w+2*gap+2*ground_width+4*h)`입니다.

기본 영역은 시작값이며 절단 오차를 보장하지 않습니다. 상자 폭·공기 높이를 각각 늘려 확인하고,
공면 접지 폭도 별도로 늘리세요. 두께 0은 허용하나 폭·간격·유전체 치수는 양수여야 합니다.
잘못되거나 겹치는 형상은 메시 전에 거부합니다. 신호 이름은 `signal` 또는 순서대로
`positive`, `negative`, 공면 접지 이름은 `ground_left`, `ground_right`입니다.
층 이름은 `substrate`, `air` 또는 `dielectric`입니다.

## 입력 문서

```python
from sipi import CrossSectionDocument, microstrip

doc = CrossSectionDocument(microstrip(
    width=1e-3, substrate_height=1e-3, eps_r=4.3, thickness=35e-6),
    mesh={"edge_size": 3.5e-6, "far_size": 0.5e-3, "grade": 0.15})
text = doc.dumps()
restored = CrossSectionDocument.loads(text)
line = restored.analyze()
```

JSON 최상위에는 아래 필드가 모두 필요하며 다른 필드는 허용하지 않습니다.

| 필드 | 계약 |
|---|---|
| `schema` | `"sipi.cross-section/1"` |
| `length_unit` | `"m"`; 암묵적 단위 변환 없음 |
| `layers` | 비어 있지 않은 순서 있는 `{name, thickness, eps_r, tan_delta}` 배열 |
| `traces` | 비어 있지 않은 순서 있는 `{name, x, width, y, thickness, ground}` 배열 |
| `box` | `{width, bottom, top, sides}`; 경계는 `"open"` 또는 `"ground"` |
| `mesh` | 선택 필드 `edge_size`, `far_size`, `grade`, `min_angle`을 가진 객체 |

이름은 공백만으로 이루어지지 않은 문자열이며 각 배열 안에서 유일해야 합니다. 수는 유한 실수이고
불리언·숫자 문자열을 허용하지 않으며 `ground`는 불리언이어야 합니다. 모르는 필드·빠진 필드·
지원하지 않는 버전·중복 JSON 키·비유한 수를 거부합니다. 형상은 `CrossSection` 계약을 따릅니다.
메시 길이는 양수이며 기본값 해석 후 `edge_size <= far_size`, `grade >= 0`,
`0 < min_angle < 34`도(기본 28)여야 합니다. 메시 값의 null은 거부하며 기본값을 쓰려면
필드를 생략합니다. `section.mesh_settings(**options)`는 메시 생성 없이 기본값과 유효성을 확인합니다.

`from_dict`, `to_dict`는 일반 객체를 사용합니다. 문서는 입력을 복사하고 `section`,
`mesh_options`, `to_dict()`는 새 값을 반환합니다. `dumps()`는 결정적인 JSON을 반환하며
파일을 자동으로 쓰지 않습니다. 결과는 이 입력 스키마에 저장하지 않습니다. 생략한 메시 설정은
설치된 엔진의 기본값을 따릅니다. 명시 설정을 보관하려면 `mesh=section.mesh_settings()`로
문서를 만들고 엔진 버전도 함께 기록하세요. 버전에 따라 기본값과 수치 구현이 달라질 수 있습니다.

## 목표 임피던스

```python
from sipi import seek_impedance, stripline

result = seek_impedance(
    lambda w: stripline(width=w, plane_spacing=1e-3, eps_r=4),
    (0.3e-3, 0.8e-3), 50.0,
    mesh={"edge_size": 0.5e-6, "far_size": 0.125e-3, "grade": 0.075},
    tolerance=0.1, max_evaluations=20)
print(result.parameter, result.impedance, result.refined_impedance)
```

`factory(parameter)`는 유효한 `CrossSection`을 반환해야 합니다. 범위는 파라미터 단위의
양수·유한·오름차순 값입니다. `quantity="z0"`는 단일 신호, `"z_diff"`는 대칭 쌍을
`even_odd()`의 대칭 검사까지 포함해 사용합니다. 목표와 허용값은 양수·유한 Ω입니다.

양 끝점을 계산하고 허용값 안의 끝점이 있으면 선택합니다. 그렇지 않으면 양 끝 잔차 부호가
반대여야 합니다. 실제 임피던스 잔차가 허용값 안에 들어와야 이분법을 끝냅니다. 마지막 한 번은
`edge_size`, `far_size`, `grade`를 절반으로 줄인 메시로 계산합니다. 원 메시와 세분 메시
임피던스가 모두 목표 허용값을 만족해야 성공입니다. `max_evaluations`는 세분 계산까지
포함한 전체 계산 횟수 상한이며 3 이상의 정수입니다.

`ImpedanceDesign`은 파라미터·목표·선택량·원/세분 임피던스·입력 문서·평가 이력을 담습니다.
`residual`, `refined_residual`, `mesh_change`로 목표 오차와 메시 변화를 구분합니다.
문서는 원 메시 입력입니다. 구간·평가 상한·파라미터 분해능·세분 검사 실패 시
`GoalSeekError.history`에 완료된 평가가 남습니다. 잘못된 입력과 factory/solver 오류는
전파하며 실패를 성공 설계로 반환하지 않습니다. 세분 검사 실패 시 메시를 더 촘촘하게 설정해
다시 탐색하세요. 이는 수치적 목표 검사이지 제조 공차 보장이나 임의 factory의 단조성 증명이
아닙니다. 영역·재료 불확실성은 별도로 분석해야 합니다.

## 검증

`tests/sipi/test_design_documents.py`에서 네 템플릿과 직접 작성한 형상을 비교하고 JSON
왕복 후 C, C0, L, 유전 손실 행렬 보존을 검사합니다. 잘못된 필드·외부 변경 격리·탐색 실패
경로도 검사합니다. 실제 FEM의 50 Ω 스트립라인 탐색을 독립적으로 근을 구한 Cohn 등각사상
공식과 비교합니다. 폭 오차 1% 이내, 양쪽 메시 잔차 각각 0.1 Ω 이하가 실행 전 정한 기준입니다.
Linux, Python 3.12.14, NumPy 2.5.4, SciPy 1.18.1에서 47개 시험이 통과했습니다.
다른 플랫폼과 설치 패키지 수락은 필수 CI에서 별도로 다룹니다. 기존 물리 참조 허용값은 그대로입니다.
새 외부 의존성은 없으며 템플릿 동등성만으로 공면 구조 물리가 독립 검증됐다고 주장하지 않습니다.
