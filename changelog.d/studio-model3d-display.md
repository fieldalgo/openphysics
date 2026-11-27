# Added

## English

- `simcase`: **Studio answers a display tessellation and section outlines of a 3d component (experimental).** `GET`/`POST /api/model3d/display` builds triangles on the server from the exact stage 5 complex (boxes and slab layers), not from the mesh: each face is split exactly into rectangles, every triangle carries its face's id, and each face lists its provenance names; positions are float32 metres from the domain centre. `POST /api/model3d/section` answers the exact outline where a plane x, y or z = const cuts the faces. Refusals carry the engine's words. Checks W1 (every triangle on its exact face, on E1, the card document and 50 G1 sets: 0 and 0), W2 (face areas, worst 9.5e-8 against 1e-6) and W15 (one SHA-256 over 3 processes); the expected picks of W3 are written from an independent ray cast on the exact complex. [3D view](docs/packages/simcase/studio_3d.md).

## 한국어

- `simcase`: **Studio가 3d 구성 요소의 표시용 삼각형과 단면 윤곽을 답합니다(실험적).** `GET`/`POST /api/model3d/display`는 메시가 아니라 정확한 5단계 복합체(상자와 슬래브 층)로 서버에서 삼각형을 만듭니다. 면마다 직사각형으로 정확히 나누고, 모든 삼각형이 자기 면의 id를 가지며, 면마다 출처 이름을 나열합니다. 위치는 영역 중심에서의 float32 미터입니다. `POST /api/model3d/section`은 평면 x, y 또는 z = 상수가 면을 자르는 정확한 윤곽을 답합니다. 거부 메시지는 엔진의 문구 그대로입니다. 검사 W1(E1, 카드 문서, G1 집합 50개에서 모든 삼각형이 정확한 면 위: 0과 0), W2(면 넓이, 최대 9.5e-8, 기준 1e-6), W15(프로세스 3개에서 SHA-256 하나). W3의 기대 선택은 정확한 복합체에 대한 독립 광선 투사로 적었습니다. [3D 보기](packages/simcase/studio_3d.md).
