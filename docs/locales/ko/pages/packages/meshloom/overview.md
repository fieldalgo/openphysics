# meshloom — 정확 산술 컴파일 커널을 가진 사면체 메시 생성

[English](../../../../../packages/meshloom/overview.md) | **한국어**

[문서 홈](../../index.md)

**상태: 패키징 골격.** meshloom은 여러 재료로 된 조각별 선형 입력을 위한 OpenPhysics의 일반
사면체 메셔가 될 패키지입니다. 정확 술어를 쓰는 제약 Delaunay 사면체 분할, 경계 복원, 품질
세분화, 메시 개선을 컴파일된 Rust 커널로 합니다. 이번 릴리스는 패키징이 보여야 할 것만 담습니다.
모든 wheel 플랫폼에서 커널이 로드되고, 버전을 알려 주며, 정확 술어가 기대는 IEEE double 곱셈을
fused multiply-add 없이 계산합니다. `generate3d`는 `NotImplementedError`를 냅니다.

```python
import meshloom
meshloom.kernel_available()   # 컴파일 커널이 로드되면 True
meshloom.kernel_version()     # 커널 버전, meshloom.__version__과 같음
```

meshloom이 메시를 만들기 전까지 적층 형상에는 [`meshine.extrude`](../meshine/overview.md#적층-사면체-메시)를,
다른 형상에는 [`gmshio`](../gmshio/overview.md)를 통한 Gmsh를 쓰세요. 합격 기준은
[사전 등록 3D 검증 계획](../meshine/validation3d.md)에 미리 고정했습니다. 출력은 `meshine.TetMesh`처럼
`galerkin.from_mesher`가 읽는 필드를 가질 것입니다.

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
abi3 모듈인지, 오차 없는 곱이 정확한 유리수 산술과 같은지 봅니다.

## 라이선스

meshloom은 Apache-2.0입니다. 확장 모듈에는 PyO3와 그 작은 의존성, Rust 표준 라이브러리가
정적으로 링크되며, 모두 허용형 라이선스이고 제3자 C·C++ 코드는 없습니다. 이들의 라이선스 전문은
`THIRD_PARTY_NOTICES`에 담겨 배포되며 `tools/build_meshloom_notices.py`가 만들고 확인합니다.
[제3자 소프트웨어](../../third-party.md)를 보세요.

## 한계

- 아직 메시를 만들지 않습니다.
- musllinux, 32비트, free-threaded CPython용 wheel은 없습니다.
- 확인용 probe가 쓰는 Dekker의 오차 없는 곱은 절댓값이 2^996보다 작고 오차 항이 underflow하지 않는
  피연산자에서 정확합니다. 메셔는 입력을 단위 크기로 축척할 것입니다.
