# 지정 온도에서의 3D 열탄성

[English](../../../../../packages/galerkin/thermoelasticity3d.md) | **한국어**

`galerkin.thermoelasticity3d.solve_thermoelasticity_3d`에 미터 단위
`Mesh3D`와 같은 메시의 절점 온도를 전달합니다. 온도 배열은 메시 절점 순서의
`(N,)` 배열이며 단위는 K입니다. `stress_free_temperature`는 K 단위
스칼라입니다. 두 온도 입력은 유한한 비음수입니다.
`linear_expansion_coefficient`(1/K), `youngs_modulus`(Pa),
`poisson_ratio`는 각각 스칼라 또는 재료 영역 이름별 매핑입니다.
팽창계수는 부호를 가질 수 있습니다.

사면체의 P1 평균 온도는 네 절점 온도의 산술평균입니다. 단위 텐서에
α(mean(T) − Tref)를 곱해 요소 자유팽창 변형률을 구합니다. 탄성 솔버는 전체
변형률에서 자유팽창 변형률을 빼 응력을 계산합니다.
`prescribed_displacement`는 `(절점, 성분)`을 미터 단위 값에 대응시킵니다.
`body_force_density`(N/m³)와 면 태그별 `traction`(Pa)은 탄성 솔버의
규약을 따릅니다. 표면력은 전체 물리 응력과 외향 법선의 곱입니다.

결과는 미터 단위 변위 `(N, 3)`와 요소별 전체 변형률·응력 `(T, 3, 3)`을
담습니다. 두 텐서는 대칭이며 물리 전단변형률과 인장 양수의 Pa 응력을
사용합니다. 지지점 반력의 단위는 N입니다.

독립 기준 시험은 균일 자유팽창, 완전 구속된 단위 사면체의 수압 응력
−E α ΔT/(1 − 2ν), 그리고 체적과 응력 및 각 절점 형상함수 기울기의 곱으로 구한
지지점 반력을 비교합니다. 온도 변화 0과 재료 영역별 부호 있는 열팽창도 검사합니다.
