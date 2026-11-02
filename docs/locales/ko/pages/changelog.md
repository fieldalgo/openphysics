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

- `simcase`: 균질 직사각형의 headless 기계해석 문서 두 종. `mechanics.elasticity2d`는 변별 변위 성분·전역 직교좌표계 변 traction·상수 체적력을 쓰는 정적 평면응력/평면변형률 선형탄성을, `mechanics.thermoelastic2d`는 같은 메시에서 변별 상수 경계 데이터의 정상 열전도를 먼저 풀고 전체 traction으로 열응력을 풉니다. 구속이 강체 운동을 남기는 문서는 메시 생성 전에 거부합니다. 결과는 `mechanics.elasticity2d-result-v1`(layout `mechanics2d-p1-v1`)과 `mechanics.thermoelastic2d-result-v1`(`thermoelastic2d-p1-v1`)로 저장되고 `export_fields`가 이름 붙은 변형률·응력 성분으로 VTU를 쓰며 Studio는 둘을 거절합니다. 예제 `elastic_plate`, `thermoelastic_bar`. [문서](packages/simcase/mechanics2d.md).

- `simcase`: `em.modes2d` 결과가 저장 layout을 기록합니다. `summary.json`과 `fields.npz`에 `field_layout` `em-modes2d-p1-node-centroid-v1`(subspace sweep은 `em-modes2d-subspace-raw-v1`), `mesh_length_unit`, `length_unit_to_m`이 들어가고 archive에는 `study_parameter`도 들어갑니다. 기존 키는 바뀌지 않습니다.

- `simcase`: `simcase.export.export_fields`가 단일 지점 도파관 모드 결과(`em-modes2d-p1-node-centroid-v1`)를 미터 단위 좌표로 씁니다. 스칼라는 점 데이터 `mode_<k>`(복소면 `_real`/`_imag`), 벡터는 셀 데이터 `electric_field_mode_<k>_real`/`_imag`과 점 데이터 `longitudinal_electric_mode_<k>_real`/`_imag`, 그리고 `triangle_regions`입니다. 새 `export_sweep`은 study 지점마다 VTU 하나와 `.pvd`를 쓰며, 단조 파장 sweep이면 timestep이 파장(문서 단위), 아니면 지점 번호입니다. PML 결과는 흡수층을 포함해 내보내고, subspace sweep과 `field_layout` 없이 저장된 결과는 거절합니다. 이전의 모든 VTU/PVD 출력은 바이트까지 같습니다. [문서](packages/simcase/overview.md#paraview로-보기).

- `galerkin`: `solve_transient_heat`의 경계 데이터가 시간에 의존할 수 있습니다. g, h, T_amb는 각각 scalar, callback(points, normals), callback(time_s)->scalar 또는 callback(points, normals, time_s)->(Q,)이며 Dirichlet·source callback처럼 각 단계 끝에서 표본화합니다. H는 h가 변할 때만 다시 조립하고 정적 데이터의 결과는 이전과 비트 단위로 같습니다. JAX/PyTorch 입력은 시간 의존 g·T_amb를 지원하고 시간 의존 h는 거절합니다. 새 `refsol.transient_heat_robin` 주기 주변 온도(해석·후진 Euler 이산 진폭)와 ramp 열유속 Duhamel 기준해. 기준: 주기 진폭·위상 공간 차수 ≥1.8, 시간 ≥0.9, 최세분 ≤ A의 3e-3; ramp 열유속 차수 ≥1.8/0.9, 최세분 ≤ 상승의 2e-3; 단계별 열수지 ≤1e-10. simcase 문서는 상수 변만 유지합니다. [문서](packages/galerkin/transient_heat.md).

- `simcase`: `thermal.transient2d` 문서가 정상 경계조건 계약의 `outward_flux_w_m2`·`convection` 변 키를 받습니다(같은 이름·한계·메시지, 상수만, anchor 불필요). 키가 있으면 새 쌍 `thermal.transient2d-result-v2` / `thermal2d-transient-p1-node-cell-boundary-v1`을 선택해 step별 `prescribed_outward_load_w_per_m`·`convective_outward_w_per_m`(W/m)을 단위·위치·시간축과 함께 저장하고, 키가 없는 문서는 v1을 byte 단위로 유지합니다. `export_fields`·`export_time_series`가 새 layout을 쓰고 과도 Studio route는 검증 전에 거절합니다. 새 예제 `transient_thermal_boundary`. 기준: `refsol.transient_heat_robin` 대류 slab 상대 L2 ≤ 2e-3(측정 2.0e-4). [문서](packages/simcase/thermal_transient2d.md).

- `galerkin`: `solve_transient_heat`가 정상 솔버와 같은 입력 형식·부호의 `outward_flux`·`convection`을 받습니다(변 태그별 scalar 또는 callback(points, normals), 한 번 표본화하는 시간 무관 데이터; 시간 callback은 거절). 시스템은 M/dt+K+H이며 결과에 `prescribed_outward_load_w_per_m`·`convective_outward_w_per_m`이 추가됩니다(경계 데이터가 없으면 None; Dirichlet 전용 이력은 비트 단위로 동일). 새 `refsol.transient_heat_robin` 대류·상수 열유속 slab 급수. 기준: slab 공간 차수 ≥1.8, 시간 차수 ≥0.9, `solve_steady_heat`와 장시간 일치 ≤1e-8, 단계별 열수지 ≤1e-10. [문서](packages/galerkin/transient_heat.md).

- `galerkin`: `triangle_geometry`가 검증 결과를 메시 내용 기준으로 캐시하고(8개 LRU, 복사본 반환) 겹침·엣지 표·정점 팬·매달린 노드 검사를 벡터화했으며, 경계 샘플러는 캐시된 엣지 표를 조회합니다. 판정과 솔버 결과는 비트 단위로 그대로이고(결과 배열 660개·거부 메시 15개로 확인), Linux에서 정상 열 n=64가 2.0 s→0.46 s, 열저항 Picard n=16이 6.2 s→0.22 s입니다. [문서](packages/galerkin/overview.md#메시-검증-캐시).

- `galerkin`: `Mesh3D`가 바깥 방향 태그 면과 `check()`(모든 외부 면 한 번 태그, 바깥 감김, 절점 집합 일치)를 갖고 음수 영역 id를 거부합니다. `from_mesher`는 면·영역·계면을 유지하고 `-1` 영역을 개수와 함께 거부하며 `read_msh`는 3D 영역과 표면 태그를 유지합니다. 계약: [사면체 메시 형식](packages/galerkin/mesh3d_format.md).

- `galerkin`: `solve_cavity`·`solve_material_cavity`가 외부 사면체 메시(meshine, gmshio)에서 면 태그별 PEC·임피던스 벽과 영역별 재료로 공진기를 풉니다. gradient kernel은 구속 표면에서 셉니다. 상자 솔버는 비트 단위로 동일하고 메시 변형에는 미분 경로가 없습니다. [문서](packages/galerkin/cavity_solver.md#외부-메시), [재료 공진기](packages/galerkin/material_cavity.md#외부-메시).

- `galerkin`: `galerkin.thermal3d.solve_steady_heat_3d`, 영역별 열전도율·열원, Dirichlet 면과 단열, W 단위 열수지 검사를 갖는 사면체 메시의 P1 정상 열전도; `refsol.thermal3d` 기준해. [문서](packages/galerkin/thermal3d.md).

- `galerkin`: `galerkin.electrostatics` 추가 — 절점 집합 도체·자유 전하·절연 외부 경계의 2D 정전기와 에너지·전하 경로로 검사한 Maxwell 정전용량 행렬(실수 또는 손실 복소 유전율; 실수 입력의 JAX/PyTorch 미분); `refsol.electrostatics`에 동축·두 층 평행판 정전용량 레퍼런스 추가. [문서](packages/galerkin/electrostatics.md).

- `galerkin-refsol`: 참조 모듈 셋 추가. `refsol.lossy_slab`은 복소 유전율 다층 슬랩(흡수 결합 모드와 기판 누설 모드, 명시한 sheet 선택, 잔차 ≤ 1e-12, 1차 섭동·터널링 검증)을 풀고 galerkin 스칼라/벡터·PML 모드 솔버를 2차 수렴으로 평가합니다. `refsol.joule_slab`은 고정 전위·온도 사이의 `sigma = sigma0 (1 + alpha (T - T0))` 정확한 1D 정상 Joule 가열 슬랩(erf/erfi 폐형식, 전류 구동 fold)을 제공하고 `solve_temperature_joule_heat`를 2차 수렴으로 평가합니다. `refsol.bent_slab`(선택적 mpmath)은 복소 차수 Bessel 정합으로 일정 반경 굽은 슬랩 극점을 제공합니다. [문서](packages/galerkin-refsol/overview.md).

- galerkin: `galerkin.mode_overlap` — 모드 전력(정확한 edge 질량과 edge-절점 결합 행렬로 계산한 Faraday 경로 복소 Poynting 적분), 교차 전력, 장 중첩과 중첩 행렬, power/mass/peak 정규화, 결합 효율(퇴화 공간 사영 포함), 에너지 구속 계수, 유효 면적(정확한 질량 분자, `int |E|^4`는 4차 대칭 삼각형 규칙), 주어진 장의 Nédélec/P1 보간, P1 스칼라 쌍; NumPy 전용. refsol slab·광섬유 장으로 검증했습니다. [계약과 검증](packages/galerkin/mode_overlap.md).

- galerkin: 도파관 정식화 문서가 scalar P1·혼합 Nédélec/절점 모드 솔버, 복소 재료와 좌표 늘림 PML, 테두리 고유쌍 미분, 연성 경계, 준정적 sipi 경로를 구현된 대로 읽고 각 수식을 모듈·함수와 함께 인용합니다. [문서](packages/galerkin/waveguide_formulation.md).

- 문서: 패키지 README와 문서 개요에 빠져 있던 기능을 추가했습니다. galerkin의 정상 전기전도, 단방향·온도 의존 Joule heating, JAX/PyTorch 미분과 coupling 계층; meshine의 `extrude`와 사면체 메시 계약("2D 전용" 한계 삭제); refsol의 `thermal_multilayer`, `transient_heat_multilayer`, `elasticity_multilayer`. 진입 문서는 workspace의 정상 열전도 판과 광학 도형을 설명하고, 모든 영문 페이지가 한국어 쌍과 서로 링크합니다.

- CI: GitHub의 Node 20 런타임 종료에 맞춰 고정한 GitHub Actions를 Node 24 릴리스(`actions/checkout` v5, `actions/setup-python` v6, `actions/setup-node` v5, `actions/upload-artifact` v6)로 올렸습니다. 검사 내용과 아티팩트 이름은 바뀌지 않습니다.

- CI: 필수 검사가 아닌 하루 한 번의 `Latest dependencies` 카나리(`.github/workflows/latest-deps.yml`)가 메타데이터가 허용하는 가장 새 의존성으로 패키지를 설치하고 `pip check`, 라이선스 목록 검사, 사전 검사 묶음, non-slow 시험, 강제 커널 시험을 돌린 뒤 해석된 버전과 함께 이슈 하나를 열거나 갱신하거나 닫습니다. 고정 버전은 여전히 의도적으로 올립니다. [문서](development.md#최신-의존성-카나리).

- 시험: galerkin의 경계 항을 같은 메시에서 scikit-fem과 비교합니다. `thermal.solve_steady_heat`의 외향 열유속·대류(Robin) 변(혼합과 Robin만), 0이 아닌 규정 변위를 둔 `elasticity.solve_elasticity`의 Cartesian traction 변, Helmholtz 조립의 1차 흡수 경계(`assemble_boundary_mass`)입니다. 행렬·하중·반력·장·에너지가 1e-13 이하로 일치합니다. [레퍼런스 도구 비교](reference-comparisons.md#현재-사례).

- `physmat`: Ciddor 1996의 습한 공기를 `standard_air` / `physmat.standard_air(temperature_c, pressure_pa, humidity, co2_ppm)`와 벡터화된 `physmat.air.refractive_index`로 추가했습니다. 표준 건조 공기의 분산과 CO2 보정, 수증기 분산, BIPM 1981/91 밀도로 0.3–1.69 µm에서 유효하며, NIST Engineering Metrology Toolbox 값을 1e-9 이내, 상온 조건의 Birch & Downs 1994를 6e-9 이내로 재현합니다. `air`는 진공 그대로입니다. 내장 재료 표는 재료별 출처를 밝힙니다. [문서](packages/physmat/overview.md#공기-ciddor-1996).

- 저장소 검사: `tools/tests/test_examples_smoke.py`가 `examples/` 아래의 모든 스크립트와 JSON 문서를 임시 디렉터리에서 실행하고 종료 코드 0을 요구합니다. 약 20초를 넘는 예제는 `slow` 마커를 달았습니다. [tools/README.md](../../../../tools/README.md#examples-smoke-test)에 문서화했습니다.

- 벤치마크: `benchmarks/benchmark_thermal.py`, `benchmark_elasticity.py`, `benchmark_electric.py`, `benchmark_derivatives.py`가 정상·과도 열전도, 탄성과 열탄성 traction workflow, 전기 전도·Joule 가열·온도 의존 Joule 풀이(Picard와 Newton), 그리고 forward 풀이 대 gradient(NumPy 중심 차분, 설치된 경우 JAX·PyTorch adjoint, 없으면 건너뜀)의 시간을 새 프로세스에서 재고 checkout·고정 요구사항·머신·peak RSS를 기록합니다. 전체 열·전기 호출 옆에 공개 assembly 함수의 시간도 잽니다. 사람이 손으로 실행하며 CI는 실행하지 않습니다. 안내: [열전도](benchmark_thermal.md), [탄성](benchmark_elasticity.md), [전기](benchmark_electric.md), [미분](benchmark_derivatives.md).

- 도구: 설치 플랫폼 검사(`tools/check_platform_install.py`)가 이제 cavity3d, `sipi`, 완전 벡터/PML 도파로 모드 wheel 소비자를 Linux·macOS·Windows에서 실행합니다. `test_sipi_wheel.py`(거친 메시에서 Cohn, Hammerstad–Jensen, 정확한 저항 비교)와 `test_vector_modes_wheel.py`(`refsol.slab`, 누설 슬래브 외향 근, PML 유무의 `vector_slab` 예제 CLI 실행)는 새 소비자입니다. cavity 소비자의 Studio 검사는 배포 검사에서 Linux에만 남습니다. Linux에서 확인했고 macOS·Windows는 CI에서 돕니다. [개발 안내](development.md#ci가-돌리는-것).

- `galerkin`: `galerkin.read_msh`가 평면 MSH 2.2/4.1 파일의 물리 그룹을 보존합니다. 물리 표면은 `regions`/`region_names`가 되고(어느 물리 표면에도 속하지 않는 삼각형은 영역 -1), 물리 곡선은 `boundary_edges`와 `boundary`가 되며, 어떤 삼각형도 쓰지 않는 절점은 버립니다. 결과는 `from_mesher(gmshio.to_fem2d(gmshio.read_msh(path)))`와 배열 단위로 같습니다. `write_msh`는 평면 메시의 영역마다 물리 표면 하나를 씁니다. 사면체 메시는 바뀌지 않습니다. [문서](packages/galerkin/overview.md).

- `sipi`: 버전 공차 입력으로 sweep/corners·독립 uniform·상관 normal, 고정 피치 차동 형상과 실패 행 보존을 지원합니다. [계약·검증](packages/sipi/study.md).

- `simcase`: `simcase.export.export_fields`가 저장 배치 두 가지를 더 VTU로 씁니다. 열유속·대류 변이 있는 직사각형 정상 열전도(`thermal2d-p1-node-cell-boundary-v2`)는 절점 경계 하중 배열과 함께, 전기 전도·Joule 가열(`electric-joule2d-p1-v1`, `electric.steady2d`·`joule.steady2d`·`joule.temperature2d`)은 점 데이터 `potential_v`와 절점 전기 배열(Joule이면 열 배열도), 셀 데이터 `electric_field_v_m`, `current_density_a_m2`, `conductivity_s_m`, `joule_heating_w_m3`(Joule이면 `heat_flux_w_m2`도)로 내보냅니다. 배열은 저장된 이름과 값을 그대로 쓰고 Dirichlet 절점 목록은 복사하지 않으며 저장 파일은 바뀌지 않습니다. 손실 공진기와 `em.modes2d` 결과는 여전히 거절합니다. [문서](packages/simcase/overview.md#paraview로-보기).
- `simcase`: `export_fields`가 재료와 손실 벽이 있는 공진기(`cavity3d-edge-complex-v1`)도 씁니다. VTK에는 복소 배열이 없으므로 모드마다 사면체 셀 데이터 `electric_field_mode_<k>_real`과 `electric_field_mode_<k>_imag`(저장된 정규화와 `exp(+j*omega*t)` 규약)로, 재료는 `tet_relative_permittivity_real`/`_imag`과 `tet_relative_permeability_real`/`_imag`으로 내보냅니다. 주파수·Q 값·벽 전도도는 `fields.npz`와 `summary.json`에 남습니다. 진공 공진기 내보내기와 다른 모든 VTU는 바이트까지 그대로이며, `em.modes2d` 결과만 여전히 거절합니다. [문서](packages/simcase/cavity3d.md).
- SIPI 인과적 Huray 도체 거칠기로 저항·내부 인덕턴스를 함께 보정하고,
  기존 버전 1을 보존하는 명시적 선로 JSON 버전 2를 추가했습니다.
- `sipi`: strict `sipi.circuit/1`에 RLGC/Touchstone 또는 형상 선로 문서와 소스/부하를 저장해 단자 응답·명시 누화를 재현합니다. [계약](packages/sipi/circuit_document.md).

- `meshloom`: 커널의 첫 단계를 `meshloom._core`의 내부 구성 요소로 추가했습니다. 정확한 `orient3d`, `insphere`(점 번호 순서의 기호 섭동 포함), 평면 안 `incircle3d` 술어(부동소수점 필터 뒤 정확한 expansion), 점 집합의 Bowyer–Watson Delaunay 사면체 분할, 정확한 검증기입니다. 큰 정수·`Fraction` 행렬식과 비교했고 격자, 한 구 위의 점 껍질, 같은 평면 점 집합에서 확인했습니다. 기준 머신에서 균일한 점 10⁶개에 초당 16만 점입니다. [문서](packages/meshloom/overview.md#커널-구성-요소).

- `meshloom`: OpenPhysics의 첫 컴파일 코드 배포판을, 계획한 정확 산술 사면체 메셔의 패키징 골격으로 새로 추가했습니다. 플랫폼마다(manylinux 2.17 x86_64·aarch64, macOS 11 x86_64·arm64, Windows x64) abi3 wheel 하나에 PyO3와 maturin으로 빌드한 Rust 커널이 들어 있습니다. `kernel_available()`과 `kernel_version()`이 커널을 알려 주고, `generate3d`는 `NotImplementedError`를 냅니다. wheel에는 정적으로 링크된 허용형 Rust crate와 표준 라이브러리의 `THIRD_PARTY_NOTICES`가 들어 있습니다. 릴리스·라이선스·배포 도구가 컴파일 wheel을 빌드하고 확인합니다. [문서](packages/meshloom/overview.md).
- `sipi`: 동일 기하의 유한 금속·유전체 선로에서 DC/AC RLGC·S를 추출하며 `sipi.volume-line/1` JSON과 명시적 유한 경계를 제공합니다. [계약](packages/sipi/volume_line.md).

- `sipi`: 유한 금속 P1 전류 확산으로 DC부터 해상된 표피·근접 효과까지 계산합니다. DC 극한·전체 인덕턴스·보존 잔차와 CrossSection 부피 메시 adapter를 제공합니다. [계약과 검증](packages/sipi/conductor_diffusion.md).

- `meshine`: `extrude`가 Gmsh 없이 meshine 바닥 메시로 적층 사면체 메시를 만듭니다. 바닥 영역과 층마다 재료(또는 뺀 칸)를 주고, 하위 층은 `size`나 `divisions`로 나누며, 이웃 프리즘이 항상 맞도록 꼭짓점 순서 규칙으로 프리즘을 자르고, 면에 `z0`, `z1`, 바닥 옆면 이름, `void` 태그와 재료 사이 interface를 붙입니다. Gmsh가 없으면 건너뛰던 3D interop·비정형 공진기 시험에 적층 메시로 같은 단언을 쓰는 Gmsh 없는 쌍둥이 시험이 생겼습니다. [문서](packages/meshine/overview.md#적층-사면체-메시).

- `sipi`: single-ended Touchstone 1/2 S 입력과 명시적 조건의 네트워크 비교를 제공합니다. 복소 보간은 범위 안에서 명시적으로 선택합니다. [계약과 검증](packages/sipi/touchstone.md).

- `sipi`: `LineNetwork`의 명시 Thevenin 소스/부하를 연결해 단자 V/I·잔차·전력과 기준 전압이 명시된 주파수 NEXT/FEXT를 계산합니다. [계약·검증](packages/sipi/termination.md).

- `simcase`: simcase가 galerkin의 공개 이름만 import하는지 시험이 확인합니다. `galerkin.core`와 밑줄 이름은 쓰지 않습니다. 목록에 적힌 예외는 정상 경계 계약의 사각형 메시 검사 하나이며, galerkin에 공개 메시 검사가 생기면 없앱니다.
- 문서: 미분 계약 문서가 살아 있는 계수로 `galerkin.core` 커널을 조립하는 법을 적습니다. `galerkin.core`도 나머지 Python API와 같은 0.x 규칙을 따르고, `core.forms.matrix`는 모양만 검사하며(다른 공간에서 온 같은 모양의 표는 오류 없이 틀린 행렬을 만듦), 표 하나가 커널마다 넣을 DOF 표를 밝힙니다. 커널과 `forms.matrix`의 docstring도 같은 내용을 적습니다. `eval_edge_field_3d`가 계속 NumPy 전용인 이유도 적습니다. [문서](packages/galerkin/differentiation.md#core-커널을-직접-조립하기).
- `galerkin`: `radial_pml_coeffs`는 NumPy로 계산하며 이제 JAX·PyTorch 값인 `k`, `r0`, `d`, `sigma_max`를 `TypeError`로 거부합니다. 이것은 동작하던 경로를 없앱니다. JAX `k`나 `sigma_max`는 계수를 거쳐 `galerkin.core.kernels`, `core.forms`, `core.solve`까지 맞는 미분을 날랐습니다. 이 저장소 안에서는 그 경로를 쓰는 코드가 없었고, 계수를 받는 공개 함수(`assemble_stiffness`, `assemble_mass`)는 살아 있는 값을 거부합니다. 그렇게 미분하던 코드는 이제 NumPy 수를 넘겨야 합니다. 나머지 경우는 미분을 주지 않았습니다. PyTorch 값과 `jax.grad` 아래의 JAX `r0`·`d`는 NumPy 안에서 실패했고, eager JAX `r0`는 NumPy 배열을 돌려줬습니다. NumPy 입력의 결과는 같습니다. [문서](packages/galerkin/differentiation.md#근사하지-않고-거부하는-것).
- `galerkin`: `eval_edge_field`는 JAX·PyTorch 모서리 dofs(실수 또는 복소수, 예: 살아 있는 입력으로 푼 `solve_modes`의 `et[i]`)를 받습니다. 그러면 중심 필드는 그 라이브러리의 float64 또는 complex128 배열이고, dofs에 대한 미분을 나릅니다. 전에는 JAX dofs가 검사 없이 NumPy 연산을 지나갔고(`jax_enable_x64` 없이 float32 dofs는 float32로 남음), PyTorch dofs는 NumPy 안에서 실패했습니다. 살아 있는 dofs는 모서리마다 값이 하나여야 하고(아니면 `ValueError`), JAX는 `jax_enable_x64`가 필요합니다. 공간의 기하는 미분을 나르지 않습니다. NumPy dofs의 결과는 전과 같습니다. [문서](packages/galerkin/differentiation.md#도파관-모드-고유값-필드-축퇴-모드).
- `galerkin`: `ElementConductivity`는 `ElementHeatSource`(필드 단위 `W/m^3`)를 빌려 쓰지 않고, 단위 `S/m`, 이름 `element conductivity`인 요소 `Field`에 값을 담습니다. 모양·메시 불일치·살아 있는 값 오류 문구가 `element heat source` 대신 `element conductivity`로 시작합니다. `Field`는 단위를 기록만 하고 비교·변환하지 않으므로 값과 결과는 그대로입니다.
- `galerkin`: 온도 의존 Joule 계약 문서에 `solve_temperature_joule_heat`가 무엇을 평가하기 전에 `ValueError`로 검사하는 옵션을 나열하고, 평가 중에 난 것(하위 해석이 거부한 열전도도나 경계 자료, 범위 위반, 콜백이 낸 `Exception`의 모든 하위 예외)은 원래 예외를 원인으로 이은 `JouleConvergenceError`로 호출자에게 닿으며 history가 비어 있을 수 있다고 적었습니다. `last_temperature`를 끝난 방식마다 정의했습니다. Picard가 `max_iterations`에 닿으면 완화했지만 평가하지 않은 상태, Newton은 마지막으로 받아들인 상태, 평가가 실패하면 평가하던 상태나 그 시도 열 해입니다. 잘못된 열전도도를 감싸는 동작을 시험으로 고정했습니다. 동작은 그대로입니다. [문서](packages/galerkin/temperature_joule_heating.md#오류).
- `galerkin`: `solve_temperature_joule_heat`는 두 방법 모두 입력에 JAX·PyTorch 값이 있으면(영역 표와 경계 표 안의 값 포함) 무엇을 복사하거나 풀기 전에 `TypeError`로 거부합니다. 전에는 `thermal_dirichlet`, `initial_temperature`, `relaxation`과 두 허용오차만 `TypeError`를 냈고, 다른 입력은 `TypeError`를 원인으로 가진 `JouleConvergenceError`로, 그 입력에 넣은 non-leaf PyTorch 텐서는 `copy.deepcopy` 안에서 `RuntimeError`로 실패했으며, 살아 있는 `max_iterations`는 `ValueError`로 실패했습니다. 콜백(전도도 콜백, 또는 `outward_flux`, `convection`, `outward_current`의 경계 콜백)이 돌려준 살아 있는 값은 콜백이 돌 때에야 보이므로 여전히 `TypeError`를 원인으로 가진 `JouleConvergenceError`로 나옵니다. NumPy 결과는 그대로입니다. 미분 문서에 반복 solver의 규칙을 적었습니다. 미분은 잔차의 음함수 미분이며, 반복을 한 번 더 돌린 미분이 아닙니다([문서](packages/galerkin/differentiation.md#반복-solver)).
- `meshine`: `TetMesh`, `check`, `write_msh`가 OpenPhysics 자체 3D 메셔의 사면체 메시 계약을 정합니다. `galerkin.from_mesher`가 읽는 필드와 interface, 정확한 방향 검사(부동소수점 필터, 나머지는 `Fraction`), 위반 사항을 모두 나열하는 면·태그·감김·영역 검사, 품질 지표, Gmsh 없이 쓰는 Gmsh MSH 4.1 ASCII 출력입니다. 3D 생성기는 아직 없고 합격 기준은 사전 등록했습니다. [문서](packages/meshine/overview.md#사면체-메시-계약), [검증 계획](packages/meshine/validation3d.md).
- `sipi.PowerPlane`을 추가합니다. 전압 소스, 전류 부하, 절개가 있는 구리 전원면의 DC 전압강하(IR drop)를 계산하며, 정확한 띠, 원환, 무한 시트 두 패드 저항과 비교해 검증했습니다. 비아, 여러 층, 온도 의존 구리는 모델에 없습니다. [문서](packages/sipi/overview.md#전원면-dc-전압강하ir-drop).
- `galerkin`: `solve_temperature_joule_heat(..., method="newton")`은 전위와 온도를 함께 Newton으로 풉니다. 한 걸음에 희소 풀이 한 번(complex-step 요소 Jacobian), 온도 결함에 대한 반감 선 탐색을 쓰며, 수렴 검사·결과·이력은 그대로인 완화 Picard(`method="picard"`)와 같습니다. `method`의 기본값은 `"picard"`이며, 언제 `"newton"`을 쓸지는 계약 문서에 있습니다. JSON 문서는 계속 Picard 반복을 씁니다. 계약 문서의 전류 구동 서미스터에서 3–4개 상태로 수렴하며, 기본 완화 0.5의 Picard가 100회 안에 수렴하지 않는 강한 피드백(alpha = 7, 9 /K)에서도 수렴합니다. `ConductivityModel`은 Newton 걸음에 쓰는 선택 `derivative`(dσ/dT)를 받습니다. [문서](packages/galerkin/temperature_joule_heating.md#newton-방법).
- `galerkin`: 열 해석의 경계 연립(Robin 행렬, 유속·주변 하중)을 `galerkin.thermal`의 공개 이름 `scalar_boundary_system`으로 두어, `solve_temperature_joule_heat`의 Newton 방법이 열 해석과 같은 연산자를 선형화합니다. 열 결과는 바뀌지 않습니다.
- `galerkin`: Joule 발열 공식을 `galerkin.core.kernels.p1_joule`로 옮겨 `solve_steady_electric`가 NumPy와 JAX·PyTorch 입력에 똑같이 쓰며, 하중은 `p1_load`의 중심점 규칙으로 계산합니다. 전기 결과는 비트 단위로 같습니다.
- `galerkin`: `solve_material_cavity_box`, `mode_coordinates`, `scalar_coordinate_system`, `solve_scalar_coordinates`, `assemble_mode_system`, `solve_dirichlet`, `l2_error`, `eval_edge_field_3d`는 NumPy로 계산하며 이제 JAX·PyTorch 값을 `TypeError`로 거부합니다. 전에는 대부분의 입력에서 JAX 배열이나 `requires_grad`가 없는 PyTorch 텐서를 NumPy로 바꿔 미분이 끊긴 NumPy 결과를 돌려줬습니다. 이런 호출은 이제 NumPy 수를 넘겨야 합니다. 몇몇 입력은 이미 관련 없는 오류로 실패했고(`assemble_mode_system`·`scalar_coordinate_system`·`solve_scalar_coordinates`의 `k0`, `solve_scalar_coordinates`의 `n_target`, `l2_error`·`eval_edge_field_3d`와 `mode_coordinates` 대부분의 입력에 넘긴 PyTorch 값), `solve_material_cavity_box`와 `mode_coordinates`의 PML 두께는 `ValueError`를 냈으며, 추적 중이거나 `requires_grad`인 값은 NumPy 안에서 실패했습니다. NumPy 입력은 그대로입니다.
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

- `meshine`: `generate(candidate_order="stable")`는 반지름이 같은 세분 후보의 입력 순서를 유지합니다. 기본 `"legacy"`는 기존 quicksort 선택을 보존합니다. SIPI는 native/WebAssembly 동률 순서 차이를 막기 위해 stable을 사용합니다. 동률이 있는 SIPI 메시는 바뀔 수 있으며 임의의 수치 라이브러리 버전 사이에서 동일 메시를 보장하지는 않습니다.
- `meshine`: `generate`는 삽입이 `max_points`를 넘기려 하면 `RuntimeError` 하위 클래스인 `MeshSizeLimitError`를 발생시키고, 만들어진 입력 영역도 세분화 작업 전에 상한과 비교합니다. 그래서 점이 더 많은 입력은 세분화되거나, 삽입이 필요 없을 때 상한을 넘긴 채 반환되지 않고 그 자리에서 거절됩니다. 꼭짓점 수에 대해 O(V²)인 영역 만들기는 여전히 먼저 실행됩니다. [문서](packages/meshine/overview.md#안전장치).

- `galerkin`: 정상·과도 열→역학 workflow가 단계를 연성 층의 `OneWayChain`으로 실행하고, 각 절점 Kelvin 장을 동결하기 전에 같은 메시 `transfer`에 통과시킵니다. 결과·manifest JSON·단계 오류와 메시지는 바뀌지 않습니다. [문서](packages/galerkin/thermal_mechanical_workflow.md).

- `galerkin`: 한 방향 Joule workflow와 `ElementHeatSource`가 연성 층 위에서 동작합니다. Joule 열은 전기 메시 위의 요소 `Field`이고 같은 메시 전달로 열 메시에 옮겨지며, `ElementHeatSource.field`로 볼 수 있습니다. 결과·검산·오류 메시지는 바뀌지 않습니다. [문서](packages/galerkin/joule_heating.md#요소-열원-api).

- `galerkin`: 새 `galerkin.coupling` 층. `Field`는 한 메시의 절점 또는 요소 값을 SI 단위와 함께 담고, `transfer`는 그것을 같은 메시로 그대로 옮기며, `OneWayChain`은 한 방향 workflow의 단계를 실행하고 실패에 단계 이름을 붙입니다. 커널 인터페이스를 문서로 정하며, 유한요소 엔진이 첫 커널입니다. 기존 workflow는 바뀌지 않습니다. [문서](packages/galerkin/coupling.md).

- `galerkin`: PEC 상자 공진기(`solve_cavity_box`)가 JAX나 PyTorch 상자 길이를 받고, 주파수, 고유값, 모서리 계수, 중심 필드를 그 라이브러리로 돌려주며 역방향 미분을 붙입니다. 메시의 축 방향 배율을 거쳐 정확합니다. 축퇴 모드는 NaN 미분과 `DegenerateModeWarning`을 받습니다. NumPy 결과는 바뀌지 않습니다. [문서](packages/galerkin/differentiation.md#상자-공진기-길이에-대한-미분).

- `galerkin`: 도파관 모드(`solve_modes`)가 eps_r, mu_r(스칼라 또는 요소 배열, 실수·복소수)와 k0에 JAX나 PyTorch 값을 받고, n_eff와 두 필드 배열을 그 라이브러리로 돌려주며 고유값과 필드의 역방향 미분을 붙입니다. 축퇴 모드는 NaN 미분과 `DegenerateModeWarning`을 받습니다. NumPy 결과는 바뀌지 않습니다. [문서](packages/galerkin/differentiation.md#도파관-모드-고유값-필드-축퇴-모드).

- `galerkin`: 탄성과 열탄성이 E, nu, alpha, 기준 온도, Dirichlet 변위, 체적력, 견인력에 JAX나 PyTorch 값을 받고 역방향 미분을 돌려줍니다. NumPy 결과는 바뀌지 않습니다. [문서](packages/galerkin/differentiation.md).

- `galerkin`: 과도 열전도가 전도도, 열용량, 열원, Dirichlet 온도, 초기 온도장에 JAX나 PyTorch 값을 받고, 모든 시간 단계를 거치는 역방향 미분을 돌려줍니다. `checkpoint_every`로 재계산과 메모리를 맞바꿀 수 있습니다. NumPy 결과는 바뀌지 않습니다. [문서](packages/galerkin/differentiation.md#과도-열-메모리와-checkpoint).

- `galerkin`: 정상 열전도와 정상 전기 전도가 전도도, 열원, Dirichlet·기준 전위, 경계 데이터에 JAX나 PyTorch 값을 받고, 결과를 그 라이브러리로 미분과 함께 돌려줍니다(adjoint 희소 풀이를 통한 역방향 모드). NumPy 결과는 바뀌지 않습니다. 아직 미분하지 않는 solver는 미분을 조용히 버리지 않고 JAX·PyTorch 값을 거부합니다. [문서](packages/galerkin/differentiation.md).

- `sipi`: 수동 유전체 완화/표 모델, 엄격 재료 JSON, 동일 메시의 주파수별 복소 C/G 추출. [계약·검증](packages/sipi/dielectrics.md).
- `sipi`: 명시한 RLGC의 균일 전송선 2N포트 S, 차동/공통 변환, single-ended Touchstone 2.0 출력을 추가했습니다. 단면 C/L/G를 재사용하고 R을 필수로 받습니다. 도체 손실 추출은 미구현입니다. [계약](packages/sipi/network.md).
- `sipi`: 중심정렬 사다리꼴 도체의 실제 메시, 평탄 코팅 microstrip, 기존 v1을 보존하는 엄격 JSONv2를 추가했습니다. [계약·검증](packages/sipi/manufacturing_sections.md).
- `sipi`: 직사각형 단면 템플릿 4종, 엄격한 `sipi.cross-section/1` JSON 입력, 메시 설정 해석과 별도 세분 검사를 포함한 제한 있는 목표 임피던스 설계를 추가했습니다. [계약](packages/sipi/design.md).
- 신호·전원 무결성 패키지 `sipi`를 추가합니다. 층 유전체와 직사각형 트레이스로 된 PCB 단면을 준정적(quasi-TEM)으로 풀어 C·L·유전 손실 G 행렬, 단일선 임피던스와 유효 유전율, 결합선 even/odd 모드를 계산합니다. 평행판·동축 정확해, Cohn 스트립라인 정확해, Hammerstad–Jensen 마이크로스트립 식과 비교해 검증했으며 도체 손실은 포함하지 않습니다. `openphysics[sipi]`로 설치합니다. [문서](packages/sipi/overview.md).
- `sipi`: 유한 두께 트레이스의 기본 단면 메시 과도 세분을 줄였습니다. 층·폭·간격 기준은 유지하면서 모서리 크기의 두께 제한을 두께 / 100에서 두께 / 10으로 바꿨습니다. 명시적 메시 설정은 그대로입니다.

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
