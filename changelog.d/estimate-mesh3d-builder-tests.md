# Changed

## English

- `simcase`: tests: `estimate_mesh3d` is checked against `build_mesh3d` on cylinders and spheres in meshloom's builder shapes (C4 `via_in_slab`, C11 `nested_spheres`). The two give the same acceptance at 0.99× the limit and the same `E-MESH-ESTIMATE` refusal at 1.5×, and the estimate names route `builder`. A below-tolerance via is refused by both with `E-CONTRACT`, and a cylinder no builder takes in `recognise`'s words. [3D boxes, slab layers, cylinders and spheres](docs/packages/simcase/geometry_engine3d.md).

## 한국어

- `simcase`: 테스트: meshloom builder 모양의 원통과 구(C4 `via_in_slab`, C11 `nested_spheres`)에서 `estimate_mesh3d`를 `build_mesh3d`와 대조합니다. 한도의 0.99배에서는 둘 다 받고, 1.5배에서는 같은 문구의 `E-MESH-ESTIMATE`로 거부하며, 추정은 경로 `builder`를 밝힙니다. 허용 오차보다 가까운 비아는 둘 다 `E-CONTRACT`로, 어느 builder도 받지 않는 원통은 `recognise`의 문구로 거부합니다. [3D 상자, 판 층, 원통, 구](packages/simcase/geometry_engine3d.md).
