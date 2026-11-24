# Fixed

## English

- Studio: **over 16 MiB, the header no longer says every field is kept for recovery.** Browser recovery of an optical session over 16 MiB keeps the fields of the selected and pinned runs only; the header and the save indicator now say *kept for recovery in this browser without the fields of 5 runs*, as the heated model already did for its maps, where they read *kept for recovery in this browser*. The Messages line now reads *Session is now 22 MB, over the 16 MiB (16.8 MB) limit. File › Save will ask whether to keep the fields of the selected and pinned runs only (Run 6); the other runs keep n_eff, the TE fractions and the effective areas. Browser recovery already keeps only those fields.* and wraps. The limit, the session format and the recovery record are unchanged. [Workspace](docs/packages/simcase/workspace.md).

## 한국어

- Studio: **16 MiB를 넘으면 헤더가 모든 장이 복구용으로 보존된다고 하지 않습니다.** 16 MiB를 넘는 광학 세션의 브라우저 복구는 선택·고정 실행의 장만 보존합니다. 헤더와 저장 표시가 *kept for recovery in this browser* 대신, 가열 모델이 이미 맵에 대해 그랬듯 *kept for recovery in this browser without the fields of 5 runs*라고 말합니다. Messages 줄은 이제 *Session is now 22 MB, over the 16 MiB (16.8 MB) limit. File › Save will ask whether to keep the fields of the selected and pinned runs only (Run 6); the other runs keep n_eff, the TE fractions and the effective areas. Browser recovery already keeps only those fields.*이며 줄바꿈됩니다. 한도, 세션 형식, 복구 기록은 그대로입니다. [워크스페이스](packages/simcase/workspace.md).
