# Fixed

## English

- Studio browser check: **the multiphysics session script waits for the model's solve order before it uses the tree.** Opening the Heated silicon waveguide template posts *Heated silicon waveguide ready.* as the model's check is sent, and a tree item's accessible name gains *solve order 1* only when the check's reply arrives; stage S8 once looked the item up in between and found none (it passed on a rerun). The template step now also waits for the tree's solve-order badge. No assertion changes. [Development guide](docs/development.md#what-ci-runs).

## 한국어

- Studio 브라우저 검사: **multiphysics 세션 스크립트가 트리를 쓰기 전에 모델의 풀이 순서를 기다립니다.** Heated silicon waveguide 템플릿을 열면 모델 검사를 보내면서 *Heated silicon waveguide ready.*가 나오고, 트리 항목의 접근성 이름에는 검사 응답이 온 뒤에야 *solve order 1*이 붙습니다. S8 단계가 그 사이에 항목을 찾아 하나도 찾지 못한 적이 있습니다(다시 돌리니 통과). 이제 템플릿 단계가 트리의 풀이 순서 배지도 기다립니다. 바뀌는 단언은 없습니다. [개발 안내](development.md#ci가-돌리는-것).
