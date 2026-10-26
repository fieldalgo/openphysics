# 첫 열전도 해석: 온도가 다른 두 면 사이의 슬래브

[English](../../../../../packages/galerkin/thermal_tutorial.md) | **한국어**

기존 Python 예제를 실행하고 물리 결과를 해석한 뒤 입력을 하나씩 바꿔봅니다.
엔진을 직접 사용하므로 Studio나 plotting extra는 필요하지 않습니다.

## 시작 전

Python 3.12 이상과 활성화한 가상환경을 사용하세요. 저장소 루트에서 이 튜토리얼에
필요한 두 로컬 패키지를 설치합니다.

```sh
python -m pip install -e packages/galerkin -e packages/galerkin-refsol
```

저장소·환경 준비는 [도구 개요](../../overview.md)를 따르세요. 명령은 `packages/` 안이
아닌 저장소 루트에서 실행합니다. 이 예제들은 터미널에 출력하며 그림이나 결과 파일을 저장하지 않습니다.

## 1. 문제 설정

2 m × 0.7 m 직사각형의 왼쪽은 350 K, 오른쪽은 300 K로 고정하고 위·아래는 단열합니다.
열전도율은 12 W/(m K)이며 내부 발열은 없습니다. 시간 이력이 아니라 정상 온도와
열유속을 구하는 문제입니다. 이 Python 엔진에 전달하는 좌표는 m, 온도는 K입니다.

[기존 예제](../../../../../../examples/galerkin/thermal_steady2d.py)는
`rectangle_mesh(2., .7, 8, 5)`로 8 × 5개 격자 셀을 만들고 각 셀을 P1 삼각형 두 개로 나눕니다.
실제 왼쪽·오른쪽 경계 노드 ID를 `dirichlet`에 넣으며, 지정하지 않은 자연 경계는 단열입니다.
`solve_steady_heat`는 노드 온도와 삼각형마다 일정한 열유속 벡터를 반환합니다.

## 2. 실행과 결과 해석

```sh
python examples/galerkin/thermal_steady2d.py
```

다음 물리량이 출력됩니다. 반올림 오차 수준의 값은 실행 환경에 따라 달라질 수 있습니다.

| 출력 항목 | 예상 크기 | 의미 |
|---|---|---|
| Maximum temperature error | 약 1e-13 K | 독립 기준해 `refsol.thermal.slab`과의 비교 |
| Mean heat flux | [300, 0] W/m² | 뜨거운 왼쪽에서 차가운 오른쪽, +x 방향으로 흐르는 열 |
| Left/right heat input | +210, −210 W/m | 양의 reaction은 열 유입, 음의 reaction은 열 유출 |
| Heat imbalance | 약 1e-12 W/m 이하 | 내부 source load와 경계 reaction의 합 |

균질 슬래브의 독립 정답은 `T(x) = 350 - 25*x` K이며,
`q_x = -k*dT/dx = 300` W/m²입니다. 높이 0.7 m인 면에서 적분하면 돌출 깊이당
210 W/m입니다. 실제 깊이가 0.01 m라면 전달되는 열은 **2.1 W**입니다.
깊이는 결과에 명시적으로 곱하며, 솔버가 암묵적으로 적용하는 매개변수가 아닙니다.

## 3. 입력 하나씩 바꾸기

예제를 `packages/` 밖의 작업 위치에 복사한 뒤 한 번에 한 항목씩 바꾸세요.
복사본과 출력은 로컬 실험이며 저장소에 포함된 검증 근거가 아닙니다.

- 두 경계를 모두 300 K로 설정하고 기준해 호출의 `left_temperature`도 바꿉니다.
  source가 없으므로 온도는 일정하고 열유속은 0입니다.
- 솔버와 기준해 호출의 열전도율을 모두 12에서 24로 바꿉니다.
  온도는 같고 열유속은 600 W/m², reaction은 ±420 W/m가 됩니다.
- `rectangle_mesh`의 분할을 `(8, 5)`에서 `(16, 10)`으로 늘립니다. 정확한 온도장이
  선형이라 이미 P1 요소로 표현되므로 오차는 여전히 반올림 수준입니다.
  부호·단위 확인에 유용하지만 일반적인 수렴 차수를 측정하는 문제는 아닙니다.

기준해에 이전 입력을 남겨두면 서로 다른 물리 문제를 비교하게 됩니다.
이 예제를 수정할 때는 솔버와 기준해 호출의 조건을 함께 바꾸세요.

## 4. 검증 범위 이해하기

전체 에너지 보존이 국소 열유속 정확도를 증명하지는 않습니다. 불균일 source, 재료 경계,
곡선 형상에는 별도 해상도 검사가 필요합니다. 경계 reaction은 적분된 약형 물리량(W/m)이며
열유속 밀도(W/m²)가 아닙니다.

[열전도 계약](thermal_steady2d.md), [열유속·대류](thermal_flux_robin.md),
[독립 수용 검증](thermal_independent_validation.md)을 이어 읽으세요.
JSON/CLI를 사용하려면 별도 [열 모델 문서](../simcase/thermal_steady2d.md)를 따릅니다.
다음 실습은 [전기로 발열시키기](joule_tutorial.md) 또는
[온도를 역학으로 전달하기](thermoelastic_tutorial.md)입니다.

다음 실습: [과도 열전도 튜토리얼: 입력 에너지는 어디에 저장될까?](transient_tutorial.md).
