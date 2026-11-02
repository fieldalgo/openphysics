# 전기 전도와 Joule 가열 시간 측정

[English](../../../benchmark_electric.md) | **한국어**

저장소 루트에서 [개발 안내](development.md)의 고정 환경을 사용하고, 패키지는 이
checkout에서 설치한 것이어야 합니다. 추가 의존성은 필요하지 않습니다.

```bash
python benchmarks/benchmark_electric.py --output /tmp/electric-baseline.json
python benchmarks/benchmark_electric.py --case thermistor_picard --case thermistor_newton \
  --sizes 16 32 --repeats 5 --output /tmp/thermistor.json
```

출력 파일은 새 경로여야 하며 worker마다 checkpoint를 저장합니다. 표본마다 NumPy/SciPy
import 전에 BLAS/OpenMP thread 변수를 하나로 설정한 새 Python 프로세스에서 실행하고,
한 반복은 모든 사례를 모든 크기에서 실행한 뒤 다음 반복으로 넘어갑니다.
`JouleConvergenceError`를 포함한 실패한 풀이는 traceback과 함께 기록되고 최종 exit
status는 0이 아닙니다. 기본값은 네 사례를 `n = 8, 16, 32, 64`에서 세 번 반복하는
것입니다. Windows의 RSS는 null입니다.

## 사례

| 사례 | 작업량 |
|---|---|
| `conduction` | [Joule 튜토리얼](packages/galerkin/joule_tutorial.md)의 20 mm × 10 mm 띠를 `2n × n` 셀로 나눈 `galerkin.electric.solve_steady_electric`, σ = 3 S/m, 왼쪽 0 V, 오른쪽 2 V |
| `joule` | 같은 DC 풀이 뒤 k = 5 W/(m K), 양 끝 300 K의 `galerkin.joule_heating.solve_steady_joule_heat`. 두 단계를 따로 측정 |
| `thermistor_picard` | [온도 의존 튜토리얼](packages/galerkin/temperature_joule_tutorial.md)의 전류 구동 thermistor에 `galerkin.temperature_joule_heating.solve_temperature_joule_heat(method="picard")`: 1 m × 0.25 m를 `4n × n` 셀로, [300, 400] K에서 ρ(T) = 1 + 0.5 (T − 300 K) Ω m, 오른쪽 끝으로 1 A/m², 양 끝 300 K, `--relaxation` 기본 1.0(튜토리얼 값) |
| `thermistor_newton` | 같은 문제를 `method="newton"`으로. `ConductivityModel`이 해석적 dσ/dT를 지니므로 Newton 단계는 차분을 쓰지 않음 |

전류 밀도는 단위 깊이당 값입니다. 띠의 정확한 Joule 전력 σV²H/L = 6 W/m을 계산값
옆에 기록합니다.

## 측정량

- `mesh_seconds`: mesh 생성자.
- `stiffness_assembly_seconds`, `dirichlet_solve_seconds`(`conduction`): 같은
  mesh에서 `assemble_stiffness(mesh, σ)`와 양 끝을 고정한 그 행렬의 `solve_dirichlet`:
  solver의 검사·후처리 없는 희소 factorization과 풀이 한 번(`stiffness_nonzeros`가
  크기를 기록합니다).
- `solver_call_seconds`: 전체 `solve_steady_electric` 호출(`conduction`) 또는 안쪽의
  모든 전기·열 풀이를 포함한 전체 `solve_temperature_joule_heat` 호출(두 thermistor 사례).
- `electric_seconds`, `heat_seconds`(`joule`): DC 풀이와, 전기 snapshot을 복사하고
  수지를 검사하는 열 전달.
- `iterations`, `seconds_per_iteration`(thermistor): 반환된 history의 길이와 호출
  시간을 그것으로 나눈 값. Picard와 Newton의 반복 비용은 다르므로(Newton은 Jacobian을
  구성하고 단계를 절반으로 줄일 수 있음) 반복 수만이 아니라 호출 시간을 비교합니다.
- `peak_rss_mib`: 풀이 직후 읽은 worker 자신의
  `resource.getrusage(RUSAGE_SELF).ru_maxrss`. import를 포함한 프로세스 lifetime
  최고치이며 solver만의 메모리가 아닙니다.

표본마다 node·삼각형 수, Joule 전력, 최대 온도, 자유 node의 최대 잔차, 그리고
thermistor의 최종 온도 결손과 비선형 열 잔차를 기록합니다. 두 thermistor 방법은 수렴한
온도와 전력이 일치해야 하며, 시간을 비교하기 전에 이를 확인합니다.

## 출처와 읽기

보고서는 시작·끝의 Git revision과 dirty 상태, benchmark와 공유 `_harness.py`와 모든
galerkin 소스 파일의 hash, pin 파일 hash, Python/platform/CPU, 보이는 affinity와
cgroup-v2 한도, 그리고 worker마다 PID, 검사한 import 경로, NumPy/SciPy 버전과 BLAS
build 설정, thread 환경, profiler 상태를 기록합니다. 실행 중 소스 식별 정보가 바뀌면
최종 명령은 실패합니다.

`summary`는 표본을 사례와 크기로 묶어 성공하고 profile하지 않은 표본의 중앙값·최소·최대를
줍니다. 같은 크기·relaxation·의존성 버전으로, 다른 작업이 없는 같은 머신에서 중앙값과
범위를 비교합니다. relaxation이나 mesh를 바꾸면 새 작업량입니다. CI wall-time 임계값은
없습니다.

profile은 worker 하나를 cProfile로 실행하고(worker는 profiler가 활성이었음을 기록합니다)
비계측 표본과 분리해 둡니다.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python -m cProfile -o /tmp/thermistor32.prof benchmarks/benchmark_electric.py \
  --worker thermistor_newton --size 32 > /tmp/thermistor32-profile.json
python -m pstats /tmp/thermistor32.prof
```

## 참고 실행 (2026-11-02)

공유 클라우드 컨테이너에서 `n = 8, 16, 32`, relaxation 1.0으로 한 번 반복: Linux
x86-64, Intel Xeon 2.10 GHz, CPython 3.12, NumPy 2.5.4, SciPy
1.18.1, BLAS thread 하나. 스크립트는 commit `92b6e15`의 것이고, checkout의 dirty flag는 당시 추적되지 않은 이 변경의
안내 문서 때문입니다. 프로세스에 CPU 네 개가 보였고 cgroup CPU·메모리 한도는 보고되지 않았으며
다른 세션이 호스트를 공유했습니다.
단일 표본이므로 범위는 없습니다. 도구 검사이며 기준선이
아닙니다. 시간은 초, 메모리는 MiB입니다.

| 사례 | n | Node | 강성 assembly | Dirichlet 풀이 | Solver 호출 (전기 + 열) | 반복 | Peak RSS |
|---|---:|---:|---:|---:|---:|---:|---:|
| `conduction` | 8 | 153 | 0.0053 | 0.0010 | 0.038 | — | 85.9 |
| `conduction` | 16 | 561 | 0.0067 | 0.0027 | 0.153 | — | 87.9 |
| `conduction` | 32 | 2145 | 0.0082 | 0.0068 | 0.525 | — | 95.5 |
| `joule` | 8 | 153 | — | — | 0.039 + 0.038 | — | 86.4 |
| `joule` | 16 | 561 | — | — | 0.160 + 0.176 | — | 88.5 |
| `joule` | 32 | 2145 | — | — | 0.562 + 0.513 | — | 96.1 |
| `thermistor_picard` | 8 | 297 | — | — | 1.787 | 8 | 87.4 |
| `thermistor_picard` | 16 | 1105 | — | — | 7.990 | 8 | 92.4 |
| `thermistor_picard` | 32 | 4257 | — | — | 26.629 | 8 | 108.7 |
| `thermistor_newton` | 8 | 297 | — | — | 0.795 | 3 | 88.4 |
| `thermistor_newton` | 16 | 1105 | — | — | 3.081 | 3 | 97.0 |
| `thermistor_newton` | 32 | 4257 | — | — | 12.368 | 3 | 129.7 |

두 thermistor 방법은 모든 크기에서 같은 최대 온도와 Joule 전력(상대 10⁻¹¹까지)으로
수렴했습니다. Newton은 Picard의 여덟 pass에 비해 세 상태만 필요했고 시간은 약 절반이었습니다.
`joule`의 열 전달은 그 앞의 DC 풀이와 비슷한 비용입니다.
