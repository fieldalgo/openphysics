# 3D 과도 열전도

[English original](../../../../../packages/galerkin/transient_heat3d.md)

`galerkin.transient_heat3d.solve_transient_heat_3d`는 좌표 단위가 m인 적합
`Mesh3D`에서 P1 사면체, 일관 열용량 행렬, 후진 오일러 적분을 사용합니다.
`thermal_conductivity`는 W/(m K), `volumetric_heat_capacity`는 J/(m³ K)이며,
각각 양의 스칼라 또는 모든 재료 영역을 포함하는 매핑입니다. `time`에는
엄격히 증가하는 초 단위 시각이 두 개 이상 필요하며 구간 길이는 서로 달라도
됩니다. `initial_temperature`는 N개 절점의 K 단위 배열입니다.

`prescribed_temperature`는 외부 절점별 고정 온도이며 초기값과 일치해야 합니다.
`inward_heat_flux`는 외부 면 태그별 유입 열유속(W/m²)입니다. `convection`은
태그별 `(h, ambient_temperature)`이며 단위는 W/(m² K)와 K입니다. 경계의
나머지 규칙은 [정상 솔버](thermal3d.md)와 같으며 완전 단열도 허용합니다.

`heat_source_density`의 단위는 W/m³이며 스칼라, 영역 매핑, 사면체 순서의 배열을
받습니다. 호출 가능 객체는 구간 중점 시각(초)을 받아 이 형식 중 하나를
반환합니다. 히터 전환 시각은 시간 격자에 포함합니다. 같은 구간 길이에서는
희소 행렬 분해를 재사용할 수 있습니다.

결과의 `time` (S,)과 `temperature` (S, N)는 초기 상태를 포함합니다. 각 절점
열률의 형태는 (S−1, N), 단위는 W입니다. 구간별 `heat_storage_rate`의 합은
수치 잔차 범위에서 `generated_heat_rate`와 `reaction_heat_rate`를 더하고
`outward_prescribed_heat_rate`와 `outward_convective_heat_rate`를 뺀 값입니다.
구간 길이를 곱하면 `stored_heat`의 변화량(J)이 됩니다. 반력 열률은 유입이
양수이며 자유 절점에서는 0입니다. `residual_heat_rate`는 저장·전도·유출 열률을
더하고 발생 열률을 뺀 값으로, 반력을 빼기 전의 잔차입니다.

단열 히터 전환의 닫힌형 온도와 열수지, 독립 일관 열용량 사면체 고유모드의
1차 시간 수렴, 혼합 경계 선형 평형 및 대류 경계 냉각을 검증했습니다.
두 재료로 된 물체의 일부에 열을 가하고 한 면을 대류로 냉각한 경우에는
scikit-fem으로 별도 조립해 불균일 시간 간격의 모든 시각과 절점 온도를 대조했습니다.
