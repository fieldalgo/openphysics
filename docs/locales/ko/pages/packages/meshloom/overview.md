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
균일한 점 10⁶개에서 처리량과 꼭짓점당 V15 카운터를 잽니다.

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

- 아직 메시를 만들지 않습니다. 입력 면, 경계 복원, 세분화, 개선이 없습니다. flip과 선분·면 위에 저장한
  점의 술어는 경계 복원과 함께 들어옵니다.
- 커널은 아핀 독립인 점이 넷보다 적거나, 좌표의 절댓값이 0도 아니고 [2⁻¹²⁰, 2¹²⁰] 밖이면 거절합니다.
  한 스레드로 돕니다.
- musllinux, 32비트, free-threaded CPython용 wheel은 없습니다.
