# Changed

## English

- meshloom: **the region, rounding and repair stage of `mesh_plc` keys its face and node tables with the fast hasher of facet triangulation**, not the standard randomly seeded one; no result depends on their order. On the needle readiness input at 3e5 faces the stage falls from 17.5 to 9.4 s; meshes are unchanged.

## 한국어

- meshloom: **`mesh_plc`의 영역·rounding·수리 단계는 면과 절점 표에 facet 삼각 분할의 빠른 해시를 씁니다.** 표준 해시는 무작위 시드를 씁니다. 결과는 표의 순서에 기대지 않습니다. 면 3e5개 needle 사전 점검 입력에서 이 단계가 17.5 s에서 9.4 s로 줄었고, 메시는 같습니다.
