# 전송선 네트워크 검증

[English](../../../../../packages/sipi/network_validation.md) | **한국어**

[계약](network.md)

판정 기준은 구현 전에 정했습니다. 입력 RLGC의 전파 변환을 검증하며, 도체·재료 추출이나 FEM
정확도 검증을 대체하지 않습니다. 기존 단면의 정확도·메시 수렴 기준은 그대로입니다.

| 시험 | 기준 |
|---|---|
| 정합 무손실 선로·음의 전파 위상·DC 직렬 R·길이 0 | S 절대 오차 <=1e-10 |
| 스칼라 손실/부정합 선로와 독립 ABCD 식 | S 절대 오차 <=1e-10 |
| 무손실 유니터리·상호성·수동 특이값 | 오차/초과 <=1e-10 |
| 대칭 결합선과 독립 odd/even ABCD | S 절대 오차 <=1e-10 |
| 교환하지 않는 비대칭 2도체 행렬·비결합 3도체 포트 연결 | 같은 항등식과 절대 1e-10 |
| 정합 alpha*length=4000 | 유한 출력, S 절대값 <=1e-10 |
| scikit-rf DistributedCircuit 단일선·odd/even·se2gmm | S 절대 차이 <=1e-10 |
| Touchstone 2.0 독립 읽기, 의도적 비상호 2/4포트 데이터 | 절대 1e-14·주파수 완전 일치 |

`tests/sipi/test_line_network.py`는 해석식·실제 손실 stripline 연결·입력 거부·snapshot을 검사합니다.
`tests/sipi/test_crosscheck_skrf_network.py`는 `sipi[test]`의 scikit-rf **2.2.0**을 시험 시에만
불러옵니다. 필수 CI에서는 없으면 실패합니다. SIPI가 import하거나 번들하지 않습니다.
[라이선스 목록](../../third-party.md)에 정확 버전·소스 라이선스·시험 전용 의존성을 기록합니다.

로컬 Linux 관측(2026-10-30): Python3.12.14, NumPy2.5.4, SciPy1.18.1, scikit-rf2.2.0,
pandas3.0.3. 네트워크 36시험 통과. 최대 차이: 단일선 S 1.53e-11, odd/even S 1.83e-14,
변환 2.49e-16. 분리된 기준 도구 환경은 수치 핀 변경 없이 wheel 설치 약2.2초·의존성 검사 통과.
import 포함 기준시험3개는 0.67초·최대RSS66.3MiB였습니다. 한 컴퓨터의 관측이며 보장값이 아닙니다.
기존 별도 개발 환경에는 `simcase`가 없어 그 환경의 의존성 검사를 통과로 보고하지 않습니다.

설정된 검증 환경에서 저장소 루트 기준 재현:

```bash
OPENPHYSICS_REQUIRE_CROSSCHECK=1 OPENBLAS_NUM_THREADS=1 \
  python -m pytest -q tests/sipi/test_line_network.py tests/sipi/test_crosscheck_skrf_network.py
```

crosscheck 기록은 동일 RLGC 입력의 알고리즘 대조와 해석적 판정을 구분합니다. 저장 기준값이나
golden 재생성은 없습니다. R/G=0인 DC는 기준 도구의 특성 임피던스 0/0을 피하고 해석식으로 검사합니다.
고주파 분산·전파 해석·표피 효과·거칠기·측정 쿠폰·브라우저·Windows 앱 검증을 뜻하지 않습니다.
