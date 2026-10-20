# 처방 온도 열탄성 traction 독립 수용

[English](../../../../../packages/galerkin/thermoelastic_traction_independent_validation.md)

명시 생산 후보 **b3e8d7291f7c82788bf813d5d85bca21244f1df5**, 독립 코드 checkpoint
**5c08599ac0ffd8b16808e6d37eb4d312f75557b3**를 수용합니다. 원 3D oracle과 수치 gate는
구현 열람 전에 고정했습니다. Producer62개와 준비 대수를 독립 FEM 수용으로 쓰지 않습니다.
전용 oracle/pytest/isolated consumer/이 전체ENKO 보고만 추가하며 생산/refsol/기존 시험/
공용 설정은 변경하지 않습니다.

확장은 처방 nodal-P1 Kelvin 열탄성에 명시 TOTAL 기계 traction을 더합니다. 열전도,
별도 one-way workflow, Robin, CLI/Studio, 저장/feedback/과도/비선형/3D/locking 해결은
범위 밖입니다. 고정 T의 endpoint 기계계산이며 가열 경로 열역학적 일·저장열 모델이 아닙니다.

## 독립 법칙·하중·에너지

동결 oracle은 NumPy만 import합니다. PS z를 제거하거나 PE z를 고정해 full3D stress/
energy를 도출하고 균일 patch는 inverse3D compliance에서 구합니다. Cubic MMS의 body는
원 stress의 명시 Hessian 미분이며 별도 complex-step 발산으로 확인했습니다. 생산/refsol
constitutive/load/quadrature/geometry/reference를 정답으로 쓰지 않습니다. 공개 component
해석은 검사 대상이며 private producer alias는 runtime fault actor로만 patch합니다.
```text
mu=E/[2(1+nu)], lambda=E nu/[(1+nu)(1-2nu)], a=alpha(T-Tref)
sigma=2mu(epsilon-aI)+lambda tr(epsilon-aI)I
psi=mu(epsilon-aI):(epsilon-aI)+.5lambda tr(epsilon-aI)^2
PS: (2mu+lambda)ezz+lambda(exx+eyy)-(2mu+3lambda)a=0
PE: ezz=0
q_PS=Ea/(1-nu), q_PE=Ea/(1-2nu), m=(1,1,0)
K u=f_body+f_traction+g, g=integral B^T q m
F=f_body+f_traction, r=K u-F-g
U=integral psi=.5uKu-u.g+CT
2U=u.F+u_D.r_D-u.g+2CT
CT_PS=integral Ea^2/(1-nu), CT_PE=integral 1.5Ea^2/(1-2nu)
```

Engineering shear gamma_xy=2epsilon_xy입니다. Traction은 이미 물리 TOTAL sigma*n이므로
q*n을 보정하지 않습니다. g는 양의 thermal equivalent load이지 별도 물리 외력이 아닙니다.
g의 강체 합력/모멘트는0이므로 global balance만으로 오분류를 잡지 못하고 nodal split과
비강체 work를 따로 대조합니다. 입력 traction은 Cartesian Pa, body N/m³, 조립 body/
traction/g/reaction/residual은 두께당 N/m, moment N, physical U/work J/m입니다.
열 W/m을 기계 힘에 더하지 않습니다.

독립 Cartesian Vandermonde gradient와 Duffy 구적으로 실제 P1 변위 strain·내부 보간
T를 복원해 stiffness 작용/body/positiveg/원 residual/reaction을 평가합니다. 독립 owner-side
segment normal과8점 선적분으로 생산4점 loader를 감사합니다. 추가로 degree0..6 traction
monomial을 정확 유리 모멘트 L/[(k+1)(k+2)], L/(k+2)와 대조하므로 단순히 두 구적
구현끼리 비교한 것이 아닙니다.

Full3D stress/energy에는 PE sigma_zz와 잔여 .5Ea²가 필요합니다. 반환 total strain은 요소
상수, thermal/elastic strain/stress/sigma_zz/epsilon_zz는 centroid 표본으로 해당 위치에서
검사합니다. Full stress norm은 실제 P1 T의 내부 원 법칙 복원을 사용하며 centroid-T²는
에너지 적분이 아닙니다. 비영 처방 변위에는 support work가 필요하고 독립 적분 U,
.5uKu-u.g+CT, endpoint 외력/support work가 일치합니다.

## 사전 사례와 고정 gate

Uniform theta20K, 목표 S=[[8e6,3e6],[3e6,-2e6]]Pa, body0입니다. 3D compliance
(epsilon-aI)=[(1+nu)sigma-nu tr(sigma)I]/E에서 PS sigma_zz=0 또는
PE sigma_zz=nu*tr(S)-Ea를 넣고 u=(exx*x+gamma_xy*y,eyy*y)+c를 만듭니다.
왼쪽 두 성분에 정확 변위, 오른쪽/상하에 total S*n을 주며 별도로 처방 성분인 왼쪽에도
traction을 더합니다. Heating/cooling·signed/zero alpha·None/{}·S0 자유팽창·T/Tref
동시 shift로 기존 계약을 확인합니다.

V2 mixed polynomial과 정확 linear-T 대조:
```text
L0=1 m; X=x/L0, Y=y/L0; c0=1e-4; c=(2e-5,-1e-5) m
E=70e9 Pa, nu=.3, alpha=12e-6/K, Tref=293.15 K
u=c0 L0(X^3+2XY^2+XY, 2X^2Y+Y^3+X^2)+c
theta=12+9X-4Y+6XY+3Y^2 K
linear-T control: theta=12+9X-4Y K
e=c0(3X^2+2Y^2+Y, 2X^2+3Y^2, 8XY+3X)
d_x e=c0/L0(6X,4X,8Y+3), d_y e=c0/L0(4Y+1,6Y,8X)
b=-(d_x sigma_xx+d_y sigma_xy, d_x sigma_xy+d_y sigma_yy)
```

왼쪽 두 성분 u를 처방하고 다른 면에는 해석 sigma*n을 가합니다. 해석 T로 body/traction을
만들고 정확 절점 T를 P1로 고정합니다. 실제 u_h·복원 stress를 연속체 u/T와 비교하고
P1 T의 self-consistency는 따로 감사합니다. 비선형 T 보간오차는 기계 일관성의 일부이며
열 solver/transfer 오차가 아닙니다. Linear-T는 정확 보간인 별도의 manufactured load 문제입니다.

병진 전 연속체 다항식은 왼쪽 ux=0·sigma_xy=0이므로 support work0이며 그 대조를 유지합니다.
V2 강체 병진은 strain/stress/body/traction을 바꾸지 않고 work를 관측하게 합니다. 유한 mesh의
FE reaction work까지 정확0이라고 가정하지 않습니다. 실제 수용은 일정 u차·stress/U불변·
support work 변화 c·sum(reaction)를 검사하며 근거 없는 이산 zero 조건을 만들지 않습니다.

양 plane에서 **n8/16/32/64**, 마지막 두 구간16→32/32→64 각각 u L2>=1.8,
full-gradient H1/strain-tensor/full3D stress/tangent-energy norm>=.9,
quadratic-T 보간 L2>=1.8/H1>=.9입니다. 강체/affine fit은 사용하지 않습니다.

- Uniform 장/독립 body·traction·g split/표본 stress/work/U 및 direct edge 합력·모멘트는
  정규화<=1e-10.
- Free residual·물리 힘/모멘트<=1e-9. 상쇄 순하중이나 기대 에너지0으로 정규화하지 않습니다.
- Norm8/10 차이<=측정 비영 오차1%, reference physical U12/16 차이<=특성에너지1e-8.
- Physical-U 오차는 모든 refinement에서 감소·최종 정규화<=.02. 새 raw-energy 차수 gate는 없습니다.
- 정확 snapshot identity·잘못된 입력 거절을 확인하며 skip/xfail하지 않습니다.

Scale은 변위 c0L, strain*=max(c0,|alpha|20), sigma*=E strain*, force*=sigma*L,
moment*=sigma*L², U*=E strain*²L²이며 1m nominal에서4032J/m입니다. 모든 문턱은 사전 값이고
8→16은 진단값이지 gate가 아닙니다.

## 실제 수렴·geometry 근거

각 행은8→16/16→32/32→64이며 마지막 두 구간을 필수로 요구합니다.
| Plane / T | u L2 orders | H1 orders | strain orders | full3D stress orders | energy-norm orders |
|---|---|---|---|---|---|
| stress / quadratic | 1.954155, 1.985643, 1.995543 | 1.005310, 1.002097, 1.000678 | 0.988719, 0.996472, 0.998937 | 0.994224, 0.998273, 0.999498 | 0.991440, 0.997357, 0.999212 |
| strain / quadratic | 1.949089, 1.983482, 1.994629 | 1.004486, 1.001814, 1.000580 | 0.989446, 0.996717, 0.999015 | 0.996137, 0.998885, 0.999687 | 0.992733, 0.997773, 0.999340 |
| stress / linear | 1.954585, 1.985797, 1.995595 | 1.005252, 1.002074, 1.000671 | 0.988656, 0.996457, 0.998933 | 0.994307, 0.998296, 0.999504 | 0.991405, 0.997349, 0.999210 |
| strain / linear | 1.949738, 1.983731, 1.994720 | 1.004404, 1.001781, 1.000571 | 0.989341, 0.996692, 0.999008 | 0.996302, 0.998929, 0.999698 | 0.992665, 0.997756, 0.999336 |

| Plane / T | Reference U (J/m) | normalized U errors n8/16/32/64 |
|---|---:|---|
| stress / quadratic | 3291.810598290596 | 0.007927270097, 0.002010066652, 0.0005043863928, 0.0001262097426 |
| strain / quadratic | 5673.107521367519 | 0.006360377024, 0.001623915604, 0.0004081910488, 0.0001021809346 |
| stress / linear | 3762.290598290595 | 0.01169039278, 0.002961166698, 0.000742922836, 0.000185896445 |
| strain / linear | 5446.867521367519 | 0.01293195082, 0.003276914363, 0.0008221117274, 0.0002056986806 |

에너지 열은 연속체 U로 나눈 값이 아니라 |U_h-U|/U*입니다. 모든 refinement에서 감소했습니다.
Quadratic-T 보간은 roundoff 내 L2 2차/H1 1차, linear-T 오차는 roundoff여서 차수를 주장하지
않습니다. Norm과 reference energy 모두 독립 구적 교차검사를 통과했습니다.

실제 시험은 affine combined 정확 patch, cubic overlap에 대한 반력 변화=-추가 consistent
left load, 비영 support-work 항등식을 포함합니다. 사각 ring hole normal은 안쪽 void로
향하며 균일 shear/thermal과 내향 압력 벡터 -p*n patch가 정확합니다. Scalar pressure라는
새 API는 없습니다. Edge endpoint/cell/tag 순서·node 순열·회전 이동 Cartesian frame·
명시 상사 scale.1/10에서 u/body/stress/normal/load/U를 함께 변환합니다. 상사는 SI로
일관되게 물리 크기를 바꾸며 자동 단위 추론이 아닙니다. 성분별 구속 시험은 평형 pure-Neumann,
두 번째 무구속 성분, 서로 다른 scalar구속3개지만rank2인 경우를 거절합니다.

## Runtime 호환·음성 대조

ThermoelasticResult 기존18개 field 위치를 유지하고 load_body/load_traction(defaultNone)을
뒤에 추가합니다. 실제18-positional 생성에서 기존 의미와 새None을 확인합니다. 정상 출력은
(N,2) 배열, external=body+traction, total=external+g이고 None/{}는 기존18개 수치 필드를
정확 보존합니다. 출력 배열은 가변이고 snapshot은 불변 bytes 복사본이며 반환 후 가변
결과를 재인증하지 않습니다.

Snapshot의 정확 geometry/order/T 결합은 scale/node/cell 순서/schema/unit/변경T·hash/
mutable backing을 거절합니다. 강제 checksum collision actor도 정확 배열 불일치를 거절합니다.
현재 tag는 hash하지 않습니다. 같은 snapshot hash에서 유효한 edge map을 바꾸면 하중이
바뀌지만 잘못된 교체는 거절합니다. Load/tag/T 출처 서명이나 자동 mapping을 약속하지 않습니다.

Callback 전에 전체 selected edge를 검증하여 shape/bool/float/empty/range/zero/interior/
non-edge/선택 중복을 거절하고, 앞에 둔 유효 callback도 호출하지 않은 것을 확인합니다.
Callback exact(Q,2)/실수/유한성·조립 overflow도 검사합니다. Pure deterministic callback과
동시 입력 변이 없음은 caller 조건이며 batch/순서/purity 인증은 아닙니다.

**실제 runtime wrong17대안**을 지정 audit assertion에서 검출했습니다: thermal 부호/g누락,
q*n 추가/차감,3alpha, naivePE, PE-as-PS, zz누락, PE잔여에너지 누락, centroidT²,
supportwork 누락, lineweight, endpoint lumping, fixed-component line 하중 삭제,
hole normal 반전, g를 external로 표시, body/traction field 교환입니다. 잘못된 인자·
thermal/line alias로 실제 solver를 실행하거나 특정 반환 필드를 메모리에서 변조했으며
source 파일은 바꾸지 않습니다. 예상 assertion label로 무관한 import/fixture 실패가
음성 대조 성공으로 취급되지 않게 했습니다.

## 재현과 정확 artifact 경계

```bash
# Repository root; use existing dependencies and an isolated source environment.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export BLIS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PIP_NO_INDEX=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
python -m pip install --no-index --no-deps --no-build-isolation \
  -e packages/galerkin -e packages/galerkin-refsol -e packages/meshine \
  -e packages/gmshio -e packages/physmat -e packages/simcase
python -m pytest -c pyproject.toml -q -s \
  tests/galerkin/test_thermoelastic_traction_independent_validation.py
python -m pytest -c pyproject.toml -q -ra
```
```bash
# Build from the exact clean source inventory; these paths are illustrative.
python -m build --sdist --no-isolation --outdir dist-source packages/galerkin
python -m pip wheel --no-index --no-deps --no-build-isolation \
  dist-source/galerkin-0.1.0.tar.gz -w wheelhouse
# Use a separate installed environment for the following commands.
python -m pip install --no-index --no-deps --force-reinstall \
  wheelhouse/galerkin-0.1.0-py3-none-any.whl
# Copy the independent oracle and pytest file together outside the source tree.
# Remove source PYTHONPATH, and avoid source conftests forcing checkout imports.
python -m pytest -c pyproject.toml --confcutdir="$ACCEPTANCE_TEST_DIR" -q -s \
  "$ACCEPTANCE_TEST_DIR/test_thermoelastic_traction_independent_validation.py"
python -I tests/galerkin/thermoelastic_traction_independent_consumer.py
```

설치 pytest90은 실제 site-packages와 checkout 밖 복사 oracle/test·confcutdir를 사용합니다.
이90은-I 실행이 아닙니다. 첫-I 시도는 user-site 비활성화로 pytest가 없어 collection 전
실패했고 새 의존성을 추가하지 않았습니다. 별도 standalone unittest/NumPy consumer가 실제
-I로 실행되며 각 시험에서 site-packages origin을 단언합니다. 보조 smoke이며90개 고정
gate를 대체하지 않습니다.

Python3.12.14/NumPy2.3.5/SciPy1.17.0, 기존 의존성의 격리 venv/공유 Linux 클라우드 환경,
thread6변수1입니다. Source inventory와 source/sdist/wheel/installed **runtime Python17개**의
정확 파일명 집합·byte가 일치하고 추가 module을 허용하지 않습니다. Thermoelasticity Git blob
**e91cfa089bc09dfc0c646841190f536ae5412333**, SHA256
**3ebe7f891113c09f27b03b9c9ab0be759e73e4fb50dfa5ac01a325f7091303a2**.
Clean sdist SHA256 **d8caef3170de33bcc4bc8dad628c93423ed580ed234ae887c2879602d506d9bc**,
clean wheel SHA256 **3f7b7ac69943514abd7fca2b65c4ec03ef749a89de799da37c7c04cbc29a57de**입니다.
실제 __file__/모듈별 hash를 기록했으며 새 dependency/GPL solver 구현 source를 채택하지 않았습니다.

## 원 실패·회복·최종 결과

재사용 checkout에 이전 workflow 파일11개와 추가 runtime module1개가 남아 있었습니다.
Tracked blob 일치만 검사해 untracked 잔여를 놓쳤습니다. 초기90/isolated4/관련208은 올바른
traction core를 썼지만 오염 artifact의 **잠정 관측**이지 최종 exact 후보 수용이 아닙니다.
첫 whole는 추가 old module 때문에 dependency guard 실패를 표시했고 본인 managed session에서
중단(exit130)하여 완료된 전체 count가 없습니다. 앞선 direct-PID 중단 시도는 ProcessLookupError로
실패했으므로 성공 신호를 가정하지 않습니다. 본인 검증 환경 오류이며 생산 결함이 아닙니다.

11개 파일·초기 sdist/wheel/origin/log를 별도 archive로 보존했습니다. 잔여를 제거하고 own
checkout의 build/egg-info cache를 정리했습니다. 정확 Python inventory는 후보+본인 전용3개
시험파일이며 unapprovedPython0/runtime17입니다. Source/sdist/wheel/installed 집합·byte를
다시 검사하고 clean artifact를 재build/재설치했습니다. 회복 실행은 필요한 정정이며 설명 없는
중복 실행이 아닙니다.

- Clean 설치 독립 **90pass/0fail/0skip**, wrong-runtime17개와 양plane 네 fixed-mesh 사례 포함.
- Clean 설치 **python-I consumer4tests OK**: 양plane combined patch, legacy18/snapshot 수명,
  consistent linear edge 하중.
- Clean source 독립 **90cases 통과**, 관련 component/기존독립/producer/reference
  회귀 **208cases 통과**를 whole JUnit에서 직접 계수했습니다. 완료 clean root whole는
  **1385pass / 7fail / 16skip / 하위검사9pass / warning1개**(Starlette deprecation),
  공유시간335.66s입니다. 7실패는 모두 기존 thermal CLI-I subprocess가 user-site 비활성화로
  Shapely를 찾지 못해 실행 전에 난 오류입니다. 기존 필수 Shapely2.2.0(BSD-3-Clause)의
  동일 설치 파일만 본인 source venv에 복사·byte hash를 기록했고 download/프로젝트 의존성/
  버전 변경은 없습니다. 해당7실패만 재실행해 **7pass/132deselected**를 확인했습니다.
  원 전체 결과는 실패로 유지하고 두 번째 clean whole 실행이나 새 전체 합계는 만들지 않습니다.
  Skip은Gmsh14개/로컬 refractiveindex.info database2개입니다. 수치수용·환경 target회복·
  오너/release 최종결합 전체수용은 별도이며 이 gate에서 생산 수치결함은 발견하지 않았습니다.

원-I pytest import 실패와 오염 whole 중단은 보존하고 성공으로 바꾸지 않습니다. 최초 pip는
기본 build cache를 사용했으나 이후 cache를 비활성화했고 공용 cache를 열람·삭제하지 않았습니다.
Hydrated checkout에서 무관한 binary PNG7개는 빠져 있어 figure-asset 배포 완결성을 주장하지
않습니다. 새 report/consumer 자산 포함·모든 package release metadata·최종 release 결합은
별도 검토입니다. Develop 통합/배포를 주장하지 않으며 공유 시간은 성능 baseline이 아닌 metadata,
Actions는 조회·실행하지 않았고 Windows는 중단/미검증입니다. Linux로 Windows를 대신하지 않습니다.
