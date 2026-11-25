# Added

## English

- Studio's browser checks compare the field view, the line profile and the field PNG of three closed T18 runs before and after the fields are kept at single precision (at most one colour level on at most 0.1 % of the pixels; measured: identical in 30 of 31 views, 4 pixels by one level in the other), and time the encoding in the browser (a field of 3 modes and 12,253 triangles encodes in about 11 ms; the tab of 11 fields, 13.6 MB as text, converts in about 68 ms). `tools/studio_field_encoding.mjs` measures the fields kept at 20 runs, Recompute in a compact tab, the sizes and deflate of compact fields. [Development guide](docs/development.md).

## 한국어

- Studio 브라우저 검사가 닫힌 T18 실행 셋의 장 보기, 단면, 장 PNG를 필드를 단정밀도로 보관하기 전후로 비교하고(픽셀의 0.1 % 이하에서 색 단계 최대 1; 측정: 31개 보기 중 30개는 같고 나머지 하나는 4픽셀이 1단계 다름), 브라우저에서 인코딩 시간을 잽니다(모드 3개, 삼각형 12,253개 장의 인코딩 약 11 ms; 텍스트로 13.6 MB인 필드 11개 탭의 변환 약 68 ms). `tools/studio_field_encoding.mjs`는 실행 20개에서 보관되는 필드, 압축 탭의 Recompute, 압축 필드의 크기와 deflate를 잽니다. [개발 안내](development.md).
