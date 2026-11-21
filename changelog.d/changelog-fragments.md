# Changed

## English

- Contributing: **a change records its changelog entry as a fragment**, `changelog.d/<slug>.md`, with English and Korean bullets under one Keep a Changelog category, instead of editing this file, so concurrent PRs no longer conflict at the top of `[Unreleased]`. `tools/changelog.py --check` checks every fragment's name, category, both languages and links (in `linux-py312`); `--assemble`, run by the version-change PR, inserts the bullets at the top of each category's subsection of `[Unreleased]` in both changelogs and deletes the fragments, and `tools/check_release_version.py --tag` refuses a release while fragments remain. Lines already here stay where they are. [Changelog fragments](docs/development.md#changelog-fragments).

## 한국어

- 기여: **변경은 변경 기록 항목을 조각 `changelog.d/<slug>.md`로 남깁니다.** 이 파일을 직접 고치지 않고 Keep a Changelog 분류 하나 아래 영어·한국어 항목을 쓰므로, 동시에 열린 PR이 `[Unreleased]` 맨 위에서 더는 충돌하지 않습니다. `tools/changelog.py --check`가 조각마다 이름, 분류, 두 언어, 링크를 확인하고(`linux-py312`), 버전 변경 PR이 돌리는 `--assemble`은 두 변경 기록 `[Unreleased]`의 분류별 하위 절 맨 위에 항목을 넣고 조각을 지웁니다. `tools/check_release_version.py --tag`는 조각이 남아 있으면 릴리스를 거부합니다. 이미 있는 줄은 그 자리에 그대로 둡니다. [변경 기록 조각](development.md#변경-기록-조각).
