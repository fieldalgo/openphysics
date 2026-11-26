# Fixed

## English

- Studio: **the Library's restore box appears only once every record kept in this browser has been read**, so its first offer is final. Before, after a reload, **Restore newest from this browser** could be shown and clicked while the earlier records were still being read: for a project with both models it restored one model, and offered both a moment later. Until the records are read, the Library shows Open file… and the cards without the box. The strings, the order of the offers, the first screen and **Not now** are unchanged. No session, project or recovery format change. `tests/simcase/studio_restore_offer_race.cjs` and the project browser check's R20 cover it. [Workspace](docs/packages/simcase/workspace.md#first-optical-study).

## 한국어

- Studio: **Library 복원 상자는 이 브라우저에 보관된 기록을 모두 읽은 뒤에만 나타나므로** 처음 보이는 제안이 최종입니다. 전에는 새로고침 뒤 이전 기록을 읽는 동안 **Restore newest from this browser**가 보이고 눌릴 수 있었고, 두 모델이 있는 프로젝트에서 한 모델만 복원했다가 잠시 뒤 두 모델을 제안했습니다. 기록을 읽기 전까지 Library는 상자 없이 Open file…과 카드를 보여 줍니다. 문구, 제안 순서, 첫 화면, **Not now**는 그대로입니다. 세션, 프로젝트, 복구 형식은 바뀌지 않습니다. `tests/simcase/studio_restore_offer_race.cjs`와 project 브라우저 검사의 R20이 확인합니다. [워크스페이스](packages/simcase/workspace.md#첫-광학-해석).
