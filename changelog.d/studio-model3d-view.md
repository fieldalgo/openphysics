# Added

## English

- `simcase`: **the geometry lab shows a 3d component in a read-only 3D view (experimental).** The page draws boxes and slab layers with three.js (served by Studio, no CDN) and Studio's own controls: rotate, pan, zoom, fit, six axis views and the isometric one, all from the keyboard too. A click picks a face by a CPU ray cast and the names panel lists its provenance names (for example `via.z1`, `stack.top.bottom`); a keyboard faces list reaches every face; regions can be hidden; a section keeps one side of a plane and draws the server's exact outline. The card document "Via in a layer stack" (µm) is a starter. Checks W3 (40/40 picks against the independent ray cast), W12 (first view at 1440 × 900 and 390 × 844) and W13 (keyboard only) pass in headless Chromium. [3D view](docs/packages/simcase/studio_3d.md).

## 한국어

- `simcase`: **형상 실험실이 3d 구성 요소를 읽기 전용 3D 보기로 보여 줍니다(실험적).** 페이지는 상자와 슬래브 층을 three.js(Studio가 보냄, CDN 없음)와 Studio 자체 조작으로 그립니다. 회전, 이동, 확대·축소, 맞춤, 축 보기 여섯 개와 등각 보기를 모두 키보드로도 할 수 있습니다. 클릭하면 CPU 광선 투사로 면을 고르고 이름 패널이 출처 이름(예: `via.z1`, `stack.top.bottom`)을 나열합니다. 키보드 면 목록으로 모든 면에 가고, 영역을 숨길 수 있으며, 단면은 평면 한쪽을 남기고 서버의 정확한 윤곽을 그립니다. 카드 문서 "Via in a layer stack"(µm)이 시작 문서로 들어 있습니다. 검사 W3(독립 광선 투사와 비교해 40/40), W12(1440 × 900과 390 × 844 첫 화면), W13(키보드만)이 headless Chromium에서 통과합니다. [3D 보기](packages/simcase/studio_3d.md).
