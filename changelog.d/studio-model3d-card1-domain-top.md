# Changed

## English

- `simcase`: **Studio's card 1 domain top follows the stack (experimental).** The domain's `zmax` is now `500 + t_ox + 100` (substrate + oxide + top silicon). Making the oxide 5 µm thick therefore moves the top to 605 µm, and `z1` stays the top face; before, 605–610 µm was void, and `z1` selected no face. At `t_ox` = 10 µm the model is unchanged bit for bit: the check, the mesh and a run are identical.

  [3D models](docs/packages/simcase/workspace.md#3d-models-experimental).

## 한국어

- `simcase`: **Studio의 카드 1 영역 위끝이 층을 따릅니다(실험적).** 영역의 `zmax`가 이제 `500 + t_ox + 100`(기판 + 산화막 + 위 실리콘)입니다. 그래서 산화막을 5 µm로 하면 위끝이 605 µm로 옮겨 가고 `z1`은 맨 위 면으로 남습니다. 전에는 605–610 µm가 빈 공간이었고 `z1`은 아무 면도 고르지 않았습니다. `t_ox` = 10 µm에서 모델은 비트까지 같습니다: 검사, 메시, 실행이 같습니다.

  [3D 모델](packages/simcase/workspace.md#3d-모델실험적).
