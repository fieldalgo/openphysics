# 흡수 도파관 모드

[English](../../../../../packages/simcase/lossy_modes.md) | **한국어**

`em.modes2d`는 scalar·full-vector 유한 계산창 모드에서 수동 복소 등방성
유전율을 받습니다. Scalar는 TE slab 방정식에서는 정확하지만 일반적인
고대비 2D 구조나 표면 플라즈몬의 정확한 모델은 아닙니다. 그런 경우에는
full-vector를 사용하세요. PML·방사/누설 손실·굽힘·이득 매질·예외점 추적은
지원 범위 밖입니다.

## 부호·입력·단위

기존 장 규약 `exp(+i omega t-i beta z)`, `beta=(2*pi/lambda0)*n_eff`를
유지합니다. +z 수동 감쇠는 **Im n_eff < 0**입니다.
저수준 `galerkin.solve_modes`의 `eps_r`와
`simcase.physics_em_modes2d.solve`의 `eps_tri`도 이 규약으로 입력하므로
손실 유전율의 허수부는 음수입니다. JSON/physmat의 재료는 양의 소멸계수
`n+ik`를 사용하며 문서 runner가 해석기 경계에서 유전율을 켤레 변환합니다.
문서 재료를 사용자가 다시 켤레 변환하지 마세요.

beta의 단위가 1/m일 때 진폭은 `exp(-a*z)`, `a=-Im beta`로 감소하고,
전력은 `exp(-alpha*z)`, `alpha=2*a`로 감소합니다.
`loss_dB_cm=10*alpha/(100*ln(10))`이며 양수는 감쇠입니다.
`RunResult.propagation_loss_db_cm()`이 파장을 SI로 변환합니다.
굴절률은 무차원이며 장은 상대 진폭으로, V/m 또는 단위 전력이 아닙니다.

## Python·JSON

```python
import copy
from simcase import Document, examples, run

data = copy.deepcopy(examples.VECTOR_SLAB)
data["materials"]["film"] = {"n": 3.48, "k": 0.01}
data["study"] = {"type": "single"}
result = run(Document.from_dict(data), verbose=False)
print(result.neff)
print(result.propagation_loss_db_cm())
result.save("absorbing_slab")
```

Python/NPZ의 `neff`, scalar `fields`, vector 장 배열은 복소수를 유지합니다.
복소 결과 JSON은 `mode_result_schema: "openphysics.modes2d/2"`와 `phasor`를
명시하고, 기존 숫자 배열 `neff`를 **실수부**로 유지하면서 같은 모양의
`neff_imag`·`propagation_loss_db_cm`를 추가합니다. 복소 군지수도
`group_index`·`group_index_imag`로 분리합니다. 입력 문서 버전과 기존
무손실 숫자 출력은 유지합니다.

Studio는 모드별 Re n_eff·Im n_eff·dB/cm를 표시합니다. Scalar 장 화면은
크기이며 응답의 `scalar_fields_complex`가 실수부·허수부 절점장을 보존합니다.
Vector 성분은 기존 복소 인코딩을 유지합니다.

## 선택·정규화·추적

기본 vector 유전체 검색은 `n_cladding < Re n_eff < sqrt(max Re epsilon)`
범위에서 Re n_eff 내림차순입니다. 구속이나 검색 완전성의 증명은 아닙니다.
Re epsilon이 양수가 아닌 매질은 physics에 양의 실수 `n_target`을 명시합니다.
목표에 가까운 후보를 선택한 후 Re n_eff 순으로 정렬하며 유전체 상한을
적용하지 않습니다. Vector 문서는 `n_cladding`도 계속 필요합니다.
저수준 `galerkin.solve_modes`는 복소 목표값도 받습니다. 메시와 계산창을
각각 수렴시켜야 하며 자동 손실 상한 필터는 없습니다.

Scalar는 최대 계수를 1로, vector는 최대 중심점 |E|를 1로 정규화합니다.
저수준 물리장 `Ez=i*ez`와 성분 비율을 유지하고 전체 위상은 임의입니다.
가까운 고유장을 섞어 직교 고유기저를 만들지 않습니다.

분리된 vector sweep과 흡수 scalar 파장 sweep은 고정 메시의 양의 켤레
electric/scalar L2 겹침, 할당·겹침/여유·복소 고유값 거리 검사를 사용합니다.
전력 직교성이나 좌우 고유벡터 쌍대성은 아닙니다. 흡수 scalar sweep은
엄격히 단조인 파장 3개 이상과 기본 할당 설정을 사용하며 JSON에서 추적
설정을 변경하는 기능은 아직 없습니다. 기존 무손실 scalar는 순위 정렬을
유지합니다.

복소 `n_g=n_eff-lambda0*d(n_eff)/d(lambda0)`는 스펙트럼 미분이며 에너지·신호
속도가 아닙니다. 파장 간격 수렴을 확인하세요. 추적하지 않은 복소 sweep은
군지수를 제공하지 않습니다. 실수 스펙트럼을 가정하는
`electric-l2-subspace-v1`은 흡수 재료를 명시적으로 거절합니다. 분리 모드나
단일 해석을 사용하세요. 축퇴 근처·겹침 실패·불완전 검색은 오류로 보고합니다.

## 검증·한계

`tests/simcase/test_lossy_modes.py`는 독립 복소 slab 분산식과 scalar TE·vector
TE/TM의 세 메시를 비교하고 약손실·무손실 극한, 잔차, 복소 저장장과 손실
단위를 검사합니다. 금속 계면은 full-vector와
`n_eff=sqrt(epsilon_m*epsilon_d/(epsilon_m+epsilon_d))`를 비교합니다.
scikit-fem 비교는 독립 조립·밀집 QZ와 제품 희소 해법을 비교합니다.
도구 간 일치는 수렴 증명이 아니며 특정 사례의 수용은 보편적 오차 보장이
아닙니다. [비교 계약](../../reference-comparisons.md)을 참고하세요.
통합 전 필수 CI는 별도로 필요합니다.
