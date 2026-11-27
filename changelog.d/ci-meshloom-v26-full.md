# Changed

## English

- CI: **meshloom's V26 runs in full on main pushes.** Three jobs of `Validate packages` (`meshloom-v26-wheel`, `meshloom-v26`, `meshloom-v26-compare`) build one abi3 meshloom wheel, run V26 with C3 at h = 0.1 (`MESHLOOM_V26_FULL=1`) on Python 3.12 and 3.15, and require the same digests on both. They run on main pushes and manual dispatch only, so pull requests take no longer; on those events the required `tests` check needs them. Pull requests still run V26 without C3 on Python 3.12 in the source test parts. [Development guide](docs/development.md#what-ci-runs).

## 한국어

- CI: **meshloom V26이 main push에서 전체로 돕니다.** `Validate packages`의 job 세 개(`meshloom-v26-wheel`, `meshloom-v26`, `meshloom-v26-compare`)가 meshloom abi3 wheel 하나를 빌드합니다. 이 wheel로 C3 h = 0.1을 포함한 V26(`MESHLOOM_V26_FULL=1`)을 Python 3.12와 3.15에서 돌리고, 두 Python의 다이제스트가 같기를 요구합니다. 이 job들은 main push와 수동 dispatch에서만 돌아 pull request 시간은 늘지 않으며, 그때 필수 검사 `tests`가 이 job들을 요구합니다. pull request는 지금처럼 소스 시험 부분에서 C3 없이 Python 3.12로 V26을 돌립니다. [개발 안내](development.md#ci가-돌리는-것).
