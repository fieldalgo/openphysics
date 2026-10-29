# 변경 기록

[English](../../../../CHANGELOG.md) | **한국어**

OpenPhysics 배포판 여덟 개(`galerkin`, `galerkin-refsol`, `meshine`, `gmshio`,
`physmat`, `simcase`, `sipi`, 그리고 `openphysics` 메타 배포판)는 하나의 버전 번호로 함께
릴리스됩니다. 이 문서는 릴리스마다 바뀐 점을 기록합니다. 형식은
[Keep a Changelog](https://keepachangelog.com/ko/1.1.0/)를 따릅니다. 기준 문서는 영어판
`CHANGELOG.md`입니다.

## 0.x의 안정성

0.x 릴리스는 알파입니다.

- 모든 패키지의 Python API는 마이너 릴리스(0.1에서 0.2)마다 바뀔 수 있습니다. 패치
  릴리스(0.1.x)는 버그를 고치며 API를 바꾸려는 것이 아닙니다.
- JSON 모델 문서 형식 `"openphysics": "0.2"`는 계약입니다. 이 형식으로 유효한 문서는 계속
  유효하고 뜻도 그대로입니다. 이를 깨는 변경에는 새 형식 버전을 붙입니다.
- 저장 결과의 형식·필드 layout 식별자(예: `thermal.steady2d-result-v1`,
  `cavity3d-edge-v1`)는 계약입니다. 어떤 식별자가 붙은 파일은 그 layout을 유지합니다.
  layout이 바뀌면 새 식별자를 붙입니다.

각 패키지가 구현하는 범위와 한계는 [개요](overview.md)에 있습니다.

## [Unreleased]

- `galerkin`: `eval_edge_field`는 JAX·PyTorch 모서리 dofs(실수 또는 복소수, 예: 살아 있는 입력으로 푼 `solve_modes`의 `et[i]`)를 받습니다. 그러면 중심 필드는 그 라이브러리의 float64 또는 complex128 배열이고, dofs에 대한 미분을 나릅니다. 전에는 JAX dofs가 검사 없이 NumPy 연산을 지나갔고(`jax_enable_x64` 없이 float32 dofs는 float32로 남음), PyTorch dofs는 NumPy 안에서 실패했습니다. 살아 있는 dofs는 모서리마다 값이 하나여야 하고(아니면 `ValueError`), JAX는 `jax_enable_x64`가 필요합니다. 공간의 기하는 미분을 나르지 않습니다. NumPy dofs의 결과는 전과 같습니다. [문서](packages/galerkin/differentiation.md#도파관-모드-고유값-필드-축퇴-모드).
- `galerkin`: `ElementConductivity`는 `ElementHeatSource`(필드 단위 `W/m^3`)를 빌려 쓰지 않고, 단위 `S/m`, 이름 `element conductivity`인 요소 `Field`에 값을 담습니다. 모양·메시 불일치·살아 있는 값 오류 문구가 `element heat source` 대신 `element conductivity`로 시작합니다. `Field`는 단위를 기록만 하고 비교·변환하지 않으므로 값과 결과는 그대로입니다.
- `galerkin`: 온도 의존 Joule 계약 문서에 `solve_temperature_joule_heat`가 무엇을 평가하기 전에 `ValueError`로 검사하는 옵션을 나열하고, 평가 중에 난 것(하위 해석이 거부한 열전도도나 경계 자료, 범위 위반, 콜백이 낸 `Exception`의 모든 하위 예외)은 원래 예외를 원인으로 이은 `JouleConvergenceError`로 호출자에게 닿으며 history가 비어 있을 수 있다고 적었습니다. `last_temperature`를 끝난 방식마다 정의했습니다. Picard가 `max_iterations`에 닿으면 완화했지만 평가하지 않은 상태, Newton은 마지막으로 받아들인 상태, 평가가 실패하면 평가하던 상태나 그 시도 열 해입니다. 잘못된 열전도도를 감싸는 동작을 시험으로 고정했습니다. 동작은 그대로입니다. [문서](packages/galerkin/temperature_joule_heating.md#오류).
- `galerkin`: `solve_temperature_joule_heat`는 두 방법 모두 입력에 JAX·PyTorch 값이 있으면(영역 표와 경계 표 안의 값 포함) 무엇을 복사하거나 풀기 전에 `TypeError`로 거부합니다. 전에는 `thermal_dirichlet`, `initial_temperature`, `relaxation`과 두 허용오차만 `TypeError`를 냈고, 다른 입력은 `TypeError`를 원인으로 가진 `JouleConvergenceError`로, 그 입력에 넣은 non-leaf PyTorch 텐서는 `copy.deepcopy` 안에서 `RuntimeError`로 실패했으며, 살아 있는 `max_iterations`는 `ValueError`로 실패했습니다. 콜백(전도도 콜백, 또는 `outward_flux`, `convection`, `outward_current`의 경계 콜백)이 돌려준 살아 있는 값은 콜백이 돌 때에야 보이므로 여전히 `TypeError`를 원인으로 가진 `JouleConvergenceError`로 나옵니다. NumPy 결과는 그대로입니다. 미분 문서에 반복 solver의 규칙을 적었습니다. 미분은 잔차의 음함수 미분이며, 반복을 한 번 더 돌린 미분이 아닙니다([문서](packages/galerkin/differentiation.md#반복-solver)).
- `galerkin`: `solve_temperature_joule_heat(..., method="newton")`은 전위와 온도를 함께 Newton으로 풉니다. 한 걸음에 희소 풀이 한 번(complex-step 요소 Jacobian), 온도 결함에 대한 반감 선 탐색을 쓰며, 수렴 검사·결과·이력은 그대로인 완화 Picard(`method="picard"`)와 같습니다. `method`의 기본값은 `"picard"`이며, 언제 `"newton"`을 쓸지는 계약 문서에 있습니다. JSON 문서는 계속 Picard 반복을 씁니다. 계약 문서의 전류 구동 서미스터에서 3–4개 상태로 수렴하며, 기본 완화 0.5의 Picard가 100회 안에 수렴하지 않는 강한 피드백(alpha = 7, 9 /K)에서도 수렴합니다. `ConductivityModel`은 Newton 걸음에 쓰는 선택 `derivative`(dσ/dT)를 받습니다. [문서](packages/galerkin/temperature_joule_heating.md#newton-방법).
- `galerkin`: 열 해석의 경계 연립(Robin 행렬, 유속·주변 하중)을 `galerkin.thermal`의 공개 이름 `scalar_boundary_system`으로 두어, `solve_temperature_joule_heat`의 Newton 방법이 열 해석과 같은 연산자를 선형화합니다. 열 결과는 바뀌지 않습니다.
- `galerkin`: Joule 발열 공식을 `galerkin.core.kernels.p1_joule`로 옮겨 `solve_steady_electric`가 NumPy와 JAX·PyTorch 입력에 똑같이 쓰며, 하중은 `p1_load`의 중심점 규칙으로 계산합니다. 전기 결과는 비트 단위로 같습니다.
- `galerkin`: `solve_material_cavity_box`, `mode_coordinates`, `scalar_coordinate_system`, `solve_scalar_coordinates`, `assemble_mode_system`, `solve_dirichlet`, `l2_error`, `eval_edge_field_3d`는 NumPy로 계산하며 이제 JAX·PyTorch 값을 `TypeError`로 거부합니다. 전에는 대부분의 입력에서 JAX 배열이나 `requires_grad`가 없는 PyTorch 텐서를 NumPy로 바꿔 미분이 끊긴 NumPy 결과를 돌려줬습니다. 이런 호출은 이제 NumPy 수를 넘겨야 합니다. 몇몇 입력은 이미 관련 없는 오류로 실패했고(`assemble_mode_system`·`scalar_coordinate_system`·`solve_scalar_coordinates`의 `k0`, `solve_scalar_coordinates`의 `n_target`, `l2_error`·`eval_edge_field_3d`와 `mode_coordinates` 대부분의 입력에 넘긴 PyTorch 값), `solve_material_cavity_box`와 `mode_coordinates`의 PML 두께는 `ValueError`를 냈으며, 추적 중이거나 `requires_grad`인 값은 NumPy 안에서 실패했습니다. NumPy 입력은 그대로입니다. `radial_pml_coeffs`는 막지 않았습니다([한계](packages/galerkin/differentiation.md#한계)).
- `galerkin`: 정상 열전도, 정상 전기전도, 탄성, 열탄성은 NumPy 입력과 JAX·PyTorch 입력 모두 연립방정식을 `galerkin.core.solve`로 한 번 풉니다. 전에는 NumPy 분기와 살아 있는 분기를 따로 두거나(열·전기), NumPy로 푼 뒤 살아 있는 보정 풀이를 한 번 더 했습니다(탄성·열탄성). NumPy에서는 그 풀이가 자유 블록을 SciPy의 SuperLU(`splu`)로 분해합니다. 탄성이 그랬고 JAX·PyTorch 경로가 그렇듯, scikit-umfpack이 설치돼 있어도 그렇습니다. NumPy 결과는 scikit-umfpack이 없으면 비트 단위로 같고, 있으면 열·전기 결과가 반올림 수준으로 달라집니다(전에는 `spsolve`가 UMFPACK을 썼습니다). JAX·PyTorch 결과는 반올림 수준으로만 달라집니다(상대 3e-14 이하, 정확한 값이 0인 곳, 예컨대 자유 열팽창의 응력에서는 반올림 수준의 절대 차이). 특이한 NumPy 열 연립방정식은 경고 뒤 유한하지 않은 해를 알리는 대신 살아 있는 경로와 같은 `singular or ill-conditioned constrained heat system`을 냅니다. JAX에서 특이한 탄성·열탄성 연립방정식은 이제 열·전기처럼 `ValueError` 전에 JAX 콜백 traceback을 로그에 남깁니다([한계](packages/galerkin/differentiation.md#한계)). 이제 어떤 풀이도 프로세스 전체의 경고 필터를 바꾸지 않습니다. 전기가 바꿨고, 두 스레드가 동시에 풀면 그 필터가 남을 수 있었습니다. `galerkin.solve_dirichlet`은 그대로입니다.
- `galerkin`: 어떤 모듈도 다른 모듈이나 클래스의 밑줄 멤버를 읽지 않으며 층 시험이 이를 검사합니다. 클래스 밖에서 쓰던 `EdgeSpace3D._ids`와 `Mesh3D._edge_matrix`는 `galerkin.core.spaces.edge_ids`와 `galerkin.core.tets.edge_matrix`로 바꿨습니다. 결과는 바뀌지 않습니다.
- `galerkin`: `EdgeSpace`와 `EdgeSpace3D`를 변 커널이 쓰는 국소 변 순서와 함께 `galerkin.core.spaces`로 옮겼습니다. `galerkin`, `galerkin.edge`, `galerkin.edge3d`는 여전히 내보내며, 클래스 모듈(repr과 pickle 경로)은 이제 `galerkin.core.spaces`입니다. 행렬과 필드는 바뀌지 않습니다.
- `galerkin`: 어떤 모듈도 다른 모듈의 비공개 이름을 import하지 않으며, 층 시험이 이를 검사합니다. 상자 공진기와 탄성이 그렇게 나눠 쓰던 입력 검사는 `galerkin.core.checks`로, 열→역학 workflow의 메시 격리·Dirichlet 검사와 공진기의 광속·수치 기준·상자 메시는 패키지 비공개 모듈로 옮겼습니다. 결과와 오류 메시지는 바뀌지 않습니다.
- `galerkin`: `solve_elasticity`, `solve_thermoelasticity`, 도파관 모드 연립방정식은 NumPy 본문과 따로 살아 있는 본문을 두는 대신, NumPy와 JAX·PyTorch 입력에 `core.kernels`로 만든 본문 하나를 씁니다. NumPy 결과는 비트 단위로 같습니다.
- `galerkin`: 요소 공식은 이제 `galerkin.core.kernels`에 한 벌만 있습니다. 공개 조립 함수(`assemble_stiffness`, `assemble_mass`, `assemble_boundary_mass`, `assemble_load`, 그 3D 함수와 변 요소 함수)는 이 커널을 조립하며 같은 행렬을 돌려줍니다. 이제 JAX·PyTorch 값을 NumPy로 바꾸는 대신(미분이 끊김) `TypeError`로 거부하고, `assemble_curlcurl_3d`, `assemble_edge_mass_3d`, `assemble_edge_grad_3d`, `assemble_load`는 복소 계수 배열의 허수부를 `ComplexWarning`과 함께 버리는 대신 `TypeError`로 거부합니다. 새 symfem 비교가 셀별·텐서·복소 계수의 커널을 정확한 적분과 비교합니다([요소 정의](reference-comparisons.md#계수)).
- `galerkin`: `galerkin.core`가 메시 형식만 import합니다. 사면체 기울기는 `galerkin.core.tets`로 옮겼고(`galerkin.tet_gradients`, `galerkin.assembly3d.tet_gradients`는 그대로), SciPy Dirichlet 풀이 본문은 `galerkin.core.solve`로 옮겼으며(`galerkin.solver.solve_dirichlet`의 서명은 그대로), `core.loads`는 중심점 하중을 `core.kernels`로 만듭니다. 공개 조립 모듈은 이제 core 위에 있고, 층 시험이 메시 형식과 이 모듈들도 검사합니다. 결과는 바뀌지 않습니다.
- `galerkin`: `solve_modes`와 `assemble_mode_system`이 복소 `mu_r`를 유지합니다. 전에는 NumPy 경로가 허수부를 버리고(배열은 경고, 스칼라는 `TypeError`) JAX·PyTorch 경로는 유지해서, 두 경로가 서로 다른 문제를 풀었습니다. 이제 손실 있는 `mu_r`도 손실 있는 `eps_r`처럼 문제를 복소로 만들고, 유한하지 않은 `mu_r`는 거부합니다. 0차원 복소 JAX·PyTorch 입력(예: `2 - 0.1j * t`)도 수를 읽을 때 더는 실패하지 않습니다. 실수 입력의 결과는 같습니다.
- 문서: [아키텍처](architecture.md#galerkin-안-core-physics-coupling) 문서가 galerkin의 core·physics·coupling 층, 아직 core로 옮기지 않은 것, 새 물리 추가 절차를 설명합니다.
- `galerkin`: `galerkin.core`가 더는 위쪽 모듈을 import하지 않습니다. 재료 조회는 `galerkin.core.materials`로 옮겼고(`galerkin.materials`는 같은 공개 이름을 유지), `core.loads`는 `ElementHeatSource`를 import하는 대신 검사를 마친 요소 열원 값(`ElementSource`)을 받습니다. import 방향을 검사하는 시험을 더했습니다. 결과는 바뀌지 않습니다.

- `simcase` Studio: 정상·과도 열전도 route가 열전도 영역 문서를 worker thread에서 검증하고 실행합니다. 실행 전에는 도형, 원, 다각형 점, 경계 교차, 루프 꼭짓점 수를, job에서는 절점과 셀 수를 한도와 비교합니다. 영역 결과는 자체 형식 `studio-thermal-steady-regions-v1`과 `studio-thermal-transient-regions-v1`을 쓰고, 직사각형 문서의 응답은 그대로입니다. 페이지는 영역 결과를 영역 색, 경계, 범례, 재료 표, 커서 아래 영역 표시와 함께 보여 줍니다. [문서](packages/simcase/thermal_studio.md#영역-문서).

- `simcase`: `region_complexity`가 `Document.from_dict` 전에 원시 열전도 영역 문서를 읽어 도형, 원, 다각형 점 수를 세고, 어느 것도 주어진 최댓값을 넘지 않으면 `from_dict`의 불리언 연산 비용을 좌우하는 도형 사이 경계 교차 수도 셉니다. 잘못된 데이터에서도 예외를 발생시키지 않습니다. [문서](packages/simcase/thermal_regions2d.md#호출자를-위한-메시-상한).

- `simcase`: `run`이 정상·과도 열전도 영역 문서에 선택적인 `max_input_vertices`, `max_nodes`, `max_triangles`를 받아 풀이 전에 검사하고 `MeshLimitError`로 거절합니다. `check_mesh_limits`는 영역을 만들지 않고 문서의 루프 꼭짓점 수를 반환합니다. 메시 전 작업을 제한하는 것은 `max_input_vertices`뿐입니다. 두 열전도 종류는 물리 등록표(`PhysicsKind.accepts_mesh_limits`)를 통해 상한을 받고, 상한이 없으면 실행은 그대로입니다. [문서](packages/simcase/thermal_regions2d.md#호출자를-위한-메시-상한).

- `meshine`: `generate`는 삽입이 `max_points`를 넘기려 하면 `RuntimeError` 하위 클래스인 `MeshSizeLimitError`를 발생시키고, 만들어진 입력 영역도 세분화 작업 전에 상한과 비교합니다. 그래서 점이 더 많은 입력은 세분화되거나, 삽입이 필요 없을 때 상한을 넘긴 채 반환되지 않고 그 자리에서 거절됩니다. 꼭짓점 수에 대해 O(V²)인 영역 만들기는 여전히 먼저 실행됩니다. [문서](packages/meshine/overview.md#안전장치).

- `galerkin`: 정상·과도 열→역학 workflow가 단계를 연성 층의 `OneWayChain`으로 실행하고, 각 절점 Kelvin 장을 동결하기 전에 같은 메시 `transfer`에 통과시킵니다. 결과·manifest JSON·단계 오류와 메시지는 바뀌지 않습니다. [문서](packages/galerkin/thermal_mechanical_workflow.md).

- `galerkin`: 한 방향 Joule workflow와 `ElementHeatSource`가 연성 층 위에서 동작합니다. Joule 열은 전기 메시 위의 요소 `Field`이고 같은 메시 전달로 열 메시에 옮겨지며, `ElementHeatSource.field`로 볼 수 있습니다. 결과·검산·오류 메시지는 바뀌지 않습니다. [문서](packages/galerkin/joule_heating.md#요소-열원-api).

- `galerkin`: 새 `galerkin.coupling` 층. `Field`는 한 메시의 절점 또는 요소 값을 SI 단위와 함께 담고, `transfer`는 그것을 같은 메시로 그대로 옮기며, `OneWayChain`은 한 방향 workflow의 단계를 실행하고 실패에 단계 이름을 붙입니다. 커널 인터페이스를 문서로 정하며, 유한요소 엔진이 첫 커널입니다. 기존 workflow는 바뀌지 않습니다. [문서](packages/galerkin/coupling.md).

- `galerkin`: PEC 상자 공진기(`solve_cavity_box`)가 JAX나 PyTorch 상자 길이를 받고, 주파수, 고유값, 모서리 계수, 중심 필드를 그 라이브러리로 돌려주며 역방향 미분을 붙입니다. 메시의 축 방향 배율을 거쳐 정확합니다. 축퇴 모드는 NaN 미분과 `DegenerateModeWarning`을 받습니다. NumPy 결과는 바뀌지 않습니다. [문서](packages/galerkin/differentiation.md#상자-공진기-길이에-대한-미분).

- `galerkin`: 도파관 모드(`solve_modes`)가 eps_r, mu_r(스칼라 또는 요소 배열, 실수·복소수)와 k0에 JAX나 PyTorch 값을 받고, n_eff와 두 필드 배열을 그 라이브러리로 돌려주며 고유값과 필드의 역방향 미분을 붙입니다. 축퇴 모드는 NaN 미분과 `DegenerateModeWarning`을 받습니다. NumPy 결과는 바뀌지 않습니다. [문서](packages/galerkin/differentiation.md#도파관-모드-고유값-필드-축퇴-모드).

- `galerkin`: 탄성과 열탄성이 E, nu, alpha, 기준 온도, Dirichlet 변위, 체적력, 견인력에 JAX나 PyTorch 값을 받고 역방향 미분을 돌려줍니다. NumPy 결과는 바뀌지 않습니다. [문서](packages/galerkin/differentiation.md).

- `galerkin`: 과도 열전도가 전도도, 열용량, 열원, Dirichlet 온도, 초기 온도장에 JAX나 PyTorch 값을 받고, 모든 시간 단계를 거치는 역방향 미분을 돌려줍니다. `checkpoint_every`로 재계산과 메모리를 맞바꿀 수 있습니다. NumPy 결과는 바뀌지 않습니다. [문서](packages/galerkin/differentiation.md#과도-열-메모리와-checkpoint).

- `galerkin`: 정상 열전도와 정상 전기 전도가 전도도, 열원, Dirichlet·기준 전위, 경계 데이터에 JAX나 PyTorch 값을 받고, 결과를 그 라이브러리로 미분과 함께 돌려줍니다(adjoint 희소 풀이를 통한 역방향 모드). NumPy 결과는 바뀌지 않습니다. 아직 미분하지 않는 solver는 미분을 조용히 버리지 않고 JAX·PyTorch 값을 거부합니다. [문서](packages/galerkin/differentiation.md).

- 신호·전원 무결성 패키지 `sipi`를 추가합니다. 층 유전체와 직사각형 트레이스로 된 PCB 단면을 준정적(quasi-TEM)으로 풀어 C·L·유전 손실 G 행렬, 단일선 임피던스와 유효 유전율, 결합선 even/odd 모드를 계산합니다. 평행판·동축 정확해, Cohn 스트립라인 정확해, Hammerstad–Jensen 마이크로스트립 식과 비교해 검증했으며 도체 손실은 포함하지 않습니다. `openphysics[sipi]`로 설치합니다. [문서](packages/sipi/overview.md).

- `/workspace`에 실험적 모델 작업공간을 추가합니다. 고정 조건 광학 실행, 모델 편집 이력, 세션 파일과 버전이 있는 지원 범위 계약을 제공하며 기존 광학·열 편집기를 유지합니다.

- Scalar/full-vector 모드 PML·일정 반경 굽힘: 복소 후보 진단, 물리창 추적, 총 감쇠, Studio 입력 및 독립 slab/원통 기준 검증.

구현 패키지 여섯 개와 `openphysics` 메타 배포판의 첫 PyPI 릴리스이며, 0.1.0으로
계획돼 있습니다.

### Added

- 수동 복소 scalar/full-vector 도파관 모드, 복소 분리 모드 sweep, dB/cm 손실과 Studio/JSON/NPZ 출력. [부호와 한계](packages/simcase/lossy_modes.md).

- 정확한 정답과 대조하는 공개 기준값 벤치마크를 추가했습니다: Timoshenko (1925) 바이메탈
  띠(`refsol.bimetal`)와 NAFEMS T4 대류 열전달(`refsol.thermal_convection`, 출판 목표값
  18.3 °C 포함). 메시 수렴 기준, 그림 스크립트, 검증 문서
  `docs/packages/galerkin/public_benchmarks.md`가 함께 들어갔고 엔진 코드는 바뀌지 않았습니다.

- 같은 메시의 명시적 정상 전기→열 연성과 메시 사본에 결합한 요소별 열원 입력을
  추가했습니다. 해석해 수렴·에너지 수지·독립 도구 비교로 검증했습니다.

### Changed

- `openphysics`는 메타 배포판입니다. 코드가 없고 여섯 구현 패키지를 의존성으로 요구합니다.
  extra `studio`, `export`, `rii`는 `simcase[studio]`, `simcase[export]`,
  `physmat[rii]`를 설치합니다. 어떤 extra도 Gmsh를 설치하지 않습니다. 이전의
  `openphysics` 0.0.1은 다른 여섯 이름의 0.0.1과 마찬가지로 빈 이름 예약이었습니다.
- 모든 패키지가 Python 3.12 이상을 요구합니다. numpy·scipy·shapely·matplotlib의 최소 버전은
  Python 3.12 휠이 있는 첫 릴리스인 1.26, 1.11.2, 2.0.2, 3.8로 올렸습니다.
- 패키지 사이의 의존성은 0.1 계열(`>=0.1.0,<0.2`)로 제한됩니다.

- 온도 의존 2D 정상 Joule heating: 유효 범위 물성, 완화 Picard 반복, 실패 이력 및 독립 검증 추가.

- 전기전도·상수/온도 의존 Joule heating의 직사각형 JSON/CLI, SI 결과 저장과 실패 반복 근거를 추가했다. 기존 솔버를 재사용한다.
