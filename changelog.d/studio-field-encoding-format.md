# Added

## English

- Studio reads and writes optical session version 14: version 13 whose runs may keep a compact field (encoding `f32-base64-v1`). Samples are stored as float32, node coordinates as float64 and triangles as uint32, each as little-endian base64; a field's size follows exactly from its counts. A run with a compact field also stores its TE fractions and effective areas. A session is written as version 14 only when a run is kept with a compact field; every other session is written as version 13, 12, 11, 10, 9 or 7, byte for byte. The reader refuses an unknown encoding, other keys, counts outside the reader's limits, base64 that is not canonical or of the wrong length, a value that is not finite and a triangle that names a missing or repeated node, each by name with the run's number. A Studio before this one refuses a version 14 file as newer than it reads, alone or in a project file, and does not take over a browser-recovery record that holds one. [Workspace](docs/packages/simcase/workspace.md).

## 한국어

- Studio가 광학 세션 버전 14를 읽고 씁니다. 버전 13에 더해 실행이 압축 필드(인코딩 `f32-base64-v1`)를 담을 수 있습니다. 표본은 float32, 노드 좌표는 float64, 삼각형은 uint32로 각각 리틀 엔디언 base64로 저장하며, 필드 크기는 개수에서 정확히 정해집니다. 압축 필드를 가진 실행은 TE 비율과 유효 면적도 저장합니다. 압축 필드를 가진 채 보관된 실행이 있을 때만 버전 14로 쓰고, 그 밖의 세션은 지금처럼 버전 13, 12, 11, 10, 9, 7로 바이트 그대로 씁니다. 읽기는 모르는 인코딩, 다른 키, 읽기 한도를 벗어난 개수, 정규형이 아니거나 길이가 맞지 않는 base64, 유한하지 않은 값, 없는 노드나 같은 노드를 다시 가리키는 삼각형을 각각 실행 번호와 함께 이름을 밝혀 거부합니다. 이전 Studio는 버전 14 파일을 단독으로든 프로젝트 파일 안에서든 읽을 수 있는 것보다 새 파일로 거부하고, 그런 파일을 담은 브라우저 복구 기록을 넘겨받지 않습니다. [작업 공간](packages/simcase/workspace.md).
