# 교대 Kuhn 공진기 mesh의 독립 검증

[영문 원문](../../../../../packages/galerkin/cavity3d_alternating_validation.md)

아래 실행 수치·실패·미검증 서술은 영문 원문의 해당 후보 시점 기록이며 새 수용 결과를 뜻하지 않습니다.

새 공진기 구현은 **변경하지 않은 독립/기준 시험 27개**를 실패·skip 없이 통과합니다. 원래 n=4,8,16 평균 오차 차수 기준 >1.8은 그대로입니다. 직육면체 111 doublet에서 독립 측정한 최종 평균 오차 차수는 **1.89290945**입니다. 시험, 허용치, cluster 개수, refinement 수열을 완화하지 않았습니다.

## 정확한 source와 환경

| 구성 요소 | Commit |
| --- | --- |
| Base | `75df651457b8f78540e9050b27c276ab8b07aaf1` |
| Core | `a660233cc224ccf9b7f8c121b4dc0ded9271bb55` |
| simcase | `1747aaffc6d1b9b0adec53c1b2166864a472ec6b` |
| 독립 검증(기준 helper 포함) | `076a25df74e6581b933577bc0ceebb9d0992cf82` |

[manifest](../../../../../packages/galerkin/cavity3d_alternating_manifest.json)는 서로 겹치지 않는 변경 source 경로 25개 각각의 경로와 blob SHA, 그리고 추가 mesh 감사 시험의 blob SHA를 기록합니다. 각 base blob과 변경 blob을 확인했습니다. 단일 통합 commit이 아니라 정확한 component source 조합입니다. 이전 core/simcase handoff source는 사용하지 않습니다. 해석 helper는 이미 검증 component에 포함되어 있습니다.

환경은 Python 3.12.14, NumPy 2.3.5, SciPy 1.17.0, pytest 9.1.1이며 BLAS/OpenMP thread는 1입니다. 수치 라이브러리는 CI의 NumPy 2.5.4/SciPy 1.18.1과 다릅니다.

## 변경하지 않은 수용 시험과 독립 mesh 검사

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest -c pyproject.toml -q \
  packages/galerkin/tests/test_cavity3d_validation.py \
  packages/simcase/tests/test_cavity3d_persistence_validation.py \
  packages/galerkin-refsol/tests/test_cavity_reference.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest -c pyproject.toml -q \
  packages/galerkin/tests/test_cavity3d_mesh_validation.py
```

첫 명령의 결과는 **27 passed in 30.79s**였습니다. 해석 중복도, 완전한 기준 cluster, 자유 DOF 잔차, 질량 직교성, gradient 배제, 독립 벽 trace, 물리 scaling, 축퇴 부분공간, m/um/nm 표현, 평행이동한 SI 좌표, 정확한 raw 배열 복원과 복원 후 물리, JSON/NPZ metadata, save_fields=false를 포함합니다. NPZ 데이터와 metadata는 allow_pickle=False로 읽습니다. 기준 시험 17개는 이 개수에 포함되며 따로 더하지 않습니다.

둘째 명령의 결과는 **3 passed, 9 subtests passed in 0.40s**였습니다. 이 새 시험들은 공개 solve API가 subdivision (2,2,2), (3,3,3), (4,3,2)에서 반환한 mesh를 검사하며 다음을 독립적으로 확인합니다.

- 원래 grid의 절점 수와 좌표, cell당 정확히 사면체 6개, 같은 양의 체적, 올바른 전체 체적.
- 각 cell의 사면체 쌍 15개 모두에 대한 볼록 분리축 시험: 내부가 서로 겹치지 않습니다. 각 사면체는 배정된 cell 안에 있습니다. 서로 겹치지 않는 이런 사면체 6개의 체적은 정확히 cell 체적입니다.
- 공유 면 incidence가 1 또는 2, 내부 면의 반대 방향, 연결된 사면체 인접성, 가짜 내부 경계 면 없음.
- 여섯 물리 벽 각각의 올바른 경계 삼각형 개수, 표면 Euler 특성 2.
- 실제 반환 topology마다 전체 dense 일반화 고유문제: nullity prod(subdivisions-1), 유의한 음의 고유값 없음, 독립 node-edge incidence가 상대 1e-11로 K C를 만족.

기하 검사는 parity 반사 mesh 생성법을 재현하지 않습니다. 짝수·홀수·혼합 개수와 local parity 이웃 구성을 다룹니다. 이 box mesher에 한정된 시험이며 임의 mesh나 CAD의 인증이 아닙니다. 반환된 공진기 mesh를 기존 일반 box_mesh로 대체하지 않습니다.

## 연속체 고유공간과 고정 수렴

기존 독립 진단은 raw 에지 적분에서 Whitney 장을 재구성하고 정확한 연속체 111 편광 두 개와의 overlap을 적분합니다. 정확한 기준은 k dot A=0과 L2 정규화 sqrt(8/volume)를 사용합니다. overlap의 singular value가 기저와 무관한 주각을 줍니다.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python ci/cavity3d_convergence_diagnosis.py \
  --meshes 4 8 16 --quadrature-orders 4 5 --output /tmp/alternating111.json
```

| n | 아래 모드의 부호 있는 상대 k² 오차 | 위 모드의 부호 있는 상대 k² 오차 | 부호 있는 평균 | 최대 주각 sine |
| --- | ---: | ---: | ---: | ---: |
| 4 | -0.01309442 | +0.02634101 | +0.00662330 | 0.37382373 |
| 8 | -0.00223671 | +0.00730112 | +0.00253220 | 0.18858890 |
| 16 | -0.00050188 | +0.00186554 | +0.00068183 | 0.09460838 |

최종 평균 오차 차수는 1.89290945, 개별 모드 차수는 2.15597과 1.96853, RMS 차수는 1.98283입니다. 최대 주각 sine의 차수는 0.99520으로, 정확한 연속체 부분공간 쪽으로 측정된 감소와 일치합니다. 이 값들에서 새 장 정확도 수용 기준을 추론하지 않습니다. n=16에서 보고된 최대 자유 DOF 잔차는 2.37e-13입니다.

4차와 5차 구적의 최대 주각 sine 차이는 최대 2.80e-7(n=4), n=16에서 3.43e-10으로 측정된 장 간격보다 훨씬 작습니다. 이 측정은 장 부분공간을 검사하며 개별 TE/TM label이나 부호가 해석마다 일치해야 한다고 주장하지 않습니다.

## 이력과 한계

[이전 상쇄 진단](cavity3d_convergence_diagnosis.md)은 명시적으로 기록한 이전 core 후보에 대해 여전히 유효합니다. 그 실패한 1.22837 평균 차수 결과는 재분류하지 않습니다. 현재 통과는 같은 수치 수용 규칙 아래에서 솔버가 소유한 공진기 mesh를 바꾼 결과입니다.

이 작업은 검증 시험과 문서만 바꿨습니다. 검사한 사례에서 독립적인 mesh나 물리 결함을 찾지 못했습니다. 전체 source 회귀, CLI, build/wheel 검사, 원격 CI, 최종 통합 commit 검사는 이번 독립 작업에서 실행하지 않았습니다. 다른 작업의 보고는 이 독립 결과로 세지 않습니다. 제품 통합은 별도 단계입니다.
