# openphysics

[English](../../../../../packages/openphysics/overview.md) | **한국어**

[영어·한국어 문서와 번역 상태](https://github.com/fieldalgo/openphysics/blob/main/docs/locales/ko/pages/index.md)

OpenPhysics 제품군을 한 번에 설치하는 배포판입니다. 자체 코드는 없고, 함께 릴리스되는
OpenPhysics 패키지 여섯 개를 의존성으로 요구합니다.

| 패키지 | 역할 |
|---|---|
| `galerkin` | 유한요소 엔진 |
| `galerkin-refsol` | 엔진 검증에 사용하는 해석적 참조해 |
| `meshine` | 2D 품질 메시 생성기 |
| `gmshio` | Gmsh 실행기와 MSH 판독기 |
| `physmat` | 재료 및 광학 분산 |
| `simcase` | 모델 문서, 헤드리스 실행기, 선택적 브라우저 스튜디오 |

```bash
pip install openphysics                  # 여섯 패키지, 헤드리스
pip install "openphysics[studio]"        # 로컬 브라우저 Studio 포함
pip install "openphysics[studio,export,rii]"
```

| extra | 추가되는 것 |
|---|---|
| `studio` | `simcase[studio]`: 로컬 브라우저 Studio (FastAPI, Uvicorn) |
| `export` | `simcase[export]`: ParaView용 VTU 내보내기 (meshio) |
| `rii` | `physmat[rii]`: 로컬 refractiveindex.info 데이터베이스 읽기 (PyYAML) |

어떤 extra도 Gmsh를 설치하지 않습니다. `gmshio`는 Gmsh를 별도 프로그램으로 실행하므로,
필요하면 Gmsh 자체 라이선스에 따라 따로 설치하세요(예: `pip install gmsh`).

각 패키지는 따로 설치할 수도 있습니다. 0.1.0 이전 버전(`0.0.1`)은 아무것도 설치하지 않는
빈 이름 예약이었습니다.

소스: https://github.com/fieldalgo/openphysics
