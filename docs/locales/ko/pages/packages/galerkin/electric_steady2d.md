# 2D 정상 전기전도

## 연성 계약 (버전 1)

명시적 Python 진입점은
`galerkin.electric.solve_steady_electric(mesh, *, conductivity, dirichlet,
outward_current=None, reference_potential=None)`입니다.
적합 P1 삼각형에서 `div(J)=0`, `E=-grad(V)`, `J=sigma*E`를 풉니다.
체적 전류원은 없습니다. 전기전도도는 유한한 양의 스칼라 또는 모든 영역 이름과
정확히 일치하는 `{region_name: scalar}` 표이며 단위는 S/m입니다. 재료 경계는
요소 변과 일치해야 합니다. 전위는 연속이며 법선 전류는 약한 형식으로 보존합니다.
온도 의존성·접촉저항·이방성·3D·UI는 범위 밖입니다.

`dirichlet`은 외부 경계 절점 번호를 스칼라 전압(V)에 대응시킵니다.
`outward_current`는 외부 변 태그를 `J.n`(A/m²)에 대응시키며 양수는 **외향**입니다.
스칼라 또는 `(points_m, outward_normals) -> (Q,)` 콜백을 받고 변마다 Gauss 점
4개로 적분합니다. 미지정 변과 명시적 0은 절연입니다. 변 순서가 뒤집혀도 법선은
기하학적 외향입니다. 중복 선택 변·내부 변·두 끝점 모두 전압 지정인 변에 자연
경계를 주면 거절합니다. 인접 전압/전류 변은 끝점 하나를 공유할 수 있습니다.

전압 조건이 없는 각 연결 성분은 외향 전류 적분이 0이어야 합니다.
`integral(abs(J.n))` 대비 상대 허용오차는 `1e-12`이고 절대 전류 하한은 없습니다.
적합성은 게이지를 추가하기 **전에** 검사합니다. `reference_potential`은 이러한
각 성분에 정확히 하나의 절점→전압을 지정하는 사전이며 내부 절점도 가능합니다.
누락·중복·불필요한 게이지는 거절합니다. 이는 상수 자유도만 고정하며 물리적 전류를
공급하거나 전극 반력에 포함되지 않습니다. 분리 성분 사이의 전류 상쇄는 허용하지 않습니다.

`SteadyElectricResult`의 배열과 복사된 메시 배열은 입력과 독립적인 읽기 전용
스냅샷입니다. 재메시 없이 절점·삼각형 순서와 영역 번호를 유지합니다.

| 필드 | 모양 | 단위 / 의미 |
|---|---|---|
| `mesh` | `Mesh` | 입력 토폴로지·m 좌표·경계/영역 식별자의 복사본 |
| `potential` | `(N,)` | V, 지정 게이지를 포함한 P1 절점 전위 |
| `electric_field` | `(M,2)` | V/m, 요소별 상수, Cartesian x/y |
| `current_density` | `(M,2)` | A/m², 요소별 상수 |
| `conductivity` | `(M,)` | S/m, 전개한 재료 표 |
| `joule_heating` | `(M,)` | W/m³, 음이 아닌 `J·E = sigma*abs(E)**2` |
| `joule_load` | `(N,)` | W/m, 각 요소가 절점마다 `Q*A/3`을 더한 일관 하중 |
| `joule_power_per_length` | 스칼라 | W/m, `sum(Q*A) = sum(joule_load)` |
| `reaction` | `(N,)` | A/m, 전압 전극이 주입한 전류; 나머지는 0 |
| `prescribed_outward_load` | `(N,)` | A/m, 지정 외향 전류의 형상함수 적분 |
| `residual` | `(N,)` | A/m, 오프셋 복원 전 계산한 `K*V + prescribed_outward_load` |
| `supplied_power_per_length` | 스칼라 | W/m, 전극·전류원이 공급한 전력 |

열 소비자는 절점/요소 순서가 동일한 **같은 메시**를 사용해야 합니다.
`joule_heating`을 명시적인 요소별 체적 열원으로, 또는 `joule_load`를 조립된
하중으로 전달합니다. 요소 배열을 스칼라/영역 전용 `heat_source`에 그대로 넣거나,
영역/절점 평균·경계 너머 보간을 하거나, 전기전도도를 다시 곱하면 안 됩니다.
`sum(Q*A) == sum(joule_load)`를 반올림 오차 내에서 확인합니다. 전기 모듈은 기존
열 솔버를 변경하지 않습니다. 열전도도와 열 경계조건은 소비자 소관입니다.
실제 깊이가 `d` m이면 단위 깊이당 전류·전력에 `d`를 곱해 A·W를 얻습니다.
Q는 W/m³ 그대로이며 암묵적 두께·단위 변환은 없습니다.

전극 외향 전류는 해당 전극의 중복 없는 절점에서 `-sum(reaction)`입니다.
각 성분은 `sum(reaction) = sum(prescribed_outward_load)`를 만족해야 합니다.
절점을 공유하는 전극 집합의 반력을 중복 합산하면 안 됩니다.
공급 전력은 `V·reaction - V·prescribed_outward_load`이며 수치 안정성을 위해
성분별 전위 오프셋을 빼고 계산합니다. 이산 해의 Joule 전력과 같습니다.
P1 요소 기울기는 H(div) 평형 유속이 아닙니다. 직접 경계 `J.n` 적분과 요소 간
점프는 메시 수렴으로 평가해야 하며 조립 전극 반력을 대신할 수 없습니다.
