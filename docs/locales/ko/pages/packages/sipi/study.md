# 임피던스 공차 분석

[English](../../../../../packages/sipi/study.md) | **한국어**

[개요](overview.md) · [임피던스 역산](design.md)

`sipi.study.ImpedanceStudyDocument`는 템플릿의 명시 변수를 샘플링해 단일선 또는
대칭 차동 임피던스를 계산합니다. sweep·corners·독립 균등분포·상관 정규분포를
지원하며 실패 표본을 삭제하거나 다시 추출해 통계를 만들지 않습니다.

```python
from sipi.study import ImpedanceStudyDocument

plan = ImpedanceStudyDocument('coupled_microstrip',
    dict(width=.4e-3, gap=.3e-3, substrate_height=.5e-3, eps_r=4,
         thickness=0, air_height=1e-3, box_width=4e-3),
    sampling=dict(kind='sweep', count=3,
                  variables=[dict(name='width', lower=.35e-3, upper=.45e-3)]),
    quantity='z_diff', fixed_pitch_m=.7e-3,
    mesh=dict(edge_size=.1e-3, far_size=.4e-3, grade=.3))
restored = ImpedanceStudyDocument.loads(plan.dumps())
result = restored.analyze()
```

각 행은 선폭·계산한 간격·저장 단면·Zdiff 또는 오류를 보존합니다.

## 입력 저장·샘플링 계약

strict `sipi.impedance-study/1`의 필드는 정확히 `schema`, `template`,
`parameters`, `sampling`, `quantity`, `mesh`, `fixed_pitch_m`입니다.
`from_dict`, `loads`, `to_dict`, `dumps`로 검사·복사·저장합니다.
미등록/누락 필드, JSON 중복 키, NaN/Infinity, bool 수치와 잘못된 형상을 거부합니다.
템플릿은 `microstrip`, `stripline`, `coupled_microstrip`, `grounded_coplanar`,
`coated_microstrip`입니다. 기존 SI 입력을 따르며 모든 템플릿 기본값과 nominal에서
해결한 메시 설정을 저장합니다. 자동 크기의 `None`은 기존 템플릿 규칙을 유지하므로
다른 치수가 바뀌면 상자 크기도 바뀔 수 있습니다. 고정하려면 공기·상자 치수를
명시하세요.

`quantity`는 `coupled_microstrip`에서 `z_diff`, 나머지에서는 `z0`입니다.
독립 변수는 템플릿 매개변수 이름 1–8개를 중복 없이 지정하고 나열 순서를 유지합니다.

| `sampling.kind` | `kind` 외 필수 필드 | 변수 필드 |
|---|---|---|
| `sweep` | `variables`, `count` | `name`, `lower`, `upper`; 변수 하나 |
| `corners` | `variables` | `name`, `lower`, `upper`; 2^D개 모든 모서리 |
| `uniform` | `variables`, `count`, `seed` | `name`, `lower`, `upper`; 독립 균등분포 |
| `normal` | `variables`, `count`, `seed`, `correlation` | `name`, `mean`, `std`; std > 0 |

경계는 유한하며 lower < upper입니다. 유한 범위의 모든 모서리 형상을 메시 전에
검사합니다. count는 정수 2–10000, seed는 정수 0–2^32-1입니다.
NumPy `Generator(PCG64(seed))`를 사용합니다. 정규분포는 **비유계**이며 clipping,
거부 재추출·절단을 하지 않습니다. 물리적으로 잘못된 평균/표본은 해석 시 오류 행으로
남깁니다.

상관행렬은 유한 D×D 대칭 양의 준정부호이며 대각이 1입니다. 대칭·대각·원소범위·
음의 고윳값 roundoff 허용은 절대 1e-12이고 비대칭 roundoff는 평균합니다.
허용된 [-1e-12,0] 고윳값만 대칭 제곱근 계산에서 0으로 놓습니다.
더 큰 음의 고윳값은 거부합니다. 완전 상관/역상관도 지원합니다.
표본은 `mean + (standard_normal @ sqrt(correlation).T) * std`입니다.
분포의 상관을 지정하는 것이며 유한 표본의 경험적 상관이 정확히 같지는 않습니다.
결과와 함께 엔진·NumPy 버전을 기록하세요. seed만으로 버전 간 bitwise 동일을
보장하지 않습니다.

`samples()`는 독립 변수 순서의 읽기 전용 `(count,D)` 복사 배열,
`sample_parameters()`는 파생값을 포함한 전체 템플릿 인수의 새 맵 목록입니다.
이 두 메서드는 FEM을 실행하지 않습니다.

## 고정 피치

`fixed_pitch_m`은 `None` 또는 coupled_microstrip의 양의 중심 간 거리입니다.
독립 변수에 width가 있어야 하고 gap을 독립적으로 샘플링할 수 없습니다.
nominal width+gap이 pitch와 상대 1e-12 이내로 같아야 합니다.
각 행의 `gap=pitch-width`로 두 선의 중심 위치를 유지합니다. 사다리꼴은 기존
템플릿의 바닥 선폭을 기준으로 합니다. 유한 범위 모서리에서 gap<=0이면 생성 시
거부하고, 정규 표본에서 발생하면 오류 행으로 보존합니다. 통계 상관 매개변수가
아니라 결정적 형상 제약입니다.

## 계산·실패·통계

`analyze(max_evaluations=128)`은 정수 2–10000의 명시 계산 예산을 첫 해석 전에
검사합니다. 계획 표본 수가 더 크면 `ValueError`이며 표본 수를 조용히 줄이지
않습니다. 행마다 저장된 nominal 설정으로 별도 형상 메시를 만듭니다.
`ImpedanceStudy`는 `input_json`, `quantity`, 불변 `rows`, `failed`, `summary`를
보존합니다. `StudyRow`에는 index·읽기 전용 parameters·생성 성공 시 저장된
CrossSectionDocument·임피던스 Ω 또는 None·error_type/error가 있습니다.
해석 실패에도 정상 입력 문서를 보존하고 형상 생성 실패는 문서가 없습니다.
인터럽트를 성공 행으로 바꾸지 않습니다.

하나라도 실패하면 `summary=None`입니다. 모두 성공하면 표본 최소·최대·평균,
표본 표준편차(ddof=1), 5/95백분위(NumPy linear 보간)를 읽기 전용 맵으로
반환합니다. sweep/corners의 통계는 확률분포가 아닌 기술 통계입니다.
표본 극값·분위수는 **보증 제조 공차·수율·연속 영역 최악값이 아닙니다**.

각 행의 자동 메시 세분 검사는 없습니다. 작은 임피던스 차이에 의존하기 전에
관련 형상별 메시·외곽 수렴을 확인하세요. 기존 준정적 단면에 도체 손실·주파수
네트워크·비선형 재료·full-wave 물리를 추가하지 않습니다. JSON은 입력 계약이며
새 결과 저장 스키마가 아닙니다. UI/CLI 연결은 Python API와 별개입니다.

## 검증

```sh
OPENBLAS_NUM_THREADS=1 python -m pytest -q tests/sipi/test_study.py
python examples/sipi/tolerance_study.py
```

sweep/corners 끝점·순서, uniform 범위, seed/JSON 재현을 검사합니다.
고정 피치 상대 1e-12, 완전 역상관 정규화 절대 차이 1e-12를 요구합니다.
상관 정규분포 10000개에서 각 표준화 평균 오차 <=6/sqrt(N), 정규화 공분산과
목표 상관행렬의 최대 절대 차이 <=0.08입니다. 독립 scipy.stats.multivariate_normal
표본도 같은 해석 moment 기준을 적용하고, 두 표본 집합 모두 각 주변분포의
정규 CDF KS 통계량 <0.03을 요구합니다. 통계 검증이며 재료 물리 검증이 아닙니다.

실제 단일선·차동 각각 두 점의 FEM 결과는 저장 입력 직접 해석과 상대 1e-10
이내입니다. 조합·재현 검증이며 독립 정확도 주장과 구분합니다. invalid normal
형상의 무재추출 보존, 해석 오류, budget, 잘못된 JSON·상관/shape/seed도 검사합니다.
기존 단면 해석 기준과 수렴 한계를 유지합니다.
[실행 예제](../../../../../../examples/sipi/tolerance_study.py).
