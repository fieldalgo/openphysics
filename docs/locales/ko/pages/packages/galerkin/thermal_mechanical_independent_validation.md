# 정상 열전도 → 기계 workflow 독립 수용

[English](../../../../../packages/galerkin/thermal_mechanical_independent_validation.md)

**한눈에 보기**

- **확인하는 것:** `galerkin.thermal_mechanical.solve_steady_thermoelasticity`를 독립 수용 검증합니다. Dirichlet·단열 정상 열전도, 같은 메시 절점 P1 온도의 정확한 전달, 처방 온도 기계해석을 평면응력·평면변형률에서 확인합니다.
- **고정 기준:** n=8/16/32/64의 모든 구간에서 온도·변위 L2 차수 ≥ 1.8, 열유속·변형률·3D 전체 응력·에너지 노름 차수 ≥ 0.9가 필요합니다. 정확 균일·선형 장과 열수지는 1e-10, 기계 잔차·힘·모멘트는 1e-9로 일치해야 합니다.
- **범위:** 단방향 끝점 기계해석입니다. Robin, 외향 열유속, 표면하중, 과도 열전도, 되먹임, CLI/Studio, 저장은 범위 밖입니다. 아래 후보 기록은 그대로 보존하며, 특정 커밋의 결과는 그 커밋의 CI 실행에서 확인하세요.

명시 생산 후보 **b4131d0dab425c2ba54380492e33109f78a92a0b**의 공개 Python
workflow를 수용합니다. 이는 초기 **48920cc066708784864c95eb5bae597b0e2a2abd**의
정상 후속입니다. 독립 시험 코드는 **ecc924b80603426cd751cf3fc0fa62b25cedd976**에
고정했습니다. 구현을 보기 전에 독립 수학과 gate를 동결했으며 producer 검사는 회귀
근거일 뿐 독립 oracle이 아닙니다. 독립 추가 파일은 생산/refsol/기존 시험/설정을 수정하지 않았으며, 아래 별도 배정
후속의 producer 소유 guard 변경만 정상 merge했습니다.

범위는 Dirichlet·단열 정상 열전도, 같은 메시 nodal-P1의 정확 snapshot 복사,
처방 온도 기계단계입니다. Robin·외향 flux·기계 traction·재메시·반복·피드백·과도열·
CLI/Studio·저장은 포함하지 않습니다. One-way endpoint 기계단계이며 열역학적
완전 연성이나 가열 경로의 에너지 수지가 아닙니다.

## 독립 법칙과 약형식

Oracle은 NumPy만 import합니다. Cartesian Vandermonde 역행렬, 독립 Duffy 구적,
직접 구성한 정사각형 topology를 사용합니다. 생산 D/열하중/assembly/geometry helper,
refsol 및 producer의 별도 oracle을 정답으로 import하지 않습니다. 공개 component
해석을 두 번 호출하는 것은 이산 기계 기여분을 분리하기 위한 것입니다.

a=alpha(T-Tref), mu=E/[2(1+nu)], lambda=E nu/[(1+nu)(1-2nu)]로 두고 원래
3차원 tensor 법칙에서 시작합니다.

```text
elastic strain = epsilon - a I
sigma = 2 mu (epsilon-a I) + lambda tr(epsilon-a I) I
psi = mu (epsilon-a I):(epsilon-a I) + .5 lambda tr(epsilon-a I)^2
PS: sigma_zz=0 -> epsilon_zz=((2mu+3lambda)a-lambda(exx+eyy))/(2mu+lambda)
PE: epsilon_zz=0
```

Engineering gamma_xy는 tensor epsilon_xy의 두 배입니다. z를 포함한 원 법칙을
점별 평가하고 unit-strain probe로 norm/compliance의 면내 tangent를 만듭니다.
PE의 축약 자유 팽창 계수는 (1+nu)a이지만 물리적 thermal eigenstrain은 여전히 aI입니다.

e=(exx,eyy,gamma_xy), m=(1,1,0)에 대해 q는 PS E a/(1-nu), PE E a/(1-2nu)입니다.
독립 virtual-work 적분으로 stiffness 작용, 양의 g=integral B^T q m, body
f=integral N^T b, 열 K_T(T-Tref), f_Q=integral N Q를 평가·조립합니다. 반환 residual이나
producer 열수지 summary를 정답으로 사용하지 않습니다. 균일 q는 체적 발산이0이어도
경계 functional이0이 아니므로 body-only 대체는 균일 자유 팽창을 놓칩니다. 이
Dirichlet·단열 workflow의 H는0이며 Robin 행렬을 가정하지 않습니다.

```text
mechanical residual = K u-f-g
reaction = residual on prescribed components, zero on free components
U = integral psi = .5 u^T K u-u^T g+CT
2U = u^T f+u_D^T r_D-u^T g+2CT
CT_PS = integral E a^2/(1-nu)
CT_PE = integral 1.5 E a^2/(1-2nu)
heat: residual=K_T T-f_Q, sum(f_Q+reaction)=0
outward integrated heat = -sum(heat reaction)
```

Support work와 PE z/잔여 기여가 필수입니다. P1 온도는 요소 내부에서 변하므로 중심
온도를 제곱하지 않고 T²를 적분합니다. 전체 strain은 요소별 상수이며 반환 stress/
thermal·elastic strain/epsilon_zz/sigma_zz는 중심 표본으로 검사합니다. Full stress
오차는 실제 P1 T와 원 3D 법칙을 내부 구적점에서 복원하여 구합니다. 열 load/reaction/
residual은 W/m, flux는 W/m², 기계 힘은 N/m, physical U는 J/m입니다. 열의 quadratic
work는 W K/m이며 탄성 에너지나 저장 열이라고 부르지 않습니다.

## 사례·오차 분리·불변 gate

1m 정사각형, k=10 W/(m K), E=70e9 Pa, nu=.3, alpha=12e-6/K,
Tref=293.15 K를 씁니다. 양 plane에서 n=8/16/32/64의 **인접 세 구간 모두** 검사합니다.

- Uniform theta=20 K: 최소 scalar 구속3개 및 별도의 외벽 전체 영변위 사례.
  자유 PS u=a(x,y), sigma=U=0. 자유 PE u=(1+nu)a(x,y), 면내 stress0,
  sigma_zz=-Ea=-16.8MPa, U/area=.5Ea²=2016 J/m³입니다. 완전 구속 PS는 법선
  stress=-24MPa/U density5760, PE는 모든 법선 stress=-42MPa/U density15120입니다.
  sigma*n과 half-edge corner 기여로 변별·corner 반력을 직접 구합니다. 냉각·음수
  alpha·alpha0는 별도 사례입니다.
- Linear T=Tref+10+20x, Q=0, 좌우 열 구속·상하 단열.
  v=(alpha10x+.5alpha20(x²-y²),alpha10y+alpha20xy), PS u=v, PE u=(1+nu)v.
  열은 P1-exact이고 변위는 이차이므로 그 기계 오차를 전달 오차로 오인하지 않습니다.
  Support 값을 먼저 확인한 뒤 mass-weighted additive 강체 병진/미소 회전만 fit합니다.
  Affine·shear/scale/strain fit이나 finite Procrustes 회전은 허용하지 않습니다.
- Sine T=Tref+20S, u=(1e-4,.6e-4)S m, S=sin(pi x)sin(pi y), 외벽 전체 열 Tref와
  해석 변위를 지정합니다. Q=2 k20 pi² S. Body는 원 total stress의 미분에서
  -mu Laplacian(u)-(lambda_eff+mu)grad(div u)+beta grad T로 유도하며 beta/탄성
  계수는 원 법칙 probe입니다. 별도 사전 동결 수학에서 원 3D 발산을 독립 중심차분으로도
  검사했으나 그것을 실제 FEM 대신 사용하지 않습니다.

Ledger는 해석 T/u, 보간 I_hT, 실제 열 T_h, 정확 snapshot S_h=T_h, 처방 u_h[I_hT],
chain u_h[T_h]를 구분합니다. 온도 보간과 nodal heat correction은 장으로 합쳐 total
heat error가 됩니다. Prescribed 기계 오차+heat-induced delta_u는 chain 오차와
벡터로 같으며 norm은 가산적이지 않습니다. 전달은 배열 동일성이지 fit한 차수가 아닙니다.
같은 생산 기계 component를 두 번 푸는 것은 기여분 분리이며 해석 정답을 만드는 과정이 아닙니다.

같은 body/support 조건에서는 delta_u의 처방 값이0이며 독립 thermal-stress
변화 delta(qm)에 대해 다음을 확인합니다.

```text
||delta_u||_K <= ||D^(-1/2) delta(qm)||_L2
```

상수는1, 단위는 sqrt(J/m)입니다. 고정된 정규화 roundoff 여유1e-10을 명시하며
거의0인 linear heat 차이에는 차수를 만들지 않습니다. 사전 uniform은 이 bound를
포화했고 실제 sine 이산 두 해도 만족합니다.

원 gate는 그대로 유지합니다.

- 모든 구간 L2 T/u 차수>=1.8, H1 seminorm/flux/strain/full3D stress/tangent
  energy-norm 차수>=.9. 해당하는 prescribed 및 chain mechanics 모두 검사합니다.
- Uniform/linear heat 정확성 및 정규화 uniform 장/반력/U<=1e-10;
  열 residual/성분 수지<=1e-10, 기계 residual/물리 힘/모멘트<=1e-9,
  원 3D stress/U/support-work 항등식<=1e-10.
- Norm 구적8×8/10×10 차이<측정한 비영 오차1%, 연속체 physical U12×12/16×16
  차이<=고정 에너지 scale1e-8.
- Sine physical-U 상대오차 단조 감소·최종<=.02. Raw energy에 임의2차 gate를
  만들지 않습니다. 외부 m/mm/um 명시 변환의 일치<=1e-9.

정규화는 L=1m, theta*=20 K(linear30 K), strain*=max(|alpha|theta*,1e-4/L,
.6e-4/L), sigma*=E strain*, force*=sigma*L, moment*=force*L,
U*=E strain*² area입니다. 열 scale=max(k30,integral |Q|)이며 정확0인 에너지/stress,
절대 Tref나 상쇄된 순 힘으로 나누지 않습니다. Support-gradient 변형 사례에는 실제
비교 가능한 기계 scale을 사용합니다.

## 실제 수치 근거

각 행은 8→16,16→32,32→64이며 유리한 마지막 두 구간만 고른 값이 아닙니다.
| Case / plane | u L2 orders | u H1 orders | strain orders | full 3D stress orders | tangent energy-norm orders |
|---|---|---|---|---|---|
| linear / stress | 1.880927, 1.957799, 1.986410 | 1.017262, 1.011588, 1.005117 | 0.962522, 0.987473, 0.996022 | 0.980940, 0.993448, 0.997904 | 0.976221, 0.991961, 0.997442 |
| linear / strain | 1.875303, 1.957907, 1.987224 | 1.017359, 1.011805, 1.005215 | 0.963903, 0.987991, 0.996198 | 0.983130, 0.993985, 0.998045 | 0.978170, 0.992552, 0.997622 |
| sine / stress | 1.974154, 1.992991, 1.998197 | 0.994778, 0.998802, 0.999708 | 0.996900, 0.999346, 0.999844 | 1.018590, 1.004798, 1.001208 | 0.997224, 0.999433, 0.999867 |
| sine / strain | 1.965368, 1.990436, 1.997520 | 0.999449, 1.000082, 1.000037 | 1.001758, 1.000724, 1.000200 | 1.060010, 1.016053, 1.004083 | 1.002938, 1.001041, 1.000281 |

Prescribed-mechanics도 모든 구간을 통과했습니다. 최저 prescribed u L2 차수는
linear1.880927/1.875303, sine1.977839/1.972497(PS/PE)입니다. Sine heat L2 차수는
1.974492,1.993493,1.998363, heat H1/flux는 .989101,.997254,.999312입니다.
Linear heat/flux는 원 정규화1e-10 내에서 정확하며 차수를 주장하지 않습니다.
Snapshot 전달은 모든 mesh에서 정확히0입니다.

| Sine / plane, n64 | heat L2 K | interpolation L2 K | nodal-correction L2 K | prescribed u L2 m | heat-induced u L2 m | total u L2 m |
|---|---:|---:|---:|---:|---:|---:|
| stress | 0.006759846697 | 0.0049176047 | 0.002040899385 | 3.173073191e-08 | 2.655169708e-09 | 3.234097101e-08 |
| strain | 0.006759846697 | 0.0049176047 | 0.002040899385 | 3.170303274e-08 | 3.852302631e-09 | 3.299352745e-08 |

n64 sine perturbation energy norm/bound는 PS .005092452628/.01095261542,
PE .008094146270/.01651994279 sqrt(J/m)입니다. 전체 mesh의 physical-U 상대오차는
PS [.04493895740,.01139003516,.002857136716,.0007148822010],
PE [.05036883381,.01279098160,.003210043739,.0008032724247]입니다.

실제 runtime wrong-physics **9대안**을 검출했습니다: thermal RHS 부호, 3alpha,
PE 면내 alpha 단축, T-Tref 대신 절대 T, sigma_zz 누락, PE 잔여 에너지 누락,
centroid-T² 에너지, support work 누락, body-only 열하중입니다. 공개 stage alias를
메모리에서 patch하여 잘못된 수치 인자로 실제 solver를 실행하거나 출력을 변조한 뒤,
독립 audit이 실패해야 합니다. 생산 파일은 변경하지 않습니다. 사전 수학22대안 및
잘못된 입력 거절과 다른 근거입니다.

## 실행 계약과 출처 주장 한계

Raw float/bool/clockwise/nonfinite/out-of-range 형상·metadata, 정확 SI 선언,
잘못된 scalar/body/source shape·nonfinite, 연결 성분별 열·기계 강체 anchor,
input/heat/transfer/mechanics/manifest의 stage 및 원인 예외 연결, 잘못된 전달 후
mechanics 미호출을 검사합니다. -finfo(float).tiny까지 모든 negative K를 거절하며
실제 열해의 음수 K와 주입한 잘못된 transfer를 각각 실행했습니다. Linux 확장 범위
cast overflow는 offending node를 표시합니다. 유한20K·0K는 유효하며 Celsius
추론·clamp·offset·기준온도 보정을 주장하지 않습니다.

모든 단계는 같은 내부 소유 격리 mesh를 사용합니다. Caller callback 변경은 복사한
형상/구속/region metadata를 바꾸지 못하고, 관측한 내부 소유 형상·region 변경은 해당
stage 경계에서 실패합니다. Region validation/lifetime 및 cast overflow가 b413의
생산 delta이며 thermal/thermoelastic core blob은489와 같습니다. Snapshot은
canonical immutable bytes를 보존해 이후 heat/caller/reference-mesh 변경과 분리됩니다.
순서·scale·stale geometry·schema/units/hash 변경은 component 재사용 시 거절합니다.
반환 후 가변 결과의 무결성을 재인증하지 않는다는 한계를 유지합니다.

Manifest canonical JSON과 접근마다 새 dictionary는 실제 SI/재료/구속,
constant-vs-unfingerprinted callback 표시, 정확 복사 정책, hash, 완료 stage,
origin·물리량 단위를 기록합니다. Hash는 식별자이지 서명이 아닙니다. Workflow가
열 호출을 소유했다는 사실이 callback 동작·물리 단위·freeze 전 의도를 인증하지 않습니다.
유한20K나 m로 거짓 표시한 mesh에서 의도한 출처를 알아낼 수 없습니다. 자동 cross-mesh
보정·thread safety·입력 출처 인증·반환 후 무결성 인증을 주장하지 않습니다.

## 재현·실패·검증 경계

```bash
# Run from the repository root, using an environment with existing dependencies.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export BLIS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PIP_NO_INDEX=1 PIP_DISABLE_PIP_VERSION_CHECK=1
python -m pip install --no-index --no-deps --no-build-isolation \
  -e packages/galerkin -e packages/galerkin-refsol -e packages/meshine \
  -e packages/gmshio -e packages/physmat -e packages/simcase
python -m pytest -c pyproject.toml -q -s \
  tests/galerkin/test_thermal_mechanical_independent_validation.py
python -m pytest -c pyproject.toml -q -ra
```
```bash
python -m pip wheel --no-index --no-deps --no-build-isolation \
  packages/galerkin -w wheelhouse
# Install the wheel into a separate environment; do not use an editable install.
python -m pip install --no-index --no-deps wheelhouse/galerkin-0.1.0-py3-none-any.whl
# Copy the independent oracle and test together into an external test directory.
# ACCEPTANCE_TEST_DIR denotes that directory, outside the source checkout.
python -m pytest -c pyproject.toml --confcutdir="$ACCEPTANCE_TEST_DIR" -q -s \
  "$ACCEPTANCE_TEST_DIR/test_thermal_mechanical_independent_validation.py"
```

설치본은 source PYTHONPATH를 제거하고 source conftest를 수집하지 않습니다.
Root conftest는 의도적으로 checkout import를 강제하므로 독립 oracle/test만 checkout
밖으로 복사하고 위 confcutdir를 사용합니다. 실제 module __file__와 hash를 기록하며
단순 import 성공만으로 설치본 검증이라 부르지 않습니다.

Linux Python3.12.14 / NumPy2.3.5 / SciPy1.17.0, 기존 의존성의 격리 venv,
thread6변수 모두1. Source origin은 해당 checkout, 설치 origin은 별도 venv의
site-packages입니다. 두 workflow 파일 모두 Git blob
**28ecea0150234cff77bcd3d7a0a2c39252a8caa1**, SHA256
**77e196d31ffa99b396a54169794ece6a947d5bbc3db12a4bbaea8de85469d648**입니다.
b413 wheel SHA256은
**44d63f83196503dc3d1e5a5ec41b2bd7c539a672ba907de14a9c074c2ce15391**입니다.
새 의존성이나 GPL solver 구현 source는 사용하지 않았습니다.

- 초기489 독립 source81pass/0skip은 b413 이전의 역사적 결과입니다.
- b413 첫 독립 source89pass/1fail/0skip: region-name 음성 fixture가 이미 바꾼
  동일 이름을 다시 대입해 실제 변경이 없었습니다. 다른 이름으로 fixture를 정정한 뒤
  영향3pass/87deselected. 생산/gate 변경은 없고 원 실패 로그를 보존했습니다.
- 최종 설치 독립90pass/0fail/0skip에 모든 mesh와 runtime wrong9대안이 포함됩니다.
  관련 source component/기존 독립/API 회귀226pass/0fail/0skip이며 producer 결과를
  독립 개수로 합치지 않습니다.
- 최초 최종 root 실행은 **1001pass / 3fail / 16skip / 하위검사9pass**,
  Starlette deprecation warning1개입니다. JUnit에서 독립90개는 모두 통과했습니다.
  기존 dependency guard가 표준 라이브러리 collections/contextlib/copy/json을 거절한
  1실패와, source venv에 local simcase를 설치하지 않아 난 cavity CLI2실패입니다.
  기존 로컬6패키지를 no-index/no-deps로 설치한 뒤 CLI 해당2개는 통과했습니다.
  원 전체 결과는 실패로 보존하며 깨끗한 전체 통과로 다시 표시하지 않습니다.
  명시 후속 **e2a1a26a2bb46aa9b0d3a860a34c55d5c960aa81**는 producer 소유
  test_independence.py 한 파일만 변경합니다(blob a94ff620d18e0cce8cd5f8665ce12b03a0c984e1).
  정상 merge 후 source pytest collection에서 기존 실제2개 대비 **6개**를 관측했습니다.
  Source guard **6pass/0fail/0skip**, 설치 engine guard **6pass/0fail/0skip**이며
  표준 라이브러리 허용과 httpx/requests/refsol 거절 probe, 별도 refsol 금지를 유지합니다.
  설치 검사는 빈 복사 시험 경로 대신 collection에서 ENGINE을 실제 site-packages로
  명시 연결합니다. Workflow를 포함한 **runtime Python18모듈**이 source와 기존b413
  wheel 사이에서 직접 byte-identical이며 독립 oracle/test byte도 고정했습니다. 따라서
  수치90·관련226·전체를 자동 반복하지 않았습니다. 이 target 회복은 새로 깨끗한 전체
  실행 결과가 아니며 오너의 별도 최종 release 결합/fullsource를 기다립니다.

다른 최초 실행 오류도 보존했습니다. 첫 explicit-file pytest는 package 설정을 골라
ModuleNotFoundError(galerkin) collection 오류가 났으며 root의 -c pyproject.toml로
정정했습니다. Heredoc 상대경로 오류는 아무 파일도 쓰지 않았고 뒤의16pass는 이전
uniform 시험이지 새 계약 검사가 아닙니다. Origin script도 sibling 경로 오류로2회
cannot-open 후 정정 실행했습니다. 초기489 wheel binary는 후속 build에 덮어써져 원 binary 대신 build log/hash만
보존했습니다. Build 성공 후 pip network check가
차단됐고 최종b413 wheel build/install은 no-index와 version-check 비활성화를 사용했습니다.
이는 실행/fixture 오류이며 수치 gate를 완화한 것이 아닙니다.

Source text/configuration은 exact 후보 blob과 대조했습니다. Hydrated source에서
무관한 binary PNG7개는 빠져 있어 figure-asset packaging 완결성을 주장하지 않습니다.
Galerkin 수치 wheel에는 검증한 module이 포함되지만 공용 release manifest/doc asset
배포는 별도 검토입니다. 공유 host 시간은 metadata이며 성능 기준선이 아닙니다.
Actions는 조회·실행하지 않았고 Windows runner 수용은 중단/미검증입니다.
Linux 결과로 Windows를 대신하지 않습니다. Develop 통합이나 배포도 주장하지 않습니다.
