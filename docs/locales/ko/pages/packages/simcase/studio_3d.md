# Studio 3D 보기(실험적)

[English](../../../../../packages/simcase/studio_3d.md) | **한국어**

[문서 홈](../../index.md)

상태: **실험적.** 3D 보기는 버전 1 형상 문서([계약](geometry_document.md))의 `3d`
구성 요소를 `/geometry-lab`의 [형상 실험실](geometry_lab.md) 페이지에서 보여 줍니다.
읽기 전용이며, 5단계 엔진(`simcase.geometry_engine3d`)이 받는 것, 곧 상자와 `layers`
기능의 슬래브 층만 받으며, 이를 메시할 수 있습니다([메시](#메시)). 모델 작업 공간에는
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
  tetrahedra · about 30 s"로 보여 줍니다. T = 6.3 Σ V_r / h_r³를 유효숫자 두 자리로
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
    부피(`owned`, 둘 다 구성 요소 길이 단위의 세제곱), `coverage`. coverage는 `full`,
    `partial`("covered in part by N (id)"), `none`("covered by N (id); adds no region"),
    `outside`("outside the domain; adds no region")입니다. N은 그 상자와 겹치고 자기
    부피가 남은 뒤쪽 기능 번호(1부터)입니다. 모두 복합체로 pm 단위에서 정확히
    계산합니다.
  - `parameters`: SI 값, 단위, 적은 값, 그 파라미터 이름을 쓰는 구성 요소 필드
    `used_by`.
  - `regions`, `selections`, 그리고 `display` 아래의 표시 응답.
- 거부는 `{"ok": false, "refused": <엔진 메시지 그대로>, "code", "path",
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

## 한계

- 5단계 slice 1처럼 상자와 슬래브 층만, 읽기 전용(3D에서 기능 편집 없음).
- 메시는 meshloom의 것(실험적)이고 품질도 meshloom의 것입니다. 추정은 엔진의 T이며
  실제 개수와 다릅니다(카드: 추정 20,160개, 실제 23,652개). 단계는 Studio가 아는
  것이고, meshloom 안의 진행은 보여 줄 수 없습니다.
- 보관한 메시는 서버 메모리에 있고 서버와 함께 사라집니다. 모델 작업 공간은 아직 메시를
  보여 주지 않습니다.
- `layers` 기능 하나만 가진 구성 요소(E1)는 `meshine.extrude`로 메시하고
  `evaluate3d`는 거부합니다. 보기는 공개 함수 `simcase.display_complex3d`에서 복합체를
  받으며, 이 함수는 그런 구성 요소에 meshloom 경로가 만들 복합체를 만듭니다.
- 요청마다 서버에서 구성 요소 전체를 평가하고, CPU 면 고르기는 보이는 삼각형을 모두
  봅니다(이 문서들의 수백 개에는 충분함).
- 단면은 한쪽을 지우고 윤곽을 그리며, 잘린 영역은 메우지 않습니다.
- 캔버스는 창 너비 1300 px부터 720 × 504 CSS px, 그보다 좁으면 열 너비에 10:7입니다.
  브라우저 검사는 Linux의 headless Chromium에서 소프트웨어 GL로만 돌렸습니다. 하드웨어
  GL에서 메시 보기의 프레임 시간은 여기서 재지 않았습니다.
