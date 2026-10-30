# 사다리꼴 도체와 평탄 코팅

[English](../../../../../packages/sipi/manufacturing_sections.md) | **한국어**

[개요](overview.md) · [템플릿·JSON](design.md)

`Trace(..., top_width=...)`는 등가 직사각형 폭이 아닌 **중심이 같은 사다리꼴**입니다.
`width`는 밑폭, `top_width`는 윗폭, `x`는 공통 중심, `y`는 밑면, `thickness`는 수직 두께이며
단위는 m입니다. 윗폭은 유한 양수여야 하고 어느 면이 더 넓어도 됩니다. 두께0이면 두 폭이 같아야
합니다. `top_width=None`은 기존 직사각형 동작을 그대로 유지합니다. 접지 도체에도 적용됩니다.

```python
from sipi import CrossSectionDocument, microstrip
from sipi.templates import coated_microstrip

bare = microstrip(width=0.6e-3, top_width=0.4e-3, thickness=0.1e-3,
                  substrate_height=1e-3, eps_r=4)
coated = coated_microstrip(width=0.6e-3, top_width=0.4e-3, thickness=0.1e-3,
                          substrate_height=1e-3, eps_r=4,
                          coating_height=0.2e-3, coating_eps_r=3.5,
                          coating_tan_delta=0.02)
document = CrossSectionDocument(coated)
restored = CrossSectionDocument.loads(document.dumps())
parameters = restored.analyze()
```

기존 템플릿4개는 신호 도체의 선택적 `top_width`를 받습니다. 결합선 `gap`과 공면 간격은
**밑면 가장자리** 기준입니다. 윗면을 넓히면 실제 간격이 줄거나 겹칠 수 있으며 메시 전에 거부합니다.
공면 템플릿 접지는 직사각형입니다. 기본 상자 폭은 기존 밑폭 공식을 유지하므로 윗폭에 비해
좁으면 명시적으로 넓혀야 합니다. 직접 `CrossSection`을 구성하면 이 중심정렬 도체와 수평층의
비중첩 조합을 쓸 수 있습니다. `x0`/`x1`은 밑면 끝, `xmin`/`xmax`는 전체 수평 범위입니다.

`coated_microstrip`은 `sipi.templates`에서 가져옵니다. `coating_height`는 기판 표면부터
평탄한 코팅 윗면까지의 높이로 **도체 두께를 포함**하며 도체보다 높아야 합니다. 코팅이 도체
옆과 위를 채우고 그 위에 공기층이 있습니다. `coating_eps_r>=1`, `coating_tan_delta>=0`과
기판 손실탄젠트는 별개입니다. 다른 표면 템플릿 인자는 같은 뜻입니다. 평탄 충전 모델이며
conformal 코팅·국소 레지스트·meniscus·임의 마스크는 아닙니다.

## 형상과 메시

층과 도체의 위/아래 면에서 수평 구간을 나누고, 각 구간의 실제 경사면 사이를 유전체 다각형으로
채웁니다. 층 공유선은 constrained segment로 유지하고 구간에 물성을 배정합니다. 도체가 층 경계를
가로질러도 도체 내부는 유전체 메시에서 제외합니다. 두께0 선은 constrained line으로 남습니다.
실제 다각형까지의 거리를 세분 크기와 경계 절점 식별에 씁니다. 배치는 수직으로 겹치는 구간의
실제 폭을 검사하므로, bounding box만 겹치는 비중첩 사다리꼴을 잘못 거부하지 않습니다.

모든 도체가 직사각형이면 윗폭을 명시적으로 같게 주어도 기존 직사각형 분할을 그대로 씁니다.
사다리꼴의 기본 메시에는 두 면의 폭과 실제 도체 간 거리가 포함되며 기존 양의 두께/10 제한도
유지합니다. 명시 메시 설정은 같습니다. 얇은 층·좁은 틈·큰 경사·작은 윗폭은 비용이 클 수 있고
메시 실패를 직사각형 근사로 숨기지 않습니다. 각 설계에서 edge/far/grade 세분과 영역 절단을 확인하세요.

[실행 가능한 코팅 예제](../../../../../../examples/sipi/coated_trace.py)는
입력 저장/복원과 원/반분 메시를 비교합니다.

## JSON 버전

- `sipi.cross-section/1`은 그대로이며 도체 필드는 `{name,x,width,y,thickness,ground}`입니다.
  v1에 모르는 `top_width`를 넣으면 거부합니다.
- `sipi.cross-section/2`는 **모든** 도체에 **필수** `top_width`를 더합니다. 직사각형은 두 폭을
  같게 씁니다. 나머지 필드와 SI 단위는 같으며 null·불리언·누락된 윗폭은 거부합니다.
- 문서를 구성할 때 하나라도 두 폭이 다르면 v2, 모두 직사각형이면 v1을 출력합니다. v2를 읽고
  같은 문서를 다시 dump하면 v2가 유지됩니다. 중복/모르는 필드·유한 수·입력 복사 규칙은 같습니다.
- 코팅은 일반 층이므로 추가 스키마 필드가 필요 없습니다. v1 전용 소비자는 사다리꼴 v2를
  거부해야 하며 직사각형으로 조용히 바꾸면 안 됩니다.

## 검증

`tests/sipi/test_manufacturing_sections.py`의 사전 기준: 직사각형 극한의 절점/삼각형/C 완전동일,
유전체 면적 상대1e-12, 도체 내부·층 경계를 침범하는 요소0, 경계 태그·두께0 선 혼합,
상하반사/세 설정을 모두 반으로 줄인 임피던스 차이 각각0.5% 이하, 균일유전체 C/C0=eps_r
상대1e-9, 좁은/넓은 직사각형 사이의 사다리꼴 정전용량 단조 경계. eps_r=1 코팅은 무코팅
영역값을0.5% 이내로 재현하고 코팅 유전율을 키우면 C가 늘고 Z가 줄어야 합니다.

첫15시험이 Linux/Python3.12.14/NumPy2.5.4/SciPy1.18.1에서 통과했습니다.
균일 stripline 밑/윗폭0.6/0.3mm·두께0.4mm·접지간격2mm·eps_r=4에서
edge5um/far0.25mm/grade0.15의 Z=48.12452Ω, 모두 반분하면48.18408Ω,
위아래 폭 반사 시48.18417Ω입니다. 세분 차0.124%, 반사 차0.00018%입니다.
공기 등가 코팅은93.28491Ω, 추가 경계 없는 값은93.28555Ω입니다. 특정 사례의 관측이며 보편 오차한계가 아닙니다.

기존 시험용 BSD scikit-fem **12.0.2**가 eps_r=4/6 경계를 가로지르는 비대칭 사다리꼴 두 도체의
동일 P1 메시를 독립 조립·풀이합니다. C 비교 기준은 상대1e-9, 무손실 관측은7.46e-15이며
유전손실이 있는 복소 C 관측은1.39e-14입니다. 같은 이산화의 알고리즘 대조이며 수렴 증명이 아닙니다.
필수 CI는 기존 galerkin 비교 extra로 도구를 설치합니다. 로컬에 없으면 skip하지만
`OPENPHYSICS_REQUIRE_CROSSCHECK=1`에서는 실패합니다. 새 런타임 의존성이나 기존 기준/golden 변경은 없습니다.

```bash
OPENPHYSICS_REQUIRE_CROSSCHECK=1 OPENBLAS_NUM_THREADS=1 \
  python -m pytest -q tests/sipi/test_manufacturing_sections.py
```

임의 다각형·중심이 어긋난 윗면·둥근 모서리·도체 손실·주파수 분산·제조 분포·웹 화면은 이 변경에 포함되지 않습니다.
