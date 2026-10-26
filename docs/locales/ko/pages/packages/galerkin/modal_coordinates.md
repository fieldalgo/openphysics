# 모드 복소 좌표

[English](../../../../../packages/galerkin/modal_coordinates.md)

저수준 API는 `exp(+i omega t-i beta z)`를 사용합니다.
`galerkin.mode_coordinates.mode_coordinates(mesh, thickness={"left": 1.0,
"right": 1.0}, strength=3.0, order=2)`는 요소 중심 Jacobian `(sx, sy, h)`,
물리 영역 마스크와 경계를 반환합니다. 두께 단위는 메시 길이 단위이며
계산 영역에 PML 띠가 포함됩니다. 재료도 PML 안까지 연장해야 합니다.
늘림은 `s=1-i strength (depth/thickness)**order`이고 차수는 2, 3, 4입니다.
메시는 물리 영역과 PML을 모두 분해해야 합니다.

일정 반경 굽힘은 `bend_radius`, `bend_axis="x"` 또는 `"y"`,
`bend_origin`으로 지정합니다. 선택한 축이 바깥 방향이며 원점에서 반경이
양수입니다. 전파 거리는 기준 호 길이 `z=R theta`이고 전체 영역의 반경이
양수여야 합니다. `h=1+(q_tilde-bend_origin)/bend_radius`에는 PML 내부의
적분된 복소 좌표도 들어갑니다. 곡률이 일정한 모델입니다.

`coordinates.factors`를 `galerkin.solve_modes` 또는 `assemble_mode_system`의
`coordinate_factors`에 전달합니다. 벡터식은 유전율과 투자율을 함께
변환합니다. 반환 edge/nodal 계수는 계산 좌표의 공변 성분입니다.
PML 밖의 물리 종방향 전기장은 `1j*ez/h`입니다.
`solve_scalar_coordinates`는 scalar Helmholtz 근사의 복소 지수와 절점장을
반환합니다. 불변 축 TE slab 편광에서는 원통 굽힘까지 정확한 식이나,
일반적인 2D 고대비 도파관에서는 근사입니다.

두 솔버 모두 복소 비Hermitian pencil에 일반 shift-invert를 사용합니다.
진폭은 임의이며 반환 후보를 물리 극점으로 인증하지 않습니다. PML 인공
모드가 있으므로 메시·물리 창·PML 두께·강도를 각각 바꿔 검증해야 합니다.
단일 계산은 안정성을 검증하지 않습니다. 수동 순방향 극점의 유효굴절률
허수부는 음수입니다. 총 감쇠에는 흡수와 방사가 포함되며 둘을 분리하지 않습니다.

현재 검증은 독립 outgoing TE/TM slab 해석해·정렬 메시 수렴·PML/창 변화
(`test_pml_modes.py`), 별도 scikit-fem 조립과 dense QZ의 직선/굽힘
scalar/vector 비교(`test_crosscheck_skfem_pml_modes.py`)입니다. 동일 이산화
상대 기준은 1e-9이며 조립 일치는 물리 수렴을 대신하지 않습니다.
문서 입력과 Studio의 상위 계약은 이 기능 브랜치에서 개발 중입니다.
