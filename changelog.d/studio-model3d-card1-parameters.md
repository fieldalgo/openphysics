# Changed

## English

- `simcase`: **Studio's card 1 holds the design's parameters (experimental).** Via in a layer stack now has `t_ox` = 10 µm, the oxide's thickness and the via's height, and `via_w` = 20 µm, the via's width. The via's x and y run from `100 - via_w / 2` to `100 + via_w / 2`, and its z from 500 to `500 + t_ox`. The model is the same: the check answers the same display, coverage and regions, `build_mesh3d` gives the same mesh, and a run gives the same temperature and reaction heat rate, bit for bit. Only the document's text and its digest change. `POST /api/model3d/check` also answers each box's evaluated `size`, which the tree shows (*20 × 20 × 10 µm*).

  [3D models](docs/packages/simcase/workspace.md#3d-models-experimental).

## 한국어

- `simcase`: **Studio의 카드 1이 설계의 매개변수를 담습니다(실험적).** Via in a layer stack은 이제 `t_ox` = 10 µm(산화막 두께이자 via의 높이)와 `via_w` = 20 µm(via의 너비)를 가집니다. via의 x와 y는 `100 - via_w / 2`부터 `100 + via_w / 2`까지, z는 500부터 `500 + t_ox`까지입니다. 모델은 같습니다: 검사는 같은 표시, 덮임, 영역을 답하고, `build_mesh3d`는 같은 메시를, 실행은 같은 온도와 반력 열률을 비트까지 같게 줍니다. 문서의 글과 그 digest만 바뀝니다. `POST /api/model3d/check`는 상자마다 계산된 `size`도 답하며, 트리가 그것을 보입니다(*20 × 20 × 10 µm*).

  [3D 모델](packages/simcase/workspace.md#3d-모델실험적).
