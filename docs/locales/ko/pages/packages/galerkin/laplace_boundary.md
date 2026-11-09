# 균질 Laplace 경계 패널

[English](../../../../../packages/galerkin/laplace_boundary.md) | **한국어**

`galerkin.laplace_boundary.solve_grounded_rectangle`는 균질 2차원 직사각형 안의
닫힌 등전위 도체를 푼다. 바닥은 접지이고 양옆과 윗면의 법선 플럭스는 0이다.
[체적 정전기 API](electrostatics.md)와 함께 명시적으로 선택하는 경계 API이다.

## 입력과 예제

```python
import numpy as np
from scipy.constants import epsilon_0
from galerkin.laplace_boundary import solve_grounded_rectangle

trace = 1e-3 * np.array([[1.05, .2], [1.15, .2], [1.14, .24], [1.06, .24]])
result = solve_grounded_rectangle(
    [trace], width=2.4e-3, height=1e-3, panels_per_edge=32,
)
capacitance_f_per_m = epsilon_0 * result.capacitance_per_permittivity
print(capacitance_f_per_m)
```

좌표·`width`·`height`는 m이다. `height`는 직사각형 전체 높이로, 외부에서
다른 모델과 조합할 때 기판 두께도 포함한다. 이 커널 자체에는 적층 재료가 없다.
다각형은 암시적으로 닫히며 마지막에 시작 꼭짓점을 반복하지 않는다. 양방향을 받는다.

| 입력 | 계약 |
|---|---|
| `polygons` | 유한 실수 `(n,2)` 배열 1–16개의 list/tuple. 각 경계는 꼭짓점 3개 이상의 단순하고 엄격히 볼록한 다각형. 일직선 변·접촉·겹침·포함·두께 0·벽 접촉은 거부. |
| `width`, `height` | 유한 양의 실수, 폭/높이는 `[0.25,4]`. |
| `panels_per_edge` | 정수 1–256, 기본 32. 전체 패널 최대 2048개. 각 변 끝을 cubic 분포로 세분. |
| `interpolation_degree` | 정수 10/12/14/16 중 하나, 기본 10. degree−2와 요청한 차수를 비교하며 자동 변경하지 않음. |
| `ground_modes` | 정수 64–4096, 기본 512. 두 배의 cosine 모드와 비교하고 세분 결과 반환. |

도체 전체 bounding box는 양옆·윗벽에서 자신의 최대 길이 이상 떨어져야 한다.
`max(width,height)`로 정규화한 변 또는 패널 길이가 `128*eps` 이하이면 거부한다.
Boolean 제어값, 유한하지 않은 좌표, 해상도가 부족한 계는 결과를 반환하지 않는다.
이는 해당 구현의 검증 범위와 비용 한계이며 Laplace 방정식 일반의 제한은 아니다.

## 결과·수식·검사

`RectangleBoundaryResult`는 변경 불가능한 스냅샷을 담는다.

| 필드 | 형태와 의미 |
|---|---|
| `capacitance_per_permittivity` | `(n,n)`, 균질 절대 유전율로 나눈 무차원 전하/전압 행렬. F/m 유전율을 곱하면 F/m 단위 길이당 정전용량. |
| `current_gram` | `(n+1,n,n)`, 1/m. 도체 `i`의 적분 전류를 1로 정규화한 `j_i*j_j`의 표면 적분. 입력 도체 순서 다음 접지 바닥. |
| `current_integrals` | `(n+1,n)`, 무차원. 도체에서 단위행렬, 접지에서 −1. |
| `panel_count`, `condition_bound` | 전체 패널 수, `1e10` 미만이어야 하는 무한대 노름 조건수 추정값. |
| `reciprocity_error`, `residual_error`, `current_error` | 원행렬/정전용량의 상대 상호성, 해 잔차, 절대 전류 보존 오차. 각각 `1e-10` 이하. |
| `matrix_refinement_error`, `ground_refinement_error` | 구적·보간·영상합 및 접지 Fourier·구적 세분 상대 변화. 각각 `1e-10` 이하. |

미지수는 상수 패널의 **총 전하**이다. 에너지 행렬은 source와 target 양쪽 패널에
걸쳐 Green 함수를 평균하여 상호성을 보존한다. 특이한 접지 반공간 항은 double-log
해석 적분을 사용한다. 동일 패널 평균은 `log(length)-3/2`이며 길이 차이가 큰
패널은 정규화한 1차원 source 원시함수와 세분 target 구적으로 상쇄를 피한다.
매끄러운 양옆·윗벽 영상 보정만 도체 영역의 tensor Chebyshev 기저로 보간한다.
바닥 전류 Gram 행렬은 cosine harmonic-measure의 Parseval 합으로 구한다.

`interpolation_degree-2`와 `interpolation_degree`를 구적 차수 6/8 및 확장 영상합으로
비교한다. 기본은 여전히 보간 8/10이다. 기본 차수에서 거부된 기하는 명시적으로
높은 차수를 요청하여 재평가할 수 있으며 `1e-10` 기준은 그대로이다. 영상 수는 직사각형 종횡비를
따른다. 접지는 `ground_modes`/`2*ground_modes`, 구적 6/8로 비교한다. 반올림
평균 전에 원행렬 상호성을 검사하고 양의 정부호 Cholesky 분해를 요구한다.
대각 jitter, 허용값 완화, 다른 모델로의 fallback은 없다.

**이 검사는 패널·외곽 수렴을 대신하지 않는다.** 접지에 대한 도체 좌표를 유지하고
`panels_per_edge`를 늘리거나 외곽을 확대하여 다시 계산해야 한다. 작은 대수 잔차가
물리적 이산화 오차의 상한은 아니다. 표면 인자만으로 주파수 의존 선로나 실측
정확도를 주장할 수 없다.

## 검증과 재현

저장소 루트에서 실행한다.

```sh
OPENPHYSICS_REQUIRE_CROSSCHECK=1 python -m pytest -q \
  tests/galerkin/test_laplace_panel_integrals.py \
  tests/galerkin/test_laplace_boundary.py \
  tests/galerkin/test_laplace_boundary_interpolation.py \
  tests/galerkin/test_crosscheck_skfem_laplace_boundary.py
```

- 독립 adaptive source/target 적분으로 self·인접·회전·근접·길이비 `1e8`까지
  `1e-10`을 검사한다. 회전·scale·교환·전류 보존·양의 에너지·입력 거부도 검사한다.
- 반지름 `a=.1 m`, 중심 높이 `h=.5 m`인 256변 원에서 `(W,H)`를 `(4,2)`부터
  `(64,32) m`까지 두 배씩 늘려 무한 접지 반공간 극한과 비교한다.
  `b=sqrt(h*h-a*a)`, 기준은 `C/eps=2*pi/acosh(h/a)`, 도체 Gram
  `h/(2*pi*a*b)`, 접지 Gram `1/(2*pi*b)`. 모든 오차가 감소하고 마지막이 `.005` 미만이어야 한다.
- 폭·두께가 다른 도체 쌍을 고정 외곽 3개에서 변당 32/64/128 패널로 검사한다.
  각 마지막 변화는 이전보다 작고, 정전용량 `.001`, 개별 표면 Gram `.005` 이하여야 한다.
- scikit-fem P2를 직접 실행하여 동일한 64변 도체·외곽의 체적장과 경계 mass를
  독립 조립하고 체적 크기 3개를 비교한다. 서로 다른 이산화이므로 **보고 전용**이며
  해석식·패널 수렴 기준을 대신하지 않는다. `OPENPHYSICS_CROSSCHECK_DIR`를 지정하면
  도구 버전·일치 조건·차이·시간을 저장한다.

런타임은 기존 NumPy/SciPy만 사용하며 scikit-fem은 시험 전용이다.
이 검사로 새 Windows/macOS·브라우저·JSON 문서·외부 재료·full-wave 지원을 확립하지 않는다.

4 m × 2 m 고정 외곽에 64변 원형 도체 3개를 둔 시험은 기본 차수를 의도적으로
거부한다. 8→10 변화가 약 `2.35e-10`이기 때문이다. 명시적 12/14/16 차수에서는
각 표면 Gram 행렬을 포함해 `1e-10` 이내로 일치한다. 기하를 유지한 세분이며
허용값 완화나 외곽 확대로 통과시킨 결과가 아니다.
