# Fixed

## English

- Studio: **browser recovery names the project file.** A restore of a record that was the same as its project file left the header at *Untitled project · not saved to a file* and Save suggested `untitled-project.json` (a P3 regression of round 14's Q3): the project now names that file and its name again. A project save now relinks the stored record of every model it wrote, shown or not, so the heated model's card names the newest project file instead of an older one. The record's `savedFile` gains an optional browser-only `projectName`; no file format changes. [Workspace](docs/packages/simcase/workspace.md).

## 한국어

- Studio: **브라우저 복구가 프로젝트 파일을 가리킵니다.** 프로젝트 파일과 같았던 기록을 복원해도 헤더가 *Untitled project · not saved to a file*로 남고 Save가 `untitled-project.json`을 제안했습니다(14차 Q3의 P3 회귀). 이제 프로젝트가 그 파일과 이름을 다시 가리킵니다. 프로젝트 저장은 보이는 모델이든 아니든 저장한 모든 모델의 기록을 다시 연결하므로, 가열 모델 카드가 예전 파일 대신 가장 새 프로젝트 파일을 말합니다. 기록의 `savedFile`에 브라우저 전용 선택 키 `projectName`이 생겼으며 파일 형식은 바뀌지 않습니다. [워크스페이스](packages/simcase/workspace.md).
