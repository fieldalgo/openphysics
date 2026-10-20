# 진공 PEC 직육면체 공진기 독립 검증 계획

[영문 원문](../../../../../packages/galerkin/cavity3d_validation.md)

아래 실행 수치·실패·미검증 서술은 영문 원문의 해당 후보 시점 기록이며 새 수용 결과를 뜻하지 않습니다.

범위는 여섯 벽 모두 PEC인 진공 직육면체, 한 번의 모드 해석, 최저차 사면체 Nedelec 요소입니다. 유전체 장하, 손실, 개방 경계, 임의 CAD, renderer 검증은 다루지 않습니다.

이 문서는 검증 계획이자 재현 가능한 **기존 저수준 기준선**입니다. 새 공개 솔버, 문서 schema, persistence API를 정의하지 않습니다. 제품 수용 시험은 별도로 승인된 인터페이스를 사용하고 채점한 정확한 구현 commit을 기록해야 합니다.

가장 최근에 독립 검증한 후보는 **변경하지 않은 시험 27/27 통과**이며 반환 mesh 독립 시험 3개를 추가로 통과했습니다. 고정 n=4,8,16 / >1.8 gate는 그대로입니다. [교대 mesh 보고서](cavity3d_alternating_validation.md)와 그 정확한 source manifest를 참고하세요. 아래 이전 후보의 결과는 과거 기록입니다.

## 해석 oracle과 중복도

변 길이 a, b, d(m)에 대해 다음과 같습니다.

    k² = π²[(m/a)² + (n/b)² + (p/d)²]
    f_Hz = 299792458 sqrt(k²) / (2π).

`refsol.metallic.rect_cavity_resonances`는 Hz가 아니라 k²를 반환합니다. TE index 규칙은 p >= 1, (m,n) != (0,0)이고 TM은 m,n >= 1, p >= 0입니다. 이와 독립적으로 정재파 진폭을 보면 양의 index가 정확히 두 개일 때 편광 하나, 세 개 모두 양수일 때 편광 두 개가 있습니다. 양의 index가 0개 또는 1개이면 물리 모드가 없습니다. 기준 구현·솔버와 독립된 두 번째 열거로 유용합니다.

단위 정육면체에는 k²/π² = 2, 3, 5의 완전한 낮은 cluster가 있고 중복도는 3, 2, 6입니다. 직육면체 (1, 0.8, 0.6) 사례는 처음 세 단순 모드와 TE111/TM111 쌍을 시험합니다. 유한한 index 상한은 생략된 가장 작은 index의 k²가 비교 대역보다 클 때만 충분합니다. index 상한 N에 대해 π²(N+1)² / max(a,b,d)²가 보수적인 하한입니다.

가장 가까운 기준까지의 거리만이 아니라 정렬한 spectrum을 **중복도와 함께** 비교합니다. cluster 개수와 누적 개수가 필요합니다. 갈라진 수치 cluster는 서로 다른 해석 cluster 사이의 중간점으로 배정할 수 있지만 정확도·수렴 gate도 만족해야 합니다. 주파수 목표 shift-invert 검색은 최저 N개 모드가 반환되었음을 증명하지 않습니다. 해석 cluster 안에서 끝나는 요청에는 명시적인 부분 cluster 정책이 필요합니다. 이 검증 사례들은 완전한 cluster를 요청합니다.

축퇴 고유공간은 임의의 기저 회전과 부호·위상을 허용합니다. 개별 고유벡터나 TE/TM label은 안정적인 비교 대상이 아닙니다. 변 길이가 다른 box의 우연한 doublet을 정육면체의 모든 축퇴가 우연하다는 주장으로 일반화하지 않습니다.

## 새 수용 시험 실행 전에 고정한 gate

| 양 | Gate |
|---|---|
| 해석 진폭 열거 vs refsol | 같은 개수, 정렬한 k² 상대 오차 <= 1e-13 |
| k²→Hz 변환 | 위 SI 공식 대비 상대 오차 <= 1e-12 |
| 구조 refinement | 축당 n = 4, 8, 16, box 불변 |
| cluster 평균 k² 오차 | 단계마다 감소; 마지막 관측 차수 > 1.8 |
| 상대 cluster 폭 | 마지막 관측 차수 > 1.8, 또는 최세밀 폭 < 1e-10 |
| 개별 주파수 정확도 | n = 16에서 비교한 모든 모드가 1% 이내 |
| 자유 DOF 고유쌍 잔차 | 모든 모드 rho <= 1e-9 |
| 질량 직교성 | 질량 정규화 후 max abs(U* M U - I) <= 1e-8 |
| gradient 결합 | 정규화한 각 내부 절점 gradient overlap <= 1e-9 |
| 작은 mesh nullspace | n = 2, 3, 4에서 영 모드 정확히 (n-1)^3개 |
| gradient의 이산 curl | 상대 행렬 max norm <= 1e-11 |
| 경계 raw 에지 계수 | 상대 max <= 1e-12 |
| 독립 벽 접선 trace | 상대 max <= 1e-10 |
| 등가 m/um/nm 입력 | 주파수와 무차원 k² 상대 차이 <= 1e-9 |
| 실제 기하 scaling s = 1e-6, 1, 1e3 | f*s가 1e-9 이내로 불변 |
| 등가 모델 사이의 축퇴 부분공간 | 정규화 질량 overlap singular value >= 1 - 1e-7 |
| 저장한 primitive 배열/raw 계수 | dtype, shape, 값을 정확히 보존 |
| 재구성한 centroid 장 | 상대 차이 <= 1e-12; 잔차와 PEC gate를 다시 통과 |

실패한 gate는 시험한 구현에 대해 실패로 남습니다. 실패를 통과로 만들기 위해 허용치를 넓히거나, 중복도를 줄이거나, 어려운 cluster를 빼거나, 처방한 입력 subdivision 수·refinement 순서·기하를 바꾸지 않습니다.

문서화된 솔버·mesher 구현 수정은 별도 변경입니다. 구현 SHA와 근거를 기록하고 이전 실패를 보존한 뒤, 같은 사전 선언 사례와 gate를 다시 실행합니다. core `3b850a8d7e303fd45a6b77f85571d45ab7c51114`에서 `a660233cc224ccf9b7f8c121b4dc0ded9271bb55`로의 mesh 계열 변경이 이 절차를 따랐습니다. 공진기 mesher는 교대 Kuhn diagonal로 바뀌었고 box 기하, 입력 n=4,8,16 수열, cell/node 수, cell당 사면체 6개, 최종 평균 차수 기준 >1.8은 유지했습니다. 이전 1.22837 실패는 과거 기록으로 남습니다. 수정 구현에서 독립 측정한 1.89291 통과는 변경하지 않은 gate 아래의 새 결과입니다. 정확한 source의 [재검증 보고서](cavity3d_alternating_validation.md)를 참고하세요.

K_ff u = lambda M_ff u에 대해 다음을 사용합니다.

    rho = ||K_ff u - lambda M_ff u||₂ /
          (||K_ff u||₂ + |lambda| ||M_ff u||₂).

PEC로 제거한 행에는 반력 잔차가 있을 수 있으므로 이 고유쌍 잔차 시험에 포함하지 않습니다. 방향 있는 node-to-edge incidence C는 낮은 node에서 높은 node로 가는 에지 쌍으로 독립 구성합니다. 열은 내부 절점, 행은 자유 에지로 제한합니다. 각 열 c_j에 대해 abs(c_j* M u) / sqrt((c_j* M c_j)(u* M u)) <= 1e-9를 확인합니다. 분모가 0이면 통과가 아니라 오류입니다.

작은 시스템에서는 구속된 전체 일반화 pencil을 독립적으로 대각화합니다. 무차원 고유값 scale로 gradient kernel 개수를 세고 정수 nullity와 K C 항등식을 확인합니다. 양의 값만으로는 완전성이나 가짜 비영 모드의 부재를 입증하지 못합니다.

## PEC와 raw 장 재구성

한 사면체에 속한 면과 그 에지 쌍을 독립적으로 열거합니다. 3D에서는 양 끝 절점이 경계 절점이라는 사실만으로 경계 에지를 식별할 수 없습니다. 끝점이 경계에 있는 diagonal도 내부 에지일 수 있습니다.

사면체와 local barycentric 좌표 lambda_i에 대해 다음과 같이 재구성합니다.

    E = sum_edges u_edge sign_edge
        (lambda_i grad(lambda_j) - lambda_j grad(lambda_i)).

각 경계 삼각형의 꼭짓점과 centroid에서 인접 사면체로 평가하며 독립 계산한 barycentric gradient와 법선을 사용합니다. max ||n cross E||는 모든 사면체 꼭짓점에서의 최대 크기로 scale합니다. 이는 체적 centroid 표본에서 추론하는 대신 최저차 요소의 다항식 trace를 검사하는 것입니다. raw 경계 DOF는 전체 에지 계수의 최대 절댓값으로 나눕니다. 모두 0인 모드는 무효입니다.

복원은 절점, 사면체, 전역 에지 방향/순서, local 방향, 전체 에지 계수, 고유값, 단위 metadata를 보존하거나 결정적으로 재구성해야 합니다. 배열은 allow_pickle=False로 load합니다. 복원 후 행렬을 재조립하고 잔차, PEC, 재평가한 장을 검사합니다. 저장한 그림이나 centroid 배열은 raw 계수를 대체할 수 없습니다.

실제 기하 scaling에서는 같은 에지 적분 규약일 때 K가 1/s, M이 s, k²가 1/s²로 scale됩니다. 대응한 두 기저의 overlap singular value를 비교하기 전에 공통 질량 계량에서 정규화합니다. 한 번 저장/복원한 기저에는 정확한 배열 일치가 필요하지만, 축퇴 부분공간 안에서 따로 호출한 고유솔버 결과끼리는 필요하지 않습니다.

## 기존 기준선 재현

저장소 루트에서 실행합니다. 이 명령은 기존 패키지와 NumPy/SciPy만 사용하며 추가 의존성이나 솔버 코드를 도입하지 않습니다. source 기준선은 commit `75df651457b8f78540e9050b27c276ab8b07aaf1`입니다.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python - <<'PY'
import itertools
import sys
from pathlib import Path
import numpy as np

root = Path.cwd()
for package in (root / "packages").iterdir():
    if (package / "pyproject.toml").exists():
        sys.path.insert(0, str(package))
sys.path.insert(0, str(root / "packages/galerkin/examples"))
import cavity_modes as example
from refsol.metallic import rect_cavity_resonances

example.check_mesh()
example.check_whitney_identities()
example.check_kernel_dimension(sizes=((2, 2, 2), (3, 3, 3), (4, 4, 4)))
for sides in ((1, 1, 1), (1, .8, .6)):
    independent = []
    for indices in itertools.product(range(5), repeat=3):
        positive = sum(i > 0 for i in indices)
        multiplicity = {0: 0, 1: 0, 2: 1, 3: 2}[positive]
        k2 = sum((np.pi * i / a)**2 for i, a in zip(indices, sides))
        independent.extend([k2] * multiplicity)
    expected = [k2 for k2, _ in rect_cavity_resonances(*sides, n_max=4)]
    assert len(independent) == len(expected) == 176
    assert np.allclose(sorted(independent), sorted(expected), rtol=1e-13, atol=0)
    if sides == (1, 1, 1):
        q = np.asarray(independent) / np.pi**2
        for value, count in ((2, 3), (3, 2), (5, 6)):
            assert np.count_nonzero(np.isclose(q, value, rtol=1e-13, atol=0)) == count
print("Existing mesh/identity/kernel checks and independent oracle: PASS")
PY
```

수렴 기준선은 기존 예제의 A_BOX/B_BOX/C_BOX를 메모리에서 위의 각 box로 설정하고, 각 n in (4,8,16)에 대해 `solve_cavity(n,n,n,num_modes=20,sigma=1.3*analytic_lowest_k2)`를 호출합니다. 반환된 정렬 고유값을 위 해석 중복도대로 묶고(정육면체는 처음 11개 모드, 직육면체는 처음 5개 모드) 평균만 비교하지 않고 표의 모든 gate를 계산합니다. `assemble_curlcurl_3d`와 `assemble_edge_mass_3d`로 전체 K/M을 재조립하고 반환된 자유 에지로 제한해 각 모드의 잔차를 계산합니다. 이는 기존 예제의 탐색 검사이며 새 최저 N개 공개 API의 수용이 아닙니다.

## 현재 근거와 한계

(1,0.8,0.6)에서 기존 mesh 검사가 통과했습니다. 체적 0.48, 예상 경계 면 132개, Euler 특성 1, 양의 체적, refinement에 불변인 dihedral angle입니다. 상대 Whitney 항등식 오차는 최대 6.8e-16이었습니다. kernel 개수는 정확히 1, 8, 27이었습니다. 두 독립 해석 열거는 index 상한 4에서 176개 모드 모두 일치했고 정육면체 개수는 3/2/6이었습니다.

이 초기 직접 검사는 API 검증과 pytest 설치보다 먼저 수행했습니다. 아래 후속 대상 결과가 현재 근거와 실패를 설명합니다. 전체 suite 통과는 주장하지 않습니다.

## 승인된 기술 계약과 실행 가능한 시험

호출 형식은 `galerkin.solve_cavity_box(lengths_m, subdivisions, *, num_modes=6, target_frequency_hz)`입니다. 길이와 mesh 좌표는 SI m, 주파수는 Hz입니다. 선택은 제곱 주파수 기준 `near_target`이며 성공하면 요청한 개수를 정확히 반환합니다. 축퇴 cluster를 가를 수 있습니다. 결과와 저장 metadata는 `cluster_completeness="not_certified"`, `mode_count_policy="exact_count_may_split_cluster"`를 선언합니다. 저장 데이터는 `field_layout="cavity3d-edge-v1"`을 선언하고 pickle 없이 load되어야 합니다. `save_fields=false`이면 raw 에지/centroid 배열은 생략하고 spectrum과 검색/정규화 metadata는 유지합니다.

공개 솔버의 거절 한계는 잔차 1e-8, 질량 직교성 1e-7입니다. 표의 더 엄격한 독립 benchmark 한계 1e-9와 1e-8은 그대로입니다. 정규화 계수는 Q* M_SI Q = I를 만족합니다. 에지 계수는 임의 정규화 단위 m^-1/2, centroid 장은 m^-3/2이며 보정된 V/m가 아닙니다.

새 독립 시험은 승인된 API와 simcase 구현을 포함한 source checkout에서 실행합니다. 패키지 시험 파일을 선택할 때는 루트 설정을 명시적으로 지정해, 패키지 local pytest discovery가 루트 conftest의 경로 설정을 우회하지 않게 합니다.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest -c pyproject.toml -q \
  packages/galerkin/tests/test_cavity3d_validation.py \
  packages/simcase/tests/test_cavity3d_persistence_validation.py
```

수렴 fixture는 원래 고정 shift sigma = 해석 기본 k²의 1.3배를 target_frequency_hz로 표현해 사용합니다. gradient kernel에서 떨어져 있으면서 시험 대상인 완전한 기준 cluster를 유지합니다. 수치 gate를 바꾸거나 다른 목표에서의 완전성을 보장하지 않습니다. raw 복원 시험은 저장한 primitive 배열에서 Mesh3D/EdgeSpace3D를 재구성하며 제품 load API를 요구하거나 만들어 내지 않습니다.

## 측정한 후보 결과(2026-10-15)

source base는 `75df651457b8f78540e9050b27c276ab8b07aaf1`입니다. 임시 시험 snapshot은 core commit `163239a5ae03c05a1b8f49c78c2a1277c42ca3e6`, simcase commit `1837b46b4f533ca97279e29004ecba39b48b8044`, reference commit `ce74a783e0cf679e9e031360b6bd9d556346a575`의 정확한 변경 blob을 사용했습니다. 단일 통합 Git commit이나 빌드한 wheel의 검증이 아니라 component-source 조합입니다. Python 3.12, NumPy 2.3.5, SciPy 1.17.0, pytest 9.1.1을 사용했으며 수치 라이브러리 버전은 CI lock과 다릅니다. runtime 의존성 선언은 바뀌지 않았습니다.

| 독립 검사 | 관측 결과 |
|---|---|
| 진폭/refsol oracle과 dense 일반화 nullity | 통과 |
| raw 고유쌍 잔차, 질량 직교성, gradient overlap, 독립 벽 trace | 작은 정육면체와 변 길이가 다른 box fixture에서 통과 |
| 실제 기하 scaling과 축퇴 부분공간 | 통과 |
| m/um/nm 문서 표현과 평행이동한 SI 좌표 | 통과 |
| 저장한 raw 배열 dtype/shape/값과 복원 후 잔차/PEC/장 | 통과 |
| core 필수 cluster metadata | 실패: cluster_completeness 속성 없음 |
| 저장 계약 metadata | 실패: cluster_completeness 값이 계약과 다름; source 검사에서 필수 layout/count-policy key도 없음 |
| 정육면체 n=4,8,16 완전 cluster 수렴 | 통과; 평균 차수 1.9184, 1.9568, 1.9836 |
| 직육면체 n=4,8,16 완전 cluster 수렴 | 실패: 111 cluster 평균 차수 1.22837, 1.8 미만 |

실패한 직육면체 cluster의 평균 k² 상대 오차는 0.0038258485, 0.0007879605, 0.0003363018이었습니다. 폭은 2.05384차로 수렴했고 최세밀 개별 주파수 정확도도 좋았지만, 어느 쪽도 실패한 평균 차수 gate를 뒤집지 않습니다. 정육면체의 최세밀 최대 주파수 오차는 0.32417%, 직육면체는 0.18691%였습니다. 허용치나 refinement 단계를 완화하지 않았습니다.

유한 cutoff 기준 handoff의 전용 시험 17개를 code review 후 이 source에서 다시 실행했습니다. 이는 위 독립 진폭/개수 검사를 대체하지 않습니다. 전체 source 회귀, CLI 수용, build/wheel 시험, 원격 CI는 이 검증 작업에서 실행하지 않았습니다. 알려진 실패는 제품 수용을 주장하기 전에 검토가 필요합니다.

## 실제 구현 후보 재실행(2026-10-15)

위 최초 handoff 결과는 과거 기록으로 남습니다. 새 정확한 파일 snapshot은 같은 base에 대해 core `3b850a8d7e303fd45a6b77f85571d45ab7c51114`, simcase `cd4071a5685fcdf6d21d19c5d382461685c2e501`, validation `db9367e90518bd92f5f72fbd87fd65b58fcd069c`, reference `ce74a783e0cf679e9e031360b6bd9d556346a575`를 사용했습니다. 변경하지 않은 독립 시험과 기준 시험 17개는 **26 통과, 1 실패**였고 skip은 없었습니다. 실패 하나는 여전히 직육면체 111 평균 차수 gate입니다. 이전 metadata 실패 세 개는 이 실제 source에서 해결되었습니다.

요약 검증 뒤의 NPZ metadata assertion이 이제 실행되어 통과합니다. cluster completeness, exact-count 정책, layout 식별자, 좌표/주파수 단위와 정규화가 JSON과 pickle 없이 load한 NPZ 사이에서 일치합니다. raw 배열 복원과 save_fields=false 검사도 통과합니다.

부호 있는 평균과 연속체 부분공간 진단은 [cavity3d_convergence_diagnosis.py](../../../../../../studies/cavity3d_convergence_diagnosis.py)로 재현하고 [진단 문서](cavity3d_convergence_diagnosis.md)에서 설명합니다. 진단은 실패를 그대로 두고 유한 mesh의 부호 상쇄를 식별하며, 자동으로 대체하는 수용 규칙을 도입하지 않습니다. CI와의 도구/환경 차이는 그대로입니다.
