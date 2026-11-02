# 2D 정전기와 정전용량 행렬

[English original](../../../../../packages/galerkin/electrostatics.md)

## 정식화와 규약

`galerkin.electrostatics`는 m 단위의 적합 P1 삼각형 메시에서, 면 밖 축 방향
단위 길이당

```text
-div(eps0 eps_r grad V) = rho,   E = -grad V,   D = eps0 eps_r E
```

를 풉니다. 도체는 전위를 지정한 절점 집합입니다. 도체 위에 없는 외부 경계는
절연(`D.n = 0`, 자연 경계)입니다. 약한 형식은
`int eps0 eps_r grad V . grad phi_i = int rho phi_i`이며 강성행렬 `K`가 절대
유전율을 포함하므로 잔차 `K V - f`는 C/m 단위의 전하입니다. 규약:

- `eps_r`는 상대 유전율이며 유한하고 `Re > 0`입니다. 손실 유전체는
  `eps' (1 - j tan d)`로 `Im(eps_r) <= 0`입니다(`exp(+j omega t)` 규약,
  [sipi](../sipi/overview.md)와 동일). `Im > 0`은 거절합니다. 복소수는 NumPy
  경로에서만 받습니다.
- 도체 전하는 조립된 반력 `(K V - f)_i`를 도체 절점에서 합한 값입니다. 도체가
  양전하를 띠어 `D`가 도체에서 유전체로 향할 때 양수입니다. `rho = 0`이면 도체
  전하의 합은 0이고, 자유 전하가 있으면 합은 `-int rho`입니다.
- 단위 길이당 에너지는 `W = V^T K V / 2`(J/m)입니다. 공액을 취하지 않으므로
  `eps_r`에 대해 해석적이고 손실 유전체에서는 복소수입니다. 성분별 전위 오프셋을
  뺀 뒤 계산합니다. 접지에 대해 `U` V인 도체 하나면 `W = Q U / 2`입니다.
- 도체 절점은 메시 어디에나 둘 수 있습니다. 두께 0 트레이스는 내부 절점 선,
  실체 도체는 구멍의 경계입니다.

## API

```python
from galerkin import solve_electrostatics, capacitance_matrix, ElementPermittivity
```

`solve_electrostatics(mesh, *, permittivity, conductors, ground=None, charge_density=0.0, reference_potential=None)`

| 인자 | 의미 |
|---|---|
| `permittivity` | `eps_r`: 양의 스칼라, 정확한 `{region name: value}` 표([입력 규칙](multimaterial.md)) 또는 메시에 결합된 `ElementPermittivity(mesh, values)`(실수, 엄격히 양수, 같은 기하·순서·영역). 스칼라와 표 항목은 `Im <= 0`인 복소수일 수 있습니다. 원시 요소 배열은 거절합니다. |
| `conductors` | `{name: (node ids, volts)}` 절점 집합(`sipi` 방식) 또는 평범한 `{node: volts}` Dirichlet 사상. 후자는 전하를 절점 번호별로 보고합니다. 한 호출에 한 형식만 씁니다. 도체는 절점을 공유할 수 없고, 모든 절점은 존재해야 하며, 빈 집합은 거절합니다. |
| `ground` | 0 V로 고정하는 절점 번호. 도체 `"ground"`로 보고하며, `ground`를 준 경우 같은 이름의 사용자 도체는 거절합니다. |
| `charge_density` | 자유 전하 `rho`(C/m³): 스칼라, 영역 표 또는 삼각형 중심에서 평가하는 콜백 `(x, y) -> rho`(중심 규칙, 일관 P1 하중). |
| `reference_potential` | `{node: volts}`. 도체 절점이 없는 연결 성분마다 정확히 하나의 게이지. 그 성분의 순 자유 전하는 `sum(abs(load))` 대비 `1e-12` 이내로 0이어야 하며(게이지 추가 전에 검사), 도체가 있는 성분의 게이지는 거절합니다. 게이지는 전하를 공급하지 않고 `reaction`에 나타나지 않습니다. |

`ElectrostaticsResult` 필드(입력 메시 순서의 읽기 전용 스냅샷; 입력이 live이면
JAX·PyTorch 배열):

| 필드 | 모양 | 단위 / 의미 |
|---|---|---|
| `mesh` | `Mesh` | 입력 토폴로지·좌표·경계/영역 식별자의 복사본 |
| `potential` | `(N,)` | V, 게이지를 포함한 절점 P1 전위 |
| `electric_field` | `(M,2)` | V/m, 삼각형별 상수, `-grad V` |
| `displacement` | `(M,2)` | C/m², `eps0 eps_r E` |
| `relative_permittivity` | `(M,)` | 전개한 `eps_r` 표 |
| `energy_per_length` | 스칼라 | J/m, `V^T K V / 2` |
| `load` | `(N,)` | C/m, `int rho phi_i` |
| `reaction` | `(N,)` | C/m, 도체 절점의 `K V - f`; 그 밖과 게이지에서는 0 |
| `residual` | `(N,)` | C/m, 모든 절점의 `K V - f`, 오프셋 제거 |
| `conductors` | dict | 이름 -> 정렬된 읽기 전용 절점 번호(`"ground"` 포함) |
| `charge` | dict | 이름 -> C/m, 도체 위 반력의 합 |
| `total_free_charge` | 스칼라 | C/m, `sum(load)` |

`ValueError`를 내는 검사: 비유한 강성·하중·해; `max(abs(K) abs(V) + abs(f))`의
`1e-10`을 넘는 자유 잔차; 성분별 전하 수지
`abs(sum(reaction) + sum(load)) <= 1e-10 (sum(abs(reaction)) + sum(abs(load)))`;
특이 계. 어떤 것도 고쳐 쓰지 않습니다.

`capacitance_matrix(mesh, *, permittivity, conductors, ground)`는 도체
`{name: node ids}`의 사전 순서대로, 필수이며 비어 있지 않은 `ground`에 대한
Maxwell 정전용량 행렬(F/m)을 돌려줍니다. 열 `j`는 도체 `j`를 1 V, 나머지 도체와
접지를 0 V로 둔 해입니다. 항 `(i, j)`는 **전하 경로**, 즉 도체 `i`의 반력 합입니다.
**에너지 경로** `eps0 V_i^T K_r V_j`를 같은 전위와 독립 조립으로 계산해 두 경로가
가장 큰 항의 `1e-10` 이내로 일치해야 하며(아니면 `ValueError`), 그 뒤에만 전하
행렬을 `(C + C^T)/2`로 대칭화해 돌려줍니다. 실수 유전율이면 대칭 양의 정부호입니다.
`eps' (1 - j tan d)`이면 행렬은 복소수 `C - j C_loss`이고 `C_loss = -Im C`는 양의
준정부호입니다. 대각 `Im C_ii < 0`이고, 상호 정전용량이 음수이므로 비대각
`Im C_ij`는 양수입니다. `sipi`는 선로 파라미터에 자체 루틴
(`sipi.capacitance_matrix`)을 계속 쓰며 이 모듈은 그것을 바꾸지 않습니다.

### JAX·PyTorch

`permittivity`(스칼라 또는 영역 표), 도체 전위, 기준 전위, `charge_density`
(스칼라·표·live 값을 돌려주는 콜백)는 [정상 전기전도](electric_steady2d.md)와
[미분 계약](differentiation.md)처럼 JAX·PyTorch float64 값일 수 있습니다. 결과와
정전용량 행렬은 그 라이브러리로 돌아오며 해당 입력에 대한 미분을 지닙니다.
자유 잔차·수지·경로 검사는 수치 스냅샷을 읽습니다. 복소 live 유전율은
`TypeError`입니다. 복소 유전율은 NumPy 전용입니다. `ElementPermittivity` 값은
NumPy입니다.

## 예제

```python
import numpy as np
from galerkin import annulus_mesh, capacitance_matrix, solve_electrostatics

mesh = annulus_mesh(1.0, 3.0, 16, 96)                       # metres
C = capacitance_matrix(mesh, permittivity=2.2,
                       conductors={"inner": mesh.boundary["inner"]},
                       ground=mesh.boundary["outer"])
print(C[0, 0])   # 1.1150e-10 F/m; exact 2 pi eps0 2.2 / ln 3 = 1.1141e-10

r = solve_electrostatics(mesh, permittivity=2.2,
                         conductors={"inner": (mesh.boundary["inner"], 1.0)},
                         ground=mesh.boundary["outer"])
print(r.charge["inner"] + r.charge["ground"])   # 0 to roundoff; C[0, 0] == r.charge["inner"]
```

## 검증

```sh
python -m pytest -q -s tests/galerkin/test_electrostatics_capacitance.py
```

기준은 구현 전에 고정했고 임계값은 조정하지 않았습니다. 레퍼런스는
`refsol.electrostatics`(`coax_capacitance`, `two_layer_plate_capacitance`)와
`refsol.metallic.coax_potential`이며 엔진을 import하지 않습니다. Linux, Python
3.12, NumPy 2.5.4, SciPy 1.18.1에서 측정:

| 기준 | 조건 | 측정값 |
|---|---|---|
| E1 에너지 대 전하 경로 | 가장 큰 항 대비 `<= 1e-10`; `capacitance_matrix` 내부 검사이고 시험에서 `assemble_stiffness`로 다시 계산 | `6.9e-16`(접지면 위 내부 트레이스 2개) |
| E2 동축 `C = 2 pi eps0 eps_r / ln(b/a)`, `annulus_mesh(1, 3, n, 6n)`, n = 4, 8, 16, 32 | 마지막 두 세분화의 관측 차수 `>= 1.8`, 최세 `<= 1e-3` | 오차 `1.39e-2 / 3.52e-3 / 8.83e-4 / 2.21e-4`, 차수 `1.984 / 1.995 / 1.999` |
| E3 두 층 평행판(0.3 mm·2.0, 0.7 mm·5.0, 폭 2 mm) 직렬 결합, P1에서 정확 | `<= 1e-12` | `6.7e-16`; 손실 탄젠트 0.01/0.002의 복소 폐형식과도 비교 |
| E4 실수 `eps_r` | `C` 대칭(대칭화 후 정확), 양의 정부호, `C_ij < 0 < C_ii` | 통과 |
| E4 복소 `eps_r (1 - 0.02 j)` | `Im C_ii < 0`, `-Im C` 양의 정부호; `Re C`가 무손실 `C`와 `1e-12` 이내 | `Re` 차이 `6.1e-16`; `Im C + tan d C` 차이 `2.4e-17` |
| E5 JAX·PyTorch에서 `dC/d eps_r = C / eps_r` | 상대 `1e-10`; 두 층 `dC/d eps_1`도 폐형식과 비교 | **건너뜀**: 검증 환경에 두 라이브러리가 없어 live 경로는 여기서 미검증 |
| E6 동축에 `rho = 1e-6 C/m³`인 전하 수지 | `abs(sum(charge) + total_free_charge) <= 1e-10` 상대 | `6.7e-16` |
| E6 `rho = 0` | `abs(sum(charge)) <= 1e-12` × 가장 큰 전하 | `2.4e-16` |

오류 경로: 접촉하는 도체(접지 포함), 메시 밖 절점, 빈 집합·비정수 집합, 혼합
키 형식, 비스칼라 전압, 게이지 누락·불필요, 게이지 성분의 부적합 순 전하, 잘못된
유전율(0, 음수, 비유한, 불, `Im > 0`, 비스칼라), 메시와 맞지 않는 영역 표, 다른
메시의 `ElementPermittivity`, `"ground"` 이름 충돌, 경로 검사 자체(허용오차 0으로
강제). `tests/galerkin/test_electrostatics.py`는 바탕이 되는 동축 전위를 2차로
채점합니다. 로컬 통과로 CI나 macOS/Windows 수용을 주장하지 않습니다.

## 한계

- 2D 단위 길이당만 지원합니다. 3D·축대칭·z 방향 유한 두께는 없습니다.
- 자유 전하는 주어진 밀도입니다. 공간 전하 수송, 반도체·전해질 물리, 비선형
  유전율은 없습니다.
- 이방성 유전율은 받지 않습니다(`assemble_stiffness`의 텐서 경로는 직접 조립하는
  호출자에게 남아 있습니다).
- P1 요소 장은 평형 유속이 아닙니다. 도체 전하는 변을 따라 `D.n`을 적분하지 않고
  조립 반력에서 얻습니다.
- `sipi` 선로 파라미터(`C`, `C0`, `L`, `G`)는 `sipi.capacitance_matrix`를 계속
  씁니다.
- 복소 유전율은 NumPy 전용이며 JAX·PyTorch 입력은 실수입니다.
