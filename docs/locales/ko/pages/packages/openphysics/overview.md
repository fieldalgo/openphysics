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

**0.0.2는 아직 PyPI에 없습니다.** PyPI에는 빈 `0.0.1` 이름 예약만 있으므로 지금은 아래
명령이 쓸모 있는 것을 설치하지 않으며, pip가 성공이라고 보고할 수도 있습니다. 릴리스 전까지는
[소스 checkout에서 설치](../../overview.md#소스에서-설치)하거나 거기서 만든 wheel로 설치하고, pip가 `0.0.1`을
고르지 않고 거부하도록 버전을 고정하세요(`"openphysics[studio]==0.0.2"`). 아래 명령은
릴리스용입니다.

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
| `sipi` | `sipi`: PCB 단면의 신호·전원 무결성 (추가 의존성 없음) |

어떤 extra도 Gmsh를 설치하지 않습니다. `gmshio`는 Gmsh를 별도 프로그램으로 실행하므로,
필요하면 Gmsh 자체 라이선스에 따라 따로 설치하세요(예: `pip install gmsh`).

각 패키지는 따로 설치할 수도 있습니다. 모든 이름의 `0.0.1`은 아무것도 설치하지 않는
빈 이름 예약이었습니다.

0.x는 알파입니다. Python API는 마이너 버전 사이에 바뀔 수 있습니다. 릴리스마다 바뀐 점과
안정적으로 유지하는 점은 [변경 기록](../../changelog.md)에 있습니다.

소스: https://github.com/fieldalgo/openphysics
