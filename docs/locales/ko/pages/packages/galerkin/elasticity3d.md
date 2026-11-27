# 3차원 소변형률 탄성

[English original](../../../../../packages/galerkin/elasticity3d.md)

`galerkin.elasticity3d.solve_elasticity_3d`에 좌표 단위가 m인 적합 `Mesh3D`를
전달합니다. P1 사면체와 절점당 세 Cartesian 변위 성분으로 정적 등방성 선형탄성을
풉니다. `youngs_modulus`는 Pa(E > 0), `poisson_ratio`는 무차원(−1 < ν < 0.5)입니다.
스칼라 또는 모든 이름 있는 재료 영역에 값을 지정하는 매핑을 전달할 수 있습니다.

`prescribed_displacement`는 `(절점, 성분)`을 키로 사용하며 변위 단위는 m입니다.
성분 0, 1, 2는 각각 x, y, z입니다. 분리된 성분마다 병진 세 개와 회전 세 개를
구속해야 합니다. `body_force_density`는 N/m³ 단위의 일정한 Cartesian 벡터이고
`traction`은 외부 면 태그별 Pa 단위의 일정한 Cartesian 벡터입니다. 생략한 하중은
0입니다. 표면력은 물체에 가하는 단위 면적당 힘이며, 지정 변위 성분의 반력에도
기여할 수 있습니다.

결과는 절점 `displacement`(m)와 (T, 3, 3) 대칭 요소 텐서 `strain`·`stress`를
포함합니다. 변형률은 물리 전단 성분을 쓰는 전체 미소변형률입니다. 응력의 단위는
Pa이고 인장이 양수입니다. 절점 `applied_force`, `reaction_force`,
`residual_force`의 형태는 (N, 3)이고 단위는 N입니다. 잔차는 내력에서 가한
하중을 뺀 값입니다. 반력은 구속이 물체에 가하는 힘이며 자유 성분에서는 0입니다.

축 인장과 포아송 수축, 단순 전단, 힘과 모멘트 평형, 이차 제조해의 세 메시
세분화 수준을 검증했습니다. 체적력과 표면력을 함께 가한 독립 scikit-fem P1
해석으로 변위, 응력, 반력을 비교했습니다.
