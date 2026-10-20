# 진공 직육면체 PEC 공동 솔버

[영문 원문](../../../../../packages/galerkin/cavity_solver.md)

```python
from galerkin import solve_cavity_box

result = solve_cavity_box(
    lengths_m=(1.0, 1.0, 1.0),
    subdivisions=(8, 8, 8),
    num_modes=6,
    target_frequency_hz=210e6,
)
print(result.frequencies_hz)
```

이 API는 `(0, 0, 0)`에서 시작하는 진공 직육면체의 여섯 벽 모두에 완전 전기 도체
조건을 적용합니다. Cartesian cell당 사면체 6개의 적합 교대 Kuhn mesh와 기존
최저차 Nedelec 에지 요소를 사용합니다. 재료·손실·개방 경계·임의 CAD·sweep 옵션은 없습니다.

아래 고정 정육면체/직육면체 수렴 gate는 교대 mesh에서 통과합니다. 대수 잔차와
연속체 이산화 오차는 별도로 검사하며 작은 잔차만으로 mesh 정확성을 인증하지 않습니다.

## 인수와 검색

`solve_cavity_box(lengths_m, subdivisions, *, num_modes=6, target_frequency_hz)`는
`CavityResult`를 반환합니다.

- `lengths_m`: m 단위의 유한한 양의 실수 길이 세 개(Python 또는 NumPy 수치 scalar)
- `subdivisions`: 양의 정수 세 개
- `num_modes`: 개별 고유벡터 수를 세는 양의 정수. 중복 고유값도 유지합니다. bool은 수치 입력으로 받지 않습니다.
- `target_frequency_hz`: 필수인 유한한 양의 Hz 주파수

검색은 `near_target`입니다. 유한한 계산 물리 후보에서 목표에 **제곱** 파수
(동등하게 제곱 주파수)가 가장 가까운 요청 개수를 고르고, 주파수 오름차순으로
반환합니다. 완전한 최저 spectrum, 구간의 모든 모드 또는 축퇴 cluster의 모든
partner를 보장하지 않습니다. 특히 최소 반환 주파수가 기본 주파수일 필요는 없습니다.

성공할 때 요청 개수는 정확하며 cluster 중간에서 잘릴 수 있습니다. 특정 검증 예에서
완전한 기준 cluster를 포함해도 모든 결과에는 `cluster_completeness="not_certified"`,
`mode_count_policy="exact_count_may_split_cluster"`가 들어갑니다. 이는 검색의
한계를 나타내며 그 결과에서 실제 partner가 빠졌는지 진단하는 문자열은 아닙니다.

## 배열·방향·단위

요청 모드 수 K, 전체 에지 수 E, 사면체 수 T로 둡니다. 모든 모드는 실수 정재파입니다.

| 속성 | shape / 의미 | 단위 |
|---|---|---|
| `mesh` | `Mesh3D`, 절점과 사면체 connectivity | 절점 m |
| `space` | 같은 mesh의 `EdgeSpace3D` | 방향 있는 topology |
| `frequencies_hz` | `(K,)`, 양수·오름차순 | Hz |
| `eigenvalues_m2` | `(K,)`, 제곱 파수 | m^-2 |
| `edge_coefficients` | `(E,K)`, 정확한 PEC 0을 포함한 전체 벡터 | m^-1/2 |
| `electric_field` | `(K,T,3)`, 사면체 centroid의 벡터 | m^-3/2 |
| `relative_residuals` | `(K,)`, 자유 에지 방정식 | 무차원 |
| `pec_edge_ids` | 전체 에지 순서의 index | index |
| `requested_modes` | K | 개수 |
| `target_frequency_hz` | 입력 목표 | Hz |
| `search` | `"near_target"` | metadata |

위 cluster 정책 속성 두 개도 `CavityResult`에 있습니다. 정확한 진공 광속은
`c0 = 299792458 m/s`이고 `f = c0 * sqrt(eigenvalues_m2) / (2*pi)`입니다.

전역 에지는 낮은 node ID에서 높은 ID로 향합니다. `space.edges`, `space.tet_edges`,
`space.signs`가 순서와 local-to-global 방향을 설명합니다. 경계 에지는 경계 면에
포함된 에지입니다. 양 끝 절점이 경계에 있어도 내부 에지는 자유 상태로 남습니다.

전체 계수 Q와 반환 SI mesh의 진공 에지 질량행렬 M_SI에 대해, 아래 허용치 안에서
`Q.T @ M_SI @ Q = I`입니다. 계수는 임의 수학 정규화 아래의 선적분입니다.
단위는 **V가 아니며**, 복원 장도 **보정된 V/m 또는 전력**이 아닙니다.
각 모드의 최대 절댓값 에지 계수를 양수로 합니다. 축퇴 부분공간은 해석 간 기저가
회전할 수 있으므로 개별 편광 label·벡터 부호·고유벡터는 유일한 물리 식별자가 아닙니다.

내부 좌표는 `L=max(lengths_m)`로 나눕니다. 반환 계수는 `q_normalized/sqrt(L)`,
고유값은 `k2_normalized/L**2`, centroid 장은 `E_normalized/L**1.5`입니다.
물리 크기를 균일하게 s배 하면 주파수는 s로 나눠집니다. 각 centroid 장은
`eval_edge_field_3d(result.space, result.edge_coefficients[:, j])`로 복원합니다.

직렬화는 호출자 책임입니다. 기술적 장 계약을 보존하려면 SI 좌표, 사면체, 에지
순서/방향, PEC index, 선언한 정규화 및 검색 metadata와 전체 raw 계수를 저장합니다.
3D layout 식별자는 `cavity3d-edge-v1`이며 NPZ reader는 `allow_pickle=False`로
동작해야 합니다. 장 저장을 끄면 raw 에지·centroid 배열은 생략하되 spectrum과
정규화/검색 metadata는 유지합니다.

## 수치 방법과 실패 정책

mesh는 `box_mesh` 절점과 cell당 6사면체 Kuhn pattern에서 시작합니다. cell `(i,j,k)`에서
해당 cell index가 홀수인 local 좌표를 반사합니다. 절점·Cartesian cell 수·사면체 수·모양을
바꾸지 않고 body diagonal이 교대합니다. 공유 면은 같은 접선 parity를 써서 diagonal도
같습니다. 짝수 subdivision은 해당 box 중간면의 반사 대칭을 복원합니다. 홀수도 적합하지만
그 전역 대칭은 없을 수 있습니다. 고유값·기준 정답·목표·요청 개수는 mesh에 영향을 주지 않습니다.

이 mesh 계열은 box 전체에 단일 선호 body diagonal을 두지 않습니다. 계산 고유값을
보정하는 대신 이산화 오차를 바꿉니다. 공개 `box_mesh` 생성기 자체는 그대로입니다.
공동이 원래 connectivity를 쓴다고 가정하지 말고 반환 mesh/topology를 사용해야 합니다.
직육면체 111 doublet은 여전히 갈라질 수 있습니다. box 반사 대칭이 우연한 편광
축퇴를 강제하지는 않습니다.

자유 에지 일반화 문제는 `S q = k2 M q`입니다. 이 단순연결 PEC box의 gradient
nullspace 차원은 `(nx-1)*(ny-1)*(nz-1)`입니다. 경계 0인 내부 절점 potential을
자유 에지 circulation으로 보내는 C에 대해 `H=C.T @ M @ C`,
`P=I-C H^-1 C.T M`이며 H는 양의 정부호입니다.

자유 에지가 256개 이하면 전체 dense 일반화 spectrum을 구하고 kernel 차원을 검사합니다.
그보다 크면 대칭 projected shift-invert
`OPinv=P (S-sigma*M)^-1 P.T`, `sigma=(2*pi*f_target*L/c0)**2`를 사용합니다.
`OPinv M`은 gradient를 제거하고 물리적 변환 고유값 `1/(k2-sigma)`를 보존합니다.
penalty로 Maxwell 고유문제를 바꾸지 않습니다. H와 shifted 행렬은 직접 sparse 분해합니다.

N개 모드 요청에서 sparse 후보 예산은
`min(max(2*N, N+8), physical_dofs, free_edges-1)`,
`physical_dofs=free_edges-interior_nodes`입니다. ARPACK은
`ncv=min(free_edges,max(6*candidates,90))`, 허용치 `1e-10`, 최대 50000회,
seed `0`의 random 초기 벡터를 사용합니다. 단일 유한 검색을 수행하고 반복 고유값을
중복 제거하지 않습니다.

kernel 판정 scale은 정규화 좌표에서 해석 box 기본 k²의 `1e-8`배입니다.
목표와 독립적이며 반환 고유값을 공급하지 않습니다. 선택 벡터는 다음을 만족해야 합니다.

- 자유 에지 상대 잔차 `||S q-lambda M q|| / (||S q||+abs(lambda)*||M q||) <= 1e-8`
- `Q.T M Q-I`의 최대 성분별 오차 `<= 1e-7`
- gradient projection의 M-norm `<= 1e-9`

잔차는 벽 반력이 있을 수 있는 구속 경계 행을 제외합니다. 연속체 정답 오차가 아닌
이산 방정식을 측정합니다.

잘못된 인수나 표현 불가능한 내부 scale은 `ValueError`입니다. 물리 자유도/후보 부족,
유의한 음의 고유값, nonfinite 출력, 분해 실패, 비수렴, 품질 검사 실패는 부분 결과 없이
`RuntimeError`입니다. 목표가 이산 고유값이면 shifted 분해가 특이할 수 있으므로
근처 다른 목표를 택합니다. 조용한 개수 축소·0 padding·허용치 완화는 없습니다.

## 재현 가능한 검증과 수렴 수정

로컬 시험 의존성을 설치한 저장소 루트에서 실행합니다.

```bash
python -m pytest -q tests/galerkin/test_cavity_solver.py
python -m pytest -q
```

시험은 refsol TE/TM 열거를 독립 transverse-amplitude 개수,
완전 dense 이산 spectrum, 낮은 목표 sparse 검색의 343차원 gradient kernel,
전체 PEC 0, SI 재조립/복원, 물리 상사·축퇴 부분공간, 수치 오류주입과 비교합니다.

고정 수열은 모든 방향 `n=4,8,16`, 목표 제곱 파수는 `1.3 * analytic_fundamental`이고
완전 cluster끼리 비교합니다. 교대 mesh의 n=16 결과입니다.

| Box (m) | cluster 중복도 | 마지막 평균 k² 오차 차수 | 최대 개별 f 오차 |
|---|---|---|---|
| `(1,1,1)` | `3,2,6` | `2.0880, 1.9627, 2.0639` | `0.1657%` |
| `(1,.8,.6)` | `1,1,1,2` | `1.9393, 2.0296, 1.9988, 1.8929` | `0.1881%` |

모든 평균 오차는 단계마다 감소하고 마지막 차수는 기존 **1.8** gate를 넘습니다.
직육면체 111 cluster 폭은 `2.0103`차로 감소하며 정육면체의 세 폭은 roundoff입니다
(상대 폭 최대 `2.1e-14`). 직육면체 111 부호 있는 평균 상대 오차는
`+0.0066232970`, `+0.0025322041`, `+0.0006818301`입니다.

원래 평행 diagonal Kuhn mesh는 같은 gate에 실패했습니다. 직육면체 111 부호 있는
평균 오차 `-0.0038258485`, `+0.0007879605`, `+0.0003363018`로 마지막 차수는
**1.2284**였습니다. 음/양 개별 오차는 `2.2708`, `1.9130`차로 수렴했지만 평균의
상쇄가 이 고정 수열에서 기대 차수를 가렸습니다. 수정은 실제 mesh 계열을 바꾸며,
숨은 refinement·spectrum 보정·허용치 변경·skip·xfail은 없습니다. 원 고정 수렴
시험 본문을 그대로 유지합니다.

별도 진단으로 선택·고유솔버 오차와 mesh 오차를 구분합니다. n=4에서 두 mesh 계열은
완전 dense 일반화 spectrum과 상대 `4.7e-14` 이내로 일치하고 gradient 모드는
정확히 27개입니다. 요청 개수를 5에서 11로 늘려도 첫 다섯 값은 `6.7e-16` 이내로
유지되며 111 질량 정규화 고유공간도 roundoff까지 보존됩니다.

독립 체적 구적으로 111 장 부분공간과 정확한 정재파를 비교합니다. 진폭 벡터는
`(pi/a,pi/b,pi/c)`에 수직이고 `sqrt(8/(a*b*c))`로 정규화합니다. 유일한 TE/TM
벡터를 지정하지 않고 연속 L2 overlap의 두 singular value를 사용합니다. n=8에서:

| Mesh | 두 overlap singular value | 상대 부분공간 projection 오차 |
|---|---|---|
| 평행 diagonal | `0.98605, 0.97110` | `0.20576` |
| 교대 diagonal | `0.98928, 0.98206` | `0.16866` |

n=4의 교대 값은 `0.95618, 0.92750`(평행: `0.93536, 0.86931`)로 거친 mesh에서도
두 편광을 확인합니다. 사면체 Duffy map의 5점 tensor Gauss 구적은 6점과 절대
`1e-9`로 비교합니다. projection 오차는 `sqrt(1 - mean(singular_values**2))`입니다.
이 검사, raw Maxwell 잔차, mesh 적합성/반사 시험과 고정 spectrum gate는 서로
보완하며 어느 하나로 다른 것을 대체하지 않습니다.
