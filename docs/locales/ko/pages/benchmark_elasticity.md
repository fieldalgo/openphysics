# 탄성과 열탄성 workflow 시간 측정

[English](../../../benchmark_elasticity.md) | **한국어**

저장소 루트에서 [개발 안내](development.md)의 고정 환경을 사용하고, 패키지는 이
checkout에서 설치한 것이어야 합니다. 추가 의존성은 필요하지 않습니다.

```bash
python benchmarks/benchmark_elasticity.py --output /tmp/elasticity-baseline.json
python benchmarks/benchmark_elasticity.py --case elasticity --sizes 32 64 --repeats 5 \
  --output /tmp/elasticity-fine.json
```

출력 파일은 새 경로여야 하며 worker마다 checkpoint를 저장합니다. 표본마다 NumPy/SciPy
import 전에 BLAS/OpenMP thread 변수를 하나로 설정한 새 Python 프로세스에서 실행하고,
한 반복은 모든 사례를 모든 크기에서 실행한 뒤 다음 반복으로 넘어갑니다. 실패한 풀이는
traceback과 함께 기록되고 최종 exit status는 0이 아닙니다. 기본값은 세 사례를
`n = 8, 16, 32, 64`에서 세 번 반복하는 것입니다. Windows의 RSS는 null입니다.

## 사례

모든 사례는 `4n × n` 셀의 1 m × 0.25 m 막대(`galerkin.rectangle_mesh`)를 쓰고,
E = 70 GPa, ν = 0.3, 평면 응력, 왼쪽 끝에서 두 변위 성분을 고정합니다(구속 자유도
`2(n+1)`개).

| 사례 | 작업량 |
|---|---|
| `elasticity` | 오른쪽 끝에 상수 traction (10⁶, 0) Pa를 준 `galerkin.elasticity.solve_elasticity` |
| `thermoelastic_traction` | `solve_steady_heat`(k = 50 W/(m K), 왼쪽 300 K, 오른쪽 350 K), `freeze_temperature`, 그 뒤 α = 12·10⁻⁶ /K, T_ref = 293.15 K, 오른쪽 끝 전체 traction (8·10⁶, 3·10⁶) Pa의 `galerkin.thermoelasticity.solve_thermoelasticity`. 세 단계를 따로 측정 |
| `workflow` | `galerkin.thermal_mechanical.solve_steady_thermoelasticity`: 같은 열 문제와 재료를 한 호출로, 자연 traction은 0 |

역학 문제는 선형 정적 P1 풀이이며 접촉, 큰 변형, 3D 사례는 다루지 않습니다.

## 측정량

- `mesh_seconds`: mesh 생성자.
- `solver_call_seconds`(`elasticity`): assembly, 희소 factorization과 풀이, 잔차 검사,
  변형률·응력 후처리를 포함한 전체 `solve_elasticity` 호출.
- `heat_seconds`, `freeze_seconds`, `mechanics_seconds`(`thermoelastic_traction`):
  열 풀이, snapshot(mesh와 field의 hash를 계산), 역학 단계.
- `workflow_seconds`(`workflow`): mesh 격리, 두 단계, manifest를 포함한 전체 한 호출
  workflow.
- `peak_rss_mib`: 마지막 단계 직후 읽은 worker 자신의
  `resource.getrusage(RUSAGE_SELF).ru_maxrss`. import를 포함한 프로세스 lifetime
  최고치이며 solver만의 메모리가 아닙니다.

표본마다 node·삼각형·DOF 수, 자유 자유도의 최대 잔차(`max_abs_free_residual_n_per_m`),
그리고 일치 확인용 해의 양을 기록합니다: 평균 끝단 변위(방향 참고용으로 단축 막대 값 σL/E를
나란히 둡니다. 고정단 막대의 P1 해가 이 값과 같을 것으로 기대하지는 않습니다), 최대 변위,
최대 온도, 물리 탄성 에너지. 시간을 비교하기 전에 이 값들을 확인합니다.

## 출처와 읽기

보고서는 시작·끝의 Git revision과 dirty 상태, benchmark와 공유 `_harness.py`와 모든
galerkin 소스 파일의 hash, pin 파일 hash, Python/platform/CPU, 보이는 affinity와
cgroup-v2 한도, 그리고 worker마다 PID, 검사한 import 경로, NumPy/SciPy 버전과 BLAS
build 설정, thread 환경, profiler 상태를 기록합니다. 실행 중 소스 식별 정보가 바뀌면
최종 명령은 실패합니다.

`summary`는 표본을 사례와 크기로 묶어 성공하고 profile하지 않은 표본의 중앙값·최소·최대를
줍니다. 같은 크기·의존성 버전으로, 다른 작업이 없는 같은 머신에서 중앙값과 범위를
비교합니다. 한 번의 반복으로 속도 향상을 추론하지 마십시오. CI wall-time 임계값은 없습니다.

profile은 worker 하나를 cProfile로 실행하고(worker는 profiler가 활성이었음을 기록합니다)
비계측 표본과 분리해 둡니다.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python -m cProfile -o /tmp/elasticity32.prof benchmarks/benchmark_elasticity.py \
  --worker elasticity --size 32 > /tmp/elasticity32-profile.json
python -m pstats /tmp/elasticity32.prof
```

## 참고 실행 (2026-11-02)

공유 클라우드 컨테이너에서 `n = 8, 16, 32`로 한 번 반복: Linux x86-64, Intel Xeon
2.10 GHz, CPython 3.12, NumPy 2.5.4, SciPy 1.18.1, BLAS thread 하나.
스크립트는 commit `92b6e15`의 것이고, checkout의 dirty flag는 당시 추적되지 않은 이 변경의
안내 문서 때문입니다. 프로세스에 CPU 네 개가 보였고 cgroup CPU·메모리 한도는 보고되지 않았으며
다른 세션이 호스트를 공유했습니다.
단일 표본이므로 범위는 없습니다. 도구 검사이며 기준선이 아닙니다. 시간은 초, 메모리는
MiB입니다.

| 사례 | n | DOF | 역학 / 호출 | 열 | Freeze | Peak RSS |
|---|---:|---:|---:|---:|---:|---:|
| `elasticity` | 8 | 594 | 0.089 | — | — | 87.9 |
| `elasticity` | 16 | 2210 | 0.302 | — | — | 94.4 |
| `elasticity` | 32 | 8514 | 1.228 | — | — | 121.5 |
| `thermoelastic_traction` | 8 | 594 | 0.076 | 0.069 | 0.0617 | 88.4 |
| `thermoelastic_traction` | 16 | 2210 | 0.283 | 0.261 | 0.2501 | 95.5 |
| `thermoelastic_traction` | 32 | 8514 | 1.125 | 0.975 | 0.9616 | 123.5 |
| `workflow` | 8 | 594 | 0.220 | — | — | 88.7 |
| `workflow` | 16 | 2210 | 0.813 | — | — | 95.1 |
| `workflow` | 32 | 8514 | 3.673 | — | — | 124.5 |
