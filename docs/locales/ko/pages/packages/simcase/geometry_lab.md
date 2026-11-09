# Studio 형상 실험실 (실험적)

[English](../../../../../packages/simcase/geometry_lab.md) | **한국어**

[문서 홈](../../index.md)

상태: **실험적.** 형상 실험실은 `/geometry-lab`에 있는 별도 Studio 페이지입니다. 버전 1 형상 블록을 가진
문서([계약](geometry_document.md))를 [정확 2D 엔진](geometry_engine.md)으로 바로 다룹니다. Studio가 버전 1 문서를
읽게 하는 첫 단계이며, `/workspace`의 [모델 작업공간](workspace.md)과 `/`의 기존 페이지는 바뀌지 않았고 이 페이지에
링크하지 않습니다. 페이지와 HTTP 응답은 어느 릴리스에서든 바뀔 수 있습니다.

## 사용

평소처럼 Studio를 띄우고 페이지를 엽니다.

```sh
python -m simcase.studio            # 그다음 http://127.0.0.1:8765/geometry-lab 열기
```

- **Start from**에서 동봉 예제(`examples/simcase/geometry_v1_soi_strip.json`,
  `geometry_v1_imprint_rib.json`, 페이지에 들어 있음)나 사각형 하나짜리 새 문서를 고르거나, **Open file**로 JSON
  문서를 엽니다.
- **Parameters**에 파라미터와 평가된 값이 나옵니다. `range`가 있고 숫자로 쓴 파라미터에는 슬라이더가 붙습니다.
  슬라이더 간격은 10의 거듭제곱(범위 안에 200칸 이상)이라 저장되는 값이 짧은 소수로 남습니다. 모든 파라미터에 숫자나
  식(`2 * t + 0.1`)을 받는 입력 칸이 있습니다. double로 담을 수 없는 수(`1e999`, `1e-400`)는 페이지에서 거부하고, 입력
  칸은 문서가 가진 값으로 돌아갑니다.
- 편집할 때마다 문서 전체를 서버로 보내고, 서버가 문서를 파싱해 구성 요소 하나를 평가합니다. 그림은 셀을 영역별로
  칠하고(빈 공간 셀은 칠하지 않음) 모든 곡선을 그립니다. 원호와 원은 그리기용으로만 점을 찍습니다. 영역, 이름 붙은
  선택, 경계 태그를 누르면 해당 셀이나 곡선이 강조되고, 강조는 새 응답마다 이름으로 다시 찾습니다. **Engine listing**은 같은 문서에 대해
  `python -m simcase geometry`가 출력하는 글입니다.
- 엔진이 거부한 문서는 마지막으로 받아들인 그림을 흐리게 남기고 엔진의 메시지를 그대로 보입니다. 메시지는 피처,
  선택 또는 파라미터 이름을 밝힙니다(예: `feature 'bow': its boundary crosses itself …`,
  `component 'xs': selection 'gold' selects nothing`).
- **Component**로 여러 구성 요소 중 하나를 고릅니다. 고르지 않으면 첫 `2d`·`axisymmetric` 구성 요소를 보입니다.
  `3d` 구성 요소는 이름을 밝혀 거부합니다.
- **Save JSON**은 편집한 문서를 그대로(2칸 들여쓰기 JSON) 내려받습니다. 서버에는 아무것도 저장하지 않습니다.

실험실은 물리 계산을 하지 않습니다. 저장한 문서는 `python -m simcase run`이나 각 물리 페이지의 경로로 실행합니다.

## 보내는 것과 받는 것

`POST /api/geometry-lab/evaluate`는 `{"doc": <문서>, "component": <이름 또는 null>}`을 받습니다.
`python -m simcase geometry`처럼 `units`와 `geometry` 블록만 읽으므로 물리가 없는 문서도 받습니다. 응답은 구성
요소의 셀, 곡선(문서 길이 단위의 점), 면적이 붙은 영역, 항목 번호가 붙은 선택, 경계 태그, 파라미터(쓴 값과 평가한
값), 반올림, 엔진 출력이 담긴 `{"ok": true, ...}`이거나 `{"ok": false, "refused": <메시지>}`입니다. 이 페이지를
위한 보기이며 저장 형식이 아니고 문서 계약에 속하지 않습니다.

페이지는 `/geometry-lab-assets/`의 자기 파일만 불러옵니다. 인라인 스크립트·스타일과 다른 출처는 없고, 페이지
응답에 `script-src 'self'`가 든 `Content-Security-Policy`가 붙습니다. Studio는 공개 이름
`simcase.parse_geometry`, `simcase.evaluate_geometry`, `simcase.GeometryError`로 엔진을 부릅니다.

## 검사

페이지를 쓰기 전에 등록했습니다.

| 검사 | 위치 |
|---|---|
| GL-1 두 예제에서 엔진 출력이 `python -m simcase geometry`와 같고, 영역·선택·곡선 출처·태그가 엔진과 같음 | `tests/simcase/test_studio_geometry_lab.py` |
| GL-2 파라미터 편집(범위 안 세 값과 식) 뒤 셀 면적·꼭짓점·곡선·선택이 새로 돌린 엔진 결과와 `==`로 같음 | 같은 파일 |
| GL-3 거부에 엔진 메시지가 그대로 실림: 자기 교차 path, 원 위에 없는 원호 끝, `3d` 구성 요소, 빈 선택, 파라미터 순환, 0.2 블록(CLI 문구) | 같은 파일 |
| GL-4 저장한 글이 편집한 문서와 같은 모델로 다시 파싱됨 | 같은 파일과 브라우저 검사 |
| GL-5 실제 브라우저: 두 시작 문서, 슬라이더·입력 편집, 거부, 저장에서 콘솔 오류와 정책 위반 없음 | `tools/studio_browser/geometry_lab_browser.mjs`(로컬, Playwright 필요, CI 밖) |
| GL-6 페이지의 순수 도우미 | `tests/simcase/studio_geometry_lab.cjs` |
| 문서 자체와 비교한 그리기 자료: 원호·원의 표본 점이 그 원 위에 있고 반시계 방향으로 돌며, 그린 루프의 면적이 엔진 면적과 2e-3 이내, nm·µm·mm에서 길이·면적 단위 | `tests/simcase/test_studio_geometry_lab.py` |
| GL-7 `/`와 `/workspace`가 실험실을 불러오거나 링크하지 않음, 실험실 모듈은 공개 이름만 가져옴 | `tests/simcase/test_studio_geometry_lab.py` |

## 한계

- 엔진 범위인 2D·축대칭 구성 요소만 다룹니다. 아직 피처나 선택은 편집하지 못하고 파라미터만 바꿉니다.
- 편집할 때마다 서버가 구성 요소 전체를 다시 평가합니다. 엔진 측정 시간은 [엔진 검증](geometry_engine.md#검증)에
  있습니다.
- 파일럿 페이지에서 링크하지 않으며, 설치한 wheel의 브라우저 검사에 들어 있지 않습니다.
- 로컬 Studio 서버용으로 만들었습니다. 거부 응답에는 제출한 문서로 만든 리더·엔진 메시지만 담기고, 그 밖의 오류는
  예외 문구 없는 일반 500입니다(시험으로 확인). Studio를 다른 사람에게 서비스하려면 요청 크기와 평가 시간 제한도
  필요하며, 이 페이지는 그 제한을 두지 않습니다.
