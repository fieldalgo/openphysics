# Studio 3D 보기(실험적)

[English](../../../../../packages/simcase/studio_3d.md) | **한국어**

[문서 홈](../../index.md)

상태: **실험적.** 3D 보기는 버전 1 형상 문서([계약](geometry_document.md))의 `3d`
구성 요소를 `/geometry-lab`의 [형상 실험실](geometry_lab.md) 페이지에서 보여 줍니다.
읽기 전용이며, 5단계 엔진(`simcase.geometry_engine3d`)이 받는 것, 곧 상자와 `layers`
기능의 슬래브 층만 받습니다. 모델 작업 공간에는 아직 나오지 않습니다. 페이지, 조작,
HTTP 응답은 어느 릴리스에서든 바뀔 수 있습니다.

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

메시 모서리는 그리지 않습니다. 이 보기는 메시가 아니라 정확한 형상을 보여 줍니다.

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
| W12 | 1440 × 900과 390 × 844 첫 화면: 콘솔 오류 없음, CSP 위반 없음, 캔버스가 보이고 비어 있지 않음, 390에서 가로 스크롤 없음, Tab으로 면 목록에 닿음, 화면 저장 | 모두 성립 | 모두 성립(면 목록까지 Tab 17번) | 같음 |
| W13 | 키보드만으로 회전, 축 보기, 면 목록에서 `via.z1` 고르기, 포인터 이벤트 없음 | 완료 | 완료, 포인터 이벤트 0 | 같음 |
| W15 | 새 서버 프로세스 3개에서 표시 응답의 SHA-256 | 같음 | 같음 | `tests/simcase/test_studio_model3d.py` |

그 밖의 시험: 단면 윤곽이 평면 위에 있고 면마다 정확한 잘린 길이를 가짐(카드의 평면
네 개, 하나는 via 구멍의 모서리를 따름), 거부 메시지가 엔진의 문구 그대로임, 자원
경로가 자기 파일만 보냄, 순수 도우미(`tests/simcase/studio_model3d.cjs`: 카메라 계약,
조작, 면 고르기, 보이기).

브라우저 검사는 로컬에서 돌립니다(Playwright와 실행 가능한 Chromium 필요, CI 밖).
실행 중인 Studio에 대고 돌립니다.

```sh
python -m simcase.studio --no-browser --port 8765 &
node tools/studio_browser/model3d_view_browser.mjs http://127.0.0.1:8765 out-dir
```

## 한계

- 5단계 slice 1처럼 상자와 슬래브 층만, 읽기 전용(3D에서 기능 편집 없음), 메시 보기는
  아직 없음.
- `layers` 기능 하나만 가진 구성 요소(E1)는 `meshine.extrude`로 메시하고
  `evaluate3d`는 거부합니다. 보기는 공개 함수 `simcase.display_complex3d`에서 복합체를
  받으며, 이 함수는 그런 구성 요소에 meshloom 경로가 만들 복합체를 만듭니다.
- 요청마다 서버에서 구성 요소 전체를 평가하고, CPU 면 고르기는 보이는 삼각형을 모두
  봅니다(이 문서들의 수백 개에는 충분함).
- 단면은 한쪽을 지우고 윤곽을 그리며, 잘린 영역은 메우지 않습니다.
- 캔버스는 창 너비 1300 px부터 720 × 504 CSS px, 그보다 좁으면 열 너비에 10:7입니다.
  검사는 Linux의 headless Chromium에서만 돌렸습니다.
