# 세 기저의 원거리 로그 상호 작용

`galerkin.laplace_corner_quadratic_far`의 `power_panel_quadratic_far_log`는
[세 방사형 자기 기저](laplace_corner_quadratic.md)에 대한 원거리 적분입니다.
기저는 rho_p, sqrt(3)*(rho_2p-rho_p),
sqrt(5)*(2rho_3p-3rho_2p+rho_p)이며 rho_a(s)=a/h*(s/h)^(a-1)입니다.
물리 질량은 [1,0,0]입니다.

```python
from galerkin.laplace_corner_quadratic_far import power_panel_quadratic_far_log
result = power_panel_quadratic_far_log(
    [1., 0.], [.3, .4], [8., 2.], .6, .875, quadrature_order=32)
assert result.mean_log_distance.shape == (3, 3)
```

첫 선분은 원점, 둘째 선분은 `offset`에서 시작합니다. 세 벡터는 평면의
미터 단위입니다. 두 지수는 (0.5,1], 길이비는 64 이하이며 offset의 크기는
두 선분 길이 합의 네 배 이상이어야 합니다. 내부 기하 정규화는 물리 측도를
바꾸지 않습니다. 결과는 log(|x-y| / 1 metre)의 무차원 적분이며 기저 순서의
읽기 전용 3x3 배열입니다. 전체 길이의 lambda 배율은00항에만 log(lambda)를
더합니다.

n=4..64의 명시적 n/2n 물리 Jacobi 구적을 사용합니다. 가중치를 재정규화하거나
자동 재시도하지 않습니다. 물리 질량 잔차는1e-12 이하이며 coarse/fine의
각 항은1e-12*max(1,abs(fine)) 이내여야 합니다. 이는 정규화된 원시 적분
기준이며 작은 항의 상대 정확도나 장 오차 상한이 아닙니다. 두 결과의 왼쪽
위2x2 블록은 기존 harmonic 적분과 정확히 같습니다. 새 영 질량 항은
log1p 중심화를 사용합니다.

독립 기준8개는 해석적 밀도 모멘트를 사용한 복소 Taylor100항 전개를
70/100자리에서 계산합니다. rho=(|first|+|second|)/|offset|<=1/4일 때 생략한
스칼라 기여의 상한은5*rho^101/(101*(1-rho))이며 반올림 오차는 별개입니다.
생성기는 제품 모듈을 불러오지 않고 저장값과 비교만 합니다. 기준 파일을
보존하고 임시 출력을 정리합니다. 독립 기준·기존 부분공간·교환 전치·반사·
회전·물리 배율을 검증합니다. 등록한 원거리 사례의 낮은 차수도 수렴했으므로,
거절·재시도 없음 검사는 명시적인 오류 주입이며 실제 구적 실패로 보고하지
않습니다. 물리 가중치 손상도 거부합니다.

근접·접촉·균일 혼합 적분, 행렬 조립, 장 해, 고정 접지 또는 다른 플랫폼을
추가로 수락하지 않습니다. 소비자가 완성된 고차 방법을 사용하려면 독립
장 기준과 수렴 검증이 더 필요합니다.

[English](../../../../../packages/galerkin/laplace_corner_quadratic_far.md)
