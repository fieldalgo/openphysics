# 3D PEC 공진기의 시간·메모리 측정

[English original](../../../benchmark_cavity.md)

번역 기준은 `7259635a150106a7b98869e7f5a7aa8561ba8028`의 영문 문서입니다.

[개발 안내](development.md)의 고정 Python 환경을 사용하고 저장소 루트에서 실행합니다.
이 소스 benchmark는 자신의 checkout에서 `packages/galerkin/src`를 명시적으로 로드하고
import 위치를 검사합니다. 새 의존성, solver 최적화, API 변경이나 CI 시간 gate는 없습니다.

```bash
python benchmarks/benchmark_cavity.py --output /tmp/cavity-baseline.json
```

기본값은 여덟 조건 각각 세 번 반복입니다. 정육면체 `(1,1,1)` m와 직육면체
`(1,0.8,0.6)` m에 대해 `n=4,8,12,16`의 `(n,n,n)` Cartesian 분할을 사용합니다.
각 solve는 **210 MHz** 부근의 개별 모드 여섯 개를 요청합니다. 이는 solver의 유한
`near_target` 탐색이지, 반환 집합이 완전한 최저 스펙트럼이거나 모든 퇴화 partner를
포함한다는 주장이 아닙니다. 정확한 개수 정책은 cluster를 나눌 수 있습니다. 모든 호출에서
목표·모드 수·solver 허용치를 동일하게 고정합니다.

반복마다 새 Python subprocess를 순차 실행하며 **NumPy/SciPy import 전에**
BLAS/OpenMP 환경 한도를 하나로 설정합니다. 반복, 분할 수, 기하 순으로 실행하고
warm-up을 버리지 않습니다. 출력은 새 파일이어야 합니다. worker마다 checkpoint를
저장하며 성공·실패·timeout 시도를 모두 유지합니다. 실패하면 최종 exit status는
0이 아니지만 뒤에 예정된 사례도 계속 실행합니다. worker별 300초 timeout은 해당
worker를 종료·회수하며 RSS는 parent에서 복사하지 않고 미확보로 둡니다. 중단된
보고서는 `completed=false`입니다. 원시 보고서는 소스 checkout 밖에 보존합니다.

짧은 검사 또는 의도적으로 실패하는 solve는 다음과 같습니다.

```bash
python benchmarks/benchmark_cavity.py --case cube --subdivisions 4 --repeats 1 \
  --output /tmp/cavity-smoke.json
python benchmarks/benchmark_cavity.py --case cube --subdivisions 1 --repeats 1 \
  --output /tmp/cavity-insufficient-dofs.json
```

두 번째 명령은 물리 DOF가 부족한 mesh에서 모드 여섯 개를 요청하므로 실패해야 합니다.
성능 표본이 아닙니다. 사례·mesh·개수·목표·timeout은 `--help`를 통해 명시적으로
바꿀 수 있습니다. 바꾸면 새 작업량이 되므로 비교할 때 밝혀야 합니다.

## 측정량과 출처

- `solve_wall_seconds`: mesh 구성, topology, assembly, kernel projection,
  factorization, 고유값 풀이, 품질 검사와 반환 field/mesh 구성을 포함한 전체
  `solve_cavity_box` 호출입니다. import·보고서 구성·직렬화는 제외합니다. 실패 시
  호출까지 도달했다면 대신 `failed_solve_wall_seconds`가 있습니다.
- `subprocess_wall_seconds`: parent가 child를 시작하고 기다린 경과 시간으로,
  import·보고·프로세스 종료를 포함합니다. 별도 측정량이며 solve 시간에 더하지 않습니다.
- `peak_rss_mib`: solve 직후 읽은 **worker 자신의**
  `resource.getrusage(RUSAGE_SELF).ru_maxrss`입니다. Linux는 KiB, macOS는 bytes를
  보고하며 모두 MiB(2^20 bytes)로 변환하고 원시 값·단위도 유지합니다. import를 포함해
  solve까지의 프로세스 lifetime 최고치입니다. solver만의 증분 메모리, 현재 RSS,
  Python allocation 집계나 parent의 peak가 아닙니다. 미지원 플랫폼에서는 null입니다.

보고서는 모든 개별 표본과 성공 표본의 median/min/max를 포함하며,
attempted/succeeded/failed 개수를 명시합니다. 입력 hash, node/tet/total edge/PEC/free
DOF 수, 반환 주파수·제곱 파수, 모든 잔차, cluster metadata와 반환된 두 field 배열의
크기를 보존합니다. 이 배열 크기는 solver의 총 메모리가 아닙니다.

출처에는 시작·끝 Git SHA와 dirty 상태, benchmark·engine 파일 hash, pin 파일 hash,
Python/platform/CPU, 가능하면 보이는 affinity와 cgroup-v2 CPU/메모리 한도가 있습니다.
각 worker는 PID, 검사한 import 경로, NumPy/SciPy 버전, 두 라이브러리의 BLAS build
설정과 thread 환경을 기록합니다. thread 변수는 thread 하나를 요청하는 것이며 build
설정은 실제 native thread 수를 독립 측정한 것이 아닙니다. 측정 중 소스 식별 정보가
바뀌면 최종 명령은 실패합니다. 기준선을 수집하기 전에 도구를 commit하고 run 내내
checkout을 바꾸지 마십시오.

다른 작업이 없는 같은 머신에서 중앙값**과 범위**를 사용합니다. 이 단일 버전 기준선만으로
속도 향상이나 메모리 감소를 추론하지 마십시오. 새 프로세스 반복이 차가운 filesystem
cache나 호스트 자원 격리를 보장하지 않습니다. 시간을 비교하기 전에 잔차·반환 개수·주파수
일관성을 검토합니다. 유한 near-target 선택은 여전히 별도 물리 수용 검증이 필요합니다.

## 별도 profiling

기다리는 parent가 아닌 worker 하나를 profile합니다. 그 시간·RSS를 비계측 기준선과
분리해 둡니다.

worker는 기존 `sys.getprofile()` hook과 `sys.monitoring.PROFILER_ID`의 활성 event를
검출합니다(CPython 3.12+). monitoring tool 이름, event mask와 기존 hook 상태를
`profiling`에 기록합니다. monitoring tool을 예약했어도 활성 event가 없으면 active로
표시하지 않습니다. 기존 hook만으로는 `None`을 반환하는 CPython 3.12의 cProfile
검출을 수정한 것입니다. native·외부 profiler나 다른 monitoring slot 도구를 모두
검출하는 기능은 아닙니다. 실제 profiling 명령과 artifact도 출처로 보존합니다.

요약의 `succeeded`는 모든 성공 solve 수이며 `unprofiled_succeeded`와
`profiled_succeeded`가 이를 나눕니다. 시간·RSS median/min/max에는 `profiled=true`가
아닌 성공 표본만 사용합니다. `failed`는 timeout을 포함한 실패 시도 수입니다.
전부 profile했거나 전부 실패한 그룹은 시간·RSS 통계가 null입니다. 구 도구의 과거
보고서는 CPython 3.12 cProfile을 잘못 false로 표시할 수 있습니다. 요약기는 누락된
출처를 복구할 수 없습니다. 도구를 갱신한 뒤에도 외부 명령에 근거해 그 보고서를 분리합니다.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
BLIS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_THREAD_LIMIT=1 \
python -m cProfile -o /tmp/cavity-rectangle16.prof benchmarks/benchmark_cavity.py \
  --worker rectangle --subdivisions 16 > /tmp/cavity-rectangle16-profile.json
python -m pstats /tmp/cavity-rectangle16.prof
```

profile에는 solve뿐 아니라 import·보고도 포함합니다. 중첩 항목을 합산하지 않고
cumulative 시간을 해석합니다. `solve_cavity_box`, 희소 factorization, ARPACK/선형
solve, assembly, topology와 field 복원은 call tree에서 겹칩니다. cProfile은 peak
RSS를 개별 단계에 귀속시킬 수 없습니다. 메모리 최적화를 선택하기 전에 별도 후속
작업으로 그러한 귀속을 확립해야 합니다.

[개발 안내](development.md)의 루트 전체 시험은 시간 측정과 따로 실행해 benchmark의
CPU·메모리를 놓고 경쟁하지 않게 합니다. 이 도구는 기존 고정 수치 수용 gate를
보완하며 대체하지 않습니다.

## 인계받은 기준선 증거 (2026-10-15)

이전 담당은 clean source `88ee02c2bfc49ebfa6df4b55260310790613ea2c`에서 기본
비계측 solve 24/24 성공, 각 여섯 모드 반환, 최대 상대 잔차 2.01e-12, 조건별 세
반복의 주파수가 같았다고 보고했습니다. 후임은 **그 원시 보고서나 profile을 검사하지
않았습니다**. 아래 값은 독립 재현 측정이 아닌 인계받은 보고입니다.

| n=16, 인계 보고 | Cube | Rectangle |
| --- | ---: | ---: |
| 풀이 중앙값, seconds | 13.0385 | 12.8399 |
| 풀이 min–max, seconds | 12.4931–13.8035 | 12.8333–14.1168 |
| 프로세스 wall 중앙값, seconds | 13.3233 | 13.1404 |
| 프로세스 lifetime peak RSS 중앙값, MiB | 625.1875 | 628.3828 |
| peak RSS min–max, MiB | 621.9688–626.4336 | 626.8477–628.4414 |
| 전체/자유 edge DOF | 31024/26416 | 31024/26416 |
| 사면체 | 24576 | 24576 |

보고 환경은 Linux x86-64, CPython 3.12.14, NumPy 2.5.4, SciPy 1.18.1,
요청 BLAS/OpenMP thread 하나, AMD EPYC 9V74, CPU 네 개 quota, 메모리 한도 32 GiB입니다.
이후 보관한 이전 담당 세션을 다시 시작하지 않고 기록된 명령 출력을 회수했습니다.
여기에는 아래 여덟 그룹 요약과 원래 기준선 JSON digest
`dca2d01105934093269c3e5c5b6210ad5f2cdc327c29e68d08f32efb8dec6fb8`가 있습니다.
이는 출력된 중앙값·범위를 회수한 것이며 원시 24표본 JSON이나 binary profile을 회수한
것은 아닙니다. 표본별 audit와 원래 artifact 전달은 아직 남아 있습니다. 서로 다른
머신 사이의 속도 향상이나 메모리 감소를 주장하지 않습니다.

| 기하 | n | 자유 edge DOF | 풀이 seconds: 중앙값 [min, max] | 프로세스 중앙값, s | Worker lifetime RSS MiB: 중앙값 [min, max] |
| --- | ---: | ---: | --- | ---: | --- |
| Cube | 4 | 316 | 0.0316 [0.0271, 0.0331] | 0.3455 | 66.3125 [65.3438, 66.5352] |
| Cube | 8 | 3032 | 0.2548 [0.2268, 0.2808] | 0.5634 | 80.8359 [80.7930, 81.1445] |
| Cube | 12 | 10836 | 2.3142 [2.0294, 2.3908] | 2.6945 | 166.1484 [166.0078, 167.3359] |
| Cube | 16 | 26416 | 13.0385 [12.4931, 13.8035] | 13.3233 | 625.1875 [621.9688, 626.4336] |
| Rectangle | 4 | 316 | 0.0309 [0.0273, 0.0343] | 0.3843 | 66.0273 [65.6641, 66.4336] |
| Rectangle | 8 | 3032 | 0.2490 [0.2345, 0.2641] | 0.5915 | 81.1641 [79.6836, 81.3789] |
| Rectangle | 12 | 10836 | 2.2943 [2.1346, 2.3477] | 2.6291 | 166.7148 [166.6250, 167.1484] |
| Rectangle | 16 | 26416 | 12.8399 [12.8333, 14.1168] | 13.1404 | 628.3828 [626.8477, 628.4414] |

출력 요약에서 반복 사이 주파수 차이는 0이고 최대 상대 잔차는 2.01e-12 미만이라고
보고했습니다. n=8에서 n=16으로 갈 때 두 기하 모두 free DOF가 약 8.7배, solve
중앙값이 약 51배, lifetime RSS가 약 7.7배로 증가합니다. 이 입력에서 관측한 비율이며
점근 복잡도 fitting, solver만의 메모리 측정이나 최적화 증거가 아닙니다. 작은 n=4의
프로세스 시간은 solver 호출 밖의 작업이 지배합니다. 아래 별도 factorization profile
보고와 함께 보면 큰 사례는 반복법을 선택하기 전에 factorization 메모리·시간 연구가
필요함을 보여줍니다. 대체 방법도 기존 물리 gate를 만족해야 합니다.

이전 담당은 직육면체 n=16 cProfile 하나를 별도로 보고했습니다. 총 13.278 s,
solve cumulative 12.856 s, `splu` 두 호출에 걸쳐 7.962 s, `eigsh`에 4.342 s입니다.
원래 metadata는 `profiled=false`라고 잘못 기록했습니다. 그 flag가 아닌 명령과
profile artifact가 계측 실행임을 식별합니다. 중첩 cumulative 값은 더하면 안 됩니다.
metadata assertion 실패 뒤 원래 profile-analysis JSON은 생성되지 않았습니다.
별도 flag 오류가 비계측 24회 보고를 무효화한 것은 아닙니다.

## 후임의 검증과 한계

후임은 다른 개발 세션과 공유하는 호스트에서 별도 checkout·환경·records 디렉터리를
사용합니다. 다른 수치 작업이 시간에 영향을 줄 수 있으며 배타적 부하 조건은 확인되지
않았습니다. 검증 범위는 metadata/CLI/summarizer 검사, 새 cube/rectangle n=4 smoke
solve와 별도 rectangle n=4 profile로 제한됩니다. 도구 검사이며 **새 기준선이 아닙니다**.
환경은 Python 3.12.14, NumPy 2.3.5, SciPy 1.17.0이므로 인계된 시간 측정 환경과
수치 라이브러리 버전도 다릅니다. 나열된 BLAS/OpenMP 변수 여섯 개를 모두 import 전에
thread 하나로 요청합니다.

metadata 검사는 실제 cProfile 활성화·비활성화, 비활성 monitoring 예약, 기존 hook
fallback, success/error/timeout/profile 혼합 요약, CLI 검증과 덮어쓰기 거부를 다룹니다.
mock resource 값으로 Linux KiB·macOS bytes 변환도 검사했지만 native macOS 검증은 아닙니다.

clean source `2223528cc3f46f24471399e2288618751023f424`의 제한된 fresh-worker
검사에서는 두 n=4 기하 모두 모드 여섯 개, 사면체 384개, free edge DOF 316개를
반환했습니다. 최대 잔차는 cube 2.682e-13, rectangle 5.282e-15였습니다. 비계측
worker 둘은 false로 표시됐고 별도 rectangle n=4 cProfile worker는 도구 `cProfile`과
활성 monitoring event를 가진 true로 표시됐습니다. 보고서에는 소스 식별 정보가 바뀌지
않았다고 기록됐습니다. 당시 보이는 한도는 CPU 여덟 개 quota·메모리 8 GiB,
affinity CPU 아홉 개로, 인계 환경과 다릅니다.

첫 smoke 명령은 worker 둘의 성공을 출력하고 0으로 종료했지만 뒤에 읽었을 때는 첫
미완료 checkpoint만 보였습니다. 그 파일을 보존하고 완료 증거로는 거부했습니다.
제한된 재시도에서는 같은 호출 안에서 최종 JSON을 검사해 별도 최종 artifact에 복사하고,
나중에 다시 읽어 두 완료 보고서를 확인했습니다. 별도 atomic-replace probe도
통과했습니다. 원래 불일치의 원인은 확립되지 않았습니다.

위 코드 revision에서 원격
[CI 38727103372](https://github.com/fieldalgo/openphysics/actions/runs/38727103372)는
source 시험 498개(skip 0, subtest 아홉 개)를 통과하고 sdist→wheel 배포 일곱 개를
build·검증했으며 설치 wheel 시험 28개와 Node 시험 여덟 개를 통과했습니다. CI의
고정 환경을 사용한 검사입니다. 반면 후임의 로컬 루트 suite는 통과 480개·실패 아홉 개·skip 아홉 개로 보고했습니다. 실패 일곱 개와 skip 일곱 개에는 사용할 수 없는 Gmsh가
필요했고, skip 두 개에는 없는 RII DB가 필요했으며, CLI subprocess 두 개는 설치되지
않은 소스 패키지를 import하지 못했습니다. 이 로컬 결과는 전체 통과가 아닙니다.
twine/Gmsh가 없어 로컬 배포 검증은 실행하지 않았고 의존성도 설치하지 않았습니다.
benchmark 전용 코드 revision에서 package/build/CI 입력은 변경하지 않았습니다.

## 권고와 남은 분석

인계 profile에 따르면 희소 factorization이 향후 첫 조사 **후보**입니다. 먼저 원래
profile call tree, 행렬 차원·nonzero 수, factorization 준비와 반복 solve를 검토합니다.
그 뒤 같은 작업량·통제된 머신에서 적절히 전처리한 반복 shifted solve와 희소 직접
factorization을 비교합니다. cavity 연산자에는 gradient nullspace가 있고 shifted
system은 양의 정부호가 아닐 수 있으므로 conjugate gradients나 일반적인 preconditioner가
적용된다고 가정하면 안 됩니다. 이후 방법은 시간 개선을 수용하기 전에 독립 잔차,
nullspace 제외, 직교성, 퇴화 부분공간과 수렴 검사를 만족해야 합니다. 여기서는 반복
solver나 preconditioner를 구현하지 않습니다.

n=16 factorization 보고는 점근 scaling이나 메모리 사용 주체를 확립하지 않습니다.
추세 fitting이나 작업량 확장 전에 여덟 조건과 원시 표본을 모두 회수해야 합니다.
import·프로세스 overhead와 solver wall time을 분리하고 lifetime RSS를 factorization
증분 메모리라고 부르지 마십시오. 작은 mesh profile은 metadata를 검증하지만 n=16
병목을 확인하지는 않습니다. profiling을 분리하고 후속 작업에서 단계별 메모리 귀속을
확립합니다.

원래 원시 결과는 승인된 비공개 채널로 전달해야 하는 외부 records로 남아 있습니다.
그 전달 전에는 최종 기준선 분석이 미완료입니다. 원래 데이터를 회수할 수 없고 통제된
성능 환경이 명시적으로 확보된 경우가 아니라면 새 전체 run은 불필요합니다.
