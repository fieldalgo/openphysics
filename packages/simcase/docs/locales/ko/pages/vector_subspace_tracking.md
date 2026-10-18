# 벡터 파장 sweep의 선택형 부분공간 추적

[English](../../../vector_subspace_tracking.md) | **한국어**

기본 벡터 sweep 추적기(`electric-l2-assignment-v1`, [개요](overview.md) 참고)는 개별
모드를 따라가며 원형 광섬유의 두 HE11 편광처럼 근축퇴 상대가 있으면 거절합니다.
`electric-l2-subspace-v1`은 명시적으로 선택하는 방법으로, 가까운 모드들이 이루는 고립
군집의 **span**을 추적합니다. Python, CLI, Studio에서 쓸 수 있습니다.

```bash
python -m simcase example vector_fiber_subspace_sweep > fiber_pair.json
python -m simcase run fiber_pair.json -o fiber_pair_results
```

```json
"study": {"type": "sweep", "parameter": "physics.em1.wavelength",
          "values": [1.5, 1.525, 1.55, 1.575, 1.6],
          "tracking": {"method": "electric-l2-subspace-v1",
                       "cluster_span_max": 1e-4, "external_gap_min": 1e-3}}
```

기본 추적기의 sweep 규칙은 그대로 적용됩니다. 벡터 physics 항목 하나, 유한하고 양수이며
엄격히 단조인 파장 3개 이상, 고정 메시, 구간 전체를 덮는 보수적 `n_cladding`이 필요합니다.

## 설정

| 설정 | 기본값 | 의미 |
|---|---|---|
| `method` | `electric-l2-assignment-v1` | `electric-l2-subspace-v1`이면 이 추적기 |
| `cluster_span_max` | 필수 | 한 군집의 최대 절대 n_eff 폭. 이보다 가까운 이웃은 합칩니다 |
| `external_gap_min` | 필수 | 이웃 후보 모두와의 최소 절대 n_eff 간격. `cluster_span_max`보다 커야 합니다 |
| `search_modes` | `max(2*num_modes, num_modes+4)` | 유도 후보 한도. `num_modes`보다 큰 정수 |
| `min_overlap` | `0.8` | 각 군집에서 **가장 작은** 주값 제곱의 하한 |
| `min_margin` | `0.1` | 대안 완전 군집 할당의 최소 점수 손실 |

두 n_eff 임계값에는 기본값이 없습니다. 모든 도파로·메시·구간에 맞는 값이 없기 때문입니다.
`degeneracy_tolerance`는 기본 방법의 설정이며 이 방법과 함께 쓰면 거절합니다.

## 추적 대상

각 파장에서 유도 후보를 n_eff 내림차순으로 놓고, 이웃 간격이 `cluster_span_max` 이하이면
같은 군집으로 묶습니다. `num_modes`는 **벡터 개수**입니다. 처음 `num_modes`개 후보는 완전한
군집들로만 이루어져야 하며, 군집 구성원 하나만 고르는 일은 없습니다.

선택 군집은 다음을 모두 만족할 때만 받아들입니다.

- 폭이 `cluster_span_max` 이하. 이보다 넓은 근접 이웃 사슬은 나누거나 합치지 않고 거절합니다.
- 이웃 후보와의 간격이 각각 `external_gap_min`보다 큼.
- 아래쪽에 **lower guard** 후보가 관측됨. 없으면 탐색 경계가 미확정이므로 후보 한도를 다 쓰지
  않았어도 실패합니다. 예제 광섬유에서는 HE11 쌍 아래에 TE01/TM01/HE21 계열이 관측돼야 하며,
  기본 모드만 있는 구간은 거절합니다.

각 군집의 원시 장 `U`를 고정 문서 메시의 전기장 L2 metric `W = diag(M_edge, M_node)`로
백색화합니다. `G = U^H W U`이면 frame `Q = U G^(-1/2)`는 `Q^H W Q = I`를 만족합니다. Gram
행렬이 rank 부족이거나 조건수가 1e8을 넘으면 실패하며 pseudoinverse는 쓰지 않습니다.

이전 frame `P`와의 교차 Gram `P^H W Q = L diag(sigma) V^H`가 주각의 코사인을 줍니다. 같은
rank 군집끼리 군집별 `sigma^2` 평균의 합이 최대인 전역 일대일 할당으로 짝짓습니다. 짝은 가장
작은 `sigma^2`가 `min_overlap` 이상이어야 하므로, 평균이 높아도 한 방향을 잃으면 실패합니다.
각 짝의 margin은 그 짝을 뺀 최선의 완전 할당이 잃는 점수이며, 대안이 없으면 `null`입니다.
구성원을 잃거나 얻은 군집, 이웃과 합쳐지거나 나뉜 군집은 파장·군집·원인과 함께 실패하며,
성공한 부분 sweep은 반환하지 않습니다.

frame은 가장 가까운 unitary 회전 `R = V L^H`로 이전 frame에 정렬하므로 `P^H W (Q R)`은
Hermitian 양의 준정부호입니다. 시작 지점의 방향은 임의입니다. 구성원이 하나인 군집에서는
점수가 기본 추적기의 정규화 overlap 제곱과 같고 `R`은 그 위상 인자입니다.

## 결과

`run`은 `SubspaceSweepResult`를 반환합니다. 서로 다른 세 대상을 구분합니다.

| 대상 | 접근 | 의미 |
|---|---|---|
| 원시 고유쌍 | `neff`, `vector_fields` | 솔버 고유장. 보통의 max-centroid 정규화. 열은 시작 군집 순서이고 구성원은 **각 지점에서** n_eff 내림차순. 구성원 열은 분지 식별자가 아닙니다. |
| 군집 | `cluster_ids`, `cluster_ranks`, `cluster_offsets` | 일정한 rank와 열 범위 |
| 운반 frame | `frame_transforms`, `frame_fields(i)` | 블록 대각 `T`, `frame = raw @ T`. 문서 길이 좌표에서 전기장 L2 정규직교. **고유모드가 아닙니다.** |

군집 값:

- `cluster_mean_index()`: 군집별 원시 n_eff 평균, 모양 (지점, 군집).
- `cluster_mean_group_index()`: 기본 추적기와 같은 2차 유한차분으로 구한
  `n_bar - lambda * d(n_bar)/d(lambda)`. 군집 평균 굴절률의 미분이며, 어떤 frame 열의
  군굴절률도 아니고 출력 가중 평균도 아닙니다. rank 1이면 보통의 군굴절률입니다
  (`singleton_group_index()`).
- `group_index()`는 `None`을 반환합니다. 열별 군굴절률은 없습니다.
- `subspace_density(i, cluster_id)`: 삼각형 중심에서 frame 전체의 `sum_j |F_j|^2`를 최댓값으로
  나눈 값. frame의 unitary 변환에 불변입니다. 전자기 에너지 밀도나 편광 모드가 아닙니다.

`summary.json`은 `field_representation="vector-subspace-edge-nodal-v1"`을 쓰며 `clusters`,
`raw_neff`, `cluster_mean_neff`, `cluster_mean_group_index`, `mode_tracking`을 담습니다. 지점·군집별
추적 근거에는 후보 순위, 폭, 위/아래 간격, guard 순위, Gram 조건수, 정규직교 결함, 모든 주값 제곱,
점수, margin, 최대 각의 sine이 있습니다. `neff`와 `group_index` 키는 없으므로 기본 구성을 읽는
소비자가 원시 구성원 열을 분지로 오해할 수 없습니다.

`fields.npz`(`allow_pickle=False`로 읽힘)는 메시, `values`, `cluster_ids`, `cluster_offsets`,
`raw_neff`, `edges`, `raw_transverse`, `raw_longitudinal`, `raw_electric`, `frame_transform`
(지점 x 벡터 x 벡터, 복소), `cluster_mean_neff`, `cluster_mean_group_index`,
`mode_tracking_json`을 담습니다. `save_fields=false`이면 이 파일을 쓰지 않습니다. `save`와 CLI는
이미 있는 출력 경로를 거절하므로 새 metadata가 이전 실행의 장과 섞이지 않습니다.

`simcase.physics_em_modes2d.vector_pencil_residuals(mesh, eps_tri, wavelength,
boundary, neff, field)`는 풀이와 같은 파장 축척·PEC 구속으로 각 열을 원래 벡터 pencil의
고유쌍으로 평가합니다. 원시 열은 반올림 수준의 고유쌍입니다(예제에서 약 1e-14). n_eff가 다른
구성원을 섞은 frame 열은 고유쌍이 아니며, 잔차는 구성원 고유값의 상대 폭 정도입니다. 예를 들어
예제의 HE11 쌍 안에서는 2e-6, HE11 구성원과 TE01을 섞으면 3e-3입니다.

근거 항목 `sin_max_angle`은 `sqrt(1 - sigma^2)`가 아니라 투영 잔차 `Q - P (P^H W Q)`로
계산하므로 작은 각의 상쇄 오차를 피합니다. 정확도는 여전히 frame 정규직교 결함 delta에 따라 약
sqrt(delta)로 제한됩니다. 보통 군집에서는 1e-8 근처, Gram 조건수 한계 근처에서는 약 1e-4입니다.

## Studio

Studio는 분지 대신 군집 선택("cluster 1 (rank 2)")을 보여 줍니다. 장 화면은 정규화 부분공간
장 밀도를 그리고, 선택한 파장에서 n_eff 범위·평균·평균 굴절률 미분·가장 작은 주값 제곱을
표시합니다. sweep 그래프는 군집 평균 n_eff를 그립니다. 표는 군집별 평균 n_eff, 범위 폭, 평균
굴절률 n_g를 보여 주며 구성원 군굴절률은 표시하지 않습니다. HTTP 결과는
`field_representation="vector-subspace-edge-nodal-v1"`인 별도 `subspace` 객체를 담고 `neff`와
`group_index`는 null이므로 분지 화면이 이를 표시할 수 없습니다. 페이지는 다른 구성 버전을
거절하며, 실행이 실패하면 이전 표시를 지웁니다.

## 한계

- 물리 검증은 아직 좁습니다. 대칭 polar 광섬유 fixture(a = 4 um, n1 = 1.45, n2 = 1.44,
  반지름 6a, 1.53~1.57 um)에서 HE11 쌍의 군집 평균 굴절률 미분은 1.55 um에서 정확한 벡터
  군굴절률(음함수 미분, `refsol.fiber.vector_group_index`)과 메시 scale 1, 2, 3에서 각각
  2.1e-5, 6.4e-6, 2.9e-6 차이 납니다. 사전 등록한 기준은 scale 2에서 2e-4 미만, scale 3에서
  감소입니다. 같은 fixture에서 TE01과 TM01을 각각 단일 군집으로 추적하는 시도는 실패했습니다.
  이 메시는 둘의 9.6e-6 분리를 약 1e-6까지만 분해합니다. 같은 HE11 사례에서 영역을 8a, 10a로
  넓혀도 결과는 1e-11만 바뀌었습니다. 파장 간격을 절반이나 두 배로 바꾼 변화(약 1e-7)는 해석
  stencil 절단 오차 예측과 일치했습니다. 후보 한도를 늘리거나 솔버 축퇴 기저를 무작위로 회전해도
  반올림 이상의 변화는 없었습니다. FEM HE11 고유벡터 span은 정확한 두 편광 장 span(`refsol.fiber.vector_mode_field`)에 1차로
  수렴합니다. 최대 주각의 sine은 scale 1~3에서 0.097, 0.049, 0.033입니다. Sellmeier 분산 코어·클래딩
  사례는 scale 2, 3에서 정확한 분산 n_g와 6.0e-6, 2.6e-6 차이이며, 재료 분산 기여는 정확한 값과
  2.5e-7 이내로 일치합니다. 더 높은 V의 광섬유(n1 = 1.47, V = 4.79)에서
  우연 rank-3 군집(HE21 쌍과 TM01, 2.2e-5 간격)을 HE11·TE01과 함께 추적하면 평균 굴절률 미분 오차가
  메시 scale 3에서 3.5e-5 미만이고 scale 4에서 줄어듭니다. scale 2에서는 같은 설정이 거절됐습니다.
  더 성긴 메시가 TE01을 그 군집에 이어 붙이기 때문입니다. 다른 도파로와 형상은 아직 남아 있습니다.
- 분리, 합류, rank 변화, 차단 연속, 개별 편광 라벨, 군집 안 개별 기울기는 범위 밖입니다.
- 후보 탐색은 제한돼 있습니다. guard는 군집 아래에 무언가 관측됐다는 뜻일 뿐 스펙트럼이
  완전하다는 뜻이 아닙니다. 군집 식별에 의존하기 전에 더 큰 `search_modes` 두 개로 반복하세요.
- 표본 overlap으로 표본 사이 동작을 인증할 수 없습니다. 파장 간격을 줄여 확인하세요. 식별은
  표본에서의 장 연속성입니다. 군집 사이 회피 교차 근처에서 큰 간격은 장의 성격(diabatic)을, 작은
  간격은 순간 고유벡터(adiabatic)를 따릅니다. 추적기가 둘 중 어느 의미인지 대신 정하지 않습니다.
- 예제의 원형 코어는 비정형 메시의 정사각형 PEC 상자 안에 있어 HE11 쌍이 n_eff로 약 4e-6
  갈라집니다. 이는 수치적 분리이며 물리적 분리가 아닙니다.
