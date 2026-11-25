# Fixed

## English

- Studio's line before a run ("If you run: Run 5 (…) keeps its values, not its fields") and the line without an estimate ("older runs' fields may not be kept") now count the sizes the result's arrival will apply. In a tab whose fields are still text, a result whose fields would not all fit as text makes every field single precision first, so the line names only the runs that would lose their fields even then. Before, it counted text sizes, so a tab that the next run converted (every field then kept) was told a run would lose its fields. [Workspace](docs/packages/simcase/workspace.md).

## 한국어

- 실행 전 줄("If you run: Run 5 (…) keeps its values, not its fields")과 추정이 없을 때의 줄("older runs' fields may not be kept")이 이제 결과가 도착할 때 적용할 크기로 셉니다. 필드가 아직 텍스트인 탭에서 필드를 모두 텍스트로 담을 수 없게 되는 결과는 먼저 모든 필드를 단정밀도로 바꾸므로, 줄은 그래도 필드를 잃을 실행만 밝힙니다. 전에는 텍스트 크기로 세어, 다음 실행에서 압축되어 모든 필드가 남는 탭에도 실행 하나가 필드를 잃는다고 했습니다. [작업 공간](packages/simcase/workspace.md).
