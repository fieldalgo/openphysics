# Added

## English

- `simcase`: **`shape_problem` takes mode documents with a modal PML.** An `em.modes2d` vector document with a `pml` gives the shape derivative of its kept modes' effective indices. The modes are chosen from the numbers on the moved mesh exactly as `run` chooses them, and the same eigensolve with the layer's factors of the moved mesh held fixed carries the derivative. The design velocity leaves the layer in place: it is zero on every node of an element whose coordinate factors are not 1, and its normal component is zero on the outer faces. A design that moves a point there is refused by name, and a `bend` stays refused. Checked (PM1-PM6, pre-registered): on the leaky-slab example as a version 1 document, the live index at t = 0 equals `run`'s (3.0e-15); dn_eff/dd matches a same-mesh central difference within 5.7e-9, JAX and PyTorch within 4.8e-15; against the analytic outgoing pole it is within 2.7e-4 (imaginary part 5.7e-4). [Design velocity](docs/packages/simcase/geometry_engine.md#design-velocity-stage-4).

## 한국어

- `simcase`: **`shape_problem`이 modal PML이 있는 모드 문서를 받습니다.** `pml`이 있는 `em.modes2d` 벡터 문서는 남긴 모드 유효 굴절률의 형상 미분을 줍니다. 모드는 `run`과 똑같이 움직인 메시의 수치로 고르고, 움직인 메시의 층 인자를 고정한 같은 고유값 풀이가 미분을 실어 나릅니다. 설계 속도는 층을 제자리에 둡니다. 좌표 인자가 1이 아닌 요소의 모든 노드에서 0이고, 바깥 면에서는 법선 성분이 0입니다. 그곳의 점을 움직이는 설계는 이름을 밝혀 거부하며 `bend`도 계속 거부합니다. 검사(PM1-PM6, 사전 등록): 버전 1 문서로 바꾼 누설 slab 예제에서 t = 0 live 지수가 `run`과 같고(3.0e-15), dn_eff/dd가 같은 메시 중앙 차분과 5.7e-9, JAX와 PyTorch가 4.8e-15 이내이며, 해석 외향 극점과 2.7e-4 이내입니다(허수부 5.7e-4). [설계 속도](packages/simcase/geometry_engine.md#설계-속도-4단계).
