# Changed

## English

- `galerkin`: **`ground_modes` of the two-ground panel solvers is documented and tested as a compatibility argument.** `solve_two_ground_rectangle` and `solve_two_ground_rectangle_edges` (internal and in `galerkin.panel_electrostatics`) still accept it and still refuse values outside the integers 64–4096, so existing calls and stored controls keep working, but no result depends on it since the plane current Gram is integrated in physical space; a test checks that results are bit for bit equal for 64 and 4096. The unused mode count is no longer passed inside the solver. The corner solvers still use it as their Fourier count. [Two-ground panels](docs/packages/galerkin/two-ground.md).

## 한국어

- `galerkin`: **두 접지 panel 풀이기의 `ground_modes`를 호환용 인자로 문서화하고 시험합니다.** `solve_two_ground_rectangle`과 `solve_two_ground_rectangle_edges`(내부 및 `galerkin.panel_electrostatics`)는 여전히 이 값을 받고 64–4096 정수 밖의 값을 거절하므로 기존 호출과 저장된 제어값은 그대로 동작하지만, 접지판 전류 Gram을 실공간에서 적분한 뒤로는 어떤 결과도 이 값에 의존하지 않습니다. 시험은 64와 4096에서 결과가 비트 단위로 같은지 확인합니다. 풀이기 안에서는 쓰이지 않는 모드 수를 더는 넘기지 않습니다. 코너 풀이기는 여전히 이 값을 Fourier 개수로 씁니다. [두 접지 panel](packages/galerkin/two-ground.md).
