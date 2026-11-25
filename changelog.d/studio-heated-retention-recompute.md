# Added

## English

- Studio: **Recompute Run N's maps** brings back the maps of a heated run that keeps its values only. It sends the run's stored document, checks the node and triangle counts, the mesh check and the iteration counts exactly and n_eff, the heat temperature range, the coupling differences and the iteration residuals to 1e-12 relative (1e-15 absolute below 1e-3), and on a match attaches the maps to the same run (its number, name, pin and stored values unchanged); otherwise the run is unchanged and Messages names the first value that differs. Measured single-threaded: the template, its 4-mode and 0.12 µm variants and the heated slab example recompute to the same maps bit for bit. [Workspace](docs/packages/simcase/workspace.md#keeping-heated-runs-values-and-maps).

## 한국어

- Studio: **Recompute Run N's maps**가 값만 보관한 가열 실행의 맵을 되돌립니다. 실행에 저장된 문서를 보내고, 절점·삼각형 개수, 메시 검사, 반복 횟수는 정확히, n_eff, 열 온도 범위, 결합 차이, 반복 잔차는 상대 1e-12(1e-3 미만은 절대 1e-15)로 확인하며, 맞으면 같은 실행에 맵을 붙입니다(번호, 이름, 고정, 저장된 값은 그대로). 아니면 실행은 그대로이고 Messages가 처음 다른 값을 밝힙니다. 단일 스레드 측정: 템플릿, 그 4모드·0.12 µm 변형, 가열 슬래브 예제는 비트까지 같은 맵으로 재계산됩니다. [작업 공간](packages/simcase/workspace.md#가열-실행-보관-값과-맵).
