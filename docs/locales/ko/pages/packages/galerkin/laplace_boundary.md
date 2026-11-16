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

### 불변 parametric corner 기하

`galerkin.laplace_corner_geometry.prepare_two_ground_corner_panels`는 명시적
corner 기저의 기하를 준비한다. 입력 polygon과 rectangle `width`/`height`는
미터 단위다. 기존 두-ground 볼록·분리·내부·측벽거리 조건을 재사용하고
polygon을 CCW로 정렬한다. `panels_per_edge`는 16–512의 짝수다. 각 edge
양끝의 첫 cubic 구간 4개를 각각 하나의 정규 power 패널로 합치므로 실제
패널 수는 edge당 `panels_per_edge-6`이며 총 8192개 이하로 제한한다.

```python
from galerkin.laplace_corner_geometry import prepare_two_ground_corner_panels

g = prepare_two_ground_corner_panels(
    [[[.0038, .0008], [.0042, .0008], [.0042, .0012], [.0038, .0012]]],
    width=.008, height=.002, panels_per_edge=32,
)
print(g.panel_count, g.lengths_m)
```

`CornerPanelGeometry`는 정규 anchor, 작은 local start, 직접 계산한 변위,
지수, 도체 owner, CCW face 번호와 공통 끝점 ID를 불변 배열로 반환한다.
정규 좌표에 `length_unit_m`를 곱하면 미터다. 밀도는
`anchor+local_start`에서 시작해 변위 방향을 따르며, edge 양끝의 지수는
`pi/(2*pi-interior_angle)`, 나머지는 1이다. Edge 반대쪽 절반도 해당
꼭짓점으로부터 작은 cubic 좌표를 계산하므로 1에 가까운 수를 빼지 않는다.
짧은 변위를 큰 절대 끝점 두 개의 차로 만들지 않는다.

정규 width/height, 파생 start/end 및 물리 길이도 제공한다. 끝점 ID는
해당 snapshot 안에서만 의미가 있다. 미해상 edge·corner 지수·패널 길이는
명시적으로 거부한다. 정사각형·정삼각형·직각삼각형의 해석각, polygon
coverage/면적·길이합, 반사·배율, 입력/출력 불변성을 검증한다. 이 함수는
행렬을 구성하거나 field/전류손실 수렴을 입증하지 않는다. 기존 상수패널
솔버의 개별 패널 제한과 기본값은 그대로이며 이 기하 예산으로 확대되지
않는다.

### 모서리 밀도의 반공간 행렬

`galerkin.laplace_corner_assembly.assemble_corner_half_space`는 모서리 기하
생성 함수와 같은 다각형, 미터 단위 사각형 크기 및 세분 수를 받는다.
불변 기하와 접지선 `y=0` 위의 Green 커널
`0.5*log1p(4*y_target*y_source/distance_squared)`에 대한 거친/세분 원행렬을
반환한다. 원천과 관측 패널 모두 정규화한 거듭제곱 또는 상수 밀도로
적분한다. 사각형은 기하 허용 조건과 정규화에 쓰이며, 위쪽 평면과 옆 벽의
보정은 이 원시요소에 포함하지 않는다.

```python
from galerkin.laplace_corner_assembly import assemble_corner_half_space

half = assemble_corner_half_space(
    [[[.0038, .0008], [.0042, .0008], [.0042, .0012], [.0038, .0012]]],
    width=.008, height=.002, panels_per_edge=16,
)
print(half.matrix.shape, half.quadrature_error, half.reciprocity_error)
```

멀리 떨어진 상수 패널의 작은 상대 거리는 네 좌표 성분의 float64 보정합으로
먼저 만든 뒤 구적점 변위를 더한다. 플랫폼별 확장 정밀도에 의존하지 않는다.
고정 6/8점 Gauss 구적과 거듭제곱 적분 원시요소의 자체 세분 규칙을 사용한다.
정규화한 행렬 세분 오차와 평균 전 원상호성 오차가 각각 `1e-10` 이하여야
하며, 유한하지 않거나 미해결인 결과는 `ValueError`로 거절한다. 반환 배열은
평균으로 상호성 증거를 지우지 않는다.

독립 60/80자리 직접 2차원 적분은 공통 모서리, 분리된 거듭제곱 및 상수
항목과 짧은 원거리 패널의 상쇄 사례를 검사한다. 수평 이동·반사, 물리 배율,
양의 Green 에너지 및 불변성을 별도로 검사한다. 이는 적분 검증이며 패널·외곽
수렴이나 전체 장 정확도 보장이 아니다. 기존 솔버의 한도·기본값을 바꾸지
않으며 브라우저 또는 Windows 검증 완료를 뜻하지 않는다.

### 범위가 명시된 조밀 행렬 잔차

`galerkin.dense_residual.bounded_dense_residual(A, x, b)`는 Dekker 곱의
상위·하위 성분과 `math.fsum`을 사용하여 `b - A @ x`의 새 float64 배열을
계산한다. 일반 행렬곱의 반올림으로 잃을 수 있는 곱·합의 비트를 보존한다.
방정식을 풀거나 바꾸지 않으며 입력을 수정하지 않는다. 확장 정밀도 dtype은
필요하지 않다.

```python
from galerkin.dense_residual import bounded_dense_residual

r = bounded_dense_residual(
    [[1.0, 1.0, 1.0]], [[2.0**53], [1.0], [-2.0**53]], [[0.0]],
)
assert r[0, 0] == -1.0
```

입력은 float64로 변환하는 유한 실수이며 서로 맞는 2차원 배열이어야 한다.
행렬의 행·열은 각각 1–8192, 우변 열은 1–16이다. 행렬·해의 0이 아닌
절댓값은 양 끝을 포함하여 `2**-400`부터 `2**400`, 우변 절댓값은
`2**900` 이하로 제한한다. 이 범위는 분해와 0이 아닌 곱 전개의 중간값을
정규·유한 부동소수점 범위 안에 두며, 밖의 입력은 `ValueError`로 거절한다.
행 블록으로 임시 메모리 크기를 제한한다. 정확 이진 유리수 곱·합 참조,
상쇄 사례, 열 순서 변경과 경계값 검사가 산술의 근거다. 실제 6072행
행렬 대조는 작은 단위 검사와 별도로 기록한다. 잔차는 조건수나 해 오차,
장 수렴의 보증이 아니다. 기존 솔버·검사는 바꾸지 않으며 이 원시요소만으로
보정된 장 또는 다른 플랫폼의 검증 완료를 뜻하지 않는다.

## 정규화된 power/constant 반공간 적분

`galerkin.laplace_half_space.power_constant_half_space(first, second, offset,
exponent, height=...)`는 정규 power target 밀도 `p*u**(p-1)`와 constant
source 밀도에 대해 바닥 접지 Green kernel `log(image_distance / distance)`의
평균을 계산합니다. `1/(2*pi)` 인자는 포함하지 않습니다. Target은
`(0,height) + u*first`, source는 `(0,height) + offset + v*second`이며
`u,v` 범위는 `[0,1]`입니다. 벡터와 높이 단위는 m입니다.
불변 `HalfSpacePanelIntegral`은 `green_mean`, `coarse_green_mean`,
`quadrature_order`, `refinement_error`를 보존합니다.

```python
from galerkin.laplace_half_space import power_constant_half_space

mean = power_constant_half_space(
    [0.001, 0.0], [0.001, 0.0], [0.001, 0.0], 0.625, height=0.002,
)
assert mean.refinement_error <= 1e-12
```

지수는 `(0.5,1]`, 길이비는 최대 `1e6`이고 모든 끝점은 접지 위에 있어야 합니다.
분리된 선분이나 끝점 접촉만 받으며, 정확한 이진 입력의 위상으로 겹침과 내부
교차를 거부하고 좌표를 맞춰 붙이지 않습니다. 최대 길이·offset/image norm·시작
높이를 scale로 삼고, 각 패널 길이와 끝점 높이는 그 scale의
`128*binary64_epsilon` 이상이어야 합니다. 실수가 아니거나 유한하지 않거나
표현할 수 없는 입력도 거부합니다.

Constant source는 해석적으로 적분합니다. 고정 target 차수 64/128은
`1e-12*max(1,abs(fine))` 이내에서 일치해야 하며 각 규칙의 mass 오차는
`1e-12` 이하여야 합니다. 정확한 0차 moment를
`f(0) + sum(w*(f(u)-f(0)))`로 분리하며 가중치를 재조정하지 않습니다.
먼 image/source 로그에는 안정적인 log-ratio와 유계 급수의 차를 사용합니다.
이 영역의 정확한 Green kernel은 엄밀히 양수이므로 상쇄로 0이나 음수가 나온
평균은 거부합니다. Fallback·clipping은 없으며 작은 평균의 상대 정확도를
보장하지 않습니다.

mpmath 1.3.0(BSD-3-Clause)의 독립 직접2D 적분을 60/80자리로 확인한 고정 참조
6개는 끝점 접촉·근접·경사·양방향 길이비 4000을 포함합니다. 반사·source 반전·
물리 배율·constant 밀도 상호성·접지에서의 이동·가중치 보존·입력 거부를 별도로
검사합니다. 적분 원시요소의 검사이며 완전한 장 해·메시/외곽 수렴·다른 플랫폼·
실측 검증을 뜻하지 않습니다.

## Power 패널의 계층적 선형 모드

`galerkin.laplace_corner`의 `power_panel_linear_gram(length, exponent)`와
`power_panel_linear_self_log(length, exponent)`는 한 패널 위 두 모드의 불변
2×2 행렬을 반환합니다. `h=length`, `u=s/h`, `p=exponent`일 때 정의는 다음과 같습니다.

- `phi0 = p/h * u**(p-1)`: 적분 mass는 1입니다.
- `phi1 = sqrt(p*(p+2)) * ((p+1)/h*u**p - phi0)`: 적분 mass는 0입니다.

행·열 순서는 `[phi0, phi1]`입니다. `h`는 m 단위의 유한 양수이고 `p`는
`(0.5,1]`이어야 하며 이 범위에서 두 모드의 제곱 전류가 적분 가능합니다.
Gram 단위는 `1/metre`, self 적분의 kernel은 `log(abs(s-t) / 1 metre)`이며
self 행렬은 무차원입니다. 다른 모드의 mass가 0이므로 self의 00 항만
`log(h)`에 의존합니다. 공통 digamma·길이 항을 먼저 해석적으로 소거합니다.
표현할 수 없는 Gram 항은 거부합니다. `p=0.5`에 가까우면 current Gram의
조건수가 커집니다. 유한한 항만으로 상쇄하는 이차형식이나 장 해의 정확도를
보장하지 않습니다.

`p=1`은 정규 constant 모드와 첫 shifted Legendre 모드입니다. Gram은 `I/h`,
self 행렬은 `[[log(h)-1.5, 0], [0, -0.75]]`입니다. 기존 스칼라 함수가
00 항을 그대로 제공하며 기존 constant/power basis나 솔버는 바꾸지 않습니다.
패널 간 상호작용과 완전한 선형 Galerkin 장 모델은 별도 구현·검증이 필요합니다.

독립 직접1D 제곱밀도·2D Duffy 로그 적분을 mpmath 1.3.0(BSD-3-Clause)으로
60/80자리에서 대조했습니다. `0.5001`과 uniform 한계를 포함한 지수 5개가
대상입니다. Uniform 교차항의 정확한 0을 보존하고, 0이 아닌 참조항은
분모 floor 없이 비교합니다. 물리 배율·양정 Gram 에너지·모드 moment·uniform
정확 분할도 검사합니다.

## 두 접지면 사이의 명시 all-active corner 장 계산

`galerkin.laplace_two_ground.solve_two_ground_corner_rectangle_edges`는
**모든 도체가 활성 전압/전류 기저인 볼록 도체 1~2개**의 별도 균일매질 정적 솔버입니다.
기존 불변 `TwoGroundRectangleEdgesResult`를 반환합니다. 정전용량/유전율은 무차원,
직선 edge current Gram은 `1/metre`, 부호 있는 적분은 단위 전류 기준이며 아래·위
접지면을 따로 유지합니다. 기존 솔버를 대체하거나 고정접지 도체 선택기를 추가하지 않습니다.

```python
from galerkin.laplace_two_ground import solve_two_ground_corner_rectangle_edges

result = solve_two_ground_corner_rectangle_edges(
    [[[0.00385, 0.0008], [0.00445, 0.0008],
      [0.00445, 0.00087], [0.00385, 0.00087]]],
    width=0.008, height=0.002, panels_per_edge=128, ground_modes=256,
)
```

사각 영역의 아래·위는 Dirichlet 접지, 옆은 Neumann 경계입니다. 기존 볼록·비접촉·내부
기하 및 cluster-옆벽 간격 조건을 유지합니다. 짝수 분할 `16..512`에서 각 끝의 cubic
구간 4개를 하나의 corner-power 패널로 합쳐 edge당 `n-6`개, 전체 최대 4096개를 씁니다.
모서리 지수는 `pi/(2*pi-interior_angle)`, 나머지 패널은 상수입니다. 해석 밀도 Gram이
적분 가능한 모서리 특이성을 유지합니다.

국소 상대좌표·안정적 근접 source 적분·정확 상수 moment·유계 배치로 바닥접지 행렬을
구성합니다. 위/옆 경계의 smooth 보정은 degree20/24를 비교하므로 `interpolation_degree`는
24만 받습니다. 고정 2회의 보정 잔차 계산 뒤 전류를 정규화하고 edge/whole Gram을 직접
계산합니다. 구적 가중치 재정규화나 대각 성분 기반 분모 floor는 없습니다.
`ground_modes`는 **실제 fine 모드 수**인 짝수 `64..4096`이며 절반의 모드 수와 비교하고
power 구적16/32도 비교합니다. 기존 솔버의 coarse 모드 수 의미와 다릅니다. 수치세분·상반성·
에너지·보존·partition·PSD는 `1e-10`, condition bound는 `1e10` 미만이며 미해결 입력은
`ValueError`로 거부합니다. 새 기하의 panel/outer 수렴은 별도로 확인해야 합니다.

독립 scikit-fem12.0.2(BSD-3-Clause, 비배포) P3 volume-energy 참조는 각 기하의 두 mesh,
정확 triangle-bubble condensation, 내부 velocity extension 두 개, 구적8/10을 사용합니다.
평행판 해석 anchor의 정전용량/shape-current Gram은 `1e-10`으로 검사했습니다.
저장 참조·출처는 `tests/galerkin/two_ground/evidence/corner-field-*.json`에 있으며 replay
시험이 독립 솔버를 다시 실행하지는 않습니다. 작은 부호 있는 교차항도 각 항 그대로 비교합니다.

| 선택 기하, 영역8×2mm | 독립 참조 DOF | 최종 panel whole 변화 | whole 반사 변화 | fine 참조 whole 차이 |
|---|---:|---:|---:|---:|
| 편심 사각 하나 | 265878 / 422727 | 0.009256% | 6.98e-16 | 0.006748% |
| 비대칭 사다리꼴 쌍 | 746444 / 914228 | 0.098622% | 2.12e-11 | 0.265163% |

등록 기준은 참조 mesh·최종 panel `256→512` 변화1%, 외곽폭 `8→16→32mm`의 각 변화1%,
정전용량 참조0.05%, edge 참조2%, whole 참조1%, 반사`1e-10`입니다. 외곽 경우의 fine
Fourier 모드는 각각256/512/1024개입니다. 쌍의 이전441197→746444DOF 참조는 whole mesh
1.127808%로 1% 기준에 실패했습니다. 그 실패는 후속 참조 mesh 쌍 수락과 구분하여 보존합니다.

제한된 수치 근거이며 일반 정확도·실측 수락이 아닙니다. 3활성도체는 whole 참조 mesh 수렴,
2신호+고정접지도체는 whole 반사에 실패하여 이 솔버의 지원범위에 포함하지 않습니다.
이종매질 경계 모서리·유한금속 확산·재료법칙·다른 플랫폼·브라우저 메모리 한계는 별도입니다.
구현 helper 모듈은 패키지 내부용입니다.

## 계층 선형 원거리 상호작용

`galerkin.laplace_corner.power_panel_linear_far_log`는 선형 self/Gram 원시 함수와
같은 `phi0`·`phi1`의 변경 불가능한 세분/기준 2×2 로그 거리 블록을 반환합니다.
첫 패널 원점은0, 둘째는 명시 offset이며 벡터 길이는 m입니다. 지수는(0.5,1],
길이비는64 이하, 원점 offset 크기는 두 패널 길이 합의 네 배 이상이어야 합니다.
유계 원거리 원시 함수이며 근접·접촉 블록과 전체 선형 전류 솔버는 범위 밖입니다.

모드의 해석적 질량은[1,0]입니다. 중심화한 `log1p` 차분으로 영질량 행·열에
`log(scale)`을 넣지 않으며 물리 구적 가중치를 재정규화하지 않습니다.
n/2n 차수(n=4..64)는 각 항에서1e-12*max(1,abs(fine)) 이내로 일치해야 합니다.
이는 무차원 구적 조건입니다. 공통 기하 배율의 log(scale)은00항에만 더해지고
두 패널을 교환하면 블록을 전치합니다. 어느 항등식도 전류 장 수렴을 확정하지 않습니다.

독립 복소 Taylor 급수100항 기준8개는 해석적 모멘트
mu0(r)=p/(p+r), mu1(r)=sqrt(p(p+2))*r/((p+r)*(p+r+1)), mpmath1.3.0의60/80자리와
rho<=1/4에서 나머지 상한16*rho^101/(101*(1-rho))를 사용합니다. 기준 도구는 배포하지
않습니다. 서로 다른 지수·길이와 끝점 지수·방향을 포함하며 입력 거부·불변성·교환·
반사·배율 시험을 유지합니다. 기존 상수 power·반공간·장 경로는 그대로입니다.

## 계층 선형 공유 꼭짓점 상호작용

`power_panel_linear_shared_vertex_log`는 원거리 원시 함수와 같은 두 모드 및 변경
불가능한 세분/기준 블록 결과를 사용합니다. 두 벡터는 같은 원점에서 시작하며 m 단위,
겹치지 않는 ray여야 합니다. 길이비는64 이하, 각 지수는(0.5,1]입니다. self·원거리
블록을 보완하며 떨어진 근접 패널과 전체 선형 장 솔버는 별도 미완료 범위입니다.

벡터를 최대 길이로 나눈 뒤 r,s∈{0,1}의 가중 모멘트에 Duffy 분할을 적용하면

`J_rs - M*log(scale) = (p*E_q[v^s*log|a-v*b|] + q*E_p[u^r*log|u*a-b|] - M)/T`,
여기서 `T=p+q+r+s`, `M=p*q/((p+r)*(q+s))`입니다.

반지름 방향 로그는 해석적으로 적분하고 남은 각도 함수를 정규화 Gauss-Jacobi로
적분합니다. 계산된 질량으로 가중치를 나누지 않습니다. 네 모멘트에 두 모드 다항식을
적용하고 해석적 질량[1,0]에 따라00에만 log(scale)을 더합니다. n/2n(n=4..64)은 각 항의
기존 무차원 구적 조건1e-12*max(1,abs(fine))을 만족해야 합니다. 기하가 허용되어도
요청 차수에서 해결되지 않을 수 있으며 자동 재시도·대체법은 없습니다. 보존한 길이비64
예는32/64에서 거부되고 호출자가 명시적으로64/128을 선택했을 때 통과합니다.

길이가 같은 반대 공선 p=q=1에는 독립 폐형식
`[[log(h)+2log(2)-3/2, 2sqrt(3)*(1-log(2))/3], [same, 5/4-2log(2)]]`이 있습니다.
저장한60/80자리 적응형 각도 적분 기준6개로 다른 지수·길이·각도도 검사합니다.
이 기준은 같은 수학적 Duffy 분할을 사용하지만 유한 Gauss-Jacobi 대신 적응형 적분을
쓰며 독립 전체 장 솔버가 아닙니다. 교환·반사·기하 배율·상수 모드 호환·결과 불변성도
따로 검사합니다. 기존 전류 솔버 기본값·물리 기하·수락 조건은 바꾸지 않습니다.
### 선형 블록 참조의 재현 가능한 출처

[원거리 기록](../../../../../../tests/galerkin/reference_values/mpmath/linear_far_log.json)과
[공유 꼭짓점 기록](../../../../../../tests/galerkin/reference_values/mpmath/linear_vertex_log.json)은
stored-reference v1 계약을 사용합니다. 명시적 소비자는 이 기록에서 입력을 만들고,
모든 binary64 값이 기존 raw fixture와 같은지 확인한 뒤 원래의 무차원 원시 기준을
적용합니다. 기존 fixture·시험·요청 차수 거부는 그대로 유지합니다.

같은 디렉토리의 해시 고정 mpmath 1.3.0 requirements는 참조 재현 전용이며 런타임
의존성이 아닙니다. 수정하지 않은 BSD-3-Clause wheel을 제품 모듈을 불러오지 않는
별도 환경에서 실행합니다. 비교 전용 스크립트는 60·80자리에서 모든 항을 다시
계산하고 배열별 차이를 출력한 뒤 임시 출력을 지웁니다. fixture를 덮어쓰는 기능은
없습니다. 참조 환경에서 저장소 루트를 기준으로 실행합니다.

```bash
python tests/galerkin/reference_values/mpmath/compare_linear_logs.py far
python tests/galerkin/reference_values/mpmath/compare_linear_logs.py vertex
```

새 기록의 시간은 기존 생성 시각이 아닌 이번 재현 측정입니다. 기록하지 않은 CPU
모델·컴파일 시간·상주 메모리는 이유와 함께 null로 둡니다. 저장값 소비자는 현재
참조 실행 시간을 주장하지 않습니다. 이는 수학 원시 비교이며, 꼭짓점 참조는 Duffy
항등식을 공유합니다. 어느 기록도 장 수렴·물리 정확도·다른 플랫폼 지원의 근거가
아닙니다.

### 분리된 계층 선형 power 블록

`power_panel_linear_separated_log(first, second, offset, p, q,
quadrature_order=32)`는 두 선분의 최소 간격이 긴 선분 길이의 절반 이상이고,
지수는(0.5,1], 길이비는64 이하인 비접촉 경우를 다룹니다. 첫 선분은 원점에서
`first`까지, 둘째는 `offset`에서 `offset+second`까지이며 단위는 m입니다.
정규화한 방향도 표현 가능해야 합니다. self·vertex·far 블록과 같은 물리 모드와
불변 fine/coarse 2x2 결과를 쓰는 별도 API입니다. 기존 허용 범위를 바꾸거나
해법을 자동 선택하지 않습니다.

각 영질량 모드는 기준점을 뺀 로그 차이를 사용합니다. 기준 벡터 b와 증분 d에 대해
`log1p((2*b.dot(d)+d.dot(d))/(|b|*(|b+d|+|b|)))`로 거리 로그의 차이를
평가합니다. 혼합 블록은 적분 전에 대응하는 단일변수 기준값을 뺍니다. 물리 구적
가중치는 그대로 두고 해석적 질량[1,0]에 따라 log(scale)은00에만 더합니다.
명시한 n/2n, n=4..64 규칙에 원래의 무차원 항별1e-12*max(1,abs(fine)) 비교를
유지합니다. 요청 차수가 미해결이면 재시도 없이 거부합니다. 이보다 가까운 선분과
다른 끝점에서 접하는 선분은 여전히 별도 계약이 필요합니다.

길이가 같은 평행 단위지수 선분의 간격이 길이의 h배이면, 독립적인 차이좌표 합성곱은
`I00=log(length)+J0-J1`, `I01=I10=0`, `I11=J0-3*J1+2*J3`을 줍니다.
여기서 `Jk=integral_0^1 t^k*log(t^2+h^2) dt`입니다. k=0,1,3의 폐형 원시함수로
h=.5/1/2, 길이2^-15/1/2^15를 검사합니다.
[저장 직접적분 기록](../../../../../../tests/galerkin/reference_values/mpmath/linear_separated_log.json)은
서로 다른 지수·길이·각도 다섯 사례를 확인합니다. mpmath1.3.0 구현은48/64점,
60/80자리의 직접 텐서 Gauss-Jacobi 적분입니다. Gaussian 계열은 공유하지만 제품의
중심화나 제품 코드 import는 사용하지 않습니다. 차수 차이1e-25 미만과 정밀도 차이
1e-45 미만은 참조 자체 점검이며 장 수렴 근거가 아닙니다. 같은 디렉토리의 비교 전용
생성기와 해시 고정 requirements로 다섯 배열을 재현합니다.

교환·좌표축 부호변환·물리 배율·상수 모드 호환성·far API와 겹치는 범위·불변 출력·
명시적 거부를 별도로 검사합니다. 이 원시 블록만으로 전체 선형 경계 장 솔버·전류
분할·고정 접지 어댑터가 검증된 것은 아닙니다.

### 선형 power/constant 끝점 상호작용

`power_panel_linear_constant_log(a, b, offset, exponent)`는 power 대상과 단위지수
소스 사이의2x2 블록을 제공합니다. 대상은 원점에서 a까지, 소스는 offset에서
 offset+b까지이며 평면 좌표 단위는 m입니다. 양쪽 모두 두 물리 모드를 갖고,
정규화 좌표에서 소스 모드는1과sqrt(3)*(2v-1)입니다. 대상 지수는(0.5,1], 길이비는
1e6 이하입니다. 입력 binary 값의 정확한 위상으로 비접촉과 공통 끝점을 허용하고,
겹침·내부 교차는 거부합니다. 정규화 방향과 소스 좌표도 표현 가능해야 합니다.
자기 상호작용은 별도 해석적 self API를 사용합니다.

소스의 첫 다항 모멘트는
`F(z)=Re[z+1/2-z*(z+1)*(log(z+1)-log(z))]`이며 F(0)=1/2, F(-1)=-1/2입니다.
|z|>2에서는 상쇄를 피하려고
`sum_k>=1 (-1)^(k+1)/((k+1)*(k+2)*z^k)`의48항을 사용합니다. 빠진 절대 나머지는
1.5e-18 미만입니다. 물리 소스 모드에는sqrt(3)을 곱합니다. 모드0에는 기존의 정확한
constant-source 로그 적분을 사용합니다.

고정 cubic-coordinate64/128 규칙으로 대상을 적분합니다. 해석적 질량[1,0]에 따라
log(source_length)는00에만 더하고, 영질량 대상 모드는 적분 전에 대상 원점에서의
소스 모멘트를 뺍니다. 계산된 구적 가중치는 재정규화하지 않습니다. 대상 질량 오차와
각 정규화 fine/coarse 차이는 원래1e-12 원시 기준을 유지합니다. 대상 내부를 마주보는
짧은 소스는 미해결일 수 있습니다. 대상[0,1], 시작점(.5,.001), 길이1/64·1e-3·1e-4의
등록 사례는 거부합니다. 재시도나 모든 근접 상호작용의 정확도를 보장하지 않습니다.

[저장 adaptive 기록](../../../../../../tests/galerkin/reference_values/mpmath/linear_power_constant_log.json)은
소스 첫 모멘트11개를 직접80자리 구적으로, 전체 블록7개를60/80자리로 비교합니다.
소스 항등식은 공유하는 수학입니다. 전체 참조는 power 측도를 평탄화한 뒤 별도
adaptive 대상 적분을 사용합니다. 처음 z=-.3+.01j에서 구간을 나누지 않은 소스
구적은1e-50 항등식 기준에 실패했습니다. 가장 가까운 투영점 주위에서 분할한 별도
계산은 기준을 바꾸지 않고 통과했습니다. 비교 전용 생성기는 이 이력을 보존하고,
같은 디렉토리의 해시 고정 mpmath1.3.0 환경을 요구합니다.

소스 방향을 뒤집으면 소스의 선형 모드 부호만 바뀝니다. 대상에도 같은 규칙을
적용할 수 있는 것은 단위지수일 때뿐입니다. 일반 power 패널을 뒤집으면 특이점
위치가 바뀌므로 같은 입력이 아닙니다. 독립 끝점 항등식·shared-vertex/far와 겹치는
범위·상수 모드 호환성·좌표축 부호변환·배율·단위지수 상반성·불변 출력·미해결 입력
거부를 검사합니다. 이 원시 검사는 전체 선형 장 조립·고정 접지 정확도·플랫폼 지원의
근거가 아닙니다.

### 자기항과 제곱 밀도 참조 출처

[저장 self/Gram 기록](../../../../../../tests/galerkin/reference_values/mpmath/linear_self_gram.json)은
기존 지수·길이 다섯 사례를 측도를 제거한 직접 Gram 적분과 Duffy self-log 적분으로
60/80자리에서 재현합니다. 균일 모드 참조의 미소 비영 교차항까지 열 개 binary64
배열이 기존 raw fixture와 같습니다. 소비자는 기존 비영 항의 엄격한 상대1e-12와
균일 모드의 정확한 영값·참조 교차 모멘트1e-30 검사를 유지합니다. 분모 하한이나
수치 클리핑을 추가하지 않습니다. 같은 디렉토리의 비교 전용 생성기는 해시 고정
mpmath1.3.0 참조 환경을 사용합니다. 새 측정 기록은 이번 재현만 설명하고, 기록하지
않은 CPU·RSS·컴파일 메타데이터는 null로 둡니다. 런타임·raw fixture·기존 시험·
판정 기준은 바뀌지 않습니다.

### 분할 혼합 선형 power 블록

`galerkin.laplace_corner_partitioned.power_panel_linear_constant_log_partitioned`는
power 표적과 단위 지수 원천의 질량1·질량0 선형 모드를 적분하는 명시적 별도 방식입니다.
기존 `(0.5, 1]` 지수, 최대1e6 길이비, binary 입력의 정확한 교차 판정을 유지하며,
기존 비분할 방식의 실패를 재시도하거나 그 방식을 수정하지 않습니다.

원천 끝점의 투영은 표적 매개변수 적분 구간만 정합니다. 거리의 두 배 간격과
특이 원점 밖 upper/lower<=2 세분으로 밀도 변화를 제한합니다. 최대128구간에 고정
64/128 양끝 cubic 규칙을 사용하며 첫 구간은 정확한 power 측도, 나머지는 물리적
power 밀도를 유지합니다. 기하·물리적 가중치·결과 모멘트를 정규화·스냅·클리핑하지
않습니다. 해석적 질량[1,0]과 항별 coarse/fine 차이의1e-12 검사를 유지하고 예산 초과나
미해결 상호작용은 명시적으로 거절합니다. 결과는 변경 불가능한
`mean_log_distance`, `coarse_mean_log_distance`, `quadrature_order`,
`subintervals`, `mass_error`를 제공합니다.

[저장 adaptive 참조](../../../../../../tests/galerkin/reference_values/mpmath/linear_partitioned_log.json)는
승인된 패널 기하 상호작용 두 개와 국소 짧은 원천 아홉 사례를 포함합니다.
별도 mpmath1.3.0/BSD-3-Clause 과정은 제품 dyadic 구간 대신 측도를 평탄화한 표적
좌표에서60/80자리 adaptive 적분을 수행합니다. 정확한 원천 항등식은 수학을 공유하고
첫 두 입력은 제품 기하에서 왔습니다. 인접 비교 전용 생성기는 기록을 덮어쓰지 않으며
미측정 비용을 명시합니다. 기존 비분할 거절·raw fixture·기준·솔버는 바뀌지 않습니다.
이 원시 계산만으로 전체장 수렴이나 다른 플랫폼 정확도를 입증하지 않습니다.

### 두 모드 모서리 half-space 조립

`galerkin.laplace_corner_linear_assembly.assemble_linear_corner_half_space`는
접지선 y=0 위의 볼록 도체 경계에 대해 영상항-실제항의 무차원 원행렬을 반환합니다.
기존 직사각형 기하 허용 조건과 미터 단위를 재사용하며 위쪽 접지면·측벽의 장은
포함하지 않습니다. 직사각형 크기는 기하 허용과 정규화에만 사용됩니다.

물리 패널마다 밀도 모드 두 개가 교차 배치됩니다.2*i는 질량1,2*i+1은 질량0인
선형 모드입니다. 정확한 자기항·공유 원점·분리·명시적 분할 혼합 블록이 물리 가중치를
유지합니다. 단위 지수 원천을 끝점 기준으로 뒤집으면 선형 모드 부호도 바꾸며,
비단위 특이점을 뒤집지 않습니다. 기존 혼합 방식의 실패를 감지해 재시도하지 않습니다.
양방향 패널 쌍을 계산하고 호출자의 대칭 평균 전에 원 상호성·세분1e-10을 검사합니다.
출력과 기하 스냅샷은 변경 불가능합니다. 짝수16..512 모서리 분할은 모서리당 n-6
물리 패널이 되지만, 이 밀집 행렬 방식은 최대512 물리 패널(1024밀도 모드)만 허용하고
초과 시 행렬을 할당하기 전에 거절합니다.

정사각형·삼각형·서로 다른 사다리꼴에서 P0 부분공간, 양의 Green 에너지, 물리적
단위 배율, 수평 반사, 도체 순서를 검증합니다.
[저장 일곱 블록 참조](../../../../../../tests/galerkin/reference_values/mpmath/linear_half_space.json)는
공유 일반 끝점의 선형 원천 부호를 포함합니다. 별도 mpmath1.3.0/BSD-3-Clause 과정은
48/64점·60/80자리 직접 적분을 비교합니다. 저장 기하는 제품에서 왔으며 자기항·원천·
Duffy 항등식은 수학을 공유합니다. 비교 전용 생성기는 기존 참조값을 유지합니다.
행렬 검사만으로 양 접지면 전체장·전류 수렴·다른 플랫폼 동작을 입증하지 않습니다.
기존 솔버와 수치 기준은 바뀌지 않습니다.
