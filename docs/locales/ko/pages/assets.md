# 포함된 이미지·fixture·데이터

[English](../../../assets.md) | **한국어**

이 목록은 포함된 비코드 자산을 저장소 이력과 생성 입력에 연결합니다. 아래 파일은
저장소에만 있고 패키지 sdist·wheel에는 들어가지 않습니다. 자체 그림,
화면 캡처와 fixture에는 저장소의 [Apache-2.0](../../../../LICENSE)가 적용되며,
별도로 명시한 자료는 [NOTICE](../../../../NOTICE)와 패키지 고지의 조건을 유지합니다.
과거 그림은 설명 자료이며 새 검증 실행의 결과가 아닙니다.

| 자산 | 출처와 재현 입력 |
|---|---|
| `packages/gmshio/examples/hadley_rib_mesh.png` | `packages/gmshio/examples/hadley_rib_mesh.py`의 예제 메시 그림 |
| `packages/meshine/examples/compare_with_gmsh.png` | `packages/meshine/examples/compare_with_gmsh.py`의 예제 메시 비교 |
| `packages/physmat/examples/materials.png` | `packages/physmat/examples/plot_materials.py`의 재료 함수 그래프. 광학 데이터는 `packages/physmat/NOTICE`의 조건을 유지함 |
| `packages/simcase/docs/geometry.png`, `mesh.png`, `results.png` | 자체 Studio의 이전 화면과 SOI-strip 예제 캡처. UI와 함께 커밋 `f44d7f8373f09ba9a7dbcd04066a0087485a3fd2`에 도입됐고 패키지 이름 변경 뒤에도 보존됨 |
| `packages/simcase/examples/soi_strip_results.png` | 문서 실행기·입력과 함께 커밋 `07d4a89`에 도입한 SOI-strip 예제 그림. 현재 그래프 생성 경로는 `packages/simcase/src/simcase/runner.py` |
| `tests/gmshio/data/unit_square.geo`, `unit_square.msh` | reader·검사와 함께 커밋 `b2fe26a`에 도입한 단위 정사각형 형상과 메시 fixture. `.geo`에 점·변·physical tag를 명시함 |

공개 검토에서 simcase 그림 네 개를 직접 열어 자체 UI·예제 내용과 대조했습니다.
그림의 예전 이름과 수치는 유지합니다. 이번 검토에서 그림을 byte 단위로 재생성하거나
메시 생성기를 다시 실행하지는 않았습니다. Git 작성자, 함께 도입된 이력과 해당
구현을 출처 근거로 기록합니다.

광학 테이블과 분산 계수의 출처는 `physmat._tables.REFERENCES`, 재료 source 문자열과
[physmat/NOTICE](../../../../packages/physmat/NOTICE)에 기록합니다. upstream
refractiveindex.info 데이터베이스는 CC0 1.0입니다. 출판된 benchmark 수치는
[galerkin-refsol/NOTICE](../../../../packages/galerkin-refsol/NOTICE)에 인용합니다.
handbook 값으로 표시된 대표 열·기계 상수는 근사 예제 입력입니다. 모든 값에 특정
handbook 판본을 명시한 것은 아니므로 인증된 측정값이나 RII 데이터로 표현하면 안 됩니다.

Gmsh는 별도로 설치하고 실행파일·파일 교환으로 호출합니다. 프로그램 라이선스와
수치 메시 출력은 구분합니다. 이 fixture나 이미지에 upstream solver 구현을 포함하지 않습니다.
