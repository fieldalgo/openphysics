# PML·누설·일정 반경 모드

[English](../../../../../packages/simcase/pml_modes.md) · [복소 재료 모드](lossy_modes.md) · [좌표 정식화](../galerkin/modal_coordinates.md)

`em.modes2d`는 직사각형 영역에서 scalar/full-vector 복소좌표 PML과 일정
반경 굽힘을 지원합니다. 반환값은 물리 공진으로 인증된 결과가 아닌 **후보**입니다.
PML 인공 모드가 포함될 수 있으므로 메시·물리 창·PML 두께·강도를 각각
변경하여 감쇠의 안정성을 확인해야 합니다. 단일 실행은 항상
`stability: "not_checked"`를 보고합니다.

## 입력과 단위

기존 `physics.em1`에 다음 설정을 추가합니다.

```json
{
  "target_effective_index": 2.85,
  "pml": {
    "pml_thickness": {"bottom": "0.5 um", "top": "0.5 um"},
    "pml_strength": 3.0,
    "pml_order": 2,
    "pml_minimum_physical_fraction": 0.1,
    "pml_search_mode_count": 16
  },
  "bend": {"bend_radius": "5 um", "axis": "y", "bend_origin": "0 um"}
}
```

직선에서는 `bend`를 생략합니다. 두께·반경·원점은 단위를 붙인 길이,
`pml_strength`와 비율은 무차원, `pml_order`는 정수 2/3/4입니다. 생략한 면의 두께는
0이며 하나 이상은 양수여야 합니다(`"0 um"`으로 쓴 면은 거절). `pml_strength`(기본 3),
`pml_order`(기본 2), 비율(기본 0.1, (0, 1]), `bend.axis`(기본 `x`)를 생략하면
`defaults_applied`에 기록합니다. PML 띠를 제외한 물리 창이 남아야 하고
메시가 두 영역을 모두 분해해야 합니다. 선언한 형상에 PML이 포함되므로
재료를 PML까지 연장합니다. PML 외곽은 PEC, 다른 면은 기존 PEC/PMC입니다.
두 방향 모두 재료 경계·PML·장을 충분히 분해해야 합니다. 요소를 가로지르는
PML/물리창 경계는 요소중심 계수와 소속으로 근사하므로 메시 수렴에 포함합니다.

양수 `target_effective_index`를 명시해야 합니다. 닫힌 도파관의 유전체 구간 대신 목표
근처를 검색합니다. vector `effective_index_threshold`는 설명용이며 열린 후보의 분류 기준이
아닙니다. 금속·흡수 재료는 기존 복소 재료 계약을 따릅니다. 굽힘 축은 바깥
방향이고 `bend_origin`에서의 양수 `bend_radius`를 지정합니다. 전체 영역의 반경이 양수여야
하며 전파 거리는 기준 호 길이 `z=R theta`입니다.

## API와 결과

```python
from simcase import Document, run
result = run(Document.load("model.json"), verbose=False)
print(result.effective_index)            # 복소수, 점 × 모드; Im > 0이 감쇠
print(result.propagation_loss())         # dB/m, 부호를 보존한 총 전력 감쇠
print(result.bend_loss())                # 90도당 dB; 직선이면 None
print(result.open_boundary)              # 점별 전체 검색 후보
result.save("results")
```

`solve_point`와 `run`은 exp(−iωt)의 SI로 보고합니다. 커널 기준틀의
`simcase.physics_em_modes2d.solve(..., n_target=2.85, pml=..., bend=...)`(마이크로미터,
exp(+iωt), 커널 고유 이름)는 내부 구현입니다. JSON summary는
`mode_result_schema="openphysics.modes2d/3"`, `time_convention`과 함께 `re`/`im` 값 객체인
`effective_index`, `propagation_loss`(dB/m), `open_boundary`, 굽힘이면 `bend_loss`(90도당 dB)를
기록합니다. NPZ는 pickle 없이 복소 배열과 `open_boundary_json`을 저장합니다.
기능 브랜치 구현이 릴리스를 뜻하지는 않습니다. PML 결과는 [닫힌 창
결과](overview.md#모드-후처리)의 `unnormalized_mode_power`/`confinement_factor`/
`unnormalized_field_overlap`/`coupling_efficiency` 배열을 저장하지 않습니다. 횡 계수가 늘린 좌표의 공변
적분이어서 창 전체의 무손실 Poynting 식은 물리 전력이 아니며, 물리 창 변형은
제공하지 않습니다. `results.mode_overlap` 블록은 검증만 하고 무시합니다.

굽힘이 없는 벡터 PML 결과는 `te_polarization_fraction`과 `effective_area`를 **물리 창**에서 계산해
`fields.npz`와 `summary.json`에 저장합니다. 물리 창은 중심 (p0 + p1 + p2)/3이 `physical_bounds`
안(경계 포함)에 있는 삼각형들이며, 미터 단위 `node_coordinates`와 `physical_bounds`로 판정합니다.
이는 풀이기 자신의 물리 마스크와 같습니다. 식은 닫힌 창의 식을 저장된 중심 장에 그대로 쓴 것이며,
그곳에서 중심 장은 물리적인 E입니다. 이때 `mode_postprocessing`에는 이 두 키와 `integration_region:
"physical_window"`가 들어갑니다. 누설이 강한 모드의 유효 면적은 창에 따라 달라집니다. 닫힌 결과에는
키가 늘지 않고, 굽힘과 스칼라 PML 결과에도 늘지 않습니다. `results.group_index`는 `pml`과 함께
받으며(`bend`와는 받지 않음) 복소 n_g를 줍니다([군굴절률](group_index.md)). 검증:
[열린 경계의 모드 식별](workspace.md#열린-경계의-모드-식별),
`tests/simcase/test_open_boundary_mode_identity.py`의 V9, V10, V12, V13과
`tests/simcase/test_open_boundary_group_index.py`의 V11.

각 `openphysics.pml-candidates/2` 점은 전체 후보의 1부터 시작하는 번호,
복소 `effective_index`, 원래 pencil 상대잔차 `relative_residual`, 양의 물리/PML L2 비율,
선택 번호와 이유, 미터 단위 `physical_bounds`를 기록합니다. `pml_search_mode_count`가 없으면 검색 수는 최소 6개 또는 요청 수의
두 배이고, 있으면 정확히 그 수입니다(1부터 64까지의 정수이며 `mode_count` 이상, 스윕에서는
추적기의 `study.tracking.search_mode_count` 이상이어야 하고 아니면 `E-CONTRACT`). 어느 쪽이든
자유 DOF에 제한됩니다. 검색을 넓히면 좁은 검색이 목표 근처에서 놓치는 물리 모드를 찾습니다.
이 키는 `defaults_applied`에 기록하지 않으므로 이 키가 없는 문서는 키가 생기기 전과 같은 결과를 냅니다. 적격 기준은 양수 실수부, 잔차<=1e-8
(`relative_residual_threshold`), 물리 비율>=`pml_minimum_physical_fraction`(기본 0.1, (0, 1]),
허수부>=−b입니다(이득처럼 보이는 후보는 `negative_imaginary_index`로 제외; b는 아래
[이득 경계](#이득-경계)). 적격 후보 중 목표와 가까운 것을 선택하고
첫 점에서 실수부 내림차순으로 반환합니다. 제외·미선택 후보도 기록합니다.
비유한 전파근은 저수준 계산을 중단하며 조용히 삭제하지 않습니다. 벡터 정식화의
정적 `beta^2 = 0` 근 중 `|beta^2| <= 1e-10 |sigma|`인 것은 후보가 아니며, 그런 근만
나온 탐색은 적격 후보가 없는 탐색과 똑같이 거부합니다
([도파관 정식화](../galerkin/waveguide_formulation.md#3-full-vector-혼합-nédélec절점-정식화)).
한계: 작은 창에서 큰 `pml_search_mode_count`(또는 낮은 목표)는 목표와 그 무리 사이에 있는
근보다 많은 근을 요구할 수 있습니다. 굽은 slab 예제를 64로 찾으면 정적이 아닌 후보는
27개입니다. 이런 탐색은 ARPACK 재시작 200번 뒤에 멈춥니다. 수렴하지 않은 근이 정적 근뿐이면
수렴한 탐색과 같은 후보를 galerkin의 `PartialSearchWarning`과 함께 주고, 기록은 그대로입니다.
그 밖에는 ARPACK의 `ArpackNoConvergence`로 실행이 멈춥니다. Studio의 탐색(목표 근처 32개,
1.95 근처 16개)은 template과 기판 위 strip에서 무리에 닿지 않습니다. 가장 작은 `|nu|`가
무리의 1.44배 이상입니다.

### 추가 검색

목표 하나 근처의 검색 하나는 목표에서 먼 물리 모드를 놓칠 수 있습니다. 기판 위 스트립에는
클래딩 굴절률 근처의 모드(n ≈ 1.486 + 7.9e-3i)가 있는데, 2.46 근처 32개 검색은 이를 찾지 못합니다.
`pml.pml_additional_searches`는 주 검색(`target_effective_index`와 `pml_search_mode_count`) 외에
추가 검색 1~3개를 나열합니다.

```json
"pml": {"pml_thickness": {"bottom": "1 um", "top": "1 um"}, "pml_search_mode_count": 32,
        "pml_additional_searches": [{"target_effective_index": 1.95, "pml_search_mode_count": 16}]}
```

- 항목마다 두 키를 모두 씁니다. 각 목표는 유한한 양수이고, 쓴 그대로의 값(정확한 십진수:
  `1.95`와 `1.950`은 같은 목표)이 주 목표와도 다른 모든 항목과도 달라야 합니다. 각 개수는
  1부터 64까지의 정수(주 개수와 같은 `pml_search_mode_count`의 레지스트리 범위)이며 주 개수처럼 자유 DOF에 제한되고, `mode_count` 이상일 필요는 없습니다.
  오류는 키 경로의 `E-CONTRACT` 또는 `E-DOMAIN`입니다.
- 이 키는 벡터 정식화와 단일 study에서 읽습니다(굽힘은 허용). 스윕은 거부합니다(`E-CONTRACT`):
  "pml_additional_searches is not read with a study sweep in this release; give one target".
- 검색은 같은 메시와 pencil에서 순서대로 돌고 목표마다 분해를 한 번 합니다. 행렬은 같지만
  검색마다 다시 조립합니다(조립 1 + k번). 후보는 그 순서로 번호를 매기고 각각 위의 기준으로 적격 여부를 정합니다.
- 뒤 검색의 후보 b는 앞 후보 a(앞 검색의 후보이고 그 자신은 중복이 아니며, 적격 여부와 무관)와
  |n_b − n_a| ≤ 1e-9 max(1, |n_a|)이고 η_w(a, b) = |⟨a, b⟩| / (‖a‖ ‖b‖) ≥ 0.99이면
  **중복**입니다. 내적은 횡방향 모서리 계수와 전체 계산 메시의 모서리 질량 행렬로 계산합니다.
  굴절률 허용치 안에 앞 후보가 여럿이면 b를 그 생성 공간에 사영한 것이 제곱 노름의 0.99 이상을
  담을 때 중복입니다. 중복 후보도 기록은 남지만 선택되지 않습니다. 이유에 자신의 이유와 함께
  `duplicate_candidate`가 붙고, `duplicate_of`, `duplicate_effective_index_distance`,
  `duplicate_field_overlap`(겹침 경우에는 사영 비율의 제곱근), 그 경우에만 `duplicate_span`을
  기록합니다.
- 목표와의 거리 대신 **Re n_eff가 큰** 적격 비중복 후보 `mode_count`개를 Re 내림차순으로
  반환합니다(`selected_descending_real_index`, 나머지는 `outside_requested_count`). 적격 후보가
  없으면 합친 진단과 함께 `ModeSelectionError`를 냅니다.
- 기록은 `openphysics.pml-candidates/3`입니다. /2의 모든 키에 `searches`(`search`,
  `target_effective_index`, `search_mode_count`, `candidate_count`), `selection:
  "descending_real_index"`, `duplicate_rule`, 후보마다 `search`(1부터)가 더해집니다. 요약의
  `selection`은 `pml_heuristic_descending_real_index`이고, `mode_result_schema`와 모드장 배치는
  바뀌지 않으며, `resolved_inputs`가 검색들을 그대로 보여 줍니다. 키가 없으면 아무것도 바뀌지
  않습니다(스키마 /2, `selected_near_target`). 이 키보다 오래된 simcase는 키 이름으로
  거부합니다(`E-KEY-UNKNOWN`).
- 한계: 추가 검색이 있으면 순위는 Re 내림차순이므로, PML이 지배하는 후보를 빼는 일은
  `pml_minimum_physical_fraction`에 기댑니다. 0.1처럼 낮은 비율에서는 손실 있는 후보가 첫째로
  올 수 있습니다(`examples/simcase/pml_leaky_slab.json`에 추가 검색 2.0/8을 넣으면 2.8521 대신
  3.4396 + 0.0513i를 반환). Studio 문서는 0.5를 씁니다.
- 한계: 추가 검색이 있으면 모드는 Re 내림차순으로 순위가 매겨집니다. 원하는 Re가 낮은 모드(예를
  들어 다른 편광 갈래) 위에 놓인 모드 수보다 적게 요청하면 그 모드는 반환되지 않습니다. 모드 수를
  늘리거나 그 근처의 단일 목표를 쓰십시오. 옆벽이 PMC인 누설 슬래브에서 1개를 요청하면 TM 극
  2.0555 + 6.82e-4i가 아니라 TE 편광 슬래브 모드 2.833018 + 1.915e-5i를 반환합니다. TM 후보
  (2.054060 + 6.724e-4i)는 Re 순으로 8번째이며 `mode_count` 8에서 반환됩니다.

### 이득 경계

무손실 도파 모드의 Im n_eff는 0입니다. PML 메시에서 계산된 Im n_eff는 부호가 어느 쪽이든 될 수 있는
잡음이며, 모드 장 중 PML 안에 있는 부분이 클수록 커집니다. 후보는 다음일 때만 이득처럼 보이는
후보로 보고 `negative_imaginary_index`로 거절합니다.

    Im n_eff < −b,   b = max(1e-10, K f_pml) max(1, |Re n_eff|),   K = 1e-2

f_pml은 기록된 `pml_l2_fraction`입니다. 무손실 모드의 잡음은 |Im n_eff| ≤ b이며, 이득 쪽이라도
b 안이면 적격입니다.

- **측정**(Linux, 27회 계산: 템플릿, 기판 위 스트립, 누설 슬랩, 700 × 300 nm 코어, P1 V5의 PML
  1.5 µm와 2 µm 템플릿을 요소 길이 × 1, ½, ¼로, 그리고 PML 세기 1.5와 6, 차수 3, 굽힌 슬랩(벡터와
  스칼라)을 포함한 넓은 검색 10회). 비 r = |Im n_eff| / (f_pml max(1, |Re n_eff|)):
  - Im < 0인 무손실 도파 모드: r은 7.6e-6부터 2.57e-3(가장 큰 것은 PML 세기 1.5에서 템플릿의 속박
    1.4924 모드, Im −5.4e-5, 약 19 dB/cm의 잡음);
  - 이득처럼 보이는 후보(굽힘의 PML 모드, f_pml ≥ 0.956): r은 5.67e-2부터 0.68;
  - 참고로 실제 누설 모드(Im > 0): r ≥ 8.6e-2(슬랩의 1.87e-5, f_pml 7.6e-5).
- **K**는 이 27회 계산에서 골랐습니다. 가장 큰 무손실 비보다 3.9배 위, 가장 작은 이득형 비보다
  5.7배 아래입니다. 경험값이며 증명이 아닙니다. r이 K보다 작은 이득형 후보는 받아들여지고 r이 K보다
  큰 무손실 모드는 거절되겠지만, 둘 다 관측되지 않았습니다.
- **기록.** −b ≤ Im n_eff < −1e-10 max(1, |Re n_eff|)인 후보는
  `attenuation_status: "negative_within_pml_bound"`로 표시합니다. `numerically_unresolved`와
  `resolved_sign`의 뜻은 그대로이고 키나 스키마 이름은 바뀌지 않았습니다. 이 경계 전의 한계
  −1e-10 max(1, |Re n|)는 측정된 잡음보다 1e2~1e5배 아래였습니다. 그래서 세밀한 메시에서 Studio
  템플릿의 TM-like 모드(Re 1.7712, × ½에서 Im −2.4e-9)가, × 1에서는 속박 1.4923 모드(Im −2.67e-7)가
  거절되었습니다. 이제 둘 다 반환됩니다. P1의 단일 검색 템플릿 문서에서 모드 2개면 × 1 선택은 그대로이고,
  4개나 8개면 1.4923 모드를 세 번째로 반환합니다(`tests/simcase/test_pml_gain_bound.py`).
- **잡음 크기.** 반환된 무손실 모드의 잡음은 부호와 무관하게 |Im n_eff| ≤ b입니다. PML 세기 3에서
  템플릿의 1.4923 모드는 Im −2.67e-7(약 0.094 dB/cm)이며, 같은 크기의 양수 Im은 손실로 보고됩니다.
  b보다 작은 손실은 분해되지 않습니다.

`abs(Im n)<=1e-10 max(1,|Re n|)`이면 `numerically_unresolved`로 표시하고
부호 있는 값과 감쇠를 보존합니다. 0으로 고치지 않습니다. 이 문턱은 수치적
부호 진단이지 정확도 보증이 아닙니다. 요청보다 적게 찾으면 개수를 명시하며
0개면 `.diagnostics`가 있는 `ModeSelectionError`를 냅니다. 유한 검색은 완전성을
보장하지 않고 비율 문턱만으로 모든 인공 모드를 구분할 수도 없습니다.

## 모드장·정규화·추적

scalar는 물리 절점 peak=1, vector는 물리 요소중심의 최대 |E|=1입니다.
둘 다 상대진폭이며 단위 전력이 아닙니다. 요소 소속은 중심으로 판단합니다.
`pml-vector-edge-nodal-v2`에서 transverse는 계산 좌표의 공변 edge 선적분
(늘림 없는 물리창에서는 실제 Et), longitudinal은 h로 나눈 실제 Ez 절점값,
electric은 각 Jacobian 성분으로 나눈 요소중심 장입니다. PML 내부 장은
인공적입니다. scalar 표현은 `pml-scalar-nodal-v2`입니다.
둘 다 파일 배치 `em-modes2d-p1-node-centroid-v2`로 저장되므로 `simcase.export`는 다른 모드
결과처럼 내보냅니다. VTU는 계산 메시 전체를 담으므로 배열은 흡수층까지 덮고 그 안의 값은
인공적입니다. `open_boundary`의 `physical_bounds`가 물리창을 표시하며 VTU에는 복사되지
않으므로 뷰어에서 잘라 보세요.

양의 L2 진단은 transverse 계산좌표 edge mass와 실제 Ez의 절점보간을 씁니다.
물리창에서 sx=sy=1입니다. PML 기여는 이 지표를 확장한 진단값이며 전자기
에너지·biorthogonal 내적·모드 직교성 주장이 아닙니다. 동일한 양의 지표를
물리 영역에 제한해 파장 추적에 사용합니다.

형상/PML/굽힘을 고정한 파장 sweep만 지원합니다. scalar/vector 모두 양수의
엄격히 단조로운 파장 3개 이상이 필요합니다. 모드 부족·모호한 매칭·거의 축퇴한
매칭이면 중단합니다. resolved assignment는 개별 고유장을 보존하고 후보
선택 번호를 갱신하며 서로 다른 고유값의 장을 섞지 않습니다.
`electric-l2-subspace-v1`은 이 복소 스펙트럼에서 지원하지 않습니다. 복소 군지수는
스펙트럼 미분이며 에너지 속도가 아닙니다. 파장 간격과 후보 수도 검증해야 합니다.

## 부호·감쇠·한계

`exp(-i omega t+i beta z)`, `beta=k0 n_eff`입니다. 수동 재료는 Im epsilon>=0,
수동 순방향 감쇠는 Im n_eff>0입니다. 전력 손실은 미터 단위 진공 파장으로
`40 pi Im(n_eff)/(ln(10) wavelength)` dB/m입니다. 굽힘은 기준 반경에서
`bend_loss=propagation_loss pi R/2`(90도당 dB, R은 미터)입니다. 커널은 exp(+iωt)에서
계산하며 simcase가 경계에서 모든 복소 값을 한 번 켤레로 바꿉니다. 모두 흡수와 방사가 포함된 **총**
감쇠입니다. 서로 다른 계산을 빼는 것으로 재료·누설·굽힘 손실이 유일하게
분리되지는 않습니다.

Studio에서 PML 면·강도·차수·비율·목표 및 굽힘을 입력합니다(길이는 양 문자열). 결과는 모든
후보 이유와 잔차를 표시하며 인공 PML 장은 회색으로 가립니다. scalar는 불변축
TE slab 편광의 정확식이고 일반 2D 고대비 도파관에서는 근사입니다. 가변곡률,
3D 열린 모드, 자동 PML 수렴 인증, 비Hermitian 축퇴 부분공간 추적은 범위 밖입니다. PML 잡음과
이득을 가르는 [이득 경계](#이득-경계)는 경험값입니다.

검증은 독립 outgoing slab 전달식, 복소차수 원통 J/Y/Hankel 매칭, 3개 메시,
독립 PML/창 변화, bound 무손실·큰 반경 극한, 별도 scikit-fem 조립+dense QZ를
사용합니다. 관련 시험은 `tests/galerkin/test_pml_modes.py`,
`tests/galerkin/test_crosscheck_skfem_pml_modes.py`,
`tests/simcase/test_pml_contract.py`이며 기존 무손실 기준과 golden을 바꾸지 않습니다.

실행 예제: [기판 누설 slab](../../../../../../examples/simcase/pml_leaky_slab.json), [일정 반경 slab](../../../../../../examples/simcase/pml_bent_slab.json).
