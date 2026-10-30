# 다각형 도체·국소 유전체·표면 마스크

[English](../../../../../packages/sipi/polygon_sections.md) | **한국어**

[개요](overview.md) · [템플릿과 JSON](design.md) · [사다리꼴 도체](manufacturing_sections.md)

`PolygonTrace(name, vertices, ground=False)`는 단면의 미터 좌표로 유한 도체를
정의합니다. 시계/반시계 방향과 오목 다각형을 지원합니다. 마지막 닫힘 꼭짓점은
생략합니다. 반복 꼭짓점·면적 0·자체 교차·도체 접촉/중첩은 거부하며, 등가
직사각형으로 대체하지 않습니다. 도체 내부 구멍·곡선 경계·CAD 가져오기는 범위 밖입니다.

`DielectricRegion(name, vertices, eps_r=1, tan_delta=0)`는 같은 단순 다각형 규칙의
국소 재료입니다. `CrossSection(..., dielectric_regions=[...])`로 전달합니다.
영역 내부는 겹칠 수 없지만 모서리 공유·층 경계 통과·상자 접촉은 허용합니다.
국소 재료가 기존 층을 덮어쓰고 금속 내부가 모든 유전체보다 우선합니다. 상자 밖으로
나갈 수 없으며 금속을 뺀 뒤 양의 유전체 면적이 남아야 합니다. 층과 국소 영역의
이름은 전체에서 고유해야 합니다.

```python
from sipi import CrossSection, Layer, PolygonTrace, DielectricRegion, CrossSectionDocument

section = CrossSection(
    [Layer('substrate', 1e-3, 4), Layer('air', 1e-3)],
    [PolygonTrace('signal', [(-.3e-3, 1e-3), (.3e-3, 1e-3),
                             (.2e-3, 1.2e-3), (-.25e-3, 1.2e-3)])],
    4e-3,
    dielectric_regions=[DielectricRegion('mask',
        [(-.4e-3, 1e-3), (.4e-3, 1e-3), (.4e-3, 1.3e-3), (-.4e-3, 1.3e-3)], 3.5, .02)])
document = CrossSectionDocument(section, mesh=dict(edge_size=5e-6, far_size=.2e-3, grade=.15))
restored = CrossSectionDocument.loads(document.dumps())
parameters = restored.analyze()
```

## 마스크와 추가 템플릿

다음 함수는 `sipi.templates`에 있습니다.

| 함수 | 형상 / 추가 입력 |
|---|---|
| `with_surface_mask(section, thickness, eps_r, tan_delta=0, gap_fill_height=0)` | 마스크 입력은 키워드 전용. 같은 높이의 유한 직사각형/사다리꼴 도체 위·옆을 코팅하며 공면 접지 도체도 포함 |
| `offset_stripline` | `stripline` 입력에 필수 `trace_height` 추가. 아래 접지면부터 도체 밑면까지 높이 |
| `coupled_stripline` | 필수 수평 밑면 간격 `gap`, 선택 `trace_height` 추가. 같은 폭의 positive/negative 신호 |
| `broadside_stripline` | 필수 `width`, 수직 금속 간격 `gap`, `plane_spacing`, `eps_r`, 양의 `thickness`. 선택 부호 있는 수평 `offset`, `tan_delta`, `box_width`. 아래/위 직사각형 신호 이름 positive/negative |

새 스트립라인 템플릿은 두 접지면 사이의 균일 유전체를 사용합니다. 다른 층 적층,
서로 다른 폭, 다각형은 `CrossSection`으로 만듭니다. 마스크는 공통 도체 밑면이
층 경계에 있어야 합니다. 면을 평행 이동하고 **직선 mitre 모서리, 제한 5**로
잇는 다각형 근사입니다. 제조 메니스커스나 둥근 코너를 예측하는 모델이 아닙니다.
공통 밑면 아래만 잘라내며 옆/위가 상자 밖이면 두께를 몰래 자르지 않고 거부합니다.
기존 국소 영역은 보존하고 새 마스크와 중첩되면 거부합니다.

`gap_fill_height`는 밑면부터 상자 전체 폭에 평탄한 채움을 추가해 위·옆 코팅과
합칩니다. 연결된 결과 이름은 `mask`, 떨어진 영역은 경계 상자의 왼쪽 순서대로
`mask_1`, `mask_2`, ... 입니다. 형상 변경으로 연결 관계와 이름이 바뀔 수 있으며,
각 이름에 유전체 모델을 지정합니다. 구멍을 가진 결과는 거부하므로 그런 경우에는
단순 영역들로 나누어 직접 입력합니다.

```python
from sipi.templates import coupled_microstrip, with_surface_mask
pair = coupled_microstrip(width=.4e-3, gap=.2e-3, substrate_height=1e-3,
                          eps_r=4, thickness=.1e-3, air_height=1e-3, box_width=4e-3)
masked = with_surface_mask(pair, thickness=.03e-3, eps_r=3.5,
                           tan_delta=.02, gap_fill_height=.08e-3)
```

## 형상과 엔진 연결

다각형 교차 연산으로 층과 국소 재료를 분할합니다. 메시 제약은 실제 금속·유전체
경계와 교차점·오목 코너를 따릅니다. 두께 0인 `Trace`도 수평 분할과 끝점 제약으로
국소 재료를 가로질러 전체 길이를 유지합니다. 다각형/국소 영역이 없으면 기존
직사각형·사다리꼴 메시 경로를 유지합니다. 직사각형을 다각형으로 표현하면 분할이
달라지므로 같은 메시라는 보장은 없습니다.

기본 세분화에는 다각형 꼭짓점/변 간 최소 거리와 국소 영역의 해당 거리를 반영하고,
국소 영역 꼭짓점에도 세분화를 적용합니다. 매우 좁은 간격·거의 일직선인 꼭짓점·예각은
계산이 비싸거나 메시 생성에 실패할 수 있습니다. 실패는 그대로 전달합니다.
설계마다 edge/far/grade 세분 및 상자 확대 검증이 필요하며 아래 사례를 모든 형상의
정확도 보증으로 사용하면 안 됩니다.

`section.materials`는 층 다음 국소 영역 순서입니다. `dispersive_line`과
`TransmissionLineDocument`는 두 종류 모두 이름으로 분산 모델을 받고 생략한
재료는 상수값을 유지합니다. `mesh_conductor_section`은 다각형 금속 내부를 포함하고
`VolumeLineDocument`는 같은 형상의 유전체 메시에서 국소 재료를 사용합니다.
자기 해석 전용 메시에는 재료 경계를 추가하지 않습니다. 표면 손실의 skin-depth
검사는 경계 상자 폭 대신 다각형 최소 거리를 사용합니다. 기존 delta <= 치수/5와
적분 전류 오차 5% 제한은 유지하며 최소 거리는 곡률/저항 오차의 보증이 아닙니다.

## JSON v3

`sipi.cross-section/3`은 `length_unit`, `layers`, `box`, `mesh`, `traces`를 유지하고
**필수** `dielectric_regions`를 추가합니다(빈 배열 허용).

- 다각형 도체: `{kind: "polygon", name, vertices, ground}`.
- 직사각형/사다리꼴: `{kind: "trapezoid", name, x, width, y, thickness,
  top_width, ground}`. 직사각형은 위/아래 폭이 같습니다.
- 국소 영역: `{name, vertices, eps_r, tan_delta}`.
- `vertices`는 유한 `[x,y]` 쌍이며 닫힘 꼭짓점을 반복하지 않습니다. 구멍·반경·회전·
  암묵적 단위·알 수 없는 필드는 허용하지 않습니다.

다각형/국소 영역이 있으면 v3를 생성하고 나머지는 기존 v1/v2를 생성합니다.
명시적인 v3 입력은 직사각형뿐이어도 버전을 유지합니다. 기존 transmission-line,
volume-line 스키마는 v3를 그대로 포함하며 바깥 버전은 바꾸지 않습니다. 구형 소비자는
v3를 평탄화하지 말고 거부해야 합니다. 이 변경에 브라우저 소비자·UI·EXE 지원은 없습니다.

## 검증과 한계

`tests/sipi/test_polygon_sections.py`는 유전체/마스크/금속 면적 상대 1e-12, 재료 경계,
입력 불변성, 얇은 도체, 접촉 거부, 엄격 v3 왕복, 국소 분산 재료, 체적 DC 저항
해석식 1e-9, 표면 제한, 템플릿 대칭/유전율 단조성을 검사합니다. 직사각형-다각형 등가,
반사, edge/far/grade를 모두 반으로 줄인 임피던스 변화는 0.5% 미만이어야 합니다.
균일 C/C0=eps_r 기준은 1e-9이며 내부 체적 태그가 사용자 재료 이름과 혼동되지 않아야 합니다.

Linux / Python 3.12.14 / NumPy 2.5.4 / SciPy 1.18.1 / Shapely 2.2.0에서 직사각형과
그 다각형 표현은 44.550999/44.550400Ω이었습니다. 오목 도체와 국소 마스크는
edge 10μm, far 0.2mm, grade .15에서 51.529417Ω, 세 값을 반으로 줄이면
51.581918Ω(변화 0.102%), 반사하면 51.582412Ω이었습니다. 전체 형상의 오차 보증이
아닌 특정 측정값입니다. 독립 scikit-fem 12.0.2 복소 P1 조립과 동일 메시 복소 C
차이는 5.44e-15(기준 1e-9)였고 표준 비교 기록을 출력합니다. 동일 메시의 코드 간
일치는 수렴 검증과 별도입니다. 신규 코드는 Linux 로컬에서 검증했으며 신규 Windows/
macOS 실행 근거는 없습니다. 신규 25개 시험은 소스와 로컬에서 함께 빌드한
SIPI/meshine/galerkin 휠에서 모두 통과했습니다. 전체 SIPI와 관련 문서/참조 도구 회귀는
673개 통과·skip 0(402.90초)이며 저장소 전체 CI 통과를 의미하지 않습니다.

```bash
OPENPHYSICS_REQUIRE_CROSSCHECK=1 OPENBLAS_NUM_THREADS=1 \
  python -m pytest -q tests/sipi/test_polygon_sections.py
```

[실행 예제](../../../../../../examples/sipi/polygon_mask.py)는 두 형상을 저장/복원하고
메시 세분 비교를 출력합니다. SIPI가 Shapely(`>=2.0.2`)를 직접 의존성으로 선언하며
이미 검토한 Python API를 사용합니다. 상류 코드/바이너리를 복사하지 않습니다.
BSD 조건과 동적으로 로드되는 GEOS 구성 요소는 [라이선스 목록](../../third-party.md)을
참고하십시오.
