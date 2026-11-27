# Fixed

## English

- meshloom: **`mesh_plc` no longer takes time quadratic in the facet count to group its boundary faces by facet.** A surface with one facet per triangle spent about as long here as in meshing. The faces of each facet and their order are unchanged.

## 한국어

- meshloom: **`mesh_plc`가 경계 면을 facet별로 묶을 때 facet 수의 제곱에 비례하는 시간이 들지 않습니다.** 삼각형마다 facet이 하나인 곡면에서는 여기에 메시 생성만큼 시간이 들었습니다. 각 facet의 면과 그 순서는 그대로입니다.
