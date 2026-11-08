# meshloom — 정확 산술 컴파일 커널을 가진 사면체 메시 생성

[English](../../../../../packages/meshloom/overview.md) | **한국어**

[문서 홈](../../index.md)

**상태: 커널 구성 요소만 있고 메셔는 아직 없음.** meshloom은 여러 재료로 된 조각별 선형 입력을 위한
OpenPhysics의 일반 사면체 메셔가 될 패키지입니다. 정확 술어를 쓰는 제약 Delaunay 사면체 분할, 경계
복원, 품질 세분화, 메시 개선을 컴파일된 Rust 커널로 합니다. 커널에는 이제 첫 두 단계, 정확한 기하
술어와 점 집합의 Delaunay 사면체 분할이 있습니다(아래). 메셔를 위한 내부 구성 요소이며 아직 공개 API가
아닙니다. `generate3d`는 `NotImplementedError`를 냅니다.

```python
import meshloom
meshloom.kernel_available()   # 컴파일 커널이 로드되면 True
meshloom.kernel_version()     # 커널 버전, meshloom.__version__과 같음
```

meshloom이 메시를 만들기 전까지 적층 형상에는 [`meshine.extrude`](../meshine/overview.md#적층-사면체-메시)를,
다른 형상에는 [`gmshio`](../gmshio/overview.md)를 통한 Gmsh를 쓰세요. 합격 기준은
[사전 등록 3D 검증 계획](../meshine/validation3d.md)에 미리 고정했습니다. 출력은 `meshine.TetMesh`처럼
`galerkin.from_mesher`가 읽는 필드를 가질 것입니다.

## 커널 구성 요소

`meshloom._core`는 시험과 벤치마크를 위해 커널의 첫 단계를 감쌉니다. 메셔의 공개 API가 나오기 전에
이름이 바뀔 수 있습니다.

- **정확 술어.** `predicate_signs(kind, coords, ids=None)`는 `orient3d(a, b, c, d) = det[b − a, c − a, d − a]`,
  `insphere`(양의 방향 a, b, c, d를 지나는 구 안에 e가 있으면 양수), 그 기호 섭동 형태 `insphere_sos`,
  `incircle3d`(같은 평면의 d가 a, b, c를 지나는 원 안에 있으면 양수, 투영 없이 3D에서 계산)의 정확한
  부호를 돌려줍니다. Shewchuk의 오차 한계를 쓰는 부동소수점 필터가 대부분을 정하고, 나머지는
  부동소수점 expansion으로 정확히 계산합니다. 좌표는 0이거나 절댓값이 2⁻¹²⁰과 2¹²⁰ 사이여야 하며,
  이 범위에서는 정확 계산이 underflow·overflow하지 않습니다. 그 밖의 값은 `ValueError`로 거절합니다.
- **Delaunay 사면체 분할.** `delaunay(points, order=None)`는 양의 방향 사면체, 각 점에 대해 꼭짓점이 된
  같은 점의 번호(가장 작은 번호), 커널 카운터를 돌려줍니다. 한 구 위에 놓인 점들의 동률은 점 번호 순서의
  기호 섭동으로 끊으므로, 결과는 점과 번호에만 달려 있고 삽입 순서와 무관합니다. 점은 Hilbert 라운드를
  가진 편향 무작위 순서로 Bowyer–Watson 방식으로 넣습니다.
- **검증기.** `verify_delaunay(points, tetrahedra)`는 배열만 보고 정확 술어로 확인합니다. 모든 사면체가
  양의 방향인지, 모든 내부 면이 섭동 아래 국소 Delaunay인지, 껍질이 국소 볼록인지, 오일러 지표가 1인지,
  서로 다른 모든 점이 꼭짓점인지 봅니다.

- **평면 면과 PLC 검사.** `triangulate_facet(points, loops)`는 평면 면 하나(바깥 고리, 이어서 구멍,
  짝홀 규칙으로 합침)를 제약 Delaunay 삼각 분할합니다. 평면 밖의 점과 서로 교차하는 고리는
  거절합니다. 평면 안의 방향은 좌표 하나를 빼고 정확히 계산합니다. 원 판정은 면 자체의 거리로
  하고(`incircle_plane`, 원을 투영하지 않고 정확), 동률은 3D와 같은 점 번호 순서의 섭동으로
  끊습니다. `check_plc(points, segments, facets)`는 조각별 선형 복합체 전체를 정확히 검사합니다.
  점이 서로 다르고 커널 범위 안에 있으며, 면이 단순한 고리를 가진 평면이고, 두 셀(점, 모서리,
  면)의 교집합이 셀들의 합집합인지 봅니다. 따라서 점이 모서리나 면 안에 있는 것(T자 연결), 모서리가
  면 안에 있는 것, 면이 같은 평면의 다른 면 안에 있는 것은 유효합니다. 교차, 관통, 같은 직선 위의
  부분 겹침, 공통 셀이 덮지 않는 같은 평면 겹침은 거부합니다. 첫 위반은 `InvalidPLC`(`ValueError`의
  하위 클래스)에 이름, 가져오기 유효성 규칙의 증거 유형, 따로 확인할 수 있는 증거(꼭짓점, 면, 교차라면
  두 셀에 모두 있으면서 둘 다에 포함된 어떤 셀에도 없는 정확한 유리수 점)로 나옵니다. 점에서 나뉜 모서리 조각과,
  홀수 개 면의 경계에 놓인 조각(닫힌 곡면이면 없음)도 돌려줍니다.
- **선분 위의 점.** 경계 복원은 입력 선분 위에 점을 더합니다. S 점은 `0 < t < 1`인
  `points[a] + t (points[b] - points[a])`이고, (a, b, t)로 저장하며 메셔 안에서는 반올림하지 않습니다.
  좌표가 정확한 2진 유리수이므로 `mixed_predicate_signs(kind, points, segments, t, query, axis=2)`는
  입력 점과 S 점이 섞인 어떤 조합에서도 `orient3d`, `insphere`, `insphere_sos`와 평면 안의
  `orient2d_proj`, `incircle_plane`, `incircle_plane_sos`를 정확히 계산합니다. 구간 필터(연산마다 바깥쪽으로
  1 ulp 반올림)가 대부분의 부호를 정하고, 나머지는 정확한 큰 정수로 계산합니다. 질의는 전역 번호(입력 점
  먼저, 그다음 S 점)를 쓰고, 이 번호가 동률을 끊는 섭동의 순서도 정합니다. `spoint_coords`는 각 좌표를
  가장 가까운 double로 한 번 반올림한 출력 좌표를 줍니다.
- **선분 복원.** `recover_segments(points, segments, max_depth=60)`는 모든 기본 선분(`check_plc`의
  `subsegments`)을 Delaunay 사면체 분할의 변들의 합집합으로 만들고, 새 점은 선분 위(S 점)에만 넣습니다.
  빠진 조각이 선분들이 90도보다 작게 만나는 꼭짓점에서 끝나면, 먼저 그 꼭짓점의 모든 선분을 꼭짓점에서
  같은 거리에서 나눕니다(보호 구). 나머지 빠진 조각은 변이 될 때까지 반으로 나눕니다. 결과는 입력 점과
  S 점의 점 번호 순서 섭동 아래 Delaunay 사면체 분할이며, 각 선분은 자기 S 점을 지나는 변의 사슬입니다.
  `max_depth`번보다 더 나눠야 하는 조각은 무한히 돌지 않고 `RuntimeError`를 냅니다.
- **면 복원.** `recover_plc(points, segments, facets)`는 PLC 검사와 선분 복원을 한 뒤, 선분 위 S 점을
  넣어 모든 면을 다시 삼각 분할하고(subfacet, 같은 정확 술어와 동률 처리) 아직 면이 아닌 subfacet을
  알려 줍니다. `recover_boundary(points, segments, facets)`는 이어서 모든 subfacet을 면으로 만듭니다.
  한 면에서 빠진 subfacet들이 이어진 영역마다 내부가 그 영역을 지나는 사면체를 지우고, 면 평면의 양쪽을
  gift-wrapping으로 다시 채웁니다(새 사면체마다 그 면을 보는 공동 꼭짓점 가운데 정확한 Delaunay 선택).
  그다음 배열에서 결과를 검증합니다. 사면체가 모두 양의 방향, 볼록 껍질 면 그대로, 모든 점이 꼭짓점,
  모든 subfacet이 면, 모든 선분 조각이 변, 그리고 나머지 내부 면이 모두 국소 Delaunay입니다. 그래서
  결과는 제약 Delaunay 사면체 분할입니다. 채우지 못한 공동은 `ValueError`를 내며, 사면체는 아직 볼록
  껍질 전체를 채웁니다(영역 표시는 아직 없음).
- **세분화 없는 메시.** `mesh_plc(points, facets, segments=None, domain="regions")`는 경계 복원에서
  이어서 계획의 출력 계약을 따르는 메시를 냅니다. 면(facet)이 아닌 면으로 이어진 사면체들이 한 성분이고,
  면이 아닌 볼록 껍질 면에 닿는 성분은 바깥입니다. `domain="regions"`이면 나머지 성분이 각각 영역이고
  (여러 영역 PLC), `domain="parity"`이면 바깥에서 홀수 개 면 떨어진 성분들이 한 영역입니다(닫힌 표면의
  짝홀 영역. 면 세 개가 붙은 변처럼 닫히지 않은 표면은 `ValueError`). 선분 위 점은 가장 가까운 double로
  한 번 반올림하고, 입력 점은 비트 그대로 두며, 쓰이지 않는 점은 빼고, 모든 사면체를 출력 double에서
  정확한 `orient3d > 0`으로 인증합니다. `nodes`, `tetrahedra`, `regions`, `region_names`, 면 번호별
  `boundary_faces`와 `boundary_nodes`(바깥쪽으로 감김), 영역 쌍별 `interfaces`(작은 번호 영역에서 큰 번호
  영역 쪽으로 감김)를 돌려줍니다. 세분화는 없어서, 메시에는 입력 점과 경계 복원에 필요한 점만 있습니다.

```python
import numpy as np
from meshloom._core import delaunay, verify_delaunay

points = np.random.default_rng(0).random((10_000, 3))
tetrahedra, vertex_of, stats = delaunay(points)
verify_delaunay(points, tetrahedra)   # 위반이 있으면 ValueError
```

이 단계들은 [3D 계획](../meshine/validation3d.md)의 V16·V17로 평가합니다. `cargo test`는 각 술어를
무작위 10⁴개와 적대적 10⁴개 사례에서 큰 정수 행렬식과 비교하고, `tests/meshloom`은 Python `Fraction`으로
교차 확인하며 C12 점 집합에서 검증기와 세 가지 삽입 순서를 돌립니다. `benchmarks/benchmark_delaunay.py`는
균일한 점 10⁶개에서 처리량과 꼭짓점당 V15 카운터를, `benchmarks/benchmark_recovery.py`는 칩 패키지와
측지 구에서 선분 복원 카운터(선분당 Steiner 점)를 잽니다.

## 플랫폼과 빌드

meshloom은 컴파일된 코드를 가진 유일한 OpenPhysics 패키지이며 numpy에만 의존합니다. wheel은 안정
ABI(`cp312-abi3`, 플랫폼마다 CPython 3.12 이상용 wheel 하나)를 쓰며 manylinux 2.17 x86_64·aarch64,
macOS 11 x86_64·arm64, Windows x64용으로 만듭니다. 그 밖의 환경에서는 `pip`가 sdist를 빌드하며
Rust 도구 모음과 maturin이 필요합니다. 커널이 없으면 `kernel_available()`은 `False`이고
`generate3d`는 `KernelUnavailable`을 냅니다.

checkout에서(저장소 루트):

```bash
rustup toolchain install 1.97.0 --profile minimal --component rust-src
python -m pip install maturin -e packages/meshloom
python -m pytest -q tests/meshloom
(cd packages/meshloom && cargo test --locked)
```

커널의 단위 시험은 `cargo test`로 돌고, `tests/meshloom`은 빌드된 확장을 확인합니다. 패키지 버전의
abi3 모듈인지, 오차 없는 곱이 정확한 유리수 산술과 같은지, 술어와 Delaunay 사면체 분할이 위의 확인을
통과하는지 봅니다.

## 라이선스

meshloom은 Apache-2.0입니다. 확장 모듈에는 PyO3와 그 작은 의존성, Rust 표준 라이브러리가
정적으로 링크되며, 모두 허용형 라이선스이고 제3자 C·C++ 코드는 없습니다. 이들의 라이선스 전문은
`THIRD_PARTY_NOTICES`에 담겨 배포되며 `tools/build_meshloom_notices.py`가 만들고 확인합니다.
[제3자 소프트웨어](../../third-party.md)를 보세요.

## 한계

- 세분화와 품질 개선은 아직 없습니다. `mesh_plc`는 입력 점과 복원 점만으로 경계를 따르는 메시를
  냅니다. double로 반올림해 납작해지거나 뒤집힌 사면체는 `ValueError`를 냅니다(flip 수리는 다음 단계).
  테스트에서는 아직 일어난 적이 없습니다. 면 복원은 공동을 gift-wrapping으로만 채웁니다. 제약 Delaunay로
  채울 수 없는 공동(지금까지 테스트에는 없음)은 오류이며 아직 점을 더해 고치지 않고, 채우는 시간은
  공동 크기의 제곱에 비례합니다(더 빠른 공동 경로는 나머지 경계 복원과 함께 들어옵니다).
- PLC 검사는 경계 상자 sweep으로 고른 후보 쌍을 비교하고, 면 삼각 분할은 선형 탐색을 씁니다. 둘 다
  builder 크기의 입력을 위한 것이며 아주 큰 표면에 맞게 다듬지는 않았습니다.
- 커널은 아핀 독립인 점이 넷보다 적거나, 좌표의 절댓값이 0도 아니고 [2⁻¹²⁰, 2¹²⁰] 밖이면 거절합니다.
  한 스레드로 돕니다.
- musllinux, 32비트, free-threaded CPython용 wheel은 없습니다.
