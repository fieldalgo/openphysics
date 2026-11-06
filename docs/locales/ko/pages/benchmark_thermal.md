# 정상·과도 열전도 시간 측정

[English](../../../benchmark_thermal.md) | **한국어**

저장소 루트에서 [개발 안내](development.md)의 고정 환경을 사용하고, 패키지는 이
checkout에서 설치한 것이어야 합니다. 추가 의존성은 필요하지 않습니다.

```bash
python benchmarks/benchmark_thermal.py --output /tmp/thermal-baseline.json
python benchmarks/benchmark_thermal.py --case steady --case transient --sizes 32 64 \
  --repeats 5 --steps 100 --output /tmp/thermal-fine.json
```

출력 파일은 새 경로여야 하며 worker마다 checkpoint를 저장하므로 중단되거나 실패한
실행도 표본을 유지합니다(`completed=false`). 표본마다 NumPy/SciPy import 전에
BLAS/OpenMP thread 변수를 하나로 설정한 새 Python 프로세스에서 실행합니다. 한 반복은
모든 사례를 모든 크기에서 실행한 뒤 다음 반복으로 넘어갑니다. 실패한 풀이는 traceback과
함께 기록되고 최종 exit status는 0이 아니지만, 남은 표본도 계속 실행합니다. 기본값은
네 사례를 `n = 16, 32, 64, 128`에서 세 번 반복하는 것입니다. Windows의 RSS는 null입니다.

## 사례

모든 사례는 `2n × n` 셀의 1 m × 0.5 m 직사각형(`galerkin.rectangle_mesh`)을 쓰고,
k = 2 W/(m K), 균일 열원 10³ W/m³, 왼쪽 변 350 K이며 따로 말하지 않은 변은
단열입니다.

| 사례 | 작업량 |
|---|---|
| `steady` | `galerkin.thermal.solve_steady_heat`, 오른쪽 변에 300 K로의 대류 h = 5 W/(m² K) |
| `steady_regions` | 같은 문제를 `layered_rectangle_mesh`의 전도도 층 네 개(2, 4, 6, 8 W/(m K))에 영역 표로 풂 |
| `transient` | `galerkin.transient_heat.solve_transient_heat`, c = 4 J/(m³ K), 300 K에서 시작해 1 s 동안 `--steps`개의 backward Euler 단계(기본 50), 왼쪽 변 350 K 고정 |
| `document` | 배포된 `THERMAL_BOUNDARY` 예제(오른쪽에 유출 열유속과 대류)의 `subdivisions`를 `[2n, n]`으로 바꿔 headless `simcase.run`으로 실행 |

대표적인 회귀 작업량이며 기하, 경계 종류, 시간 단계 수를 망라한 조사는 아닙니다.

## 측정량

전체 solver 호출 외에 galerkin 세 사례는 같은 mesh에서 공개 assembly 함수의 시간도
재므로, profiling 없이 풀이에서 assembly가 차지하는 몫을 읽을 수 있습니다.

- `mesh_seconds`: mesh 생성자.
- `stiffness_assembly_seconds`, `mass_assembly_seconds`, `load_assembly_seconds`:
  해당 사례의 계수로 같은 mesh에 `assemble_stiffness`, `assemble_mass`,
  `assemble_load`를 호출한 시간(`stiffness_nonzeros`가 행렬 크기를 기록합니다).
- `dirichlet_solve_seconds`: 그 강성 행렬과 하중에 왼쪽 변을 고정한
  `galerkin.solve_dirichlet`: 대류·검사·후처리 없는 희소 factorization과 풀이 한 번.
- `solver_call_seconds`: 자체 assembly, 경계 시스템, 입력 검사, 잔차·수지 검사와
  결과 구성을 포함한 전체 `solve_steady_heat` 또는 `solve_transient_heat` 호출.
  과도 사례에서는 `seconds_per_step`이 이를 단계 수로 나눈 값이고 `history_bytes`는
  반환된 온도·열유속 history의 크기입니다.
- `run_seconds`(`document`): 직사각형 열전도 문서의 전체 `simcase.run`(mesh는 meshine이
  아니라 `galerkin.rectangle_mesh`). `timings`에 runner 자체의 mesh/solve 구분이 남으며,
  두 쪽 모두 단계마다 한 번씩 도는 `triangle_geometry`의 mesh 검증이 대부분입니다.
- `peak_rss_mib`: solver 호출 직후 읽은 worker 자신의
  `resource.getrusage(RUSAGE_SELF).ru_maxrss`(Linux KiB, macOS bytes를 MiB로 변환).
  import를 포함한 프로세스 lifetime 최고치이며 solver만의 메모리가 아닙니다.

`solver_call_seconds`와 assembly·Dirichlet 풀이 시간 합의 차이는 solver의 경계 처리,
검사, 후처리 비용입니다. 이 코드의 측정값이며 상한이 아닙니다. 표본마다 node·삼각형·
nonzero 수, 온도 범위, 자유 node의 최대 잔차(`max_abs_free_residual_w_per_m`)도
기록하므로 시간을 비교하기 전에 수치 일치를 확인할 수 있습니다.

## 출처

보고서는 시작·끝의 Git revision과 dirty 상태, benchmark와 공유 `_harness.py`와 모든
galerkin 소스 파일의 hash, pin 파일 hash, Python/platform/CPU, 보이는 affinity와
cgroup-v2 CPU·메모리 한도, 그리고 worker마다 PID, 검사한 import 경로, NumPy/SciPy
버전과 BLAS build 설정, thread 환경, profiler 상태를 기록합니다. 실행 중 소스 식별
정보가 바뀌면 최종 명령은 실패합니다. 기준선을 수집하기 전에 도구를 commit하십시오.

`summary`는 표본을 사례와 크기로 묶어, 성공하고 profile하지 않은 표본에 대해 측정량마다
중앙값·최소·최대를 줍니다. 같은 크기·단계·의존성 버전으로, 다른 작업이 없는 같은 머신에서
중앙값과 범위를 비교합니다. CI wall-time 임계값은 의도적으로 두지 않습니다.

## Profiling

기다리는 parent가 아닌 worker 하나를 profile하고, 비계측 표본과 분리해 둡니다(worker는
profiler가 활성이었음을 기록합니다).

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python -m cProfile -o /tmp/thermal-steady64.prof benchmarks/benchmark_thermal.py \
  --worker steady --size 64 > /tmp/thermal-steady64-profile.json
python -m pstats /tmp/thermal-steady64.prof
```

## 참고 실행 (2026-11-02)

공유 클라우드 컨테이너에서 `n = 16, 32, 64`, 기본 50단계로 한 번 반복: Linux x86-64,
Intel Xeon 2.10 GHz, CPython 3.12, NumPy 2.5.4, SciPy 1.18.1,
BLAS thread 하나. 스크립트는 commit `92b6e15`의 것이고, checkout의 dirty flag는 당시 추적되지 않은 이 변경의
안내 문서 때문입니다. 프로세스에 CPU 네 개가 보였고 cgroup CPU·메모리 한도는 보고되지 않았으며
다른 세션이 호스트를 공유했습니다.
단일 표본이므로 범위는 없습니다. 도구 검사이며 기준선이 아닙니다.
시간은 초, 메모리는 MiB입니다.

| 사례 | n | Node | Assembly (K, M, f) | Dirichlet 풀이 | Solver 호출 / run | Peak RSS |
|---|---:|---:|---:|---:|---:|---:|
| `steady` | 16 | 561 | 0.0067 | 0.0024 | 0.129 | 87.8 |
| `steady` | 32 | 2145 | 0.0102 | 0.0083 | 0.631 | 94.7 |
| `steady` | 64 | 8385 | 0.0198 | 0.0337 | 2.460 | 112.6 |
| `steady_regions` | 16 | 561 | 0.0065 | 0.0021 | 0.126 | 87.8 |
| `steady_regions` | 32 | 2145 | 0.0091 | 0.0066 | 0.519 | 94.9 |
| `steady_regions` | 64 | 8385 | 0.0188 | 0.0321 | 2.303 | 113.0 |
| `transient` | 16 | 561 | 0.0067 | 0.0022 | 0.342 | 90.4 |
| `transient` | 32 | 2145 | 0.0095 | 0.0066 | 1.143 | 105.1 |
| `transient` | 64 | 8385 | 0.0200 | 0.0326 | 4.668 | 158.2 |
| `document` | 16 | 561 | — | — | 0.282 | 87.8 |
| `document` | 32 | 2145 | — | — | 1.077 | 94.1 |
| `document` | 64 | 8385 | — | — | 5.405 | 115.5 |

이 크기에서는 공개 assembly 함수와 Dirichlet만의 풀이를 합쳐도 전체 정상 solver 호출의
약 2 %(node 8385개에서 2.46 s 중 0.054 s)이고, 호출은 node 수에 거의 비례해 node당 약
0.3 ms씩 늘어납니다. 호출의 대부분은 factorization이 아니라 solver의 경계 시스템, 검사,
후처리입니다. 50단계의 과도 호출은 같은 mesh의 정상 호출의 약 두 배입니다. `document`의
실행 시간은 mesh와 solve 단계로 거의 반씩 나뉘고, 프로파일에 따르면 두 쪽 모두 문서 경로가
두 번(계약 검사, 솔버) 실행하는 `triangle_geometry`의 mesh 검증이 대부분입니다.
이 환경의 관측이며 scaling 주장이 아닙니다.
