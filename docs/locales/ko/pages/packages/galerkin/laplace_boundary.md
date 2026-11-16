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

## 짧은 패널의 적분

길이가 다른 패널의 로그 적분은 기존 32/64점 검사를 통과한 값을 그대로
보존합니다. 실패한 항만 정규화한 국소 좌표에서 같은 적분을 다시 평가합니다.
큰 좌표 원점을 먼저 더하면서 짧은 타깃을 따라
이동하는 값이 반올림으로 사라지는 일을 피합니다. 기존 32/64점 일치 기준
`1e-12 * max(1, abs(mean_log_distance))`는 유지하며, 해상도가 부족한 적분은
계속 거부합니다.

저장된 독립 검증은 짧은 패널과 긴 패널 한 쌍을 두 소스 순서로 다룹니다.
mpmath 1.3.0의 60자리 및 80자리 직접 2차원 로그 거리 적분은 상대
`1e-30` 이내로 일치합니다. 끝점 반전, 원점으로 이동, 반사, 정확한 2배
스케일도 검사합니다. 이 검증은 산술 안정성에 한정하며 새로운 분할 방식,
보간 차수 또는 임의 도체 손실 정확도를 수락하지 않습니다. 기존 공개
기본값과 입력 제한을 유지합니다.

## 명시적 모서리 멱함수 패널 적분

`galerkin.laplace_corner`는 `0 < s < h`에서 정규 밀도
`phi(s) = p/h * (s/h)**(p-1)`의 수치 구성 요소를 제공한다. 길이 `h`의
단위는 m이고 특이 끝점은 `s=0`이다. 제곱 전류 적분이 발산하는 `p=0.5`를
제외하여 `0.5 < p <= 1`을 요구한다. 내부각 `alpha`인 볼록 금속 모서리의
균질 외부 Laplace 쐐기에서는 선도 지수가 `p = pi/(2*pi-alpha)`이다.
이 관계는 유전체 접합, 이방성 모서리 법칙, 유한 도전율 내부 확산을 포함하지 않는다.

```python
from galerkin.laplace_corner import (
    power_panel_gram, power_panel_self_log, power_panel_shared_vertex_log,
)

gram_per_m = power_panel_gram(1e-3, 2/3)
self_log = power_panel_self_log(1e-3, 2/3)
pair = power_panel_shared_vertex_log(
    [1e-3, 0.], [0., 1e-3], 2/3, 2/3,
)
print(gram_per_m, self_log, pair.mean_log_distance, pair.refinement_error)
```

정확한 자기 모멘트는 `p**2 / ((2*p-1)*h)`와
`log(h/1 metre) - 1/(2*p) - digamma(p+1) - EulerGamma`이다.
`p=1`이면 `1/h`, `log(h/1 metre)-1.5`로 환원된다.
`power_panel_quadrature(p, order)`는 `[0,1]`의 정규 측도
`p*u**(p-1) du`에 대한 불변 절점·양의 가중치를 반환한다. 4–128차에서
Golub–Welsch Jacobi 삼대각 행렬과 고유벡터 첫 성분의 제곱을 사용하며,
계산된 가중치 합으로 다시 나누지 않는다.

`power_panel_shared_vertex_log(a, b, p, q)`는 공통 꼭짓점으로부터의 유한하고
길이가 양수인 평면 변위 벡터를 m 단위로 받는다. 두 패널은 그 꼭짓점에서만
만나야 하며 길이비는 64 이하이다. 겹치는 반직선은 거부한다. 결과는
`log(distance/1 metre)`의 이중 가중 평균이다. Duffy 분할로 반지름 방향의
로그 적분을 정확히 처리하고 각도 항에 Gauss–Jacobi 적분을 적용한다.
명시적 성긴 차수는 4–64, 기본값은 32이며 두 배 차수의 값을 반환한다.
`abs(fine-coarse) <= 1e-12*max(1,abs(fine))`를 요구하고 미달하면
`ValueError`를 발생시킨다. 불변 결과는 두 값과 성긴 차수를 보존하며
`refinement_error`가 정규화 차이를 나타낸다. 비유한 입력, 표현 불가능한
Gram 값, 수렴하지 않은 적분을 거부한다.

검증은 `2*order-1`차까지의 정확한 다항 모멘트, 상수 패널 환원, 전류 스케일,
독립 mpmath 60/80자리 직접 이중 적분 네 사례와 순서 교환·회전·반사·길이
스케일을 사용한다. 저장 기준은
`tests/galerkin/two_ground/evidence/corner-panel-integrals.json`이며 런타임은
mpmath를 가져오지 않는다. 적분·참조 대조 기준은 `1e-12`, 두 참조 정밀도 간
일치 기준은 `1e-30`이다.

이 함수들은 명시적 적분 구성 요소이며 완성된 가중 패널 장 솔버가 아니다.
기존 경계 솔버·기본값·상수 패널 결과는 그대로 유지한다. 후속 장 구성은
조립 연산자, 전류, 재료 가정, 패널·외곽 수렴을 독립 검증해야 한다.
이 적분 검사만으로 일반 모서리 장, 작은 상호 손실 항, 다른 플랫폼의
정확도가 확보된 것은 아니다.

### 분리된 멱함수 패널

`power_panel_separated_log(first, second, offset, p, q)`는 0에서 `first`까지의
패널과 `offset`에서 `offset + second`까지의 패널 사이 이중 가중 로그 거리를
계산한다. 입력은 m 단위의 유한 평면 변위 벡터이다. 각 멱함수 밀도는 지정한
패널 시작점에서 시작한다. 비상수 밀도 패널을 뒤집으면 특이점이 이동하므로
이 연산은 불변식이 아니다.

길이비 64 이하, 최소 선분 거리가 긴 패널 길이의 절반 이상이어야 한다.
끝점 접촉·교차·중첩을 거부하고 벡터 노름과 적분 거리가 표현 가능해야 한다.
양의 tensor Gauss–Jacobi 적분은 명시적 성긴 차수 4–64(기본 32)와 두 배
차수를 비교하며 같은 `1e-12*max(1,abs(fine))` 기준과 불변 결과 필드를
유지한다. 좌표 정규화에서 길이 스케일의 로그를 해석적으로 분리하며 적분
가중치를 다시 정규화하지 않는다.

```python
from galerkin.laplace_corner import power_panel_separated_log

pair = power_panel_separated_log(
    [1e-3, 0.], [0., 1e-3], [2e-3, 2e-3], 2/3, .75,
)
print(pair.mean_log_distance, pair.refinement_error)
```

별도의 mpmath 60/80자리 직접 이중 적분 네 사례는 서로 다른 지수·길이의
평행·직교·비스듬한·동일 직선 위 분리 패널을 다룬다. 저장 자료는
`tests/galerkin/two_ground/evidence/corner-separated-integrals.json`이다.
참조·변환 `1e-12`, 참조 정밀도 간 `1e-30` 기준을 유지하며, 양의 가중치에
따른 거리 범위, 정확한 분리거리 허용 경계, 명시적 거부, 밀도 방향과 표현
가능한 길이 스케일도 검사한다. 일반 가까운 쌍, 다른 끝점 접촉 형태와
조립된 가중 장 솔버는 이 API 범위에 포함하지 않는다.

### Power 패널과 상수 패널 사이의 적분

`power_panel_constant_log(a, b, offset, p)`는 power 패널 `0 -> a`와 상수
패널 `offset -> offset+b` 사이의 가중 로그 평균을 구한다. 벡터 단위는
미터이며 `0.5 < p <= 1`, 길이비는 최대 `1e6`이다. 떨어진 패널과 하나의
공통 끝점 접촉을 허용한다. 중첩·내부 교차·비유한 입력·표현 불가능한
좌표는 거부한다. 교차 판정에는 입력 float의 정확한 유리수 표현을
사용하며 좌표를 임의로 맞추지 않는다. 상수 패널의 방향을 뒤집어도
밀도는 같지만 power 패널의 방향을 뒤집으면 일반적으로 밀도가 달라진다.

상수 source 선적분은 해석식으로 계산한다. 먼 거리 급수의 정규 로그
평균 절단오차 상한은 `1.5e-18` 미만이다. Power target에는 cubic 좌표
`u=t^3/(t^3+(1-t)^3)`, Jacobi 인자 `(2, 3*p-1)`과 해석적 밀도 정규화를
사용한다. 계산한 가중치 합으로 다시 나누지 않는다. 고정 64/128차 비교만
지원하며 가중치 합 오차와 정규 세분 오차를 모두 `1e-12` 이하로 요구한다.
미수렴 근접쌍은 자동 대체 없이 `ValueError`로 거부한다.
`PowerPanelLogResult`는 두 평균값과 낮은 차수 64를 보존한다.

```python
from galerkin.laplace_corner import power_panel_constant_log

pair = power_panel_constant_log(
    [1e-3, 0.], [1e-3, 0.], [1e-3, 0.], .625,
)
print(pair.mean_log_distance, pair.refinement_error)
```

독립 직접 2D 참조 5건은 시작/끝점 접촉, 근접 평행, 길이비 4000:1 및
1:4000을 다룬다. 직접 1D 참조 4건은 복소 source 좌표를 다룬다.
저장한 mpmath 60/80자리 결과는 `1e-30` 이내로 일치하며 실행 시 참조·변환
검사는 `1e-12`를 유지한다. 기록은
`tests/galerkin/two_ground/evidence/power-constant-integrals.json` 및 같은
디렉터리의 `constant-segment-log.json`이다. 해석적 밀도 모멘트, 상수 적분
닫힌식, 회전·반사·source 역방향·길이 배율, 1 ULP 간격/중첩 구분과 실제
근접쌍 미수렴 거부도 검사한다. 이 원시 적분만으로 가중 field 또는 전류
손실의 수렴을 입증하지 않으며 기존 경계 솔버를 변경하지 않는다.

반복 적분 요청은 프로세스별로 정규 power 규칙과 cubic 좌표 규칙을 각각
최대 128개 재사용한다. 조회 전에 입력을 검증하며 캐시된 노드·가중치는
불변 바이트 저장소를 사용한다. 규칙의 계산식·차수·정규화·수렴 기준은
그대로이며 field 행렬 구성 중 같은 고유문제를 반복해서 풀지 않는다.
