# 두 재료 벽 만들기: 모델부터 열 흐름 확인까지

[English](../../../../../packages/simcase/layered_wall_tutorial.md) | **한국어**

[문서 홈](../../index.md)

형상·재료 영역·메시·대류 경계·저장 결과를 연결하는 실습입니다. 계수는 설명용이며
특정 제품의 인증된 물성이 아닙니다. 엔진이 처음이라면
[첫 열전도 해석](../galerkin/thermal_tutorial.md)을 먼저 읽으세요.

## 1. 모델 실행기 설치

Python 3.12 이상과 활성화한 가상환경에서 저장소 루트를 기준으로 실행합니다.
로컬 의존 패키지를 함께 설치하며, extra는 선택적 내보내기에 필요한 meshio를 제공합니다.

```sh
python -m pip install -e packages/galerkin -e packages/meshine -e packages/physmat -e 'packages/simcase[export]'
python -m simcase validate examples/simcase/layered_wall.json
python examples/simcase/layered_wall.py out/wall-base --export
```

출력 폴더는 새 폴더 또는 빈 폴더여야 합니다. 스크립트는 한 번 해석하고 결과를 저장한 뒤
`view.vtu`를 만듭니다. `--export`를 생략하면 meshio가 필요하지 않습니다.
`out/` 아래 출력은 로컬 생성물이며 새 clone에 포함된 검증 근거가 아닙니다.
이 파일은 저장소 튜토리얼 입력이며 `simcase example`에 등록된 이름은 아닙니다.

## 2. 물리적 순서로 모델 읽기

[layered_wall.json](../../../../../../examples/simcase/layered_wall.json)을 여세요.

| 구성 | 의미 |
|---|---|
| 영역 전체 | 폭 40 mm, 높이 10 mm |
| `background` 영역 | 재료 `low_k`, k=1 W/(m K) |
| `left_layer` 도형 | 왼쪽 10 mm 폭, 재료 `high_k`, k=10 W/(m K) |
| 왼쪽 경계 | 350 K로 온도 고정 |
| 오른쪽 경계 | h=50 W/(m² K), 주위 온도 300 K인 대류 |
| 위·아래 경계 | 지정하지 않은 자연 경계이므로 단열 |
| 메시 | 목표 크기 2 mm, 요청 최소각 28도 |

**영역 이름**은 형상, **재료 이름**은 물성 레코드를 가리킵니다. 여러 영역이 같은 재료를
사용할 수 있습니다. source 맵의 키는 `high_k` 같은 재료 이름이 아니라 `left_layer` 같은
영역 이름입니다. 형상·메시 크기는 `units.length`를 따르지만 `_w_mk`, `_w_m3`, `_w_m2k`,
`_k`로 끝나는 물성은 SI 단위를 유지합니다. 실행기가 열 엔진으로 m 좌표를 전달하므로
문서의 일부만 수동으로 단위 변환하지 마세요.

뒤에 나오는 도형이 앞선 도형과 겹치는 부분을 대체합니다. 배경은 남는 영역을 채우고
메시 모서리는 재료 경계를 따릅니다. 완전히 덮인 도형은 메시에서 사라질 수 있으므로
그림뿐 아니라 log와 summary도 확인하세요. 두 층은 접촉 열저항 없는 완전 열접촉을 가정합니다.

## 3. 그림을 믿기 전에 예상값 확인

내부 source가 없고 위·아래가 단열이므로 직렬 열저항으로 계산할 수 있습니다.

```text
R_per_area = 0.01/10 + 0.03/1 + 1/50 = 0.051 m² K/W
q_x = (350-300)/R_per_area = 980.392157 W/m²
T_interface = 350 - q_x*(0.01/10) = 349.019608 K
T_right = 300 + q_x/50 = 319.607843 K
heat_per_depth = q_x*0.01 = 9.803922 W/m
```

스크립트는 약 319.607843–350 K의 온도 범위와 각각 약 9.803922 W/m인 온도 고정 경계
유입·대류 유출을 출력합니다. 돌출 깊이가 1 mm라면 0.009803922 W입니다.
삼각형 개수는 달라질 수 있으며 수용 기준값이 아닙니다.

정확한 온도장은 구간별 선형이며 재료 경계에 정렬된 P1 메시로 표현됩니다.
이 일치는 재료 배정·단위·부호·Robin 조립을 확인하지만 일반 형상·source·접촉 모델의
수렴을 증명하지는 않습니다.

## 4. 설계 조건 하나씩 바꾸기

JSON을 로컬 파일로 복사하고 그 파일에 대해 `python -m simcase validate`와
`python -m simcase run <your-file.json> -o <new-output>`을 실행하세요.
보조 스크립트는 항상 자신의 옆에 있는 저장소 JSON을 읽으며 사용자의 복사본은 읽지 않습니다.

- `low_k`를 1에서 2 W/(m K)로 바꿉니다. 직렬 열저항부터 다시 계산하면 열유량이
  증가할 것으로 예상할 수 있습니다. 다른 입력은 물리적으로 바꾸려는 경우에만 수정하세요.
- `left_layer.w`를 10에서 15 mm로 바꿔 경계를 이동합니다. 두 층 두께는 0.015와
  0.025 m이며 전체 폭은 여전히 40 mm입니다.
- physics 객체에 `heat_source_w_m3: {"left_layer": 200000}`를 넣습니다.
  source가 없는 위 정답은 더 이상 적용되지 않습니다. source 유입·온도 고정 경계 reaction·
  대류 유출을 비교한 뒤 메시 세분화를 수행하세요.

원래 입력에서 메시만 바꾸려면 다음을 실행합니다.

```sh
python examples/simcase/layered_wall.py out/wall-fine --mesh-size-mm 1 --export
```

각 실행 폴더를 분리해서 보존하세요. 다음으로 [저장 결과와 ParaView](../../results/saved-results.md),
[수렴 확인](../../validation/convergence.md)을 읽습니다. 이 영역·대류 모델은 JSON/CLI/Python
경로이며 thermal Studio 모델이 아닙니다. 정확한 도형·배정·지원 한계는
[영역 문서 계약](thermal_regions2d.md)을 따릅니다.
