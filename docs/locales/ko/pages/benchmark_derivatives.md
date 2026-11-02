# 미분 비용 측정

[English](../../../benchmark_derivatives.md) | **한국어**

공개 [미분 API](packages/galerkin/differentiation.md)를 통해, gradient가 그것이 미분하는
풀이에 비해 얼마나 드는지 측정합니다: JAX·PyTorch에서 희소 풀이의 adjoint와 NumPy 풀이의
중심 차분을, 매개변수 네 개에 대해 비교합니다. 저장소 루트에서 [개발 안내](development.md)의
고정 환경을 사용합니다.

```bash
python benchmarks/benchmark_derivatives.py --output /tmp/derivatives-baseline.json
python benchmarks/benchmark_derivatives.py --case heat --backend numpy --backend jax \
  --sizes 32 64 --repeats 5 --output /tmp/derivatives-heat.json
```

JAX와 PyTorch는 선택 사항입니다(`pip install "galerkin[jax]"`, `"galerkin[torch]"`.
pin은 개발 안내에 있습니다). 라이브러리가 설치되지 않은 backend는 그 backend의 모든
표본과 `summary.skip_reasons`에 이유와 함께 `status: "skipped"`로 기록되며, 건너뛴
표본은 실행을 실패시키지 않습니다. 출력 파일은 새 경로여야 하며 worker마다 checkpoint를
저장합니다. 표본마다 BLAS/OpenMP thread 변수를 하나로 설정한 새 Python 프로세스에서
실행하고, 한 반복은 모든 사례·크기·backend를 실행한 뒤 다음 반복으로 넘어갑니다.
기본값은 세 사례를 `n = 8, 16, 32, 64`에서 세 backend 모두로 세 번 반복하는 것입니다.

## 사례

각 사례는 매개변수 네 개의 스칼라 목적 함수입니다. 미분 문서의 gradient 시험이 같은
종류의 입력을 사용합니다.

| 사례 | Mesh | 매개변수 | 목적 함수 |
|---|---|---|---|
| `heat` | `layered_rectangle_mesh`, 1 m × 0.5 m를 가로지르는 층 네 개, 층마다 `n × n` 셀 | 영역 표로 준 네 층의 전도도(2, 3, 4, 5 W/(m K)); 왼쪽 350 K, 오른쪽에 300 K로의 대류 h = 5 W/(m² K) | 오른쪽 변의 평균 온도 |
| `transient` | `rectangle_mesh`, `2n × n` 셀 | k = 2.5, c = 4, callback으로 준 열원 q (1 + x) W/m³의 진폭 q, 그리고 균일 초기장과 왼쪽 Dirichlet 값으로 함께 쓰는 T₀ = 300 K; 1 s 동안 `--steps`개의 backward Euler 단계(기본 20) | 오른쪽 절반의 최종 평균 온도 |
| `elasticity` | `rectangle_mesh`, 1 m × 0.25 m, `4n × n` 셀, 왼쪽 끝 고정, 평면 응력 | E = 70 GPa, ν = 0.3, 오른쪽 끝의 traction (10⁶, 2·10⁵) Pa를 live 벡터로 | 오른쪽 끝의 평균 x 변위 |

## 측정량

- `forward_seconds`: 이 backend의 값(NumPy float, JAX float64 스칼라,
  `requires_grad`인 PyTorch float64 leaf)으로 목적 함수를 처음 호출한 시간.
  `second_forward_seconds`는 두 번째 호출로, 느리게 import되는 SciPy 모듈이나 JAX의
  작은 primitive 컴파일 같은 일회성 비용을 제외합니다.
- `gradient_seconds`: NumPy에서는 매개변수마다 상대 간격 10⁻⁶의 중심 차분, 풀이 여덟
  번(`gradient_solves`); JAX에서는 `jax.grad` 호출 한 번; PyTorch에서는 forward 호출
  한 번과 `.backward()`(`backward_seconds`는 backward 부분만). live backend에서
  gradient는 forward 풀이와 전치 행렬의 adjoint 풀이 한 번이며 매개변수 수와 무관합니다.
  그 비용은 매개변수 수에 따라 늘지 않아야 하고, 유한 차분은 선형으로 늘어납니다.
- `gradient_to_forward_ratio`: `gradient_seconds / second_forward_seconds`.
  매개변수 네 개의 유한 차분에서 8에 가까운 비율은 풀이가 지배함을, 더 낮은 비율은
  호출마다의 고정 overhead가 지배함을 뜻합니다.
- `peak_rss_mib`: gradient 뒤의 worker 자신의
  `resource.getrusage(RUSAGE_SELF).ru_maxrss`. import와, live backend에서는 기록된
  reverse pass를 포함한 프로세스 lifetime 최고치입니다. 과도 문제에서
  `checkpoint_every`가 그 메모리를 시간과 어떻게 맞바꾸는지는 미분 문서에 있습니다.
  이 benchmark는 모든 단계를 유지합니다.

표본마다 목적 함수 값과 gradient를 기록하므로, 한 크기의 유한 차분과 adjoint gradient를
backend 사이에서 비교할 수 있습니다(중심 차분의 정확도인 약 10⁻⁶ 상대까지). JAX와
PyTorch의 값은 NumPy 풀이와 rounding까지 일치합니다. 불일치는 시간을 비교하기 전에
조사해야 할 결함입니다.

## 출처와 읽기

보고서는 시작·끝의 Git revision과 dirty 상태, benchmark와 공유 `_harness.py`와 모든
galerkin 소스 파일의 hash, pin 파일 hash, Python/platform/CPU, 보이는 affinity와
cgroup-v2 한도, 그리고 worker마다 PID, 검사한 import 경로, NumPy/SciPy 버전과 BLAS
build 설정, live 라이브러리의 버전, thread 환경, profiler 상태를 기록합니다. 실행 중
소스 식별 정보가 바뀌면 최종 명령은 실패합니다.

`summary`는 표본을 사례·크기·backend로 묶어 성공하고 profile하지 않은 표본의
중앙값·최소·최대를 줍니다. 같은 크기·단계·라이브러리 버전으로, 다른 작업이 없는 같은
머신에서 중앙값과 범위를 비교합니다. JAX와 PyTorch는 CPU에서 실행하며 GPU는 쓰지
않습니다. CI wall-time 임계값은 없습니다.

## 참고 실행 (2026-11-02)

공유 클라우드 컨테이너에서 `n = 8, 16, 32`, 과도 20단계로 한 번 반복: Linux x86-64,
Intel Xeon 2.10 GHz, CPython 3.12, NumPy 2.5.4, SciPy 1.18.1,
BLAS thread 하나. 그 환경에는 JAX와 PyTorch가 설치되지 않아 그 표본은 건너뜀으로
기록되었고, 표에는 NumPy forward 풀이와 중심 차분만 있습니다. 스크립트는 commit `92b6e15`의 것이고, checkout의 dirty flag는 당시 추적되지 않은 이 변경의
안내 문서 때문입니다. 프로세스에 CPU 네 개가 보였고 cgroup CPU·메모리 한도는 보고되지 않았으며
다른 세션이 호스트를 공유했습니다.
단일 표본이므로 범위는 없습니다. 도구 검사이며 기준선이 아닙니다. 시간은 초, 메모리는 MiB입니다.

| 사례 | n | Node | Forward (첫 호출) | Forward (두 번째) | 중심 차분 (풀이 8번) | 비율 | Peak RSS |
|---|---:|---:|---:|---:|---:|---:|---:|
| `heat` | 8 | 297 | 0.074 | 0.068 | 0.653 | 9.63 | 73.7 |
| `heat` | 16 | 1105 | 0.312 | 0.267 | 1.982 | 7.42 | 79.6 |
| `heat` | 32 | 4257 | 1.269 | 1.206 | 8.893 | 7.38 | 92.3 |
| `transient` | 8 | 153 | 0.114 | 0.098 | 0.852 | 8.72 | 73.5 |
| `transient` | 16 | 561 | 0.283 | 0.285 | 2.301 | 8.07 | 77.2 |
| `transient` | 32 | 2145 | 1.030 | 1.206 | 8.611 | 7.14 | 89.5 |
| `elasticity` | 8 | 297 | 0.077 | 0.065 | 0.667 | 10.29 | 75.0 |
| `elasticity` | 16 | 1105 | 0.297 | 0.260 | 2.372 | 9.14 | 82.1 |
| `elasticity` | 32 | 4257 | 1.235 | 1.118 | 9.503 | 8.50 | 109.3 |

유한 차분 gradient는 매개변수 네 개에 대해 forward 풀이 7~10번의 비용이며 예상대로입니다
(풀이 여덟 번과 overhead). adjoint 열은 이 환경에서 측정할 수 없었습니다. JAX와 PyTorch에서는
미분 문서의 시험이 gradient가 forward 한 번과 adjoint 풀이 한 번임을 보여 주며, 그 extra가
설치되면 이 benchmark가 시간을 잽니다. gradient는 닫힌 형태가 있는 곳에서 그것과 일치합니다:
`heat` 목적 함수의 네 층 전도도에 대한 도함수는 모든 크기에서 2.304, 1.024, 0.576,
0.369 K/(W/(m K))입니다(층 slab은 P1에 정확합니다).
