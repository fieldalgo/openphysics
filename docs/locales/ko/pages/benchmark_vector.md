# 벡터 모드 성능 측정

[English original](../../../benchmark_vector.md)

번역 기준은 `7259635a150106a7b98869e7f5a7aa8561ba8028`의 영문 문서입니다.

저장소 루트에서 [개발 안내](development.md)의 editable 설치와 고정 환경을 사용합니다.
추가 의존성은 필요하지 않습니다.

```bash
python benchmarks/benchmark_vector.py --repeats 3 --output /tmp/vector-baseline.json
python benchmarks/benchmark_vector.py --case te --case tm --repeats 5 \
  --output /tmp/vector-slab.json --snapshots /tmp/vector-slab-fields
```

출력 파일과 선택적 snapshot 디렉터리는 새 경로여야 합니다. 반복마다 BLAS/OpenMP
thread 한도를 하나로 설정한 새 Python 프로세스에서 실행합니다. import하는 구현 패키지는
이 checkout에서 와야 합니다. 보고서는 Git revision, dirty 상태, Python/platform/의존성
버전, 검증 pin hash, 정확한 입력 문서와 hash, mesh 크기, 원시 시간, 수치 결과,
추적 증거와 프로세스 peak RSS를 기록합니다. 예외가 나면 명령은 실패하며 실패한 풀이를
성공 표본으로 시간을 재지 않습니다. Windows의 RSS는 null입니다.

사례는 slab TE·TM의 다섯 점 sweep, 두 모드 slab의 세 점 sweep, 단일 점 slab TE,
여섯 모드 fiber, 단일 점 Hadley rib, mesh 크기를 절반으로 줄인 TE sweep입니다.
대표적인 회귀 작업량이며 모든 기하나 모드 수를 망라한 benchmark는 아닙니다.

`seconds`는 mesh 생성과 tracking을 포함한 전체 `run` 호출을 측정합니다. import,
입력 parsing, 출력 직렬화와 선택적 snapshot 쓰기는 제외합니다. `timings`는 runner
자체의 mesh/solve 시간 구분이며 모든 준비·tracking 비용을 포함하지 않습니다.
`peak_rss_mib`는 풀이 뒤의 프로세스 lifetime 최고치로 import도 포함합니다. RSS는
solver만 분리한 메모리가 아닙니다. 별도 `topology_seconds_median`은 run과 RSS
측정 뒤 풀이에 사용한 mesh에서 `EdgeSpace`를 완전히 구성하는 작업을 21번 측정합니다.

동일한 문서·의존성 버전·thread 한도를 사용하고, 다른 작업이 없는 같은 머신에서
중앙값과 범위를 비교합니다. 모든 표본을 보존하고 시간을 비교하기 전에 수치 결과를
검토합니다. mesh·의존성·solver 설정 변경을 밝히지 않은 채 시간 비교에 섞지 마십시오.
분리한 연산이 개선되어도 전체 run의 작은 차이는 잡음일 수 있습니다. CI wall-time
임계값은 의도적으로 두지 않습니다.

profile을 얻으려면 단일 사례 worker를 직접 호출합니다. parent는 주로 child를
기다립니다. 이 측정은 비계측 run과 분리해 둡니다.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  python -m cProfile -o /tmp/vector-te.prof benchmarks/benchmark_vector.py --worker te
python -m pstats /tmp/vector-te.prof
```

profile은 import와 별도 topology 측정도 포함합니다. `run`, `solve_modes`, `eigs`,
assembly와 `EdgeSpace` 항목을 따로 검토합니다. worker는 내부 측정 진입점이며
solver 설정 API가 아닙니다.

## 수치 검증

시간만으로는 충분하지 않습니다. 보고서 사이의 유효 굴절률·군 굴절률·candidate rank와
overlap을 비교합니다. `--snapshots`를 사용하면 각 사례 첫 반복에 edge 순서와 원시
복소 field 배열도 저장합니다. assembly·solver 입력을 보존하는 구현은 이 배열들도
보존해야 합니다. 더 일반적인 solver 변경에는 위상 불변 field 비교가 필요하며,
퇴화 고유장은 부분공간 안에서 회전할 수 있습니다.

[개발 안내](development.md)의 전체 시험과 배포 검사를 실행합니다. 기존 검사는 해석적
TE/TM·fiber 정답, Hadley, mesh/영역/파장 수렴, 물리 field 복원·Maxwell 잔차,
단위·분산·혼합 경계와 보수적인 tracking 실패를 다룹니다. 수치 계약을 별도로 검토·검증하지
않는 한 성능 작업 동안 solver 허용치, candidate 수와 tracking 임계값은 고정합니다.

## Edge 번호 부여 측정 (2026-10-15)

2D `EdgeSpace` 생성자는 두 정수 끝점 열을 직접 정렬한 뒤 인접한 고유 쌍에 번호를
붙이고 각 삼각형에 다시 매핑합니다. NumPy 구조화 행 정렬의 overhead 없이 기존의
사전식 번호·방향 부호를 유지합니다. node ID를 하나의 정수로 packing하지 않고,
고유값 문제나 solver/tracking 허용치도 바꾸지 않습니다.

아래 비교는 최적화 전 `44d0339`의 solver와 새 생성자를 사용한 같은 solver 사이의
비교입니다. benchmark 도구는 `d84268f`에서 도입했으며, commit하지 않은 도구·문서
변경 때문에 기준선 보고서의 dirty flag가 설정되었습니다. Linux x86-64, CPython
3.12.14, NumPy 2.5.4, SciPy 1.18.1, Shapely 2.2.0을 사용했고 CPU 네 개의 quota,
32 GiB 메모리 한도와 BLAS thread 하나를 적용했습니다. 사례마다 새 프로세스 run
세 번을 수행하고, 각 run에 별도 topology 구성 21번을 수행했습니다. 아래 값은 중앙값입니다.
run을 순차 수집했으므로 전체 run 비교에는 머신 부하·시간 변동도 포함됩니다.

| 사례 | 삼각형 | 이전 topology (ms) | 이후 topology (ms) | 비율 | 이전 run (s) | 이후 run (s) |
|---|---:|---:|---:|---:|---:|---:|
| TE sweep | 1,381 | 1.780 | 0.405 | 4.40 | 0.6210 | 0.6203 |
| TM sweep | 1,381 | 1.774 | 0.403 | 4.40 | 1.1685 | 1.2036 |
| Two-mode sweep | 1,381 | 1.773 | 0.451 | 3.93 | 0.4160 | 0.3792 |
| Single TE | 1,381 | 1.771 | 0.450 | 3.94 | 0.1217 | 0.1159 |
| Fiber | 1,792 | 2.248 | 0.538 | 4.17 | 0.2371 | 0.2460 |
| Hadley | 8,284 | 12.531 | 2.648 | 4.73 | 1.8987 | 1.8842 |
| Fine TE sweep | 5,509 | 7.669 | 1.795 | 4.27 | 6.7156 | 6.9678 |

개선은 topology 구성에 대해 확인되었습니다. 이 표본은 전체 run의 일관된 속도 향상을
입증하지 않습니다. 시험한 sweep에서는 고유값 풀이가 지배적입니다. 예를 들어 fine TE
run 시간 범위는 이전 6.539–6.755 s, 이후 6.526–7.353 s였습니다. 프로세스 peak RSS
중앙값은 이전 92.0–131.8 MiB, 이후 91.6–133.1 MiB 범위였으며 메모리 감소의 증거가
아닙니다.

모든 반복에서 이전·이후 유효 굴절률, 군 굴절률과 tracking 증거가 정확히 같았습니다.
일곱 사례 모두의 첫 run snapshot에서 edge map과 횡·종·centroid 전기장 배열이
정확히 같았습니다. 시험은 빈 topology를 포함한 node/triangle 순서 변경 뒤에도
물리 field 복원과 curl이 0임을 추가 검증합니다. 이 측정은 해당 환경과 입력을 설명하며
성능을 보장하지 않습니다.
