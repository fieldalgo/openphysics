# Studio 3D 보기(실험적)

[English](../../../../../packages/simcase/studio_3d.md) | **한국어**

[문서 홈](../../index.md)

상태: **실험적.** 3D 보기는 버전 1 형상 문서([계약](geometry_document.md))의 `3d`
구성 요소를 `/geometry-lab`의 [형상 실험실](geometry_lab.md) 페이지에서 보여 줍니다.
읽기 전용이며, 5단계 엔진(`simcase.geometry_engine3d`)이 받는 것, 곧 상자와 `layers`
기능의 슬래브 층, 그리고 표시 모양으로 그리는 meshloom builder 모양의 원통과 구([원통과 구](#원통과-구))를 받으며, 이를 메시하고([메시](#메시)) 서버에서 3D 정상 열을 풀 수 있습니다([실행](#실행)). 모델 작업 공간에는
아직 나오지 않습니다. 페이지, 조작, HTTP 응답은 어느 릴리스에서든 바뀔 수 있습니다.

## 사용

Studio를 시작하고 형상 실험실을 엽니다.

```sh
python -m simcase.studio            # 그다음 http://127.0.0.1:8765/geometry-lab 을 엽니다
```

**Start from**에서 **Via in a layer stack (3D example)**를 고르거나, 보여 줄 구성 요소가
`3d`인 문서를 엽니다. 2D 구성 요소가 있는 문서는 예전처럼 그것을 먼저 보여 주므로
**Component**에서 `3d` 구성 요소를 고릅니다. 카드 문서
(`simcase/studio/static/model3d-via-stack.json`, 단위 µm)는 10 × 10 영역에 슬래브 층
세 개(기판 0–2, 산화막 2–3, 위 실리콘 3–4, `layers` 기능 `stack` 하나)와 산화막을
관통하는 구리 상자 `via`(x, y는 [4, 6], z는 [2, 3])로 되어 있습니다.

같은 보기가 작업 공간 3D 모델의 Model 페이지이며, 거기서 문서를 편집하고 고른 면으로 선택을
만듭니다: [3D 모델](workspace.md#3d-모델실험적)을 보십시오.

같은 보기가 작업 공간 3D 모델의 Model 페이지이며, 거기서 문서를 편집하고 고른 면으로 선택을
만듭니다: [3D 모델](workspace.md#3d-모델실험적)을 보십시오.

| 동작 | 포인터 | 키보드(보기에 초점) |
|---|---|---|
| 회전 | 끌기 | 화살표 키(한 번에 15°) |
| 이동 | Shift 끌기 또는 오른쪽 끌기 | Shift + 화살표 키 |
| 확대·축소 | 휠 | `+`, `−` |
| 영역 전체 맞춤 | **Fit** | `F` |
| 축 보기 +X, −X, +Y, −Y, +Z, −Z | 버튼 | `1`–`6` |
| 등각 보기 | **Iso** | `0` 또는 `I` |
| 면 고르기 | 클릭 | **Faces** 목록: Tab으로 항목에 가서 Enter |

- **Names**는 고른 면의 평면, 정확한 넓이, 양쪽 영역, 태그, 그리고 그 면이 가진 모든
  출처 이름을 정렬해 보여 줍니다(예: `stack.oxide.top`, `stack.top.bottom`, `via.z1`).
- **Faces**는 복합체의 모든 면을 이름과 함께 나열합니다. 내부 면을 포함해 모든 면에
  키보드로 가는 길입니다.
- **Regions**에는 영역마다 숨기기·보이기 상자가 있습니다. 면은 양쪽 가운데 빈(void)
  영역이 아닌 쪽이 보일 때 그립니다.
- **Section**은 x, y 또는 z가 슬라이더 값 이하인 부분만 남기고, 잘린 면의 정확한
  윤곽을 서버가 빨간 선으로 그립니다. 면 고르기는 지운 부분을 무시합니다.
- 거부 메시지는 엔진의 문구 그대로입니다. 5단계 엔진이 아직 받지 않는 기능은 이름으로
  말합니다(`E-3D-COMBINATION`, 예: `cylinder 'pin' is not taken yet in a 3d component;
  boxes and slab layers are`).

3D 보기는 메시 모서리를 그리지 않습니다. 정확한 형상을 보여 줍니다. 메시는
**Mesh** 아래 자기 보기에 그립니다.

## 메시

**Mesh**는 보이는 `3d` 구성 요소의 사면체 메시를 `simcase.build_mesh3d`(meshloom)로
서버의 자식 프로세스에서 만들고, 메시의 겉면을 보여 줍니다. 물리 계산은 하지 않고
파일도 바꾸지 않습니다.

- **추정 먼저.** 3D 보기가 구성 요소를 보여 줄 때마다 페이지는 `I-MESH-ESTIMATE`
  추정(`simcase.estimate_mesh3d`, 메시하지 않음)을 받아 예를 들어 "Estimate 48,000
  tetrahedra · about 30 s"로 보여 줍니다. T = 6.3 ∫ dV / s³(s는 얇은 층과 틈에서 더 작아지는 요소
  크기, [추정](geometry_engine3d.md#사용))를 유효숫자 두 자리로
  반올림한 값과, 사면체당 0.6 ms(엔진의 0.4–0.6 ms 가운데 느린 끝)로 잡은 예상 시간입니다.
  `mesh.element_count_limit`를 넘으면 **Mesh**가 꺼지고 추정의 문구 그대로 거부를
  보여 줍니다(`E-MESH-ESTIMATE`). 서버도 그런 요청은 프로세스를 시작하기 전에 거부합니다.
- **진행.** 작업 중에는 Studio가 아는 단계 "Forming geometry → Meshing (expected about
  N s) → Checking the mesh → Ready"와 경과 시간(m:ss)을 보여 줍니다. 경과 시간이 추정의
  두 배를 넘으면 "taking longer than the estimate"를 덧붙입니다. 백분율은 없습니다.
  meshloom이 진행률을 알려 주지 않기 때문입니다.
- **Cancel meshing**은 자식 프로세스를 끝내고 "Meshing cancelled; nothing kept."라고
  알립니다. 이 동작의 이름은 어디서나 Cancel 하나입니다(실행에는 그대로 "Stop run").
  meshloom은 중간에 멈출 수 없고, 얇은 입력에서는 끝나지 않기도 합니다(예: 영역
  대각선의 6e-8 너비 배경 띠를 사이에 둔 상자 두 개). 그런 작업을 끝내는 것이 자식
  프로세스입니다.
- **한 번에 하나.** 서버는 3D 모델을 한 번에 하나만 메시합니다. 두 번째 요청에는 429
  "Studio is already meshing one 3D model; wait for it or cancel it."으로 답합니다.
- **재사용.** 서버는 구성 요소마다(최대 네 개) 마지막 메시를 정규화한 `geometry`와
  `mesh` 블록(키 정렬, 공백 없음, 숫자는 쓴 그대로)의 SHA-256을 키로 서버 프로세스가
  살아 있는 동안 보관합니다. 블록이 그대로면 **Mesh**가 보관한 메시를 바로 답하고,
  나중의 Run도 키가 같으면 그것을 다시 씁니다. 문서가 바뀌면 다음 메시 전까지 메시
  보기를 흐리게 합니다.
- **메시 보기**는 메시의 바깥 삼각형과 경계면 삼각형을 영역별 색과 메시 모서리로
  그리며, 3D 보기와 같은 키, 카메라, 숨긴 영역, 단면을 씁니다. 메시 보기에서 고르면
  같은 면 id로 같은 면을 고르고 **Names** 패널은 같은 이름(메시의 `provenance_faces`)을
  보여 줍니다. 통계는 절점, 사면체, 영역 수와 형상 품질 q = 3 r_in/R_circ(정사면체에서
  1)의 최솟값과 중앙값입니다. 이 품질은 meshloom 검증이 쓰는 척도입니다
  ([meshloom](../meshloom/overview.md)). meshloom의 `stats`에는 사면체별 품질이 없어
  Studio가 메시에서 q를 계산합니다.
- **경로**는 `thermal.steady3d` 종류의 것입니다(`simcase.build_thermal3d_mesh`). 판 `layers` 피처
  하나만 가진 구성 요소(E1)는 `meshine.extrude`로, 그 밖에는 `simcase.build_mesh3d`로 메시합니다.
  압출 경로의 추정은 그 경로의 개수로, 발자국 삼각형 10,000개까지는 정확하고 그 위로는 하한입니다. 하한일 때는
  한도 확인이 자식 프로세스에서 발자국 메시 뒤, 압출 전에 추정과 같은 문구로 일어날 수 있습니다
  ([추정](geometry_engine3d.md)). 추정 응답에 `route`와 `count`가 더해집니다.

## 실행

`POST /api/model3d/run`은 `thermal.steady3d` 문서([3D 정상 열](thermal_steady3d.md))를 서버에서 풀고
값, 겉면 지도, 단면, 탐침을 응답합니다. 사면체와 해는 서버 밖으로 나가지 않습니다.

- **프로세스 전에 거부**합니다. 읽기 또는 추정의 문구 그대로입니다: `thermal.steady3d` 항목 하나가 아닌
  문서, 이 종류의 읽기가 거부하는 문서(그 코드와 함께), `mesh.element_count_limit`를 넘는 메시 추정.
- **두 단계.** `mesh`: 구성 요소에 보관한 메시의 재사용 키가 같으면 바로 씁니다(`reused: true`, 프로세스
  없음). 아니면 [메시](#메시) 작업 그 자체를 자식 프로세스에서 돌리고, **Mesh**처럼 그 구성 요소의 메시로
  보관합니다. `solve`: 서버 스레드에서 `simcase.mesh3d_from_arrays`로 되읽은 보관 메시에
  `simcase.solve_thermal3d`를 돌리므로([이미 있는 메시에서](thermal_steady3d.md#이미-있는-메시에서)) 결과가
  `simcase.run`과 비트까지 같습니다. 상태는 메시 작업과 같은 필드입니다: `steps` `mesh`, `solve`, `done`
  가운데 `step`, 경과·예상 시간, `longer_than_estimate`, `route`.
- **한 번에 실행 하나**, 메시 작업이 도는 동안에도 실행하지 않습니다. 자식 프로세스 자리를 같이 씁니다(429,
  "Studio is already running one 3D heat model; wait for it or cancel it." 또는 메시 작업의 문구).
- **Cancel**은 mesh 단계에서 **Cancel meshing**처럼 자식 프로세스를 끝냅니다. 풀이는 중단할 수 없으므로
  solve 단계의 Cancel은 실행을 취소로 표시하고("Run cancelled; nothing kept.") 풀이가 돌아오면 결과를
  버립니다.
- **고정 온도가 없는 연결된 영역 묶음**은 galerkin의 검사(사면체 모서리의 연결 성분)에서 영역 이름을 들어
  거부합니다: "Fixed temperature is missing on the connected group of regions 'B': each connected group of
  regions needs one (galerkin: each connected component of the mesh needs a Dirichlet node)". 내부 면의 고정
  온도는 읽기가 거부합니다("Fixed temperature needs an outer face; …").

응답(`/api/model3d/runs/{run}/…`; 위치는 보기의 `origin_m`에서 잰 float32, 요청의 길이는 단면처럼 구성
요소의 단위):

| 경로 | 응답 |
|---|---|
| `values` | `heat_rate_by_selection`(`prescribed_temperature` 이름마다 W: 그 노드의 `reaction_heat_rate` 합, 두 이름이 고정한 노드는 앞 이름에), `total_source`, `balance_residual`(바깥으로 나간 열에서 열원을 뺀 W)과 `relative_balance_residual`, 노드·위치·영역이 붙은 `temperature_min`과 `temperature_max`, 메시 통계, 경로, 재사용 키, `document_sha256`(정규화한 문서의 해시) |
| `extremes` | `{run, temperature_min: {node, regions}, temperature_max: {node, regions}}`: 각 극값 노드를 나누는 사면체들의 서로 다른 영역, 메시의 영역 순서로, 서버가 가진 메시에서(HTTP 보기; `values`, 내보내기, 기록은 그대로). 서버가 갖지 않은 실행은 다른 실행 경로처럼 거부(404, *no such 3D heat run*) |
| `surface` | 메시 응답의 면, 영역, 위치, 삼각형과 면 id, 그 노드의 `temperature`(float32) |
| `cut {axis, at}` | 평면에 의한 정확한 P1 절단: 사면체마다 평면 위 노드와 모서리 교점, 교점의 T는 그 모서리에서 보간; 평면에 놓인 면은 한 번만; 삼각형은 +축을 봅니다 |
| `probe {point}` | 점을 담은 사면체에서 P1 보간 T, 영역, 무게중심 좌표; 메시한 영역 밖이면 거부 |
| `export/cut.csv?axis=&at=` | `# cut plane: z = 1.2345 mm (0.0012345 m)`, `# run: …`, `# document_sha256: …` 다음에 `x_m,y_m,z_m,temperature_K`(float64, `repr`) |
| `export/surface.csv` | 겉면 노드, `x_m,y_m,z_m,temperature_K,face`(노드의 첫 삼각형이 속한 면의 provenance 이름), 같은 머리 줄 |
| `export/run.json` | `{values, document}` |
| `record?maps=kept` | 실행 기록 `thermal-steady3d-run-v1`: `document`, `document_sha256`, `values`, `mesh`, `maps`(`kept`이면 `surface`, `not kept`이면 그 개수; [멀티피직스 실행의 maps](workspace.md)와 같음) |

## 원통과 구

원통이나 구가 meshloom의 builder 모양(C4 판을 관통하는 비아, C5 상자 안의 구, C1 구, C11 동심 구;
[builder 모양](geometry_engine3d.md#builder-모양의-원통과-구슬라이스-3)) 가운데 하나인 `3d` 구성 요소에는
정확한 복합체가 없습니다. 보기는 이를 `simcase.display_shapes3d`([표시 모양](geometry_engine3d.md#표시-모양))로
그립니다. 면의 이름 집합이 메시의 출처 이름이어서 고르면 메시의 이름을 주며, 면은 따로 정한 표시 규칙으로
그립니다(평면은 정확, 원통의 고리와 양 끝의 원판·고리는 내접 n각형 n = min(256, max(48, ⌈2πr/ℓ⌉)), 구는 정이십면체
측지 격자 f = min(64, max(8, ⌈1.05 r/ℓ⌉)), ℓ = 영역 대각선 / 200). 곡면을 고르면 **Names**에 "Shape drawn for
display; the mesh follows it to within its size"가 붙고, 곡면은 꼭짓점 법선으로 음영을 넣습니다.

- 표시, 단면, 검사 응답은 파싱한 모델의 피처 종류로 갈립니다. 원통이나 구를 가진 구성 요소는
  `display_shapes3d`로 가고, 다른 구성 요소는 복합체의 응답을 그대로 둡니다. 어느 builder도 받지 않는 원통이나
  구는 전처럼 builder의 문구로 거부합니다.
- 표시 응답은 모든 필드를 유지합니다. 면마다 `shape`(`plane`, `cylinder`, `sphere`)와 `segments`(n 또는 f,
  직사각형은 0)가 붙고, 곡면은 `axis`와 `at`이 null이며, 응답에 `display_note`가 붙습니다. 단면은 정확합니다.
  원통을 z로 자르면 n각형, x나 y로 자르면 ±√(r² − d²)의 두 선, 구를 d < r에서 자르면 ρ = √(r² − d²)의 원입니다.
- 검사(`check_view_shapes`)는 정확한 부피로 피처의 덮임(비아는 `full`, C11에서는 가장 안쪽을 뺀 구가
  `partial`, 안쪽 구들에 "covered in part by"), 정확한 부피의 영역, 빈 선택, `mesh` 아래 슬라이스 3의 추정(경로
  `builder`), 그리고 상자와 층처럼 `run`(아래)을 답합니다: 카드 2에서는 `{"ok": true}`, `via.side`에 고정 온도를 주면
  *Fixed temperature needs an outer face; via.side is inside*(E-CONTRACT).
- **Mesh**와 **Run**이 이 구성 요소를 받습니다. 메시 작업의 자식 프로세스는 builder 메시의 경계·경계면
  삼각형마다, 그 삼각형을 가진 출처 이름 집합과 이름 집합이 같은 표시 면을 붙입니다(`route: "builder"`).

카드 `model3d-via-slab-3d.json`(`/model3d-assets/`)은 5단계의 E2입니다. k_s = 1 W/(m·K)인 판
[−1, 1]² × [0, 1] m, (0, 0)에 있는 r = 0.3 m, k_v = 100 W/(m·K)의 비아, z0에 300 K와 z1에 301 K, 옆면 단열,
`mesh.element_size` 0.1 m. 기대 열유량은 Q = ΔT/L · (k_v πr² + k_s (A − πr²)) = 31.99159 W입니다.

## 보내는 것과 응답

- `POST /api/model3d/display`는 `{"doc": <문서>, "component": <이름 또는 null>}`을
  받습니다(이름이 없으면 첫 `3d` 구성 요소). `GET /api/model3d/display`는 카드 문서를
  답합니다. 응답은 `{"ok": true, ...}` 또는 `{"ok": false, "refused": <메시지>}`이고,
  요청은 다른 실험실 경로와 같이 읽습니다([형상 실험실](geometry_lab.md#보내는-것과-받는-것)).
- 표시용 삼각형은 메시가 아니라 정확한 복합체로 서버에서 만듭니다. 복합체의 면은 모두
  축에 나란한 다각형(구멍 포함)이고, pm 정수로 자기 꼭짓점 좌표 격자의 직사각형으로
  정확히 나눈 뒤 직사각형마다 삼각형 두 개로 나눕니다. 모든 삼각형은 자기 면의 평면
  위, 다각형 안에 있고 그 면의 id를 가집니다.
- 배열은 little-endian base64입니다. `positions`(float32, 영역 중심 `origin_m`에서의
  미터, 각각 정확한 pm 값에서 변환), `indices`(uint32, 삼각형마다 세 개),
  `triangle_faces`(uint32, 삼각형마다 면 id), 면 윤곽 `edges`(float32 선분 끝점)와
  `edge_faces`.
- `faces`는 면마다 `id`, `axis`와 `at`(평면, 구성 요소의 길이 단위), `names`(정렬한
  출처), `minus`·`plus` 쪽 영역, `exterior`, `tag`, 정확한 `area`, 삼각형 범위를 줍니다.
  `regions`는 이름, 재료, `void`, 정확한 `volume`, 면을 주고, `selections`와 `tags`는
  엔진을 따르며, `summary`는 텍스트 목록입니다.
- `POST /api/model3d/section`은 같은 봉투에 `"axis"`(`x`, `y`, `z`)와 `"at"`(구성
  요소 길이 단위의 수, pm으로 한 번 반올림)을 더해 받습니다. 평면이 닫힌 면과 만나는
  선분(`segments`, float32, 선분마다 끝점 두 개, 같은 좌표계, `segment_faces`), 잘린
  면, 만나는 영역을 답합니다. 영역 밖의 평면은 이름을 들어 거부합니다.
- 응답은 결정적입니다(W15). 순서 없는 것은 응답에 들어가지 않습니다. 면마다 `alone`에
  그 면만 고르는 이름을 나열합니다.
- `POST /api/model3d/check`는 3D 빌더의 검사입니다(같은 봉투). `{"ok": true, ...}`로
  답합니다.
  - `features`: 기능마다 `index`, `id`, `type`, 영역 안의 `volume`과 자기 셀이 남긴
    부피(`owned`, 둘 다 구성 요소 길이 단위의 세제곱), `coverage`; 상자는 계산된 `size`(구성 요소 길이 단위의 x, y, z,
    매개변수와 식을 계산한 값)도 가집니다. coverage는 `full`,
    `partial`("covered in part by N (id)"), `none`("covered by N (id); adds no region"),
    `outside`("outside the domain; adds no region")입니다. N은 그 상자와 겹치고 자기
    부피가 남은 뒤쪽 기능 번호(1부터)입니다. 모두 복합체로 pm 단위에서 정확히
    계산합니다.
  - `parameters`: SI 값, 단위, 적은 값, 그 파라미터 이름을 쓰는 구성 요소 필드
    `used_by`.
  - `regions`, `selections`, 그리고 `display` 아래의 표시 응답.
  - `mesh`: 구성 요소를 메시할 때의 추정, `{"ok": true, "estimate": ..., "key": ...}`
    (`/api/model3d/mesh/estimate`와 같은 말, `simcase.estimate_mesh3d`, 메시 작업의 재사용
    키), 또는 메시를 막는 거부(아래와 같은 형식): 요소 수 한도를 넘는 E-MESH-ESTIMATE,
    허용 오차 아래의 E-CONTRACT, 한 좌표로 반올림되는 두 값(`features[i]`의
    E-3D-COMBINATION). 어느 쪽이든 형상은 만들어지므로 응답은 `"ok": true`로 남습니다.
    카드에서는 검사의 8 ms에 약 7 ms를 더합니다.
  - `domain`: 구성 요소의 길이 단위로 된 영역, 매개변수와 식을 계산한 수. 작업 공간의 Domain 행, 크기 범위, Add feature의
    기본값에 씁니다.
  - `run`: Run이 문서를 받을지 여부. `POST /api/model3d/run`이 무엇이든 시작하기 전에 읽는 대로
    읽습니다(`thermal.steady3d` physics 항목 하나, 그다음 종류의 reader): `{"ok": true}` 또는
    `{"ok": false, "refused": <reader의 말>, "code"}`, 예를 들어 *Fixed temperature needs an outer
    face; via.z1 is inside*(`E-CONTRACT`). 실행, 메시 작업, 프로세스를 시작하지 않습니다(카드에서 약
    10 ms). 고정 온도가 없는 연결된 영역 묶음은 메시에서만 찾을 수 있으므로, 그 거부는 실행에서 옵니다.
- 형상을 만드는 중의 거부는 `{"ok": false, "refused": <엔진 메시지 그대로>, "code", "path",
  "feature_index"}`입니다. index는 경로가 가리키는 `features[i]`이거나 null이며, 빌더는
  그 기능을 표시합니다.
- `POST /api/model3d/selection`은 봉투에 `"face"`(면 id)와 `"name"`을 더해 받습니다.
  `selections[name] = {"boundary": <이름>}`을 넣은 문서로 답하며, `<이름>`은 그 면만
  고르는 이름 가운데 정렬해 첫 번째입니다("Use for → New selection"). 한 이름으로 고를
  수 없는 면, 이미 있는 이름, 기능 id는 이름을 밝혀 거부합니다.

메시 작업:

- `POST /api/model3d/mesh/estimate`는 표시와 같은 봉투를 받아 `{"ok": true,
  "estimate": {"code": "I-MESH-ESTIMATE", "message", "component", "tetrahedra", "limit",
  "seconds"}, "key"}` 또는 `{"ok": false, "refused", "code"}`로 답합니다.
- `POST /api/model3d/mesh`도 같은 봉투를 받습니다. 추정의 거부는 400, 실행 중인 작업이
  있으면 429로 답하고, 아니면 `{"job", "status", "reused", "estimate", "key"}`로
  답합니다. 보관한 메시의 키가 같으면 `status`는 `"done"`, `reused`는 `true`이고, 아니면
  `"running"`입니다.
- `GET /api/model3d/jobs/{job}`은 `status`(`running`, `done`, `error`, `cancelled`),
  `step`(`forming`, `meshing`, `checking`, `ready`), `elapsed_s`, `expected_s`,
  `longer_than_estimate`, `error`, `has_result`를 답합니다.
  `POST /api/model3d/jobs/{job}/cancel`은 자식을 끝내고(terminate, 1초 뒤 kill) 그
  디렉터리를 지웁니다. `GET /api/model3d/jobs/{job}/result`는 메시를 답합니다(작업이
  끝나기 전에는 409). 작업 id는 서버가 만듭니다(`m3d-`와 16진 12자리). 다른 id는 404입니다.
- 자식은 모든 플랫폼에서 `multiprocessing`의 `spawn` 문맥으로 시작합니다. 서버가 만든
  임시 디렉터리(`tempfile.mkdtemp`)에 정해진 이름으로 NumPy 배열을 쓰고, 서버는 그것을
  읽은 뒤 작업이 끝났다고 알리기 전에, 그리고 취소·실패 뒤와 서버가 끝날 때 디렉터리를
  지웁니다. 요청에서 온 경로는 쓰지 않습니다.
- 메시 응답에는 표시 응답의 좌표계, `faces`(면마다 메시 삼각형 범위), `regions`,
  `selections`, `tags`가 있고, 표시 삼각형 대신 메시의 겉면만 담습니다: `positions`
  (float32), `indices`, `triangle_faces`(복합체 면 id), `triangle_regions`(int32,
  `region_names`의 위치: plus 쪽 영역, 없으면 minus 쪽), `edge_indices`(uint32 쌍)와
  `edge_faces`, `stats`. 사면체는 서버에 남습니다.

페이지는 three.js 0.186.1을 Studio 자신에게서 읽고
([브라우저로 보내는 파일](../../third-party.md#브라우저로-보내는-파일)), 보기 모듈은
`/model3d-assets/`에서 읽습니다. 페이지 정책은 그대로 `script-src 'self'`입니다.

### 카메라

처음 카메라는 등각 카메라이고, 면 고르기(W3)를 이것으로 확인합니다.

- 좌표계는 영역 중심에서의 미터이고, R은 영역 대각선의 절반입니다.
- 직교 카메라가 target + 4 R e에서 target을 봅니다. e = (1, 1, 1)/√3, 위 방향 +z이고,
  축은 z = e, x = normalize(up × z), y = z × x(three.js `lookAt`)입니다.
- **Fit**은 반지름 1.1 R인 구를 담습니다. W × H 캔버스에서 W ≥ H이면 반높이 1.1 R, 반너비
  1.1 R W/H, 아니면 반너비 1.1 R, 반높이 1.1 R H/W입니다(확대 배율로 나눔).
- CSS 픽셀 캔버스 점 (px, py)는 ndc (2 px/W − 1, 1 − 2 py/H)에 있습니다.
- 축 보기는 ±x, ±y(위 +z)와 ±z(위 +y)를 따라 봅니다.

면 고르기는 표시용 삼각형(float32)에 대한 CPU 광선 투사로, 보이는 면 가운데 가장
가까운 교점을 단면의 남는 쪽에서 고릅니다.

## 검사

사전 등록(측정 전에 정하고 완화하지 않음):

| 검사 | 내용 | 기준 | 측정 | 위치 |
|---|---|---|---|---|
| W1 | E1, 카드, 시드 G1 집합 50개에서 모든 표시 삼각형이 정확한 표면의 출처를 가짐: (a) 면 id가 없거나 이름 집합이 면과 다름, (b) 꼭짓점이 면의 평면 밖이거나 다각형 밖, 또는 무게중심이 안에 있지 않음(float32 이전 pm 값으로 정확히) | (a) 0, (b) 0 | 0, 0(문서 52개, 면 1458개, 삼각형 3066개) | `tests/simcase/test_studio_model3d.py` |
| W2 | 면마다 float32 삼각형 넓이와 정확한 면 넓이 | 상대 1e-6 이하 | 최대 9.5e-8(G1 시드 0, 면 7) | 같음 |
| W3 | 1440 × 900 창, 등각 카메라, 카드에서 고정된 40개 점의 면 id와 첫 이름을, 보기보다 먼저 정확한 복합체로 쓴 독립 광선 투사(`tests/simcase/model3d_pick_oracle.py`, `studio_model3d_pick_points.json`, 모서리 3 px 안의 격자점 26개 제외)와 비교 | 40/40 | 40/40 | `tools/studio_browser/model3d_view_browser.mjs` |
| W12 | 1440 × 900과 390 × 844 첫 화면: 콘솔 오류 없음, CSP 위반 없음, 캔버스가 보이고 비어 있지 않음, 390에서 가로 스크롤 없음, Tab으로 면 목록에 닿음, 화면 저장 | 모두 성립 | 모두 성립(면 목록까지 Tab 17번, **Mesh** 버튼이 생긴 뒤 18번, 2026-11-27 재실행) | 같음 |
| W13 | 키보드만으로 회전, 축 보기, 면 목록에서 `via.z1` 고르기, 포인터 이벤트 없음 | 완료 | 완료, 포인터 이벤트 0 | 같음 |
| W15 | 새 서버 프로세스 3개에서 표시 응답의 SHA-256 | 같음 | 같음 | `tests/simcase/test_studio_model3d.py` |
| W8 | 취소: 실제 서버 프로세스에서 추정 60초 이상인 메시 작업(카드를 0.28 µm로: 약 69초)을 시작 3초 뒤 취소 | 취소 2초 뒤 자식 프로세스가 끝남, 결과를 남기지 않음, 서버 RSS가 전과 50 MB 안 | 모두 성립 | 모두 성립, 3번 중 3번(RSS +0.2 MB, 남은 파일 없음) | `tests/simcase/test_studio_mesh3d_job.py`, CI job `studio-mesh3d-w8`(main push와 수동 dispatch) |
| W9 | 추정: 한도의 0.5배, 0.99배, 1.5배인 카드 | 메시 전에 `I-MESH-ESTIMATE`로 답함, 1.5배 문서는 프로세스 시작 전에 거부 | 3/3 | 3/3 | `tests/simcase/test_studio_mesh3d_job.py` |
| W12(메시 보기) | 1440 × 900과 390 × 844에서 카드의 첫 메시 보기: 콘솔 오류 없음, CSP 위반 없음, 메시 캔버스가 보이고 비어 있지 않음, 390에서 가로 스크롤 없음, Tab으로 면 목록에 닿음, 화면 저장 | 모두 성립 | 모두 성립(면 목록까지 Tab 5번) | `tools/studio_browser/model3d_mesh_browser.mjs` |
| W6-E1 | E1(판 층 셋, 압출 경로)을 `POST /api/model3d/run`으로 푼 것과 `meshine.extrude` + `galerkin.solve_steady_heat_3d`를 직접 부른 것: 노드, 사면체, 온도, 반작용 열유량의 SHA-256 | 같음 | 같음 | `tests/simcase/test_studio_heat3d_run.py` |
| W6-card | `layer-stack-3d` 카드(meshloom 경로, 비아 열원)를 경로로 푼 것과 `build_mesh3d` + `solve_steady_heat_3d`를 직접 부른 것: 같은 SHA-256 | 같음 | 같음 | 같은 곳 |
| W7 | 경로로 푼 E1과 `refsol.thermal3d.layered_slab`(P1에서 정확): 노드 최대 \|T_h − T\|; 윗면 열유량(`heat_rate_by_selection.z1`)의 상대 오차 | ≤ 1e-10; ≤ 1e-9 | 1.4e-12 K; 2.5e-11 | 같은 곳 |
| W17 | E1의 단면과 유리수 산술(`fractions.Fraction`)로 계산한 정확한 P1 절단: 같은 점, 최대 \|T − T_exact\|; 평면 여섯(1 mm 경계면의 z, z = 1.2345 mm, x = 3.3, y = 7.1, 면 x = 0과 z = 2.5 mm), 압출·meshloom 경로, 경로를 거친 z = 1.2345 mm의 `cut.csv` | ≤ 1e-12 K | 최악 2.8e-14 K(노드 평면에서 0) | `tests/simcase/test_studio_heat3d_slice.py`, `test_studio_heat3d_run.py` |
| W8-run | 실행의 mesh 단계에서 Cancel: 11 µm의 열 카드(추정 약 69초)를 실제 서버 프로세스에서 실행 시작 3초 뒤 취소 | Cancel 2초 뒤 자식 종료; 실행은 취소, 남긴 것 없음; 파일 없음 | 모두 만족 | `tests/simcase/test_studio_heat3d_run.py`, CI 작업 `studio-mesh3d-w8` |
| W1(a) 모양 | C1, C4, C5, C11과 E2 카드: 메시의 경계·경계면 삼각형마다 표시 면 id가 있고, 그 면의 이름 집합이 같은 h에서 meshloom의 builder 메시에 슬라이스 3의 태그 표를 적용한 독립 표와 같음 | 불일치 0 | 0(삼각형 720, 1614, 1662, 1220, 5658개) | `tests/simcase/test_studio_model3d_shapes_mesh.py` |
| W1(b) 모양 | 같은 다섯: 평면 표시 면마다 float32 이전 pm에서 `vertices[:, axis] == coord`가 정확히 성립 | 평면 밖 꼭짓점 0 | 0(평면 면 8, 6, 0, 0, 8개) | `tests/simcase/test_geometry_display3d.py` |
| W2 모양 | 정확한 넓이에 대한 표시 넓이, s(x) = sin x / x: 직사각형 상대 오차, 원판 (A − A_h)/A ≤ 1 − s(2π/n), 고리 0 ≤ A_h − A ≤ πr²(1 − s(2π/n)), 원통 옆면 (A − A_h)/A ≤ 1 − s(π/n), 구 0 ≤ (A − A_h)/A ≤ max_f (ρ_f/R)²(각각 + 1e-12) | 직사각형 ≤ 1e-6, 각 한계 | 직사각형 0, 원판 4.14e-4, 고리 A의 3.15e-5, 옆면 1.04e-4(n = 126, 한계에 닿음), 구 1.18e-4~4.56e-4(한계 2.24e-4~8.63e-4) | 같은 곳 |
| W18 | h = 0.1에서 `POST /api/model3d/run`으로 푼 E2 카드: e_Q = \|Q_h − Q\|/Q(Q_h는 z1의 반작용), 그리고 Q_h, 노드 T, 반작용을 `build_mesh3d` + `galerkin.solve_steady_heat_3d` 직접 호출과 SHA-256으로 비교 | ≤ 1e-2, 같음 | 7.51e-3(Q_h = 31.75147 W, Q = 31.99159 W, 사면체 23,427개), 같음 | `tests/simcase/test_studio_model3d_shapes_mesh.py` |
| W14(실행) | 서버 쪽 겉면 지도와 z 단면의 시간과 크기 | 기록 | 아래 | `tests/simcase/test_studio_heat3d_run.py`(가장 큰 것은 `OPENPHYSICS_STUDIO_W14=1`) |
| W14 | 사면체 약 48,000개인 카드와 겉면 삼각형 150,000개에서 성능: 메시 응답 시간, 메시 보기 프레임 시간(120 프레임 중앙값), 탭 JS 힙 | 기록, 하드웨어 GL Chromium에서 관문: 힙 300 MB 이하, 프레임 중앙값 33 ms 이하 | 아래 기록, 관문은 **돌리지 않음**(소프트웨어 GL만) | 같음 |

W14는 2026-11-27에 Linux의 headless Chromium 158(Xeon 2.1 GHz, CPU 4개, GPU 없음)에서
기록했습니다. 렌더러가 SwiftShader 위의 ANGLE이었으므로 하드웨어 GL 관문은 돌리지 않았고
통과했다고 하지 않습니다. 삼각형 150,000개 경우는 스크립트가 카드의 표시 삼각형을
개수에 닿을 때까지 넷으로 나누어 만든 메시 응답을 서버 응답 대신 페이지에 주어, 그
크기에서 보기를 잽니다.

| 경우 | 메시 응답 | 클릭부터 메시가 그려질 때까지 | 프레임 중앙값(120) | JS 힙 + 배열 저장소 |
|---|---|---|---|---|
| 카드, 0.375 µm: 사면체 47,047개, 겉면 삼각형 12,411개 | 10 ms, 0.73 MB | 11.5초(메시 포함) | 53 ms | 10.1 MB |
| 겉면 삼각형 150,002개 | 197 ms, 8.9 MB | 1.0초 | 392 ms | 41.1 MB |

작업 자체의 시험은 그 밖에 429 응답, 취소한 작업이 아무것도 남기지 않음(메시, 디렉터리
없음, 결과는 409), 재사용 키가 형상이나 메시 블록이 바뀌면 바뀌고 다른 블록이나 키
순서에는 바뀌지 않음, meshloom이 끝나지 않는 작업(얇은 띠 문서)이 추정의 두 배를 훨씬
넘어서도 메시 중이고 취소 2초 안에 끝남, 작업 중에 끝나는 서버가 자식도 디렉터리도
남기지 않음, 메시 응답(모든 면이 자기 평면에서 메시되고 면과 이름이 표시 응답과 같음)을
확인합니다. platform-install 워크플로가 이 가운데 프로세스 수준 시험(`tests/simcase/test_studio_mesh3d_process.py`, HTTP 클라이언트 없음)을 Linux, macOS, Windows에서 돌립니다.

그 밖의 시험: 단면 윤곽이 평면 위에 있고 면마다 정확한 잘린 길이를 가짐(카드의 평면
네 개, 하나는 via 구멍의 모서리를 따름), 거부 메시지가 엔진의 문구 그대로임, 자원
경로가 자기 파일만 보냄, 순수 도우미(`tests/simcase/studio_model3d.cjs`: 카메라 계약,
조작, 면 고르기, 보이기).

브라우저 검사는 로컬에서 돌립니다(Playwright와 실행 가능한 Chromium 필요, CI 밖).
실행 중인 Studio에 대고 돌립니다.

```sh
python -m simcase.studio --no-browser --port 8765 &
node tools/studio_browser/model3d_view_browser.mjs http://127.0.0.1:8765 out-dir
node tools/studio_browser/model3d_mesh_browser.mjs http://127.0.0.1:8765 out-dir-mesh
```

W14(실행), 2026-11-28 Linux(Xeon 2.1 GHz, CPU 4개)에서 TestClient로 기록:

| 경우 | 실행(메시와 풀이) | 겉면 지도 | z = 505 µm 단면 |
|---|---|---|---|
| 열 카드, 40 µm: 사면체 6,774 | 2.1초 | 3 ms, 0.10 MB | 24 ms, 0.05 MB |
| 열 카드, 6.4 µm(추정 586,395, 한도 아래 가장 큼): 사면체 468,472 | 126초 | 13 ms, 1.77 MB | 123 ms, 0.30 MB |

실행 테스트는 프로세스 전 거부(종류가 아님, 읽기의 거부, 추정 한도), 429, 프로세스 없는 보관 메시 재사용(E1의
**Mesh** 뒤에도), 영역 이름으로 거부하는 고정 온도 없는 묶음, 정확한 판과 비교한 탐침(1e-10 K)과 영역 밖 탐침,
값, 내보내기 머리 줄, 기록도 확인합니다. `tests/simcase/test_studio_heat3d_process.py`(platform-install, Linux,
macOS, Windows)는 HTTP 없이 mesh 단계의 실행을 취소합니다.

## 한계

- 5단계 slice 1처럼 상자와 슬래브 층만, 읽기 전용(3D에서 기능 편집 없음).
- 메시는 meshloom의 것(실험적)이고 품질도 meshloom의 것입니다. 추정은 엔진의 T이며
  실제 개수와 다릅니다(카드: 추정 20,160개, 실제 23,652개). 단계는 Studio가 아는
  것이고, meshloom 안의 진행은 보여 줄 수 없습니다.
- 보관한 메시는 서버 메모리에 있고 서버와 함께 사라집니다. 모델 작업 공간은 아직 메시를
  보여 주지 않습니다.
- 실행의 풀이는 중단할 수 없습니다. 풀이 중 Cancel은 풀이가 돌아오면 결과를 버립니다. 최근 실행 여덟 개의
  메시, 해, 응답을 메모리에 둡니다.
- meshloom builder 모양(원통, 구)의 구성 요소는 정확한 복합체가 아니라 표시 모양으로 그립니다. 그린 고리와
  구는 정확한 곡면에서 표시 규칙의 한계(W2) 안에 있고, 메시는 자기 크기 안에서 이를 따릅니다. 곡면 모양 면에서는
  아직 선택을 만들 수 없습니다("Use for → New selection"은 엔진의 문구로 거부하며, builder 경로는 선택이나 경계
  태그를 받지 않음). 경계 이름은 물리 필드에서 씁니다(예: `z0`, `z1`, `via.bottom`의 `prescribed_temperature`).
- `layers` 기능 하나만 가진 구성 요소(E1)는 (Mesh와 Run 모두) `meshine.extrude`로 메시하고
  `evaluate3d`는 거부합니다. 보기는 공개 함수 `simcase.display_complex3d`에서 복합체를
  받으며, 이 함수는 그런 구성 요소에 meshloom 경로가 만들 복합체를 만듭니다.
- 요청마다 서버에서 구성 요소 전체를 평가하고, CPU 면 고르기는 보이는 삼각형을 모두
  봅니다(이 문서들의 수백 개에는 충분함).
- 단면은 한쪽을 지우고 윤곽을 그리며, 잘린 영역은 메우지 않습니다.
- 캔버스는 창 너비 1300 px부터 720 × 504 CSS px, 그보다 좁으면 열 너비에 10:7입니다.
  브라우저 검사는 Linux의 headless Chromium에서 소프트웨어 GL로만 돌렸습니다. 하드웨어
  GL에서 메시 보기의 프레임 시간은 여기서 재지 않았습니다.
