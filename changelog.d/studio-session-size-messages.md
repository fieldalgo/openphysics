# Changed

## English

- Studio: **the optical session's size messages name the runs that are over the limit and say what Save will do.** When a new run makes the session go over 16 MiB, its result message adds *Session is now 18 MB, over the 16 MiB limit: File › Save will ask whether to keep the fields of the selected and pinned runs only.*, or, when Save would refuse, the refusal followed by *Browser recovery is off.* (the round-18 recovery line is then not repeated). The refusal names the selected run and the pinned runs apart and says *Unpin* only when a pinned run is among them; a selected run alone over the limit reads *Select a different run before saving, so this one is saved without its fields, or run it again with fewer modes.* Browser recovery's error uses the same words. Limits and file formats are unchanged. [Optical session files](docs/packages/simcase/workspace.md#optical-session-files-version-9).

## 한국어

- Studio: **광학 세션의 크기 메시지가 한도를 넘는 실행을 밝히고 저장이 무엇을 할지 알립니다.** 새 실행으로 세션이 16 MiB를 넘으면 그 결과 메시지에 *Session is now 18 MB, over the 16 MiB limit: File › Save will ask whether to keep the fields of the selected and pinned runs only.*가, 저장이 거부될 때는 거부 문구와 *Browser recovery is off.*가 붙습니다(이때 round 18의 복구 줄은 되풀이하지 않습니다). 거부 문구는 선택 실행과 고정 실행을 따로 밝히고, 그중 고정 실행이 있을 때만 *Unpin*을 말합니다. 선택 실행만 한도를 넘으면 *Select a different run before saving, so this one is saved without its fields, or run it again with fewer modes.*입니다. 브라우저 복구 오류도 같은 문구를 씁니다. 한도와 파일 형식은 그대로입니다. [광학 세션 파일](packages/simcase/workspace.md#광학-세션-파일버전-9).
