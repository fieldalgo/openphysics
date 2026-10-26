# 첫 열탄성 해석: 열전도에서 역학으로

[English](../../../../../packages/galerkin/thermoelastic_tutorial.md) | **한국어**

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

## 1. 열 조건과 기계 조건 구분하기

[예제](../../../../../../examples/galerkin/thermal_mechanical_workflow.py)는
1 m × 1 m 직사각형의 왼쪽을 303.15 K, 오른쪽을 323.15 K로 고정하고 나머지는 단열합니다.
열전도율은 10 W/(m K)입니다. 역학에서는 E=70 GPa, nu=0.3, 선팽창계수 alpha=12e-6 /K,
무응력 기준 온도 293.15 K를 사용하며 **평면 변형률** 모델을 선택합니다.

온도 고정은 변위 고정이 아닙니다. 기계 구속 맵은 `{(0,0):0., (0,1):0., (n,1):0.}`으로,
노드 0의 x·y 변위와 노드 n의 y 변위를 고정합니다. 이 구조화 메시에서 노드 0은 왼쪽 아래,
노드 n은 오른쪽 아래 모서리입니다. 세 개의 스칼라 구속으로 면내 병진과 회전을 제거합니다.
임의의 메시에서 이 ID를 그대로 사용하지 말고 의도한 물리 위치와 성분을 선택하세요.
나머지 기계 경계의 전체 열탄성 자연 traction은 0입니다.

## 2. 두 단계 실행하기

```sh
python examples/galerkin/thermal_mechanical_workflow.py
```

터미널에 출력되는 JSON에는 다음 항목이 있습니다.

| 필드 | 대략적인 결과 | 해석 |
|---|---|---|
| `temperature_range_k` | [303.15, 323.15] | 역학으로 전달한 정상 온도장 |
| `net_outward_heat_w_per_m` | 약 1e-13로 0에 가까움 | source가 없어 순유출은 0이지만 내부에는 열이 흐름 |
| `max_displacement_m` | 4.8693e-4 | 이 메시·모델·구속에서 약 0.487 mm |
| `sigma_zz_range_pa` | [−2.4641e7, −8.9588e6] | 평면 변형률에서는 면외 응력이 일반적으로 0이 아님 |
| `physical_elastic_energy_j_per_m` | 2206.0 | 돌출 깊이당 물리적 탄성 에너지 |
| `stages` | heat, mechanics, transfer completed | 요청한 단계가 모두 완료됨 |
| `authentication` | `not_certified` | 외부 입력이나 물리 정확도를 인증한다는 뜻이 아님 |

기준 온도는 열변형률 `alpha*(T-Tref)`에 들어갑니다. 열 경계값에서 미리 빼는 값이 아니며,
열 솔버에는 절대 온도 K를 전달합니다. 평면 변형률은 면외 변형률이 0이라는 조건이지
면외 응력이 0이라는 조건이 아닙니다. 3차원 구성법칙 감소와 에너지 정의는
[기계단계 계약](prescribed_temperature_thermoelasticity.md)을 읽으세요.

## 3. 매개변수와 해석 확인하기

스크립트를 `packages/` 밖의 로컬 작업 파일로 복사하고 한 번에 한 항목씩 바꾸세요.

- `thermal_expansion_per_k=0.`으로 설정합니다. 예제처럼 변위 구속이 0이고 체적력이
  없으면 변위·응력·탄성 에너지가 0이 되며 열 결과는 그대로입니다.
- 다른 입력을 유지한 채 alpha를 `24e-6`으로 두 배 늘립니다. 이 선형 문제에서는 변위와
  응력이 두 배, 탄성 에너지가 네 배입니다. 일관성 검사에는 유용하지만 구성법칙의 독립 검증은 아닙니다.
- `n`을 8에서 16, 32로 늘립니다. 구속 맵에도 `n`을 유지해 두 번째 지지점이 오른쪽 아래
  모서리에 남게 하세요. 변하지 않는 양 끝 온도만 보지 말고 변위·응력·에너지를 비교합니다.
  이 예제는 수용 허용치를 지정하거나 응력장이 수렴했다고 주장하지 않습니다.

## 4. 연계 범위 이해하기

열을 먼저 풀고 같은 격리된 기준 메시에서 노드 온도를 역학으로 전달합니다.
기계 변형이 열 문제의 메시를 바꾸거나 온도로 되먹임되지 않습니다. 정상·소변형률·단방향
계산이며 구조 동역학이 아닙니다. Python 전용이고 JSON/CLI나 Studio 양식은 없습니다.
별도 열유속·Robin 확장과 기계 traction 확장을 이 정상 workflow의 인자로 넣을 수는 없습니다.

정확한 단위·검사·출처 정보는 [workflow 계약](thermal_mechanical_workflow.md)과
[독립 수용 검증](thermal_mechanical_independent_validation.md)을 읽으세요.
저장된 과도 열 시간 중 일부에서 준정적 역학을 풀려면 별도의
[과도 열→역학 workflow](transient_thermal_mechanical.md)를 사용합니다.
