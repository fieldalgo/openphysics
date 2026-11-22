# Changed

## English

- `galerkin`: **a coefficient callback refused with a motion is now a `TypeError`.** With `motion=`, a callable conductivity, heat capacity, electrical conductivity, Young's modulus, Poisson ratio, expansion coefficient or stress-free temperature was refused with `ValueError`, while callable sources, boundary values and Dirichlet values raised `TypeError`. All of them are now a `TypeError`; the coefficient refusals are also still a `ValueError`, so existing `except ValueError` handlers keep catching them, and the messages are unchanged. Checked (N1, pre-registered): every callback refusal with a motion across steady, transient and 3D heat, electric conduction, elasticity and thermoelasticity is a `TypeError`, and the coefficient ones are a `ValueError` too. [Shape derivatives](docs/packages/galerkin/shape_derivative.md#refused).

## 한국어

- `galerkin`: **motion과 함께 거부하는 계수 콜백이 이제 `TypeError`입니다.** `motion=`에서 호출 가능한 전도도, 열용량, 전기 전도도, Young 계수, Poisson 비, 팽창 계수, 응력 없는 온도는 `ValueError`로 거부했고, 호출 가능한 열원·경계값·Dirichlet 값은 `TypeError`였습니다. 이제 모두 `TypeError`입니다. 계수 거부는 여전히 `ValueError`이기도 하므로 기존 `except ValueError` 처리기도 계속 잡으며, 메시지는 그대로입니다. 검사(N1, 사전 등록): 정상·과도·3D 열, 전기 전도, 탄성, 열탄성에서 motion과 함께 준 모든 콜백 거부가 `TypeError`이고, 계수 거부는 `ValueError`이기도 합니다. [형상 미분](packages/galerkin/shape_derivative.md#거부).
